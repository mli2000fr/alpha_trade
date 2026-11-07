# Connexion locale LM Studio

Vérifiée le 7 novembre 2026 sur `http://127.0.0.1:1234/v1` : modèle exposé
`qwen3.5-9b`, réponse finale `LM_STUDIO_OK` en 5,49 secondes, arrêt normal.
73 tokens d'entrée, 202 de sortie dont 195 de raisonnement, selon le serveur.
Le second identifiant exposé est un modèle d'embeddings ; il n'a pas été appelé.

Configuration réutilisable : `config/ia/connections/lm_studio.yaml`.
Client : `service/local_ai/lm_studio.py`. Les appels passent par les endpoints
compatibles OpenAI `/v1/models` et `/v1/chat/completions` de **LM Studio local**,
pas par les serveurs OpenAI.
[Documentation LM Studio](https://lmstudio.ai/docs/developer/openai-compat/chat-completions).

La connexion est limitée à la boucle locale, sans redirection, proxy d'environnement,
reprise automatique ni repli cloud. Une clé facultative se lit uniquement dans
`LM_STUDIO_API_KEY` si l'authentification du serveur est activée. Elle n'est pas
archivée dans les rapports. Le modèle demandé doit apparaître dans la liste du
serveur ; un autre modèle chargé ne le remplace pas automatiquement.

Le prompt de connectivité est distinct :
`config/ia/prompt/local/connectivity/v1/system.txt`, identifiant
`local.connectivity.v1.system` dans le catalogue. Aucun prompt financier cloud
n'a été réutilisé. Le modèle local n'est pas encore raccordé au filtre après
Oracle ni au risque, au backtest ou aux ordres ; ce changement n'active aucun
appel de trading et ne modifie pas `config.yaml`.

Pour refaire uniquement le test, laisser le serveur LM Studio démarré puis lancer :

```powershell
.\.venv\Scripts\python.exe -m service.local_ai.lm_studio --output-dir artifacts/operations/lm_studio_connection/nouveau-test
```

Le dossier doit être neuf. `report.json` contient la requête, la réponse et sa
consommation locale. Référence de validation réelle :
`artifacts/operations/lm_studio_connection/20261107-v1/report.json`.
Un statut `CONNECTED_RESPONSE_DIFFERS` prouve une réponse du serveur mais pas le
respect du texte demandé ; une réponse sans texte final est un échec explicite.
La connectivité ne démontre aucune fiabilité financière.
