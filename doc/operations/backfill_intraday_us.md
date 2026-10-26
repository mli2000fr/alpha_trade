# Backfill des barres intraday US — Alpaca / EODHD

État initial au 11 octobre 2026 : table, service CLI et page IHM livrés. La table a été
créée dans `alpha_trade` ; aucun téléchargement massif n'a été lancé. Les tests
SQL d'insertion, de mise à jour et d'idempotence ont été annulés en transaction.
La colonne `provider` est déployée. Un petit test HTTP AAPL du 2 janvier 2025
(14:30–15:00 UTC) a retourné 7 barres pour IEX et 7 pour SIP avec le compte
principal, sans insertion SQL. Ce smoke ne prouve pas la couverture de l'univers.

**Mise à jour du 17 octobre 2026 : SIP obligatoire pour toute nouvelle collecte
Alpaca.** Le sélecteur et les commandes n’acceptent plus IEX. Un ancien plan IEX
est refusé avant accès SQL ou réutilisation des archives : créer un nouveau plan
SIP et réellement télécharger les données. L’inventaire opérationnel trouve
62 117 194 barres `alpaca_sip` et aucune barre `alpaca_iex` dans cette table.
Voir la [politique et le bilan de migration](migration_iex_vers_sip.md).

## Utilisation dans l'IHM

Ouvrir **Analyse & Recherche → 🕒 Barres intraday**. Choisir :

- le fournisseur **Alpaca par défaut** ou EODHD ;
- le flux Alpaca **SIP uniquement**, sans fallback automatique ;
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
Dans **Exécution à suivre**, **Arrêter le run** arrête le processus sélectionné.
Après son arrêt ou sa fin, **Supprimer de la liste** retire cette exécution de
l'historique visible. Les barres SQL, logs et points de reprise restent conservés.
La suppression d'un run actif est refusée. Aucun ancien fichier IEX n’est
réétiqueté SIP ; les archives anciennes restent identifiées par leur vrai flux.
Le bloc de logs a une hauteur de 350 pixels et un défilement interne (100 dernières
lignes). `INFO` indique une progression, pas un échec : les anciens préfixes
`[stderr]` identifient un flux de sortie. Les nouveaux lancements écrivent les
logs du collecteur sur stdout ; une exception garde son traceback. Un run déjà
en cours n'est pas redémarré pour changer son flux de logs.

Défauts de la page et de la CLI dans `config.yaml` (section indépendante du
fournisseur de barres journalières) :

```yaml
intraday_backfill:
  provider: alpaca
  alpaca_feed: sip
  account_id: default
```

Les clés Alpaca proviennent du registre de comptes existant, jamais des
arguments de commande. La CLI peut surcharger `--provider`, `--alpaca-feed` et
`--account-id`. L'IHM fige ces paramètres dans la commande de lancement.

Exemple CLI, sans quota dépensé ni écriture SQL :

```powershell
python -u -m service.market.intraday_backfill --provider alpaca --alpaca-feed sip --account-id default --start-date 2025-01-01 --end-date 2025-12-31 --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt --interval 5m --plan-only
```

Retirer `--plan-only` pour télécharger. Ajouter `--max-tasks 1` pour limiter le
premier passage à une tranche titre/période. Une tranche représente un titre et
30 jours calendaires par défaut, et non 30 séances. `--chunk-days` change cette
taille. Le service garde une pause entre les appels et utilise les contrôles de
quota, retries et circuit breaker du client EODHD existant.
Pour Alpaca, les pages de 10 000 points sont parcourues jusqu'à disparition de
`next_page_token`, avec une pause entre pages et des retries HTTP bornés. Le
budget de crédits EODHD n'est pas affiché pour Alpaca : le nombre d'appels
effectifs dépend aussi de la pagination. Les connexions HTTPS utilisent les
certificats vérifiés Certifi + Windows ; jamais `verify=False`.

## Table et conventions

Table indépendante : **`alpha_trade.stock_bars_intraday`**. Les bases CN/FR et
`stock_bars_daily` ne sont pas modifiées. Pour l'instant, le collecteur accepte
uniquement un univers US.

| Données | Convention |
|---|---|
| `symbol`, `provider_symbol` | symbole interne et identifiant EODHD |
| `bar_timestamp`, `bar_end_timestamp` | début UTC et fin exclusive UTC de la barre |
| `interval_code` | `5m`, `1m` ou `1h` ; les intervalles peuvent coexister |
| `provider` | `alpaca` ou `eodhd`, fournisseur explicite |
| `trade_date` | date calendaire New York, pas une date décalée vers la prochaine séance |
| `session_tag` | pré-marché, séance régulière, post-marché ou jour non négociable selon calendrier US |
| OHLC, `volume` | données brutes fournisseur validées, pas de remplissage de trous |
| `data_source`, `data_adjustment` | nouvelles collectes : `alpaca_sip` ou `eodhd_intraday` ; `raw`. `alpaca_iex` reste reconnaissable comme provenance historique, non collectée |
| `observed_at` | heure réelle de récupération ; ce n'est pas une preuve de disponibilité historique |
| `payload_hash`, `run_id` | empreinte de la barre et plan de téléchargement |

La clé primaire est `(symbol, bar_timestamp, interval_code, data_source)`.
Les répétitions n'ajoutent pas de doublons. Une réponse identique ne change pas
les métadonnées d'observation ; une correction du fournisseur met à jour la
barre. Les réponses brutes précédentes restent archivées lors d'un rafraîchissement.
Une barre IEX n'écrase donc jamais une barre SIP ou EODHD au même timestamp.

