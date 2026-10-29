# Consensus EODHD — collecte prospective US

Livré le 11 octobre 2026. Nouveau batch `eodhd_consensus_snapshot`, indépendant
de Yahoo. Les tables et le launcher Yahoo ne sont ni lus ni alimentés.
Configuration exclusivement dans `batch.yaml` ; page **Workflow & Orchestration → Batch → US**.

## Accès vérifié, pas historique PIT reconstruit

Le compte et `/calendar/trends` répondent HTTP 200 après souscription Calendar
& News. AAPL retourne 96 lignes et MSFT 98. Le smoke du collecteur sur les deux
premiers titres du fichier tradable reçoit 194 lignes en un appel, sans SQL écrit.
Preuves : `artifacts/research/eodhd_consensus/qualification-20261011-new-plan-v1/report.json`
et `artifacts/research/eodhd_consensus/collector-smoke-20261011-v1/report.json`.

Les dates fiscales présentes depuis des années ne prouvent PAS les états du
consensus connus à ces dates. `snapshot_date` est la date réelle de collecte
New York ; `observed_at` et `available_at` sont la réception UTC réelle.
Ne pas transformer J−7/30/60/90 en snapshots artificiels datés dans le passé.
La disponibilité fournisseur antérieure à notre réception n'est pas certifiée.

## Pourquoi ne pas réutiliser les tables Yahoo ?

Les clés uniques Yahoo EPS/trend/revision sont `provider,symbol,snapshot_date,
horizon_normalized` (avec `estimate_type` pour les estimations). EODHD retourne
plusieurs dates fiscales pour un même `0q/+1q/0y/+1y` dans la même réponse :
réutiliser ces tables ferait perdre des périodes ou imposerait de changer leurs
contrats et consommateurs. Les références de période et unités restent à qualifier.

Nouvelle table **`alpha_trade.stock_analyst_consensus_eodhd_history`**.
Clé unique : fournisseur, symbole, date de collecte, date fiscale, horizon brut.
Une seule première observation par clé/jour, jamais de mise à jour des valeurs
anciennes. Toute autre période est conservée. Les valeurs fiscales anciennes
restent observées aujourd'hui, pas rétroactivement disponibles.

## Champs collectés

| Famille | Champs typés | Limites |
|---|---|---|
| Consensus EPS | moyenne, bas, haut, analyst_count, croissance, EPS année précédente | Unité/normalisation à qualifier |
| Consensus revenus | moyenne, bas, haut, analyst_count, croissance | Devise et échelle non déclarées dans le smoke |
| Tendances EPS | courant, références 7/30/60/90 jours | Pas historique PIT complet |
| Révisions EPS | hausse 7/30 jours, baisse 7/30 jours si présentes | Baisse 7 jours absente sur les 194 lignes ; baisse 30 jours NULL sur 90 |
| Identité | code fournisseur, date fiscale, horizon brut | `fiscal_identity_qualified=false` |
| Traçabilité | réception UTC, run_id, hash, ligne JSON complète, version parseur | Réponse entière également conservée dans `pit_raw_payloads` |

Le champ fournisseur `revenueEstimateYearAgoEps` est conservé sous
`revenue_year_ago` avec sémantique non qualifiée ; absent sur tout le smoke.
Ne pas l'utiliser comme revenu réalisé vérifié. `growth` est stocké séparément
des croissances EPS/revenue. Les champs inconnus futurs restent dans le JSON.
Valeur absente = NULL, jamais zéro inventé. Nombres non finis, compteurs négatifs
ou fractionnaires, symboles étrangers et doublons contradictoires sont refusés.

**Non collectés ici** : objectifs de cours, recommandations buy/hold/sell,
observations individuelles de chaque analyste, révisions revenue détaillées non
exposées, prix historiques et nouvelles news. Les autres batchs restent inchangés.

## Mise en service

Le batch est **activé dans la configuration** depuis le 11 octobre 2026
(`enabled: true`, `RESEARCH_ONLY`), à la demande utilisateur.
Cette activation ne prouve pas l'installation de la tâche Windows.
La table dédiée a été créée et vérifiée dans `alpha_trade` le 11 octobre 2026 ;
elle contient zéro ligne, car aucun run de collecte avec insertion n'a été lancé.
Aucune table Yahoo n'a été modifiée. La révision Alembic n'a pas été estampillée.
Pour une autre installation, créer la table via Alembic 0099 ou exécuter :
`database/sql/forward_pit/stock_analyst_consensus_eodhd_history.sql`.
Le CREATE est idempotent ; il ne modifie aucune table Yahoo. Ne pas lancer une
migration globale sans vérifier le schéma US et la version déjà appliquée.

