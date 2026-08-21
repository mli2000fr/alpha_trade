Un backtest LONG à +35 % pendant un marché où presque toutes les actions montent ne prouve pas que le modèle a de l’alpha. Il peut simplement avoir capturé le bêta du marché.

Pour ton système, je ferais un chantier séparé, par exemple E27 — LONG Alpha Attribution, dont la question n’est plus « est-ce que le portefeuille gagne ? », mais :

Est-ce que les actions choisies par le modèle gagnent davantage que des actions qu’il aurait pu choisir au hasard, au même moment et avec les mêmes contraintes ?

Le test n°1 : TOP vs marché, mais surtout TOP vs RANDOM

À chaque date D où ton système sélectionne ses LONG :

MODEL
= vrais titres choisis par B25


RANDOM
= même nombre de titres
  tirés dans l'univers éligible ce même jour


Même date d'entrée
Même durée
Même C2
Même B4
Même sizing
Même coûts
Même exécution

Tu répètes le portefeuille RANDOM, par exemple 1 000 fois.

Tu obtiens une distribution :

                    distribution RANDOM
                ┌─────────────────────────┐
                │     ███████████         │
                │   ███████████████       │
                │ ███████████████████     │
───────────────┴──────────────────────────────
             10%       25%       40%


                                      ▲
                                  B25 = 35%

Si B25 fait +35 %, mais la médiane random fait +32 %, ce n’est pas impressionnant.

Si B25 fait +35 % alors que la médiane random fait +15 %, le 95e percentile +24 % et le 99e +29 %, là tu as une vraie preuve que la sélection apporte quelque chose.

Encore plus important : neutraliser le bêta

Ton random doit être comparable au modèle.

Si B25 sélectionne naturellement des mid-caps high-beta/momentum, comparer B25 à SPY n'est pas suffisant. Je voudrais au minimum :

R0 — SPY
benchmark marché.

R1 — Random universe
même nombre de positions aux mêmes dates.

R2 — Random sector-matched
si B25 choisit 2 Tech + 2 Industrials + 1 Healthcare, le random doit reproduire cette composition.

R3 — Random beta/size-matched
chaque sélection B25 est remplacée par un titre de bêta, capitalisation et idéalement volatilité similaires.

R3 devient particulièrement intéressant : si B25 le bat, le gain est beaucoup plus difficile à expliquer simplement par « le modèle choisit des actions risquées dans un bull market ».

Le test le plus pur pour ton rank

Tu peux même enlever complètement C2/B4/sizing.

Pour chaque jour :

Alpha
H
	​

=Return(TOP
B25
	​

,H)−Return(Random,H)

et surtout :

Spread
H
	​

=Return(TOP
B25
	​

,H)−Return(BOTTOM
B25
	​

,H)

pour H5/H10/H15/H20.

Par exemple :

2025 BULL	H10
Marché éligible	+2.1%
Random	+2.0%
TOP B25	+3.4%
BOTTOM B25	+0.8%
TOP − Random	+1.4 pp
TOP − BOTTOM	+2.6 pp

Même si 80 % des titres montent, ce serait une excellente preuve : B25 ne prédit pas simplement « ça monte », il classe correctement les gagnants relatifs.

À l'inverse :

TOP       +3.0%
Random    +3.1%
BOTTOM    +2.9%

Ton portefeuille peut être extrêmement rentable et pourtant le modèle n'apporte pratiquement aucune sélection.

Et il faut absolument tester par régime

C'est là que ton interrogation devient vraiment intéressante.

Je ferais :

Régime	TOP B25	Random	TOP−Random	TOP−BOTTOM
BULL				
CORRECTION				
SLIDE				
REBOUND				

Tu pourrais découvrir par exemple que B25 possède :

un excellent alpha relatif en BULL ;
encore un petit alpha en CORRECTION ;
aucun alpha en SLIDE ;
un très fort alpha en REBOUND.

Ce serait parfaitement compatible avec une stratégie LONG-only + B4 : B4 réduit l'exposition quand les conditions sont mauvaises, et le modèle reprend son travail lorsque son pouvoir de classement revient.

Je rajouterais un test particulièrement sévère : le placebo rank

À chaque date, shuffle les ranks entre les symboles, puis fais exactement la sélection B25.

1 000 permutations donnent la distribution du résultat sous :

H
0
	​

:le rank B25 ne contient aucune information

Tu regardes ensuite où tombe le vrai B25.

Si :

1000 ranks randomisés


médiane       IC = 0.000
95e pct       IC = 0.008
99e pct       IC = 0.012


B25 réel      IC = 0.026
                     ↑

c'est beaucoup plus convaincant que « mon backtest fait +35 % ».

Et ton historique possède déjà un avertissement

Tu as déjà observé quelque chose d'important : le global rank historique avait un IC positif, mais il s'est inversé sur certaines fenêtres 2026. Donc je ne me contenterais surtout pas d'un résultat agrégé 2023–2026.

Je demanderais :

2018
2019
2020
2021
2022
2023
2024
2025 OOS
2026 OOS


+ BULL/CORRECTION/SLIDE/REBOUND

Le modèle doit battre le random sur plusieurs périodes indépendantes, pas simplement énormément le battre pendant une seule année.

Ce que je demanderais à ton IA

Tu peux lui donner cette spécification :

E27 — LONG Alpha Attribution

Objectif : déterminer si le LONG B25 possède un véritable pouvoir de sélection, indépendamment de la hausse générale du marché.

Ne modifier aucun modèle, seuil, feature, trailing, breaker ou sizing.

Test A — Rank pur : pour chaque date PIT et H5/H10/H15/H20, comparer les forward returns de TOP10 B25, univers complet, BOTTOM10 et 1 000 sélections RANDOM de même taille.

Mesurer TOP−Random, TOP−Universe, TOP−BOTTOM, Rank IC et hit rate.

Test B — Placebo permutation : permuter le rank entre symboles à chaque date 1 000 fois et comparer le véritable rank à la distribution nulle.

Test C — matched controls : comparer les sélections B25 à des sélections random de même secteur, puis idéalement secteur+bêta+volatilité+size.

Test D — stabilité : résultats par année et par régime BULL/CORRECTION/SLIDE/REBOUND. Aucune conclusion fondée uniquement sur l'agrégat.

Test E — portefeuille : seulement après validation du rank pur, comparer B25 réel à 1 000 portefeuilles random avec exactement les mêmes dates, nombre de positions, sizing, coûts, C2 et B4.

Rapporter le percentile du portefeuille B25 dans la distribution random et une p-value empirique.

Interdiction de tuner quoi que ce soit à partir des résultats.

Verdict :

GO fort si B25 bat significativement Random/matched-random, TOP−BOTTOM est positif et la propriété est stable OOS ;
GO faible si le portefeuille gagne mais l'avantage vs random est petit/instable ;
NO-GO alpha si B25 ne bat pas random : les profits LONG proviennent essentiellement du bêta/exposition/mécanique de portefeuille.

À mon sens, E27 est même plus important que le nouveau modèle SHORT. Avant de chercher une deuxième source d'alpha, il vaut mieux établir précisément combien d'alpha possède réellement la première.