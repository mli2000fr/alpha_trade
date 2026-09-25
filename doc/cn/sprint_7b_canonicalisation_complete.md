# Sprint 7-B — Canonicalisation complète et couverture historique CN

## Statut

**Implémentation terminée le 22 septembre 2026. Backfill 217/217 terminé le 24 septembre 2026 ; audit de qualité détaillé effectué, gate complet conditionnel.** Voir [l'audit après backfill](./sprint_7b_audit_final_2026_09_24.md).

Le Sprint 7-B généralise le pipeline validé au Sprint 7-A à toutes les actions A ayant chevauché la période du 1er janvier 2018 au 31 décembre 2025. Il ne débloque pas à lui seul le ML, le backtest ou le live CN : le gate final exige la fin du backfill, l'audit de couverture et la validation des exceptions.

Le manifeste figé contient **5 405 actions** actives ou délistées et porte le SHA-256 4a8710fb5fcc1c5847f0210cf0ead4830b57abf2356d2c708f1601f30d500c1a. Il est découpé en **217 lots de 25 titres**. La petite taille des lots est volontaire : BaoStock n'accepte pas de sessions concurrentes stables et un lot court réduit le coût d'une reprise.

## Livrables

- migration Alembic CN 0005_canonical_full_coverage ;
- SQL database/sql/cn/migration_cn_0005_canonical_full_coverage.sql ;
- service service/market/cn_canonical_full.py ;
- orchestrateur dataIntegrityEngine/cn_sprint7b_full.py ;
- manifeste config/univers_cn/canonical_full_2018_2025.txt ;
- lots et index sous config/univers_cn/sprint7b_chunks_2018_2025/ ;
- état reprenable artifacts/cn/sprint7b/state.json ;
- rapports sous artifacts/cn/sprint7b/sprint7b-*/report.json ;
- tests tests/test_sprint7b_cn_canonical_full.py.

La migration refuse toute base autre que alpha_trade_cn. L'audit CN attend désormais la révision 0005_canonical_full_coverage.

## Périmètre historique

La population est reconstruite depuis la dernière révision stock_basic du staging BaoStock. Un instrument est retenu si :

1. type = 1, donc action ;
2. sa date d'introduction est au plus tard le 31 décembre 2025 ;
3. sa radiation est absente ou postérieure au 1er janvier 2018 ;
4. son symbole BaoStock est valide et rattachable à Shanghai ou Shenzhen.

Les titres radiés sont conservés afin d'éviter le biais de survivance. Ce manifeste n'est pas encore l'univers tradable PIT : cette responsabilité appartient au Sprint 8.

## Architecture

~~~text
stock_basic déjà collecté
        │
        ▼
manifeste historique 5 405 titres
        │
        ▼
217 lots déterministes de 25
        │
        ▼
collecte BaoStock séquentielle
  daily raw + adjustment factors
        │
        ▼
staging neutre et rejouable
        │
        ▼
promotion canonique par lot
        ├── instruments et mappings
        ├── stock_bars_daily
        ├── instrument_status_history
        └── instrument_adjustment_factors
        │
        ▼
enrichissements dérivés
        ├── cn_daily_price_limits
        └── cn_corporate_actions
        │
        ▼
couverture board × année
        │
        ▼
gate Sprint 8
~~~

Un lot COMPLETED est ignoré, sauf avec --force. Un échec est marqué FAILED avec son message. La reprise évite les lots terminés et réutilise également l'état interne du collecteur.

## Limites journalières de cours

cn_daily_price_limits contient une valeur par instrument et séance. Les valeurs sont **dérivées**, pas téléchargées comme limites officielles. `source=alpha_trade_derived` et `derivation_method` distinguent les anciennes règles `board_rule_v1`, la correction `board_rule_v2` et les exceptions `observed_break_v1`. Une borne contredite par l'OHLC est désormais mise à `NULL` avec `policy_code=OBSERVED_OUTSIDE_DERIVED_LIMIT_V1` et `is_rule_exception=1`. Cette contradiction n'est observable qu'après la clôture et ne doit jamais être utilisée pour décider rétroactivement d'une exécution intrajournalière.

| Cas | Limite |
|---|---:|
| cinq premières observations | aucune limite affirmée, exception conservatrice |
| STAR, y compris ST | ±20 % |
| ChiNext à partir du 24 août 2020, y compris ST | ±20 % |
| ST des marchés principaux avant le 6 juillet 2026 ou ChiNext avant le 24 août 2020 | ±5 % |
| ST des marchés principaux à partir du 6 juillet 2026 | ±10 % |
| Autres actions ChiNext avant la réforme et marchés principaux | ±10 % |

À partir du **6 juillet 2026**, les ST des marchés principaux passent également à ±10 %. Cette règle future n'affecte pas le backfill 2018–2025. Références : [règle ChiNext et ST de Shenzhen](https://www.szse.cn/English/rules/siteRule/P020240911598586572526.pdf), [réforme 2026 de Shanghai](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml), [entrée en vigueur Shenzhen](https://investor.szse.cn/lawrules/rule/trade/t20260424_620190.html).

Les bornes partent de pre_close et sont arrondies au centime avec ROUND_HALF_UP. Sans pre_close, la séance reste une exception. reached_up, reached_down, locked_up et locked_down utilisent une tolérance d'un demi-centime.

La V1 ne prétend pas encore couvrir toutes les règles d'IPO, relisting ou réformes historiques. Les cinq premières observations sont exclues plutôt que faussement classées. Une source officielle pourra remplacer ces valeurs.

## Corporate actions

BaoStock fournit des facteurs d'ajustement, sans classification fiable de chaque dividende, split ou rights issue. Le Sprint 7-B détecte chaque changement, stocke ancien et nouveau facteur, date d'effet, hash et timestamps PIT, puis classe l'événement UNCLASSIFIED_FACTOR_EVENT.

Il ne déduit jamais un dividende ou un split du seul facteur. Les champs d'annonce, record, paiement, montant et ratio restent nuls sans source justificative. Ces événements signalent une discontinuité ; ils ne constituent pas encore un ledger économique complet.

## Suspensions et couverture

Une absence de barre n'est jamais convertie en suspension. Seuls les statuts explicitement observés alimentent explicit_suspension_count. Une séance attendue sans barre ni statut reste une lacune, **sauf** l'exception terminale explicitement comptée quand elle coïncide avec `delisting_date` sur une séance ouverte. La date de radiation est par ailleurs inclusive : 200 des 223 titres radiés ont une barre ce jour-là.

cn_canonical_coverage_metrics agrège chaque exécution par board et année :

- instruments concernés ;
- séances attendues selon calendrier, listing et delisting ;
- barres observées ;
- suspensions explicites ;
- facteurs présents ;
- ratio et statut ;
- `details_json.delisting_day_no_bar` et `details_json.unexplained_missing`.

Le statut PASS exige 95 % **et zéro absence inexpliquée**. Ce seuil est un gate technique, pas une preuve d'exécutabilité. La dernière vérification complète donne 31/31 PASS, 23 exceptions terminales et aucune lacune inexpliquée. Voir le [contrat d'univers négociable PIT](contrat_univers_tradable_pit.md).

