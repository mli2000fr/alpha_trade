# Deux univers AUC : confirmation Winner et DD15 de production

Ces résultats achètent les TOP5 d'amplitude Oracle. Le classement LONG
per-symbol quotidien a ensuite été ajouté et testé dans une
[campagne séparée avec contrôles identiques](univers_auc_per_symbol_top5_20261104.md).

**32 simulations terminées le4novembre2026 ; comparaison partielle, aucune
conclusion de performance sur les univers complets.** L'utilisateur a demandé
les mêmes conditions que les deux audits précédents, en ajoutant séparément
confirmation Winner, coupe-circuit DD15, puis les deux. Il a confirmé le mode
**production : liquidation de50 % des positions puis reprise B4**, et non un
arrêt définitif après liquidation totale.

## Conditions communes et référence

Scores des six Oracles annuels déjà entraînés, **sans réentraînement** :
32titres H10 et37titres H20 des fichiers `symbols_winner_h10_auc_gt060.txt`
et `symbols_parcours_h20_auc_gt060.txt`. TOP5 quotidiens figés, LONG imposé,
aucun remplacement par le rang6 si un titre est détenu ou exclu.

Capital4 000USD,1x,positions complètes, entiers, SL5 %, aucun TP/trailing ou
renforcement, sortie open11/open21. Maximum20positions,20 % par position,
budget de risque1,25 % par entrée, minimum50USD ; frais estimés8bps par jambe.
Une opportunité porte sur **la séance suivant le signal**, comme le test daily.
La confirmation seule n'introduit pas d'anciens plans attendant20séances.
Ni option CALL/PUT/OI ni filtre LLM ajouté.

Trois années indépendantes avec4 000USD au départ de chacune, et un compte
continu supplémentaire sans remise à zéro :2024–**19octobre2026**. Positions
finales valorisées sans liquidation artificielle de fin.

Les quatre bras utilisent exactement les mêmes bougies et le même masque
de qualité par symbole/date d'entrée. La **référence intraday** a été recalculée.
Elle ne vaut plus les résultats daily précédents (H10−25,01 %, H20+167,11 %) :
prix SIP bruts, qualification de l'historique cinq minutes, exclusions de
changements de base et observation du DD intraday diffèrent. **Ne pas attribuer
ces différences à Winner ou DD15.** Seules les comparaisons entre les quatre
bras de cette nouvelle campagne isolent les mécanismes sur le périmètre qualifié.

## Confirmation effectivement testée

La fonction native `confirmed_breakout` demande une clôture cinq minutes au
plus haut de la veille ou en dessous, puis **deux clôtures consécutives au-dessus**.
Ce n'est pas simplement deux hausses quelconques sous ce niveau.

Plus haut calculé depuis la séance régulière précédente en SIP brut. Preuves
clôturées et contiguës, délai configuré930secondes, marge de fraîcheur native.
Décision à l'horloge réelle ; aucune exécution rétroactive au cours de la
bougie de confirmation. Un seul ordre IOC simulé à l'ouverture cinq minutes
observée suivante, plafond natif arrondi au centime inférieur à+1 % du dernier
close retardé. Si le cours dépasse le plafond, ordre annulé, sans attente d'un
meilleur cours ultérieur. Réserve de cash, recontrôle de quantité au fill et
SL ancré au prix effectivement simulé.

La stratégie daily précédente n'avait pas de filtre gap3 % ; il n'en est pas
ajouté dans ce comparatif. Aucun spread temps réel inventé. Les modules de
confirmation/prix limite sont natifs ; le ledger financier de comparaison reste
un adaptateur de recherche, **pas le moteur intégral de plans/risque de production**.

## DD15 effectivement raccordé

Réutilisation de `CampaignRiskState`, `CircuitBreaker`/B4 et des décisions de
`GlobalLiquidation`, avec les paramètres de risque actuels archivés.
Régime SPY issu uniquement des clôtures antérieures, SMA50/200 avec chauffe2023.
Les observations cinq minutes ne deviennent pas de fausses journées favorables.
L'hystérésis et le réarmement B4 restent ceux du code partagé.

Au déclenchement, sélection native de50 % du **nombre de positions**, arrondi
au plus proche avec minimum un si le portefeuille n'est pas vide, en commençant
par les moins-values latentes absolues les plus importantes. Vente de ces positions
entières à l'ouverture observée suivante après le déclenchement connu. SL et
sorties temporelles déjà engagés sont traités en premier, sans double vente.
Les IOC en attente sont annulés lors d'un déclenchement. Le budget des nouvelles
entrées suit le facteur d'allocation B4.

**15 % est un seuil de déclenchement, pas un plafond garanti de drawdown.**
La liquidation est partielle, le reste du portefeuille conserve son risque,
le contrôleur peut réarmer et l'exécution peut subir un gap. Si les stops viennent
déjà de vider le portefeuille, l'événement DD existe mais n'ajoute aucune vente ;
le mode dégradé B4 peut néanmoins affecter les entrées suivantes.

