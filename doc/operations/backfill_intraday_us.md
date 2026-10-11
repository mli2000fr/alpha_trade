# Backfill des barres intraday US — EODHD

État au 11 octobre 2026 : table, service CLI et page IHM livrés. La table a été
créée dans `alpha_trade` ; aucun téléchargement massif n'a été lancé. Les tests
SQL d'insertion, de mise à jour et d'idempotence ont été annulés en transaction.

## Utilisation dans l'IHM

Ouvrir **Analyse & Recherche → 🕒 Barres intraday**. Choisir :

- la date de début et la date de fin, inclusives, en dates New York ;
- un fichier univers parmi les fichiers proposés ; par défaut
  `config/univers_batch/univers_filtred_tradable.txt` ;
- l'intervalle : **5 minutes par défaut**, 1 minute ou 1 heure ;
- éventuellement une limite de tranches pour commencer par un petit passage.

La fin est limitée à la veille New York : aucune séance en cours n'est importée.
La commande équivalente et le budget indicatif sont affichés avant lancement.
Le bouton **Lancer / reprendre le backfill** démarre un processus géré : barre
de progression, compteurs, titre/date en cours, logs et bouton d'arrêt sont
disponibles dans la page. Aucun batch quotidien existant n'est modifié.

Exemple CLI, sans quota dépensé ni écriture SQL :

```powershell
python -u -m service.eodhd.intraday_backfill --start-date 2025-01-01 --end-date 2025-12-31 --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt --interval 5m --plan-only
```

Retirer `--plan-only` pour télécharger. Ajouter `--max-tasks 1` pour limiter le
premier passage à une tranche titre/période. Une tranche représente un titre et
30 jours calendaires par défaut, et non 30 séances. `--chunk-days` change cette
taille. Le service garde une pause entre les appels et utilise les contrôles de
quota, retries et circuit breaker du client EODHD existant.

## Table et conventions

Table indépendante : **`alpha_trade.stock_bars_intraday`**. Les bases CN/FR et
`stock_bars_daily` ne sont pas modifiées. Pour l'instant, le collecteur accepte
uniquement un univers US.

| Données | Convention |
|---|---|
| `symbol`, `provider_symbol` | symbole interne et identifiant EODHD |
| `bar_timestamp`, `bar_end_timestamp` | début UTC et fin exclusive UTC de la barre |
| `interval_code` | `5m`, `1m` ou `1h` ; les intervalles peuvent coexister |
| `trade_date` | date calendaire New York, pas une date décalée vers la prochaine séance |
| `session_tag` | pré-marché, séance régulière, post-marché ou jour non négociable selon calendrier US |
| OHLC, `volume` | données brutes fournisseur validées, pas de remplissage de trous |
| `data_source`, `data_adjustment` | `eodhd_intraday`, `raw` |
| `observed_at` | heure réelle de récupération ; ce n'est pas une preuve de disponibilité historique |
| `payload_hash`, `run_id` | empreinte de la barre et plan de téléchargement |

La clé primaire est `(symbol, bar_timestamp, interval_code, data_source)`.
Les répétitions n'ajoutent pas de doublons. Une réponse identique ne change pas
les métadonnées d'observation ; une correction du fournisseur met à jour la
barre. Les réponses brutes précédentes restent archivées lors d'un rafraîchissement.

Pas de `adj_close` ni de VWAP inventé : le fournisseur livre des OHLCV bruts.
Les prix intraday ne doivent pas être mélangés directement avec des clôtures
journalières ajustées aux dates de splits ou autres opérations sur titres.

DDL : `database/sql/stock/stock_bars_intraday.sql`.
Migration : `0097_stock_bars_intraday`, après `0096_public_macro_versions`.
La création directe de cette table ne modifie pas le pointeur Alembic et ne
signifie pas que toutes les migrations précédentes sont déployées.

## Reprise, stockage et qualification

Chaque plan fige son univers, son empreinte et ses dates sous
`artifacts/eodhd_intraday_backfill/intraday-<empreinte>/` :

- `plan.json` : paramètres et univers ;
- `progress.json`, `report.json` : état et compteurs ;
- `tasks/` : checkpoint de chaque tranche ;
- `raw/` : réponses brutes compressées, sans clé API.

Les écritures SQL sont commitées par lots de **500 barres**, sans attendre la fin
du backfill. Une relance du même plan ignore les tranches terminées, y compris
les réponses vides, et reprend les autres depuis l'archive locale si possible.
Une panne au milieu d'une tranche ne crée pas de doublons à la reprise.
Changer l'univers produit un autre plan ; l'IHM vérifie qu'il n'a pas changé
entre aperçu et lancement. Un verrou empêche deux processus du même plan.

`--refresh` retélécharge aussi les tranches terminées/vides. C'est notamment
utile pour examiner une réponse vide suspecte ou des corrections fournisseur.
Les droits refusés, le quota épuisé ou un circuit ouvert arrêtent le passage
explicitement. Un arrêt manuel conserve les lots déjà commitées.

**Terminée ne signifie pas couverture historique complète** : une réponse vide
est enregistrée comme `EMPTY`, pas comme preuve qu'aucune transaction n'existait.
Les OHLC/volumes invalides et les versions contradictoires sont signalés et
rejetés. Il faut encore mesurer les trous, la couverture et la cohérence avec
les news avant une étude d'impact. `persisted` compte les barres soumises en
UPSERT, pas uniquement les nouvelles lignes ; les compteurs reprennent les
tranches déjà terminées du plan.

## Abonnement et limites du fournisseur

Selon la [documentation intraday EODHD](https://eodhd.com/financial-apis/intraday-historical-data-api),
le forfait EOD seul ne suffit pas : accès EOD + Intraday ou All-in-One nécessaire.
Un appel intraday coûte 5 crédits API. Les limites de plage par requête sont
120 jours pour 1m, 600 pour 5m et 7 200 pour 1h, pas des limites de profondeur
totale. Le service impose des tranches plus courtes ; en 1m, 119 jours maximum
pour ne pas dépasser 120 jours UTC lors du changement d'heure.

L'historique annoncé commence en 2004 pour les actions US en 1m et en octobre
2020 pour 5m/1h. La présence effective doit être contrôlée titre par titre.
Les données peuvent être finalisées plusieurs heures après clôture et ne sont
pas ajustées rétroactivement pour splits/dividendes. EODHD indique aussi que ses
données ne sont pas un flux de bourse certifié et peuvent être indicatives :
ne pas les assimiler à un SIP officiel ni à des quotes/fills d'exécution.

## Implémentation et validation

- API : `service/eodhd/clientEodhd.py::fetch_intraday` ;
- orchestration : `service/eodhd/intraday_backfill.py` ;
- persistance : `database/intraday_bars.py` ;
- page : `ihm/pages/intraday_bars.py` ;
- commandes/univers IHM : `ihm/services/intraday_backfill.py` ;
- tests : `tests/test_intraday_backfill.py`.

Validation : **104 tests passés**, incluant calendrier/DST, bornes de tranches,
normalisation, doublons, reprise, refus d'accès, page IHM et imports EODHD
existants. Test SQL réel validé sans conserver de lignes de test. Ces tests ne
prouvent pas l'accès intraday de l'abonnement actuel ; aucun appel massif lancé.
