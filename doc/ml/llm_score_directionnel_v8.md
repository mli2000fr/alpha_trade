# Étape 10 — score d'orientation LLM de 1 à 10

Livraison du 24 octobre 2026. GPT et DeepSeek, en mode local ou Web, utilisent
le protocole `oracle-fresh-evidence-direction-score-v8` pour les **nouvelles**
analyses configurées ainsi :

```yaml
llm_directional_filter:
  oracle_top_n: 20        # 1–100 : premiers scores Oracle soumis au LLM.
  max_selected: 5        # Plafond après filtrage, distinct du nombre analysé.
  allow_long: true       # Autorisation de retenir les LONG qualifiés.
  allow_short: true      # Autorisation de retenir les SHORT qualifiés.
  scoring_mode: direction_1_10
  long_score_threshold: 8
  short_score_threshold: 3
```

Le modèle renvoie `direction_score`, entier obligatoire entre 1 et 10. Un
score proche de 1 signifie une orientation baissière plus forte, proche de 10
une orientation haussière plus forte. 5–6 représente une appréciation mixte
ou indéterminée. Ce n'est ni une probabilité, ni un rendement attendu, ni la
probabilité d'atteindre un TP avant un SL. Le modèle évalue la tendance pendant
les prochaines séances de l'horizon fourni, pas seulement la clôture finale.

Les deux booléens sont indépendants : LONG seul (`true/false`), SHORT seul
(`false/true`), les deux (`true/true`) ou aucune sélection (`false/false`).
Ils ne forcent pas le LLM à changer son opinion : score, direction et réponse
brute restent archivés. Un sens désactivé reçoit le motif `long_not_allowed`
ou `short_not_allowed` ; le titre n'est pas publié vers le risque. Les seuils,
preuves qualifiées et contrôles de risque restent obligatoires pour un sens
autorisé. Les deux à `false` n'arrêtent pas les appels d'analyse : désactiver
le filtre/son lancement pour éviter leur coût. Le prompt reste inchangé.

La configuration est figée dans chaque run et relue aux étapes 11/12 : modifier
ces booléens agit sur la **prochaine analyse de l'étape 10**, pas sur une
ancienne sélection. Les archives sans `allow_long` conservent LONG autorisé ;
sans `allow_short`, elles conservent SHORT interdit. Aucun ordre ni aucune
évaluation historique n'est réécrit.

`oracle_top_n` était déjà raccordé au moteur d'analyse. Son défaut YAML et
composant est désormais **20**. Le tableau 10 n'est plus tronqué à dix lignes :
il respecte le N du run archivé. Le tableau 11 reste limité à la sélection
publiée, pas aux vingt candidats. Une ancienne analyse garde son N (dix si
ce champ manquait dans une ancienne archive). Aucun candidat n'est inventé
pour compléter un univers plus petit, ni une ancienne analyse élargie après
coup. Le coût potentiel d'un passage augmente avec le nombre de titres : le
paramètre borne les appels d'analyse ; aucun nouvel appel n'est lancé ici.

L'application, pas le LLM, dérive le sens avec des comparaisons **strictes** :

| Score avec les défauts actuels | Décision |
| --- | --- |
| 1 ou 2 (`score < 3`) | SHORT |
| 3 à 8 inclus | NEUTRE / ABSTENTION |
| 9 ou 10 (`score > 8`) | LONG |

Les seuils YAML sont des entiers validés tels que
`1 <= short_score_threshold < long_score_threshold <= 10`. Changer le YAML
agit sur la prochaine analyse, pas sur un run déjà archivé. Le fournisseur,
le modèle LLM, l'horizon, les protections et le plafond de sélection existants
ne sont pas changés par cette évolution.

## Sélection, preuves et risque

Un score extrême ne suffit pas. Identité, sources traçables, fraîcheur,
citations exactes, contexte figé et autorisation SHORT restent obligatoires.
Les données non qualifiées ne deviennent pas des preuves admissibles. Un
score 10 sans preuve qualifiée est exclu ; un score 1 avec SHORT désactivé est
exclu. Les contrôles emprunt, risque et PAPER des étapes 11/12 restent intacts.

Le plafond `max_selected` reste un maximum, pas un quota. Les candidats
admissibles sont classés symétriquement par force de direction : 1/10 d'abord,
puis 2/9 ; égalité départagée par rang Oracle puis symbole. Les tableaux
restent, eux, dans l'ordre Oracle initial. La confiance subjective 0–1 reste
un champ d'audit distinct, sans conversion artificielle du score ; le seuil
`min_confidence` n'est plus un filtre d'admission v8. Il conserve son sens pour
les archives et le mode `legacy_confidence`. Aucun nouveau score n'est présenté
comme une probabilité calibrée ; le sizing existant n'est pas remplacé.

## Stockage et compatibilité

Aucune migration ni réécriture SQL nécessaire :

- `llm_directional_runs.config_json` : mode et seuils du run ;
- `input_json.candidates[].direction_score_policy` : échelle et seuils figés,
  inclus dans le snapshot haché et transmis au LLM ;
- `llm_directional_assessments.response_json` : réponse brute contenant le score ;
- `assessment_json` : score, décision dérivée, politique et motifs de rejet ;
- `selected_json` du run et `selected` des assessments : sélection publiée.

La requête exacte, les réponses brutes et leurs empreintes restent conservées.
Les étapes 11/12 revalident le run exact avec **sa configuration archivée**,
jamais les seuils courants. Les protocoles v4–v7 restent inchangés, leurs notes
de confiance ne sont pas converties en faux scores /10. Un ancien run encore
lié ne sera donc pas transformé par un simple rafraîchissement de l'IHM.

## Écrans et notifications

Les tableaux 10 et 11 affichent **Score GPT (/10)** ou **Score DeepSeek (/10)**
et la direction dérivée. Le tableau 10 affiche tous les candidats Oracle et
les motifs de non-sélection, notamment les bornes incluses dans la zone neutre.
Le tableau 11 garde uniquement la sélection de l'étape 10, avec ses décisions
risque. Les anciennes analyses affichent « Confiance historique … (%) ».
Telegram et le rapport d'audit reprennent le nouveau score et les seuils.

Il faut lancer une **nouvelle étape 10** pour obtenir de nouveaux scores ;
aucun appel payant, ordre ni réentraînement n'a été lancé pour cette livraison.

## Vérification

Tests hors ligne : bornes exactes 2/3/8/9, seuils personnalisés, rejet des scores
invalides/non entiers, neutralité, permissions SHORT, preuves insuffisantes,
URL non traçables, sélection symétrique/plafond, stockage SQL de test,
revalidation exacte après modification des réglages courants, affichage des
deux tableaux et transports GPT/DeepSeek simulés (local et Web natif).
Les anciens tests v4–v7 conservent leurs contrats.
Validation finale : **453 tests ciblés passent**, sans API payante ni ordre.

Suivi TOP configurable (24 octobre 2026) : **457 tests ciblés passent**, dont
l'analyse des vingt candidats avec plafond de cinq sélections, l'affichage
des vingt lignes et la compatibilité des anciennes archives. Aucun appel
fournisseur ni ordre n'a été lancé pour cette validation.
La configuration courante a été chargée et ses six bornes 1/2/3/8/9/10
vérifiées. Les sources scellées des trois runs grille/mensuel restent valides.

Le format GPT est imposé par un JSON Schema strict ; DeepSeek JSON est validé
localement par le même contrat. [Documentation officielle Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Ces tests valident le raccordement technique, pas l'efficacité directionnelle
ou économique du nouveau score.
