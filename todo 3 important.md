TODO-3, retester model oracle exterme, et/ou combiner model global, model global ensuite filtrer avec model oracle exterme


A1-A7 sans --include-directional-features
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --global-model-only --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --global-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8  --training-start-date 2011-01-01 --training-end-date 2020-12-31 --comment "Baseline A1 2020-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --global-model-only --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --global-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8  --training-start-date 2012-01-01 --training-end-date 2021-12-31 --comment "Baseline A2 2021-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --global-model-only --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --global-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8  --training-start-date 2013-01-01 --training-end-date 2022-12-31 --comment "Baseline A3 2022-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --global-model-only --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --global-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8  --training-start-date 2014-01-01 --training-end-date 2023-12-31 --comment "Baseline A4 2023-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --global-model-only --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --global-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8  --training-start-date 2015-01-01 --training-end-date 2024-12-31 --comment "Baseline A5 2024-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --global-model-only --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --global-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8  --training-start-date 2016-01-01 --training-end-date 2025-12-31 --comment "Baseline A6 2025-12-31"


// delete
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2014-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2019-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "A1 B25 2019-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2014-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2020-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "A2 B25 2020-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2015-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2021-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "A3 B25 2021-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2015-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2022-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "A4 B25 2022-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2023-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "A5 B25 2023-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2024-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "A6 B25 2024-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "A7 B25 2025-12-31"
B1-B7 avec --include-directional-features
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2014-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2019-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --include-directional-features --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B1 B25 2019-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2014-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2020-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --include-directional-features --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B2 B25 2020-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2015-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2021-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --include-directional-features --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B3 B25 2021-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2015-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2022-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --include-directional-features --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B4 B25 2022-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2023-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --include-directional-features --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B5 B25 2023-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2024-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --include-directional-features --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B6 B25 2024-12-31"
python -u -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --global-model-only --enable-global-model --include-short-score --include-factors --include-directional-features --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B7 B25 2025-12-31"

A1 B25 2019-12-31
    - entrainnement: 
    - predit: 
    - backtest 2020
A2 B25 2020-12-31
    - entrainnement: 
    - predit: 
    - backtest 2021
A3 B25 2021-12-31
    - entrainnement: 
    - predit: 
    - backtest 2022
A4 B25 2022-12-31
    - entrainnement: 
    - predit: 
    - backtest 2023
A5 B25 2023-12-31
    - entrainnement: 
    - predit: 
    - backtest 2024
A6 B25 2024-12-31
    - entrainnement: 
    - predit: 
    - backtest 2025
A7 B25 2025-12-31
    - entrainnement: 
    - predit: 
    - backtest 2026

B1 B25 2019-12-31
    - entrainnement: 
    - predit: 
    - backtest 2020
B2 B25 2020-12-31
    - entrainnement: 
    - predit: 
    - backtest 2021
B3 B25 2021-12-31
    - entrainnement: 
    - predit: 
    - backtest 2022
B4 B25 2022-12-31
    - entrainnement: 
    - predit: 
    - backtest 2023
B5 B25 2023-12-31
    - entrainnement: 
    - predit: 
    - backtest 2024
B6 B25 2024-12-31
    - entrainnement: 
    - predit: 
    - backtest 2025
B7 B25 2025-12-31
    - entrainnement: 
    - predit: 
    - backtest 2026




























VERIFIER: dans le artifact/model, si ces features sont bien present dedans après l'entrainnement !!!! vérifier aussi dans predit sils sont bien utilisés (ainsi skp bien calculé, voicl'ano suivant)
J'ai identifié un écart de parité critique. Vérifions la cause exacte : dans compute_features, si benchmark_df est None, alors relative_strength_20/60/5, regime_bull_market, regime_risk_off, market_* sont mis à 0.0. Or :
Entraînement (train_global_ranking_wf) : charge benchmark_df quand feature_set == "expert" ✓
Prédiction (predict_global_rank) : les 2 appelants (predict_global_rank_history et _try_compute_global_rank_for_prediction) appellent sans benchmark_df ✗
Conséquence pour la liste direction : relative_strength_20, relative_strength_60, sector_relative_strength_20 et leurs *_xs_rank / *_sector_neutral seraient dégradés (0.0 / rangs à 0.5) en prédiction. Je vérifie ce que contient le metadata pour lire le benchmark_symbol, et je corrige predict_global_rank pour charger le benchmark.

