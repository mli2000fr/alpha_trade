# Étape 11 options — univers et reprise contrôlée (27 octobre 2026)

## Incident vérifié

Le run options `opt-d1682793383e4fedb878c37c4dfdf6ff` était complet pour la séance
du 26 octobre, avec le preset d'univers `capital_2001_5000`. Le moteur risque
recalculait à tort le preset d'univers depuis l'equity de 1 974,30 $, choisissant
`capital_0_2000`, pour lequel aucune publication n'existait.

La lecture SQL a confirmé une publication canonique `full` du 26 octobre pour
`capital_2001_5000` : 1 790 lignes écrites/attendues, 1 138 tradables.
Le rapport options sélectionnait MRVL et INTC ; cette sélection n'est ni une
approbation du risque ni une preuve d'exécution.

## Correctifs

- Le preset d'univers de l'étape 11 vient du rapport options déjà qualifié.
- Le capital réel et les paramètres de sizing ne sont pas remplacés par les
  valeurs du preset d'univers. Les protections existantes restent applicables.
- Les presets invalides, les univers absents/incomplets et les symboles non
  tradables ne bénéficient d'aucun fallback permissif.
- Verrou système exclusif par sélection, identifiant unique par tentative et
  archivage du claim précédent. Une reprise n'est autorisée automatiquement
  qu'avec une preuve liée par empreintes à l'échec du chargement d'univers,
  avant publication de décisions/cibles. Une issue inconnue reste bloquée.
- Toute sortie de risque même partielle, tout binding et toute tentative
  d'exécution interdisent ce chemin de reprise. Le claim d'exécution reste unique.

## Libération ciblée de l'ancien claim

Sur autorisation utilisateur, l'ancien `risk.claim.json` a été déplacé, sans
suppression, vers :

`artifacts/options_directional/opt-d1682793383e4fedb878c37c4dfdf6ff/risk_attempts/legacy-20261027_013903_7909b6cc/risk.claim.json`

Le reçu voisin `recovery.json` conserve les empreintes du claim, du rapport,
du record IHM terminalement échoué et du journal d'erreur. Vérifications : aucun
processus de risque correspondant actif, sceaux intacts, aucun résumé/binding
ni claim d'exécution. Le journal situe l'échec avant publication du portefeuille.

Aucune écriture SQL, aucun appel broker, aucun ordre, aucune relance de 10/11/12
n'ont été effectués pendant cette remédiation. Une relance manuelle de 11 reste
soumise à la fenêtre avant ouverture J+1, la fraîcheur et tous les garde-fous.
Si le rapport n'est plus qualifiable, refaire 10 puis 11, sans réutiliser de force
une analyse ancienne. L'avertissement legacy `market_code absent` n'était pas
la cause de cet incident ; ce correctif ne supprime pas les contrôles de marché.

## Vérification hors ligne

119 tests passent : `test_risk_management_cli`, `test_options_universe_preset`,
`test_options_risk_attempts`, `test_llm_universe_preset`,
`test_options_directional_orchestration`, `test_options_directional_filter`,
`test_options_directional_pipeline`, `test_options_oracle_coverage_clock`.
Les sous-processus/brokers sont simulés dans les tests d'orchestration.

## Seconde tentative à 07:59 — workflow 11 → 12 sans étape 10

Le journal recopié à 01:39 était celui de l'ancien échec. Le nouveau run IHM
`20261027_075907_802e18fe` a bien utilisé le code modifié, mais son parent
`20261027_075907_dac71030` a généré à tort un nouvel identifiant
`opt-574f84b1884e408ba9f4df0311059bc9` pour un workflow ne contenant que 11/12.
Aucun rapport de filtre ne correspondait à ce nouvel identifiant ; le wrapper
a échoué en lecture de `report.json`, avant d'appeler le moteur de risque.

Le registre de workflows génère désormais un nouvel ID seulement lorsqu'il
inclut 10. Sans 10, il qualifie et fige un rapport existant pour la même séance,
le même modèle, univers, compte et preset. Le choix reste immuable jusqu'à 12 ;
un identifiant explicite invalide ne bénéficie d'aucune substitution.

