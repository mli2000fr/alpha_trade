# Audit du backtest `20260601_191555_282c4792`

## 1. Périmètre et méthode

Analyse réalisée à partir :

- des artefacts du run `F:\projets\artifacts\ihm_backtesting_runs\run\20260601_191555_282c4792\artifacts`
- des sources du projet (référence de vérité), en particulier :
  - `backtesting/report.py`
  - `backtesting/risk_overlay.py`
  - `backtesting/microstructure.py`
  - `backtesting/exit_lifecycle_replay.py`
  - `risk_management/config.py`
  - `risk_management/position_sizer.py`
  - `risk_management/constraints.py`
  - `risk_management/portfolio_builder.py`
  - `risk_management/regime_apply.py`
  - `service/market/regime_manager.py`
  - `service/market/sentiment_regime.py`
  - `execution_engine/config.py`
  - `execution_engine/order_intents.py`
  - `config.yaml`
  - `config/capital_presets.yaml`

Je n’ai pas utilisé `combined.log`/`stdout.log`/`stderr.log` car vous avez précisé qu’ils sont trop volumineux et que `combined.log` duplique déjà les autres.

---

## 2. Résumé exécutif

### Verdict court

Le backtest **gagne en valeur absolue** mais le profil de risque est **beaucoup trop violent** pour être exploitable tel quel :

- capital initial : **2 000 $**
- valeur finale : **4 811.30 $**
- rendement total : **+140.57 %**
- CAGR : **15.80 %**
- **max drawdown : 53.28 %**
- Calmar : **0.297**
- Ulcer Index : **22.99**

En pratique, le système produit une performance positive, mais avec un **profil de douleur incompatible avec un pilotage prudent**, surtout pour un **micro-compte**.

### Conclusion principale

Les grosses baisses ne viennent **pas d’un seul bug**, mais d’une **combinaison structurelle** :

1. **Sélection dégradée** : le run fonctionne presque sans ML.
2. **Exposition trop concentrée** pour un capital de 2 000 $.
3. **Protection portefeuille insuffisante** : pas de coupe-circuit drawdown actif côté backtest pipeline.
4. **Régime marché trop permissif** : il réduit un peu le risque, mais **n’empêche pas** de rester fortement exposé dans les mauvais contextes.
5. **Sensibilité forte au régime de taux 2021-2022** : le filtre actuel protège surtout contre `Technology/Tech/Growth`, mais laisse encore beaucoup d’exposition à des poches sensibles aux taux (immobilier, cycliques, financières).
6. **Hypothèses d’exécution trop optimistes** : slippage nul, implementation shortfall nul, gap filter désactivé.

### Réponse à votre question “pourquoi ça baisse autant et comment l’éviter ?”

- **Oui, certains paramètres sont mal adaptés** au contexte du run.
- **Oui, il manque des protections importantes** au niveau portefeuille.
- **Oui, il faut renforcer la logique de régime** pour 2021-2022.
- **Oui, il faut traiter la qualité/couverture ML comme un gating réel**, pas comme un warning toléré.

---

## 3. Constats factuels issus des artefacts

## 3.1 Performance et drawdowns

D’après `report.json` et `equity_curve.csv` :

- départ equity : **2 000 $**
- fin : **4 811.30 $**
- max drawdown global : **-53.28 %**
- pire point absolu : **2020-03-18**
- drawdown depuis le pic de **2021-11-18** jusqu’au creux de **2022-06-30** : **-53.06 %**

### Pires mois observés

- **2020-03** : **-29.48 %**
- **2022-06** : **-13.77 %**
- **2022-02** : **-12.40 %**
- **2022-01** : **-12.10 %**
- **2022-04** : **-10.28 %**
- **2020-02** : **-10.52 %**
- **2021-09** : **-7.89 %**
- **2024-04** : **-9.86 %**

### Episodes majeurs

- **Crash COVID** : drawdown prolongé de fin février 2020 à mai/juin 2020
- **Grand plateau baissier** après le pic du **18/11/2021** jusqu’au **30/06/2022**
- plusieurs rechutes secondaires ensuite (notamment 2023 H2 et 2024)

