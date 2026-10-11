# Sprint 17-D — Préparation de la bascule des catalogues CN (sans activation)

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

État au 1er octobre 2026 : **préparation seulement**. Les quatre tâches prospectives D6/D9/D10 restent installées et lisent `batch.yaml`. Aucun déplacement de section, réinstallation, changement d'horaire, de base ou de serving n'est autorisé avant au moins un cycle réel D6 → D9 → D10 → qualité 17-C cohérent. La clôture opérationnelle complète de 17-C exige toujours sept séances ouvertes consécutives ; un premier cycle ne la remplace pas.

## Pourquoi un simple déplacement YAML casserait le flux

Les lanceurs CN D6, D9 et D10 prennent `batch.yaml` par défaut lorsque la tâche Windows ne transmet pas `-BatchConfigPath`. Les quatre tâches actuellement installées sont `Ready` et leurs actions invoquent leurs lanceurs sans ce paramètre. Les modules Python possèdent également `batch.yaml` comme valeur par défaut. L'IHM fusionne aujourd'hui les quatre batchs de recherche depuis `batch.yaml` avec les seuls `cn_db_backup` et `cn_daily_quality_17c` depuis `batch_cn.yaml`. Déplacer les sections sans adapter **ensemble** les lanceurs, les appels Python, les commandes IHM et les tâches produirait des `Missing batch.yaml section`, ou rendrait les batchs invisibles dans l'IHM.

**Compatibilité préparée le 01/10 :** le catalogue IHM sait désormais fusionner les quatre sections de recherche depuis `batch_cn.yaml` si et seulement si elles ne sont plus présentes dans `batch.yaml`. Ses commandes transmettent alors `-BatchConfigPath` ; le wrapper Windows accepte un sixième argument facultatif, sans modifier les actions installées à cinq arguments. Le contrôle 17-C accepte D9 dans un seul des deux catalogues et refuse un doublon. L'audit 17-A connaît également les deux états. Ces changements ne déplacent aucune section et ne prouvent pas encore la parité d'un cycle réel après bascule.

Le [contrat de route 17-D](../../service/market/cn_catalog_contract_17d.py) est maintenant appelé par les trois runners D6/D9/D10. Sous `batch_cn.yaml`, il exige `CN_A`, `cn_primary`, le fuseau CN par défaut et l'absence de la même section dans `batch.yaml` ; les nouveaux rapports de run portent alors `market_code`, `database_alias` et `catalog_path`. Sous le catalogue legacy actuellement installé, il renvoie un contexte vide et ne change pas les rapports métier. Les [tests de parité simulée](../../tests/test_cn_catalog_contract_17d.py) exercent les trois runners sans collecte ni accès base. **Aucune définition de tâche Windows n'a été réinstallée.**

L'installeur `install_forward_pit_task.ps1` retire une tâche existante avant de la recréer. Cette opération n'est pas atomique au niveau Windows ; il faut un créneau contrôlé hors des fenêtres de 08:30, 09:30, 17:30 et 18:15 Shanghai et un rollback explicite. Ne pas utiliser « installer tous » comme mécanisme de migration.

## Inventaire figé avant bascule

| Batch / tâche Windows | Heure CN | État actuel | Lecteur du catalogue | Sortie / identité à conserver |
|---|---:|---|---|---|
| `cn_dragon_tiger_before_open` / `AlphaTrade-CnDragonTigerBeforeOpen` | 08:30 | `batch.yaml`, `RESEARCH_ONLY` | lanceur D6 + `cn_dragon_tiger_schedule_15d6.py` | observations officielles, phase et cutoff PIT |
| `cn_dragon_tiger_daily_match` / `AlphaTrade-CnDragonTigerDailyMatch` | 09:30 | `batch.yaml`, `RESEARCH_ONLY` | lanceur D10 + `cn_dragon_tiger_daily_15d10.py` | appariement outcome-blind, empreintes Oracle |
| `cn_dragon_tiger_after_close` / `AlphaTrade-CnDragonTigerAfterClose` | 17:30 | `batch.yaml`, `RESEARCH_ONLY` | lanceur D6 + `cn_dragon_tiger_schedule_15d6.py` | observations officielles de la séance J |
| `cn_oracle_prospective_daily` / `AlphaTrade-CnOracleProspectiveDaily` | 18:15 | `batch.yaml`, `RESEARCH_ONLY` | lanceur D9 + `cn_oracle_daily_15d9.py` | collecte canonique unique, export Oracle de K |

`cn_db_backup` et `cn_daily_quality_17c` sont déjà dans `batch_cn.yaml` et ne doivent pas être déplacés. `cn_daily_market_data_sync` reste désactivé : il ne devient pas un second propriétaire du canonique. Les chemins relatifs d'artefacts devront continuer à être résolus depuis la racine du projet, et non depuis un sous-répertoire ou le dossier courant de Windows.

## Gates avant autorisation de migration

