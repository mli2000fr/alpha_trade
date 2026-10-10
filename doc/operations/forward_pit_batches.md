# Batchs de collecte Forward PIT

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Repère actuel et périmètre historique

Rapprochement du 10/10/2026 : le
[catalogue courant US/CN/FR](catalogue_batchs_actuel.md) fait référence pour
les familles actives, retirées et bloquées. Les descriptions/itérations plus
anciennes ci-dessous n'annulent pas les statuts droits/prudence actuels ni
les frontières fichiers/staging/canonique. Cette page décrit surtout le
contrat de collecte US ; FR/CN ont leurs runners et historiques séparés.

## Pilotage depuis l'IHM

La page **Workflow & Orchestration → Batch** constitue le catalogue opérationnel
du marché sélectionné. Elle affiche finalité, priorité P0 à P4,
les tables alimentées, le calendrier configuré et l'état réel de la tâche Windows.
Elle rapproche également la dernière exécution du Planificateur avec le dernier run
présent dans pit_collection_runs (volumes demandés, reçus, persistés, alertes et
échecs). Les trois traitements historiques qui ne renseignent pas encore cette table
restent observables via leur tâche Windows et leur journal dédié.

Les compteurs distinguent configuré, exécutable, installé et exécutable,
et installé mais dormant. Une tâche installée mais associée à enabled=false
reste présente dans Windows, mais son launcher s'arrête avant tout appel fournisseur
et n'écrit aucune donnée métier.
Chaque batch dormant affiche une explication issue de son champ
activation_requirement dans batch.yaml. Elle décrit le fournisseur, le quota, le
flux amont ou la décision de recherche nécessaire avant de passer enabled à true.
Les blocages droits/prudence sont noirs avec ⛔ ⚖️, pas rouges comme un échec
opérationnel. enabled=true seul ne lève jamais leur verrou.
Elle est suivie d'une section **Comment le débloquer**, alimentée par `unlock_steps`,
qui détaille les contrôles, développements et validations à réaliser dans l'ordre.

Les boutons **Installer / réinstaller**, **Lancer maintenant** et **Désinstaller**
exécutent les mêmes
scripts PowerShell que l'exploitation manuelle. Un lancement depuis l'IHM est
asynchrone : quitter la page ne coupe pas le traitement. Les batchs désactivés ou en
attente de fournisseur/quota restent documentés mais leur bouton de lancement est
bloqué. Les notifications email et Telegram sont envoyées par le launcher du batch ;
la notification générique de l'IHM est neutralisée afin d'éviter un doublon.
La désinstallation supprime uniquement la tâche du Planificateur Windows : elle ne
supprime ni batch.yaml, ni les journaux, ni les données collectées. Le bouton est
désactivé quand la tâche est absente ou en cours, et le script refuse également une
désinstallation tant que la tâche s'exécute.

Deux actions globales permettent d'installer ou réinstaller les tâches actives configurées,
et de désinstaller les tâches Batch installées du marché sélectionné. Une opération
globale continue après un échec isolé et affiche le résultat par batch. Les tâches en
cours sont toujours ignorées. Installer une configuration dormante ne l'active pas :
enabled=false demeure le verrou fonctionnel.

## Objectif et contrat

Ce dispositif construit, à partir de maintenant, l’historique réellement observable par Alpha‑Trade. Il ne reconstitue pas artificiellement le passé : chaque payload reçu porte un `observed_at`, un `available_at`, un hash de contenu, un hash de schéma et l’identifiant du run. Les données normalisées conservent ce lignage.

Le code métier US est dans `service/forward_pit/batch.py`.
`scripts/windows/forward_pit_launcher.ps1` adapte lecture du catalogue,
heure/jour/fuseau, mutex, journal et notifications. Le planning de collecte est
dans batch.yaml ; exception : les listes d'étapes/mode/compte de us_pipeline
sont dans config.yaml. Les profils FR/CN sont séparés.

Principes invariants :

- RAW append-only avant normalisation ;
- idempotence par clés naturelles et hash ;
- corrections conservées au lieu d’écraser l’historique source ;
- `available_at` utilisé pour les futurs joins PIT ;
- réponse globalement vide considérée comme erreur, sauf absence légitime de nouveaux filings SEC, signalée comme avertissement ;
- aucune disparition du security master ne devient automatiquement un delisting ;
- aucune source expérimentale n’est activée sans fournisseur et quota validés.
- timestamps persistés en UTC ; la date de séance reste calculée en heure New York.
- tout batch par symbole utilise `config/univers_batch/univers_filtred_tradable.txt` ; l'absence du fichier est bloquante et ne déclenche aucun repli vers un univers dynamique ;
- seuls les flux de découverte ou intrinsèquement globaux restent market-wide : security master, corporate actions, dépôts SEC et séries macro.

### Contrat d'univers des batchs

