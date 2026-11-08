# Variantes continues Q051 / Q088 — 2021 au 1er octobre 2026

Demande utilisateur : rejouer le portefeuille continu avec Q051, puis ajouter
deux variantes à seuils abaissés. Comparaison au Q088 0,60/0,60 déjà terminé :
capital final6 186,50 USD,+54,66 %, DD−29,65 %,1 254 trades,38,68 % gagnants.

## Trois variantes figées

| Variante | Pool Oracle | Classement LONG | Score strictement supérieur à | AUC calibration minimale | Plafond de risque nouvelles entrées | B4/DD15 et liquidation globale |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Q051_060 | TOP10 %,179 candidats | TOP5 | 0,60 | 0,60 | 1× | Désactivés |
| Q088_050 | TOP20 %,358 candidats | TOP10 | 0,50 | 0,50 | 2× | Activés comme le témoin |
| Q051_050 | TOP10 %,179 candidats | TOP5 | 0,50 | 0,50 | 1× | Désactivés |

Conditions communes :4 000 USD au départ, six mêmes bundles annuels H10 et
univers de1 790 titres. Chaque modèle annuel est entraîné jusqu'à l'année
précédant son année d'entrée. Mapping par année de J+1, y compris le signal de
fin décembre de l'année précédente. Les AUC sont celles de calibration,
disponibles avant le signal, pas les AUC du futur test annuel.

Position complète, risque1,25 %, poids maximal20 %,20 positions, minimum50 USD,
quantités entières. Entrée daily J+1 sans confirmation, SL5 %, sans TP ni
trailing, H10 puis sortie open11. Capacité du compte margin2× ; pour Q051,
le plafond1× est appliqué aux achats, sans rééquilibrage forcé des positions
détenues. Frais8 points de base par opération et financement6,5 % annuel.
Facteurs, corrélation, limites sectorielles, options et GPT désactivés.
Autres règles de répétition/cooldown identiques au portefeuille continu source.
Aucune remise à zéro annuelle du capital, des positions ou des exclusions.

## Sources et contrôles

Les entrées figées du replay v6 sont conservées bit pour bit. Le nouveau
classement est calculé sur les scores archivés complets ; filtrer seulement
les anciens TOP10 LONG ne permettrait pas de reproduire le TOP5 dans un pool
Oracle différent. Les trois sélections sont figées avant tout calcul financier.

Les exports IHM annuels2025 et2026 ont été supprimés depuis le premier replay.
2025 est récupéré dans l'archive de grille scellée ;2026 utilise les prédictions
et leur traçabilité déjà en SQL, en lecture seule. Les poids, folds, disponibilités,
profils et AUC sont vérifiés. Le classement témoin Q088 0,60/0,60 doit reproduire
les5 606 candidatures originales avant d'accepter les nouvelles variantes.
Aucun entraînement, nouvelle inférence ou appel fournisseur.

Des seuils plus faibles peuvent introduire de nouveaux symboles. Seuls leurs
cours manquants dans le jeu de prix source sont lus en SQL et archivés. Les prix
source ne sont pas remplacés. Pour ces nouveaux symboles, l'inventaire5m couvre
l'entrée possible J+1 jusqu'à open11 ; la disponibilité future ne sert jamais
de filtre d'entrée. Les protections daily et limites de couverture sont celles
du replay précédent. Secteurs et opérations sur titres des nouveaux symboles
sont également archivés ; aucun secteur ou événement n'est inventé.

Le témoin Q0512025 autonome doit reproduire le résultat historique+31,67 %,
DD−18,04 %, avant les trois portefeuilles continus. Ce contrôle ne préjuge pas
du rendement de2025 dans un portefeuille qui hérite du capital et des positions
depuis2021.

## Exécution et historique IHM

Programme : `scripts/research/us_winner_continuous_q051_q088_20261108.py`.
Dossier actif : `artifacts/research/us_winner_continuous_q051_q088/20261108-v2`.
Journal : `artifacts/research/us_winner_continuous_q051_q088/launch-20261108-v2.log`.
v1 conserve une préparation interrompue lors de l'export : les dates SQL et CSV
de folds avaient des types différents. Les six archives annuelles v1 sont
relues et revalidées dans v2, avec dates normalisées avant concaténation.
Après préparation/validation, trois processus peuvent calculer les variantes
en parallèle, chacun dans son dossier `cases/<variante>` avec `progress.json`.

Chaque réussite est importée automatiquement dans l'historique IHM, sans
recalcul, avec un libellé indiquant le profil et les seuils. Identifiants prévus :

