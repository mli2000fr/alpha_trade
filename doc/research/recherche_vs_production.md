# Recherche, backtest et production

## Trois environnements logiques

| Environnement | But | Autorité |
|---|---|---|
| exploration | formuler/tester rapidement une hypothèse | aucune promotion implicite |
| validation | protocole gelé, OOS/walk-forward, baseline | décision documentée |
| production | servir le contrat approuvé sur données disponibles | code, configuration et artefacts runtime |

Un script de recherche cohérent peut utiliser un lifecycle, un univers ou des
labels différents de la production. Ses résultats ne diagnostiquent pas
automatiquement le système live.

## Contrat à comparer

Univers et dates disponibles ; features/labels/horizons ; batch, modèle,
calibration et cascade ; timing d’entrée et intrabar ; stop, TP, trailing,
time-stop et gap filter ; sizing/coûts/contraintes ; corporate actions et prix
ajustés ; fallbacks et gates.

Une différence matérielle doit être nommée, puis le diagnostic rejoué sous le
contrat cible avant optimisation.

## Chemin de promotion

1. hypothèse et journal d’expérience ;
2. synthèse des résultats positifs et négatifs ;
3. recheck sous contrat production ;
4. validation OOS et robustesse ;
5. parité/replay ;
6. promotion contrôlée avec rollback ;
7. monitoring.

Voir [expériences](../experiences/README.md),
[validation ML](../ml/validation_et_gouvernance.md),
[backtesting](../backtesting/README.md) et
[Oracle historique](../ml/oracle/06_diagnostics_et_historique.md).

