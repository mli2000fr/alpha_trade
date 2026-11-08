# GPT : réponses invalides exclues des achats — 2025

## Décision autorisée

Le 8 novembre, l'utilisateur demande d'exclure les onze réponses GPT invalides
des achats, puis de comparer le portefeuille 2025 à Winner seul. La cohorte et
les reçus payants du test précédent restent inchangés. Une réponse invalide
reste invalide : elle entraîne un refus d'entrée explicite dans cette variante.
Pas de remplacement depuis les rangs suivants, pas de réinterprétation de citation.

Source : `artifacts/research/us_gpt_winner_ab/20261107-v1`.
Sortie distincte : `artifacts/research/us_gpt_winner_invalid_excluded/20261108-v2`.
Programme : `scripts/research/us_gpt_winner_invalid_excluded.py`.

## Deux bras comparables

- A : Winner seul, référence `20261107_095041_0b38b8de`.
- B : même sélection, sauf 34 vetoes GPT validés et onze réponses invalides
  exclus. 159 candidatures restent sur204 ; les38 dossiers sans news sont conservés.

Bundle Oracle H10 `model-factory-20261106203103-91b063`, univers1 790,
TOP10 % Oracle → TOP10 LONG per-symbol, score strictement >0,70 et AUC calibration
≥0,60. 2025, capital initial4 000 USD, compte margin capacité2×, risque1,25 %,
poids20 %, montant minimum50 USD, position complète, entrée journalière J+1 sans
confirmation, SL5 %, sans TP ni trailing, dix séances puis open11. Contrôleur
DD/B4 et facteurs désactivés, frais8 points de base par opération, financement
6,5 % annuel. Il s'agit de la référence de l'expérience LLM, pas du profil Q088.

Même moteur natif, mêmes prix daily/5m, secteurs, actions et ordre de sélection
figés que la grille. A doit reproduire exactement le résultat initial
(+6,898841663 % et DD−10,856029369 %) avant publication de B. Capital, liquidités,
frais et positions sont intégralement rejoués ; les signaux exclus ne sont pas
assimilés à des trades qui auraient tous été exécutés.

## Traçabilité et limites

Cache SQLite source ouvert en lecture seule, décisions valides revalidées,
identité de chaque candidature et absence de réponses manquantes contrôlées.
Les onze invalides et34 vetoes doivent correspondre à la cohorte autorisée.
Décisions, raisons, empreintes des entrées et programme enregistrés dans le
nouveau dossier. Aucun appel API, téléchargement, écriture SQL partagée ou ordre.
LM Studio reste arrêté conformément à la demande utilisateur.

La décision de rejet des invalides est prise après l'observation des erreurs
techniques. Elle mélange effet économique des vetoes et indisponibilité de
preuves exploitables. Elle ne mesure donc pas isolément la justesse des34 avis
baissiers. Étude rétrospective exploratoire : versions de news actuellement
archivées, mémoire potentielle2025 du LLM et secteurs actuels ; aucune
certification PIT/OOS ou parité complète avec les exécutions réelles.

## Suivi et restitution

`progress.json` indique le bras et la dernière séance. `comparison.csv` contiendra
rendement, DD, gagnants/perdants, gains/pertes moyens, durées de détention,
capital engagé moyen/maximal et frais/financement. Chaque bras conserve ses
trades, événements et courbe quotidienne. Deux tests de politique passent.

Première tentative v1 arrêtée avant simulation : le journal de progression du
run était en dehors du sous-dossier autorisé pour le bras A. L'isolation est
corrigée pour autoriser uniquement le dossier complet du nouveau run v2 et ses
sous-dossiers ; les fichiers partagés restent protégés. v1 conservé pour audit.

## Résultat terminé

Les deux bras ont terminé leurs250 séances. Les18 indicateurs du témoin ont été
reproduits avec tolérance numérique stricte, y compris frais, financement,
gagnants/perdants et capital engagé. Aucun nouvel appel GPT ou Qwen.

| Indicateur | Winner seul | Winner + exclusions GPT et invalides |
| --- | ---: | ---: |
| Capital final valorisé | 4 275,95 $ | 3 971,82 $ |
| Rendement | +6,90 % | −0,70 % |
| DD maximal | −10,86 % | −12,98 % |
| Trades clôturés | 59 | 53 |
| Gagnants / perdants | 27 / 32 | 21 / 32 |
| Taux gagnant | 45,76 % | 39,62 % |
| Gain moyen gagnant | 57,16 $ | 55,98 $ |
| Perte moyenne perdant | −39,60 $ | −37,61 $ |
| Durée moyenne gagnant, jours calendaires | 15,07 | 15,28 |
| Durée moyenne perdant, jours calendaires | 6,10 | 5,86 |
| Capital engagé moyen | 1 334,04 $ | 1 081,80 $ |
| Capital engagé maximal | 4 713,95 $ | 4 660,49 $ |
| Frais simulés | 73,70 $ | 63,26 $ |
| Financement | 0,36 $ | 0,17 $ |

