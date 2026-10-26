# Incident2024 SL7/TP15 : qualification et reprise bornées

Demande utilisateur du25 octobre2026 : traiter l'arrêt de la grille TOP10 sans
levier sur `2024-SL7_TROFF_H15_TP15`, après213 combinaisons2024 terminées.
Audit scalaire refuse `60.6 != 60.61`, pas une erreur de collecte.

## Intervention

Réutiliser le mécanisme de qualification existant, sans modifier ses sources
scellées ni celles du moteur : `scripts/research/us_winner_cent_qualification_20261024`.
La requête1x/2024 existe déjà, découverte automatiquement ; elle attendait la
fin de la reprise1x/2022. Une qualification ciblée peut travailler sur2024
avec son verrou annuel distinct, sans lancer une seconde reprise2022.

Le moteur exact des anciens runs est chargé par
`scripts.research.us_winner_legacy_resume_20261024`. Aucun nouveau DD25/pause,
paramètre de profil, prix, seuil d'audit ou modèle. Les213 comptes2024 déjà
terminés sont inventoriés par empreintes et ne sont pas remplacés.

Étapes : reproduire le cas original en traçant les fills ; vérifier que l'écart
provient bien du prix moyen recalculé `quantité*prix/quantité` ; rejouer le seul
cas avec le correctif existant FIRST_FULL_FILL_AVERAGE_V1 ; contrôler les cas
antérieurs dont les niveaux auraient pu dériver ; installer uniquement le cas
manquant une fois audité. Un mécanisme non expliqué interdit la promotion.

Le correctif conserve le `filled_avg_price` exact du premier fill complet,
au lieu d'en recalculer une moyenne inutile. Les fills partiels/mixtes restent
hors qualification et refusés. Ce n'est pas une modification arbitraire de
l'arrondi au cent : l'auditeur indépendant conserve ses calculs et tolérances.

Une régression synthétique utilise52,70USD, TP15%, avec plusieurs quantités :
la multiplication/division peut donner52,70000000000001 et un TP60,61 plutôt
que60,60. Cet exemple n'identifie pas encore le titre/date du cas réel : les
preuves réelles sont à lire dans `diagnosis/diagnosis.json` avant de conclure.

## Suivi

Dossier `artifacts/research/us_winner_cent_qualification/20261024-v1/1x-2024` :
`request.json`, `progress.json`, diagnostic et validation, inventaire préservé,
puis `qualified.json` et `resolution.json`. Ne pas confondre qualification du
correctif avec achèvement des300 combinaisons : la reprise annuelle vient
ensuite par le compagnon existant, avec verrou et conservation des comptes.

Pas de SQL, fournisseur, LLM, entraînement, ordre ou changement de production.
Les autres années/grilles restent en cours. L'incident ×2, s'il survient sur le
même profil, nécessite sa propre qualification ; ne pas copier un PnL1x en2x.
