# GPT/DeepSeek : probabilité de hausse sans toucher le SL et choix humain

Les nouveaux appels du parcours Q051/B utilisent le protocole versionné
`oracle-long-probabilities-v12`, avec trois estimations, analyses en français
et horizon de court terme explicite. Les anciennes analyses v4–v11 et leurs
prompts restent inchangés et revalidables. Ajouter ce prompt ne relance aucun
appel payant sans lancement explicite.

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

Les commentaires, arguments, risques, catalyseurs, analyses du consensus et
du contexte sont demandés **en français**. Les clés JSON et codes techniques
restent ceux du schéma ; citations exactes, titres originaux et URL ne sont
pas traduits. Pour H10, la question concerne **dix séances boursières de
détention**, entrée incluse, puis sortie open11. L'analyse privilégie les
informations susceptibles d'agir dans cette fenêtre. Les objectifs d'analystes
à douze mois et les perspectives annuelles servent de contexte : ils ne sont
jamais convertis en probabilité de hausse à dix séances. L'horizon effectivement
fourni par le contrat reste impératif pour les éventuels autres profils.

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

- `config/ia/prompt/cloud/oracle_directional/v11/web_search.txt` ;
- `config/ia/prompt/cloud/oracle_directional/output/v11.txt`.

Les deux fichiers v10 sont conservés pour reproduire les requêtes archivées.
Le contrôle v11 compte **155 tests réussis**, dont français/court terme pour
GPT et DeepSeek, horizons transmis sans remplacement, archivage/relecture SQL,
et empreintes identiques des requêtes v10. Reçu :
`artifacts/operations/llm_probability_20261120/tests-fr-v11-final.xml`.
L'analyse réelle `llm-d15e1538e26b400d87b025faa44528af` a aussi été revalidée
en lecture seule avec son contrat v10 : aucune réponse réécrite et aucun
nouvel appel fournisseur.

Une citation Web doit appartenir aux résultats réellement reçus. Les dates,
fraîcheur et citations locales restent contrôlées ; les dates Web sont des
dates déclarées par les sources, pas une certification historique universelle.

## Validation dans la page Pipeline

### Trois probabilités distinctes — protocole v12

Les nouvelles analyses GPT/DeepSeek renvoient désormais, en français :

| Champ JSON | Événement estimé |
| --- | --- |
| `probability_up_without_stop` | Sortie à open(H+1) au-dessus du prix d'achat ET aucune touche du SL auparavant. |
| `probability_stop_touch` | Au moins une touche du SL fixe avant la sortie, gaps compris. |
| `probability_positive_exit` | Prix à open(H+1) supérieur au prix d'achat, dans le parcours hypothétique même si un SL aurait déjà fermé la position. |

Le même prix d'entrée réel encore inconnu, le même horizon et le même SL
s'appliquent aux trois événements. La hausse finale ne désigne ni un pic
temporaire ni un trade effectivement encore ouvert après un stop.
Les deux marginales peuvent se recouvrir : elles ne s'additionnent pas à 100 %,
et le complément de la conjointe n'est pas le risque de SL. Le parseur impose
`max(0, hausse - SL) <= conjointe <= min(hausse, 1 - SL)` pour les valeurs
disponibles, sans supposer l'indépendance ni inventer une valeur absente.
Chaque marginale peut rester `null`, avec son explication ; le champ
`probability_status` conserve son sens historique pour la conjointe.

Le tableau montre **Hausse sans SL (%)**, **Touche du SL (%)** et
**Hausse à la sortie (%)**. Le tri et la sélection humaine restent fondés sur
la conjointe qualifiée. La fenêtre de détail affiche les trois valeurs et
leurs explications séparées. Les réponses v10/v11 restent revalidables,
avec « — » pour les nouvelles valeurs absentes ; leurs textes, schémas et
requêtes sont inchangés. Les deux probabilités supplémentaires ne sont jamais
déduites de `1 - probability_up_without_stop`.

