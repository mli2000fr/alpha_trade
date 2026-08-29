# Recherche de données directionnelles

Retour : [recherche](README.md)

Le sous-package teste si de nouvelles données séparent le bon et le mauvais côté dans le pool Oracle avant d'entraîner un modèle complexe. Les familles actuelles couvrent short interest, news sentiment, earnings revisions et analyst revisions.

`harness.assemble_pool` joint Oracle OOS top20 quotidien aux labels décile/return, folds, année et régime. `analyze_features` calcule médianes D1..D10, BAD5/GOOD5, delta, IC Spearman, AUC direction et amplitude, puis stabilité du signe par fold.

Une feature candidate doit être disponible à J, historisée et jointe as-of. Une API actuelle sans historique de publication ne peut pas être utilisée rétroactivement. Le diagnostic univarié précède CatBoost/LightGBM. Les critères portent sur stabilité multi-fold et direction, pas seulement une AUC moyenne.

Ces scripts n'alimentent pas automatiquement `features.py`. Une feature promue doit obtenir loader, availability contract, tests anti-fuite, config opt-in, fingerprint et replay.