Pas de `adj_close` ni de VWAP inventé dans la table : elle stocke les OHLCV bruts.
Pour Alpaca, les champs natifs supplémentaires `n`/`vw` restent dans les archives.
Les prix intraday ne doivent pas être mélangés directement avec des clôtures
journalières ajustées aux dates de splits ou autres opérations sur titres.

DDL : `database/sql/stock/stock_bars_intraday.sql`.
Migration : `0097_stock_bars_intraday`, après `0096_public_macro_versions`.
L'ajout de `provider` est porté par `0098_intraday_provider`, avec SQL pour
table existante `database/sql/stock/stock_bars_intraday_provider.sql` ; ce SQL
ALTER n'est à exécuter qu'une fois, si la colonne est absente. Les lignes
EODHD antérieures conservent le fournisseur `eodhd` par défaut.
La création directe de cette table ne modifie pas le pointeur Alembic et ne
signifie pas que toutes les migrations précédentes sont déployées.

## Reprise, stockage et qualification

### Reprise ciblée de 2018 — 23 octobre 2026

Le plan `intraday-5dfcdc71cfaf4819ed1b` (SIP brut 5 minutes, compte
`default`, univers figé de 1 790 titres) s'est arrêté le 23 octobre à
03:02 UTC sur un HTTP **429**, après les tentatives HTTP automatiques.
La tranche en échec était `HOV`, du 28 octobre au 27 novembre 2018
exclusif. Le code regroupe 401/403/429 dans un même message
« compte/droits/quota » ; ici le code observé est bien une limitation
de requêtes, pas une preuve de refus des droits SIP historiques.

L'inventaire des checkpoints avant reprise donnait :

- 14 719 tranches avec barres et 3 960 réponses vides déjà traitées ;
- une tranche en échec et 4 590 non commencées, soit **4 591 à reprendre** ;
- aucune archive brute disponible pour ces tranches restantes.

Aucun processus intraday actif n'a été trouvé avant la relance. Le plan
2018–2019 `intraday-75d9f29edb1bb670e48c`, affiché `RUNNING` dans un
ancien fichier, n'a pas été relancé : ce statut seul ne prouve pas qu'un
processus tourne. La reprise utilise le plan 2018 d'origine, **sans
`--refresh`**, avec `--expected-plan-id` et une pause de 2 secondes entre
requêtes/pages. Elle ignore les 18 679 checkpoints terminés, sans modifier
les autres téléchargements ni les paramètres de production.

Relance effectuée le **23 octobre à 10:08 Paris**. Premier résultat vérifié :
HOV a fourni 1 540 barres, soumises à la persistance sans rejet ; le
collecteur est ensuite passé à HP. Ce constat confirme le redémarrage,
pas la fin du rattrapage ni la complétude de toutes les séances.

Suivi du passage :

- progression : `artifacts/intraday_backfill/intraday-5dfcdc71cfaf4819ed1b/progress.json` ;
- logs : `log/intraday-2018-resume-20261023-100812.stdout.log` et
  `log/intraday-2018-resume-20261023-100812.stderr.log` ;
- `report.json` peut encore contenir le bilan de l'ancien passage bloqué
  jusqu'à la fin du nouveau passage : lire la progression et les logs
  courants. Les réponses `EMPTY` restent à qualifier, sans les assimiler
  automatiquement à des séances complètes.

Chaque plan fige son univers, son empreinte et ses dates sous
`artifacts/intraday_backfill/intraday-<empreinte>/` :

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
Le fournisseur, le flux Alpaca et le compte sont figés dans le plan et participent
à son empreinte : changer de source crée un plan distinct. Les anciens plans
version 1 gardent leur répertoire `artifacts/eodhd_intraday_backfill/`.

## Abonnement et limites du fournisseur

### Alpaca

[API officielle de barres historiques](https://docs.alpaca.markets/us/reference/stockbars) :
intervalle 5Min, données brutes et pagination explicite. IEX représente seulement
les échanges de cette place, pas le volume consolidé ; des trous sont possibles.
SIP couvre les places US, avec droits à vérifier sur le compte. Le smoke présent
a réussi avec SIP historique mais ne constitue pas une qualification de tous
les titres/dates. Aucun fallback SIP → IEX ni Alpaca → EODHD n'est effectué.
Les erreurs 401/403/429 persistantes bloquent le passage.

Le service utilise `asof=-` : pas de remappage automatique des anciens tickers.
L'identité historique, les radiations et les changements de symbole doivent être
qualifiés séparément. Les plages avant le 4 janvier 2016 sont refusées pour Alpaca.

### EODHD

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

- API : `service/eodhd/clientEodhd.py::fetch_intraday`, `service/alpaca/intraday_bars.py` ;
- orchestration : `service/market/intraday_backfill.py` ; l'ancien module sous
  `service/eodhd/` reste un point d'entrée compatible, avec les mêmes nouveaux défauts ;
- persistance : `database/intraday_bars.py` ;
- page : `ihm/pages/intraday_bars.py` ;
- commandes/univers IHM : `ihm/services/intraday_backfill.py` ;
- tests : `tests/test_intraday_backfill.py`.

Validation : **111 tests passés**, incluant calendrier/DST, bornes de tranches,
normalisation, doublons, reprise, refus d'accès, page IHM et imports EODHD
existants. Test SQL réel validé sans conserver de lignes de test. Ces tests ne
prouvent pas l'accès intraday de l'abonnement actuel ; aucun appel massif lancé.
La pagination Alpaca, les défauts configurables, la séparation des plans par
flux, le blocage des refus d'accès et la reprise Alpaca sont également testés.
