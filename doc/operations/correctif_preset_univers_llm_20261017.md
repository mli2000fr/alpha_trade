# Étape 11 LLM — preset d’univers distinct de l’equity de sizing

## Cause de l’échec du 17 octobre à 21:29

La reprise du run IHM `20261017_212959_2ad0b4d6` a bien passé le calcul du régime.
L’échec suivant était `UniverseSnapshotNotFoundError` sur `capital_0_2000`.

L’analyse `llm-fa604bed142d41a7be61012432c1fc6e`, séance du 16 octobre, archive
`capital_2001_5000` dans son `input_json`. Le risque choisissait pourtant son
preset d’univers uniquement à partir de l’equity PAPER réelle (**1 974,30 USD**),
donc `capital_0_2000`, alors que seul l’univers `capital_2001_5000` était publié.
La réservation prise à 21:30:00 Paris est restée active après cet échec ; les
relances de 21:36 et 21:37 se sont donc arrêtées sur « Risque déjà tenté ».

## Correctif

- Avec un filtre LLM : le preset d’univers est celui du snapshot archivé,
  après validation complète de l’analyse (`qualified_selection`). Un preset
  absent, invalide ou inconnu est bloquant, sans fallback vers l’equity ou
  un autre univers.
- Sans filtre LLM : la résolution habituelle du preset par equity reste intacte.
- Le capital, le sizing, les budgets et les gardes restent fondés sur l’equity
  réelle du courtier. **Choisir cet univers ne simule pas un capital supérieur
  à 2 000 USD et n’applique pas ses paramètres de sizing.**
- La qualité `full` de la publication et l’appartenance du titre à l’univers
  tradable demeurent obligatoires. Aucun univers fictif n’est créé.
- Les logs, la progression et le résumé risque distinguent désormais
  `universe_capital_preset_key`, `universe_preset_source`, `universe_run_id`
  et `llm_filter_run_id`.

Implémentation : `service/llm_directional/risk_adapter.py`
(`archived_universe_preset`) et `risk_management/cli.py`
(`_load_tradable_universe_for_risk`).

## Contrôle réel en lecture seule

Le nouveau chargement retrouve :

- preset `capital_2001_5000`, source `llm_archived_input` ;
- publication `universe-1e6cf5f693b24be3881eb38186d77572`, qualité `full` ;
- **297 titres tradables**, avec une equity de sizing toujours **1 974,30 USD** ;
- **FMC absent de cet univers** : son avis LLM SHORT ne suffit pas à en faire
  une cible risque. Le filtre d’appartenance doit le rejeter, sans substitution
  par un autre titre et sans élargissement implicite de l’univers.

Ce contrôle ne lance pas le risque complet, n’interroge pas GPT/DeepSeek et
n’envoie aucun ordre. Il ne réinitialise pas la nouvelle réservation risque.
La reprise de la tentative de 21:29 nécessite donc encore une vérification et
un réarmement contrôlé ; ne pas relancer l’étape 10 pour contourner ce verrou.

Tests : `tests/test_llm_universe_preset.py` couvre le franchissement du seuil
de 2 000 USD, l’absence de modification de la configuration de sizing, les
archives altérées, les presets non qualifiés, les publications manquantes,
le parcours sans LLM et l’exclusion d’un titre hors univers tradable.

Validation élargie : **312 tests passent**, incluant la CLI risque, les archives
LLM, les SHORT, les reprises manuelles, le lecteur d’état régime et le batch LLM.
