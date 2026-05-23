# Macro regime — impact concret sur le backtest et le live

Ce document centralise les explications fonctionnelles et techniques sur la couche **macro / market regime** du projet :

- à quoi sert la donnée macro ;
- quelles sources sont utilisées ;
- pourquoi des logs Stooq peuvent apparaître ;
- quel impact cela a **concrètement** sur le **backtest** et sur le **live** ;
- comment est gérée l'absence de macro.

> Complément utile : voir aussi `doc/mode_regime.md` pour la FAQ orientée opérateur sur les modes `normal`, `capital_preservation`, `close_only`, `cash_only`.

---

## 1. Résumé exécutif

La macro n'est **pas** seulement décorative ou destinée au reporting.

Elle sert à construire un **snapshot de régime de marché** qui peut ensuite modifier le comportement du moteur de risque.

Concrètement, la macro peut :

- réduire le risque pris ;
- diminuer le nombre de positions autorisées ;
- bloquer certains secteurs ou les titres à fort bêta ;
- bloquer complètement les nouvelles entrées selon le mode résultant ;
- en mode strict, faire échouer un backtest si les données macro requises sont indisponibles.

Donc :

- en **backtest**, la macro peut changer les entrées retenues, l'exposition, le turnover, l'equity curve et les diagnostics ;
- en **live**, la macro peut changer le portefeuille cible et donc les ordres réellement autorisés / envoyés.

---

## 2. Où la logique vit dans le code

### Construction du snapshot de régime
- `service/market/regime_manager.py`
  - fonction clé : `build_snapshot(...)`

### Signaux macro bruts
- `service/market/macro_signals.py`
  - `evaluate_vix(...)`
  - `evaluate_yield_10y(...)`

### Providers macro
- `service/market/macro_providers.py`
  - `StooqMacroProvider`
  - `EodhdMacroProvider`
  - `CompositeMacroProvider`
  - `build_default_macro_provider(...)`

### Application au moteur de risque
- `risk_management/regime_apply.py`
  - `apply_snapshot(...)`

### Intégration live
- `risk_management/cli.py`
  - `_resolve_market_regime_snapshot(...)`
  - `apply_snapshot(...)`

### Intégration backtest
- `backtesting/risk_bridge.py`
  - appelle `build_snapshot(...)`
  - collecte `macro_missing_dates_count`
  - stocke `macro_data_quality_distribution`

---

## 3. Quelles données macro sont utilisées

Aujourd'hui, la couche macro exploite principalement :

### A. VIX
- VIX principal
- VIX court terme (ex. `VIX9D` / `^vix9d`)

### B. Taux US 10Y
- série du 10Y US Treasury
- utilisée pour mesurer un éventuel **spike** sur une fenêtre de lookback

---

## 4. Quelles sources sont utilisées

Le provider par défaut est construit dans `service/market/macro_providers.py`.

### Sources supportées

#### Stooq
Service gratuit, sans clé, utilisé notamment avec :
- `^vix`
- `^vix9d`
- `^tnx`

#### EODHD
Source secondaire / alternative avec symboles de type :
- `VIX.INDX`
- `VIX9D.INDX`
- `US10Y.INDX`

### Choix par défaut
Le factory `build_default_macro_provider(...)` retourne par défaut un provider **composite** :

- **Stooq d'abord** ;
- **EODHD en secours** si un token EODHD est disponible dans l'environnement.

C'est volontaire :
- Stooq est gratuit et ne consomme pas de quota ;
- EODHD est utilisé comme fallback si disponible.

---

## 5. Pourquoi on voit des logs Stooq

Exemple de log :

```text
[stdout] 2026-05-23 07:28:42,716 WARNING  service.stooq.clientStooq -- Stooq fetch failed for ^vix : <urlopen error timed out>
```

### Signification
Cela veut dire que la couche macro a tenté de récupérer la donnée macro `^vix` via Stooq et que l'appel réseau a expiré.

### Pourquoi Stooq est appelé ?
Parce que le provider macro par défaut essaie Stooq en premier pour obtenir :
- le VIX ;
- le VIX court terme ;
- le 10Y US.