Les autres contrôles du risque (facteurs, secteurs, corrélation, ciblage de
volatilité, etc.) ne sont pas introduits : cela changerait plusieurs variables
à la fois par rapport à la référence. Pas de plafond globalDD25 ajouté.

## Données récupérées et limite matérielle

Les TOP5 de tous les jours concernent31symboles distincts,13H10 et18H20.
La base contenait des historiques5m pour huit seulement. Un snapshot SQL
**en lecture seule** a archivé418 092bougies ; les23titres entièrement absents
ont ensuite été récupérés depuis Alpaca SIP dans le dossier de recherche :
**1 008 328barres de séance régulière**,379réponses paginées archivées.
Les queues des huit historiques existants ont apporté3 240barres supplémentaires.
Ni écriture SQL ni changement d'univers de batch ou abonnement.

Un premier plafond local de30requêtes par titre a arrêté BB : le fournisseur
retournait des pages partielles malgré `limit=10000`. Après examen, la chaîne
des31pages déjà reçues a été rejouée localement, puis seule sa fin téléchargée.
Le nouveau plafond100 n'a pas été atteint. Le reçu et le rapport de cet arrêt
restent préservés ; aucun historique reçu n'a été jeté ni redemandé pour cette reprise.

Le référentiel corporate_actions local était vide pour ces31titres/période :
cela ne prouve pas l'absence de splits. Six requêtes daily SIP raw/split ont
permis de comparer21 725couples symbole/date. Trois transitions de facteur
de split du fournisseur sont identifiées : RIGL27juin2024, NKTR9juin2025,
POWL6avril2026. Elles ne sont pas inférées depuis le rendement du titre.
Les fenêtres qui les traversent sont exclues en commun, au lieu de comptabiliser
une variation mécanique du nombre d'actions comme un gain.

Le masque commun conserve les exigences du précédent audit daily (OHLCV,
identité et fournisseur stables), et exige une séance5m régulière complète
la veille puis sur toute la fenêtre de détention projetée, bornée à la fin
globale du test. Aucun prix/barre inventé ou interpolation. Cette règle regarde
la disponibilité future : **biais de sélection rétrospectif supplémentaire**.
Elle est identique dans les quatre bras, mais ne certifie pas le live.

Malgré les récupérations, de nombreuses réponses5m n'ont pas toutes les
bougies attendues. Ces absences ne distinguent pas à elles seules illiquidité
et défaut de couverture ; elles ne sont pas assimilées à des bougies complètes.

| Année | H10 : occasions qualifiées / proposées | H20 : occasions qualifiées / proposées |
|---|---:|---:|
| 2024 | 132 /1 255 — **10,52 %** | 54 /1 255 — **4,30 %** |
| 2025 | 258 /1 250 — **20,64 %** | 146 /1 250 — **11,68 %** |
| 2026 partiel | 309 /1 000 — **30,90 %** | 205 /1 000 — **20,50 %** |

Il s'agit de l'éligibilité potentielle avant détention, confirmation, sizing
et cash. Les quatre bras peuvent donc avoir des nombres différents de rejets
effectivement rencontrés, tout en partageant exactement le même masque initial.

## Résultats annuels

Chaque cellule indique **rendement net / DD maximal**. Le DD est mesuré sur
les clôtures5m observées, avec dépôt initial inclus ; il n'est pas un maximum
intrabar garanti. Les trois années repartent séparément de4 000USD.

**H10 — 32titres :**

| Année | Référence intraday | Confirmation Winner | DD15 /B4 | Winner + DD15 /B4 |
|---|---:|---:|---:|---:|
| 2024 | +7,95 % /−13,82 % | +5,34 % /−9,42 % | +7,95 % /−13,82 % | +5,34 % /−9,42 % |
| 2025 | −2,09 % /−18,47 % | +13,51 % /−9,76 % | −16,26 % /−21,02 % | +13,51 % /−9,76 % |
| 2026 au19/10 | −1,80 % /−27,01 % | −1,41 % /−16,76 % | +1,50 % /−17,51 % | −4,84 % /−16,14 % |

**H20 — 37titres :**

| Année | Référence intraday | Confirmation Winner | DD15 /B4 | Winner + DD15 /B4 |
|---|---:|---:|---:|---:|
| 2024 | −11,28 % /−13,84 % | −5,96 % /−7,58 % | −11,28 % /−13,84 % | −5,96 % /−7,58 % |
| 2025 | +24,27 % /−12,66 % | −6,10 % /−9,68 % | +24,27 % /−12,66 % | −6,10 % /−9,68 % |
| 2026 au19/10 | −5,76 % /−26,55 % | −1,20 % /−14,41 % | −8,41 % /−16,18 % | −1,20 % /−14,41 % |