En mode direction, il faut charger le benchmark même si feature_set != "expert" (car relative_strength_* sont dans la liste direction). Je corrige la condition pour inclure le mode direction.
Le chemin _prepare_prediction_frame (per-symbol / Global Model tabulaire) n'utilise pas les *_xs_rank (le Global Model tabulaire a ses propres features cross-symbol). La liste direction concerne le Global Ranking, dont le predict est predict_global_rank — qui fait bien la normalisation xs_rank. Je vérifie les erreurs de compilation sur les fichiers modifiés.
Maintenant je dois vérifier un point critique supplémentaire dans le chemin predict per-symbol _prepare_prediction_frame : la normalisation xs_rank. Dans predict_global_rank (le chemin Global Ranking — le bon pour c68b36), elle est faite. Mais vérifions si _prepare_prediction_frame (utilisé pour les modèles per-symbol) calcule aussi les *_xs_rank — sinon si un modèle per-symbol utilisait des features direction, elles manqueraient.
Point important : _prepare_prediction_frame (chemin per-symbol / Global Model tabulaire) ne calcule pas les *_xs_rank — mais ce chemin n'est pas utilisé pour le Global Ranking (c68b36 est un batch Global Ranking, dont le predict passe par predict_global_rank, qui fait bien la normalisation xs_rank). Le Global Model tabulaire utilise ses propres features cross-symbol, sans conflit.

Réponse : vérification de la parité prédiction vs entraînement
J'ai audité le calcul des 17 features "direction" côté prédiction, et j'ai trouvé et corrigé un écart de parité important.

✅ Les 4 étapes de calcul sont identiques entre train et predict (Global Ranking)
Pour le batch c68b36 (Global Ranking Model), le predict passe par predict_global_rank, qui reproduit exactement la même séquence que train_global_ranking_wf :

Étape	Entraînement	Prédiction
1. Benchmark	chargé si feature_set=="expert"	chargé si expert/direction (corrigé, voir ci-dessous)
2. Cross-sectional	build_cross_sectional_features(..., sector_map, feature_subset)	idem via metadata (flag sauvegardé)
3. Normalisation *_xs_rank	groupby("date").rank(pct=True)	idem (_XS_RANK_SOURCE_FEATURES)
4. Sector-neutral	_compute_sector_neutral_inplace	idem
🐛 Bug de parité corrigé : le benchmark manquait en prédiction
En vérifiant, j'ai découvert que compute_features met relative_strength_20/60/5, regime_*, market_* à 0.0 quand benchmark_df is None. Or :

L'entraînement charge le benchmark (feature_set=="expert")
Mais les 2 appelants predict (predict_global_rank_history et _try_compute_global_rank) appelaient predict_global_rank sans benchmark_df
→ Conséquence directe pour la liste direction : relative_strength_20, relative_strength_60, sector_relative_strength_20 et leurs dérivés (relative_strength_20/60_xs_rank, relative_strength_20_sector_neutral) étaient dégradés à 0.0 / rangs neutres en prédiction.

Corrections apportées :

predict_global_rank : charge désormais le benchmark SPY sur la plage de universe_df si benchmark_df is None et que le modèle en a besoin (expert / cross-sectional / direction)
Metadata : ajout de benchmark_symbol dans _global_ranking_features.json pour recharger le bon symbole
_prepare_prediction_frame (predictor) : la condition de chargement du benchmark inclut le mode direction
⚠️ Note de périmètre
_prepare_prediction_frame (chemin per-symbol / Global Model tabulaire) ne calcule pas la normalisation *_xs_rank — c'est normal, ce chemin n'est pas utilisé pour le Global Ranking (le predict c68b36 passe par predict_global_rank). Le Global Model tabulaire utilise ses propres features cross-symbol, sans conflit avec la liste direction.








