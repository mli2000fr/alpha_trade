# POC Eroya — nouvelles informations directionnelles

## But

Ce POC cherche de l'information signée pour départager LONG et SHORT au sein
du TOP20 Oracle. Il ne modifie ni les tables, ni les modèles, ni la cascade.
Les réponses sont figées sous `artifacts/research/eroya_directional/`.

## Priorités

1. révisions EPS et tendance du consensus;
2. upgrades/downgrades et variations de target price;
3. achats/ventes d'initiés avec timestamp de dépôt;
4. short interest avec retard de publication correctement modélisé;
5. short volume comme contexte, pas comme signal autonome;
6. options et microstructure dans une étude séparée.

Les 13F sont trimestriels et publiés avec retard : ils conviennent davantage à
un régime de propriété qu'à une direction H3/H10. Une chaîne d'options Eroya
est un snapshot courant; sept jours de snapshots ne suffisent pas à valider une
feature. Les trades/quotes tick sont volumineux et ne sont pas collectés par
défaut.

## Étape 0 — droits du trial

```powershell
python -m modelFactory.eroya_directional_poc --mode probe
```

Cette commande demande deux lignes maximum sur un symbole par endpoint. Elle
produit `entitlement_probe.json` avec les codes HTTP et la disponibilité, sans
conserver la clé ni les réponses métier.

## Étape 1 — figer les données du trial

Après validation des droits seulement :

```powershell
python -m modelFactory.eroya_directional_poc --mode collect --symbol-file config/univers/ticket_mid_cap_400.txt --datasets upgrades_downgrades,insider_transactions,short_interest,short_volume,eps_trend,eps_revisions --start-date 2018-01-01 --end-date 2025-12-31
```

Les réponses brutes paginées sont écrites en JSONL gzip, avec date de collecte,
symbole demandé et rapport d'erreurs. `EROYA_API_KEY` est envoyée uniquement
dans l'en-tête Bearer.

## Contrat PIT obligatoire

Une donnée n'entre dans l'évaluation que si son `available_at` est démontré :

- short volume : séance publiée;
- short interest : date de publication, jamais simple settlement date;
- Form 4/insiders : date/heure du dépôt, jamais date de transaction seule;
- analystes : timestamp de l'action ou de la révision;
- 13F : dépôt public, jamais fin de trimestre;
- snapshot courant : interdit dans un backtest historique.

Après normalisation, la jointure impose `available_at <= date de décision`, sans
backward fill antérieur à la disponibilité.

## Évaluation

La population reste le TOP20 Oracle OOF. LONG et SHORT sont mesurés séparément
à H3, H10 et H20 : couverture, probabilités par quantile, IC/AUC, rendement
signé par date, Walk-Forward purgé, comparaison Oracle seul / Oracle + Eroya et
confirmation finale intacte. L'abstention est autorisée.

Une famille sparse comme Form 4 reste un signal événementiel. Elle n'est jamais
imputée à zéro lorsque la couverture du fournisseur est inconnue.

## Implémentation de recherche

- `modelFactory/eroya_directional_poc.py` : probe et collecte brute paginée ;
- `modelFactory/directional_data_research/eroya_features.py` : normalisation,
  contrat PIT et analyse dans Oracle TOP20 ;
- `tests/test_eroya_directional_poc.py` : sécurité de la clé, bornes de dates,
  pagination Eroya/Massive et contrats d'API ;
- `tests/test_eroya_directional_features.py` : décalages PIT, date de mise à
  jour Analyst Insights et détail des IC par fold.

Le collecteur réécrit les `next_url` Massive/Polygon afin qu'ils repassent par
le proxy Eroya. Il retire tout paramètre `apiKey` du lien avant l'appel. Les
endpoints globaux ne sont appelés qu'une fois ; les endpoints par symbole sont
appelés une fois par membre de l'univers. Les identifiants de run possèdent une
précision à la microseconde pour autoriser les collectes parallèles.

## Collectes réalisées sur les 400 mid caps

