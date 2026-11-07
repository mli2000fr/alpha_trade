# Modèle financier exécuté localement — recherche

`v1/research_veto.txt` est le prompt dédié au test 2025 de Qwen3.5-9b après
per-symbol, identifiant `local.oracle_directional.v1.research_veto` dans le
catalogue. Il demande une appréciation et des faits cités, avec indétermination
explicite lorsque les preuves manquent. Il ne passe aucun ordre.

Client : `service/local_ai/lm_studio.py`. Protocole et commandes :
[Test A/B 2025](../../../../../doc/ml/llm_local_winner_ab_2025.md).
Ce pilote indépendant ne raccorde pas le modèle local au pipeline de production.
Le prompt reste distinct des versions cloud, sans repli automatique.
