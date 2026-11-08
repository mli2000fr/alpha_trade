# Qwen local, GPT et Winner sans LLM — comparaison 2025

Demande : mesurer le rendement et le taux gagnant, notamment parmi les achats
sur avis favorable, et comparer le modèle local à GPT et à l'absence de LLM.

## Analyses figées

204 candidatures communes, avec exactement les mêmes dossiers et le même
prompt. Qwen `qwen3.5-9b` et GPT `gpt-6-luna` ont déjà répondu ; aucun nouvel
appel n'est nécessaire. La collecte Qwen s'est terminée le 8 novembre à
11h20 Europe/Paris : 88 réponses valides, 38 dossiers sans news et 78 invalides.
Les invalides : 54 citations non exactes, 23 citations trop longues, une valeur
hors schéma. Les invalides restent archivées et ne deviennent pas des avis
baissiers ou neutres.

Qwen : 46 UNFAVORABLE/SUFFICIENT, 38 INDETERMINABLE (31 preuves insuffisantes,
7 suffisantes), 4 FAVORABLE/SUFFICIENT. Les 4 favorables concernent ZLAB le
1er mai, CARS les 21 et 22 octobre, CCJ le 19 novembre 2025, soit 3 sociétés.
Seulement 17 avis défavorables remplissent le contrat de veto mécanique.

## Comparaison financière

Même portefeuille 2025 : 4 000 USD, capacité margin 2×, risque 1,25 %,
poids maximal 20 %, entrée daily J+1 sans confirmation, SL5 sans TP/trailing,
sortie open11, contrôleur DD/B4 désactivé. Oracle H10 TOP10 % (179 candidats),
puis TOP10 LONG, score >0,70 et AUC calibration ≥0,60. Frais 8 points de base
par opération et financement annuel 6,5 %. Pas de filtre options.

Trois replays natifs : témoin sans LLM, veto Qwen avec invalides exclus,
achats réservés aux FAVORABLE Qwen valides. Dans le bras veto, les dossiers
sans news et les avis valides sans veto conservent la règle de référence.
Dans le bras favorable, ils sont exclus. Pas de remplissage des places libérées.
Les 4 favorables Qwen ont tous des preuves suffisantes : les deux règles
FAVORABLE et FAVORABLE/SUFFICIENT coïncident pour ce modèle.

Résultats GPT déjà calculés réutilisés après vérification du témoin commun.
Les prix et réponses restent scellés ; les empreintes du code actuel sont
enregistrées, ainsi que les différences avec le code d'inférence historique.
Le témoin doit reproduire tous les indicateurs financiers de référence avant
de publier la comparaison. SQL et HTTP interdits pendant le replay.

Suivi et résultats :
`artifacts/research/us_qwen_gpt_winner_comparison/20261108-v1`.
Programme : `scripts/research/us_qwen_gpt_winner_comparison_20261108.py`.
Test du masque de sélection : 1 passé.

## Résultats

Les trois replays sont terminés et le témoin reproduit tous les indicateurs
financiers de référence. GPT est réutilisé après vérification de ce témoin.

| Politique | Capital final USD | Rendement | DD maximal | Gagnants / clôturés | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sans LLM | 4 275,95 | +6,90 % | −10,86 % | 27/59 | 45,76 % |
| GPT veto + invalides exclus | 3 971,82 | −0,70 % | −12,98 % | 21/53 | 39,62 % |
| Qwen veto + invalides exclus | 4 016,50 | +0,41 % | −15,97 % | 19/49 | 38,78 % |
| GPT favorable uniquement | 4 111,96 | +2,80 % | −4,58 % | 5/9 | 55,56 % |
| GPT favorable + preuves suffisantes | 4 152,15 | +3,80 % | −3,52 % | 5/8 | 62,50 % |
| Qwen favorable uniquement, tous avec preuves suffisantes | 3 909,34 | −2,27 % | −2,89 % | 0/3 | 0,00 % |

Qwen favorable : 4 signaux mais 3 achats, car le second signal CARS tombe alors
que le titre est déjà détenu. Perte totale réalisée 90,66 USD, perte moyenne
30,22 USD. Capital engagé moyen 40,39 USD sur l'année, contre 211,31 USD pour
GPT favorable et 1 334,04 USD pour le témoin. Le faible DD Qwen favorable est
associé à une exposition presque nulle et ne démontre pas une bonne sélection.
Qwen veto : 109 candidatures conservées, 17 veto et 78 invalides exclus ;
capital engagé moyen 1 015,05 USD. GPT veto : 159 candidatures conservées.

Sur cet essai, aucun des deux filtres n'améliore le rendement du témoin.
GPT favorable a un taux gagnant descriptif supérieur, mais seulement 8/9 trades.
Les 3 pertes Qwen ne permettent pas de conclure sur tous les usages du modèle.
Les réponses invalides beaucoup plus fréquentes chez Qwen font aussi varier
fortement les occasions et l'exposition.

Étude rétrospective exploratoire ; versions des news et mémoire LLM non PIT,
année 2025 déjà observée. Le grand nombre de réponses invalides et les quelques
favorables interdisent d'interpréter le seul taux gagnant comme une probabilité
fiable ou une preuve de supériorité du modèle.
