# Analyses GPT des news : stockage SQL et réutilisation sans nouvel appel

Extension distincte autorisée le 15 octobre :
[campagne TOP20 Oracle parcours 2024–septembre 2026, plafond de nouveaux appels 8 USD](../ml/news_gpt_top20_historique_2024_2026.md).
Elle utilise les mêmes tables ; les effectifs ci-dessous décrivent l'import
initial, pas le nombre courant après cette nouvelle campagne. Son état réel est
dans son `progress.json`/`report.json` ; aucune réussite n'est présumée ici.

Livraison du **15 octobre 2026**, à la demande de l'utilisateur. US uniquement,
base `alpha_trade`. Ni nouveau test payant, entraînement, ordre, batch ni changement
des règles du portefeuille. Le cache est distinct du filtre quotidien GPT/Web.

## Ce qui est livré et vérifié

**221 réponses déjà payées importées** : 213 du T1 2025 et 8 du pilote de septembre
2026. 203 valides techniquement, 18 invalides conservées sans les repayer.
Une seconde importation a réutilisé les 221 lignes, sans doublon.

Deux relectures **depuis la base seule**, sans besoin des fichiers d'origine pour
le replay, ont reconstitué les 600 couples titre/date du trimestre et les 25 du
pilote. Avis, veto et rangs identiques aux fichiers originaux. Clé OpenAI retirée
du processus de vérification et HTTP bloqué : **zéro nouvel appel API**.

Cela ne transforme pas l'expérience en historique PIT : les dates d'import et
de disponibilité locale restent celles de cette opération, jamais 2025.

## Tables

| Table | Contenu |
| --- | --- |
| `llm_news_analysis_cache` | Une requête exacte et sa réponse brute, modèle demandé/retourné, symbole, périmètre, empreintes, consommation originale, avis validé, statut et timestamps UTC. Clé primaire SHA-256 de la requête versionnée et de son périmètre. |
| `llm_news_analysis_articles` | Articles et versions exactes fournis dans chaque requête, position dans le lot et empreinte de l'objet texte/métadonnées. Recherche par article, jointe au symbole de l'analyse. Pas de suppression en cascade depuis `news_raw`. |
| `llm_news_analysis_uses` | Traçabilité des imports, appels et réutilisations par expérience. Une réutilisation ne recompte pas les tokens originaux comme nouvelle facture. |
| `llm_news_analysis_research_runs` | Snapshot complet des paquets de recherche, y compris les candidats sans news, rangs Oracle, références des réponses et manifeste d'origine. Permet une relecture autonome depuis SQL. |

Après import et première relecture : **221 analyses, 912 associations article/lot,
442 usages et 2 snapshots de recherche**. Les associations ne sont pas 912 appels
GPT ni nécessairement 912 articles distincts. Les usages grandiront avec les tests.

L'avis validé et le RAW contiennent `decision`, `confidence`, `reason`,
`issuer_match`, `basis` et les citations `evidence` avec `article_id` :

- BULLISH : faits soutenant une lecture haussière ;
- BEARISH : faits soutenant une lecture baissière ;
- ABSTAIN : preuve insuffisante ou ambiguë ;
- confiance entre 0 et 1 : **note subjective, pas probabilité calibrée de gain**.

Une réponse invalide reste `UNKNOWN_INVALID_RESPONSE`, pas un avis de confiance
utilisable ; son texte brut original n'est ni corrigé ni effacé. Dans le test
T1 2025, BEARISH valide et confiance >=0,75 bloque seulement un nouveau LONG :
**aucun SHORT** n'est déclenché et les positions existantes ne sont pas fermées.

## Deux unités d'analyse à ne pas confondre

### `SYMBOL_DATE_BUNDLE` : anciens tests importés

L'avis porte sur **un lot d'articles pour un symbole et une date**, avec son
heure limite de décision. Les 221 réponses importées ont ce périmètre.

Même requête, modèle, prompt, contenu et contexte temporel : la réponse SQL est
réutilisée. Changer uniquement le TP/SL, la taille du portefeuille ou le filtre
appliqué aux avis ne nécessite pas de rappeler GPT.

Mais un avis sur cinq articles ne devient pas artificiellement cinq avis
indépendants. Si un article de ce lot est demandé seul, le système signale
`BundledEvidenceOnly` **sans appeler GPT** : récupérer le lot comme lot, ou
autoriser explicitement une expérience unitaire distincte. Ne pas affecter la
conclusion d'un ensemble à chacun de ses articles.

### `ARTICLE_AT_PUBLICATION` : service unitaire réutilisable

`service.llm_directional.stored_news.analyze_article` analyse un seul article
pour un émetteur, à sa publication. Sa requête ne contient pas la date courante
du backtest : un article strictement inchangé peut donc être relu à plusieurs
dates/expériences sans paiement supplémentaire.

L'identité du cache comprend le symbole, la référence d'émetteur, l'identifiant
et les textes/métadonnées exacts, la publication, le modèle, le prompt, le schéma
et les paramètres de génération. L'ordre des clés des dictionnaires est
normalisé par le constructeur de requête unitaire. Un texte corrigé, un nouveau
modèle ou protocole ne doit pas récupérer un ancien verdict incompatible.