Utiliser **Installer/réinstaller** sur sa carte IHM pour planifier les passages.
Commande équivalente depuis la racine du projet :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install_forward_pit_task.ps1 -BatchName eodhd_consensus_snapshot
```

Exécution immédiate avec les notifications habituelles :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/forward_pit_launcher.ps1 -BatchName eodhd_consensus_snapshot -Force
```

Horaires Paris : **22 h 15**, secours **4 h 15**, hors absence 7 h 30–20 h.
Tous les jours : une réponse courante ne se reconstruit pas fidèlement en J−7/J.
Le secours consulte `pit_collection_runs` : succès dans les dix dernières heures
→ SKIP. Les lancements manuels restent autorisés si le batch est activé.
Les snapshots déjà présents à la date New York sont ignorés ; un symbole est
commité entièrement, puis la reprise passe au suivant. Aucun tableau incomplet
n'est déclaré complet via un simple checkpoint fichier.

**Univers courant depuis le 18 octobre 2026 :**
`config/univers_batch/stock_bars_daily.txt`, export fixe de **13 105 symboles**
au changement. Configuration : `symbol_source: universe-file`, `symbols_file`
vers cet export. Le fichier est relu au lancement, mais n'est pas régénéré depuis
SQL automatiquement. Aucun filtre actif/tradable, TOP20 ou TOP10 n'est appliqué.
`us_pipeline` reste sur son fichier tradable de 1 790 titres.

L'univers large de 13 105 symboles de `stock_bars_daily`, utilisé auparavant,
reste un mode pris en charge explicitement, mais n'est plus celui configuré.
Ses anciennes observations SQL et archives restent conservées sans modification.
Le mode courant utilise ce fichier exporté, pas une requête SQL d'univers.
Les anciennes preuves et métriques gardent leur périmètre daté.

Le seuil de couverture de 95 % reste limité à
`config/univers_batch/univers_filtred_tradable.txt` (`coverage_symbols_file`),
pas à l'ensemble des ETF/radiés de l'export. Absence de consensus et erreur
technique restent distinguées. Lots de 20 titres, pause 1,1 seconde : environ
656 appels pour 13 105 titres, hors retries/subdivision et titres déjà collectés.
Quota et retries du client EODHD
existant ; HTTPS vérifié. 401/403/quota/circuit arrêtent la collecte, sans repli Yahoo.
Une couverture inférieure à 95 % du fichier tradable ou une erreur technique
fait échouer le run. Les réponses vides sont distinctes des échecs techniques :
`no_consensus_symbols` / `no_consensus_count`. Les identifiants 404, ou 422
explicitement liés aux symboles, sont isolés par subdivision puis consignés dans
`invalid_symbols` / `invalid_symbol_count` ; ils comptent en vide, pas en panne
technique. Une erreur technique locale est enregistrée sans abandon des
sous-lots frères ; auth/quota/circuit interrompent le run avec compteurs détaillés.
Les symboles sans consensus ou invalides dans le fichier tradable réduisent sa
couverture ; les absences hors de cette référence n'affectent que la couverture
globale descriptive. Les titres sont demandés selon le fichier étendu.
Le changement prend
effet au prochain lancement, sans nouveau téléchargement ni écriture SQL lors
de cette modification de configuration. Horaires, secours et notifications
restent inchangés ; pas de nouvelle installation Windows nécessaire pour le
seul changement d'univers, le launcher relisant `batch.yaml` à chaque lancement.

Le 11 octobre, les types partagés `Outcome` et `BatchRunError` ont été déplacés
dans `service/forward_pit/outcomes.py` pour préserver les compteurs lorsque le
runner est lancé en `python -m` et également importé par un collecteur. Les anciens
résumés d'échec tronqués ne sont pas réécrits ; le correctif vaut pour les prochains
runs, SQL, résumé launcher et notifications. Les données métier restent conservées.

Demandés/reçus/vides/échecs comptent des **symboles**, persistés des **lignes**.
`details_json` conserve reçus-lignes, champs manquants, appels, couverture et
erreurs. Le launcher envoie mail et Telegram selon les canaux configurés, avec
statut, compteurs, message d'erreur et passage principal/secours/manuel.
Un lancement CLI direct du runner ne remplace pas le launcher de notification.

