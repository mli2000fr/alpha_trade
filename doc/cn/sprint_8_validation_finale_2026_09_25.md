# Sprint 8 CN — Validation finale du backfill PIT

Date : 25 septembre 2026. Périmètre : actions A CN_A, séances ouvertes du 1er janvier 2018 au 31 décembre 2025, politique V1 du [guide Sprint 8](sprint_8_univers_pit.md).

## Verdict

**PASS technique pour l'univers quotidien PIT historique.** Les 1 942 séances ouvertes ont chacune un snapshot terminé. Aucun snapshot manquant ou doublon de séance pour la politique validée ; les comptes de décisions et d'audits correspondent aux métadonnées de chaque run. Aucune décision ne lit une barre datée de J ou un `available_at` postérieur à l'ouverture J. Aucun candidat ne précède son introduction ou ne suit sa date de radiation.

Le contrôle complet est reproductible :

```powershell
python -u -m dataIntegrityEngine.cn_sprint8_audit --start-date 2018-01-01 --end-date 2025-12-31
```

Résultat :

| Contrôle | Résultat |
|---|---:|
| Séances attendues / runs terminés | 1 942 / 1 942 |
| Séances absentes, doublonnées ou comptes incohérents | 0 / 0 / 0 |
| Décisions avec données futures | 0 |
| Candidats hors période de cotation | 0 |
| Conflits de statut source / présents parmi les candidats audités | 8 / 3 |
| Conflits de candidats non exclus au replay | 0 |
| Limites inconnues source / présentes parmi les candidats audités | 181 / 67 |
| Limites inconnues de candidats certifiées à tort | 0 |
| Dates de radiation sans barre / candidates le matin | 23 / 2 |
| Dates terminales candidates sans barre mais mal auditées | 0 |

Les 5 conflits, 114 limites inconnues et 21 dates terminales restants ne figuraient **pas** parmi les candidats avant séance selon les autres règles PIT. Les deux dates terminales candidates sont correctement classées `NO_SESSION_BAR` après séance : elles ne sont pas transformées en fills.

## Correction de performance du gate

La première version du gate commençait ses jointures par des millions de lignes d'audit, puis recherchait les huit et 181 rares anomalies. La migration CN [0007](../../alembic_cn/versions/0007_universe_audit_indexes.py) ajoute les index `trading_status,date` et `policy_code,session_date`. L'audit commence désormais par les anomalies source, puis joint les runs et les audits correspondants. Cela évite la jointure massive non indexée ; le contrôle complet retourne en environ une minute sur la base actuelle. La migration a été appliquée à `alpha_trade_cn` uniquement.

## Portée du GO

Ce PASS valide la **construction de l'univers de recherche** et l'absence des fuites temporelles vérifiées. Les seuils de prix/liquidité de `config/universe_cn.yaml` sont initiaux et doivent être évalués économiquement avant déploiement. `DATA_CHECKS_PASSED` ne garantit ni carnet disponible, ni exécution d'ordre, ni coûts réels. Le live CN reste désactivé. Les changements historiques de ticker ne sont pas représentés par plusieurs mappings BaoStock dans ce backfill ; leur gestion devra être exercée avec un cas synthétique ou une source qui les fournit avant un GO d'exécution complet.

Le Sprint 9 (features CN baseline) peut commencer sur ces snapshots figés. Aucun modèle CN ni backtest de production n'est validé par ce document.
