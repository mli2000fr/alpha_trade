# LLM génériques et direction après Oracle — revue du 2 novembre 2026

Statut : **REVUE DOCUMENTAIRE, AUCUNE EXPÉRIENCE EXÉCUTÉE**.

Demande : identifier sur Internet des usages applicables à Alpha Trade sans
rejouer les expériences déjà consignées. Les propositions ci-dessous sont des
hypothèses de recherche, pas des améliorations directionnelles démontrées chez nous.
Aucun appel LLM payant, entraînement, backtest, ordre ou changement de production.

## Recoupement avec le registre

Lecture des rubriques LLM/news/consensus de [experiences_done.md](experiences_done.md),
recherche transversale des termes embeddings, réseaux économiques, métriques
abandonnées et questions/réponses, puis lecture des protocoles factuels associés.
L'absence d'une expérience équivalente dans ce registre ne prouve pas qu'aucun
autre script du projet ne contient une ébauche similaire.

| Travail déjà consigné | Conclusion pour cette revue |
| --- | --- |
| Avis GPT LONG/SHORT, scores 1–10, confiance, exclusions et comparaisons Winner/directes, notamment août 2026 | Déjà essayé ; pas une nouvelle piste. Les améliorations ponctuelles ne constituent pas une validation indépendante. |
| Sentiment J, J−1/J−2, trajectoires et sortie après news négatives | Déjà essayé ; une autre moyenne de sentiment ne renouvelle pas l'information. |
| Contexte LLM enrichi de consensus, SEC, prix/volume, calendrier | Déjà livré techniquement ; ajouter ces mêmes familles au prompt n'est pas une expérience nouvelle. |
| LLM factuel SEC, 21 octobre | Préparation/revue seulement, sans benchmark LLM ni test économique. Reprendre ce dossier serait une continuation, pas une idée entièrement nouvelle. |
| Nouveauté des annonces, financement et publication financière + réaction du prix | Déjà étudié en faisabilité ; limites historiques de disponibilité et d'identité à conserver. |
| P-MATH-1 : lead-lag cross-asset | Déjà négatif avec un réseau construit à partir des prix. Un réseau fondé sur des relations économiques documentées apporterait une information différente ; il faut néanmoins comparer au contrôle déjà testé. |

Références locales :
[LLM factuel](llm_faits_nouveaux_20261021.md),
[preuves fraîches](llm_preuves_fraiches_20261019.md),
[T1 2025 GPT](news_gpt_top10_t1_2025_resultats_20261014.md),
[P-MATH-1](pmath1_cross_asset_lead_lag.md).
Le prompt de production `service/llm_directional/prompts.py` reste une évaluation
de tendance et de qualité des preuves ; le protocole factuel de recherche est
séparé dans `scripts/research/us_llm_factual_readiness.py`.

## 1. Représentation du texte et petit modèle directionnel — priorité proposée