---

## 3.2 Le run est massivement dégradé côté signaux ML

D’après `coverage_summary.json` / `report.json` / `replay_diagnostic_summary.json` :

- couverture ML : **1.31 %** seulement
- lignes ML manquantes : **142 902 / 144 798**
- sessions dégradées : **1521 / 1537**
- raison principale : **`ml_predictions_missing`**

Cela veut dire que, pendant presque tout le run, le pipeline tourne **sans la composante ML attendue**.

Or les paramètres du run déclarent toujours :

- `conviction_weights.score_weight = 0.4`
- `conviction_weights.prediction_weight = 0.6`

Mais dans les artefacts Phase 2 / diagnostics, les sélections sont très souvent portées par :

- **`final_score_sentiment`**
- `core.conviction:score_only`

Donc, en pratique, **le moteur sélectionne majoritairement sur le score/sentiment**, pas sur un signal ML complet.

### Conséquence

Le backtest a probablement capturé un **style plus “momentum/sentiment” que prévu**, avec moins de garde-fous de robustesse. C’est particulièrement dangereux lors des ruptures de régime comme 2021-2022.

---

## 3.3 Le régime marché existe, mais il ne bloque presque rien

D’après `phase2_risk_summary.json` :

- distribution régime :
  - `normal` : **1028** sessions
  - `capital_preservation` : **509** sessions
- `entries_blocked_by_regime` : **0**

Le code confirme pourquoi :

- `service/market/regime_manager.py` peut faire monter le mode vers `capital_preservation`
- `risk_management/regime_apply.py` applique surtout :
  - `risk_multiplier`
  - `effective_max_positions_override`
  - `enforce_min_notional`
  - `max_tickers_per_sector`

Mais :

- **`capital_preservation` ne coupe pas automatiquement les nouvelles entrées**
- seules les modes `close_only` / `cash_only` bloquent réellement les entrées (`service/market/regime_manager.py`)

### Conséquence

Le système peut rester long et continuer à tourner dans un marché hostile, simplement avec un profil un peu plus prudent, mais **pas assez défensif**.

---

## 3.4 Les protections portefeuille ne sont pas actives dans ce run

Le run déclare dans `report.json.params.risk_overlay` :

- `regime_filter_enabled: false`
- `max_sector_exposure_pct: 0.0`
- `max_portfolio_dd_pct: 0.0`
- `target_annual_vol: null`

Donc côté backtest overlay :

- **pas de filtre de régime simple SMA**
- **pas de cap sectoriel overlay**
- **pas de coupe-circuit drawdown portefeuille**
- **pas de volatility targeting**

Le code `backtesting/risk_overlay.py` le confirme : tous ces modules existent, mais ils sont **désactivés** dans ce run.

### Point important

Le preset micro-compte (`config/capital_presets.yaml`) prévoit pourtant une discipline plus stricte :

- `risk_max_positions: 3`
- `risk_max_position_weight: 0.35`
- `risk_max_sector_weight: 0.55`
- `risk_min_position_notional: 500.0`
- `risk_max_drawdown_pct: 0.07`
- `risk_max_daily_loss_pct: 0.025`

Mais dans le **pipeline de backtest**, le seuil de drawdown portefeuille de `RiskConfig` n’est **pas** le garde-fou principal. Le coupe-circuit réellement utilisé en backtest est celui de `backtesting/risk_overlay.py`, et ici il est **désactivé** (`max_portfolio_dd_pct = 0.0`).

### Conséquence

Le backtest pouvait mathématiquement laisser courir un drawdown de **-53 %**, sans mécanisme de stop global du portefeuille.

---

## 3.5 Le petit capital force une concentration structurelle

Le preset `capital_0_2000` est explicitement décrit comme un preset de **micro-compte** avec **“concentration assumée (3 lignes)”**.

Pour rappel (`config/capital_presets.yaml`) :

- capital max du preset : **2 000**
- `risk_max_positions: 3`
- `risk_min_position_notional: 500 $`
- `risk_max_position_weight: 35 %`
- `risk_max_sector_weight: 55 %`

