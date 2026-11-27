# Supervision horaire des watchers US

Le batch `us_watcher_services`, visible dans les batchs US, est activé dans
`batch.yaml`. Il concerne les comptes PAPER `default`, `test1`, `test2`.

La tâche Windows `AlphaTrade-UsWatcherServices` vérifie chaque heure à :30.
Le lanceur n'admet que 09:30, 10:30, 11:30, 12:30, 13:30, 14:30 et 15:30,
heure de New York, du lundi au vendredi. Le traitement vérifie ensuite le
calendrier NYSE strict : aucun lancement de service un jour férié, avant
l'ouverture ou après la clôture, y compris les clôtures anticipées. Ce contrôle
reste actif en lancement manuel. Les décalages saisonniers sont gérés par le
fuseau `America/New_York`, sans heure de Paris figée.

Le processus local est recherché avant son heartbeat : un service encore en
démarrage ne provoque pas de doublon. Un service présent est conservé. Si son
heartbeat, son identité ou sa version ne sont pas qualifiés, le compte est
signalé en erreur sans arrêt ni remplacement automatique. Les autres comptes
sont vérifiés. Un service absent est démarré séquentiellement par le même
lanceur persistant que le pipeline, puis son heartbeat est attendu (120 s).
L'élection du leader par compte reste active en cas de démarrage concurrent.

Le service lancé est celui de 12.bis, compte entier en PAPER, avec les défauts
du bouton de la page Pipeline. Les paramètres Winner figés dans les plans
existants restent appliqués par ce watcher. Ce batch ne lance pas 10/11/12 et
ne crée pas un nouveau portefeuille. Le watcher peut ensuite gérer les ordres
et protections selon le fonctionnement habituel de 12.bis.

Les services survivent à la fin du batch. Ils ne sont pas arrêtés à la clôture.
Désactiver le batch empêche les futurs démarrages, sans arrêter les services.

## Exploitation

Installation ou mise à jour de la tâche Windows, depuis `F:\projets` :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install_forward_pit_task.ps1 -BatchName us_watcher_services
```

Lancement manuel (même contrôle de marché ouvert) :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/forward_pit_launcher.ps1 -BatchName us_watcher_services -Force
```

Diagnostic sans démarrage ni écriture SQL :

```powershell
.venv\Scripts\python.exe -X utf8 -m service.forward_pit.batch --batch us_watcher_services --dry-run
```

Suivi : `log/batch/us_watcher_services.txt`, table `pit_collection_runs` et,
pendant une séance, `artifacts/operations/us_watcher_services/<run_id>/` avec
`progress.json`, `report.json` et les journaux des services nouvellement lancés.
Les compteurs indiquent les comptes demandés, disponibles, démarrés et en
erreur (pas des titres ou des lignes de marché).

Le PC doit être allumé et la session Windows utilisateur ouverte, comme pour
les autres tâches installées avec le mode Interactive.