Les réponses complètes restent dans les JSON des tables LLM existantes ;
les colonnes dérivées sont ajoutées au parquet scellé de la nouvelle sélection.
Aucune migration SQL ni réécriture des anciennes réponses n'est nécessaire.
Les contrôles de preuve, d'expiration, de choix humain et de risque restent
applicables ; une probabilité élevée ne les remplace pas.

Le tableau de l'étape10 affiche les candidats par probabilité décroissante,
avec une case **Retenir** par ligne, les explications et les limites des preuves.
Dans le mode **Utiliser la configuration du batch us_pipeline**, les blocs
**10, 11 et 12** restent visibles avant publication des résultats. Avec GPT ou
DeepSeek actif, ils sont ouverts et affichent les états d'attente. Le compte
choisi dans le bloc11 sert également au bloc12 ; risque et exécution sont liés
à la sélection, au compte et à la séance exacts. Le bloc12 affiche le bilan de
fin d'étape (ordres soumis et quantités exécutées constatées à cet instant),
avec prix de référence et montant cible distingués d'un prix d'exécution.
Cette consultation lit les archives locales sans appel broker ou fournisseur.
La colonne **Courbe et analyse** contient un bouton **📈 Voir** par symbole.
La fenêtre propose **1 mois / 6 mois / 1 an**, avec les barres journalières
locales arrêtées à la séance analysée, et la réponse GPT/DeepSeek archivée :
explications de probabilité, preuves, arguments favorables/défavorables,
consensus, contexte, catalyseurs, risques et sources. La consultation conserve
les cases cochées ; elle n'approuve aucun titre et ne déclenche aucun nouvel
appel fournisseur. Si les barres sont absentes, l'analyse reste consultable.
Les cases sont initialement décochées. Une estimation absente ou invalide,
une identité non confirmée ou un autre contrôle obligatoire en échec restent
interdits. Aucun titre hors de la liste per-symbol n'est ajouté.
La qualification des preuves peut être exigée ou laissée au choix humain via
`config.yaml → us_pipeline.gpt_require_qualified_evidence_for_manual_selection`.
Cette option vaut **false** à la demande de l'utilisateur : un candidat avec
estimation valide peut être choisi malgré des preuves partielles. Sa qualité
et ses réserves restent affichées. Si la clé est absente, le défaut est strict
(`true`) ; une valeur qui n'est pas booléenne est refusée.

Une nouvelle validation de schéma2 archive la politique choisie et les réserves
de preuve explicitement acceptées, sans modifier le rapport, le parquet ni les
réponses LLM originaux. Les anciennes validations de schéma1 restent strictes.
Le risque et l'exécution utilisent la liste humaine figée et l'empreinte de sa
validation ; changer la politique globale après validation ne change pas ce
choix archivé. Les contrôles techniques de réponse, modèle, horizon/SL,
intégrité et expiration restent applicables, ainsi que les limites de risque.

Un choix interdit est refusé explicitement avec ses symboles avant la
revalidation SQL. Ce message est conservé malgré le rafraîchissement du bloc ;
un indicateur signale la revalidation des preuves lors d'un choix admissible.
Valider une liste vide permet de terminer sans achat.

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

Pour l'évolution **Courbe et analyse**, **191 tests ciblés passent**, dont le
bouton intégré à chaque ligne, le tri avec conservation de l'identité du titre,
les périodes 1/6/12 mois, la conservation des cases cochées après consultation,
l'analyse disponible sans barres, la liaison à la proposition scellée et
l'absence de validation d'achat lors de l'ouverture d'une fenêtre.
Reçu : `artifacts/operations/llm_probability_20261120/tests-details-verified.xml`.

Limite de l'environnement de test : deux tests historiques d'arrêt de processus
de la suite complète du registre ne peuvent pas arrêter leur propre enfant via
`taskkill` dans l'environnement restreint (refus d'identification Windows).
Le diagnostic sur un enfant de test reproduit ce refus ; la terminaison directe
de cet enfant fonctionne. Le code de terminaison n'a pas été modifié pour cette
évolution. Les tests pertinents du registre, dont blocage/reprise avant risque
et préparation du watcher, passent dans le contrôle ciblé final.