| Périmètre | Batchs | Contrat |
|---|---|---|
| Univers tradable stable | `market_cap_sync`, `earnings_calendar_sync`, `analyst_snapshot_collection`, `latest_quotes_sync`, `daily_bars_sync`, `borrow_status_snapshot`, `business_quant_analyst_snapshot`, `oracle_options_indicative_snapshot`, `options_delayed_bars_sync`, `oracle_opening_window_sync` | fichier `config/univers_batch/univers_filtred_tradable.txt`, complet, sans TOP20 ni limite implicite ; population, pas autorisation des familles désactivées |
| Futurs collecteurs par symbole | `auction_imbalance_sync`, `securities_lending_sync`, `official_options_nbbo_sync` | le même fichier est déjà déclaré ; les collecteurs restent désactivés tant que source, stockage et qualité ne sont pas validés |
| Découverte market-wide | `security_master_snapshot` | toutes les cotations disponibles afin de détecter nouveaux titres, changements et disparitions |
| Événements market-wide | `corporate_actions_sync` | flux global afin de ne pas manquer une action affectant un titre entrant, sortant ou détenu |
| Dépôts SEC globaux | `sec_edgar_incremental`, `sec_corporate_events_normalize`, `sec_institutional_ownership_normalize` | collecte RAW puis normalisation des formulaires configurés ; pas de présélection Oracle |
| Macro | `fred_alfred_vintage_sync` | séries économiques, notion de symbole non applicable |
| Sauvegarde ML | `ml_artifacts_backup` | snapshot hebdomadaire du répertoire runtime `artifacts/models`, sans univers de symboles |
| Sauvegardes DB | `db_core_backup`, `db_news_raw_backup` | dumps locaux sans univers de symboles ; périmètres complémentaires et rotations indépendantes |

Le TOP20 est une **sortie de modèle**, recalculée après entraînement ou à chaque date de backtest. Il n'est jamais une source de collecte. Ainsi, un nouvel Oracle, un nouvel horizon ou une nouvelle politique de ranking peut reconstruire son propre TOP20 à partir du même historique large.

## Inventaire opérationnel

| Priorité | Batch | Source | Table(s) normalisée(s) | État au 10/10/2026 |
|---|---|---|---|---|
| P0 | `daily_bars_sync` | Business Quant `/quotes`, mode `eod` | `stock_bars_daily_versions` RAW | actif |
| P0 | `latest_quotes_sync` | Alpaca historique IEX | `stock_quote_snapshots` | autonome désactivé ; intégré à l'étape 4 de us_pipeline, J−7/J |
| P0 | `security_master_snapshot` | Nasdaq Symbol Directory quotidien, Business Quant Universe hebdomadaire | `security_master_snapshots`, `security_master_changes` | actif |
| P0 | `corporate_actions_sync` | Business Quant market-wide + Alpaca | `corporate_action_source_events` | actif |
| P0 | `sec_edgar_incremental` | SEC daily master index + submissions | `sec_filing_raw` | actif |
| historique | `pit_data_quality_daily` | anciens contrôles locaux | `pit_data_quality_metrics`, `pit_data_quality_issues` | retiré du catalogue ; aucune réactivation planifiée |
| P0 | `ml_artifacts_backup` | système de fichiers local | `backups/ml/ml_artifacts_*.tar.gz` | actif ; samedi 01:00 Paris ; rétention configurable (`keep`) |
| P0 | `db_core_backup` | MySQL local / `mysqldump` | `backups/db/alpha_trade_without_news_*.sql.gz` | actif ; dimanche 01:00 Paris ; toute la base sauf `news_raw` ; 5 archives |
| P0 | `db_news_raw_backup` | MySQL local / `mysqldump` | `backups/db/alpha_trade_news_raw_*.sql.gz` | actif ; chaque dimanche, heure de Paris configurée dans `batch.yaml` ; `news_raw` seule ; 3 archives |
| P1 | `borrow_status_snapshot` | Alpaca Assets | `stock_borrow_status_snapshots` | actif |
| P1 | `analyst_snapshot_collection` | Yahoo Finance/yfinance | consensus, tendances/révisions EPS, targets et recommandations | désactivé : `BLOCKED_YAHOO_AUTOMATED_ACCESS` |
| P1 | `business_quant_analyst_snapshot` | Business Quant `/estimates` | `stock_analyst_consensus_snapshots` | remplacé par Yahoo, désactivé |
| P1 | `finra_short_volume_sync` | FINRA Consolidated NMS public | `stock_short_volume_daily` | désactivé : `BLOCKED_FINRA_PREDICTIVE_USE` |
| P2 | `oracle_options_indicative_snapshot` | Alpaca Basic indicative | `stock_option_snapshots` | actif, recherche uniquement |
| P2 | `options_delayed_bars_sync` | Alpaca historique retardé, provenance non attestée | `stock_option_contract_versions`, `stock_option_bars_delayed` | actif, recherche uniquement |
| P2 | `option_contract_adjustment_sync` | RSS officiel OCC | `option_contract_adjustments` | actif, métadonnées prospectives |
| P2 | `official_options_nbbo_sync` | fournisseur requis | — | bloqué : aucune source NBBO gratuite |
| P3 | `oracle_opening_window_sync` | Alpaca IEX historique 1 minute | `stock_opening_window_bars`, `stock_opening_window_bar_versions` | recherche active ; volume non consolidé, pas prix d'exécution officiel qualifié |
| P3 | `sec_corporate_events_normalize` | RAW SEC 8‑K/6‑K | `sec_corporate_events` | actif |
| P4 | `sec_institutional_ownership_normalize` | RAW SEC 13F/13D/13G | `sec_ownership_snapshots` | actif |
| P4 | `fred_alfred_vintage_sync` | FRED/ALFRED | `macro_vintage_observations` | désactivé : `BLOCKED_FRED_ARCHIVE_ML_RIGHTS` |
| attente | `auction_imbalance_sync` | Nasdaq NOII/NYSE live payants ; Web NYSE post-auction limité | — | `BLOCKED_NO_FREE_OFFICIAL_FEED` ; [POC séparé](../ml/nyse_auction_history_poc.md) |
| attente | `securities_lending_sync` | fournisseur requis | — | désactivé |

