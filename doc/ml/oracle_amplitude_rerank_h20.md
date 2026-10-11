# Reclassement d’amplitude Oracle × ATR — H20

## Objectif et protocole figé (11 octobre 2026)

Concentrer davantage de grands mouvements **absolus** dans les 10 ou 20 premiers
titres, sans prétendre prédire leur direction ni leur rentabilité en portefeuille.
Les listes triées par rendement futur dans `oracle_atr_market_regime_daily` ne
sont pas un classement exploitable à J : elles sont réordonnées après observation.

Cette expérience reste séparée du modèle en production. Aucune écriture SQL,
aucun changement de batch, aucune substitution de champion. Les modèles produits
sont exclusivement des artefacts de recherche.

## Comparaison

Pool quotidien identique : intersection Oracle TOP20 % et ATR TOP20 % calculée
sur les titres observables, **avant** de consulter les labels futurs.

1. Ordre du score Oracle décroissant.
2. Ordre ATR20 normalisé décroissant dans ce même pool.
3. LightGBM Ranker d’amplitude, cible ordinalisée à partir de `abs(future_return)`
   H20 au sein du pool. Aucun sens LONG/SHORT dans la cible.

Chaque méthode sélectionne 10 et 20 **titres**, avec départage par symbole.
Les résultats manquants ne sont ni remplacés par des gagnants ni éliminés pour
recomposer une sélection. La comparaison principale retient uniquement les
séances où les trois sélections du même N sont complètes et évaluables ; les
séances écartées sont comptées dans le rapport.

32 entrées numériques figées dans le script : score Oracle, ATR20, trajectoire,
volatilité, volumes, momentum, distances aux moyennes, force relative et bêta.
Pas de sentiment/consensus ajouté sans qualification historique de disponibilité.
Pas de recherche de paramètres : 200 arbres, profondeur 4, seed 42, 4 threads.

## Chronologie et limites

Archives Oracle corrigées hors échantillon : juillet 2018–juillet 2024. Le ranker
commence après 504 séances de scores historiques OOF ; tests successifs de 126
séances, apprentissage expansif et purge stricte : `oracle_available_date` doit
précéder le début du test. Minimum 480 séances d’apprentissage arrivées à maturité.

Comparaison externe janvier 2025–3 septembre 2026 : ranker figé entraîné uniquement
sur les archives OOF historiques antérieures. Pas de réentraînement sur 2025/2026.
Le second semestre 2024 est absent : il n’est pas reconstitué artificiellement.
2026 a déjà été étudié : **ce n’est pas un holdout vierge**.

Univers nettoyé archivé de 1 790 titres, pas l’univers présent évolutif, ni une
certification complète d’univers historique PIT. Les empreintes des archives sont
vérifiées. Les rendements sont close J → close J+20, pas une entrée J+1 avec SL/TP.

## Mesures et décision

Principales : capture du label extrême archivé et amplitude absolue moyenne.
Secondaires : médiane quotidienne, proportion `|R| >= 20 %` et `>= 50 %`.
Comparaison annuelle et deltas appariés ; intervalle descriptif bootstrap par
blocs de 20 séances (retours chevauchants, pas des trades indépendants).

Une suite ne serait justifiée que si les deux mesures principales progressent
contre **les deux baselines** dans chaque année externe et dans une majorité des
blocs historiques. Aucun passage automatique en production, même dans ce cas.
Pas de calcul de PnL à ce stade.

## Exécution et reprise

```powershell
python -u -m scripts.research.us_oracle_amplitude_rerank --threads 4 --output artifacts/research/us_amplitude_rerank/amplitude-rerank-h20-20261011-v1
```

`progress.json` indique la lecture des shards puis l’apprentissage par bloc.
Chaque bloc terminé conserve modèle, sélections, métriques, dates de maturité
et empreintes dans `done.json`. La même commande reprend les blocs terminés
après vérification des empreintes, sans les réentraîner. Ne pas lancer deux
instances dans le même répertoire. `report.json` et `annual.parquet` constituent
les résultats finaux ; aucune conclusion n’est annoncée avant leur génération.

## Résultats — calcul terminé le 11 octobre 2026

Répertoire : `artifacts/research/us_amplitude_rerank/amplitude-rerank-h20-20261011-v1`.
Neuf blocs terminés, six tests ciblés validés (`pytest --no-cov`). Le seuil de
couverture global de toute l’application n’est pas applicable à ces seuls tests.

TOP10, pool Oracle × ATR identique, séances complètes communes :

| Année | Séances | Capture extrêmes Oracle | Capture ranker amplitude | Amplitude moyenne Oracle | Amplitude moyenne ranker |
|---|---:|---:|---:|---:|---:|
| 2025 | 250 | 54,28 % | 50,28 % | 16,82 % | 16,14 % |
| 2026 jusqu’au 03/09 | 160 | 56,25 % | 55,06 % | 18,36 % | 17,99 % |

Le ranker perd contre l’ordre Oracle sur 2025 et 2026. Sur les 410 séances
externes TOP10 communes : capture −2,90 points, amplitude moyenne −0,56 point.
Intervalle descriptif block20 du delta de capture : [−5,15 ; −0,88] points.
TOP20 : capture −2,41 points et amplitude moyenne −0,27 point contre Oracle,
sur 402 séances communes. Il ne s’agit pas d’un rendement de portefeuille.

Historique juillet 2020–juillet 2024 : 1 007 séances communes ; TOP10 capture
−1,62 point, amplitude −1,70 point contre Oracle. Un seul bloc sur huit améliore
simultanément les deux mesures contre **les deux** baselines, pour N=10 comme
N=20. Quelques améliorations locales (notamment début 2024) ne sont pas stables.
L’écart externe contre ATR seul est légèrement positif, mais ne justifie pas
de remplacer l’ordre Oracle, supérieur dans cette comparaison.

84 lignes de métriques politique/date/N sont écartées par le contrôle commun
de complétude, soit 28 combinaisons date/N, et non 84 séances distinctes.
Ce filtrage sert uniquement à évaluer équitablement, pas à sélectionner en live.

**Conclusion : NO_GO pour ce ranker d’amplitude et ce protocole précis.**
Conserver l’ordre du score Oracle dans le pool Oracle × ATR. Cela ne démontre
pas que tout reclassement possible est inutile, mais aucun gain stable n’est
démontré ici. Aucun modèle de production, donnée SQL ou batch n’a été modifié.

Suite autorisée et terminée : voir [modèle à deux parties pour les mouvements
>=20 %](oracle_tail_amplitude_h20.md). Cette hypothèse distincte progresse sur
plusieurs blocs historiques mais ne confirme pas d’avantage contre l’ordre
Oracle en 2025–2026 ; elle reste également non promue.
