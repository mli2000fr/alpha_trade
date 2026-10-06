# Page Batch — périmètres US, CN et FR séparés

5 octobre 2026. Workflow & Orchestration → Batch → **Périmètre des batchs** :
États-Unis (US), Chine (CN), France (FR). US reste le défaut ; l'ancien choix
US/CN combiné est ramené vers US pour les sessions déjà ouvertes.

Les trois vues utilisent le même rendu : cinq compteurs, recherche, priorités,
filtre d'état, compte Windows Interactive/System, actualisation, installation
globale, désinstallation globale, cartes, commandes et journaux. Les filtres
d'affichage ne limitent pas l'action « tous » : elle concerne le catalogue
du **marché sélectionné**, pas les autres marchés. Les tâches en cours sont
ignorées et seules les sections activées sont proposées à l'installation.
Une famille sans launcher raccordé ne peut pas être exécutée par substitution US.

## Sources et isolation

- US : sections US de `batch.yaml`, historique SQL de collecte US.
- CN : `batch_cn.yaml` et quatre sections CN historiques de `batch.yaml`,
  restées à leur emplacement pour ne pas reconfigurer les tâches existantes.
  La séparation est logique dans l'IHM ; ce changement ne migre pas ces sections.
  Doublon de nom entre les catalogues CN = erreur visible. Les familles
  CN déclarées sans launcher raccordé sont visibles mais non installables/exécutables.
  Derniers runs des jobs raccordés lus dans leurs ledgers CN, pas dans SQL US.
- FR : `batch_fr.yaml`, rapports fichiers sous `artifacts/fr/operations/runs`.
  Aucun historique SQL US consulté. Les restrictions recherche restent visibles.

Les compteurs d'exécution active et les actions installer/désinstaller sont
limités aux noms des batchs du marché choisi. Les lancements CN/FR ne reçoivent
pas les identifiants DB runtime US depuis la page. Les boutons ne changent
ni source, ni calendrier, ni notifications, ni droits des collecteurs.

Aucune tâche Windows n'a été modifiée par cette évolution. Aucun SQL/migration
n'est nécessaire. Tests : partition réelle des catalogues, mêmes contrôles
sur trois rendus Streamlit, absence de lecture SQL US en CN/FR, boutons globaux
limités au marché, migration du sélecteur et non-régressions Batch/FR/CN.
