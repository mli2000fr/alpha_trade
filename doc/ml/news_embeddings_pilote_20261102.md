# News → embeddings → direction après Oracle : pilote du 2 novembre 2026

## Autorisation et état

GO utilisateur après proposition d'un plafond de **3 USD**, embeddings seuls.
**Terminé et audité : `COMPLETED_EXPLORATORY_NOT_PIT`.**
24 244 textes uniques, 11 013 120 tokens réellement retournés dans l'usage API,
**1,43170560 USD** calculés au tarif Standard. 190 lots réussis, un premier
rejet HTTP 429, zéro appel à issue inconnue. Plafond de 3 USD respecté.
Réserve conservatrice initiale totale 1,89048704 USD ; aucune somme remise à
zéro pour les appels réussis lors de la reprise.

## Résultat et décision

**Petit signal H5, pas d'avantage directionnel stable démontré.** L'objectif
primaire H20 reste proche du hasard sur la totalité des cas évaluables.
L'amélioration relative contre une référence inférieure à 0,50 ne suffit pas
à démontrer une capacité utile de classement. Aucune promotion du filtre.

Évaluation rétrospective 2026, mêmes observations pour les trois bras :

| Horizon | Cas qualifiés | AUC prix/rang/news-count | AUC texte seul | AUC prix/rang + texte |
| --- | ---: | ---: | ---: | ---: |
| H5 | 2 170 | 0,5179 | 0,5343 | 0,5485 |
| H10 | 2 141 | 0,4475 | 0,5250 | 0,5238 |
| H20, primaire | 2 038 | 0,4577 | 0,5072 | 0,4997 |

Contrôle sans chevauchement, dates choisies avant les résultats futurs :

| Horizon | Cas qualifiés | AUC prix/rang/news-count | AUC texte seul | AUC prix/rang + texte |
| --- | ---: | ---: | ---: | ---: |
| H5 | 674 | 0,5100 | 0,5388 | 0,5374 |
| H10 | 445 | 0,4309 | 0,4777 | 0,4670 |
| H20 | 281 | 0,4243 | 0,5651 | 0,5327 |

H20 texte seul paraît meilleur sur le contrôle de 281 cas, mais ce résultat
ne se retrouve pas sur les 2 038 événements : il ne justifie pas de choisir
après coup cet échantillonnage comme preuve positive.

Le sens du pic dominant est haussier pour 52,35 % des cas H5, contre 54,75 %
des cas retenus à probabilité >=0,5 par prix + texte. Sur le contrôle sans
chevauchement : 50,30 % contre 51,72 %. Ce sont des proportions de mouvements
dominants positifs, **pas des taux de trades gagnants après stop**.

Diagnostic unitaire LONG TP10/SL10, coûts 13 bps par opération, sans portefeuille :

| Horizon | Tous, moyenne nette | Retenus prix + texte | Tous sans chevauchement | Retenus sans chevauchement |
| --- | ---: | ---: | ---: | ---: |
| H5 | +0,233 % | +0,400 % | +0,134 % | +0,096 % |
| H10 | +0,260 % | +0,314 % | +0,305 % | −0,003 % |
| H20 | +0,129 % | +0,210 % | +1,085 % | +0,959 % |

Les améliorations unitaires observées sur les événements qui se chevauchent
ne se confirment pas sur ce contrôle. Ces moyennes ne sont pas des rendements
de capital, ni un replay Winner, ni une preuve que des positions indépendantes
pourraient toutes être achetées.

Prix + texte améliore l'AUC relative dans 4/9 mois H5, 7/9 H10 et 6/9 H20.
Les intervalles hebdomadaires exploratoires des deltas AUC valent respectivement
[−0,0100 ; +0,0682], [+0,0318 ; +0,1228], [+0,0031 ; +0,0760]. Ils portent sur
le delta contre la référence, pas sur une capacité absolue supérieure au hasard ;
ils ne retirent pas toutes les dépendances de H20.

Le comparateur ordinal des anciens avis GPT donne, sur les cas communs valides,
AUC 0,4947/0,4970/0,4987 à H5/H10/H20. Ce n'est pas une probabilité calibrée.

**16 tests ciblés passent.** Les neuf modèles sauvegardés reproduisent les
19 047 probabilités publiées à une erreur maximale de 1,12e−16. Les 24 244
vecteurs du cache ont été vérifiés ; tokens prévus et retournés identiques.
Audit réalisé par le même assistant, pas une revue humaine indépendante.

