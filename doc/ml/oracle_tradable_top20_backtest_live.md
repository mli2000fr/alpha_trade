# Oracle TOP20 sur univers tradable — backtest et live

## Objet

Ce document décrit le contrat d’exécution de la cascade directionnelle dans laquelle :

1. l’Oracle calcule un score d’amplitude sur un univers large ;
2. l’application détermine les titres réellement tradables à la date considérée ;
3. les percentiles Oracle sont recalculés sur ces seuls titres tradables ;
4. le TOP20 est sélectionné ;
5. les modèles directionnels Per-Symbol produisent une décision LONG, SHORT ou abstention ;
6. les candidats retenus passent dans le portefeuille, les contrôles de risque et le moteur d’exécution.

Le même ordre logique est disponible dans le backtest et dans le flux live. Cette fonctionnalité ne transforme pas l’Oracle en modèle directionnel : l’Oracle détecte l’amplitude potentielle, tandis que les branches Per-Symbol déterminent éventuellement le sens.

## Flux de référence

```text
Univers Oracle large P0f
        │
        ▼
Scores d’amplitude Oracle à la date J
        │
        ▼
Univers tradable PIT à la date J
        │
        ▼
Intersection Oracle ∩ tradable
        │
        ▼
Recalcul des percentiles Oracle
sur les titres tradables uniquement
        │
        ▼
TOP20 tradable
        │
        ▼
Disponibilité des branches Per-Symbol servables
        │
        ▼
P(LONG), P(SHORT), marge et quality gate
        │
        ├── LONG
        ├── SHORT
        └── abstention
        │
        ▼
Construction du portefeuille
        │
        ▼
Risque, capacité, exposition et exécution
```

## Pourquoi recalculer le TOP20 après le filtre tradable ?

Le percentile Oracle initial est calculé sur l’univers large. Une partie de cet univers peut être inéligible au trading à la date J : capitalisation insuffisante, données trop anciennes, titre non tradable, absence de barres, prix ou liquidité hors limites, etc.

Filtrer simplement le TOP20 initial peut laisser beaucoup moins de 20 % de candidats et modifier la population sans recalculer le classement. La politique recommandée effectue donc l’intersection avec l’univers tradable avant de recalculer les percentiles.

Exemple simplifié :

```text
1 000 scores Oracle disponibles
→ 600 titres tradables à J
→ percentiles recalculés sur ces 600 titres
→ TOP20 = environ 120 titres avant les autres gates
```

Le TOP20 désigne donc 20 % de la population tradable effectivement observable à J, et non 20 % de l’univers historique brut.

## Politiques disponibles

### `off`

Le filtre tradable Oracle est désactivé. Le comportement historique est conservé.

Cette valeur reste utile pour :

- reproduire d’anciens résultats ;
- comparer le comportement avant et après activation ;
- isoler l’effet du filtre tradable.

Elle ne doit pas être confondue avec une validation de la tradabilité au niveau du portefeuille : des contrôles ultérieurs peuvent toujours exister, mais le percentile Oracle n’est pas recalculé sur l’univers tradable.

### `filter_then_top20`

Politique recommandée :

```text
scores Oracle
→ filtre tradable PIT
→ nouveau percentile
→ TOP20
```

Elle garantit que le seuil TOP20 représente la distribution des titres tradables de la date J.

### `top20_then_filter`

Politique de comparaison :

```text
scores Oracle
→ TOP20 de l’univers large
→ filtre tradable PIT
```

Cette politique ne remplace pas les titres éliminés et ne recalcule pas le percentile. La population finale peut donc être nettement inférieure à 20 % de l’univers tradable.

## Contrat PIT et absence de fuite temporelle

L’univers tradable doit être reconstruit avec les informations disponibles à la date J. Le backtest charge un snapshot canonique par date Oracle et ne doit pas utiliser silencieusement la situation actuelle pour une date historique.

Principes :

- aucune capitalisation future pour filtrer une date passée ;
- aucune substitution d’un snapshot courant à un snapshot historique manquant ;
- aucun `as-of` implicite non documenté ;
- si le snapshot exact requis est absent, le flux doit échouer de manière fermée ou produire zéro candidat pour la date concernée, plutôt que créer une fuite temporelle.

En politique `market_cap.policy: strict`, la qualité de la couverture des fondamentaux
et des capitalisations est un prérequis opérationnel. En politique `liquidity_only`, la
capitalisation est absente du gate et l’univers repose sur les filtres PIT de liquidité,
prix, spread, historique, volatilité, qualité et earnings.

