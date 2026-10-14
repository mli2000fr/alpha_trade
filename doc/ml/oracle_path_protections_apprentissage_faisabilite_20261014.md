# Oracle parcours TOP5 — espace d'apprentissage des protections

## Protocole borné, figé avant calcul — 14 octobre 2026

GO : vérifier s'il existe un intérêt potentiel à personnaliser les protections.
**Pas d'entraînement, SQL, ordre courtier, changement de live ou batch.**
Cette étude ne reprend pas le modèle TP/SL de l'ancien Oracle à barrières.

Population : TOP5 **CatBoost** déjà archivés de chacun des trois folds annuels
causaux 2024/2025/2026, dans
`artifacts/research/us_oracle_path_backend_economic/20261014-v1`.
Le choix de CatBoost et les périodes ont déjà été examinés : pas de holdout vierge.
Les 1 790 titres de l'univers observable ont été classés avant qualification du
futur. Aucun remplacement du candidat absent par un rang suivant.

## Trois profils uniquement

| Profil | SL dur | Trailing | TP |
| --- | ---: | ---: | ---: |
| COURT | 5 % | 10 % | 10 % |
| REFERENCE | 5 % | 15 % | 20 % |
| LARGE | 5 % | 20 % | 30 % |

Chaque candidat reçoit les trois contre-factuels, depuis le même open J+1,
avec barrières ancrées à ce fill. Stop avant TP si collision intraday ; gaps
défavorables au prix open ; gap favorable au prix limite TP. Le trailing
n'utilise que le sommet des séances précédentes et ne remplace le SL initial
qu'après activation ne pouvant le desserrer, effective à la séance suivante.
Pas de sortie forcée H20, ni de protection modifiée pendant le trade.

Fenêtre principale : **60 séances, entrée incluse**. Contrôle de convention :
20 séances, entrée incluse. Un trade encore ouvert est **MTM**, pas vendu ;
un trade fermé conserve son produit de vente, sans réinvestissement.
Les dates dont la fenêtre n'est pas arrivée à maturité au 9 octobre 2026 restent
dans le journal d'exclusions, même si un profil serait déjà sorti. Disponibilité
du label commun = clôture de la dernière séance de la fenêtre ; elle n'est
jamais avancée pour les gagnants rapides. Ce label borné ne décrit pas une
détention illimitée et ne suffit pas, seul, à entraîner le gestionnaire final.

## Qualité et coûts

Les exclusions à J sont celles de l'archive. Entrée : open qualifié J+1,
gap absolu au close J limité à 3 %, comme le contrat des replays précédents.
Pour comparer les profils sur le **même** échantillon, toute la fenêtre doit
avoir OHLC cohérents, volume positif, aucune barre remplie et identité constante.
Toute opération de changement d'identité référencée dans la fenêtre est réservée
pour les trois profils, sans conversion inventée. Ces filtres futurs sont des
qualifications rétrospectives, **pas des filtres d'entrée applicables en live**.
Leur biais potentiel et leurs comptes par année/horizon sont affichés.

Rendements unitaires sur notionnel d'entrée, non rendements du portefeuille :
coûts plats canoniques 8 bps par jambe (commission 1, slippage 2, demi-spread 5).
Sortie effective : produit net moins coût d'entrée ; MTM : coût d'entrée seulement,
aucun coût de vente fictive. Sensibilité séparée : coût de liquidation hypothétique
des positions ouvertes et financement théorique de 50 % du notionnel à 6,5 %
ACT/360 jusqu'à sortie/observation. Aucun de ces calculs n'est le financement
réel du portefeuille à levier variable, ni une parité complète du broker.
Pas de dividendes complets, de spread réel, d'impact quantité/volume, de sizing,
de gardes macro/risque ou de réinvestissement dans ce diagnostic unitaire.

## Mesures et critères fixés

- Rendement moyen/médian de chaque profil sur échantillon commun, par année.
- Meilleur choix **connu après coup** par candidat, comparé à REFERENCE et au
  meilleur profil constant également connu après coup sur ce même échantillon.
  Ce plafond de rendement unitaire n'est pas une performance réalisable,
  ni une borne prouvée du portefeuille avec contraintes et réinvestissement.
- Ex aequo à 1e-10 près séparés ; parts des meilleurs profils partagées entre
  ex aequo, pas d'attribution artificielle au premier profil.
- Part avec amélioration >1 point contre REFERENCE ; écart entre premier et
  deuxième profils >1 point ; concentration du gain théorique par titre et
  par les 1 % d'observations les plus contributrices.
