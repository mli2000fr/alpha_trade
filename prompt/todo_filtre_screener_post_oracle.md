# TODO — Audit et règles screener PIT après Oracle Extreme

## Prompt autonome de recherche et d’intégration éventuelle

> Ce document décrit une expérience indépendante du ranker conditionnel. Le but
> est de savoir si des informations screener disponibles à la date de décision
> permettent de filtrer ou d’orienter le TOP20 Oracle. Le code source, les tables,
> les migrations et les artefacts sont prioritaires sur les documents anciens.

---

## 1. Mission

À partir du pool TOP20 % produit par Oracle Extreme, auditer les scores et
composants screener réellement disponibles en PIT afin de déterminer s’il existe
des règles simples, stables et interprétables qui :

- enrichissent les vrais événements haussiers pour une branche LONG ;
- enrichissent les vrais événements baissiers pour une branche SHORT ;
- ou éliminent des faux extrêmes sans supprimer excessivement les gagnants.

Architecture étudiée :

```text
univers complet
    ↓
Oracle Extreme OOF
    ↓
TOP20 % Oracle
    ↓
règles screener PIT LONG et SHORT, distinctes
    ↓
candidats autorisés / abstention
```

Cette mission ne doit ni entraîner le ranker conditionnel de l’autre prompt, ni
modifier la cascade actuelle avant un GO explicite.

---

## 2. Séparer deux catégories de filtres

### 2.1 Filtres de tradabilité

Ils ne prétendent pas prédire la direction :

- symbole tradable et barres disponibles ;
- prix minimum ;
- volume/dollar volume ;
- spread maximum ;
- market cap minimum ;
- fraîcheur des données ;
- corporate action ou donnée invalide.

Ces règles peuvent être appliquées en amont à l’univers tradable canonique, à
condition que le même contrat soit utilisé pour calculer les percentiles Oracle.

### 2.2 Filtres prédictifs directionnels

Ils sont testés uniquement après la constitution du TOP20 Oracle : tendance,
relative strength, VCP, score composite, short score, volatilité, proximité du
plus haut, earnings, etc. Leur but est de modifier la probabilité conditionnelle
de hausse ou de baisse.

Ne jamais mélanger une amélioration due à la liquidité avec une amélioration de
la prédiction du sens. Publier les résultats des deux couches séparément.

---

## 3. Sources et colonnes à auditer

Inspecter au minimum :

- `modelFactory/features.py` ;
- `modelFactory/data_loader.py` ;
- `modelFactory/oracle/dataset.py` ;
- `modelFactory/shared_directional.py` ;
- modules `screener/`, `selector/` et backfills PIT ;
- `stock_scores_history` et tables historiques associées ;
- migrations/SQL correspondants ;
- configuration des capital presets ;
- tests de disponibilité temporelle.

Le code expose notamment, sous réserve de confirmation par les tables réelles :

- `selector_trend_score` ;
- `selector_vcp_score` ;
- `selector_final_score` et `selector_raw_final_score` ;
- `selector_selection_rank` ;
- `selector_atr_pct_20` ;
- `selector_weekly_trend_score` ;
- `selector_high_52w_proximity` ;
- `selector_volatility_ratio` ;
- `selector_earnings_blackout` ;
- `selector_market_cap` ;
- `selector_beta_126` ;
- `selector_spread_bps` ;
- `selector_days_to_earnings` ;
- `selector_normalized_total_score` et `selector_normalized_rsi` ;
- scores neutralisés secteur ;
- `selector_relative_strength_index_neutralized` ;
- composants tendance/VCP/RSI ;
- `selector_short_score` ;
- composants sentiment, entreprise, macro, quant et secteur lorsqu’ils sont
  réellement PIT et suffisamment couverts.

Cette liste n’est pas une autorisation d’utilisation. Pour chaque colonne,
produire une fiche indiquant : source, formule, timestamp, date de disponibilité,
couverture, historique, valeurs par défaut et risques de fuite.

Attention : plusieurs features manquantes sont actuellement susceptibles d’être
remplies par `0.0` dans certaines constructions. Un zéro technique ne doit pas
être interprété comme une observation screener réelle. Conserver un indicateur
de présence et auditer la donnée brute avant toute règle.

---

## 4. Population et outcomes

Utiliser exactement le même pool conditionnel que les expériences Oracle :

1. prédictions Oracle strictement OOF ;
2. percentile calculé dans la population quotidienne canonique ;
3. TOP20 % retenu avant les règles directionnelles ;
4. jointure as-of/PIT avec le dernier screener disponible ;
5. absence de fallback futur ou de snapshot courant appliqué au passé.

Commencer par H3 pour rester comparable à E2-B. Conserver pour chaque événement :

