# Oracle parcours H20 — campagnes de suivi H5/H10/H15/H20

## Objet et statut initial

GO utilisateur du 20 octobre 2026 : tester la gestion séquentielle d'une même
sélection Oracle, sans choisir la direction à J ni réentraîner un modèle.
Protocole figé avant extraction des prix de ce test. **Résultats complétés en
fin de document après les contrôles ; pas de stratégie promue au lancement.**

Cette expérience ne remplace ni l'Oracle ni les protections de production.
Ce n'est pas une nouvelle optimisation des anciens TP/SL ou du retour à la
moyenne intraday, et ce n'est pas une reproduction d'un fonds professionnel.

## Sélection et durée

- Même Oracle **PATH_H20**, mêmes TOP10 à J pour chaque bras, scores de recherche
  CatBoost OOS annuels déjà figés sous
  `artifacts/research/us_h10_h20_frozen_comparison/20261019-v1`.
- Pas le champion LightGBM live, pas les rangs H10, pas une prédiction de sens.
- 6 690 lignes TOP10 originales, 2024 au 1er septembre 2026 ; pas de remplacement
  du rang dont les prix manquent. Univers tradable actuel, biais de survivants.
- Admission au premier J disponible par titre, puis blocage pendant **vingt
  séances pour tous les horizons**, avant examen de la qualité future. J+20
  peut redevenir un signal, dont la première entrée serait J+21. Pas de remise
  à zéro annuelle ni réarmement anticipé grâce à un H5 plus court.
- **673 campagnes admises** : 255 en 2024, 248 en 2025, 170 en 2026.
- Une campagne H dure **J+1 à J+H**, attente comprise. Une seconde entrée ne
  redémarre jamais le compteur. Une campagne sans signal garde un résultat nul ;
  une campagne aux données non qualifiées reste inconnue et n'est pas nulle.
- Expiration à l'ouverture de la dernière barre 5m de J+H : 15:55 New York
  normalement, 12:55 en demi-séance. Pas de fill fictif à la clôture ou d'entrée
  simultanée à l'expiration.

Les tests principaux emploient une **cohorte commune entièrement qualifiée
jusqu'à H20**, même pour H5. Cela empêche de comparer quatre ensembles différents,
mais conditionne la recherche à une couverture complète de vingt séances :
biais de sélection explicite. L'expiration d'un portefeuille ayant laissé courir
des positions au-delà de H20 serait un autre contrat.

## Entrée et seconde tentative

Référence : plus haut/bas de la **séance précédente complète**, reconstitués
dans les barres intraday SIP brutes. Pas de seuil daily ajusté appliqué à du raw.

1. Deux clôtures 5m consécutives au-dessus du haut précédent donnent LONG ;
   deux sous le bas précédent donnent SHORT.
2. La clôture précédant ces deux barres doit être à l'intérieur ou au contact
   de la borne concernée : nouvelle cassure, pas répétition d'un dépassement.
   Pour les deux premières barres de séance, la clôture précédente sert de
   clôture antérieure. Une seule barre à l'ouverture ne confirme rien.
3. Entrée à l'open de la barre suivante, contiguë dans la même séance. Jamais
   dans la barre donnant le signal, jamais une pending réinterprétée au lendemain.
4. Après sortie, une seconde entrée exige **deux nouvelles barres de confirmation
   commençant après la barre de sortie**, et une nouvelle cassure. Elle peut
   être du même sens ou du sens opposé. Pas de retournement automatique au stop.
5. Une seule position par campagne, pas de renforcement ou moyenne à la baisse.

Deux univers d'actions possibles sont prévus avant résultats : `BOTH`
(LONG/SHORT, SHORT hypothétique) et `LONG_ONLY` (ne considère que les nouvelles
cassures LONG, sans transformer une cassure SHORT en achat).

## Protections communes, non optimisées sur ces résultats

- Stop initial **5 %** du prix d'entrée.
- Trailing **15 %** du high favorable LONG ou du low favorable SHORT, non TP fixe.
- Trailing mis à jour seulement aux bornes 5m à partir des **barres terminées**.
  Le high/low favorable de la barre courante ne peut pas resserrer rétroactivement
  le stop à l'intérieur de cette barre. C'est un suivi discret, **pas la parité
  d'un ordre trailing natif surveillé tick par tick**.
