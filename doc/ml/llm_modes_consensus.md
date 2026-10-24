# Oracle → filtre LLM : Web ou données locales

Depuis le 24 octobre 2026, le mode courant `scoring_mode: direction_1_10`
utilise le protocole v8, score /10 et seuils stricts configurables, dans les
quatre parcours fournisseur × mode. [Contrat v8 et compatibilité des archives](llm_score_directionnel_v8.md).
Les descriptions v5–v7 ci-dessous documentent le socle et les archives, pas une
conversion des anciennes notes de confiance.

Audit complémentaire : [quelles données des batchs ajouter au contexte LLM](audit_donnees_batchs_contexte_llm_20261019.md).
Inventaire en base, couvertures/fraîcheur et réserves de qualification ; aucun
nouveau branchement opérationnel effectué par cet audit.

Livraison du 19 octobre 2026. Les nouvelles analyses opérationnelles de l’étape
10 figent le contexte local puis utilisent l’un des **deux prompts distincts**
de `service/llm_directional/prompts.py`. Le protocole courant est désormais
`oracle-fresh-evidence-trend-v7` pour les quatre parcours. Il ajoute le calendrier,
les extraits SEC et les résumés prix/volume/fondamentaux, avec contrôles de fraîcheur
par famille. [Contrat v7 et aperçu réel](llm_preuves_fraiches_20261019.md).
Les descriptions v5/v6 ci-dessous restent l'historique du socle ; les limites v7
plus restrictives font foi pour les nouvelles analyses. Les archives v4/v5/v6
restent lues avec leur contrat historique, sans réécriture.

## Choisir le mode dans config.yaml

```yaml
llm_directional_filter:
  analysis_mode: local_data_only  # ou web_search
  provider: openai              # ou deepseek
```

La configuration courante reste `provider: openai` et `analysis_mode: local_data_only` ;
cette évolution ne change pas ces choix. Pour DeepSeek avec Internet, choisir
`provider: deepseek` et `analysis_mode: web_search`, puis lancer une nouvelle étape 10.
Une analyse déjà terminée garde son fournisseur/mode et son contexte archivés.
Les étapes 11/12 utilisent son identifiant exact, pas les nouvelles valeurs YAML.

| Mode | GPT | DeepSeek | Preuves demandées |
|---|---|---|---|
| `local_data_only` | Un appel Responses, outils vides et `tool_choice: none` | Un appel direct DeepSeek, aucun appel OpenAI ; seule DEEPSEEK_API_KEY nécessaire | Références locales et citations exactes dans le contexte fourni |
| `web_search` | OpenAI avec recherche Web + même contexte local | Search / Fetch natifs DeepSeek puis analyse DeepSeek, sans appel OpenAI ; seule DEEPSEEK_API_KEY nécessaire | Sources Web traçables/récentes, plus références locales si utilisées |

Aucun repli automatique entre modes/fournisseurs, aucune génération payante de
validation lancée lors de cette livraison. Le mode local réduit les appels
externes, mais les textes transmis et la réponse consomment toujours des tokens.
Le Web conserve `min_sources` ; en v7 sa fenêtre est le minimum de
`max_source_age_days` et `evidence_news_max_age_days`. Le local utilise
`min_local_sources` ; le seuil de confiance et le plafond de sélection restent
communs. Les modèles configurés ne sont pas remplacés.

Référence API officielle : [sorties structurées OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs).
La structure JSON ne garantit ni exactitude factuelle, ni calibration des scores.

## Recherche native DeepSeek — 19 octobre 2026

Le nouveau contrat n'utilise ni GPT comme relais ni une synthèse GPT préalable :

1. `POST https://api.deepseek.com/v1/tools/search` : deux requêtes déterministes
   par titre (résultats/guidance et risques/dilution/dette), cinq résultats au plus
   par requête, `need_content: true`, identité publique et fenêtre de dates uniquement.
2. `POST https://api.deepseek.com/v1/tools/fetch` : jusqu'à deux URL distinctes
   effectivement renvoyées, jamais une URL inventée par le modèle. Les URL privées,
   avec identifiants, hors HTTP(S) ou ports non standards sont exclues.
3. `POST https://api.deepseek.com/chat/completions` : modèle `deepseek_model`
   inchangé, consensus/news locaux figés et textes/résumés Web bornés. Même objectif
   de tendance, mêmes seuils de confiance/sources, mêmes protections PAPER.

```yaml
llm_directional_filter:
  provider: deepseek
  analysis_mode: web_search
  deepseek_model: deepseek-flash
  deepseek_api_key_env: DEEPSEEK_API_KEY
  max_tool_calls: 5
  deepseek_search_queries: 2       # 1–2, tronqué au budget Web
  deepseek_search_results: 5       # 1–10 par requête
  deepseek_fetch_pages: 2          # 0–5, limité au budget restant
  deepseek_web_text_chars: 6000    # 500–12000 par source
```

