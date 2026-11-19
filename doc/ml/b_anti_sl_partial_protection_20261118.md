# B + anti-SL TOP10 — protection partielle et reprise progressive

Expérience demandée le 18 novembre 2026. Quatre variantes croisent **quantité pilotée 100 % ou 50 %** et **ancienne sortie ou reprise progressive**. Un cinquième replay reproduit le témoin B + anti-SL sans protection. Aucun changement de production ou de modèle.

## Référence et invariants

2021–1er octobre 2026, **4 000 $ continus**, sans remise à zéro annuelle. Même univers de 1 790 titres et mêmes modèles annuels/sélections archivées que B + anti-SL témoin : TOP10 % Oracle H10 (179) → TOP10 LONG B29, score >0,50/AUC de calibration ≥0,50, puis veto anti-SL sans remplacement. Aucun entraînement, nouveau score, label ou seuil de modèle.

Position complète entière, ouverture J+1 sans confirmation, **SL5 %, sans TP/trailing/renforcement, sortie open11**. Risque 1,25 %, poids maximal 20 %, vingt positions, minimum 50 $, plafond nouvelles entrées 1× et capacité margin 2× ; frais et financement natifs conservés. Concentration native inchangée. B4/DD, facteurs, corrélation et plafonds sectoriels désactivés comme le témoin. Intraday et repli OHLC exactement issus des archives antérieures.

Les liquidations et rachats sont de véritables transactions simulées à l'ouverture officielle suivante, avec frais et capital partagé ; pas d'ajustement a posteriori de la courbe.

## Activation commune et indépendante des variantes

L'observateur est celui du test antérieur `SL10_SHADOW`, recalculable uniquement à partir des données connues à chaque clôture : baisse du taux LONG mûr B TOP10 sur vingt séances par rapport à la référence antérieure de 120 séances, écart >5 points pendant trois clôtures qualifiées. La cohorte B est mesurée avant veto anti-SL et ne dépend pas des positions exécutées par chaque variante.

Cet observateur conserve son réarmement historique : le compte virtuel continu B + anti-SL sans protection doit avoir un rendement sur vingt séances >5 % pendant cinq clôtures pour remettre son alerte à zéro. Les quatre variantes reçoivent donc **exactement les mêmes dates ON**. Une reprise anticipée de leur budget ne fabrique pas de nouvelle alerte dès le lendemain parce qu'un ancien taux reste faible.

Cette comparaison isole les modalités de liquidation/reprise. Elle ne prétend pas avoir trouvé un meilleur signal d'activation. Les contrôles de préfixe sur 2022, novembre 2024 et mai 2025 vérifient que les états passés ne changent pas en ajoutant des données futures.

## Quantité pilotée : compte unique

| Variante | Partie de base | Partie pilotée |
| --- | --- | --- |
| Totale | Aucune | Toute la quantité approuvée par le risque natif |
| Partielle | Environ 50 % des actions de chaque nouvelle position | Le reste |

Pour une quantité native N, la partie de base vaut **ceil(N/2)** et la partie pilotée **floor(N/2)**. Une position d'une seule action reste entièrement dans la partie de base. Ce choix évite les fractions et conserve au moins une action lorsque l'approbation native le permet ; la répartition n'est donc pas exactement 50/50 pour les petites quantités.

Il n'y a ni deux comptes de 2 000 $, ni duplication des achats ou de la capacité. Les deux parties appartiennent au même ordre initial et partagent le même capital et les mêmes limites natives. L'overlay ne peut jamais augmenter une quantité approuvée. Le minimum de 50 $ est vérifié sur l'ordre total, pas sur deux ordres artificiels. **Cette règle fractionne les actions par position ; elle ne plafonne pas la partie de base à 50 % de l'équité globale.** Les arrondis, mouvements des cours et nouveaux achats de base peuvent conduire à une exposition différente. L'exposition totale réellement obtenue doit être rapportée ; ne pas interpréter le cas comme deux poches d'actifs rééquilibrées à parts strictement égales.

À ON, vendre uniquement la **partie pilotée encore détenue**. La base restante n'est pas à nouveau divisée par deux aux alertes suivantes ; son allocation initiale est conservée. Elle reste protégée par son SL et conserve son échéance d'origine. L'arrondi et les sorties SL/open11 déjà exécutées à cette ouverture sont rapprochés avant toute réduction.

Les réductions partielles utilisent le journal de recherche `RESEARCH_REDUCE`, le calcul natif de vente/PnL et le réarmement natif du stop sur la quantité restante. Elles ne sont pas marquées comme un EXIT terminal, ce qui empêcherait à tort la vente open11. Ce raccordement reste dans les scripts de recherche, sans modification du moteur de production.

## Ancienne sortie et reprise progressive

**Ancienne sortie** : protection pendant toute la durée de l'alerte de l'observateur ; retour normal après rendement virtuel vingt séances >5 % pendant cinq clôtures.

**Reprise progressive** :

