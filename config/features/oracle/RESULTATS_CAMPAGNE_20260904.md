# Résultats de la campagne d'ablation Oracle Extreme — 2026-09-04

## Verdict

Après les deux vagues, le meilleur profil reste `ablation_09_no_market_relative_regime.json` (140 features). Il améliore à la fois le TOP10 et le TOP20 effectivement consommé par la cascade face à O0, mais son avantage n'est **pas statistiquement établi** une fois le chevauchement des cibles H20 correctement pris en compte.

Les trois combinaisons de la vague 2 n'améliorent pas A09 de façon exploitable. Elles dégradent toutes son TOP10 et son minimum de fold TOP20 ; aucune ne franchit donc le gate fixé avant leur entraînement. A09 ne doit toutefois pas remplacer immédiatement `oracle.json` en production : quatorze variantes ont désormais été comparées sur le même historique, ce qui expose le gagnant au biais de sélection multiple. La prochaine étape est une confirmation out-of-time verrouillée de **A09 contre O0 uniquement**.

## Contrôle de comparabilité

- baseline : Oracle O0 du batch `model-factory-20260903174624-014164`, profil `oracle.json`, 168 features ;
- univers : `ticket_recherche.txt` et `ticket_mid_cap_400.txt` contiennent exactement les mêmes 400 symboles et ont le même SHA-256 ;
- chaque résultat : 482 155 observations OOS labellisées, 390 symboles, 1 386 dates et 11 folds ;
- période OOS : 2018-07-05 à 2024-01-05 ;
- prévalence de la cible Extreme : 19,403 % pour tous les runs ;
- fenêtres : train 504, validation 126, test 126, pas 126, maximum 12 ;
- calibration Oracle : score OOS brut, sans calibration utilisée pour classer les symboles ;
- cible : événement d'amplitude cross-sectionnel D1/D10 à H20, indépendamment du sens.

Le fait que les lignes, dates, symboles, labels et prévalences soient identiques autorise une comparaison appariée date par date.

## Résultats

Les deltas sont exprimés en points de pourcentage par rapport à O0. L'intervalle de confiance est obtenu par bootstrap apparié en blocs contigus de 20 séances sur les 1 386 dates. Ce bloc est nécessaire car deux cibles H20 de dates voisines partagent une grande partie de leur fenêtre future.

| Profil | Features | P@10 | Δ P@10 | P@20 | Δ P@20 | AUC | Minimum fold P@10 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| O0 `oracle.json` | 168 | 46,868 % | — | 40,589 % | — | 0,669 | 42,637 % | Témoin |
| A01 sans rangs XS | 124 | 46,242 % | −0,627 | 40,420 % | −0,169 | 0,661 | 43,137 % | Rejet : les rangs XS sont utiles |
| A02 rangs XS seuls | 44 | 46,736 % | −0,132 | 40,159 % | −0,430 | 0,711 | 44,976 % | Rejet : les features absolues restent utiles |
| A03 socle brut simple | 62 | 45,191 % | −1,677 | 39,377 % | −1,212 | 0,638 | 34,620 % | Rejet fort, instable |
| A04 sans momentum/rendements | 131 | 47,068 % | +0,200 | 40,666 % | +0,077 | 0,692 | 43,706 % | Favorable TOP10, TOP20 non concluant |
| A05 sans tendance/position | 125 | 47,007 % | +0,139 | 40,664 % | +0,075 | 0,705 | 44,436 % | Inconclusif, conserver pour l'instant |
| A06 sans volatilité/range | 138 | 46,086 % | −0,783 | 40,317 % | −0,272 | 0,715 | 44,033 % | Rejet : essentiel pour le haut du classement |
| A07 sans volume/flux | 154 | 46,808 % | −0,060 | 40,477 % | −0,112 | 0,682 | 44,128 % | Légère dégradation TOP20 ; conserver |
| A08 sans RSI/mean-reversion | 146 | 47,005 % | +0,137 | 40,613 % | +0,024 | 0,698 | 44,363 % | Inconclusif, conserver pour l'instant |
| **A09 sans marché/relative/régime** | **140** | **47,116 %** | **+0,247** | **40,711 %** | **+0,122** | **0,697** | **44,291 %** | **Meilleur candidat, gain à confirmer** |
| A10 sans transformations complexes | 128 | 47,069 % | +0,201 | 40,701 % | +0,112 | 0,700 | 44,828 % | Challenger ; TOP20 à la limite de significativité |
| A11 sans z-scores temporels | 146 | 46,532 % | −0,336 | 40,138 % | −0,451 | 0,655 | 42,878 % | Rejet : z-scores temporels importants |

### Intervalles appariés importants

- A09, Δ P@10 : +0,247 point, IC95 % blocs H20 `[-0,127 ; +0,577]` ;
- A09, Δ P@20 : +0,122 point, IC95 % blocs H20 `[-0,103 ; +0,355]` ;
- A10, Δ P@10 : +0,201 point, IC95 % blocs H20 `[-0,186 ; +0,538]` ;
- A10, Δ P@20 : +0,112 point, IC95 % blocs H20 `[-0,066 ; +0,316]` ;
- A04, Δ P@10 : +0,200 point, IC95 % blocs H20 `[-0,114 ; +0,492]` ;
- A04, Δ P@20 : +0,077 point, IC95 % blocs H20 `[-0,096 ; +0,254]`.