Contrôle en lecture seule à 08:03 : les commandes préparées pour 11 et 12
pointent toutes deux vers `opt-d1682793383e4fedb878c37c4dfdf6ff` (séance du 26).
Rapport scellé et fenêtre temporelle validés par le lecteur normal ; aucune
commande de risque/exécution n'a été lancée.

98 tests passent sur le raccordement des workflows, le registre de processus,
l'orchestration options, les reprises et les presets. Les hooks SQL et SMTP du
test du registre sont neutralisés ; les tests de cycle de vie démarrent/arrêtent
seulement des processus Python de test isolés.

## Qualification des contrôles fournisseurs / contrat Oracle

L'évaluation de 08:04 a terminé 11/12, mais sans cible : MRVL et INTC étaient
refusés pour `MISSING_OR_DUPLICATE_SESSIONS`, puis le contrôle de compatibilité
recherchait l'ancien registre de champions par symbole.

Le diagnostic en lecture seule a établi :

- fenêtre requise : 61 séances du **31 juillet au 26 octobre** ; aucune barre
  du 27 octobre n'était demandée avant l'ouverture ;
- pour chaque titre : 66 lignes, 61 dates distinctes, aucune date manquante ;
  cinq dates avaient la paire EODHD/SIP ;
- après priorité EODHD : 55 lignes EODHD et 6 SIP, soit une ligne réelle par
  séance, sans fabrication de cours ni mélange prix/volume ;
- le contrat Oracle parcours est valide, contrairement au registre legacy
  `artifacts/model_registry.json` qui n'est pas son format de publication.

Le contrôle des nouvelles entrées applique désormais le sélecteur canonique de
fournisseurs **par titre**. Les doublons d'un même fournisseur et sources
concurrentes inconnues restent refusés ; un titre ambigu ne bloque pas les autres.
Une ligne du fournisseur préféré invalide, synthétique ou future n'est pas
remplacée par une alternative pour contourner le contrôle. Les chargements
risque prix/ATR/ADV et corrélations utilisent la même priorité SQL **avant** les
limites de lignes et calculs glissants.

Le risque Oracle parcours utilise `risk_management.oracle_path_contract` :
protocole terminé/servable, empreintes des poids/profil, fold causal exact,
univers, identité du batch/run synthétique, source `oracle_path_policy`, date
exacte, score d'amplitude borné et lineage présent au cutoff UTC. Aucune création
d'un faux registre, aucun score d'amplitude assimilé à P(LONG), aucun Kelly.
Les erreurs de lecture/validation restent bloquantes.

La fraîcheur EOD est qualifiée par la dernière séance réellement clôturée,
son délai de publication et l'échéance avant l'ouverture suivante. Cela remplace
pour ce modèle le proxy legacy « minuit de J vieux de plus de cinq minutes » ;
les limites de quotes SIP, liquidité, risque, watcher et exécution ne sont pas
désactivées. Le chemin classique conserve son registre et ses contrôles existants.

Contrôle réel en lecture seule à 08:21 : contrat compatible, fold causal
`2026-01-08`, 10 folds vérifiés ; barres et objets prix/ATR/ADV MRVL/INTC qualifiés
au 26 octobre. Aucun calcul de portefeuille publié, écriture SQL ou ordre.

Le run de risque déjà terminé à zéro cible reste immuable. Pour une nouvelle
évaluation métier avec ces correctifs, créer une nouvelle analyse via 10, puis
11 ; ne pas effacer son résumé/binding/claim pour forcer une réutilisation.

Non-régression finale : **200 tests passent**, incluant les lecteurs de cours
risque, les choix EODHD/SIP, les contrôles de métadonnées, les contrats Oracle
valables/corrompus/futurs, le CLI risque classique et les raccordements options.
Commande de tests (sans fournisseur, broker ni ordre réel) :

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_risk_oracle_path_contract.py tests/test_new_entry_data_guard.py tests/test_risk_management_cli.py tests/test_daily_bar_sources.py tests/test_oracle_path_serving.py tests/test_risk_daily_source_readers.py tests/test_options_oracle_coverage_clock.py tests/test_options_directional_filter.py tests/test_options_universe_preset.py tests/test_options_directional_orchestration.py tests/test_options_risk_attempts.py tests/test_pipeline_log_freshness.py tests/test_options_workflow_resume_binding.py -o addopts='' --no-cov -q
```