- Sensibilité sans pseudo-indépendance : premier candidat de chaque titre,
  puis aucun nouveau candidat de ce titre avant la fin des 60 séances précédentes,
  selon dates et titre seulement. Ce n'est pas le portefeuille réel.
- Incertitude descriptive par bootstrap de blocs de 63 séances de décision,
  999 réplications, seed 731. Les observations journalières répétées ne sont
  pas traitées comme des trades indépendants. Pas de test de signal appris.

**Espace matériel exploratoire** seulement si, à 60 séances, pour chaque année :
gain moyen du plafond >1 point contre le meilleur constant, >10 % des candidats
ont une amélioration >1 point face à REFERENCE, et au moins deux profils ont
chacun >10 % de part parmi les meilleures valeurs. Ces seuils sont des critères
de faisabilité, pas un réglage de trading. Sensibilités et concentration peuvent
imposer des réserves même si ce critère passe.

Variabilité et plafond ne prouvent **pas** que les features disponibles à J
prédisent le bon profil. Si l'espace existe, une autorisation distincte sera
nécessaire pour préparer les features, les anciens candidats OOF et l'évaluation
chronologique purgée, avant tout entraînement. Les tests 2024–2026 resteront
exploratoires et demanderont une confirmation prospective.

## Reprise et contrôles

Artefacts dédiés :
`artifacts/research/us_oracle_path_protection_headroom/20261014-v2`.
Protocole/empreintes avant calcul, sorties par année/horizon avec reprise vérifiée,
journal des exclusions, rapport final, aucun écrasement des recherches antérieures.
Les changements de code IHM/training autorisés après les anciennes recherches
sont enregistrés comme dérives historiques explicites ; les anciennes empreintes
ne sont pas réécrites. Prix, scores, poids et code du moteur utilisés doivent
rester vérifiables. Une comparaison des sorties de protection avec les trades
CatBoost de référence est exigée avant conclusion.

Le précontrôle v1 s'est arrêté avant gel/calcul : les trois anciens dossiers
de modèles annuels ne sont plus présents (de nouveaux dossiers existent).
V2 conserve les scores TOP5 et replays archivés avec leurs empreintes et le
contrat historique ; aucun score n'est régénéré avec les nouveaux modèles.
Les anciennes empreintes des fichiers de modèles absents sont conservées dans
`unavailable_original_model_files`, mais **les poids ne peuvent pas être
revérifiés aujourd'hui**. Cette réserve de provenance interdit de présenter
l'audit comme une reproduction des poids, sans empêcher le diagnostic des
sélections archivées. Un fichier de prix, scores ou code requis absent reste
bloquant. Les métadonnées de disponibilité des anciens folds sont contrôlées.

## Résultats terminés et vérifiés

Six cohortes terminées, sans échec de calcul dans v2. Verdict :
`MATERIAL_HINDSIGHT_SPACE_NOT_LEARNABILITY`. Les critères de faisabilité
figés passent sur les trois cohortes principales. Ce n'est pas un GO live.

Les lignes sont des **candidats quotidiens**, pas des trades effectivement
approuvés/exécutés ni des observations indépendantes. Suivi de 60 séances depuis
chaque entrée : la queue d'une cohorte annuelle peut dépasser le 31 décembre.
2026 est limitée aux décisions dont cette fenêtre est mûre dans les prix
archivés jusqu'au 9 octobre. Aucun résultat neuf de 2026 après cette borne.

### Fenêtre principale : 60 séances, entrée incluse

Tous les chiffres de rendement suivants sont des pourcentages **unitaires
moyens par candidat**, pas le rendement annuel du portefeuille.

| Cohorte de décision | Candidats qualifiés | COURT | REFERENCE | LARGE | Choix parfait après coup | Surplus vs meilleur constant |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 1 155 | +0,32 % | +0,40 % | +0,56 % | +4,24 % | +3,68 points |
| 2025 | 1 109 | +0,27 % | +0,77 % | +0,81 % | +4,72 % | +3,91 points |
| 2026, 2 janvier–16 juillet | 504 | +0,38 % | +1,40 % | +0,29 % | +4,65 % | +3,25 points |

Le plafond améliore REFERENCE de >1 point sur 38,18 /38,14 /34,33 % des
candidats respectivement. Le premier profil dépasse le deuxième de >1 point
sur 45,11 /46,17 /46,03 %. Cependant, **50,82 /49,95 /51,19 % ont des résultats
identiques pour les trois profils** : ne pas transformer ces ex aequo en
preuves de choix personnalisé. Les parts de meilleurs résultats de summary
partagent les ex aequo ; les parts de **meilleur unique** de completion-audit
sont, COURT/REFERENCE/LARGE : 26,23/7,10/15,84 %, 24,62/8,03/17,40 % et
22,02/11,71/15,08 %.

