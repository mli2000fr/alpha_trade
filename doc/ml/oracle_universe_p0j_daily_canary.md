# P0j — Canary quotidien de l'Oracle dynamique

## Statut et périmètre

P0j est implémenté comme **canary shadow uniquement** pour le batch
`model-factory-20260909051302-323684`. Il automatise la surveillance ouverte
par P0i, sans transformer l'Oracle en stratégie directionnelle.

P0j n'écrit jamais dans `oracle_extreme_predictions`, `model_predictions`, les
tables de risque ou les tables d'ordres. Tous ses états sont des fichiers JSON
et Parquet sous `artifacts/models/oracle/canary`.

## Cycle quotidien

```text
Dernière séance SPY disponible
        │
        ▼
Admission P0b quotidienne PIT
        │
        ▼
Prédiction Oracle shadow
        │
        ├── Parquet de scores isolé
        ├── TOP20 informatif
        └── trading_eligible=false
        │
        ▼
Contrôle immédiat
  couverture + distribution + PSI
  comparés aux 230 jours de P0i
        │
        ▼
Recherche des anciens runs arrivés à D+20
        │
        ▼
Labels post-hoc dry-run + performance réalisée
```

## Configuration

Le fichier [oracle_canary.yaml](../../config/oracle_canary.yaml) contient :

- le batch et le fichier d'univers ;
- le run P0i utilisé comme baseline de distribution ;
- l'horizon H20 ;
- le répertoire d'artefacts ;
- les horaires et jours de la tâche Windows ;
- le minimum de vingt dates réalisées avant d'émettre un contrôle de
  performance glissant.

Le canary choisit la dernière date disponible pour SPY. Il doit donc être lancé
après la collecte EOD ; le défaut est 23 h, du lundi au vendredi.

### Situation locale depuis le 10 juillet 2026

La table `stock_bars_daily` n'est volontairement plus alimentée après le
10 juillet 2026, la connexion EODHD ayant été arrêtée. Le canary travaille donc
sur la dernière donnée locale existante ; il ne tente pas de télécharger ou de
fabriquer des barres manquantes.

Tant que cette alimentation reste suspendue, une exécution planifiée retrouve
le 10 juillet 2026 et répond `already_completed`. Elle n'apporte aucune nouvelle
date au suivi H20. Cette limitation n'empêche ni l'analyse des historiques déjà
présents, ni les expériences ML OOF menées sur ces données.

La date de coupure doit être relue comme un **cutoff de données volontaire** et
non comme une panne du canary ou une dérive du modèle.

## Idempotence et concurrence

`index.json` est indexé par date de prédiction. Une seconde exécution le même
jour retourne `already_completed` et n'ajoute aucun score. `--force` est réservé
au diagnostic manuel.

Un verrou `.lock` interdit deux processus simultanés. La tâche Windows utilise
également `MultipleInstances IgnoreNew`. Les écritures d'état passent par un
fichier temporaire puis un remplacement atomique.

## Contrôle de dérive immédiat

Le KS/PSI brut contre toutes les observations P0i est conservé comme information,
mais ne pilote pas seul le statut : avec environ 2 000 scores quotidiens, une
p-value KS peut devenir faible pour un changement minime.

Le statut opérationnel compare le jour aux distributions **quotidiennes** de la
baseline P0i :

- PSI du jour contre quantiles empiriques 95 % et 99 % ;
- taille d'univers contre quantiles 1 % et 99 % ;
- moyenne du score contre la bande empirique 1–99 % ;
- âge du champion, signalé après 365 jours.

`ALERT` reste une alerte de shadow : il n'existe aucun kill-switch trading à
actionner puisque P0j n'alimente aucun consommateur de trading.

## Évaluation retardée H20

Un run devient évaluable seulement lorsqu'au moins H20 plus une séance de
publication existent dans le calendrier SPY. P0j reconstruit alors les labels
avec le contrat canonique de qualité et `dry_run=True`.

Pour chaque date, il conserve : AUC extrême, précision/rappel TOP20, lift
d'amplitude TOP20, amplitude moyenne du TOP20 et taux de rendements positifs
informatif. Avant vingt dates réalisées, le statut est
`INSUFFICIENT_HISTORY`.

Sur les vingt dernières dates réalisées :

- `ALERT` si AUC < 0,60 ou lift TOP20 < 1,15 ;
- `WARN` si AUC < 0,70 ou lift TOP20 < 1,40 ;
- `OK` sinon.

