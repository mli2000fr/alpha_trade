# TOP10 Oracle H10 — confirmation J−1/J/J+1, TP10/SL5

## Conclusion

**TERMINÉ / EXPLORATOIRE / PAS DE PROMOTION.** La confirmation par trois
clôtures strictement croissantes/décroissantes ne fait pas apparaître un signal
directionnel transversal. LONG presque à l'équilibre en 2024, perdant en
2025–2026 ; SHORT perdant chaque année. La combinaison LONG/SHORT reste
négative dans les trois années sur les occasions quotidiennes répétées.

Ce ne sont pas des rendements annuels de capital : les chiffres ci-dessous
sont des moyennes par occasion, après frictions hypothétiques. Aucun portefeuille
avec capital limité, levier, déduplication de positions ou marge réelle n'est simulé.

## Règle figée avant calcul

Demande du 19 octobre, précisée par l'utilisateur : **TOP10**, pas TOP20 %.

- Scores Oracle **H10 d'amplitude** issus de la comparaison dédiée précédente :
  même modèle annuel pour les signaux de chaque année, entraînements antérieurs
  aux dates testées dans les folds. Aucun nouveau réentraînement.
- Les dix premiers scores à **J** restent figés. Aucun reclassement à J+1,
  remplacement d'un titre non confirmé ou sélection par son rendement futur.
- LONG si `close_ajusté(J−1) < close_ajusté(J) < close_ajusté(J+1)`.
- SHORT si les trois clôtures sont strictement décroissantes. Cela signifie
  deux variations entre trois clôtures, pas trois rendements quotidiens positifs.
- Sinon abstention : une hausse entre les deux extrémités ne suffit pas si la
  clôture intermédiaire ne respecte pas l'ordre. Égalité ou valeur inconnue :
  pas de confirmation.
- Le signal n'est connu qu'à la **clôture de J+1**. Entrée **open J+2**, et non
  J ou J+1. Dix séances de détention maximum **entrée comprise** : expiration
  close J+11 si aucun seuil. Ce n'est pas une expiration fixe à J+10.
- TP10 %, SL5 %, sans trailing. SHORT : TP à −10 % du prix d'entrée,
  stop à +5 %. Gap défavorable exécuté à l'open, TP au prix limite ; collision
  OHLC stop-first sauf ouverture départageant les barrières.
- Frictions inchangées : 8 bps par jambe, emprunt SHORT supposé 0,3 %/an.
- Référence sans confirmation : mêmes dix titres, **même entrée J+2**, mêmes
  protections et durée, tous LONG ou tous SHORT séparément.
- Contrôles sur les mêmes paires confirmées : ignorer la direction de la règle
  et les acheter toutes LONG, ou les shorter toutes. Pas de choix du meilleur
  bras après observation pour annoncer un gain prédictif.

Sources de scores :
`artifacts/research/us_h10_h20_frozen_comparison/20261019-v1/{année}-H10-scores.parquet`.
Ce ne sont pas les scores des anciens modèles H20 annuels de production.
Prix : copie normalisée et réserves du
[contrôle H10/H20](oracle_h10_h20_prix_et_comparaison_20261019.md), sans nouvelle
requête fournisseur ni écriture SQL.

## Résultats par occasion

2024/2025 : dates de signal annuelles ; 2026 : du 2 janvier au **1er septembre**,
comme la comparaison précédente, observations de prix bornées au 30 septembre.

| Signaux | LONG confirmés | Gagnants LONG | Moyenne LONG | SHORT confirmés | Gagnants SHORT | Moyenne SHORT | Moyenne sens combinés |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 520 | 37,31 % | +0,046 % | 691 | 30,82 % | −1,208 % | −0,669 % |
| 2025 | 568 | 32,22 % | −0,679 % | 628 | 30,10 % | −1,107 % | −0,904 % |
| 2026 | 447 | 34,90 % | −0,097 % | 413 | 30,51 % | −0,936 % | −0,500 % |

Gagnant = résultat net strictement positif ; ce n'est pas nécessairement une
touche TP. Le taux gagnant ne mesure pas le signe du rendement terminal à dix
séances indépendamment des protections.

