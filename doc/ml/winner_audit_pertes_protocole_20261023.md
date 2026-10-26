# Winner seul : diagnostic borné des pertes 2025–2026

GO du 23 octobre 2026 après les deux essais de veto. Audit descriptif, sans
nouvel entraînement, simulation économique, téléchargement, SQL ou ordre.
Référence exclusive : `us_winner_bottom_rank_filter/20261022-v2`, WINNER_ONLY.
Ne pas mélanger l'ancien HALF_CONTROL +12,92 % : autre contrat et autres rangs.

## Population et contrôles avant lecture des signatures

Tous les fills d'achat réels et tous les trades clôturés, pas seulement les
perdants : 53 clôtures 2025 (9/44), 120 clôtures 2026 (38/82), six positions
2026 ouvertes à part. Vérifier le rapport, son audit, les reçus SIP, les
campagnes, les frais/PnL et le rattachement exact signal → campagne → fill.
SL 7 %, trailing 15 %, sans TP, demi-position, risque natif, pas d'ajout.
Les deux années sont déjà observées : aucun nouveau holdout indépendant.

## Définitions figées, sans optimisation de seuil

Une unité R en prix = 7 % du prix d'entrée, pas le risque effectivement alloué
en dollars. Décrire chaque trade gagnant ET perdant avec mêmes mesures.

- MFE/MAE pendant détention : inclure les barres entièrement antérieures à
  la sortie et son prix. Un STOP est horodaté au début de sa bougie dans ce
  replay ; le high/low de cette bougie ne donne pas l'ordre des événements.
  Publier une borne inférieure certaine et une borne supérieure OHLC, jamais
  supposer que le high a précédé le stop. Sorties à l'open : exclure toute
  excursion ultérieure de leur bougie.
- Faux départ immédiat : les deux premières clôtures 5m après le fill sont
  toutes deux sous le plus haut de la veille, et disponibles AVANT la sortie.
  Absence de ces deux clôtures = non observé, pas absence de faux départ.
- Gain restitué : perdant net après MFE certaine >= 1R. Ce n'est pas une vente
  possible au sommet ni une preuve qu'un TP aurait amélioré le portefeuille.
- Rebond post-stop : clôture 5m >= entrée +1R après la bougie du stop, avant
  la fin de la 20e séance de détention théorique (entrée incluse). Exiger
  une fenêtre régulière complète, sans OST connue ; sinon inconnu/censuré.
  Donner délai, plus bas depuis l'entrée avant ce rebond et récupération du
  seuil de rentabilité frais inclus. Aucun maintien contrefactuel valorisé.
- Fenêtre complète sans ces signatures : résidu descriptif, PAS preuve
  d'« absence de tendance ». Sorties/réentrées, périodes censurées et
  ambiguïtés OHLC sont explicites.

Flags non exclusifs conservés. Partition principale des pertes : gain restitué,
puis faux départ, puis rebond post-stop, puis ambiguïté de bougie de sortie,
puis résidu sans ces signatures si fenêtre complète, sinon inconnu/censuré.
Cet ordre est comptable ; ne signifie pas causalité exclusive.

## Informations d'entrée : séparation chronologique

Table différente des diagnostics futurs. Onze sondes figées : rang Oracle du
vrai signal, âge du signal en séances, heure d'entrée, extension de la dernière
clôture confirmée au-dessus du plus haut précédent (en ATR14), gap d'ouverture,
volume des deux bougies de confirmation / mêmes créneaux de la veille,
momentum20, écart MA20, ATR14 du titre sur séances SIP précédentes, momentum20
et volatilité20 SPY du cache daily split déjà archivé. Pas de remplacement de
valeurs manquantes. Sessions SIP passées complètes ; aucun cours ou volume du
reste de la journée d'entrée n'entre dans une sonde.

Comparer médianes gagnants/perdants et AUC orientée par hypothèse écrite dans
le manifeste, séparément par année, avec couverture/classes/titres/dates.
Pas de seuil choisi, classement des meilleurs signaux, p-value promotionnelle,
modèle, filtre, PnL ou taux gagnant contrefactuel. Sensibilité descriptive par
symbole : fenêtres de vingt séances non chevauchantes sélectionnées dans
l'ordre du temps, sans regarder les résultats ; dépendance marché persistante.
Contrôles préfixes : tronquer tous les prix à l'entrée ne change aucune sonde.

## Limites et livrables

Les six positions ouvertes ne sont ni gagnantes ni perdantes réalisées ; elles
restent dans l'inventaire et ne servent pas au calcul du taux gagnant.
2026 arrêté au 30 septembre. Cohorte amont déjà conditionnée par couverture
future, univers survivant, secteurs actuels, inventaire OST non exhaustif,
daily SPY révisable : pas certification PIT ni parité quote/fill live.
L'arrêt B4 du compte 2025 et l'exposition changent les trades observés.
Un rebond post-stop ne justifie jamais de desserrer les stops réels.

Livrer une ligne par achat, table des clôtures et signatures, partitions et
flags par année, sondes d'entrée et couverture, concentrations temporelles/
symboles, contrôles de réconciliation, bilan français et registre ML actualisé.
Sources et protocole scellés par SHA256 ; même assistant ≠ revue humaine.
