# TODO de reprise — Oracle CN × Dragon/Tiger, sprints 15-D7 à 15-D11

**État figé au 30 septembre 2026.** Ce document sert de point de reprise lorsque les observations prospectives seront disponibles. Il ne constitue pas une validation de la direction D1/D10 ni une autorisation de déploiement. Les contrats complets sont dans [D6](./sprint_15d6_collecte_prospective_dragon_tiger.md), [D7](./sprint_15d7_protocole_appariement_dragon_tiger.md), [D8](./sprint_15d8_export_oracle_prospectif.md), [D9](./sprint_15d9_journal_oracle_prospectif_quotidien.md), [D10](./sprint_15d10_appariement_d7_quotidien.md) et [D11](./sprint_15d11_cumul_d7_outcome_blind.md). Le fichier [batch.yaml](../../batch.yaml) reste la source des horaires.

> Mise à jour opérationnelle du 1er octobre 2026 : le code de compatibilité [Sprint 17-D](./sprint_17d_preparation_bascule_catalogues.md) est prêt, mais **les quatre tâches CN n'ont pas été migrées**. Elles lisent toujours `batch.yaml`. Le préflight 17-D reste `BLOCKED` tant qu'un premier cycle prospectif complet postérieur au 8 octobre n'a pas été observé. Les sept séances exigées pour clôturer [17-C](./sprint_17c_qualite_quotidienne_proprietaire_collecte.md) sont un gate distinct.

## Ce qui est déjà fait — ne pas recommencer

- [x] Protocole D7 et seuils pré-enregistrés : Oracle H20 TOP20, événement officiel connu avant 09:15 Shanghai, même séance et même board, calipers de rang et rendement préalable, distinction `D1_veto` / `D10_long`.
- [x] Collecte D6 après clôture et avant ouverture, avec observations horodatées ; quatre tâches Windows CN sont actuellement `Ready` en mode `Interactive` : `AlphaTrade-CnDragonTigerAfterClose`, `AlphaTrade-CnDragonTigerBeforeOpen`, `AlphaTrade-CnDragonTigerDailyMatch`, `AlphaTrade-CnOracleProspectiveDaily`.
- [x] Premier export D8 de recherche pour la **décision du 8 octobre 2026** : [rapport](../../artifacts/research/cn_oracle_prospective_15d8/2026-10-08/report.json), 5 166 actions éligibles et 1 034 candidates TOP20. Le score a été publié le 30 septembre avant le cutoff du 8 octobre. Il doit rester immuable.
- [x] D9 : collecte quotidienne de la séance close et préparation de l'Oracle pour la séance suivante à **18:15 Shanghai** ; D10 : appariement D7 outcome-blind à **09:30 Shanghai** ; D11 : audit cumulatif et liste des séances manquantes. Aucun de ces composants ne sert le trading.
- [x] [Premier rapport D11](../../artifacts/research/cn_dragon_tiger_15d11/readiness-20260930.json) : `WAITING_FOR_FIRST_PROSPECTIVE_MATCH`, zéro séance, zéro lacune. C'est normal : le cutoff du 8 octobre n'a pas encore eu lieu.
- [x] Tests ciblés D7–D11 et IHM passants au jalon de préparation. Ne pas les confondre avec un cycle fournisseur réel réussi.

## P0 — Premier cycle prospectif du 8 octobre 2026

Toutes les heures ci-dessous sont **Asia/Shanghai** ; le 8 octobre, Paris a six heures de retard. Les tâches fonctionnent uniquement si la session Windows `Interactive` requise est ouverte. Contrôler l'heure du PC et la disponibilité de BaoStock ainsi que des pages officielles SSE/SZSE.

### Avant 09:15 : établir le snapshot de décision, sans rétrodatation

