# GPT : TOP20 Oracle d'août 2026, deux excursions et leur ordre

## Objectif et périmètre figés avant les appels et les résultats

Autorisation utilisateur : août2026, budget maximal **4 USD**. Le mois compte
**21 séances US**, et non20 : conserver les21, soit **420 couples titre/date**,
sur37 symboles distincts. Aucune sélection par le rendement futur.

Source : `us_news_gpt_top20_history/20261015-v1/months/2026-08`, archives vérifiées
par empreintes. Oracle parcours H20 annuel `model-factory-20261014113232-bc35a7`,
CatBoost, fold2025-12-10, modèle disponible2025-12-09. Vérification du rang1..20,
du profil, des poids déclarés, de l'absence de labels futurs et des21 dates.
Pas de nouvel entraînement, d'inférence Oracle, de changement du modèle live.

Ce n'est pas une reproduction du batch live complet : les reçus prospectifs
consensus EODHD commencent le11 octobre2026. Ils sont **exclus** du contexte
d'août, comme les autres familles sans disponibilité historique reconstituable.
L'identité de société est actuelle ; le biais d'univers statique demeure.

## GPT et preuves fournies

GPT `gpt-6-luna`, protocole tendance/preuves v9, échelle1..10 ou null si aucune
base utilisable. Même grille de tendance que le filtre actuel, avec une
instruction additionnelle signalant la reconstruction historique et l'interdiction
de prétendre disposer de preuves PIT ou d'autoriser un ordre. Mode local,
aucune recherche Web. Effort de raisonnement `low`, sortie plafonnée12000 tokens,
délai300 secondes, au plus3 requêtes simultanées par défaut.

Pour chaque J, uniquement :

- TOP20, rang/score Oracle d'amplitude, identité courante et horizon20 séances ;
- jusqu'à8 articles récents, dédoublonnés par contenu, publiés avec horodatage
  fournisseur qualifié avant la clôture J, sur7 jours calendaires ;
- historique prix/volume d'au plus21 séances arrêté à J, lignes entières choisies
  EODHD prioritaire puis Alpaca SIP, sans remplissage des trous.

Les résumés/textes ont des bornes fixes, les omissions/troncatures sont signalées.
Pas de données de compte, positions, secrets ou rendements futurs. Toutes les
sources sont contexte rétrospectif, non preuves d'exécution certifiées. Les
horodatages réels de réception/analyse ne sont jamais antidatés à août.

GPT doit donner une tendance provisoire même si les preuves d'exécution manquent,
lorsqu'il existe une base informative utilisable ; il ne doit ni transformer
l'absence de données en5, ni fabriquer une direction. Le score n'est pas une
probabilité calibrée de gain. Identité, schéma et citations exactes sont contrôlés.
Une réponse invalide reste invalide, n'est pas convertie en neutre et n'est pas
repayée automatiquement.

## Archives et budget

Script séparé : `scripts/research/us_gpt_august_2026_path_audit.py`.
Dossier : `artifacts/research/us_gpt_august_2026_path_audit/20261025-v2`.
Le dossier v1 est une préparation interrompue avant tout appel payant ; il est
conservé, pas réutilisé. Une source ressemblant à un secret a motivé une exclusion
explicite avant envoi, sans affaiblir le contrôle des contenus sortants.

Les demandes exactes sont figées dans `requests.json` avant les appels.
Chaque requête est identifiée par son SHA-256 intégral : modèle, prompt, schéma,
date, données et paramètres doivent correspondre pour réutiliser une réponse.
Les anciens lots BULLISH/BEARISH ne sont pas convertis artificiellement en scores.
Un même article intégré à deux contextes de date/prix différents n'est pas la
même question : on ne réutilise pas une conclusion de lot comme verdict isolé.

Écritures SQL exclusivement dans `llm_news_analysis_research_runs` : réclamations
durables avant appel, requêtes/réponses brutes et qualifications après appel,
puis bilan. Références `gpt-aug2026-path-v1:claim:<hash>` et
`gpt-aug2026-path-v1:response:<hash>`. Horodatages actuels, données de recherche,
aucune publication dans `llm_directional_runs`, risque ou ordres.
Copies locales `api/<hash>/request.json` et `response.json` avant parsing/SQL.
Une tentative ambiguë sans réponse durable bloque la reprise payante implicite.