Les batchs `earnings_calendar_sync` et `market_cap_sync` ne font pas doublon. Le premier stocke calendrier/estimates/actuals d’earnings. Le second rafraîchit les faits SEC nécessaires à la capitalisation PIT, puis interroge Yahoo uniquement pour les symboles sans couverture SEC fraîche et Finnhub uniquement pour les trous restants. `market_cap_sync` passe par le handler et le lanceur Forward PIT commun : son état et ses compteurs survivent donc à un redémarrage de l’IHM dans `pit_collection_runs`.

### Politique de rattrapage J−7/J

Les collecteurs historiques rejouent une fenêtre glissante et s'appuient sur
les clés métier des tables : une observation identique est ignorée ou mise à
jour, tandis qu'une correction de fournisseur conserve une version distincte.

| Batch | Fenêtre effective | Reprise |
|---|---:|---|
| `earnings_calendar_sync` | J−7 à J+30 | reprise par symbole et upsert `(symbol, earnings_date)` |
| `latest_quotes_sync` | J−7 à J | uniquement les séances quotes manquantes |
| `daily_bars_sync` | J−10 à J | même payload ignoré, correction conservée par hash |
| `corporate_actions_sync` | J−7 à J+30 | événements dédupliqués par identité et hash |
| `sec_edgar_incremental` | 7 jours ouvrés précédents | accession SEC unique |
| `oracle_opening_window_sync` | J−7 à J | séance ignorée dès que son gate de couverture OPEN est atteint |
| `finra_short_volume_sync` | 7 jours ouvrés précédents | fichier/date/symbole/hash idempotents |
| `fred_alfred_vintage_sync` | J−730 à J | unicité série/observation/vintage |

Les normalisations `sec_corporate_events_normalize` et
`sec_institutional_ownership_normalize` ne dépendent pas d'une fenêtre : elles
reprennent tout dépôt RAW encore absent de leur table cible.

Les snapshots `security_master_snapshot`, `market_cap_sync` (fallbacks
Yahoo/Finnhub), `analyst_snapshot_collection`, `borrow_status_snapshot` et
`oracle_options_indicative_snapshot` ne peuvent pas recréer fidèlement un état
historique manqué. Le RSS de `option_contract_adjustment_sync` n'offre pas non
plus de paramètre J−7/J garanti. Enfin, `options_delayed_bars_sync` expose des
barres historiques, mais une séance manquée ne peut être reconstruite sans le
catalogue des contrats alors actifs ; utiliser la chaîne courante introduirait
un biais de sélection. Ces sept batchs utilisent donc un passage de secours
conditionnel, pas un faux backfill : avant tout appel fournisseur, le launcher
cherche un succès récent en base. Un succès produit `SKIP`; une absence ou un
échec du passage principal déclenche le rattrapage. Si le contrôle SQL est lui-même
indisponible, le rattrapage est exécuté afin de privilégier la continuité de la
collecte. Les lancements manuels avec `-Force` ignorent toujours ce gate.

| Batch snapshot | Passage principal | Secours conditionnel | Écart |
|---|---:|---:|---:|
| `security_master_snapshot` | 01:00 Paris | 06:00 Paris | 5 h |
| `market_cap_sync` | 20:00 Paris | 23:00 Paris | 3 h |
| `analyst_snapshot_collection` (désactivé / droits) | 22:00 Paris | 04:00 Paris le lendemain | 6 h |
| `borrow_status_snapshot` | 15:45 New York | 22:25 New York | 6 h 40 |
| `oracle_options_indicative_snapshot` | 16:20 New York | 22:20 New York | 6 h |
| `options_delayed_bars_sync` | 17:00 New York | 23:00 New York | 6 h |
| `option_contract_adjustment_sync` | 01:15 Paris | 06:15 Paris | 5 h |

Depuis le 10 octobre 2026, `borrow_status_snapshot` observe la disponibilité
SHORT en soirée Paris, et non avant l'ouverture US. Le secours mesure aussi
l'état courant à son heure réelle : il ne remplace pas fidèlement un snapshot
pré-marché. La disponibilité doit être revérifiée avant un nouvel ordre SHORT.

