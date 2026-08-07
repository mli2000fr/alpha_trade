# Analyse Global Ranking - batch `model-factory-20260807171001-525c56`

**Date d'analyse :** 2026-08-07
**Objet :** evaluation du Global Ranking CatBoost pour le swing trading et controle de l'honnetete des scores.
**Statut :** baseline Global Ranking encourageante, sans fuite directe de cible ou de split identifiee. Le modele reste en recherche : la selection de l'univers et la validation economique doivent etre corrigees avant toute promotion.

---

## 1. Perimetre du batch de reference

Ce document remplace les analyses des anciens batchs. Les conclusions et chiffres ci-dessous concernent exclusivement le batch `model-factory-20260807171001-525c56`.

| Element | Valeur |
|---|---|
| Backend Global Ranking | CatBoost, objectif RMSE |
| Univers declare | 100 titres issus de `ticket-recherche` |
| Periode source | 2016-01-01 a 2025-12-31 |
| Folds utilises | 6 walk-forward, validation OOS de 2019-01 a 2024-06 |
| Horizons | H3, H5, H10, H15, H20 |
| Features | 143, `feature-set expert` |
| Lignes de prediction OOS | 65 367 |
| IC moyen multi-horizon | 0.0203 |
| Stacking Global Rank | non |
| Baseline de portefeuille evaluee | H20 seul |

La commande du batch a active le Global Model, les cross-sectionnelles, CatBoost et le walk-forward. Elle n'a pas active les fondamentales, les facteurs, les scores screener, le sentiment ou les features macro en options explicites. Le risque PIT lie aux fondamentales ne peut donc pas expliquer ce resultat precis, mais reste a verrouiller avant de les activer dans une future variante.

---

## 2. Resultats OOS observes

| Horizon | IC moyen | IC std entre folds | IR temporel du rapport | Spread decile de cible | Lecture |
|---|---:|---:|---:|---:|---|
| H3 | 0.0142 | 0.0254 | 0.56 | 0.0100 | Positif mais instable; deux folds negatifs. |
| H5 | 0.0161 | 0.0238 | 0.68 | 0.0183 | Positif; deux folds negatifs. |
| H10 | 0.0249 | 0.0241 | 1.03 | 0.0187 | Meilleur IC, mais un fold negatif et un proche de zero. |
| H15 | 0.0235 | 0.0248 | 0.95 | 0.0287 | Bon candidat swing; un fold negatif. |
| H20 | 0.0229 | 0.0281 | 0.82 | 0.0283 | Baseline actuelle; trois folds negatifs ou quasi nuls. |

Les horizons H10, H15 et H20 dominent H3 et H5 sur l'IC moyen. Ils sont plus coherents avec une strategie swing car une detention plus longue peut absorber davantage de frais et limiter le turnover. Le signal est toutefois heterogene selon les periodes : aucun horizon ne constitue encore une preuve de robustesse production.

### Detail de stabilite par horizon

* **H3 :** IC negatif sur les validations 2019-01 a 2019-06 et 2020-12 a 2021-06; meilleur fold 2020-01 a 2020-06, IC `0.0620`.
* **H5 :** IC negatif en 2019 et 2021; meilleur fold 2024-01 a 2024-06, IC `0.0500`.
* **H10 :** IC negatif en 2021 (`-0.0077`), faible en 2019 et 2022, fort en 2020, 2023 et 2024.
* **H15 :** IC negatif en 2021 (`-0.0130`), meilleur fold 2023 (`0.0645`).
* **H20 :** IC negatif en 2019 et 2024, quasiment nul en 2021; resultat principalement porte par 2020, 2022 et 2023.

Le resultat est donc un signal cross-sectionnel positif moyen, non une performance uniforme par regime.

---

## 3. Correction de lecture du `IC IR = 4.70`

Le rapport de ce batch affiche un `IC IR` global de `4.70`. Ce chiffre ne doit pas etre utilise : l'ancienne implementation calculait l'ecart-type entre les cinq **moyennes d'horizon**, et non la volatilite des IC OOS dans le temps.

Depuis l'audit, [modelFactory/global_ranking.py](../modelFactory/global_ranking.py) calcule l'ecart-type global a partir de toutes les observations `fold x horizon`. L'IC moyen reste identique; le prochain batch affichera un IR global de stabilite nettement plus realiste. Pour ce batch, les IR interpretables sont ceux par horizon, entre `0.56` et `1.03`.

Formellement, la mesure corrigee utilise :

$$
IR_{global} = \frac{\operatorname{mean}(IC_{h,f})}{\operatorname{std}(IC_{h,f})}
$$

ou $h$ est l'horizon et $f$ le fold OOS. Cette correction modifie le reporting, pas les predictions ni les IC individuels du batch.

---

## 4. Audit de fuite de donnees et d'incoherences

### 4.1 Points verifies comme sains

Le chemin Global Ranking verifie dans [modelFactory/global_ranking.py](../modelFactory/global_ranking.py) et [modelFactory/dataset.py](../modelFactory/dataset.py) protege les mecanismes centraux suivants :

