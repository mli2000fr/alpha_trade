# Test local Qwen après per-symbol — préparation du 7 novembre 2026

Ce protocole compare **deux bras figés**, sans sélectionner des paramètres après
observation des rendements. Il ne remplace pas le per-symbol et ne modifie ni le
pipeline ni les comptes Alpaca. Aucun appel GPT/DeepSeek, entraînement ou ordre.

## Comparaison

| Bras | Parcours |
| --- | --- |
| A | Oracle H10 → per-symbol LONG → risque → Winner |
| B | Même sélection → veto news du Qwen local → même risque → même Winner |

Référence : `20261107_095041_0b38b8de`, modèle
`model-factory-20261106203103-91b063`. Les **204 candidatures**, concernant
**24 titres**, sont analysées, sans se limiter aux 59 trades effectivement exécutés.
Les candidatures exclues ne sont pas remplacées par les rangs suivants.

Paramètres entièrement repris du protocole archivé, indépendamment des réglages
actuels de production : 2025, 4 000 USD, compte margin, exposition maximale 2×,
TOP10 % Oracle (179/1 790) → TOP10 LONG, probabilité strictement >0,70,
AUC de calibration ≥0,60. Entrée directe à l'ouverture J+1, sans confirmation 5m,
position complète, aucun renforcement. SL5 %, sans TP ni trailing, H10 et sortie
open11. Risque budgété 1,25 %, poids maximal 20 %, minimum 50 USD, vingt positions.
Frais canoniques 8 points de base par opération, intérêt annuel de marge 6,5 %.
Pas de contrôleur DD ni de contrôle factoriel dans cette référence précise.

Le replay A doit retrouver le capital **4 275,9536665 USD**, le rendement
**+6,8988417 %**, le DD **−10,8560294 %**, les coûts, l'exposition moyenne et
les 59 trades de la référence. Une différence bloque la publication du comparatif B.
Le replay utilise le moteur natif et les mêmes données figées que la grille en
cours, sans la modifier. Les protections/valorisations conservent l'intraday et
les replis OHLC journaliers de la référence ; l'entrée seule est journalière.

## Données fournies au modèle

Pour chaque couple symbole/date J, cutoff = clôture officielle NYSE de J :

- News EODHD/Alpaca déjà en base, publiées strictement avant le cutoff pendant
  les sept jours calendaires précédents. Horaires et fuseaux bruts contrôlés ;
  dates seules exclues. Doublons de corps supprimés. Maximum six articles récents,
  titre de 500 caractères et extrait de corps de 3 000 caractères par article.
- Résumé prix/volume limité aux soixante dernières observations journalières
  disponibles à J : rendements passés 1/5/20/59 séances, dernier cours et volumes.
  Même résumé pour SPY. Les prix futurs ne figurent jamais dans une requête.
- Nom actuel de l'entreprise identifié comme métadonnée rétrospective, indicateur
  de ticker principal, URL, publication et dates observées des versions archivées.

Pas de consensus/options historiques extrapolés à 2025, de sentiment recalculé
présenté comme historique, ni d'extraits SEC sans reçus qualifiés. Les bornes de
requête couvrent uniquement les fenêtres des candidatures, fusionnées et
partitionnées aux changements de mois. Toute limite SQL atteinte est fatale :
aucune conclusion sur un corpus tronqué. Les omissions d'articles/extraits dans
un dossier sont comptées ; le LLM ne lit donc pas nécessairement toutes les news.

## Prompt et règle de veto

Prompt dédié :
`config/ia/prompt/local/oracle_directional/v1/research_veto.txt`,
catalogue `local.oracle_directional.v1.research_veto`, runtime `local`.
Le texte exact est copié dans l'archive ; toute modification impose une nouvelle
préparation. Les prompts cloud restent indépendants.

JSON structuré imposé par `response_format` de LM Studio, puis validé localement :
appréciation FAVORABLE / UNFAVORABLE / INDETERMINABLE, qualité des
preuves, faits avec citations exactes, attribution à l'émetteur et contre-arguments.
Pas de conseil d'ordre, d'objectif de prix ni de score de confiance inventé.
Le prompt rappelle qu'un bon résultat publié peut rester inférieur aux attentes,
mais interdit d'inventer un consensus absent pour prétendre mesurer une surprise.

