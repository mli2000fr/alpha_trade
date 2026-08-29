# Glossaire

| Terme | Définition dans Alpha Trade |
|---|---|
| ADV | volume moyen quotidien, souvent converti en dollars pour la capacité |
| ATR | Average True Range, mesure de volatilité utilisée pour stops et sizing |
| Batch | run d'entraînement/version cohérente d'artefacts ML |
| Buying power | capacité d'achat déclarée par le broker ; différente du cash |
| Capital preservation | régime défensif réduisant les risques/entrées |
| Champion | modèle publié et autorisé pour l'inférence |
| Challenger | modèle évalué contre le champion/baseline |
| Conviction | transformation normalisée des sorties ML pour le risque |
| Corporate action | dividende, split ou événement affectant position/cash |
| Cross-sectionnel | calcul comparant les symboles à une même date |
| Decision rank | ordre final des positions acceptées |
| Effective trade date | première séance où une information peut être utilisée |
| Extreme gate | filtre du top percentile quotidien de `proba_extreme` |
| Fill | exécution confirmée par le broker |
| Fingerprint | empreinte de contrat, features, données ou décision |
| Flat | classe ternaire sans prise de position directionnelle |
| Gross exposure | somme des expositions absolues long et short |
| IC Rank | corrélation de Spearman entre score/rang et résultat futur |
| IEX | feed Alpaca gratuit partiel, source potentielle de biais de volume/spread |
| Lifecycle | règles complètes entrée, protections, sorties et observation |
| MAE/MFE | excursion adverse/favorable maximale d'un trade |
| Net exposure | exposition long moins exposition short |
| O0 | Oracle Extreme sans Global Rank comme feature |
| OOS | out-of-sample, période non utilisée pour ajuster le modèle |
| Oracle Extreme | modèle du potentiel de mouvement extrême, non directionnel |
| PIT | point-in-time : uniquement l'information disponible à la date |
| Portfolio target | position souhaitée produite par le risque |
| `proba_extreme` | probabilité/score d'extrême, jamais `P(LONG)` |
| Run summary | résumé structuré et versionné d'une exécution de module |
| Selection rank | ordre ML avant contraintes portefeuille |
| Sleeve | compartiment de budget/exposition, par exemple long ou short |
| TCA | Transaction Cost Analysis |
| Time-stop | sortie après une durée maximale, seulement si effective dans le contrat |
| Tradable universe `full` | snapshot complet et publié des symboles admissibles |
| Triple barrier | méthode de label future ; pas automatiquement un exit live |
| Walk-forward | succession de trains passés et tests futurs chronologiques |
| Watcher | processus post-run surveillant protections et positions |

