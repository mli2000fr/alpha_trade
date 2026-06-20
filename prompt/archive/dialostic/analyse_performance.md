1) Règle du jeu : ce qu’on ne touche pas
Sur les 5 runs, tu gardes strictement identiques :
fenêtre : 2020-01-01 → 2020-12-31
equity : 2000
preset de base : capital_0_2000
compte : cash
allow_fractional_shares = true
mêmes phases :
phase2 = risk_execution
phase3 = execution_replay
phase4 = protection_replay
phase5 = watcher_replay
phase7 = exit_lifecycle_replay
même branche / même dataset si possible
L’idée est de faire du one-factor-at-a-time.
 
2) Les 5 backtests à relancer
BT0 — Contrôle / réplication
But
Recréer un run le plus proche possible du run analysé, pour avoir une base propre de comparaison.
Commande
python -m backtesting run `
  --start 2020-01-01 `
  --end 2020-12-31 `
  --equity 2000 `
  --capital-preset-key capital_0_2000 `
  --engine-mode pipeline `
  --ml-mode rebuild-missing `
  --ml-pit-strategy rebuild-missing `
  --account-type cash `
  --cash-settlement-days 1 `
  --allow-fractional-shares `
  --max-positions 3 `
  --phase2-mode risk_execution `
  --phase3-mode execution_replay `
  --phase4-mode protection_replay `
  --phase5-mode watcher_replay `
  --phase7-mode exit_lifecycle_replay `
  --output-dir artifacts/ablation/bt0_control
Ce que tu attends
un résultat proche de :
perf ~ -0.6%
win rate ~ 36.7%
profit factor ~ 0.82
peu de vraies fractions
run ML encore possiblement dégradé
 
BT1 — ML explicitement coupé
But
Mesurer le comportement sentiment-only assumé, sans ambiguïté.
Différence vs BT0
seule différence : --ml-mode off
Commande
python -m backtesting run `
  --start 2020-01-01 `
  --end 2020-12-31 `
  --equity 2000 `
  --capital-preset-key capital_0_2000 `
  --engine-mode pipeline `
  --ml-mode off `
  --account-type cash `
  --cash-settlement-days 1 `
  --allow-fractional-shares `
  --max-positions 3 `
  --phase2-mode risk_execution `
  --phase3-mode execution_replay `
  --phase4-mode protection_replay `
  --phase5-mode watcher_replay `
  --phase7-mode exit_lifecycle_replay `
  --output-dir artifacts/ablation/bt1_ml_off
Lecture
Si BT1 ≈ BT0, alors :
ton run initial se comportait déjà quasiment comme un run sans ML.
Si BT1 est nettement pire que BT0, alors :
même dégradé, le ML résiduel/fallback faisait encore un peu de boulot.
 
BT2 — ML reconstruit avec gate dur
But
Mesurer le vrai effet de la restauration du ML.
Différence vs BT0
on garde le ML
on force un niveau minimal de couverture pour invalider tout run “dégradé acceptable”
Commande
python -m backtesting run `
  --start 2020-01-01 `
  --end 2020-12-31 `
  --equity 2000 `
  --capital-preset-key capital_0_2000 `
  --engine-mode pipeline `
  --ml-mode rebuild-missing `
  --ml-pit-strategy rebuild-missing `
  --min-ml-coverage-ratio 0.95 `
  --account-type cash `
  --cash-settlement-days 1 `
  --allow-fractional-shares `
  --max-positions 3 `
  --phase2-mode risk_execution `
  --phase3-mode execution_replay `
  --phase4-mode protection_replay `
  --phase5-mode watcher_replay `
  --phase7-mode exit_lifecycle_replay `
  --output-dir artifacts/ablation/bt2_ml_restored
Si ce run échoue sur la couverture ML
Dans ce cas, ne l’interprète pas : il faut d’abord réparer la donnée / reconstruction ML.
Commande de préchauffage possible si ton parser l’expose bien comme dans la CLI :
python -m backtesting backfill-scores-history `
  --start 2020-01-01 `
  --end 2020-12-31 `
  --capital 2000
Puis tu relances BT2.
Lecture
Si BT2 >> BT0 : le ML manquant est un facteur majeur
Si BT2 ~ BT0 : le vrai problème n’est probablement pas le ML, ou pas seulement
 
BT3 — Régime OFF
But
Isoler ce que coûtent :
capital_preservation
cash_only
les blocages par régime
Différence vs BT0
Tu ne changes que la bascule globale du régime dans config.yaml.
Patch à faire dans config.yaml
Dans la section market_regimes :
market_regimes:
  enabled: false
