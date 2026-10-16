# Consensus FR — EODHD, snapshots prospectifs de recherche

État vérifié le **15 octobre 2026**. Le batch `fr_consensus_snapshot` conserve
son nom et son launcher FR mais **remplace Yahoo par EODHD**. Aucun fallback
Yahoo ou vers une cotation US. L'ancien pilote Yahoo reste une preuve historique,
pas une source réactivée. Le changement ne restaure aucune archive Yahoo supprimée.

## État livré

- `batch_fr.yaml` : `provider: eodhd`, `status: ACTIVE_RESEARCH`.
- **`enabled: true` sur demande explicite de l'utilisateur le 15 octobre**.
  L'activation du catalogue ne prouve pas l'installation de la tâche Windows.
- Horaire principal conservé : **20 h Europe/Paris** ; jours configurés 0…6,
  donc tous les jours comme les snapshots US. Pas de run entre 7h30 et 20h.
- Pas de rattrapage historique J−7/J : les états du consensus non observés ne
  se reconstruisent pas. Une relance le même jour reprend seulement les absents.
- Notifications mail/Telegram par `fr_operational_launcher_15a.ps1` et le launcher
  commun. Résumé structuré : demandés, reçus, persistés, échecs, alertes et erreur.

## API et données

`GET https://eodhd.com/api/calendar/trends?symbols=OR.PA&fmt=json`
avec la clé existante, jamais affichée dans les rapports.

Même parseur numérique/champs que `eodhd_consensus_snapshot` US, sans modifier
ce dernier : EPS et revenus moyens/bas/hauts, nombres d'analystes, croissance,
EPS courant et points relatifs 7/30/60/90 jours, compteurs de révisions EPS.
Tous les couples date fiscale/horizon fournis sont conservés, pas seulement
la première ligne de la réponse.

Ne sont **pas** collectés par ce batch : objectifs de cours, recommandations
achat/conserver/vendre, borrow ou options. Un champ absent reste `NULL`.
La devise n'étant pas fournie par ces réponses Trends, elle reste inconnue :
une cotation à Paris ne prouve pas que les estimations sont exprimées en EUR.

## Univers et identité

Référentiel `artifacts/fr/sprint6c_reference/identities.jsonl.gz` : 330 identités,
**294 actives vérifiées**, 36 exclues lors du contrôle. Segments XPAR/ALXP/XMLI.
Symboles `.PA`, unicité symbole/ISIN, checksum ISIN et noms courants ESMA requis.
L'empreinte du référentiel et la référence d'identité sont archivées par passage.

Ce référentiel courant n'est pas un univers historique sans biais de survivance.
L'endpoint Trends confirme le code demandé mais ne renvoie pas ici une preuve
indépendante d'ISIN ; l'identité fiscale et les unités restent à qualifier.
Un changement de référentiel en cours de journée bloque la reprise automatique.

## Stockage isolé

Les deux tables ont été créées dans **`alpha_trade_fr`** :

| Table | Usage |
| --- | --- |
| `eodhd_consensus_raw_payloads` | Réponse complète par titre/appel, empreinte, run, réception UTC, statut de normalisation et reçu de disponibilité |
| `stock_analyst_consensus_eodhd_history` | Valeurs par titre, date réelle d'observation Paris, date fiscale et horizon ; ISIN, empreinte du référentiel et lien vers la réponse brute |

Les tables US `alpha_trade.*`, leurs `pit_collection_runs`/`pit_raw_payloads`,
et toutes les tables Yahoo sont **inchangées et non alimentées** par le batch FR.
Le nom de la table normalisée est identique à celui de l'US mais la base physique
est distincte. Routage imposé `FR_EQ / fr_primary / alpha_trade_fr`, sans override US.

Les lignes brutes et normalisées sont d'abord committées avec disponibilité
non confirmée (`available_at=NULL`), puis la réception est confirmée après ce
commit, en UTC. Un reçu manquant peut être réparé après vérification des lignes
déjà committées, sans appel réseau et sans antidatage.

Unicité : `(provider,symbol,snapshot_date,fiscal_period_end,horizon_raw)`.
La première observation quotidienne gagne ; les observations d'un autre jour
s'ajoutent. Les réponses brutes réussies sont conservées même si le parseur
refuse leur schéma. Les valeurs ne sont pas remplacées pour forcer la qualification.