## Backtest

### Paramètres essentiels

```text
--cascade-rank-mode extreme_gate_directional
--oracle-tradable-policy filter_then_top20
--extreme-gate-pct 0.20
--oracle-batch-id <batch_oracle>
```

Exemple minimal :

```powershell
python -m backtesting run --cascade-rank-mode extreme_gate_directional --oracle-tradable-policy filter_then_top20 --extreme-gate-pct 0.20 --oracle-batch-id model-factory-YYYYMMDDHHMMSS-xxxxxx
```

Les autres paramètres du backtest — période, capital, coûts, stops, limites d’exposition, couverture ML et stratégie PIT — restent nécessaires et doivent être définis selon le contrat de l’expérience.

### Reproductibilité

Pour comparer `off` à `filter_then_top20`, conserver strictement identiques :

- le batch Oracle ;
- le batch directionnel ;
- les dates ;
- le capital et le nombre maximal de positions ;
- les coûts ;
- les règles d’entrée et de sortie ;
- les paramètres LONG/SHORT ;
- le quality gate et la marge directionnelle.

Seule la politique de construction du pool Oracle doit changer.

### Valeur par défaut et anciens runs

Le CLI conserve `off` comme comportement compatible avec les anciens appels qui ne fournissent pas l’option. Un nouveau backtest ne doit donc pas être considéré comme utilisant le TOP20 tradable simplement parce qu’il emploie `extreme_gate_directional` : il faut vérifier explicitement `--oracle-tradable-policy filter_then_top20` dans la commande ou dans les paramètres persistés du run.

## Live

> État du dépôt au 9 septembre 2026 : `config.yaml` conserve `live_oracle_tradable_policy: off`. La construction tradable utilise désormais `market_cap.policy: strict` avec `provider: yahoo_then_finnhub`. Le gate Oracle live reste désactivé jusqu’à validation des snapshots PIT et du batch de serving.

### Configuration

Activation recommandée :

```yaml
cascade:
  live_oracle_tradable_policy: filter_then_top20
  live_oracle_batch_id: null
  live_oracle_pool_pct: 0.20
```

Signification :

- `live_oracle_tradable_policy` : ordre de filtrage et de sélection ;
- `live_oracle_batch_id` : batch Oracle imposé. Avec `null`, le batch de serving applicable est résolu par l’application ;
- `live_oracle_pool_pct` : fraction supérieure conservée après recalcul. `0.20` signifie TOP20.

Pour forcer un batch :

```yaml
cascade:
  live_oracle_tradable_policy: filter_then_top20
  live_oracle_batch_id: model-factory-YYYYMMDDHHMMSS-xxxxxx
  live_oracle_pool_pct: 0.20
```

Un batch de recherche, shadow ou canary ne doit pas être promu implicitement. Son identifiant ne doit être placé dans la configuration live qu’après validation et décision explicite de promotion.

### Comportement live

À la date J, le moteur :

1. résout l’univers tradable courant selon les règles configurées ;
2. charge les scores Oracle du batch et de la date attendus ;
3. applique la politique `filter_then_top20` ;
4. calcule le pool TOP20 sur les titres restants ;
5. recherche les prédictions Per-Symbol du même contrat directionnel ;
6. écarte les titres sans branche servable ou sans prédiction exploitable ;
7. transmet les décisions restantes au portefeuille et au risque.

Dans ce nouveau flux live, une prédiction synthétique Oracle ne doit pas remplacer une direction Per-Symbol manquante. L’absence de direction exploitable conduit à l’abstention.

## Disponibilité et servabilité Per-Symbol

Il faut distinguer quatre états :

```text
symbole présent dans l’univers
≠ modèle entraîné
≠ modèle éligible/servable
≠ prédiction disponible à la date J
```

Un symbole ne peut atteindre la décision directionnelle que si les artefacts nécessaires sont réellement servables et si une prédiction compatible est disponible. Pour un bundle à deux branches, les diagnostics doivent distinguer le nombre de symboles entraînés du nombre de paires réellement servables.

Le dénominateur de couverture doit correspondre au pool TOP20 tradable sélectionné, et non à l’univers large initial.

## LONG, SHORT et abstention

Pour chaque candidat Oracle :