Même sans bug, cela fabrique un portefeuille **intrinsèquement concentré**.

Sur la fenêtre de drawdown **2021-11-18 → 2022-06-30**, les flux d’entrées acceptées (`phase2_risk_entries.csv`) sont dominés par :

- **Consumer Cyclical** : **367** entrées acceptées/réduites
- **Real Estate** : **226**
- **Financial Services** : **204**
- **Technology** : **110**

Et côté concentration quotidienne des flux acceptés sur cette fenêtre :

- sur **92 / 156** sessions, au moins **40 %** des noms acceptés du jour venaient d’un seul secteur
- sur **24 / 156** sessions, un seul secteur représentait au moins **50 %** du poids cible accepté du jour

> Important : cela décrit les **flux d’acceptation/targeting** du jour, pas forcément les holdings simultanés finaux. Mais cela montre une **pression sectorielle forte** sur la construction du portefeuille.

### Conséquence

Avec **2 000 $**, **pas de fractions**, **tickets minimum élevés**, et une logique ATR stricte, on obtient un portefeuille mécaniquement trop concentré pour traverser proprement les ruptures de régime.

---

## 3.6 Le filtre de taux 2021-2022 est incomplet

Dans `config.yaml`, la logique `market_regimes.yields` :

- bloque surtout `Technology`, `Tech`, `Growth`
- active `block_high_beta`
- applique `risk_mult: 0.6`

Le problème observé entre **novembre 2021 et juin 2022** est que la casse ne se limite pas à la tech pure.

Les flux acceptés du backtest sur cette fenêtre sont fortement orientés vers :

- **Real Estate**
- **Consumer Cyclical**
- **Financial Services**

Or ce sont précisément des poches qui peuvent souffrir d’un changement violent de régime de taux / discount rate / consommation / financement.

### Conclusion spécifique sur 2021-2022

Le moteur a bien une logique de régime, mais elle est **trop étroite dans son ciblage** :

- elle protège une partie du risque “growth/tech”
- elle **laisse encore passer trop d’exposition** dans d’autres segments sensibles aux taux

C’est une explication très plausible du long drawdown post-pic de novembre 2021.

---

## 3.7 Les sorties sont nombreuses, mais elles ne suffisent pas à protéger le portefeuille

D’après `phase7_exit_lifecycle_replay_summary.json` :

- sorties totales : **11 692**
- `filled_initial_stop` : **9 313**
- `filled_take_profit` : **1 246**
- `filled_trailing_stop` : **1 133**

Le code le confirme :

- stop initial dérivé de `ATR * atr_stop_multiple` (`risk_management/portfolio_builder.py`, `execution_engine/order_intents.py`)
- take-profit : max entre `% fixe` et `2R` (`execution_engine/order_intents.py`)
- trailing stop activé après **+1R** par défaut (`execution_engine/config.py`, `execution_engine/order_intents.py`)

### Lecture correcte

Le système a bien des stops **trade par trade**.

Mais cela **n’empêche pas** un gros drawdown portefeuille quand :

1. beaucoup de trades sont exposés au même régime adverse,
2. les entrées se renouvellent dans le mauvais style,
3. il n’y a pas de coupe-circuit au niveau portefeuille,
4. la rotation des signaux continue malgré un contexte hostile.

Autrement dit : **les stops individuels existent, mais la protection globale du portefeuille est insuffisante**.

---

## 3.8 Les hypothèses de microstructure/exécution sont trop optimistes

Le run utilise :

- `slippage_bps = 0.0`
- `microstructure.slippage_base_bps = 0.0`
- `microstructure.slippage_impact_coef = 0.0`
- `max_entry_gap_pct = 0.0`

Et `phase2_execution_tca_summary.json` affiche :

- `avg_slippage_bps = 0.0`
- `total_implementation_shortfall = 0.0`

Pour un micro-compte qui travaille des titres parfois volatils, et surtout sur des phases stressées comme 2020 ou 2022, c’est **trop favorable**.

