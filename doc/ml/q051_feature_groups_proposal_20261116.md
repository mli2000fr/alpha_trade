# Q051 — proposition de tests ciblés des variables par titre

Statut : premier lot T0/A/B lancé le 16 novembre 2026 à 16 h 16 Europe/Paris.
Les 431 blocs d’entraînement LONG annuel 2021–2026 et les six replays T0/A/B
sont terminés. Les 9 267 modèles sont conservés et vérifiés ; les six bilans sont
publiés dans l’historique IHM. Résultats comparatifs en fin de note.
Deuxième lot C/D lancé le 16 novembre 2026 à 18 h 46 Europe/Paris.
Entraînement LONG en cours, puis quatre replays C/D avec et sans vol20 + régime.
La référence T0 et les résultats A/B restent inchangés. Production inchangée.

Suivi du deuxième lot : `artifacts/research/us_q051_feature_groups/20261116-lot2-cd/progress.json`.
Archives du premier lot terminé : `artifacts/research/us_q051_feature_groups/20261116-lot1/`.
Détails par bloc : `jobs/<année-bloc>/progress.json` ; logs : `logs/`.
Les six entrées d’historique IHM sont publiées ; voir `history.json`.

## Ce que le test 173 permet de dire

Le paquet 173 a été moins performant que le paquet compact 24 dans le replay
apparié. Cela ne prouve pas que chaque nouvelle variable soit inutile. Ce test
remplaçait le vecteur compact par le vecteur Oracle : seulement 14 noms sont
communs. Plusieurs autres variables ont des équivalents ou des noms différents,
et les trois variations `return_5d_delta5`, `rsi_14_delta5` et
`vol_ratio_20_60_delta5` du compact sont absentes des 173. Le critère de
disponibilité d'au moins 80 % des entrées changeait aussi certains échantillons.

L'expérience suivante doit donc conserver les 24 variables exactes, puis ajouter
un petit groupe à la fois. Les ablations déjà documentées pour l'Oracle
amplitude ne répondent pas à cette question d'ajout au modèle LONG par titre.

## Diagnostic de préparation, pas preuve d'efficacité

Les poids de 128 modèles LONG ont été lus : 32 symboles régulièrement espacés
dans l'ordre alphabétique pour chaque année 2021–2024. Aucun choix fondé sur le
rendement ou sur les années 2025/2026. Les gains d'apprentissage sont normalisés
séparément pour chaque modèle.

Sur cet échantillon, `r_squared_252` est utilisé dans 96,09 % des modèles,
`beta_252` dans 94,53 %, et `rolling_volatility_120_zscore` dans 95,31 %.
`sma50_minus_sma200` et `cmf_20` sont également des candidats utilisés par les
arbres. Une variable utilisée dans l'apprentissage peut être inutile ou nuisible
en test : ces chiffres servent uniquement à préparer les familles à vérifier.

Archives : `artifacts/research/us_q051_feature_groups/20261116-proposal/`.
`inventory.json` conserve les deux listes exactes et les groupes proposés ;
`training-gain-sample.csv` conserve les 128 modèles et leurs gains par variable ;
`training-gain-summary.csv` donne le résumé.

## Groupes figés proposés

| Test | Ajout aux 24 variables | Nombre final | Hypothèse à vérifier |
| --- | --- | ---: | --- |
| T0 | Aucun | 24 | Référence réentraînée sur les mêmes données et dates que les variantes |
| A — lien au marché | `beta_252`, `r_squared_252`, `alpha_252`, `momentum_252_vs_market` | 28 | Le contexte SPY déjà présent dans les 24 devient-il plus utile lorsqu'on connaît la sensibilité du titre au marché ? |
| B — état de volatilité | `rolling_volatility_60`, `rolling_volatility_120`, `rolling_volatility_20_zscore`, `rolling_volatility_60_zscore`, `rolling_volatility_120_zscore` | 29 | L'agitation actuelle, comparée à l'histoire propre du titre, aide-t-elle à sélectionner les LONG qui survivent au SL5 ? |
| C — structure de tendance | `sma20_minus_sma50`, `sma50_minus_sma200`, `ema20_minus_sma20` | 27 | L'organisation des tendances courtes et longues complète-t-elle les pentes déjà utilisées ? |
| D — participation des volumes | `cmf_20`, `volume_ratio_20`, `volume_zscore_20`, `daily_return_times_volume_ratio_20` | 28 | Les volumes accompagnant le prix améliorent-ils la sélection LONG ? Ces indicateurs ne sont pas un relevé réel des ordres acheteurs/vendeurs. |

