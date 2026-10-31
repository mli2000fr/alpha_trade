# Winner : lancement Backtest et parcours PAPER/live

Raccordement du 31 octobre 2026. Évolution technique ; aucune nouvelle mesure
de rentabilité, aucun ordre, aucune activation d'un compte en argent réel.

## Depuis l'IHM

Page **Backtesting**, onglet **Backtest**, cocher **Utiliser Winner — Oracle
parcours et replay intraday**. Cette case reprend `winner_pyramiding.enabled`
au premier affichage. Le formulaire dédié remplace les paramètres du moteur
daily classique ; les deux moteurs ne mélangent pas leurs protections.

Sélectionner un modèle Oracle parcours terminé H10/H15/H20, les dates, le
fichier d'univers, le TOP-N (20 par défaut), le capital, le type de compte,
les positions maximales et l'exposition 1×/2×. Le 2× n'est proposé que pour
un compte margin et si la configuration de levier l'autorise. Les contraintes
de risque peuvent encore réduire l'exposition effectivement utilisée.
La couverture minimale des prédictions reprend le seuil du filtre options (90 %
actuellement) ; disposer de vingt scores ne suffit pas si le reste de
l'univers demandé n'est pas suffisamment couvert. La disponibilité SQL de
chaque fold est recoupée avec les reçus immuables de training/validation.

La date minimale est calculée depuis les folds du modèle : le premier signal
doit être causal et disponible avant la séance d'entrée. Pour le modèle
`model-factory-20261030213826-eda503`, premier signal le 2 juillet 2021,
première entrée possible le 6 juillet (NYSE fermé le 5 juillet).

Les prédictions causales et les bougies SIP 5m doivent déjà être en base.
Générer au besoin les prédictions avec le bouton historique de la page Pipeline,
sur une période comprenant la séance précédente du début du replay. Le
lancement du backtest ne fait ni prédiction automatique ni téléchargement.

Les frais canoniques s'appliquent par défaut ; un coût explicite par achat et
vente peut les remplacer pour ce replay. Le taux de financement est séparé
et porte sur le débit de marge. La réserve de sizing Winner n'est pas une
commission supplémentaire. Le capital reste commun à toutes les positions.

Le profil **« replay prudent disponible, proche du fonctionnement en production »**
est coché par défaut. Ce choix active les hypothèses conservatrices réellement
supportées : bougies SIP 5m, délai de publication configuré, aucun achat
rétroactif, limite d'achat respectée et priorité à la sortie défavorable si
SL et TP sont touchés dans la même bougie. Il n'existe pas de bouton capable
de reconstruire le carnet ou les secteurs historiques absents : les secteurs
actuels restent une approximation et le rapport garde sa qualification
exploratoire. Ce profil ne permet pas d'envoyer un ordre.

Les paramètres utiles du moteur intraday sont accessibles dans des blocs
dédiés : protections/confirmation/renforcement Winner, risque par entrée,
montant minimum, poids par titre et secteur, plafonds de titres, corrélations,
drawdown/perte quotidienne, liquidation au coupe-circuit, volatilité cible,
répétition des entrées/exclusions et plafond bêta. Le capital, les positions
maximales, les frais et le levier restent dans le formulaire principal.
Les valeurs sont préremplies depuis `config.yaml` et le preset du capital.
Un bouton **« Reprendre les réglages de production »** remet les contrôles
de simulation à ces valeurs sans changer les dates, le modèle ni le capital.
Validation du formulaire enrichi : **359 tests réussis**, dont édition des
valeurs, retour aux paramètres de production, transmission JSON au CLI,
replay SQL en lecture seule et vérification que le budget modifie les
quantités. Les paramètres effectifs et les différences locales figurent
dans le rapport.

Les modifications ne concernent que ce replay et sont transmises explicitement
dans `--risk-overrides-json` / `--policy-overrides-json`, contrôlées par liste
de champs raccordés, puis figées dans `protocol.json`. Aucun fichier YAML,
plan existant ou compte courtier n'est modifié. Les paramètres daily non
raccordés à Winner ne sont pas présentés comme des commandes actives.

## Réglages réellement utilisés