Veto seulement si les conditions cumulatives sont vérifiées : UNFAVORABLE,
SUFFICIENT, citation exacte d'une news fournie, fait BEARISH attribué par le modèle
à l'émetteur, association de ticker principal. Les faits concernant un partenaire
ou un investisseur ne doivent pas devenir des faits de l'émetteur.
Les espaces et sauts de paragraphe peuvent être normalisés ; aucun mot ni signe
de ponctuation ne peut être modifié, ajouté ou omis pour faire passer une citation.
**Ce contrôle automatique ne prouve pas la vérité de l'attribution sémantique.**
Un petit pilote doit être relu avant la campagne complète.

Absence de news et indétermination conservent la candidature initiale. Une erreur
technique ou une réponse invalide n'entraîne pas de veto, mais reste visible comme
analyse incomplète et **bloque le comparatif complet** tant qu'elle n'est pas résolue.
Pas de reprise automatique en boucle après erreur, ni de recours au cloud.

## Cache, reprise et commandes

Script : `scripts/research/us_local_llm_winner_ab.py`.
Les phases s'exécutent séparément ; aucune campagne financière n'est lancée par
la préparation. Le prompt, les requêtes, les sources et les données ont des
empreintes vérifiées avant analyse/replay. Un verrou local évite deux analyses
simultanées du même dossier ; aucun verrou du pipeline n'est modifié.

Préparation depuis la base US en lecture seule, dans un dossier neuf :

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.research.us_local_llm_winner_ab prepare --output-dir artifacts/research/us_local_llm_winner_ab/NOUVEAU_DOSSIER
```

Pilote local, maximum trois appels nouveaux, puis reprise avec les mêmes dossiers :

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.research.us_local_llm_winner_ab analyze --output-dir artifacts/research/us_local_llm_winner_ab/20261107-v7 --limit 3
.\.venv\Scripts\python.exe -X utf8 -m scripts.research.us_local_llm_winner_ab analyze --output-dir artifacts/research/us_local_llm_winner_ab/20261107-v7 --limit 204
```

Serveur local exclusivement : `127.0.0.1:1234/v1`, Qwen3.5-9b, température zéro,
Initialement 8 192 tokens maximum en sortie et délai 300 secondes ; la reprise v7
utilise 16 384 et 600 secondes pour les appels restants. Appels séquentiels. La limite
de sortie inclut le raisonnement éventuel. Une réponse tronquée est invalide.
Une erreur transport arrête l'invocation ; `--retry-errors` permet une reprise
explicite des erreurs. Les réponses valides déjà présentes ne sont pas rappelées.

Cache **SQLite de recherche isolé**, fichier `analyses.sqlite3`, table `attempts` :
requête exacte, réponse brute, consommation renvoyée par le serveur, validation,
justification et citations, horodatage. Pas d'écriture dans les tables cloud ou
dans MySQL partagé. Clé = requête exacte + version déclarée des poids ; un autre
jour/contexte/prompt/modèle/options donne une autre clé. Le même article dans
un nouveau contexte nécessite une nouvelle analyse. Si les poids/quantification
changent sous le même nom LM Studio, refaire un dossier/version : leur empreinte
physique n'est pas certifiée par ce connecteur.

