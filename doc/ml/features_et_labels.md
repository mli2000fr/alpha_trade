# Features, contrats et labels ML

Retour : [références ML](README.md)

## Construction des features

`features.py` calcule d'abord des séries intra-symbole triées par date : rendements, momentum, volatilités, RSI, moyennes/distances, range, ATR/ADX, volume et dynamiques. Les jointures optionnelles ajoutent benchmark, scores, sentiment, macro, fondamentaux et facteurs. `cross_sectional.py` calcule ensuite rangs intra-date et neutralisations sectorielles.

Une feature future ne doit jamais entrer dans `get_feature_columns`. Les colonnes de target, futures returns, labels et dates de sortie sont interdites par les audits Oracle et les contrats généraux.

## Liste et ordre

`get_feature_columns` dérive une liste ordonnée des flags. `compute_features` doit produire exactement ces colonnes. `build_feature_contract` et le fingerprint figent le contrat ; le predict appelle `validate_feature_contract`. Même un réordonnancement est significatif pour un modèle tabulaire exporté.

## Whitelist

La whitelist filtre la matrice finale après calcul et garde l'ordre fourni. Elle ne doit pas filtrer les colonnes structurelles avant les groupby/jointures. Avec LSTM, `force_v1_lstm` limite normalement le feature set ; une whitelist ou un override expert change ce comportement.

## Cross-sectionnel

Les rangs sont calculés dans la coupe du jour, jamais sur toute la période. Les features sector-neutral soustraient la médiane du secteur. Les z-scores fondamentaux utilisent médiane/MAD et clipping. Un secteur manquant reçoit le fallback défini par le code et doit être compté.

## Fixed horizon

Le futur close est obtenu par `groupby(symbol).shift(-H)`. Selon target, le rendement est transformé en binaire, ternaire ou régression ; les seuils et scaling doivent être appliqués après calcul intra-symbole. Les dernières H lignes n'ont pas de label et sont exclues du train, pas remplies à zéro.

## Triple barrier

`TripleBarrierConfig` contient multiples stop/TP, durée et coûts. Le label parcourt le futur autorisé, résout la première barrière et le cas ambigu selon la règle implémentée, puis renvoie classe, rendement net, durée et reason. Ces paramètres sont un contrat d'étiquetage indépendant du lifecycle PROD.

## Targets expérimentales

Excès vs SPY soustrait le benchmark avant normalisation. Intra-sector rank transforme le rendement relatif à la coupe secteur/date. Le ternaire intra-secteur utilise quantiles haut/bas et laisse le centre flat. Chaque variante change la question prédite et interdit de comparer directement des F1 sans contexte.

## Audit

Pour chaque batch conserver taux de NaN avant/après imputation, distribution, constantes, doublons, importance, fingerprint et exemples par date. Les tests doivent couvrir frontières de fenêtre, changement de symbole, date future, split et petite coupe cross-sectionnelle.

