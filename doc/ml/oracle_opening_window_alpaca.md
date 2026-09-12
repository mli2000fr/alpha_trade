# Oracle Opening Window — collecte Alpaca SIP PIT

## Finalité

`oracle_opening_window_sync` construit prospectivement un historique minute du
prémarché et du début de séance US. Malgré son nom historique, la collecte
n'est jamais limitée aux candidats d'un Oracle. Elle couvre intégralement
`config/univers_batch/univers_filtred_tradable.txt` afin d'éviter qu'un modèle
ou un TOP20 courant décide des données qui seront disponibles pour les futures
recherches.

Le dataset vise deux usages distincts :

1. entraîner et auditer des signaux de confirmation directionnelle après une
   prévision d'amplitude ;
2. étudier une entrée retardée, lorsque le comportement réel de l'ouverture est
   déjà observable.

Il ne fournit pas une confirmation SIP temps réel à 09:30. Le plan Alpaca
gratuit expose le SIP historique avec retard ; le premier passage attend donc
plus de 15 minutes après la fin de fenêtre.

## Contrat fournisseur

| Élément | Valeur verrouillée |
|---|---|
| Fournisseur | Alpaca Market Data |
| Endpoint | `/v2/stocks/bars` multi-symboles |
| Feed | `sip` consolidé |
| Timeframe | `1Min` |
| Ajustement | `raw` |
| Fenêtre | 04:00–10:30 `America/New_York` |
| Population | univers tradable stable complet |
| Lot | 100 symboles par défaut |
| Pagination | jusqu'à disparition de `next_page_token` |
| Limite | 10 000 barres par page |

Les identifiants proviennent du registre Alpaca déjà utilisé par
l'application. Aucune clé n'est stockée dans `batch.yaml`.

## Calendrier

Le batch est configuré les jours de semaine à :

- 10:50 New York : première photographie, après expiration de la limite SIP
  gratuite sur la barre de 10:30 ;
- 18:15 New York : second passage après clôture pour détecter les corrections.

Le calendrier NYSE empêche une absence totale de données un jour férié d'être
interprétée comme une panne fournisseur. Le fuseau New York suit directement
les changements d'heure US.

## Flux

```text
univers_filtred_tradable.txt
        │
        ├─ lots de 100 symboles
        │
        ▼
Alpaca historical bars — feed=sip — 1Min
        │
        ├─ pagination exhaustive
        ├─ payload RAW horodaté et haché
        └─ normalisation OHLCV / trades / VWAP
                 │
                 ├─ table canonique de lecture
                 │  stock_opening_window_bars
                 │
                 └─ versions append-only
                    stock_opening_window_bar_versions
```

## Mapping des barres

Alpaca retourne des noms compacts :

| Alpaca | Stockage | Sens |
|---|---|---|
| `t` | `bar_timestamp` | début UTC de la minute |
| `o`,`h`,`l`,`c` | `open`,`high`,`low`,`close` | OHLC minute |
| `v` | `minute_volume` | volume de cette minute |
| `n` | `trade_count` | nombre de transactions agrégées |
| `vw` | `vwap` | VWAP de la minute |

`cumulative_volume` est une donnée dérivée : somme de `minute_volume` depuis
04:00 pour le symbole et la séance. Il ne faut pas différencier `v` : l'ancien
connecteur Business Quant fournissait un cumul, mais Alpaca fournit déjà le
volume minute.

`session_name` vaut :

- `PRE` avant 09:30 New York ;
- `OPEN` entre 09:30 et 10:30 inclus.

## Sémantique PIT et corrections

Trois temps doivent rester distincts :

- `bar_timestamp` : minute économique observée sur le marché ;
- `observed_at` : réception effective par Alpha-Trade ;
- `available_at` : première disponibilité autorisée pour une lecture PIT.

Le contrat est volontairement conservateur : `available_at = observed_at`.
Une barre de 09:31 téléchargée à 10:50 n'est donc jamais présentée au modèle
comme connue à 09:46.

La table canonique conserve le plus ancien `observed_at/available_at` et reçoit
la dernière valeur fournisseur. La table de versions ajoute une ligne seulement
si le hash économique de la barre change. Le second passage quotidien ne crée
donc pas un faux doublon, mais une correction réelle reste observable.

## Contrôles de qualité

Le run expose dans `pit_collection_runs.details_json` :

- taille de l'univers ;
- symboles couverts globalement, en prémarché et après 09:30 ;
- ratios de couverture global et OPEN ;
- nombre de pages et de barres ;
- lignes invalides ou hors fenêtre ;
- fenêtre, feed, ajustement et contrat de disponibilité.

Les seuils par défaut sont :

- couverture globale ≥ 75 % ;
- couverture OPEN ≥ 70 %.

Une faible couverture prémarché n'est pas bloquante : l'absence de transactions
avant 09:30 est normale pour de nombreux titres. Une violation des deux seuils
principaux rend cependant le run bloquant afin d'éviter un dataset silencieusement
tronqué.

Les barres sont rejetées si un prix manque, est non positif, ou si `high/low`
est incohérent avec `open/close`. Les volumes négatifs sont ramenés à zéro.

## Features de recherche possibles

Le stockage permet notamment de calculer :

- rendement, plus haut, plus bas et range du prémarché ;
- volume prémarché et volume relatif ;
- gap d'ouverture ;
- rendements et ranges à 5, 15, 30 et 60 minutes ;
- cassures du plus haut/bas prémarché ;
- distance au VWAP et reprise/perte du VWAP ;
- accélération du volume et du nombre de transactions ;
- continuation, retournement et comblement du gap.

Ces variables devront être évaluées OOF et PIT. La disponibilité de cette
collecte ne démontre pas à elle seule qu'elles distinguent D1 et D10.

## Exploitation

Migration :

```powershell
python -m alembic upgrade head
```

Installation de la tâche :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_forward_pit_task.ps1 -BatchName oracle_opening_window_sync
```

Exécution immédiate :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\forward_pit_launcher.ps1 -BatchName oracle_opening_window_sync -Force
```

Le lancement immédiat avant 10:46 New York échoue volontairement : le batch ne
doit pas basculer silencieusement sur IEX ni stocker une fenêtre SIP incomplète.