stock_vs_sector_ret_20, stock_vs_sector_ret_60, momentum_20_sector_neutral, relative_strength_20_sector_neutral, stock_vs_sector_ret_5, sector_relative_strength_20, sector_ret_20, sector_ret_60, sector_ret_5, relative_strength_20_xs_rank, relative_strength_60_xs_rank, momentum_20_xs_rank, momentum_60_xs_rank, momentum_10_xs_rank, momentum_5_xs_rank, momentum_120_xs_rank, range_position_20_xs_rank

 avec ces features:
our ton problème précis — le modèle sait repérer les extrêmes, mais confond parfois futur TOP10 et futur BOTTOM10 — je classerais les features cross-sectional disponibles par potentiel pour apprendre le signe futur, pas simplement l'amplitude.

Classement prioritaire
Rang	Feature	Priorité	Pourquoi pour UP vs DOWN
1	stock_vs_sector_ret_20	⭐⭐⭐⭐⭐	Momentum spécifique au titre en retirant une grosse partie du mouvement sectoriel.
2	stock_vs_sector_ret_60	⭐⭐⭐⭐⭐	Même idée sur tendance plus lente ; utile pour distinguer leader/laggard structurel.
3	relative_strength_20_rank	⭐⭐⭐⭐⭐	Position relative récente du titre dans tout l'univers. Très directement liée au signe du momentum relatif.
4	ret_20_rank	⭐⭐⭐⭐⭐	Dit explicitement si le titre appartient aux gagnants/perdants récents de l'univers.
5	relative_strength_60_rank	⭐⭐⭐⭐⭐	Confirmation plus lente de la force/faiblesse relative.
6	ret_60_rank	⭐⭐⭐⭐⭐	Permet notamment de distinguer tendance persistante et mouvement récent isolé.
7	momentum_20_sector_neutral	⭐⭐⭐⭐⭐	Très intéressant : momentum propre au titre après retrait de l'effet secteur.
8	relative_strength_20_sector_neutral	⭐⭐⭐⭐⭐	Même logique : force relative idiosyncratique plutôt que simple bêta sectoriel.
9	stock_vs_sector_ret_5	⭐⭐⭐⭐	Signal court terme. Potentiellement utile pour détecter une accélération ou détérioration récente.
10	sector_relative_strength_20	⭐⭐⭐⭐	Donne le vent sectoriel dans lequel évolue l'action.
11	sector_ret_20	⭐⭐⭐⭐	Direction intermédiaire du secteur.
12	sector_ret_60	⭐⭐⭐⭐	Régime directionnel plus lent du secteur.
13	sector_ret_5	⭐⭐⭐	Contexte très court terme ; probablement plus bruité.
14	range_position_20_rank	⭐⭐⭐	Peut différencier un titre qui tient ses hauts d'un titre qui se dégrade.
15	autres momentum/RS sector-neutral disponibles	⭐⭐⭐	Potentiellement utiles si leur horizon apporte une information réellement différente.

J’ai comparé la liste réelle de ton batch (164 features) avec les 15 features directionnelles que je t’avais proposées. Point important : ton batch possède déjà beaucoup de ranks cross-sectionnels (*_xs_rank), même si le metadata indique enable_cross_sectional: false.

Comparaison exacte
#	Feature directionnelle proposée	Dans ton batch ?	Équivalent présent ?	Mon avis
1	stock_vs_sector_ret_20	❌	—	MANQUE — très intéressant
2	stock_vs_sector_ret_60	❌	—	MANQUE — très intéressant
3	relative_strength_20_rank	⚠️ nom différent	relative_strength_20_xs_rank	✅ déjà présent
4	ret_20_rank	⚠️	rolling_mean_return_20_xs_rank + momentum_20_xs_rank	✅ largement couvert
5	relative_strength_60_rank	⚠️	relative_strength_60_xs_rank	✅ déjà présent
6	ret_60_rank	⚠️	momentum_60_xs_rank	✅ couvert
7	momentum_20_sector_neutral	❌	—	MANQUE — très intéressant
8	relative_strength_20_sector_neutral	❌	—	MANQUE — très intéressant
9	stock_vs_sector_ret_5	❌	—	MANQUE
10	sector_relative_strength_20	❌	—	MANQUE
11	sector_ret_20	❌	—	MANQUE
12	sector_ret_60	❌	—	MANQUE
13	sector_ret_5	❌	—	MANQUE
14	range_position_20_rank	⚠️ nom différent	range_position_20_xs_rank	✅ déjà présent
15	autres momentum/RS sector-neutral	❌	—	MANQUE

