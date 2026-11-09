# Q051 — effet du classement LONG per-symbol sur le taux gagnant annuel

Recomptage du 9 novembre 2026 des deux replays continus existants. Aucun nouveau backtest, entraînement, appel fournisseur ou accès SQL.

## Protocole comparé

- Période du **01/01/2021 au 01/10/2026**, capital initial 4 000 USD, sans remise à zéro annuelle ; modèles annuels identiques.
- Configurations complètes du portefeuille comparées champ par champ : **identiques**. Q051, risque par entrée 1,25 %, poids maximal 20 %, plafond de nouvelles entrées 1×, compte margin de capacité 2×. B4/DD15, régime SPY, budget de volatilité supplémentaire, facteurs, corrélation et limites sectorielles désactivés.
- Position complète, entrée à l’ouverture J+1 sans confirmation, SL5 %, sans TP ni trailing, sortie open11. Frais 8 pb par opération ; financement de portefeuille conservé dans les replays.
- **Avec per-symbol** : TOP10 % Oracle (179 candidats) → TOP5 LONG per-symbol → score strictement >0,50 et AUC de calibration ≥0,50 → risque → Winner.
- **Sans per-symbol** : mêmes 179 candidats Oracle en ordre d’amplitude → risque → Winner ; pas de TOP5 LONG ni de seuil score/AUC.

## Taux de trades gagnants

Un gagnant est un trade clôturé de PnL strictement positif, après frais achat/vente et dividendes affectés au lot. Les intérêts de marge sont débités au portefeuille et ne sont pas répartis artificiellement entre trades. Les positions encore ouvertes ne sont pas comptées comme trades clôturés. Année = année de sortie réelle, heure de New York ; les positions traversant le 31 décembre ne sont pas liquidées artificiellement.

| Année | Avec per-symbol | Gagnants / trades | Sans per-symbol | Gagnants / trades | Écart (points) |
|---|---:|---:|---:|---:|---:|
| 2021 | 33,00 % | 66/200 | 22,91 % | 82/358 | +10,09 |
| 2022 | 28,16 % | 58/206 | 18,84 % | 68/361 | +9,32 |
| 2023 | 40,35 % | 69/171 | 34,44 % | 93/270 | +5,91 |
| 2024 | 36,21 % | 84/232 | 25,59 % | 76/297 | +10,62 |
| 2025 | 35,44 % | 84/237 | 32,05 % | 100/312 | +3,39 |
| 2026 (au 01/10) | 37,77 % | 71/188 | 29,68 % | 92/310 | +8,09 |
| **Total pondéré par les trades** | **35,01 %** | **432/1234** | **26,78 %** | **511/1908** | **+8,23** |

Le taux gagnant est plus élevé avec le classement chaque année. Cela ne signifie pas que le rendement annuel est toujours supérieur : la taille et le nombre des gagnants/perdants, les dates de remplissage et les capitaux réinvestis comptent aussi.

| Année | Rendement avec per-symbol | Rendement sans per-symbol |
|---|---:|---:|
| 2021 | 14,24 % | 16,69 % |
| 2022 | -12,36 % | -36,50 % |
| 2023 | 69,49 % | 111,00 % |
| 2024 | 7,55 % | -26,46 % |
| 2025 | 20,39 % | 31,59 % |
| 2026 | 39,50 % | 76,40 % |

| Ensemble 2021–01/10/2026 | Avec per-symbol | Sans per-symbol |
|---|---:|---:|
| Capital final valorisé | 12260,32 USD | 10675,29 USD |
| Rendement cumulé | +206,51 % | +166,88 % |
| DD maximal intraday | -36,89 % | -74,62 % |
| Titres distincts effectivement tradés | 309 | 256 |
| Trades clôturés perdants | 802 | 1397 |

## Détail par titre

Les fichiers `per-symbol-by-year.csv` et `per-symbol-overall.csv` conservent pour chaque variante et titre : nombre de trades, gagnants, perdants, trades nuls, taux gagnant/perdant et somme de PnL clôturé. Le drapeau `small_sample_lt10` signale moins de dix trades, sans filtrer les résultats. Ce sont les statistiques des titres réellement exécutés, pas de tous les modèles entraînés.

Un titre à 100 % sur un ou deux trades ne démontre pas une prévisibilité stable. Aucune nouvelle liste de titres ni sélection a posteriori n’a été créée. Les taux ne sont ni les AUC des modèles ni leurs taux de classification sur tous les signaux.

## Réserves et vérifications

Les comptes annuels et globaux ont été recalculés depuis `trades.csv` puis rapprochés sans écart avec les bilans natifs. Identité des configurations et des modèles annuels vérifiée. Les variantes modifient aussi la largeur, la composition et l’ordre des candidatures, l’occupation des positions et le parcours du capital : la comparaison ne mesure pas la qualité isolée du classifieur à population et taille figées.

Les deux replays restent exploratoires avec couverture intraday incomplète et protections OHLC daily de secours. Aucun changement de production.

Racine : `artifacts/research/us_q051_per_symbol_winrate/20261109-v1/`. `report.json` contient les empreintes des sources, les paramètres de lecture, les vérifications et tous les chiffres. `annual-comparison.csv` et `annual-by-variant.csv` fournissent les tableaux annuels.