### Disponibilité du PC US : 20:00–07:30 Paris

Les passages principaux **et** de secours des batchs US actifs sont placés hors
de l'absence 07:30–20:00 Paris. `us_pipeline` conserve **22:45 Paris**, sa liste
d'étapes et son calendrier. Ni FR/CN ni les sources désactivées n'ont été modifiés.
Les horaires de New York sont conservés pour les collecteurs liés à la séance ;
leurs secours restent le même jour **US**, donc fonctionnent aussi samedi matin
Paris après le passage principal du vendredi. Aucune modification du calendrier
ou du launcher n'est nécessaire.

| Batch actif | Principal Paris | Secours Paris | Durée maximale réussie observée sur 30 jours |
|---|---|---|---:|
| `market_cap_sync` | 20:00, lundi/jeudi | 23:00 | 1 h 19 |
| `sec_edgar_incremental` | 20:00, lundi–samedi | — | 28 min |
| `db_news_raw_backup` | 20:00, dimanche | — | 17 min |
| `borrow_status_snapshot` | 21:45 / 20:45* | 04:25 / 03:25* le lendemain | 7 min |
| `oracle_opening_window_sync` | 21:50 / 20:50* | — (J−7/J) | 2 min |
| `oracle_options_indicative_snapshot` | 22:20 / 21:20* | 04:20 / 03:20* le lendemain | 29 min |
| `us_pipeline` | **22:45, inchangé** | — | run non clos au moment de l'audit ; durée non déduite |
| `sec_corporate_events_normalize` | 23:00, lundi–samedi | — (backlog RAW) | 4 min |
| `sec_institutional_ownership_normalize` | 23:00, mardi/jeudi/samedi | — (backlog RAW) | moins de 1 min |
| `options_delayed_bars_sync` | 23:00 / 22:00* | 05:00 / 04:00* le lendemain | 16 min |
| `corporate_actions_sync` | 00:00, lundi–vendredi | — (J−7/J+30) | 3 min |
| `security_master_snapshot` | 01:00, lundi–vendredi | 06:00 | moins de 1 min |
| `option_contract_adjustment_sync` | 01:15, lundi–samedi | 06:15 | moins de 1 min |
| `daily_bars_sync` | 03:00, lundi–vendredi | — (J−10/J) | moins de 1 min |
| `ml_artifacts_backup` | 01:00, samedi | — | 5 min |
| `db_core_backup` | 01:00, dimanche | — | 19 min |

\* Premier horaire : décalage habituel de six heures. Second : décalage de cinq
heures entre les changements d'heure US et France, au printemps et en automne.
Les jours sont ceux du fuseau configuré dans `batch.yaml` (NY pour les quatre
collecteurs indiqués avec deux horaires ; Paris pour les autres).

**Contrôle de durée du 10/10/2026** : lecture seule de `alpha_trade.pit_collection_runs`,
30 derniers jours, uniquement runs terminés `COMPLETED` ou
`COMPLETED_WITH_WARNINGS` (4 à 25 runs par batch). Les durées ci-dessus sont
arrondies à la minute supérieure. Les échecs rapides et runs non clos ne sont
pas des estimations de durée normale. Les tests réservent une enveloppe prudente
(au moins 45 minutes, davantage pour capitalisation, options, SEC et backups)
et une marge de 30 minutes avant 07:30. Ils couvrent 2025–2027, changements
d'heure inclus. Aucun traitement de deux heures n'est placé à 07:00.

Ces enveloppes servent à **valider le planning**, pas à interrompre les processus :
un fournisseur lent, un gros rattrapage ou le pipeline peut dépasser la durée
observée. En particulier, `us_pipeline` n'est pas déplacé ni artificiellement
déclaré terminé avant le départ. Si un batch est encore en cours à 07:30, une
extinction du PC peut interrompre sa collecte ; la reprise suit son contrat propre.

La fenêtre historique de l'ouverture reste **04:00–10:30 New York** : seule
l'heure de téléchargement est déplacée, sans disponibilité PIT rétrodatée.
Les snapshots ne reconstruisent pas les états intermédiaires manqués. Les
normalisations de 23:00 traitent le RAW alors disponible ; un collecteur SEC
encore actif ne garantit pas que tout son nouveau RAW soit traité le même soir.

Les tâches Windows installées utilisent des déclencheurs **horaires**, aux
minutes utiles, puis relisent `batch.yaml`. Ces minutes n'ont pas changé
(notamment 25/45 pour borrow et 15 pour OCC). Les nouveaux horaires sont donc
appliqués au prochain passage **sans réinstallation** des tâches Forward PIT
existantes. Aucun run n'a été lancé ou interrompu et aucune écriture SQL métier
n'a été effectuée pour ce changement. L'IHM et les notifications continuent
d'afficher le principal ou le secours conditionnel.

