# TOP10 Oracle H10 — cassure intraday des bornes de J

## Conclusion

**Test terminé, piste non retenue sous cette forme.** La première cassure
confirmée du plus haut/bas de J ne fournit pas une direction rentable sur les
fenêtres intraday qualifiées de 2025–2026. Le contrôle sans chevauchement ne
rétablit pas l'avantage. Pas de promotion, d'entraînement supplémentaire ou
de modification du trading de production.

Les résultats ci-dessous sont des **rendements nets moyens par occasion**, pas
des rendements annuels de capital. Aucun levier, réinvestissement ou portefeuille
avec capital disponible n'a été simulé.

## Protocole figé avant les rendements

Nouveau GO utilisateur : employer la table intraday existante pour tester une
entrée conditionnelle, plutôt qu'une autre confirmation en clôtures quotidiennes.

- Source de sélection : les mêmes scores annuels de recherche Oracle **amplitude
  H10** que l'étude H10/H20, sous
  `artifacts/research/us_h10_h20_frozen_comparison/20261019-v1`.
  Ce ne sont ni des prédictions directionnelles ni une nouvelle sélection des
  meilleurs modèles après lecture du test. Les poids annuels de cette recherche
  sont CatBoost ; aucun nouvel entraînement ici.
- Conserver les dix premiers rangs **à J**, sans remplacement d'un titre dont
  les données manquent. Aucun filtre des quatre clôtures J−1 à J+2 : ce test est
  distinct de la précédente expérience d'entrée à J+3.
- Reconstituer les bornes de J avec ses barres SIP brutes de séance régulière.
  Ne pas comparer directement des seuils daily ajustés à des prix intraday bruts.
- À J+1, première barre de cinq minutes **clôturée strictement au-dessus du
  haut de J → LONG**, ou **strictement au-dessous du bas de J → SHORT**.
  Un simple contact intrabar n'est pas un signal.
- Entrée à l'open de la barre suivante. La dernière barre de séance ne peut
  donc pas déclencher une entrée ce jour-là. Si les deux directions apparaissent
  successivement, la première gagne ; aucune inversion ni nouvelle entrée pour
  cette occasion. L'absence de cassure entraîne une abstention.
- **TP10 % / SL5 %**, sans trailing. Dix séances d'exposition maximum,
  J+1 incluse : liquidation au dernier close cinq minutes de J+10.
- SL/TP contrôlés dès la barre d'entrée. Stop prioritaire si les deux barrières
  sont touchées dans une même barre sans ordre observable ; gap défavorable au
  prix d'ouverture, gap favorable au TP à la limite, sans amélioration supposée.
- Frictions illustratives : **8 points de base par jambe** ; coût de sortie
  proportionnel à son montant. SHORT : emprunt hypothétique de 0,3 % annualisé,
  jours calendaires/365, au moins une journée. Ce n'est pas une preuve de locate,
  de disponibilité short ou de tarif effectivement payé.
- Aucun balayage des seuils de cassure, des délais ou des TP/SL.

Le calendrier NYSE vient de `pandas_market_calendars`, avec heures UTC,
changements d'heure et demi-séances. Aucune approximation lundi–vendredi.

## Données existantes et exclusions

Lecture seule de `alpha_trade.stock_bars_intraday` :
`provider=alpaca`, `data_source=alpaca_sip`, `interval_code=5m`,
`market_code=US_EQ`, prix `raw`, séance `regular`. Aucun IEX ni mélange de flux.

L'inventaire SQL indique :

| Année | Barres 5m SIP présentes, toutes séances confondues | Symboles | Période présente |
|---|---:|---:|---|
| 2024 | 0 | 0 | aucune |
| 2025 | 34 423 039 | 1 684 | 2 janvier–31 décembre |
| 2026 | 27 694 155 | 1 692 | 2 janvier–15 octobre |

Ces nombres sont la couverture de la table lors de la lecture, **pas le nombre
de barres effectivement utilisé par le test**. L'extraction ciblée comporte
**650 036 barres**, 244 demandes symbole/année. Elle a été réalisée dans une
transaction `REPEATABLE READ`, `READ ONLY`, terminée par `ROLLBACK`, puis scellée
localement avec les empreintes des fichiers. Aucun téléchargement fournisseur.

Une occasion exige les **onze séances complètes J à J+10**, toutes les barres
attendues, sans doublon, OHLC positifs et cohérents, volume positif et aucune
barre remplie artificiellement. Même un trou après une sortie qui aurait été
gagnante exclut la fenêtre : pas de qualification différente selon le résultat.

