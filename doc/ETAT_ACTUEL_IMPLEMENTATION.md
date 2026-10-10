# État actuel de l'implémentation — 10 octobre 2026

Ce document rapproche les guides du **code et des fichiers de configuration
présents dans le dépôt**. Il ne certifie ni l'état d'une base déployée, ni la
santé des tâches Windows, ni une performance économique. Les comptes rendus de
sprints/expériences restent des preuves datées, pas des contrats d'exploitation.

## 1. Trois marchés, pas trois copies de l'application

| Marché | Base / alias | Devise, calendrier, heure métier | Capacité actuelle |
| --- | --- | --- | --- |
| US_EQ | alpha_trade / us_primary | USD, NYSE, America/New_York | Pipeline, ML, risque, simulation/PAPER/LIVE selon parcours et compte ; filtre GPT uniquement PAPER |
| CN_A | alpha_trade_cn / cn_primary | CNY, CN_A, Asia/Shanghai | Recherche, datasets, entraînement et replay ; pas d'exécution broker autorisée |
| FR_EQ | alpha_trade_fr / fr_primary | EUR, XPAR, Europe/Paris | Collectes/recherche/replay isolés, shadow local simulé ; pas de trading broker autonome autorisé |

Sources : `config/markets/market_us.yaml`, `market_cn.yaml`, `market_fr.yaml`,
`common/market_context.py`, `database/router.py`. CN_BJ a un contexte séparé ;
ce n'est pas une preuve de qualification de tout Pékin pour le trading.
Les contextes CN/FR ont `enabled: false`, `live_enabled: false` et
`short_execution_enabled: false` : leurs capacités de recherche déclarées ne
constituent pas une ouverture du serving ou des ordres.

`config/databases.yaml` allowliste les marchés par alias. CN/FR peuvent utiliser
les identifiants LOGIN_DB/PASSWORD_DB en fallback explicitement configuré,
**sans partager les données**. FR exige physiquement alpha_trade_fr ; ne pas
remplacer un chemin FR par une connexion US pour contourner un échec.
Le fallback sans `market_code` reste US legacy avec avertissement ; ce n'est pas
une détection automatique du marché à partir du ticker.

Configurations : `config.yaml` (US/paramètres communs), `config_cn.yaml`,
`config_fr.yaml`, `batch.yaml`, `batch_cn.yaml`, `batch_fr.yaml`, profils
`config/features*`, protocoles `config/research_cn` et `config/research_fr`.
Une option de ces fichiers n'agit que si le composant la lit effectivement.

## 2. Les parcours US doivent être distingués

### ML classique et cascade Oracle × ATR

Les prédictions ternaires, rankings et modèles Per-Symbol/Per-Sector existent
toujours. Un batch Oracle-only n'est pas un modèle directionnel :
`proba_extreme` mesure l'amplitude, pas le sens du futur rendement.
Les politiques Oracle tradable/cascade sont décrites dans
[le contrat TOP20](ml/oracle_tradable_top20_backtest_live.md) et
[le gate ATR](ml/oracle_atr_amplitude_gate.md).

Valeurs locales : `cascade.oracle_atr_enabled: true`, mais
`cascade.live_oracle_tradable_policy: off` et `extreme_gate.enabled: false`.
**Le booléen ATR ne suffit pas à activer une branche Oracle live**, et ne
modifie ni l'entraînement ni les scores stockés. Son effet dépend du parcours
de sélection effectivement utilisé.

### Oracle → GPT + recherche Web → risque → PAPER

Implémentation : `service/llm_directional/{config,runner,validation,pipeline,
risk_adapter,protections,repository}.py`, builders IHM et moteur d'exécution.
[Contrat détaillé](ml/oracle_llm_directional_filter.md).

| Paramètre | Configuration locale actuelle | Défaut du composant sans option YAML |
| --- | --- | --- |
| activation IHM | enabled=true | false |
| univers | universe-file:univers_filtred_tradable.txt | idem |
| batch Oracle | model-factory-20261003082853-e98332 | idem |
| nombre analysé / plafond retenu | 20 / 3 | 10 / 5 |
| SHORT autorisé | true | false |
| SL spécifique | 7 % | 7 % dans ProtectionProfile |
| sortie spécifique | ouverture séance 21, séance d'entrée = 1 | idem |
| trailing spécifique | 15 % | 20 % dans ProtectionProfile |

Le modèle demandé par la configuration est `gpt-6.1-sol`, clé via
`OPENAI_API_KEY`. Ce document décrit la requête du code ; il ne certifie pas
la disponibilité du modèle pour un compte API ni la gratuité de l'appel.

