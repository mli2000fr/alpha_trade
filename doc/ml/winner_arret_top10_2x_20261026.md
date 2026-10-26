# Arrêt explicite TOP10 levier ×2 — 26 octobre 2026

Demande humaine : arrêter la grille TOP10×2, conserver ses résultats terminés
et laisser tourner sans levier. Pas d'arrêt ou réinitialisation du TOP10×1.

Les anciens superviseurs ne disposent pas de contrôle d'annulation par branche.
Arrêter uniquement le superviseur×2 et ses workers×2, après contrôle des commandes,
PID et dates de création. Le superviseur de reprise commun doit aussi être
remplacé, mais SANS tuer récursivement ses enfants : son worker×1 est conservé
et adopté par un ordonnanceur×1 uniquement. Les deux superviseurs/replays×1
originaux restent intacts. Aucune attente d'achèvement de la grille×2.

Conserver tous les comptes et rapports déjà scellés, comparer leurs empreintes
avant/après ; les comptes interrompus restent incomplets, non promus. État
`STOPPED_BY_USER`, marqueur durable `user-stop.json` à la racine×2 et pour ses
reprises ; aucun reçu `resolution.json` ni bilan complet inventé. Pas de reprise
automatique×2 par le nouvel ordonnanceur. Une relance future nécessite un choix
humain explicite et ne doit pas être déduite d'un état historique `RUNNING`.

Exécuter le nouveau module de recherche
`scripts.research.us_winner_stop_2x_20261026 --phase stop`, puis `--phase supervise`
en arrière-plan pour le suivi×1. Verrous et sources legacy exactes inchangés,
jamais d'édition des sources scellées. Preuves, inventaire et progression :
`artifacts/operations/winner-stop-top10-2x-20261026-v1`.
Aucune suppression, SQL/API/LLM/entraînement/ordre ou modification production.