Les 16 ajouts distincts ont été vérifiés dans la liste Oracle 173 et sont absents
de la liste compacte 24 par leur nom exact. Certains apportent une information
proche de variables existantes ; c'est précisément ce que le test doit mesurer.
Commencer par T0, A et B. C et D peuvent suivre selon le budget de calcul.
Ne pas tester toutes les combinaisons ; au plus une combinaison des deux groupes
qui montrent un apport stable sur la période de développement, figée avant le
contrôle 2025/2026.

## Conditions communes indispensables

- Oracle H10 et scores Oracle figés pour tous les cas ; TOP10 % Oracle → TOP10
  LONG, probabilité strictement >0,50 et AUC de calibration ≥0,50, sans remplissage.
- Seuls les modèles LONG par titre sont réentraînés. Aucun modèle SHORT n'est
  nécessaire à cette question.
- Mêmes prix, cibles SL5/open11, fenêtres annuelles, séparation entraînement /
  calibration, traitement des absences, paramètres LightGBM et calibration.
  Conserver aussi les trois variations sur cinq jours du compact.
- Figer un échantillon commun de dates et de titres admissibles avec des règles
  de disponibilité des entrées connues à J, identiques pour T0/A/B/C/D. Ne pas
  appliquer cinq seuils de disponibilité différents en fonction du nombre de
  colonnes. Les dates futures de résultats ne servent jamais à qualifier une
  entrée au moment de la décision.
- Reprendre le recoupement de prix v3-SIP et ses réserves avant de reconstruire
  les entrées/labels des branches à comparer ; le T0 doit être reconstruit de la
  même manière. Aucun groupe ne doit bénéficier seul d'une réparation de prix.
- Portefeuille continu 4 000 $, sans remise à zéro annuelle : entrée J+1,
  position complète, risque par entrée 1,25 %, poids maximal 20 %, achat plafonné
  à 1× avec capacité margin 2×, SL5 %, sans TP/trailing/confirmation, open11,
  frais/financement identiques. B4, corrélation et limites sectorielles inchangés
  par rapport au protocole de comparaison.
- Développement 2021–2024 avec modèles annuels n'utilisant que leur passé.
  Choix des groupes figé avant le contrôle 2025–1er octobre 2026. Cette dernière
  période a déjà été observée dans nos autres expériences ; elle ne constitue
  pas un nouvel échantillon indépendant. Une confirmation ultérieure en PAPER
  restera nécessaire avant promotion.

## Mesures et décision

Mesurer d'abord AUC, calibration et taux gagnant conditionnellement aux candidats
Oracle TOP10 %, sur populations communes ; fournir aussi un résumé par titre
et par année lorsque les deux classes et les effectifs permettent le calcul.
Mesurer la qualité des TOP10 LONG retenus, leur changement par rapport à T0 et
leur couverture ; ne pas extrapoler une AUC calculée sur tout l'univers.

Rejouer ensuite les portefeuilles avec et sans vol20 + régime en conservant
exactement les autres paramètres. Comparer rendement net, DD, taux gagnant,
gain/perte moyens, capital engagé, nombre de trades et concentration des gains.
Un gain d'AUC seul ne suffit pas à retenir une famille. Chercher une amélioration
répartie dans plusieurs années, non expliquée par un seul titre ou une chute
importante d'exposition ; conserver T0 si le compromis ne s'améliore pas.

