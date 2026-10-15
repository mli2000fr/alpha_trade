# Oracle parcours — TOP5 LONG, protections et levier ×2

Date : 14 octobre 2026. Expérience autorisée, locale et exploratoire.
Ce document ne modifie ni les protections de production, ni les modèles, ni les batchs.

## Question et périmètre figés

Acheter les cinq premiers titres prédits par Oracle parcours, en LONG, sans
renforcer un symbole déjà détenu et sans liquidation automatique après H20.
Comparer les protections dans un vrai portefeuille chronologique : cash,
capital emprunté, positions simultanées, coûts, contraintes et valorisation.
Il ne s'agit pas de sommer des rendements indépendants de titres.

| Année testée | Modèle fourni | Fold causal employé | Champion archivé | Disponibilité maximale des labels train / validation |
| --- | --- | --- | --- | --- |
| 2024 | `model-factory-20261014052407-a4bd20` | 2023-12-05 | CatBoost | 2023-06-05 / 2023-12-04 |
| 2025 | `model-factory-20261014052414-155d09` | 2024-12-05 | LightGBM | 2024-06-05 / 2024-12-04 |
| 2026 | `model-factory-20261014052423-4df571` | 2025-12-10 | CatBoost | 2025-06-10 / 2025-12-09 |

Les dates demandées à l'entraînement ne prouvent pas à elles seules un backtest
causal. Le fold est choisi par les bornes effectives de disponibilité des labels,
toutes strictement antérieures à la première décision annuelle. Le dernier fold
admissible reste ici le même pendant chaque année. Aucun entraînement supplémentaire,
aucun choix du backend selon les profits de l'année testée.

Univers commun des modèles : **1 790 titres actuels**, mêmes 173 features et options
de génération. Ce n'est pas un univers historique certifié sans biais de survie.
Le classement journalier est reconstruit sur l'univers complet avant TOP5.
Les TOP5 sont choisis par score décroissant, symbole comme tie-break ; pas par
mouvement réalisé dans le futur. Les titres rejetés à J ne sont pas remplacés
par le sixième meilleur pour améliorer artificiellement la sélection.

Fenêtres : 2024 et 2025 complètes ; 2026 du 1er janvier au **30 septembre**.
La maturité de labels H20 futurs n'est pas nécessaire pour rejouer les scores et
valoriser les positions détenues. Les features à J et les bars d'exécution restent
soumis aux réserves ci-dessous.

## Grille — 48 profils annuels, 144 portefeuilles

- Stop initial : **5 %, 7 %, 10 %** du fill effectif.
- Trailing : **OFF, 10 %, 15 %, 20 %**.
- TP : **OFF, 10 %, 20 %, 30 %**.
- Capital initial : **4 000 USD**, remis à zéro pour chaque année et chaque profil.
- LONG explicite ; le modèle d'amplitude ne prédit pas que tous ces titres monteront.
- Pas de vente forcée à H20 ni à la dernière clôture de l'année.
- En fin de test, les positions encore ouvertes sont valorisées au close ; leurs
  plus/moins-values latentes sont séparées des résultats réellement clôturés.
- Une position ouverte empêche un nouvel achat du même symbole. Après une véritable
  sortie, une réentrée ultérieure reste soumise aux trackers et aux risques natifs.

Le trailing ne desserre jamais le SL initial. Son sommet de référence disponible
provient des séances précédentes : le HIGH de la journée ne relève pas
rétrospectivement le stop contre le LOW de cette même journée. En collision OHLC
stop/TP non ordonnable, priorité conservatrice au stop. Les gaps défavorables
peuvent produire une perte supérieure au SL nominal ; pas de plafonnement fictif.

## Levier et dimensionnement

Plafond d'entrée à **2× l'equity**, compte simulé sur marge et equity minimale
2 000 USD pour autoriser le levier. Budget nominal agressif : au plus 40 %
d'equity par position, risque de base `.4 × SL` avant les modulations natives.
Cela représente respectivement 2 %, 2,8 % et 4 % d'equity risquée par candidat
avant modulation pour SL5/7/10. La limite secteur est 100 % d'equity, soit 50 %
du gross maximal à ×2. Jusqu'à huit positions cumulées, mais seulement cinq
nouveaux candidats possibles à chaque date.

