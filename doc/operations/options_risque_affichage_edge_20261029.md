# Étape 11 : sélection options complète et risque Oracle amplitude

## Incident du 29 octobre 2026

La sélection `opt-5f789c9df25b434b9d4506d78085a4fc`, séance du 28 octobre,
retenait douze LONG. Le risque `de209d7cf1f949c3` n'avait enregistré que six
décisions, toutes refusées pour `optimizer: edge net manquant`.

Les six autres titres — MXL, COHU, UCTT, SIMO, TTMI, STRL — étaient non
tradables pour `earnings_blackout` dans l'univers exact archivé
`universe-0e97dda82ff443faa9fbab76a47e1c86`. Ils étaient exclus avant le sizing,
mais le tableau ne partait que des décisions/cibles enregistrées : il les masquait.

## Corrections

Le tableau du risque part désormais des titres retenus dans le rapport options
scellé, dans l'ordre Oracle. Il relie ce rapport au risque exact du compte par
ses empreintes et son identifiant. Les exclusions avant sizing sont expliquées
depuis l'univers exact du run ; un motif absent reste explicitement inconnu.
Les cours affichés sont ceux de J archivés avec la sélection.

La lecture historique vérifie l'intégrité des archives, indépendamment de leur
expiration pour le trading. Elle n'autorise ni nouveau risque ni ordre. Les
contrôles de fraîcheur, de séance et de compte de `qualified()` restent imposés
aux consommateurs opérationnels. Aucun ancien run n'est substitué si le lien
exact est manquant ou altéré.

Oracle parcours estime l'amplitude, pas une probabilité LONG ni un rendement net
attendu. La CLI utilise maintenant le parcours natif `oracle_pure_long` pour cette
stratégie explicitement LONG, après les contrôles Oracle et le veto options.
Le score reste un rang d'amplitude ; il n'est plus présenté comme une probabilité
directionnelle dans les décisions. Aucun edge ni taux de réussite n'est fabriqué.

L'optimiseur qui exige un edge directionnel n'est pas branché sur cette politique.
La covariance et les expositions factorielles restent branchées au moteur de
risque. Les limites de capital réel, buying power, positions et ordres en cours,
secteur, corrélation, bêta, régime, données et protections restent applicables.
Le contrat signé Oracle, son univers et sa fraîcheur restent contrôlés avant
toute construction. Kelly reste incompatible avec ce parcours.

Le parcours LLM explicite, lui aussi sans probabilité calibrée, conserve son
adaptateur natif et n'est pas envoyé dans cet optimiseur d'edge. Pour les vraies
prédictions directionnelles, l'optimiseur et ses refus pour edge manquant restent
inchangés. Le résumé précise `portfolio_selection_policy` et
`edge_optimizer_applicable` pour distinguer les cas.

## Validation et reprise

Tests isolés : affichage complet, sceaux et liens altérés, compte secondaire,
expiration inchangée pour le trading, absence d'écriture par la vue, absence de
probabilité/Kelly inventés, capital insuffisant, positions/ordres réservés,
régime, corrélation et contraintes factorielles. Les suites existantes de risque,
filtre, enchaînement et multicomptes sont également vérifiées.

La lecture seule de la base réelle confirme désormais douze lignes dans la vue :
six exclusions `earnings_blackout` et les six anciens refus de l'optimiseur.
L'ancien résultat n'est pas réécrit. Aucun recalcul de risque, ordre ou déverrouillage
n'a été effectué. Les nouveaux calculs utiliseront le parcours corrigé ; une cible
éventuellement acceptée doit encore passer les contrôles d'exécution et du watcher.

## Décision ultérieure : Winner reste en actions entières

Après la relance PAPER, les cibles fractionnaires ont été refusées avant tout
ordre. L'utilisateur a choisi de différer le support des fractions et de conserver
les protections Winner actuelles. Les modifications expérimentales fractionnaires
ont été annulées ; aucun renouvellement de stop DAY ni TP local n'a été activé.