Donc, sur les 14 features concrètement nommées, ton batch en couvre déjà environ 5, et il lui manque surtout toute la famille sector-relative / sector-neutral.

Et c'est précisément cette famille qui m'intéresse le plus pour ton problème.

Ce que ton modèle possède déjà

Tu as déjà une quantité importante d'information directionnelle cross-universe :

momentum_3_xs_rank, momentum_5_xs_rank, momentum_10_xs_rank, momentum_20_xs_rank, momentum_60_xs_rank, momentum_120_xs_rank, momentum_250_xs_rank, ainsi que relative_strength_20_xs_rank, relative_strength_60_xs_rank, les ranks SMA/EMA, RSI, etc.

Donc je corrige légèrement mon diagnostic précédent : ton modèle n'est absolument pas dépourvu d'information cross-sectionnelle.

Il en a déjà beaucoup.

Ce qui lui manque principalement, c'est une deuxième dimension de comparaison : le secteur.

Les features manquantes que je testerais

Pour ton problème :

predicted TOP10 contient parfois les vrais futurs BOTTOM10

je ne rajouterais surtout pas les 49 features de --enable-cross-sectional aveuglément.

Je testerais en priorité seulement ceci :

Tier A — priorité maximale

stock_vs_sector_ret_20
stock_vs_sector_ret_60
momentum_20_sector_neutral
relative_strength_20_sector_neutral

Tier B — ensuite

stock_vs_sector_ret_5
sector_relative_strength_20
sector_ret_20
sector_ret_60

Tier C — probablement secondaire

sector_ret_5

Pourquoi ?

Ton modèle sait déjà répondre à quelque chose comme :

« NVDA est-elle forte par rapport aux 400 actions ? »

avec momentum_20_xs_rank, relative_strength_20_xs_rank, etc.

Mais il lui manque davantage la question :

« NVDA est-elle forte parce que tout son secteur monte, ou est-elle réellement forte relativement aux autres actions du même secteur ? »

C'est potentiellement très important pour éviter certains faux TOP.

Et il y a quelque chose de très intéressant dans ton fichier

Ton batch a :

enable_cross_sectional: false

mais contient néanmoins une grosse famille de *_xs_rank.

Cela indique probablement que tes 164 features "expert" construisent déjà des ranks XS indépendamment du flag --enable-cross-sectional.

Donc je ne ferais surtout pas :

B25 + --enable-cross-sectional → automatiquement meilleur.

Tu risques essentiellement de rajouter beaucoup de variables redondantes.

Le test que je donnerais à ton IA

Je ferais plutôt une ablation extrêmement propre :

OBJECTIF
Réduire la contamination :
P(realized BOTTOM10 | predicted TOP10)

Ne PAS optimiser uniquement l'IC moyen.

BASELINE
Batch actuel = 164 features.

TEST A
Baseline + uniquement :
- stock_vs_sector_ret_20
- stock_vs_sector_ret_60
- momentum_20_sector_neutral
- relative_strength_20_sector_neutral

TEST B
TEST A +
- stock_vs_sector_ret_5
- sector_relative_strength_20
- sector_ret_20
- sector_ret_60

TEST C
Baseline + --enable-cross-sectional complet
(contrôle uniquement, pour savoir si les 49 features apportent
plus que le sous-ensemble directionnel)

Et je demanderais par horizon H5/H10/H15/H20 :

IC Rank, TOP10 mean forward return, BOTTOM10 mean forward return, TOP-BOTTOM spread, % predicted TOP10 réellement futur BOTTOM10, % predicted TOP10 avec forward return < 0, % predicted BOTTOM10 réellement futur TOP10, et stabilité de ces métriques par split WF.

