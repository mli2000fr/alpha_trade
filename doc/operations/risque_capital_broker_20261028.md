# Étape 11 — capital du compte broker, 28 octobre 2026

## Incident

Le calcul `3db6b005e2f144ee`, séance du 27 octobre, utilisait 100 000 $ faute
de snapshot SQL du compte. Le parcours LLM relisait déjà le broker, mais le
filtre options et le parcours standard conservaient le repli CLI. Ce calcul
a publié zéro cible, les neuf entrées étant refusées pour cotation SIP absente.

## Comportement corrigé

- En **PAPER/LIVE**, lire le compte Alpaca sélectionné au moment du risque :
  equity, cash, buying power, positions et ordres ouverts. Le mode doit
  correspondre à celui du compte configuré ; `default` est explicite.
- Les lectures sont uniquement des GET. Le client utilise une session HTTPS
  vérifiée avec les certificats système, sans désactivation TLS.
- Une API indisponible, un compte bloqué, une equity invalide ou une liste
  d'ordres potentiellement tronquée bloque le calcul, avant toute nouvelle cible.
- Le CLI `--account-equity` et l'ancien snapshot SQL ne fournissent plus le
  capital courant en PAPER/LIVE. L'historique reste utilisé pour préserver
  le high-watermark du même compte, sans le remettre à zéro.
- La capacité n'est pas inventée : un buying power de zéro reste zéro. Les
  positions et ordres ouverts consomment la capacité du snapshot opérationnel.
- Le montant configuré reste utilisable en recherche **`--run-mode shadow`**,
  qui force le dry-run et ne publie pas de cibles d'exécution.

Le générateur de commande Pipeline transmet désormais le mode risque : PAPER
pour un planning PAPER ou une exécution simulée, LIVE pour LIVE, SHADOW pour
un dry-run risque explicite. Ainsi, la simulation de l'envoi des ordres n'est
pas confondue avec l'invention d'un capital de compte. Le champ IHM devient
**Capital de recherche pour le risque (shadow)**, désactivé hors dry-run.

## Horloges et audit

L'horodatage de capture est conservé en UTC, sans être antidaté à la séance du
signal. Une capture récente peut financer le signal de la clôture précédente
avant l'ouverture suivante ; un snapshot vieux de plus de cinq minutes, futur
ou utilisé hors de cette fenêtre est refusé. Les snapshots de replay gardent
leurs contrôles de date habituels. Le contrat LLM existant reste distinct.

Dans le résumé du risque :

- `effective_equity` et `account_equity` : capital effectivement utilisé ;
- `requested_account_equity` : ancienne valeur CLI, conservée pour audit ;
- `equity_source` : `broker:paper:risk`, `broker:live:risk` ou source LLM dédiée ;
- `equity_captured_at` : instant réel de capture ;
- `equity_fallback_used=false` pour une capture broker valide.

Le preset d'univers archivé par le filtre options reste celui de cette analyse.
Il ne remplace pas le capital utilisé pour dimensionner les positions.

## Validation

- **274 tests passent** : capital broker, CLI, snapshots, portefeuille, options,
  commandes Pipeline et batch US.
- Lecture réelle du compte principal `default` PAPER le 28 octobre à
  **00:50:49 UTC / 01:50:49 Paris** : equity **1 974,30 $**, cash **1 974,30 $**,
  buying power **1 974,30 $**, zéro position et zéro ordre ouvert.
- Aucun ordre envoyé et aucun ancien résultat de risque remplacé.

Le refus **HTTP 403 du SIP temps réel** est indépendant. Le contrôle bid/ask de
l'étape 11 est désormais configurable et désactivé par défaut, à la demande de
l'utilisateur : voir [le réglage dédié](controle_spread_etape11.md). Les autres
contrôles de liquidité et les contrôles distincts d'exécution restent actifs.
Le prochain calcul doit créer son propre bilan ; les
archives déjà publiées ne sont pas réécrites et leurs verrous ne sont pas supprimés.
