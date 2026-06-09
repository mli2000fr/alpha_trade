# Fraction / activation technique

## Question
Comment activer le fractionnaire dans le backtest et dans le live ?
Est-ce qu'il existe un paramètre centralisé à activer, ou faut-il modifier du code partout ?

## Réponse courte
Non, il ne faut **pas modifier partout dans le code**.

L'activation est désormais **centralisée par sous-système** et **pilotable opérateur** via CLI et IHM, même s'il n'existe toujours pas un unique flag global partagé entre backtest et live :

- **Backtest** : flag central = `RiskConfig.allow_fractional_shares`
- **Live / paper execution** : flag central = `ExecutionConfig.allow_fractional_shares`
- **Protections live fractionnaires** : second niveau d'activation via
  - `ExecutionConfig.allow_fractional_live_protections`
  - ou `ExecutionConfig.fractional_live_mode`

Donc :
- **pas besoin de modifier les algos partout** ;
- **oui**, il faut activer le bon paramètre **dans la config qui alimente le backtest** et **dans celle qui alimente le live** ;
- **oui**, cette activation est désormais exposée en **CLI** et dans l'**IHM** ;
- **non**, il n'existe toujours pas un unique flag global dans `config.yaml` qui active tout d'un coup.

---

## 1. Backtest : activation

### Source de vérité
Le backtest s'appuie sur `RiskConfig.allow_fractional_shares`.

Chemins utiles :
- `risk_management/config.py`
- `common/capital_presets.py`
- `backtesting/cli/_impl.py`
- `backtesting/simulator.py`

### Points clés
#### a) Flag dans `RiskConfig`
Dans `risk_management/config.py` :
- `allow_fractional_shares: bool = False`

#### b) Mapping centralisé depuis les presets capital
Dans `common/capital_presets.py` :
- `risk_allow_fractional_shares` -> `RiskConfig.allow_fractional_shares`

#### c) Le CLI backtest propage déjà le preset vers `RiskConfig`
Dans `backtesting/cli/_impl.py` :
- `build_risk_config_kwargs_from_preset(effective_preset)`
- puis `RiskConfig(**risk_kwargs)`

#### d) Le simulateur respecte ce flag
Dans `backtesting/simulator.py` :
- `_allow_fractional_shares()` lit `self.config.risk_config.allow_fractional_shares`
- `_normalize_trade_quantity()`
  - garde la quantité décimale si le flag est `True`
  - tronque à l'entier sinon

### Conclusion backtest
Pour activer le fractionnaire en backtest, trois voies existent désormais :

1. **preset capital** :

```yaml
risk_allow_fractional_shares: true
```

Exemple dans `config/capital_presets.yaml`, dans `values:` du preset visé.

2. **CLI backtest** :

```powershell
python -m backtesting run --start 2025-01-01 --allow-fractional-shares
```

3. **IHM backtest** : switch persistant `Autoriser les quantités fractionnaires en backtest`, restauré depuis :

```text
artifacts/ihm_preferences/fractional_trading.json
```

### Important
Les presets visibles dans `config/capital_presets.yaml` ne l'activent pas nécessairement par défaut ; l'IHM, elle, propose un **switch activé par défaut** pour les runs lancés depuis l'interface.

Donc si tu veux du fractionnaire en backtest, tu dois **l'ajouter dans le ou les presets concernés**.

### Est-ce qu'il faut modifier le moteur de backtest ?
**Non**, pas en usage normal.
Le support est déjà câblé dans le flux `preset -> RiskConfig -> simulator`.

---

## 2. Live / paper : activation

### Source de vérité
Le live/paper s'appuie sur `ExecutionConfig`.

Chemins utiles :
- `execution_engine/config.py`
- `execution_engine/order_intents.py`
- `run_execution.py`

### Flags disponibles
Dans `execution_engine/config.py` :
- `allow_fractional_shares: bool = False`
- `allow_fractional_live_protections: bool = False`
- `fractional_live_mode: Literal["entry_only", "intraday_only", "full_if_supported"] = "entry_only"`

### Sens des flags
#### a) `allow_fractional_shares`
C'est le switch principal pour autoriser les **entrées fractionnaires**.

Dans `execution_engine/order_intents.py` :
- si `config.fractional_live_entries_enabled` est faux,
- les cibles fractionnaires sont bloquées avec la raison `fractional_shares_disabled`.

