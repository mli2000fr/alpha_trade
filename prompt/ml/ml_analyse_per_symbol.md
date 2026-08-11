# Analyse per-symbol - hypotheses, limites et plan de validation

**Date :** 2026-08-06  
**Statut :** recherche prioritaire, pas encore eligible a une promotion de trading.  
**Conclusion courte :** le per-symbol peut avoir un signal propre et le pilote `71ad0b` justifie une investigation. Il ne permet pas encore de conclure, car il couvre seulement dix titres de `ticket-recherche`, sans univers PIT representatif ni backtest portefeuille apparié au Global Ranking.

---

## 1. Ce que montre le premier pilote

Le batch `model-factory-20260805180215-71ad0b` est un entrainement per-symbol en regression, horizon H20, avec les features `expert` et les hyperparametres fixes. Il fournit les resultats walk-forward moyens suivants :

| Backend | Directional accuracy WF | MSE WF | Lecture |
|---|---:|---:|---|
| CatBoost | 57.24 % | 1.1503 | Signal potentiel a repliquer. |
| LightGBM | 54.61 % | 1.1685 | Signal faible mais potentiellement utile. |
| LSTM Attention | 56.96 % | 39.9255 | Non interpretable avant diagnostic d'echelle/calibration. |

Les F1 macro sont mecaniquement limitees par l'absence pratique de classe `flat` en regression. Elles ne doivent pas etre utilisees seules pour comparer les modeles ou promouvoir un champion.

Le pilote est encourageant pour les arbres, mais ne constitue pas une preuve economique :

* seulement dix titres, et non `50-100` titres liquides representatifs;
* source `ticket-recherche`, qui n'est pas une regle d'univers stable et PIT par fold;
* absence de comparaison sur les memes titres/dates avec le Global Ranking;
* absence de PnL long-short, spread net de couts, turnover, capacite et drawdown;
* pas de test explicite de la valeur incremental du per-symbol dans le portefeuille final.

Le LSTM doit etre temporairement sorti de la selection automatique. Un MSE WF proche de $40$ alors que les arbres sont proches de $1$ indique une prediction non calibree, une incoherence d'echelle, un scaler/target non inverse correctement, ou un checkpoint inadequat. Le bon ordre est de diagnostiquer ce chemin, pas de modifier son architecture.

---

## 2. Ou la performance peut etre gagnee ou perdue

### 2.1 Univers de symboles

C'est le premier levier a controler. Les actions n'ont pas toutes la meme dynamique : mega-caps, small caps, biotechs evenementielles, cycliques et titres illiquides ne constituent pas une population homogene.

Construire un univers de recherche fige de `50-100` titres avec une selection **PIT par fold** :

* historique minimum apres warm-up des features et horizon;
* ADV minimum et prix minimum;
* spread bid-ask acceptable avec politique explicite pour les quotes manquantes;
* pas de biais de survivance : l'appartenance a l'univers doit etre connue a la date du fold;
* repartition tracee par secteur et decile de liquidite.

Le choix doit etre persiste dans le manifest : liste/hash des symboles par fold, filtres appliques, raisons d'exclusion et metadonnees de liquidite. `--per-symbol-max-symbols` peut limiter le cout, mais la liste finale ne doit pas etre une simple troncature manuelle de `ticket-recherche`.

### 2.2 Donnees

OHLCV et indicateurs techniques sont une baseline valable, mais une prediction H20 par symbole requiert souvent une information plus specifique. Toute source additionnelle doit avoir une hypothese et un timestamp de disponibilite $
0<= date de decision$.

| Famille | Hypothese per-symbol | Controle PIT necessaire |
|---|---|---|
| Fondamentales / revisions | Valorisation, rentabilite et revisions lentes differentient les titres | date de publication, pas seulement date comptable |
| Earnings / analystes | Surprise et revision peuvent expliquer une derive post-evenement | calendrier et heure de disponibilite |
| Sentiment / news | Le flux d'information cree une pression de court/moyen terme | timestamp publication, deduplication, stale rate |
| Liquidite / microstructure | Volume, spread et short interest modulent la tradabilite et le signal | quotes fraiches, ADV pre-decision, borrow pour shorts |
| Facteurs / secteur | Le signal individuel peut etre une exposition cachee a taille, value, momentum ou secteur | univers et calculs cross-sectionnels PIT |
| Macro | Un regime peut moduler momentum et volatilite | macro connue au moment de la decision; interactions locales |

