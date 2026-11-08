# GPT contre Qwen — même prompt, mêmes dossiers, filtre B sur 2025

Lancement utilisateur le 7 novembre 2026 après proposition d'un plafond **2 USD**
pour B. **Test C exclu** : ses 44 750 dossiers potentiels ne sont pas autorisés
dans cette enveloppe. Le test A est la référence Winner commune.

## Comparaison figée

- Référence `20261107_095041_0b38b8de`, Oracle H10
  `model-factory-20261106203103-91b063`, année2025, TOP10 % → TOP10 LONG,
  probabilité >0,70 et AUC calibration ≥0,60.
- 204 candidatures/24 sociétés : **166 dossiers avec news**, 38 sans news
  conservés sans appel. Le corpus est celui de la campagne Qwen
  `artifacts/research/us_local_llm_winner_ab/20261107-v7`.
- Instructions système et texte utilisateur **copiés exactement**, avec contrôle
  d'égalité pour chaque requête. Aucun nouveau texte, cours, consensus ou appel Web.
  Même schéma JSON, même validation des citations et même règle de veto.
- Même comptabilité et risque, capital4 000 USD, exposition autorisée2×, entrée
  directe J+1 sans confirmation, fraction initiale1, SL5 %, sans TP/trailing,
  horizon10/open11, frais8bps par opération et financement6,5 % annuels.

Le modèle GPT est `gpt-6-luna`, via Responses API. Runtime figé : raisonnement
`medium`, plafond16 384 tokens, délai600s, service `default`, `store=false`,
aucun outil. La température n'est pas envoyée ; Qwen conserve son runtime local.
**Même prompt ne signifie pas même échantillonnage ou même calcul de raisonnement.**
Il s'agit d'une comparaison des deux systèmes, sans promettre d'isoler le seul
effet des poids du modèle.

## Prompt et archives

Copie cloud indépendante, explicitement identique pour cette expérience :
`config/ia/prompt/cloud/oracle_directional/v1/research_veto_comparison.txt`,
catalogue `cloud.oracle_directional.v1.research_veto_comparison`.
Le prompt Qwen local et les prompts cloud de production restent distincts dans
le catalogue. Aucun remplacement du filtre de production.

Dossier GPT : `artifacts/research/us_gpt_winner_ab/20261107-v1`.
`protocol.json` contient les empreintes, les 166 réservations et l'autorisation.
`api/` conserve requêtes exactes, réponses brutes, durées et éventuelles erreurs.
`analyses.sqlite3`, table `attempts`, conserve aussi les réponses normalisées,
leur validation, les citations, raisons et consommation. Clés de cache propres
à OpenAI : une réponse Qwen n'est jamais réutilisée comme réponse GPT.

Une requête est journalisée **avant** tout appel potentiellement facturable.
Pas de répétition automatique après timeout/erreur. Une reprise avec réponse
déjà reçue réutilise le reçu, sans nouvel appel. Une tentative au statut ambigu
reste bloquée avant toute nouvelle facturation pour ce dossier.

## Plafond de dépense

Tarifs standard vérifiés le7 novembre : entrée0,10 USD/million et sortie0,50 USD/
million, raisonnement compris. Pour borner la dépense avant lancement, réservation
plus conservatrice à0,125 USD/million d'entrée (écriture du cache), nombre d'octets
du corps plus4 096 tokens de marge et plafond de sortie complet.

Réservation totale maximale : **1,788514875 USD**, inférieure à **2 USD**.
La vérification précède le premier appel et est répétée à la reprise. Niveau de
service `default` explicite, pas de Fast ni recherche Web. Les coûts publiés
restent des estimations à partir des consommations API, hors taxes, conversion
monétaire et autres appels éventuels du compte. La clé API n'est jamais archivée.