Suite éventuelle : H5 peut rester une hypothèse de recherche à confirmer sur
des textes correctement datés/versionnés et une période future figée. Ce pilote
ne justifie pas une recherche de nouveaux seuils sur 2026 ni une nouvelle
dépense API immédiate. Les embeddings restent réutilisables sans les repayer.

Ce travail est **rétrospectif exploratoire, non certifié PIT**. Les fichiers
étaient archivés avant cette expérience, mais leurs dates de réception ne
certifient pas leur disponibilité lors des décisions 2024–2026. Aucune preuve
directionnelle exploitable en production ne découle des seuls résultats du pilote.

## Population et textes

Les TOP20 originaux des modèles annuels déjà utilisés sont repris, sans
réentraîner Oracle et sans substituer des titres manquants :

| Année | Modèle annuel | Couples titre/séance | Couples avec textes |
| --- | --- | ---: | ---: |
| 2024 | `model-factory-20261014113215-437ed1` | 5 040 | 1 379 |
| 2025 | `model-factory-20261014113226-102eca` | 5 000 | 2 257 |
| 2026, jusqu'au 30 septembre | `model-factory-20261014113232-bc35a7` | 3 740 | 2 191 |

Source : `artifacts/research/us_news_gpt_top20_history/20261015-v1`.
Fichiers mensuels, rangs, scores et lignée Oracle sont vérifiés par empreinte.
Les seuls textes sont titre, résumé et corps/extrait déjà fourni dans les
paquets scellés. Les avis GPT antérieurs ne sont pas fournis à l'encodeur.
18 377 des 25 787 associations article/titre/séance portent déjà un indicateur
de troncature : il ne s'agit pas d'un test sur un corpus entièrement intégral.
Aucune nouvelle troncature n'a été appliquée. Aucun nouveau téléchargement de news.

Le modèle `text-embedding-3-large` est figé, avec 256 dimensions demandées.
Le nombre de tokens est calculé par `cl100k_base` avant toute dépense.
Les embeddings ne sont ni des opinions GPT ni des probabilités LONG.
Les textes sont traités comme des données, sans recherche Web ni outil.

## Conservation et maîtrise des appels

Stockage SQL local de recherche :
`artifacts/research/us_news_embeddings/cache.sqlite`.
Tables : `embedding`, `paid_call`, `campaign`.

La clé de cache inclut le texte exact, le modèle, les dimensions et le protocole
de représentation. Une même représentation peut être réutilisée entre titres,
dates, horizons et expériences. Les anciennes analyses conversationnelles GPT
ne sont ni écrasées ni réétiquetées en embeddings.

Chaque lot est réservé durablement en SQLite avant le POST. Réserve : tokens
comptés + 25 % + 32 tokens par entrée. Une requête à issue inconnue conserve sa
réserve et interdit la reprise automatique. Aucun retry HTTP payant automatique.
Les entrées exactes, réponses brutes compressées, usage et vecteurs sont conservés
sous le répertoire de recherche. Le tarif utilisé est 0,13 USD/million de tokens,
Standard, hors taxes/change. Le plafond concerne ce pilote, pas d'autres logiciels
qui utiliseraient éventuellement la même clé API.

Un premier passage a reçu HTTP 429 après 22 lots réussis. Sa réponse d'erreur
complète n'avait pas été conservée ; le code précis de ce premier rejet est
donc inconnu. Son statut HTTP et son journal identifient néanmoins un refus
explicite, pas une requête à issue inconnue. Une reprise contrôlée a conservé
les succès, scellé le reçu de rejet et repris seulement les textes absents.
Le premier appel de reprise a réussi. Les en-têtes annoncent 1 000 000 tokens
par minute ; la suite limite ses fenêtres à 70 % de ce seuil.

L'amendement de transport est `transport-amendment.json`, avec les empreintes
du protocole initial inchangé et du nouveau transport. Les réponses positives
ne sont jamais rappelées. Les futurs refus 429 ne sont repris automatiquement
que pour un code explicitement temporaire ; crédit/quota/facturation ou code
inconnu arrêtent la reprise. Les timeouts et issues ambiguës conservent leur
réserve. Le budget de 3 USD reste celui du même registre SQLite.

