# Capitalisation PIT — Yahoo prioritaire, Finnhub, SEC EDGAR ou EODHD

## Objectif

Cette architecture empêche une capitalisation actuelle d'être recopiée dans le
passé. Elle sert à exclure les microcaps avant les modèles directionnels et
l'exécution, tout en laissant l'Oracle calculer ses scores sur son univers large.

La source est un choix opérateur explicite dans config.yaml :

    market_cap:
      policy: strict
      provider: yahoo_then_finnhub
      max_age_days: 365
      missing_policy: reject

Le mode actif est `strict`. Avant tout contrôle de capitalisation, le publieur
écarte les ETF, ETN, fonds indiciels, fonds obligataires et produits à levier ou
inverses détectés dans les métadonnées instrument. Le mot `Trust` seul n'est jamais
un motif de rejet : les REIT et sociétés organisées en trust restent admissibles.

Avec `yahoo_then_finnhub`, le choix est effectué indépendamment pour chaque symbole
et chaque date J :

1. prendre le dernier snapshot Yahoo positif, disponible au plus tard à J et non périmé ;
2. sinon prendre le dernier snapshot Finnhub positif et non périmé ;
3. sinon rejeter avec `market_cap_unavailable` ou `market_cap_stale`.

Yahoo est prioritaire car les valeurs Finnhub de certains ADR utilisent la
capitalisation de la cotation primaire ou une unité incompatible avec l'ADR. Le TTL,
le provider effectivement configuré et la formule de sélection entrent dans le
fingerprint. Les lignes Yahoo et Finnhub coexistent grâce à l'unicité
`(symbol, trade_date, source)`.

Le mode `liquidity_only` reste disponible comme rollback : il ignore la
capitalisation mais conserve les filtres PIT du screener, le spread et les earnings.

## Mode Yahoo puis Finnhub

Les snapshots actuels se collectent séparément afin de conserver leur provenance :

    python -m modelFactory.fundamental_features --provider yahoo_finance --symbol-source universe-file:univers_filtred.txt
    python -m modelFactory.fundamental_features --provider finnhub --symbol-source universe-file:univers_filtred.txt

`--provider config` choisit Yahoo, le fournisseur primaire de la chaîne. Il ne lance
pas implicitement deux collectes réseau. Le fallback Finnhub du publieur utilise les
lignes Finnhub déjà persistées.

### Automatisation Windows

Le batch `AlphaTrade-MarketCapSync` exécute ces deux collectes les lundis et
jeudis à 11 h et 23 h, heure locale de la machine. Son contrat se trouve sous
`market_cap_sync` dans `batch.yaml`. Le fichier de statut est
`log/batch/market_cap_sync.txt` et le détail Python reste dans
`log/fundamental_features.log`.

Le batch refuse un univers absent, empêche deux exécutions simultanées et considère
comme erreur un fournisseur qui ne produit aucun snapshot. Des échecs symboles
partiels sont signalés comme `WARNING` sans supprimer les snapshots valides. Toute
fin `OK` ou `ERROR` produit une notification email et Telegram best-effort ; les
échecs de notification ne changent jamais le résultat de la collecte.

Installation :

    powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_market_cap_sync_task.ps1

Lancement immédiat :

    powershell -ExecutionPolicy Bypass -File .\scripts\windows\market_cap_sync_launcher.ps1

Rattrapage un jour hors `run_days` (défaut : lundi et jeudi) :

    powershell -ExecutionPolicy Bypass -File .\scripts\windows\market_cap_sync_launcher.ps1 -IgnoreRunDays

Ces snapshots ne sont pas rétroactifs : une ligne collectée aujourd'hui ne peut pas
filtrer une date de backtest antérieure. Les backtests historiques exigent des
snapshots réellement disponibles à chaque date ou une autre source PIT historique.

## Exclusion des instruments collectifs

La même politique de noms est partagée par le screener et le publieur final. Elle
écarte notamment ETF, ETN, fonds, émetteurs de produits indiciels reconnus et notes
structurées/produits explicitement à levier ou inverses. Les actions ordinaires, ADR,
REIT et BDC ne sont pas rejetés par leur seule forme juridique.

Le filtre par nom constitue un garde-fou en attendant un champ provider explicite de
type d'instrument. Tout rejet est conservé dans le snapshot avec un motif
`excluded_*`, donc reste auditable.

Pour les nouveaux entraînements, construire le fichier homogène sans modifier le
fichier historique :

    python -m scripts.build_equity_universe --source config/univers/univers_filtred.txt --output config/univers/univers_filtred_equities.txt