| Famille | Requêtes | Succès | Observations | Profondeur constatée | Verdict PIT |
|---|---:|---:|---:|---|---|
| short interest | 400 | 400 | 66 463 | 2018-01-12 → 2025-12-31 | publication FINRA requise |
| short volume | 400 | 400 | 187 867 | 2024-02-06 → 2025-12-31 | utiliser au plus tôt à J+1 |
| upgrades/downgrades | 400 | 400 | historique imbriqué | 2012-04-10 → 2026-09-03 | gradeDate + 1 jour prudent |
| insiders agrégés | 400 | 400 | historique imbriqué | 2024-07-29 → 2026-09-02 | non strict, date de dépôt absente |
| Analyst Insights | 400 | 400 | 5 192 | date d'émission 2020–2025 | `last_updated` strict, date d'émission en sensibilité |
| Form 4 brut | 400 | 400 | 239 876 lignes brutes | 2022-01-03 → 2025-12-31 | `filing_date` réel, utilisable à la séance suivante |
| News récent multi-source | 400 | 400 | 39 919 lignes, 37 401 articles uniques | principalement 2026 | snapshot plafonné à 100 articles/symbole, non backtestable historiquement |

Artefacts principaux :

- `eroya-collect-20260905165856` : short interest ;
- `eroya-collect-20260905165858` : short volume ;
- `eroya-collect-20260905170034696938` : upgrades/downgrades ;
- `eroya-collect-20260905170032737879` : insiders agrégés ;
- `eroya-collect-20260905172136718088` : Analyst Insights.
- `eroya-collect-20260905173833752368` : Form 4 historique par symbole.
- `eroya-collect-20260905215559407200` : snapshot News multi-source.