Validation ciblée des horaires : **176 tests réussis** (marge de durée, DST,
rattrapages, catalogue IHM et séparation des marchés). La réserve alors isolée
sur les étapes 13/14 a ensuite été corrigée avec un GO distinct : le batch
accepte 1–14, le moteur conserve les sélections explicites, sans doublon, et
exige un compte PAPER pour les opérations sur titres. Les listes configurées
et l'horaire du pipeline restent inchangés. Voir [le guide](us_pipeline.md).

La page **Workflow & Orchestration → Batch** affiche, pour chaque entrée, soit
la fenêtre de reprise (`J−N à J`, éventuellement prolongée à `J+N`), soit la
présence et l'heure du second passage conditionnel. Les normalisations locales
affichent leur reprise de backlog RAW et les batchs désactivés indiquent qu'aucune
collecte n'est planifiée.

En cas d'échec, les notifications email et Telegram portent également le rôle
du déclenchement : `premier passage (principal)`, `second passage (secours
conditionnel)` ou `lancement manuel`. Un secours annulé parce que le principal
a réussi écrit seulement un `SKIP recovery-already-completed` dans le journal ;
il n'émet pas une fausse notification de succès ou d'échec.

## Tables et flux

```text
Fournisseur
   │
   ├── payload brut ──> pit_raw_payloads
   │                         │ hash + schema_hash + available_at
   │                         ▼
   └── normaliseur ──> tables PIT thématiques
                              │
                              ├── contrôle couverture/fraîcheur
                              ▼
                    pit_data_quality_metrics/issues

Chaque exécution ──> pit_collection_runs ──> statut + compteurs + erreur
```

La provenance peut contenir plusieurs fournisseurs (par exemple
`nasdaq_symbol_directory,business_quant`). Toutes les colonnes `provider` du
socle Forward PIT acceptent donc 255 caractères. Les migrations `0080` et
`0081` uniformisent respectivement le registre des runs puis toutes les tables
thématiques ; cette provenance ne remplace pas le détail conservé dans les
payloads bruts.


La migration `0075_forward_pit_collection` crée les 16 tables du socle. Le DDL de référence indépendant est `database/sql/forward_pit/forward_pit_tables.sql`.

## Détails par famille

### Barres journalières

Business Quant est interrogé par lots de 100 symboles sur une fenêtre glissante de dix jours afin de récupérer les séances tardives et corrections. Une version différente pour un même `(provider, symbol, trade_date)` est conservée et marquée `is_correction=1`. Ces prix sont enregistrés avec `adjustment_mode=raw`. Le service refuse explicitement `canonical_upsert: true` : `stock_bars_daily` exige actuellement des prix ajustés des splits. Un canonicaliseur fondé sur les corporate actions devra être validé avant de lever ce garde-fou ; étiqueter directement ces prix `split` créerait une série incohérente. L’univers courant d’environ 2 300 titres représente environ 23 appels par passage.

### Security master

Nasdaq apporte le répertoire de cotation officiel ; Business Quant complète hebdomadairement CIK, type, classe d’actif, secteur et industrie. Le service compare le snapshot courant au snapshot précédent du même fournisseur. `NEW_SYMBOL`, `MISSING_FROM_DIRECTORY` et les changements de champs sont enregistrés avec `confirmed=0`. Une radiation doit être confirmée par corporate action ou plusieurs observations : une absence isolée n’est jamais suffisante.

### Corporate actions

Les événements Business Quant et Alpaca restent séparés par fournisseur. `conflict_group_key` rapproche les événements portant sur le même symbole, type et date sans supprimer les désaccords. Les splits, dividendes, changements de ticker, fusions, spin-offs et delistings restent donc auditables source par source.

### SEC EDGAR et normalisations

`sec_edgar_incremental` lit les daily indexes des derniers jours et ne télécharge que les accessions absentes ou dont le contenu n’avait pas pu être conservé. `SEC_EDGAR_USER_AGENT` est obligatoire au format `NomApplication contact@domaine`. L’heure d’acceptation SEC est extraite du header SGML lorsqu’elle existe ; `available_at` reste l’heure réellement reçue par l’application, choix volontairement conservateur.

La taille d’une soumission complète est plafonnée par `max_submission_bytes` (16 MiB par défaut), nettement sous le paquet MySQL de 64 MiB. Si l’archive complète dépasse cette limite, le collecteur lit seulement son en-tête SGML, identifie le fichier de type principal (`primary_document`) et télécharge directement ce document, lui aussi plafonné par `max_primary_document_bytes`. Chaque accession est validée dans une transaction courte indépendante : un dépôt exceptionnel ne peut plus annuler les dépôts déjà enregistrés. Si même le document principal est indisponible ou trop volumineux, ses métadonnées sont conservées, le contenu reste `NULL` et l’anomalie apparaît dans `details_json` pour permettre une relance ultérieure.

Les batchs P3/P4 relisent ce RAW local : aucun second téléchargement SEC. P3 extrait les items 8‑K/6‑K. P4 normalise les holdings XML embarqués des 13F et conserve une ligne de dépôt lorsque la table d’information n’est pas analysable. Les champs non fiables restent `NULL` plutôt que d’être inventés.

#### Annexes SEC EX-99