Le processus relit `config.yaml` au lancement et fige sa politique dans
`protocol.json` : confirmation, fraction initiale, renforcement, seuil d'ajout,
SL/TP/trailing, durée et expiration du plan, limites de fraîcheur et réserve.
Les modifications de formulaire concernent uniquement ce replay.
La configuration du coupe-circuit reprend désormais explicitement
`risk_management.prod_force_close_on_breaker` / `prod_force_close_pct`
(avec fallback legacy), au lieu d'ignorer ces clés. Le réglage de travail
est actif, liquidation de 50 % des positions lors du déclenchement ; cela
ne garantit pas un drawdown maximal de 15 %. Le capital initial réel du
replay est aussi injecté dans la configuration de risque, et un SL Winner
modifié localement est répercuté dans le sizing. Winner étant LONG-only,
le plafond LONG suit le nombre de positions choisi dans le formulaire.

Au contrôle du 31 octobre : position complète, deux confirmations 5m,
renforcement désactivé, **SL 5 %, aucun TP ni trailing, horizon 10 séances**.
L'entrée compte comme première séance ; sortie à l'ouverture de la **11e**.
L'horizon du modèle d'amplitude et la durée de détention sont deux paramètres
distincts : choisir Oracle H20 ne modifie pas implicitement la durée Winner.

Le replay emploie `BacktestEngine` puis `WinnerCampaignRuntime` et la
revalidation native `reapprove_campaign`, comme le watcher. Il applique
budget de risque, capital disponible, limites configurées, frais, capacité de
marge, financement, protections et échéance. Les dividendes USD documentés
sont comptabilisés ; les actions sur titres non prises en charge lorsqu'une
position est détenue interrompent le replay.

Pour les daily, la ligne entière du fournisseur préféré de
`market_data.daily_bars_preferred_source` est sélectionnée : EODHD par défaut,
SIP complémentaire si le préféré est absent. Une ligne préférée invalide
n'est pas masquée par un autre fournisseur. L'intraday utilise uniquement
Alpaca SIP, US_EQ, séance régulière, 5m raw, non rempli, avec provenance.

## Risque factoriel et données manquantes

Le contrôle factoriel reprend la configuration de production par défaut.
Il exige les observations réellement archivées dans `stock_risk_factor_inputs`
et connues avant la décision, avec les prix historiques SPY/IWM/MTUM.
Le replay ne lance pas le rafraîchissement live, ne rétrodatera pas une
capitalisation actuelle et ne remplace pas les facteurs par zéro.

Sans contexte qualifié, la nouvelle entrée est bloquée et le bilan est
`INCOMPLETE_COVERAGE`, avec motifs et reçus. Le traitement des positions
déjà ouvertes conserve ses protections. Une bougie manquante nécessaire à
la valorisation d'une position détenue provoque un échec explicite.

Le formulaire permet de désactiver **explicitement pour ce replay** le
contrôle factoriel. Cette différence avec la production est affichée et
figée dans le protocole ; le fichier de configuration n'est pas modifié.

## Rapports et périmètre exact

Le launcher conserve les résultats dans son dossier neuf
`artifacts/ihm_backtesting_runs/run/<run-id>/artifacts` (chemin exact visible
dans la commande et le registre). Rapport et graphique sont lisibles dans
la page : `report.json`, `equity_curve.csv`, `equity_curve.png`, `trades.csv`,
`annual-summary.csv`, événements, risque 5m, reçus intraday et factoriels.
Le rapport conserve également les anciens indicateurs de recherche à plat.
Les empreintes des signaux, des daily, des secteurs et des actions sur titres
sont consignées. Un dossier existant n'est jamais écrasé.

Ce formulaire sélectionne les TOP-N Oracle dans leur ordre de score,
**LONG uniquement**, puis applique par défaut le filtre CALL/PUT + OI du
pipeline. Le même lecteur SQL, les mêmes features et la même fonction de
sélection sont utilisés. Le filtre GPT n'est pas rejoué.
Les secteurs sont actuels, les historiques daily peuvent être
révisés et les décisions de régime ne constituent pas une bande macro PIT
complète. Prix OHLC, priorité conservatrice des touches et glissement simulé
ne reproduisent pas le carnet réel. `full_live_parity` reste donc **false**.
Un résultat incomplet est signalé dans la page même si le calcul est arrivé
à la dernière séance. Les positions finales restent valorisées, sans vente
terminale artificielle.