Fichiers opérationnels séparés de l'ancien Yahoo :
`artifacts/fr/operations/fr_consensus_snapshot/eodhd/` contient `raw`, `receipts`,
et `days/YYYY-MM-DD.json`. L'IHM lit uniquement ce checkpoint EODHD lorsque le
fournisseur configuré est EODHD ; elle ne reprend pas un ancien succès Yahoo.
Fichiers couverts par `fr_artifacts_backup`, tables par `fr_db_backup` lorsque
ces sauvegardes s'exécutent avec succès.

## Reprise, compteurs et erreurs

Une requête Trends par symbole ; plafonds de 400 symboles et 400 appels logiques
par jour configurables, intervalle 1,1 seconde. Tracker global EODHD actif ;
les retries techniques ne constituent pas des snapshots supplémentaires.
Budget local réservé au checkpoint avant l'appel.

- Demandés : titres éligibles dans le périmètre du passage.
- Reçus : titres nouvellement reçus avec au moins une estimation financière.
- Persistés : **nouvelles lignes fiscales normalisées**, pas nombre de titres.
- `skipped_completed` : observations déjà présentes ce jour, sans nouvel appel.
- `empty_count` / `no_consensus_count` : absence normale ou symbole non couvert,
  distincte d'une erreur technique ; un simple nombre d'analystes ne prouve pas
  la présence d'une estimation.
- Échecs : réseau, permission, quota, schéma ou SQL ; message explicite et statut
  FAILED, sans masquer les compteurs déjà accumulés.

Pas de seuil arbitraire de 95 % de consensus sur les 294 titres : les petites
capitalisations ne sont pas toutes suivies. La couverture est affichée, pas
assimilée à la qualité ou à une disponibilité ML.

## Vérifications réelles

1. Accès avec l'abonnement existant : OR.PA 56 lignes, SU.PA 55, BN.PA 55,
   AI.PA 58. Témoin AAPL.US 96 lignes ; **aucune ligne US insérée** par ce probe.
2. Installation ciblée des deux tables FR, pas d'upgrade Alembic global.
3. Smoke OR.PA/SU.PA/BN.PA : **3 demandés, 3 reçus, 166 lignes normalisées,
   3 réponses brutes, 0 échec, 0 alerte**.
4. Second passage : **3 déjà observés, 0 appel API, 0 nouvelle ligne**, succès.
   Ce n'est pas une exécution sur tout le catalogue.

Preuves : `artifacts/fr/research/eodhd_consensus_access/20261015-v1`,
`storage-smoke-20261015-v1`, `storage-resume-20261015-v1`.

## Activation utilisateur

Les tables sont installées sur l'environnement contrôlé. Pour une autre base :

```powershell
python -u -m service.fr.eodhd_consensus_daily --install-schema
```

Dans Workflow & Orchestration → Batch → France, `fr_consensus_snapshot` est
déjà activé (`enabled: true`) ; installer/réinstaller la tâche. Le bouton manuel partage
le runner, le verrou et les rapports de la planification.

```powershell
python -u -m service.fr.operational_batch_15a --batch fr_consensus_snapshot --dry-run
```

Le dry-run contrôle le périmètre sans API, SQL ni fichier métier. Smoke réel
explicite limité à cinq titres maximum, sans activer la planification :

```powershell
python -u -m service.fr.eodhd_consensus_daily --smoke --symbols OR.PA,SU.PA,BN.PA --output artifacts/fr/research/eodhd_consensus_access/NOUVEAU_DOSSIER
```

## Avant ML/backtest

Lignes `RESEARCH_ONLY`, identités fiscales/unités/PIT historique non qualifiés.
**Une ligne fiscale de 2023 reçue aujourd'hui n'est pas un snapshot du consensus
connu en 2023.** Les points J−7/30/60/90 sont les valeurs renvoyées lors de la
réception, pas quatre preuves de disponibilité ancienne.

Qualifier titre/exercice/unité/devise, construire les révisions entre observations
réellement comparables et imposer une disponibilité confirmée strictement avant
la décision. Tester ensuite l'apport hors échantillon contre une baseline sans
consensus. Aucun entraînement, backtest ou changement de serving dans cette livraison.

## Droits

Usage de l'API sous l'abonnement EODHD de l'utilisateur et ses conditions
applicables ; ce n'est pas une autorisation de redistribution ou de vente.
Un HTTP200 prouve l'accès technique, pas tous les usages imaginables. La réserve
sur l'automatisation Yahoo reste valable pour Yahoo, pas comme motif de blocage
de ce nouveau collecteur EODHD.
