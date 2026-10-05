# Sprint 15-B — Collecte EODHD quotidienne France, J−7/J

5 octobre 2026. Collecteur implémenté, tests et deux passages réels réussis
sur trois titres. `fr_daily_bars_sync` est `enabled: true`, `ACTIVE_RESEARCH`
dans `batch_fr.yaml`. Aucune tâche Windows installée automatiquement.

## Périmètre exact

OHLC, close ajusté fournisseur et volume quotidien, endpoint EODHD `eod`.
Ce batch ne télécharge pas les dividendes/splits : leur famille reste séparée.
Il n'utilise pas le skip des archives historiques. Il ne touche ni US/CN,
ni modèles, ni SQL, ni `stock_bars_daily` canonique. La collecte ne suffit
pas à qualifier un titre comme négociable ou à lever les réserves fiscales.

Source d'univers : `artifacts/fr/sprint6c_reference/identities.jsonl.gz`.
Retenir les identités `VERIFIED_RESEARCH`, statut fournisseur courant `active`,
symboles `.PA`. Cela donne **294 titres** sur les 330 identités historiques.
Les radiés sont conservés dans l'historique, mais pas demandés chaque jour.
Ce référentiel est figé : les nouvelles IPO/changements ultérieurs ne seront
pas découverts avant l'intégration du master quotidien. Ce statut courant
n'est pas une preuve PIT historique de négociabilité.

## Horaires et budget

22h Europe/Paris du lundi au vendredi ; pas horaire New York. À un lancement
avant 22h, la fin demandée est J−1, pour ne pas archiver la séance en cours.
Après 22h, J est inclus. J−7 est calculé en jours calendaires ; les barres
retournées doivent correspondre à des séances XPAR de bibliothèque.
Le passage du lundi rattrape également les séances de la semaine précédente.

Une requête EOD par titre, intervalle minimal configuré 0,5 seconde,
budget de 400 titres maximum : au-delà, arrêt explicite, pas troncature cachée.
Les retries peuvent augmenter le nombre d'appels ; ce budget n'est pas un
relevé du quota fournisseur. Délais/timeouts/backoff et TLS vérifié utilisent
le transport FR existant. Token : variable `EODHD_API_TOKEN`, jamais journalisée.

## Stockage, reprise et corrections

Racine : `artifacts/fr/operations/eodhd_daily/`.

- `raw/<sha256>.json` : contenu fournisseur par titre et fenêtre, adressé
  par hash. Même contenu = même fichier ; corrections = nouveau contenu.
- `observations/<hash_symbole>/*.json` : chaque réception, son heure UTC,
  fenêtre et hash brut. Conserve le lineage même après correction.
- `latest/<hash_symbole>.json` : une seule entrée par date et titre, dernière
  version acceptée ; pas de doublon métier. Une valeur inchangée garde sa
  première disponibilité, une correction reçoit sa nouvelle disponibilité.
- `windows/<début>_<fin>.json` : progression sauvegardée après chaque titre.
- `.lock` : exclusion de deux collecteurs simultanés, PID et début. Après un
  arrêt brutal, vérifier l'absence du processus avant toute suppression manuelle.

La **relance normale re-fetch tous les titres** : nécessaire pour détecter
les corrections. `--resume` saute seulement les titres COMPLETED de la même
fenêtre, après contrôle des hashes du brut et du fichier latest ; les échecs
sont redemandés. Une fenêtre différente est une nouvelle collecte J−7/J.
Les écritures de JSON sont atomiques ; les résultats déjà sauvegardés restent
disponibles si un autre titre échoue. Aucune reprise ne reconstitue une date
de disponibilité historique : `available_at` est l'observation effective.

Prix invalides, OHLC incohérents, volume invalide, date hors fenêtre,
non-séance ou doublon de date : brut conservé, titre en échec, pas d'écrasement
du fichier latest. Volume zéro est conservé et étiqueté ZERO_VOLUME, sans
interpréter automatiquement cela comme une suspension. Réponse vide avec
séances attendues = échec. Séances manquantes dans une réponse non vide =
alerte de couverture, pas remplissage artificiel.

## Compteurs, lancement et supervision

Demandés/reçus sont des **titres**, persistés des **barres nouvelles ou corrigées**.
Une seconde exécution peut donc recevoir tous les titres et persister zéro
barre. `unchanged_rows`, `changed_rows`, `resumed_symbols` et les erreurs sont
dans le rapport local du runner. Un échec partiel rend le run FAILED, avec
les compteurs déjà accumulés, plutôt qu'un faux succès global.

Dans Workflow & Orchestration → Batch → France — recherche uniquement,
installer/réinstaller `fr_daily_bars_sync`, puis lancer immédiatement si besoin.
Le launcher partagé transmet logs, compteurs et erreurs aux notifications
email/Telegram configurées. La livraison réelle de ces notifications FR
reste à confirmer sur une exécution du launcher, pas via un smoke Python.

Commande manuelle (sans notifications launcher) :

```powershell
python -u -m service.fr.operational_batch_15a --batch fr_daily_bars_sync
```

Reprise même fenêtre :

```powershell
python -u -m service.fr.operational_batch_15a --batch fr_daily_bars_sync --resume
```

Préflight sans réseau/écriture : ajouter `--dry-run`. Smoke limité : ajouter
`--max-symbols 3`. La commande affichée dans la page Batch utilise le launcher
et ses notifications ; `-Force` ignore l'heure, pas la désactivation.

## Validation réelle et limites restantes

Fenêtre 28 septembre–4 octobre 2026, AB.PA, ABCA.PA, ABVX.PA :
premier passage 3 reçus / 15 barres persistées / 0 échec ; second passage
3 reçus / 0 nouvelle barre / 15 inchangées / 0 échec.
Preuves : `artifacts/fr/operations/eodhd_daily_smoke_15b/`.
Les tests simulés couvrent correction, reprise partielle, invalides,
verrouillage, doublons et séparation FR. Cela ne prouve pas encore la
couverture de l'ensemble des 294 titres ni une semaine d'exploitation.
La sélection de non-régression FR/US/CN/Batch/sauvegardes compte **124 tests
passants** ; ce n'est pas la suite complète de l'application.

Prochain raccordement : chargement versionné en staging SQL FR et contrôle
de fraîcheur quotidien, après qualification. Ne pas injecter ces fichiers
directement dans l'ancien loader historique sans adapter son contrat brut.
Pas de migration Alembic dans cette tranche exclusivement fichiers.