#### b) `allow_fractional_live_protections`
Compatibilité historique / raccourci pour autoriser les protections fractionnaires live.

#### c) `fractional_live_mode`
Mode effectif pour les protections :
- `entry_only` : seulement l'entrée fractionnaire
- `intraday_only` : protections fractionnaires limitées au mode intraday
- `full_if_supported` : protections fractionnaires complètes si le broker/flux les supporte

### Où activer en pratique
Dans `run_execution.py`, les presets runtime sont définis dans le dict `PRESETS` :
- `simulate`
- `paper`
- `live`

Ce sont eux qui alimentent ensuite :

```python
config = ExecutionConfig(**preset, ...)
```

### Conclusion live
Pour activer les entrées fractionnaires en live/paper, trois voies existent désormais :

1. **CLI exécution** :

```powershell
python run_execution.py paper --allow-fractional-shares
```

2. **IHM pipeline** : switch persistant `Execution/Risk — autoriser les quantités fractionnaires`.

3. **preset runtime** : si l'on veut l'activer structurellement dans les presets Python :

```python
"allow_fractional_shares": True,
```

Et si tu veux aussi des protections fractionnaires live :

```python
"allow_fractional_live_protections": True,
```

ou plus explicitement :

```python
"fractional_live_mode": "full_if_supported",
```

### Important
Le support existe côté `ExecutionConfig`, et il est maintenant pilotable sans toucher au code via `run_execution.py --allow-fractional-shares` ou depuis l'IHM. En revanche, il n'existe toujours pas de **flag global YAML unique** branché simultanément sur backtest + risk + execution.

### Est-ce qu'il faut modifier plusieurs modules live ?
**Non**, pas partout.

En pratique, il suffit soit :

- d'utiliser le flag CLI `--allow-fractional-shares` ;
- soit d'utiliser le switch IHM persistant ;
- soit, pour un comportement structurel, de modifier la source centrale du preset runtime dans `run_execution.py`.

---

## 3. Est-ce qu'il existe un paramètre centralisé unique pour backtest + live ?

### Réponse
**Pas complètement.**

Il y a une centralisation, mais à **deux niveaux distincts** :

- **Backtest** -> `RiskConfig.allow_fractional_shares`
- **Live** -> `ExecutionConfig.allow_fractional_shares`

Autrement dit :
- il n'y a **pas un seul flag global unique** dans `config.yaml` qui pilote tout ;
- mais il n'y a **pas non plus besoin de modifier tout le code** ;
- il faut activer le flag dans **la config amont de chaque pipeline**.

---

## 4. Réponse opérationnelle

### Si ton objectif est seulement de tester le fractionnaire en backtest
Modifier le preset concerné dans `config/capital_presets.yaml` :

```yaml
values:
  risk_allow_fractional_shares: true
```

### Si ton objectif est d'activer le fractionnaire en paper/live
Le plus simple est désormais :

```powershell
python run_execution.py paper --allow-fractional-shares
```

Ou via l'IHM Pipeline, avec persistance serveur du switch.

Pour un comportement imposé par preset, modifier le preset concerné dans `run_execution.py` :

```python
"allow_fractional_shares": True,
```

Et éventuellement :

```python
"fractional_live_mode": "full_if_supported",
```

### Si ton objectif est un vrai switch global unique
Il faut faire une **petite refactorisation de centralisation**, car ce switch global unique n'existe pas encore.

La bonne approche serait de définir une config partagée (YAML ou preset central) puis d'alimenter :
- `RiskConfig.allow_fractional_shares`
- `ExecutionConfig.allow_fractional_shares`
- `ExecutionConfig.fractional_live_mode`

à partir de cette source unique.

---

## 5. Conclusion nette

### Aujourd'hui
- **Backtest** : activation via `risk_allow_fractional_shares: true`, via `python -m backtesting run --allow-fractional-shares`, ou via le switch IHM persistant
- **Live** : activation via `python run_execution.py ... --allow-fractional-shares`, via le switch IHM Pipeline, ou via `allow_fractional_shares=True` dans le preset runtime
- **Protections live fractionnaires** : via `fractional_live_mode` / `allow_fractional_live_protections`

### Donc
- **non**, pas besoin de modifier partout ;
- **non**, il n'y a pas un unique paramètre global déjà branché pour tout ;
- **oui**, l'activation est déjà largement centralisée, mais **séparément** pour backtest et live ;
- **oui**, elle est désormais documentée et pilotable côté opérateur via IHM + CLI.

