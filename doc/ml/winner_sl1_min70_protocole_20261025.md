# TOP20 : SL1 contre SL5, minimum 70 USD et dépôt 4 000 USD

25 octobre 2026. L'utilisateur demande « TOP20 SL1 sans TP/trailing H20 ».
La dernière mention « comparer avec SL1 » est interprétée comme comparaison
au SL5 en cours, conformément au contexte. Un seul nouveau compte.

## Protocole

Même TOP20 et archives, compte neuf 4 000 USD, 2 janvier 2020–31 décembre2024,
positions complètes, cap1x, sans renforcement, minimum70USD, frais8pb/jambe,
vingt séances entrée incluse puis open21. SL effectif passe de5% à1% ; aucun
TP ni trailing. Mêmes risque1,25%, B4/DD15 originaux, concentration et secteurs.
Pas de nouvelle pause/liquidation globale, sélection mensuelle ou reset annuel.

Configuration moteur strictement identique au run min70/SL5, seules les
politiques effectives des campagnes changent de SL5 à SL1. Conservation du
plafond historique d'admission SL3 : ne PAS agrandir les quantités au-delà de
ce plafond sous prétexte que SL1 autorise théoriquement plus de titres. Le
risque réellement utilisé peut donc être inférieur au budget1,25%. Le nombre
et la taille des achats pourront néanmoins varier par trajectoire du capital.
Ce test n'est pas une optimisation du sizing pour consommer tout le budget SL1.

## Exécution et audits

Moteurs archivés chargés dans un processus neuf ; pas de fichiers de production
modifiés. Vérification des configurations/politiques et des sources scellées.
Test natif d'un prix qui touche SL1 mais pas SL5, contrôle de restauration des
adaptateurs, maintien du plafond de quantité d'admission. Audit indépendant
cash/frais/positions/confirmation/sorties scalaires/DD/coverage. Aucune tolérance
augmentée pour un incident d'arrondi éventuel. Le stop ne garantit pas1% réalisé
en présence de gap ; frais inclus dans les PnL. Les deux runs peuvent avancer
en parallèle ; le bilan SL1 mentionne explicitement si SL5 n'est pas encore prêt.

Commande : `.venv\Scripts\python.exe -u -m scripts.research.us_winner_sl1_min70_20261025`.

Nouveau dossier : `artifacts/research/us_winner_sl1_min70/20261025-v1`.
Témoin : `artifacts/research/us_winner_min70_4000/20261025-v1`.
Suivi `progress.json`, bilan `report.json`, années `annual-summary.csv`.

Archives locales uniquement, HTTP interdit, aucun SQL/API/LLM/modèle/ordre.
Recherche exploratoire, historique déjà examiné, couverture future et secteurs
actuels nonPIT conservés ; pas de parité live complète ni recommandation.
