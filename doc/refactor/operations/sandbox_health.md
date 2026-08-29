# Sandbox health nocturne

`ihm/services/sandbox_health_loader.py` lit `artifacts/sandbox_runs/_rollup.json` et `<date>/health.json`. Absence ou JSON invalide retourne `{}` : distinguer « aucune preuve lisible » d’un run vert. La page et l’aide sont dans `ihm/pages/sandbox_health.py` et `ihm/help/sandbox_health.yaml`.

## Triage

1. identifier date et étape en échec ;
2. ouvrir l’artefact du workflow ;
3. classer migration, pre-live, données, screener/selector/risk, exécution, réconciliation ou audit ;
4. reproduire avec même commit/config ;
5. corriger ou classer l’incident fournisseur ;
6. relancer et vérifier le rollup.

Un échec inexpliqué concernant ordres, PIT, risque, protections, réconciliation ou audit impose NO-GO. Conserver artefact initial, diagnostic, test de régression et run vert de confirmation.

