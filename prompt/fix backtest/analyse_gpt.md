# Analyse du backtest

## Observation

La courbe présente une baisse importante entre novembre 2021 et juin 2022. Cette période correspond à un changement de régime de marché marqué par la hausse des taux d'intérêt, la fin des mesures de soutien post-Covid, une forte correction des valeurs de croissance et une augmentation de la volatilité.

Cependant, il est important de vérifier si la baisse est réellement liée au contexte macroéconomique ou à une faiblesse structurelle de la stratégie.

## Analyses à effectuer

### 1. Étudier les trades perdants
- Identifier les actifs les plus contributeurs aux pertes.
- Identifier les signaux les moins performants.
- Mesurer la concentration des pertes.
- Mesurer l'exposition moyenne.

### 2. Ajouter un filtre de tendance
- Trader uniquement lorsque l'indice de référence est au-dessus de sa MM200.
- Réduire ou stopper les nouvelles positions lorsque l'indice passe sous cette moyenne.

### 3. Adapter la taille des positions à la volatilité
- Réduire automatiquement l'exposition lorsque la volatilité augmente.

### 4. Mettre en place un circuit breaker
- Drawdown > 10 % : exposition divisée par 2.
- Drawdown > 15 % : passage temporaire en cash.

### 5. Diversifier les signaux
- Momentum.
- Trend following.
- Mean reversion.
- Breakout.

### 6. Vérifier le surapprentissage
- Nombre de paramètres optimisés.
- Validation hors échantillon.
- Robustesse temporelle.

### 7. Ajouter des filtres macro
- VIX.
- Inflation.
- Taux directeurs.
- Courbe des taux.

## Plan d'action recommandé

1. Extraire les trades de novembre 2021 à juin 2022.
2. Calculer :
   - taux de réussite ;
   - profit factor ;
   - drawdown ;
   - exposition moyenne.
3. Tester un filtre MM200.
4. Tester un dimensionnement basé sur la volatilité.
5. Comparer les résultats.

## Conclusion

Les filtres de tendance et la gestion dynamique du risque sont généralement les leviers les plus efficaces pour réduire ce type de drawdown prolongé.