- [ ] Vérifier que `cn_dragon_tiger_before_open` a réellement observé la séance événementielle du **30 septembre** le **8 octobre vers 08:30**, avec rapport `COMPLETED_RESEARCH_ONLY`, deux sources attendues, snapshot complet et `observed_at` strictement avant 09:15.
- [ ] Comparer ce snapshot au passage `cn_dragon_tiger_after_close` du 30 septembre : les ajouts **et retraits** comptent. Le dernier snapshot complet et admissible avant 09:15 fait foi.
- [ ] Si le passage automatique manque et que l'on est **encore avant 09:15**, une tentative manuelle D6 est admissible :

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_dragon_tiger_schedule_15d6 --batch-name cn_dragon_tiger_before_open --force
```

- [ ] Si aucun snapshot complet n'a été réellement observé avant 09:15, noter la séance comme **manquante**. Ne pas collecter après coup en prétendant que l'événement était connu avant la décision. Ne pas coder « sans Dragon/Tiger » par défaut.

### Après 09:15 : contrôle et premier appariement

- [ ] Confirmer que l'export D8 du 8 octobre conserve son SHA-256, son horodatage et ses **1 034 candidats** ; le `score_available_at_utc` et la disponibilité du mouvement préalable doivent être antérieurs au cutoff.
- [ ] À partir de 09:30, contrôler dans **Workflow & Orchestration → Batch** le passage `cn_dragon_tiger_daily_match` et son journal `log/batch/cn_dragon_tiger_daily_match.txt`. Le dossier attendu est `artifacts/research/cn_dragon_tiger_15d10/2026-10-08/` avec `report.json` et `outcome_blind_matches.parquet`.
- [ ] Si D10 échoue, lire le message exact du journal sous `artifacts/research/cn_dragon_tiger_15d10/runs/`. Une relance manuelle est possible **uniquement avec les mêmes scores et observations réellement disponibles avant 09:15** :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows/cn_dragon_tiger_daily_launcher_15d10.ps1 -BatchName cn_dragon_tiger_daily_match -Force
```

- [ ] Un échec de provenance, de snapshot ou d'empreinte est un blocage à auditer ; ne pas supprimer ni modifier les exports ou rapports pour faire passer le contrôle. Un second lancement réussi doit sauter le dossier déjà apparié, pas le réécrire.
- [ ] Après D10, lancer D11 avec un **nouveau nom** de sortie et vérifier `decision_sessions = 1`, l'absence de lacune et les compteurs exposés/appariés. Le statut `INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE` est attendu après une seule séance ; zéro paire peut également être une vraie observation à interpréter, pas un résultat directionnel.

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_dragon_tiger_cumulative_15d11 --output artifacts/research/cn_dragon_tiger_15d11/readiness-20261008.json
```

### Après clôture du 8 octobre : préparer le 9 octobre

- [ ] Vérifier le passage D6 `cn_dragon_tiger_after_close` de **17:30** pour les événements du 8 octobre.
- [ ] Vérifier le passage D9 `cn_oracle_prospective_daily` de **18:15** : collecte complète des barres du 8 octobre, préflight `READY_TO_SCORE`, export D8 pour la **décision du 9 octobre**, empreinte et publication avant son cutoff. Suivre `log/batch/cn_oracle_prospective_daily.txt`, `artifacts/cn/sprint7c_daily/2026-10-08/state.json` et `artifacts/research/cn_oracle_daily_15d9/runs/`.
- [ ] Si D9 échoue, conserver les lots déjà reçus et auditer la cause. Une reprise ne doit ni écraser l'export existant ni fabriquer une prédiction après le cutoff du 9 octobre. Le mode D9 planifie la séance **courante après clôture** : ne pas considérer un lancement tardif le lendemain comme un rattrapage prospectif de la veille.

## P0 bis — Reprendre Sprint 17-D après le premier cycle réel

Ne pas confondre code prêt et migration effective. L'[IHM](../../ihm/services/batch_management.py), les lanceurs Windows et les runners D6/D9/D10 savent déjà recevoir `batch_cn.yaml` explicitement ; les tests ciblés de préparation étaient passants le 1er octobre. **Aucune section ni tâche installée n'a encore été déplacée.**

- [ ] Après la séance ouverte du 8 octobre (ou une séance ouverte ultérieure si elle échoue), vérifier dans les rapports réels : D6 avant/après, D10 outcome-blind, D9 avec tous ses lots, Oracle de la séance suivante et contrôle quotidien 17-C sans échec critique. Un rattrapage manuel de septembre et un `SKIP` de calendrier ne suffisent pas.
- [ ] Relancer le [préflight en lecture seule](../../service/market/cn_catalog_preflight_17d.py) avec un nouveau nom de rapport ; il doit ne plus signaler `first_real_d6_d9_d10_quality_cycle_missing`. Vérifier aussi les quatre actions Windows et l'absence de tâche `Running` : le préflight **ne certifie pas** le Planificateur.
- [ ] Seulement alors, suivre la [séquence et le rollback de 17-D](./sprint_17d_preparation_bascule_catalogues.md) : transférer les quatre sections une seule fois de `batch.yaml` vers `batch_cn.yaml`, garder horaires et valeurs métier, ajouter `market_code: CN_A` / `database_alias: cn_primary`, transmettre explicitement le catalogue, réinstaller une tâche à la fois sous son nom actuel hors fenêtre CN et confirmer la parité au cycle suivant.
- [ ] Si une tâche ou un export manque, restaurer la configuration et les quatre définitions d'origine **avant** la prochaine échéance ; ne jamais créer deux propriétaires D9 ni rétro-dater un score Oracle.
- [ ] Continuer indépendamment le gate 17-C : **sept séances ouvertes consécutives** sans anomalie critique inexpliquée. Un premier cycle permettant d'envisager 17-D ne clôture pas 17-C.

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_catalog_preflight_17d --output artifacts/research/cn_operations_17a/cutover-preflight-NOUVELLE_DATE.json
```