Dans ton fichier actuel, c’est la ligne-clé la plus importante à modifier.
Exécution
Une fois config.yaml temporairement mis à enabled: false, tu relances exactement le run contrôle :
python -m backtesting run `
  --start 2020-01-01 `
  --end 2020-12-31 `
  --equity 2000 `
  --capital-preset-key capital_0_2000 `
  --engine-mode pipeline `
  --ml-mode rebuild-missing `
  --ml-pit-strategy rebuild-missing `
  --account-type cash `
  --cash-settlement-days 1 `
  --allow-fractional-shares `
  --max-positions 3 `
  --phase2-mode risk_execution `
  --phase3-mode execution_replay `
  --phase4-mode protection_replay `
  --phase5-mode watcher_replay `
  --phase7-mode exit_lifecycle_replay `
  --output-dir artifacts/ablation/bt3_regime_off
Lecture
Si BT3 améliore fortement la perf et surtout :
augmente le nombre d’entrées acceptées
réduit les périodes sous-investies
fait monter l’exposition moyenne
alors :
le principal frein est bien le régime.
Si en plus le DD reste raisonnable, tu as une piste très claire : régime trop conservateur.
 
BT4 — Sizing up, sans toucher au régime
But
Tester si le moteur a de l’edge mais ne le monétise pas assez, à cause d’un sizing trop faible.
Différence vs BT0
Tu ne touches qu’au sizing du preset micro-compte, pas au régime.
Patch minimal à faire dans config/capital_presets.yaml
Dans le preset capital_0_2000, change uniquement :
risk_per_trade_pct: 0.01
en
risk_per_trade_pct: 0.015
Je te recommande de ne rien changer d’autre sur ce run pour garder un test propre.
Exécution
python -m backtesting run `
  --start 2020-01-01 `
  --end 2020-12-31 `
  --equity 2000 `
  --capital-preset-key capital_0_2000 `
  --engine-mode pipeline `
  --ml-mode rebuild-missing `
  --ml-pit-strategy rebuild-missing `
  --account-type cash `
  --cash-settlement-days 1 `
  --allow-fractional-shares `
  --max-positions 3 `
  --phase2-mode risk_execution `
  --phase3-mode execution_replay `
  --phase4-mode protection_replay `
  --phase5-mode watcher_replay `
  --phase7-mode exit_lifecycle_replay `
  --output-dir artifacts/ablation/bt4_sizing_up
Lecture
Si BT4 améliore la perf sans trop dégrader le DD :
il y avait bien un problème de sous-dimensionnement
Si BT4 ne change presque rien :
le sous-dimensionnement n’est pas le moteur principal, ou il est écrasé par le régime
Si BT4 augmente surtout le DD sans améliorer le PF :
les signaux ne sont pas assez bons pour supporter plus de levier économique
 
3) Le tableau de lecture : comment conclure proprement
A. Effet du ML manquant
À comparer :
BT1 (ml_off)
BT0 (control)
BT2 (ml_restored)
Conclusion type
BT1 ≈ BT0 et BT2 > BT0
→ le run initial était déjà quasi sans ML, et la perte de ML coûte vraiment
BT1 < BT0 mais BT2 ≈ BT0
→ il reste un peu de signal utile même en mode dégradé
BT2 ne passe pas la gate
→ pas de conclusion ML valide tant que la couverture n’est pas réparée
 
B. Effet du régime
À comparer :
BT3 (regime_off)
BT0 (control)
Conclusion type
BT3 améliore nettement perf + exposition + nb de trades
→ le régime est le frein principal
BT3 augmente seulement le DD sans améliorer la perf
→ le régime te protège d’un mauvais moteur d’entrée
BT3 améliore tout légèrement
→ régime trop serré, mais pas unique cause
 
C. Effet du sous-dimensionnement
À comparer :
BT4 (sizing_up)
BT0 (control)
Conclusion type
BT4 améliore perf avec DD tolérable
→ vrai sujet de sous-dimensionnement
BT4 ne change presque rien
→ le frein vient d’abord de la sélection / du régime
BT4 dégrade beaucoup le DD
→ le sizing n’est pas le bon bouton à pousser tant que les entrées restent fragiles
 
4) Les métriques à relever à chaque run
Je te conseille un tableau à 10 colonnes :
Run
Return %
CAGR %
Max DD %
Sharpe
Profit Factor
Win Rate %
Total Trades
ML coverage
Exposition moyenne
Où les prendre
Dans report.json
summary.total_return_pct
summary.cagr_pct
summary.max_drawdown_pct
summary.sharpe_ratio
summary.profit_factor
summary.win_rate_pct
summary.total_trades
Dans report.json > fidelity.coverage.ml
coverage_ratio_after
Dans trade_audit_log.csv
moyenne de gross_exposure_after_pct
ou au minimum distribution de entry_cost
Dans phase2_risk_summary.json
entries_accepted
entries_blocked_by_regime
regime_mode_distribution
 
5) Ordre conseillé d’exécution
Pour éviter de perdre du temps :
BT0 — contrôle
BT1 — ML off
BT2 — ML restored + gate
si ça casse, tu t’arrêtes et tu répares la couverture ML
BT3 — régime off
BT4 — sizing up
 
6) Ce que j’attends comme issue la plus probable dans ton cas
Vu le diagnostic du run actuel, mon scénario central est :
BT1 proche de BT0
→ le run actuel est déjà presque sentiment-only
BT2 meilleur que BT0 si la couverture ML est réparée
→ le ML manquant est un vrai problème
BT3 meilleur que BT0
→ le régime bride trop l’exposition
BT4 améliore un peu, mais moins que BT3
→ le sous-dimensionnement existe, mais il est probablement secondaire par rapport au régime + qualité signal
 
7) Recommandation finale
Si tu veux un plan ultra propre, ton ablation prioritaire est :
ML : BT0 / BT1 / BT2
Régime : BT0 / BT3
Sizing : BT0 / BT4
Ça te donne en 5 runs une lecture suffisamment nette pour décider :
est-ce qu’il faut d’abord réparer la donnée ML
ou desserrer le régime
ou augmenter le sizing
Si tu veux, je peux maintenant te préparer un tableau de suivi prêt à remplir avec les colonnes exactes et les hypothèses associées à chaque run.