# Calendrier IPO EODHD — US

Batch `eodhd_ipo_calendar_sync`, P2, activé dans `batch.yaml`, visible dans
Workflow & Orchestration → Batch → US. Tous les jours à **1 h Paris** ; secours
conditionnel à **5 h** (succès récent de ce même batch dans les six dernières
heures → SKIP). Le lancement manuel reste autorisé. Notifications mail/Telegram
via `forward_pit_launcher.ps1`, comme les autres collecteurs Forward PIT.

État vérifié le 11 octobre 2026 : tables dédiées créées dans `alpha_trade`, tâche
Windows `AlphaTrade-EodhdIpoCalendarSync` installée. SQL exécuté directement,
révision Alembic non estampillée. Backfill lancé à 15h37 Paris, 130 fenêtres,
2016-01-01 à 2026-10-11. Logs :
`log/batch/eodhd-ipo-backfill-2016-20261011-v1/stderr.log` (progression INFO),
`stdout.log` (résumé terminal). Installation n'est pas une preuve de succès futur.

## Périmètre et données

GET `/api/calendar/ipos?from=...&to=...&fmt=json`, authentification EODHD existante,
quota partagé, HTTPS vérifié. API marché entier, sans filtre symbole côté serveur.
**Depuis le 18 octobre 2026**, normalisation filtrée sur
`config/univers_batch/univers_filtred_tradable.txt`, comme `us_pipeline` :
`symbol_source: universe-file`, `symbols_file` vers ce fichier. Il contient
1 790 titres au changement et est relu à chaque lancement. Aucun filtre
`is_tradable=1` supplémentaire. Le fichier exporté `stock_bars_daily.txt`
n'est pas utilisé. L'API reste marché entier : ce filtre réduit les observations
normalisées, pas le nombre de requêtes calendrier par fenêtre.

Historique : le mode `stock_bars_daily` (environ 13 105 symboles) avait été
configuré le 11 octobre 2026. Le premier backfill, achevé avec
130 fenêtres et 208 observations insérées, utilisait encore ses 1 790 symboles.
Relancer la même commande depuis 2016 relit les fenêtres avec le nouveau hash
d'univers ; les anciennes observations restent conservées sans écrasement.
Relance effective le 11 octobre 2026 à 15h53 Paris : 13 105 symboles, période
2016-01-01 à 2026-10-11, 130 fenêtres. Logs de cette relance :
`log/batch/eodhd-ipo-stock-bars-daily-2016-20261011-v1/stderr.log` et `stdout.log`.
Le lancement ne certifie pas l'achèvement : le statut final figure dans le résumé
du stdout et dans `pit_collection_runs`.
Les nouvelles introductions absentes du fichier tradable restent uniquement
dans la réponse brute archivée : aucune addition automatique à l'univers.
Les anciennes observations hors fichier restent conservées. Les checkpoints
IPO dépendent du hash des symboles : un périmètre changé entraîne leur relecture
lors d'un futur passage/backfill demandé, pas pendant cette modification.
Horaires, secours et notifications restent inchangés. Le launcher relit le
fichier YAML ; aucune réinstallation Windows ni collecte n'a été lancée ici.

`stock_ipo_eodhd_history` conserve symbole, nom, place, devise, dates de première
cotation prévue/effective, dépôt/amendement, statut fournisseur, fourchette,
prix final, nombre d'actions, hash et JSON original. Prix/quantité zéro = inconnu.
Le statut distingue attendu/réalisé ; la date seule ne certifie pas une cotation.
`observed_at/available_at` = réception réelle UTC ; aucune disponibilité ancienne
PIT reconstruite à partir d'une date événementielle historique.

Clé `(symbol,snapshot_date,raw_hash)` : répétition identique dans la même journée
ignorée ; version modifiée ajoutée ; aucun écrasement. Nouvelle journée = nouvelle
observation. Tables Yahoo et consensus EODHD inchangées.

`pit_collection_runs` suit les exécutions ; `pit_raw_payloads` archive les réponses
complètes avant normalisation, même si la réponse est rejetée. Une fenêtre vide
ou sans titre de notre univers est un succès vide, pas une panne.

## Reprise et backfill

Passage quotidien J−7/J+21, réparti en fenêtres mensuelles. Les anciennes fenêtres
quotidiennes sont relues pour capter les modifications, sans suppression.
Backfill depuis **2016-01-01**, fin explicite :

```powershell
python -u -m service.eodhd.ipo_calendar --start-date 2016-01-01 --end-date 2026-10-11
```

Chaque mois est commité séparément avec son checkpoint dans
`eodhd_ipo_collection_windows`, lié au hash de l'univers ; une relance du backfill
ignore uniquement ces fenêtres déjà validées avec ce même univers. Modifier le
périmètre de symboles déclenche leur relecture. Le checkpoint ne certifie pas l'exhaustivité
fournisseur : seulement que la fenêtre a été reçue et persistée sans erreur.
Premier échec technique → arrêt, compteurs préservés ; relance reprend les mois
restants. Compteurs demandés/reçus/échecs = fenêtres ; persistés = observations.

SQL : `database/sql/forward_pit/stock_ipo_eodhd_history.sql` ; Alembic
`0100_eodhd_ipo`, après `0099_eodhd_consensus`, base US exclusivement.

Installation planifiée :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install_forward_pit_task.ps1 -BatchName eodhd_ipo_calendar_sync
```

Exécution immédiate quotidienne avec notifications :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/forward_pit_launcher.ps1 -BatchName eodhd_ipo_calendar_sync -Force
```

Les backfills CLI directs ne déclenchent pas les notifications du launcher ; ils
ont un run et des compteurs SQL et des logs mensuels. Aucun entraînement ni ordre
de trading ajouté. Utilité directionnelle non démontrée ; données de recherche.