Une macro brute comme VIX, VXN, VIX9D, VIX3M ou MOVE est identique pour tous les titres a une date. Elle peut aider un modele temporel per-symbol, mais elle doit etre testee avec une interaction explicite, par exemple `VIX x momentum_20`, et non comme ajout massif de colonnes.

### 2.3 Features et feature engineering

Le probleme n'est pas le nombre de features mais leur contribution incrementale hors echantillon. Avant tout tuning, faire une ablation par famille :

| Run | Schema | Question |
|---|---|---|
| F0 | `expert` sans families optionnelles | Baseline reproductible. |
| F1 | F0 + features cross-sectionnelles reelles | Le contexte de ranking ajoute-t-il du signal ? |
| F2 | F0 + fondamentales PIT | Information lente incrementalement utile ? |
| F3 | F0 + regime macro et interactions | Le regime change-t-il la validite des features locales ? |
| F4 | meilleure famille + une seule seconde preregistree | Complementarite reelle ou bruit ? |

Ne pas activer simultanement score short, VIX, VXN, VIX9D, VIX3M, MOVE, CAPM, fondamentales, facteurs et cross-sectionnelles. Sinon un echec ou un gain ne peut pas etre attribue.

Pour chaque feature active et chaque fold, stocker :

* presence dans la matrice passee a `fit`;
* missing rate avant imputation;
* taux de valeurs par defaut apres imputation;
* variance et nombre de valeurs distinctes;
* importance moyenne et stabilite d'importance entre folds;
* correlation avec target et rendements futurs, comme diagnostic seulement;
* timestamp/fingerprint du dataset.

Une feature a forte importance dans un fold mais absente ou constante dans les autres est une hypothese de bruit a retirer, pas une source d'alpha confirmee.

### 2.4 Cible et horizons

La regression doit rester le mode principal. Elle preserve l'intensite du score pour classer les convictions et construire des poids. La classification ternaire est un challenger, pas un remplacement automatique : elle perd la magnitude et doit etre calibree par fold.

Pour le per-symbol, commencer avec H20 en regression CatBoost/LightGBM. Tester H10 seulement si H20 est stable; ne pas multiplier les cinq horizons avant d'avoir une preuve economique.

La directional accuracy de regression compare le signe de la prediction avec le signe de la cible transformee dans chaque fold. La cible est winsorisee et standardisee selon le train du fold. C'est coherent pour l'apprentissage, mais ce n'est pas directement une preuve de direction economique du rendement brut.

Les metriques decisives sont donc :

$$
IC_{date} = \operatorname{corr}_{cross-section}(score_{i,t}, future\_return_{i,t+h})
$$

et le rendement long-short net :

$$
spread_{net} = R_{top} - R_{bottom} - couts - impact
$$

Les mesurer par date et par fold, avec turnover, capacite ADV, drawdown et holdout final gele.

### 2.5 Modele et regularisation

Le tuning est raisonnable apres F0-F4, mais il doit rester petit, preregistre et regularisant :

| Modele | Variantes limitees | Role |
|---|---|---|
| LightGBM | depth `3/5/7`, `min_child_samples` `150/300`, feuilles coherentes | Challenger arbre rapide. |
| CatBoost | depth `4/6/7`, `l2_leaf_reg` `3/10`, `200/500` iterations avec early stopping | Challenger principal du pilote. |
| Ridge / ElasticNet | petite grille `alpha` / `l1_ratio` | Controle lineaire interpretable. |
| Random Forest | une configuration stable | Controle de variance, pas candidat par defaut. |
| XGBoost | une configuration regularisee equivalente | Un challenger unique, pas une grille massive. |

Choisir sur les folds de developpement; consulter le holdout une fois pour la configuration gagnante. En cas d'egalite, retenir le modele le plus simple et le plus regulier entre folds.

---

## 3. Ce que les professionnels font avec le secteur

Des professionnels utilisent des signaux long/short conditionnes au secteur, mais rarement onze classifieurs identiques entraines uniquement avec des indicateurs techniques generiques.

### 3.1 Modeles globaux conditionnes par le secteur

Un modele unique apprend une relation de la forme :

$$
P(long_i \mid x_i, secteur_i, regime_t)
$$

ou predit un rendement attendu $E[r_i \mid x_i, secteur_i, regime_t]$. Le secteur est alors une categorielle et/ou intervient dans des interactions :

* `secteur x momentum`;
* `secteur x valorisation`;
* `secteur x volatilite`;
* `secteur x regime macro`.

