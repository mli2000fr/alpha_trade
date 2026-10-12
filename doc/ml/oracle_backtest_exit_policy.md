# Oracle — sorties configurables TP 20 % / SL 10 %

Décision du 12 octobre 2026 : conserver **TP fixe 20 % / SL fixe 10 %,
sans trailing**, pour les prochains replays de recherche Oracle.

Dans `config.yaml` :

```yaml
oracle_backtest:
  take_profit_pct: 0.20
  stop_loss_pct: 0.10
```

Les valeurs sont des fractions, pas des entiers `20` et `10`. La configuration
est validée : valeurs non finies, booléens, paramètres inconnus et fractions
hors de `]0,1[` sont refusés. Un changement s'applique au prochain replay
configuré, jamais aux résultats archivés.

Validation locale : **80 tests passent**, incluant paramètres personnalisés,
TP/SL depuis le fill, expiration, archivage, échec explicite et non-régression
des protections LLM. Aucun backtest historique supplémentaire n'a été lancé.

## Périmètre exact

- TP et SL calculés depuis le **prix réellement exécuté à l'open J+1**.
- Trailing désactivé ; expiration conservée à l'open de la **21e séance depuis
  l'entrée**, séance d'entrée incluse dans les 20 séances de détention.
- Classement, sizing ATR natif, capital, coûts et règles de lifecycle inchangés.
- Replay **LONG uniquement**, sur les scores figés des deux modèles étudiés ;
  2025 ou 2026 jusqu'au 3 septembre, TOP10/20/50.
- Aucun réentraînement, aucune écriture SQL ni aucun ordre broker.

**Ce bloc ne pilote pas les backtests génériques de l'IHM, le PAPER/LIVE ni les
protections LLM.** Il ne transforme pas le modèle de recherche en modèle servant.
Les positions déjà ouvertes conservent leurs protections.

Le bloc `oracle_barrier` reste indépendant : **TP20/SL7 pour les labels du
prochain entraînement**, sauf modification explicite. Le modèle déjà entraîné
`model-factory-20261011221400-867a1e` conserve toujours son protocole initial.
Les valeurs d'exécution ne requalifient pas ses probabilités de TP avant SL.

## Utiliser la configuration

Point d'entrée dédié, avec un **nouveau répertoire de résultat** :

```powershell
python -u -m scripts.research.us_oracle_configured_replay --inputs artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1 --output artifacts/research/us_oracle_barrier_comparison/configured-top10-2026-v1 --year 2026 --count 10 --arm NEW_BARRIER_LONG
```

`--config` permet un YAML alternatif. `OLD_TERMINAL_LONG` sélectionne l'ancien
modèle pour une comparaison aux mêmes sorties. Chaque lancement traite un cas,
lit les archives locales et produit `protocol.json`, `progress.json`,
`report.json` et les détails de portefeuille. Les paramètres et empreintes
sont figés avant le calcul, puis les protections des transactions sont auditées.
Un ancien répertoire n'est pas écrasé. Aucun replay historique complet n'est
lancé par la simple modification du YAML.

## Limites conservées

Un SL de 10 % n'est pas une garantie de perte maximale : un gap adverse peut
dépasser ce niveau. Les frais s'ajoutent. Secteurs actuels/non PIT et conventions
OHLC gardent les réserves des expériences précédentes ; pas une certification live.

Les grilles TP/SL et trailing précédentes restent **des expériences figées** :
elles ne lisent pas ce nouveau bloc. La modification du YAML change son empreinte
actuelle ; ne pas réécrire leurs protocoles pour faire passer une vérification
contre le code/configuration courants. Leurs audits constatent l'état au moment
de leur calcul. Toute reprise exige une nouvelle campagne ou la restauration
exacte des inputs et de la configuration archivés, pas un mélange de versions.

Références : [grille TP/SL](oracle_tp_sl_grid_20261012.md),
[résultats trailing](oracle_trailing_grid_20261012.md),
[contrat d'entraînement](oracle_barrier_training.md).