* les splits walk-forward sont atomiques par date; train et validation ne partagent pas une meme seance;
* la cible de chaque horizon est recalculee separement dans le train et dans la validation de chaque fold;
* le rendement futur est construit par `groupby("symbol")`, ce qui empeche un `shift(-horizon)` de traverser deux titres;
* les observations sans rendement futur disponible sont exclues du label;
* l'IC Spearman est calcule date par date sur la coupe transversale, puis moyenne; il n'est pas artificiellement augmente par une correlation pool-ee;
* la neutralisation de la **cible** par date, secteur ou facteur utilise les rendements futurs uniquement pour definir le label relatif. Elle ne fournit pas ces rendements aux features a la date de decision.

Conclusion de cet audit : aucune fuite directe de cible, de prix futur ou de frontiere train/validation n'a ete identifiee dans le calcul des IC de ce batch.

### 4.2 Risques encore ouverts

| Priorite | Risque | Impact possible | Action obligatoire |
|---|---|---|---|
| P1 | Univers de 100 titres possiblement selectionne sur volume/liquidite constates sur toute la periode | Biais de selection et de survivance; IC possiblement trop favorable | Reconstruire l'eligibilite par date ou par fold avec seulement l'information disponible alors. Persister la liste eligibile PIT. |
| P1 | Spread decile calcule sur la cible transformee/rankee | Le `0.0283` H20 n'est pas un rendement de `2.83%` ni un PnL | Ajouter le spread top-bottom sur rendement futur brut, puis le backtest net executable. |
| P2 | Le backtest compare des unites de rang | Sharpes relatifs non convertibles en performance economique | Executer avec prix, execution, frais, slippage, turnover, ADV et contraintes risque. |
| P2 | `split.test` n'est pas un vrai holdout economique final dans cette route | Le choix H20 a deja consulte les six validations | Geler H20 et executer une fois sur une periode jamais utilisee. |
| P2 | Les artefacts conservent le modele du dernier fold | Ambiguite entre objet de recherche WF et modele de production | Refit explicite sur l'historique admissible ou etiqueter l'artefact `last_fold_model`. |
| P2 conditionnel | Disponibilite fondamentale datee par `trade_date` plutot que publication effective | Look-ahead si les fondamentales sont activees | Utiliser `available_at`/date de publication et tester la jointure PIT. |
| P2 conditionnel | Features calculees a la cloture | Incoherence si une execution pretend intervenir avant que la cloture soit connue | Declarer et appliquer une execution au prochain open ou apres close. |

---

## 5. Interpretation correcte du backtest actuel

Le rapport compare trois variantes :

| Variante | Resultat relatif | Interpretation |
|---|---:|---|
| V1 - H20 seul | Reference | Meilleure variante parmi les trois tests. |
| V2 - H20 + H5 rising | -5.8% | Le filtre de hausse H5 ne justifie pas sa complexite. |
| V3 - H20 + H5 < 0.35 | -60.1% | Le filtre contrarian est rejete. |

Les frais annonces de `0.25%` aller-retour ne rendent pas encore ce test economique, car la performance est simulee en unites de rang. La seule conclusion exploitable est relative : parmi les trois politiques testees, **H20 seul** est la baseline de recherche a conserver.

Le passage a une strategie de portefeuille doit mesurer, pour chaque date de rebalancement :

$$
R_{LS,t} = R_{top,t}^{brut} - R_{bottom,t}^{brut} - couts_t - slippage_t - impact_t
$$

avec publication separee du long-only, long-short, turnover, capacite ADV, drawdown et expositions secteur/facteur.

---

## 6. Decision de recherche et plan immediat

### Baseline gelee

* Conserver **CatBoost Global Ranking, 143 features, H20 seul** comme baseline de comparaison.
* Conserver H10 et H15 comme challengers preregistres, car leurs IC moyens sont respectivement `0.0249` et `0.0235`.
* Ne pas retenir H3/H5 comme horizons de portefeuille principaux; ils peuvent servir plus tard au timing, apres test hors echantillon.

### Prochain batch obligatoire

1. Reconstruire l'univers eligible PIT a chaque date de decision avec un historique de liquidite/volume borne a cette date.
2. Relancer exactement la baseline H20, H15 et H10 avec le calcul d'IR global corrige.
3. Sauvegarder dans le manifeste : hash de code, configuration resolue, symboles eligibles par fold, dates, nombre de titres par date, taux de valeurs par defaut et schema des 143 features.
4. Calculer en parallele le spread de target pour le diagnostic et le spread de rendement brut pour l'economie.
5. Construire un portefeuille top/bottom avec execution au prochain open, frais, slippage, turnover, ADV, caps secteur et HHI.
6. Choisir une seule variante par les folds de developpement, puis l'executer une seule fois sur un holdout final inedite.

### Criteres de promotion

Le Global Ranking peut avancer vers un paper-trading seulement si les conditions suivantes sont remplies apres correction PIT :

* IC par date et spread de rendement brut positifs sur la majorite des folds;
* resultat net positif apres couts et impact, sans dependance excessive a 2020 ou 2023;
* turnover, capacite ADV, drawdown et concentration secteur compatibles avec le mandat swing;
* stabilite confirmee sur holdout jamais consulte;
* artefact de production explicitement refit et reproductible.

**Conclusion :** le batch `525c56` etablit une baseline plus convaincante que les precedentes analyses documentees ici, en particulier a H10-H20. Ses scores ne paraissent pas gonfles par une fuite directe de labels ou de split. Ils ne sont toutefois pas encore une preuve de rentabilite : l'univers PIT et le PnL net executable sont les deux verrous qui determinent maintenant la credibilite economique du modele.