# Oracle H10 → modèles LONG par symbole → TOP10 → Winner

**Campagne terminée le 3 novembre 2026 : 9/9 simulations, zéro échec technique,
mais les neuf rapports sont `INCOMPLETE_COVERAGE`.**
La présence de modèles entraînés ne prouve aucun avantage. Pas de promotion
dans le pipeline, aucun ordre, appel LLM ou téléchargement fournisseur.

## Demande et protocole

L'utilisateur a choisi l'Oracle H10 du dernier replay Winner :
`model-factory-20261030213826-eda503`. Pour chaque séance, conserver les
**vingt premiers titres Oracle**, les classer avec des modèles LONG propres
à chaque symbole, puis transmettre les dix retenus au risque et à Winner.

Trois comptes simulés indépendants par année, **4 000 USD au départ de chaque
compte**, sans transport du capital d'une année à l'autre :

1. `ORACLE_TOP20` : vingt candidats Oracle, sans filtre directionnel ;
2. `ORACLE_TOP10` : dix premiers au rang Oracle, sans filtre directionnel ;
3. `PER_SYMBOL_TOP10` : dix meilleures probabilités LONG dans le TOP20.

Cela distingue l'effet du classement LONG du simple passage à dix candidats.
Les titres choisis gardent leur priorité Oracle dans le moteur ; le score
directionnel sélectionne, il ne remplace pas le score d'amplitude ni les
budgets de risque. Aucun remplacement par le vingt-et-unième titre.

Périodes : années civiles 2024 et 2025, puis **2026 jusqu'au 29 octobre**,
borne complète de l'archive H10 réutilisée. Le dernier signal est celui de
la séance précédente. Ce n'est pas un test de l'année 2026 complète.

## Winner et risque

Réglages de `config.yaml` figés par empreinte : position complète, pas de
renforcement, SL5 %, aucun TP ni trailing, deux confirmations 5m, dix séances
de détention puis sortie à l'ouverture suivante, validité d'entrée vingt
séances, données retardées de 930 secondes. Quantités entières.

Compte simulé margin, levier autorisé **au maximum 2×**, soumis aux conditions
de la configuration et à la capacité du portefeuille ; ce n'est pas une
promesse d'investissement permanent à 2×. Coûts canoniques et financement
annuel 6,5 % du replay natif. Les 25 bps Winner sont une réserve de sizing,
pas un remplacement des frais comptables. Risque chargé avec le preset
correspondant au capital de 4 000 USD, liquidation de production comprise.

Comme le défaut demandé précédemment dans l'IHM, le facteur de capitalisation
historique est désactivé : aucune capitalisation actuelle substituée. Les
autres contrôles de risque, notamment les facteurs de marché/momentum, restent
natifs. Le filtre options et GPT ne sont pas appliqués : seul le filtre de
modèles demandé doit différencier les variantes.

## Modèles réellement par symbole et actualisés annuellement

Les six modèles de production présents sont des modèles Oracle d'amplitude ;
ils ne fournissent pas un spécialiste LONG exploitable pour cette campagne.
De nouveaux modèles **LightGBM indépendants, par symbole et par année** sont
donc sauvegardés dans le dossier de recherche, sans modifier ModelFactory.

| Test | Année de calibration du spécialiste | Dernier résultat d'apprentissage/calibration autorisé | Modèles exploitables |
|---|---|---|---:|
| 2024 | 2023 | 28 décembre 2023 | 128 |
| 2025 | 2024 | 30 décembre 2024 | 148 |
| 2026 | 2025 | 30 décembre 2025 | 122 |

Le fit utilise les années propres au titre antérieures à la calibration,
depuis 2019 ; la calibration Platt utilise seulement l'année précédente.
Labels matures strictement avant les deux frontières ; la première décision
annuelle est aussi purgée. Les modèles 2024 ne sont pas réutilisés en 2025/26.

Vingt-quatre features causales : rendements, RSI, ADX, volatilité, ATR,
distances/pentes de moyennes, force relative, marché SPY et trois variations
sur cinq séances. Aucun consensus actuel, news révisée, résultat futur ou
rang Oracle interprété comme probabilité LONG. Hyperparamètres fixés avant
les rendements du test : 120 arbres, profondeur3, sept feuilles, pas de
recherche de meilleurs poids sur 2024–2026.