`max_tool_calls` est une borne **locale dure** sur Search + Fetch, hors l'appel
d'analyse. Par défaut : au plus quatre appels Web et un appel d'analyse par titre.
Un petit budget réduit d'abord Fetch ; il reste toujours au moins une recherche.
Les requêtes Search restent sous 128 caractères Unicode. Aucun compte, position,
clé ou consensus n'est inséré dans les requêtes au moteur de recherche.
La cadence séquentielle du client est bornée à quatre appels Web par seconde ;
la limite fournisseur est partagée au niveau du compte (plusieurs processus
peuvent donc encore recevoir HTTP 429). Aucun retry payant automatique ni repli GPT.

Les erreurs techniques de Search ou d'analyse bloquent le run ; les reçus déjà
obtenus restent archivés. Fetch 403/404 est conservé comme page inaccessible,
sans contournement ni nouvelle tentative : seul le contenu Search disponible
reste transmis, sans prétendre avoir ouvert cette page. Les autres erreurs Fetch
bloquent. Une recherche sans résultat peut produire une abstention valide ;
elle ne suffit pas à qualifier un LONG/SHORT.

Les dates de publication doivent être copiées exactement depuis le champ `date`
du résultat Search : inconnue → `null`, jamais remplacée par l'heure de réception.
Une date inventée/modifiée exclut la source et bloque l'admissibilité. Une date
fournisseur même précise reste une **déclaration non certifiée PIT**. Les résumés
ne sont pas présentés comme lecture intégrale ; `page_fetched` et
`content_truncated` distinguent lecture Fetch et texte borné. Les contenus restent
des données non fiables, sans exécution d'instructions issues des pages.

