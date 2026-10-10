# US 2025 — Combinaison de features candidates D10

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Protocole fixé avant calcul, le 4 octobre 2026

Expérience exploratoire uniquement : les familles ont été choisies à partir
de l'audit 2025. Aucune partie de 2025 n'est présentée comme une validation
indépendante. Aucun fit, serving, SQL ou moteur de backtest ne sera modifié.

Population principale : intersection figée ATR20 TOP20 × Oracle H20 TOP20,
67 084 couples symbole/séance de l'univers statique de 1 798 titres.
Pas de filtre sentiment obligatoire, pas de condition sur cinq SMA.
Pas d'extension à un autre univers pendant ce test.

### Blocs et sélection

- M (momentum) : rang percentile quotidien croissant `momentum_120`.
  Pas de choix ultérieur entre brut et z-score d'après la performance.
- V (volatilité/amplitude) : moyenne des rangs quotidiens croissants
  `rolling_volatility_60` et `atr20_pct`. Deux features corrélées regroupées
  dans un bloc, pour ne pas lui donner deux fois le poids du momentum.
- S (sentiment positif à J) : minimum des `positive_score` des articles
  scorés de J, puis rang quotidien parmi les candidats avec scores. Valeur
  manquante ou aucun article : rang neutre 0,5, sans les exclure. Ceci n'est
  pas une condition « tous >0,9 » : c'est un score progressif. Les articles
  non scorés ne sont pas dans l'archive ; disponibilité PIT non certifiée.

Rangs calculés dans tous les candidats à J avant jointure des labels futurs.
Sept politiques fixées : M, V, S, M+V, M+S, V+S, M+V+S. Poids égaux
entre blocs présents, pas de recherche d'hyperparamètre. Pour chaque
politique, retenir le TOP10 et le TOP20 du pool par séance (effectif ceil),
ex aequo départagés par symbole. Moins de candidats : ne pas compléter.
Baseline : tout le pool ATR×Oracle. Références appariées : blocs seuls à
la même fraction de sélection. Oracle seul n'est pas la population de ce test.

### Mesures et limites

- Effectifs candidats, titres distincts, inconnus conservés dans les comptes.
- Vrais D1/D10/D2–D9, gains de part D10 et de part D1 par rapport au pool.
- Moyenne/médiane des rendements ajustés J→J+20, proportion positive.
- Moyenne des rendements et proportions quotidiens (poids égal aux dates),
  semestres et mois, comparaison combinaison/blocs seuls au même TOP.
- Aucune annualisation de rendements H20 chevauchants, pas de PnL portefeuille,
  de Sharpe, de coûts ou d'exécution next-open simulée.
- Les features utilisent la clôture J, comme les études précédentes. Le
  rendement close-J→close-J+20 n'est pas un fill réellement exécutable.
- Aucun intervalle de confiance groupé ni correction de multiplicité ;
  un meilleur résultat moyen peut dépendre de quelques titres/dates.

Tout résultat reste un candidat à une confirmation multi-annuelle verrouillée,
et non un GO production. Une combinaison ne sera pas déclarée supérieure si
elle ne fait que dépasser le pool sans dépasser les blocs seuls comparables.

## Sources et reproduction

Panel : `feature-separation-20261004-v1/features.parquet`, labels :
`intersection-realized-20261004-v1/native_realized_labels.parquet`, news :
`audit-20261004-v1/news_observations.parquet`, pool :
`audit-20261004-v1/symbol_day_windows.parquet`, sous
`artifacts/research/us_atr_oracle_sentiment/`.

Script : `python -m scripts.research.us_feature_combination_d10`.
Sortie : `artifacts/research/us_atr_oracle_sentiment/combination-d10-20261004-v1/`.
Les preuves existantes ne sont jamais écrasées.

## Résultats terminés

Tous les labels des sélections sont valides selon les gardes natives.
TOP10 du pool ≈27titres par séance ; TOP20≈54. Ce n'est pas le TOP10/TOP20
de l'univers entier. News scorées disponibles sur16 112couples, absentes
sur50 972 (≈76 %) : neutralisation à0,5, pas de faux score imputé.

