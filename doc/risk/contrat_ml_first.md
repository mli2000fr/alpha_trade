# Contrat ML-first entre prédiction, sélection et risque

Retour : [références Risk](README.md)

## Autorité de décision

`risk_management/selection_contract.py` fixe la frontière : le ML est l’autorité nominale sur le côté et le ranking. Le selector apporte contexte et vetos, le régime et le risque peuvent rejeter ou réduire, mais ne doivent ni inventer un candidat ML, ni retourner son côté, ni le reclasser avec un score technique.

Flux canonique :

`univers PIT full → prédictions compatibles → candidats ML → rankings long/short → vetos → régime → sizing → contraintes → targets`.

## MLRankedCandidate

Le DTO immutable contient symbole, date, côté `long|short|flat`, probabilités ternaires, `p_side`, rang par côté, edge éventuel, model run id, version de policy, universe run id, cutoffs, lineage, indicateur research-only et compte.

Le constructeur exige symbole, côté valide, model run id et policy version positive. Pour long, `p_side` doit correspondre à `p_long`; pour short, à `p_short`. `flat` n’est jamais actionable.

`build_candidate_from_prediction()` normalise le symbole en majuscules. Un côté absent ou inconnu devient `flat`, comportement défensif qui empêche l’exécution mais doit rester visible dans les métriques.

## Validations

`validate_candidate_consistency()` contrôle :

- symbole, côté, model run id et policy version ;
- chaque probabilité dans [0,1] ;
- somme ternaire égale à 1 à tolérance `1e-4` ;
- cohérence `p_side`/classe ;
- date de trade présente.

`validate_payload_completeness()` ajoute les exigences de lineage : universe run id, feature cutoff et compte. Ces contrôles doivent être passés avant le bridge legacy ou le portfolio builder.

## Temps point-in-time

Les features sont disponibles après la clôture J, la décision porte la date J et l’entrée la plus proche est l’open tradable J+1. `compute_entry_date()` utilise le calendrier de marché.

`validate_decision_timing()` vérifie : décision sur jour de bourse, feature cutoff non postérieur à J, decision cutoff daté J et prochaine séance strictement après J. Un timestamp présent reste plus précis que sa seule date ; les consumers sensibles à l’heure doivent préserver timezone et cutoff, pas seulement comparer `.date()`.

## Ranking

`build_rankings()` retire implicitement flat, sépare long et short, trie chaque côté par `p_side` décroissant puis attribue `side_rank` à partir de 1. Les deux rangs ne sont pas un classement global commun.

Les contraintes peuvent produire un rang final différent après budget, corrélation et concentration. Conserver rang ML initial, motif de rejet et rang final afin de distinguer alpha et portefeuille.

## Selector et bridge legacy

`SelectorVetoContext` contient secteur, qualité, blackout earnings, veto, reason code, score informatif et explication. Il ne possède volontairement aucun champ side/rank.

`to_selection_score()` est un adaptateur de compatibilité marqué temporaire dans le code : `p_side → score_used`, long/short → buy/sell, `side_rank → selection_rank`, model run id → calibration id et `score_source="ml_p_side"`. Un nouveau développement ne doit pas redonner au DTO legacy une autorité que le contrat ML-first retire.

## Gates ML

Deux protections différentes existent :

1. le gate de couverture compare nombre de prédictions et taille de l’univers contre `--min-ml-coverage-ratio` ;
2. `ml_gate.py` combine le kill manuel `disable_ml` et la dernière décision `drift_policy_decision` de `ml_drift_runs`.

La priorité est kill manuel, puis action drift `kill_switch_ml` ou gate disabled, puis activation par défaut si aucune décision n’existe. Le summary conserve raison, decision id, drift status et action.

Le helper `apply_ml_gate_to_risk_config()` tente un mode quant-only en posant poids score à 1 et prédiction à 0 lorsque le gate est fermé. C’est un chemin de compatibilité explicite, distinct du flux ML-first nominal. Il ne doit pas être présenté comme un fallback silencieux équivalent : le summary doit montrer que ML est désactivé et aucune décision ML ne doit être attribuée à ce run.

## Chargement et compatibilité des prédictions

Le CLI charge les prédictions as-of pour les symboles de l’univers seulement si le gate autorise ML. Il vérifie couverture, ids modèle/champion, batch/date et champs utilisables avant de construire les candidats. Les modèles incompatibles, prédictions futures, probabilités invalides ou symboles hors univers deviennent erreurs ou rejets codifiés.

## Invariants de production

- Univers publié `full` et identifié.
- Prédiction disponible au cutoff, jamais future.
- Feature cutoff ≤ décision ; entrée ≥ prochaine séance.
- Côté et rang proviennent du ML dans le mode ML-first.
- Flat ne passe pas au sizing.
- Selector = veto/contexte uniquement.
- Compte, batch, modèle, policy et universe run traçables.
- Pas de passage score-only silencieux.
- Toute baisse de couverture visible et bloquante selon le seuil.
- Chaque candidat accepté ou rejeté produit une décision auditable.

## Tests indispensables

Tester probabilités bornées/somme, side mismatch, flat, ranking séparé, égalités, payload incomplet, week-end/jour férié, cutoff futur, couverture sous seuil, kill manuel, kill drift, absence de décision drift, mismatch champion et compte absent.

## Diagnostic

| Symptôme | Vérification |
|---|---|
| aucun candidat | gate ML, couverture, prédictions as-of, flat |
| côté inattendu | predicted_side et policy, jamais selector |
| rang différent | rang ML initial contre rang portefeuille final |
| quant-only | reason du ML gate et feature flag |
| look-ahead | feature/decision cutoff et date d’entrée |
| modèle mélangé | model run ids, champion et batch |

