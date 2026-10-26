# Grilles natives 1x/2x — réparation du pilotage du23octobre2026

GO utilisateur : réparer l'enchaînement en conservant tous les comptes déjà
calculés. Réparation d'exécution uniquement : pas de changement de profils,
prix, frais, risque, levier, modèles, cohortes, métriques ou audits économiques.
Les sources/protocoles scellés d'origine ne sont pas édités.

## Cause confirmée, pas une supposition de quota

Lecture seule des piles des deux pilotes CPython3.14 : threadprincipal dans
`ProcessPoolExecutor.shutdown(wait=True)`/`Thread.join`, workers encoreactifs.
Le résuméglobal avait cessé de se rafraîchir alors que les étatsannuels
progressaient. Une année2017 terminée ne libérait pas un nouvel envoi vers2020.

Après arrêt ciblé des quatreworkers de recherche identifiés parPID, parent,
date decréation et moduledupilote, les deux pilotes ont enfin imprimé la
**mêmeexceptionoriginale** : `PermissionError` à la lecture de `year-2017.json`,
depuis la compréhension `states=[base.read(...)]`. La lecture concurrençait
les remplacements atomiques Windows. L'exception sortait de la boucle, mais
la sortie du contexte du pool attendait les tâchesannuelles ; le traceback
restait donc masqué et les années suivantes n'étaient plus distribuées.

Les anciens stderr sont conservés dans `log/winner-native-grid-...stderr.log`.
Ce n'est ni un échec de prix, ni une erreur de PnL, ni un quotaAPI. Aucun
batch, téléchargement, autreentraînement ou ordre n'a été arrêté. Seuls les
profils nonencore terminés peuvent être rejoués après reprise ; aucun rapport
de compte terminé n'est effacé ou recalculé pour modifier son résultat.

## Nouveau superviseur

Script : `scripts/research/us_winner_grid_supervisor_repair_20261023.py`.

- Retry borné des lecturesJSON surPermissionError/fichier momentanément absent
  ou JSONen cours depublication ; JSONpersistant corrompu refusé.
- Échec de lecture d'un simple statut : dernière valeurvalide conservée avec
  avertissement, sans faire abandonner tous les calculs.
- Un sous-processus indépendant parannée, deuxmaximum pargrille. Pas de
  `ProcessPoolExecutor`, donc pas d'attente implicite masquant une exception
  du pilote jusqu'à la fin des années.
- Vérification SHA256 de tousles comptes déjàterminés, paramètres et audit,
  puis réutilisation du worker économique original. Année entièrement terminée
  ignorée ; année partielle reprise sur ses seuls profils restants.
- 1x reprend ses snapshotsSQL READONLY. 2x copie toujours les snapshots1x
  identiques, sans nouvel appelSQL/fournisseur. Attente d'entrée nonbloquante
  dans la file si une archive deréférence n'est pas encore prête.
- Étatglobal horodaté régulièrement, erreurs immédiates et sorties locales
  parannée. Retry d'unworker seulement surPermissionError, troisessaismaximum ;
  un échec économique/dequalité n'est pas masqué par une boucle infinie.
- Au premier échec inattendu du superviseur, publier l'erreur sans attendre
  les annéesterminées : arrêter uniquement ses sous-processus de recherche,
  conserver les cas scellés et permettre une reprise explicite.

Dans chaque dossier de run :

- `supervisor-v2/amendment.json` : protocoleoriginal et nouvelles sources liés
  parempreinte ; aucune réécriture du protocole économique ;
- `supervisor-v2/original-progress.json` : ancienrésumé figé conservé ;
- `supervisor-v2/preserved-completed.json` : rapports et fichiers conservés,
  vérifiés avant reprise puis contrôlés de nouveau àla fin ;
- `supervisor-v2/year-<année>-attempt-<n>.*` : sortie, erreurs et reçu de fin
  du sous-processus ;
- `progress.json` : étatglobal courant, comptes et années actives/enattente,
  PID/essai, avertissements, erreurs et heure de miseàjourUTC.

Commandes de reprise des mêmes dossiers :

```powershell
python -u -m scripts.research.us_winner_grid_supervisor_repair_20261023 --kind 1x --workers 2
python -u -m scripts.research.us_winner_grid_supervisor_repair_20261023 --kind 2x --workers 2
```

Ne pas utiliser enparallèle les anciens lanceurs pour ces mêmes dossiers.
Le verrouglobal demeure ; chaque sous-processus prend aussi un verrouannuel.
Ni nouveauTOP3, ni changement de classement, ni promotion enproduction à partir
de cette réparation. Les réserves des protocoles1x/2x restent intégrales.