Un contrôle supplémentaire confronte les OHLC SIP agrégés à la référence daily
de recherche normalisée : une échelle constante est admise, mais la dispersion
des ratios sur les onze séances et les quatre champs doit rester ≤1 %.
Les réserves DD/TOELY et les ruptures d'identité du protocole parent sont
conservées. Aucun ratio de split n'est inventé et aucun cours n'est corrigé ici.

| Année des signaux J | TOP10 attendus | Fenêtres retenues | Séances de signaux représentées | Titres représentés |
|---|---:|---:|---:|---:|
| 2024 | 2 520 | **0** | 0 | 0 |
| 2025 | 2 500 | **1 504 (60,16 %)** | 250 | 61 |
| 2026 | 1 670 | **1 022 (61,20 %)** | 167 | 44 |

Signaux 2025 : 2 janvier–31 décembre. Signaux 2026 : 2 janvier–**1er septembre**,
limite des scores H10 déjà figés, et non le 30 septembre. Les prix de suivi
peuvent être postérieurs au signal selon le calendrier des dix séances.

Motifs exclusifs de non-qualification :

| Année | Séance absente | Grille 5m incomplète | Écart de base/OHLC daily–intraday non qualifié |
|---|---:|---:|---:|
| 2024 | 2 520 | 0 | 0 |
| 2025 | 62 | 809 | 125 |
| 2026 | 0 | 422 | 226 |

Un écart au contrôle daily n'établit **pas** quel fournisseur a tort : agrégation,
enchère de clôture, filtres de transactions ou ajustement peuvent intervenir.
Ces 351 fenêtres restent non qualifiées, pas réparées en faveur de la stratégie.
Les titres exclus ne sont ni remplacés par le rang suivant ni comptés à rendement
nul. Cette sélection de couverture interdit d'extrapoler au TOP10 entier.

## Résultats de la cassure

Parmi les 2 526 fenêtres qualifiées, **2 022 cassures exécutables**, soit environ
80 %, et **504 abstentions**. Les frais simulés sont déjà déduits.

| Année | Direction | Trades | Gagnants nets | Rendement net moyen/trade |
|---|---|---:|---:|---:|
| 2025 | LONG | 595 | 35,46 % | **−0,20 %** |
| 2025 | SHORT | 613 | 28,87 % | **−1,59 %** |
| 2025 | Ensemble | 1 208 | 32,12 % | **−0,91 %** |
| 2026 | LONG | 421 | 31,83 % | **−0,63 %** |
| 2026 | SHORT | 393 | 32,06 % | **−0,90 %** |
| 2026 | Ensemble | 814 | 31,94 % | **−0,76 %** |

Intervalles descriptifs à 95 % par blocs de vingt séances de signaux,
2 000 réplications à graine fixe : **[−1,30 ; −0,34] %** en 2025 et
**[−1,32 ; −0,27] %** en 2026 pour l'ensemble. Les années et plusieurs idées
ont déjà été étudiées : ces intervalles ne recréent pas un holdout vierge.

Contrôle sans chevauchement : pour un symbole, aucune nouvelle position,
dans l'une ou l'autre direction, avant la fin de la fenêtre complète précédente,
même si le TP/SL l'avait terminée plus tôt. Adhésion figée pour les contrôles.

| Année | Occasions indépendantes | Gagnants nets | Rendement net moyen/trade |
|---|---:|---:|---:|
| 2025 | 248 | 33,87 % | **−0,49 %** |
| 2026 | 186 | 24,73 % | **−1,82 %** |

Les blocs ne rendent pas tous les titres indépendants du marché : ils limitent
la fausse multiplication des mêmes trajectoires, sans supprimer tous les liens.

## Contrôles : l'information de direction aide-t-elle ?

Mêmes occasions déclenchées, même prix et heure d'entrée, TP10/SL5 identiques :

| Politique | 2025 : net moyen/trade | 2026 : net moyen/trade |
|---|---:|---:|
| Suivre la première cassure | **−0,91 %** | **−0,76 %** |
| Toujours LONG à la même heure | +0,42 % | +0,05 % |
| Toujours SHORT à la même heure | −1,35 % | −0,63 % |
| Prendre l'inverse de la cassure | −0,02 % | +0,18 % |

La cassure n'améliore pas le contrôle LONG aux mêmes heures. Le LONG systématique
reste lui-même non démontré : intervalles incluant zéro. L'inversion n'est pas
une nouvelle stratégie validée ; elle est peu favorable en 2025 et son apparente
amélioration 2026 ne suffit pas à la promouvoir.

