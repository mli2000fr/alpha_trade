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

#### Métriques d'armement TP/SL (filet S26)

Le watcher expose dans son `run_summary` deux compteurs supplémentaires
(visibles dans la section *Historique des runs*) :

| Métrique | Signification | Lecture |
|---|---|---|
| `armed_missing_protections` | Nb de positions `FILLED` pour lesquelles le watcher vient d'armer TP/SL manquants. | > 0 attendu en exploitation overnight (entrée la veille → fill à l'ouverture). > 0 récurrent en intraday = anomalie. |
| `armed_missing_protections_failed` | Nb d'échecs lors de l'armement post-fill. | **Doit rester 0**. Sinon : ouvrir runbook §positions sans protection. |

L'executor expose les mêmes notions sous les noms
`children_armed_post_sync` / `children_armed_post_sync_failed` (visibles
dans la page **Execution** → section *Métriques du run*).


### Lancer / arrêter le watcher

> ⚠️ **GAP CONNU** : pas encore de bouton dans l'IHM. En attendant :
>
> ```powershell
> # Démarrer
> python execution_engine/protection_watcher.py
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

- Doc technique : [doc/watcher.md](../backup/watcher.md).
- Runbook 24/7 : [doc/runbook_24_7.md](../backup/runbook_24_7.md).

