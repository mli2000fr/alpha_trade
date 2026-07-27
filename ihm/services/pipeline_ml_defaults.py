"""Constantes ML par défaut pour l'IHM Pipeline — Sprint S12.

Extrait de ``pipeline_runner.py`` pour réduire la taille de ce dernier
et faciliter la maintenance des paramètres ML.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# ML train — cible swing cash + walk-forward
# ---------------------------------------------------------------------------
DEFAULT_ML_TARGET_MODE = "ternary"
DEFAULT_ML_FORECAST_HORIZON = 5              # 10 jours = horizon swing étendu (TODO-5)
DEFAULT_ML_TARGET_UP_THRESHOLD = 0.03        # +3.0 % cible long
DEFAULT_ML_TARGET_DOWN_THRESHOLD = -0.03     # -3.0 % cible short
DEFAULT_ML_TERNARY_WEIGHT_SHORT = 1.0
DEFAULT_ML_TERNARY_WEIGHT_FLAT = 1.0
DEFAULT_ML_TERNARY_WEIGHT_LONG = 1.0
DEFAULT_ML_TERNARY_THRESHOLD_SHORT = 0.35
DEFAULT_ML_TERNARY_THRESHOLD_LONG = 0.35
DEFAULT_ML_TERNARY_TOP2_MARGIN = 0.02
DEFAULT_ML_DECISION_THRESHOLD = 0.55
DEFAULT_ML_CALIBRATION_METHOD = "platt"
DEFAULT_ML_FEATURE_SET = "expert"
DEFAULT_ML_MAX_WORKERS = 6
DEFAULT_ML_MAX_EPOCHS = 50
DEFAULT_ML_PATIENCE = 5            # early stopping LSTM (source unique: modelFactory.config.DEFAULT_PATIENCE)
DEFAULT_ML_MODE = "rebuild-all"
DEFAULT_ML_WALKFORWARD = True                # walk-forward activé par défaut en swing prod
DEFAULT_ML_WF_MIN_TRAIN_SIZE = 504
DEFAULT_ML_WF_VAL_SIZE = 126
DEFAULT_ML_WF_TEST_SIZE = 126
DEFAULT_ML_WF_STEP_SIZE = 126
DEFAULT_ML_WF_MAX_SPLITS = 11
DEFAULT_ML_LOG_LEVEL = "INFO"
DEFAULT_ML_DEBUG_TRAIN = False
DEFAULT_ML_HEARTBEAT_INTERVAL_SECONDS = 60.0
DEFAULT_ML_WATCHDOG_TIMEOUT_SECONDS = 0

# ---------------------------------------------------------------------------
# Presets recommandés
# ---------------------------------------------------------------------------
RECOMMENDED_ML_PROD_SWING_ACCELERATOR = "auto"
RECOMMENDED_ML_PROD_SWING_LOG_LEVEL = DEFAULT_ML_LOG_LEVEL
RECOMMENDED_ML_PROD_SWING_DEBUG_TRAIN = DEFAULT_ML_DEBUG_TRAIN
RECOMMENDED_ML_PROD_SWING_MAX_WORKERS = DEFAULT_ML_MAX_WORKERS
RECOMMENDED_ML_PROD_SWING_WALKFORWARD = DEFAULT_ML_WALKFORWARD
RECOMMENDED_ML_PROD_SWING_MAX_EPOCHS = DEFAULT_ML_MAX_EPOCHS
RECOMMENDED_ML_PROD_SWING_HEARTBEAT_INTERVAL_SECONDS = DEFAULT_ML_HEARTBEAT_INTERVAL_SECONDS
RECOMMENDED_ML_PROD_SWING_WATCHDOG_TIMEOUT_SECONDS = DEFAULT_ML_WATCHDOG_TIMEOUT_SECONDS
RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR = "cpu"
RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL = "DEBUG"
RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN = True
RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS = 1
RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD = False
RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS = 10
RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS = 30.0
RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS = 300
RECOMMENDED_ML_DEBUG_GPU_ACCELERATOR = "gpu"
RECOMMENDED_ML_DEBUG_GPU_LOG_LEVEL = RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL
RECOMMENDED_ML_DEBUG_GPU_DEBUG_TRAIN = RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN
RECOMMENDED_ML_DEBUG_GPU_MAX_WORKERS = RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS
RECOMMENDED_ML_DEBUG_GPU_WALKFORWARD = RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD
RECOMMENDED_ML_DEBUG_GPU_MAX_EPOCHS = RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS
RECOMMENDED_ML_DEBUG_GPU_HEARTBEAT_INTERVAL_SECONDS = RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS
RECOMMENDED_ML_DEBUG_GPU_WATCHDOG_TIMEOUT_SECONDS = RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS

# ---------------------------------------------------------------------------
# Garde-fous d'inférence
# ---------------------------------------------------------------------------
DEFAULT_ML_MIN_ACTION_RATE = 0.03
DEFAULT_ML_MAX_ACTION_RATE = 0.20            # plus prudent que 0.35 backend
DEFAULT_ML_MIN_PRECISION_LONG = 0.55         # plus exigeant que 0.52 backend

# ---------------------------------------------------------------------------
# Hyperparamètres avancés (alignés CLI modelFactory)
# ---------------------------------------------------------------------------
DEFAULT_ML_SEQUENCE_LENGTH = 40
DEFAULT_ML_BATCH_SIZE = 32
DEFAULT_ML_HIDDEN_SIZE = 256
DEFAULT_ML_ARTIFACTS_DIR = "artifacts/models"
DEFAULT_ML_BENCHMARK_SYMBOL = "SPY"
DEFAULT_ML_DEFAULT_CHAMPION = "lstm_attention"
DEFAULT_ML_TRAINING_START_DATE = "2018-01-01"
DEFAULT_ML_TRAINING_END_DATE = "2025-12-31"
DEFAULT_ML_INCLUDE_SCREENER_SCORES = False
DEFAULT_ML_INCLUDE_SENTIMENT = False          # Sentiment news — horizon court, non adapté au swing J+10
DEFAULT_ML_INCLUDE_SHORT_SCORE = True
DEFAULT_ML_INCLUDE_MACRO_VIX = False          # VIX/VIX9D — macro vol S&P 500
DEFAULT_ML_INCLUDE_MACRO_VXN = False          # VXN — macro vol NASDAQ-100
DEFAULT_ML_INCLUDE_MACRO_VIX3M = False        # VIX3M — term structure vol
DEFAULT_ML_INCLUDE_MACRO_MOVE = True         # MOVE — macro vol obligataire
DEFAULT_ML_INCLUDE_FUNDAMENTALS = False     # EODHD fundamentals (PE, ROE, marges, croissance)
DEFAULT_ML_INCLUDE_FACTORS = True          # CAPM factor exposures (beta, alpha, R² via rolling 252j)
DEFAULT_ML_INCLUDE_MACRO_REGIME = True      # SPY_SMA_200_slope + VIX_zscore (macro regime indicators)
DEFAULT_ML_ENABLE_LIGHTGBM = True             # challenger LightGBM activé par défaut
DEFAULT_ML_ENABLE_CATBOOST = True             # challenger CatBoost activé par défaut
DEFAULT_ML_ENABLE_GLOBAL_MODEL = True        # Global Ranking Model (stacking uniquement)
DEFAULT_ML_ENABLE_GLOBAL_STACKING = False   # Stacking global_rank comme feature (défaut OFF — cascade ML)
DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER = False  # DÉSACTIVÉ — le ranking ne participe pas au championnat
DEFAULT_ML_GLOBAL_MODEL_NAME = "lightgbm"     # type de GlobalModel par défaut
DEFAULT_ML_ENABLE_CROSS_SECTIONAL = True     # features cross-sectionnelles + sectorielles
DEFAULT_ML_SELECT_CHAMPION = True             # champion selection activée
DEFAULT_ML_OPTIMIZE_THRESHOLDS = False         # optimization des seuils de décision
DEFAULT_ML_OPTIMIZE_TARGET = False            # target optimization (supervisée)
DEFAULT_ML_CROSS_SECTIONAL_MIN_UNIVERSE = 20
DEFAULT_ML_CALIBRATION_MIN_SAMPLES = 64
DEFAULT_ML_CALIBRATION_MAX_ITER = 100
DEFAULT_ML_LGBM_MAX_DEPTH = 4
DEFAULT_ML_LGBM_N_ESTIMATORS = 200
DEFAULT_ML_LGBM_LEARNING_RATE = 0.05
DEFAULT_ML_CATBOOST_DEPTH = 6
DEFAULT_ML_CATBOOST_ITERATIONS = 300
DEFAULT_ML_CATBOOST_LEARNING_RATE = 0.03
DEFAULT_ML_RANKING_TOP_K_FEATURES = 0       # 0 = toutes les features (feature selection désactivée)
DEFAULT_ML_GLOBAL_RANKING_MAX_SYMBOLS = 0  # 0 = pas de limite, >0 = top N par volume

# ---------------------------------------------------------------------------
# LightGBM tuning (optionnel — activé par checkbox IHM)
# ---------------------------------------------------------------------------
DEFAULT_ML_LGBM_TUNING_ENABLED = True
DEFAULT_ML_LGBM_REG_ALPHA = 0.1
DEFAULT_ML_LGBM_REG_LAMBDA = 0.1
DEFAULT_ML_LGBM_MIN_CHILD_SAMPLES = 50
DEFAULT_ML_LGBM_SUBSAMPLE = 0.8
DEFAULT_ML_LGBM_COLSAMPLE_BYTREE = 0.8

# ---------------------------------------------------------------------------
# CatBoost tuning (optionnel — activé par checkbox IHM)
# ---------------------------------------------------------------------------
DEFAULT_ML_CATBOOST_TUNING_ENABLED = True
DEFAULT_ML_CATBOOST_L2_LEAF_REG = 3.0
DEFAULT_ML_CATBOOST_BORDER_COUNT = 128
DEFAULT_ML_CATBOOST_RANDOM_STRENGTH = 1.0
DEFAULT_ML_CATBOOST_BAGGING_TEMPERATURE = 1.0
DEFAULT_ML_CATBOOST_OD_TYPE = "IncToDec"
DEFAULT_ML_CATBOOST_OD_WAIT = 20
# ---------------------------------------------------------------------------
# Filtrage liquidité (Sprint 2026-07-24)
# ---------------------------------------------------------------------------
DEFAULT_ML_ENABLE_LIQUIDITY_FILTER = False
DEFAULT_ML_LIQUIDITY_MIN_AVG_VOLUME_20D = 500_000
DEFAULT_ML_LIQUIDITY_MIN_MARKET_CAP = 500_000_000.0
DEFAULT_ML_LIQUIDITY_MAX_AVG_SPREAD_PCT = 0.5

# ---------------------------------------------------------------------------
# Grilles candidate (resserrées swing 2-10 j)
# ---------------------------------------------------------------------------
DEFAULT_ML_CANDIDATE_HORIZONS: tuple[int, ...] = (3, 5, 7, 10)
DEFAULT_ML_CANDIDATE_UP_THRESHOLDS: tuple[float, ...] = (0.015, 0.02, 0.03)
DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS: tuple[float, ...] = (-0.01, -0.015)
DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS: tuple[float, ...] = (0.55, 0.60, 0.65)
DEFAULT_ML_MIN_TRADES_FRACTION = 0.15

# ---------------------------------------------------------------------------
# CatBoost — vérification de disponibilité (Sprint S12)
# ---------------------------------------------------------------------------

def is_catboost_available() -> bool:
    """Vérifie si CatBoost est installé et importable.

    À utiliser dans l'IHM pour griser l'option si non disponible.
    """
    try:
        import catboost  # noqa: F401
        return True
    except ImportError:
        return False