Des contrôles LONG/SHORT à l'ouverture J+1 sont aussi archivés, à la fois sur
toutes les fenêtres qualifiées et appariés aux seules occasions déclenchées.
Ils ne doivent pas être comparés sans préciser lequel de ces périmètres est pris.
Les écarts appariés et leurs intervalles sont dans
`paired-control-comparisons.csv` ; ventilation mensuelle dans `monthly-breakout.csv`.

## Les pertes peuvent dépasser le SL5 %

Le stop n'est pas un prix garanti lorsque le marché ouvre au-delà. La règle
enregistre **102 stops en gap en 2025 et 104 en 2026**, sans plafonner la perte
au seuil. Exemples conservés, et non retirés pour améliorer le résultat :

- MP SHORT, signal du 8 juillet 2025 : entrée le 9 à **30,3656 $** ; ouverture
  du 10 à **48,10 $**, après une dernière clôture 5m de **30,02 $**.
  Perte nette de cette occasion **−58,61 %**. Le daily de recherche confirme
  également l'ouverture à 48,10 $ ; dispersion des ratios de la fenêtre ≈0,20 %.
- SRPT LONG, signal du 24 octobre 2025 : entrée le 27 à **23,72 $**, sortie
  en gap le 4 novembre à **15,24 $**, après dernière clôture 5m à **24,46 $**.
  Perte nette **−35,88 %** ; même ouverture 15,24 $ dans le daily, dispersion
  des ratios ≈0,33 %.

C'est une concordance entre les archives disponibles, pas une certification
indépendante des ticks ou de toutes les opérations sur titres. Pas de clipping
des pertes, pas d'hypothèse d'exécution overnight à un ancien stop.

## Vérifications, versions et limites

Résultat final : `artifacts/research/us_top10_intraday_breakout/20261019-v2/`.

- `protocol.json` : règles et empreintes des sources, figées avant ce replay.
- `snapshot-ready.json`, `snapshot/` : extraction SQL initiale scellée.
- `selected-at-j.parquet` et `sessions.parquet` : sélection et calendrier figés.
- `coverage.parquet`, `coverage-reasons.csv` : chaque occasion, y compris exclue.
- `trades.parquet`, `summary.csv`, `report.json` : détails et bilans.
- `final-audit.json` : **PASS_EXPLORATORY_PARTIAL_COVERAGE**, 13 140 lignes
  stratégie/contrôles et 2 526 fenêtres revérifiées.

La v1 est conservée pour la traçabilité. La v2 réemploie **exactement le même
snapshot SQL**, sans nouvelle donnée ou modification de stratégie. Deux correctifs
techniques : contacts exacts avec des barrières décimales malgré l'arrondi flottant,
et horodatage des sorties intrabar comme intervalle observable de cinq minutes,
sans inventer une heure de fill. Quatre lignes de **contrôles** ont un rendement
ou une issue corrigé ; aucun rendement de la politique BREAKOUT n'a changé.

**22 tests unitaires nouveaux et 96 tests au total** passent sur le groupe de
non-régression lancé, sans le seuil global de couverture du projet qui ne peut
pas être satisfait par cette seule sélection de tests. Un second calcul vectoriel
distinct vérifie chaque sortie, coûts, gap et collision. C'est une seconde
implémentation par le même assistant, pas une revue humaine indépendante.

`observed_at` est l'heure réelle de récupération rétrospective : elle ne prouve
pas la publication historique à la seconde près. Les OHLC 5m ne fournissent ni
bid/ask, ni profondeur, ni ordre des ticks à l'intérieur de la barre. Dividendes,
locates, frais d'emprunt réels et cashflows d'opérations sur titres non simulés.
Les résultats sont donc un diagnostic de prix, pas une promesse de fills live.

## Suite

**Clore cette règle, ne pas l'intégrer en production.** Pas de réglage opportuniste
des bornes ou du TP/SL sur les mois perdants. Une éventuelle expérience différente
nécessiterait une hypothèse distincte et un nouveau GO ; aucun backfill 2024,
appel fournisseur/LLM, entraînement, ordre ou écriture SQL n'a été lancé ici.

Code : `scripts/research/us_top10_intraday_breakout.py` et
`scripts/research/us_top10_intraday_breakout_audit.py`.
Tests : `tests/test_us_top10_intraday_breakout.py`.