Les annexes sont un flux distinct, activé prospectivement avec
download_exhibits: true. Le collecteur consulte
la page de détail de chaque dépôt, sélectionne les types commençant par les
préfixes de exhibit_type_prefixes (EX-99 par défaut, donc EX-99.1, EX-99.2,
etc.) et enregistre chaque document séparément dans sec_filing_documents. Le
formulaire principal n’est jamais concaténé avec ses annexes. HTML, texte et
PDF sont conservés en binaire avec URL, type MIME, taille et SHA-256.
max_exhibit_bytes limite chaque document à 8 MiB et max_exhibits_per_filing à
dix annexes par dépôt. Une annexe trop volumineuse conserve ses métadonnées
avec un contenu NULL, produit une alerte et pourra être retentée. L’unicité
(accession_number, document_name) rend les passages répétés idempotents.

Configuration active :

    sec_edgar_incremental:
      download_exhibits: true
      exhibit_type_prefixes: "EX-99"
      max_exhibits_per_filing: 10
      max_exhibit_bytes: 8388608

Le lookback configuré est de sept jours ouvrés. Activer l’option ne constitue
donc pas un backfill historique complet ; un rattrapage doit temporairement
élargir lookback_days ou utiliser une campagne dédiée.

### Borrow, analystes, options et ouverture

Alpaca Assets permet de suivre `shortable`, `easy_to_borrow`, `marginable` et `tradable` plusieurs fois par séance. L'endpoint renvoie globalement les actifs Alpaca : le payload RAW global est conservé pour audit, mais seules les actions US appartenant à `config/univers_batch/univers_filtred_tradable.txt` sont normalisées dans `stock_borrow_status_snapshots`. Cela ne fournit ni borrow fee, ni utilization, ni lendable supply.

Le batch analyste Yahoo existant respecte désormais `enabled: false`, distingue couverture EPS et REVENUE et ne tourne plus deux fois le même jour avec un `resume` rendant le second passage vide. Business Quant analyste est un challenger désactivé. Sa population cible est l’univers stable `config/univers_batch/univers_filtred_tradable.txt`, et non la sélection d’un modèle Oracle courant.

Les trois collecteurs de recherche `business_quant_analyst_snapshot`, `oracle_options_indicative_snapshot` et `oracle_opening_window_sync` utilisent le même univers tradable stable. Ce contrat évite un biais de sélection : un TOP20 produit aujourd’hui par un batch donné ne doit pas décider quelles données seront disponibles demain pour réentraîner ou backtester un autre Oracle, un autre horizon, un modèle Per-Symbol ou un ranker. Les noms historiques contenant `oracle_` sont conservés pour compatibilité, mais ne signifient plus que la collecte est limitée au TOP20. Le contrat détaillé Alpaca de la fenêtre d'ouverture est documenté dans [`../ml/oracle_opening_window_alpaca.md`](../ml/oracle_opening_window_alpaca.md).

Les barres d'options retardées et les ajustements OCC suivent un contrat distinct détaillé dans [`../ml/options_delayed_alpaca_occ.md`](../ml/options_delayed_alpaca_occ.md). Ils ne transforment pas Alpaca en source NBBO officielle.

Par défaut, le service charge tout le fichier. `max_symbols` n’est jamais une
limite implicite de production ; il reste accepté uniquement lorsqu’il est fourni
explicitement pour un smoke test. Au 12 septembre 2026, le fichier contient
1 798 symboles uniques. Le batch options utilise le fichier complet : il ne
reçoit ni TOP20 ni identifiant de batch Oracle. Ce nombre reste un cliché,
pas un plafond codé. Opening-window est maintenant un collecteur Alpaca IEX
actif, et non un pilote Business Quant à activer.

Le collecteur options réduit le volume au niveau **des contrats**, pas au niveau
des actions :

- cours du sous-jacent obtenu par snapshots actions Alpaca IEX, par lots de 100 ;
- fenêtre de strikes comprise par défaut entre 80 % et 120 % du sous-jacent ;
- expirations interrogées autour de DTE 5, 10 et 20, puis conservation de
  l'expiration disponible la plus proche de chacun de ces trois horizons ;
- pour chaque expiration et côté CALL/PUT, un contrat est retenu au plus près
  de chaque moneyness cible 0,85/0,90/0,95/1,00/1,05/1,10/1,15 ;
- quote bid/ask bilatérale, bid d'au moins 0,01 USD et spread relatif maximal de
  100 % ;
- open interest d'au moins 10 lorsqu'Alpaca le fournit ; une valeur manquante ne
  bloque pas le contrat car l'absence peut venir de l'endpoint de référence ;
- pagination intégrale des snapshots et des contrats, avec échec explicite si
  la limite de sécurité est atteinte.

Les réponses RAW paginées sont conservées avant le filtre. La table normalisée
reçoit les quotes, trades, IV, Greeks et l'open interest issu de
`/v2/options/contracts`. Le volume journalier reste `NULL` : le snapshot de
chaîne gratuit ne le fournit pas de façon exploitable en bulk. Il ne doit pas être
confondu avec `trade_size`, qui est seulement la taille du dernier trade.