- `20261108_continu_Q051_060_v1`
- `20261108_continu_Q088_050_v1`
- `20261108_continu_Q051_050_v1`

Le tableau `comparison.csv` rassemble les trois nouveaux résultats et le
témoin Q088. Les bilans annuels, trades, capital engagé, frais, financement,
DD et taux gagnants sont conservés. Les limites de couverture restent visibles.
6 tests passent sur les paramètres, l'inventaire de prix, les dates SQL/CSV et l'import historique.

Sélections figées (candidatures, pas encore des achats exécutés) :

| Année d'entrée | Q051_060 | Q088_050 | Q051_050 |
| --- | ---: | ---: | ---: |
| 2021 | 67 | 2 474 | 907 |
| 2022 | 345 | 2 491 | 1 164 |
| 2023 | 162 | 1 826 | 768 |
| 2024 | 491 | 2 417 | 1 227 |
| 2025 | 557 | 2 321 | 1 095 |
| 2026 au01/10 | 556 | 1 754 | 912 |
| Total | 2 178 | 13 283 | 6 073 |

Les cours de286 nouveaux symboles ont été archivés en complément des300 noms
du jeu de prix source, SPY compris.539 571 lignes daily supplémentaires, sans
nouvelle date de calendrier par rapport au jeu de base. Les5 606 candidatures
du témoin Q088 initial sont reproduites, y compris les années récupérées.

Contrôle financier Q0512025 : PASS,+31,673754444206416 %,
DD−18,039949760727914 %, onze indicateurs reproduits. Les trois simulations
continues sont lancées en parallèle ; les configurations effectives vérifient
les plafonds d'entrée1×/2×, capacité margin2×, contrôleur off/on et frais16bps
aller-retour. Import IHM automatique à la fin de chaque cas.
## Résultats finaux

Les trois variantes sont terminées, sans échec, et présentes dans l'historique
IHM sous les identifiants annoncés. Capital initial4 000 USD, sans remise à zéro
annuelle, mêmes modèles H10. Frais et financement inclus.

| Variante | Capital final USD | Rendement | DD maximal | Gagnants / trades | Taux gagnant | Capital engagé moyen USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q088_060, témoin | 6 186,50 | +54,66 % | −29,65 % | 485/1 254 | 38,68 % | 3 229,12 |
| Q051_060 | 6 361,85 | +59,05 % | −25,94 % | 189/551 | 34,30 % | 1 958,05 |
| Q051_050 | 12 260,32 | +206,51 % | −36,89 % | 432/1 234 | 35,01 % | 5 461,32 |
| Q088_050 | 4 907,72 | +22,69 % | −50,37 % | 938/2 525 | 37,15 % | 5 463,75 |

Q051_050 augmente le rendement et l'exposition, mais aussi le DD. Q051_060 garde
le DD le plus faible de ces quatre profils. Le seuil0,50 dégrade simultanément
le rendement et le DD du Q088. Les deux seuils ont été abaissés ensemble ; ces
tests ne permettent pas d'attribuer l'effet au score ou à l'AUC séparément.
Le taux gagnant ne suffit pas à comparer les rendements et les risques.

Statut des données `INCOMPLETE_COVERAGE` dans chaque cas : protections OHLC daily
sur les séances5m incomplètes ; aucun parcours5m inventé. Les trois imports IHM
sont `completed`, avec badge de couverture incomplète conservé.
Expérience rétrospective ;2025 déjà largement
examinée, pas une validation indépendante ni une certification de parité live.

## Profil Q051 de l'écran mis à jour

À la demande de l'utilisateur le 8 novembre 2026, le choix Q051 de « Profil de
paramètres du backtest » reprend désormais Q051_050 : TOP10 % Oracle → TOP5 LONG,
score strictement > 0,50, filtre AUC activé avec AUC ≥ 0,50. Les autres paramètres
Q051 sont conservés : SL5, open11, position complète, entrée journalière J+1 sans
confirmation, risque 1,25 %, poids 20 %, plafond d'entrée 1×, capacité margin 2×,
B4/DD15 désactivé, frais 8 bps par opération et intérêt annuel 6,5 %.
L'écran affiche la période continue 2021–2026, le rendement et le DD, ainsi que
les limites de couverture. Q088 et config.yaml ne sont pas modifiés. Les sessions
Q051 déjà ouvertes reçoivent une seule fois les nouveaux seuils ; les modifications
manuelles suivantes sont conservées, sauf réapplication explicite du profil.
Les dates et le modèle restent ceux choisis par l'utilisateur : sélectionner ce
profil seul ne recrée pas la succession des six modèles annuels du replay continu.
