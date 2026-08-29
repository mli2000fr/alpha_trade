# Réconciliation, reprise et TCA

Retour : [références Execution](README.md)

`broker_state_sync.py` photographie compte, positions et ordres. `reconciliation.py` compare interne/broker ; `reconcile_statement.py` ajoute les relevés. Les écarts portent sur symboles, côtés, quantités, ordres, fills, protections, cash et lots.

Procédure de reprise : geler entrées, lire broker, rechercher client ids, importer observations/fills, reconstruire positions/lots, restaurer protections, puis rapprocher cash. Le broker est vérité d'exécution ; la base garde la preuve et doit converger.

`tca.py` calcule l'écart orienté entre référence et fill, latence et agrégats. Achat plus cher/vente moins chère sont défavorables. Séparer slippage des non-fills et du coût d'opportunité.

Tolérances fractionnaires doivent être explicites. Un écart critique non résolu empêche de déclarer le run sain.

