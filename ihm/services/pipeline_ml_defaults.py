"""Constantes ML par défaut pour l'IHM Pipeline — Sprint S12.

Extrait de ``pipeline_runner.py`` pour réduire la taille de ce dernier
et faciliter la maintenance des paramètres ML.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# ML train — cible swing cash + walk-forward
# ---------------------------------------------------------------------------
DEFAULT_ML_TARGET_MODE = "regression"
DEFAULT_ML_FORECAST_HORIZON = 0               # 0 = tous les horizons (3,5,10,15,20)
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
DEFAULT_ML_WF_STEP_SIZE = 252
DEFAULT_ML_WF_MAX_SPLITS = 8
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
DEFAULT_ML_TRAINING_START_DATE = "2016-01-01"
DEFAULT_ML_TRAINING_END_DATE = "2024-06-30"
DEFAULT_ML_INCLUDE_SCREENER_SCORES = False
DEFAULT_ML_INCLUDE_SENTIMENT = False          # Sentiment news — horizon court, non adapté au swing J+10
DEFAULT_ML_INCLUDE_SHORT_SCORE = True
DEFAULT_ML_INCLUDE_MACRO_VIX = False          # VIX/VIX9D — macro vol S&P 500
DEFAULT_ML_INCLUDE_MACRO_VXN = False          # VXN — macro vol NASDAQ-100
DEFAULT_ML_INCLUDE_MACRO_VIX3M = False        # VIX3M — term structure vol
DEFAULT_ML_INCLUDE_MACRO_MOVE = False         # MOVE — macro vol obligataire
DEFAULT_ML_INCLUDE_FUNDAMENTALS = False     # EODHD fundamentals (PE, ROE, marges, croissance)
DEFAULT_ML_INCLUDE_FACTORS = True          # CAPM factor exposures (beta, alpha, R² via rolling 252j)
DEFAULT_ML_INCLUDE_VOLUME_FEATURES = False  # P3-5 : profil volume/liquidité (10 features opt-in)
DEFAULT_ML_INCLUDE_MACRO_REGIME = False      # SPY_SMA_200_slope + VIX_zscore (macro regime indicators)
DEFAULT_ML_INCLUDE_SCORE_COMPONENTS = False  # P0-6 : composants stock_scores_history (sentiment_net_agg, company_idio_score...)
DEFAULT_ML_GLOBAL_MODEL_ONLY = False  # P0-6 : skip per-symbol & per-sector, ne faire que le global
# 2026-08-28 : Exclude per-symbol & per-sector — saute l'entraînement par ticker/secteur
# mais GARDE le Global Ranking et l'Oracle Extreme si activés. COCHÉ PAR DÉFAUT.
DEFAULT_ML_EXCLUDE_PER_SYMBOL_PER_SECTOR = True
DEFAULT_ML_ENABLE_ORACLE_MODEL = True  # 2026-08-20 : entraîne AUSSI le modèle Oracle Extreme (O0 sans global_rank_20)
DEFAULT_ML_ORACLE_MODEL_ONLY = False    # 2026-08-20 : entraîne UNIQUEMENT l'Oracle Extreme — skip global, per-symbol, per-sector
DEFAULT_ML_TARGET_SKIP_VOL_SCALING = False   # T1 experiment: désactiver le vol-scaling (target = future_return brut)
DEFAULT_ML_TARGET_EXCESS_VS_SPY = True      # P0-7 : target = (future_return - spy_return) / vol20 – centre la distribution
DEFAULT_ML_TARGET_INTRA_SECTOR_RANK = False  # T2 experiment: target = rang percentile intra-secteur [0,1]
DEFAULT_ML_TARGET_THRESHOLD_TERNARY_INTRA_SECTOR = False  # T3 experiment: ternary classification intra-sector
DEFAULT_ML_TARGET_THRESHOLD_TERNARY_QUANTILE = 0.30  # T3: top/bottom quantile for LONG/SHORT
DEFAULT_ML_PREDICT_MAX_DATE_WORKERS = 4  # nb de dates traitées en parallèle lors du predict historique
DEFAULT_ML_ENABLE_LIGHTGBM = False             # challenger LightGBM activé par défaut
DEFAULT_ML_ENABLE_CATBOOST = False             # challenger CatBoost activé par défaut
DEFAULT_ML_ENABLE_GLOBAL_MODEL = True        # Global Ranking Model
DEFAULT_ML_ENABLE_GLOBAL_STACKING = False   # Stacking global_rank comme feature (défaut OFF — cascade ML)
DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER = False  # DÉSACTIVÉ — le ranking ne participe pas au championnat
DEFAULT_ML_GLOBAL_CHAMPION = True           # Entraîne CatBoost + LightGBM → sélection champion (IC rank WF)
DEFAULT_ML_GLOBAL_MODEL_NAME = "catboost"     # Sprint 2026-08-01 v4 : CatBoost RMSE continu (pas de discrétisation)
DEFAULT_ML_ENABLE_CROSS_SECTIONAL = False     # features cross-sectionnelles + sectorielles
DEFAULT_ML_INCLUDE_DIRECTIONAL_FEATURES = True  # 2026-08-23 : liste restreinte 'direction' (sous-ensemble des features cross-sectionnelles/sectorielles, ~17 features au lieu de ~49)
DEFAULT_ML_SELECT_CHAMPION = False             # champion selection activée
DEFAULT_ML_OPTIMIZE_THRESHOLDS = False         # optimization des seuils de décision
DEFAULT_ML_OPTIMIZE_TARGET = False            # target optimization (supervisée)
DEFAULT_ML_CROSS_SECTIONAL_MIN_UNIVERSE = 20
DEFAULT_ML_CALIBRATION_MIN_SAMPLES = 64
DEFAULT_ML_CALIBRATION_MAX_ITER = 100
DEFAULT_ML_LGBM_MAX_DEPTH = 5  # 6→5 (Sprint 2026-08-01 v2)
DEFAULT_ML_LGBM_N_ESTIMATORS = 200
DEFAULT_ML_LGBM_LEARNING_RATE = 0.03  # 0.05→0.03 (Sprint 2026-08-01)
DEFAULT_ML_CATBOOST_DEPTH = 6
DEFAULT_ML_CATBOOST_ITERATIONS = 300
DEFAULT_ML_CATBOOST_LEARNING_RATE = 0.03
DEFAULT_ML_RANKING_TOP_K_FEATURES = 0       # 0 = toutes les features (feature selection désactivée)
DEFAULT_ML_GLOBAL_RANKING_MAX_SYMBOLS = 0  # 0 = pas de limite, >0 = top N par volume
DEFAULT_ML_PER_SYMBOL_MAX_SYMBOLS = 0  # 0 = pas de limite, >0 = top N premiers symboles

# ---------------------------------------------------------------------------
# LightGBM tuning (optionnel — activé par checkbox IHM)
# ---------------------------------------------------------------------------
DEFAULT_ML_LGBM_TUNING_ENABLED = True
DEFAULT_ML_LGBM_REG_ALPHA = 0.1
DEFAULT_ML_LGBM_REG_LAMBDA = 0.1
DEFAULT_ML_LGBM_MIN_CHILD_SAMPLES = 150  # 50→150 (Sprint 2026-08-01, Mid Caps)
DEFAULT_ML_LGBM_SUBSAMPLE = 0.8
DEFAULT_ML_LGBM_COLSAMPLE_BYTREE = 0.7  # 0.8→0.7 (Sprint 2026-08-01)

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
DEFAULT_ML_CATBOOST_LOSS_FUNCTION = "YetiRank"  # "RMSE", "YetiRank", "QueryRMSE", etc.
# ---------------------------------------------------------------------------
# Filtrage liquidité (Sprint 2026-07-24)
# ---------------------------------------------------------------------------
DEFAULT_ML_ENABLE_LIQUIDITY_FILTER = False
# 1. Taille de l'entreprise (Filtre de Classe d'Actifs)
DEFAULT_ML_LIQUIDITY_MIN_MARKET_CAP = 500_000_000  # 500 Millions $ (Élimine Small/Micro Caps — bruit microstructurel tuant H3)
DEFAULT_ML_LIQUIDITY_MAX_MARKET_CAP = 20_000_000_000   # 20 Milliards $ (Élimine les Large/Mega Caps)   # 0 = pas de limite
# 2. Liquidité & Exécution (Filtres de Friction)
DEFAULT_ML_LIQUIDITY_MIN_AVG_VOLUME_20D = 50_000  # 250k actions/j (Évite les pièges sur titres chers)
DEFAULT_ML_LIQUIDITY_MAX_AVG_HIGH_LOW_RANGE_PCT = 5.0  # 5.0% d'amplitude High-Low quotidienne moyenne max (pas le spread bid-ask)
DEFAULT_ML_LIQUIDITY_MIN_DAILY_DOLLAR_VOLUME = 10_000_000  # 10.0M $ / jour  (Garantit un volume institutionnel)
# Filtres de Structure
DEFAULT_ML_LIQUIDITY_MIN_PRICE = 10.0  # $10 min, élimine penny stocks
# Filtre spread bid-ask réel (stock_quote_snapshots.spread_bps)
DEFAULT_ML_LIQUIDITY_MAX_SPREAD_BPS = 40.0  # 40 bps = 0.40% de spread bid-ask max (0 = désactivé)
DEFAULT_ML_LIQUIDITY_SPREAD_FALLBACK_MODE = "warn_only"  # "pass" | "reject" | "warn_only"
DEFAULT_ML_LIQUIDITY_SPREAD_MAX_QUOTE_AGE_DAYS = 5  # âge max d'une quote spread

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
