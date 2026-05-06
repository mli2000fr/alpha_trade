# Preset micro-compte (~2 000 €) — analyse & justification

> **Sprint S26** — adaptation du paramétrage swing trade pour un capital initial
> de l'ordre de **2 000 € (≈ 2 150 USD)**, profil débutant.

## 1. Contexte

L'utilisateur démarre avec ~2 000 €. Avant cette livraison, le preset le plus
bas disponible était `capital_0_5000` (0 → 5 000 USD). Ses valeurs ont été
calibrées pour un compte « petit mais déjà investissable » (~5 000 $) ; à 2 000 €
plusieurs paramètres rendent le pipeline trop restrictif ou trop coûteux :

| Paramètre `capital_0_5000` actuel | Valeur | Effet sur 2 000 € | Verdict |
|---|---|---|---|
| `risk_min_position_notional` | 150 USD | 7 % du capital par ticket | Borderline OK |
| `risk_max_positions` | 4 | 500 USD/ligne | Trop dispersé pour frais fixes |
| `risk_per_trade_pct` | 0.02 (2 %) | 40 € risqués max | OK |
| `screener_liquidity_threshold_usd` | 5 000 000 | Filtre des micro-cap pourtant accessibles | Trop strict |
| `selector_min_market_cap` | 1 000 000 000 | Exclut tout < 1 Md$ | Trop strict |
| `selector_min_close` | 5 USD | Penny stocks bord de zone | OK borderline |
| `selector_max_spread_bps` | 60 | Spreads micro-cap typiques 60-100 bps | Trop strict |
| `selector_min_high_52w_proximity` | 0.65 | Univers réduit en fin de cycle | Strict |
| Frais backtest CLI (`--commission-bps 5 --slippage-bps 5`) | 10 bps round-trip | Réalité broker fixed-fee : **40-60 bps** sur 200 USD | **Trop optimiste** |

**Conclusion** : un nouveau preset spécifique est nécessaire pour ne pas
fausser les décisions sur micro-compte.

## 2. Preset livré : `capital_0_2000_eur`

Plage : `0 ≤ equity ≤ 2 000 USD`. Le preset existant `capital_0_5000` voit son
plancher déplacé à `2 000.01 USD` (relabel `2 001 → 5 000 $`). Le fingerprint du
preset historique reste **inchangé** car il dépend uniquement de `(key, values)`
et non de la borne `min_equity` (cf. `common/capital_presets.py::capital_preset_fingerprint`).

### 2.1 Choix de paramètres

| Paramètre | Valeur retenue | Justification |
|---|---|---|
| `risk_per_trade_pct` | **0.015** | 1.5 % ≈ 30 € risqués / trade (psychologie débutant : pertes < 30 € par trade tolérables). |
| `risk_max_positions` | **3** | Concentration assumée. 3 lignes × ~600 € = couvre les frais fixes broker. |
| `risk_max_position_weight` | **0.35** | Cohérent avec 3 lignes (1/3 ≈ 0.33). |
| `risk_max_sector_weight` | **0.55** | Permet 2 lignes dans le même secteur (sinon univers vide). |
| `risk_min_position_notional` | **200 USD** | En dessous, frais fixes (≈ 1 USD aller-retour) > 0.5 % alpha attendu. |
| `risk_max_drawdown_pct` | **0.07** | Capital limité ⇒ tolérance DD réduite. Doit rester strictement inférieur aux tranches supérieures (test `test_thresholds_increase_with_account_size`). |
| `risk_max_daily_loss_pct` | **0.025** | Circuit breaker journalier : ~50 € de perte max / jour. Strict mais cohérent avec un micro-compte. |
| `screener_liquidity_threshold_usd` | **2 M USD** | Vs 5 M ⇒ univers ~+30 %. À 200 USD/ticket l'impact marché reste < 5 bps. |
| `selector_liquidity_threshold` | **5 M USD** | idem (couche selector). |
| `selector_min_market_cap` | **500 M USD** | Mid-cap accessibles. Filtre conservé pour exclure micro-cap < 500 M (manipulation, news risk). |
| `selector_min_close` | **10 USD** | Limite l'impact des frais fixes (sur 5 USD un ordre de 200 USD = 40 actions ; sur 10 USD = 20 actions). |
| `selector_min_relative_strength_index` | **90** | Vs 95 ⇒ univers élargi (encore haut décile). |
| `selector_min_high_52w_proximity` | **0.55** | Détendu : sinon univers vide hors euphorie. |
| `selector_min_weekly_trend_score` | **0.65** | Détendu cohérent ci-dessus. |
| `selector_max_atr_pct_20` | **0.09** | Tolère un peu plus de volatilité (mid-cap). |
| `selector_max_spread_bps` | **80** | Vs 60 ⇒ accepte spreads micro-cap typiques. |
| `selector_max_anomaly_count` | **28** | Vs 25 (plus permissif). |
| `selector_selection_size` | **15** | Pas besoin de >15 candidats pour 3 positions actives. |
| `execution_account_type` | **cash** | Compte cash obligatoire < 25 000 USD pour échapper au PDT (Pattern Day Trader rule). |
| `execution_swing_only` | **true** | Aucun day-trade autorisé. |
| `execution_pdt_rule` | **off** | Activable côté broker, ici neutralisé car cash + swing only. |
| `risk_enable_kelly` | **false** | Kelly inadapté à micro-échantillon (variance élevée). |