- Gap défavorable : sortie au prix d'ouverture, perte non plafonnée au stop.
- À l'expiration, seule l'ouverture de la dernière barre est lue, pas son
  high/low ou sa clôture futurs.

Les valeurs 5 % / 15 % sont un contrat de départ figé, pas un optimum démontré.
Le test ne balaie pas aussi des combinaisons de stops et de seuils d'entrée.

## Budget commun et témoin de sizing

Allocation **hypothétique indépendante de 1 000 USD par campagne**, sans levier,
capital non partagé entre les titres ; ce n'est pas le montant du compte réel.
Budget maximal de perte **planifiée** : 2 % de cette allocation, soit 20 USD.

| Profil | Tentatives exécutées maximum | Risque planifié par tentative | Rôle |
|---|---:|---:|---|
| ONE_FULL | 1 | Jusqu'à 20 USD | Témoin au budget complet |
| TWO_SPLIT | 2 | Jusqu'à 10 USD chacune | Seconde tentative, même plafond de campagne |
| ONE_HALF_CONTROL | 1 | Jusqu'à 10 USD | Même première taille que TWO_SPLIT, isole la réentrée |

Quantités en actions entières ; notionnel limité à l'equity positive courante.
Le dénominateur de risque réserve le stop, deux jambes de frais conservatrices
et, pour SHORT, l'emprunt sur le reste de la fenêtre commune H20. La même réserve
H20 s'applique aux quatre horizons pour ne pas changer la première quantité
SHORT uniquement parce que H5 est plus court.

Seconde taille : budget disponible au plus 10 USD et au plus 20 USD moins la
somme des pertes nettes déjà réalisées. Les gains ne rechargent pas le budget.
Un gap peut consommer plus de 20 USD : la deuxième entrée sera alors bloquée,
mais cela **ne garantit pas** une perte maximale réelle de 2 %.

Si le premier signal admissible ne permet pas d'acheter une action entière,
abstention de ce profil, sans chercher après coup un prix plus bas permettant
un fill. La granularité des actions et de l'allocation peut différencier les
bras : le témoin ONE_HALF_CONTROL aide à l'identifier.

## Coûts, lecture des chiffres et contrôle statistique

- 8 bps par jambe sur le notionnel effectivement exécuté, sans commission fixe
  supplémentaire : hypothèse globale spread/slippage/frais, pas tarif réel
  Alpaca historiquement prouvé.
- Emprunt SHORT hypothétique de 0,3 % annuel, jours calendaires/365, un jour
  minimum. Aucun locate, recall, dividende compensatoire ou disponibilité
  historique short certifié ; résultats SHORT de recherche uniquement.
- Stress 25 bps/jambe **sur les mêmes quantités et fills**. Décomposition
  comptable, pas nouvelle simulation des gardes de budget à ce tarif stressé.
- Ledger indépendant par campagne, equity = capital + PnL réalisé + PnL signé
  de la position ouverte, frais/emprunt inclus.
- Rendement par campagne = PnL net / 1 000 USD ; ne pas confondre avec le
  rendement notionnel par trade. Les campagnes sans entrée font partie de la
  moyenne ; la moyenne des seules campagnes actives est aussi conservée.
- Drawdown calculé aux clôtures 5m et fills d'une campagne, pas drawdown intratick
  ou drawdown annuel d'un portefeuille à capital partagé. Les PnL de campagnes
  qui se chevauchent entre titres ne doivent pas être additionnés comme un compte.

Contraste principal figé : **H20 BOTH, TWO_SPLIT moins ONE_FULL**. Autres H et
LONG_ONLY sont secondaires. SECOND contre ONE_HALF_CONTROL mesure directement
le PnL ajouté par la nouvelle tentative, à première position identique.