**Source primaire :** Chen, Kelly et Xiu, *Expected Returns and Large Language
Models*, version signalée février 2026 :
[SSRN](https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=4416687),
[page de l'auteur](https://dachxiu.chicagobooth.edu/).

Les auteurs utilisent des représentations numériques des news produites par des
modèles de langage, dont ChatGPT et LLaMA. Ils rapportent une information
incrémentale sur les rendements et des résultats après coûts. L'effet décrit
est court : plusieurs jours sur petites valeurs, plus rapide sur grandes.
Le résumé indique aussi un intérêt des textes complets et résumés structurés.
Abstract et pages d'auteurs consultés ; pas de réplication du papier effectuée.
Cela ne valide ni notre univers Oracle ni nos barrières.

**Adaptation proposée, distincte des scores de sentiment déjà testés :**

- Figer un encodeur de texte générique. Il transforme chaque article en un
  ensemble de nombres décrivant son contenu ; ce ne sont pas des probabilités.
- Comparer une représentation directe de l'article à un petit ensemble de faits
  extraits, si le premier essai justifie cette deuxième branche.
- Apprendre un modèle simple et régularisé sur ces représentations, avec les
  issues réellement observées dans notre population Oracle. Le LLM reste figé.
- Conserver le même article une seule fois ; réutiliser son résultat pour les
  dates/titres autorisés, sans confondre ses différents émetteurs.

Exemple hypothétique : « revenus en hausse mais guidance abaissée » et « revenus
en hausse avec carnet de commandes renforcé » peuvent avoir le même sentiment
global ; leurs contenus peuvent être séparés par la représentation du texte.
Il reste à démontrer que cette différence aide à prévoir le parcours futur.

Gate préalable : compter les textes intégraux, versions, dates de réception et
séances Oracle exploitables. Nous n'avons pas vérifié aujourd'hui leur couverture
en base. Les études antérieures signalent des imports tardifs et des textes non
versionnés ; une représentation numérique ne répare pas ces limites.

## 2. Indicateurs mis en avant puis abandonnés — nouvelle mesure, socle voisin

**Source primaire :** Choi et al., *From Text to Alpha: Can LLMs Track Evolving
Signals in Corporate Disclosures?*,
[version 5 du 15 mars 2026](https://arxiv.org/html/2510.03195v5).

Ce préprint utilise Gemini-2.5-Pro pour extraire des métriques, puis un encodeur
pour comparer les mêmes trimestres à un an d'intervalle. Il étudie 5 615
observations société/trimestre du S&P 100 entre 2010 et 2024. Le portefeuille
montre une association favorable au maintien des métriques ; les tests portent
sur des rendements mensuels. Les seuils ont été balayés et le coefficient de
régression présenté n'est pas significatif à 5 % : les résultats ne sont pas
uniformément concluants. Aucun taux de réussite H20 ne peut en être déduit.

**Adaptation hypothétique :** vérifier si une entreprise cesse de commenter un
indicateur économique qu'elle mettait auparavant en avant : ventes comparables,
commandes, rétention clients, marge d'un segment. Un changement de présentation,
de périmètre ou une source tronquée doit rester distinct d'un véritable abandon.

Cette mesure précise n'a pas été trouvée dans le registre. Elle prolonge toutefois
le dossier factuel SEC déjà préparé. Le papier s'appuie sur les conférences de
résultats ; utiliser seulement des communiqués/annexes SEC serait une adaptation
à valider, pas une reproduction. Deux documents comparables sont indispensables.

## 3. Relations économiques entre sociétés — piste nouvelle, plus coûteuse en données

**Source primaire :** Huang et al., *Cross-Stock Predictability via LLM-Augmented
Semantic Networks*,
[préprint v2, avril 2026](https://arxiv.org/html/2604.19476v2).

Les auteurs emploient DeepSeek-Chat pour classer des liens entre entreprises
à partir d'extraits de 10-K. Ils distinguent notamment concurrence, chaîne
d'approvisionnement et complémentarité. Le filtrage améliore leur backtest
S&P 500 2011–2019. Il s'agit d'un dispositif de retour à la moyenne, avec
détention de référence de deux mois, pas d'un test de news Oracle H20. Les
limites de mémoire du LLM et de textes tronqués restent pertinentes.

**Adaptation proposée :** pour une action du TOP20, rechercher les faits nouveaux
concernant ses clients/fournisseurs réellement documentés, en gardant l'identité,
la nature et la date de validité de chaque relation. Une annonce de commande
chez un client peut constituer un contexte différent d'une simple mention du
ticker. L'effet fournisseur, client ou concurrent ne doit jamais être déduit
automatiquement du signe de la news.

La propagation de news est notre hypothèse ; ce n'est pas l'expérience du papier.
Contrôles nécessaires : relations connues à J seulement, comparaison au secteur
et au réseau de prix de P-MATH-1, liens non vérifiables laissés inconnus.

## 4. Questions des analystes et réponses des dirigeants — à réserver

**Source primaire professionnelle :** S&P Global, *Questioning the Answers:
LLMs enter the Boardroom*, janvier 2025,
[rapport](https://www.spglobal.com/content/dam/spglobal/global-assets/en/documents/general/QuestioningTheAnswers_GoLive.pdf).

Sur 192 000 conférences, le rapport combine représentations de textes et
réponses synthétisées pour mesurer l'alignement des réponses et l'anticipation
des questions. Il rapporte des écarts de portefeuille favorables aux dirigeants
plus directs/proactifs. Le classement est mensuel avec quatre mois de contexte ;
les frais sont exclus. Le taux de réussite de portefeuille n'est pas celui des
trades individuels. C'est une étude du fournisseur, pas une validation chez nous.

**Adaptation envisagée :** relever les questions sur les commandes, marges,
financement et demande auxquelles la direction apporte ou non un élément concret,
avec les citations et les éventuels changements de discours. Une réponse hors
sujet ne prouve ni mensonge ni future baisse.

Pas d'expérience équivalente repérée dans le registre. La disponibilité et les
droits sur les transcriptions historiques restent à qualifier ; les news et les
tableaux de consensus ne les remplacent pas. Priorité moindre tant que cette
source n'est pas disponible de façon fiable.

## Sources à ne pas surinterpréter

- [Lopez-Lira et Tang, Journal of Financial Economics, octobre 2026](https://www.sciencedirect.com/science/article/pii/S0304405X26001066) :
  environ 90 % concerne la réaction initiale non négociable, au niveau des
  portefeuilles/jours. Ce n'est pas 90 % de trades gagnants ni une performance
  sur vingt séances. La piste avis sur titres de news recoupe nos essais.
- [Financial Statement Analysis with Large Language Models](https://arxiv.org/abs/2407.17866)
  a été retiré en février 2025 pour incohérences de données et d'analyses.
  Ne pas invoquer ses performances initialement annoncées comme preuve.
- [The Price of Thought](https://arxiv.org/abs/2609.30705), préprint septembre
  2026 : augmenter l'effort de raisonnement n'améliore pas régulièrement les
  rendements nets dans l'étude. Ce n'est pas une justification pour multiplier
  d'emblée les agents, raisonnements longs ou appels coûteux.

## Premier protocole envisageable, non lancé

1. Commencer par un inventaire en lecture seule de la couverture documentaire et
   des scores Oracle causaux, avant toute dépense. Évaluer l'extraction séparément
   de son utilité financière : exactitude sur des faits ne signifie pas alpha.
2. TOP20 Oracle primaire, fixé avant les résultats ; TOP10/TOP50 secondaires.
   Respecter les vrais rangs à la date de décision. Un effet sur un vaste univers
   ne garantit pas un effet dans cette population conditionnelle.
3. Choisir avant l'essai un horizon primaire parmi H5/H10/H20. Pour chaque horizon,
   conserver les deux excursions signées, leurs dates et l'ordre des passages aux
   barrières. Un maximum positif postérieur au stop n'est pas un succès LONG
   négociable. Une bougie touchant les deux barrières sans chronologie suffisante
   reste ambiguë ou suit la convention conservatrice figée du replay.
4. Comparer d'abord mêmes dates et mêmes preuves disponibles : modèle de base
   sans texte, ajout du sentiment existant, ajout de la représentation textuelle.
   Le prix de référence doit être une entrée possible après disponibilité du
   signal et délais réels, pas le prix avant publication.
5. Normalisation/réduction de dimension et réglages appris sur train uniquement ;
   validation chronologique purgée des horizons qui se chevauchent. Regrouper les
   répétitions d'un même événement et tenir compte des dépendances titre/date.
6. Une consigne « comme si nous étions en 2025 » ne retire pas les connaissances
   futures d'un LLM actuel. Masquer les noms atténue certains risques sans
   certifier l'absence de fuite. Exiger un modèle antérieur au test lorsque
   possible ; sinon résultat rétrospectif exploratoire, puis gel prospectif.
   Nos années déjà beaucoup examinées ne constituent plus un test vierge.
7. Mesurer précision LONG, calibration, abstention/couverture et performance
   incrémentale ; ensuite seulement comparer Winner seul à Winner + filtre,
   mêmes protections/capital/frais. Les coûts d'API s'ajoutent aux coûts de trade.
8. Garder la qualité manquante séparée d'une opinion neutre. Aucun changement de
   production justifié par les seules publications externes.

Décision proposée : **qualifier les données pour la piste 1 en premier**, garder
la piste 2 comme prolongement ciblé du socle factuel, puis considérer les pistes
3 et 4 selon la couverture des sources. Cette note n'est pas une nouvelle entrée
de résultat dans `experiences_done.md`.
