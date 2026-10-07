# Sprint 15-D10 — Journal quotidien de l'appariement D7

Le batch `cn_dragon_tiger_daily_match` de [batch.yaml](../../batch.yaml) automatise **uniquement l'appariement de recherche sans issues futures** défini par [D7](./sprint_15d7_protocole_appariement_dragon_tiger.md). Il n'entraîne rien, ne lit pas les labels D1/D10, ne modifie ni la base CN, ni le serving, ni le trading.

## Séquence et temporalité

1. [D9](./sprint_15d9_journal_oracle_prospectif_quotidien.md) publie, après la clôture de J, l'export Oracle TOP20 pour la prochaine séance ouverte K, avec empreinte et disponibilité avant 09:15 Shanghai.
2. [D6](./sprint_15d6_collecte_prospective_dragon_tiger.md) observe la liste officielle après J et de nouveau avant l'ouverture de K. Le dernier snapshot complet réellement observé avant 09:15 K fait foi, y compris lorsqu'il retire un titre.
3. D10 est prévu à **09:30 Asia/Shanghai** sur K. Il exige une séance ouverte, un export Oracle D8 vérifiable et un snapshot officiel recevable par le moteur D7. Il n'invente jamais une absence d'événement lorsque le snapshot manque. Un échec est signalé ; il ne devient pas une ligne de contrôle négative.
4. Le moteur D7 applique les calipers pré-enregistrés de score Oracle et rendement antérieur, par même séance et board. Il écrit `outcome_blind_matches.parquet` et `report.json` dans un dossier daté `artifacts/research/cn_dragon_tiger_15d10/K/` non écrasable. Les passages sont également consignés dans `.../runs/` pour la page **Workflow & Orchestration → Batch** et les notifications mail/Telegram.

Le batch saute les jours fermés et les instants antérieurs à 09:20 sans faux succès. Une exécution manuelle ne contourne **pas** le calendrier ni le cutoff. L'export Oracle D8 et le rapport D7 déjà produits ne sont pas remplacés ; une empreinte incohérente bloque la relance. Un passage manqué ne reconstruit pas rétroactivement les observations : seules des captures dont l'horodatage prouve la disponibilité avant 09:15 sont admises.

Le premier appariement possible est **le 8 octobre 2026 à 09:30 Shanghai**, si le passage D6 avant ouverture a réussi. Le score Oracle du 8 octobre, publié le 30 septembre, comporte 1 034 candidats ; cela n'implique pas que des paires valides existent. Le résultat quotidien aura normalement le statut `INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE`. Les gates D7 restent **60 séances**, **200 exposés**, **deux trimestres**, plus équilibre des paires. Aucun résultat directionnel ne doit être annoncé avant maturité des H20 et audit séparé des issues.

## Exploitation

La tâche `AlphaTrade-CnDragonTigerDailyMatch` utilise un déclencheur Windows horaire à la minute 30 ; le lanceur ne traite que l'heure configurée dans `batch.yaml` (09:30 Shanghai). Elle utilise le même journal et la même notification que les autres batchs CN. En mode `Interactive`, elle ne fonctionne pas si la session Windows est fermée.

Contrôle sans collecte, sans appariement ni écriture :

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_dragon_tiger_daily_15d10 --batch cn_dragon_tiger_daily_match --batch-config batch.yaml --dry-run
```

Exécution manuelle après le cutoff :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/cn_dragon_tiger_daily_launcher_15d10.ps1 -BatchName cn_dragon_tiger_daily_match -Force
```

Installation ou réinstallation depuis la page Batch, ou :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install_forward_pit_task.ps1 -BatchName cn_dragon_tiger_daily_match -TaskName AlphaTrade-CnDragonTigerDailyMatch -RunAs Interactive -LauncherPath scripts/windows/cn_dragon_tiger_daily_launcher_15d10.ps1
```

Le calendrier vérifié couvre seulement 2026. Avant le premier traitement de 2027, il faut qualifier le calendrier suivant et vérifier l'accès aux données officielles. Les sorties D10 restent des paires quotidiennes ; un agrégat prospectif interséances et l'audit des issues H20 sont des étapes distinctes, à exécuter seulement après les gates pré-enregistrés.
