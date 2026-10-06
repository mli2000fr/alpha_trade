# Sprint 7-B — Features relatives au benchmark France

Réalisé le 3 octobre 2026. Ce lot enrichit le [profil prix figé 7-A2](sprint_7a2_profil_prix_fige_par_periode.md) sans le modifier : **14 features prix + 12 features benchmark = 26 features**. Il construit un panel de recherche et mesure sa couverture ; aucun modèle n'est entraîné, aucune conclusion de prédictivité Oracle ou D1/D10 n'est acquise.

## Quelle référence de marché ?

Le benchmark est `FR_RESEARCH_EW_PRICE_V1`, construit au [Sprint 6-C](sprint_6c_identite_benchmark_secteurs.md). Il ne s'agit ni du CAC 40, ni d'un indice officiel Euronext, ni d'un indice total return. Il est fondé sur les rendements de clôtures brutes des titres de l'univers recherche : composition déterminée avant la séance, pondération égale, minimum 20 constituants et couverture des rendements de 95 %. Les dividendes ne sont pas réinvestis. Les prix/corporate actions restent sous les réserves du GO limité Sprint 5.

Les observations `UNKNOWN` ne portent aucun rendement exploitable. Lorsqu'une séquence connue reprend, un nouveau segment est créé. Le niveau de l'indice est réinitialisé, mais on utilise directement les rendements quotidiens archivés : aucun calcul de rendement ne doit franchir une rupture de segment.

Un titre peut être constituant de son propre benchmark : ces features ne sont pas « leave-one-out ». Cela n'introduit pas de rendement futur, mais crée une dépendance mécanique titre–benchmark à signaler lors de l'analyse. Cette référence reflète notre sous-univers liquidité/recherche, pas l'ensemble des actions françaises.

## Features ajoutées et formules

Soit `r_i` le rendement quotidien titre et `r_b` le rendement quotidien benchmark ; les horizons et fenêtres sont exprimés en séances XPAR. Les valeurs sont des ratios, non des pourcentages multipliés par 100.

| Feature | Formule | Interprétation |
|---|---|---|
| `benchmark_return_1` | `produit(1+r_b,1)-1` | Contexte de marché de la dernière séance |
| `benchmark_return_5` | `produit(1+r_b,5)-1` | Mouvement du benchmark sur 5 séances |
| `benchmark_return_10` | `produit(1+r_b,10)-1` | Mouvement du benchmark sur 10 séances |
| `benchmark_return_20` | `produit(1+r_b,20)-1` | Mouvement du benchmark sur 20 séances |
| `excess_return_1` | `return_1 - benchmark_return_1` | Sur/sous-performance quotidienne |
| `excess_return_5` | `return_5 - benchmark_return_5` | Force relative sur 5 séances |
| `excess_return_10` | `return_10 - benchmark_return_10` | Force relative sur 10 séances |
| `excess_return_20` | `return_20 - benchmark_return_20` | Force relative sur 20 séances |
| `beta20` | `cov(r_i,r_b)/var(r_b)` sur 20 paires | Sensibilité récente aux mouvements du benchmark |
| `correlation20` | `cov(r_i,r_b)/(std(r_i)*std(r_b))` | Co-mouvement titre/marché, borné à [-1,1] |
| `relative_volatility20` | `std(r_i)/std(r_b)` | Volatilité du titre rapportée au benchmark |
| `residual_return20` | `return_20-beta20*benchmark_return_20` | Approximation du mouvement hors exposition marché |

Covariances/variances sont échantillonnales (`ddof=1`). Les deux variances doivent dépasser `1e-12` pour publier les trois statistiques : un benchmark ou un titre pratiquement constant ne donne pas de corrélation exploitable. `residual_return20` n'est pas une somme de résidus issus d'une régression, ni une estimation d'alpha futur ; c'est une approximation descriptive utilisant le bêta historique courant. L'excès de rendement est une différence arithmétique, pas `(1+R_i)/(1+R_b)-1`.

## Disponibilité et garde-fous PIT

Pour une décision à l'ouverture J+1, les features utilisent la séance source J et ses antécédents seulement. Les deux dates sont contrôlées contre la succession des séances officielles XPAR. `benchmark_available_at` est l'ouverture de la séance suivante ; aucune entrée ne peut être disponible après `decision_at`. `max_input_available_at` est le maximum de la disponibilité titre et benchmark.

Cette convention reste **`RESEARCH_J1_HYPOTHESIS_NOT_VERIFIED_PUBLICATION`** : une disponibilité reconstruite pour la recherche n'est pas une preuve de réception réelle historique. Le lot ne rend pas le marché FR automatiquement tradable/live.

Pour le benchmark, chaque fenêtre doit rester dans une séquence KNOWN du même segment. Une valeur manquante, un état UNKNOWN ou une rupture impose un nouveau warm-up. Un segment réutilisé après interruption, un doublon, une disponibilité non J+1 ou une observation UNKNOWN contenant un rendement provoquent une erreur.

Pour bêta/corrélation/volatilité relative, le rendement quotidien du titre provient du panel prix figé et est réindexé sur **toutes les séances**, sans compression des jours absents. Il faut 20 paires consécutives finies. Les séances où le titre était absent du panel candidat ne sont pas réintroduites depuis une autre archive ; cette politique conservative augmente la perte de couverture. Aucun remplissage, interpolation ou estimation sectorielle n'est utilisé.

## Support commun pour comparer les deux profils

Toutes les 170 046 candidates sont conservées. Les 14 colonnes prix et leurs masques historiques restent inchangés.