Le preset micro-compte recommande d’ailleurs explicitement des hypothèses de stress plus dures (`config/capital_presets.yaml`) :

- `backtesting_commission_bps_stress: 15.0`
- `backtesting_slippage_bps_stress: 25.0`

### Conséquence

Le backtest est probablement **optimiste sur la performance** et **sous-estime** une partie du risque réel.

Cela n’explique pas à lui seul le drawdown observé, mais cela signifie que le profil réel serait probablement **encore moins confortable**.

---

## 3.9 Il existe aussi un sujet qualité des données / cohérence d’artefacts

Deux signaux d’alerte :

1. `coverage_summary.json` indique `mixed_data_source_window` sur les barres (`eodhd_eod` + `alpaca_iex`).
2. Les exports pipeline ne sont pas totalement cohérents entre eux :
   - `trades.csv` ne contient qu’**1 trade**
   - alors que `phase7_exit_lifecycle_replay.csv` contient **11 692 sorties**

Le code montre aussi que les exports `trades.csv` / `trade_audit_log.csv` ne reflètent pas forcément tout le lifecycle pipeline de phase 7 (`backtesting/report.py`).

### Conséquence

Pour le diagnostic fin “trade par trade”, il faut privilégier :

- `equity_curve.csv`
- les résumés phase 2 → 7
- les sources du moteur

et **ne pas faire confiance aveuglément** à tous les CSV de sortie pour l’attribution PnL détaillée.

---

## 4. Pourquoi les grosses baisses se produisent

## 4.1 Baisse n°1 : février-mars 2020 (crash COVID)

### Cause probable

Le système reste exposé à un choc de marché extrêmement brutal alors que :

- il n’a **pas** de coupe-circuit portefeuille actif en backtest
- il n’a **pas** de volatility targeting
- il n’a **pas** de filtre de gap d’ouverture
- il applique des stops individuels, mais pas de réduction globale d’exposition assez agressive

### Diagnostic

Ce drawdown est cohérent avec un moteur qui sait couper **chaque trade**, mais pas **le portefeuille dans son ensemble**.

### Comment l’éviter

- activer un **drawdown breaker portefeuille**
- activer un **vol targeting**
- passer en **`cash_only`** ou **`close_only`** quand un choc macro/VIX majeur est détecté
- activer un **gap filter** à l’entrée

---

## 4.2 Baisse n°2 : novembre 2021 → juin 2022 (la plus importante après le pic)

### Cause probable principale

Le moteur continue à recycler des entrées dans un style de marché qui devient défavorable, avec :

- **ML quasi absent**
- forte dépendance au score/sentiment
- régime `capital_preservation` souvent actif mais **non bloquant**
- surexposition des flux vers :
  - **Consumer Cyclical**
  - **Real Estate**
  - **Financial Services**

### Interprétation marché

La période correspond à un changement de régime profond :

- remontée des taux
- compression des multiples
- rotation factorielle
- pression sur l’immobilier / consommation / finance / growth

Le système avait une brique “yield spike”, mais elle est **trop centrée sur Tech/Growth** et ne protège pas assez les autres segments sensibles aux taux.

### Pourquoi la baisse dure si longtemps

Parce que la logique actuelle :

- **réduit un peu** le risque
- mais **ne coupe pas** réellement l’exposition
- et **n’impose pas** une sortie portefeuille après franchissement d’un drawdown global

Donc le portefeuille peut continuer à subir une longue séquence de pertes / faux rebonds / réallocations défavorables.

### Comment l’éviter

- élargir le régime “taux” aux secteurs vraiment sensibles au contexte 2021-2022
- transformer certains contextes `capital_preservation` en **`cash_only` backtest**
- réduire **gross exposure** et **poids par ligne** en mode défensif
- imposer un **cut-off portefeuille** beaucoup plus tôt

---

## 4.3 Les autres baisses significatives

Elles semblent provenir du même noyau de causes :

- concentration sectorielle/style
- absence de gouvernance portefeuille forte
- stratégie qui continue à rentrer alors que le contexte ne valide plus le style dominant
- qualité signal dégradée faute de ML

