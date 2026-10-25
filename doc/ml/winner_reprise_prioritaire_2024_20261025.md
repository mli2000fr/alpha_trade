# Reprise prioritaire2024 —25 octobre2026

Demande utilisateur : pourquoi attendre et peut-on reprendre2024 maintenant ?
Le correctif1x est qualifié,214/300 comptes2024 sont en place ; le2x reste
à qualifier sur son propre incident213/300. Ni données ni abonnement ne
bloquent. Le lanceur legacy limite volontairement le compagnon centimes à
un worker, occupé depuis plusieurs heures par1x2022. L'attente est de calcul.

Intervention bornée : remplacer seulement l'ordonnanceur centimes, après
contrôle des PID/commandes/filiation ; adopter son worker2022 vivant sans
l'arrêter. Le nouvel ordonnanceur dispose de deux slots incluant ce worker
adopté. Priorité à1x2024 reprise ; puis2x2024 qualification et reprise ; les
autres travaux gardent leur file. L'ancien superviseur de chaque grille
continue et défère ces années à la réparation grâce aux verrous existants.

Le script`us_winner_2024_priority_20261025` charge les deux moteurs legacy
archivés avant leurs consommateurs, puis appelle les fonctions de reprise
existantes et leur dispatcher enfant. Aucun changement de profils, prix,
paramètres DD, audit ou production. Les comptes terminés restent hashés et
préservés. Les erreurs non expliquées/échecs d'un worker ne sont pas relancés
aveuglément. L'absence d'une résolution2022 après sa terminaison est un échec
de l'ordonnanceur, pas une autorisation de refaire les comptes en double.

Suivi :`artifacts/operations/winner-2024-priority-20261025-v1/{handoff,progress}.json`,
et états annuels/cas existants. La présence du fichier`run.lock` ne prouve
pas qu'un processus tient le verrou ; le verrou annuel système est conservé.
Mémoire disponible vérifiée avant ajout d'un unique calcul supplémentaire.
Pas de fournisseur,SQL,LLM,entraînement,ordre ni changement des anciens runs.