Le tool Responses intégré `web_search` est documenté pour `deepseek-v4-pro`,
mais ignoré par `deepseek-flash`, et `max_tool_calls` y est ignoré. D'où l'usage
explicite des API Search/Fetch, sans changer silencieusement de modèle.
[Search & Fetch](https://api-docs.deepseek.com/guides/search/),
[compatibilité Responses](https://api-docs.deepseek.com/guides/responses_api/).

Les archives hybrides historiques gardent leurs requêtes et preuves OpenAI et
peuvent être revalidées par les étapes 11/12. Le transport refuse de les renvoyer
comme nouvelles analyses DeepSeek : lancer une nouvelle étape 10. L'ancien
comparatif de recherche à preuves GPT partagées reste consultable/preview mais
ses nouveaux appels payants sont bloqués ; il ne faut pas le présenter comme
une comparaison indépendante avec le nouveau moteur.

## Objectif : tendance, pas barrières

À la demande finale de l’utilisateur, **aucun objectif TP/SL n’est demandé au
LLM**. Il doit juger la tendance qualitative haussière, baissière ou indéterminée
sur `horizon` séances (20 actuellement), répondre LONG/SHORT/ABSTAIN, expliquer
les scénarios favorables, contraires et les incertitudes. Le score Oracle reste
une amplitude ; la confiance LLM n’est pas une probabilité de gain.

Il ne doit pas prédire un prix exact, un ordre de franchissement TP/SL ou une
garantie de rendement final H20. Les blocs `oracle_barrier`, `oracle_backtest`
et `llm_directional_filter.protections` ne sont **pas modifiés**. SL, trailing,
sortie temporelle, sizing et contraintes de risque/exécution restent distincts.
Le filtre demeure réservé au compte principal PAPER et à la fenêtre prospective
après clôture J / avant ouverture US suivante ; ce n’est pas un nouveau backtest.

## Ce qui est effectivement transmis

Le constructeur opérationnel conserve symbole, identité locale, score/rang
Oracle, date/horizon et 21 clôtures réelles au plus jusqu’à J, puis ajoute un
cutoff UTC réel unique avant les appels et les preuves suivantes **dans les deux modes**.

### Consensus EODHD

Lecture exclusive de `alpha_trade.stock_analyst_consensus_eodhd_history` :
EPS moyens/bas/haut, comptes d’analystes, revenus et croissances fournisseur,
EPS courant/J−7/30/60/90, compteurs de révisions, qualifications, date fiscale,
horizon brut, date/heure de collecte, run d’origine et empreinte source.
Les valeurs NULL restent NULL, et les unités/devise inconnues ne sont pas inventées.

Une seule date de collecte récente est choisie avant le cutoff, puis la période
la plus proche pour chaque horizon brut (`0q/+1q/0y/+1y`), jusqu’au plafond de
`consensus_max_periods` (4). Les périodes récemment closes sont incluses : une
fin de trimestre précède souvent l’annonce des résultats. La borne basse fiscale
est de 120 jours, pour ne pas envoyer toutes les anciennes périodes retournées
par EODHD. Cela ne certifie pas l’affectation fiscale des horizons fournisseur.

Jusqu’à `consensus_history_count` (3) snapshots antérieurs réellement collectés
pour chaque même période/horizon sont joints, dans la fenêtre récente de
`consensus_max_age_days` (7). Aucune interpolation ni fausse collecte J−7/30/60/90.
`available_at` et `observed_at` doivent précéder strictement le cutoff, avec une
horloge de réception cohérente. Aucun appel fournisseur n’est déclenché.

Les valeurs RESEARCH_ONLY et les unités/périodes non qualifiées sont envoyées
comme **contexte provisoire**. Elles ne comptent pas seules comme preuves
autorisant une sélection locale. Il faut les marqueurs explicites d’unités et
d’identité fiscale qualifiées, un statut connu `QUALIFIED`, `VALIDATED` ou
`PROSPECTIVE_QUALIFIED`, et des valeurs pertinentes. Aucun statut n’est modifié.
`historical_pit_qualified=false` reste visible : une réception prospective connue
ne prouve pas l’historique des consensus avant notre collecte.

### Actualités locales

Uniquement les versions et reçus scellés de `news_raw_versions`,
`news_ticker_map_versions` et `news_archive_observations`. Texte et mapping
émetteur doivent correspondre à la même version, être reçus avant cutoff,
avec origine fournisseur EODHD/Alpaca et publication horodatée explicite récente.
Une version/mapping plus récente, pendante ou contradictoire n’est pas utilisée
pour attribuer un ancien texte au mauvais titre.

Échantillon borné à `local_news_max_articles` (8), chaque texte limité à
`local_news_max_chars` (2 400) caractères, troncature signalée. Les doublons
d’article sont retirés ; la sélection ne lit aucun rendement futur. Le mapping
fournisseur seul ne vaut pas qualification d’émetteur : une news non qualifiée
reste du contexte et ne compte pas seule pour une entrée locale. Les scores de
`news_ticker_sentiment` ne sont pas joints faute de liaison versionnée score/texte
prouvée ; aucun repli sur les tables courantes mutables ou Yahoo.

Les tables absentes ou l’absence de données sont signalées dans `local_data_status`.
Une erreur SQL réelle n’est pas maquillée en absence normale de données.
Le mode Web reste soumis à ses preuves Web ; le local peut légitimement
s’abstenir, notamment si toutes les données sont encore RESEARCH_ONLY.

## Réponse, archivage et contrôles

Les deux prompts requièrent les scénarios haussier/baissier, catalyseurs,
`consensus_analysis`, décision et confiance subjective. `local_evidence` contient
les identifiants fournis et des citations textuelles exactes. Une référence
inventée ou une citation absente du texte bloque l’admissibilité ; aucun outil
ou URL Web n’est accepté en local. Une abstention est une réponse valide ; une
erreur technique conserve un run échoué, sans candidats publiés.

- `llm_directional_runs.input_json` : contexte complet figé, preuves/cutoff et empreinte ;
- `llm_directional_runs.config_json` : mode, fournisseur, paramètres archivés ;
- `llm_directional_assessments.request_json/response_json` : requête et réponse exactes ;
- `assessment_json` : analyse du consensus, citations, qualifications et motifs d’exclusion.

Pour DeepSeek Web natif, `response_json` contient aussi `search_receipts`,
`fetch_receipts` (requêtes exactes, réponses brutes et horodatages UTC réels),
`analysis_request` et `analysis_response` (dont consommation fournisseur).
`request_json` archive le plan borné, le prompt et le contexte. Le validateur
reconstruit les URL depuis les vrais reçus Search, pas depuis les citations ou
les traces de confort produites par le modèle. Pas de nouvelle table/migration.

Aucune nouvelle table ni migration. Aucune ancienne analyse réécrite. La
revalidation des étapes 11/12 utilise l’archive, sans relire le consensus courant.
Les notifications et l’IHM indiquent le mode ; l’audit de sélection permet de
consulter l’analyse du consensus et les preuves citées.

Le bloc consensus de la **popin graphique** reste une consultation à fin de J
New York, indépendante du paquet effectivement transmis. Le filtre peut utiliser
des observations reçues après J et avant son cutoff prospectif préouverture.
Le contexte exact fait foi dans les archives de l’analyse, pas dans la popin.

## Vérification

Tests SQLite/faux transports : inclusion/exclusion au cutoff, périodes récemment
closes, historique fiscal identique, valeurs manquantes, reçus pendants,
citations inventées, abstention, absence d’OpenAI pour DeepSeek local,
transmission du même consensus en Web, conservation des archives v4 et rejeu des
analyses v5 sans lecture de nouvelles données. Aucun appel API payant, aucun
ordre, aucune collecte, aucune qualification SQL de production.

Code : `service/llm_directional/local_evidence.py`, `prompts.py`, `openai_client.py`,
`validation.py`, `runner.py`. Tests spécifiques : `tests/test_llm_local_data.py`.

Pour le parcours natif : `service/llm_directional/deepseek_search.py` et
`tests/test_llm_deepseek_search.py`. Bilan final de régression : **749 tests passent**
(filtre, traces, archives v4/v5/v6, consensus, modes locaux, préflight sans OpenAI,
SHORT, protections, dates, IHM et batch). Tests simulés ; accès Search/Fetch réel
avec la clé de l'utilisateur non vérifié, aucun succès API payant revendiqué.
