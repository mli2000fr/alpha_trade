# 12. Page 🛟 Supervision Ops

## À quoi sert cette page

Surveiller les **processus en arrière-plan** : pipeline qui tournent encore,
watcher de protection, runs récents et leurs logs.

## Sections principales

### Runs actifs

Liste des processus pipeline / execution actuellement en cours. Pour chaque :
- `run_id`, `step`, `started_at`, `pid` (Process ID Windows)
- bouton **« Voir logs »**

### Watcher de protection (24/7)

Le watcher est un programme qui tourne en continu et vérifie que vos
ordres protecteurs (stop-loss, take-profit) sont bien en place chez le
broker.

Indicateurs :
- 💚 **Heartbeat OK** : dernière vérification < 2 min
- 🟡 **Heartbeat lent** : 2-10 min
- 🔴 **Watcher mort** : > 10 min

> ⚠️ Si le watcher est mort, vos positions ne sont **plus protégées**.
> Relancez-le manuellement (cf. ci-dessous).

### Lancer / arrêter le watcher

> ⚠️ **GAP CONNU** : pas encore de bouton dans l'IHM. En attendant :
>
> ```powershell
> # Démarrer
> python run_execution_protection_watch.py
>
> # Arrêter
> # Ctrl+C dans la fenêtre PowerShell où il tourne
> ```

### Historique des runs

Tableau de tous les runs des 30 derniers jours, filtres par module / statut.

## Pour un débutant

- Vérifiez **chaque matin** que le watcher est 💚.
- Si un step pipeline a échoué la veille, vous le voyez ici.

## Pour aller plus loin

- Doc technique : [doc/watcher.md](../watcher.md).
- Runbook 24/7 : [doc/runbook_24_7.md](../runbook_24_7.md).

