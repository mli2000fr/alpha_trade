# E21-B4 — Validation indépendante du lecteur de tableaux

> **Piste fermée — CLOSED / SUSPENDED_DATA_NOT_READY, 15 septembre 2026.**
> Les itérations B4 à B8 sont terminées. Aucun B9 ne doit être lancé avec la
> chaîne actuelle et aucun candidat extrait ne doit devenir un label ML.

## Pré-enregistrement avant collecte et lecture

Date : 15 septembre 2026. Les règles de `guidance_tables.py` sont gelées avant
la collecte. Émetteurs non consultés pendant leur développement : Salesforce
(`CRM`), Best Buy (`BBY`) et FedEx (`FDX`). Fenêtre : 2024-01-01 à 2024-12-31.
Maximum douze dépôts 8-K éligibles par émetteur, deux annexes texte par dépôt,
deux pages anciennes au maximum. Aucun rendement n'intervient dans la sélection.

Le corpus doit être analysé sans retoucher les règles. Toute correction fondée
sur ces documents transforme E21-B4 en corpus de développement et impose une
nouvelle validation sur d'autres émetteurs.

## Référence à produire

Annoter tous les candidats de fourchettes dollar avec exactement un rôle :
`NEW_FORECAST`, `PRIOR_FORECAST`, `REALIZED_RESULT`, `NOT_A_RANGE` ou
`AMBIGUOUS`. Les répétitions titre/corps sont conservées pour mesurer le
parseur, mais identifiées comme dépendantes. Annoter aussi, par lecture de
l'annexe complète, les fourchettes appartenant à ces rôles mais manquées par
le détecteur afin d'estimer son rappel documentaire.

Une comparaison avec l'exercice précédent est `REALIZED_RESULT`, jamais
`PRIOR_FORECAST`. Une fourchette de bilan reliant deux dates via `respectively`
est `NOT_A_RANGE`. Une ancienne guidance exige une indication explicite
prior/previous/compared to dans un contexte prospectif. Les tables de targets
sont `NEW_FORECAST`. En cas de doute réel, `AMBIGUOUS`.

## Mesures pré-enregistrées

- matrice de confusion par rôle ;
- précision parmi les candidats classés ;
- couverture et taux d'abstention ;
- rappel des prévisions actuelles, anciennes et résultats détectables ;
- résultats séparés phrases/tableaux et par émetteur ;
- faux intervalles classés à tort ;
- support brut et nombre de publications uniques pour chaque chiffre.

Aucun pourcentage isolé ne sera interprété si son support est inférieur à dix
candidats et trois publications. Une classe absente ou trop petite est
`NOT_VALIDATED`, jamais parfaite. Gate technique provisoire, fixé avant
lecture : aucun faux intervalle accepté ; précision classée >=95% ; couverture
NEW_FORECAST >=80% ; les autres rôles restent soumis au support minimal.
Ce gate ne rend pas les données ML-ready : mesure/période/unité/définition et
disponibilité PIT doivent encore franchir leurs contrôles séparés.

Run : `artifacts/research/guidance_historical_backfill/e21b4-new-issuers-2024-v1`.
Logs : `log/batch/e21b4-new-issuers-2024-v1/`. Aucun batch quotidien, table,
entraînement ou backtest concerné.

## Résultats sans adaptation des règles

Collecte : CRM cinq dépôts, BBY quatre, FDX cinq ; 14 annexes téléchargées,
zéro erreur, inventaires non tronqués. Après déduplication, l'extraction porte
sur 12 publications ayant produit 99 candidats.

Revue exhaustive assistant des 99 candidats :

- 76 nouvelles prévisions ;
- neuf anciennes prévisions ;
- 14 faux intervalles ;
- aucun véritable intervalle de résultat réalisé.

Matrice des règles gelées :

| Référence | NEW prédit | PRIOR prédit | Abstention | Support |
|---|---:|---:|---:|---:|
| NEW_FORECAST | 11 | 0 | 65 | 76 |
| PRIOR_FORECAST | 0 | 5 | 4 | 9 |
| NOT_A_RANGE | 0 | 1 | 13 | 14 |

