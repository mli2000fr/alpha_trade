# Résultats de la campagne d'ablation Oracle Extreme — 2026-09-04

## Verdict

Le meilleur profil moyen de cette vague est `ablation_09_no_market_relative_regime.json` (140 features). Il améliore à la fois le TOP10 et le TOP20 effectivement consommé par la cascade, mais son avantage n'est **pas statistiquement établi** une fois le chevauchement des cibles H20 correctement pris en compte.

Elle ne doit toutefois pas remplacer immédiatement `oracle.json` en production. Onze variantes ont été comparées sur le même historique : le gagnant est donc exposé au biais de sélection multiple. Il faut d'abord tester les combinaisons proposées plus bas, puis effectuer une confirmation out-of-time verrouillée.

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

## Vague suivante recommandée

Créer seulement trois nouveaux profils à partir d'O0 :

1. `combined_12_no_market_regime_no_engineered.json` : union des retraits A09 + A10, 120 features ;
2. `combined_13_no_market_regime_no_momentum.json` : union des retraits A09 + A04, 107 features ;
3. `combined_14_no_market_regime_no_engineered_no_momentum.json` : union A09 + A10 + A04, 93 features, comme test de parcimonie plus agressif.

Conserver strictement le même univers et les mêmes fenêtres. Comparer chaque combinaison à O0 et à A09, avec P@20 comme métrique principale. Ne garder une combinaison que si elle ne dégrade ni le P@20 moyen ni le minimum par fold.

Après cette vague, figer un seul profil et le comparer à O0 sur une période out-of-time non utilisée pour la sélection des ablations. Aucun profil ne doit être promu dans `oracle.json` avant ce contrôle final.
