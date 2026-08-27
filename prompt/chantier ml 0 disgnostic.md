Il faut toutefois séparer Oracle Extreme et Global Rank :

Pour Oracle Extreme, le TOP10% signifie « très forte probabilité de mouvement extrême ». Son BOTTOM10% signifie simplement « faible probabilité d'extrême », pas « SHORT ». Donc je ne donnerais pas de sens directionnel au BOTTOM10 Oracle.
Pour Global Rank, TOP10% et BOTTOM10% sont tous les deux intéressants : TOP10 comme candidats LONG naturels, BOTTOM10 comme candidats SHORT naturels, mais aussi pour vérifier les cas d’inversion.

Je demanderais à ton IA de faire le diagnostic suivant.

Expérience : persistent_tail_price_confirmation

Aucun réentraînement.
Aucun changement de risk management.
Aucun changement PROD.

Objectif : déterminer si la combinaison

persistance dans une queue du ranking
+
confirmation du prix sur N jours

permet d’obtenir davantage de vrais bons LONG/SHORT tout en conservant suffisamment de candidats.

Paramètres pré-enregistrés

Tester uniquement :

N = 2, 3, 4, 5

et :

X = 0%, 1%, 2%, 3%

Ne pas ajouter ensuite 0.5%, 1.5%, 2.5%, etc. en fonction des résultats.

A. Oracle Extreme

Pour Oracle, utiliser uniquement :

extreme_pct >= 0.90

soit TOP10% proba_extreme.

Pour chaque N :

persistent_extreme_N =
TOP10 Oracle à J
AND TOP10 à J-1
...
AND TOP10 à J-N+1

Calculer :

ret_N = close[J] / close[J-N] - 1
LONG

Pour X ∈ {0,1,2,3}% :

LONG_condition =
persistent_extreme_N
AND ret_N >= +X
SHORT
SHORT_condition =
persistent_extreme_N
AND ret_N <= -X

C'est particulièrement intéressant pour Oracle :

Oracle = "un gros mouvement semble persistant"
prix = "le marché nous montre déjà son sens"
B. Global Rank

Ici tester séparément :

predicted_TOP10  = global_rank >= 0.90
predicted_BOTTOM10 = global_rank <= 0.10

avec persistance pendant N jours.

Construire quatre diagnostics :

TOP10 persistant + prix +X
TOP10 persistant + prix -X

BOTTOM10 persistant + prix -X
BOTTOM10 persistant + prix +X

Cela permet justement de mesurer les inversions.

Les deux cas naturels sont :

LONG:
TOP10 persistant + hausse >= X

SHORT:
BOTTOM10 persistant + baisse <= -X

Mais conserver les deux cas contraires dans le rapport :

BOTTOM10 + hausse
TOP10 + baisse

car ils permettront de voir si certaines inversions du modèle sont systématiquement confirmées par le prix.

Et surtout, je ne choisirais pas la meilleure combinaison sur le seul rendement.

Pour chaque combinaison (source, tail, N, X, direction), fais produire :

métrique	pourquoi
n_signals	combien d'opportunités
signals_per_month	exploitable ou trop rare
coverage_vs_baseline	combien du pool on conserve
D1...D10	distribution complète réelle
BAD5 / GOOD5	qualité globale LONG
mean / median H20	payoff
P(return > 0)	hit-rate LONG
P(return < 0)	hit-rate SHORT
D10 rate	vrais très bons LONG
D1 rate	vrais très bons SHORT
D10/D1	qualité LONG
D1/D10	qualité SHORT
Pour LONG

Je créerais un score de qualité simple, pas forcément utilisé pour optimiser automatiquement :

LONG_quality =
GOOD5 - BAD5

et :

extreme_LONG_ratio =
D10 / D1

Tu veux simultanément :

D1 ↓
BAD5 ↓

D8/D9/D10 ↑
GOOD5 ↑

et suffisamment de signaux/mois
Pour SHORT

Exactement l'inverse :

D1 ↑
D2/D3 ↑

D8/D9/D10 ↓

avec :

extreme_SHORT_ratio =
D1 / D10
Le point que j'ajouterais absolument : fréquence

Tu as raison : une règle extraordinaire avec une entrée par mois peut être inutilisable.

Je demanderais donc explicitement :

signals_per_month
median_signals_per_month
p10_signals_per_month
months_with_zero_signal_pct

Exemple :

N=5, X=3%
D10 = 45%
D1 = 5%

peut sembler fantastique.

Mais si :

0.4 signal/mois

=> probablement pas intéressant pour ton système.

Alors qu'une règle :

N=3, X=1%
D10 = 32%
D1 = 13%
5.8 signaux/mois

peut être beaucoup plus exploitable.

Je ferais aussi un Pareto plutôt qu'un “meilleur paramètre”

Demande à ton IA de ne pas simplement annoncer le meilleur N/X.

Produire une frontière de compromis :

qualité directionnelle
vs
nombre de signaux

Par exemple :

N	X	signaux/mois	D1	D10	GOOD5	BAD5
2	0%	15	18%	27%	56%	44%
2	1%	11	15%	30%	60%	40%
3	1%	7	12%	34%	64%	36%
4	2%	3	8%	39%	70%	30%
5	3%	0.5	5%	44%	78%	22%

Je choisirais ensuite une zone de compromis raisonnable, pas forcément la dernière ligne.

Et il faut absolument tester la stabilité

Pour chaque combinaison :

2022
2023
2024
par semestre
par fold WF

Parce que sinon N=4, X=2% peut apparaître miraculeux uniquement en marché haussier.

Le critère intéressant serait quelque chose comme :

LONG:
D10/D1 > baseline
GOOD5 > baseline
mean H20 > baseline
fréquence suffisante
amélioration présente dans majorité des périodes

et symétriquement pour SHORT.

Ma préférence pour le premier diagnostic

Je commencerais par Oracle Extreme TOP10 persistant, parce que c'est exactement adapté à ton problème actuel :

Oracle:
"ce titre continue d'avoir un potentiel extrême"

+

prix:
"et depuis N jours le mouvement commence réellement
dans le sens LONG/SHORT"

Donc matrice initiale :

N = 2,3,4,5
X = 0%,1%,2%,3%

LONG  : ret_N >= +X
SHORT : ret_N <= -X

Seulement ensuite je ferais la même matrice sur Global Rank TOP10/BOTTOM10.

C'est un test très utile parce qu'il peut nous dire avant tout ML supplémentaire si le prix lui-même peut résoudre une partie du problème de direction que les 182 features n'ont pas réussi à résoudre.