Références officielles : [GPT-6 Luna et tarifs](https://developers.openai.com/api/docs/models/gpt-6-luna),
[tokens de raisonnement et facturation](https://developers.openai.com/api/docs/guides/reasoning),
[sorties structurées](https://developers.openai.com/api/docs/guides/structured-outputs).

## Suivi, replays et restitution

Lancement : `scripts/research/us_gpt_winner_ab.py`, phase `run`, même dossier
préparé. Le programme ne lance les replays A et B_GPT que si chaque dossier est
valide ou explicitement sans news. Le témoin A doit reproduire son capital,
rendement, DD, trades, coûts, financement et exposition avant de publier B.
Une réponse de direction n'est pas, par elle-même, un résultat économique.

`progress.json` : titre/date en cours, appels, coût estimé et avancement du replay.
`analysis-report.json` : validité, vetoes, consommation et budget.
`replay/comparison.csv` : résultats A/B GPT, si la qualification permet le replay.

Le suivi `scripts/research/us_gpt_qwen_comparison_followup.py` ne fait aucun appel
API et ne relance aucun job. Il actualise les reçus comparatifs pendant les deux
campagnes, puis se termine à leurs bilans terminaux :

- `gpt-vs-qwen.csv` : par titre/date, avis, veto et statut de chaque modèle ;
- `gpt-vs-qwen-report.json` : couverture, erreurs et accords sur l'intersection
  **valide avec news**, sans gonfler l'accord par les 38 absences de news ;
- `comparison-followup.json` : état des campagnes et disponibilité des replays.

Les taux d'accord ne sont pas des taux de réussite directionnelle. Une comparaison
sur l'intersection valide peut être biaisée par les dossiers rejetés : les deux
couvertures et leurs erreurs sont affichées séparément. Si Qwen reste incomplet,
ne pas présenter une comparaison économique complète GPT/Qwen.

Validation technique préalable : **71 tests passent**, dont identité des textes,
plafond global vérifié avant appel, refus de changement de modèle/niveau/outils,
cache sans double facturation et blocage des tentatives ambiguës.
Au démarrage, les quatorze premiers appels GPT ont produit des réponses valides.
Ce constat technique n'établit pas l'utilité prédictive du filtre.

## Incident et reprise autorisée — 7 novembre, 22 h 03 Paris

Arrêt initial à21 h02 sur `ConnectionError` pour VAC, signal du21 novembre2025 :
155 réponses reçues (144 valides, onze invalides), onze dossiers restant sans reçu.
La requête VAC était journalisée mais sans réponse ni identifiant récupérable.
Une tentative interrompue ne prouve pas l'absence de facturation.

Sur instruction utilisateur « Reprend test gpt », lancement de
`scripts/research/us_gpt_winner_resume.py`. Une nouvelle tentative VAC seulement,
puis les dix requêtes initiales non encore envoyées. Les155 réponses reçues ne
sont pas rachetées ; les invalides reçues restent conservées sans répétition.
Le journal et l'erreur VAC d'origine sont préservés ; le nouveau reçu est ajouté
uniquement dans l'emplacement auparavant absent. Ancien bilan et progression
archivés dans `resume-attempts/20261107T210335Z-075914ec/`.

Réservation additionnelle maximale de la nouvelle tentative : **0,011681375 USD**,
soit une réserve totale de **1,800196250 USD**, toujours sous2 USD, en comptant
conservativement les deux tentatives VAC possibles. Pas de changement de prompt,
modèle, sélection, validation ou comptabilité. Onze tests de reprise/transport
passent. VAC a produit un reçu valide à la reprise. Les coûts du reçu perdu
restent inconnus et ne sont pas supposés nuls.

`resume-attempts/.../authorization.json`, `recovery-report.json` et
`final-report.json` détaillent la reprise. Le protocole initial reste immuable.
Une nouvelle erreur n'est pas répétée automatiquement ; les replays demeurent
conditionnés à la qualification complète des réponses.

### Bilan de la reprise — 22 h 05 Paris

Rattrapage terminé : les onze reçus manquants sont récupérés, sans répéter les
155 réponses déjà reçues. Les 166 dossiers avec news disposent désormais d'une
réponse : **155 valides et onze invalides**. Avec les 38 dossiers sans news
conservés, 193/204 dossiers sont qualifiés ; 34 vetoes sont validés.
Coût standard estimé des reçus : **0,1606705 USD**, estimation conservatrice
**0,176604375 USD**, hors coût inconnu de la première tentative VAC interrompue.
Cette tentative reste couverte par la réservation globale de1,800196250 USD.

Statut final : `INCOMPLETE_ANALYSIS_NO_REPLAY`. Les onze erreurs de validation
restantes empêchent les replays économiques A/B ; aucune performance ni
supériorité GPT/Qwen ne peut être publiée. Les réponses et erreurs sont
conservées pour diagnostic, sans nouvel appel automatique. Qwen est encore en
cours à ce bilan ; les accords disponibles sont partiels.

## Limites historiques

Les textes sont les versions actuellement archivées, pas un historique de toutes
les versions réellement disponibles à chaque décision2025. La mémoire du modèle
peut contenir des événements2025. Les réserves de survivorship, métadonnées
actuelles et couverture OHLC quotidienne/5m restent celles de la référence.
**Étude rétrospective exploratoire, pas une certification PIT ni un avantage
validé hors échantillon.** Aucun entraînement ou ordre broker dans cette campagne.