`budget.json` réserve sous verrou le coût maximal de chaque appel avant envoi,
sortie comprise, au tarif cache-write conservateur. Réservation inconnue conservée,
jamais remise à zéro. Plafond cumulatif **4 USD estimés hors taxes/conversion**,
indépendant des autres appels du compte. Tarifs vérifiés le25 octobre : entrée0,10,
écriture de cache0,125, sortie0,50 USD/M tokens ; remise de cache ignorée par
prudence. [Documentation officielle OpenAI](https://developers.openai.com/api/docs/models/gpt-6-luna).

## Mesure après gel des réponses

Prix de référence commun : ouverture régulière de **J+1**. Fenêtre de20 séances,
entrée incluse, dernier jour observé jusqu'à sa clôture. Pas de TP/SL, sortie
simulée, frais ou calcul de portefeuille : c'est un diagnostic de direction.

Conserver indépendamment :

- hausse maximale et prix du sommet, en pourcentage du prix d'entrée ;
- baisse minimale et prix du creux, sur la même base ;
- première bougie5min atteignant chacun des deux extrêmes globaux et séance1..20 ;
- sommet avant creux, creux avant sommet, ou même bougie : ordre indéterminé ;
- rendement de clôture H20 comme comparaison, sans le confondre avec les excursions.

Exemple : +18% et−15% ⇒ amplitude dominante LONG, même si clôture H20 négative.
Si le cours ne passe jamais au-dessus/au-dessous de l'entrée, l'excursion de ce
côté vaut0. L'ordre des extrêmes n'est pas l'ordre de franchissement d'un TP/SL,
ni la preuve qu'un short/long aurait survécu jusqu'à l'extrême favorable.

Source résultats : Alpaca SIP brut5min, séance régulière uniquement. Grille
complète exigée sur les20 séances, OHLC cohérents, volume positif, pas de barres
remplies. Splits et ruptures d'identité connus excluent la qualification brute.
Les parcours incomplets sont conservés comme **observés non qualifiés**, jamais
assimilés à leurs vrais extrêmes complets. Aucune exclusion de prix futurs ne
modifie les420 candidatures ni les scores déjà figés.

Lire `results.csv`/`results.parquet` par date/rang : score, deux excursions,
horodatages, ordre et statut de qualité. Bilan par score exact, orientation1..4
SHORT /5..6 mixte /7..10 LONG ; comparer à toujours-LONG et toujours-SHORT sur
**les mêmes lignes évaluables**. Seuils live inchangés : >8 LONG, <3 SHORT.
Inclure un contrôle sans chevauchement par symbole et les effectifs de chaque
groupe : les420 lignes ne sont pas420 observations indépendantes.

## Limites et état

Reconstruction non PIT : les news et prix peuvent être des versions révisées,
leur publication ne prouve pas une réception locale à J. La mémoire rétrospective
du LLM ne peut pas être exclue par le prompt. Un mois,37 sociétés et des horizons
chevauchants ne démontrent ni une précision future ni un rendement exploitable.

27 tests synthétiques passent avant le lancement : excursions distinctes du
rendement H20, ordre indéterminé dans la même bougie, trous, splits, doublons,
sources non traçables, score invalide, données de compte/futures refusées,
coût/plafond, cache exact et absence de retry payé d'une tentative ambiguë.

Préparation terminée :420 requêtes,366 avec news, aucune sans prix J ; consensus
et autres familles non reconstituables exclus. Trois sources contenant un motif
ressemblant à une clé ont été exclues, sans en exposer le contenu.

Le premier lancement payant a été bloqué avant exécution par le contrôle de
sécurité : autorisation explicite du contenu détaillé transmis à OpenAI
(rangs/scores Oracle, données de marché locales dérivées) demandée. Aucun
contournement ni appel/réclamation SQL de cette première tentative.

L'utilisateur répond ensuite **« oui, go »** à cette demande précise.
Nouvelle tentative acceptée, superviseur local caché démarré le25 octobre,
PID87848. Trois requêtes simultanées au maximum, plafond4 USD inchangé.
Le superviseur lance la mesure des deux excursions uniquement après
`analysis.json: SCORES_COMPLETED` ; aucun risque/ordre appelé. Pas de seconde
campagne en parallèle, ni remise à zéro des réclamations/coûts pour une reprise.

Consulter `progress.json`, puis `analysis.json` et `report.json` après reprise.
Ce document ne prétend pas que les420 appels sont déjà terminés.

## Appels terminés et reprise de la mesure

Les420 réponses sont archivées :315 valides,105 invalides, coût estimé
**0,570567575 USD**, plafond4 USD respecté. Parmi les invalides,104 ne passent
pas le contrôle de citation exacte et une réponse est incomplète. Elles ne sont
pas changées en scores neutres, ni rappelées automatiquement. Leurs réponses
brutes demeurent disponibles pour un audit technique distinct.

La première mesure de parcours a planté sur AGX : le maximum/minimum conservé
en SQL/parquet comme `Decimal` était converti en flottant puis recherché par
égalité dans la colonne `Decimal`. Aucun prix non exactement représentable en
binaire ne correspondait, d'où un timestamp `NaT` et `KeyError`.

Reprise d'évaluation seule via
`scripts/research/us_gpt_august_2026_path_recovery.py` : normalisation OHLC/volume
sur le même type flottant déjà utilisé par les contrôles numériques, puis
réducteur, fenêtre, qualité et statistiques inchangés.29 tests passent,
dont des prix décimaux à8 décimales, leurs dates exactes, les trous et les
deux extrêmes dans une même bougie. Aucun nouvel appel GPT.

Le script original et son manifeste restent scellés, non modifiés. L'amendement
`evaluation-recovery-v1.json` conserve les empreintes des demandes, scores,
réponses résumées et nouveau code ; l'ancien progrès figé est sauvegardé.
Le snapshot AGX déjà lu est réutilisé. Les105 avis invalides et les parcours
incomplets restent explicitement distincts des observations évaluables.

## Bilan final — 25 octobre2026

Statut `COMPLETED_RETROSPECTIVE_NOT_PIT`, sans appel supplémentaire après les420
analyses initiales.242 parcours complets sur420 ;178 grilles5min incomplètes
conservées comme observations non qualifiées. Parmi les242,164 ont un avis GPT
valide. Les315 réponses valides du mois se répartissent : score3=30,4=142,
5=21,6=85,7=34, et3 tendances indéterminables à score null. Aucune réponse
valide à1,2,8,9 ou10 : aucune ne passe les seuils live >8 / <3.

Sur107 avis orientés avec parcours complets, hors égalité des amplitudes :
**42,99%** du côté dominant correct, contre43,93% toujours-LONG et56,07%
toujours-SHORT sur les mêmes107 lignes. Contrôle sans chevauchement par titre :
20 observations,45% correctes. Ce contrôle est petit et ne démontre pas une
précision prospective.

| Score | Lignes valides/parcours complets | Hausse max moyenne | Baisse max moyenne | Sommet avant creux | Côté estimé dominant |
|---|---:|---:|---:|---:|---:|
|3|4|+12,83%|−13,89%|75,00%|50,00%|
|4|72|+15,61%|−13,68%|54,17%|48,61% (une égalité incluse)|
|5|12|+17,64%|−13,38%|58,33%|Pas de côté demandé|
|6|44|+15,23%|−14,42%|56,82%|Pas de côté demandé|
|7|32|+9,66%|−18,83%|81,25%|28,13%|

Pour le score7,9 amplitudes dominantes LONG et23 SHORT. Le sommet précède
souvent le creux : cela n'implique ni un TP atteint, ni une entrée/sortie
exécutable, ni une rentabilité. Ne pas renverser les avis après observation
et présenter ce renversement comme une règle prédictive validée.

Contrôle indépendant du correctif sur les242 parcours complets : recherche
des maxima/minima et de leur premier timestamp directement dans les colonnes
`Decimal` originales des snapshots.242/242 concordent avec les prix et les
horodatages du rapport corrigé ; aucune modification de bougie ou de réponse.

Conclusion : **pas d'amélioration directionnelle démontrée dans ce test**.
Le rapport porte sur un sous-ensemble qualifié, pas sur une validation complète
du pipeline live. Les105 réponses invalides,178 fenêtres incomplètes,
chevauchements et réserves historiques restent visibles. Les résultats complets
sont dans `results.csv`, `results.parquet` et `report.json` du dossier v2.
