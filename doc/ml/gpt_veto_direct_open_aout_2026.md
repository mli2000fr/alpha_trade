# GPT août2026 — entrée directe J+1 contre entrée confirmée Winner

Demande utilisateur après le constat du faible taux gagnant des quatre comptes
Winner. Convention annoncée : **retirer la confirmation d'entrée**, conserver
la demi-position pour isoler ce facteur. Ce n'est pas un test passant
simultanément en positions complètes ou désactivant le risque.

## Quatre nouveaux comptes

Sans veto GPT, puis exclusion des avis VALID1–3,1–4,1–5. Même cohorte237/420
signaux TOP20 d'août2026, mêmes avis archivés (invalides/absents sans veto),
même capital partagé4000USD et même classement Oracle, sans remplacementTOP21.
Signaux du3 au31 août ; portefeuille suivi au30 septembre2026.

Chaque signal retenu est proposé à l'ouverture officielle de J+1, sans
cassure du plus haut de la veille ni deux bougies5m de confirmation. Si
l'achat est refusé ou non exécuté à cette ouverture, le plan est annulé :
pas de tentative9h35 ou plusieurs jours plus tard. Un nouveau signal du
lendemain peut être admis normalement. Un titre déjà détenu n'est pas
racheté et il n'y a aucun renforcement. Les contraintes natives (cash, huit
positions, corrélation, secteurs, concentration, B4) continuent de s'appliquer.

SL7 fixe, sans TP ni trailing, vingt séances de détention depuis le fill puis
vente open21. Frais8pb/jambe, gross cap1x et sizing en demi-position identiques.
Positions restantes valorisées à fin septembre, sans liquidation artificielle.
Pas les règles de liquidation globale/pause des expériences mensuelles.

## Moteur et sécurité

Adaptateur local du signal d'entrée et annulation des plans refusés. Le moteur
de campagnes reste utilisé **comme infrastructure comptable/de risque/de
protection**, pas comme stratégie de timing Winner. Le mettre simplement à
`enabled:false` aurait changé de moteur et plusieurs règles à la fois.
Sources de production et YAML inchangés. Entrées proposées via réapprobation
native, journal d'ordres simulés, cash partagé et protections normales.

Premier prix moyen de fill exact, sans dérive d'arrondi binaire. Les niveaux
SL7 des109 achats des quatre comparateurs Winner sont contrôlés inchangés
avant de réutiliser ces résultats. Aucun audit de prix n'est desserré.

Audit indépendant de chaque achat : J+1 officiel exact, signal retenu de la
veille, prix d'ouverture brut, quantité entière plafonnée par l'approbation,
frais. Audit de toutes les sorties SL/gap/horizon et du cash, stocks finaux,
PnL et DD. Aucun calcul sur rendements futurs pour décider des entrées.

## Fichiers et limites

Module `scripts.research.us_gpt_veto_direct_open_august_2026`.
Dossier `artifacts/research/us_winner_gpt_veto_august_2026/20261025-direct-open-v1`.
Quatre comptes nouveaux ; le rapport final inclut les quatre comparaisons
Winner/direct à filtre identique. Les témoins Winner restent scellés.
Résultat économique seulement après audits complets des quatre comptes.

Pas de SQL, fournisseur, GPT/DeepSeek, entraînement ou ordre réel. Mêmes biais
que le test précédent : GPT rétrospectif non PIT, un mois déjà observé, choix
des seuils après essais précédents, secteurs actuels et sélection conditionnée
par couverture future J..J+40. OHLC5m et non quotes/fills historiques certifiés.
L'ouverture est un prix d'exécution simulé observable, pas un fill garanti en
production. Pas de promotion live ni de validation indépendante.