Les N premiers sont pris par **score Oracle décroissant**, départagés par
symbole. Ce sont des nombres de titres, pas des TOP N %. Pas d'intersection ATR
ajoutée implicitement dans ce filtre. GPT cherche des éléments documentés et
répond LONG, SHORT ou abstention ; sa confidence est **non calibrée**.
Sélection par confidence décroissante, puis rang Oracle, plafonnée à K au total.
Une seule réponse invalide fait échouer le run ; aucune sélection partielle
n'est transmise silencieusement au risque.

L'analyse est prospective : après clôture réelle de J et **avant l'ouverture
de la séance US suivante**, y compris le lendemain matin Paris. Pas de recherche
Web historique ni Oracle shadow. Le risque consomme le run exact de la même
date/du même compte, encore valide (24 h configurées) ; aucun fallback « latest ».
Une analyse expirée ou déjà consommée ne doit pas être recyclée pour de nouvelles entrées.

Archivage US : `llm_directional_runs`, `llm_directional_assessments`, puis
`llm_directional_evaluations` pour l'évaluation future. Requête, réponse brute,
empreintes, sources, décision, candidats retenus/non retenus et lien risque
sont conservés. Les dates de publication rapportées par GPT ne sont **pas
certifiées indépendamment** (`source_timestamps_verified=False`).

Compte `default` Alpaca PAPER seulement. SHORT : compte autorisé, actif
tradable/marginable/shortable/easy_to_borrow, quantités entières, contrôles
répétés avant risque et avant ordre. Pas de HTB/locate automatique ni retournement
implicite d'une position opposée. Les contraintes de régime, univers et capital
restent prioritaires. Kelly est interdit pour une note non calibrée.

Le profil de protection est figé dans config_json du run : une modification
YAML ultérieure ne change pas la protection d'un lot existant. SL depuis le
fill, pas le close du signal. Pas de TP de prix dans le profil ; sortie
temporelle séance 21. Transition vers trailing seulement sans desserrer le SL.
Pour SHORT, stop/trailing/sortie sont des rachats. Gaps et pannes peuvent
dépasser la perte théorique du stop. Watcher continu sain obligatoire pour ce
profil et dès que SHORT est autorisé, même sans profil spécifique.

## 3. Pipeline interactif et batch planifié ne sont pas identiques

La page Pipeline expose 1–14 et T1 hors quotidien. Voir
[les étapes](04_pipeline_quotidien.md). Le builder conserve les étapes
13/14 explicitement sélectionnées ; le workflow non personnalisé conserve
son cœur 1–12 et ses options séparées de corporate actions.

`us_pipeline` est le nom actuel, pas `us_pipeline_1_9`.
`config.yaml/us_pipeline.steps` règle lundi–jeudi ; `steps_friday` règle la
**séance US** du vendredi, même si le run continue après minuit Paris.
Valeurs actuelles : 1–7,9–14 en semaine ; 1–14 le vendredi. Mode paper,
compte default, horaire 22:45 Paris. LIVE interdit dans ce batch.
Une étape omise n'est pas injectée ; son prérequis doit déjà exister.

Les options fraîches du scheduler ne reprennent pas la session Streamlit :
**la case GPT cochée par défaut dans l'IHM n'active pas le filtre du batch**.
`pipeline_page_default_options()` part de `PipelineLaunchOptions`, dont
`llm_filter_enabled=False`. Sélectionner 10/11/12 ne suffit donc pas à y
injecter GPT. Les paramètres GPT ci-dessus concernent le parcours activé
explicitement dans l'IHM/CLI.

L'univers partagé du batch est `config/univers_batch/univers_filtred_tradable.txt`
pour les étapes acceptant cette option. La publication et le risque appliquent
ensuite leurs critères tradables ; ne pas confondre fichier de collecte et
liste finale autorisée à entrer.

La séance US est figée au départ : quotes J−7/J, earnings J−7/J+30 ; import
EODHD ciblant J, attente de publication et contrôle de couverture, sans succès
sur une ancienne date. Avant 12 PAPER, watcher existant sain réutilisé ou
service local démarré et vérifié. Le service reste vivant après le batch et
ne recharge pas automatiquement les modules modifiés.
13/14 exigent un compte paper **même en mode simulate**, car l'application
des corporate actions peut écrire le ledger ; ce n'est pas un dry-run global.
Voir [guide complet du batch](operations/us_pipeline.md).

## 4. Collectes : état configuré ≠ santé ≠ autorisation

[Catalogue courant](operations/catalogue_batchs_actuel.md) : US 25 entrées,
16 activées ; CN 10 entrées visibles, 3 activées ; FR 13 entrées, 9 activées.
Ces chiffres sont un cliché du YAML, **pas un nombre de runs réussis**.
Les horaires actifs sont hors absence 07:30–20:00 Paris, avec l'exception
`us_pipeline` dont l'horaire reste 22:45 ; détails et marges dans
[US](operations/forward_pit_batches.md) et [FR/CN](operations/horaires_fr_cn_presence_pc.md).

