# Sprint 4 — Calendrier et PIT multi-marchés

> Statut : **GO** — 20 septembre 2026  
> Migration : `0086_market_calendar_pit` appliquée sur `alpha_trade`  
> Portée : infrastructure temporelle US/CN ; aucune donnée instrument CN chargée.

## Résultat

Le calendrier n’est plus une constante NYSE implicite. Tout nouveau traitement reçoit un `MarketContext` et utilise le même contrat pour obtenir les séances, les bornes UTC, avancer de N séances, représenter les segments de cotation et calculer le cutoff PIT d’un dataset.

Les chemins US existants restent compatibles via `nyse_session_dates`, `get_nyse_session_bounds`, `next_trading_day`, `is_trading_day` et `getLastDateMarche`.

```text
MarketContext (market_code, timezone, calendar_id)
              |
              v
       get_market_calendar(context)
              |
       +------+------------------+
       |                         |
       v                         v
market_sessions             bibliothèque validée
priorité 1                  NYSE / XSHG, priorité 2
       |                         |
       +------------+------------+
                    v
           MarketSession timezone-aware
       date / open UTC / close UTC / segments
                    |
          +---------+----------+
          |                    |
          v                    v
   advance_sessions      dataset_cutoff
   Hn = n séances        règle PIT par dataset
```

Le fallback lundi–vendredi reste limité à l’US historique. Pour `CN_A` et `CN_BJ`, l’absence de table canonique et de bibliothèque validée lève `MarketCalendarUnavailableError`.

## API et sémantique

```python
calendar = get_market_calendar(context, engine=engine)
dates = calendar.session_dates(start, end)
opening, closing = calendar.session_bounds(day)
j20 = calendar.next_session(signal_day, 20)
previous = calendar.previous_session(day, 1)
target = calendar.advance_sessions(day, count)
available_at = dataset_cutoff(context, "daily_bars", day, engine=engine)
```

- `next_session(J, 1)` est la première séance strictement après J ;
- `previous_session(J, 1)` est la première séance strictement avant J ;
- `advance_sessions(J, 20)` est identique à `next_session(J, 20)` ;
- `advance_sessions(J, 0)` exige que J soit une séance ;
- H20 signifie 20 séances réelles, jamais 20 jours calendaires ou weekdays.

## Sources

### Table canonique

Quand `market_sessions` couvre tout l’intervalle demandé, elle est prioritaire. Une date absente à l’intérieur de la couverture est fermée. Les lignes ouvertes portent `market_code`, date, statut, bornes UTC, `session_segments_json`, source et timestamps PIT.

Chargement idempotent :

```powershell
python -m service.market_calendar_sync --market-code US_EQ --start-date 2010-01-01 --end-date 2035-12-31
```

`--dry-run` est disponible. Ne pas charger de données canoniques CN avant le gate Sprint 5.

### Bibliothèque validée

- `US_EQ / NYSE` : calendrier NYSE ;
- `CN_A` : jours XSHG ;
- `CN_BJ` : jours fériés nationaux XSHG provisoires, identité `CN_BJ` préservée. Les exceptions BSE devront être inscrites dans `market_sessions` avant exploitation.

Après le sprint, US 2010–2035 contient **6 534 séances**. Aucun calendrier/instrument CN n’a été persisté. Hash table/bibliothèque sur 2016–2026 :

```text
8f5d1bf4fb6b0ae54f41aaa18279064e0d72699cb228e232a166bf1e111d2824
```

## Segments chinois

```text
morning    09:30 → 11:30 Asia/Shanghai
pause      11:30 → 13:00
afternoon  13:00 → 15:00 Asia/Shanghai
```

Sans DST chinois, cela donne 01:30–03:30 puis 05:00–07:00 UTC. Les objets et valeurs persistées sont timezone-aware.

## Contrat PIT

Les politiques versionnées sont dans `config/markets/dataset_cutoffs.yaml` :

| Dataset | Ancre | Délai | Marchés |
|---|---|---:|---|
| `daily_bars` | clôture | 15 min | US_EQ, CN_A, CN_BJ |
| `opening_window` | ouverture | 30 min | US_EQ, CN_A, CN_BJ |
| `official_close` | clôture | 0 min | US_EQ, CN_A, CN_BJ |

Le cutoff dépend de la vraie séance : `daily_bars` US vaut 21:15 UTC en hiver et 20:15 UTC en été.

`DataAvailabilityInfo` porte facultativement `market_code`, `dataset` et `publication_policy`. Les états `suspended` et `closed` complètent `not_yet_available`. `make_market_availability_from_bar_date` exige un contexte explicite. Le helper historique à 21:00 UTC reste disponible pour le legacy mais ne doit pas servir un nouveau flux multi-marché.

La règle reste : `available_at <= decision_cutoff`. Un événement publié après la décision est rejeté.

## Migration et code

- `alembic/versions/0086_market_calendar_pit.py` ;
- `database/sql/migration_0086_market_calendar_pit.sql` ;
- `database/sql/market/market_sessions.sql` ;
- `common/market_calendar.py` ;
- `common/data_availability.py` ;
- `database/repositories/market_sessions.py` ;
- `service/market_calendar_sync.py` ;
- `config/markets/dataset_cutoffs.yaml` ;
- `tests/test_market_calendar_multi_market.py`.

La migration ajoute `session_segments_json`. Son downgrade retire uniquement cette colonne.

## Gate et preuves

Les tests couvrent : hash US inchangé, DST, timezone Shanghai, jours fériés distincts, deux segments CN, H20 exact, cutoff réel, identité marché/dataset PIT, erreur si calendrier CN absent, priorité DB, upsert idempotent et wrappers NYSE.

Limites assumées : les modules Oracle/backtest actuels restent US et peuvent employer les wrappers. Tout chemin CN devra employer l’API générique. Une politique événementielle conserve le véritable `available_at` fournisseur. Le Sprint 5 propagera `instrument_id` dans les faits US avant toute ingestion canonique CN.