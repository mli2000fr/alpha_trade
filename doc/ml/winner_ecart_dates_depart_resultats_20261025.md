# Résultats audit date de départ / capital / état hérité

Les trois replays contrôlés sont terminés et audités le25 octobre2026.
TOP20, position complète, pas de renforcement, cap1x, SL5 sansTP/trailing,
H20/open21, mêmes cours/secteurs/frais et risque B4 de l'expérience ancienne.
Pas des nouveaux scénarios de liquidation/pause DD15. Aucune règle assouplie.

## Reproduction et comparaison

Le témoin juillet2019–décembre2024 est reproduit exactement :4000USD devient
23810,29USD (+495,26%),DD−39,88%,1088 clôtures,22,33% gagnantes.
Au31 décembre2019, son capital était déjà7980,17USD (+99,50%sur2019).
Il possédait aussi six positions et des plans/historiques de risque hérités.

| Départ effectif2020 | Capital au départ2020 | Capital fin2024 | Rendement2020–24 | DD maximal |
|---|---:|---:|---:|---:|
| Compte neuf, ancien comparateur |4000,00USD|5178,78USD|+29,47%|−48,76%|
| Compte continu hérité de2019 |7980,17USD|23810,29USD|+198,37%|−39,88%|
| Compte neuf, capital égal au compte hérité |7980,17USD|39598,15USD|+396,21%|−35,82%|

Le DD de la ligne continue est mesuré sur le replay2019–24 ; son maximum
se situe après2019 (le DD2019 était−15,61%). Les rendements2020–24 sont
recalculés depuis7980,17USD, pas comparés naïvement aux+495,26%sur2019–24.

## Expériences isolées

**Capital à état neuf identique** : changer uniquement le dépôt initial du
compte neuf2020 de4000 à7980,17USD change les trades/sizes/contraintes et le
capital final de5178,78 à39598,15USD.1027 clôtures,227 gains/800 pertes,
22,10% gagnantes, contre609/124/485/20,36% pour le compte neuf4000.
Les seuils absolus et les actions entières rendent les trajectoires non
proportionnelles ; ce n'est pas multiplier simplement le gain par1,995.

**État hérité à capital égal** : le compte neuf7980,17USD n'a ni positions,
plans, garde ni historique de concentration hérités. Il dépasse même le
compte continu. Cet effet est un ensemble non séparable : on ne peut pas
l'attribuer à un titre ou à un seul filtre sans autre contrôle.

**Remise à zéro de la seule garde B4 au31 décembre2019** : conserver cash,
positions, plans et historique de concentration, mais resemer la garde au
capital observé. Résultat strictement identique au témoin23810,29USD. Cette
remise à zéro particulière n'explique donc pas l'écart. Cela ne prouve pas
que tous les risques/historiques de compte sont sans effet.

## Mécanisme documenté, limites de l'attribution

Le minimum notionnel155USD peut interagir avec le budget de risque réduit,
les coûts réservés et les actions entières. La note antérieure montrait
une borne théorique à allocation6%. Les traces réelles2022 des comptes
rejoués ici observent surtout10%, puis50%,100%,25%, et aucune décision
avec plafond théorique de risque sous155USD. Ne pas prétendre que le cas6%
a été mesuré sur ces comptes. Le petit compte4000 n'a pas été retracé avec
les hooks du nouveau replay ; la part exacte de chaque mécanisme n'est
donc pas isolée. Les résultats contrôlés établissent l'effet non linéaire
du capital, pas une causalité exclusive du seuil155USD.

Cette sensibilité au dépôt/date/état de portefeuille fragilise la généralisation
du résultat+495%. Augmenter son capital ne garantit pas ces rendements futurs.
Pas de preuve de fuite de calcul de PnL : le témoin reproduit achats, ventes
et courbe5m de l'archive. Limites de l'expérience d'origine maintenues :
secteurs actuels, univers survivant, couverture future, périodes déjà vues,
pas de parité live complète ni de holdout indépendant.

Rapport :`artifacts/research/us_winner_start_state_audit/20261025-v1/report.json`.
