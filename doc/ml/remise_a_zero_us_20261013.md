# Remise à zéro des modèles US — 13 octobre 2026

À la demande de l'utilisateur, les modèles US et leurs données d'entraînement,
prédictions et métriques ont été retirés pour reprendre l'apprentissage.
L'utilisateur a ensuite demandé la suppression directe des fichiers,
sans créer d'archive de modèles.

## Périmètre exécuté

- Base `alpha_trade` uniquement. Les seize tables ML identifiées ont été vidées,
  structures conservées : campagnes/runs, registre, serving, métriques,
  gouvernance, diagnostics, prédictions, classements et labels Oracle,
  étude `oracle_atr_market_regime_daily`, historique des champions et drift ML.
- 33 campagnes étaient enregistrées en base. L'inventaire initial compte
  60 954 127 lignes sur les tables ciblées. Un ancien nettoyage par batch
  était déjà actif ; le rapport distingue les suppressions effectuées avant
  la reprise et le nombre total de lignes vidées depuis l'inventaire.
- 19 dossiers de campagnes US identifiés sur disque : répertoire principal,
  variantes S7, screening et PSV2. Le dossier des champions Oracle US a
  également été supprimé.
- Poids de recherche US identifiables et dossiers `fit-data` des challengers
  explicitement rattachés au modèle supprimé. Le plan final contient 80 cibles :
  74 supprimées par cette opération, 6 déjà absentes après l'ancien nettoyage.
- Aucun nouvel entraînement ou test économique n'a été lancé.

## Données conservées

Prix quotidiens/intraday, news, sentiment, consensus, options, fondamentaux,
univers et données sources restent conservés. Les bases et artefacts CN/FR
ne sont pas ciblés. Les ordres, fills et historiques de positions sont
conservés : 14 ordres broker, 14 fills, 14 événements, 14 requêtes d'ordres,
7 lots historiques et 1 ligne de projection de position, compteurs inchangés.
Cette ligne de projection ne prouve pas une position encore ouverte au broker.

Les rapports d'expériences, leurs journaux de trades et les datasets de recherche
génériques sont conservés comme historique. Un dataset générique n'est pas
supprimé au seul motif qu'il s'appelle `features.parquet` ou `labels.parquet`.
Le contrôle automatique avait refusé ce périmètre plus large ; le plan a été
resserré avant toute suppression de fichiers.

Les anciens rapports restent descriptifs de leurs campagnes datées. Leurs
commandes de reprise ne sont plus exécutables avec les poids supprimés ;
un nouvel entraînement produira de nouveaux identifiants.

## Configuration pour repartir

La configuration `oracle_barrier` au terme du nettoyage est TP 20 %, SL 10 %,
vingt séances. La page Pipeline et la commande d'entraînement reprennent ces
valeurs. Les anciens identifiants figés du live et du backtest sont retirés.
Le filtre LLM reste désactivé ; `RETRAIN_US_MODEL_REQUIRED` est un marqueur de
configuration, pas un modèle existant. Après entraînement, remplacer ce marqueur
par l'identifiant retenu si le filtre LLM doit être utilisé.

Ne pas confondre date de fin demandée, fin des labels effectivement disponibles
au fit et fin de validation du fold utilisé. Pour chaque test historique,
utiliser uniquement un fold validé avant la date de décision.

## Traçabilité et récupération

Plan exact, inventaire, contrôles SQL et résultat de suppression des fichiers :
`artifacts/operations/us_models_reset/20261013-v1/`.

Les fichiers supprimés directement ne disposent d'aucune nouvelle archive de
récupération. Les sauvegardes antérieures existantes ont été conservées ;
elles ne garantissent pas de contenir les modèles nouvellement créés les
12 et 13 octobre. Une copie JSON des métadonnées SQL avant nettoyage est
conservée avec l'audit, sans poids de modèles ni les grands historiques de
prédictions/labels. Le dernier backup SQL existant identifié est
`backups/db/alpha_trade_without_news_20261010_230004.sql.gz`.