Cette dernière partie est essentielle : ton batch actuel a déjà un problème de stabilité temporelle. Par exemple H10 est excellent sur certains splits mais l'IC CatBoost devient −0,0127 sur le split correspondant à 2022 ; H20 descend à −0,0156 sur ce même type de période.

Donc notre objectif ne devrait pas être simplement :

IC 0,0296 → 0,032 = victoire.

Je préférerais largement quelque chose comme :

IC 0,0296 → 0,0290, mais contamination TOP→BOTTOM 12 % → 5 % et meilleure stabilité entre régimes.

Ça répondrait beaucoup plus directement au défaut que tu cherches à corriger.
































Après cela, je descendrais fortement en priorité les variables du genre volatilité, dollar volume, volume, liquidité, taille du secteur, etc. Elles peuvent améliorer le modèle globalement, mais répondent beaucoup moins directement à ta question « cet extrême sera-t-il positif ou négatif ? ». Les features cross-sectional mélangent effectivement plusieurs familles, notamment momentum, volatilité, volume, liquidité, secteur et variables neutralisées.

Il y a cependant quelque chose d'encore plus important : je ne mettrais pas automatiquement les 15 premières dans un nouveau modèle. Je commencerais par un petit noyau, par exemple les 8 premières. Ton B25 contient déjà beaucoup de features ; ajouter 49 variables pour résoudre un problème de signe risque d'ajouter beaucoup plus de bruit que d'information.

Le test que je trouve particulièrement intéressant serait donc B25 vs B25 + TOP8 directionnelles vs B25 + les 49 XS. Et surtout, ne choisis pas le gagnant sur l'IC global uniquement : ta métrique n°1 devrait être P(realized BOTTOM10 | predicted TOP10). Si le TOP8 fait par exemple passer cette contamination de 15 % à 8 %, même avec un IC global presque inchangé, ce serait une amélioration très pertinente pour ton système.

Dernière réserve : ce classement est un prior théorique, pas une preuve empirique que stock_vs_sector_ret_20 sera réellement n°1 sur tes données. Le test WF/OOS doit décider l'ordre réel.


-----------------------------------------------------------------------------------------




retour GPT:
le rank global sait repérer des titres “importants / extrêmes / relativement forts”, mais il laisse encore entrer dans son TOP10% des titres qui finissent réellement dans le BOTTOM10% des rendements futurs. C’est un problème de contamination du TOP par des faux positifs directionnels, pas juste un problème de marché haussier ou baissier.

En pratique, il faut mesurer directement ce taux de contamination :

P(future_rank <= 10% | predicted_rank >= 90%)

et son symétrique utile :

P(future_rank >= 90% | predicted_rank >= 90%)

Si, même en BULL, ton TOP10 prédit contient beaucoup de futurs BOTTOM10, alors le modèle a un problème de séparation des queues : il sait détecter “quelque chose va se passer”, mais pas assez bien si c’est la bonne direction relative.

--enable-cross-sectional peut aider, mais ce n’est pas garanti. Les features cross-sectionnelles peuvent améliorer la notion de “leader vs laggard” relative, donc elles peuvent réduire cette contamination. Mais le bon test n’est pas seulement l’IC global : il faut comparer XS OFF vs XS ON sur une matrice de confusion des extrêmes.

Je demanderais à ton IA de produire, pour chaque version du modèle et par régime :

parmi le TOP10 prédit, % qui finit futur TOP10, TOP20, middle, BOTTOM20, BOTTOM10 ;
parmi le BOTTOM10 prédit, même chose ;
contamination extrême : % predicted TOP10 → realized BOTTOM10 ;
pureté extrême : % predicted TOP10 → realized TOP10 ;
spread moyen futur TOP10 prédit vs random ;
idéalement la même analyse en 2025 validation et 2026 vrai OOS.

Le test vraiment décisif est :

XS ON réduit-il nettement TOP10 → BOTTOM10 sans dégrader TOP10 → TOP10 ?

Si oui, c’est exactement le type d’amélioration que tu cherches.

Si non, alors le problème est probablement plus profond que les features : la target/loss actuelle ne pénalise pas assez les erreurs catastrophiques de queue. Un ranker pairwise peut être bon en moyenne tout en laissant passer quelques inversions extrêmes.

