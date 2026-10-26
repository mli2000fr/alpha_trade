# FR : combinaison exploratoire équipondérée — 26 octobre 2026

Demande humaine explicite : examiner une combinaison sans entraînement,
recherche de poids, seuils ou inversion opportuniste. Utiliser uniquement
le snapshot revu P0/P1 déjà figé, sans SQL, fournisseur, LLM, ordre ou changement
de batch. Les diagnostics individuels de ce même historique ont déjà été vus :
ce protocole n'est pas une préinscription aveugle ni une validation indépendante.

## Une combinaison, trois comparateurs

Sur chaque date d'entrée, cohorte commune disposant des trois features finies
AVANT l'open : momentum5, momentum20 et variation AMF des mêmes détenteurs,
orientée baisse des positions publiques→LONG. Pas de zéro pour absence AMF.
Ne pas ajouter le niveau AMF isolé défavorable, un contenu DILA non qualifié,
le consensusP3 non inclus ou des données bloquées pour droits/prudence.

Rang normalisé = (rang moyen des ex aequo−0,5)/nombre de candidats. Une feature
constante donne0,5. Classements calculés parmi TOUS les candidats aux features
complètes avant entrée, même si leur label est ensuite nonmûr/ambigu/incomplet.
Ne pas reclasser après connaissance des chemins futurs. Un seul score figé :

- Prix seuls =50% rang momentum5 +50% rang momentum20.
- AMF seule =rang de la variation orientée des mêmes détenteurs.
- Combinaison =50% prix +50% AMF, soit25%/25%/50% des trois rangs.

Aucun poids estimé ; aucun autre mix testé puis sélectionné. Scores de classement,
pas probabilités calibrées ni recommandations d'ordres. Tous les comparateurs
sont évalués sur EXACTEMENT les mêmes lignes/titres/dates disponibles.

## Cible et mesures

Conserver le label précédent : excursion favorable maximale avant stop10% propre
à LONG/SHORT, pas le signe de clôture terminale ni une sortie réalisable au pic.
Gaps, bornes stop/pic intraday et ambiguïtés identiques aux archives sources.
H20 primaire : zéro label mûr au snapshot, aucun remplacement par une fenêtre
partielle. H5/H10 descriptifs seulement.

AUC par date, moyenne des mêmes dates avec les deux classes ; score constant
contribuant0,5, pas une date supprimée. Différence appariée combinaison−prix,
nombre de dates favorables/défavorables ; AUC poolée secondaire. Deux contrôles
sans réajustement : première observation par titre et cohortes de dates espacées
d'au moinsHséances officielles. Sensibilité en retirant une date de la moyenne,
sans apprendre de nouveaux coefficients ni choisir une variante.

Historique de quelques dates, mêmes titres et fenêtres chevauchantes : pas de
test économique, intervalle de confiance trompeusement serré par ligne, modèle
ou filtre promu. Une AUC supérieure sur cet échantillon ne démontrerait pas un
rendement positif. Toute conclusion doit indiquer le nombre de titres ET dates.

Source : `artifacts/fr/research/p0_p1_directional/20261026-v1-reviewed`.
Sortie immuable : `artifacts/fr/research/p0_p1_equal_mix/20261026-v1`.
Script : `scripts.research.fr_p0_p1_equal_mix_20261026`.
