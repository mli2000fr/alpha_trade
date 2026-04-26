# Windows packaging — watcher de protections

Ce dossier contient les scripts d’exploitation Windows pour le watcher post-run de protections.

## Scripts

- `protection_watcher_launcher.ps1` : lanceur commun PowerShell ; c’est lui qui charge éventuellement le `.env` et le secret store DPAPI avant de démarrer Python.
- `protection_watcher_secrets.ps1` : crée / supprime / décrit un secret store Windows chiffré en DPAPI.
- `install_protection_watcher_task.ps1` : installe une tâche planifiée Windows.
- `uninstall_protection_watcher_task.ps1` : supprime la tâche planifiée.
- `install_protection_watcher_service_nssm.ps1` : installe un service Windows via NSSM.
- `uninstall_protection_watcher_service_nssm.ps1` : supprime le service NSSM.
- `protection_watcher.env.example` : exemple de fichier `.env` à copier/adapter.

## Quand utiliser quel script ?

### `protection_watcher_launcher.ps1`

À utiliser :

- pour lancer le watcher manuellement ;
- comme point d’entrée commun appelé par Task Scheduler ou NSSM ;
- quand vous voulez injecter un `.env` ou un store de secrets sans modifier la machine.

### `protection_watcher_secrets.ps1`

À utiliser :

- une seule fois lors du setup pour écrire les secrets DB / broker ;
- quand vous faites une rotation de credentials ;
- quand vous voulez éviter de laisser des secrets en clair dans un `.env`.

### `install_protection_watcher_task.ps1`

À utiliser :

- si vous voulez un déclenchement périodique simple ;
- si le mode recommandé est un scan `once` toutes les X minutes ;
- si vous ne voulez pas de service Windows long-lived.

### `install_protection_watcher_service_nssm.ps1`

À utiliser :

- si vous voulez un vrai process persistant ;
- si vous voulez redémarrage / supervision via NSSM ;
- si le watcher doit rester vivant avec heartbeat continu.

## Secrets : `.env` ou secret store Windows ?

### Option 1 — `.env`

Simple et rapide pour :

- dev local ;
- recette ;
- premiers tests d’exploitation.

Copier :

```powershell
Copy-Item .\scripts\windows\protection_watcher.env.example .\scripts\windows\protection_watcher.env
```

Puis ajuster les valeurs.

### Option 2 — secret store Windows DPAPI

Recommandé pour exploitation Windows.

Écriture interactive :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\protection_watcher_secrets.ps1 -Action Save -DpapiScope CurrentUser
```

Écriture depuis les variables d’environnement déjà présentes dans la session :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\protection_watcher_secrets.ps1 -Action Save -DpapiScope CurrentUser -FromEnvironment
```

Afficher les métadonnées du store :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\protection_watcher_secrets.ps1 -Action ShowMetadata
```

Supprimer le store :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\protection_watcher_secrets.ps1 -Action Remove
```

Le launcher charge d’abord le `.env`, puis le secret store ; le store peut donc surcharger les secrets du fichier.

## Exemples

### Task Scheduler

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_task.ps1 -TaskName "AlphaTrade-ProtectionWatcher" -FrequencyMinutes 5 -Account default
```

Avec `.env` explicite :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_task.ps1 -TaskName "AlphaTrade-ProtectionWatcher" -FrequencyMinutes 5 -Account default -EnvFilePath "C:\Users\me\alpha_trade\scripts\windows\protection_watcher.env"
```

Avec secret store explicite :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_task.ps1 -TaskName "AlphaTrade-ProtectionWatcher" -FrequencyMinutes 5 -Account default -SecretStorePath "$env:APPDATA\AlphaTrade\protection_watcher.secrets.json"
```

### NSSM

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_service_nssm.ps1 -NssmExePath "C:\tools\nssm\win64\nssm.exe" -ServiceName "AlphaTradeProtectionWatcher" -Account default -StartAfterInstall
```

Pour un service lancé en compte machine, préférer un store `LocalMachine` + ACL restreintes :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\protection_watcher_secrets.ps1 -Action Save -DpapiScope LocalMachine -StorePath "$env:ProgramData\AlphaTrade\protection_watcher.secrets.json"
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_service_nssm.ps1 -NssmExePath "C:\tools\nssm\win64\nssm.exe" -ServiceName "AlphaTradeProtectionWatcher" -Account default -SecretStorePath "$env:ProgramData\AlphaTrade\protection_watcher.secrets.json" -StartAfterInstall
```

## Pré-requis

- variables DB / broker disponibles soit via l’environnement, soit via `.env`, soit via le secret store DPAPI ;
- Python accessible ou `-PythonExePath` renseigné ;
- pour NSSM : binaire `nssm.exe` déjà installé côté machine.

