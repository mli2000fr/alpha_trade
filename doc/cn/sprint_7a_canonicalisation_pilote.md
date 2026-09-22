# Sprint 7-A — Canonicalisation pilote du marché chinois

## Statut et objectif

**Statut : GO — pilote exécuté et audité le 22 septembre 2026.** Rapport final : `artifacts/cn/sprint7a/sprint7a-20260922055348/report.json`.

Le Sprint 7-A transforme un sous-ensemble contrôlé du staging BaoStock en données canoniques consommables par les futurs moteurs de features, d’entraînement et de backtest CN. Il ne rend pas encore le marché CN actif dans l’IHM et n’autorise ni prédiction de production ni trading réel.

Le pilote porte sur **80 actions A** et **4 indices**. Il sert à démontrer cinq propriétés avant toute généralisation : identité stable des instruments, calendrier correct, barres quotidiennes brutes cohérentes, facteurs d’ajustement séparés et promotion rejouable sans doublon.

## Périmètre du pilote

La sélection des 80 actions est déterministe et ne dépend d’aucun rendement futur :

| Segment | MIC | Préfixes principaux | Nombre |
|---|---|---|---:|
| Shanghai principal | XSHG | 600/601/603/605 | 25 |
| Shenzhen principal | XSHE | 000/001/002/003 | 25 |
| STAR Market | XSHG | 688 | 15 |
| ChiNext | XSHE | 300/301 | 15 |

Dans chaque segment, les symboles actifs de type action sont triés puis échantillonnés à intervalles réguliers. Si un symbole ainsi choisi a été introduit après la date de fin du pilote, il est remplacé dans le même segment par le code éligible le plus récent qui couvre toute la fenêtre historique. Cette règle évite les IPO futures sans déplacer tout l'échantillon et reste parfaitement reproductible.

BaoStock ne tolère pas plusieurs sessions simultanées fiables : des collecteurs parallèles peuvent s'invalider mutuellement avec le code 10001001. Les appels BaoStock de production et de backfill doivent donc rester séquentiels par machine/compte.

Les quatre indices de contrôle sont `sh.000001`, `sz.399001`, `sh.000300` et `sz.399006`. Ils ne comptent pas dans les 80 actions.

Le manifeste est écrit dans `config/univers_cn/sprint7a_pilot_80.txt`, au format `symbole,symbole` sans espace. Son SHA-256 est enregistré avec chaque promotion.

## Flux de données

```text
BaoStock
   │
   ├── stock_basic ───────┐
   ├── trade_cal ─────────┤
   ├── daily ─────────────┤
   ├── index_daily ───────┤
   └── adj_factor ────────┘
                           ▼
              cn_raw_payloads / cn_staging_rows
                           │
                 cutoff + dernière révision
                           │
                           ▼
      markets / instruments / provider symbols / sessions
             / stock_bars_daily / adjustment factors
                           │
                           ▼
              audit Sprint 7-A + rapport immuable
```

La promotion lit uniquement les lignes dont `available_at` est antérieur ou égal au cutoff. Pour une même clé métier, elle conserve la révision ayant le plus récent `available_at`, puis le plus grand `staging_id`. Une correction fournisseur demeure donc PIT et reproductible.

## Contrats canoniques créés

### Marché et instruments

- `markets` contient `CN_A`, désactivé pour le live.
- `instruments` porte l’identité canonique, le MIC, le code local, le type, la devise et les dates de cotation.
- `instrument_provider_symbols` traduit l’identité canonique vers le symbole BaoStock avec une période de validité.
- l’UUID stable dépend du marché, du MIC et de l’identité BaoStock enrichie de la date d’introduction ; un renommage d’affichage ne change pas l’instrument.

### Calendrier

`market_sessions` combine le statut ouvert/fermé BaoStock avec le contrat horaire CN_A versionné :

- 09:30–11:30 Asia/Shanghai ;
- 13:00–15:00 Asia/Shanghai ;
- conversion UTC persistée ;
- aucune séance n’est dérivée des simples présences de barres.

### Prix quotidiens

`stock_bars_daily` utilise la clé `(instrument_id, date)`. Le symbole fournisseur est gardé pour diagnostic, mais n’est pas l’identité primaire.

