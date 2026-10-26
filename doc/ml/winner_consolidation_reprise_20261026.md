# Winner : consolidation TOP50 et reprise de la file — 26 octobre 2026

Incident : les300comptes TOP50/2017 sont terminés et audités, mais le bilan
échoue sur `NaN` dans `best_2017_descriptive_only[].fill_price_correction`.
Les anciens comptes n'ont pas les métadonnées de correction ajoutées aux
comptes repris. Leur réunion dans un DataFrame crée des valeurs manquantes
pour ces champs, refusées à juste titre par le writer JSON strict.

## Correctif borné et non économique

Adaptateur de processus versionné, sans édition des sources scellées.
Normaliser uniquement les valeurs NaN des deux métadonnées facultatives
`fill_price_correction` et `correction_amendment_sha256` en null, seulement
dans les lignes descriptives du bilan TOP50. Conserver les métadonnées connues.
Toute valeur financière non finie, ou une infinité même dans ces champs,
reste une erreur. Aucun `allow_nan=True`, aucun zéro artificiel, aucune
modification des cours, stops, quantités, rendements ou tolérances d'audit.

Vérifier les300rapports TOP50 et tous leurs fichiers avant/après. Refaire
uniquement leur consolidation. Le CSV financier dérivé déjà produit doit
rester identique octet par octet. Garder les anciennes erreurs comme preuves.
Rafraîchir les états TOP20/TOP50, sans recommencer un seul compte terminé.

## Reprise sécurisée

Charger les deux modules moteur legacy archivés EXACTS avant tout consommateur,
réutiliser le launcher validé et ses vérifications de sources. Aucun retour en
arrière des fichiers de production. Le worker centimes2024×2 encore actif
est adopté depuis l'état antérieur avec contrôle commande/PID/creation_time,
jamais interrompu ni lancé en double. Sa fin exige un reçu resolution.json.

Deux nouveaux workers au maximum, trois centimes en comptant les adoptés,
plus les deux workers2026 des superviseurs originaux, laissés intacts.
Garde mémoire libre6Gio avant un nouveau lancement, verrous annuels/root
existants et nouveau verrou d'ordonnanceur. D'abord les reprises déjà qualifiées,
puis seulement les qualifications si nécessaire. Ne pas réessayer les cas
bloqués sans nouvelle qualification. 2018 reste conditionné à sa collecte et
n'est pas déclaré terminé ni téléchargé par cet amendement.

Commande consolidation :
`python -u -m scripts.research.us_winner_consolidation_resume_20261026 --phase consolidate`.
Puis même module `--phase supervise` en arrière-plan.
Reçus et progression :
`artifacts/operations/winner-consolidation-resume-20261026-v1`.
Scripts/tests de recherche uniquement ; aucun SQL/API/LLM/entraînement/ordre,
changement de profil ou paramètre économique. Les résultats restent exploratoires.
