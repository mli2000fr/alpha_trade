# Registre des expériences ML réalisées

## Objet et règle de lecture

Ce document est l'index central des expériences ML et des recherches directement
liées à la sélection Oracle, à l'amplitude, à la direction et à leur
monétisation. Il doit être complété après chaque nouvelle campagne, y compris
lorsque son résultat est négatif.

Les documents historiques décrivent le protocole et les résultats observés à
leur date. Le code source, les contrats d'artefacts et les prédictions OOF restent
les sources de vérité pour reproduire une expérience. Un `GO_RESEARCH` autorise
une étape de confirmation ; il n'autorise jamais automatiquement le serving.

### États employés

| État | Signification |
|---|---|
| `GO` | gates de l'étape franchis ; la portée exacte est précisée |
| `GO_RESEARCH` | signal à confirmer, non déployable |
| `WEAK_SIGNAL` | information faible ou instable, sans promotion |
| `NO_GO` | hypothèse rejetée dans le contrat testé |
| `INCONCLUSIVE` | données, couverture ou période insuffisantes |
| `IN_PROGRESS` | campagne en cours, aucune conclusion définitive |
| `PROPOSED` | protocole préparé mais non exécuté |
| `STANDBY_ABONNEMENT` | protocole prêt, suspendu jusqu'à disponibilité du forfait requis |
| `ABANDON_COÛT` | source ou expérience volontairement arrêtée car l'accès requis est payant |
| `BLOCKED_NO_PIT_HISTORY` | hypothèse non rejetée, mais aucune source historique PIT suffisante |

## Résumé décisionnel actuel

1. **Oracle Extreme détecte réellement l'amplitude** : E6-A passe ses six
   gates OOF avec une relation monotone entre score et excursion future.
2. **La direction reste non résolue** : les formulations statiques,
   per-symbol, mutualisées, pairwise, path-aware, first-touch, régime et
   screener n'ont pas produit un avantage LONG/SHORT stable.
3. **Le long straddle est rejeté, y compris avec DTE adapté à l'horizon** :
   E6-B2 reste négatif à H3/H5/H10/H20. Les moyennes vont de `-14,39 %` à
   `-29,68 %`, les médianes sont toutes négatives et seulement 0 à 2 dates sur
   8 sont positives selon l'horizon.
4. **Aucune famille Eroya testée n'est promue**. Quelques effets descriptifs
   existent, mais pas de gain directionnel Walk-Forward suffisamment stable.
5. **La surface Options directionnelle 45 DTE est rejetée** : aucune feature ne
   passe les gates préfixés. Les deux effets descriptifs H10/H20 sont instables
   et défavorables au SHORT ; le volume historique est non testable.
6. **Temporal D1/D10 V2 est fermé en `NO_GO_DATASET_A`** : sur 399 symboles,
   T0 Logistic reste meilleur à 0,5143 d'AUC same-date. Le meilleur T2
   logistique tombe à 0,5112 ; le plus grand delta T2 est +0,0066 mais avec une
   AUC absolue de 0,4961 et des buckets inversés. Dataset B/C n'est pas ouvert.
7. **E9 ferme la confirmation directionnelle post-signal** : attendre le close
   J+1/J+2/J+3/J+5 puis entrer à l'open suivant ne révèle pas le sens restant.
   La politique primaire D2 atteint 49,40 % de précision et -0,309 % net par
   date ; les groupes désignés SHORT continuent en réalité de monter.
8. **E10 rejette l'interprétation pullback LONG** : l'avantage découvert dans
   E9 ne se confirme pas du 10 juillet 2024 au 11 juillet 2025. Le delta
   quotidien contre Oracle LONG au même open vaut -0,056 point, IC95
   [-0,603 ; +0,436], avec 1/2 folds et 1/3 semestres favorables.

## Campagnes directionnelles récentes après Oracle