- rendement brut futur H3 ;
- rendement excess-SPY et résiduel secteur pour diagnostics ;
- `TRUE_LONG = rendement brut H3 >= +3 %` ;
- `TRUE_SHORT = rendement brut H3 <= -3 %` ;
- zone intermédiaire ;
- MFE/MAE seulement si elles sont calculées avec un contrat séparé et jamais
  utilisées comme feature.

Ne pas redéfinir « vrai haussier » et « vrai baissier » après consultation des
résultats.

---

## 5. Question statistique correcte

Pour chaque feature screener `S`, mesurer :

```text
P(TRUE_LONG | Oracle TOP20, tranche de S)
P(TRUE_SHORT | Oracle TOP20, tranche de S)
E[rendement H3 | Oracle TOP20, tranche de S]
```

Comparer à :

```text
P(TRUE_LONG | Oracle TOP20)
P(TRUE_SHORT | Oracle TOP20)
E[rendement H3 | Oracle TOP20]
```

Les résultats doivent être pondérés/agrégés par date pour éviter que les journées
ayant davantage de lignes dominent l’analyse. Toujours publier support, nombre
de dates, nombre de symboles et couverture réelle.

Une règle n’est intéressante que si elle améliore une probabilité conditionnelle
hors échantillon. Une corrélation calculée sur toute l’histoire ne suffit pas.

---

## 6. Phase A — Audit descriptif sans créer de règles

Pour chaque colonne valide :

1. couverture globale, par année et par semestre ;
2. quantiles et valeurs aberrantes ;
3. nombre de valeurs distinctes ;
4. stabilité de la définition dans le temps ;
5. taux de zéros et distinction zéro réel/zéro imputé ;
6. latence entre `as_of` et date de décision ;
7. relation univariée avec TRUE_LONG, TRUE_SHORT et rendement ;
8. courbe par déciles/quintiles ;
9. résultats par régime, secteur et tranche d’amplitude Oracle ;
10. redondance/corrélation avec les features techniques déjà présentes.

Produire des tables de fiabilité lisibles, par exemple :

| Feature | Tranche | Support | Dates | P(LONG) | Lift LONG | P(SHORT) | Lift SHORT | Rendement H3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

Ne sélectionner aucun seuil pendant cette phase.

---

## 7. Phase B — Découverte de règles sur train uniquement

La découverte doit être chronologique et imbriquée :

```text
train : découvre les seuils candidats
validation : choisit ou rejette la règle
test : mesure une seule fois la règle figée
```

Commencer par des règles univariées et monotones :

```text
LONG autorisé si score >= seuil_train
SHORT autorisé si score <= seuil_train
SHORT autorisé si short_score >= seuil_train
abstention si donnée absente ou trop ancienne
```

Les seuils doivent venir de quantiles calculés dans le train, pas de valeurs
absolues choisies après observation. Préférer des quantiles robustes et des
relations répétables à une coupure très précise.

Ensuite seulement, si plusieurs signaux indépendants survivent :

- tester au maximum deux ou trois conditions conjointes ;
- éviter les arbres de règles profonds ;
- mesurer l’apport marginal de chaque condition ;
- corriger le biais de tests multiples ou utiliser une confirmation intacte ;
- conserver une règle LONG et une règle SHORT séparées.

Ne pas exiger qu’un symbole soit bon des deux côtés. Une règle LONG peut recevoir
un GO même si aucune règle SHORT ne survit, et inversement.

---

## 8. Règle, feature ML ou simple diagnostic

Pour tout signal survivant, comparer trois usages :

1. filtre dur après Oracle ;
2. feature ajoutée au modèle directionnel/ranker ;
3. diagnostic sans action.

Un filtre dur est justifié uniquement si la relation est monotone, stable,
interprétable et si son comportement face aux valeurs manquantes est sûr. Une
feature continue est préférable lorsque l’effet est graduel ou dépend d’autres
variables. Ne transformer en règle métier que les effets qui résistent aux folds
et à la confirmation.

Cette comparaison doit rester séparée de l’expérience du ranker conditionnel :
tester d’abord les règles contre Oracle seul, puis éventuellement leur apport au
ranker dans une campagne ultérieure pré-enregistrée.

---

## 9. Baselines et politiques à comparer

À tailles identiques et sur les mêmes dates :

- Oracle TOP20 sans filtre ;
- tirage aléatoire apparié dans le TOP20 ;
- filtre de tradabilité seul ;
- chaque règle screener seule ;
- combinaison minimale pré-enregistrée ;
- score screener natif utilisé comme classement, si sa sémantique le permet.

Pour éviter qu’une règle paraisse bonne seulement parce qu’elle sélectionne très
peu de lignes, produire :

- performance à couverture observée ;
- comparaison appariée de même taille ;
- courbe lift contre taux de rétention ;
- nombre médian de candidats par jour ;
- jours sans candidat.

---

## 10. Métriques et stabilité

Pour LONG et SHORT séparément :