Pour approfondir une famille candidate, mesurer son apport sur des blocs de
validation chronologiques avant d'ajuster sa composition. L'importance par
permutation dépend du modèle et du jeu évalué ; les variables corrélées peuvent
masquer leurs contributions individuelles. La suppression/réintroduction d'un
groupe entier avec réentraînement est donc le test économique principal.
Référence : [documentation scikit-learn](https://scikit-learn.org/stable/modules/permutation_importance.html).

<!-- REPLAY_IMPORT_RECOVERY_20261116 -->

## Reprise du lanceur après entraînement

Le premier coordinateur s’est arrêté dans la préparation du marché : il
importait une constante EXT inexistante au lieu de ROOT du module d’extension.
La reprise a aussi corrigé le dossier de garde des écritures locales : les
exports communs sont autorisés dans le seul dossier de cette campagne,
avec SQL toujours en lecture seule. La première exécution sous accès restreint
avait également rencontré un refus sur le canal TLS de l’environnement ; la
reprise autorisée a établi la connexion locale sans retirer cette instrumentation.

Les modèles et les trois sélections ont été conservés : 431 blocs et 9 267
fichiers de poids vérifiés, zéro réentraînement. Le protocole original et les
journaux d’échec sont préservés. Les quatre tests ciblés passent, dont la
conservation des valeurs des 24 entrées, la causalité des variables, le contrôle
d’import avant SQL et le périmètre de garde des écritures.

Reprise : `scripts.research.us_q051_feature_groups_resume_20261116`.
Journal courant : `resume-final.stderr.log` ; suivi : `progress.json`.
Aucun rendement final n’est disponible à ce stade.

<!-- Q051_FEATURE_GROUPS_LOT1_RESULTS_20261116 -->

# Q051 — ajouts ciblés aux 24 variables : premier lot terminé

Six replays terminés et publiés dans l’historique IHM. Production inchangée.
2021-01-01–2026-10-01, capital continu 4 000 $, Oracle TOP10 % → TOP10 LONG, probabilité >0,50 et AUC de calibration ≥0,50, sans remplacement.
Entrée J+1, position complète, SL5/open11, sans TP/trailing/confirmation/B4 ; plafond d’achat 1×, capacité margin 2× ; frais et financement inclus.

| Profil | Capital final | Rendement | DD max | Taux gagnant | Trades | Capital engagé moyen |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 24 — témoin | 9162.34 $ | +129.06 % | -39.12 % | 34.23 % | 1420 | 5475.08 $ |
| 24 + marché — témoin | 10408.83 $ | +160.22 % | -32.96 % | 35.47 % | 1418 | 6558.37 $ |
| 24 + volatilité — témoin | 15894.14 $ | +297.35 % | -40.99 % | 37.63 % | 1419 | 6401.43 $ |
| 24 — vol20 + régime | 6652.63 $ | +66.32 % | -21.25 % | 36.53 % | 1136 | 2185.46 $ |
| 24 + marché — vol20 + régime | 5229.86 $ | +30.75 % | -28.94 % | 33.70 % | 1101 | 1994.78 $ |
| 24 + volatilité — vol20 + régime | 3780.78 $ | -5.48 % | -41.91 % | 35.69 % | 1076 | 1667.39 $ |

## Lecture

A (bêta, R², alpha et momentum relatif au marché sur 252 séances) améliore le témoin simple : +160,22 % contre +129,06 %, DD −32,96 % contre −39,12 %.
B (cinq variables de volatilité longue et normalisée) augmente davantage le rendement simple : +297,35 %, mais le DD se dégrade à −40,99 %.
Avec vol20 + régime, A et B font moins bien que T0 à la fois en rendement et en DD : conserver les 24 variables pour ce profil à ce stade.
Les expositions brutes moyennes rapportées au capital courant sont proches entre témoins simples (environ 88 %) et entre cas protégés (environ 46 %).
Les trois références ont été réentraînées sur une population et des lignes communes ; ces chiffres ne remplacent pas rétroactivement les anciennes références à 24 variables.

## Rendements annuels

| Année | T0 témoin | A témoin | B témoin | T0 vol20/régime | A vol20/régime | B vol20/régime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | +5.82 % | +26.53 % | -13.17 % | -11.27 % | +11.93 % | -9.60 % |
| 2022 | -9.20 % | +10.64 % | +46.16 % | +3.31 % | -5.28 % | -14.83 % |
| 2023 | +67.36 % | +44.03 % | +46.95 % | +29.56 % | +4.35 % | +24.83 % |
| 2024 | +28.26 % | +2.23 % | +12.13 % | +3.93 % | +0.68 % | -14.77 % |
| 2025 | -14.20 % | +31.68 % | +14.04 % | -2.34 % | -5.84 % | +1.91 % |
| 2026 | +29.44 % | -4.13 % | +66.61 % | +37.97 % | +24.67 % | +13.22 % |

## Contrôles et limites

431 blocs et 9 267 modèles LONG vérifiés après entraînement ; les trois branches partagent les mêmes lignes fit/calibration, avec 24, 28 et 29 entrées.
Quatre tests ciblés passent. Les six bilans passent les vérifications de PnL, de capital annuel et de drawdown. Les prix d’exécution communs sont figés avant les replays.
Qualification ciblée de prix : **OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY**, réserves observées : 0. Voir `price-window-validation.json` (positions clôturées et ouvertes).
Cette revue porte uniquement sur la liste préexistante de titres signalés et ses fenêtres réellement détenues, pas sur la qualification de tout le corpus.
Intraday partiel avec repli OHLC, prix historiques révisés et unités ajustées, univers contemporain. Aucune certification PIT ni parité d’exécution live.
Les années 2021–2026 ont déjà été explorées dans d’autres expériences ; pas de nouvelle validation indépendante. Les gains observés ne justifient pas une activation automatique.
La contre-performance sous vol20 + régime ne permet pas à elle seule de séparer l’effet du budget de volatilité de celui du filtre de régime.
Les erreurs de préparation ont été corrigées sans réentraînement ; anciens protocoles et journaux conservés. Aucune modification de production, aucun ordre, appel fournisseur/LLM ou écriture SQL.

Archives : `artifacts/research/us_q051_feature_groups/20261116-lot1/`.
Courbes : `capital-comparison.png`. Détails : `comparison.csv`, `annual-comparison.csv`, `classification-by-year.csv`, `history.json`.

<!-- Q051_FEATURE_GROUPS_CD_LAUNCHED_20261116 -->

## Deuxième lot C/D lancé

C ajoute `sma20_minus_sma50`, `sma50_minus_sma200` et `ema20_minus_sma20`
aux 24 entrées exactes : 27 variables. D ajoute `cmf_20`, `volume_ratio_20`,
`volume_zscore_20` et `daily_return_times_volume_ratio_20` : 28 variables.
Chaque variante est testée séparément, avec et sans budget de volatilité 20 %
et filtre de régime. Période 2021–1er octobre 2026, capital continu 4 000 $,
Oracle TOP10 % → TOP10 LONG, score >0,50/AUC calibration ≥0,50,
SL5/open11 et autres réglages du premier lot inchangés.

La référence T0 n’est pas réentraînée. Les dates et les valeurs de ses entrées
sont reproduites pour chaque titre, et les signatures fit/calibration doivent
correspondre exactement. Les modèles C/D sont entraînés uniquement dans la
cohorte des modèles T0 déjà qualifiés ; une calibration constante propre à une
nouvelle variante produit une abstention documentée, sans élargir les candidats.
Le masque de disponibilité utilisé au premier lot est conservé.

Huit tests préalables passent. Le premier bloc réel produit 14 modèles C/D et
reproduit les prédictions T0 sans différence, sur les mêmes dates de scoring.
Les modèles et les anciens résultats du premier lot sont préservés.
Les réponses intraday vides déjà connues du premier lot ne sont pas remplies
rétroactivement ; seuls les nouveaux couples titre/séance sont lus en SQL,
dans une transaction lecture seule. Aucun appel fournisseur/LLM, ordre ou
changement de configuration/modèle de production.

Lanceur : `scripts.research.us_q051_feature_groups_cd_20261116 --phase all`.
Suivi : `artifacts/research/us_q051_feature_groups/20261116-lot2-cd/progress.json`.
Les modèles et audits sont dans `jobs/`, les sorties dans `variants/C` et
`variants/D`. Les quatre nouveaux backtests seront publiés dans l’historique
IHM après validation et consolidés avec T0/A/B dans le bilan final.
Aucun rendement final C/D n’est encore disponible au lancement.

<!-- Q051_FEATURE_GROUPS_AB_LAUNCHED_20261116 -->

## Variante complémentaire A+B — témoin uniquement

Lancée le 16 novembre 2026 à 18 h 59 Europe/Paris, en parallèle de C/D.
Un nouveau modèle LONG par titre reçoit les 24 entrées compactes exactes,
les quatre variables marché A et les cinq variables volatilité B : 33 variables
uniques. Il ne s’agit pas d’une moyenne de scores ni d’une addition de rendements.

Une seule variante économique est prévue : témoin sans vol20 ni filtre de régime,
2021–1er octobre 2026, 4 000 $ continus, TOP10 % Oracle → TOP10 LONG,
score >0,50 et AUC calibration ≥0,50, SL5/open11 et autres réglages du premier
lot inchangés. Les références T0, A et B sont réutilisées sans réentraînement.
Les dates fit/calibration et les valeurs des entrées communes doivent être
identiques à T0 ; ses prédictions sont vérifiées pour chaque modèle annuel.

Douze tests ciblés passent après validation de l’accès local aux liens de fichiers.
Le pilote réel produit sept modèles AB et reproduit T0 sans écart. Deux processus
entraînent le lot, puis un seul replay AB_SIMPLE est enchaîné. Les publications
IHM partagent le verrou de fichier des cas C/D pour éviter des écritures concurrentes.
Le lot C/D et ses sources restent inchangés. Aucun ordre, appel fournisseur/LLM,
écriture SQL ou changement de production.

Lanceur : `scripts.research.us_q051_feature_groups_ab_20261116 --phase all`.
Suivi : `artifacts/research/us_q051_feature_groups/20261116-lot3-ab-temoin/progress.json`.
Le bilan comparera T0/A/B/AB après validation. Aucun résultat économique AB
n’est encore disponible au lancement.

<!-- Q051_FEATURE_GROUPS_CD_RESULTS_20261116 -->

# Q051 — C/D après T0/A/B

Quatre nouveaux replays C/D terminés, comparés aux six résultats T0/A/B conservés. Aucun réentraînement de la référence.
2021-01-01–2026-10-01 ; 4 000 $ continus ; TOP10 % Oracle → TOP10 LONG ; score >0,50 ; AUC calibration ≥0,50 ; sans remplacement.
Entrée J+1, SL5/open11, position complète, aucun TP/trailing/confirmation/B4 ; plafond achat 1×, capacité margin 2× ; frais et financement inclus.

| Variables | Gestion | Capital final | Rendement | DD max | Gagnants | Capital engagé moyen |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 24 — référence | Témoin | 9162.34 $ | +129.06 % | -39.12 % | 34.23 % | 5475.08 $ |
| 24 — référence | Vol20 + régime | 6652.63 $ | +66.32 % | -21.25 % | 36.53 % | 2185.46 $ |
| 24 + marché | Témoin | 10408.83 $ | +160.22 % | -32.96 % | 35.47 % | 6558.37 $ |
| 24 + marché | Vol20 + régime | 5229.86 $ | +30.75 % | -28.94 % | 33.70 % | 1994.78 $ |
| 24 + volatilité | Témoin | 15894.14 $ | +297.35 % | -40.99 % | 37.63 % | 6401.43 $ |
| 24 + volatilité | Vol20 + régime | 3780.78 $ | -5.48 % | -41.91 % | 35.69 % | 1667.39 $ |
| 24 + structure de tendance | Témoin | 7626.59 $ | +90.66 % | -43.66 % | 35.43 % | 4113.63 $ |
| 24 + structure de tendance | Vol20 + régime | 4972.47 $ | +24.31 % | -21.61 % | 36.12 % | 1877.76 $ |
| 24 + volumes | Témoin | 6933.40 $ | +73.33 % | -39.88 % | 33.56 % | 4822.82 $ |
| 24 + volumes | Vol20 + régime | 5963.11 $ | +49.08 % | -22.07 % | 34.95 % | 2189.87 $ |

## Méthode et limites

C ajoute trois écarts entre moyennes mobiles (27 entrées), D quatre indicateurs de volume (28). Les deux conservent les 24 entrées exactes du compact.
Pour chaque titre et année, les dates et valeurs communes sont comparées au premier lot, les signatures fit/calibration sont identiques et les probabilités T0 sont reproduites à 1e-12 près.
Seule la population disposant déjà d’un modèle T0 qualifié est utilisée. Une éventuelle calibration constante de C ou D produit une abstention propre à cette variante, comptabilisée dans les audits.
Les archives du premier lot sont inchangées. Les nouvelles requêtes SQL de préparation sont en lecture seule et ne remplissent pas rétroactivement ses réponses vides connues.
Qualification ciblée des fenêtres de prix C/D : PRICE_RESERVES_REMAIN ; réserves : 3. Voir `price-window-validation.json`.
L’intraday reste partiel avec repli OHLC. Univers contemporain, cours révisés et période déjà explorée : aucune certification PIT, parité live ou validation future indépendante.
Aucun ordre, appel fournisseur/LLM ou changement du modèle/configuration de production.

Archives : `artifacts/research/us_q051_feature_groups/20261116-lot2-cd/`. Détails : `comparison.csv`, `annual-comparison.csv`, `capital-comparison.png`, `history.json`.

<!-- Q051_FEATURE_GROUPS_AB_RESULTS_20261116 -->

# Q051 témoin — ajout conjoint de A et B

Un seul nouveau modèle LONG à 33 variables : les 24 entrées exactes + les quatre variables marché A + les cinq variables volatilité B.
Aucune moyenne des scores existants et aucune addition des rendements. Modèles annuels passés, même Oracle, cohorte T0, dates fit/calibration et seuils.
2021–1er octobre 2026, 4 000 $ continus, TOP10 % Oracle → TOP10 LONG, score >0,50/AUC calibration ≥0,50 ; SL5/open11 ; sans TP/trailing/confirmation/B4/vol20/régime ; plafond achat 1×, capacité margin 2× ; frais inclus.

| Modèle | Capital final | Rendement | DD max | Gagnants | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| 24 — référence | 9162.34 $ | +129.06 % | -39.12 % | 34.23 % | 1420 |
| 24 + marché | 10408.83 $ | +160.22 % | -32.96 % | 35.47 % | 1418 |
| 24 + volatilité | 15894.14 $ | +297.35 % | -40.99 % | 37.63 % | 1419 |
| 24 + marché + volatilité | 9923.95 $ | +148.10 % | -42.76 % | 36.42 % | 1436 |

Contrôle de prix ciblé : OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY, réserves : 0.
Les références T0/A/B et le lot C/D ne sont pas modifiés. Intraday partiel avec repli OHLC, univers contemporain, prix révisés et période déjà explorée ; aucune certification PIT ou parité live.
Aucun ordre, appel fournisseur/LLM, écriture SQL ou changement de production.
Archives : `artifacts/research/us_q051_feature_groups/20261116-lot3-ab-temoin/`. Détails : `comparison.csv`, `annual-comparison.csv`, `validation.json`, `capital-comparison.png`.
