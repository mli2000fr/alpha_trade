# Capitalisation PIT — SEC EDGAR ou EODHD

## Objectif

Cette architecture empêche une capitalisation actuelle d'être recopiée dans le
passé. Elle sert à exclure les microcaps avant les modèles directionnels et
l'exécution, tout en laissant l'Oracle calculer ses scores sur son univers large.

La source est un choix opérateur explicite dans config.yaml :

    market_cap:
      provider: sec_edgar       # sec_edgar | eodhd
      max_age_days: 365
      missing_policy: reject

Il n'existe aucun fallback automatique entre SEC et EODHD. Le fournisseur, la
formule et le TTL entrent dans le fingerprint de chaque publication d'univers.
La contrainte d'unicité de stock_fundamentals_daily inclut aussi source :
les deux historiques peuvent donc coexister et un changement de switch
n'écrase pas les observations de l'autre fournisseur.

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
