from database.connection import get_sqlalchemy_engine
import pandas as pd

e = get_sqlalchemy_engine()

# Predictions 2018-2019
p = pd.read_sql_query(
    "SELECT MIN(prediction_date) as min_d, MAX(prediction_date) as max_d, COUNT(1) as cnt "
    "FROM model_predictions "
    "WHERE prediction_date BETWEEN '2018-01-01' AND '2019-12-31'",
    e
)
print("model_predictions 2018-2019:", p.iloc[0].to_dict())

# All predictions
p2 = pd.read_sql_query(
    "SELECT MIN(prediction_date) as min_d, MAX(prediction_date) as max_d, COUNT(1) as cnt "
    "FROM model_predictions",
    e
)
print("model_predictions ALL:", p2.iloc[0].to_dict())

# Win rates
m = pd.read_sql_query(
    "SELECT COUNT(1) as cnt FROM model_metrics m "
    "JOIN model_training_run t ON m.run_id = t.run_id "
    "WHERE t.status = 'completed' AND m.directional_accuracy IS NOT NULL",
    e
)
print("win_rates:", m.iloc[0, 0])

# Scores 2018-2019
s = pd.read_sql_query(
    "SELECT MIN(snapshot_date) as min_d, MAX(snapshot_date) as max_d, COUNT(1) as cnt "
    "FROM stock_scores_history "
    "WHERE snapshot_date BETWEEN '2018-01-01' AND '2019-12-31'",
    e
)
print("scores 2018-2019:", s.iloc[0].to_dict())

# Bars 2018-2019
b = pd.read_sql_query(
    "SELECT MIN(date) as min_d, MAX(date) as max_d, COUNT(1) as cnt "
    "FROM stock_bars_daily "
    "WHERE date BETWEEN '2018-01-01' AND '2019-12-31'",
    e
)
print("bars 2018-2019:", b.iloc[0].to_dict())
