# Cascade de modèles et politiques de fallback

## Principe

Une cascade essaie des sources/modèles selon une priorité et conserve la
première sortie admissible. Elle augmente la couverture, mais rend la population
hétérogène. La priorité, les conditions d’admissibilité et l’identité servie
doivent être observables.

## États à distinguer

```text
candidat disponible ?
  non → niveau suivant
  oui → artefact compatible ?
          non → niveau suivant + motif
          oui → gate qualité ouvert ?
                  non → niveau suivant/blocage selon politique
                  oui → servir et persister selection_mode
```

Un fallback neutre ou non-ML ne doit pas être étiqueté comme prédiction du
modèle principal.

## Risques

- comparaison de scores d’échelles différentes ;
- biais de sélection si les cas difficiles tombent systématiquement en fallback ;
- métrique globale attribuée au mauvais modèle ;
- backtest utilisant un fallback indisponible à la date ;
- changement de priorité non visible dans la configuration du run.

## Validation

Mesurer performances et couverture par niveau, taux de transition, raisons et
stabilité temporelle. Tester aussi le système privé d’un niveau afin de mesurer
sa valeur marginale. La parité live/backtest exige la même résolution PIT et le
même ordre de cascade.

Voir [cascade de sélection recherche](../research/cascade_selection.md),
[qualité/couverture](qualite_couverture_et_fallbacks.md) et
[audit serving](../guide_utilisateur/05_ml_predictions.md).