Le mode daily classique reste accessible en décochant Winner dans l'IHM.
Sa commande porte `--no-winner-pyramiding`, override local qui évite
d'activer accidentellement Winner via le YAML global. Le CLI dédié complet
est `python -m backtesting.winner_campaign_replay --help`.
Cet override retire aussi les trois adaptations Winner du risque daily :
stop fixe, suppression du TP en prix et obligation de quantités entières.
Les autres contraintes restent intactes.

## En exploitation

Le chemin existant reste : prédiction/sélection → risque 11 → exécution 12
→ campagnes persistées → watcher du **même compte et du même mode**.
Avec confirmation positive, le watcher vérifie les clôtures 5m puis le
risque courant avant achat. Avec confirmation zéro, le chemin standard
applique le réglage dédié des cotations. Les protections sont attachées
aux fills réels et la date de sortie est calculée depuis le premier fill,
selon le calendrier officiel ; un ajout ne redémarre pas le compteur.

Chaque compte garde son propre capital, ses contraintes, ses ordres et
ses verrous. Les campagnes déjà ouvertes gardent leur politique figée :
modifier le YAML ne change pas rétroactivement leur trailing ou leur durée.
Le watcher doit rester en fonctionnement pour la sortie temporelle et les
protections locales. Les ordres stop déjà déposés restent chez le broker.

La configuration accepte désormais le SIP retardé :
`winner_pyramiding.market_data_delay_seconds: 900` et
`delayed_entry_limit_buffer_pct: 0.01`. Les confirmations utilisent les
bougies closes connues à l'heure réelle moins quinze minutes. L'ordre IOC
est limité au dernier close retardé majoré de 1 %, avec les plafonds de
risque et le plafond d'écart à la référence approuvée lorsqu'il est configuré.
Le sizing se fonde sur ce plafond, et le fill réel peut être plus bas.
Il n'y a pas de bid/ask temps réel inventé ni d'appel SIP latest pour ce chemin.
Au-dessus de la limite, aucun achat n'est garanti. `market_data_delay_seconds: 0`
conserve le chemin temps réel et ses contrôles. Aucun fallback IEX n'est ajouté.

Le délai accepte **tout entier entre 900 et 3 600 secondes**, sans obligation
de multiple de cinq minutes : `930` représente quinze minutes et trente
secondes et conserve une marge de publication. Le fichier de travail est
actuellement réglé à `930`. La grille temporelle des bougies reste cinq minutes.
Une valeur invalide est signalée dans la page Backtest, sans lancement ni
remplacement silencieux de la politique par une valeur par défaut.

Le délai est aussi reproduit dans le backtest : disponibilité après le délai,
achat à une ouverture 5m observée à partir de cette disponibilité, jamais
au cours historique de la bougie de confirmation. La sortie temporelle
compte depuis le fill réel. Le contrôle de fraîcheur résiduel reste 60 secondes
au-delà du délai, et les confirmations doivent appartenir à la séance courante.

Le cutoff options du replay est fixé une seconde avant l'ouverture de la
séance d'entrée. Cela inclut les reçus de la nuit connus à cette date, sans
lire les données options de la nouvelle séance. `options-receipts.json` et
`options-selection.csv` tracent les décisions, exclusions et empreintes des
inputs. Un historique d'OI absent ne peut pas être reconstitué avec du
volume seul ou avec les snapshots d'aujourd'hui : bilan incomplet et aucune
entrée pour les cohortes insuffisantes. L'option peut être décochée pour un
témoin Oracle brut, différence explicitement consignée dans le protocole.

### Diagnostic du premier semestre 2025, run 20261031_125841_66dcce61

La commande demande le 01/01/2025–30/06/2025, modèle parcours H10
`model-factory-20261030213826-eda503`, TOP20, 4 000 $, sans levier,
confirmation de deux bougies, filtre options et contrôle factoriel activés.
Les artefacts du run établissent :

- 122 séances, 2 440 lignes dans `signals.csv` ;
- 2 440 lignes dans `options-selection.csv`, toutes refusées avec
  `MISSING_OR_STALE_OPTIONS` ;
- 122 cohortes `covered: 0`, `incomplete: true` dans `options-receipts.json` ;
- 122 lacunes `OPTIONS_COHORT_INCOMPLETE`, aucune campagne et aucun achat ;
- reçus intraday et facteurs vides : ces contrôles n'ont pas été atteints ;
- rapport `INCOMPLETE_COVERAGE`, capital inchangé 4 000 $ ; le rendement 0 %
  ne constitue pas une performance économique mesurée.

