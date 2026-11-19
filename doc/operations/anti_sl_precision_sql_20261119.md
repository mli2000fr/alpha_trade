# Précision SQL anti-SL — correctif du 19 novembre 2026

## Incident

La reprise `us_pipeline-20261119100748-5ac86c17` s'est arrêtée à l'étape 10
avant risque ou exécution, sur le contrôle du contrat anti-SL. Le manifeste
du batch `model-factory-20261118172104-2f6a31` indique un seuil
`0.16660042812602094`. MySQL, avec une colonne `FLOAT`, renvoyait `0.1666`.
Le modèle, son empreinte et la date de disponibilité étaient cohérents ; le
seuil arrondi dépassait la tolérance stricte du contrôle.

Le profil B témoin désactive le veto anti-SL mais ne valide pas pour autant
des preuves corrompues du bundle : ce contrôle de cohérence reste actif.

## Correction

`anti_sl_probability` et `anti_sl_threshold` utilisent désormais `DOUBLE`
pour les nouvelles tables. La migration explicite
`database/sql/migration_0089_anti_sl_prediction_precision.sql` élargit ces deux
colonnes sur une table existante. La publication des scores vérifie la
précision MySQL avant toute suppression/insertion et demande la migration
si elle rencontre encore un ancien stockage `FLOAT`.

La tolérance du contrôle de seuil reste **1e-12**, avec vérification du
manifeste, du modèle, de sa causalité, de ses dates et du cutoff. Aucun lecteur
ne répare ni ne réécrit les données en SQL. Les règles de sélection, les
modèles entraînés et les règles de risque ne changent pas.

Élargir une colonne ne retrouve pas les décimales perdues de ses anciens
scores. Les dates nécessaires doivent être recalculées avec ML Predict et
leur batch d'origine ; les autres dates anciennes ne sont pas déclarées
réparées. La reprise opérationnelle recalcule le **18 novembre 2026** avant
de relire ses scores.

## Application et validation

La migration a été appliquée à `alpha_trade` : **2 370 457 lignes avant et
après**, sans suppression ni remplacement de scores pendant la migration.
Le schéma antérieur et les 1 639 lignes du batch/séance concernés ont été
archivés dans
`artifacts/operations/anti_sl_precision_repair/20261119T103729Z`.
Le reçu `report.json` confirme les types `DOUBLE`, le nombre de lignes et
la durée. Les valeurs binaires d'origine du périmètre ont aussi été conservées.

**62 tests ciblés réussis** : création MySQL en double précision, aller-retour
SQL exact du seuil, rejet inchangé d'un seuil arrondi ou d'un autre contrat,
cutoff, garde avant toute suppression, bundle anti-SL et profils B/Q051 PAPER.
Le transport SQL réel a aussi été vérifié en lecture seule avec
`SELECT CAST(... AS DOUBLE)` pour le seuil du manifeste.

La nouvelle reprise est préparée sous
`artifacts/operations/us_pipeline_resume/20261119T103833Z` : étapes 10/11/12
uniquement, séance du 18 novembre, B témoin sans veto anti-SL, puis 11/12 sur
les deux autres comptes PAPER. Une copie de configuration propre au run
empêche un changement ultérieur du YAML principal de modifier ce lancement.
Les collectes précédemment terminées ne sont pas rejouées.

## Résultat opérationnel

La relecture stricte a réussi après recalcul : **1 639 lignes** portent
exactement le seuil `0.16660042812602094`. L'étape 10 a publié dix candidats
B témoin ; le risque a ensuite été exécuté par compte.

Un watcher antérieur au code Winner a bloqué le premier passage à l'étape 12.
Les services PAPER ont été rétablis et leurs heartbeats vérifiés. Le watcher
`test1` avait aussi une erreur TLS sur Alpaca : un bundle associant certifi aux
racines déjà approuvées par Windows a permis de vérifier la chaîne. La
vérification TLS reste active. Le bundle scoped est
`artifacts/operations/us_pipeline_resume/20261119T103833Z/windows-trusted-ca.pem` ;
le conserver tant que les watchers qui le référencent sont actifs.

La continuation ponctuelle `scripts/operations/resume_q051_20261119.py` refuse
les dates, modèles et reçus différents. Elle conserve Oracle et le risque
default scellés ; tous les ordres passent par les workflows et contrôles
natifs. Après réussite de default/test1, une collision de verrou a arrêté
test2 avant la création d'un risque. Seul test2 a été repris, après preuve
des deux autres comptes terminés et de l'absence de tentative publiée sur test2.
Aucun verrou actif n'a été supprimé pour contourner ce refus.

| Compte | Cibles risque | Nouveaux ordres soumis | Titres |
| --- | ---: | ---: | --- |
| default | 5 | 2 | IONS, FUTU |
| test1 | 6 | 6 | GLW, ZS, CTVA, IONS, FUTU, ASX |
| test2 | 6 | 6 | GLW, ZS, CTVA, IONS, FUTU, ASX |

Les plans default existants GLW/ZS/CTVA ont été conservés sans duplication.
Les 14 nouveaux ordres étaient soumis et non remplis lors de la vérification
avant ouverture. Les trois watchers étaient sains et les notifications
Telegram de fin d'étape 12 acceptées.

Dernier batch de continuation : `us_pipeline-20261119111758-3b538b99`, statut
SQL **COMPLETED**, deux étapes demandées/persistées, zéro échec. Les autres
étapes validées lors des passages précédents sont conservées ; les échecs
historiques restent dans les journaux. Le reçu consolidé est
`artifacts/operations/anti_sl_precision_repair/20261119T103729Z/completion.json`.