Les barres sont persistées en convention **raw/non ajustée** :

- `adj_close = close` ;
- `data_adjustment = raw` ;
- OHLC, volume et montant non négatifs ;
- cohérence `high/low/open/close` imposée en base ;
- `daily_return` calculé depuis `close/pre_close` lorsqu’un `pre_close` valide existe ;
- statut de cotation et indicateur ST conservés ;
- hash source persisté ;
- observed_at et available_at canoniques placés à 15:00 Asia/Shanghai (07:00 UTC), instant où la barre quotidienne devient économiquement connaissable ;
- l’heure réelle d’ingestion 2026 reste dans le staging et dans created_at, afin de ne pas confondre disponibilité historique et arrivée locale du backfill.

Une suspension n’est jamais remplacée par une barre synthétique. Si BaoStock ne fournit pas de barre, aucune ligne n’est inventée.

### Facteurs d’ajustement

`instrument_adjustment_factors` est volontairement distinct de `stock_bars_daily`. Cette séparation évite de mélanger prix bruts et séries rétrospectivement ajustées. Un futur lecteur devra demander explicitement une convention et joindre le facteur compatible avec son cutoff PIT. Faute de date d’annonce fiable chez BaoStock, le facteur n’est rendu disponible qu’à sa date d’effet à la clôture : il ne doit jamais être joint avant cette date.

### Statut quotidien

`instrument_status_history` reçoit le statut observé à chaque séance disponible : négociable, suspendu et/ou ST. Ces informations serviront au futur univers PIT ; le Sprint 7-A ne les utilise pas encore pour construire un univers de backtest.

## Rejouabilité et idempotence

Toutes les tables métier ont une clé naturelle ou canonique. Une seconde promotion du même staging met à jour les mêmes lignes ; elle ne multiplie pas les barres, sessions, mappings ou facteurs. `cn_canonicalization_runs` conserve néanmoins chaque exécution et ses compteurs, ce qui distingue l’audit de traitement des données métier.

## Commandes opératoires

Mettre la base CN à niveau :

```powershell
F:\projets\.venv\Scripts\python.exe -m alembic -c alembic_cn.ini upgrade head
```

Exécuter tout le pilote :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint7a_pilot all --start-date 2018-01-01 --end-date 2025-12-31
```

Les étapes peuvent aussi être isolées avec `select`, `collect`, `promote` et `audit`. Cette séparation permet de rejouer une promotion sans rappeler BaoStock, ou de réauditer le canonique après une correction de contrôle.

Les rapports sont écrits dans `artifacts/cn/sprint7a/<run>/report.json`.

## Gates de validation

Le Sprint 7-A est accepté uniquement si :

1. la connexion réelle est `alpha_trade_cn` ;
2. 80 actions et 4 indices possèdent une identité canonique ;
3. aucun doublon `(instrument_id, date)` n’existe ;
4. aucune barre OHLC invalide ou valeur volume/montant négative n’est persistée ;
5. les 80 actions possèdent au moins une barre sur la fenêtre pilote ;
6. les facteurs restent séparés des prix ;
7. un second passage conserve les mêmes nombres de lignes métier ;
8. aucune table US n’est lue ou écrite.

Un statut `PASS_WITH_WARNINGS` autorise seulement des rejets explicitement expliqués dans le rapport. Il ne suffit pas pour ouvrir le Sprint 7-B ou activer CN dans l’IHM ; la cause doit d’abord être acceptée.

## Ce que ce sprint ne fait pas

- pas d’univers PIT de production ;
- pas de features, modèle, prédiction ou backtest CN ;
- pas de remplissage artificiel des suspensions ;
- pas de prix ajusté construit implicitement ;
- pas d’activation de `market_cn.yaml` ;
- pas de mélange avec `alpha_trade` US ;
- pas de dépendance obligatoire à Tushare, AKShare ou RQData.

## Suite prévue

Après un gate vert, le Sprint 7-B généralisera la promotion à l’univers historique retenu, ajoutera les limites journalières et les événements corporate disponibles, puis mesurera la couverture par période. Le Sprint 8 construira ensuite l’univers tradable PIT quotidien ; c’est seulement après lui que les features et expériences ML peuvent commencer.