**63,20 /62,76 /62,10 % perdent avec les trois profils.** Même le sélecteur
parfait de ces trois protections ne rendrait pas ces observations gagnantes.
Le rendement médian du plafond reste proche de −5,16 %, coûts inclus : les
gains moyens proviennent d'une minorité de trajectoires favorables. Le SL dur
à 5 % limite les degrés de liberté, sans plafonner les pertes lors des gaps.

### Répétitions, concentration et incertitude

Le sous-échantillon non chevauchant par titre compte 105 /79 /56 candidats.
Son surplus du plafond face au meilleur constant reste +2,36 /+4,41 /+2,14
points. Le résultat n'est donc pas uniquement créé par le comptage répété
du même titre chaque jour. Mais ces petits comptes ne certifient pas une
capacité de prédiction, et cette sélection n'est pas un portefeuille.

Intervalles descriptifs par blocs de 63 séances pour le surplus face au meilleur
constant, échantillon quotidien : [2,44;3,77] /[2,85;4,47] /[0,71;3,49] points.
Seulement quatre blocs 2024/2025 et trois en 2026 : résolution limitée.
Dans le non-chevauchant 2026, intervalle [0;2,77] ; prudence renforcée.

Les 1 % d'observations les plus contributrices expliquent 8,25 /9,29 /8,95 %
du gain théorique face à REFERENCE. Les cinq premiers titres en expliquent
37,32 /42,92 /45,02 %. Ils ne sont ni supprimés ni utilisés pour choisir
des règles spécifiques après examen des résultats.

### Sensibilités et exclusions

- À 20 séances : surplus vs meilleur constant +2,98 /+3,29 /+3,12 points ;
  2026 qualifie 650 candidats, jusqu'au 11 septembre.
- À 60 séances avec coût hypothétique de liquidation des marques ouvertes :
  +3,68 /+3,92 /+3,25 points.
- Avec en plus financement unitaire hypothétique : +3,71 /+3,94 /+3,25 points.
  Ce ne sont pas les coûts complets de levier du portefeuille réel.
- Très peu de positions ouvertes à 60 : zéro COURT/REFERENCE, 0,78 /1,17 /0 %
  LARGE. Le label n'est néanmoins pas une sortie forcée au 60e jour.
- Exclusions principales : 2024 105 gaps >3 % ; 2025 141 gaps >3 % ; 2026
  165 gaps, 265 fenêtres immatures et une histoire J non qualifiée. Les 3 445
  candidats initiaux = 2 768 qualifiés +677 exclusions, sans remplacement.
  Aucune autre réserve de prix/identité dans ces fenêtres principales ; les
  contrôles existent et ne sont pas désactivés. L'exigence de maturité est
  conservée même si les profils sortent vite.

### Contrôles techniques et suite bornée

51 tests ciblés réussis (23 dédiés à cet audit, plus grille/activation natives).
**437 sorties archivées du portefeuille CatBoost** ont la même date, le même
prix et le même motif : stops 254, gaps SL 27, TP 93, trailing 46, gaps trailing
5 et gaps TP 12. Aucune sortie sautée dans ce contrôle. Cette parité porte sur
les protections, pas sur les coûts unitaires, le sizing ou le portefeuille entier.

Revue arithmétique distincte `completion-audit.json` : six cohortes, 5 682 lignes
qualifiées au total entre les deux horizons (donc pas 5 682 candidats uniques),
comptes exacts, dates, marques ouvertes, coûts et plafond recalculés. Empreintes
des fichiers/données/code présents revérifiées. Les 18 fichiers de poids/contrat
des trois anciens dossiers absents restent une réserve explicite ; aucune
substitution par les nouveaux modèles ni nouvel entraînement.

**Conclusion : la personnalisation dispose d'une marge rétrospective matérielle,
mais son apprentissage n'est pas démontré.** La prochaine étape proposée, sous
nouveau GO, est de qualifier les features disponibles à J et une population OOF
historique antérieure, avec fenêtres/labels disponibles et purge, pour vérifier
si un sélecteur peut prédire l'avantage d'un profil plutôt que memoriser ces
meilleurs choix futurs. Les trois profils et le témoin doivent rester figés.
2024–2026 déjà examinées ne seront pas présentées comme confirmation vierge.
Pas d'entraînement ni de test économique supplémentaire lancé dans ce GO.

Rapport : `artifacts/research/us_oracle_path_protection_headroom/20261014-v2/report.json`.
Revue : `completion-audit.json`. Détails : `counterfactuals.parquet`, `excluded.parquet`,
et sous-dossiers année/horizon. Le précontrôle v1 arrêté est conservé.