## Validation déjà obtenue

Sur les 80 actions du pilote 7-A :

- 123 819 limites journalières ;
- 318 changements de facteur non classifiés ;
- 31 segments board×année, tous PASS ;
- 80/80 instruments mappés avec barres ;
- audit PASS.

Rapports : artifacts/cn/sprint7b/sprint7b-20260922064708/report.json, sprint7b-20260922064709/report.json et sprint7b-20260922064710/report.json.

Ces preuves valident le code ; elles ne remplacent pas l'audit des 5 405 actions.

## Commandes

Migration :

~~~powershell
F:projets.venvScriptspython.exe -m alembic -c alembic_cn.ini upgrade head
~~~

Préparation :

~~~powershell
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full prepare --chunk-size 25
~~~

Un lot, puis reprise complète :

~~~powershell
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full run-chunk --chunk-index 0
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full run-all --start-chunk 0
~~~

Limiter une session à dix lots :

~~~powershell
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full run-all --start-chunk 0 --max-chunks 10
~~~

Promotion/enrichissement sans appel BaoStock :

~~~powershell
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full promote --chunk-index 0
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full enrich --chunk-index 0
~~~

Couverture et audit :

~~~powershell
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full coverage
F:projets.venvScriptspython.exe -u -m dataIntegrityEngine.cn_sprint7b_full audit
~~~

## Surveillance

~~~powershell
$s = Get-Content F:projetsartifactscnsprint7bstate.json -Raw | ConvertFrom-Json
$items = @($s.chunks.PSObject.Properties | ForEach-Object { $_.Value })
[pscustomobject]@{
  Termines = ($items | Where-Object status -eq 'COMPLETED').Count
  Echecs = ($items | Where-Object status -eq 'FAILED').Count
  EnCours = ($items | Where-Object status -eq 'RUNNING').Count
  Total = 217
}
~~~

Un RUNNING ancien après arrêt brutal peut être repris avec run-chunk. Ne jamais lancer deux sessions BaoStock en parallèle.

## Gate final

Le Sprint 7-B passe à GO complet uniquement si :

1. les 217 lots sont COMPLETED ;
2. les 5 405 instruments sont mappés ;
3. chaque titre possède des barres sur ses périodes effectivement cotées ;
4. aucun doublon canonique n'existe ;
5. les anomalies OHLC, volume, montant et calendrier sont nulles ou justifiées ;
6. chaque manque de couverture est accepté ou recollecté ;
7. limites dérivées et événements non classifiés ne sont pas traités comme sources officielles ;
8. un second passage conserve les comptes métier ;
9. aucune table US n'est lue ou modifiée ;
10. CN_A reste désactivé pour le live.

Le backfill et la couverture du Sprint 7-B sont terminés. Sprint 8 pourra publier l'univers tradable quotidien PIT **après** le branchement du contrat de décision/replay et la validation des exceptions ; le `PASS` de couverture ne suffit pas pour le backtest exécutable ou le live.

## Correctif de robustesse BaoStock du 22 septembre 2026

BaoStock utilise une socket sans timeout natif fiable et ses historiques longs déclenchent une pagination fragile. Le client Alpha-Trade impose désormais un timeout de 30 secondes, trois tentatives et une reconnexion.

Lorsqu'un manifeste explicite est fourni, le service ne recharge plus le référentiel stock_basic complet. Les barres 2018–2025 sont demandées par fenêtres maximales de trois ans, soit trois requêtes quotidiennes par symbole, afin de rester sous la page BaoStock de 1 000 lignes. Chaque fenêtre validée est inscrite immédiatement dans l'état de reprise.