Quand `winner_pyramiding.enabled: true`, le chargeur de risque impose
`allow_fractional_shares=False` **avant le sizing**, même si le preset ou la CLI
demande des fractions. Les commandes 11/12 du Pipeline omettent aussi ce flag et
la configuration d'exécution impose la même règle pour les appels directs.
Winner désactivé, le fonctionnement fractionnaire nominal reste disponible.

Une ancienne cible fractionnaire est refusée explicitement avant l'écriture
d'un plan ; elle doit être recalculée par l'étape 11. Aucune quantité n'est arrondie
vers le haut pour atteindre une action. Le minimum de montant et les autres
limites de risque restent inchangés. Si le budget ne finance pas une action,
l'entrée est refusée. En demi-position, le montant doit aussi financer la moitié
initiale entière ; sinon aucun plan n'est armé.

Les nouveaux résumés de risque exposent `allow_fractional_shares` effectif et
`quantity_policy`. L'écran rappelle la priorité de Winner sur la case fractionnaire.
Cette adaptation ne réécrit pas les anciens runs et ne relance aucun ordre.

## Relance des comptes secondaires du 29 octobre

Lancement explicitement demandé par l'utilisateur sur les autres comptes PAPER,
sans nouvelle exécution du compte `default`. Les étapes 11/12 consomment une
sélection commune et conservent leurs budgets et fichiers de tentative par compte.

Le premier essai sur `test1` a révélé une erreur de normalisation : Alpaca retourne
une quantité négative pour un SHORT, alors que le lecteur exigeait une quantité
strictement positive avant d'en prendre la valeur absolue. La lecture conserve
désormais le côté SHORT et sa magnitude positive. Une quantité LONG négative,
nulle ou non finie reste refusée. Validation : 42 tests locaux réussis, dont
les gardes de capital et d'exposition.

Après cette correction, `test1` reste bloqué avant publication du risque : sa
position BW a `INCOMPLETE_DAILY_SESSIONS` dans les 272 séances requises par les
facteurs au 28 octobre. Sa capitalisation datée est disponible ; c'est l'historique
de cours qui manque. Aucune étape 12 n'a été forcée et aucun ordre n'a été envoyé.

`test2` a terminé 11 et 12 avec zéro cible : TXG, FN et SDGR dépassent le plafond
de bêta projeté (2,07 > 1,20), ICHR, PENG et HPE atteignent le plafond sectoriel.
L'exécution a donc été ignorée avec `NO_RISK_TARGETS`. Son watcher PAPER est sain.

Sélection de reprise : `opt-11e70e399d54431eaefa6ffcf7ad193f`, issue exclusivement
des prédictions et données SQL déjà disponibles. Aucun ancien verrou n'a été
supprimé. Les quatre ordres précédemment envoyés sur `default` restent inchangés.
Comptes rendus locaux sous `artifacts/operations/options_secondary_accounts/`.

## Reprise après réparation de BW et plafond bêta à 3,5

À la demande de l'utilisateur, les sept séances BW absentes du 20 au 28 octobre
ont été récupérées en SIP historique Alpaca puis enregistrées dans `stock_bars`
et `stock_bars_daily` avec le convertisseur canonique, source `alpaca_sip`,
ajustement `split`. Les observations déjà présentes n'ont pas été remplacées.
La qualification forcée des facteurs au 28 octobre est désormais `QUALIFIED`
pour BW : 272 séances, aucune raison d'incomplétude. La position SHORT BW reste
donc comptée dans le portefeuille réel de `test1` ; aucune position n'a été masquée
ni clôturée pour contourner les protections.

Une sélection locale fraîche `opt-c6ebd063000f48be9f8d887aab51ba6f` a été partagée
entre les deux nouveaux calculs, sans modifier les anciens verrous ni relancer
la prédiction Oracle ou un LLM. Plafond bêta effectif demandé : 3,5.

- `test1`, risque `de77527ff0664a52` : 11 et 12 terminées, zéro cible. Les six
  nouveaux candidats sont refusés par `final_factor_diversification:1<2`.
  Watcher PAPER sain ; aucun ordre envoyé.
