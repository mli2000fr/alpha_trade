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

L'étape `12 Execution` soumet déjà les ordres d'entrée puis leurs enfants broker-side :

- un **take-profit** ;
- un **stop initial broker-side** dans le cas nominal ;
- et, en cas d'échec sur ce stop initial, un **trailing fallback** peut être soumis directement par `Execution`.

Autrement dit : la première couche de protection ne dépend pas du watcher, elle dépend du moteur `Execution` et des ordres enfants envoyés au broker.

#### Ce que fait ensuite le watcher

Le watcher prend le relais **après** `Execution` pour :

- relire les protections encore ouvertes ;
- vérifier si le trigger métier de transition est atteint ;
- annuler le stop initial ;
- promouvoir ce stop vers un **trailing stop dynamique** ;
- journaliser et superviser cet état dans l'IHM / Windows.

Le watcher ne sert donc pas à "faire partir" l'ordre d'entrée. Il sert à **gérer intelligemment la vie de la protection après exécution**.

### 2.3 Si je ne lance pas le watcher, les ordres seront-ils exécutés ?

**Oui.**

Les ordres d'entrée et leurs protections initiales sont soumis par `Execution`, pas par le watcher.

Donc, si `Execution` réussit :

- l'ordre principal peut être exécuté ;
- le take-profit peut être armé ;
- le stop initial broker-side peut être armé ;
- un trailing fallback peut parfois exister dès `Execution` si le stop initial n'a pas pu être soumis.

Le watcher n'est donc **pas requis pour que les ordres d'entrée soient exécutés**.

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
| Stop initial exécuté | **Oui** | S'il a bien été posé broker-side par `Execution`. |
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