**Aucune analyse unitaire payante n'a été lancée pour cette livraison.** Les
221 anciens lots ne remplissent donc pas une prétendue collection de verdicts
unitaires. Le service retourne d'abord un hit SQL, même sans clé OpenAI ; sur un
miss, la dépense est désactivée par défaut. Un appel nouveau exige un transport
fourni explicitement, `allow_paid=True` et un journal local durable ; le code
appelant doit aussi imposer le budget autorisé. La CLI livrée n'a aucune commande
permettant de lancer des appels payants.

La réutilisation d'une extraction ne prouve pas que la news soit encore récente,
nouvelle ou pertinente pour une entrée aujourd'hui. Les nouvelles informations
et le contexte du jour restent à qualifier séparément.

## Concurrence, reprise et preuves

La réservation en base est atomique sur la clé unique **avant** un appel payant.
Un second processus ne peut donc pas déclencher un deuxième appel pour la même
requête. Une tentative en cours ou dont l'issue est inconnue n'expire pas pour
être automatiquement repayée.

Le RAW est sauvegardé localement puis en SQL avant validation. `available_at`
est confirmé après le commit SQL. Si cette confirmation est interrompue,
l'import explicite de la même réponse sauvegardée peut la confirmer plus tard,
à l'heure de reprise, sans antidatation ni nouvel appel. Une horloge reculant
par rapport à la réception est refusée.

Une réponse différente pour une même requête provoque un refus d'écrasement.
Les empreintes du RAW et des snapshots sont vérifiées à la lecture. Les dates
fournisseur et fichiers historiques sont conservées en provenance, sans devenir
des dates de disponibilité locale. Les manifests de préparation et de réponses
sont vérifiés avant import, paquets et rangs compris.

Une nouvelle validation locale peut relire le RAW déjà payé sans le remplacer.
Une invalidité technique n'est pas une permission de retry ni un avis baissier.
Les fichiers et rapports de recherche scellés d'origine restent inchangés.

## Utilisation

Installation ciblée, **déjà effectuée** ; ne lance pas toutes les migrations
intermédiaires et ne modifie pas le marqueur Alembic local :

```powershell
python -m service.llm_directional.news_cache_cli --install
python -m service.llm_directional.news_cache_cli --status
```

Réimport idempotent d'une recherche :

```powershell
python -m service.llm_directional.news_cache_cli --import-run artifacts/research/us_news_gpt_q1_2025/20261014-v2
```

Relecture du T1 2025 **uniquement depuis SQL**, dans un nouveau dossier :

```powershell
python -m service.llm_directional.news_cache_cli --replay-import 6881b0239c790d8c3d9c88278266c92ddfe2884c2b0af14de80cd7c970aea021 --output artifacts/research/llm_news_cache/mon-prochain-test
```

Produit `assessments.json` et `report.json`, sans API ni PnL. Le nouveau test
peut joindre ces avis à ses candidats par date/symbole et tester ses propres
règles, en déclarant l'optimisation rétrospective si elle utilise ces résultats.

Recherche d'une analyse existante :

```powershell
python -m service.llm_directional.news_cache_cli --find-article <article_id> --symbol <SYMBOL>
python -m service.llm_directional.news_cache_cli --show-analysis <cache_key>
```

Le second identifiant d'import, pour le pilote septembre :
`65c047dee041fa2a607886be03265b8d70ed5ed287b729df55dca1ae8a0c9d8d`.
Toutes ces commandes sont dépourvues de chemin d'appel API payant.

## Périmètre d'intégration et validation

Le pipeline quotidien GPT/DeepSeek + recherche Web continue d'utiliser
`llm_directional_runs` / `llm_directional_assessments`, avec ses contrôles de
fraîcheur et d'exécution PAPER. **Il n'est pas remplacé par ce cache historique** :
une réponse Web ancienne ne suffit pas à vérifier les nouvelles informations.
Les anciens scripts de recherche scellés ne sont pas modifiés ; les nouveaux
tests réutilisent l'entrée SQL décrite ici.

Schéma canonique : `database/sql/ml/llm_news_analysis_cache.sql` ; migration
livrée : `0105_llm_news_cache`, après `0104_news_versions`. Aucun downgrade
destructif automatique des réponses payées. L'installation est limitée à US ;
pas d'écriture dans FR/CN, `news_raw` ou les anciennes tables directionnelles.

Rapport d'opération : `artifacts/research/llm_news_cache/20261015-v1/verification.json`.
**92 tests isolés réussis**, dont 27 dédiés au cache. SQLite/transports simulés :
idempotence, deux workers, erreur ambiguë,
citations invalides, séparation lot/article, changement texte/modèle/prompt,
lecture autonome, corruption et schéma canonique. Aucun nouveau résultat de
performance ou capacité directionnelle n'est revendiqué par cette infrastructure.

Référence API consultée : [conservation des réponses OpenAI](https://developers.openai.com/api/docs/guides/conversation-state).
La sauvegarde SQL applicative est indépendante de `store:false` dans nos requêtes
et du cache de tokens côté fournisseur : une relecture SQL ne soumet aucune
requête à GPT.