Le feed reste **Alpaca Basic `indicative`**, jamais OPRA/NBBO : ses quotes sont
modifiées et ses trades peuvent être retardés. Il est autorisé uniquement pour
constituer des features de recherche prospectives ; il ne doit jamais fournir un
prix d'exécution live. Le passage unique est planifié à 16:20 New York, vingt
minutes après la clôture régulière. Un dataset ML quotidien doit sélectionner
une seule observation PIT par séance selon une règle pré-enregistrée, par
exemple la dernière observation complète disponible.

La collecte est prospective : changer ultérieurement de modèle ou de TOP20 ne supprime pas les observations déjà acquises. En revanche, l’activation aujourd’hui ne reconstitue pas automatiquement un historique PIT antérieur si le fournisseur ne l’expose pas avec ses dates d’observation d’origine.

### Short volume FINRA

`finra_short_volume_sync` télécharge le fichier public Consolidated NMS sur une fenêtre glissante de sept jours, puis conserve seulement les symboles de `config/univers_batch/univers_filtred_tradable.txt`. Le passage unique à 23 h New York privilégie la disponibilité de la publication du jour. Une ligne strictement identique est ignorée par sa clé incluant le hash ; une correction crée une nouvelle version auditable. Le payload source complet est conservé dans `pit_raw_payloads`.

Le verdict ML historique `NO_GO` est conservé. **La collecte est arrêtée** :
`BLOCKED_FINRA_PREDICTIVE_USE`, même si le handler existe. Les détails de
fenêtre décrivent ses capacités techniques, pas une consigne de réactivation
ni une validation des droits.

### FRED/ALFRED

Le batch conserve pour chaque observation la valeur, `realtime_start`, `realtime_end`, la date de vintage et l’heure de réception. Les futurs datasets doivent joindre sur `available_at <= decision_time` et sélectionner le dernier vintage alors disponible ; joindre seulement sur `observation_date` créerait une fuite de révision.

## Qualité et alertes

FRED/ALFRED est **bloqué** par `BLOCKED_FRED_ARCHIVE_ML_RIGHTS`.
Posséder une clé ne lève pas ce verrou. La description de son stockage
ci-dessus explique seulement le contrat implémenté.

`pit_data_quality_daily` vérifie au minimum : âge des barres Business Quant, âge du security master, âge du borrow snapshot, âge du dernier vintage macro, derniers états métier échoués sur 24 heures et couverture sur sept jours de l’univers configuré. Le seuil de couverture par défaut est 90 %. Le compteur `failed_runs_24h` retient uniquement le dernier run de chaque batch métier : un échec corrigé par une relance réussie ne reste plus critique pendant 24 heures. Les anciens échecs de `pit_data_quality_daily` sont également exclus afin que le moniteur n’entretienne pas sa propre alerte.

Ces contrôles et tables sont historiques : `pit_data_quality_daily` est
**retiré du catalogue US**, pas simplement désactivé temporairement. Ne pas
réactiver FINRA ou FRED pour satisfaire un ancien contrôle ; leurs blocages
droits/prudence priment. Les contrôles de couverture intégrés aux importations,
au risque et aux nouvelles entrées restent indépendants.

Pour `market_cap_sync`, la couverture minimale opérationnelle est fixée à 95 %. Une couverture supérieure ou égale à ce seuil produit un statut `COMPLETED`, zéro échec et zéro alerte ; les symboles non couverts restent néanmoins conservés dans `details_json` (`uncovered_count` et `uncovered_symbols`). En dessous de 95 %, le run échoue de manière bloquante.

Une anomalie critique crée une ligne dans `pit_data_quality_issues`, fait échouer le batch qualité et déclenche la notification du lanceur. Cet échec transporte néanmoins l’`Outcome` complet : `requested_count`, `received_count`, `persisted_count`, `failed_count`, avertissements et liste `critical_checks` sont conservés dans `pit_collection_runs` et dans le résumé envoyé aux notifications.

Les réponses brutes permettent ensuite d’ajouter sans perte d’historique : détection de changement de schéma, volumes anormalement faibles, conflits fournisseurs, trous par symbole et contrôle de cohérence OHLC.

### Notifications de fin de batch

Tous les nouveaux batchs installés par `install_forward_pit_task.ps1` passent par le même lanceur. Après chaque exécution réelle, réussie ou échouée, celui-ci transmet le statut, le code retour, la durée, le message d'erreur et les 300 dernières lignes du run à `scripts/send_batch_email.py`. Le service métier émet un résumé machine lisible, y compris lorsqu'une exception remonte ; le lanceur PowerShell possède un second `try/catch` afin de notifier aussi une erreur d'orchestration.

- email via `ihm.services.email_notifier` et les variables `ALPHA_TRADE_EMAIL_*` / `ALPHA_TRADE_SMTP_*` ;
- Telegram via `service.telegram`, `TOKEN_TELEGRAM_BOT` et `TELEGRAM_CHAT_ID`.

