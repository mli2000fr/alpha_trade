# 1. Vérifier les variables d'environnement
python run_execution.py check

# 2. Menu interactif (aucun argument)
python run_execution.py

# 3. Simulation pure — aucun ordre envoyé
python run_execution.py simulate
python run_execution.py simulate --date 2026-04-18
python run_execution.py simulate --run-id abc123def4567890
python run_execution.py simulate --debug        # logs détaillés

# 4. Paper trading (argent fictif Alpaca)
python run_execution.py paper
python run_execution.py paper --date 2026-04-18
python run_execution.py paper --run-id abc123def4567890

# 5. Live trading (argent réel — demande confirmation)
python run_execution.py live --run-id abc123def4567890



Ce que chaque mode fait différemment
Mode
Ordres Alpaca
Horaires marché
Throttle
Usage
simulate
❌ aucun
ignorés
désactivé
test & debug
paper
✅ paper API
respectés
350 ms
validation
live
✅ live API
respectés
350 ms
production