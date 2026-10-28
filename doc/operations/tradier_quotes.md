# Tradier — cotations consolidées US, raccordement du 28 octobre 2026

## État

Le connecteur est livré pour les **cotations bid/ask uniquement**. Aucun compte
Tradier n'est ouvert par l'application et aucun ordre Tradier n'est implémenté.
Les ordres, positions, capital et borrow restent chez Alpaca.

Aucun jeton Tradier n'a été trouvé dans l'environnement processus/utilisateur/
machine lors de la préparation. Le fournisseur actif reste donc **Alpaca**,
et `risk_management.quote_spread_check_enabled` reste `false`, comme demandé.
La connexion réelle et les droits Tradier sont **à valider**, sans prétendre
qu'un test HTTP simulé démontre l'accès du compte.
Le diagnostic local `service.tradier.probe` a confirmé `UNAVAILABLE` en
l'absence du jeton ; aucune requête réseau fournisseur n'a été envoyée.

## Compte, données et frais

[Tradier Lite](https://tradier.com/pricing) est affiché à **0 USD/mois**, API
incluse. Les [données US](https://docs.tradier.com/docs/market-data) sont
consolidées et temps réel pour les titulaires d'un compte Brokerage actif.
Le sandbox est différé de 15 minutes : ses cotations ne qualifient pas les
nouvelles entrées, même lorsque l'ordre final est en PAPER Alpaca.

Cela ne signifie pas compte sans frais : le barème consulté indique
**50 USD/an pour moins de deux trades par an**, et un accès en ligne limité
pour les comptes non alimentés après 60 jours. Pour un usage de données
uniquement depuis la France, confirmer les conditions du compte auprès de
Tradier avant ouverture. Les anciens PDF internationaux peuvent contenir
d'autres frais et ne sont pas une garantie du tarif courant.

## Configuration et qualification préalable

1. Disposer d'un compte Brokerage accepté, actif et d'un jeton de **production**.
2. Enregistrer le jeton dans `TRADIER_API_TOKEN`, jamais dans le dépôt ou le chat.
   Redémarrer les processus qui doivent hériter de cette variable.
3. Vérifier quelques symboles en lecture seule :

   ```powershell
   .venv\Scripts\python.exe -m service.tradier.probe --symbols AAPL,MSFT
   ```

   Ce diagnostic n'écrit pas en SQL, ne change pas le fournisseur et ne passe
   aucun ordre. Hors marché, une quote peut être accessible mais périmée :
   `available=true` et `fresh=false` sont alors distincts. Les droits réellement
   exploitables avant achat se vérifient sur des cotations fraîches.

4. Après validation, modifier dans `config.yaml` :

   ```yaml
   market_data:
     quotes_provider_live: tradier  # alpaca reste disponible ; aucun basculement implicite
     quotes_provider_live_second: null
     tradier:
       environment: production
       token_env: TRADIER_API_TOKEN
       batch_size: 100
   risk_management:
     quote_spread_check_enabled: true  # facultatif : réactive le contrôle à l'étape 11
   ```

Le contrôle étape 11 peut rester désactivé. Les contrôles distincts de
pré-soumission et de watcher restent actifs et utilisent le fournisseur choisi.
Ils bloquent si les cotations requises sont absentes, refusées ou périmées.

## Parcours raccordés

- Risque étape 11 : fournisseur configuré si le contrôle spread est activé.
- Étape 12 : chargement des spreads pré-soumission et dernier contrôle du
  `BrokerAdapter` avant une nouvelle entrée LONG ou SHORT.
- Watcher Winner : bid/ask, tailles et horodatage provenant du fournisseur choisi ;
  source conservée séparément du flux des bougies.
- Prix de secours des protections : quote configurée, sans empêcher l'usage
  préexistant du prix de position fourni par le broker.
- Collecte de quotes en mode `latest` : Tradier disponible via le même réglage.
  Source `tradier`, flux `consolidated`, sans fausse qualification historique SIP.
- Historique de clôture, barres daily et intraday : **inchangés**. Le backfill
  des quotes historiques reste Alpaca SIP et son contrat de preuve reste strict.

**Limite Winner importante :** les confirmations sur bougies de cinq minutes
continuent d'utiliser Alpaca SIP. Une quote Tradier n'accorde pas les droits
aux bougies SIP récentes ; ce raccordement ne résout donc pas un éventuel 403
sur ces bougies et ne garantit pas à lui seul le fonctionnement gratuit de
la confirmation intraday.

## Contrat du connecteur

`service.tradier.quotes` appelle uniquement
**GET `https://api.tradier.com/v1/markets/quotes`**. Le jeton est envoyé en
en-tête Bearer, jamais en URL ; les redirections HTTP ne sont pas suivies.
TLS vérifié, sessions fermées lorsqu'elles appartiennent au connecteur.

- Réponse objet ou liste normalisée ; symboles inattendus ou dupliqués refusés.
- Conversion des classes d'actions (`BRK.B` → `BRK/B`) conservant le symbole
  interne ; alias ambigus refusés.
- Stocks/ETF USD uniquement ; quotes manquantes ou invalides omises, sans
  prix inventé. Bid/ask croisés, verrouillés, non finis ou tailles nulles refusés.
- `bid_date` et `ask_date` sont conservés. La date représentative est la plus
  ancienne des deux ; jamais la date du dernier trade ni celle de la requête.
  Chaque côté est contrôlé pour fraîcheur et absence de date future.
- Retours de production identifiés `tradier/consolidated`, sans étiquette SIP.
- Trois tentatives au maximum sur erreurs réseau, 429 et 5xx ; 401/403 sans
  retry. Le HTTP 400 **Quota Violation** seul reçoit les reprises bornées du
  helper HTTP partagé ; les autres 400 restent terminaux.
- Aucun fallback Alpaca/IEX/Yahoo après un refus Tradier dans le parcours
  risque/exécution/watcher. Une réponse partielle ne qualifie que les symboles
  effectivement disponibles.

## Validation

Les tests utilisent des réponses simulées, sans compte ni ordre réel. Ils
couvrent les identités, les lots, les dates des deux côtés, les tailles,
le sandbox interdit, les reprises bornées, le routage et les refus avant achat.
**326 tests passent** : connecteur Tradier, helper HTTP, politique SIP,
collecte de quotes, risque, capital broker, exécution et watcher Winner.
Trois anciens tests de l'exécuteur isolent désormais explicitement leur
parcours standard de Winner (désactivé dans leur configuration de test) ;
les protections de production n'ont pas été désactivées.
La validation réelle du compte reste en attente du jeton de production.