Bootstrap apparié par blocs de vingt séances, 1 999 tirages, seed fixe 20261020,
intervalles 95 % et correction huit comparaisons direction×horizon, IC99,375 %.
Cette correction est par famille de contrôle et année ; elle ne corrige pas
l'ensemble des expériences déjà examinées dans le projet.
Il n'est pas permis de retenir le meilleur horizon de chaque année après
observation. 2025/2026 ont déjà été examinées dans d'autres études et 2024 est
sans SIP intraday : **pas de vraie période vierge pour sélectionner un champion**.
Un éventuel résultat favorable restera exploratoire, sans promotion automatique.

## Qualité et archives

Racine : `artifacts/research/us_oracle_campaign/20261020-v1`.

Barres SQL existantes exclusivement `alpaca / alpaca_sip / 5m / raw / regular /
US_EQ`, volume positif, OHLC cohérents, aucune barre remplie ou doublonnée,
grilles complètes suivant calendrier NYSE réel. Extraction dans une transaction
REPEATABLE READ / READ ONLY, terminée par ROLLBACK. Aucun téléchargement.

Contrôle de la référence daily : une échelle constante est admise sur les quatre
OHLC des 21 séances ; dispersion des ratios <=1 %. Les réserves de prix et les
ruptures d'identité du parent restent exclues, sans inventer de correction de
split ou de nouveau symbole. Un trou après une sortie potentiellement gagnante
réserve quand même la campagne commune, pour ne pas qualifier selon son gain.

`protocol.json` scelle règles et sources ; `selected.parquet` garde les 6 690
signaux avec admission avant prix ; `snapshot-ready.json` scelle les fichiers
bruts, `coverage.parquet` les inconnus, `campaigns.parquet` les 24 bras par
campagne qualifiée, `trades.parquet` chaque fill/sizing/protection/coût.
`summary.csv` et `comparisons.csv` contiennent les tableaux par année et horizon.

```powershell
python -u -m scripts.research.us_oracle_campaign --phase prepare --output artifacts/research/us_oracle_campaign/20261020-v1
python -u -m scripts.research.us_oracle_campaign --phase snapshot --output artifacts/research/us_oracle_campaign/20261020-v1
python -u -m scripts.research.us_oracle_campaign --phase replay --output artifacts/research/us_oracle_campaign/20261020-v1
python -u -m scripts.research.us_oracle_campaign_audit --output artifacts/research/us_oracle_campaign/20261020-v1
```

Une extraction interrompue demande un nouveau dossier ; pas de fusion silencieuse
de deux états de la base. Les scripts/reférences scellés ne sont pas réécrits.
**17 tests** initiaux passent, dont comparaison sur 200 chemins aléatoires des
stops/trailing calculés par deux formules. Audit final par le même assistant,
pas seconde revue humaine indépendante. Aucun modèle, batch, compte, paramètre
de trading ou univers modifié.

## Bilan

### Statut final : test terminé, aucune promotion

Audit `PASS_EXPLORATORY_CAMPAIGN_AUDIT`, **4 983 trades simulés** et **5 112 bras
de campagne** revérifiés par calcul séparé des signaux, du trailing, des
quantités, du budget et du ledger. Ce sont **213 campagnes distinctes**, pas
5 112 observations indépendantes. Les premières positions TWO_SPLIT et
ONE_HALF_CONTROL sont identiques, vérifiées fill par fill.

Verdict principal : **NO_STABLE_PRIMARY_REENTRY_ADVANTAGE**. Pas de sélection
d'un meilleur horizon, de nouvelle optimisation ou d'activation PAPER/LIVE.
Le LONG simple positif mérite un constat séparé, mais n'est pas une confirmation
de rentabilité robuste ni de prédiction D1/D10 par un nouveau modèle.

### Couverture

Extraction existante : **662 873 barres**, transaction unique le 20 octobre
2026 de 21:47:56 à 21:48:18 Paris, 232 parties symbole/année. Pas d'appel
fournisseur, d'achat, de modification SQL ou de nouveau backfill.

| Année du signal J | Lignes TOP10 originales | Campagnes admises sans chevauchement | Campagnes qualifiées communes aux quatre H | Grille incomplète | Désaccord prix/base daily | Séance absente |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | 2 520 | 255 | **0** | 0 | 0 | 255 |
| 2025 | 2 500 | 248 | **119** | 105 | 17 | 7 |
| 2026 | 1 670 | 170 | **94** | 48 | 27 | 1 |

