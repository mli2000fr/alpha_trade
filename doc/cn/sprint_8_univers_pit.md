# Sprint 8 — Univers chinois quotidien Point-in-Time

Statut au 25 septembre 2026 : **backfill 2018–2025 et gate PIT terminés, `PASS` technique**. Voir la [validation finale](sprint_8_validation_finale_2026_09_25.md). Ce travail ne branche pas encore le ML, le backtest de production ou le live CN.

## Objectif et frontière temporelle

Chaque séance `CN_A` possède deux états distincts :

1. **Décision avant ouverture** (`decision_at = market_sessions.open_at_utc`) : toutes les barres utilisées datent au plus de la séance ouverte précédente et vérifient `available_at <= decision_at`. Le référentiel conserve les entreprises radiées ultérieurement et identifie les IPO futures sans filtre basé sur `is_active` actuel.
2. **Audit après clôture** : présence et statut de la barre du jour, politique de limite de prix et verrouillage. Cet audit ne modifie pas la sélection initiale et ne revendique pas un fill réel. Les 8 conflits `SOURCE_CONFLICT` sont exclus de l'audit ; les limites inconnues et verrouillées sont `UNVERIFIABLE`.

Le [contrat de négociabilité](contrat_univers_tradable_pit.md) fixe la convention `delisting_date` inclusive et les reason codes. Un titre à la date de radiation peut être candidat avant ouverture ; sans barre à la clôture, aucun fill ne peut être certifié.

## Politique V1 configurable

Le fichier [universe_cn.yaml](../../config/universe_cn.yaml) définit les seuils initiaux : 60 séances de regard arrière, au moins 40 barres valides ; 20 séances pour la liquidité, au moins 15 barres ; close précédent ≥ 1 CNY et montant moyen ≥ 5 M CNY ; barre de la séance précédente exigée. Il s'agit d'une **politique technique initiale, non d'un optimum de performance démontré**. Un changement de paramètre crée un nouveau fingerprint ; les anciens snapshots restent inspectables.

`TRADE|ST` n'est pas exclu par défaut : une politique ST doit être testée économiquement et être connue avant décision. Une limite verrouillée le jour même ne peut pas non plus exclure rétroactivement le titre de la sélection du matin ; elle rend l'audit d'exécution dépendant du côté LONG/SHORT et donc non vérifiable sans données supplémentaires.

## Persistance et reprise

La migration [0006_universe_pit.py](../../alembic_cn/versions/0006_universe_pit.py) et le [SQL de référence](../../database/sql/cn/migration_cn_0006_universe_pit.sql) créent dans `alpha_trade_cn` uniquement :

- `cn_universe_runs` : date, heure de décision, empreintes de politique et de données, comptes et statut ;
- `cn_universe_decisions` : une ligne par instrument, candidat/exclu, tous les motifs, historiques et valeurs connues avant ouverture ;
- `cn_universe_execution_audit` : seulement les candidats, avec état `DATA_CHECKS_PASSED`, `EXCLUDED` ou `UNVERIFIABLE` et motif associé.

L'identifiant du run est dérivé de la date et du fingerprint des décisions. Rejouer exactement les mêmes entrées produit le même identifiant et n'ajoute pas de doublon. Une correction des données antérieures ou un changement de politique crée un nouveau run conservant le précédent. La commande exporte aussi les candidats du matin, triés et séparés par virgule, dans `artifacts/cn/universe/<run_id>/universe.txt` et un `report.json`.

Commandes :

```powershell
# Smoke sans écriture
python -u -m dataIntegrityEngine.cn_sprint8_universe --start-date 2024-06-03 --end-date 2024-06-03 --dry-run

# Publication d'une période ; relancer la même période est idempotent
python -u -m dataIntegrityEngine.cn_sprint8_universe --start-date 2018-01-01 --end-date 2025-12-31

# Limiter le nombre de séances pour un contrôle
python -u -m dataIntegrityEngine.cn_sprint8_universe --start-date 2024-01-01 --end-date 2024-12-31 --max-sessions 5

# Gate de fin de backfill, en lecture seule ; sortie PASS ou INCOMPLETE
python -u -m dataIntegrityEngine.cn_sprint8_audit --start-date 2018-01-01 --end-date 2025-12-31
```

Le backfill complet lancé le 24 septembre utilise `log/batch/cn-sprint8-universe-20260924/stdout.log` et `stderr.log`. Un log de sortie par séance porte la date, l'identifiant, les candidats et les comptes d'audit. La relance après arrêt est sûre mais recalcule les dates déjà traitées ; on peut choisir une date de reprise plus tardive en lisant la dernière ligne complète.

Pour suivre la progression sans garder une fenêtre ouverte :

```powershell
(Get-Content F:\projets\log\batch\cn-sprint8-universe-20260924\stdout.log | Measure-Object -Line).Lines
Get-Content F:\projets\log\batch\cn-sprint8-universe-20260924\stderr.log -Tail 5
```

## Validation initiale réelle

Sur la séance 2024-06-03 : 5 405 actions de référence, 5 057 candidates avant ouverture, 5 057 audits dont 5 041 `DATA_CHECKS_PASSED`, 1 `EXCLUDED` et 15 `UNVERIFIABLE`. Parmi les candidates, **53 titres sont aujourd'hui radiés mais l'étaient après cette date** ; **139 IPO futures sont exclues**. Deux passages ont produit le même run `cn8-20240603-1113b52f4ea21649` et les comptes en base restent 1 run, 5 405 décisions et 5 057 audits. Les séances 2020-06-17 et 2018-08-24, choisies pour des conflits de statut et de limite, ont également passé le smoke sans écriture.

Les tests ciblés couvrent l'IPO future, le titre radié ultérieurement, la borne de radiation inclusive, la suspension connue, le statut encore inconnu au matin, la liquidité, le fingerprint et la migration. Les résultats économiques ne sont pas évalués par ces tests.

## Gate de clôture du Sprint 8

Ne déclarer le Sprint 8 terminé qu'après :

1. fin du backfill 2018–2025, sans séance manquante ni erreur ;
2. contrôle du nombre de runs et de décisions par séance, des fingerprints et de l'absence de doublons ;
3. vérification ciblée des 23 dates de radiation sans barre, des 8 conflits et des 181 limites inconnues ;
4. revue des tailles quotidiennes et de la couverture par année/board, ainsi que de la stabilité des seuils de liquidité ;
5. preuve qu'aucune table US n'a été modifiée et qu'aucune donnée de clôture J ne filtre la décision avant l'ouverture J.

Seule cette validation autorisera le Sprint 9 (features CN) ; les exécutions live restent désactivées.