Les valeurs identiques entre bras sans/avec DD sont normales lorsqu'aucun
déclenchement n'a lieu sur ce compte annuel. Exemple : H20 annuel2025.

## Comptes continus 2024–19octobre2026

Capital4 000USD, sans remise à zéro et sans levier, frais inclus. Capital final
valorisé, positions résiduelles incluses ; taux gagnants sur les trades clos.

| Univers | Variante | Capital final | Rendement | DD max | Trades clos | Gagnants | Exposition moyenne /equity |
|---|---|---:|---:|---:|---:|---:|---:|
| H10 | Référence intraday | 4 177,52 $ | +4,44 % | −27,10 % | 190 | 21,58 % | 22,51 % |
| H10 | Confirmation Winner | **4 709,78 $** | **+17,74 %** | −17,67 % | 95 | 23,16 % | 11,77 % |
| H10 | DD15 /B4 | 3 849,99 $ | −3,75 % | −22,73 % | 185 | 22,16 % | 12,05 % |
| H10 | Winner + DD15 /B4 | 4 627,14 $ | +15,68 % | **−15,89 %** | 94 | 22,34 % | 10,03 % |
| H20 | Référence intraday | **4 121,53 $** | **+3,04 %** | −30,42 % | 95 | 21,05 % | 20,86 % |
| H20 | Confirmation Winner | 3 447,85 $ | −13,80 % | −21,38 % | 47 | 14,89 % | 8,78 % |
| H20 | DD15 /B4 | 3 387,90 $ | −15,30 % | **−20,66 %** | 95 | 21,05 % | 10,57 % |
| H20 | Winner + DD15 /B4 | 3 236,03 $ | −19,10 % | −20,75 % | 47 | 17,02 % | 6,12 % |

Le faible capital engagé vient du masque strict de couverture, puis de la
confirmation et, quand actif, du sizing dégradé B4. Un DD plus faible peut
refléter surtout une exposition moindre, pas une meilleure direction.

Sur ces seuls comptes qualifiés, Winner aide H10 mais pas H20 ; DD15 seul ne
constitue pas une amélioration économique régulière. **Pas de choix de
production déduit de cet échantillon restreint.** Les univers ont en outre été
sélectionnés avec les résultats2023–2026 : absence de validation indépendante,
même en présence de modèles annuels chronologiquement causaux.

![Comptes continus](../../artifacts/research/us_selected_universe_oracle/20261104-winner-dd15-v1/comparison-continuous.png)

## Vérification et stockage

Dossier `artifacts/research/us_selected_universe_oracle/20261104-winner-dd15-v1/` :

- `protocol.json`, `progress.json`, `report.json`, **`comparison.csv`** :32cas.
- `coverage-summary.csv`, `{univers}-matched-entry-quality.csv` : éligibilité,
  motifs et dates ; `intraday-qualified-coverage.csv` : comptes de bougies.
- `inputs/` : snapshot SQL et SPY ; `recovery/` :23titres, réponses paginées et
  reçus ; `tail-recovery/` : queues ; `split-qualification/` : bases raw/split.
- `runs/{univers}/{2024,2025,2026,continuous}/{BASE,WINNER,DD15,WINNER_DD15}/` :
  comptes, courbes, trades, décisions et journaux d'ordres de confirmation.
- `verification.json`, `verification-cases.csv` : **PASS_WITH_MATERIAL_COVERAGE_LIMIT**.

Contrôles :32comptes et **1 693trades** (simulations annuelles/continues avec
doublons économiques entre cas), frais/cash/PnL latent, absence de levier,
entrée à la séance suivante, horizons, stop et gaps, signatures des sources,
379corps de réponses fournisseur, délai et plafond IOC, journaux DD et absence
de divergence des trajectoires avant le premier trip. **46tests ciblés passent**
sur l'adaptateur et les modules partagés de confirmation/DD.

Les bougies/citations futures ne servent pas au ranking ni à la confirmation,
mais leur existence sert au masque de qualification rétrospectif déclaré.
Pas de modèle modifié, de filtre promu, de batch reconfiguré, de SQL écrit,
d'appel LLM ou d'ordre broker. Même assistant : pas une revue humaine indépendante.
Le comparatif ne certifie ni les carnets historiques, ni les remplissages
broker réels, ni les liquidités/spreads des petites valeurs.

Scripts : `us_selected_universe_intraday_inputs_20261104.py`,
`us_selected_universe_intraday_repair_20261104.py`,
`us_selected_universe_intraday_tail_20261104.py`,
`us_selected_universe_split_qualification_20261104.py`,
`us_selected_universe_winner_dd15_20261104.py`,
`us_selected_universe_winner_dd15_review_20261104.py`, sous`scripts/research`.