Le modele conserve ainsi la taille du panel global tout en apprenant que le meme momentum, par exemple, n'a pas la meme interpretation dans Utilities et Technology.

### 3.2 Modeles sectoriels specialises

Un modele par secteur est justifie quand il existe une information distincte et une hypothese economique specifique :

| Secteur | Donnees specialisees PIT | Usage plausible |
|---|---|---|
| Energy | courbe petrole/gaz, stocks, crack spreads, production | risque/allocation Energy ou dispersion producteur-raffineur |
| Financials | pente des taux, spreads credit, depots, defaults | banques versus assureurs, sensibilite taux/credit |
| Semiconductors | commandes, stocks, capex, prix memoire | cycle industrie et dispersion fournisseurs |
| Real Estate | taux reels, spreads credit, refinancement | sensibilite des REITs au financement |
| Utilities | courbe de taux, energie, meteo, regulation | expositions defensives et cout du capital |

La probabilite long/short doit etre calibree sur une population/regime comparable. Une sortie CatBoost de `0.70` n'est pas automatiquement une probabilite economique fiable : elle doit etre evaluee par calibration, hit rate conditionnel, PnL et couts OOS.

### 3.3 Secteur dans le portefeuille et le risque

Meme sans alpha per-sector, le secteur est indispensable pour construire le portefeuille. Le Global Ranking selectionne les titres; le constructeur impose des caps et/ou une neutralite sectorielle; `risk_management` valide la concentration, ADV, drawdown, gross/net et les poids finaux.

Un portefeuille peut etre neutre en exposition nette tout en etant fortement expose en gross :

$$
net_s = \sum_{i \in s} w_i,
\qquad
gross_s = \sum_{i \in s} |w_i|
$$

Un long $10\%$ et un short $10\%$ en Energy donnent $net_s=0$, mais $gross_s=20\%$. Les deux doivent etre mesures et bornes.

---

## 4. Protocole de decision per-symbol

### Phase 1 - Reproduction et controles

1. Constituer l'univers PIT de 50-100 titres liquides et sauvegarder le manifest.
2. Rejouer F0 H20 pour CatBoost et LightGBM, avec le Global Ranking sur les memes titres/dates.
3. Ajouter zero, momentum 20/60 et ElasticNet comme controles.
4. Verifier le LSTM separement : cible/scaler/predictions/checkpoint; aucun champion LSTM tant que le MSE est hors echelle.

### Phase 2 - Donnees et features

1. Executer F1, F2, F3 sequentiellement, avec un seul changement par run.
2. Conserver uniquement les familles qui ameliorent IC par date et spread net sur la majorite des folds.
3. Executer F4 une seule fois, avec les deux familles preregistrees.

### Phase 3 - Tuning limite

1. Executer la grille courte CatBoost/LightGBM uniquement sur le schema gagnant.
2. Comparer au controle ElasticNet et au Global Ranking apparié.
3. Geler le vainqueur de developpement, puis l'executer une fois sur holdout.

### Phase 4 - Integration prudente

1. Comparer Global Ranking seul, per-symbol seul et Global + per-symbol.
2. La combinaison n'utilise que des predictions OOF et ne modifie le poids que de maniere bornee.
3. Passer chaque portefeuille propose au validateur de risque existant : poids single-name, caps secteur/industrie, ADV, gross/net, HHI et drawdown.
4. Promouvoir uniquement si le portefeuille combine augmente le rendement net ou reduit le drawdown sans augmenter materiallement le turnover et la concentration.

## 5. Criteres stop/go

**Go per-symbol :** CatBoost ou LightGBM bat les controles simples sur une majorite de folds en IC par date et spread net, survit au holdout, et ajoute une valeur au Global Ranking ou a la diversification du portefeuille.

**Stop per-symbol generique :** aucun backend ne bat les controles sur l'univers liquide apres F0-F4 et tuning limite. Dans ce cas, ne pas lancer une recherche infinie de flags; limiter le per-symbol a la recherche et concentrer les ressources sur le Global Ranking et les contraintes de portefeuille.

**Go per-sector specialise :** seulement si un dataset sectoriel PIT et une hypothese economique nouvelle battent zero et momentum intra-secteur en IC relatif/spread net, avec confirmation holdout.

**Stop per-sector generique :** les ablations et tuning H20 ne montrent aucun gain economique stable. Fermer alors cette branche pour le dataset actuel, tout en gardant le secteur dans le Global Ranking et le risque de portefeuille.