Dans ce cas, je verrais deux pistes propres : garder le global rank comme étage 1, puis ajouter un veto directionnel qui cherche uniquement à éliminer les candidats à forte probabilité de finir dans le bottom futur ; ou revoir la target pour mieux séparer les extrêmes signés.

La première est souvent plus propre : au lieu de demander au ranker de tout faire, tu gardes son talent pour trouver les meilleurs candidats, puis tu filtres seulement les TOP contaminés.

Si tu veux, je peux te rédiger une spec de test très précise pour mesurer cette contamination TOP10 prédit → BOTTOM10 réalisé et comparer XS ON/OFF sans overfitter.


---------------
En regardant la liste complète, je vois plusieurs familles qui peuvent potentiellement aider ton problème précis : éviter qu’un titre qui finira réellement dans le BOTTOM10 se retrouve dans le TOP10 prédit. Et certaines me paraissent plus pertinentes que d’autres.

Le point de départ est important : --enable-cross-sectional ajoute déjà ~49 features de rangs intra-date, sectorielles, sector-neutral et z-scores sectoriels. C’est utile pour mieux positionner chaque titre relativement à l’univers, mais ça ne suffit pas forcément à éliminer les faux TOP extrêmes.

1. Les features que je testerais en priorité pour la direction

A. Screener scores — probablement la meilleure piste déjà disponible. Tu as notamment selector_trend_score, selector_weekly_trend_score, selector_high_52w_proximity, selector_normalized_rsi, selector_relative_strength_index_neutralized, selector_trend_vcp_component et selector_total_score_neutralized. Celles-ci donnent de l’information explicitement orientée tendance/force relative, donc elles peuvent être utiles pour distinguer un vrai leader d’un titre simplement volatil. Elles sont bien disponibles dans Global Ranking.

Je les utiliserais surtout comme veto contre la contamination TOP→BOTTOM, pas nécessairement comme moteur principal du rank.

B. Volume directionnel. Dans les 10 features volume, plusieurs sont beaucoup plus intéressantes pour ton problème que la simple volatilité :

up_volume_ratio_20
volume_price_corr_20
obv_slope_20
éventuellement dollar_volume_trend_20_60

Ces features indiquent si le volume accompagne réellement les hausses ou les baisses. C’est très différent d’un ATR ou d’une volatilité, qui ne dit rien sur le signe.

Et tu as déjà une preuve historique intéressante : le batch B41 avec volume avait amélioré l’IC global et gagné sur les 5 horizons par rapport à B25. Donc ce n’est pas seulement une intuition théorique.

Pour ton problème, OBV slope + up-volume ratio + price-volume correlation sont probablement parmi les features les plus pertinentes de toute ta liste.

C. Score components idiosyncratiques. company_idio_score, company_idio_signal_norm, company_idio_component et sector_impact_agg sont intéressants parce qu’ils peuvent aider à distinguer :

mouvement parce que tout le secteur/marché bouge

de

mouvement réellement propre au titre.

Ces 9 score components sont maintenant disponibles dans Global Ranking après correction.

Pour éviter un futur BOTTOM10 dans ton TOP10, company_idio_* peut être particulièrement intéressant.

2. Une feature que j’utiliserais probablement comme veto négatif

selector_short_score.

Elle est disponible directement comme feature indépendante et correctement chargée dans Global Ranking.

Ton besoin n’est pas forcément de devenir excellent en short. Tu pourrais avoir une utilisation beaucoup plus simple :

Parmi les candidats TOP10 du global rank, short_score permet-il d’identifier les futurs BOTTOM10 ?

Autrement dit, pas :

short_score → faire des shorts

mais :

TOP global + short_score très mauvais → veto LONG

C’est beaucoup plus cohérent avec ce que tu cherches.

Je mesurerais directement :

P(realized BOTTOM10 | predicted TOP10, short_score élevé)

contre

P(realized BOTTOM10 | predicted TOP10, short_score faible).

Si tu trouves une séparation importante, tu as potentiellement un filtre anti-faux-TOP.

3. Les fondamentales : certaines oui, mais plutôt lentement directionnelles