- `benchmark_complete` : les 12 nouvelles features sont finies ;
- `common_row_ready` : les 26 features sont finies et au moins 20 titres satisfont cette complétude le même jour ;
- `common_period_coverage_state` : qualification du semestre avec **exactement les mêmes gates** que 7-A2 ;
- `common_offline_qualified` : intersection du semestre GO prix, du semestre GO conjoint et du masque conjoint de séance.

Pour une future expérience, prix seul et prix+benchmark devront être entraînés/évalués sur **les mêmes clés `(decision_session_date,research_uid)` sélectionnées par `common_row_ready`**, avec labels, folds, purge et embargo identiques. Il faut également publier les résultats prix-only sur sa couverture d'origine afin de distinguer l'effet des features de l'effet du sous-échantillonnage.

Le gate semestre est une qualification rétrospective des données, **pas un signal PIT de trading** : ne jamais utiliser la couverture finale d'un semestre pour décider une entrée au début de ce semestre. Les semestres bloqués doivent rester dans les diagnostics et sensibilités, avec leurs causes explicites. Il ne faut pas les supprimer pour fabriquer une performance favorable.

## Couverture mesurée

| Mesure | Nombre |
|---|---:|
| Candidates conservées | 170 046 |
| Prêtes prix-only | 146 293 |
| Prêtes sur le support commun à 26 features | 119 505 |
| Perte par rapport au prix-only | 26 788, soit 18,31 % |
| Support commun dans les semestres qualifiés | 41 282 |

| Semestre | Lignes communes prêtes | Lignes prêtes perdues vs prix-only | Gate conjoint |
|---|---:|---:|---|
| 2018H1/H2 | 0 | 0 | Burn-in, bloqué |
| 2019H1 | 4 392 | 1 708 | Bloqué |
| 2019H2 | 5 489 | 2 971 | Bloqué |
| 2020H1 | 6 085 | 3 145 | Bloqué |
| 2020H2 | 7 933 | 1 333 | Bloqué |
| 2021H1 | 4 019 | 2 309 | Bloqué |
| 2021H2 | 6 815 | 3 441 | Bloqué |
| 2022H1 | 8 571 | 1 990 | Bloqué |
| 2022H2 | 9 887 | 523 | GO données |
| 2023H1 | 9 825 | 660 | GO données |
| 2023H2 | 8 090 | 1 230 | Bloqué |
| 2024H1 | 6 566 | 1 725 | Bloqué |
| 2024H2 | 10 052 | 548 | GO données |
| 2025H1 | 7 000 | 1 932 | Bloqué |
| 2025H2 | 11 518 | 725 | GO données |
| 2026H1 | 8 925 | 2 328 | Bloqué |
| 2026H2 au 2 octobre | 4 338 | 220 | Bloqué, partiel |

Les gates restent 80 % de lignes prêtes, 80 % des séances officielles couvertes, au moins 40 séances et semestre complet. **Quatre semestres passent**, contre douze en prix-only. Le benchmark à 1 séance est connu sur 167 785 lignes, à 20 séances sur 129 935 ; les statistiques conjointes sur 20 séances sont présentes sur 119 505 lignes. La dégradation vient des fenêtres traversant les ruptures et des historiques titre discontinus ; elle ne démontre ni inutilité ni utilité prédictive du benchmark.

## Fichiers, exécution et preuves

- Configuration : `config/features_fr/fr_price_benchmark_v1.yaml`.
- Module : `modelFactory/fr_benchmark_features.py`.
- Tests : `tests/test_fr_benchmark_features.py`.
- Artefact final : `artifacts/fr/features/fr_price_benchmark_v1/fr-benchmark-v1-bc8f18f98f29/`.
- `panel.parquet` : panel enrichi, états de benchmark, disponibilité, masques par feature et support commun.
- `report.json` : dictionnaire relatif, configuration, empreintes, comptes par semestre/feature et provenance.

```powershell
python -u -m modelFactory.fr_benchmark_features --verify-rebuild
```

La commande a été exécutée, deux fois avec vérification d'identité. Hash du panel : `69c3ccfcc34bc2d29bc1d33f920c1dfbf2453abcd00f95bf486255633315eb3d`. Le profil prix et le benchmark source sont verrouillés par SHA-256 ; le rapport du profil prix et son contrat sont vérifiés. La version inclut les empreintes du code d'enrichissement et de qualification, les rapports source et le calendrier. Un artefact final différent n'est pas écrasé silencieusement.

Les prototypes d'artefacts d'une version antérieure du module peuvent subsister ; le répertoire ci-dessus désigne la version finale de ce lot. Les sources 7-A/7-A2/6-C restent inchangées.

**164 tests ciblés passent**, dont 12 tests nouveaux : composition des rendements, premières fenêtres complètes, rupture/UNKNOWN, bêta et corrélation connus, volatilité relative, absence de compression des séances titre, variance nulle, doublons, calendrier, segment réutilisé, disponibilité future et invariance des features passées après modification du futur. Ruff passe. Cette validation ne correspond pas à l'ensemble des tests applicatifs.

Aucune migration SQL, écriture canonique, tâche planifiée ou modification US/CN ; aucun batch en cours touché. Le panel n'est pas encore branché à l'IHM d'entraînement ni au serving. Les memberships sectoriels restent UNKNOWN.

## Suite

Avant toute conclusion ML, construire les labels France avec maturité et disponibilité contrôlées, puis figer les folds purgés. Comparer la baseline prix-only et le profil enrichi sur support commun, sans modifier leurs listes de features ni les gates après lecture du test. La couverture historique fragmentée interdit de présenter quatre semestres disjoints comme une validation continue 2019–2026.