Les six intervalles incluent zéro. Il faut donc parler de **signaux favorables**, pas encore de gains prouvés.

## Lecture par famille

### À retirer ou retester en combinaison

- **marché, force relative et interactions de régime** : leur retrait A09 améliore en moyenne le TOP10, le TOP20, l'AUC, le pire fold TOP10 et la dispersion TOP20 ; c'est le signal le plus cohérent, mais il reste à confirmer ;
- **transformations complexes** : A10 est favorable, surtout en TOP10 et en AUC, mais sa confirmation TOP20 reste marginale ;
- **momentum et rendements** : A04 est favorable au TOP10 seulement ; la famille doit être testée après A09, pas supprimée directement.

### À conserver

- rangs cross-sectionnels ;
- features absolues non classées ;
- volatilité et range ;
- volume et flux ;
- z-scores temporels.

### À ne pas trancher encore

- tendance et position du prix ;
- RSI et mean-reversion.

Leur retrait donne un petit gain moyen, mais les intervalles appariés incluent zéro et le TOP20 ne progresse pas de manière fiable.

## Pourquoi l'AUC ne suffit pas

A02 et A06 obtiennent une AUC élevée, respectivement 0,711 et 0,715, tout en détériorant la précision du TOP20. Ce n'est pas contradictoire : l'AUC mesure l'ordre de toutes les observations, alors que la stratégie n'exécute que la queue supérieure quotidienne. La décision doit donc privilégier P@20, puis P@10, la stabilité par fold et enfin l'AUC.

La monotonie par décile du rendement **signé** existante dans le rapport historique est mal adaptée à une cible symétrique D1/D10. Pour cette campagne, la monotonie du taux d'extrêmes et celle de `abs(future_return)` ont été recalculées ; elles sont saturées à 1,0 pour toutes les variantes et ne départagent donc pas les profils.

## Vague 2 — combinaisons

Les trois profils ont été entraînés avec le même protocole que la vague 1 :

1. `combined_12_no_market_regime_no_engineered.json` : union des retraits A09 + A10, 120 features ;
2. `combined_13_no_market_regime_no_momentum.json` : union des retraits A09 + A04, 107 features ;
3. `combined_14_no_market_regime_no_engineered_no_momentum.json` : union A09 + A10 + A04, 93 features, comme test de parcimonie plus agressif.

| Profil | Features | P@10 | Δ P@10 vs O0 | Δ P@10 vs A09 | P@20 | Δ P@20 vs O0 | Δ P@20 vs A09 | AUC | Min. fold P@20 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A09 | 140 | **47,116 %** | +0,247 | — | 40,711 % | +0,122 | — | 0,697 | **37,991 %** | Référence de la vague 2 |
| C12 A09 + sans transformations complexes | 120 | 46,853 % | −0,015 | −0,262 | 40,682 % | +0,093 | −0,028 | **0,707** | 36,857 % | Rejet : queue et pire fold dégradés |
| C13 A09 + sans momentum/rendements | 107 | 46,695 % | −0,174 | **−0,421** | **40,789 %** | **+0,200** | +0,078 | 0,682 | 37,575 % | Rejet : gain TOP20 fragile, perte TOP10 établie face à A09 |
| C14 triple retrait | 93 | 46,946 % | +0,078 | −0,170 | 40,652 % | +0,063 | −0,059 | 0,681 | 37,396 % | Rejet : aucun avantage sur A09 |

### Intervalles appariés contre A09

- C12, Δ P@10 : −0,262 point, IC95 % blocs H20 `[-0,596 ; +0,087]` ; Δ P@20 : −0,028 point, `[-0,222 ; +0,179]` ;
- C13, Δ P@10 : −0,421 point, IC95 % blocs H20 `[-0,794 ; -0,038]` ; Δ P@20 : +0,078 point, `[-0,123 ; +0,272]` ;
- C14, Δ P@10 : −0,170 point, IC95 % blocs H20 `[-0,517 ; +0,233]` ; Δ P@20 : −0,059 point, `[-0,271 ; +0,158]`.

C13 obtient le meilleur P@20 brut de toute la campagne, mais son gain sur A09 est de seulement 0,078 point et son intervalle inclut largement zéro. En parallèle, sa perte TOP10 face à A09 est statistiquement défavorable selon ce bootstrap, et son pire fold TOP20 baisse. Il ne satisfait donc pas le gate préétabli. L'AUC élevée de C12 ne compense pas sa dégradation sur la queue réellement tradée.

## Étape suivante recommandée

Figer deux profils seulement :

1. témoin : `oracle.json` (O0, 168 features) ;
2. challenger : `ablation_09_no_market_relative_regime.json` (A09, 140 features).

Les comparer sur une période out-of-time qui n'a servi ni aux ablations ni au choix des combinaisons. Les métriques de décision restent, dans l'ordre : P@20, stabilité temporelle/blocs H20, minimum par période, P@10, puis AUC. Ne plus essayer de nouvelles combinaisons sur l'historique 2018-2024 avant ce holdout : cela augmenterait le biais de sélection sans fournir de preuve indépendante.

Aucun profil ne doit être promu dans `oracle.json` avant ce contrôle final.
