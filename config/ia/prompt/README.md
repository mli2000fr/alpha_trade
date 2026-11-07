# Prompts IA — cloud et exécution locale

`cloud/` contient les prompts transmis aux API externes GPT/OpenAI et DeepSeek.
`local/` contient les prompts des modèles exécutés sur le PC. La connectivité
LM Studio dispose de son propre prompt ; aucun filtre financier local n'est
encore raccordé. [Connexion et test](../../../doc/operations/lm_studio_connexion_locale.md).

**`local_data_only` décrit les données fournies, pas le lieu d'exécution du
modèle.** Le prompt actuel reste donc sous `cloud/`, même sans recherche Web.

## Fichiers courants du filtre après Oracle

- `cloud/oracle_directional/v9/local_data_only.txt` : analyse cloud sur données locales seules.
- `cloud/oracle_directional/v9/web_search.txt` : analyse cloud avec recherche Web et données locales.
- `cloud/oracle_directional/output/v9.txt` : consigne finale du format de réponse.
- `cloud/oracle_directional/deepseek/` : compléments de transport propres à DeepSeek.

Les fichiers `v4` à `v8` conservent les contrats historiques. Ils ne sont pas
convertis vers v9. Les textes ont été extraits sans changer les requêtes.
Le Python conserve la sélection du protocole, les données, le schéma JSON et les
contrôles de sélection/risque ; les instructions en langage naturel sont ici.

## Catalogue et chargement

`catalog.json` déclare les identifiants, chemins, runtime (`cloud` ou `local`),
familles et versions. Exemple courant :
`cloud.oracle_directional.v9.local_data_only`.
Le chargeur partagé est `common.ia_prompts.load_prompt` ; `render_prompt` gère
les seules variables explicitement fournies sous la forme `{{response_schema}}`.
Il n'exécute pas le contenu des fichiers.

Les chemins sont résolus depuis le projet, indépendamment du répertoire de
lancement. Un fichier absent, vide, illisible ou hors du bon répertoire provoque
une erreur avant l'appel IA. Aucun repli automatique entre cloud et local, ni
vers un texte Python. Les fichiers sont relus à chaque nouvelle requête.
Modifier les fichiers entre deux analyses, pour conserver un même prompt sur
tous les titres d'un run.

## Modifier ou ajouter un prompt

1. Modifier le fichier de la bonne famille/version pour les nouvelles requêtes.
   Ne pas modifier les anciennes versions pour « corriger » les archives.
2. Pour une évolution de contrat (champs de réponse, sens d'un score, nouvelles
   contraintes), ajouter une nouvelle version et adapter explicitement le
   protocole/validateur avant de l'utiliser.
3. Pour le futur modèle local, créer ses propres fichiers sous
   `local/oracle_directional/<version>/`, puis une entrée de catalogue avec
   `runtime: local`. Son futur client devra demander explicitement ce runtime.
   L'ajout d'un fichier seul ne raccorde ni n'active un moteur local.

Les requêtes et réponses déjà archivées en SQL restent inchangées. Certains
contrôles reconstruisent une requête pour en vérifier l'intégrité : si son
prompt a changé, une ancienne analyse peut être refusée à la reprise ; lancer
alors une nouvelle étape 10. Aucun ancien résultat n'est réécrit.

Ces fichiers sous `config/` sont inclus dans le paquet « configuration » de
la sauvegarde T5.6.
