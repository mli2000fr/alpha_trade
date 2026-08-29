# Contrat ML-first du run risque

Retour : [références Risk](README.md)

Le scope vient de l'univers `full`; le côté et la priorité viennent des prédictions compatibles. `selection_contract.py` construit `MLRankedCandidate`, valide cohérence et payload, calcule l'entry date prochaine séance et interdit une décision utilisant une prédiction future.

`build_rankings` sépare les côtés et ordonne sur la probabilité directionnelle prévue. `filter_actionable` retire flat/non actionnables. Le selector est représenté par `SelectorVetoContext` : il peut bloquer, jamais créer un candidat sans ML.

Le run charge batch/date, contrôle couverture/fraîcheur, applique `ml_gate`, abstention et consistency checks. Chaque rejet devient `RiskDecisionRow` avec reason code. Les acceptés deviennent `PortfolioTargetRow` seulement après sizing et contraintes.

Invariants : date prédiction <= décision ; entry date > décision selon calendrier ; symbole dans univers ; probabilités finies ; côté cohérent ; pas de fallback score-only ; rang initial distinct du rang final.