Les replis 2023 H2 / 2024 restent plus modestes que 2020 ou 2021-2022, mais ils montrent que le problème n’est **pas isolé** à une seule crise.

---

## 5. Ce qui manque aujourd’hui

## 5.1 Un vrai garde-fou de drawdown portefeuille dans le pipeline backtest

Aujourd’hui, le run n’active pas le coupe-circuit `backtesting/risk_overlay.DrawdownCircuitBreaker`.

C’est l’amélioration la plus évidente pour éviter qu’un drawdown de -15 % devienne -25 %, puis -35 %, puis -50 %.

### Recommandation

Activer un coupe-circuit avec un réglage initial de type :

- `max_portfolio_dd_pct`: **0.12 à 0.15**
- `dd_recovery_pct`: **0.97 à 1.00**

Pour un micro-compte, je recommanderais même un premier test à **12 %**.

---

## 5.2 Une réduction de risque réellement contraignante en mode défensif

Le mode `capital_preservation` actuel est trop doux.

### Il faut ajouter en mode défensif

- baisse de `max_gross_exposure`
- baisse de `max_position_weight`
- baisse de `max_sector_weight`
- éventuellement baisse du nombre de nouvelles entrées par séance
- passage en `cash_only` si plusieurs signaux macro négatifs s’empilent

### Recommandation concrète

Quand le mode devient `capital_preservation` :

- `max_gross_exposure` : **1.0 → 0.35 / 0.50**
- `max_position_weight` : **réduction de 30 à 50 %**
- `max_sector_weight` : **0.55 → 0.20 / 0.25** sur micro-compte
- si VIX élevé + spike taux + sentiment warning : **`cash_only`**

---

## 5.3 Une logique de régime “taux” plus complète

Le filtre actuel cible surtout `Technology/Tech/Growth`.

### Il faut étendre / calibrer sur 2021-2022

À tester dans le régime `yield_spike_10y` :

- `Real Estate`
- `Consumer Cyclical`
- certaines `Financial Services`
- éventuellement segments très endettés / duration longue

### Recommandation

Créer une variante de régime :

- `yield_spike_10y_soft` : réduction forte de risque
- `yield_spike_10y_hard` : `cash_only` ou blocage de certains paniers sectoriels

---

## 5.4 Un gating dur sur la couverture ML

Aujourd’hui, le système tolère un run quasi complet sans ML.

Pour un backtest pipeline censé combiner score + ML, c’est trop permissif.

### Recommandation

Ajouter une règle simple :

- si couverture ML < **X %** (ex. 60 %, 80 %, à calibrer), alors :
  - soit on **bloque** le run pipeline,
  - soit on le bascule explicitement dans un mode **score-only défensif**,
  - soit on **divise par 2** le risque et le nombre max de positions.

### Pourquoi

Sans cela, on compare un comportement “prévu ML+score” avec un comportement réel “score/sentiment only”, sans reparamétrage de risque.

---

## 5.5 Une diversification compatible micro-compte

Avec :

- 2 000 $ d’equity
- tickets minimum élevés
- pas de fractions
- concentration assumée du preset

le moteur n’a pas beaucoup de liberté pour se diversifier.

### Options possibles

#### Option A — la plus réaliste
Augmenter le capital minimum exploitable si l’on veut conserver ces contraintes de ticket.

#### Option B — si le broker le permet
Activer / généraliser les **fractional shares** pour réduire la concentration.

#### Option C — si on reste sur micro-compte
Abaisser le ticket minimum et compenser par :

- filtrage de liquidité plus strict
- coûts de transaction plus réalistes
- cap sectoriel plus dur

### Mon avis

Pour un vrai micro-compte, **fractionner** est probablement plus utile que “tenter le même moteur avec 3 grosses lignes”.

---

## 5.6 Une microstructure plus réaliste

Le run actuel est trop propre :

- slippage nul
- impact nul
- gap filter off

### Recommandation

Au minimum, tester :

