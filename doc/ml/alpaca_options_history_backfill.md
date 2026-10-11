# Backfill des barres options Alpaca dans la base US

## Demande et périmètre

Backfill demandé le 10 octobre 2026, du **20 janvier 2024 au 9 octobre 2026**,
sur les **1 790 titres** du fichier
`config/univers_batch/univers_filtred_tradable.txt` (copie logique et hash dans
`plan.json`). Le 20 janvier est un samedi : première séance attendue le 22.
Le plan contient **60 860 tranches symbole/mois**, pas autant de symboles ni
de séances. Certains titres ne possèdent pas d'options accessibles.

Table alimentée : **`alpha_trade.stock_option_bars_delayed` uniquement**.
Pas d'alimentation de `stock_option_snapshots`, pas de modification des barres
actions, des modèles, des batchs ou de leur calendrier. Aucun DDL/migration.

## Surface et fréquence

Ce backfill conserve **`timeframe='1Day'`**, utile au signal de volume call/put.
Il ne reconstruit pas toutes les transactions ni toute la chaîne d'options.
Pour chaque séance et sous-jacent, sélection de paires CALL/PUT de même strike
et échéance : ATM, échéances proches de 5/10/20 jours calendaires, tolérance
5 jours. Déduplication si deux cibles retiennent le même contrat. Racine standard
correspondante et taille 100 ; racines ajustées exclues, motifs/couverture archivés.

Le prix de sélection est le **close brut historique IEX** du sous-jacent,
téléchargé séparément, sans ajustement rétroactif des strikes ni recours au prix
actuel. Le volume IEX actions n'est pas utilisé comme signal options. Le prix
IEX n'est cependant pas garanti identique au close consolidé ; le choix ATM est
une approximation documentée. Les jours sans ce prix sont comptabilisés.

Le batch quotidien existant utilise **30Min**. Pour une analyse, choisir une
seule fréquence ou agréger la fréquence intraday séparément : **ne jamais
additionner 1Day et 30Min pour le même contrat/jour**. Dédupliquer aussi les
versions par identité/timestamp si un payload corrigé a été archivé.

## Dates, qualité et provenance

- `bar_timestamp` = timestamp historique fournisseur, stocké UTC naïf.
- `observed_at` et `available_at` = date réelle de réception de la page API.
  La reprise réutilise celle archivée, sans antidater la disponibilité.
- `provider=alpaca`, `feed=historical_default`, `provenance_status=UNVERIFIED_OPRA`.
- OHLC positifs/finis/cohérents, volume et compteur de trades non négatifs ;
  les barres invalides et les barres sélectionnées manquantes sont comptées.
- Un contrat sans barre n'est pas converti en volume zéro.
- Ce backfill ne certifie pas un historique PIT tel que connu à l'époque.
  L'audit prospectif strict doit continuer à respecter `available_at` ; il ne
  doit pas traiter ces insertions rétrospectives comme reçues en 2024/2025.
- OI, IV, Greeks et NBBO historiques ne sont pas reconstruits.
- Catalogue historique récupéré aujourd'hui : couverture survivante et racines
  standard seulement, sans garantie de chaîne complète ou de titres radiés.

## Persistance, reprise et sécurité

Service : `service/alpaca/options_history_backfill.py`.

`INSERT IGNORE` par groupes de 200 lignes, transactions courtes. Index unique
identité + hash vérifié avant toute écriture. Les lignes existantes ne sont ni
écrasées ni supprimées ; un payload différent reste une version différente.
Le marqueur de tranche n'est enregistré qu'après les insertions. Après un crash
intermédiaire, les réponses RAW conservées sont relues et les doublons exacts
sont ignorés. Chaque réponse JSON est compressée sur disque avec son timestamp
de réception ; le plan, les catalogues et les prix de sélection restent archivés.

Verrou OS anti-double lancement, checkpoints JSON atomiques avec retries pour
les conflits Windows transitoires, reprise automatique des tranches en erreur.
Arrêt immédiat sur erreur d'authentification/droits ou après **1 000 tranches
en échec au total**, selon la demande utilisateur (ancien seuil : 10). Le seuil
est configurable par `--max-failed-tasks`, 1000 par défaut ; ce ne sont pas
des erreurs nécessairement consécutives. Le compteur comprend les checkpoints
FAILED non résolus, pas les échecs passés déjà récupérés avec succès. Aucun
contournement d'accès. Retries bornés sur HTTP 429/5xx, un seul processus,
espacement de requêtes 0,4 seconde. Les tâches sans données sont marquées EMPTY,
pas comme une couverture complète. Tout l'univers est parcouru.

## Contrôles avant lancement complet

Cinq tests locaux passent : tranches calendaires, appariement/mutualisation,
contrats expirés/paires manquantes, dates de réception et OHLC invalides.
Première écriture réelle : **54 lignes**, A=13 et AA=41 sur janvier 2024,
confirmées par relecture SQL. Dates historiques du 22 au 31 janvier ; réception
réelle le 10 octobre 2026. Six barres sélectionnées manquent ; rien n'est imputé.
Preuve : `first_insert_verification.json` dans le dossier du backfill.

## Commande et suivi

```powershell
python -u -m service.alpaca.options_history_backfill --write --start-date 2024-01-20 --end-date 2026-10-09 --symbols-file config/univers_batch/univers_filtred_tradable.txt --max-failed-tasks 1000
```

Même commande pour reprendre, **pas simultanément à un processus actif**.
Une modification de l'univers ou de la période exige un nouveau dossier de
sortie ; le service refuse de mélanger deux plans.

Dossier : `artifacts/research/alpaca_options_history/backfill-20240120-20261009-v1`.
`progress.json` donne statut, tranche courante, nombre terminé/en erreur/vide,
lignes reçues/persistées et barres manquantes. Les détails sont dans `tasks/`.
`report.json` est produit à la fin. Les logs du lancement complet sont
`stdout.log` et `stderr.log`. Après la reprise du 10 octobre pour appliquer le
seuil de 1000, les nouveaux logs sont `stdout-resume-1000.log` et
`stderr-resume-1000.log` ; les anciens restent conservés. Le disque et la base grandiront : le processus
télécharge une surface ATM limitée, pas l'intégralité de tous les strikes.
Le PC doit rester allumé pour avancer ; les tranches validées survivent à un arrêt.

Lancement initial borné vérifié, puis lancement complet en arrière-plan. Ne pas
confondre « lancé » avec « terminé » ; seule la progression et le rapport final
attestent la couverture réellement obtenue.
