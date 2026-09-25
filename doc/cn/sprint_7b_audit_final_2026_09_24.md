# Sprint 7-B — Audit après backfill du 24 septembre 2026

## Verdict

Le backfill historique 2018–2025 est terminé : **217/217 lots `COMPLETED`, aucun lot en échec**. Les contrôles intégrés renvoient `PASS` : **5 405/5 405 actions mappées et dotées de barres** et **31/31 segments board × année** au-dessus du seuil de couverture de 95 %.

Le **gate de qualité complet reste conditionnel pour un backtest exécutable** : les 23 absences de barre correspondent exactement à des dates de radiation et sont désormais documentées comme exceptions terminales, tandis que huit statuts de suspension contredisent le volume et 181 limites dérivées restent invérifiables. Ces exceptions ne doivent pas être masquées par le simple statut `PASS` des contrôles intégrés. Le [contrat tradable PIT](contrat_univers_tradable_pit.md) fixe les exclusions sans anticiper des données de clôture.

## Correctif appliqué le 24 septembre 2026

Les chiffres des sections suivantes décrivent **l'état avant correction**. La règle de prix applique désormais ±20 % aux actions STAR et ChiNext post-réforme même si elles sont ST ; ChiNext ST avant le 24 août 2020 et Main ST restent à ±5 %. Le recalcul historique a modifié **32 363 limites ST** (29 983 ChiNext et 2 380 STAR). Les **8 240** violations expliquées par l'ancienne priorité ST ont disparu. Les **181** journées encore incompatibles avec la règle simplifiée portent maintenant `policy_code=OBSERVED_OUTSIDE_DERIVED_LIMIT_V1`, `is_rule_exception=1` et des limites `NULL` : aucune borne active ne contredit désormais l'OHLC connu.

Les huit barres à statut suspendu et volume positif portent `SOURCE_CONFLICT` dans `trading_status` ; les huit lignes correspondantes de `instrument_status_history` restent `is_tradable=0`. Le payload BaoStock brut demeure inchangé. Le marqueur de contradiction, établi à partir du volume quotidien, n'est disponible qu'après clôture et ne constitue pas une preuve rétroactive d'exécutabilité à l'ouverture.

Preuves : `artifacts/cn/sprint7b/sprint7b-20260924181645/report.json` (32 363 / 181 / 8 / 8) et `artifacts/cn/sprint7b/sprint7b-20260924181854/report.json` (second passage : **0 / 0 / 0 / 0**). Tests ciblés : `tests/test_sprint7b_cn_canonical_full.py` et `tests/test_sprint7a_cn_canonicalization.py`, exécutés avec `--no-cov` ; 25 tests passent. Aucun schéma SQL n'a changé.

Sources de preuve : `artifacts/cn/sprint7b/state.json`, `artifacts/cn/sprint7b/sprint7b-20260923222102/report.json`, `artifacts/cn/sprint7b/sprint7b-20260924061311/report.json` (couverture) et `artifacts/cn/sprint7b/sprint7b-20260924061346/report.json` (audit). Les requêtes complémentaires ont été exécutées en lecture seule sur `alpha_trade_cn`, sauf le test d'idempotence décrit plus bas.

## Couverture 2018–2025

Le run `cn-s7b-coverage-20260924061311-192b74af` compte **8 612 894 barres d'actions observées pour 8 612 917 séances-titres théoriques**, soit 23 écarts. Le minimum des 31 ratios annuels est **99,997574 %**, bien au-dessus du seuil technique de 95 %. Les quatre indices du canonique ne sont pas compris dans ce dénominateur ; `stock_bars_daily` contient 8 620 662 lignes actions + indices dans la fenêtre.

| Segment | Attendues | Observées | Écart |
|---|---:|---:|---:|
| ChiNext | 2 056 792 | 2 056 787 | 5 |
| Shanghai Main | 3 101 844 | 3 101 834 | 10 |
| STAR | 626 057 | 626 057 | 0 |
| Shenzhen Main | 2 828 224 | 2 828 216 | 8 |
| Total | 8 612 917 | 8 612 894 | 23 |

Les 23 écarts concernent 23 titres différents, une seule date chacun. Dans tous les cas, la date absente est **exactement la `delisting_date`** ; aucune lacune interne n'a été détectée entre introduction et veille de radiation. Deux cas sont en 2018–2019, les 21 autres en 2025. Parmi les 223 titres radiés, **200 possèdent une barre à `delisting_date`** : la borne est donc conservée **inclusive** pour la vie du titre. Les 23 autres sont des exceptions terminales explicites, sans barre ni fill inventé, et non une règle d'exclusion de toutes les dates de radiation.