## P1 — Exploitation sur les séances suivantes

- [ ] Chaque jour ouvert, surveiller dans l'ordre : D6 avant ouverture → D10 après cutoff → D6 après clôture → D9 après clôture. Vérifier les heures réelles d'observation/publication, pas seulement le statut Windows `Ready`.
- [ ] Une fois par semaine, produire un nouveau rapport D11 avec un nom unique ; examiner `missing_daily_matches`, `decision_sessions`, `exposed_candidates`, `matched_exposed`, `matched_fraction`, les deux différences standardisées, les trimestres et `gate_checks`. Conserver les rapports antérieurs pour voir les ruptures de couverture.
- [ ] Investiguer chaque lacune et la classifier : D6 absent/tardif, D9 absent/tardif, fournisseur incomplet, calendrier, session Windows fermée, provenance/empreinte invalide. Ne jamais combler une lacune par un snapshot obtenu après cutoff.
- [ ] Vérifier que les notifications **mail et Telegram** arrivent effectivement en cas d'échec. L'audit D6 avait signalé une erreur de chaîne TLS Telegram locale ; ne pas désactiver la vérification HTTPS pour la contourner. Les fichiers de rapport et journaux restent la source de vérité en cas d'absence de notification.
- [ ] Contrôler la capacité disque, les sauvegardes et la conservation des exports D8, snapshots D6, paires D10, journaux et rapports D11. Ne pas laisser une politique de nettoyage supprimer les empreintes ou les données nécessaires à l'audit.
- [ ] Avant la première séance de **2027**, valider le calendrier officiel de marché et adapter le fichier/calcul métier. L'année non vérifiée échoue fermée ; ne pas prolonger 2026 par simple répétition des jours ouvrés.
- [ ] Examiner les droits de réutilisation des listes officielles SSE/SZSE et la qualification PIT : une observation faite avant notre cutoff ne prouve pas à elle seule l'heure de première publication officielle. Tant que ce point reste ouvert, usage descriptif de recherche uniquement.

## P2 — Gate scientifique avant de lire les issues

