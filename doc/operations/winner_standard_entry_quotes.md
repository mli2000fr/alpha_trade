# Cotations avant entrée standard Winner

Les cotations SIP donnent les prix acheteur/vendeur consolidés et leurs
horodatages. Elles permettent de vérifier le spread, la fraîcheur et le prix
avant achat. Leur lecture est distincte de l'appel broker qui transmet l'ordre.

Depuis le 31 octobre, une **entrée avec confirmation** peut utiliser le mode
SIP retardé explicite (`market_data_delay_seconds: 900`), avec ordre IOC
plafonné et sizing à ce plafond, sans prétendre disposer d'une quote actuelle.
Ce contrat est distinct de l'entrée standard zéro confirmation décrite ici.
Voir [raccordement et limites](winner_backtest_live_20261031.md).

## Réglage dans config.yaml

```yaml
winner_pyramiding:
  enabled: true
  confirmation_bars: 0
  standard_entry_quote_check_enabled: true
```

- `true`, valeur par défaut conservée : cotation consolidée récente et spread
  qualifié requis avant soumission de l'entrée standard. Le fournisseur reste
  `market_data.quotes_provider_live` (Alpaca SIP ou Tradier).
- `false` : pour une **nouvelle campagne LONG standard**, le risque revalide
  le budget avec le maximum du prix approuvé à l'étape 11 et de la dernière
  clôture qualifiée, ainsi que le plafond d'achat. L'entrée est obligatoirement
  un ordre **limite DAY**, même si le type initialement demandé était marché.
  Aucun bid/ask, spread ou horodatage temps réel n'est inventé. L'ordre peut être envoyé dans
  la fenêtre autorisée avant ouverture ; cela ne signifie pas qu'il est rempli.

Le paramètre est partagé par l'étape 12 manuelle, us_pipeline et le watcher.
La valeur par défaut du code est `true`. Lors de la vérification finale du
28 octobre, le fichier de travail avait été passé entre-temps à `false` ;
cette modification a été conservée.
Il est figé dans la campagne. Les anciennes campagnes qui ne contiennent pas
ce champ restent soumises au contrôle. Une configuration actuelle plus stricte
peut toujours rétablir le contrôle, sans élargir une ancienne admission.

## Périmètre et limites

Ce réglage ne désactive pas les cotations pour les cassures avec confirmation
5m, les renforcements, les entrées hors Winner ou les rééquilibrages. Il ne
modifie pas les SL, TP, échéances, sorties ou verrous anti-doublons. Capital
broker, drawdown, régime, univers, données daily, secteurs, corrélations,
corporate actions et plafonds de risque restent revalidés.

Lorsque `max_entry_gap_pct > 0`, le plafond est la référence approuvée
multipliée par `1 + max_entry_gap_pct`, arrondie vers le bas au tick. C'est
une borne supérieure d'achat, pas une mesure du gap actuel ni un contrôle
symétrique à la baisse. Si le gap est nul, le buffer limite figé dans le plan
détermine le plafond. Une limite initialement plus stricte n'est jamais élargie.
L'ordre peut rester inexécuté et expirer en fin de séance. Le risque réserve
au moins le coût au plafond, ne peut augmenter la quantité approuvée et
reste contrôlé au moment de l'envoi. Les protections se fondent sur le fill réel.

Le préchargement commun des spreads de l'exécuteur est conservé pour les
autres flux. Il peut donc encore produire un avertissement 403 ; cet échec
de lecture ne devient pas un prix qualifié et n'est pas utilisé comme veto
pour une campagne standard explicitement admise sans quote. La suppression
globale de cette collecte pour toutes les cibles LONG a été refusée à l'examen
automatique ; elle n'a pas été appliquée. La collecte commune préserve ainsi
les preuves utilisées par les autres chemins d'exécution.

Le réglage ne donne aucun droit fournisseur supplémentaire. Le trailing
et les confirmations qui utilisent les bougies SIP 5m récentes conservent
leur dépendance aux données intraday. Les stops déjà posés chez le broker
restent indépendants de l'absence de quote.

Depuis la désactivation explicite du trailing de P/OKTA le 28 octobre, leurs
positions ne demandent plus de bougies 5m ni de quotes lorsque trailing et
renforcement sont tous deux désactivés. Les SL/TP, réconciliations et échéances
continuent : voir [le suivi sans intraday inutile](winner_trailing_disabled.md).