Écart final : **−304,14 $**, soit−7,60 points de rendement, avec un DD aggravé
de2,12 points. Le filtre ne présente aucun bénéfice sur ce replay. Le nombre
de perdants clôturés reste32 dans chaque bras, mais le portefeuille est rejoué :
cela ne prouve pas que ce soient exactement les mêmes trades. Il ne faut pas
assimiler les45 candidatures exclues à45 trades exécutés dans le témoin.

Le rapport global est `COMPLETED_EXPLORATORY` ; les rapports natifs gardent
`INCOMPLETE_COVERAGE` car les protections utilisent le repli daily lorsque les
bougies5m sont incomplètes. Ce repli est identique dans les deux bras et ne
constitue pas une parité d'exécution réelle. Aucune activation en production.

## Diagnostic du recul : rôle du prompt et des nouvelles entrées

Le prompt demande de signaler des faits défavorables explicites, **pas de prévoir
un rendement précis**. Le refus mécanique exige UNFAVORABLE, SUFFICIENT,
au moins une citation négative exacte concernant l'émetteur et une association
ticker primaire. FAVORABLE, INDETERMINABLE, preuves insuffisantes et absence de
news conservent la candidature initiale. Les onze invalides sont refusés par
la nouvelle règle de simulation, et non par un avis baissier du modèle.

Le dossier contient au maximum six extraits de news des sept jours précédant
la clôture J, chacun plafonné à3 000 caractères de corps, et un résumé prix/volume
du titre et de SPY sur60 séances. Pas de consensus/options historiques qualifiés,
SEC qualifiée ni versions historiques du sentiment. Le modèle ne reçoit ni
le SL5 % ni un objectif de probabilité de rentabilité nette de la stratégie ;
le prompt indique seulement une détention de dix séances. Les news de la nuit
entre cette clôture J et l'entrée J+1 sont hors cutoff de ce protocole.

Sur les trades réellement exécutés dans le témoin, les34 vetoes valides visent
six entrées : trois gagnantes et trois perdantes, PnL cumulé−1,69 $. Les onze
invalides visent cinq entrées : trois gagnantes et deux perdantes, PnL cumulé
+34,18 $. Ces nombres n'isolent pas l'effet de chaque règle dans un nouveau
portefeuille ; ils montrent surtout l'absence de séparation nette gagnants/perdants.

Après replay,47 trades sont communs,12 anciens trades sont absents et six
nouveaux trades apparaissent. Les12 anciens trades totalisaient+147,80 $ ;
les six nouveaux font−153,49 $. Le sizing des trades communs change dans26 cas,
avec un effet PnL cumulé−3,04 $. Le différentiel de financement explique le
petit solde restant dans l'écart de capital final−304,14 $.

Exemple BOOT : le signal10/03 est invalide et l'achat11/03 est refusé ; il aurait
donné+59,08 $ (+8,25 %) dans le témoin. Le11/03, GPT renvoie INDETERMINABLE avec
preuves insuffisantes, donc la candidature redevient autorisée. Achat12/03,
sortie au stop13/03 :−37,75 $. Il n'existe pas de suspension durable par événement
ou d'interdiction de réentrée automatiquement attachée à un veto.

Autre faiblesse : FLR16/10 reçoit un veto alors que GPT reconnaît dans ses
contre-arguments que les articles d'octobre répètent la dégradation des résultats
et de la guidance annoncée le1er août. Le validateur contrôle les citations et
l'attribution, mais n'impose pas de nouveauté effective de l'événement cité.
L'entrée témoin du17/10 finit à+19,56 $ (+2,56 %).

Conclusion descriptive : faits défavorables et signal de baisse future ne sont
pas interchangeables. La fraîcheur de l'événement, la réaction déjà réalisée
du prix et la persistance d'une décision sont des dimensions mal formalisées
dans ce pilote. Leur ajout est une hypothèse de recherche, pas une amélioration
de rendement démontrée. Aucun appel LLM ni nouveau backtest dans ce diagnostic.
Fichiers du diagnostic dans `diagnostic/` du dossier v2.