Précision parmi les 17 candidats classés : **16/17 = 94,1 %**. Couverture
globale : 17/99 = 17,2 %. Couverture NEW : 11/76 = **14,5 %**. Couverture
PRIOR : 5/9 = 55,6 %, mais support inférieur au minimum pré-enregistré.
REALIZED_RESULT est absent et donc `NOT_VALIDATED`.

Les trois gates échouent : précision sous 95 %, couverture NEW sous 80 % et
un faux intervalle accepté. Ce dernier est causé par une note XBRL au milieu
de la fourchette FedEx : l'intention `$18.25 to $20.25` devient numériquement
`$18.25 to 2 $20.25`; le parseur extrait 18,25–2 et le classe PRIOR. Il s'agit
simultanément d'un faux candidat et d'une ancienne prévision correctement
présente dans le texte mais manquée avec ses vraies bornes.

Pourquoi la couverture chute malgré le succès Adobe : beaucoup de tableaux
CRM/BBY portent un heading générique `Guidance` plutôt que la formule Adobe
`following table summarizes ... targets`. Les tableaux FedEx portent
`Fiscal ... Earnings Per Share Forecast`, formulation non autorisée dans les
règles gelées. Nous n'élargissons pas les règles après lecture de ce corpus.

Verdict : **FAIL — règles de rôles non généralisées**. Cela n'invalide pas la
collecte SEC ni l'information de guidance ; cela interdit de construire des
labels automatiquement avec cette version. `role_reference.json` est lié au
SHA256 de la queue et `validation_report.json` contient la matrice et les gates.
Aucun rendement consulté, aucun entraînement/backtest, aucune table modifiée.

## E21-B6 / V3 pré-enregistré

Après l'échec B5, V3 traite explicitement `from OLD to NEW`, les en-têtes en
cellules `td` avec `colspan`, et les annexes aux noms `pressrelease` sous liste
de motifs et validation de chemin. ABBV/ANF/CPB deviennent développement.

Smoke développement : 15 NEW, sept PRIOR et une abstention sur 23 candidats,
conforme aux rôles annotés B5 pour NEW/PRIOR. Ce n'est pas une confirmation.
Nouvelle confirmation, choisie avant lecture : BorgWarner (`BWA`), Crown
Holdings (`CCK`) et BJ's Wholesale (`BJ`), année 2024, douze 8-K et deux
annexes maximum. Gates identiques ; aucune adaptation après lecture.

Une prochaine version devra gérer les notes inline et définir une grammaire
d'en-têtes générique (`Guidance`, `Forecast`, `Targets`) en contrôlant leur
portée. Comme CRM/BBY/FDX ont désormais été lus, ils devront devenir corpus de
développement ; la confirmation suivante exigera encore d'autres émetteurs.

## E21-B5 pré-enregistré avant modification

V2 autorisée après l'échec : rejeter une seconde borne immédiatement suivie
d'un autre montant dollar (note inline), les bornes décroissantes et les
constructions `and ... respectively`. Généraliser le rôle aux headings bornés
contenant `Guidance`, `Forecast` ou `Targets`. Une indication locale explicite
de prévision antérieure garde priorité sur le rôle global du tableau.

CRM/BBY/FDX deviennent développement. Confirmation gelée sur ABBV, ANF et CPB,
année 2024, mêmes limites : douze 8-K et deux annexes par dépôt. Gates inchangés.
Ces sociétés sont choisies avant lecture ; aucun rendement consulté.

## Résultat E21-B5 — confirmation V2

Collecte : 19 annexes, aucune erreur HTTP. Extraction : 23 candidats provenant
de neuf publications. Référence exhaustive des candidats : 15 prévisions
actuelles, sept anciennes prévisions et un intervalle de résultat historique.
Aucun faux intervalle parmi les candidats restants.