Minimum504 observations de fit et40 de chaque classe,100 de calibration et15
de chaque classe. Calibration propre au titre ; pas de modèle mutualisé de
secours, score neutre inventé ou inversion choisie sur l'année de test.

**Cible d'apprentissage explicitement approchée** : un LONG à l'ouverture
suivante est-il positif net des coûts, avec SL5 et sortie à l'ouverture après
dix séances de détention, sans TP ? Le modèle ne prédit ni le seul closeH20 ni
une direction SHORT. La cible utilise les barres daily et ne reproduit pas
les confirmations d'entrée Winner ; le test économique final, lui, rejoue
réellement ces confirmations en cinq minutes et le délai de930secondes.
Un arrêt touché par un gap est valorisé à l'ouverture défavorable, pas au stop
garanti. Les fenêtres de label manquantes/changement d'identité restent inconnues.

**398 fits sur427 couples symbole/année**, après qualification. Couverture des
candidats : 3941/5040 en2024,4757/5000 en2025,4160/4160 en2026. Toutes les
séances gardent au moins dix probabilités disponibles : minimum12/17/20.
Les absences sont quand même conservées dans les tableaux. La sélection n'impose
pas un seuil supérieur à0,5 : il s'agit des dix relativement plus favorables.

## Reconstruction du TOP20 et réserves historiques

L'ancien run Winner à **+122,38 %** avait effectué des exclusions de titres
sur toute la période pour lacunes intraday. Son fichier `signals.csv` ne
contenait donc plus le TOP20 complet. La nouvelle campagne réunit ce fichier
avec **les23036lignes de `excluded-signals.csv`**, sans lire de rendement pour
les réadmettre. Les1337classements historiques complets sont reconstruits,
vingt symboles distincts par séance, puis le contrat causal Oracle est revérifié.
Les sélections de test contiennent14200couples avant le filtre LONG.

Le replay natif lit les scores SQL, qualifie couverture, modèle et lineage,
puis vérifie l'égalité exacte de ses TOP20 avec la cohorte figée. Une divergence
arrête le compte ; pas de substitution. L'ancien rendement n'est pas réutilisé
comme référence du présent protocole.

Les nouvelles lacunes intraday n'excluent pas un titre sur toute l'année :
elles bloquent seulement les entrées dont la fenêtre signal/détention est
incomplète, de la même manière dans les trois variantes. **Ce contrôle utilise
la disponibilité future des données : c'est une sélection rétrospective de
qualité, pas un filtre tradable.** Les statuts `INCOMPLETE_COVERAGE`, exclusions
et nombres de trades devront accompagner tous les résultats. Aucun rattrapage
Alpaca/Yahoo/EODHD, interpolation ou daily substituée aux barres5m.

Autres limites : univers actuel survivant, secteurs actuels, données historiques
reconstituées plutôt que versions prospectives certifiées, hypothèses d'exécution
OHLC et périodes déjà vues dans d'autres expériences. Pas de validation réelle
vierge ni de fidélité live complète revendiquée.

## Contrôles et suivi

Huit tests ciblés passent : maturité des labels, gaps de stop, inconnus,
continuité d'identité, purge fit/calibration/test, mise à jour annuelle, absence
de cible future dans la sélection et absence de fallback lorsqu'un modèle manque.
Un contrôle des398modèles trouve zéro dépassement des frontières de disponibilité.

La préparation V1 a été arrêtée avant création du dataset, après détection
du TOP20 ancien tronqué. V2 restaure tous les candidats. Avant le fit, une
normalisation de type date a été ajoutée à la lecture de la cohorte et le hash
du code de fit est enregistré dans `training-report.json` ; aucun paramètre
ou résultat économique n'a déterminé cette correction.

Deux simulations au maximum en parallèle, dans des espaces isolés.
SQL partagé en lecture seule ; rapports, caches et modèles locaux.

- Racine : `artifacts/research/us_winner_per_symbol_long/20261103-v2/`.
- Avancement : `campaign/progress.json` ; détail de chaque compte dans
  `runs/ANNEE-VARIANTE/artifacts/progress.json`.