Au 9 septembre 2026, cette opération conserve 1 798 actions et écarte 898 produits
collectifs ou structurés. Le screener et le publieur réappliquent la même politique
comme garde-fou, même si un appelant fournit encore l'ancien fichier large.

## Mode SEC EDGAR, gratuit

### Collecte

service/sec/clientEdgar.py télécharge Company Facts et le mapping ticker/CIK.
La SEC exige un User-Agent identifiable. En exploitation, définir par exemple :

    $env:SEC_EDGAR_USER_AGENT="AlphaTrade/1.0 contact@votre-domaine.fr"

Les réponses Company Facts sont mises en cache 24 heures sous
artifacts/sec_cache/companyfacts/. Le mapping ticker/CIK possède également un
cache de 24 heures. Aucun token API n'est requis.

Commande de smoke test :

    python -m modelFactory.fundamental_features --provider config --symbol-source universe-file:univers_filtred.txt --start-date 2016-01-01 --limit 20

Collecte complète :

    python -m modelFactory.fundamental_features --provider config --symbol-source universe-file:univers_filtred.txt --start-date 2016-01-01

Avec market_cap.provider: sec_edgar, --provider config devient
automatiquement --provider sec. Les faits sont stockés dans
stock_fundamentals_daily avec :

- source = SEC_EDGAR ;
- trade_date = filed, date de dépôt SEC et non fin du trimestre ;
- shares_outstanding, dernier nombre d'actions connu à cette date ;
- fetched_at, date technique de collecte.

### Calcul quotidien

Lors de la publication de l'univers tradable à une date J :

1. rechercher le dernier shares_outstanding SEC dont trade_date est antérieur ou égal à J ;
2. utiliser close_price du snapshot screener exact de J ;
3. calculer market_cap[J] = close_price[J] × shares_outstanding[dernier dépôt] ;
4. refuser la valeur si le dépôt est plus ancien que max_age_days ;
5. appliquer le plancher de capitalisation du preset de capital.

La table fondamentale ne reçoit pas une ligne artificielle pour chaque séance.
Le calcul quotidien est fait à la publication, puis sa valeur est figée dans
tradable_universe_history.market_cap.

### Raisons de rejet

| Code | Signification |
|---|---|
| market_cap_unavailable | cours ou actions SEC absents/non positifs |
| market_cap_stale | dernier dépôt contenant les actions trop ancien |
| market_cap_below_minimum | capitalisation calculée sous le preset |

Toutes ces situations échouent fermées : le symbole ne peut pas être exécuté.

## Retour à EODHD

Changer uniquement :

    market_cap:
      provider: eodhd
      max_age_days: 365
      missing_policy: reject

Le publieur cherche alors la dernière ligne source = EODHD, trade_date
antérieure ou égale à J, avec market_cap positif. Il ne mélange jamais une
valeur SEC et une valeur EODHD au sein d'un même snapshot.

Un override ponctuel est disponible :

    python -m common.publish_tradable_universe --trade-date 2026-07-10 --market-cap-provider eodhd --market-cap-max-age-days 365

Sans override, la CLI et les boutons de publication IHM lisent config.yaml.

## Contrats PIT et limites

- Une ligne publiée après J n'est jamais visible à J.
- Le TTL porte sur la date de publication des actions, pas sur le cours :
  le cours appartient toujours au snapshot quotidien J.
- Les sociétés étrangères, ADR, ETF et certains tags XBRL atypiques peuvent ne
  pas fournir un nombre d'actions exploitable ; elles sont alors refusées.
- Les symboles renommés nécessitent un mapping ticker/CIK valide.
- Les prix et actions doivent partager une convention cohérente lors d'un split.
  stock_bars_daily utilise la convention split du projet.
- stock_metadata.market_cap reste utile à certains écrans et composants
  historiques, mais n'est pas la source de la publication PIT.

## Validation avant promotion

Avant d'utiliser SEC en production :

1. collecter un pilote d'au moins 20 symboles ;
2. comparer close × shares à la capitalisation EODHD/Yahoo du même jour ;
3. inspecter les écarts supérieurs à 10 % et les événements de split ;
4. mesurer couverture, valeurs manquantes et valeurs périmées sur les 2 696
   candidats ;
5. publier une période shadow et comparer les membres admis/rejetés ;
6. ne promouvoir qu'après validation de la couverture live et historique.

La collecte et la publication sont idempotentes. Changer de fournisseur exige
de republier les snapshots concernés, car leurs fingerprints diffèrent.
