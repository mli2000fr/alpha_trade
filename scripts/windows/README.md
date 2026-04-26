# Windows packaging — watcher de protections

Ce dossier contient les scripts d’exploitation Windows pour le watcher post-run de protections.

## Scripts

- `protection_watcher_launcher.ps1` : lanceur commun PowerShell
- `install_protection_watcher_task.ps1` : installe une tâche planifiée Windows
- `uninstall_protection_watcher_task.ps1` : supprime la tâche planifiée
- `install_protection_watcher_service_nssm.ps1` : installe un service Windows via NSSM
- `uninstall_protection_watcher_service_nssm.ps1` : supprime le service NSSM

## Exemples

### Task Scheduler

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_task.ps1 -TaskName "AlphaTrade-ProtectionWatcher" -FrequencyMinutes 5 -Account default
```

### NSSM

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_protection_watcher_service_nssm.ps1 -NssmExePath "C:\tools\nssm\win64\nssm.exe" -ServiceName "AlphaTradeProtectionWatcher" -Account default -StartAfterInstall
```

## Pré-requis

- variables d’environnement DB / broker disponibles pour le contexte d’exécution choisi ;
- Python accessible ou `-PythonExePath` renseigné ;
- pour NSSM : binaire `nssm.exe` déjà installé côté machine.