- Modèles : `models/ANNEE/SYMBOLE.joblib` et `model-evidence-ANNEE.json`.
- Classements : `cohort.parquet`, `predictions.parquet`, puis
  `runs/ANNEE-VARIANTE/selection-audit.csv`.
- Synthèse attendue : `annual-summary.csv`, `report.json` ; ces fichiers ne
  sont publiés qu'à la fin des simulations ; ils sont maintenant disponibles.

Scripts : `us_winner_per_symbol_long_20261103`,
`us_winner_per_symbol_long_replay_20261103`,
`us_winner_per_symbol_long_campaign_20261103` sous `scripts/research`.

## Résultats consolidés

Les sommes de départ sont indépendantes : **4 000 USD par compte et année**.
Ne pas multiplier les rendements annuels en prétendant avoir rejoué un compte
continu : le sizing et les seuils de capital dépendent du montant courant.
Les positions encore ouvertes en fin d'année sont valorisées, pas assimilées
à des trades clôturés. Les durées de détention exportées sont calendaires.

| Année | Variante | Capital final USD | Rendement | DD maximal | Trades clos | Taux gagnant |
|---|---|---:|---:|---:|---:|---:|
| 2024 | TOP20 Oracle | 3 708,85 | −7,28 % | −25,43 % | 262 | 32,06 % |
| 2024 | TOP10 Oracle | 3 366,70 | −15,83 % | −26,32 % | 165 | 29,70 % |
| 2024 | TOP10 modèles LONG | 3 356,50 | −16,09 % | −20,88 % | 159 | 36,48 % |
| 2025 | TOP20 Oracle | 3 542,22 | −11,44 % | −22,30 % | 274 | 31,02 % |
| 2025 | TOP10 Oracle | 3 082,58 | −22,94 % | −27,22 % | 166 | 27,71 % |
| 2025 | TOP10 modèles LONG | 3 815,46 | −4,61 % | −18,64 % | 184 | 31,52 % |
| 2026 au 29 octobre | TOP20 Oracle | 3 425,34 | −14,37 % | −27,17 % | 184 | 22,28 % |
| 2026 au 29 octobre | TOP10 Oracle | 4 331,71 | +8,29 % | −29,61 % | 137 | 24,82 % |
| 2026 au 29 octobre | TOP10 modèles LONG | 3 890,32 | −2,74 % | −24,09 % | 145 | 22,07 % |

Le classement par modèles réduit les pertes et le DD par rapport au TOP20
en2025 et2026, mais aggrave le rendement2024. Face au TOP10 Oracle simple,
il ne fait mieux économiquement qu'en2025. Un taux gagnant supérieur en2024
ne suffit pas à compenser le résultat en dollars. **Les trois années du filtre
sont négatives ; aucun gain économique régulier démontré et aucune promotion.**

La liquidation/réduction du risque est celle des défauts natifs, pas un plafond
mathématique garantissant de rester sous15% de DD. Le levier2x est un maximum
conditionnel : l'exposition moyenne du filtre n'est que40,98/41,21/38,56% du
capital courant, avec de nombreux candidats bloqués et des confirmations non
atteintes. Ce ne sont pas des portefeuilles constamment investis à200%.

Les données imposent une réserve forte : le filtre rencontre3385/2091/1288
séances titre/date intraday incomplètes dans ses fenêtres potentielles,
avec3099/2002/1639couples titre/date d'entrée bloqués. Ces comptes ne sont pas
des nombres de signaux indépendants ni une proportion déduisible directement
du TOP20. Le même signal peut attendre plusieurs dates d'entrée. Les lacunes
conditionnent rétrospectivement les occasions : pas de conclusion live ni
preuve causale d'amélioration du modèle à partir de ces seuls résultats.

`completion-audit.json` vérifie les neuf empreintes de rapports, leurs reçus
d'isolement `COMPLETED` sans violation et le lien capital/rendement. Les398
hashes de modèles et frontières de dates ont été contrôlés, neuf probabilités
reproduites exactement ; huit tests ciblés réussis. Même assistant, aucune
revue indépendante revendiquée. Calculs conservés dans `annual-summary.csv`,
`report.json`, `model-audit.json` et les rapports de chaque compte.