Dans les 22 fondamentales, la plupart — PE, PB, EV/EBITDA, ROE, etc. — servent davantage à la qualité/valorisation qu’à une direction swing H20.

Mais trois me semblent plus intéressantes :

fund_eps_growth_yoy
fund_revenue_growth_yoy
surtout fund_estimate_revision

fund_estimate_revision = (eps_next - eps_current) / |eps_current|. C’est une information plus directement orientée amélioration/détérioration des attentes.

Pour un H20, estimate revision est probablement beaucoup plus intéressante pour la direction que PE ou PB.

4. Les facteurs : momentum_252_vs_market

Le Global Ranking conserve seulement momentum_252_vs_market; beta/alpha/R² sont blacklistés car ils avaient une importance nulle.

momentum_252_vs_market est directionnel en relatif :

le titre a-t-il surperformé le SPY sur 252 jours ?

Ça peut aider à éviter de mettre un laggard structurel dans le TOP10. Mais j’en attendrais moins que des features plus rapides comme stock_vs_sector_ret_20, OBV ou up-volume ratio.

5. Ce que je ne privilégierais PAS pour résoudre spécifiquement la direction

Les features VIX/VXN/VIX3M/MOVE donnent surtout l’état du marché, pas la direction spécifique du titre. Et surtout, dans Global Ranking elles sont blacklistées par design car elles sont communes à tous les symboles d’une date.

Même problème avec SPY_SMA_200_slope et VIX_zscore : potentiellement utiles au niveau régime, mais blacklistés en Global Ranking.

Donc je ne perdrais pas du temps à essayer de résoudre la contamination TOP→BOTTOM avec davantage de macro.

Mais il y a une piste potentiellement encore plus importante : le vol-scaling de la target

Tu as un flag très intéressant :

--target-skip-vol-scaling

Normalement :

target = excess_return / volatility_20

et avec le flag :

target = excess_return brut.

C’est exactement une chose que j’examinerais si tu soupçonnes que ton modèle favorise les gros movers plutôt que la bonne direction.

La division par la volatilité peut modifier fortement l’ordre des observations et faire apprendre au modèle une combinaison assez particulière de mouvement + vol.

Attention toutefois : la doc indique que ce flag concerne les modes de régression et pas directement le pipeline Global Ranking, dont la target est différente.

Donc si B25 est bien ton Global Ranking YetiRank, il faudra regarder la construction exacte de sa target plutôt que simplement activer ce flag.

Mon classement pour ton problème précis

Si la question est :

« Comment réduire les futurs BOTTOM10 présents dans mon TOP10 prédit ? »

Je testerais dans cet ordre :

Priorité	Famille	Pourquoi
1	--enable-cross-sectional	leader/laggard relatif, stock vs secteur
2	volume directionnel	OBV, up-volume, volume×price
3	screener trend/RS	confirmation de tendance
4	short_score comme veto LONG	détecter les faux TOP potentiellement baissiers
5	company_idio_ / sector impact*	séparer signal propre du mouvement commun
6	fund_estimate_revision	confirmation fondamentale directionnelle
7	momentum_252_vs_market	tendance relative longue

Je ne lancerais surtout pas un entraînement avec tout activé simultanément pour voir si ça gagne.

Je ferais plutôt une ablation propre :

B25 baseline
→ + XS
→ + volume directionnel
→ + screener trend/RS
→ éventuellement + score components

avec une métrique principale préfixée :

TOP10 contamination = % predicted TOP10 qui finit realized BOTTOM10

et en secondaire :

% predicted TOP10 → realized TOP10

L’amélioration idéale serait :

contamination TOP→BOTTOM ↓ fortement,
sans faire s’effondrer TOP→TOP ni le spread moyen.

Et surtout, je regarderais cette métrique avant le rendement du backtest. C’est le moyen le plus propre de savoir si les nouvelles features corrigent réellement ton problème de direction plutôt que simplement améliorer encore l’amplitude/ranking moyen.

--------------------
Exactement. Les ~49 features de --enable-cross-sectional ne sont pas 49 features directionnelles. Le flag mélange plusieurs familles, dont certaines servent surtout à contextualiser le titre ou mesurer l'amplitude. La documentation confirme cette composition.

