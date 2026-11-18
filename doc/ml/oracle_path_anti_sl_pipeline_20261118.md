# B + anti-SL : entraînement depuis Pipeline et filtre automatique

Implémentation du 18 novembre 2026. Aucun entraînement de production, appel fournisseur/LLM ou ordre lancé pour ce raccordement. Les tests utilisent des données synthétiques et une base SQLite temporaire. Les résultats historiques de recherche ne sont pas de nouvelles performances validées.

## Entraîner un nouveau batch

Dans **Pipeline → T1. ML Train (hors pipeline quotidien)** :

1. Cocher **Oracle Extreme parcours**, horizon **H10**.
2. Cocher **Bundle Oracle + deux modèles Per-Symbol LONG/SHORT**.
3. Cocher **Volatilité inhabituelle — per-symbol (B)** : 29 variables par titre.
4. Cocher **Ajouter le filtre anti-SL — trajectoire dix séances**.
5. Choisir l’univers complet et les dates d’apprentissage, puis lancer l’entraînement.

La case est cochée par défaut pour le bundle H10/B29, avec possibilité de la décocher. Changer d’horizon ou décocher B la désactive ; revenir à une configuration compatible la coche à nouveau par défaut. Aucun ancien batch n’est converti. Le nombre de variables Oracle reste déterminé par son propre profil : cocher cette case ne force pas 173 variables dans l’Oracle.

Le même batch contient l’Oracle, les modèles LONG/SHORT par titre B et une tête anti-SL commune aux titres. Cette tête n’est pas un modèle par titre. Elle utilise 44 variables : les 29 de B à J et quinze résumés des dix séances passées J−9 à J (delta, pente et écart-type de cinq indicateurs). Sa cible est le **SL initial de 5 % touché pendant la première séance suivant J**. « Dix séances » décrit le passé observé, pas dix séances futures de protection. Cela ne garantit pas d’éviter les stops ultérieurs.

Commande supplémentaire émise par la page : `--oracle-path-anti-sl`, avec `--oracle-path-directional --oracle-path-directional-features compact_volatility --oracle-horizon 10`.

## Apprentissage et calibration

L’entraînement se déroule dans cet ordre : Oracle walk-forward, modèles LONG/SHORT B, puis anti-SL. La tête utilise uniquement les candidats TOP10 % de l’Oracle issus des folds OOF causaux du même batch. Ni prix futurs ni résultat du backtest ne déterminent le pool à J.

Pour une tête de l’année Y : fit avant l’année Y−1, calibration sur Y−1, avec maturité du label strictement antérieure aux coupures. La disponibilité des labels première séance est conservativement fixée à J+2. Au moins 2 000 lignes de fit et 500 de calibration, avec deux classes suffisamment représentées, sont nécessaires. Un historique OOF trop court peut donc empêcher la création d’une tête ; si aucune tête ne peut être entraînée, le batch échoue explicitement.

Le classifieur est un LightGBM léger calibré par Platt. Le seuil du veto est le percentile 90 des risques prédits sur la calibration, figé pour chaque tête annuelle. Ce n’est ni un seuil de probabilité universel, ni une obligation de supprimer exactement 10 % des candidats du jour.

## Utiliser le batch

Exécuter **ML Predict** avec ce nouveau batch et les dates souhaitées. Pour un backtest à entrée J+1, prévoir aussi la séance de signal précédant la première entrée.

Le parcours natif est :

**Oracle → classement LONG per-symbol → TOP choisi → veto anti-SL automatique → risque → Winner.**

Un candidat LONG est exclu si son risque première séance dépasse strictement le seuil de sa tête annuelle. Le filtre intervient après le TOP LONG : il ne remplace pas un titre exclu par le rang suivant. Les seuils LONG/AUC et les paramètres TOP personnalisés du backtest restent appliqués avant ce veto. La tête ne filtre pas les SHORT.

Dans le backtest, sélectionner Winner, le nouveau batch B+anti-SL et le profil **Q051 — B seul, volatilité inhabituelle per-symbol, TOP10**, puis réappliquer le profil. Le modèle déclare automatiquement son anti-SL ; aucune case supplémentaire n’est nécessaire pour l’activer. Les réglages du témoin restent à vérifier : TOP10 % Oracle → TOP10 LONG, score >0,50 et AUC ≥0,50, entrée journalière J+1, position complète, SL5 %, sans TP/trailing/renforcement, open11, sans vol20/régime/B4/DD/facteurs/corrélation/limites sectorielles.

L’en-tête du modèle et le tableau des décisions signalent l’anti-SL automatique ; risque, seuil, statut et exclusion sont affichés. Les exports de classement conservent ces données.

La lecture native de ML Predict, du backtest et du risque, ainsi que le classement personnalisé du service Q051 PAPER, appliquent le veto. Décocher entièrement le classement per-symbol sur un batch anti-SL est refusé. Les routes options/GPT qui repartent du seul score d’amplitude refusent explicitement ce type de batch : elles ne peuvent pas ignorer son veto en silence.

## Absences et intégrité

- Année sans tête causale ou variables insuffisantes : abstention explicite `NO_CAUSAL_MODEL` / `INSUFFICIENT_FEATURES`, candidat B conservé selon le protocole de recherche. Consulter ces statuts avant d’interpréter une couverture anti-SL comme complète.
- Manifeste/poids déclarés manquants ou corrompus, seuil incohérent, date future ou scores non persistés : erreur ; compléter ML Predict ou réparer le batch. Aucun contournement silencieux.
- Batch sans tête déclarée : ancien comportement inchangé.

Les paramètres Winner restent indépendants. La tête a appris un stop de première séance à 5 % : changer le SL ou entrer sur confirmation intraday ne reproduit plus exactement le scénario appris, même si le veto reste automatique.

## Stockage et traçabilité

Sous `artifacts/models/<batch>/oracle_path/anti_sl/` : `manifest.json`, `head-<année>.joblib`, pool OOF et panel d’apprentissage. Le manifeste contient les variables, seuils, dates fit/calibration/disponibilité, empreintes des poids, du protocole Oracle et du manifeste B. Le rapport du batch n’est publié comme terminé qu’après la tête anti-SL.

ML Predict crée/aligne la table **`oracle_path_anti_sl_predictions`** dans la base US et enregistre une ligne par date/titre/batch : risque, seuil, identifiants des modèles/manifeste, disponibilité, statut et empreinte des variables. L’horodatage est écrit en UTC. Ces lignes sont écrites dans la transaction des prédictions directionnelles. Les backtests et lecteurs opérationnels ne créent aucune table et ne recalculent pas les scores manquants.

## Ce qui reste distinct de la production actuelle

Ce raccordement ne change pas `config.yaml`, les comptes, le batch quotidien sélectionné ni les paramètres du profil Q051 PAPER figé. Ce profil reste TOP5 avec vol20 + régime ; sélectionner un batch B+anti-SL lui ajoute le veto, sans le transformer en témoin TOP10 sans protections. La reproduction exacte de B+anti-SL témoin dans un profil quotidien dédié reste une étape séparée.

Les modèles de recherche existants ne sont pas servis automatiquement comme des batchs natifs. Réentraîner via cette option et vérifier le nouveau manifeste. Pour comparer B et B+anti-SL sans changer les poids Oracle/B, conserver le même entraînement de base et documenter le protocole de comparaison ; deux campagnes réentraînées indépendamment ne garantissent pas des poids identiques.
