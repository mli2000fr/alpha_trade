# Watcher de protections — guide dédié

## Objectif

Ce document décrit le rôle, le positionnement et l'exploitation du watcher de protections post-exécution.

Le watcher sert à surveiller, après `Execution`, les protections broker-side afin de faire évoluer le cycle de vie :

- stop initial broker-side ;
- conditions de transition ;
- promotion vers trailing stop dynamique ;
- supervision de santé dans l'IHM.

---

## 1. Ce que le watcher est — et n'est pas

### Ce qu'il est

Le watcher est un **runtime post-exécution**.

Il intervient quand l'étape 12 `Execution` a déjà soumis les ordres et créé des protections à surveiller.

### Ce qu'il n'est pas

- ce n'est pas une étape 15 du pipeline ;
- ce n'est pas un composant de préparation amont ;
- ce n'est pas un simple mécanisme de secrets Windows.

Les secrets Windows (`.env`, DPAPI) servent uniquement à l'exploiter proprement.

---

## 2. Positionnement par rapport au pipeline 1 → 14

Ordre recommandé :

1. étapes `1 → 11` : préparation ;
2. étape `12 execution` ;
3. **watcher post-exécution** ;
4. étapes `13 → 14 corporate actions`.

Le watcher peut donc tourner **pendant** les Corporate Actions.

Règle pratique :

- si vous êtes en manuel, lancez un watcher `once` juste après `Execution` ;
- si vous êtes en exploitation, préférez un watcher périodique (`Task Scheduler`) ou persistant (`NSSM`).

### 2.1 Le watcher est-il nécessaire ? indispensable ?

Réponse courte :

- **non**, le watcher n'est pas indispensable pour "terminer" le pipeline `1 → 14` ;
- **oui**, il devient nécessaire dès que vous voulez **surveiller réellement après exécution** les protections créées à l'étape 12.

En pratique :

- si `Execution` n'a rien soumis, rien rempli ou rien armé côté broker, lancer le watcher n'apporte généralement rien ;
- si `Execution` a créé des positions / protections à suivre, il faut qu'un watcher prenne le relais juste après ;
- si un watcher Windows est déjà en place (`Task Scheduler` ou `NSSM`), il n'est pas nécessaire d'en relancer un second depuis l'IHM.

Règle opérateur simple :

> Pas obligatoire pour faire avancer le pipeline, mais indispensable pour exploiter correctement la surveillance post-exécution quand des protections sont en jeu.

### 2.2 Qu'est-ce qui protège le watcher — et que protège-t-il réellement ?

Il faut distinguer deux choses :

1. **la protection des ordres / positions** ;
2. **la surveillance post-exécution** assurée par le watcher.

#### Ce qui protège d'abord les ordres

L'étape `12 Execution` soumet l'ordre d'entrée puis, **dès qu'il est rempli**, ses enfants broker-side :

- un **take-profit** ;
- un **stop initial broker-side** dans le cas nominal ;
- et, en cas d'échec sur ce stop initial, un **trailing fallback** peut être soumis directement par `Execution`.