Les régimes, corrélations, contraintes sectorielles, cible de volatilité, gaps,
blacklists et circuit breaker natifs restent actifs. Le levier n'est donc pas
forcé à ×2 quand ces contrôles réduisent ou bloquent les entrées. L'exposition
moyenne et maximale effectivement obtenue est enregistrée. Une évolution de prix
peut faire dépasser ×2 au marquage sans constituer une nouvelle entrée au-delà
du plafond.

Un adaptateur **de recherche uniquement** étend à 2 le cap validé par
`ExecutionConfig`, dont la validation générique legacy accepte seulement 1.
Toutes les autres validations continuent de s'appliquer ; aucun changement
du validateur de production. Les calculs d'exécution et de buying power restent
les calculs natifs. Un ordre dont la quantité approuvée à J ne peut plus être
financée à J+1 est rejeté intégralement et journalisé : pas de réduction
silencieuse ni de fill forcé.

## Coûts et marge — hypothèses, pas relevé courtier historique

Modèle canonique natif : commission 1 bps, slippage 2 bps, half-spread de base
5 bps par jambe ; application native des spreads/impacts/gaps et arrondis.
Ce sont des hypothèses de simulation, pas des commissions et fills observés.
Les sorties, protections et cash sont raccordés au ledger natif partagé.