Pour ton problème précis — empêcher qu'un futur BOTTOM10 soit classé dans le TOP10 prédit — je les séparerais ainsi :

Groupe	Exemples	Direction UP/DOWN ?	Intérêt pour ton problème
Rendement relatif	ret_20_rank, ret_60_rank	🟢 Fort	⭐⭐⭐⭐⭐
Force relative	relative_strength_20_rank, relative_strength_60_rank	🟢 Fort	⭐⭐⭐⭐⭐
Stock vs secteur	stock_vs_sector_ret_20, _60	🟢 Fort	⭐⭐⭐⭐⭐
Momentum sector-neutral	momentum_20_sector_neutral etc.	🟢 Fort	⭐⭐⭐⭐⭐
Tendance secteur	sector_ret_20, sector_ret_60, sector_relative_strength_20	🟢/🟡	⭐⭐⭐
Position dans range	range_position_20_rank	🟡	⭐⭐⭐
Volatilité	volatility_20_rank, sector_vol_20	🔴 Non	⭐
Liquidité	dollar_volume_20_rank, sector_dollar_volume_20	🔴 Non	⭐
Volume relatif	volume_ratio_20_rank_xs	🟡	⭐⭐
Taille groupe	sector_symbol_count	🔴 Non	—
Fundamentals neutralisés/z-score	PE, valuation, etc.	🟡/🔴	⭐–⭐⭐
Global ranks stacking	global_rank_3/5/10/...	dépend du modèle source	variable

Donc oui : je ne dirais surtout pas "49 nouvelles features directionnelles". Peut-être une dizaine à une quinzaine sont vraiment intéressantes pour ton problème.

Et il y a une subtilité encore plus importante

Prenons :

ret_20_rank = 0.95

Ça signifie essentiellement :

« Ce titre a récemment mieux performé que 95 % de l'univers. »

C'est directionnel historiquement, mais ce n'est pas forcément prédictif de la direction future.

Le titre peut ensuite :

continuer à monter → momentum ;
consolider ;
faire un reversal violent → futur BOTTOM10.

Donc même les features que je qualifie de directionnelles ne garantissent absolument pas que ton problème TOP→BOTTOM sera corrigé.

Ce que je demanderais réellement à ton IA

Je ne testerais pas simplement :

B25 + --enable-cross-sectional → IC meilleur ou non ?

Je lui donnerais plutôt cette consigne :

Analyse spécifiquement les ~49 features de --enable-cross-sectional et classe-les en 4 catégories :

directionnelles relatives stock : momentum, return rank, relative strength, stock-vs-sector ;
directionnelles contexte secteur ;
amplitude/volatilité/liquidité ;
fondamentales/contextuelles non directement directionnelles.

Puis entraîne/teste d'abord uniquement le sous-ensemble directionnel, si l'architecture permet de sélectionner les colonnes.

La métrique principale n'est PAS seulement IC Rank. Mesurer OOS/WF pour chaque date :

P(realized BOTTOM10 | predicted TOP10) = contamination catastrophique ;
P(realized TOP10 | predicted TOP10) = precision TOP10 ;
rendement moyen/médian du predicted TOP10 ;
fraction de rendements positifs dans predicted TOP10 ;
symétriquement P(realized TOP10 | predicted BOTTOM10) ;
spread TOP10−BOTTOM10.

Comparer :
B25 → B25 + XS complet → B25 + XS directionnel uniquement.

Ne retenir XS directionnel que s'il réduit significativement TOP10→BOTTOM10 sans détériorer fortement TOP10→TOP10 et le spread.

Ne pas modifier la PROD sur la base de l'IC global seul.

C'est à mon avis beaucoup plus propre que d'ajouter aveuglément 49 features.

Et ton intuition met probablement le doigt sur quelque chose d'important : si B25 est déjà bon pour détecter les extrêmes mais mélange parfois l'extrême positif et l'extrême négatif, ajouter encore des features de volatilité/amplitude peut même renforcer le mauvais comportement. Ce qu'on veut ajouter maintenant est surtout de l'information de signe, pas davantage d'information disant « ce titre va beaucoup bouger ».