### Est-ce bien pour de la macro ?
**Oui.**

Dans ce contexte, Stooq sert à fournir des **indicateurs macro de régime** et non des données d'actions utilisées directement pour les entrées du portefeuille.

### Est-ce bloquant ?
Pas forcément.

Tout dépend du mode :

- **mode tolérant** : le run continue mais marque la séance en `data_quality=missing` ;
- **mode strict** : si la donnée macro requise manque, le backtest échoue explicitement.

---

## 6. Quels signaux sont dérivés de la macro

La logique brute est dans `service/market/macro_signals.py`.

### 6.1 VIX élevé
`evaluate_vix(...)` retourne notamment :
- la valeur du VIX ;
- un booléen `vix_high` si le seuil configuré est dépassé ;
- un booléen `curve_inverted` si `VIX court terme > VIX`.

### 6.2 Courbe VIX inversée
Si le VIX court terme est supérieur au VIX principal, cela signale un stress court terme.

### 6.3 Spike du 10Y
`evaluate_yield_10y(...)` mesure la variation relative du 10Y sur une fenêtre de lookback.

Si la hausse dépasse le seuil configuré, on considère qu'il y a un **spike** de taux.

---

## 7. Impact concret de la macro sur le snapshot de régime

Dans `service/market/regime_manager.py`, `build_snapshot(...)` construit un `MarketRegimeSnapshot` contenant notamment :

- `mode`
- `risk_multiplier`
- `effective_max_positions`
- `allow_new_entries`
- `blocked_sectors`
- `block_high_beta`
- `high_beta_threshold`
- `data_quality`
- `decision_trace`

### 7.1 Si le VIX est élevé
Le mode peut être escaladé vers `capital_preservation`.

Effets typiques :
- réduction de l'agressivité ;
- portefeuille plus prudent ;
- possibilité de limiter plus fortement les nouvelles entrées via les règles de régime.

### 7.2 Si la courbe VIX est inversée
Le mode peut aussi être escaladé vers un mode défensif selon la config YAML.

### 7.3 Si le 10Y spike
Le snapshot peut :
- multiplier le risque par un coefficient défensif ;
- bloquer certains secteurs ;
- bloquer les titres `high beta` ;
- durcir la sélection du portefeuille.

### 7.4 Si le mode résultant devient restrictif
Dans `build_snapshot(...)`, certains modes (`close_only`, `cash_only`) forcent :

- `allow_new_entries = False`

Donc la macro peut aboutir à une séance sans nouvelles entrées.

---

## 8. Impact concret sur le backtest

Le bridge de backtest appelle la couche régime dans `backtesting/risk_bridge.py`.

Pour chaque séance :

1. on construit un snapshot via `build_snapshot(...)` ;
2. on applique ce snapshot à la config risque via `risk_management.regime_apply.apply_snapshot(...)` ;
3. on construit les entrées du portefeuille avec cette config ajustée.

### En pratique, la macro peut donc changer :
- le nombre de candidats finalement retenus ;
- le nombre de positions autorisées ;
- la taille/risque des positions ;
- les journées où aucune entrée n'est autorisée ;
- la trajectoire de l'equity curve ;
- les statistiques finales du backtest ;
- les diagnostics exposés dans le rapport et l'IHM.

### Exemple concret
Deux runs avec les mêmes signaux alpha peuvent produire des résultats différents si :
- l'un est en contexte `normal` ;
- l'autre passe en `capital_preservation` ou bloque certaines nouvelles entrées à cause de la macro.

### Diagnostics spécifiques backtest
Le bridge collecte aussi :
- `macro_data_quality_distribution`
- `macro_missing_dates`
- `macro_missing_dates_count`

Donc on peut savoir combien de séances ont tourné avec macro absente / dégradée.

---

## 9. Impact concret sur le live

Côté live, le snapshot est résolu dans `risk_management/cli.py` via :

- `_resolve_market_regime_snapshot(...)`

Puis appliqué à la config de risque via :

- `risk_management.regime_apply.apply_snapshot(...)`

### Ce que cela change concrètement en live
Avant de construire le portefeuille cible / les ordres :

