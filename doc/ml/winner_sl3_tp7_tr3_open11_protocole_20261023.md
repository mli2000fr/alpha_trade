# Winner : SL3 / TP7 / trailing3 / open11

GO du 23 octobre2026. Un seul jeu de paramètres, deux années2025/2026au30/09.
Recherche locale, aucun modèle, SQL, téléchargement, ordre, YAML ou moteur de
production modifié. Pas de nouvelle grille ni optimisation des seuils.

## Contrat figé

Comparer au WINNER_ONLY natif déjà calculé et audité dans
`artifacts/research/us_winner_bottom_rank_filter/20261022-v2` : SL7/TR15/sansTP,
vingt séances depuis le fill puis open21. Réutiliser ses résultats scellés,
pas ceux du HALF_CONTROL historique+12,92 % ; ne pas mélanger les cohortes.

Variante : SL initial3 %, TP7 %, trailing3 % sous le plus haut des bougies5m
déjà terminées depuis le fill, jamais sous le stop précédent. Dix séances de
détention entrée incluse, puis vente à l'ouverture de la11e séance. Les arrondis
au cent, priorité stop sur collision OHLC, gap stop au prix ouvert et TP gap
plafonné suivent le runtime natif ; ce ne sont pas des prix garantis en live.
Les sorties intrabar sont horodatées FIN de bougie dans le moteur ; les gaps
et ouvertures à son début. Ne pas utiliser le high futur pour remonter un stop
pendant sa propre bougie. La fin de séance peut aussi remonter le stop sur les
hauts devenus connus et produire une sortie au cours de clôture.

Conserver : les mêmes TOP10 Oracle parcours H20 annuels, l'attente maximale de
vingt séances après signal, la confirmation d'entrée deux clôtures5m au-dessus
du haut raw de la veille après un franchissement frais, demi-position, aucun
renforcement/réachat d'un titre détenu, priorité Oracle. Aucun veto/filtre ATR
ou directionnel nouveau. L'Oracle reste H20 ; seul le contrat de sortie change.

Capital4000USD indépendant parannée, frais canoniques8bps/jambe, risque natif
et B4DD15, plafond effectif d'exposition1x malgré autorisation YAML2x. Même
formule de sizing et plafonds : **pas mêmes quantités** avec un SL plus court,
ni mêmes trades après divergence de cash/risque. Horizon10 ne raccourcit pas
la durée d'attente20 ; ne pas refaire une sélection sur couvertureJ+30.

## Entrées et vérification

Reprendre les données SIP5m/raw/régulières/nonremplies et les1428/1027signaux
admissibles du témoin, sur2510/1880signaux initiaux. Recalculer la qualification
communeJ+40 et vérifier son identité exacte, pas de nouvelle réserve liée aux
résultats de la variante. Snapshot et daily/secteurs existants scellés ; aucun
accès base ni API. Sizing entier : seul le refus technique natif d'une
demi-position arrondie à zéro est isolé, comme le témoin ; jamais arrondi au-dessus.

Réutiliser l'adaptateur de staging entier et le cache readonly du calendrier.
Substitutions limitées au processus de recherche, restaurées à la sortie.
Les paramètres du témoin sont lus du manifeste historique, pas du YAML courant.

Smoke préalable cinq séances2025 : validation technique, pas résultat annuel.
Deux comptes complets ensuite, artefacts parannée, progression et reprise des
comptes déjà terminés. Toute erreur garde un statut en échec ; aucun bilan final
promu si couverture/runtime/audit incomplet.

Auditeur séparé : achats retenus et frais/cash/positions, prix et heures de
sortie par un parcours scalaire indépendant, TP/SL/gaps/collisions/ratchet,
trailing effectif seulement après observation, open11 officiel, DD et métriques.
Ne pas réduire une sortie intrabar à un ordre high/low inventé.

Publier capital final, rendement net, DDmax, gagnants/perdants et pourcentages,
gains/pertes moyens et cumulés, durées, capital utilisé moyen/max, frais,
exposition B4, positions ouvertes MTM et différence au témoin. Seuil théorique
SL3/TP7 sans trailing n'est PAS le taux de rentabilité de cette stratégie :
les sorties trailing/horizon/gaps changent les gains/pertes effectivement réalisés.

Années déjà examinées, pas de holdout indépendant. Cohorte conditionnée par
couverture future, univers survivant, secteurs actuels et dailySPYsplit révisable.
Inventaire OST parent vide/non exhaustif : aucune preuve d'absence d'opération,
pas parité quotes/fills/live intégrale. Même assistant ≠ revue humaine indépendante.
