# Global Ranking — référence technique

Retour : [références ML](README.md) · [présentation](../07_ml_global_ranking.md)

## Question modélisée

À une date D, classer les symboles selon leur rendement futur relatif au benchmark. Le score final est un percentile intra-date. Ce n'est ni une probabilité calibrée ni une prévision absolue.

## Horizons et cible

Le code entraîne H3, H5, H10, H15 et H20. Pour chaque H, il calcule le rendement futur par symbole, l'excès vs SPY puis un vingtile 0..19 dans chaque date. Les groupes LambdaRank sont les dates. Les horizons fiables 10/15/20 peuvent recevoir le smoothing prévu ; 3/5 restent non lissés selon les constantes.

## Modèles

LightGBM utilise `lambdarank` et un gain ordinal. CatBoost sert de fallback en régression du rang [0,1] avec loss autorisée par config. Les seeds sont dérivés par horizon. La métrique principale est l'IC Spearman OOS par date/fold.

## Features

Les features brutes sont complétées par rangs cross-sectionnels. Les macro globales constantes dans la coupe sont blacklistées. La liste directionnelle optionnelle réduit les features cross-sectionnelles/sectorielles à `DIRECTIONAL_FEATURES`. Les doublons exacts de relative strength vs momentum ne sont pas régénérés comme ranks.

## Secteurs

Les secteurs sont classés cyclical/defensive/other par mots-clés. Les neutralisations soustraient médianes secteur/date ; les fondamentales utilisent MAD robuste. Le mapping est chargé depuis la DB et son absence produit un warning/fallback, pas une jointure future.

## Walk-forward

Les folds partagent le calendrier des autres modèles mais chaque horizon a son modèle. Les prédictions OOS sont concaténées sans retrain sur le test. L'évaluation doit inclure IC médian, gradient quantiles, top-N, couverture, stabilité secteurs et performance après coûts.

## Production

La synthèse choisit un horizon selon la priorité documentée dans l'orchestration. Les rows historiques Global Rank rendent le batch rank-driven. `global_rank_H` est transformé en sortie consommable selon la synthèse ; conserver l'horizon source et ne pas confondre avec `proba_long` brute.

## Pièges

Un IC moyen peut provenir de quelques dates ; un top percentile quotidien impose un turnover ; un univers tronqué change les percentiles ; une feature macro constante ne peut classer ; recalculer les percentiles avec des symboles qui n'étaient pas tradables crée une divergence.

