# Audit de la baisse B + anti-SL10 TOP10 fin 2024 / début 2025

Drawdown intraday : -34.98 %, de 2024-11-11 20:40:00+00:00 à 2025-04-07 13:35:00+00:00.
Attribution distincte en clôture : 2024-11-06 → 2025-04-04, 12764.63 $ → 8414.42 $, soit -4350.20 $ (-34.08 %).
124 trades clôturés, 29.84 % gagnants ; 86 stops dont 14 pendant la séance d'entrée et 72 plus tard. 13 stops sur gap : -1830.47 $ de PnL total de ces trades, pas une attribution indépendante des autres pertes.
Exposition brute/capital moyenne intraday de la fenêtre : 90.19 %. Financement : 0.001558 $. Résidu de rapprochement des flux, marques et dividendes : 0.0000000000 $.

Le modèle anti-SL prédit un SL5 pendant la première séance seulement. Dix séances décrit son historique de features, pas dix séances protégées contre les stops. Il ne garantit ni une absence de gap après la première séance, ni un rendement positif à H10. Les scores sont des estimations non garanties.
La règle SL5 est un seuil de déclenchement ; une ouverture sous ce seuil est exécutée au cours disponible, donc une perte supérieure à 5 % est possible. Le portefeuille continue à prendre de nouvelles entrées : aucun B4/DD, régime ou budget de volatilité ne protège ce témoin.

Les PnL des trades clôturés ne sont pas la variation de capital : celle-ci inclut les positions détenues aux deux bornes. symbol-attribution.csv rapproche exactement les deux. Les secteurs sont ceux du référentiel contemporain, sans garantie historique PIT.
Les gaps de début de séance sont comparés aux ouvertures journalières et aux impressions 5 minutes disponibles ; les gaps intraday aux seules ouvertures des bougies 5 minutes correspondantes. Cela contrôle la cohérence interne, pas une confirmation indépendante par un autre fournisseur. Couverture intraday partielle, repli OHLC, prix révisés, aucune certification live.

## Comparaison sur la même fenêtre

| Cas | Variation de capital | DD clôture dans la fenêtre | Taux gagnant des sorties |
| --- | ---: | ---: | ---: |
| B seul TOP10 | -31.16 % | -38.25 % | 24.44 % |
| B + anti-SL10 TOP10 | -34.08 % | -34.08 % | 29.84 % |
| B + anti-SL10 + vol20/régime TOP10 | -24.58 % | -25.72 % | 29.73 % |
| SPY prix seuls | -14.51 % | -17.56 % | nan % |

Archives : `artifacts\research\us_q051_b_sl10_drawdown_audit\20261117-v2`.


## Répétition des pertes et détail du contrôle existant

ROAD subit sept sorties sur la fenêtre, dont cinq stops, pour -459,81 $ de PnL réalisé. AGYS, DECK et PRIM subissent chacun trois stops. La pause100 expérimentale n'est pas activée dans ce témoin.

Point de sémantique vérifié dans le contrôle natif `execution_engine/winner_live_risk.py::concentration_allowed` : le compteur de pertes consécutives utilise les différences de prix brutes, avant frais. Sur ROAD, le trade du 28 janvier au 11 février 2025 gagne 0,75 $ avant frais, mais perd 2,479 $ net. Il remet donc le compteur natif à zéro après les deux pertes précédentes. L'entrée du 12 février reste autorisée. Un contrôle diagnostique avec frais intégrés la refuserait ; aucun replay de ce changement ni correctif de production n'a été lancé. Ce point n'explique pas à lui seul la baisse et ne permet pas de soustraire les pertes suivantes à rendement constant.

La comptabilité de la fenêtre est rapprochée exactement : -4 350,20 $ dont les cinq premiers contributeurs AGYS, ROAD, MMYT, DECK et ARLO expliquent 50,67 % de la baisse nette. Selon les secteurs contemporains, Industrials et Consumer Cyclical contribuent respectivement -1 944,29 $ et -1 579,35 $. Ce classement ne prouve pas une corrélation historique ni un filtre prédictif.

Le témoin n'est protégé ni par B4/DD, ni par régime SPY, ni par budget de volatilité. La moyenne de l'exposition brute sur capital est 90,19 %, les frais de financement de la fenêtre sont de 0,00156 $ : l'endettement n'explique pas la baisse. Les stops, l'exposition persistante, les réentrées et le manque de trades gagnants dominent.

La comparaison avec SPY (-14,51 % sur les mêmes clôtures) montre un contexte de marché défavorable, mais la stratégie perd déjà du terrain quand SPY reste relativement stable en novembre-décembre 2024. Le marché n'explique donc pas tout ; la sélection et le parcours des titres amplifient la perte. Cette lecture est rétrospective et ne démontre pas un mécanisme d'anticipation.

La nouvelle variante vol20/régime est terminée : -24,58 % sur cette fenêtre, mais -11,83 % sur tout 2021–2026 avec DD intraday -37,36 %. La réduction de cette seule baisse ne suffit pas à valider cette variante.
