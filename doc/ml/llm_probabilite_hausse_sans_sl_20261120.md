# GPT/DeepSeek : probabilité de hausse sans toucher le SL et choix humain

Le filtre du parcours Q051/B utilise désormais le protocole versionné
`oracle-long-no-stop-probability-v10`. Les anciennes analyses de tendance
v4–v9 et leurs prompts restent inchangés et revalidables.

## Événement demandé

Pour chaque titre LONG retenu après Oracle et per-symbol, le LLM estime la
probabilité conjointe suivante : le prix de sortie à l'ouverture de la séance
H+1 est strictement supérieur au prix d'entrée réel **et** le stop n'a jamais
été touché pendant la détention. Un simple pic positif ne suffit pas. Un titre
ayant touché le SL puis remonté est un échec pour cet événement.

L'horizon et le SL proviennent du profil Winner figé : actuellement H10,
SL5 %, sortie open11, sans TP ni trailing. L'entrée est un achat marché régulier
en J+1 ; son prix réel est inconnu lors de l'analyse. La dernière clôture est
une référence indicative, pas un remplissage garanti. La condition de hausse
porte sur le prix brut ; ce n'est pas une probabilité de profit net après frais.
Le pourcentage retourné est une estimation subjective non calibrée, sans
transformation d'un ancien score 1–10 en probabilité.

## Données locales et recherche Web

Le dossier contient uniquement les éléments pertinents disponibles au cutoff :
identité, rang/score Oracle, scores et AUC per-symbol, prix/volumes récents,
news, consensus, calendrier des résultats, extraits SEC et fondamentaux.
Les états de fraîcheur et les familles absentes sont explicités. Ni labels,
ni rendements futurs du panneau de recherche ne sont envoyés.

La recherche Web est obligatoire : `llm_directional_filter.analysis_mode:
web_search`. GPT utilise son outil Web ; DeepSeek utilise ses Search/Fetch
natifs, sans relais GPT. Les mêmes instructions et le même schéma définissent
l'événement pour les deux fournisseurs. Les budgets d'appels existants restent
appliqués et aucun retry payant implicite n'est ajouté.

Le prompt exige une recherche des informations utiles manquantes localement,
dont le consensus EPS/revenus et ses révisions, les annonces, la guidance et les
risques pertinents. Il demande de comparer résultats/guidance aux attentes du
marché, de vérifier identité, période, devise et unités, et de rechercher des
faits contraires. Une donnée introuvable reste indisponible ; le modèle ne doit
pas l'inventer. Il peut retourner une probabilité `null` et UNDETERMINABLE.
L'absence de consensus seule n'impose pas l'abstention si d'autres preuves
suffisantes permettent une estimation.

Fichiers des nouveaux prompts :

- `config/ia/prompt/cloud/oracle_directional/v10/web_search.txt` ;
- `config/ia/prompt/cloud/oracle_directional/output/v10.txt`.

Une citation Web doit appartenir aux résultats réellement reçus. Les dates,
fraîcheur et citations locales restent contrôlées ; les dates Web sont des
dates déclarées par les sources, pas une certification historique universelle.

## Validation dans la page Pipeline

Le tableau de l'étape10 affiche les candidats par probabilité décroissante,
avec une case **Retenir** par ligne, les explications et les limites des preuves.
Les cases sont initialement décochées. Une estimation absente ou des preuves
non qualifiées ne peuvent pas être sélectionnées côté serveur, même si la
case a été cochée. Aucun titre hors de la liste per-symbol n'est ajouté.

Le bouton **Valider la sélection** publie un choix immuable lié à la proposition
exacte et aux preuves LLM. La liste est classée par probabilité ; elle sert
d'ordre de priorité au risque. Une validation vide exclut tous les achats de
ce run. Le bouton ne soumet pas lui-même un ordre : un workflow déjà en attente
reprend ensuite 11/12, avec les contrôles et protections Winner existants.

Quand GPT est activé dans un batch, le workflow attend ce choix avant l'étape11.
Il n'y a aucune approbation automatique, y compris pour les autres comptes.
La même liste validée est partagée entre comptes PAPER ; chacun dimensionne
avec son propre capital. Les protections des positions déjà ouvertes continuent
à fonctionner pendant cette attente. Le workflow peut être arrêté et l'analyse
expire selon sa durée de validité archivée, sans achat tardif implicite.
L'heure d'expiration est affichée. Après expiration, un nouveau lancement
batch/pipeline doit refaire l'étape10 et obtenir de nouvelles réponses ;
relancer seulement 11/12 ne renouvelle jamais l'analyse. La sélection datée
reste consultable dans Pipeline, y compris si l'attente dépasse minuit.

## Traçabilité et compatibilité

Les requêtes, réponses et contrôles sont archivés dans les tables existantes
`llm_directional_runs` et `llm_directional_assessments`. Le schéma de réponse
et le contrat SL/H sont enregistrés avec la requête ; pas de nouvelle colonne
SQL nécessaire. Le champ de compatibilité `decision` dérivé après parsing
signifie « événement LONG estimable », pas une opinion LONG/SHORT du LLM.

La proposition reste scellée dans son répertoire Q051 (`selection.json`,
`selection.parquet`, `seal.json`). La validation est publiée atomiquement dans
`human_selection.json` et ne remplace pas ces fichiers. Son empreinte est liée
au bilan de risque ; l'exécution refuse un choix différent de celui dimensionné.
Les données anciennes ne sont pas réécrites et les anciens runs ne deviennent
pas rétroactivement des analyses de probabilité.

La bascule reste `config.yaml → us_pipeline.gpt_filter_enabled`. L'ouverture
du tableau et la validation de cases ne déclenchent aucun nouvel appel LLM.
Les appels payants ont lieu uniquement lors d'un lancement explicite du filtre.

## Vérification du raccordement

Le contrôle final compte **835 tests réussis** : schémas et sources des deux
fournisseurs, archivage/relecture SQL, cases et validation dans Streamlit,
refus des analyses expirées, attente/reprise du workflow, absence de lancement
du risque avant choix humain, liaison choix/risque/exécution et partage entre
comptes. Reçu : `artifacts/operations/llm_probability_20261120/tests-final.xml`.
Aucun appel fournisseur payant, notification réelle ou ordre broker n'a été
émis par ces tests. Ils ne mesurent pas la fiabilité des probabilités du LLM.

Limite de l'environnement de test : deux tests historiques d'arrêt de processus
de la suite complète du registre ne peuvent pas arrêter leur propre enfant via
`taskkill` dans l'environnement restreint (refus d'identification Windows).
Le diagnostic sur un enfant de test reproduit ce refus ; la terminaison directe
de cet enfant fonctionne. Le code de terminaison n'a pas été modifié pour cette
évolution. Les tests pertinents du registre, dont blocage/reprise avant risque
et préparation du watcher, passent dans le contrôle ciblé final.