1. PROTECTED : après ON, vol20/covariance soixante séances et régime SPY >98 % de sa SMA200 sur la partie pilotée. La partie de base conserve l'admission B normale.
2. PROBE : après **deux clôtures consécutives de rendement virtuel dix séances >0**, rétablir **la moitié du budget piloté normal**, sans filtre SPY ni budget vol20 sur cette fraction. Fixer le niveau du compte virtuel à cette clôture comme ancre de reprise.
3. NORMAL : après **cinq nouvelles clôtures consécutives** avec rendement virtuel dix séances >0 et compte virtuel au moins à l'ancre PROBE, rétablir tout le budget normal. Un échec de confirmation remet seulement ce compteur à zéro ; il ne provoque pas une nouvelle liquidation. Une nouvelle alerte ON de l'observateur remet PROTECTED et déclenche la liquidation prévue.

En variante totale, PROBE autorise environ 50 % de la quantité normale ; en variante partielle, environ 75 %. Les arrondis et le minimum natif peuvent réduire davantage les quantités. La reprise concerne les nouvelles entrées ; elle ne renforce pas les positions anciennes dont une partie a été vendue.

**Le budget vol20 porte sur la partie pilotée**, avec ses expositions et une allocation d'équité proportionnelle. La base conserve son risque propre : aucune garantie de volatilité globale 20 % ni de DD maximal n'est revendiquée. C'est un budget d'entrée, pas un rééquilibrage permanent des positions existantes.

## Plan de contrôle et comparaison

| Cas | Partie pilotée | Sortie |
| --- | ---: | --- |
| SL10 | Aucune protection | Témoin |
| FULL_OLD | 100 % | Ancienne |
| HALF_OLD | 50 % | Ancienne |
| FULL_PROGRESSIVE | 100 % | Progressive |
| HALF_PROGRESSIVE | 50 % | Progressive |

Les contrôles rejouent d'abord SL10 et FULL_OLD. Leurs transactions, courbes quotidiennes et courbes intraday doivent reproduire respectivement les archives du témoin et de `SL10_SHADOW`, à 1e−8 près, avant lancement des trois autres variantes. Des évolutions antérieures de scripts de recherche/serving sont listées dans le protocole ; elles ne sont pas ignorées sur la seule base d'une compatibilité supposée.

**12 tests ciblés passent**, dont absence de protection identique au natif, causalité par préfixe, maintien de la base quand le régime rejette, stop réarmé après réduction, priorité d'un stop déjà exécuté à la même ouverture et sortie open11 des actions restantes. Les ventes partielles fractionnent les lignes de trades : le tableau final doit afficher le **taux gagnant des campagnes entièrement clôturées**, après agrégation de leurs fragments, ainsi que les métriques natives de fragments séparément. Les compteurs de pertes/concentration natifs ne sont pas réécrits pour favoriser une variante.

Rapporter rendement, DD intraday et de clôture, capital engagé, frais, taux gagnant, résultats annuels, fréquence des liquidations et durée des phases. Comparer toute la période et la fenêtre fin 2024–mi-2025 ; aucune modification de seuil après lecture des résultats. Les années ont déjà été explorées : aucun nouveau holdout indépendant. Prix révisés, univers contemporain et intraday partiel/repli OHLC restent des limites ; les réserves prix et écarts de labels hérités sont conservés dans la revue finale.

## Suivi

Archives : `artifacts/research/us_b_protection_partial/20261118-v1`.

- `protocol.json`, `preflight.json` : protocole figé et empreintes.
- `progress.json` : phase et processus actifs ; pendant les contrôles, total=2, puis total=3 pour les nouvelles variantes.
- `cases/<cas>/progress.json` : séance courante sur 1 443 séances par replay.
- `inputs/*-states.parquet` : calendrier causal des phases.
- `cases/<cas>/result/liquidations.json`, `sizing-decisions.csv`, `protection-states.csv` : événements et allocations.
- À la fin : `comparison.csv`, `annual-comparison.csv`, `phases-by-year.csv`, `capital-comparison.png` et zoom `late2024-mid2025.png`.

Calculs et contrôles terminés le 19 novembre 2026. Résultats ci-dessous ; les dossiers interrompus avant correction technique ne sont pas utilisés.

## Amendement technique pendant l'exécution

Le calendrier supplémentaire demandé ensuite par l'utilisateur a mis en évidence un stop déjà exécuté à l'ouverture, alors que le journal de campagne n'était pas encore réconcilié. Le calcul partiel utilise désormais la quantité réellement restante du broker simulé. Douze tests ciblés passent, dont ce nouveau cas de priorité du stop ; les seuils, allocations et calendriers n'ont pas été modifiés. Les deux contrôles terminés sont conservés, la branche de liquidation totale étant inchangée. Les trois autres variantes ont été arrêtées, archivées dans `cases-before-open-stop-fix` et relancées. Voir `open-stop-fix-amendment.json` et le complément `doc/ml/b_anti_sl_protection_timing_20261118.md` pour l'essai séparé des nouvelles conditions.