Ne pas lancer l'analyse de performance simplement parce qu'un premier appariement existe. Le protocole [figé](../../config/research_cn/sprint15d7_dragon_tiger_protocol.yaml) exige simultanément :

- [ ] Au moins **60 séances de décision** prospectives réellement appariées.
- [ ] Au moins **200 candidats Oracle exposés** à Dragon/Tiger.
- [ ] Au moins **80 % des exposés** appariés à un contrôle admissible.
- [ ] Au moins **deux trimestres calendaires** représentés par des paires.
- [ ] Équilibre des paires : différence standardisée absolue **≤ 0,10** pour le rang Oracle et le rendement préalable 5 séances.
- [ ] Aucun export Oracle dont le cutoff est passé sans résultat D10 admissible, sauf lacune explicitement conservée et traitée selon le protocole ; aucun score, snapshot ou modèle tardif ; identités et empreintes cohérentes.
- [ ] Revoir l'effectif **effectif** en tenant compte de la dépendance entre titres d'une même séance et des titres récurrents. Les seuils minimaux ne garantissent pas à eux seuls la puissance statistique.

Si un gate échoue, continuer la collecte ou conclure `NO_DECISION / INSUFFICIENT_DATA` ; **ne pas assouplir les calipers en regardant les rendements futurs**.

## P3 — Audit H20 séparé, seulement après le gate et la maturité

- [ ] Geler la liste des paires et ses empreintes **avant** la jointure des issues. Pour chaque décision K, attendre la clôture de **K+20 séances** et la disponibilité du label à **K+21** ; aucune extrapolation en jours calendaires.
- [ ] Reconstruire la cible définie dans [cn_oracle_labels.py](../../modelFactory/cn_oracle_labels.py) : entrée à l'ouverture de K, sortie à la clôture ajustée de K+20, décile quotidien parmi la coupe transversale valide. Ne pas utiliser le label Oracle de la séance événementielle J.
- [ ] Vérifier radiations, suspensions, limites de prix, corporate actions et manques de barres. Exclure symétriquement toute issue invalide ; publier l'attrition et ne jamais reclasser automatiquement une paire en gagnante/perdante.
- [ ] Évaluer séparément **réduction de risque D1 (`D1_veto`)** et **gain de précision D10 (`D10_long`)**, face au TOP20 Oracle pur et à l'abstention. Publier taux de base, effectifs, différences absolues, résultats par trimestre et board, et intervalles bootstrap par **séance entière** (1 000 répétitions).
- [ ] Ne pas choisir de seuil, branche LONG/SHORT, fournisseur ou sous-groupe sur le trimestre de confirmation. Rapporter aussi les variantes et échecs, puis réserver un bloc temporel ultérieur réellement hors sélection pour toute décision de poursuite.
- [ ] En cas de résultat positif, ouvrir **ensuite seulement** un replay économique avec coûts, disponibilité réelle et risques de portefeuille. Aucun déploiement live sans droits de données, PIT qualifié et nouveau gate de production.

## Points de reprise rapides

1. Lire le dernier rapport de `artifacts/research/cn_dragon_tiger_15d11/`, puis les quatre batchs CN dans la page Batch et leurs journaux sous `log/batch/`.
2. Si `WAITING_FOR_FIRST_PROSPECTIVE_MATCH`, attendre la prochaine séance et contrôler les cutoffs D6/D8. Si `INCOMPLETE_PROSPECTIVE_JOURNAL`, examiner `missing_daily_matches` avant toute statistique.
3. Si `INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE`, consulter chaque `gate_checks` et poursuivre la collecte **sans changer les règles**. Si `MATCHING_READY_FOR_SEPARATE_OUTCOME_AUDIT`, vérifier indépendamment les empreintes, la maturité H20 et les droits avant P3.
4. Ne jamais confondre **appariement prêt**, **signal directionnel démontré**, **stratégie rentable après coûts** et **données autorisées en production** : ce sont quatre décisions distinctes.
