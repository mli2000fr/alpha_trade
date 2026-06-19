# Synthèse Sprint 3 — backtest fractionnaire natif

_Date : 2026-06-09_

## Checklist
- [x] Rendre le simulateur backtest compatible avec les quantités fractionnaires
- [x] Supprimer les troncatures entières dans les bridges risk / exécution / replay
- [x] Corriger les fills synthétiques partiels pour le replay d’exécution
- [x] Préserver les décimales dans les frames de fidélité / compare
- [x] Conserver la rétrocompatibilité du mode entier historique
- [x] Ajouter et exécuter les tests ciblés Sprint 3
- [x] Mettre à jour la documentation

---

## 1. Résumé exécutif

Le **Sprint 3 est implémenté**.

Le backtest sait maintenant transporter et simuler des quantités fractionnaires de bout en bout sur son périmètre natif :
- sizing d’entrée en `float` dans le simulateur ;
- overrides de signaux (`filled_qty`, `approved_shares`, `target_shares`) respectés sans troncature ;
- replay d’exécution compatible avec des fills partiels fractionnaires ;
- reporting/parity/fidelity conservant les décimales ;
- comportement historique entier conservé si `RiskConfig.allow_fractional_shares=False`.

---

## 2. Changements réalisés

### 2.1 Simulateur backtest
Fichier : `backtesting/simulator.py`

Réalisé :
- `_OpenPosition.quantity` passé en `float` ;
- remplacement des `int(... // ...)` bloquants par des calculs flottants normalisés ;
- plafonnement du sizing par cash disponible, budget dégradé et gross exposure en `float` ;
- prise en compte du flag `allow_fractional_shares` pour préserver le mode entier historique ;
- override de quantité issu des signaux désormais résolu en `float | None`.

### 2.2 Bridges risk / exécution / replay
Fichiers :
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`

Réalisé :
- suppression des `int(entry.approved_shares)` / `int(target_shares)` ;
- propagation des quantités via `normalize_share_quantity()` ;
- replay d’exécution enrichi pour conserver des fills synthétiques fractionnaires sur les scénarios partiels.

### 2.3 Fidélité / compare
Fichier : `backtesting/fidelity.py`

Réalisé :
- ajout de `_safe_float()` pour les quantités ;
- conservation des décimales dans les compare frames et sections parity ;
- maintien de `_safe_int()` pour les compteurs / rangs seulement.

### 2.4 Correction connexe détectée pendant validation
Fichier : `common/capital_presets.py`

Réalisé :
- correction d’un typo dans `_RISK_CONFIG_PRESET_MAPPING` sur `risk_allow_fractional_shares`, qui cassait la collecte de tests liée aux presets.

---

## 3. Tests Sprint 3

### Nouveau fichier de test
- `tests/test_backtesting_fractional.py`
  - préservation de `0.5` share dans `risk_bridge` ;
  - préservation de `0.5` share dans `execution_bridge` ;
  - préservation de `0.5` share dans `execution_replay` ;
  - compare frames fidelity sans troncature ;
  - fills synthétiques fractionnaires (`2.5 -> 1.5 + 1.0`) ;
  - run backtest en mode `execution_replay` avec `0.5` share.

### Revalidation ciblée
- `tests/test_backtesting.py`
  - mode entier historique inchangé ;
  - override replay toujours fonctionnel ;
  - cap de gross exposure toujours respecté.
- `tests/test_phase2_risk_bridge_regime.py`
- `tests/test_execution_replay_parity.py`
- `tests/test_capital_preset_risk_overrides.py`

### Commandes exécutées

```powershell
python -m pytest tests/test_backtesting_fractional.py -q -o addopts=""
python -m pytest tests/test_backtesting.py -q -o addopts="" -k "uses_integer_share_sizes or execution_replay_mode_uses_signal_share_override or enforces_max_gross_exposure_from_risk_config"
python -m pytest tests/test_phase2_risk_bridge_regime.py -q -o addopts=""
python -m pytest tests/test_execution_replay_parity.py -q -o addopts=""
python -m pytest tests/test_capital_preset_risk_overrides.py -q -o addopts=""
```

### Résultat
- **32 tests passés**

---

## 4. Fichiers clés Sprint 3

- `backtesting/simulator.py`
- `backtesting/risk_bridge.py`
- `backtesting/execution_bridge.py`
- `backtesting/execution_replay.py`
- `backtesting/fidelity.py`
- `common/capital_presets.py`
- `tests/test_backtesting_fractional.py`

---

## 5. Points désormais couverts

- un signal/replay backtest peut ouvrir une position de **`0.5` share** ;
- les bridges inter-phases ne détruisent plus silencieusement les décimales ;
- le replay synthétique peut représenter un **partial fill fractionnaire** ;
- le mode entier historique reste intact si le flag fractionnaire est désactivé.

---

## 6. Ce qui reste après Sprint 3

Le prochain blocage majeur devient le **Sprint 4 — live fractional entry** :
- propagation runtime explicite jusqu’aux `OrderIntent` live ;
- contrôle broker/asset sur la fractionnalité ;
- formatage final `qty` côté soumission ;
- bornage clair entre entrées fractionnaires live et protections live.