## Qualification ultérieure

### Couverture mesurée le 29 octobre 2026

Audit SQL en lecture seule des sept dernières dates terminées sur le fichier
courant, **22–28 octobre inclus** (jours calendaires, week-end compris). Le run
du 29 octobre est encore RUNNING au cutoff et n'entre pas dans la moyenne.

| Périmètre | Titres avec au moins un consensus | Couverture moyenne |
| --- | ---: | ---: |
| `stock_bars_daily.txt` | 5 745 / 13 105 | **43,84 %** |
| Sous-ensemble `univers_filtred_tradable.txt` | 1 778 / 1 790 | **99,33 %** |

Ces valeurs sont identiques sur les sept dates. Dernier run terminé :
`eodhd_consensus_snapshot-20261028211502-53a38d25`. Sur le grand univers :
7 326 absences de consensus, 34 symboles invalides, zéro échec technique ;
la couverture globale ne doit pas être interprétée comme un taux de panne.
La moyenne est de **956 requêtes HTTP** par passage, regroupement par 20 et
isolation récursive des symboles invalides inclus. Ce sont des requêtes
logiques du collecteur, pas un nombre garanti d'échanges réseau après retries
ni un calcul de points de facturation du fournisseur.

La couverture signifie au moins une ligne de période/horizon pour le titre,
pas l'absence de NULL dans tous les champs, une période fiscale qualifiée ou
une efficacité directionnelle. Le seuil de 95 % porte toujours sur les tradables.

Comparaison hypothétique avec le collecteur Yahoo installé (`yfinance` 1.4.1) :
EPS, revenus, tendances et révisions partagent le module `earningsTrend`, soit
environ une requête de données par titre. L'ancien collecteur ajoute
`financialData` pour les objectifs et `recommendationTrend` pour les recommandations,
soit environ trois requêtes par titre. Pour 13 105 titres : environ
13 105 requêtes pour le seul équivalent consensus, ou 39 315 avec les deux
familles supplémentaires ; pour 1 790 titres : 1 790 ou 5 370.
Ces ordres de grandeur excluent cookies/crumb, authentification, reprises et
erreurs ; ils ne promettent ni l'accès ni la même couverture Yahoo. Aucune
collecte consensus Yahoo ou modification de batch déclenchée par cet audit.

Preuve : `artifacts/operations/consensus_coverage_audit/20261029T211901Z/report.json`.
Script : `scripts/operations/audit_consensus_run_coverage_20261029.py`.

État constaté en lecture seule le **14 octobre 2026** : 959 094 lignes,
5 742 symboles, **trois dates** de snapshot (11–13 octobre). Aucun des marqueurs
d'identité fiscale, d'unités ou de PIT historique n'est encore qualifié.
Ces comptes n'attestent ni une couverture exhaustive, ni un historique
directionnel H20 mature, ni une réussite de tous les runs. Les anciennes preuves
de smoke restent des constats datés, pas l'état actuel en base.

`RESEARCH_ONLY`, `units_qualified=false`, `fiscal_identity_qualified=false`,
`historical_pit_qualified=false`. La réception prospective est tracée mais la
date fiscale, devise, échelle, corrections et disponibilité avant décision
doivent être qualifiées avant ML/backtest. Aucun entraînement ou filtre LIVE
n’est déclenché par ce collecteur.

Depuis le **19 octobre 2026**, les nouvelles analyses LLM PAPER de l’étape 10
lisent un contexte borné de cette table et l’envoient au fournisseur LLM choisi,
dans les modes `web_search` et `local_data_only`. Le collecteur ne lance toujours
aucun LLM. Les réserves d’unités/périodes et RESEARCH_ONLY sont conservées ;
ces valeurs non qualifiées ne peuvent pas autoriser seules une sélection locale.
Le paquet reçu avant le cutoff est archivé, sans transformer les références
J−7/30/60/90 en collectes historiques. [Contrat et configuration](../ml/llm_modes_consensus.md).
L'abonnement donne l'accès technique, pas une autorisation universelle de
redistribution : usages privés/licence et conservation doivent rester conformes.

Smoke sans SQL (deux titres par défaut) :

```powershell
python -u -m service.eodhd.consensus_snapshot --dry-run --max-symbols 2 --output-dir artifacts/research/eodhd_consensus/smoke-NOUVELLE-DATE
```

Le rapport ne contient ni token ni données personnelles du compte. Pas de
preuve d'amélioration D1/D10 ou Oracle : on construit les données à tester.