- la branche LONG produit `P(LONG)` ;
- la branche SHORT produit `P(SHORT)` ;
- les seuils minimaux, la marge entre les deux côtés et l’éventuel quality gate sont appliqués ;
- les options LONG-only ou SHORT-only peuvent interdire un côté ;
- en cas de confiance insuffisante, de conflit ou d’absence de modèle, le système s’abstient.

L’abstention est une sortie normale du classifieur. Elle ne doit pas être remplacée par une direction arbitraire afin de remplir le portefeuille.

## Contrôles portefeuille et risque

Le TOP20 n’est pas un ordre d’achat ou de vente. Après la décision directionnelle, les candidats restent soumis notamment :

- à la capacité disponible ;
- au nombre maximal de positions ;
- aux limites LONG/SHORT ;
- aux contraintes sectorielles ;
- aux limites d’exposition ;
- aux règles de drawdown et de volatilité cible ;
- aux contrôles de gap, de prix et de liquidité ;
- aux coûts et au lifecycle d’exécution.

Le nombre de positions ouvertes peut donc être inférieur au nombre de décisions directionnelles positives.

## Garde-fous opérationnels avant activation live

Avant de remplacer `off` par `filter_then_top20` en production :

1. vérifier la politique `market_cap.policy` du snapshot ;
2. en mode `strict`, vérifier couverture et fraîcheur des capitalisations ; en
   mode `liquidity_only`, vérifier la couverture des filtres PIT de liquidité ;
3. vérifier la présence des scores Oracle pour la date J ;
4. vérifier que le batch Oracle est promu et non seulement shadow/canary ;
5. vérifier le nombre de branches Per-Symbol servables ;
6. vérifier la couverture des prédictions directionnelles sur le TOP20 tradable ;
7. exécuter un backtest comparable avec `off` puis `filter_then_top20` ;
8. exécuter un shadow live avant toute prise de position réelle ;
9. surveiller les abstentions et les raisons d’exclusion ;
10. conserver un moyen explicite de revenir à `off`.

## Diagnostic d’un pool vide ou trop petit

Ordre de vérification recommandé :

1. scores Oracle présents pour la date et le batch ;
2. snapshot tradable exact présent ;
3. politique de capitalisation conforme au fingerprint ; si elle est `strict`,
   capitalisations disponibles et suffisamment fraîches ;
4. barres et métadonnées `tradable` disponibles ;
5. intersection entre symboles Oracle et symboles tradables non vide ;
6. percentile recalculé et `live_oracle_pool_pct` valide ;
7. branches directionnelles servables ;
8. prédictions Per-Symbol présentes ;
9. seuils de probabilité et marge directionnelle ;
10. filtres portefeuille et risque.

## Matrice de validation minimale

| Cas | Politique | Résultat attendu |
| --- | --- | --- |
| Compatibilité historique | `off` | aucune recomposition du percentile Oracle |
| Politique recommandée | `filter_then_top20` | TOP20 recalculé sur l’univers tradable |
| Politique comparative | `top20_then_filter` | TOP20 large puis suppression des non-tradables |
| Snapshot PIT absent | `filter_then_top20` | échec fermé, aucun fallback courant |
| Modèle Per-Symbol absent | toutes | abstention pour le symbole |
| Confiance insuffisante | toutes | abstention |
| LONG-only actif | toutes | aucune position SHORT |
| SHORT-only actif | toutes | aucune position LONG |

## Localisation dans le code

Les principaux points d’implémentation sont :

- `modelFactory/predictor.py` : préparation des percentiles tradables et sélection cascade ;
- `backtesting/cli/_impl.py` : option backtest et chargement des snapshots tradables PIT ;
- `ihm/pages/backtesting/` : configuration du mode dans l’IHM ;
- `ihm/services/backtesting_runner.py` : génération de la commande backtest ;
- `risk_management/cli.py` : orchestration du flux live ;
- `risk_management/db_io.py` : chargement strict des scores Oracle ;
- `config.yaml` : activation et paramétrage live.

## Résumé décisionnel

La configuration suivante active le comportement voulu en live :

```yaml
cascade:
  live_oracle_tradable_policy: filter_then_top20
  live_oracle_batch_id: null
  live_oracle_pool_pct: 0.20
```

Elle ne constitue cependant pas, à elle seule, une autorisation de mise en production. La couverture des données tradables, la promotion du batch Oracle et la servabilité directionnelle doivent être validées avant activation réelle.