> ⚠️ **Cas marché fermé (overnight cash swing)** — Si l'entrée est soumise hors RTH (profil `overnight_cash_swing` utilisé par les presets `paper`/`live`), elle ne sera remplie qu'à la prochaine ouverture. Historiquement, les enfants TP/SL n'étaient alors jamais armés (gap S26). Depuis le sprint S26, deux **filets de sécurité** comblent ce trou :
>
> 1. **Phase 7b dans `executor.py`** — après `BrokerStateSynchronizer.sync`, l'executor recherche les parents `FILLED` sans enfants ouverts (`db_io.load_unprotected_filled_parents`) et arme TP/SL via `_submit_children`. Métriques : `children_armed_post_sync`, `children_armed_post_sync_failed`.
> 2. **Filet watcher (`_arm_missing_protections`)** — à chaque tick, le watcher rejoue la même requête et arme TP/SL pour les positions oubliées (entrée remplie après terminaison de l'executor). Métriques : `armed_missing_protections`, `armed_missing_protections_failed`. Événement audit : `CHILDREN_SUBMITTED` avec `trigger="watcher_safety_net"`.

Autrement dit : la première couche de protection est portée par `Execution`, mais **le watcher en est désormais le filet de rattrapage obligatoire** dès que l'entrée est soumise hors marché.

#### Ce que fait ensuite le watcher

Le watcher prend le relais **après** `Execution` pour :

- relire les protections encore ouvertes ;
- vérifier si le trigger métier de transition est atteint ;
- annuler le stop initial ;
- promouvoir ce stop vers un **trailing stop dynamique** ;
- **armer TP/SL manquants** pour les parents `FILLED` sans enfants (filet de sécurité S26) ;
- journaliser et superviser cet état dans l'IHM / Windows.

Le watcher ne sert donc pas à "faire partir" l'ordre d'entrée. Il sert à **gérer intelligemment la vie de la protection après exécution** et à **garantir que toute position remplie a bien TP + SL**.

### 2.3 Si je ne lance pas le watcher, les ordres seront-ils exécutés ?

**Oui pour les entrées, mais attention pour les protections.**

Les ordres d'entrée sont soumis par `Execution`, pas par le watcher. Mais les enfants TP/SL **ne sont armés que lorsque l'entrée est remplie** :

- **Marché ouvert pendant le run** : `Execution` poll les fills puis arme TP/SL immédiatement → watcher non requis pour ce cas.
- **Marché fermé (overnight cash swing)** : l'entrée est remplie à la prochaine ouverture, **après** la terminaison de l'executor. Sans watcher, **TP/SL ne seraient jamais armés** côté broker. Le filet S26 de l'executor (Phase 7b) ne couvre que la fenêtre où le marché ouvre pendant le run lui-même.

Donc, si `Execution` réussit :

- l'ordre principal peut être exécuté ;
- le take-profit peut être armé (Phase 7b ou watcher) ;
- le stop initial broker-side peut être armé (Phase 7b ou watcher) ;
- un trailing fallback peut parfois exister dès `Execution` si le stop initial n'a pas pu être soumis.

Le watcher est donc **fortement recommandé en exploitation overnight** : c'est lui qui garantit l'armement TP/SL après ouverture.

### 2.4 Quelle conséquence si je ne lance pas le watcher ?

La conséquence principale n'est **pas** "aucun ordre ne part".

La vraie conséquence est :

- vous perdez la **surveillance post-exécution** ;
- le **stop initial** risque de rester en place plus longtemps que prévu ;
- la **transition vers trailing stop dynamique** ne se fera pas automatiquement ;
- vous perdez une partie de la **visibilité opérateur** (logs live, historique watcher, heartbeat, supervision de santé).

En résumé :

- **sans watcher**, l'exécution peut très bien avoir lieu ;
- **sans watcher**, la stratégie de gestion dynamique des protections après exécution est incomplète ou absente.

#### Cas où l'absence de watcher est peu gênante

- aucun ordre n'a été exécuté ;
- aucune protection n'a été créée ;
- ou un watcher Windows tourne déjà correctement ailleurs.

#### Cas où l'absence de watcher est réellement problématique

- des positions ont été ouvertes ;
- un stop initial est bien posé et doit potentiellement être promu ;
- vous comptez sur la logique de transition dynamique du trailing ;
- vous voulez une supervision opérationnelle claire de ce cycle de vie.

### 2.5 Tableau ultra-simple — que se passe-t-il sans watcher ?

| Cas | Sans watcher ? | Commentaire |
|---|---|---|
| Achat exécuté | **Oui** | Si `Execution` a bien soumis l'ordre d'entrée. |
| Stop initial / TP armés (marché ouvert pendant le run) | **Oui** | `Execution` poll fills + Phase 7b. |
| Stop initial / TP armés (entrée hors RTH, fill à l'ouverture suivante) | **Non** | Sans watcher, TP/SL ne sont jamais armés (gap S26). |
| Trailing dynamique automatique | **Non** | Cette promotion post-exécution dépend du watcher. |

---

## 3. Modes disponibles

## 3.1 Mode `once`

Commande :

```powershell
python run_execution_protection_watch.py --mode once --account default
```

À utiliser pour :

- un contrôle ponctuel après un run `Execution` ;
- un dépannage ;
- un usage manuel depuis l'IHM ou le terminal.

## 3.2 Mode `service`

Commande :

```powershell
python run_execution_protection_watch.py --mode service --account default
```

À utiliser pour :

- une surveillance continue pendant la session ;
- un service persistant ;
- une exploitation industrialisée avec heartbeat.

---

## 4. Modes de lancement recommandés

### 4.1 Depuis l'IHM

Dans `Supervision Ops`, l'opérateur peut :

- lancer un `run watcher once` ;
- démarrer / arrêter / relancer un service local IHM ;
- suivre les logs live et l'historique ;
- consulter le statut Windows réel read-only.

### 4.2 Task Scheduler

Recommandé si vous voulez un scan périodique simple :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_task.ps1 -TaskName "AlphaTrade-ProtectionWatcher" -FrequencyMinutes 5 -Account default
```

### 4.3 NSSM

Recommandé si vous voulez un service persistant :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_service_nssm.ps1 -NssmExePath "C:\tools\nssm\win64\nssm.exe" -ServiceName "AlphaTradeProtectionWatcher" -Account default -StartAfterInstall
```

---

## 5. Quel mode choisir ?

### Cas simple / robuste

Choisir :

- `Task Scheduler`
- mode `once`

Si vous voulez :

- peu de complexité ;
- un comportement périodique ;
- une exploitation Windows simple.

### Cas supervision continue

Choisir :

- `NSSM`
- mode `service`

Si vous voulez :

- un process persistant ;
- heartbeat continu ;
- supervision plus fine.

### Cas opérateur / dépannage

Choisir :

- `Supervision Ops`
- ou le CLI `once`

Si vous voulez :

- vérifier un comportement juste après `Execution` ;
- faire un contrôle ponctuel ;
- diagnostiquer sans toucher au packaging Windows.

---

## 6. Interaction avec Windows

Les scripts Windows associés sont :

- `scripts/windows/protection_watcher_launcher.ps1`
- `scripts/windows/install_protection_watcher_task.ps1`
- `scripts/windows/install_protection_watcher_service_nssm.ps1`
- `scripts/windows/protection_watcher_secrets.ps1`
- `scripts/windows/get_protection_watcher_status.ps1`

Depuis l'IHM, seuls les usages suivants sont autorisés :

- lecture read-only du statut Windows ;
- import de logs Windows ;
- affichage des commandes recommandées.

L'IHM n'installe ni NSSM ni Task Scheduler et n'exécute pas de PowerShell arbitraire.

---

## 7. Où regarder dans l'IHM ?

### Page `Pipeline`

Un bloc `12.bis` rappelle désormais :

- quand lancer le watcher ;
- dans quel ordre ;
- avec quelles commandes.

### Page `Supervision Ops`

On y trouve :

- pilotage local IHM ;
- logs live ;
- historique watcher IHM ;
- statut Windows read-only ;
- import de logs NSSM / Task Scheduler.

---

## 8. Procédure onboarding opérateur en 5 minutes

Objectif : permettre à un nouvel arrivant de savoir **quand** lancer le watcher, **où** regarder, et **quoi faire** sans toucher au packaging Windows.

### Étape 1 — retenir le bon ordre

Mémoriser la séquence suivante :

```text
1 → 11 préparation
12 execution
watcher post-exécution
13 → 14 corporate actions
```

Le watcher vient **après** `Execution`, pas avant.

### Étape 2 — décider s'il faut le lancer

Poser la question suivante :

- l'étape `12 Execution` a-t-elle créé des ordres / fills / protections à surveiller ?

Si :

- **non** → pas de watcher requis immédiatement ;
- **oui** → lancer un watcher `once` au minimum, ou laisser tourner le watcher Windows déjà prévu en exploitation.

### Étape 3 — choisir le bon mode

- **nouvel arrivant / usage manuel** : utiliser `run watcher once` ;
- **surveillance continue locale de session** : service local IHM ;
- **exploitation Windows stable** : `Task Scheduler` ou `NSSM`.

Point de départ recommandé pour un onboarding :

- ouvrir `Pipeline` ;
- lire le bloc `12.bis` ;
- cliquer ensuite sur `Supervision Ops` pour voir le pilotage, les logs et l'historique.

### Étape 4 — vérifier qu'un watcher existe déjà

Avant de lancer un watcher manuel :

- regarder dans `Supervision Ops` si un watcher local IHM est déjà actif ;
- regarder le statut Windows read-only si un service/tâche packagé(e) tourne déjà ;
- éviter de doubler inutilement un watcher Windows déjà sain.

### Étape 5 — faire le contrôle minimum attendu

Une fois le watcher lancé :

- vérifier que le run apparaît dans l'historique watcher IHM ;
- vérifier que les logs live remontent sans erreur bloquante ;
- confirmer que le watcher traite bien le bon compte / le bon contexte d'exécution.

### Commande réflexe pour un opérateur débutant

```powershell
python run_execution_protection_watch.py --mode once --account default
```

Si vous hésitez, commencez par ce mode `once` : c'est le plus simple et le moins risqué.

---

## 9. Résumé opérateur

### Phrase à retenir

> Le watcher n'est pas le 15e pipeline : c'est le gardien post-exécution des protections, à lancer juste après l'étape 12 `Execution`.

### Ordre simple

```text
1 → 11 préparation
12 execution
watcher post-exécution
13 → 14 corporate actions
```

### Recommandation pratique

- manuel : `once` juste après `Execution` ;
- exploitation simple : Task Scheduler ;
- exploitation continue : NSSM.



---

## Phase 6.3 (refactor) — leader election, allowlist scripts, sécurité secrets

### Leader election via `execution_locks`

`ProtectionWatcherService.run(...)` acquiert un lock SQL avant de démarrer
sa boucle :

```sql
INSERT INTO execution_locks (account_id, locked_by_run_id, acquired_at, expires_at)
VALUES ('watcher:<account_id>', '<service_run_id>', NOW(), NOW() + ttl)
```

- **Préfixe `watcher:`** : distingue ce lock de celui de `executor.execute_run`
  (Phase 1.2). Deux instances de watcher pour le même compte ne peuvent pas
  coexister, mais un watcher peut tourner pendant qu'un executor utilise son
  propre lock.
- **TTL = 4 × `heartbeat_interval_seconds`** (min 60s) : absorbe les pauses
  GC sans relâcher le lock par accident.
- **Best-effort** : si la table `execution_locks` est absente (env de test
  isolé), l'erreur est loguée en `DEBUG` et le service continue (pas de
  régression de la chaîne historique).
- À la sortie (clean ou exception), le lock est libéré via
  `release_execution_lock(...)`. Le `summary` final expose
  `leader_lock_account` pour observabilité.

Si le lock est déjà détenu, `run()` retourne immédiatement :

```json
{"status": "LEADER_LOCK_HELD", "leader_lock_account": "watcher:paper_main"}
```

### Heartbeat persistant SQL

Inchangé depuis Phase 1.3 : `repo.upsert_watcher_heartbeat(...)` écrit dans
`watcher_heartbeats` à chaque tick `heartbeat_interval_seconds`. Combiné au
lock leader, il permet de détecter une instance "bloquée" (lock détenu mais
heartbeat ancien → alerter, expirer manuellement).

### Allowlist scripts PowerShell

`tests/test_watcher_powershell_allowlist.py` valide statiquement chaque
script de `scripts/windows/` :

- **interdit** : `Invoke-Expression`, `iex`, `Add-Type -TypeDefinition`,
  `DownloadString`, chargement d'assembly via `Reflection.Assembly.Load(`.
- **requis** : `Set-StrictMode` + `$ErrorActionPreference` dans chaque
  script.
- **DPAPI scope** dans `protection_watcher_secrets.ps1` est contraint par
  `ValidateSet('CurrentUser', 'LocalMachine')` ; un avertissement explicite
  apparaît quand `LocalMachine` est utilisé (déchiffrable par tout compte
  ayant accès au fichier → ACL à restreindre).
- **Launcher** : `protection_watcher_launcher.ps1` doit valider l'existence
  du Python fourni et préférer `.venv\Scripts\python.exe` ; aucune
  invocation `cmd.exe /c` (interdit l'injection par interpolation).

### Tests Phase 6.3

```powershell
python -m pytest `
  tests/test_watcher_powershell_allowlist.py `
  tests/test_watcher_leader_election.py `
  tests/test_protection_watcher.py `
  tests/test_watcher_runtime.py `
  tests/test_windows_watcher_bridge.py --no-cov -q
```