1. Contrôler une séance ouverte **postérieure au 1er octobre** : rapport D9 `COMPLETED_RESEARCH_ONLY`, lots complets, Oracle K publié avant son cutoff ; D6 avant/après et D10 de J cohérents ; rapport qualité 17-C de J sans gate critique. Pour la première possibilité, J = 8 octobre 2026. Un rattrapage manuel de septembre ne vaut pas cette preuve.
2. Vérifier les actions et états réels des quatre tâches Windows, puis capturer leur définition avant toute modification. Vérifier qu'aucun de ces traitements n'est `Running` et que la prochaine fenêtre n'est pas imminente.
3. Préparer la configuration cible avec exactement une section active par nom. Les quatre sections CN sortiront de `batch.yaml` et entreront dans `batch_cn.yaml` **sans changement de valeurs métier, horaires, statut `RESEARCH_ONLY`, chemins d'artefacts ou périmètre de collecte**. Ajouter `market_code: CN_A` et `database_alias: cn_primary` explicites ; refuser toute route vers `alpha_trade`.
4. Faire passer les tests de parité sur les lecteurs Python et les commandes IHM ; vérifier `--probe` pour chaque tâche et les calendriers ouverts/fermés, sans exécution de collecte forcée. Les rapports nouveaux doivent indiquer le marché, la base et le catalogue effectivement utilisé ; les preuves antérieures restent immuables.
5. Préparer un point de retour vérifié : conserver les quatre sections et les définitions de tâches pré-bascule, ainsi que le dernier rapport complet. Une erreur pendant la bascule doit restaurer les **mêmes** noms et horaires avant la prochaine fenêtre, pas installer un deuxième jeu de tâches.

## Séquence de bascule à implémenter après le gate

1. Rejouer la compatibilité préparée des quatre modules et lanceurs avec un chemin `batch_cn.yaml` explicite. Les commandes installées et IHM transmettront ce chemin ; les sections déplacées porteront `market_code: CN_A` et `database_alias: cn_primary`. Le contrôle 17-C, les runners et le préflight refuseront deux sections actives du même nom. Les modules D6/D9/D10 gardent aujourd'hui leur valeur par défaut legacy ; leurs probes CN simulées passent, mais la parité d'un cycle réel post-bascule restera à constater.
2. Faire charger l'IHM depuis les deux catalogues sans doublon : US depuis `batch.yaml`, CN depuis `batch_cn.yaml`. Conserver les quatre boutons, états, descriptions, historiques et notifications. Mettre à jour l'affichage « catalogue central » qui suppose aujourd'hui uniquement `batch.yaml`.
3. Après tests, déplacer les quatre sections en conservant strictement leurs valeurs. Comparer automatiquement les champs sémantiques avant/après : `enabled`, `status`, `timezone`, `run_hours`, `run_minutes`, `calendar`, univers, provider, roots, cutoff, notices et logs.
4. Réinstaller **une tâche à la fois**, sous le **même nom Windows**, hors fenêtre de marché. Après chacune, relire l'action et le prochain déclenchement ; vérifier que la seule différence attendue est le chemin explicite de configuration. Ne jamais laisser simultanément l'ancienne et une nouvelle tâche de même traitement.
5. Rejouer les `--probe` sur jour fermé et jour ouvert simulé. Au cycle prospectif suivant, vérifier les quatre rapports et 17-C ; comparer compteurs, empreintes, identités de marché/base et horaires aux contrats figés. Un `SKIP` de calendrier n'est pas une preuve de parité de collecte.
6. Si un lecteur manque une section, qu'une tâche disparaît, que le modèle de données dérive ou que la preuve PIT n'est plus produite, remettre les sections et tâches d'origine avant la prochaine échéance. Conserver les rapports d'échec ; ne pas rétro-dater la décision Oracle manquée.

## Commandes de lecture avant décision

```powershell
# Préflight 17-D, lecture seule : exige un vrai rapport 17-C complet avec D6/D9/D10.
.\.venv\Scripts\python.exe -m service.market.cn_catalog_preflight_17d --output artifacts/research/cn_operations_17a/cutover-preflight-NOUVELLE_DATE.json

# Audit de configuration, sans base ni modification de tâche : choisir un nom de rapport neuf.
.\.venv\Scripts\python.exe -m service.market.cn_operations_audit_17a --output artifacts/research/cn_operations_17a/audit-NOUVELLE_DATE.json

# État des quatre tâches actuellement installées.
Get-ScheduledTask -TaskName AlphaTrade-CnDragonTigerBeforeOpen,AlphaTrade-CnDragonTigerDailyMatch,AlphaTrade-CnDragonTigerAfterClose,AlphaTrade-CnOracleProspectiveDaily | Select-Object TaskName,State,Actions

# Preuves du dernier cycle : lire les rapports, ne pas relancer Oracle a posteriori.
Get-ChildItem artifacts/research/cn_oracle_daily_15d9/runs -Filter 'run-*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,LastWriteTime
Get-ChildItem artifacts/research/cn_daily_quality_17c/runs -Filter 'run-*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,LastWriteTime
```

