# IHM Streamlit — architecture et services

Retour : [IHM et opérations](../16_ihm_et_operations.md)

`ihm/app.py` configure page, navigation, thème et contexte compte. Les pages rendent ; les services chargent données et construisent commandes. Une règle métier ne doit pas être dupliquée dans un composant Streamlit.

`pipeline_runner.py` définit les 14 étapes, `PipelineOptions`, dépendances, tables et builders de commandes. `pipeline_lock.py` évite les runs concurrents ; `process_registry.py` suit PID, sorties et rotation. `ops_runner.py` exécute les commandes avec capture stdout/stderr.

Les services DB/queries utilisent cache Streamlit avec TTL adapté. Après mutation, invalider le cache concerné. Les préférences (screener, capital, notifications, fractional) sont distinctes de la config runtime transmise ; afficher les valeurs effectives.

Les pages ne doivent jamais considérer l'absence de rows comme succès. Afficher date, compte, run id, statut et erreurs. Pour Execution live, confirmation et préflight restent dans le backend canonique même si l'IHM les prépare.