| Politique | Couples | D10 | D1 | Rendement H20 moyen brut |
|---|---:|---:|---:|---:|
| Tout le pool | 67 084 | 22,18 % | 18,15 % | +2,51 % |
| M TOP10 | 6 814 | 29,10 % | 18,81 % | +4,10 % |
| V TOP10 | 6 814 | 29,18 % | 21,44 % | +4,28 % |
| S TOP10 | 6 814 | 23,42 % | 18,58 % | +2,64 % |
| **M+V TOP10** | **6 814** | **32,05 %** | **20,08 %** | **+4,91 %** |
| M+S TOP10 | 6 814 | 27,88 % | 18,92 % | +3,78 % |
| V+S TOP10 | 6 814 | 28,57 % | 20,62 % | +3,87 % |
| M+V+S TOP10 | 6 814 | 30,70 % | 20,21 % | +4,40 % |
| M TOP20 | 13 518 | 27,50 % | 17,67 % | +3,84 % |
| V TOP20 | 13 518 | 28,52 % | 20,25 % | +3,95 % |
| S TOP20 | 13 518 | 23,10 % | 18,35 % | +2,54 % |
| M+V TOP20 | 13 518 | 29,59 % | 18,35 % | +4,49 % |
| M+S TOP20 | 13 518 | 26,64 % | 17,70 % | +3,60 % |
| V+S TOP20 | 13 518 | 28,25 % | 20,02 % | +3,83 % |
| M+V+S TOP20 | 13 518 | 28,91 % | 18,66 % | +4,22 % |

M+V est le meilleur résultat agrégé des combinaisons testées, aux deux
fractions de sélection. Cela ne démontre pas une supériorité statistique.
Au TOP10, gains descriptifs versus Vseul :+2,87points D10,+0,62point
de rendement brut moyen et−1,36point D1. Versus Mseul :+2,96points D10,
+0,81point rendement, mais+1,27point D1. L'ajout du sentiment dégrade
l'agrégat M+V :+4,91 %→+4,40 %, D10 32,05 %→30,70 %.

## Stabilité de M+V TOP10 : réserve majeure

173titres distincts,250séances,2 184vrais D10 et1 368vrais D1.
Médiane rendement H20 +3,32 %,57,75 % rendements positifs. Moyenne à poids
égal par séance +4,91 % également : le résultat agrégé n'est pas seulement
dû aux petites différences d'effectif quotidien.

| Période | D10 | D1 | Rendement H20 moyen brut |
|---|---:|---:|---:|
| Janvier–juin | 30,20 % | 24,06 % | +2,96 % |
| Juillet–décembre | 33,83 % | 16,25 % | +6,78 % |
| Janvier | 20,86 % | 30,76 % | −1,70 % |
| **Février** | **10,36 %** | **44,42 %** | **−13,74 %** |
| Mars | 17,29 % | 31,02 % | −9,47 % |

Février du pool sans sélection :−9,88 %, donc la combinaison accentue la
perte moyenne. Janvier/mars ne l'améliorent pas non plus. Surles12mois,
M+V ne dépasse simultanément Mseul etVseul en rendement moyen que **3mois**.
Le gain annuel agrégé n'est donc pas une dominance régulière des deux
blocs. Les observations mensuelles sont des dates de signal et leurs
rendements H20 peuvent déborder sur le mois suivant.

## Conclusion

**Piste descriptive M+V à confirmer, aucun GO déploiement.** La combinaison
concentre davantage les mouvements gagnants mais ne supprime pas les
perdants, et les régimes défavorables restent importants. Ne pas promettre
de maximisation du gain/minimisation des pertes. Ne pas transformer +4,91 %
en rendement mensuel, annuel ou gain portefeuille : prix, coûts, exposition,
rotation et contraintes d'exécution n'ont pas été simulés.

Suite possible avec nouveau GO : confirmer M+V figé sur des années distinctes,
sans changer les poids/seuils après lecture, puis vérifier effets secteur,
taille/symbole, intervalles groupés et rendement réellement exécutable.
Le sentiment n'est pas nécessaire à cette confirmation. Garder une période
intacte pour la validation finale ; 2025 est déjà explorée.

Rapport : `combination-d10-20261004-v1/report.json`, panel des scores et
labels : `scored_panel.parquet`. Les rapports incluent tous les déciles,
semestres/mois, effectifs inconnus, empreintes et mesures pondérées par date.
Tests : `tests/test_us_feature_combination_d10.py` (poids, missingnews,
minimumdesarticles,ceil,exaequo et indépendance des labels de sélection).