Intérêt de marge : hypothèse fixe **6,5 % par an**, calcul sur le cash débiteur
EOD en jours calendaires **ACT/360** ; week-ends compris. Pas d'intérêt sur cash
positif. Le test ne reconstruit pas les variations historiques de tarifs et de
règlement-livraison. [Référence actuelle Alpaca](https://docs.alpaca.markets/us/docs/margin-and-short-selling).

Maintenance générique par prix : 100 % sous 2,50 USD, 50 % entre 2,50 et 6 USD,
30 % au-dessus. Contrôle sur les closes observés : déficit → pas de nouvelle
approbation et demande de sortie au prochain open. La dernière séance est aussi
auditée, mais il n'est pas inventé de fill après la fin des données. La trace
du moteur s'appelle `learned_exit_orders.json` / `learned_exit_next_open` : ici
c'est une **règle de marge**, pas un modèle de sortie appris ; son
`policy_reason` est `MAINTENANCE_MARGIN_FULL_EXIT_NEXT_OPEN`.

La marginabilité par titre, les exigences individuelles/ETF et les appels de
marge intraday du courtier ne sont pas qualifiés historiquement. Le levier est
donc simulé, pas certifié disponible pour chacun des achats.

## Données, réserves et intégrité

Features archivées : `oracle_path_confirmation/20261013-v1`, 72 chunks vérifiés.
Matrices cross-sectional reconstruites sur tout l'univers ; mêmes colonnes,
ordre, générateur et poids que les contrats des trois modèles.
Les clés de dates/titres admissibles du cache sont observables, non filtrées
selon les rendements futurs. Prix qualifiés issus de
`us_oracle_tp20_sl10_new/20261012-v6/prices.parquet`, macro de
`us_oracle_path_economic/20261013-v1/macro.parquet`.

Réserves importantes :

- Secteurs actuels acceptés dans les expériences précédentes, non PIT.
- Univers de survivants et OHLC ajustés fournisseur ; pas de quotes/fills historiques.
- Macro archivée par date, pas certification de chaque vintage disponible à J.
- Dividendes : seulement 40 événements dans la source auditée, couverture
  insuffisante. Les distributions cash non qualifiées sont exclues. **Ce n'est
  pas un rendement total historique complet**, surtout pour les détentions longues.
- Opérations sur titres via ledger strict : claim/fraction cash non valorisé ou
  bar d'une position détenue non qualifiée → cas FAILED, pas suppression a posteriori
  du titre pour rendre le résultat rentable.
- LBRDK/2026-07-20, par exemple, conserve une bar de volume nul dans le tape :
  si un profil le détient ce jour, il doit échouer plutôt qu'utiliser un volume inventé.

Sources, poids, code, candidats et fichiers de résultats vérifiés par SHA-256.
Les résultats clôturés et le cash doivent se réconcilier ; avec positions ouvertes :
`equity = 4 000 + PnL réalisé + PnL latent − intérêts`.
Aucune écriture SQL, aucun appel de courtier, aucun ordre et aucun entraînement.

## Résultats et interprétation

Run canonique : `artifacts/research/us_oracle_path_top5_leverage/20261014-v3`.
La préparation, l'essai annuel de contrôle et la **grille complète sont terminés**.
Lancement le 14 octobre à 09:08 Paris, fin à **09:47:44 Paris** :
**144/144 portefeuilles complets, zéro échec**, sources et fichiers revérifiés.
Trois workers ; coordinateur réel PID 42372
(identifiant valable pour cette exécution seulement). `20261014-v1` est un essai technique
non canonique arrêté sur une incompatibilité d'ordre/budget ; `v2` a terminé le
portefeuille annuel témoin mais son reporting terminal a échoué. Ces diagnostics
sont conservés, pas présentés comme résultats annuels validés.

Le lanceur `.venv` avait le PID 7312 et avait transmis le travail au coordinateur
42372. Les workers 5292, 36884 et 13376 étaient actifs pendant le calcul.
Ces PID sont historiques ; le run n'est plus en cours.

Cas témoin validé, pas résultat optimal : 2024, SL10 / trailing15 / TP OFF,
capital final 2 401,97 USD (−39,95 %), DD maximal −42,30 %, levier moyen ×1,449,
intérêts 108,03 USD, 85 positions clôturées, 32,94 % gagnantes et quatre positions
encore ouvertes. Le dépassement ponctuel ×2,129 est au marquage, pas un achat
volontaire au-delà du plafond d'entrée. Ce cas montre que le levier peut amplifier
les pertes ; il n'autorise aucune conclusion sur les 143 autres profils.

### Meilleurs résultats observés par année

Chaque ligne est choisie après observation des 48 profils de son année :
**ce n'est pas une stratégie qu'on aurait su sélectionner au début de l'année**.
Capital initial 4 000 USD ; rendement net des coûts simulés et du financement,
incluant la valorisation des positions ouvertes, hors dividendes non qualifiés.

| Période | SL | Trailing | TP | Rendement net | Capital final USD | DD maximal | Positions clôturées gagnantes | Levier moyen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 10 % | 20 % | 20 % | +4,83 % | 4 193,14 | −39,29 % | 35/97, soit 36,08 % | ×1,494 |
| 2025 | 5 % | 20 % | 30 % | +184,83 % | 11 393,33 | −19,26 % | 37/127, soit 29,13 % | ×1,056 |
| 2026 janvier–septembre | 10 % | OFF | OFF | +77,62 % | 7 104,85 | −38,39 % | 0/16 clôturées | ×1,682 |

| Période / meilleur profil annuel | Profits des positions clôturées USD | Pertes des positions clôturées USD | PnL réalisé net de frais USD | PnL latent USD | Intérêts USD | Positions encore ouvertes |
| --- | --- | --- | --- | --- | --- | --- |
| 2024 | +5 934,65 | −5 672,04 | +262,62 | +71,46 | 140,93 | 6 |
| 2025 | +15 154,27 | −8 521,16 | +6 633,11 | +883,83 | 123,61 | 3 |
| 2026 janvier–septembre | 0,00 | −1 247,82 | −1 247,82 | +4 548,28 | 195,62 | 8 |

Les intérêts sont retirés séparément, pas imputés artificiellement à chaque trade.
Le taux de réussite ne porte que sur les positions clôturées. Le 0 % du meilleur
profil 2026 **ne signifie pas que toutes ses positions sont perdantes** : ses
gagnantes restent détenues. VICR et HPK représentent environ 71 % du PnL latent.
Le +77,62 % est donc une valeur de portefeuille au 30 septembre, pas un profit
intégralement encaissé ni un gain qu'un trailing aurait déjà sécurisé.

La forte performance 2025 contient des gains sur plusieurs titres (ICHR +2 296,41,
MLTX +1 246,99, ACVA +1 221,62, CCOI +1 103,59 USD de PnL net réalisé cumulé).
Les plus gros trades prennent effectivement TP30 : le rapport n'a pas remplacé
le TP par un maximum de trajectoire connu a posteriori. La concentration et les
réserves prix/PIT demeurent ; ces contrôles ne certifient pas une exécution courtier.

### Même combinaison sur les trois périodes

| Profil identique | 2024 | 2025 | 2026 janvier–septembre | Moyenne arithmétique | Pire DD |
| --- | --- | --- | --- | --- | --- |
| SL5 / trailing20 / TP30 — meilleure moyenne observée | −33,96 % | +184,83 % | −10,73 % | +46,71 % | −40,90 % |
| SL10 / trailing20 / TP20 — meilleur profil 2024 | +4,83 % | +32,68 % | −19,52 % | +5,99 % | −44,65 % |
| SL5 / trailing15 / TP20 — meilleure pire année observée | −16,74 % | +9,93 % | +36,14 % | +9,78 % | −32,83 % |
| SL10 / trailing OFF / TP OFF — meilleur profil 2026 | −38,04 % | −0,30 % | +77,62 % | +13,09 % | −43,25 % |

**Aucun des 48 profils n'est positif sur les trois périodes**. Nombre de profils
positifs : 1/48 en 2024, 34/48 en 2025, 13/48 en 2026. Onze moyennes sur 48
sont positives, mais cela ne supprime pas les années perdantes. La meilleure
moyenne dépend surtout de 2025 et perd sur les deux autres périodes.
La meilleure pire année est un critère alternatif calculé après observation,
pas un profil robuste validé à promouvoir.

### Trailing, levier et contrôles

À SL et TP identiques, le trailing20 améliore le rendement dans 4/12 comparaisons
en 2024, 6/12 en 2025, 5/12 en 2026. Son écart moyen au trailing OFF est
−2,31 / +11,41 / −5,58 points, respectivement. Trailing10 :
+2,08 / −5,88 / −5,19 points ; trailing15 : −1,03 / +10,09 / −4,99.
Ces différences réincluent les décisions de portefeuille et les réinvestissements
consécutifs aux sorties : elles ne sont pas une comparaison sur quantités figées.
**Pas de trailing universellement supérieur démontré**.

Zéro déficit de maintenance détecté sous l'hypothèse générique du protocole ;
cela ne prouve pas l'absence d'appels de marge réels. Les meilleurs profils annuels
ont une exposition moyenne nettement inférieure à ×2 : cash disponible, régimes,
volatilité et contraintes continuent de compter. Au marquage, les pics sont
×2,095 / ×2,058 / ×2,081 : dérive des prix, pas autorisation d'entrée au-delà de ×2.

Erreur maximale de réconciliation cash : environ 7,3e−12 USD ; tous les fichiers
des 144 cas et les sources ont été vérifiés après le calcul. 137 profils ont au
moins une position clôturée après plus de vingt séances, ce qui confirme la
suppression de l'expiration H20. Aucune liquidation terminale n'a été ajoutée.

Conclusion : **expérience terminée, optimum exploratoire mais pas de combinaison
stable démontrée**. Aucun paramètre de production, modèle, batch ou ordre modifié.

- `progress.json` : progression globale.
- Un dossier `AAAA-SLx-TRAILx-TPx` par cas : progression par séance, trades,
  courbe d'equity, exécutions/rejets, marge et positions ouvertes.
- `annual-summary.csv` : cas annuels complets.
- `cross-year-summary.csv` : uniquement les profils ayant trois années complètes,
  moyenne de rendement, pire année, DD, levier et déficits de marge.
- `report.json` final : meilleurs cas **observés** par année, profils multi-années
  et liste des échecs avec motif.

La moyenne mélange deux années complètes et neuf mois 2026 ; elle n'est ni un
CAGR, ni la performance d'un portefeuille réinvesti sans reset sur trois ans.
Choisir le meilleur de 144 replays sur ces mêmes résultats est exploratoire,
pas une preuve hors échantillon du meilleur SL/trailing/TP. Ne promouvoir aucune
combinaison uniquement sur cette recherche.

## Suivi / reprise

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_path_top5_leverage\20261014-v3\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_path_top5_leverage\20261014-v3\stderr.log -Tail 20 -Wait
```

Reprise des cas déjà complets, seulement après arrêt effectif du précédent processus :

```powershell
python -u -m scripts.research.us_oracle_path_top5_leverage_grid --output artifacts/research/us_oracle_path_top5_leverage/20261014-v3 --phase run --workers 3
```

Le run étant terminé, il n'est pas nécessaire de le relancer pour lire les résultats.
Ne pas lancer deux coordinateurs en même temps. Verrou OS exclusif et vérification
des sources empêchent une reprise avec poids/code/candidats silencieusement modifiés.
Les cas FAILED ne sont pas présentés comme rendements annuels complets.

Tests ciblés : 28 réussis sur l'adaptateur et les protections existantes ; maintien
après H20, pas de liquidation terminale ni renforcement, SL ancré au fill, trailing
causal, gaps/collisions, intérêts week-end, réconciliation cash et garde-fous marge.