| Signaux | Sans confirmation, tous LONG | Sans confirmation, tous SHORT | Confirmés, tous LONG sans utiliser leur sens | Confirmés, tous SHORT sans utiliser leur sens |
| --- | ---: | ---: | ---: | ---: |
| 2024 | +0,110 % | −0,738 % | +0,226 % | −1,049 % |
| 2025 | +0,232 % | −1,056 % | −0,088 % | −1,016 % |
| 2026 | +0,127 % | −0,387 % | +0,222 % | −0,689 % |

La règle ne fait mieux ni que la référence tous LONG sur la moyenne des LONG,
ni que tous SHORT sur celle des SHORT. Le choix de sens est aussi moins bon que
tous LONG sur les **mêmes couples confirmés**, dans les trois années. Les
intervalles descriptifs par blocs du supplément LONG/SHORT confirmé face à
l'ensemble du TOP10 de même sens comprennent zéro dans chaque année ; pas de
preuve de gain robuste, ni d'inférence précise de causalité.

### Sans chevauchement

Contrôle earliest-first par titre/sens : attendre la fin de la fenêtre entière
de dix séances avant une nouvelle entrée du même titre/sens. Ce n'est pas un
portefeuille agrégé : deux sens d'un titre sont traités séparément et il n'y a
pas de limite de positions ou de capital.

| Signaux | LONG : épisodes / moyenne | SHORT : épisodes / moyenne | Combiné : épisodes / moyenne |
| --- | ---: | ---: | ---: |
| 2024 | 239 / −0,254 % | 289 / −0,486 % | 528 / −0,381 % |
| 2025 | 239 / −0,346 % | 251 / −0,900 % | 490 / −0,630 % |
| 2026 | 175 / +0,117 % | 178 / +0,029 % | 353 / +0,072 % |

Le petit gain 2026 de ce contrôle ne se retrouve pas en 2024/2025 et ne suffit
pas à qualifier la stratégie.

## Couverture, coûts et risque

669 dates × dix titres = **6 690 couples titre/date**, 161 symboles distincts.
Tous disposent du parcours qualifié requis dans cette sous-population ;
**13 380 issues** LONG/SHORT calculées. Aucun titre manquant remplacé.

| Signaux | TOP10 total | Confirmés LONG ou SHORT | Abstentions | Part confirmée |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 2 520 | 1 211 | 1 309 | 48,06 % |
| 2025 | 2 500 | 1 196 | 1 304 | 47,84 % |
| 2026 | 1 670 | 860 | 810 | 51,50 % |

Un SL5 n'est **pas une perte garantie limitée à 5 %**. Les gaps de stop
concernent environ 6,2 / 6,9 / 8,4 % des occasions retenues, sens combinés.
Exemple d'archive, non certification de fill : MP signal SHORT du 3 juillet
2025, entrée 8 juillet à 31,25, sortie gap trois séances après l'entrée à
48,10 ; perte nette simulée −54,13 %. Le calcul ne transforme pas cet open
en fill fictif à +5 %. Les coûts d'emprunt, locates et liquidations réels ne
sont pas reconstitués ; prix ajustés et opérations sur titres restent soumis
aux réserves de la qualification précédente.

Univers courant survivant, périodes déjà explorées, pas de nouveau holdout
prospectif. La confirmation observée avant l'entrée élimine le biais grossier
d'achat à J avec connaissance de J+1 ; elle ne certifie pas toute la chaîne PIT
des anciennes features ni l'exécution réelle.

## Validation et artefacts

**105 tests passent**, dont quatorze tests de cette règle : confirmation stricte,
absence de dépendance à J+2 pour le sens, entrée retardée, échéance, stop5,
collision, ajustement mécanique, trous et réserves. Audit
`PASS_EXPLORATORY_ONLY` : TOP10 d'origine reproduit, confirmation avant entrée,
**13 380 sorties recalculées par une boucle scalaire séparée**, frais, nombres,
moyennes et contrôle sans chevauchement vérifiés.

Dossier : `artifacts/research/us_top10_three_session_confirmation/20261019-v1/`.
`protocol.json`, `selected-at-j.parquet`, `qualification.parquet`,
`evaluations.parquet`, `comparison.csv`, `report.json`, `final-audit.json`,
`progress.json`, checkpoints par tranche sous `parts/`.

Scripts de recherche : `us_top10_three_session_confirmation` (phases
`prepare/build/summarize/all`) et `us_top10_three_session_confirmation_audit`.
Aucun modèle, paramètre, batch, donnée SQL ou ordre de production modifié.
Aucun appel fournisseur/LLM, réentraînement ni balayage de seuils.