## Test fixé avant accès aux résultats futurs

- H20 primaire ; H5 et H10 secondaires.
- Entrée théorique au prochain open J+1. Pour Hn : les n séances J+1…J+n.
- Direction cible : maximum de hausse supérieur à la valeur absolue du maximum
  de baisse, depuis ce prix d'entrée. Les deux excursions et leur ordre sont gardés.
- Diagnostic distinct : premier passage à +10 % ou −10 %, avec cas touchant les
  deux barrières dans une bougie explicitement ambigus. Pour la seule mesure
  économique unitaire, ces cas sont résolus défavorablement au LONG.
- Les fenêtres incomplètes, remplies, les prix incohérents et changements
  d'identité sont exclus des labels ; aucune barre n'est inventée.
- Apprentissage 2024, réglage 2025, évaluation rétrospective 2026. Les labels
  franchissant une frontière de split sont purgés. Les observations ultérieures
  réutilisant le même texte qu'un split antérieur sont écartées.
- Trois bras : prix/rang/quantité de news ; texte seul ; prix/rang + texte.
- Modèle local : régression logistique L2. Normalisation apprise sur train.
  Trois régularisations prédéfinies, choix au Brier 2025, puis refit sur 2024–2025.
- Même cohorte pour tous les bras. La présence de textes n'est pas une opinion
  neutre pour les autres titres ; la conclusion est conditionnelle au sous-ensemble couvert.
- Mesures sur événements chevauchants et contrôle sans chevauchement par titre ;
  comparaison appariée avec bootstrap en blocs hebdomadaires et détail mensuel.
- Seuil LONG diagnostic 0,5 fixé, sans rechercher de meilleur seuil sur 2026.

Le PnL unitaire TP10/SL10 expire à la clôture de la dernière séance étudiée.
Il inclut 8 points de base de frais et 5 points de base de slippage par opération.
Ce sont des hypothèses figées du diagnostic, pas un tarif broker certifié.
**Ce n'est pas un replay de portefeuille Winner** : ni capital, levier, concurrence
entre positions, disponibilité short, financement ou drawdown de portefeuille.
Le signe du maximum dominant n'est pas le taux de réussite TP avant SL.

## Commandes et sorties

```powershell
python -u -m scripts.research.us_news_embeddings_pilot --phase prepare
python -u -m scripts.research.us_news_embeddings_pilot --phase embed
python -u -m scripts.research.us_news_embeddings_pilot --phase evaluate
```

Dossier du pilote : `artifacts/research/us_news_embeddings/20261102-v1`.
Suivi : `progress.json` et `embedding.log`.
Entrées : `protocol.json`, `population.parquet`, `articles.parquet`, `article-uses.parquet`.
Sorties d'évaluation : `report.json`, `summary.csv`, `comparisons.json`,
`coverage.json`, `predictions.parquet`, `outcomes.parquet`, `models/`.
Contrôles finaux : `completion-audit.json`, `nonoverlap-audited-summary.csv`,
`model-reproduction-audit.json`, `final-manifest.json`.

La préparation ne consulte pas les rendements futurs et ne dépense rien.
L'évaluation exige la complétion des embeddings. Aucun changement de batch,
de configuration ou de compte, aucun ordre et aucune écriture SQL de production.
Les contrôles ciblés couvrent plafond, appels ambigus, réponse invalide, cache,
séparation des textes entre splits et chronologie des barrières.

L'audit séparé `scripts.research.us_news_embeddings_audit` sélectionne les dates
sans chevauchement parmi les signaux admissibles à J, **avant** de joindre les
labels futurs. Il ne remplace pas une entrée au parcours manquant par la suivante.
Ses fichiers `nonoverlap-audited-*` et `completion-audit.json` remplacent pour
l'interprétation le premier contrôle construit sur les seules fenêtres qualifiées.
Le bootstrap hebdomadaire reste descriptif : il ne retire pas toutes les
dépendances entre horizons de vingt séances, titres ou événements liés.

Référence documentaire :
[pistes LLM](llm_directionnel_pistes_documentaires_20261102.md).
Tarifs et API consultés :
[modèle](https://developers.openai.com/api/docs/models/text-embedding-3-large),
[contrat embeddings](https://developers.openai.com/api/reference/resources/embeddings/methods/create).