Une modification du code Winner demande un redémarrage du watcher. Modifier
le YAML seul ne réécrit ni les plans existants ni la tentative verrouillée
`opt-917380c30aab40cbb99362b3ead15e7c`.
Cette tentative a ensuite été libérée séparément sur demande explicite,
après contrôle de zéro effet : voir [le bilan de reprise](execution_watcher_obsolete_20261028.md).

## Traçabilité et vérification

Le bilan inclut `standard_entry_quote_check_enabled`. L'approbation native
stockée avec l'opération enregistre `price_basis=bounded_standard_limit`,
la date de référence et `realtime_sip_qualified=false` pour le cas sans quote.
Les scénarios hors ligne couvrent soumission DAY, référence non qualifiée,
budget insuffisant, régime et concentration, héritage des anciens plans,
resserrement de configuration et maintien des contrôles intraday.

Validation : 308 tests ciblés passent. Le watcher PAPER a été rechargé avec
les paramètres de service précédents et reconnu `READY`, sans lancement
d'achat. Journaux de ce redémarrage :
`artifacts/operations/watcher_optional_quotes_20261028/watcher-9aead679/`.

Voir aussi [le contrôle distinct de l'étape 11](controle_spread_etape11.md).

## Adaptation autorisée : limites sans cotation

Après clarification des différences marché/limite, l'utilisateur a autorisé :
« ok, go si cotation désactivé ». Le mode sans quote enregistre désormais
`price_basis=bounded_standard_limit`, `order_type=limit`, le plafond exact et
`realtime_gap_checked=false` dans l'approbation durable. Le runtime réserve
le budget à ce plafond ; la réservation et le pont broker refusent un autre
type d'ordre ou un prix supérieur. Le mode coté garde ses termes antérieurs.

Cette règle s'applique aussi aux plans P et OKTA déjà PENDING, figés avec
quote désactivée et gap de 3 %, sans réécrire leurs termes, leurs identifiants
ou leurs compteurs. Plafonds calculés : P 142,89 $, OKTA 232,85 $, au plus
une action chacun sous réserve d'une revalidation positive du risque.

La prévalidation a également corrigé un défaut du collecteur Winner :
`load_risk_config(equity=...)` choisit le preset mais n'actualise pas à lui seul
`account_equity`. Le collecteur transmet maintenant le capital broker en
override explicite ; le contrôle d'égalité est maintenu.

La prévalidation finale des plans conserve un refus indépendant : le modèle
factoriel est activé, mais les colonnes `beta_126`, `market_cap`, `trend_score`
chargées au 27 octobre pour P/OKTA sont toutes nulles et le collecteur ne
qualifie pas leurs expositions. Ce contrôle n'est pas désactivé et aucun
ordre n'a été envoyé lors de ces prévalidations. Les captures immuables
figurent dans `artifacts/operations/winner_no_quote_limit_20261028/`.

### Suite : alimentation factorielle réparée le 28 octobre

Le blocage technique décrit ci-dessus est corrigé : publication dédiée hors
filtre du scanner et contexte factoriel qualifié partagé entre l'étape 11 et
le watcher. P et OKTA restent refusés par les limites réelles conservées
(bêtas 3,02 et 1,80 pour un plafond de 1,20 ; diversification insuffisante pour
OKTA). Le watcher rechargé confirme zéro achat. Voir
[l'alimentation et les preuves](risk_factor_inputs.md).

### Adaptation suivante : budget bêta du compte

Sur demande de l'utilisateur, le calcul actif est ensuite passé à
`beta_exposure_basis: account_equity`, avec le plafond 1,20 conservé.
P passe désormais le bêta, OKTA reste refusé pour diversification. Le premier
cycle a révélé un incident OMS distinct avant soumission de P (identifiant
de 39 caractères pour une colonne limitée à 32) ; aucun achat n'a été envoyé.
Voir [le contrat et l'état vérifié](risk_beta_budget.md).

L'incident OMS a ensuite été corrigé, sans élargir les colonnes SQL et sans
changer l'identifiant courtier. L'historique de l'échec est conservé et une
reprise unique de P a été auditée : voir
[les identifiants Winner et la reprise](winner_request_ids.md).
