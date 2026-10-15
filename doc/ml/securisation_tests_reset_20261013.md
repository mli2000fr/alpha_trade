# Sécurisation des tests de réinitialisation — 13 octobre 2026

Pendant la validation du raccordement Oracle parcours, un ancien test de
`tests/test_ml_reset.py` a appelé le service de reset avec un moteur SQL factice
mais **sans rediriger PROJECT_ROOT**. Sur ce poste Windows, la racine était
réellement `F:/projets`. Ce test a pu supprimer les répertoires présents de son
catalogue (historiques IHM, caches et résultats dérivés ML). Le SQL du test était
simulé ; cela ne rendait pas ses opérations fichiers/processus inoffensives.
Les données sources et `artifacts/research/us_oracle_annual_models/20261013-v1`
ne font pas partie de ce catalogue ; les neuf rapports y sont toujours présents.

## Attribution des trois modèles

L'annonce initiale attribuant au test la suppression des trois nouveaux modèles
était erronée. `log/batch_delete_audit.log` indique pour `f62825`, `f1b59f` et
`9be3d2` un nettoyage **effectif depuis Diagnostics ML**, processus 15284,
`cleanup_batches:rmtree`, à **16:50:27 UTC = 18:50:27 Paris**. Le test non isolé
a été lancé vers **19:42 Paris**, donc après leur suppression. Les quatre tables
de registre/prédiction contrôlées ensuite sont vides ; aucune copie des trois
modèles n'est dans la sauvegarde ML du 10 octobre, antérieure à leur création.
Ne pas restaurer automatiquement de vieux modèles contre l'intention de nettoyage.

Pour les autres répertoires du catalogue, aucun inventaire immédiatement antérieur
au test ne permet d'attribuer précisément tous les fichiers manquants. Il ne faut
ni affirmer qu'aucun historique n'a été perdu, ni inventer un contenu restauré.
Aucune restauration ni aucun réentraînement n'a été lancé dans ce contrôle.

## Correctifs

- Fixture automatique : racine temporaire pour **tous** les tests de reset.
- Listes de processus réels neutralisées ; toute tentative de les arrêter fait
  échouer le test.
- Le test de suppression redirige explicitement le service sur ses faux dossiers.
- Garde dans le service : sous pytest, un reset non simulé visant la racine du
  projet réel est refusé **avant** ouverture SQL, arrêt de processus ou suppression.
- Un `dry_run` n'arrête plus de processus réels.

Les sources, SQL, backups existants et rapports de recherche ne sont pas effacés
pour vérifier ces garde-fous. Les suites futures doivent demeurer hermétiques.