FINRA publie le short interest selon un calendrier distinct de la date de
settlement. Le POC joint les lignes Eroya au `publication_date` du calendrier
FINRA local et refuse les settlements sans correspondance officielle. Voir le
[calendrier FINRA](https://www.finra.org/filing-reporting/regulatory-filing-systems/short-interest).

## Features testées

### Short volume

- ratio J-1 ;
- moyennes 5 et 20 séances ;
- écart au ratio 5 séances ;
- z-score 60 séances ;
- part exemptée.

La valeur du jour J est interdite : la jointure `merge_asof` n'autorise pas une
égalité de date et limite l'âge à cinq jours calendaires.

### Short interest

- variation depuis la publication précédente ;
- short interest / volume quotidien moyen ;
- days-to-cover.

L'âge maximal d'une publication fusionnée est 45 jours.

### Analystes

- somme signée upgrades moins downgrades sur 30/90 jours ;
- nombre d'actions ;
- part nette signée ;
- jours depuis la dernière action ;
- dernière variation de target price par firme.

Pour Analyst Insights, les ratings structurés sont convertis en polarité
positive/neutre/négative. Le champ texte `insight` est volontairement exclu de
ce premier POC afin de limiter le surapprentissage.

### Insiders

Les codes achats/ventes sont analysés séparément. L'endpoint agrégé ne donnant
que la date de transaction, un décalage de deux jours ouvrés est testé comme
sensibilité mais jamais qualifié de PIT. La SEC impose généralement un dépôt
Form 4 au plus tard deux jours ouvrés après la transaction ; cela ne permet pas
de deviner le vrai jour de dépôt. Voir les [instructions officielles Form 4](https://www.sec.gov/files/form4.pdf).

### Form 4 strict

La collecte historique fournit cette fois `filing_date`. Après déduplication au
niveau transaction et exclusion des opérations administratives, le corpus
contient 41 399 transactions directionnelles sur 376 symboles :

- 4 206 achats au marché de code `P`, répartis sur 291 symboles ;
- 37 193 ventes au marché de code `S`, réparties sur 365 symboles ;
- 11 682 transactions déclarées comme liées à un plan 10b5-1 ;
- 29 717 transactions hors 10b5-1.

Les codes `A`, `M`, `F`, `C`, `G`, `D`, etc. sont exclus : une attribution, un
exercice, une retenue fiscale ou un cadeau n'est pas assimilé à une décision
d'achat/vente au marché. Comme l'heure de dépôt est absente, une déclaration du
jour J n'est utilisable qu'à partir du prochain jour ouvré.

Features évaluées dans le TOP20 Oracle :

- compte net et valeur nette sur 30 et 90 jours ;
- nombres séparés d'achats et de ventes sur 90 jours ;
- part de la valeur correspondant aux achats ;
- variantes hors plans 10b5-1 ;
- comptes nets spécifiques dirigeants et administrateurs ;
- nombre de jours depuis le dernier dépôt pertinent.

Deux politiques explicites complètent les rangs quotidiens : signe positif
contre signe négatif, et « achat(s) sans aucune vente » contre « vente(s) sans
aucun achat ». Cette précaution est indispensable, car les nombreuses valeurs
nulles/ex aequo rendent un simple top/bottom 20 % ambigu.

## Résultats H3/H10/H20 — batch `model-factory-20260904192500-0802c8`

Population H20 : 68 660 événements Oracle TOP20, 883 dates et 220 symboles sur
2022–2025. Les features sont évaluées globalement, par fold et par rang
cross-sectionnel quotidien. Un tri top/bottom doit contenir au moins 100
observations ; cette règle empêche un événement très rare de produire un lift
artificiel.

### Familles strictes

Aucune feature short/analyste historique ne franchit un gate raisonnable de
déploiement :

- AUC directionnelles globales comprises approximativement entre 0,48 et 0,507 ;
- changement de signe fréquent entre folds ;
- aucun lift SHORT robuste ;
- `short_exempt_ratio` est le meilleur signal LONG apparent à H20
  (+0,78 point de rendement dans son quintile haut), mais seulement sur
  2024–2025, avec 39 % de couverture, et son effet diminue fortement en 2025 ;
- short interest / ADV et days-to-cover atteignent environ 0,5065 d'AUC globale,
  mais deviennent défavorables en 2025.

Verdict : **ne pas injecter ces features dans les profils LONG/SHORT actuels**.

### Analyst Insights

Le mode strict utilise `max(date, last_updated)`. Or les 5 192 événements
historiques ont des `last_updated` compris seulement entre octobre 2024 et
décembre 2025. Dans la fenêtre OOF, cela ne laisse que 34 événements utilisables
et 19 sélections : échantillon insuffisant. Les lifts stricts issus de ces rares
lignes sont neutralisés par le gate de support minimal.

La sensibilité utilisant `date d'émission + 1 jour` révèle toutefois une piste
contrariante sur la variation du target price :

| Horizon | AUC brute | Lift LONG si orientation inversée | Lift SHORT si orientation inversée |
|---|---:|---:|---:|
| H3 | 0,4920 | +0,20 point | +0,11 point |
| H10 | 0,4786 | +0,78 point | +0,59 point |
| H20 | 0,4682 | +1,68 point | +0,99 point |

L'IC reste négatif sur 2023, 2024 et 2025. L'interprétation plausible est que
les changements de target price suivent partiellement un mouvement déjà
consommé : dans le pool extrême, une forte révision haussière peut être un
signal de retard plutôt qu'une continuation.

Ce résultat est **une candidate à confirmer, pas une feature validée**. Il faut
obtenir une preuve que le `price_target` attaché à chaque ancienne date n'a pas
été révisé a posteriori, ou reconstruire la série depuis des événements
immuables horodatés.

### Résultats Form 4 PIT

Le signal est horizon-dépendant. Les chiffres suivants utilisent des règles
explicites et comparent leur PnL moyen au PnL moyen de tout le pool Oracle TOP20.

| Règle LONG | H3 : PnL / lift | H10 : PnL / lift | H20 : PnL / lift | Support |
|---|---:|---:|---:|---:|
| compte net 90j > 0 | +0,60 % / +0,30 pt | +1,72 % / +0,78 pt | +3,72 % / +1,84 pt | 7 109 |
| valeur nette 90j > 0 | +0,63 % / +0,32 pt | +1,90 % / +0,96 pt | +3,87 % / +1,99 pt | 7 982 |
| compte net dirigeant 90j > 0 | +0,62 % / +0,31 pt | +1,70 % / +0,77 pt | +3,80 % / +1,92 pt | 4 079 |
| achat présent et aucune vente sur 90j | **+0,76 % / +0,45 pt** | **+2,01 % / +1,08 pt** | **+4,08 % / +2,20 pt** | 4 899 |

La dernière règle couvre 7,14 % du pool. À H20, sa précision D8–D10 atteint
40,99 %, contre 38,28 % dans le pool comparable, soit +2,71 points.

Son lift de rendement H20 est positif sur chaque fold temporel disponible :

| Fold | Support | Lift rendement H20 |
|---|---:|---:|
| 2022 | 1 091 | +1,83 pt |
| 2023 | 1 448 | +3,70 pt |
| 2024 | 1 422 | +0,86 pt |
| 2025 partiel | 938 | +1,97 pt |

Le corpus Oracle OOF utilisé contient 68 660 observations, 883 dates et 220
symboles. Il s'arrête au **11 juillet 2025** : le fold 2025 n'est donc pas une
année complète.

Pour SHORT, le classement s'améliore relativement à un short aveugle sur tout
le pool Oracle, mais le rendement signé reste négatif. Par exemple, la règle
« vente sans achat sur 90 jours » produit à H20 un PnL SHORT moyen de -0,80 %.
Son lift de +1,09 point signifie seulement qu'elle perd moins que le benchmark
SHORT du pool ; ce n'est pas une stratégie rentable. **Form 4 ne valide donc
pas encore une feature ou un gate SHORT.**

Conclusion Form 4 : la famille mérite une expérience incrémentale côté LONG à
H10/H20, en priorité avec la règle exclusive achat sans vente et les valeurs
nettes 90 jours. Elle ne doit pas encore être ajoutée directement à
`long.json` : il faut d'abord entraîner/évaluer le modèle avec et sans ces
features sur des folds Walk-Forward identiques, puis confirmer sur une période
temporelle intacte. Aucune conclusion SHORT positive n'est établie.

#### Ablation modèle LONG : baseline contre baseline + Form 4

L'ablation incrémentale a ensuite été exécutée sur la couverture commune
2022-01-04–2025-07-11. Chaque variante reçoit les mêmes lignes, les mêmes quatre
folds et les mêmes 84 features de base. La variante enrichie ajoute dix agrégats
Form 4 PIT : comptes et valeurs nettes signées, versions hors 10b5-1, rôles
officer/director, achat exclusif, activité, part de valeur acheteuse et récence.

| Horizon | Mesure | Baseline | + Form 4 | Delta |
|---|---|---:|---:|---:|
| H10 | AUC LONG | 0,5113 | 0,5207 | +0,0093 |
| H10 | précision top 10 %, rendement >= 3 % | 39,06 % | 39,93 % | +0,87 pt |
| H10 | rendement moyen top 10 % | 1,351 % | 1,216 % | **-0,134 pt** |
| H20 | AUC LONG | 0,4963 | 0,4823 | **-0,0140** |
| H20 | précision top 10 %, rendement >= 3 % | 45,46 % | 45,19 % | -0,27 pt |
| H20 | rendement moyen top 10 % | 3,460 % | 3,464 % | +0,004 pt |

Aucun horizon ne passe les gates préfixés. À H10, le rendement ne progresse que
sur un fold sur quatre ; à H20, deux folds sur quatre. L'amélioration H10 de
classification ne se traduit donc pas en magnitude de rendement, tandis que
H20 dégrade l'AUC sans gain économique matériel. **Le bloc Form 4 ne doit pas
être ajouté au modèle LONG.**

Un diagnostic secondaire a testé le gate « baseline top 10 % ET au moins un
achat P sans vente S sur 90 jours ». À H20, il affiche 4,068 % de rendement
moyen contre 3,460 % pour la baseline. Cette apparence n'est pas une confirmation
robuste : seulement 396 lignes, 35 symboles, 20,2 % des lignes sur MBLY et
74,5 % sur les dix symboles les plus fréquents. Les fenêtres de 90 jours et les
rendements H20 se chevauchent en outre fortement. Le résultat trimestriel change
de signe, notamment négatif en 2024Q3 et 2025Q1.

Décision finale de développement : Form 4 reste une hypothèse prospective H20,
à mesurer sur de nouvelles publications et de nouveaux symboles. Il n'est ni
feature, ni bonus, ni gate de production validé par cette campagne. Les rapports
sont sous `form4-model-ablation-20260906-v2-h{10,20}-0802c8` et le diagnostic
de gate sous `form4-gate-diagnostic-20260906.csv`.

### News multi-source Eroya versus sentiment existant

L'application possède déjà une chaîne plus complète que le simple endpoint
Eroya : ingestion Alpaca/EODHD, alignement sur la séance effective, mapping et
pertinence article–symbole, FinBERT global et FinBERT contextualisé, puis
agrégations 1/3/5/10/20 jours. Eroya n'est donc intéressant que pour sa
couverture éditoriale supplémentaire ou ses propres `insights` contextualisés.

Le snapshot des 400 symboles contient 39 919 lignes et 37 401 articles uniques.
La médiane atteint le plafond de 100 articles par symbole. La source fusionne
notamment Yahoo/Longbridge, Zacks, StockStory, Simply Wall St., Motley Fool,
MarketBeat, GlobeNewswire et Benzinga.

Sur la période commune janvier–juin 2026 :

- 12 449 articles Eroya uniques contre 359 561 lignes EODHD locales ;
- 55,75 % des URL Eroya sont déjà présentes dans le corpus local ;
- 64,65 % des titres sont déjà présents ;
- 32,25 % sont nouveaux simultanément par URL et titre normalisés.

La nouveauté apparente récente doit être relativisée : 24 346 articles Eroya,
soit 65,09 % du snapshot, sont postérieurs au dernier article EODHD local du
1er juillet 2026. Ils comblent donc d'abord un retard d'ingestion locale ; ils
ne prouvent pas tous une supériorité structurelle de couverture.

Les `insights` Eroya sont différents d'un score article global : chaque entrée
porte un ticker, une polarité et une justification. Leur couverture reste trop
faible pour une étude historique :

- 1 271 articles uniques avec au moins un insight pertinent pour le ticker ;
- 3,40 % seulement des 37 401 articles ;
- 1 382 annotations pertinentes et 4 062 annotations tous tickers confondus ;
- 82 articles annotés seulement en 2024–2025, contre 1 189 en 2026.

L'endpoint ne possède ni filtre historique ni pagination au-delà des 100
articles courants par symbole. Les rares articles anciens proviennent surtout
de symboles peu médiatisés et constituent un échantillon manquant non aléatoire.
Ils ne doivent pas être utilisés pour prétendre à une validation OOS.

Verdict News : **snapshot utile et contenu partiellement nouveau, mais aucune
preuve directionnelle supplémentaire à ce stade**. Une vraie validation
demanderait soit un backfill historique immuable plus profond, soit une collecte
prospective maintenue assez longtemps pour observer H10/H20. Sept jours d'essai
ne suffisent pas à cette dernière option.

### Résultats trimestriels et surprises EPS

Deux collectes de 400 symboles ont été réalisées : `earnings_dates` et
`earnings_estimates`. La première est saine : 29 269 événements Earnings sur
396 symboles, dont 29 006 avec consensus, 28 992 avec EPS réalisé et 28 944 avec
surprise. La couverture est dense sur 2016–2025.

L'heure ne peut toutefois pas être considérée exacte sur tout l'historique :
14 991 événements sont horodatés exactement à minuit New York. Le contrat PIT
du POC rend donc estimation, réalisé et surprise disponibles uniquement au
**premier jour ouvré suivant** l'événement. Cette convention conservatrice
interdit toute utilisation le jour de publication, y compris lorsque l'heure
semble indiquer une annonce pré-market.

Le POC évalue H3/H10/H20 dans Oracle TOP20 avec : surprise signée et transformée,
fenêtres de fraîcheur 5/20/60 jours, puis règles LONG/SHORT aux seuils absolus
0/5/10/25 points de surprise. Les résultats globaux et par année sont écrits
dans `earnings_signed_rules.csv` ; les classements génériques et leur stabilité
se trouvent dans `earnings_separability.csv` et `earnings_policy_by_fold.csv`.

Résultat : **la surprise EPS brute est rejetée comme signal directionnel autonome
dans Oracle TOP20**. Le pool évalué contient 68 660 observations, 883 dates et
220 symboles ; bien que la borne demandée soit fin 2025, l'artefact Oracle OOF
s'arrête au 11 juillet 2025.

| Lecture | H3 | H10 | H20 |
|---|---:|---:|---:|
| AUC quotidienne, surprise connue <= 5j | 0,493 | 0,490 | 0,487 |
| LONG, surprise positive <= 5j : PnL moyen | +0,346 % | +0,356 % | +1,628 % |
| LONG, même règle : lift contre Oracle TOP20 | +0,042 pt | -0,581 pt | -0,256 pt |
| SHORT, surprise négative <= 20j, seuil 10 % : PnL moyen | -0,260 % | -0,787 % | -0,757 % |

Le faible lift LONG H3 n'est pas stable : +1,10 point en 2022, -0,66 point en
2023, environ zéro en 2024 et -0,31 point en 2025 partiel. À H10 et H20, toutes
les règles LONG simples sous-performent globalement le pool Oracle. Les règles
SHORT restent perdantes en rendement signé, même lorsque leur lift relatif est
positif. Cela signifie seulement qu'elles perdent parfois moins qu'un short
aveugle dans un pool haussier, pas qu'elles possèdent une espérance positive.

L'inversion du signe n'offre pas non plus une stratégie convaincante : les
surprises négatives continuent en moyenne à produire des rendements actions
positifs, mais inférieurs au drift moyen du pool ; vendre les surprises positives
revient symétriquement à shorter un rendement encore positif. Le résultat est
compatible avec une information déjà incorporée dans le gap/rendement initial,
un contexte d'anticipations absent de la surprise brute, et un fort biais
haussier du pool Oracle — pas avec une règle directionnelle exploitable.

Les artefacts reproductibles sont dans
`artifacts/research/eroya_directional/earnings-evaluation-20260906-h{3,10,20}-0802c8`.
Ils ne justifient aucune modification de `long.json`, `short.json` ou de la
cascade.

La seconde source, `earnings_estimates`, est **écartée** : 392 intervalles se
terminent avant leur début, 526 durent plus de deux ans et 9 337 paires
successives se chevauchent. Surtout, les lignes n'identifient pas clairement la
période fiscale cible. Assimiler leurs dates à des intervalles de validité
créerait un risque de mélange entre horizons et de fuite temporelle.

### Dépôts 8-K structurés

La collecte complète `form8k_400/eroya-collect-20260906000547789822` a réussi
pour les 400 symboles demandés, sans erreur HTTP. Après déduplication entre les
requêtes, elle contient 24 240 disclosures uniques, datées du 2 janvier 2020 au
31 décembre 2025. La couverture du référentiel Oracle atteint 377 symboles sur
399, soit 94,49 %. Les 22 absents sont principalement des émetteurs étrangers
qui ne déposent pas de 8-K auprès de la SEC.

Un disclosure fournit le ticker, l'accession SEC, la date de dépôt, trois
niveaux de catégories structurées, un texte justificatif et l'URL du dépôt.
L'heure de publication n'étant pas fournie, le contrat PIT est conservateur :
**disponibilité au premier jour ouvré suivant la date de dépôt**, jamais le jour
même. Les catégories ont été regroupées avant lecture des rendements en huit
familles : distress, incidents opérationnels, juridique/réglementaire,
dilution/financement, départs et nominations de dirigeants, retour aux
actionnaires et événements commerciaux positifs. Les comptes sont calculés sur
5, 20 et 60 jours calendaires.

Les évaluations H3/H10/H20 portent sur le même pool Oracle TOP20 : 68 660
observations, 220 symboles et 883 dates. La période demandée finit en décembre
2025, mais l'OOF réellement disponible dans le batch s'arrête au 11 juillet
2025. Les fichiers sont sous
`8k-evaluation-20260906-h{3,10,20}-0802c8`.

La première lecture ligne par ligne produit plusieurs effets apparemment forts :

| Signal et politique | Lignes / symboles | PnL moyen | Lift contre Oracle des mêmes dates |
|---|---:|---:|---:|
| H3, dilution/financement <= 5j, SHORT | 308 / 35 | +1,254 % | +1,279 pt |
| H10, dette émise <= 20j, SHORT | 812 / 40 | +1,276 % | +1,958 pt |
| H20, incident opérationnel <= 20j, SHORT | 739 / 40 | +1,980 % | +4,006 pt |
| H20, départ du CFO <= 20j, SHORT | 906 / 57 | +1,532 % | +2,787 pt |

Cette lecture n'est toutefois pas une unité statistique valide : un même dépôt
alimente plusieurs journées Oracle consécutives, tandis que les rendements futurs
se chevauchent. Un second audit retient donc uniquement la **première date Oracle
éligible par accession et symbole**.

| Signal et politique | Entrées événementielles | PnL moyen | Stabilité annuelle |
|---|---:|---:|---|
| H3, dilution/financement <= 5j, SHORT | 89 / 35 symboles | +0,91 % | négatif en 2022 et 2025 partiel |
| H10, dette émise <= 20j, SHORT | 101 / 40 | +0,12 % | négatif en 2024 et 2025 partiel |
| H20, incident opérationnel <= 20j, SHORT | 63 / 40 | +0,03 % | négatif en 2023 et 2024 |
| H20, départ du CFO <= 20j, SHORT | 76 / 57 | +0,73 % | négatif en 2024 |

La concentration confirme la fragilité. QXO représente 68,6 % du PnL cumulé
du signal dilution H3 dans la lecture quotidienne ; SMMT représente 68,1 % du
signal dette H10 et plus de 100 % du signal dette H20. Après retrait a posteriori
des cinq meilleurs contributeurs, le PnL moyen devient négatif pour presque tous
les candidats. Le signal exploratoire `private_placement` atteint +4,79 % à H3,
mais ne correspond qu'à 14 premières entrées sur neuf symboles et provient d'un
scan multi-catégories : il ne constitue pas une confirmation.

Verdict 8-K : **les catégories structurées contiennent de l'information, mais
aucune règle directionnelle autonome n'est assez stable pour la production**.
Elles ne doivent devenir ni gate, ni bonus de score, ni modification de
`long.json`/`short.json`. Une éventuelle dernière expérience doit être une
ablation incrémentale pré-enregistrée des 24 comptes de familles dans un modèle,
avec déduplication événementielle, contrôle de concentration par symbole et
validation sur de nouvelles données. Le scan des catégories tertiaires reste
strictement exploratoire.

## Options, trades/quotes et 13F

- le snapshot Options est courant : impossible de valider H20 avec sept jours
  d'essai ;
- les archives Options daily sont accessibles mais sont des fichiers de marché
  complet, potentiellement très volumineux ;
- les trades/quotes tick sont encore plus lourds et ne constituent pas le
  premier POC raisonnable pour un modèle quotidien ;
- les 13F sont accessibles mais trimestriels et retardés : priorité faible pour
  une direction H3/H10/H20.

La documentation Eroya confirme l'historique des contrats/bars/ticks Options et
les archives quotidiennes disponibles via flat files :
[catalogue officiel Eroya](https://docs.eroya.co/llms.txt).

## Décision actuelle

1. conserver toutes les collectes comme artefacts de recherche reproductibles ;
2. ne modifier ni `long.json`, ni `short.json`, ni la cascade ;
3. considérer l'ablation Form 4 comme rejetée : elle n'améliore pas conjointement
   discrimination, rendement et stabilité Walk-Forward ;
4. considérer la surprise EPS brute comme rejetée pour la direction dans Oracle
   TOP20 ;
5. ne pas interpréter le snapshot News comme une validation historique ; seule
   une collecte prospective ou un backfill immuable plus profond permettrait de
   rouvrir cette piste ;
6. ne pas transformer les catégories 8-K en règles de trading : les résultats
   quotidiens sont gonflés par les répétitions et concentrés sur quelques
   symboles ;
7. si la piste 8-K est poursuivie, limiter l'étape suivante à une ablation modèle
   pré-enregistrée, puis exiger un nouvel OOS ou une collecte prospective avant
   toute intégration ;
8. à ce stade, la campagne Eroya n'a validé aucune nouvelle feature
   directionnelle de production pour distinguer D1 de D10 après Oracle TOP20.
