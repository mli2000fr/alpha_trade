# Sprint 15-D9 — journal quotidien Oracle CN prospectif

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Périmètre

Le batch `cn_oracle_prospective_daily` de [batch.yaml](../../batch.yaml) constitue une chaîne **de recherche uniquement** : séance CN close J → collecte BaoStock canonique J → préflight → score Oracle H20 TOP20 pour la prochaine séance ouverte K → export D8 immuable. Il ne lance aucun ordre, ne change pas le serving et n'apparie pas encore les événements Dragon/Tiger D7. Le premier score manuel du 8 octobre reste dans son dossier initial et est reconnu comme déjà publié, jamais remplacé.

Le batch est visible dans **Workflow & Orchestration → Batch**, avec installation, lancement manuel, statut du dernier rapport, compteurs et journal. Son exécution utilise le lanceur commun qui envoie les notifications mail/Telegram, y compris en cas d'échec ; la disponibilité effective de ces canaux dépend de leurs identifiants et de la configuration TLS du poste.

## Horaire et fail-closed

- Tâche Windows `AlphaTrade-CnOracleProspectiveDaily`, installée en mode **Interactive**. L'action est cachée ; si la session Windows est fermée, la tâche ne traite pas la séance. Le déclencheur technique est horaire à la minute 15 ; [le lanceur](../../scripts/windows/cn_oracle_daily_launcher_15d9.ps1) consulte `batch.yaml` et ne lance le traitement qu'à **18:15 Asia/Shanghai**. Les jours fermés sont ignorés sans notification de faux succès.
- Même en lancement manuel `-Force`, le code refuse une séance non ouverte ou antérieure à **18:00 Shanghai**. La décision K est calculée avec le calendrier CN vérifié : les congés du 1er au 7 octobre conduisent du 30 septembre au 8 octobre. Les dates 2027 échouent fermées tant que le calendrier annuel n'est pas vérifié.
- Un score manqué **n'est jamais rétrodaté**. Le modèle D8 refuse d'écrire après 09:15 Shanghai de K. Une fois l'export publié, une seconde exécution vérifie son SHA-256, ses horodatages et son statut, puis s'arrête sans collecte ni réécriture.
- Un verrou local par séance empêche deux exécutions du journal de se chevaucher. Le collecteur sous-jacent conserve aussi son verrou `run-all.lock` et son état par lot.

## Contrôles et reprise

1. Préparer un manifeste du jour et des lots de 25 actions à partir du master BaoStock et du [seed](../../config/univers_cn/canonical_incremental_2026-09-30.txt). Des chemins propres à J sont utilisés. Si le manifeste et les lots existent déjà, le batch vérifie leur concordance exacte avant la reprise ; un état partiellement préparé est arrêté pour audit manuel, non reconstruit silencieusement.
2. Reprendre uniquement les lots non terminés via [cn_sprint7c_incremental.py](../../dataIntegrityEngine/cn_sprint7c_incremental.py), en mode insert-only borné à J. Les échecs réseau BaoStock sont retentés ; une collecte incomplète interdit le score. Les lignes historiques 2018–2025 ne sont pas réécrites.
3. Exécuter le préflight D8 sur K : séance J close, barres actions connues, CSI 300, seuils de couverture, artefact Oracle gelé et cutoff. `READY_TO_SCORE` est obligatoire.
4. Publier un seul [export D8](./sprint_15d8_export_oracle_prospectif.md) atomique et vérifier indépendamment le hash du fichier et les timestamps du rapport. Les métriques de notification distinguent **actions demandées**, **barres J reçues** et **candidats TOP20 exportés** ; « persistés » désigne ici le fichier de recherche, pas des ordres ni un serving ML.
5. Écrire un rapport de passage immutable sous `artifacts/research/cn_oracle_daily_15d9/runs/`. Un échec conserve les lots déjà réussis, écrit son erreur dans ce journal et rend un code de sortie non nul pour la notification.

Le dossier d'état des lots est `artifacts/cn/sprint7c_daily/AAAA-MM-JJ/state.json`, le journal humain `log/batch/cn_oracle_prospective_daily.txt`, et l'export prévisionnel `artifacts/research/cn_oracle_prospective_15d8/K/`. Aucune sauvegarde automatique n'est inférée de cette seule installation.

## Opérations

Depuis `F:\projets`, contrôle sans base ni réseau :

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_oracle_daily_15d9 --batch cn_oracle_prospective_daily --dry-run
```

Lancement manuel via le même circuit de journal et notifications que l'IHM (ne contourne pas la clôture ni le cutoff) :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/cn_oracle_daily_launcher_15d9.ps1 -BatchName cn_oracle_prospective_daily -Force
```

Réinstallation si la configuration horaire change :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install_forward_pit_task.ps1 -BatchName cn_oracle_prospective_daily -TaskName AlphaTrade-CnOracleProspectiveDaily -RunAs Interactive -LauncherPath scripts/windows/cn_oracle_daily_launcher_15d9.ps1
```

La collecte officielle Dragon/Tiger D6 reste une tâche **distincte** à 17:30 et 08:30 Shanghai. Après 09:15 en K, l'appariement D7 doit utiliser le dernier snapshot complet réellement observé avant le cutoff. D9 n'effectue pas cet appariement et ne mesure pas D1/D10 ; les gates de 60 séances, 200 exposés, deux trimestres et H20 mature restent inchangés.

## Vérification de mise en service

Le 30 septembre, le module, l'IHM et les composants réutilisés ont passé **61 tests ciblés**. Le contrôle réel exécuté pendant le congé du 1er octobre en heure de Shanghai a répondu `SKIP_CLOSED`, sans accès base ni collecte. La tâche Windows est installée et `Ready` ; **aucun cycle quotidien D9 n'a encore tourné sur une nouvelle séance**. La première exécution utile attend le 8 octobre après clôture pour la décision du 9 octobre. Ce fait ne certifie ni la stabilité du fournisseur ni la qualité économique du modèle.