Les deux messages indiquent systématiquement :

- `demandés` : unités de travail prévues ;
- `reçus` : réponses ou éléments effectivement obtenus ;
- `persistés` : lignes écrites ou mises à jour ;
- `échecs` : unités en erreur, avec un minimum de 1 pour un run en statut `ERROR` ;
- `alertes` : avertissements métier, quotas, erreurs temporaires, schéma ou parsing.

En cas d'échec, le message d'erreur est joint aux deux canaux. Les résumés de plusieurs fournisseurs exécutés dans le même run sont additionnés. L'échec d'un canal ne court-circuite jamais l'autre : une panne SMTP laisse Telegram être tenté, et inversement. Ces notifications restent best-effort et une panne du notificateur ne transforme pas un batch métier réussi en échec ; son diagnostic est toutefois écrit dans le journal avec le préfixe `NOTIFY`.

Un batch désactivé ou ignoré parce qu’une instance est déjà active ne génère pas de fausse notification de succès. Dans **Workflow & Orchestration → Batch**, le titre d'un batch dont le dernier run enregistré est en échec apparaît en rouge et en gras ; pour les batchs historiques sans ligne dans `pit_collection_runs`, le code retour de la dernière tâche Windows sert de fallback. Le panneau conserve les compteurs et le détail de l'erreur.

## Mise en service

1. Appliquer `alembic upgrade head` avant le premier lancement.
2. Définir les secrets requis par les seules familles autorisées et actives : `BUSINESS_QUANT_API_KEY`, identifiants Alpaca ou `SEC_EDGAR_USER_AGENT` selon le batch. Ne pas activer FRED par la seule présence de `KEY_FRED`.
3. Vérifier les chemins `symbols_file` et laisser désactivés les pilotes marqués `PENDING_*` ou `ENABLE_AFTER_*`. Pour le batch options actif, vérifier que les identifiants Alpaca configurés donnent accès aux endpoints Data et Options.
4. Tester un batch manuellement avec :

   `powershell -ExecutionPolicy Bypass -File .\scripts\windows\forward_pit_launcher.ps1 -BatchName daily_bars_sync -Force -DryRun`

5. Installer un batch :

   `powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_forward_pit_task.ps1 -BatchName daily_bars_sync`

6. Installer tous les nouveaux batchs actifs :

   `powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_all_forward_pit_tasks.ps1`

Le mode `-DryRun` appelle le fournisseur et valide le parsing mais n’écrit ni RAW, ni table normalisée, ni ligne de run. `-Force` ignore seulement le calendrier du lanceur ; il n’active pas une section ayant `enabled: false` au niveau du service.

## Activation progressive recommandée

Observer les couvertures et corrections des familles déjà actives, sans élargir
les droits implicitement. Les options et opening-window collectent l'univers
stable complet, **sans dépendre d'un TOP20 Oracle quotidien**. Le consensus
Yahoo est bloqué ; Business Quant reste remplacé/désactivé. Auction imbalance,
prêt de titres complet et NBBO restent des contrats à pourvoir, pas des
collecteurs simulés. [Catalogue courant](catalogue_batchs_actuel.md).

## Pipeline US quotidien paramétrable 1 à 14

Le batch `us_pipeline` enchaîne les étapes configurées dans `config.yaml → us_pipeline.steps` ou `steps_friday` (1 à 14), à 22:45 Europe/Paris, lundi–vendredi après clôture US. T1 est exclu et LIVE interdit ; `execution_mode: paper` et `account_id: default` sont raccordés. Les étapes 11/12 en PAPER et 13/14 même en simulation exigent un compte configuré paper ; aucun ordre sans étape 12. 13 synchronise les opérations sur titres, 14 les applique au ledger à la date de séance ; arrêt au premier échec. Voir [le guide dédié](us_pipeline.md).

Les collectes quotes et earnings sont désormais intégrées aux étapes 4 et 5 : les sections/tâches autonomes `latest_quotes_sync` et `earnings_calendar_sync` sont désactivées pour éviter deux planifications. L'univers commun `config/univers_batch/univers_filtred_tradable.txt` est aussi appliqué au screener et à l'import/scoring ticker du sentiment ; fenêtres quotes J−7/J, earnings J−7/J+30. Les collecteurs restent disponibles en CLI pour les interventions manuelles.

## Retrait du contrôle US — 6 octobre 2026

Les horaires FR/CN ont également été revus le 10 octobre pour l'absence
07:30–20:00 Paris : [planning, durées et limites de couverture](horaires_fr_cn_presence_pc.md).

`pit_data_quality_daily` est retiré de `batch.yaml` et de la page Batch US à la demande de l'utilisateur. Il n'est plus installable ou lançable depuis ce catalogue. La tâche `AlphaTrade-PitDataQualityDaily` était déjà absente lors du contrôle Windows. Les journaux et les tables historiques de qualité sont conservés ; les contrôles CN et FR ne sont pas concernés. Les anciennes mentions de ce batch dans ce document décrivent l'ancien fonctionnement, pas une entrée actuelle du catalogue.