### 2.2 Frais de backtesting recommandés

⚠️ Les valeurs par défaut du CLI `backtesting run` sont **trop optimistes** pour un micro-compte :

```
--commission-bps 5      (0.05 % = 0.10 USD aller-retour sur 200 USD)
--slippage-bps   5      (0.05 %)
```

**Recommandation pour 2 000 € avec broker à frais fixes (≈ 1 USD/ordre)** :

```powershell
python -m backtesting run `
  --capital-preset-key capital_0_2000_eur `
  --equity 2150 `
  --commission-bps 25 `
  --slippage-bps   15 `
  --start 2022-01-01 `
  --end   2026-04-30
```

> Le coût de friction round-trip total ainsi simulé est de **~80 bps** (proche
> de la réalité Alpaca / IBKR sur ordres < 500 USD).

### 2.3 Limitations connues

1. **Le runtime ne connaît pas l'EUR.** Le champ `equity` est en USD partout.
   L'utilisateur doit convertir manuellement (ex. : 2 000 € → 2 150 USD au cours
   du jour). Aucune conversion automatique n'est faite.
2. **PDT rule** (FINRA) : tant que `execution_account_type=cash` et
   `execution_swing_only=true`, le risque PDT est nul. Ne **jamais** passer en
   `margin` tant que l'equity n'atteint pas 25 000 USD.
3. **Univers réduit** : malgré le relâchement, attendez-vous à ~50-150
   candidats/jour seulement, contre ~300 sur le preset standard.
4. **Frais du broker** : le moteur ne modélise pas les frais **fixes** (ex.
   1 USD/ordre IBKR Tiered, 0 USD Alpaca). Pour une simulation fidèle :
   ajuster le `--commission-bps` comme indiqué ci-dessus.

### 2.4 Comment l'activer dans l'IHM

Page **Pipeline** (et **Backtesting**) → bandeau « Capital » :
- soit saisir `equity = 2150 USD` ⇒ le preset est résolu automatiquement,
- soit forcer la clé `capital_0_2000_eur` dans le sélecteur.

Le bandeau affiche alors le label « 0 → 2 000 € (micro-compte) » et toutes les
valeurs ci-dessus sont appliquées en cascade aux pages Risk, Selector,
Screener et Execution.

## 3. Tests recommandés à exécuter avant utilisation réelle

```powershell
# 1. Lancement pipeline en mode "data only" (pas d'execution live)
python run.py
# Pipeline → cocher "simulate" → Lancer le workflow complet

# 2. Backtest sur 3 dernières années
python -m backtesting run --capital-preset-key capital_0_2000_eur --equity 2150 `
  --commission-bps 25 --slippage-bps 15 --start 2022-01-01 --end 2026-04-30

# 3. Vérifier que le rapport affiche un nombre de trades > 30
#    (sinon univers trop restrictif → relâcher selector_min_high_52w_proximity).
```

## 4. Roadmap d'amélioration possible

- [ ] Ajouter un champ `currency` à `CapitalPreset` (USD/EUR) + conversion FX.
- [ ] Modéliser les frais fixes broker dans `execution_engine.config`.
- [ ] Exposer dans l'IHM Backtesting un toggle « Frais réalistes micro-compte »
      qui force `--commission-bps 25 --slippage-bps 15`.
- [ ] Garde-fou IHM : interdire `execution_account_type=margin` quand le
      preset résolu est `capital_0_2000_eur` ou `capital_0_5000`.