2025 : 98 dates de signal qualifiées, 48 titres, du 3 janvier au 29 décembre.
2026 : 74 dates, 33 titres, du 2 janvier au **1er septembre**, prix de suivi
jusqu'au 30 septembre. Les signaux de décembre 2025 peuvent sortir en janvier
2026 : attribution par année du **signal**, pas comptabilité de PnL annuel.
2024 est non testable ici, pas nulle. Taux de qualification 47,98 % / 55,29 %
en 2025/2026 : résultats conditionnels, pas totalité du TOP10.

### Comparaison des horizons : LONG seul, une tentative au budget complet

Moyenne nette divisée par l'allocation de **1 000 USD par campagne**, y compris
abstentions ; **aucun de ces pourcentages n'est un rendement annuel de compte**.

| H | 2025 net moyen | 2026 net moyen | 2025 stress 25 bps | 2026 stress 25 bps |
|---|---:|---:|---:|---:|
| H5 | −0,303 % | +0,213 % | −0,412 % | +0,129 % |
| H10 | **+0,105 %** | **+0,480 %** | −0,019 % | +0,391 % |
| H15 | **+0,383 %** | **+0,495 %** | +0,257 % | +0,406 % |
| H20 | **+0,658 %** | **+0,670 %** | +0,532 % | +0,581 % |

H20 ressort positivement dans les deux années, sans avoir été sélectionné
comme nouvel optimum. Les IC95 % restent larges :

- 2025 H20 : **[−0,317 % ; +1,187 %]** ;
- 2026 H20 : **[−0,432 % ; +1,778 %]**.

Ils incluent zéro avant même de corriger l'examen des horizons. On ne peut pas
affirmer un avantage net établi. H10 devient légèrement négatif en 2025 au
stress de coûts. La couverture exclut une part importante des campagnes.

Lecture H20 LONG ONE_FULL :

| Mesure | 2025 | 2026 |
|---|---:|---:|
| Campagnes communes | 119 | 94 |
| Campagnes avec entrée | 118 | 75 |
| Gains / pertes / sans entrée | 39 / 79 / 1 | 24 / 51 / 19 |
| Gagnants parmi campagnes actives | **33,05 %** | **32,00 %** |
| Gain moyen d'une campagne gagnante, sur 1 000 USD | +59,89 USD | +61,86 USD |
| Perte moyenne d'une campagne perdante | −19,65 USD | −16,76 USD |
| Médiane toutes campagnes | −1,894 % | −0,959 % |
| Pire perte de campagne | −5,967 % | −3,553 % |
| Pire DD de campagne aux marks 5m | −10,427 % | −6,795 % |

La moyenne positive ne signifie donc pas un taux de réussite élevé : quelques
grands gains paient de nombreuses petites pertes. Le trailing ne garantit pas
de vendre au sommet, ni de conserver tout le mouvement.

### Risque de concentration — diagnostic, pas filtre à optimiser

Trois meilleures campagnes LONG H20 ONE_FULL :

- 2025 : CLF signal du 24 juin (+208,99 USD), PLTR du 3 janvier (+179,91 USD),
  SNDX du 4 août (+120,35 USD). Elles représentent environ **65,0 %** de la
  somme des résultats des campagnes indépendantes de cette année ;
- 2026 : DOCN du 9 avril (+278,02 USD), TTMI du 1er avril (+160,34 USD), WDC
  du 2 avril (+129,55 USD), environ **90,1 %** de cette somme.

Ces sommes sont un outil d'attribution à allocations indépendantes, pas un
portefeuille ayant réellement financé toutes les entrées. Retirer rétrospectivement
les trois meilleurs ne devient pas une nouvelle stratégie : cela décrit la
fragilité. La moyenne des campagnes restantes tombe à **+0,236 % / +0,068 %**.
La concentration temporelle d'avril 2026 interdit de présenter le LONG H20 comme
transversal à tous les régimes. Les prix ont passé les contrôles internes
SIP/daily existants, pas une nouvelle validation externe exhaustive.

### Effet d'une seconde tentative : comparaison au même plafond de risque