Le [préflight daté du 01/10](../../artifacts/research/cn_operations_17a/cutover-preflight-20261001.json) retourne `BLOCKED` uniquement parce qu'aucun cycle D6/D9/D10 + 17-C réel postérieur au 08/10 n'existe encore. Son `scheduler_actions_verified: false` est volontaire : le préflight ne prétend pas avoir validé les actions Windows ; elles doivent être contrôlées humainement avant la bascule. Les [tests](../../tests/test_cn_catalog_preflight_17d.py) vérifient qu'un rapport minimal, un échec ou un doublon de section ne peut pas autoriser la migration.

**Décision actuelle : HOLD.** Le seul avertissement de l'[audit 17-A actualisé](../../artifacts/research/cn_operations_17a/audit-20261001-after-17c.json) est le catalogue mixte ; il est connu et moins risqué que de déplacer les tâches pendant la fermeture du marché. Reprendre ce document après le premier cycle réel, puis exécuter la migration contrôlée avant de déclarer 17-D terminé.

## Préparation vérifiée le 01/10 — sans bascule

Le [plan de catalogue en lecture seule](../../service/market/cn_catalog_plan_17d.py) et son [rapport figé](../../artifacts/research/cn_operations_17a/catalog-plan-20261001.json) contrôlent les quatre sections actuellement dans `batch.yaml`. Les 15, 19, 15 et 22 champs respectifs restent identiques dans la cible simulée ; seules les identités explicites `market_code: CN_A` et `database_alias: cn_primary` seraient ajoutées. Le plan enregistre les empreintes SHA-256 des deux catalogues avant intervention et refuse une section dupliquée. Il ne génère aucun YAML cible sur disque et ne modifie ni base ni tâche.

Inspection réelle des quatre tâches Windows : elles sont toutes `Ready`, utilisent `wscript.exe` avec le lanceur D6, D9 ou D10 attendu, ont chacune un déclencheur et un principal `Interactive`. La dernière exécution signalait le code `0` au moment de l'inspection. **Aucune action ne contient encore `batch_cn.yaml` ni `-BatchConfigPath`** ; le code `0` du planificateur ne prouve pas à lui seul qu'un cycle métier D6/D9/D10 est complet. Le prochain déclenchement visible était le 01/10 à 11:30 heure du PC pour trois tâches et 12:15 pour D9. Les contrôles d'horaires métier restent dans les lanceurs.

Pour rafraîchir le plan après le premier cycle réel, utiliser un *nouveau* nom de sortie :

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_catalog_plan_17d --output artifacts/research/cn_operations_17a/catalog-plan-APRES-CYCLE.json
.\.venv\Scripts\python.exe -m pytest -q --no-cov tests/test_cn_catalog_plan_17d.py tests/test_cn_catalog_preflight_17d.py tests/test_cn_catalog_contract_17d.py
```

Après ce rapport, il faudra encore vérifier les quatre actions Windows, exporter leurs définitions et sauvegarder les deux YAML **avant** toute modification. Ces preuves devront porter les empreintes des catalogues relevées par le plan. Une divergence d'empreinte impose de régénérer le plan, pas d'appliquer un déplacement préparé sur un autre état. La migration elle-même reste interdite tant que le gate du premier cycle réel et la vérification manuelle des tâches ne sont pas satisfaits. Les tests ciblés de préparation passent (12 tests au 01/10) ; ils ne remplacent pas la preuve prospective.

### Point de retour préparé le 01/10

Le [script d'export 17-D](../../scripts/windows/export_cn_catalog_cutover_snapshot_17d.ps1) a produit un [manifest de retour arrière validé](../../artifacts/research/cn_operations_17a/cutover_snapshots/20261001T110256Z/manifest.json) contenant les deux YAML et les quatre définitions XML des tâches installées. Le [validateur de snapshot](../../service/market/cn_catalog_snapshot_validate_17d.py) vérifie les six empreintes SHA-256, le vrai décodage des XML, les lanceurs et identités de tâche, l'unicité des sections et l'absence de dérive des catalogues courants ; résultat `VALID_LEGACY_SNAPSHOT`. Les quatre tâches étaient hors exécution lors de la capture. Un premier export du 01/10 utilisait un encodage XML incompatible avec sa déclaration : le validateur l'a rejeté et cet export invalide généré pendant la préparation a été supprimé. Seul le snapshot validé doit servir de référence.

L'export est une **photo de préparation**, pas encore la sauvegarde finale de bascule : régénérer un nouveau snapshot juste avant toute migration, puis comparer ses empreintes au plan 17-D actualisé. Ne pas restaurer aveuglément la photo du 01/10 si les catalogues ou tâches ont changé entre-temps.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/export_cn_catalog_cutover_snapshot_17d.ps1
python -m service.market.cn_catalog_snapshot_validate_17d --snapshot artifacts/research/cn_operations_17a/cutover_snapshots/NOUVELLE_CAPTURE
```

Le script lit/exporte seulement ; il ne désinstalle ni ne réinstalle aucune tâche. Un rollback effectif reste une opération contrôlée à réaliser seulement si la bascule échoue, après vérification des noms, horaires et empreintes de la sauvegarde immédiatement préalable.