## Résultats définitifs de cette comparaison exploratoire

Même compte continu de 4 000 $, 2021–1er octobre 2026, frais 8 points de base par côté et financement natif inclus. Le DD maximal du tableau est intraday, dans les limites de couverture du replay. Le taux gagnant agrège les sorties fractionnées d'une même campagne entièrement clôturée ; les positions encore ouvertes restent valorisées dans le capital.

| Cas | Capital final | Rendement | DD maximal | Campagnes clôturées | Taux gagnant | Exposition moyenne / équité |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B + anti-SL témoin | 16 140,82 $ | +303,52 % | −34,98 % | 1 356 | 38,13 % | 84,57 % |
| Liquidation totale, ancienne sortie | 7 667,96 $ | +91,70 % | −42,19 % | 1 198 | 36,48 % | 66,70 % |
| Partie pilotée 50 %, ancienne sortie | 7 006,97 $ | +75,17 % | −39,96 % | 1 527 | 36,74 % | 80,54 % |
| Liquidation totale, reprise progressive | 5 819,44 $ | +45,49 % | −36,43 % | 1 569 | 36,20 % | 76,86 % |
| Partie pilotée 50 %, reprise progressive | 7 217,88 $ | +80,45 % | −37,38 % | 1 582 | 36,60 % | 82,31 % |

**Aucune de ces quatre protections n'améliore le couple rendement/DD du témoin.** Les deux contrôles reproduisent exactement leurs archives : transactions, équité quotidienne et intraday, tolérance absolue 1e−8. Les variantes partagent quinze dates ON ; seule la fraction vendue et la règle de reprise changent.

La liquidation totale et reprise progressive réduit le DD par rapport à l'ancienne protection totale, mais reste moins bonne que l'absence de cette protection : +45,49 %/−36,43 %, contre +303,52 %/−34,98 %. On ne peut donc pas retenir ce cas comme amélioration en choisissant uniquement le bon comparateur.

La reprise progressive reste dans PROBE du 6 janvier au 27 octobre 2025 : son ancre ancienne ralentit le rétablissement du budget complet malgré des rebonds. Cette observation a motivé le cas secondaire local décrit dans le document complémentaire ; les quatre premières règles n'ont pas été ajustées après leur résultat.

## Contrôles, exposition effective et réserves

- Équité finale rapprochée avec PnL clôturé, valorisation des positions ouvertes, frais d'entrée restants, dividendes déclarés et financement ; erreur absolue <2e−10 $. Reçus des frais et intérêts rapprochés.
- Ventes déclenchées par ON vérifiées à l'ouverture officielle suivante, après les stops/open11 prioritaires ; quantités partielles rapprochées et absence de vente de la base conservée. Aucun ordre au-delà de l'approbation native.
- Reconstitutions des quantités BUY/SELL : pas de survente, positions finales identiques au bilan, vingt positions maximum respectées. Courbes identiques au témoin avant la première activation exécutable (signal du 10 août 2021).
- Exposition totale pendant PROTECTED : 42,45 % en liquidation totale/ancienne sortie, mais **74,62 %** en variante partielle/ancienne sortie et **76,85 %** en partielle/progressive. La division des actions par position ne limite pas le compte entier à 50 % ; les nouveaux achats de base peuvent réinvestir du capital.
- Couverture intraday incomplète, repli OHLC journalier, prix révisés et univers contemporain. Le contrôle de labels retrouve la même divergence connue BIDU, entrée 26 février 2021, dans chacun des cas ; aucun label/modèle n'est corrigé pour améliorer le résultat.
- L'écran complémentaire des détentions identifie ALNT et QTWO le 18 juin 2026 : volume daily nul malgré des échanges 5m en cache, ouvertures et extrêmes corroborés. Les caches de 68/77 bougies restent incomplets ; la clôture daily diffère de la dernière bougie. Réserve conservée, aucune substitution ni certification exhaustive des prix. Pas de détention sur les jours problématiques LBRDK/GWRE identifiés dans l'étude SHORT distincte.

Bilan principal : `final-status.json`, `comparison-reviewed.csv`, `accounting-review.csv`, `phase-transitions.csv` et `annual-comparison.csv` dans l'archive principale. Complément six cas : `artifacts/research/us_b_protection_timing_replay/20261118-v1/completion.json`, `comparison-all.csv`, `annual-comparison-all.csv`, `phase-exposure-all.csv`, `off-recovery-all.csv` et reçus du contrôle de volume.

![Comparaison des cinq cas initiaux](../../artifacts/research/us_b_protection_partial/20261118-v1/capital-comparison.png)

Décision : **ne pas ajouter ces protections au pipeline PAPER** sur la base de ces essais. Les années sont déjà explorées, aucun nouveau holdout indépendant. Aucun modèle, paramètre de production, batch, SQL ou compte broker modifié.