Ces seuils sont des garde-fous de détérioration forte, pas des paramètres de
sélection de trades.

## Utilisation manuelle

Lancer le canary :

```powershell
python -u -m modelFactory.oracle_canary
```

Consulter l'état sans lancer de prédiction :

```powershell
python -m modelFactory.oracle_canary --status
```

Forcer une date uniquement pour un diagnostic :

```powershell
python -u -m modelFactory.oracle_canary --prediction-date 2026-09-08 --force
```

## Tâche Windows

Installation interactive :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_oracle_canary_task.ps1
```

Lancement immédiat après installation :

```powershell
Start-ScheduledTask -TaskName AlphaTrade-OracleCanary
```

Suivi :

```powershell
Get-Content .\log\batch\oracle_canary.txt -Tail 50 -Wait
```

Désinstallation :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_oracle_canary_task.ps1
```

La tâche n'est pas installée automatiquement par le code.

### Caractère optionnel et retrait propre

La tâche Windows est un confort de surveillance, pas une dépendance de
l'entraînement, de la prédiction applicative ou du backtest. Elle peut rester
absente tant que les données EOD ne sont plus actualisées.

Pour vérifier si elle existe :

```powershell
Get-ScheduledTask -TaskName AlphaTrade-OracleCanary -ErrorAction SilentlyContinue
```

Pour la retirer si elle a été installée :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_oracle_canary_task.ps1
```

La désinstallation supprime uniquement la tâche planifiée. Elle ne supprime ni
le batch, ni les rapports P0i/P0j, ni les Parquet déjà produits. Pour neutraliser
également un lancement manuel accidentel, définir `enabled: false` dans
`config/oracle_canary.yaml`. Ces deux opérations sont réversibles.

## Artefacts

```text
artifacts/models/oracle/canary/<batch>/
├── index.json
├── predictions/<batch>/oracle-shadow-.../
│   ├── report.json
│   ├── canary_report.json
│   └── parts/part-00000.parquet
└── evaluation_batches/labels-....parquet
```

`index.json` constitue le registre opérationnel : dates traitées, rapports de
dérive, évaluations retardées et état glissant. Il demeure explicitement
`research_only` et `trading_eligible=false`.

## Critère de sortie de P0j

Une promotion ultérieure exige au minimum plusieurs semaines de canary, vingt
dates H20 réalisées, un statut glissant non dégradé et une revue manuelle. Même
dans ce cas, seule la fonction amplitude peut être promue. La direction D1/D10
reste un problème séparé.

## Premier canary validé — 10 juillet 2026

Le premier run réel a terminé en 4 min 56 s avec un code retour nul :

- 2 097 symboles admis et scorés ;
- 420 symboles dans le TOP20, soit 20,03 % ;
- PSI contre la baseline P0i : 0,0182, sous le quantile empirique 95 % de
  0,0710 ;
- moyenne du score : 0,4328, dans la bande empirique 1–99 %
  `[0,4175 ; 0,4803]` ;
- taille d'univers dans la bande empirique `[1 927 ; 2 102]` ;
- zéro ligne dans `oracle_extreme_predictions` et `model_predictions`.

Le statut immédiat est `WARN` uniquement parce que le champion a 548 jours
calendaires. Le `raw_two_sample_drift` indique `ALERT` à cause de la p-value KS,
mais il est volontairement informatif : avec près de 490 000 observations de
baseline, il réagit à un faible écart alors que PSI, couverture et moyenne sont
normaux. Le statut empirique P0j est celui à retenir.

`matured_evaluated=0` est normal : les barres disponibles s'arrêtent à la date
prédite, donc le rendement D+20 du 10 juillet n'est pas encore observable dans
la base locale.

## Validation de l'évaluation retardée

Un canary de contrôle a ensuite été exécuté au 9 juin 2026, première date
disposant à la fois de D+20 et de la séance de publication suivante. La chaîne
automatique a produit `matured_evaluated=1` :

- 2 041 scores shadow, dont 2 033 labels H20 valides ;
- AUC réalisée : 0,8044 ;
- précision et rappel TOP20 : 47,17 % ;
- lift d'amplitude TOP20 : 1,884 ;
- amplitude absolue moyenne TOP20 : 12,16 % ;
- `delayed_monitor=INSUFFICIENT_HISTORY`, une date disponible sur vingt
  requises.

Cette observation unique valide le fonctionnement technique du monitoring
retardé. Elle ne constitue pas à elle seule une nouvelle validation statistique,
qui reste celle de P0i sur 230 séances.
