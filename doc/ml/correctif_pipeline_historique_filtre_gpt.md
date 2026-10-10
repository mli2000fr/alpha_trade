# Correctif Pipeline — filtre GPT et boutons de prédiction historique

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Cause et correction du 9 octobre 2026

Le filtre GPT/recherche Web peut être coché par défaut pour le parcours
prospectif PAPER. Le bloc de prédiction historique de la page Pipeline
héritait de ce choix au moment de construire son aperçu de commande.
`_wrap_llm_command` refusait correctement historique/Oracle shadow, mais
son exception interrompait le rendu de la page.

Le bloc historique/shadow construit maintenant une **copie locale** des
options avec `llm_filter_enabled=False`. La commande affichée et le lancement
utilisent exactement cette même copie. Un message précise « sans LLM ».
Le choix global et le filtre PAPER du jour restent inchangés.

Le garde-fou du runner reste intact : un appel direct demandant à la fois
LLM et historique/shadow est toujours refusé. Pas de recherche Web rétrospective,
pas de contournement LIVE et pas d'appel OpenAI dans les tests.

Fichier corrigé : `ihm/pages/pipeline.py`.
Tests : `tests/test_pipeline_historical_llm_scope.py` (5 cas), incluant
le rendu réel du bloc avec mocks et identité des options aperçu/lancement.

Les 154 tests ciblés de scope, page Pipeline et filtre LLM passent.
Avec la suite du runner Pipeline, 236 tests ciblés passent également.

```powershell
python -m pytest tests/test_pipeline_historical_llm_scope.py tests/test_pages_pipeline.py tests/test_llm_directional_filter.py --no-cov -q
```

Recharger la page, puis vérifier le bloc historique : commande Model Factory
sans `service.llm_directional.pipeline`, message explicite sans LLM. Si le
serveur ne recharge pas le code, redémarrer l'IHM. Aucun processus utilisateur
n'a été arrêté et aucun pipeline n'a été lancé pendant le correctif.
