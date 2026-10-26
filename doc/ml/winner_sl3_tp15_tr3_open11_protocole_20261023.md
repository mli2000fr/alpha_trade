# Winner : relever seulement le TP de 7 % à 15 %

GO du 23 octobre 2026. Variante unique **SL3 / TP15 / trailing3 / open11**,
comparée au SL3/TP7/TR3/open11 déjà calculé. Années2025 et2026au30septembre,
4000USD annuels, frais8bps/jambe et même risque natif/B4DD15. Pas de grille,
réentraînement, nouvelle collecte, SQL, ordre, YAML ou source de production modifié.

## Changement unique et comparaison

RéférenceTP7 scellée :
`artifacts/research/us_winner_sl3_tp7_tr3_open11/20261023-v1`.
Contrôle préalable de ses sources, rapports, comptes et audit final.
**Seule la valeur `take_profit_pct` passe de0,07à0,15.**
SL initial3 %, trailing3 % des hauts déjà connus depuis le fill, ratchet sans
desserrer le stop, dix séances de détention entrée incluse puis vente open11.
Attente après signal20séances, deux clôtures5m après cassure fraîche du haut
raw précédent, mêmeTOP10OracleparcoursH20, HALF et sans renforcement.
Pas d'ATR/direction/veto nouveau, pas de remplacement duTOP10.

Même formule de sizing, même SL, budgets et plafonds : le TP n'augmente pas la
taille initiale. Les tailles et admissions ultérieures peuvent diverger après
les premières différences de PnL/cash/risque. Exposition effective1x conservée,
pas2x accordé contre le plafond de risque. Capital annuel indépendant4000USD.

Mêmes1428/1027signaux de la cohorte native, sur2510/1880initiaux, mêmes archives
SIPraw/régulières5m et autres entrées. Requalification strictement identiqueJ+40.
RéférencesTP7 etWinnerSL7 historiques déjà auditées réutilisées par empreintes,
pas rejouées ni mélangées avec l'ancienHALF_CONTROL+12,92 %.

## Exécution et audit

Réutilisation de l'ancien lanceur et du résolveur scalaire sans éditer leurs
sources scellées. Adaptateur de recherche limité au processus : règleTP15,
nom de bras, manifeste et argument expliciteTP15 du reconstructeur. Restaurer
les symboles injectés même en cas d'erreur. Tout le reste inchangé.

Stop prioritaire siSL/TP touchés dans la même bougie, gapstop au prix ouvert,
TPgap plafonné à15 %. STOP/TP intrabar inscrits àFINde5m, gaps au début. Le
trailing n'utilise que les bougies déjà terminées, pas leur high pour protéger
rétroactivement leur low. Stop remonté au-dessus du cours ouvert : sortie au
cours disponible, pas gain garanti. Échéance open11 annulant les protections
avant l'envoi de l'ordre de clôture, selon le runtime existant.

24tests précédents plus tests ciblés de l'adaptateur/TP15, puis smoke5séances
et audit indépendant des sorties/cash/achats. Rejeu économique complet des deux
années, audit scalaire àTP15, et table comparativeTP7/TP15 parannée : rendement,
capital,DD,taux gagnant, gain/perte moyens, durées, frais et capital utilisé.
Pas de comparaison brute de maxima de prix, ni calcul « un trade=+15ou−3 ».

Années déjà observées : expérience exploratoire, pas holdout indépendant.
Cohorte conditionnée par couverture future, univers survivant, secteurs actuels,
dailySPYrévisable, inventaire OST parent vide/non exhaustif, sans quotes/fills
historiques certifiés. Ne pas modifier automatiquement la production selon les
résultats ; pas de garantie de prix au stop ni de parité broker intégrale.
