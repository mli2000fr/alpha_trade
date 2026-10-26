# US : options conditionnelles aux TOP10/20/50 Oracle parcours H20

26 octobre 2026. Audit demandé explicitement sur les N premiers titres Oracle,
pas sur tout l'univers. Aucun entraînement, fournisseur, LLM, SQL écrit ou ordre.

## Périmètre et absence de substitution d'horizon

Inventaire local/SQL :uniquement Oracle parcours H20, pas de modèle parcoursH5/H10.
La cible d'amplitude du modèle H20 est un pic sur vingt séances, pas la clôtureH20.
Les issues directionnelles protégées restent mesurées séparément sur le parcours
de5/10/20séances, pas sur les seuls cours finaux. Ne pas nommer cela OracleH5/H10.
Ne jamais sélectionner les titres selon leur amplitude future réellement observée.

Septembre :modèle annuel2026 déjà demandé `model-factory-20261014113232-bc35a7`.
Octobre :modèle Pipeline `model-factory-20261016180250-3b0515`.
Pas de compétition des modèles ni choix selon les résultats ; pas de remplissage
des jours sans scores avec le classement d'une autre date. Scores SQL existants
seulement, pas de nouveau fit ou recalcul de features/Oracle.

Disponibilité modèle :vérifier protocole H20 parcours, fold sélectionné et hash
du poids/profil, maximum des fins de disponibilité train/validation STRICTEMENT
avant la date signal. Cela ne certifie pas une disponibilité historique physique :
modèles entraînés en octobre et scores de septembre recalculés en octobre.

Deux lectures distinctes :

1. Audit rétrospectif des scores existants, lineage modèle causal mais prix/features
   historiques non certifiés PIT strict. Les timestamps SQL ne sont pas antidatés.
2. Contrôle strict de réception effective :created_at du score ET de la lineage
   avant décision09:25NY. Si aucun cas mature, publier0, pas un résultat inventé.
   created_at n'est pas un historique de versions :ce contrôle nécessaire ne suffit
   pas à certifier l'absence de réécriture depuis. Aucun label promu en production.

## Sélection puis appariement

Date signal = séance officielle précédant l'open d'entrée du protocole options.
Pour chaque date :scorer le fichier tradable courant, couverture minimale95%,
ordre proba_extreme décroissant puis symbole alphabétique pour égalités exactes.
Rang entier calculé AVANT filtre options, disponibilité des rendements, qualité
des prix ou maturité. TOP10/20/50 = N titres, pas N% ; aucun TOP11/21/51 de secours.
Contrôles de doublons et de probabilité finie[0;1] ; dates sansscores explicites.

Reprendre les features options et les parcours archivés de
`us_options_equal_mix/20261026-v2`, empreintes vérifiées. Évaluer par flux EODHD
primaire/SIP secondaire séparément ; pas de nouveau téléchargement de cours.
Sur les candidats TOPN disposant réellement des DEUX features avant décision :
rangs quotidiens de volume et OI, mélange50/50, aucun poids ajusté.
Trois scores comparés sur EXACTEMENT la même cohorte. Absence≠score neutre.
Les rangs options ne changent jamais les rangs Oracle originaux ni la sélection.

## Mesure et limite

PrimaireH20 :plus grande excursion favorable avant propre SL10LONG/SHORT ;
H5/H10 secondaires. Gaps/ordre intrabar inconnu/ambiguïtés hérités et réservés.
AUC quotidienne moyenne à deux classes, AUC groupée distincte, effectifs et
couverture réelle TOPN, classe majoritaire, moitiés et dates H-espacées choisies
sur les décisions Oracle avant issues, première observation par symbole.
Pas de comparaison AUC sur des ensembles de titres différents entre composants.
Dates/titres répétés, petits effectifs, univers survivant, options indicatives,
OPRA non attesté et vintage prix/ajustements réservés :exploratoire seulement.
Une AUC>0,5 n'est ni taux gagnant ni preuve économique, et l'appartenance aux
extrêmes Oracle ne garantit pas une meilleure séparabilité de leur sens.

Répertoire neuf immuable, protocole avant résultats TOPN, tests avant analyse,
SQL US READ ONLY / REPEATABLE READ / timezoneUTC / rollback, hashes entrées/sorties.
