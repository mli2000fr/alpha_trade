# Acheter uniquement sur avis GPT favorable — 2025

Demande utilisateur : mesurer le taux de trades gagnants et le rendement en
achetant uniquement si GPT émet un avis favorable, après le test de veto.
Toutes les réponses GPT sont réutilisées ; aucun nouvel appel ou prompt.

## Règles figées avant replay

- Bras principal **FAVORABLE_ONLY** : réponse valide, avis FAVORABLE, soit17
  candidatures. Inclut un avis favorable avec preuves INSUFFICIENT.
- Vérification séparée **FAVORABLE_SUFFICIENT_ONLY** : exige en plus des
  preuves SUFFICIENT, soit16 candidatures.
- Les onze réponses invalides, avis indéterminables/défavorables et38 dossiers
  sans news sont exclus. Aucun remplacement depuis les rangs suivants.

Même témoin que le pilote LLM :2025, Oracle H10
`model-factory-20261106203103-91b063`, TOP10 % Oracle → TOP10 LONG per-symbol,
score >0,70 et AUC calibration ≥0,60, puis risque et Winner. Capital4 000 USD,
compte margin capacité2×, risque1,25 %, poids20 %, minimum50 USD, positions
complètes, entrée journalière J+1 sans confirmation, SL5 %, sans TP/trailing,
sortie open11. Mêmes frais et financement ; contrôleur DD/B4 et facteurs désactivés.
Ce n'est pas le profil Q088 de l'IHM.

## Réutilisation et contrôles

Programme : `scripts/research/us_gpt_winner_favorable_only.py`.
Sortie : `artifacts/research/us_gpt_winner_favorable_only/20261108-v1`.
Reçus : `artifacts/research/us_gpt_winner_ab/20261107-v1/analyses.sqlite3`,
ouverts en lecture seule. Les réponses conservées sont revalidées avant sélection.

Les résultats du témoin et du veto + invalides exclus sont réutilisés depuis
`us_gpt_winner_invalid_excluded/20261108-v2`, où le témoin a déjà été reproduit.
L'identité des18 indicateurs avec le témoin original est contrôlée, de même que
les empreintes des sources et la cohérence des204 candidatures. Les deux bras
favorables sont réellement rejoués par le même moteur natif sur la bande figée,
avec capital partagé, frais, financement et limites de réentrée ; aucun calcul
de performance par simple filtrage des trades du témoin.

`decisions.csv` contient les204 avis et les deux règles de sélection. Les
rapports conservent trades, événements et courbes quotidiennes ; `comparison.csv`
compare les quatre politiques. Un test vérifie les frontières de sélection,
notamment l'avis favorable insuffisamment étayé et le rejet des indéterminables.

## Limites

Échantillon limité à17 candidatures favorables, pouvant produire moins de trades
que de signaux. Un taux gagnant élevé sur très peu de trades ne valide pas une
capacité directionnelle stable. Versions des news non certifiées PIT, mémoire
future possible du LLM, secteurs actuels et repli daily des protections 5m :
étude rétrospective exploratoire, aucune validation indépendante OOS ou parité live.
La variante « preuves suffisantes » est présentée séparément, sans sélectionner
après coup une règle selon sa performance.

## Résultats terminés

| Politique | Candidatures | Trades | Gagnants / perdants | Taux gagnant | Rendement | DD max | Capital final |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Winner seul | 204 | 59 | 27 / 32 | 45,76 % | +6,90 % | −10,86 % | 4 275,95 $ |
| Veto GPT + invalides exclus | 159 | 53 | 21 / 32 | 39,62 % | −0,70 % | −12,98 % | 3 971,82 $ |
| FAVORABLE uniquement | 17 | 9 | 5 / 4 | 55,56 % | +2,80 % | −4,58 % | 4 111,96 $ |
| FAVORABLE + preuves SUFFICIENT | 16 | 8 | 5 / 3 | 62,50 % | +3,80 % | −3,52 % | 4 152,15 $ |

Capital engagé moyen :1 334,04 $ dans le témoin,1 081,80 $ pour le veto,
211,31 $ pour les favorables et191,20 $ pour les favorables à preuves suffisantes.
Maximum pour ces deux dernières variantes :1 630,24 $. Frais11,21/10,09 $ et
aucun financement débiteur pour ces deux variantes ; coût des appels GPT antérieurs
non déduit de l'equity simulée, aucun nouvel appel pendant ce replay.

Le taux gagnant augmente sur ce petit échantillon. Le rendement reste inférieur
à celui du témoin et le capital est beaucoup moins engagé. La réduction du DD
n'isole donc pas à elle seule la qualité de sélection d'un effet d'exposition.
Cinq trades gagnants pour chacune des variantes favorables ne constituent pas
une validation d'un taux de réussite futur de55 ou62 %. La mention SUFFICIENT
reste un jugement du LLM, soumis au contrôle technique des citations et non une
revue indépendante de la qualité économique des preuves.

Statut global `COMPLETED_EXPLORATORY` ; les rapports natifs conservent les limites
de couverture5m/daily de la référence. Les résultats des deux nouvelles variantes
sont des replays complets, pas une extrapolation des signaux ou des trades anciens.
