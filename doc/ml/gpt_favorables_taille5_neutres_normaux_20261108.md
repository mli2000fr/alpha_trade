# GPT : favorables taille5, neutres normaux, défavorables exclus — 2025

## Demande et règles

L'utilisateur demande de multiplier les achats favorables par5 en levant les
limites de montant qui empêchent ce dimensionnement. Clarification reçue :
conserver les avis indéterminables et les dossiers sans news à taille normale.
Les réponses invalides restent exclues conformément au test précédent.

Sur204 candidatures :17 FAVORABLE à taille visée5×,79 INDETERMINABLE et38 sans
news à taille normale,59 UNFAVORABLE et11 invalides exclus.134 candidatures
retenues. Les59 défavorables comprennent les25 avis défavorables qui n'avaient
pas satisfait tous les critères de veto du premier protocole ; ce n'est donc
pas exactement la sélection à34 vetoes du test initial.

Deux nouveaux replays : **GPT_MIXED_NORMAL** garde la même sélection134 à taille
normale ; **GPT_MIXED_BOOST5** applique la demande. Comparaison supplémentaire
avec le témoin Winner seul et les variantes favorables déjà terminées.

## Dimensionnement réel

Les budgets d'entrée et de revalidation natifs sont multipliés pour chaque
favorabilité, sans modifier les fichiers du moteur ni la production :

- Favorable : risque budgété1,25 % →6,25 %, poids maximum20 % →100 % du capital courant.
- Indéterminable/sans news :1,25 % et20 %, inchangés.
- Capacité totale du compte margin et plafond brut2× conservés ; disponibilité
  du capital réévaluée après chaque fill, réserves de frais, quantités entières,
  historique, doublons et contrôles de répétition toujours respectés.
- SL5 %, sans TP/trailing, dix séances puis open11, entrée journalière J+1.
  Contrôleurs DD/B4 et facteurs désactivés comme dans la référence.

Le5× est une taille visée avant contraintes de capacité, avec capital courant
et arrondi ; ce n'est pas cinq fois le PnL d'un ancien fichier de trades.
Un adaptateur limité au processus de recherche raccorde le budget augmenté
à la création du plan **et** à sa revalidation ; le test natif vérifie les
quantités d'un titre renforcé et d'un titre normal, les frais intermédiaires,
le maintien du plafond2× et le rétablissement des fonctions après la simulation.

Source : `artifacts/research/us_gpt_winner_ab/20261107-v1`, reçus en lecture seule,
sans aucun nouvel appel GPT. Programme : `scripts/research/us_gpt_winner_boost_favorable.py`.
Sortie : `artifacts/research/us_gpt_winner_boost_favorable/20261108-v1`.

## Résultats

2025, capital initial4 000 USD, frais8 points de base par opération et financement
6,5 % annuel. Même référence Oracle H10 → per-symbol LONG que les précédents
tests GPT ; aucune modification de l'IHM de production ou de modèle entraîné.

| Politique | Capital final | Rendement | DD max | Gagnants / perdants | Taux gagnant | Capital moyen engagé |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Winner seul | 4 275,95 $ | +6,90 % | −10,86 % | 27 / 32 | 45,76 % | 1 334,04 $ |
| Même sélection GPT, tailles normales | 3 969,02 $ | −0,77 % | −12,98 % | 18 / 29 | 38,30 % | 935,24 $ |
| Favorables5×, neutres/sans news normaux | 4 264,90 $ | +6,62 % | −18,55 % | 18 / 29 | 38,30 % | 1 504,02 $ |

Le renforcement ajoute295,88 $ à la sélection GPT à taille normale, avec un DD
aggravé de5,57 points. Par rapport à Winner seul :−11,05 $ et DD aggravé de7,70
points. Frais83,62 $ et financement3,25 $ pour le bras5×, capital engagé maximal
5 073,61 $. Le taux gagnant de38,30 % ne s'améliore pas par le seul changement
de quantités ; les47 trades clôturés ont18 gagnants et29 perdants.

Les reçus, textes et requêtes d'origine restent inchangés. Les résultats restent
exploratoires : cohortes peu nombreuses, versions historiques/PIT non certifiées,
mémoire future possible du LLM, secteurs actuels et protections5m avec repli
daily lorsque nécessaire. Pas de validation indépendante ni parité live.