Ce constat provient des artefacts enregistrés, pas d'une nouvelle lecture SQL
de toute la couverture options. L'accès direct MySQL était indisponible pour
ce diagnostic ; aucune borne globale d'historique en base n'est affirmée.
Les reçus postérieurs au cutoff ne peuvent pas être antidatés pour débloquer
le test. Un témoin sans options est une autre expérience explicite ; le
contrôle factoriel requiert également ses propres archives qualifiées.

L'historique IHM lit désormais les flags complets `--start-date`/`--end-date`
et les anciens `--start`/`--end`, sans confondre `-date` avec une valeur. Pour
les runs Winner terminés, le badge consulte le statut du rapport/progress :
`INCOMPLETE_COVERAGE` devient **orange, couverture incomplète**, même lorsque
le processus est sorti normalement avec le code zéro. Le journal d'exécution
et les résultats historiques ne sont pas réécrits. L'avertissement apparaît
avant le chargement facultatif du rapport détaillé ; le résumé explique aussi
le cas où le filtre options a bloqué toutes les entrées.

Régressions ciblées : 59 tests réussis (dates/labels, page Backtesting et
sélection options historique). Aucun ordre, appel fournisseur, modification
SQL ni nouveau replay n'a été exécuté pour ce correctif d'affichage.

### Run 20261031_151056_45eba031 : anomalie d'horloge SIP retardée

Période demandée 06/07/2021–29/10/2026, 1 337 séances, même Oracle H10,
TOP20, 4 000 $, confirmation 2, délai 930 s, fraîcheur résiduelle 60 s,
filtre options désactivé, contrôle factoriel activé. Les artefacts indiquent
26 740 sélections et 2 409 campagnes/plans créés, sans aucun fill d'achat.

`events.csv` contient 3 204 761 refus `DELAYED_SIP_UNQUALIFIED`, 479 001
refus de référence de séance précédente, 60 022 absences de bougie candidate
et 44 budgets de signal insuffisants. Les lacunes distinctes du rapport se
répartissent en 5 619 `SIGNAL_RAW_5M_INCOMPLETE`, 7 192
`CANDIDATE_RAW_5M_INCOMPLETE` et 6 802 `PRIOR_RAW_5M_INCOMPLETE`.
Les reçus factoriels sont vides : la réapprobation factorielle n'a pas été
atteinte, ce qui ne qualifie pas sa disponibilité historique.

L'ancien replay ne testait les campagnes qu'aux ouvertures 5m. Avec
930 secondes de délai, le cutoff tombe 30 secondes avant une borne 5m : la
dernière bougie achevée a donc 270 secondes d'ancienneté résiduelle, contre
60 autorisées. Cela bloque même une série de données parfaitement complète.
Reproduction synthétique sur la séance officielle du 06/07/2021 : 74/78
instants qualifiés avec un délai 900 s, **0/78 avec 930 s** ; le même jeu
de bougies devient frais à l'instant de disponibilité décalé de 30 secondes.

Le paramètre 930 s est valide en exploitation avec un watcher au bon instant.
Le défaut venait du raccordement à l'horloge du replay ; ce résultat ne
prouvait pas une absence d'occasions de trading.

### Correctif du replay SIP décalé, 31 octobre 2026

`backtesting/winner_clock.py` sépare l'horloge de disponibilité des preuves
de celle des prix observés. Avec un délai de 930 secondes, les confirmations
sont évaluées aux bornes 5m décalées de 30 secondes. Le délai figé, la
fraîcheur résiduelle de 60 secondes et les cutoffs historiques sont conservés.

Les bougies 5m ne donnent pas le prix exact trente secondes après leur
ouverture. Pour un signal entre deux bornes, le replay réserve le capital,
fige la quantité et la limite approuvées, puis tente une seule exécution à
l'ouverture 5m suivante de la même séance. Une ouverture absente, un cours
au-dessus de la limite ou une capacité insuffisante annulent cet ordre.
Une nouvelle décision ultérieure reste possible, mais cet ordre précis ne
peut attendre une ouverture plus favorable, exploiter un low futur ou être
reporté au lendemain. C'est un **proxy d'exécution IOC pour la recherche**,
pas la reproduction d'un véritable IOC envoyé au moment du signal.