| ID | Expérience | Population/cible | Résultat essentiel | État | Documentation |
|---|---|---|---|---|---|
| D0 | Bundle Oracle + deux modèles Per-Symbol | Oracle Extreme puis branches ternaires LONG et SHORT par ticker | Architecture entraînement/prédiction/backtest rendue cohérente, mais la direction per-symbol conditionnelle n'a pas généralisé à 2026H1 | `NO_GO` ML pour le batch étudié ; capacité technique conservée | [Bundle Oracle + Per-Symbol](per_symbol/07_bundle_oracle_long_short.md) |
| D1 | Classifieur mutualisé D1/D10 | D1 contre D10 dans Oracle TOP20 OOF | Sans contexte : AUC 0,503 et IC quotidien +0,004 ; contexte symbole/secteur dégrade | `NO_GO` | [Modèle mutualisé](shared_directional_oracle_events.md#campagne-initiale-du-5-septembre-2026) |
| D1-P | Ranker pairwise D1/D10 | PairLogit groupé par date | AUC 0,500, IC +0,006 ; faible purification instable | `NO_GO` | [Objectif pairwise](shared_directional_oracle_events.md#objectif-pairwise) |
| E1 | Rendement signé continu multi-horizons | Rendements H3/H5/H10/H20 dans Oracle TOP20 OOF | IC proche de zéro, signe correct inférieur à 50 %, branche SHORT négative | `NO_GO` | [E1](shared_directional_oracle_events.md#e1--rendement-signé-continu-multi-horizons) |
| E2 | Deux probabilités indépendantes | `P(Hx >= +3%)` et `P(Hx <= -3%)` | SHORT rejeté partout ; petit signal LONG H3, AUC moyenne 0,544 et 9/9 folds > 0,50, mais probabilités mal calibrées | `GO_RESEARCH` LONG H3 uniquement | [E2](shared_directional_oracle_events.md#e2--deux-probabilités-directionnelles-indépendantes) |
| E2-B | Calibration imbriquée et confirmation LONG H3 | Platt sur validation de chaque fold, test OOF puis confirmation 2026H1 | Confirmation AUC 0,536 mais aucun lift top10 suffisant ; gates de confirmation et développement non franchis | `NO_GO` | [E2-B](shared_directional_oracle_events.md#e2-b--confirmation-long-h3-avec-calibration-imbriquée) |
| E3-A | Rentabilité path-aware binaire | Replay LONG et SHORT séparé, stop 2,5 ATR, TP 3 ATR/7 %, H20 | LONG AUC moyenne 0,541 mais lift économique -0,064 point ; SHORT AUC 0,508 et top10 -0,624 % | `NO_GO` | [E3](shared_directional_oracle_events.md#e3--deux-têtes-de-rentabilité-conditionnelles-au-chemin) |
| E3-A2 | Utilité économique path-aware | Rendement net prédit moins pénalité de perte extrême | IC fold LONG +0,009, SHORT -0,010 ; aucun côté ne passe les gates | `NO_GO` | [E3-A2](path_aware_economic_utility.md) |
| E3-R | Veto de risque path-aware | Rejeter les événements au risque extrême prévu | Réduit certains risques mais conflit avec la sélection de tête ; stabilité insuffisante | `NO_GO` production | [E3-R](path_risk_veto.md) |
| E3-D | Direction par asymétrie du tail-risk | Comparaison du risque prévu LONG contre SHORT | Décision correcte 49,9 %, lift négatif, aucun avantage au meilleur côté statique | `NO_GO` définitif pour cette formulation | [E3-D](path_risk_direction.md) |
| E4 | Première barrière symétrique touchée, quatre classes | `UP_FIRST`, `DOWN_FIRST`, `AMBIGUOUS`, `NO_TOUCH` | Surabstention et absence d'avantage directionnel stable | `NO_GO` | [E4](first_touch_directional.md) |
| E4-B | Première barrière, contrôle binaire | `UP_FIRST` contre `DOWN_FIRST`, cas ambigus retirés | AUC fold 0,501 ; couverture 4,10 %, précision 41,09 %, rendement -2,36 % | `NO_GO` | [E4-B](first_touch_binary.md) |
| E5 | Direction quotidienne du régime Oracle | Choisir un côté commun pour tout le panier du jour | Ridge Spearman 0,000 ; CatBoost -0,008 ; aucune stabilité exploitable | `NO_GO` | [E5](oracle_daily_regime_direction.md) |
| R1 | Ranker conditionnel au TOP20 Oracle | Ranking de rendement réel uniquement dans le pool Oracle | Retest batch corrigé : H3 IC +0,0148/spread +0,12 % ; H20 IC +0,0260/spread +0,67 %, mais stabilité insuffisante et LONG/SHORT `NO_GO` | `NO_GO` confirmé | [Ranker conditionnel](conditional_oracle_ranker.md) |
| C1 | Consensus des modèles OOF existants | Moyenne équipondérée de rangs quotidiens, 2 à 7 familles selon H3/H5/H10/H20, sans réentraînement ni optimisation | IC -0,0014 à +0,0118, inférieur au meilleur composant ; SHORT signé négatif partout ; unanimité et régime E5 ne sauvent pas la direction | `NO_GO` | [Audit de consensus OOF](oof_consensus_audit.md) |
| E9-A | Confirmation directionnelle après Oracle | Observer le prix à J+1/J+2/J+3/J+5, puis entrer LONG/SHORT au prochain open ; seuils choisis sur folds antérieurs | Primaire D2 : 49,40 % de précision, -0,309 % net quotidien, 1/12 folds positifs ; les signaux SHORT montent encore de +1,8 % à +3,2 % | `NO_GO`; E9-B fermé | [E9](oracle_post_signal_confirmation.md) |
| E10 | Pullback LONG après Oracle | Seuil choisi sur E9 puis gelé à -0,25 % ; confirmation Oracle H20 OOF du 2024-07-10 au 2025-07-11, entrée LONG open J+2 | +0,732 % net quotidien mais benchmark +0,788 % ; delta -0,056 point, IC95 [-0,603 ; +0,436], 1/2 folds positifs | `NO_GO`; E10-B fermé | [E10](oracle_pullback_long.md) |
| T-V2-A | Temporal D1/D10 V2 — Dataset A | État J contre trajectoires `[J-N,...,J]`, N=3/5/10, Logistic/CatBoost/PairLogit, labels H20 autoritatifs | 21 variantes, 399 symboles ; T0 Logistic 0,5143, meilleur T2 Logistic 0,5112 ; aucun gain T2 >= +0,01, aucun candidat servable | `NO_GO_DATASET_A` final | [Temporal D1/D10 V2](temporal_d1d10_v2.md) |
| S1 | Règles screener PIT post-Oracle | Signaux screener LONG/SHORT H3/H10/H20 | Couverture fraîche 10,44 %, meilleurs effets instables ; aucun gate LONG/SHORT | `NO_GO_PREDICTIVE` | [Screener post-Oracle](screener_post_oracle.md) |
| S1-D | Recontrôle screener sur panel dense | Six signaux quotidiens recalculés sur tout le pool | Couverture réparée mais verdict prédictif inchangé | `NO_GO_PREDICTIVE` | [Panel dense](panel_screener_dense.md), [résultat](screener_post_oracle.md#source-dense-recommandée) |

## Campagnes directionnelles antérieures retrouvées dans les archives ML

Ces campagnes précèdent la série E1–E6. Elles sont importantes car plusieurs
hypothèses récentes en sont des reformulations. Elles ne doivent pas être
relancées sans information nouvelle.

| ID historique | Expérience | Résultat essentiel | État | Documentation |
|---|---|---|---|---|
| GD-H20-V1 | GlobalDirection binaire D1/D10 | Modèle partagé avec features directionnelles minimales ; purification non monotone, seulement 2/3 folds favorables | `NO_GO` | [GlobalDirection H20](../experiences/archives_recherche/global_direction_h20.md#v1-binaire-seul-2026-08-26-premier-run) |
| GD-H20-C1/C2/C3 | Cibles binaire, ordinale et rank | D1 parfois réduit mais D10 non monotone ; rendement inférieur aux baselines | `NO_GO` intermédiaire | [Comparaison C1/C2/C3](../experiences/archives_recherche/global_direction_h20.md#c1-binaire--c2-ordinal--c3-rank-2026-08-26) |
| GD-H20-C4 | Ajout des features sectorielles | Échec des cinq critères pré-enregistrés contre B1 ; BAD5 augmente et GOOD5 diminue | `NO_GO` final | [Test sectoriel](../experiences/archives_recherche/global_direction_h20.md#étude-de-séparabilité-étapes-7-8--2026-08-26) |
| GD-SEP | Séparabilité univariée des features existantes | IC maximum 0,033, AUC direction maximum 0,515 ; les meilleures features expliquent davantage l'amplitude | `NO_GO` | [Séparabilité GlobalDirection](../experiences/archives_recherche/global_direction_h20.md#étude-de-séparabilité-étapes-7-8--2026-08-26) |
| GD-T0 | Audit de couverture temporelle | Historique `stock_scores_history` initialement trop discontinu pour les trajectoires | `INCONCLUSIVE_COVERAGE` initial | [Audit temporel](../experiences/archives_recherche/global_direction_temporal.md#audit-de-couverture-stock_scores_history-2026-08-26--insuffisant) |
| GD-T1 | Backfill PIT puis dérivées J-3/J-5/J-10 | 252 résultats : 0 GO, 108 NO-GO et 144 couvertures insuffisantes ; meilleure AUC environ 0,51 | `NO_GO` | [GlobalDirectionTemporal](../experiences/archives_recherche/global_direction_temporal.md#construire-la-couverture-via-le-backfill-pit-2026-08-27--résultat-inchangé) |
| DDR-1 | Estimates et révisions fondamentales | Données de consensus historiques absentes ; proxies trailing sans signal | `NON_TESTABLE` / `NO_GO` proxies | [DirectionalDataResearch — famille 1](../experiences/archives_recherche/directional_data_research.md#famille-1--estimateearnings-revisions-2026-08-26) |
| DDR-2 | Sentiment news événementiel | IC maximal absolu 0,028, AUC autour de 0,49–0,50 | `NO_GO` | [DirectionalDataResearch — famille 2](../experiences/archives_recherche/directional_data_research.md#famille-2--news-sentiment-événementiel-2026-08-26) |
| DDR-3 | Short interest et short volume historiques | Huit features, AUC maximum 0,501 et IC maximal absolu 0,044 | `NO_GO` | [DirectionalDataResearch — famille 3](../experiences/archives_recherche/directional_data_research.md#famille-3--short-interest--short-volume-2026-08-26) |
| DDR-4 | Options skew et insiders, premier audit | Options absentes de la base historique à cette date ; insiders non exploitables proprement | `NON_TESTABLE` historique | [DirectionalDataResearch — famille 4](../experiences/archives_recherche/directional_data_research.md#famille-4--options-skew--insiders-2026-08-26) |
| DDR-5 | Surprise earnings et distance aux résultats | `earn_surprise_eps_prev` AUC 0,519 et IC +0,034 stable, mais lift de tête nul et AUC sous le gate | `WEAK_SIGNAL`, non promu | [DirectionalDataResearch — famille 5](../experiences/archives_recherche/directional_data_research.md#famille-5--analyst-surprise-earnings--days-to-earnings-2026-08-27) |

Attention : l'ancien indicateur `dir_vs_amp` de
`modelFactory/global_direction/temporal.py` possède une définition amplitude
incorrecte. Les AUC directionnelles des campagnes GD-T restent utilisables, mais
leur comparaison direction/amplitude doit être recalculée avant réutilisation.

## E6 — amplitude Oracle et monétisation direction-neutral

| ID | Expérience | Résultat essentiel | État | Documentation |
|---|---|---|---|---|
| E6-A | Audit OOF de l'amplitude Oracle | 600 717 observations ; TOP20/REST80 environ +86 % d'excursion relative ; Spearman quotidien 0,551 à 0,570 ; 6/6 gates | `GO` amplitude, pas direction | [Audit amplitude](oracle_amplitude_audit.md) |
| E6-B0 | Faisabilité historique des options | Snapshot local insuffisant ; REST historique utilisable, flat files bulk non autorisés dans le trial | `GO` pilote REST ciblé, `NO_GO` bulk actuel | [Faisabilité options](oracle_options_feasibility.md) |
| E6-B1 | Long straddle ATM fixe ~45 DTE | 588 événements, entrée NBBO 67,52 % ; rendement ask→bid négatif à H3/H5/H10/H20, jusqu'à -29,68 % à H20 | `NO_GO` pour 45 DTE fixe | [Résultat E6-B1](oracle_options_feasibility.md#résultat-e6-b1--straddle-45-dte) |
| E6-B2 | DTE adapté à chaque horizon | 588 événements sur 8 dates. Couverture H3/H5/H10/H20 : 43,71/42,35/23,13/41,33 %. Rendement net moyen : -15,76/-14,39/-22,33/-29,68 % ; médiane : -17,49/-19,31/-25,21/-33,22 % ; dates positives : 1/8, 2/8, 0/8, 0/8 | `NO_GO` ; adapter le DTE ne répare pas le straddle long | [Résultat E6-B2](oracle_options_feasibility.md#résultat-e6-b2--dte-adapté-à-lhorizon) |
| E6-B3 | Confirmation options indépendante | Était conditionnée au franchissement des gates E6-B2, qui ont échoué | `NO_GO` pour l'escalade du straddle long ; non exécutée | [Décision E6-B2](oracle_options_feasibility.md#verdict-e6-b2) |

## Nouvelles données directionnelles — campagnes Eroya et autres sources

Toutes ces expériences utilisent ou visent la population Oracle TOP20 OOF. Les
effets exploratoires ne sont pas des règles de production.

| Famille | Données testées | Conclusion actuelle | État | Documentation |
|---|---|---|---|---|
| Short volume | ratio quotidien, variations et niveaux disponibles | Pas de signal directionnel stable H3/H10/H20 | `NO_GO` | [POC Eroya — Short volume](eroya_directional_poc.md#short-volume) |
| Short interest | niveaux et observations PIT disponibles | Fréquence/couverture insuffisante et absence de lift robuste | `NO_GO` | [POC Eroya — Short interest](eroya_directional_poc.md#short-interest) |
| Analyst Insights | scores et observations analystes | Quelques candidats descriptifs, aucune confirmation intacte | `INCONCLUSIVE` | [Analyst Insights](eroya_directional_poc.md#analyst-insights) |
| Analyst revisions Yahoo | révisions et objectifs | Aucun signal durable dans le harnais historique | `NO_GO` | [Synthèse historique des données directionnelles](../experiences/archives_recherche/directional_data_research.md) |
| Form 4 / insiders | transactions d'initiés avec date de dépôt PIT | Effets LONG descriptifs non stables ; ablation modèle ne passe pas les gates | `NO_GO` | [Form 4](eroya_directional_poc.md#résultats-form-4-pit) |
| News/sentiment multi-source | sentiment et événements Eroya comparés aux données internes | Contenu partiellement nouveau mais aucune preuve historique directionnelle | `NO_GO` historique ; collecte prospective possible | [News Eroya](eroya_directional_poc.md#news-multi-source-eroya-versus-sentiment-existant) |
| Earnings/surprise EPS | résultats trimestriels, surprise brute, distance earnings | Surprise brute rejetée comme signal autonome | `NO_GO` | [Earnings](eroya_directional_poc.md#résultats-trimestriels-et-surprises-eps) |
| Dépôts 8-K | catégories structurées et compteurs événementiels | Information descriptive, mais répétitions et concentration interdisent une règle | `INCONCLUSIVE`, non promu | [8-K](eroya_directional_poc.md#dépôts-8-k-structurés) |
| Options directionnelles | prix, skew, profondeur et volume put/call sur surface 45 DTE | 625 événements/8 dates, 323 surfaces complètes. Mapping volume `v` corrigé : 129 surfaces quatre jambes, 119 avec cible. H3 AUC 0,619/IC 0,032 mais stabilité 1/4 années et LONG brut perdant ; H10/H20 incohérents | `NO_GO`, volume désormais testé | [Protocole et résultat E7](options_directional_poc.md#volume--mapping-eroya-corrigé-et-réévaluation-complète) |
| Quotes de clôture IEX | dernière quote quotidienne, spread, imbalance, microprice, profondeur et âge de quote | Couverture 88,8 %, mais aucun signal directionnel stable sur H3/H5/H10/H20 ; le niveau de profondeur H20 est un confondant de liquidité | `NO_GO` pour le snapshot quotidien | [Microstructure de clôture](closing_quote_microstructure.md) |
| Intraday 5 minutes de séance complète | barres Eroya ajustées, segmentation matin/après-midi, VWAP, volume et volatilité | 393 dates, 330 séances exploitables. Direction rejetée ; volatilité amplitude AUC 0,56/IC 0,18/6 sur 8 semestres, mais p Bonferroni 0,30. Aucun profil promu | `FAIT_NO_GO` | [Trajectoire de séance](intraday_session_path_pilot.md) |
| Trades/quotes séquentiels riches | NBBO/SIP, flux signé, trajectoire prix et liquidité | Collecte Eroya validée puis hypothèses rejetées : signed-flow simple/accéléré `NO_GO`; épuisement prix 5 min non répliqué sur 400 dates disjointes (AUC 0,490) | `FAIT_NO_GO` | [Flux signé](signed_trade_flow_pilot.md), [prix/liquidité tick](tick_price_liquidity_audit.md) |
| Déséquilibres d'enchère MOC/LOC | messages historiques d'auction imbalance disponibles avant la clôture | Aucun endpoint ou dataset correspondant dans le catalogue officiel Eroya au 8 septembre 2026 ; trades/NBBO ne remplacent pas ce flux | `BLOCKED_NO_DATA_SOURCE` | [Prix/liquidité tick](tick_price_liquidity_audit.md) |
| Chaîne Options OPRA complète | minute aggregates de tous les contrats ; idéalement trades+quotes signés | Plan Pro autorise `us-options-minute-aggs`; ticks OPRA exigent Premium. REST quatre jambes trop clairsemé. `flatfiles/list` a répondu 502 deux fois, donc aucun téléchargement | `STANDBY_ARCHIVE_SERVICE` | [Options E7 — chaîne complète](options_directional_poc.md#piste-suivante--chaîne-opra-complète) |
| Contexte intraday marché | trajectoires SPY/QQQ/IWM et VXX sur séance J | 364 événements alignés/305 tails. Meilleur directionnel IWM-SPY AUC 0,52 ; meilleurs amplitude SPY vol/VXX abs AUC 0,53. Toutes p Bonferroni=1, aucun gate complet | `FAIT_NO_GO` | [Contexte intraday marché](intraday_market_context_pilot.md) |
| Borrow fee / utilization / shares available | statut Alpaca actuel et disponibilité des sources historiques | Aucun historique PIT pluriannuel local ou Eroya ; FINRA SLATE repoussé à septembre 2028. La compatibilité live Alpaca `borrow_status` a été sécurisée | `BLOCKED_NO_PIT_HISTORY` | [Audit de faisabilité borrow](borrow_lending_data_feasibility.md) |
| 13F | positions institutionnelles trimestrielles retardées | Non testé, priorité faible pour H3/H10/H20 | `PROPOSED` faible priorité | [Limites options et ticks](eroya_directional_poc.md#options-tradesquotes-et-13f) |

## Expériences historiques Per-Symbol

| Campagne | Axes testés | Verdict durable | Documentation |
|---|---|---|---|
| S7 — whitelist de features | Réduction contrôlée des features per-symbol, comparaison architecture/champion | Mécanisme conservé, gain OOS rejeté | [S7 Feature whitelist](../experiences/archives_ml/synthese_s7_feature_whitelist_2026-08-18.md) |
| Per-Symbol Directional V2 F0/F1/F2/F3a/F3b | Familles directionnelles, architectures LSTM/LightGBM/CatBoost, champion et stabilité | Aucun gain OOS stable ; `NO_GO` | [Synthèse Per-Symbol V2](../experiences/archives_ml/synthese_per_symbol_v2_2026-08-19.md) |
| Sélection des tickers par F1 LONG/SHORT | Gates par côté, folds valides, listes STRICT et DISCOVERY | Outil de screening disponible ; ne prouve pas la performance portefeuille | [Sélection des candidats](per_symbol/06_selection_candidats_directionnels.md) |
| Entraînement conditionnel aux événements Oracle | Branches LONG/SHORT entraînées dans le bundle sur les événements Oracle | Technique fonctionnelle ; généralisation directionnelle rejetée sur le batch étudié | [Population conditionnelle](per_symbol/07_bundle_oracle_long_short.md#population-dentraînement-conditionnelle--étape-3) |

## Persistance, confirmation prix et filtre DIP

Ces expériences concernent principalement Global Ranking. Elles ne doivent pas
être attribuées à Oracle Extreme par erreur.

| Expérience | Population et résultat | Verdict actuel | Documentation |
|---|---|---|---|
| Persistance + confirmation prix après Oracle TOP10 | Taux GOOD resté pratiquement plat autour de 50,2–50,3 % | `NO_GO` pour Oracle | [Persistent tail price](../experiences/archives_recherche/persistent_tail_price.md#oracle-top10--hypothèse-non-soutenue) |
| Persistance Global Rank TOP10 + hausse | GOOD rate 0,521 → environ 0,556 sur un échantillon viable | Signal historique soutenu, distinct d'Oracle | [Persistent tail price — LONG](../experiences/archives_recherche/persistent_tail_price.md#global-rank-top10-long--hypothèse-soutenue) |
| Persistance Global Rank BOTTOM10 + baisse | GOOD SHORT environ 0,512 → 0,529 | `WEAK_SIGNAL` SHORT | [Persistent tail price — SHORT](../experiences/archives_recherche/persistent_tail_price.md#global-rank-bottom10-short--faible-gain) |
| TOP10 persistant + baisse récente | Rebond observé avec GOOD rate autour de 0,567 | Découverte exploratoire, non assimilable à une direction Oracle | [Inversion TOP10](../experiences/archives_recherche/persistent_tail_price.md#inversion-top10--baisse--signal-le-plus-fort) |
| DIP N4/X2 Global Rank | Filtre DIP puis veto de régime ; +5,5 % en 2025 OOS et +4,3 % en 2026H1 contre baselines négatives | `GO` historique dans son contrat Global Rank ; paramètres gelés | [Persistent TOP10 DIP](../experiences/archives_recherche/persistent_top10_dip.md#phase-3--audit-de-parité-reclaim-validation-oos-et-implémentation-2026-08-27) |
| DIP reclaim R50/R100 | Attendre la reprise consomme le rebond et dégrade D0 | `NO_GO`, garder entrée directe | [Reclaim](../experiences/archives_recherche/persistent_top10_dip.md#32-reclaim-r50r100--no-go) |
| Tiebreaker `dip_quality` | Amélioration mécanique et métriques favorables, mais seulement 18 substitutions OOS | `INCONCLUSIVE_LOW_SAMPLE` | [Tiebreaker DIP](../experiences/archives_recherche/Tiebreaker.md) |
| Smart sector cap | Cap exposition 20 % et hybride count/exposition/corrélation retirent ou ajoutent de mauvais ensembles de trades | C0 count=2 conservé ; C1/C2 `NO_GO` | [Smart sector cap](../experiences/archives_recherche/smart_sector_cap_verdict_2026-08-27.md) |

## Calibration et transformation des scores Oracle

| Expérience | Résultat | Statut | Documentation |
|---|---|---|---|
| Percentile quotidien `rank` | Transformation déterministe, sans cible ni fit ; préserve l'ordre relatif | Contrat adapté au gate percentile | [Calibration Oracle](../experiences/archives_recherche/calibration_oracle_exterme.md#rank--percentile-intra-jour-relatif) |
| Calibration isotonic | Mapping score → fréquence d'extrême ; améliore la sémantique probabiliste mais pas l'AUC ou le classement | Non utilisable en backtest strict sans artefact calibré PIT gelé | [Isotonic](../experiences/archives_recherche/calibration_oracle_exterme.md#isotonic--proba-calibrée-absolue-pav), [contrat actuel](oracle/04_train_walk_forward_et_calibration.md#calibrationcombinaison) |
| Oracle brut `none` | Score OOS brut utilisé lorsque le consommateur reclasse quotidiennement et qu'aucun calibrateur PIT antérieur n'est disponible | Contrat actuel du backtest strict | [Entraînement/calibration Oracle](oracle/04_train_walk_forward_et_calibration.md#calibrationcombinaison) |

## Oracle Extreme — campagnes de construction et d'ablation

| Campagne | Axes testés | Conclusion conservée | Documentation |
|---|---|---|---|
| Oracle historique TOP/BOTTOM | Deux modèles directionnels au-dessus du ranking | Les deux côtés apprenaient surtout une magnitude commune ; architecture remplacée | [Synthèse Oracle](../experiences/oracle_extreme.md) |
| Oracle O0 binaire | `D1 ∪ D10` contre le milieu, sans Global Rank comme entrée | Contrat actuel : magnitude uniquement, gate percentile quotidien | [Concept Oracle](oracle/01_concept_et_architecture.md) |
| Diagnostics hard negatives/confounders | Faux positifs, sévérité, features, fondamentaux, cas catastrophiques | Diagnostics utiles, pas de gate live automatiquement validé | [Diagnostics Oracle](oracle/06_diagnostics_et_historique.md) |
| Ablations Oracle 01–11 | Ranks XS, raw simple, momentum, tendance, volatilité, volume, RSI, régime, transformations et z-scores | Comparaison corrigée terminée : l'AUC seule donne un classement trompeur ; le meilleur gain d'amplitude TOP20 est seulement +0,0215 point/jour apparié | `config/features/oracle/` et [comparaison corrigée](oracle_ablation_corrected_comparison.md) |
| Combinaisons Oracle 12–14 | Retraits combinés marché/régime, engineered transforms et momentum | Aucun profil promu ; corrélations 0,974–0,980 avec la baseline et seulement ~3 % de décisions TOP20 modifiées, donc aucun ensemble justifié | [Comparaison corrigée](oracle_ablation_corrected_comparison.md) |

## Global Ranking et Per-Sector — historique B0 à B44

Les campagnes B0–B44 ont testé les familles de features, backends, objectifs de
ranking, profondeur historique, taille d'univers et volume. Le dossier suivant
contient les rapports détaillés batch par batch :
[campagnes Global Ranking](../experiences/campagnes_global_ranking/README.md).

| Série | Variantes documentées | Documentation |
|---|---|---|
| B0–B3 | baseline, sentiment, scores screener, short score | [B0](<../experiences/campagnes_global_ranking/test/B0 Baseline.md>), [B1](<../experiences/campagnes_global_ranking/test/B1 sentiement.md>), [B2](<../experiences/campagnes_global_ranking/test/B2 scores screnner.md>), [B3](<../experiences/campagnes_global_ranking/test/B3 scores short.md>) |
| B4–B14 | SPY, VIX/VXN/VIX3M/MOVE, fondamentaux, CAPM, macro, historique de scores, secteur et stacking | [B4](<../experiences/campagnes_global_ranking/test/B4 Short + SPY.md>), [B5](<../experiences/campagnes_global_ranking/test/B5 Short + SPY + Vix.md>), [B6](<../experiences/campagnes_global_ranking/test/B6 Short + SPY + Vxn.md>), [B7](<../experiences/campagnes_global_ranking/test/B7 Short + SPY + Vix3m.md>), [B8](<../experiences/campagnes_global_ranking/test/B8 Short + SPY + Move.md>), [B9](<../experiences/campagnes_global_ranking/test/B9 Short + SPY + Fondamentaux.md>), [B10](<../experiences/campagnes_global_ranking/test/B10 Short + SPY + CAPM.md>), [B11](<../experiences/campagnes_global_ranking/test/B11 Short + SPY + Macro.md>), [B12](<../experiences/campagnes_global_ranking/test/B12 Short + SPY + Score histo.md>), [B13](<../experiences/campagnes_global_ranking/test/B13 Short + SPY + sectoriel.md>), [B14](<../experiences/campagnes_global_ranking/test/B14 Short + SPY + stacking.md>) |
| B15–B19 | transformations T1/T2/T3 et profondeur/folds | [B15](<../experiences/campagnes_global_ranking/test/B15 Short + SPY + T1.md>), [B16](<../experiences/campagnes_global_ranking/test/B16 Short + SPY + T2.md>), [B17](<../experiences/campagnes_global_ranking/test/B17 Short + SPY + T3.md>), [B18](<../experiences/campagnes_global_ranking/test/B18 Short + SPY + from 2011 + max 8 slits.md>), [B19](<../experiences/campagnes_global_ranking/test/B19 Short + SPY + from 2011 + max 16 slits.md>) |
| B20–B27 | YetiRank, QueryRMSE, QuerySoftMax, puis variantes CAPM | [B20](<../experiences/campagnes_global_ranking/test/B20 Short + SPY + YetiRank.md>), [B21](<../experiences/campagnes_global_ranking/test/B21 Short + SPY + QueryRMSE.md>), [B22](<../experiences/campagnes_global_ranking/test/B22 Short + SPY + QuerySoftMax.md>), [B25](<../experiences/campagnes_global_ranking/test/B25 Short + SPY + CAPM + YetiRank.md>), [B26](<../experiences/campagnes_global_ranking/test/B26 Short + SPY + CAPM + QueryRMSE.md>), [B27](<../experiences/campagnes_global_ranking/test/B27 Short + SPY + CAPM + QuerySoftMax.md>) |
| B30–B34 | P1–P3, fondamentaux, historique scores, secteur, screener avec YetiRank | [B30](<../experiences/campagnes_global_ranking/test/B30 Short + SPY + YetiRank +  P1-3.md>), [B31](<../experiences/campagnes_global_ranking/test/B31 Short + SPY + Fondamentaux + YetiRank.md>), [B32](<../experiences/campagnes_global_ranking/test/B32 Short + SPY + Score histo + YetiRank.md>), [B33](<../experiences/campagnes_global_ranking/test/B33 Short + SPY + sectoriel + YetiRank.md>), [B34](<../experiences/campagnes_global_ranking/test/B34 scores screnner + YetiRank.md>) |
| B35–B39 | univers 196/300/393 et challenger XGBoost rank | [B35](<../experiences/campagnes_global_ranking/test/B35 B25 + symbols 196.md>), [B36](<../experiences/campagnes_global_ranking/test/B36 B20 + symbols 196.md>), [B37](<../experiences/campagnes_global_ranking/test/B37 B25 + symbols 393.md>), [B38](<../experiences/campagnes_global_ranking/test/B38 B25 avec 300 symblos (parmi les 400).md>), [B39](<../experiences/campagnes_global_ranking/test/B39-B25-XGBoost-rank-ndcg-P3-3.md>) |
| B40–B44 | volume features, configurations B4/B20/B25 et extension train 2024 | [B40](<../experiences/campagnes_global_ranking/test/B40-B4-volume-features-P3-5.md>), [B41](<../experiences/campagnes_global_ranking/test/B41-B25-volume-features-P3-5.md>), [B42](<../experiences/campagnes_global_ranking/test/B42-B20-volume-features-P3-5.md>), [B44](<../experiences/campagnes_global_ranking/test/B44-B41-config-global-only-train-end-2024-12-31.md>) |
| Synthèse Global/Per-Sector | comparaison de tous les horizons, champions, splits, régimes et backtests | [Rapport comparatif](<../experiences/campagnes_global_ranking/test/test_global_per_sector.md>), [synthèse durable](../experiences/global_ranking_et_per_sector.md) |

## Expériences risque, exécution et lifecycle liées à l'interprétation ML

Ces campagnes ne cherchent pas directement D1/D10, mais elles déterminent si un
signal ML observé peut être monétisé sans biais d'exécution.

| Campagne | Conclusion | Documentation |
|---|---|---|
| Audit du backtest historique | Biais pullback et propagation TP découverts puis corrigés ; nécessité de la parité production | [Audit backtest](../experiences/archives_recherche/backtest_audit.md) |
| TP / risk-execution | Plusieurs TP testés ; amélioration locale non confirmée OOS | [Synthèse TP/risk](../experiences/archives_ml/synthese_tp_risk_execution_2026-08-18.md) |
| Time-stop/parité | Différence entre lifecycle de recherche et production mise en évidence | [Synthèse risque/lifecycle](../experiences/risque_execution_lifecycle.md) |
| Drawdown controller B4 | Contrôleur et gates paper validés dans son contrat historique | [B4 paper](../experiences/archives_recherche/c2_b4_breaker_go_paper_2026-08-21.md) |
| Force-close catastrophe | `CLOSE_ALL` et `CLOSE_LONGS` à -8 % rejetés | [E44](../experiences/archives_recherche/b4_force_close_side_attribution.md) |
| Validation/recalibration | Séparation entraînement, calibration, promotion et OOS | [Synthèse validation](../experiences/validation_et_recalibration.md) |

## Pistes préparées mais non encore exécutées

| Priorité actuelle | Piste | Question | Statut | Protocole |
|---:|---|---|---|---|
| 1 | Flux signé trades/NBBO Eroya proche de la clôture | L'agression bid/ask et le déséquilibre NBBO ajoutent-ils une direction dans Oracle TOP20 ? | `FAIT_NO_GO` : agrégat 5 min instable ; accélération 30 min AUC 0,567 et 5/7 semestres, mais p=0,149 et p Bonferroni=1. Aucun modèle autorisé | [Flux signé trades/NBBO](signed_trade_flow_pilot.md) |
| 2 | Modèle temporel multi-horizon | Un apprentissage commun H3/H5/H10/H20 régularise-t-il la direction ? | `PROPOSED`, conditionnel à V2 | À formaliser |
| 3 | Portefeuille relatif | Un spread dollar-neutral peut-il monétiser un faible ranking sans direction absolue ? | `FAIT_NO_GO` : H3 net quasi nul ; H20 +0,304 % net par cohorte mais seulement 4/9 folds positifs, queue SHORT encore haussière | [Pré-gate portefeuille relatif](oracle_relative_portfolio.md) |

## Audit des 49 méthodes de la roadmap professionnelle

Cette section confronte
[la roadmap des méthodes quant](alpha_trade_quant_professional_methods_roadmap.md)
au code et aux expériences réellement présents au 6 septembre 2026. Les états
ont le sens suivant :

- `ACTIF` : méthode intégrée et utilisée dans l'application ou ses harnais ;
- `FAIT_NO_GO` : expérience exécutée, hypothèse non promue ;
- `EN_COURS` : campagne actuellement exécutée ;
- `PARTIEL` : une partie seulement du contrat a été testée ou industrialisée ;
- `À_FAIRE_CONDITIONNEL` : pertinent uniquement si son prérequis passe ;
- `À_FAIRE_PRIORITAIRE` : information nouvelle potentiellement utile ;
- `DIFFÉRÉ` : intérêt possible mais rapport signal/complexité faible maintenant ;
- `À_ÉVITER` : non justifié dans l'état actuel des preuves.

### 1–10 — formulation du signal et trajectoires

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 1 | Tail Classification D1/D10 | `FAIT_NO_GO` statique et temporel | GlobalDirection, le modèle mutualisé statique et Temporal V2 ont échoué. V2 trouve au mieux 0,5143 avec l'état statique ; les trajectoires ne l'améliorent pas. Voir [GlobalDirection](../experiences/archives_recherche/global_direction_h20.md), [shared directional](shared_directional_oracle_events.md) et [Temporal V2](temporal_d1d10_v2.md). |
| 2 | Temporal Feature Engineering | `FAIT_NO_GO` ancien et V2 | Après l'ancien test sur scores clairsemés, V2 a testé proprement 27 séries locales denses, N=3/5/10 et T0/T1/T2. Aucun T2 ne gagne +0,01 contre T0 ; N10 dégrade Logistic. Voir [historique temporel](../experiences/archives_recherche/global_direction_temporal.md) et [Temporal V2](temporal_d1d10_v2.md). |
| 3 | Meta-Labeling | `PARTIEL` | La cascade Oracle → spécialistes LONG/SHORT existe techniquement. L'entraînement directionnel conditionnel Oracle a échoué en généralisation ; le méta-label temporel n'est pas validé. Conserver l'architecture, pas la considérer comme alpha démontré. Voir [bundle](per_symbol/07_bundle_oracle_long_short.md). |
| 4 | Cross-Sectional Ranking | `ACTIF` global ; `FAIT_NO_GO` post-Oracle | Global Ranking est une brique complète. Le ranker restreint au TOP20 Oracle n'a pas franchi les gates ; PairLogit est retesté dans V2 sur les trajectoires. Voir [Global Ranking](global_ranking/README.md) et [ranker conditionnel](conditional_oracle_ranker.md). |
| 5 | Cross-Feature Divergence | `PARTIEL`, `FERMÉ_CONDITIONNEL` | Plusieurs divergences existent déjà parmi les features EXPERT. L'ablation supplémentaire était conditionnée à un signal V2 ; Dataset A étant NO_GO, elle n'est pas ouverte. |
| 6 | Relative Trajectory | `PARTIEL`, `FERMÉ_CONDITIONNEL` | Les niveaux de force relative et leurs deltas/pentes sont inclus dans V2. Une trajectoire stock moins secteur autonome n'est pas lancée, car le gate Dataset A préalable a échoué. |
| 7 | Multi-Horizon Agreement | `PARTIEL`, `FERMÉ_CONDITIONNEL` | Les features multi-horizons et l'audit de consensus existent. Le test directionnel supplémentaire était conditionné à un V2 informatif ; il n'est pas ouvert. Voir [consensus OOF](oof_consensus_audit.md). |
| 8 | Persistence | `ACTIF` ailleurs ; `FAIT_NO_GO` D1/D10 V2 | V2 a inclus la fraction de variations positives sur N sans améliorer T0. Ne pas confondre ce résultat avec la persistance Global Rank/DIP. Voir [DIP historique](../experiences/archives_recherche/persistent_top10_dip.md). |
| 9 | Velocity / Acceleration | `FAIT_NO_GO` D1/D10 V2 | V2 a testé pentes, dispersion, persistance et accélération canonique dans T2. Aucun T2 ne franchit le gate de gain ; pas d'ablation séparée justifiée. |
| 10 | Change-Point Detection | `DIFFÉRÉ` | Aucun test causal dédié CUSUM/PELT n'a été trouvé. À envisager seulement si V2 montre qu'une dynamique simple existe mais reste mal captée ; sinon ce serait du feature mining supplémentaire. |

### 11–19 — conditionnement, spécialistes et modèles séquentiels

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 11 | Event-Conditioned Models | `PARTIEL` / majoritairement `FAIT_NO_GO` | Earnings, Form 4, news, analystes et 8-K ont été audités. Form 4 et earnings ne passent pas ; 8-K et Analyst Insights restent inconclusifs. Un nouveau modèle conditionné exige une série PIT plus dense ou une source nouvelle. Voir [POC Eroya](eroya_directional_poc.md). |
| 12 | Regime-Conditioned Models | `FAIT_NO_GO` pour la direction | Les régimes sont disponibles comme features et dans le risque. Le modèle directionnel quotidien de régime Oracle n'a produit aucun avantage stable. Ne pas créer maintenant des experts séparés par régime. Voir [E5](oracle_daily_regime_direction.md). |
| 13 | Mixture of Experts | `DIFFÉRÉ` | Aucun ensemble de patterns directionnels validés ne justifie encore un gating model. Requis : au moins deux experts complémentaires ayant chacun un avantage OOF. |
| 14 | Trajectory Clustering | `À_FAIRE_CONDITIONNEL` diagnostique | Non exécuté pour D1/D10. Autorisé uniquement après un signal V2, pour comprendre plusieurs formes de D1/D10 ; pas pour réoptimiser la même période. |
| 15 | Contrastive Learning | `À_ÉVITER` maintenant | Non implémenté et disproportionné sans séparabilité tabulaire préalable. |
| 16 | 1D-CNN / TCN | `NON_OUVERT` | Le prérequis T2 >= +0,01 d'AUC same-date contre T0 a échoué. Ajouter un réseau ne répondrait pas à l'absence de signal tabulaire. |
| 17 | LSTM séquentiel | `ACTIF` per-symbol générique ; `NON_OUVERT` D1/D10 | LSTM existe dans ModelFactory, mais le challenger mutualisé de polarité n'est pas lancé après le NO_GO tabulaire V2. |
| 18 | Transformer temporel | `À_ÉVITER` | Séquences de 4 à 11 observations et absence actuelle de signal ne justifient ni paramètres ni complexité supplémentaires. |
| 19 | Calibration | `ACTIF`, application conditionnelle | Platt/isotonic/temperature-vector et la gouvernance existent. E2-B a montré qu'une calibration correcte ne sauve pas un ranking faible. Calibrer Temporal uniquement après Dataset C et stabilité du classement. Voir [recalibration](recalibration_et_promotion.md). |

### 20–29 — protocole scientifique et traitement des données

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 20 | Feature Ablation | `ACTIF` et largement `FAIT` | Campagnes Global Ranking B0–B44, Oracle 01–14, Per-Symbol S7/V2 et sources Eroya. Continuer seulement par familles préfixées sur mêmes lignes, pas par suppression opportuniste. |
| 21 | Direction vs Amplitude Audit | `ACTIF` / `FAIT` | E6-A valide l'amplitude Oracle ; tous les harnais directionnels récents séparent rendement signé et amplitude. V2 recalcule correctement tail-vs-middle, contrairement à l'ancien `dir_vs_amp`. Voir [E6-A](oracle_amplitude_audit.md). |
| 22 | Same-Date Evaluation | `ACTIF` | Métrique centrale des modèles mutualisés, rankers, consensus et V2. Elle évite qu'un régime de date soit pris pour une séparation cross-sectionnelle. |
| 23 | Pairwise Ranking | `FAIT_NO_GO` statique et temporel | R1 PairLogit sur le pool Oracle a échoué. Dans V2, PairLogit reste sous 0,50 d'AUC same-date avec des buckets non monotones malgré les trajectoires. |
| 24 | Purged Walk-Forward | `ACTIF` | Oracle, Global Ranking, Per-Symbol et recherches partagées utilisent le WF. V2 impose `oracle_available_date < test_start`, donc les targets H20 du train sont connus avant le test. |
| 25 | Embargo / Leakage Controls | `ACTIF` | Assertions de features interdites/futures, garde de disponibilité target, Oracle OOF, preprocessing train-only et contrôles PIT sont présents. La confirmation finale V2 reste déclarée indisponible car 2018–2025 a déjà été observé. |
| 26 | Missingness as Information | `PARTIEL` | `is_filled`, âges de snapshots et âges d'événements existent dans plusieurs datasets. V2 local n'ajoute pas mécaniquement des centaines de flags. À compléter seulement pour les sources irrégulières réellement retenues. |
| 27 | Event Recency | `PARTIEL` / sources testées non promues | Distance aux earnings, récence Form 4/news/événements ont été testées dans les POC correspondants sans signal suffisant. Garder comme contrat standard pour toute nouvelle source événementielle. |
| 28 | Ensemble Models | `ACTIF` pour championnat ; `FAIT_NO_GO` pour consensus directionnel | La sélection de champion LSTM/LightGBM/CatBoost existe. Le consensus OOF des modèles directionnels n'améliore pas le meilleur composant ; ne pas rechercher des poids post-hoc. Voir [C1](oof_consensus_audit.md). |
| 29 | Feature Neutralization | `ACTIF` / `FAIT` | Features SPY/secteur, CAPM et cibles résiduelles ont été testées. Les campagnes Global Ranking montrent leur utilité contextuelle ; les cibles directionnelles résidualisées n'ont pas résolu D1/D10. Voir [campagnes Global](../experiences/campagnes_global_ranking/README.md) et [E1](shared_directional_oracle_events.md). |

### 30–39 — risque, portefeuille et formulations alternatives

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 30 | Risk Overlay | `ACTIF` | Moteur risque/exécution séparé, stops, TP, drawdown, volatilité cible et protections sont implémentés et documentés. Le risque ne doit pas être utilisé pour masquer un signal directionnel absent. Voir [risque/lifecycle](../experiences/risque_execution_lifecycle.md). |
| 31 | Portfolio Constraints | `ACTIF` ; portefeuille relatif `FAIT_NO_GO` | Max positions, exposition sectorielle, exposition brute/nette, drawdown et liquidité sont consommés par le backtest/production. Le pré-gate dollar-neutral dans le TOP20 Oracle obtient +0,304 % net par cohorte H20, mais seulement 4/9 folds positifs ; aucun replay n'est autorisé. Voir [portefeuille relatif Oracle](oracle_relative_portfolio.md). |
| 32 | Transaction Cost Awareness | `ACTIF` | Commission, slippage, spread, intérêt de marge et replay d'exécution font partie des contrats canoniques. Les diagnostics ML purs restent avant coûts ; tout GO doit ensuite passer le backtest net. |
| 33 | Probability Thresholding | `FAIT`, non promu | Les seuils 0,55/0,80/0,85/0,90 ont été comparés sur le bundle directionnel ; aucune politique robuste n'en est sortie. Ne pas reprendre un sweep fin sans nouveau modèle validé. |
| 34 | Symbol-Specific Thresholds | `À_ÉVITER` | Les gates de sélection de candidats per-symbol sont des contrôles de qualité, pas des seuils de trading optimisés par ticker. L'échantillon de tails reste trop faible pour cette recherche. |
| 35 | Per-Symbol Fine-Tuning | `FAIT_NO_GO` pour la mission Oracle | Les spécialistes LONG/SHORT et leur population conditionnelle Oracle sont implémentés. L'amélioration développement ne s'est pas généralisée. Capacité technique conservée, hypothèse ML non promue. |
| 36 | Hierarchical Models | `PARTIEL`, `DIFFÉRÉ` | Global, Per-Sector et Per-Symbol existent comme modules distincts, mais pas comme modèle hiérarchique joint avec shrinkage. Inutile avant un signal partagé stable. Voir [Per-Sector](per_sector/README.md). |
| 37 | Survival / Time-to-Event | `PARTIEL`, `FAIT_NO_GO` proche | First-touch, rentabilité path-aware et veto de risque ont étudié le chemin et l'ordre des barrières ; ils ont échoué. Un vrai modèle de durée n'est pas prioritaire tant que H20 reste le contrat. |
| 38 | Régression directe des rendements | `FAIT_NO_GO` | E1 a prédit le rendement signé H3/H5/H10/H20 ; IC proche de zéro et branche SHORT négative. Ne pas relancer sans données nouvelles. |
| 39 | Ordinal Classification | `FAIT_NO_GO` | GlobalDirection ordinal D1/milieu/D10 et objectif rank ont été testés sans battre les baselines. Dataset C V2 sera un audit de scoring du milieu, pas une réouverture opportuniste de cette cible. |

### 40–49 — méthodes avancées, robustesse et données alternatives

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 40 | Multitask Learning | `À_ÉVITER` maintenant | Aucun avantage à remélanger amplitude, direction et rendement après avoir clarifié leurs rôles. Une future tête multi-horizon directionnelle serait une expérience distincte, pas un modèle end-to-end. |
| 41 | Reinforcement Learning | `À_ÉVITER` | Ne résout ni la faiblesse informationnelle D1/D10 ni les problèmes de couverture. |
| 42 | Genetic Programming / Symbolic Search | `À_ÉVITER` | Risque de data mining excessif sur une période déjà largement observée. |
| 43 | SHAP Pattern Discovery | `À_FAIRE_CONDITIONNEL` diagnostique | Feature importance existe dans plusieurs entraînements, mais une analyse SHAP de trajectoires n'est utile qu'après un GO OOF V2. Elle n'est jamais une preuve autonome d'alpha. |
| 44 | Counterfactual Analysis | `PARTIEL` | Des contrefactuels de lifecycle/stops et de risque existent. Aucun contrefactuel directionnel de trajectoire n'est justifié avant un modèle V2 informatif. |
| 45 | Placebo Tests | `NON_DÉCLENCHÉ` pour V2 | Le placebo était obligatoire avant promotion d'une variante. Aucun T2 n'ayant passé le gate primaire, l'exécuter ne changerait pas la décision NO_GO et Dataset B reste fermé. |
| 46 | Bootstrap par Date | `NON_DÉCLENCHÉ` pour V2 | Le bootstrap du delta T2-T0 était prévu pour une variante candidate. Tous les deltas sont sous +0,01 ; aucun N n'est sélectionné et le contrôle n'est pas requis pour rejeter l'hypothèse. |
| 47 | Stability Selection | `PARTIEL` | Les gates fold/année et ablations par famille existent. La stabilité des rangs d'importance feature par fold n'est pas encore produite dans V2 ; à ajouter seulement pour une variante candidate. |
| 48 | Data Source Incrementality | `FAIT` sur les sources disponibles | Form 4 a eu une ablation modèle, les autres familles ont été comparées sur des populations communes lorsque la couverture le permettait. Aucune source Eroya testée n'est promue. Réouvrir seulement avec une série PIT réellement nouvelle et dense. |
| 49 | Alternative Data Families | `PARTIEL / NO_GO_TICKS_OPTIONS_VOLUME` | Flux signé, prix/liquidité et séance intraday sont rejetés. Le mapping Options `v` a été corrigé : le ratio volume call/put est enfin testable mais instable, H3 AUC 0,619 portée uniquement par 2022. Aucun feature n'est promu. Borrow fee/utilization et auction imbalance restent bloqués faute de source. Voir [Options E7](options_directional_poc.md), [flux signé](signed_trade_flow_pilot.md) et [prix/liquidité tick](tick_price_liquidity_audit.md). |

## Correctif transversal de qualité des labels Oracle

L'audit D10 a découvert 36 faux rendements issus des restructurations WFRD/CHRD
et 103 targets utilisant un prix D+H forward-fillé. Le correctif fail-closed est
implémenté : barres réelles aux deux extrémités, registre de ruptures d'identité,
quarantaine des sauts inexpliqués, traçabilité du rendement brut et segmentation
des features rolling. Le dry-run complet isole exactement 139 lignes sur
890 928. Voir [audit D10 et contrat corrigé](d10_corporate_action_anomaly_audit.md).

## P0 — audit de l’univers Oracle 400

L’univers statique du batch `model-factory-20260907170018-0e94ac` est audité
dans [P0 — univers Oracle 400](oracle_universe_p0_audit.md). Le biais de
sélection est confirmé : 112/400 symboles commencent après le début de la
période et 60 en 2020 ou après. Les 20 % de symboles les plus contributeurs
créent 41 % des tails ; leur fréquence est corrélée à 0,895 avec la volatilité
et 0,918 avec le range médian. Les snapshots PIT existants sont trop dégradés
pour servir immédiatement de gold standard. Statut : `FAIT_BIAIS_CONFIRMÉ`,
avec P0b bar-only/PIT qualifié comme prochaine étape avant tout réentraînement.

P0b est maintenant terminé. L'admission bar-only quotidienne depuis les 2 696
candidats produit 3,93 M de lignes et un univers médian de 1 550 titres.
Seulement 67,7 % des anciennes lignes passent les nouveaux gates quotidiens et
9,9 % des appartenances extrêmes changent. Les 20 % de symboles les plus
contributeurs produisent désormais 52,2 % des tails : sélectionner les titres
les plus volatils est explicitement rejeté. Voir
[P0b — univers dynamique](oracle_universe_p0b_dynamic.md). Statut :
`FAIT_DYNAMIC_BAR_ONLY`, avec capitalisation/type/pays historiques et titres
radiés restant à qualifier.

P0c compare ensuite, sur les mêmes 3,93 M lignes, le rendement brut, le
vol-scaled, le rang intra-quintile de volatilité et le rang sectoriel. Aucune
variante ne franchit tous les gates. `vol_strata` réduit la concentration de
52,2 % à 42,3 %, mais conserve 89,86 % de l'amplitude contre un gate préfixé à
90 %. Le seuil n'est pas relâché a posteriori ; le label brut reste canonique.
Voir [P0c — cibles Oracle](oracle_universe_p0c_targets.md). Statut :
`FAIT_NO_PROMOTION`, challenger `vol_strata` réservé à une confirmation future.

P0d construit ensuite, sans utiliser labels ni performances futures, un nouvel
échantillon de recherche de 400 titres depuis les 2 696 candidats. Après gates,
995 titres sont éligibles. La sortie respecte exactement les quotas : 260 mid,
100 large, 40 small ; volatilité 60/80/100/100/60 ; bêta 80 par quintile. Elle
couvre 44 secteurs, avec un maximum de 16 titres par secteur, et ne partage que
101 symboles avec l'ancien univers 400. Le fichier est reproductible par
cutoff/seed/hash, mais reste `RECONSTRUCTED_GRADE_B` et ne rend pas 2026H1 OOS.
Voir [P0d — univers équilibré 400](oracle_universe_p0d_balanced400.md). Statut :
`FAIT_BALANCED_400`, prochaine étape préfixée P0e de comparaison OOF à contrat
Oracle identique.

P0e compare ensuite le témoin `model-factory-20260907170018-0e94ac` au batch
Balanced 400 `model-factory-20260908183941-7826b4` sur 14 folds et 1 764 dates
OOF communes. Le nouvel univers augmente marginalement l'AUC (0,6851→0,6882),
mais diminue la précision TOP20 (40,00→38,94 %), le rappel
(41,37→39,14 %) et le lift d'amplitude (1,591→1,515). Les IC 95 % par blocs de
21 séances sont entièrement négatifs pour ces quatre mesures TOP20. Il ne gagne
que 2/15 semestres en AUC et 3/15 en lift d'amplitude. Statut :
`FAIT_NO_PROMOTION_PERFORMANCE`. L'ancien 400 reste un témoin biaisé et le
Balanced 400 un échantillon de recherche ; la suite est P0f sur l'univers large
dynamique. Voir [P0e — comparaison OOF](oracle_universe_p0e_comparison.md).

P0f est `FAIT_GO_RECHERCHE_AMPLITUDE`. Le batch de confirmation
`model-factory-20260909051302-323684` produit 3,93 M de labels, 14 folds et
2,91 M de prédictions OOS du 5 juillet 2018 au 11 juillet 2025. Sur les 1 512
dates communes avec le premier batch 12-fold, les prédictions et métriques sont
strictement identiques. Sur 1 764 dates face à l'ancien 400, les deltas TOP20
sont +4,08 points de précision, +2,74 points de rappel, +0,095 de lift amplitude
et +3,23 points de rétention ; tous les IC 95 % par blocs restent positifs. Face
au Balanced 400, les quatre deltas sont aussi positifs. P0f devient donc le
contrat de recherche recommandé pour l'Oracle d'amplitude. Il ne résout pas la
direction : son TOP10 contient 25,5 % de D1 et 25,0 % de D10. Le batch reste
`serving_ready=false` jusqu'à l'adaptation et la validation du serving. Voir
[P0f — entraînement dynamique](oracle_universe_p0f_dynamic_training.md).

P0g est `FAIT_NO_GO_DIRECTION`. Le témoin directionnel mutualisé figé,
sans contexte symbole/secteur, a été réentraîné sur les 582 700 événements
TOP20 OOS du batch P0f confirmé. Sur neuf folds et 179 605 observations D1/D10,
il obtient AUC 0,4904 et IC quotidien −0,0147. Le TOP LONG contient 46,88 % de
D10 contre 53,12 % de D1 ; le TOP SHORT produit −1,43 % de rendement signé.
Le dernier fold 2025 est favorable, mais les autres folds sont instables et
l'agrégat reste inférieur au hasard. Les variantes lourdes E1/E2 ne sont donc
pas relancées sans information PIT nouvelle. Le correctif technique reconstruit
désormais le cache directionnel manquant des batchs Oracle autonomes à partir
des seules lignes persistées traçables par `fold_start`. Voir
[P0g — impact directionnel](oracle_universe_p0g_directional_impact.md).

P0h est `IMPLÉMENTÉ_SHADOW_ONLY`. Le batch P0f dynamique peut désormais
calculer son admission PIT quotidienne, ses features, ses rangs et ses scores
Oracle en dehors des tables de serving. Les fragments Parquet portent
`prediction_mode=shadow`, `champion_t_start` et le gate TOP20 ; le rapport
porte `trading_eligible=false`. Sans `--oracle-shadow`, le batch reste
bloqué. L'IHM active automatiquement la case shadow lorsqu'elle détecte un
profil `pit_dynamic_bars`. Une première collecte 2025-07-14→2026-06-30
reste à exécuter, puis à évaluer lorsque les rendements H20 sont disponibles.
Voir [P0h — serving shadow dynamique](oracle_universe_p0h_shadow_serving.md).

P0i est `FAIT_GO_AMPLITUDE_SHADOW_NO_GO_TRADING`. Le run holdout dynamique
compte 462 461 labels H20 valides sur 230 séances. L'AUC atteint 0,7742 et le
lift d'amplitude TOP20 1,757 ; en 2026H1 ils restent respectivement à 0,7727 et
1,709. Les déciles du score sont parfaitement monotones sur le rendement
absolu. En revanche, parmi les vrais extrêmes retrouvés en 2026H1, 51,27 % sont
positifs : la direction reste pratiquement équilibrée. P0i valide donc le
détecteur d'amplitude, pas une stratégie LONG/SHORT. La suite autorisée est un
canary shadow P0j, sans alimentation des tables de trading.

Voir [P0i — évaluation holdout shadow](oracle_universe_p0i_shadow_evaluation.md).

P0j est `IMPLÉMENTÉ_CANARY_SHADOW`. Le canary quotidien choisit la dernière
séance EOD disponible, exécute l'admission P0b et l'Oracle dans des Parquet
isolés, contrôle couverture/distribution contre la baseline P0i, puis évalue
automatiquement les runs arrivés à H20 en reconstruisant les labels en dry-run.
Le registre est local, idempotent par date et protégé contre deux exécutions
simultanées. La tâche Windows est fournie mais n'est pas installée
automatiquement. P0j reste `research_only` et n'alimente aucune table ML.

Voir [P0j — canary quotidien](oracle_universe_p0j_daily_canary.md).

Premier run P0j réel : `FAIT_WARN_AGE_ONLY` au 10 juillet 2026. Les 2 097
scores et le TOP20 de 420 titres ont été écrits uniquement en Parquet. Le PSI
de 0,0182, la moyenne des scores et la couverture restent dans les bandes P0i ;
le seul avertissement est l'âge du champion, 548 jours. Les deux tables de
prédictions contiennent zéro ligne pour ce batch et cette date. L'évaluation
réalisée reste en attente des vingt séances futures.

La branche d'évaluation retardée a été validée séparément au 9 juin 2026 :
2 033 labels exploitables, AUC 0,8044, précision TOP20 47,17 % et lift
d'amplitude 1,884. Le registre a correctement basculé à une date évaluée sur
vingt requises, sans écrire en base.

La source EODHD étant volontairement arrêtée, `stock_bars_daily` se termine au
10 juillet 2026. P0j reste optionnel : sans nouvelle barre, la tâche quotidienne
est idempotente et ne produit aucune observation supplémentaire. Elle peut être
désinstallée sans supprimer les artefacts. Voir la section
[caractère optionnel et retrait propre](oracle_universe_p0j_daily_canary.md#caractère-optionnel-et-retrait-propre).

P0k est ouvert pour répondre à une limite de P0g : seul le classifieur D1/D10
direct a été revalidé sur le nouvel univers dynamique. Une campagne courte et
préfixée recontrôle les trois formulations réellement sensibles à la population
quotidienne — probabilités indépendantes E2, ranker conditionnel R1 et régime
quotidien E5. E4-B et les variantes lourdes ne sont autorisés que si ce premier
écran produit un signal stable. Voir
[P0k — revalidation directionnelle ciblée](oracle_universe_p0k_directional_revalidation.md).

## Pistes encore intéressantes après cet audit

### Priorité P0 — Temporal V2 fermé

Dataset A est terminé en `NO_GO_DATASET_A`. Bootstrap et placebo n'ont pas été
déclenchés, car aucune variante n'était éligible à une promotion. Dataset B/C,
N20, divergences, trajectoire relative, multi-horizon et réseaux séquentiels
restent fermés. Cette décision évite de chercher a posteriori un sous-groupe ou
un hyperparamètre favorable dans une hypothèse déjà rejetée.

### Priorité P1 — information véritablement nouvelle après l'échec V2

1. **Intraday 5 minutes de séance complète Eroya — `FAIT_NO_GO`** : 393 dates
   OOF ont été collectées et 330 séances passent la qualité. Aucun signal
   directionnel ne passe. La volatilité réalisée est descriptive pour
   l'amplitude (AUC 0,56, IC 0,18, 6/8 semestres) mais échoue Bonferroni à 0,30.
   Aucun modèle, profil ou stockage applicatif. Voir [trajectoire intraday de
   séance](intraday_session_path_pilot.md).
2. **Borrow fee/utilization/shares available — `BLOCKED_NO_PIT_HISTORY`** :
   piste squeeze/pression short pertinente, mais aucun historique PIT dense
   n'est disponible localement ou via Eroya. FINRA SLATE est repoussé à 2028.
   Voir [audit de faisabilité borrow](borrow_lending_data_feasibility.md).
3. **Capital flow signé — `FAIT_NO_GO`** : sur 200 événements, le flux agrégé
   échoue la stabilité. L'audit temporel préfixé ne le sauve pas : la meilleure
   accélération atteint AUC 0,567 et 5/7 semestres, mais p brute 0,149 et p
   Bonferroni 1,0. Aucun modèle ni découpage additionnel. Une famille séparée
   prix/spread/liquidité peut être auditée comme découverte sur les ticks déjà
   acquis, avec confirmation ultérieure obligatoire. Voir [flux signé
   trades/NBBO](signed_trade_flow_pilot.md).
4. **Épuisement du prix à la clôture — `FAIT_NO_GO`** : l'observation
   contrariante du premier échantillon ne se reproduit pas sur 400 dates
   disjointes. Le score fixe `-return_5m` obtient AUC 0,490, IC 0,005, p=0,627
   et 4/7 semestres favorables. La piste est fermée sans modèle. Une tentative
   initiale concentrée sur le ticker alphabétiquement premier a été interrompue
   avant rapport ; le correctif hash intra-date est testé. Voir [audit tick prix
   et liquidité](tick_price_liquidity_audit.md).
5. **Auction imbalance MOC/LOC — `BLOCKED_NO_DATA_SOURCE`** : cette donnée
   serait distincte des trades/NBBO et pertinente avant la clôture, mais le
   catalogue Eroya ne publie ni endpoint ni archive de messages de déséquilibre.
   Ne pas l'approximer à partir du dernier trade ou de la profondeur NBBO.
6. **Contexte intraday SPY/QQQ/IWM/VXX — `FAIT_NO_GO`** : 364 événements
   alignés et 305 tails. IWM-SPY atteint seulement AUC 0,52 ; volatilité SPY et
   mouvement VXX plafonnent à AUC amplitude 0,53. Tous les tests corrigés sont
   non significatifs. Voir [contexte intraday marché](intraday_market_context_pilot.md).

### Priorité P2 — uniquement après découverte d'un signal stable

- cross-feature divergence contrôlée ;
- trajectoire relative secteur/SPY ;
- cohérence multi-horizon ;
- SHAP et stability selection diagnostiques ;
- séquence aplatie puis TCN/1D-CNN ;
- intégration séparée dans LONG et SHORT, puis calibration et backtest net.

### Faible priorité ou arrêt actuel

- change-point avancé, clustering et mixture of experts sans patterns validés ;
- 13F/institutionnel pour des décisions H3–H20 ;
- LSTM D1/D10 avant TCN et avant preuve tabulaire ;
- Transformer, contrastive learning, multitask end-to-end, RL, genetic
  programming et seuils spécifiques par symbole.

## Multi-Horizon Oracle + Rolling Confirmation — `FAIT_WEAK_SIGNAL`

Quatre Oracle OOF H5/H10/H15/H20 sont alignés sur une coupe quotidienne
commune. Le POC pré-enregistré mesure MH0–MH3, la continuation après
J+5/J+10/J+15, la valeur incrémentale du consensus restant et une entrée
retardée symétrique S6-LS. Il est strictement `research_only` : aucune table,
aucun backtest et aucun flux live ne sont modifiés avant `GO_RESEARCH`.
L'univers courant `univers_filtred_equities.txt` implique un biais de survivance
et interdit `STRONG_GO`. Le run couvre réellement 284 symboles de juillet 2018
à juillet 2024. H5/H10/H15/H20 sont très corrélés (0,926–0,970), la sélection
multi-horizon contre REST n'est pas significative et S6-LS est négative. Un
signal exploratoire subsiste pour H20 seul + gagnant J+5 + Oracle restant
confirmé (écart quotidien +1,41 %, IC95 [+0,24 % ; +2,74 %]), mais il est
concentré dans les extrêmes et instable selon les années. Verdict `WEAK_SIGNAL` ;
phase 2 générale fermée, petit challenger OOS ciblé seulement. Voir
[protocole et mode d'emploi](multi_horizon_oracle_rolling_confirmation.md)
et [prompt de campagne](../../prompt/multi_horizon_oracle_rolling_confirmation_prompt.md).

Le challenger ciblé **Variante 2 — maintien rolling H5 jusqu'au TP** est
`FAIT_NO_GO`. Sur 30 566 entrées appariées, H20 fixe donne `+0,109 %` net/trade,
l'extension passive H60 `+0,120 %` et le rolling prix + H5 `-0,097 %`. Le rolling
perd `-0,217 %` par trade contre l'extension passive ; son delta quotidien
apparié vaut `-0,286 %`, IC95 `[-0,568 % ; -0,043 %]`. La cause principale est
le veto prix non positif, qui coupe 11 219 trades avant des récupérations
partielles. Le veto H5 seul est légèrement favorable sur sa sous-population,
mais trop faible et instable pour être promu. L'extension H60 seule n'est pas
significative et 95,5 % des trades sont inchangés face à H20. Aucun changement
du backtest ou du live. Voir la section résultat du
[protocole](multi_horizon_oracle_rolling_confirmation.md).

## E7 — Surveillance quotidienne KEEP / EXIT — `FAIT_NO_GO`

E7-A construit, pour chaque position H20 encore ouverte à une clôture, un état
PIT exécutable au prochain open. Il sépare strictement identité, features
observables et labels futurs (`KEEP`, avantage contre sortie immédiate, TP avant
stop, rendements et excursions futurs). `trade_id` est la future clé de groupe
anti-fuite et `label_end_date` la borne de purge. Le premier run a révélé puis
permis de corriger deux défauts avant entraînement : états de liquidation H20
obligatoire et historique technique tronqué à l'entrée. Son artefact est
supersédé ; E7-A doit être relancé. Aucun entraînement n'est autorisé avant le
nouvel audit de couverture, de distribution et de stabilité semestrielle. Voir
[E7 KEEP/EXIT](daily_position_keep_exit.md).

Le run E7-A corrigé contient 199 677 états sur 29 449 trades, une cible KEEP à
51,14 %, aucune décision H20 forcée et une couverture quasi complète. La forte
dérive semestrielle interdit une règle statique, mais l'état de position possède
assez de structure pour ouvrir E7-B. Trois modèles research-only sont prêts :
logistique calibrée, LightGBM calibré et LightGBM Huber sur l'avantage. Le gate
est le delta économique OOS de la première sortie contre H20, pas le F1.

E7-B est terminé sur six folds et 16 609 trades OOS. La meilleure politique,
LightGBM Huber sur l'avantage, ajoute `+0,080 %` par trade mais seulement
`+0,013 %` par date, IC95 `[-0,484 % ; +0,516 %]`, avec 2/6 folds positifs et
une corrélation score/avantage de `-0,016`. Les classifiers obtiennent AUC
environ 0,64 sans valeur économique stable. Le mécanisme évite fortement les
pertes de 2022H1 en sortant presque tout, puis détruit les gains de 2022H2 avec
la même réaction. Verdict `NO_GO` : aucun seuil ou modèle n'est promu.

## E8-A — Historique options PIT — `BLOCKED_NO_DENSE_PIT_HISTORY`

L'audit local reproductible ne trouve aucune table options en base. La meilleure
collecte comporte 625 événements, 155 symboles et 323 surfaces complètes
(51,68 %), mais seulement huit dates entre mai 2022 et juillet 2025, contre 504
requises. Les snapshots courants possèdent IV/Greeks/open interest sur quelques
contrats mais ne sont pas historiques. Il manque des quotes entrée/sortie
quotidiennes, IV/Greeks/OI historiques observés, taux, dividendes et ajustements
de contrats. E8-B n'est pas autorisé. Voir
[audit historique options PIT](options_pit_history_audit.md).

## E8-A2 — Source et coût d’acquisition — `ABANDON_COÛT`

Le TOP20 Oracle représente 28 736 événements sur les 504 dernières séances
éligibles, environ 57 par jour. Une collecte REST ciblée nécessite 363 511
tentatives pour une paire 45 DTE valorisée à H3/H5/H10/H20, soit environ
4,06 Gio bruts selon les hypothèses prudentes ; télécharger l’OPRA complet est
écarté. Un pilote de 60 dates réparties dans le temps représente 3 421 événements
et 43 276 tentatives. Le fournisseur techniquement préféré était ThetaData
Options Value, avec Massive Options Advanced comme repli opérationnel. Le
10 septembre 2026, la décision a été prise de ne souscrire à aucune source
payante : la campagne d'acquisition est donc fermée en `ABANDON_COÛT`.
Eroya n’est pas retenu tant que les droits de livraison des données américaines
ne sont pas confirmés. E8-B reste bloqué avant les gates du pilote. Voir
[source, coût et plan d’acquisition](options_acquisition_cost_audit.md).

## E8-A3 — Connecteur ThetaData et smoke — `ABANDON_COÛT`

Le connecteur REST v3 local et le smoke préfixé sont implémentés. Dix événements
Oracle TOP20 sont préparés sur cinq dates réparties de 2022 à 2024, avec un titre
faible et un titre fort en dollar-volume par date. Le premier run s’est arrêté
proprement avant tout appel : aucun Theta Terminal n’écoute sur le port 25503 et
`THETADATA_API_KEY` est absente. Ce résultat ne rejette pas la source. Après
démarrage du terminal, le même smoke doit vérifier contrats expirés, paire ATM
35–55 DTE et NBBO entrée/H3/H5/H10/H20. Artefact canonique du blocage :
`artifacts/research/thetadata_options/thetadata-options-smoke-20260910185522/report.json`.
Les 15 tests ciblés E8-A1/A2/A3 passent et le contrôle statique est propre.

La bibliothèque Python officielle publiée en 2026 permettrait aussi d'appeler
directement `option_list_contracts()` et `option_history_quote()` sans Theta
Terminal ni Java. Elle ne supprime toutefois pas l'obligation d'un abonnement
Options Value ou supérieur. La piste est donc abandonnée pour raison économique,
sans rejet scientifique de la donnée. Le connecteur research-only reste inactif,
aucun paquet ThetaData n'a été installé et E8-A4 n'est pas ouvert. Voir
[connecteur et procédure E8-A3](thetadata_options_smoke.md).

## E11 — Oracle H20 × Global Ranking H20 — `FAIT_NO_GO`

Le nouveau Global Ranking H20 strictement OOF contient 4,23 M de rangs sur
2 696 symboles et 13 folds. Son IC global CatBoost vaut `+0,0237`, mais aucun
candidat du championnat n''est éligible à cause de l''instabilité temporelle.
Le croisement propre avec l''Oracle P0f couvre 543 153 événements, 1 625 dates
et 1 461 symboles, soit 93,21 % des événements TOP20.

Dans le pool Oracle, l''IC tombe à `+0,0101`. Le haut du ranking pris en LONG
ajoute seulement `+11,8 bp` contre l''Oracle entier, IC95
`[-24,3 ; +45,8] bp`. Le bas reste haussier en valeur absolue et donne
`−1,329 %` net lorsqu''il est pris en SHORT. Le portefeuille LONG/SHORT vaut
`+8,4 bp`, IC95 `[-20,9 ; +36,6] bp`. Les trois verdicts sont `NO_GO` : le
ranking trie faiblement les rendements relatifs, mais ne distingue pas D1 de
D10. Aucun changement du serving, du backtest ou du live. Artefact canonique :
`artifacts/research/oracle_global_rank_cross/oracle-global-rank-cross-20260911141556`.
Voir [E11 — croisement Oracle H20 × Global Ranking H20](oracle_global_ranking_cross_e11.md).

## E12 — Pont de monétisation Oracle H20 — `FAIT_NO_GO_OR_BLOCKED`

E12 relie l'étude d'événements Oracle au contrat exécutable : open J+1,
sortie H20, déduplication, huit positions, comparaison priorité Oracle /
liquidité / 200 tirages aléatoires, filtre tradable PIT et lifecycle PROD. Sur
582 700 événements OOF, le rendement net fixe moyen reste positif à `+1,103 %`.
Après capacité, la priorité Oracle vaut `+2,540 %` et bat le 95e percentile de
tous les tirages aléatoires, mais son IC95 recouvre zéro.

Le replay PROD dynamique exécute 2 013 trades sur 1 160 dates et ne conserve que
`+0,276 %` moyen, IC95 journalier `[-0,290 ; +0,900] %`. Le lifecycle enlève
`2,119 points` aux mêmes événements H20, avec un IC95 du delta entièrement
négatif. Les 686 trailing stops perdent `-10,93 %` en moyenne ; 707 candidats
sont rejetés par le gap 3 %. Enfin, les snapshots tradables stricts ne couvrent
que 60/1 764 dates. La sensibilité `degraded` devient négative (`-0,791 %`),
mais ne constitue pas une preuve PIT canonique. Aucune promotion n'est
autorisée. Artefact canonique :
`artifacts/research/oracle_monetization_bridge/oracle-monetization-bridge-20260911154131`.
Voir [E12 — pont de monétisation Oracle H20](oracle_monetization_bridge_e12.md).

## E13 — Veto pré-entrée Oracle — `FAIT_NO_GO_OR_BLOCKED`

E13 entraîne un CatBoost mutualisé à prédire le futur motif `trailing_stop`
avec uniquement des variables disponibles au close J ou à l'open J+1. Les 13
folds sont strictement expanding et purgés : toute sortie d'un exemple train
précède le début du fold test. Sur 32 314 événements OOF, l'AUC vaut `0,6259` et
le taux de trailing progresse de 21,84 % dans le décile faible risque à 58,14 %
dans le décile fort risque.

Cette discrimination ne se transforme pas en avantage portefeuille. Le veto
primaire 20 %, dont le seuil est appris uniquement sur chaque train, donne
`+0,357 %` moyen contre `+0,328 %` pour la baseline, mais son delta journalier
est `-0,052 %`, IC95 `[-0,185 ; +0,087] %`. Le trailing sélectionné ne baisse
que de 33,35 % à 32,82 %, le Q05 se dégrade et la stabilité semestrielle échoue.
L'ATR% porte 26,48 % de l'importance : le modèle apprend surtout la mécanique
du stop proportionnel à l'ATR, pas une perte évitable. Les snapshots tradables
stricts ne couvrent que 53 dates. Aucun seuil n'est promu. Artefact canonique :
`artifacts/research/oracle_pre_entry_veto/oracle-pre-entry-veto-20260911155716`.
Voir [E13 — veto pré-entrée après Oracle](oracle_pre_entry_veto_e13.md).

## E14 — Cible économique pré-entrée — `FAIT_NO_GO_OR_BLOCKED`

E14 remplace le motif mécanique de sortie d'E13 par deux cibles OOF : rendement
net PROD winsorisé sur train et probabilité de perte nette. Sur 32 314
événements, l'IC utilité global vaut `+0,0364` et le score de non-perte
`+0,0592`. Le décile d'utilité supérieur rapporte `+1,162 %` avec 30,60 % de
pertes, contre `+0,433 %` et 49,20 % pour le décile inférieur, mais la relation
n'est pas monotone et l'IC quotidien moyen n'est que `+0,0047`.

Le veto primaire 20 % échoue : `+0,149 %` par date contre `+0,360 %` pour la
baseline, delta `-0,188 %`, IC95 `[-0,545 ; +0,132] %`, Q05 dégradé et seulement
6/14 semestres améliorés. L'hybride diagnostique Oracle/utilité 50/50 atteint
`+0,460 %` par date et améliore le Q05, mais son delta de `+0,063 %` est non
significatif et positif sur seulement 7/14 semestres. Aucun seuil ni poids n'est
promu. Les snapshots tradables stricts restent limités à 53 dates. Artefact :
`artifacts/research/oracle_pre_entry_utility/oracle-pre-entry-utility-20260911162146`.
Voir [E14 — cible économique pré-entrée](oracle_pre_entry_utility_e14.md).

## E15 — Audit structurel du lifecycle — `FAIT_NO_GO_OR_BLOCKED`

E15 croise quatre règles figées de trailing (PROD, activation après +0,5R,
après +1R, aucun trailing) avec TP PROD ou aucun TP. Le candidat primaire +0,5R
avec TP donne `+0,0419 %` par date sur événements appariés, IC95 recouvrant zéro,
puis `-0,0830 %` après capacité. Il dégrade Q05/Q01 et la confirmation depuis
2023 vaut `-0,2327 %`. Retarder le trailing transforme principalement les 686
trailing stops PROD en 457–498 stops initiaux plus profonds.

Le diagnostic sans TP révèle une convexité importante sur l'univers large :
`prod_no_tp` atteint `+1,810 %` moyen et un delta portefeuille de `+0,711 %`,
IC95 `[+0,078 ; +1,277] %`. Mais le delta passe de `+1,380 %` avant 2023 à
`-0,489 %` depuis 2023 ; sur les snapshots tradables dégradés, ce contrat tombe
à `-0,360 %`. Les 20 meilleurs trades portent 69 % du gain et la couche PIT
`full` ne couvre que 60 dates. Aucun contrat n'est promu et le lifecycle PROD
reste inchangé. Artefact canonique :
`artifacts/research/oracle_lifecycle_structural_audit/oracle-lifecycle-audit-20260911164445`.
Voir [E15 — audit structurel du lifecycle](oracle_lifecycle_structural_audit_e15.md).

## E16 — Reconstruction PIT de l’univers tradable — `FAIT_NO_GO_OR_BLOCKED`

E16 explique la couverture trompeuse d’E12/E15 : 1 750 dates ont un ancien run
`full`, mais 60 seulement restent canoniques après des publications `degraded`.
Ces anciens `full` ne couvrent ni `history_days`, ni `bars_available`, ni
`close_price`, ni `adv_usd`, et seulement 17,81 % des spreads : ils ne sont pas
requalifiés. La reconstruction bar-PIT couvre 1 764/1 764 séances et
582 698/582 700 événements. Le H20 fixe sous capacité vaut `+2,808 %`, mais le
lifecycle PROD seulement `+0,544 %`, IC95 recouvrant zéro.

`prod_no_tp` est globalement positif avec un IC95 de delta portefeuille > 0,
mais échoue depuis 2023 (`−0,2277 %`) et dégrade Q05 (`−15,44 %` à `−16,91 %`)
ainsi que Q01 (`−22,18 %` à `−22,65 %`). Le trailing après `+0,5R` reste
négatif après capacité et depuis 2023. Aucun contrat n’est promu. Artefact :
`artifacts/research/oracle_tradable_pit_reconstruction/oracle-tradable-pit-reconstruction-20260911192318`.
Voir [E16 — reconstruction PIT et réplication E12/E15](oracle_tradable_pit_reconstruction_e16.md).

## E17 — Bibliothèque d’alphas directionnels price-only H60/H120 — `FAIT_NO_GO`

E17 sort entièrement du pipeline Oracle et évalue six signaux price-only plus
un composite figé sur 1 798 actions, du 2018-07-01 au 2025-12-31. Le contrat est
PIT au close J, entrée open J+1, sortie open J+H+1, filtre de liquidité à J,
top/bottom 20 %, portefeuille 50/50 dollar-neutral, rebalance 20 séances et
6 bps aller-retour par jambe. Le rapport confirme `oracle_used=false`.

Le composite primaire H60 possède un IC positif (`+0,0138`, IC95 entièrement
positif), mais le rendement long/short de `+0,414 %` n’est pas significatif
(IC95 `[-0,430 ; +1,102] %`), seuls 46,67 % des semestres sont positifs et la
jambe SHORT perd `−2,288 %`. Verdict : `NO_GO` pour une stratégie directionnelle
symétrique.

Le momentum résiduel 120–10 à H120 est un `DISCOVERY_CANDIDATE` : IC `+0,0474`,
long/short `+1,664 %`, IC95 `[+0,552 ; +2,527] %`, 80 % de semestres positifs.
Mais la jambe SHORT reste perdante (`−4,368 %`) et le candidat a été identifié
après lecture des diagnostics. Il suggère un alpha de classement relatif ou
long-only à confirmer sur données nouvelles, pas une solution D1/D10. Les
métadonnées actuelles non historisées ajoutent un risque de survivorship bias.
Aucune promotion n’est autorisée. Artefact :
`artifacts/research/directional_alpha_book/directional-alpha-book-20260911194051`.
Voir [E17 — bibliothèque d’alphas price-only](directional_alpha_book_e17.md).

## E17-B — Confirmation prospective momentum résiduel H120 — `BLOCKED_DATA_UNAVAILABLE`

E17-B fige avant nouvelles observations le seul candidat exploratoire d’E17 :
momentum résiduel 120–10, H120, long-only TOP20, entrée open J+1, sortie open
J+121, rebalance 20 séances et 6 bps de coûts. La première date admissible est
le 14 septembre 2026 ; 2018–2025 est définitivement exclu de la confirmation.
Le contrat JSON est protégé par une empreinte canonique SHA-256.

Un verdict exige au moins 24 cohortes matures, quatre semestres d’entrée et 50
titres sélectionnés en moyenne. Il faut ensuite battre en moyenne et avec un
IC95 positif l’univers éligible et SPY, rester positif en absolu, être positif
sur au moins 60 % des semestres et respecter le gate de concentration. Les
seuls verdicts possibles sont `PENDING_DATA`, `NO_GO` et
`GO_RESEARCH_SHADOW_ONLY`. Le rapport initial est logiquement `PENDING_DATA`.
La base disponible s’arrêtant au 30 juin 2026, aucune observation postérieure
au début prospectif du 14 septembre 2026 n’existe. L’expérience est bloquée
jusqu’à reprise de l’alimentation des barres. Aucune promotion production n’est
autorisée.

Voir [E17-B — confirmation prospective](directional_alpha_book_confirmation_e17b.md).

## E17-C — Robustesse historique momentum résiduel H120 — `FAIT_NOT_ROBUST`

E17-C applique des contrôles verrouillés au candidat E17 sans revendiquer un
nouvel OOS. Sur 95 cohortes, le LONG net vaut `+7,696 %` et l’excès contre
l’univers `+2,294 %`, avec IC95 `[+0,959 ; +3,463] %`. Les cinq sous-univers
hash, les quatre calendriers et 14/21 secteurs sont positifs ; les 20 principaux
symboles ne portent que 13,36 % des contributions positives.

Le verdict reste `NOT_ROBUST` : l’excès contre SPY de `+1,194 %` a un IC95
`[-1,279 ; +4,093] %`, et le bloc 2021–2022 perd `−0,770 %` contre l’univers.
Le signal est donc un classement relatif diversifié mais dépendant du temps,
pas un alpha autonome universel ni une solution D1/D10. Aucun serving n’est
modifié. Artefact :
`artifacts/research/directional_alpha_book_robustness/e17c-robustness-20260911201018`.
Voir [E17-C — robustesse historique verrouillée](directional_alpha_book_robustness_e17c.md).

## E18-A — Attribution bêta, secteurs et régimes — `FAIT_MARKET_OR_SECTOR_EXPOSURE`

E18-A conserve exactement le momentum résiduel H120 et les 95 cohortes E17,
puis attribue la performance avec des informations PIT à J. Le portefeuille a
un bêta moyen de `1,021`. Sur `+7,696 %` nets par cohorte H120, la contribution
estimée du marché vaut environ `+6,990 %`. Le rendement beta-hedged tombe à
`+0,645 %`, IC95 `[-1,955 ; +3,263] %`.

La sélection n’est pas un simple pari sectoriel : l’excès sector-neutral contre
l’univers reste `+1,402 %`, IC95 `[+0,429 ; +2,239] %`. Mais la combinaison
sector-neutral + beta-hedged vaut `−0,238 %`, IC95 `[-2,360 ; +2,168] %`.
2021–2022 reste négatif sous toutes les décompositions et 2023–2025 devient
`−1,068 %` après neutralisation combinée. Aucun des quatre régimes SPY figés ne
présente à la fois IC95 positif et réplication temporelle. Verdict :
`MARKET_OR_SECTOR_EXPOSURE`, principalement marché. Aucun filtre de régime ni
serving n’est autorisé. Artefact :
`artifacts/research/directional_alpha_attribution/e18a-attribution-20260911201902`.
Voir [E18-A — attribution de l’alpha H120](directional_alpha_attribution_e18a.md).

## E19-A — Audit de disponibilité PIT des fondamentaux — `FAIT_PARTIAL_CONTRACT_BLOCKED`

E19-A audite 1 798 actions sur 2018–2025 et reconstruit une disponibilité SEC
conservatrice à la séance suivant le dépôt. Les 45 132 lignes SEC couvrent
1 621 symboles (`90,16 %`). Sur 2 369 379 lignes tradables, 89,57 % possèdent
au moins une comptabilité fraîche de moins de 180 jours ; l’âge médian est 50
jours. ROA, ROE, marges, croissance et revenue ont une couverture suffisante.
Les estimations forward, PEG et forward PE sont totalement absentes.

Le training reste interdit car le loader expose cinq défauts : utilisation le
jour même du filing, absence de période fiscale/form/accession, aucune priorité
multi-fournisseur, pas de prédécesseur antérieur au début et remplacement des
NaN par des constantes. Des incohérences sémantiques touchent aussi
debt/equity, EBITDA, dividend yield et estimate revision. Verdict :
`PARTIAL_CONTRACT_BLOCKED`, pas un manque de volume. Artefact :
`artifacts/research/fundamental_pit_availability/e19a-fundamental-pit-audit-20260911203804`.
Voir [E19-A — disponibilité PIT des fondamentaux](fundamental_pit_availability_e19a.md).

## E19-A2 — Correction du contrat PIT fondamental — `COMPLETE_DATA_READY`

Le loader applique désormais une date effective conservatrice : dépôt SEC à
J+1 et snapshots non-SEC au plus tôt le lendemain de leur collecte. Les
collisions utilisent une priorité déterministe, le dernier dépôt antérieur au
début de fenêtre est conservé et les absences sont encodées par des masques au
lieu de constantes sémantiques. La migration 0074 ajoute date de disponibilité,
période fiscale, formulaire, accession et dividende par action. Le mapper SEC
utilise désormais la dette financière, ne confond plus operating income et
EBITDA et sépare dividend/share du yield.

Le rafraîchissement SEC 2016–2025 a ensuite traité 1 798 symboles et persisté
59 358 lignes. Le nouvel audit canonique couvre 1 622 symboles SEC (90,21 % de
l’univers), 89,57 % des lignes quotidiennes avec une comptabilité fraîche de
moins de 180 jours et 99,28 % de lineage complet. Tous les gates passent ; le
verdict est `DATA_READY` et E19-B est désormais autorisée. Artefact :
`artifacts/research/fundamental_pit_availability/e19a-fundamental-pit-audit-20260912085103`.
Voir
[E19-A2 — contrat PIT fondamental](fundamental_pit_contract_e19a2.md).

## E19-B — Bibliothèque d’alphas fondamentaux PIT — `FAIT_VALUE_CANDIDATE_ONLY`

E19-B a été pré-enregistrée avant lecture des résultats puis exécutée sur
1 798 actions, 2018–2025, avec disponibilité SEC J+1, fraîcheur maximale de
180 jours, cinq folds OOF, 63 cohortes et neutralisation quotidienne secteur +
taille. Le composite qualité/valeur/croissance/levier/amélioration possède un
IC positif, mais aucun spread exploitable : à H60, IC `+0,46 %`, LONG
`+3,25 %`, SHORT `-3,32 %` et LONG/SHORT `-0,03 %`; depuis 2023 le spread vaut
`-0,28 %`. Son `GO_LONG` mécanique est expliqué par le rendement absolu : la
jambe LONG fait `-0,09 %` contre SPY à H60. Verdict scientifique composite :
`NO_GO`; aucun serving modifié.

La famille valeur, testée dès le protocole initial, ressort seule : à H60,
IC `+4,47 %` [borne 95 % `+3,31 %`] et spread net `+1,00 %` [borne
`+0,06 %`], avec 80 % des folds et semestres positifs. À H120, IC `+6,58 %`
et spread `+2,18 %` [borne `+0,33 %`], 100 % des folds positifs. Elle reste
positive depuis 2023. C’est un candidat de recherche relatif, pas encore une
stratégie short absolue. Prochaine action permise : confirmation E19-C valeur
seule, verrouillée et sans retuning. Artefact :
`artifacts/research/fundamental_alpha_book/fundamental-alpha-book-20260912112042`.
Voir [E19-B — bibliothèque fondamentale PIT](fundamental_alpha_book_e19b.md).

## E19-C — Confirmation verrouillée du facteur valeur — `FAIT_NO_GO`

E19-C a figé sans retuning le score valeur E19-B et l’a évalué sur deux blocs
qui n’avaient pas contribué aux métriques OOF précédentes : 2018-07-02 à
2020-07-01 et 2025-07-10 à 2025-12-31. Sur 33 cohortes H60, l’IC vaut
`-3,61 %` [IC95 `-5,15 ; -2,01 %`] et le spread net `-0,99 %`. À H120,
l’IC vaut `-5,23 %` et le spread `-1,59 %`. Le LONG sous-performe SPY de
`-2,16 %` à H60 et `-2,70 %` à H120.

Le holdout ancien est fortement négatif (`-1,63 %` H60 ; `-2,71 %` H120),
alors que 2025H2 est positif (`+1,35 %` ; `+3,25 %`). Les cinq sous-univers
hash sont négatifs aux deux horizons. Verdict `NO_GO` : le facteur est dépendant
de période et ne doit être ni promu, ni inversé, ni filtré a posteriori par un
régime choisi sur ces résultats. Aucun serving n’a changé. Artefact :
`artifacts/research/fundamental_value_confirmation/fundamental-value-confirmation-20260912114827`.
Voir [E19-C — confirmation valeur](fundamental_value_confirmation_e19c.md).

## Procédure de mise à jour du registre

Après chaque expérience, ajouter ou mettre à jour une ligne avec :

```text
ID / nom
hypothèse falsifiable
population exacte
target et horizon
protocole OOF/PIT
artefact canonique
métriques principales
gates passés/échoués
verdict séparé LONG, SHORT et AMPLITUDE si applicable
lien vers le document détaillé
prochaine action autorisée
```

Ne jamais remplacer un `NO_GO` par une nouvelle interprétation sans nouvelle
information, nouveau contrat pré-enregistré et nouvelle validation. Conserver
les résultats négatifs : ils empêchent de répéter les mêmes recherches sous un
autre nom.