- précision et rappel de l’événement directionnel ;
- lift de précision par rapport au TOP20 Oracle ;
- rendement brut moyen/médian ;
- rendement signé ;
- hit rate ;
- support, dates, symboles et rétention ;
- faux rejets : gagnants Oracle supprimés par la règle ;
- faux accords : candidats conservés mais partis dans le mauvais sens ;
- stabilité par fold, semestre, régime, secteur et symbole ;
- intervalles de confiance avec rééchantillonnage par date ;
- sensibilité aux observations extrêmes en contrôle de robustesse.

Pour un filtre d’exclusion, mesurer explicitement :

```text
coût des TRUE_BAD évités
gain des vrais gagnants supprimés
variation nette du rendement
variation de la couverture
```

---

## 11. Gates de promotion

Pré-enregistrer les gates avant la campagne complète. Une règle directionnelle
doit au minimum :

- améliorer la probabilité conditionnelle et le rendement apparié OOS ;
- produire un effet de même sens dans une majorité nette de folds ;
- conserver une couverture opérationnelle suffisante ;
- ne pas dépendre d’un seul symbole, secteur ou semestre ;
- survivre à une période de confirmation intacte ;
- avoir une politique explicite pour les données absentes ;
- être calculable en production avec la même disponibilité temporelle.

Un gain de précision obtenu au prix de presque toute la couverture n’est pas un
GO automatique. Publier séparément les verdicts :

```text
GO_TRADABILITY
GO_LONG_RULE
GO_SHORT_RULE
NO_GO_PREDICTIVE
```

---

## 12. Ordre d’exécution en production si une règle est validée

L’ordre recommandé est :

```text
univers tradable canonique
    -> Oracle et percentile quotidien sur cette population
    -> TOP20 Oracle
    -> jointure screener PIT
    -> règle LONG et/ou SHORT
    -> éventuel ranker directionnel validé
    -> contraintes portefeuille, risque et lifecycle
```

Les règles directionnelles ne doivent pas réduire l’univers avant le calcul du
percentile Oracle. Sinon, un même score Oracle peut changer de percentile selon
le filtre screener, ce qui rend les expériences incomparables.

---

## 13. Artefacts à produire

Créer un espace de recherche séparé contenant :

- contrat et batch Oracle source ;
- dictionnaire des colonnes auditées ;
- rapport de couverture PIT ;
- dataset analytique avec timestamps de disponibilité ;
- tables de probabilités conditionnelles ;
- folds et règles découvertes sur train ;
- prédictions/décisions OOS ligne à ligne ;
- motifs d’acceptation/rejet ;
- métriques appariées ;
- rapport GO/NO-GO ;
- commande exacte de reproduction.

Ne pas écraser les profils de features ou paramètres screener existants. Toute
configuration candidate doit porter un identifiant distinct et rester inactive.

---

## 14. Intégration éventuelle après GO seulement

Si une règle est validée :

- ajouter un mode/contrat explicite désactivé par défaut ;
- conserver les comportements historiques ;
- persister valeurs screener, timestamp, seuil, côté et motif de décision ;
- refuser les données futures, trop anciennes ou ambiguës ;
- afficher couverture et impact dans les diagnostics ;
- ajouter des tests unitaires, PIT, intégration et non-régression ;
- documenter l’ordre exact Oracle → screener → direction → portefeuille.

Ne jamais remplacer silencieusement une donnée manquante par un accord neutre si
le contrat de recherche utilisait l’abstention.

---

## 15. Condition de fin de mission

La mission est terminée seulement lorsque l’IA a livré :

1. l’audit des sources screener et de leur disponibilité ;
2. les probabilités conditionnelles sur le TOP20 Oracle ;
3. une expérimentation Walk-Forward sans fuite ;
4. des comparaisons appariées et une analyse de rétention ;
5. des verdicts LONG/SHORT séparés ;
6. une confirmation intacte ;
7. éventuellement une intégration inactive et testée après GO ;
8. la documentation complète correspondante.

---

## 16. Exécution réalisée le 5 septembre 2026

Le harnais est implémenté dans `modelFactory/screener_post_oracle.py`, testé dans
`tests/test_screener_post_oracle.py` et documenté dans
`doc/ml/screener_post_oracle.md`.

Campagne canonique :
`artifacts/models/screener_post_oracle/screener-post-oracle-20260905122039-0802c8`.

Résultat : `NO_GO_PREDICTIVE` sur H3, H10 et H20, pour LONG comme pour SHORT.
Aucune règle univariée ne franchit les gates de validation, stabilité, précision,
rendement et couverture. La couverture fraîche de `stock_scores_history` dans
le TOP20 Oracle n’est que de 10,44 % et présente une forte dérive temporelle.

Conformément au protocole, aucune combinaison de règles et aucune intégration
applicative ne sont ouvertes après ce NO-GO.
