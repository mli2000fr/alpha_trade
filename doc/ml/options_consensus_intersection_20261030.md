# TOP20 : peut-on cumuler consensus et filtre options ?

30 octobre 2026. **COMBINAISON TESTABLE PLUS TARD — ZÉRO ISSUE COMMUNE MÛRE
AU CUTOFF.** Aucun gain incrémental n'est démontré aujourd'hui.

Vérification en base US en lecture seule, sans appel fournisseur, LLM,
entraînement, inférence, écriture SQL, ordre ou changement de configuration.
Parent figé : [audit du filtre exact TOP20](options_top20_actualisation_20261030.md).
Cutoff identique au parent : 30 octobre 2026, 18:43:46 UTC ; prix à travers
la dernière séance entièrement close, le 29 octobre.

## Vérification du chevauchement disponible

Les données EODHD des sociétés de ce périmètre commencent à être effectivement
reçues le **11 octobre**. Aucun snapshot de consensus de septembre n'existe
dans cette extraction. Les points J−7/J−30/J−60/J−90 reçus en octobre ne sont
pas des archives disponibles aux décisions de septembre.

Or les 21 issues départagées parmi les retenus mûrs du filtre options viennent
des signaux du 22–30 septembre. Il est impossible de leur ajouter honnêtement
le consensus d'octobre pour mesurer une prédiction de septembre.

On trouve désormais une intersection récente :

| Séance du signal | TOP20 scorés par le filtre options | Avec révisions EPS30 et EPS actuel/J−30 reçus à temps | Parmi les retenus options |
|---|---:|---:|---:|
| 27 octobre | 11 | 9 | 4 |
| 28 octobre | 14 | 13 | 4 |
| 29 octobre | 13 | 12 | 4 |
| Total | 38 | **34 couples séance/titre, 17 sociétés** | **12 signaux** |

Les données de consensus sur les séances du 16, 23 et 26 octobre sont présentes,
mais le filtre options n'y atteint pas les quatre couverts requis pour attribuer
ses scores. On ne remplace pas ce filtre par un classement de un à trois titres.

**Zéro issue commune mûre à H5, H10, H15 ou H20**, aussi bien pour le solde
de révisions que pour EPS actuel/J−30. Les 34 intersections sont immatures aux
quatre horizons ; aucune AUC ou performance de combinaison n'est calculée.

Les premières fenêtres H5 des signaux du 27/28/29 octobre se terminent
respectivement **les 3/4/5 novembre à la clôture US**. Les H20 correspondantes
se terminent les 24/25/27 novembre, calendrier officiel et séance écourtée inclus.
Ces dates ne promettent pas une taille d'échantillon suffisante pour conclure.
Aucun suivi automatique n'a été créé.

## Informations à comparer lorsque les issues seront disponibles

Le consensus apporte une hypothèse différente de l'activité des contrats :

- Solde révisions30 : `(hausses − baisses) / (hausses + baisses)`, zéro seulement
  lorsque les deux compteurs sont explicitement nuls.
- Évolution EPS30 : `(EPS actuel − EPS à J−30) / abs(EPS à J−30)` ; référence
  nulle ou manquante exclue. Même ancrage fiscal et horizon `0q`.

Les données ne sont pas toutes constantes : dans les 34 intersections,
révisions30 positives/neutres/négatives = **27/3/4** ; EPS30 = **17/6/11**.
Cela montre qu'un signal peut être construit, pas qu'il améliore la prévision.

Le prochain comparatif doit conserver exactement les mêmes observations pour
options seules, consensus seul et combinaison figée, sans chercher les meilleurs
poids sur ces trois jours. La combinaison 50/50 déjà étudiée constitue une
référence exploratoire, pas un poids validé. Aucun classement combiné n'est ici
ajouté au pipeline ni utilisé pour supprimer des ordres.

## Qualification et limites

Contrôle du raw hash et de la normalisation de chaque ligne, run terminé,
maximum conservateur de observed/available/ingestion/fin du run avant décision,
fraîcheur 72 heures, au moins trois analystes EPS et fourchettes cohérentes.
Même politique d'ancrage que l'audit précédent : dernier ancrage fiscal `0q`
dans une fenêtre fixe de ±100 jours, puis dernière réception terminée.

Statut **RESEARCH_ONLY** conservé : convention GAAP/non-GAAP non identifiée,
dates fiscales normalisées par le fournisseur, changements de composition des
analystes non observables. Les contrôles techniques ne certifient pas ces points.
Une qualification comptable complète n'est donc pas revendiquée.

L'audit du 27 octobre avait un seul cas commun TOP20, sans AUC calculable, avec
une définition de volume et des archives différentes. Ce n'est pas une preuve
complémentaire de performance du filtre 30Min actuellement déployé.

## Livrables

- `artifacts/research/us_options_consensus_overlap/20261030-v1/` : protocole,
  consensus et reçus de runs figés, couverture avant décision CSV,
  `report.json`, empreintes SHA256.
- Script `scripts/research/us_options_consensus_overlap_20261030.py`.
- Trois tests réussis : disponibilités causales, absence de rétrodatation vers
  septembre, compteurs manquants et runs inachevés exclus.

Conclusion : piste légitime à comparer, **aucun rendement ou taux de réussite
supplémentaire attribuable au consensus ne peut encore être annoncé**.