- `test2`, risque `028114dc3fdd4c31`, exécution `0ec5f24fdd9d4d93` : 11 et 12
  terminées. Trois ordres limite DAY LONG transmis : TXG 33 à 83,70 $, FN 8 à
  367,66 $, SDGR 113 à 30,90 $. Aucun fill confirmé à la vérification initiale.
  Watcher PAPER sain. Les plafonds sectoriels continuent de refuser les trois
  autres candidats ; ils n'ont pas été modifiés.

Preuves de réparation : `artifacts/operations/bw_history_repair_20261029/`.
Workflows : `20261029_102216_6f00dcf2` et `20261029_102301_f4a4bc41`.

## Interrupteur du minimum factoriel et reprise test1, 29 octobre à 15 h Paris

À la demande de l'utilisateur, `risk_management.factor_diversification_check_enabled`
est maintenant `false` dans `config.yaml`. Le booléen est raccordé au contrôle
avant sizing, après sizing et à chaque revalidation native Winner. Le modèle
factoriel, ses données, le bêta (3,5), la concentration et les autres limites
restent actifs. Les anciens snapshots sans ce champ conservent `true`.
Les tests ciblés passent (130 dans la première sélection, 151 dans la seconde,
avec recouvrement ; validation des données manquantes et des autres plafonds incluse).

La dernière étape 11 de test1 (`3524c36a4ee84930`) avait déjà accepté six cibles,
et l'étape 12 (`ef3df923515e4ded`) avait créé leurs six plans PENDING. Le blocage
était ensuite la revalidation individuelle du watcher, avec zéro facteur >10 %.
Le diagnostic en lecture seule après correctif retrouve `OK` pour les six.

À 15 h Paris, la fenêtre de relance de la sélection du 28 octobre était fermée
(ouverture J+1 passée). Aucun nouveau 11/12 hors fenêtre, aucune nouvelle sélection,
aucune suppression de claim ou de plan : reprise des plans admis, encore dans
leur fenêtre native d'entrée, par redémarrage du seul watcher PAPER `test1`.
Identité PID/compte/mode et propriétaire du verrou vérifiés avant redémarrage.
Les comptes `default` et `test2` n'ont pas été relancés.

Six ordres limite DAY LONG ont été envoyés après revalidation, sans doublon.
État constaté le 29 octobre vers 15 h 01 Paris :

| Symbole | Quantité | État | Prix moyen exécuté USD |
| --- | ---: | --- | ---: |
| TXG | 32 | rempli | 82,73 |
| ICHR | 67 | rempli | 42,79 |
| PENG | 39 | rempli | 59,38 |
| FN | 8 | rempli | 357,79 |
| SDGR | 108 | rempli | 30,54 |
| HPE | 65 | nouveau, non rempli | — |

Pour les cinq achats remplis, OCO GTC présent chez Alpaca : TP +18 % et stop
initial −5 %, quantités identiques aux fills ; trailing Winner figé à null.
Le watcher est sain et continue de suivre HPE, sans relever sa limite 60,39 $.
Les autorisations ENTRY archivées portent `factor_diversification_check_enabled=false`.

Anomalie distincte observée : le filet de sécurité historique ne reconnaît pas
ces OCO Winner et tente un trailing supplémentaire, refusé par le broker car
les quantités sont déjà réservées aux OCO. Les cinq stops et TP ont été vérifiés
via les ordres imbriqués du broker ; aucune protection n'a été annulée pour
contourner ce refus. Le cycle suivant constate zéro échec d'armement ; le
doublonnage est transitoire autour de la création des protections. Une correction
séparée du passage entre suivi Winner et filet historique serait utile.

Preuves immuables :
`artifacts/operations/test1_factor_gate_resume/20261029T140030Z-fbbc4ca2/`
(`preflight.json`, `watcher_restart.json`, `watcher_ready.json`, `result.json`, logs).
Diagnostic préalable : `artifacts/operations/test1_factor_zero/20261029T135908Z/report.json`.
Le service a ensuite été rafraîchi après finalisation du code à 15 h 04 Paris,
en conservant toutes les opérations existantes :
`artifacts/operations/test1_factor_gate_resume/20261029T140418Z-b24a4ae9/`.