- `commission_bps`: **15**
- `slippage_bps`: **10 à 25**
- `max_entry_gap_pct`: **0.02 à 0.03**
- modèle de slippage `linear` ou `sqrt` sur les titres moins liquides

Cela n’évitera pas le drawdown, mais évitera de surévaluer la robustesse.

---

## 5.7 Une meilleure qualité d’audit post-run

Il faut corriger l’écart entre :

- `trades.csv` / `trade_audit_log.csv`
- et les artefacts Phase 7

Sinon les post-mortems détaillés sont difficiles et parfois trompeurs.

### Recommandation

Pour les runs pipeline, l’export “trade list” final devrait être reconstruit à partir de la vérité Phase 3 → 7, pas seulement d’un sous-ensemble `closed_trades_df`.

---

## 6. Plan d’action recommandé (priorité)

## Priorité 1 — indispensable

1. **Activer le drawdown breaker portefeuille en backtest pipeline**
2. **Activer un vol targeting**
3. **Mettre un gating dur sur la couverture ML**
4. **Durcir le régime en 2021-2022 style “rates shock”**

## Priorité 2 — très importante

5. **Ajouter un cap sectoriel réel**
6. **Réduire l’exposition brute en mode `capital_preservation`**
7. **Activer un gap filter à l’entrée**

## Priorité 3 — qualité de modèle / fiabilité

8. **Rendre les coûts d’exécution réalistes**
9. **Unifier les données corporate actions / ajustements prix**
10. **Réconcilier les exports pipeline de trades**

---

## 7. Paramétrage concret à tester en prochain backtest

## 7.1 Profil “défensif micro-compte”

### Couche portefeuille

- `max_portfolio_dd_pct`: **0.12**
- `dd_recovery_pct`: **0.98**
- `target_annual_vol`: **0.12 à 0.15**
- `max_sector_exposure_pct`: **0.20 à 0.25**

### Régime marché

- si `yield_spike_10y` :
  - réduire `max_gross_exposure`
  - réduire `max_position_weight`
  - étendre la liste des secteurs sensibles
- si `VIX high` + `yield spike` + `sentiment warning` :
  - **passer en `cash_only`**

### Couverture ML

- si couverture ML < **80 %** :
  - **mode défensif automatique**
  - ou **blocage du run pipeline**

### Exécution / microstructure

- commission : **15 bps**
- slippage : **10–25 bps**
- `max_entry_gap_pct`: **2–3 %**

---

## 8. Réponse finale à la question “paramètres non adaptés ou il manque autre chose ?”

### Réponse courte

**Les deux.**

### Paramètres non adaptés

Oui :

- overlay risque portefeuille désactivé
- exécution trop optimiste
- filtre de régime trop étroit
- micro-compte trop concentré
- run pipeline toléré malgré ML presque absent

### Ce qu’il manque

Oui :

- coupe-circuit drawdown au niveau portefeuille
- vraie réduction d’exposition en mode défensif
- gating ML
- meilleur traitement des régimes taux/rotation factorielle
- meilleure cohérence d’audit / données ajustées

---

## 9. Conclusion opérationnelle

Si je devais résumer en une phrase :

> Le backtest gagne, mais il gagne avec un moteur qui reste trop longtemps exposé, trop concentré, et avec un signal dégradé, sans garde-fou portefeuille suffisant — ce qui explique les drawdowns majeurs, notamment celui de novembre 2021 à juin 2022.

### Les 4 changements les plus rentables à faire en premier

1. **Activer un drawdown breaker portefeuille**
2. **Imposer une réduction d’exposition beaucoup plus forte en régime défensif**
3. **Bloquer ou dégrader fortement le run quand la couverture ML est insuffisante**
4. **Étendre le filtre “taux” à l’immobilier / cycliques / financières**

Avec ces 4 changements, vous avez de bonnes chances de :

- réduire fortement les longues phases de baisse,
- améliorer le Calmar,
- rendre la courbe beaucoup plus exploitable,
- et éviter qu’un bon rendement final masque un risque psychologiquement et opérationnellement trop élevé.

