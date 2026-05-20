# 6. Page 🤖 ML / Prédictions — comprendre le modèle d'IA

## À quoi sert cette page

Voir et gérer les **modèles de Machine Learning** qui prédisent la
probabilité qu'une action monte de +2 % dans les 5 jours suivants.

## Concepts clés (en 2 minutes)

### Qu'est-ce qu'un « modèle » ?

Un programme qui a **appris** sur un historique borné par une **date de début
de training** (par défaut `2020-01-01`) à reconnaître les
patterns annonciateurs de hausses. À chaque nouvelle journée, il regarde
les caractéristiques (prix, volume, indicateurs techniques…) et donne une
**probabilité** entre 0 et 1.


Le modèle peut aussi utiliser un **contexte selector** : rang candidat,
mode de signal (`strict`, `sector_neutralized`), blackout earnings, etc.
Ce contexte peut servir soit comme **feature supplémentaire**, soit comme
**filtre d'univers** pour décider quels symboles seront réellement entraînés
ou scorés sur le run courant.

### Champion-challenger

L'application entraîne **plusieurs** modèles en parallèle (LSTM, LightGBM,
CatBoost). Le meilleur sur la **période de validation** est sacré
**champion** ; les autres restent **challengers**. À chaque ré-entraînement,
le champion peut changer.

### Walk-forward

Plutôt que de couper l'historique en 1 train + 1 test, on découpe en N
fenêtres glissantes (ex. train 504 jours → val 126 → test 126, on glisse
de 126 jours, etc.). C'est la meilleure défense contre l'**overfitting**
(le modèle qui a appris « par cœur » mais qui ne généralise pas).

## Sections de la page

### Section 1 — Runs d'entraînement

Tableau historique : pour chaque run vous voyez `run_id`, date, mode
(`rebuild-all` / `rebuild-missing` / `refresh-stale`), date de début du
training, modèle
champion, métriques (AUC, precision_long…).

### Section 2 — Prédictions du dernier run

Pour chaque candidat : `probability_long`, `decision` (`long` / `flat`).
Triable par probabilité.

La page affiche maintenant aussi un résumé de l'**univers ML selector-driven**
porté par les artefacts :

- features selector activées ou non ;
- `selector_signal_mode` autorisés ;
- `candidate_rank` maximum éventuel ;
- exclusion éventuelle des titres en `earnings_blackout`.

### Section 3 — Métriques de validation

Graphiques : AUC, precision/recall, calibration. Comprendre :
- **AUC** ∈ [0.5, 1.0] : 0.5 = aléatoire, 0.65 = bon, 0.75+ = excellent.
- **precision_long** : % de prédictions « long » qui se sont avérées
  gagnantes.
- **action_rate** : % de candidats classés `long`.

## Quand relancer un entraînement

| Situation | Mode recommandé |
|---|---|
| Première installation | `rebuild-all` (long, 30+ min) |
| Routine quotidienne | `refresh-stale` (rapide) |
| Drift détecté (AUC qui chute) | `rebuild-missing` |
| Changement de paramètres ML | `rebuild-all` |

> ⚠️ Un `rebuild-all` peut prendre 30 min à 2 h selon votre machine. Faites-le
> le soir.

## Pièges courants pour débutants

- ❌ « Mon modèle a 90 % de précision en backtest, je passe en live » →
  c'est presque toujours de l'overfitting. Vérifiez d'abord en
  [paper trading](08_page_execution.md) pendant 4 semaines minimum.
- ❌ « Je relance un rebuild-all chaque jour » → consomme énormément de
  CPU/GPU pour rien. Une fois par semaine suffit.
- ❌ « Le champion change tous les jours » → c'est normal, ne pas s'inquiéter.
- ❌ « J'active un filtre d'univers selector puis j'oublie qu'il réduit le scope ML » →
  toujours vérifier dans la page ML le résumé `Univers ML selector-driven`
  avant d'interpréter un nombre faible de symboles entraînés ou scorés.

## Pour un micro-compte 2 000 €

Le ML est **utile mais pas indispensable** pour démarrer. Si l'entraînement
est trop lent sur votre machine, vous pouvez désactiver les steps 9-10 dans
les options du Pipeline. Le `final_score` du Selector seul suffit pour
tester. Voir [20_gestion_petit_capital_2000eur.md](20_gestion_petit_capital_2000eur.md).

## Pour aller plus loin

- Détails techniques : [doc/modelFactory.md](../modelFactory.md).
- Backtester avec/sans ML : [10_page_backtesting.md](10_page_backtesting.md).

