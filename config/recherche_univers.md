# Inventaire des sélecteurs d'univers IHM

Date de l'audit : 2026-08-30.

## Objectif

Remplacer l'option IHM statique `ticket-recherche`, historiquement liée à
`config/ticket_recherche.txt`, par la découverte dynamique des fichiers `.txt`
présents dans `config/univers/`. Les autres sources existantes doivent rester
disponibles. Le premier fichier, trié par nom, devient l'univers fichier par
défaut.

## Sélecteurs identifiés

Neuf listes déroulantes sont concernées :

1. Pipeline — ML Train.
2. Pipeline — ML Predict.
3. Pipeline — Sync Latest Quotes.
4. Pipeline — Sync Earnings Calendar.
5. Fondamentaux — population/rafraîchissement.
6. Backtesting — backfill `stock_scores_history`.
7. Backtesting — calibration sentiment.
8. Backtesting — walk-forward sentiment.
9. Composant Swing Score — calcul manuel sur un univers.

## Emplacements

- `ihm/pages/pipeline.py` : constantes partagées et blocs ML/Data Integrity.
- `ihm/pages/fundamentals.py` : sélecteur, prévisualisation et lancement.
- `ihm/pages/backtesting/__init__.py` : trois sélecteurs.
- `ihm/components/swing_score.py` : rendu du sélecteur Swing Score.
- `ihm/services/swing_score.py` : options et résolution Swing Score.
- `modelFactory/db_registry.py` : chargement historique codé en dur de
  `config/ticket_recherche.txt`.
- `modelFactory/cli.py` : validation statique des valeurs de `--symbol-source`.
- `database/selector_reference.py` : résolution commune utilisée par les outils
  Data Integrity.

## Cas associé hors liste déroulante

`ihm/pages/_execution_center/__init__.py` impose encore
`ml_train_symbol_source = "ticket-recherche"`. Ce défaut doit être raccordé au
premier fichier découvert pour rester cohérent avec la nouvelle règle.

## Répertoire constaté pendant l'audit

- `ticket_mid_cap_400.txt`
- `ticket_recherche.txt`
- `univers_filtred_2016.txt`

Avec un tri alphabétique déterministe, `ticket_mid_cap_400.txt` est le premier
fichier et devient donc le défaut.

## Architecture retenue

- Une fonction transversale découvre et trie les fichiers `.txt` de
  `config/univers/`.
- Les valeurs transportées entre l'IHM et les CLI utilisent l'identifiant
  `universe-file:<nom-du-fichier>.txt`.
- Le chargeur accepte les symboles séparés par virgules ou par lignes, ignore
  les commentaires et les entrées vides, normalise en majuscules et déduplique.
- Le chemin est validé afin d'interdire toute sortie de `config/univers/`.
- L'ancien identifiant `ticket-recherche` reste un alias de compatibilité, mais
  ne pointe plus vers `config/ticket_recherche.txt` : il résout le premier
  fichier dynamique.
- Si aucun fichier valide n'existe, une erreur explicite est remontée au lieu de
  sélectionner silencieusement un univers incorrect.

## Adaptation de Diagnostic ML et du schéma

`model_training_batch.symbol_source` conserve l'identifiant complet
`universe-file:<nom>.txt` afin que chaque batch reste attribuable à sa source.
La colonne doit être en `VARCHAR(255)` ; la migration est fournie dans
`database/sql/ml/alter_model_training_batch_symbol_source.sql`.

Dans la table et la fiche détaillée de Diagnostic ML, l'IHM retire seulement le
préfixe technique et affiche le nom lisible du fichier. La valeur persistée en
base n'est pas modifiée par ce formatage.