Direction BOTH, moyenne nette par campagne, budget complet ONE_FULL contre
budget partagé TWO_SPLIT :

| H | 2025 une tentative | 2025 deux tentatives | 2026 une tentative | 2026 deux tentatives |
|---|---:|---:|---:|---:|
| H5 | +0,009 % | +0,009 % | −0,132 % | −0,148 % |
| H10 | −0,107 % | +0,101 % | −0,042 % | −0,192 % |
| H15 | +0,047 % | +0,176 % | −0,063 % | −0,300 % |
| H20 | −0,017 % | +0,143 % | −0,141 % | −0,384 % |

Contraste principal H20 : amélioration 2025 **+0,160 point**,
IC95 % [−0,440 ; +0,762] point ; détérioration 2026 **−0,244 point**,
IC95 % [−0,468 ; +0,190] point. Les IC incluent zéro dans les deux années,
de même que les intervalles corrigés pour huit comparaisons. Pas de preuve
d'un avantage stable de réentrée et de sens opposé.

H20 TWO_SPLIT BOTH : 93 secondes tentatives en 2025, dont 61 opposées à la
première ; 53 en 2026, dont 34 opposées. Gagnants parmi campagnes actives :
45,54 % / 18,52 %. Augmenter le nombre d'essais n'assure pas de capter le bon sens.

### Séparer taille et nouvelle tentative

| H20 | 2025 LONG_ONLY | 2026 LONG_ONLY | 2025 BOTH | 2026 BOTH |
|---|---:|---:|---:|---:|
| ONE_FULL | +0,658 % | +0,670 % | −0,017 % | −0,141 % |
| ONE_HALF_CONTROL | +0,286 % | +0,104 % | +0,004 % | −0,225 % |
| TWO_SPLIT | +0,350 % | +0,199 % | +0,143 % | −0,384 % |

En LONG, une deuxième tentative ajoute +0,064 / +0,095 point par rapport à
une seule tentative de même petite taille, mais ses IC incluent zéro. Elle
reste inférieure à ONE_FULL dans les deux années. En BOTH, l'apport de la
seconde tentative s'inverse en 2026. La granularité compte : à 1 000 USD,
actions entières, une demi-taille peut ne plus financer une action chère.
En BOTH H20 2026, 75 campagnes entrent en ONE_FULL contre 54 en TWO_SPLIT ;
ce n'est pas un effet directionnel pur. Les non-entrées restent dans le bilan.

### Le budget 2 % n'est pas une garantie contre les gaps

Exemple le plus sévère : MP, signal du 27 juin 2025, SHORT ONE_FULL entré le
1er juillet à **31,92 USD**, douze actions. Sortie au gap d'ouverture du
10 juillet à **48,10 USD**, et non au stop théorique : **−194,96 USD**,
soit **−19,50 %** de l'allocation indépendante de 1 000 USD. Ce gap reste présent
à H10/H15/H20 ; les lignes répétées dans ces bras ne sont pas plusieurs pertes
distinctes. La demi-taille perd −97,48 USD et ne peut pas engager une seconde
tentative après dépassement du budget. Pas d'écrêtage artificiel à 2 %.

Le LONG seul évite mécaniquement cette position SHORT, mais cela ne prouve pas
qu'un modèle savait prévoir sa hausse. Le contrôle LONG_ONLY était figé avant
les résultats ; on ne transforme pas ce cas isolé en nouveau filtre gagnant.

### Clôture

**Ne pas intégrer la seconde tentative comme amélioration démontrée.** Garder
le LONG simple H10/H15/H20 comme observation exploratoire, H20 positif mais
incertain et concentré. Aucun meilleur horizon ou profil ne peut être déclaré
validé sur ces deux années déjà explorées et cette couverture conditionnelle.

17 tests ciblés passent ; rapport JUnit `test-results.xml`, audit final dans
`final-audit.json`. Aucun entraînement, téléchargement fournisseur, appel LLM,
écriture SQL, ordre, changement de modèle/batch/paramètres de trading. Les
sources, données, règles et résultats sont scellés pour éviter de réécrire
l'expérience en choisissant après coup les combinaisons favorables.