Les trois lignes rejetées à la promotion proviennent des lots 96 (deux) et 163 (une) : `sz.000022` le 2018-12-26, `sz.000043` le 2019-12-16 et `sz.300114` le 2025-02-17. Ce sont des lignes BaoStock `SUSPENDED` **sans OHLC ni volume**, toutes à la date de radiation. Elles n'ont pas été converties en fausses barres. Aucun lot ne manque entièrement de barres ; aucune erreur de collecte n'est signalée dans l'état des 217 lots.

## Titres radiés et intégrité

- **223 actions radiées** avant fin 2025 sont présentes dans le référentiel et possèdent **273 606 barres historiques**. Aucune barre d'action n'est datée avant son introduction ou après sa radiation.
- Aucun OHLC incohérent, prix nul/négatif, volume ou montant négatif, `adj_close` différent du close brut, barre sur séance fermée, facteur d'ajustement non positif ou timestamp PIT inversé n'a été trouvé dans les tables vérifiées.
- Les clés primaires des barres (`instrument_id`, `date`), facteurs et limites, ainsi que la clé unique des événements de facteur, empêchent les doublons métier de ces types. Aucun mapping BaoStock ne pointe vers plusieurs instruments.
- Les 12 417 volumes et montants nuls sont tous sur des lignes `SUSPENDED`. Avant correction, **8 lignes `SUSPENDED` avaient un volume positif** (dont 6 avaient aussi un montant positif). Elles sont désormais marquées `SOURCE_CONFLICT`, mais la contradiction du fournisseur reste à expliquer. Cas observés : `sz.002336`, `sz.002500`, `sh.688065`, `sz.300356`, `sh.600647`, `sh.600766`, `sh.603133`, `sz.002087`.

## Limites de prix et événements

Avant correction, les **8 612 894** limites journalières portaient `derivation_method=board_rule_v1` et `source=alpha_trade_derived`. Sur **8 585 882** journées hors exceptions avec bornes calculées, **8 421 journées** avaient au moins un haut/bas au-delà de la borne calculée (4 909 dépassements hauts, 3 795 bas ; les deux peuvent coexister). Parmi ces journées, 8 241 relevaient de la règle simplifiée ST ±5 %, 154 de Main ±10 %, 24 de ChiNext ±20 % et 2 de STAR ±20 %. Après correction et quarantaine des 181 résiduelles, la requête de contrôle retourne **0 borne active contredite**. Les limites restent indicatives, non officielles.

Les **24 972** événements de facteur sont correctement étiquetés `UNCLASSIFIED_FACTOR_EVENT` ; ils ne constituent pas un ledger officiel de dividendes, splits et droits.

## Second passage et doublons

Sans `--force`, l'orchestrateur ignorerait les **217 lots** déjà `COMPLETED`. Pour tester aussi les écritures, une nouvelle promotion et un nouvel enrichissement ont été exécutés sur les lots **6, 96 et 216** (55 actions, dont des radiées ; 93 429 barres dans ces lots). Les comptes et les signatures des valeurs métier des barres, statuts, facteurs, limites et événements étaient **identiques avant/après** pour chacun des trois lots. Le lot 96 reproduit ses deux rejets source connus ; il n'ajoute aucun doublon métier.

Ce test établit l'idempotence sur l'échantillon, pas une preuve par rejeu physique des 217 lots. Les nouvelles lignes de `cn_canonicalization_runs` créées pour la traçabilité du test ne sont pas des doublons métier.

## Décision avant Sprint 8

**GO technique pour exploiter les barres historiques et préparer le Sprint 8 en recherche ; pas encore GO sans réserve pour un univers tradable exécutable.** La convention est désormais figée et testée :

1. `delisting_date` est inclusive ; le nouveau contrôle `cn-s7b-coverage-20260924183751-a8341df5` publie 23 exceptions terminales et **zéro lacune inexpliquée**, avec 31/31 segments `PASS` ;
2. les huit `SOURCE_CONFLICT` ne sont pas certifiés tradables ; leur statut ne peut toutefois pas être utilisé avant son `available_at` ;
3. les 181 limites inconnues restent `UNVERIFIABLE` dans le replay d'exécution, pas des exclusions rétrospectives de la sélection ;
4. le module de contrat et ses tests sont prêts, mais leur branchement au snapshot quotidien Sprint 8 et la confirmation indépendante des cas ambigus restent à faire.

Les contrôles réalisés ne constituent ni un GO pour le ML/backtest CN, ni une autorisation de live CN.