| Référence | NEW prédit | PRIOR prédit | Abstention | Support |
|---|---:|---:|---:|---:|
| NEW_FORECAST | 15 | 0 | 0 | 15 |
| PRIOR_FORECAST | 7 | 0 | 0 | 7 |
| REALIZED_RESULT | 0 | 0 | 1 | 1 |

La couverture NEW atteint 100 %, mais les sept anciennes prévisions sont
toutes classées NEW : rappel PRIOR 0 %. Précision classée : 15/22 = **68,2 %**.
Le gate de précision >=95 % échoue. Le résultat réalisé unique est laissé en
abstention ; son support est très insuffisant pour valider ce rôle.

Deux structures expliquent l'échec : AbbVie écrit `raises guidance from OLD to
NEW`, et Campbell place ancienne et nouvelle fourchette dans la même ligne de
tableau sans colonnes th exploitables. Le rôle général du heading ne doit pas
être appliqué aux deux bornes sans analyser leur relation.

Une limitation de collecte invalide aussi la couverture documentaire ANF :
six 8-K étaient éligibles, mais une seule annexe a été sélectionnée. Les cinq
autres communiqués portent des noms comme `q12024pressrelease.htm` sans token
EX99. L'inventaire de dépôts était complet, mais la sélection d'annexes ne
l'était pas. Cette distinction doit désormais apparaître dans le rapport.

Verdict : **FAIL**. La correction XBRL supprime bien l'intervalle corrompu et
les headings génériques récupèrent les nouvelles prévisions, mais V2 ne
distingue pas les anciennes dans ces structures. ABBV/ANF/CPB sont désormais
explorés et ne peuvent servir de nouvelle confirmation. Aucun rendement,
entraînement ou backtest consulté.

Artefacts :
`artifacts/research/guidance_structured/e21b5-confirmation-abbv-anf-cpb-2024-v1/`
avec queue, référence liée par hash et `validation_report.json`.

Avant une V3 : parser explicitement la relation `from OLD to NEW`, reconstruire
les colonnes ou cellules adjacentes ancienne/actuelle, élargir la sélection
research des annexes aux noms `pressrelease` avec garde-fous, puis utiliser
encore de nouveaux émetteurs. Ne pas entraîner sur les rôles V2.

## Résultat E21-B6 — confirmation V3

Collecte sans erreur : 15 annexes. Couverture des dépôts ayant au moins une
annexe candidate : BWA 5/8, CCK 4/5, BJ 6/6. L'absence de candidat peut être
légitime, mais le rappel documentaire n'est pas démontré pour BWA/CCK.
Extraction : 52 candidats issus de 15 annexes.

Référence exhaustive : 34 NEW, huit PRIOR, dix NOT_A_RANGE, aucun véritable
intervalle REALIZED_RESULT. V3 reconnaît 33/34 NEW et 7/8 PRIOR. En revanche,
sept NOT_A_RANGE sont classés REALIZED_RESULT ; trois restent ambigus.

| Référence | NEW | PRIOR | REALIZED | Abstention | Support |
|---|---:|---:|---:|---:|---:|
| NEW_FORECAST | 33 | 0 | 0 | 1 | 34 |
| PRIOR_FORECAST | 0 | 7 | 0 | 1 | 8 |
| NOT_A_RANGE | 0 | 0 | 7 | 3 | 10 |

Précision classée : 40/47 = **85,1 %**. Rappel NEW 97,1 %, PRIOR 87,5 %
mais support PRIOR inférieur à dix. Sept faux intervalles acceptés : gate zéro
échoué, ainsi que le gate de précision. Les faux résultats sont des paires
réelles distinctes : bénéfice fiscal du trimestre **et** du cumul, à deux
périodes, reliés par `and`. Ce ne sont pas des bornes basse/haute.

BJ révèle un autre NOT_A_RANGE correctement laissé ambigu : « membership fee
will increase by $5 to $60 » signifie augmentation de 5 dollars vers un prix
de 60 dollars, pas une fourchette. REALIZED_RESULT reste non validé car aucun
véritable intervalle de résultat réalisé n'est présent.

Verdict : **FAIL**. V3 résout le principal problème OLD→NEW, mais la grammaire
générique de résultats confond valeurs multi-périodes et intervalles. Aucun
ajustement post-résultat, rendement, entraînement ou backtest. BWA/CCK/BJ
deviennent explorés. Artefact :
`artifacts/research/guidance_structured/e21b6-confirmation-bwa-cck-bj-2024-v1/`.

Une V4 éventuelle doit abandonner la classe REALIZED_RESULT pour toute
construction `and`/`respectively`, exiger un marqueur lexical de vraie borne
(`range`, `between`, `low/high`) et associer chaque valeur à sa période. Cette
correction devra encore être confirmée sur un nouveau corpus. En attendant,
les rôles de guidance ne sont pas utilisables pour créer des labels ML.

## E21-B7 / V4 pré-enregistré

V4 est gelée avant lecture du nouveau corpus. Une construction `$X and $Y`
n'est candidate que si elle est introduite localement par `between`. Une
construction `increase/decrease/... by $X to $Y` est rejetée comme delta puis
cible. Enfin, `REALIZED_RESULT` exige une preuve lexicale explicite de
fourchette (`range`, `between`, `low/high` ou tiret) ; sinon le système
s'abstient. La syntaxe retenue est exposée dans chaque ligne pour audit.

BWA/CCK/BJ deviennent développement. La confirmation neuve porte sur
TransDigm (`TDG`), Parker-Hannifin (`PH`) et Korn Ferry (`KFY`), année 2024,
douze 8-K et deux annexes maximum par dépôt. Le choix précède toute lecture de
leurs documents. Les gates restent inchangés : zéro faux intervalle accepté,
précision classée >=95 %, couverture NEW_FORECAST >=80 %, support minimal de
dix candidats et trois publications pour valider isolément une classe.

Le test mesure séparément le rappel de détection des fourchettes : supprimer
les faux candidats ne doit pas être présenté comme une amélioration si de
véritables prévisions disparaissent. Aucun rendement, entraînement ou backtest
ne sera consulté avant le verdict.

## Résultat E21-B7 — confirmation V4

Collecte : 12 annexes et une erreur HTTP 503 sur un index TDG. PH et KFY ont
une couverture 4/4 ; TDG possède 13 dépôts éligibles, plafonnés à 12 selon le
protocole, dont quatre avec annexe candidate. L'extraction produit 73
fourchettes sur 12 publications.

Référence exhaustive des candidats détectés : 58 NEW et 15 PRIOR, aucun faux
intervalle et aucun résultat réalisé. V4 classe correctement les 51 décisions
qu'elle prend : 36 NEW et 15 PRIOR. Les 22 autres NEW restent ambiguës.

| Référence | NEW | PRIOR | Abstention | Support |
|---|---:|---:|---:|---:|
| NEW_FORECAST | 36 | 0 | 22 | 58 |
| PRIOR_FORECAST | 0 | 15 | 0 | 15 |

La précision classée atteint **100 %** et le rappel PRIOR **100 %** sur un
support enfin supérieur à dix. Cependant, la couverture NEW n'est que
36/58 = **62,1 %**, sous le gate de 80 %. Le verdict automatique reste
**FAIL**.

La revue complète des textes révèle en outre quatre vraies fourchettes de
revenus KFY absentes de la queue : « in the range of LOW and HIGH ». La règle
V4 rejetant tout 'and' sauf après 'between' a donc supprimé les sept faux
résultats CCK, mais également quatre vrais labels. Sur le périmètre
explicitement audité, le rappel de détection des vraies fourchettes est
73/77 = **94,8 %** et le rappel NEW bout en bout 36/62 = **58,1 %**.

Verdict scientifique : **FAIL/DATA_NOT_READY**. V4 améliore fortement la
précision et valide la reconnaissance PRIOR, mais son abstention NEW et sa
grammaire 'and' sont trop restrictives. Aucun rendement, entraînement ou
backtest n'a été consulté. TDG/PH/KFY deviennent corpus de développement.

Une V5 devra accepter 'and' après une locution complète 'in the range of',
étendre les verbes de prévision à 'anticipated/projected/forecasted', et
propager prudemment le rôle d'un heading de tableau ou d'une liste financière
aux lignes/cellules qui en dépendent. Une nouvelle confirmation devra utiliser
encore d'autres émetteurs.

## E21-B8 / V5 pré-enregistré

V5 est définie avant lecture du corpus suivant. Elle réaccepte 'and' comme
connecteur uniquement après 'between' ou la locution complète 'in the range
of'. Elle reconnaît les flexions 'anticipated', 'projected' et 'forecasted'.
Enfin, un heading de prévision peut gouverner plusieurs métriques séparées par
des points-virgules dans la même phrase, uniquement si la valeur possède déjà
une grammaire explicite de fourchette ; la portée ne traverse jamais un point.

TDG/PH/KFY deviennent développement. La nouvelle confirmation est gelée sur
Apogee Enterprises ('APOG'), Sysco ('SYY') et Estée Lauder ('EL'), année
2024, avec les mêmes limites de douze 8-K et deux annexes. Les gates B4 restent
inchangés. Le rappel de détection audité et le rappel NEW bout en bout restent
obligatoires dans le rapport. Aucun rendement ne sera consulté.

## Résultat E21-B8 — confirmation V5

La collecte télécharge neuf annexes sans erreur : SYY 4/4, EL 4/4, mais APOG
seulement 1/6 dépôts avec une annexe candidate. La couverture documentaire
APOG est donc insuffisante. Les neuf annexes donnent 44 candidats issus de
huit publications.

La référence exhaustive de la queue contient 41 NEW et trois NOT_A_RANGE.
Ces trois faux candidats SYY sont une hausse de cible de 100 à 120 et deux
collisions entre un montant en dollars et son taux de croissance négatif.
V5 les laisse tous en abstention. Parmi les vraies nouvelles prévisions, 17
sont classées NEW et 24 restent ambiguës.

| Référence | NEW | Abstention | Support |
|---|---:|---:|---:|
| NEW_FORECAST | 17 | 24 | 41 |
| NOT_A_RANGE | 0 | 3 | 3 |

La précision des 17 décisions est **100 %**, sans faux intervalle accepté,
mais la couverture NEW tombe à **41,5 %**, très sous le gate de 80 %. PRIOR
et REALIZED sont absents de ce corpus et ne sont pas revalidés.

Le rappel de détection global est déclaré **non mesurable**, et non 100 % :
au moins 22 paires monétaires EL utilisent la notation SEC sans zéro initial
('$.11', '$.22', etc.) et ne sont pas reconnues par le parseur actuel. Elles
comprennent des fourchettes réelles, des doublons prose/tableau et des paires
qui exigent une revue sémantique. La faible couverture APOG empêche également
toute revendication de rappel documentaire.

Verdict : **FAIL/DATA_NOT_READY**. V5 confirme le comportement fail-closed et
ne réintroduit pas les faux résultats de V3, mais elle ne généralise pas la
couverture NEW. Aucun rendement, entraînement, backtest ou batch quotidien
n'a été modifié. APOG/SYY/EL deviennent corpus de développement.

La piste est arrêtée ici : les améliorations possibles — montants sans zéro
initial, deuxième borne suivie d'un pourcentage, sélection des annexes APOG et
provenance des tableaux 'Forecasted ... (F)' — sont consignées mais ne
constituent plus un plan d'exécution. Aucun B9 ne sera entrepris avec la chaîne
gratuite actuelle.

Conditions de réouverture : source structurée de guidance historique PIT ou
collecteur SEC démontré exhaustif ; nouveau corpus non exploré ; annotation
humaine indépendante ; zéro faux intervalle ; précision >=95 % ; couverture
NEW >=80 % ; rappel de détection effectivement mesuré. Après seulement ces
gates, une expérience directionnelle OOF pourrait être pré-enregistrée.