Quand toutes les réponses sont valides ou explicitement sans news :

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.research.us_local_llm_winner_ab replay --output-dir artifacts/research/us_local_llm_winner_ab/20261107-v7
```

Sorties : `coverage.csv`, `protocol.json`, `requests.json`, `decisions.json`,
`analysis-report.json`, `progress.json`, puis `replay/comparison.csv` et,
par bras, capital quotidien, trades, événements et rapport. Le comparatif inclut
capital final, rendement, DD max, gagnants/perdants, gains/pertes moyens,
durées de détention, capital moyen/maximal engagé et frais. Le répertoire `replay`
doit être absent avant lancement : aucun ancien résultat n'est écrasé.

## Pilote réel et durée mesurée

Première tentative à 4 096 tokens : absence de texte final, analysée comme échec,
pas comme indétermination. Deuxième tentative : **7 005 tokens générés**, dont
6 576 de raisonnement, avec plafond **8 192**, en **259,43 secondes** sur MMYT au
signal du 31 décembre 2024. Réponse JSON complète, deux citations vérifiables.
Le premier contrôle refusait une citation pour un saut de paragraphe remplacé
par un espace : la normalisation strictement typographique a permis de la
revalider **sans nouvel appel**. L'attribution et la qualité prédictive ne sont
pas pour autant validées indépendamment. L'appréciation du modèle est défavorable,
pas un résultat de trade.

Cette réponse a été reprise dans le cache de la campagne après comparaison
exacte de la requête réellement envoyée avec la requête figée. 38 candidatures
sans news sont conservées automatiquement ; 165 analyses restent à réaliser.
La campagne complète et le replay économique n'ont pas été lancés.

À cette vitesse seule : 166 × 259,43 s = **11,96 heures** en séquentiel,
hors replay et éventuelles erreurs. Estimation provisoire sur **un seul dossier**,
avec les simulations en parallèle, pas une moyenne représentative du corpus.
Les dossiers plus volumineux peuvent dépasser la limite de sortie ou le délai.
Le pilote prévu sur dossiers médian/maximal s'est arrêté après la première
validation refusée ; aucun second ou troisième appel n'est dissimulé dans la durée.

La lecture de `/api/v1/models` identifie Qwen3.5-9b Q8_0 et un contexte chargé de
**112 591 tokens** : c'est la fenêtre de contexte, **pas la limite de génération**.
Un contexte de 32 768 paraît suffisant pour les dossiers bornés de ce test,
mais n'a pas été chronométré ici. Aucun rechargement ni changement du réglage
global LM Studio n'a été effectué par ces scripts.

Preuves : `preparation-summary.json` dans le dossier v6 et
`artifacts/operations/local_llm_winner_probe/20261107-v1/response-1.json`,
`revalidation-v2.json`, `timing-reviewed.json`, `server-models.json`.
Les dossiers v1/v2 sont des préparations interrompues ; v3 conserve l'essai sans
format structuré, v4/v5 les révisions intermédiaires ; v6 est la première campagne
arrêtée sur troncature. **Poursuivre désormais v7**, décrit ci-dessous.
Le changement de budget/transport a réutilisé les entrées scellées, sans nouvelle
lecture SQL dans les révisions v5/v6.

Références techniques : [JSON structuré LM Studio](https://lmstudio.ai/docs/developer/openai-compat/structured-output),
[modèle Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B).

### Comparaison après réduction du contexte à 34 186

À la demande de l'utilisateur, nouvelle inférence du **même dossier MMYT** avec
requête exactement identique, plafond de sortie toujours 8 192. Le contexte chargé
de 34 186 a été vérifié avant l'appel. Temps réel **181,91 secondes (3 min 02)**,
contre 259,43 : **29,88 % de réduction de durée** sur cet essai.
Même nombre de tokens (2 649 en entrée, 7 005 générés dont 6 576 de raisonnement),
et **texte final identique**, avec validation des citations réussie.

À ce rythme : **8,39 heures, environ 8 h 23**, pour 166 appels séquentiels,
hors replay/erreurs. Cela reste une extrapolation sur un seul couple de mesures,
pas un benchmark répété à charge système identique. Ce second essai était un
appel délibéré de chronométrage ; les analyses métier déjà en cache n'ont pas
besoin d'être recalculées. La campagne financière reste non démarrée.
Preuve : `artifacts/operations/local_llm_winner_probe/20261107-context34186-v1/comparison.json`.
Copie du bilan de durée dans le dossier v6 : `timing-context34186.json`.

### Campagne A/B lancée le 7 novembre 2026

Go utilisateur reçu après le chronométrage. Coordinateur :
`scripts/research/us_local_llm_winner_campaign.py`, dossier de suivi
`artifacts/research/us_local_llm_winner_ab/20261107-v6/campaign`.
Départ : une analyse valide en cache, 38 candidatures sans news conservées,
165 appels locaux manquants. Qwen Q8_0, contexte chargé 34 186 vérifié au lancement,
limite de sortie 8 192 inchangée, appels séquentiels. Aucun test C.

Le coordinateur lance les analyses, puis les replays A et B seulement si toutes
les candidatures sont validées ou explicitement sans news. Une erreur terminale,
troncature ou validation non résolue interdit le bilan économique complet ;
pas de répétition automatique des appels en erreur et pas d'avis manquant inventé.
Les simulations de la grille initiale continuent indépendamment.

Suivi : `campaign/progress.json` (compteurs validés, invalides, en attente, vetoes,
PID de l'enfant, puis avancement des deux replays), `campaign/analyze.log`,
`campaign/replay.log`, bilan terminal `campaign/report.json` et, en cas de succès,
tableau `campaign/summary.md` et `replay/comparison.csv`. La consommation et les
réponses brutes sont conservées dans `analyses.sqlite3` ; aucun crédit GPT.
Le lancement n'est pas un résultat d'efficacité directionnelle.

### Reprise à 16 384 tokens — dossier v7

La campagne v6 s'est arrêtée le 7 novembre à 17 h 04 Paris sur BAND, signal du
8 janvier 2025 : 8 192 tokens générés, dont 8 191 de raisonnement, aucun texte
final. Bilan : trois analyses LLM valides, 38 absences de news conservées,
un échec et 162 dossiers en attente ; aucun replay A/B n'a été démarré.

Sur instruction explicite de l'utilisateur, reprise à **16 384 tokens de sortie**,
délai maximal **600 secondes** par appel, contexte LM Studio **34 186** inchangé
et vérifié au lancement. Dossier à poursuivre désormais :
`artifacts/research/us_local_llm_winner_ab/20261107-v7`.
La requête de BAND et les 162 requêtes non encore exécutées ont le nouveau budget.
Les trois réponses valides gardent leurs requêtes exactes à 8 192 et leurs clés
de cache initiales ; les 38 dossiers sans news restent conservés sans appel.
La copie SQLite préserve également l'ancienne tentative BAND invalide sous son
ancienne clé : elle n'est ni écrasée, ni présentée comme la réponse à 16 384.
Toutes les réponses réutilisées ont été revalidées contre leurs extraits figés.

Même corpus, prompt, ordre de sélection, règle de veto, modèle et paramètres
financiers. Pas de nouvel accès fournisseur ou SQL partagé. Amendement et liste
des clés réutilisées/modifiées : `budget-amendment.json`. Dossiers précédents
conservés intégralement. Validation technique de la reprise et des protections :
**101 tests passent**. Le nouveau coordinateur a démarré à 18 h 29 Paris :
163 appels de rattrapage, puis les replays A/B conditionnés à la validation.

Suivi courant : `20261107-v7/campaign/progress.json`, qui inclut le symbole/date
en cours et son plafond de sortie. Les commandes suivantes ciblent la reprise :

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.research.us_local_llm_winner_campaign --output-dir artifacts/research/us_local_llm_winner_ab/20261107-v7
```

Ne pas lancer une seconde instance si la campagne tourne déjà. Le coordinateur
refuse d'écraser une campagne déjà tentée. Si une réponse reste tronquée ou
invalide, le comparatif économique complet reste bloqué ; aucun nouveau doublement
ni nouvel appel sur une erreur ne sont déclenchés automatiquement.

## Limites d'interprétation

Les textes extraits aujourd'hui sont des versions mutables, pas une preuve de
disponibilité/version à chaque décision en 2025. La mémoire d'entraînement du
LLM peut aussi contenir les événements futurs de 2025. Même un bon résultat
resterait **exploratoire et rétrospectif**, sans certification PIT ni validation
indépendante. Les réserves de survivorship, de secteurs actuels et de couverture
intraday de la référence restent applicables. Voir également le registre des
expériences antérieures de veto GPT et d'embeddings : ce test local ne constitue
pas une source d'information nouvelle ni un avantage directionnel déjà établi.