La page Batch sépare US/CN/FR. Installation globale : sections activées du
marché sélectionné, sans toucher les tâches en cours ; désinstallation globale :
tâches installées du marché sélectionné hors tâches en cours.
Les blocages droits/prudence restent noirs avec ⛔ ⚖️ ; un échec opérationnel
est rouge/gras. `enabled=true` seul ne lève pas un statut bloqué.

Les collectes récupèrent soit des fenêtres reconstructibles avec déduplication,
soit des snapshots prospectifs avec second passage conditionnel lorsqu'il existe.
Le gate US accepte un succès récent COMPLETED **ou COMPLETED_WITH_WARNINGS** ;
sinon rattrapage. Un second passage ne reconstitue pas un snapshot qui n'a jamais
été observé. Les notifications exposent demandés/reçus/persistés/échecs/alertes
et passage principal/secours ; les compteurs de pipeline comptent des étapes,
pas des titres.

Les statuts juridiques sont des décisions de prudence du projet, pas une
garantie d'autorisation pour tous les autres usages/endpoints. Le statut
ACTIVE_RESEARCH ne vaut ni licence de redistribution ni GO ML/LIVE.

## 5. Ce qui est réellement stocké par marché

- US : daily canoniques via l'import métier, versions prospectives Business
  Quant séparées, données SEC, snapshots borrow/options et fenêtres IEX.
  `daily_bars_sync` Business Quant n'est pas le remplaçant canonique de
  l'import EODHD du pipeline. `market_cap.policy=liquidity_only` : la collecte
  de capitalisation existe, mais le filtre de capitalisation n'est pas imposé
  actuellement à la publication de l'univers.
- CN : tables instruments/séances/barres/facteurs/limites et datasets historiques
  propres à alpha_trade_cn. D9 propriétaire canonique prévu, **actuellement
  bloqué BaoStock** ; D6 bloqué SSE/SZSE. D10 et 17-C peuvent être activés dans
  le catalogue tout en échouant faute de leurs dépendances. Pas de nouveau
  fournisseur lancé implicitement.
- FR : import quotidien EODHD publié dans `fr_ingestion_runs`, `fr_raw_payloads`,
  `fr_provider_bars_staging`, `fr_staging_progress` quand l'option est active.
  **Pas de promotion automatique vers stock_bars_daily**. ESMA, AMF, DILA,
  corporate actions et MiFIR gardent leurs fichiers versionnés/recherche ;
  tout n'est pas en SQL. Univers S6C 330 identités, dont 294 marquées actives,
  distinct du sous-ensemble XPAR 164 utilisé par la simulation shadow locale.

Trading212 FR : lectures DEMO EUR et bancs synthétiques livrés ; protections,
parité et données non libérées. Sprints 17/18 clôturés administrativement avec
réserves, **aucun canary broker autonome autorisé**. Voir [index FR](fr/README.md).

## 6. Étude Oracle × ATR : futurs réalisés, pas signal live

`service/market/oracle_atr_study.py` alimente par tranches la table US
`oracle_atr_market_regime_daily`. Rendements à horizon Oracle arrivé à maturité,
références macro/régime et distributions D1/D10 ; pas une table d'ordres.
Les cinq listes contiennent des pourcentages entiers signés **réalisés**.
`predicted_oracle_score_order_returns_pct` conserve l'ordre du score prédit ;
les autres listes de mouvements sont triées par amplitude réalisée.
Oracle ne prédit pas le signe de ces nombres.

`missing_returns_policy=partial` est la règle configurée, pas un constat : une
ligne peut être COMPLETE avec cette politique, zéro manquant et couverture 100 %.
Lire les compteurs/statuts de `movement_quality` et la couverture de référence.
Pas de remplacement d'un candidat dont le futur manque par le suivant connu.
Un H20 immature reste inconnu, pas zéro. Les règles du contrôle live des nouvelles
entrées sont séparées : 61 séances qualifiées et délai de publication 15 minutes
configurés, barres réelles OHLCV positives, source/ajustement/timestamps vérifiés.
Un titre refusé ne condamne pas les titres valides ; une panne globale du contrôle
peut bloquer toutes les nouvelles entrées. Les positions détenues ne sont pas
vendues par ce seul contrôle. [Étude](ml/oracle_atr_market_regime_daily.md).

## 7. Périmètre et entretien de cette mise à jour

660 Markdown sont présents sous doc au début de l'audit. Les pages d'entrée,
guides opérateur et contrats transverses cités ici ont été rapprochés des
sources ciblées ; **pas une revue ligne par ligne de ces 660 documents ni de
tous les modules**. Les inventaires API anciens et résultats historiques ne
sont pas présentés comme régénérés/validés dans leur totalité.

À chaque évolution : lire le consommateur de configuration, le builder de
commande, le service métier et ses tests ; corriger le guide correspondant,
mettre à jour cet état daté et conserver la preuve historique distincte.
Ne pas copier les valeurs locales dans des defaults supposés universels.