Les décisions et exécutions ont leurs horodatages distincts dans `events.csv`
(`DELAYED_ENTRY_DECISION`, `BUY_FILL`, `DELAYED_ENTRY_CANCELED`). Le contrat
`replay_clock` est conservé dans le protocole et le rapport ; la page IHM
explique cette approximation. `full_live_parity` reste faux. Les ajustements
de stop décidés entre deux bornes prennent effet à l'ouverture suivante ;
l'ancien stop reste actif jusque-là, sans appliquer le nouveau seuil au low
déjà passé. À la fin de séance, le dernier ajustement ne peut affecter la
bougie qui le précède ; son seuil est applicable à l'ouverture suivante.

Le coordinateur traite séparément la réconciliation, la protection des lots,
l'expiration et l'échéance sur l'horloge des prix. L'entrée standard sans
confirmation conserve son exécution à l'ouverture. Les fills différés sont
réconciliés avant le contrôle de liquidation globale ; une coupure déjà
connue annule l'achat en attente avant son exécution. Le budget partagé,
les frais, les limites de levier et les contrôles natifs restent appliqués.

Validation hors ligne sur un échantillon synthétique : signal qualifié à
14:00:30 UTC, achat au prix de **103 $ à 14:05 UTC**, sans utiliser ni le cours
de 102 $ de la preuve retardée, ni l'ouverture de 101 $ à 14:00. Les cas
de limite dépassée, ouverture manquante, réservation de capital, absence de
facteurs historiques, liquidation, clôture anticipée et échéances H10/H20
sont couverts dans `tests/test_winner_replay_clock.py`.
Suite Winner : 326 tests réussis lors de la passe élargie ; après le dernier
raccordement de réconciliation avant liquidation, 69 tests ciblés réussis
(horloge, replay intraday, SIP retardé et liquidation globale).

Les archives d'origine restent inchangées. Le prochain processus de
backtest chargera le correctif. Aucun replay économique sur cinq ans, ordre,
appel fournisseur ou changement des services en fonctionnement n'a été lancé.
Les lacunes de bougies du run d'origine restent à qualifier. Le contrôle
factoriel peut désormais être atteint : son absence éventuelle doit encore
produire un refus et un bilan incomplet, jamais un facteur antidaté ou un
contrôle désactivé implicitement.

### Contrat SIP du watcher en exploitation (rappel)

Redémarrer le watcher pour charger ce nouveau contrat avant une nouvelle
étape 12. Le contrôle d'ancienneté du code refuse l'ancien processus.
Les anciennes campagnes gardent leurs paramètres figés, y compris le délai
zéro lorsqu'il n'était pas renseigné : cette mise à jour ne réécrit ni plans
existants ni positions. Les nouveaux paramètres concernent les nouvelles admissions.

**Le moteur Winner comporte les chemins PAPER et live, mais les filtres
options/LLM actuels conservent leur restriction PAPER.** Ce raccordement ne
les autorise pas en argent réel, ne bascule aucun compte et ne démarre
aucun watcher. Les tests d'exécution restent simulés.

## Validation technique

Suite Winner/exécution/registre/commandes : 309 tests réussis. Vérifications
ciblées supplémentaires après durcissement des folds et du mode daily :
65 tests réussis, avec contrats H10/H15/H20. Les scénarios comprennent le
vrai formulaire Streamlit, parsing de la commande produite, replay complet
sur base SQLite surveillée SELECT-only, rapports réutilisables par l'IHM,
blocage des données factorielles futures/manquantes, passage du contexte au
contrôle natif, confirmations, protections, échéance et reprise idempotente.
La base de production, les ordres et les services en fonctionnement n'ont
pas été modifiés par ces tests.

Complément SIP retardé/options : tests de parité de sélection avec le pipeline,
cutoffs et refus des reçus futurs, absence de substitution du rang suivant,
achat au prix ultérieur et refus au-dessus du plafond, revalidation native,
preuve retardée sans faux marqueur temps réel et idempotence du premier achat.
Suite élargie après raccordement : **364 tests réussis** (Winner, options,
commandes, formulaire et registre), complétée par les régressions du mode
zéro confirmation et du plafond d'écart approuvé. Aucun test n'a envoyé
d'ordre ni appelé de fournisseur.

Voir aussi [entrée standard](winner_standard_entry.md),
[cotations standard](winner_standard_entry_quotes.md),
[alignement SL/sizing](winner_sl_sizing_alignment_20261030.md) et
[risque factoriel](risk_factor_inputs.md).
