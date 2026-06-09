# Fraction / activation technique

## Question
Comment activer le fractionnaire dans le backtest et dans le live ?
Est-ce qu'il existe un paramètre centralisé à activer, ou faut-il modifier du code partout ?

## Réponse courte
Non, il ne faut **pas modifier partout dans le code**.

En l'état actuel du dépôt, l'activation est **centralisée par sous-système**, mais **pas via un unique switch global partagé** entre backtest et live :

- **Backtest** : flag central = `RiskConfig.allow_fractional_shares`
- **Live / paper execution** : flag central = `ExecutionConfig.allow_fractional_shares`
- **Protections live fractionnaires** : second niveau d'activation via
  - `ExecutionConfig.allow_fractional_live_protections`
  - ou `ExecutionConfig.fractional_live_mode`

Donc :
- **pas besoin de modifier les algos partout** ;
- **oui**, il faut activer le bon paramètre **dans la config qui alimente le backtest** et **dans celle qui alimente le live** ;
- **non**, il n'existe pas aujourd'hui un unique flag global dans `config.yaml` qui active tout d'un coup.

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
Pour activer le fractionnaire en backtest, il suffit normalement d'ajouter dans le preset capital utilisé :

```yaml
risk_allow_fractional_shares: true
```

Exemple dans `config/capital_presets.yaml`, dans `values:` du preset visé.

### Important
Aujourd'hui, les presets visibles dans `config/capital_presets.yaml` n'activent pas ce flag par défaut.

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
Pour activer les entrées fractionnaires en live/paper, il faut renseigner dans le preset runtime concerné :

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
Actuellement, dans `run_execution.py`, les presets `simulate`, `paper` et `live` ne contiennent pas ces flags.

Donc en l'état :
- le support existe ;
- mais il n'est pas activé par défaut ;
- et il n'y a pas de CLI ou de `config.yaml` global déjà branché pour le piloter directement.

### Est-ce qu'il faut modifier plusieurs modules live ?
**Non**, pas partout.

En pratique, il suffit de modifier **la source centrale du preset runtime** dans `run_execution.py`.

Si tu veux rendre ça pilotable sans toucher au code à l'avenir, il faudrait faire **une petite évolution de plomberie config** :
- soit ajouter un flag CLI,
- soit lire ces valeurs depuis un YAML central,
- soit injecter un preset d'exécution externe.

Mais ce n'est **pas nécessaire** pour que ça fonctionne maintenant.

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
Modifier le preset concerné dans `run_execution.py` :

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
- **Backtest** : activation via `risk_allow_fractional_shares: true` dans le preset capital
- **Live** : activation via `allow_fractional_shares=True` dans le preset runtime de `run_execution.py`
- **Protections live fractionnaires** : via `fractional_live_mode` / `allow_fractional_live_protections`

### Donc
- **non**, pas besoin de modifier partout ;
- **non**, il n'y a pas un unique paramètre global déjà branché pour tout ;
- **oui**, l'activation est déjà largement centralisée, mais **séparément** pour backtest et live.

