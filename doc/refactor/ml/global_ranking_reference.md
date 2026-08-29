# Global Ranking — référence technique

Retour : [références ML](README.md) · [présentation](../07_ml_global_ranking.md)

## Question modélisée

À une date D, classer les symboles selon leur rendement futur relatif au benchmark. Le score final est un percentile intra-date. Ce n'est ni une probabilité calibrée ni une prévision absolue.

## Horizons et cible

Le code entraîne H3, H5, H10, H15 et H20. Pour chaque H, il calcule le rendement futur par symbole, l'excès vs SPY puis un vingtile 0..19 dans chaque date. Les groupes LambdaRank sont les dates. Les horizons fiables 10/15/20 peuvent recevoir le smoothing prévu ; 3/5 restent non lissés selon les constantes.

La cible n’est définie que si symbole et benchmark possèdent les closes futurs nécessaires. Les fins de série sont donc naturellement non labellisées. La taille minimale de groupe doit être surveillée : un vingtile sur une coupe trop petite n’a pas la même résolution.

## Modèles

LightGBM utilise `lambdarank` et un gain ordinal. CatBoost sert de fallback en régression du rang [0,1] avec loss autorisée par config. Les seeds sont dérivés par horizon. La métrique principale est l'IC Spearman OOS par date/fold.

Le code sait construire plusieurs estimateurs selon les bibliothèques disponibles. Un fallback ne doit pas conserver le même nom de modèle ou être comparé comme s’il optimisait exactement la même loss. Type, hyperparamètres, version de librairie et seed appartiennent aux métadonnées.

## Features

Les features brutes sont complétées par rangs cross-sectionnels. Les macro globales constantes dans la coupe sont blacklistées. La liste directionnelle optionnelle réduit les features cross-sectionnelles/sectorielles à `DIRECTIONAL_FEATURES`. Les doublons exacts de relative strength vs momentum ne sont pas régénérés comme ranks.

`_prepare_global_ranking_frame` réalise la préparation commune ; `_get_ranking_feature_columns` décide les colonnes. Toute feature ajoutée doit être disponible PIT, varier utilement dans la coupe et être incluse dans le fingerprint. Une feature très prédictive temporellement mais constante entre symboles ne peut pas classer la coupe du jour.

## Secteurs

Les secteurs sont classés cyclical/defensive/other par mots-clés. Les neutralisations soustraient médianes secteur/date ; les fondamentales utilisent MAD robuste. Le mapping est chargé depuis la DB et son absence produit un warning/fallback, pas une jointure future.

Une catégorie inconnue ou un secteur trop petit réduit la qualité de la neutralisation. Publier couverture sectorielle, tailles de groupes et proportion `UNKNOWN`. Une taxonomie modifiée change la feature engineering et doit versionner le batch.

## Walk-forward

Les folds partagent le calendrier des autres modèles mais chaque horizon a son modèle. Les prédictions OOS sont concaténées sans retrain sur le test. L'évaluation doit inclure IC médian, gradient quantiles, top-N, couverture, stabilité secteurs et performance après coûts.

`compute_cross_sectional_ic` travaille par date, tandis que `compute_ic_rank` calcule la corrélation de rang. Le rapport doit montrer nombre de dates valides, moyenne, médiane, dispersion et proportion d’IC positifs. `_compute_decile_spread` complète par top, bottom et spread.

## Production

La synthèse choisit un horizon selon la priorité documentée dans l'orchestration. Les rows historiques Global Rank rendent le batch rank-driven. `global_rank_H` est transformé en sortie consommable selon la synthèse ; conserver l'horizon source et ne pas confondre avec `proba_long` brute.

`predict_global_rank` doit réappliquer exactement colonnes, transformations, mapping secteurs et ordre du modèle entraîné. La sortie quotidienne est relative à la population scorée. En cas de couverture partielle, publier le ratio et éviter de comparer directement ses percentiles à une journée full.

La persistance dans `global_rank_history` permet l’as-of et rattache batch, date, symbole, horizon/rank selon le schéma courant. Les consumers doivent filtrer batch et horizon, pas sélectionner un simple maximum de date transversal.

## Pièges

Un IC moyen peut provenir de quelques dates ; un top percentile quotidien impose un turnover ; un univers tronqué change les percentiles ; une feature macro constante ne peut classer ; recalculer les percentiles avec des symboles qui n'étaient pas tradables crée une divergence.

## Checklist

1. Univers PIT et benchmark complets.
2. Targets futurs construits uniquement pour le train.
3. Groupes par date conservés.
4. Features variables dans la coupe et disponibles au cutoff.
5. Folds chronologiques sans retrain sur test.
6. IC par date, spreads et turnover publiés.
7. Horizon source explicite.
8. Batch, mapping secteur et feature contract versionnés.
9. Inference avec même pipeline de transformation.
10. Couverture quotidienne surveillée.