- le `risk_multiplier` peut être réduit ;
- `effective_max_positions` peut être abaissé ;
- le min notional peut être imposé ;
- certaines contraintes sectorielles peuvent être renforcées ;
- les nouvelles entrées peuvent être interdites.

### En termes métier
Cela peut se traduire par :
- moins de lignes ouvertes ;
- tailles de position plus prudentes ;
- pas d'entrée sur certains secteurs ;
- pas d'entrée du tout si le régime est suffisamment restrictif.

Donc la macro influence directement le comportement opérationnel live.

---

## 10. Différence entre impact backtest et impact live

### Backtest
La macro influence :
- les sélections retenues ;
- le nombre de positions ;
- les journées bloquées ;
- les métriques et diagnostics du rapport.

### Live
La macro influence :
- les décisions du moteur de risque du jour ;
- le portefeuille cible ;
- les ordres réellement autorisés / bloqués.

### Point commun
La logique métier est volontairement partagée :
- même couche de snapshot ;
- même application au moteur de risque ;
- objectif de parité entre backtest et live.

---

## 11. Que se passe-t-il si la macro est absente

La couche gère explicitement l'absence de macro via `data_quality` et une politique configurable.

### Cas 1 — mode tolérant
Si `allow_neutral_fallback_on_missing_macro_data = true` :
- la séance continue ;
- `data_quality["macro"] = "missing"` ;
- la date est tracée dans les diagnostics ;
- le run reste analysable mais explicitement marqué comme dégradé.

### Cas 2 — mode strict
Si `allow_neutral_fallback_on_missing_macro_data = false` :
- une `MacroDataUnavailableError` est levée ;
- le backtest échoue explicitement.

### Pourquoi c'est utile
Cela évite les ambiguïtés :
- soit on veut un replay strictement fiable et on préfère échouer ;
- soit on accepte un replay dégradé, mais on veut le voir noir sur blanc.

---

## 12. Que signifie `data_quality=missing`

Quand une séance est marquée `data_quality=missing`, cela signifie que la donnée macro requise n'a pas pu être obtenue de manière exploitable.

Exemples de causes :
- pas de provider ;
- timeout réseau ;
- réponse vide ;
- historique insuffisant ;
- payload invalide.

Au niveau fin, les clés peuvent contenir par exemple :
- `vix = ok | missing | no_provider | provider_error`
- `yield_10y = ok | missing | no_provider | provider_error | invalid`
- `macro = ok | missing`

---

## 13. Que signifie “fallback neutre”

Le fallback neutre ne veut pas dire :
- “on invente une valeur macro”
- ou “on fait comme si tout allait bien”.

Cela veut dire :
- le run continue ;
- on **ne casse pas** le flux ;
- mais on **marque explicitement** la séance comme dégradée via `data_quality=missing`.

Autrement dit :
- le backtest n'est pas silencieusement maquillé ;
- la dette de qualité est visible dans les diagnostics.

---

## 14. Résumé opérateur

### Quand la macro sert vraiment
La macro sert quand on veut que le moteur tienne compte d'un contexte de marché global :
- stress implicite via le VIX ;
- tension court terme via la courbe VIX ;
- tension de taux via le 10Y.

### Effet concret
Elle peut rendre le moteur :
- plus prudent ;
- plus sélectif ;
- ou temporairement bloquant sur les nouvelles entrées.

### Ce que cela change pour l'utilisateur
- en backtest : résultats et diagnostics changent ;
- en live : portefeuille cible et ordres changent.

---

## 15. Réponse courte à “à quoi sert la macro ?”

La macro sert à **adapter automatiquement le niveau de prudence du moteur de risque** au contexte marché.

Formulé simplement :

- marché calme → comportement normal ;
- marché stressé → comportement plus défensif ;
- macro absente → soit on échoue, soit on continue en marquant explicitement la dégradation.

---

## 16. Références rapides

- `service/market/regime_manager.py`
- `service/market/macro_signals.py`
- `service/market/macro_providers.py`
- `risk_management/regime_apply.py`
- `risk_management/cli.py`
- `backtesting/risk_bridge.py`
- `doc/mode_regime.md`

