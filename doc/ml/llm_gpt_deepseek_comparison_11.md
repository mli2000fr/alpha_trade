# Comparaison GPT / DeepSeek sur les 11 titres déjà analysés

## Protocole borné — 11 octobre 2026

Demande utilisateur : tester les deux fournisseurs sur les mêmes 11 titres.
Sources : run parent `llm-bc155d0d71484217b0bdc98cd9e06c7d`, séance signal
**9 octobre 2026**, et nouvelle recherche prospective durant le week-end,
avant l'ouverture de la séance US suivante. Pas de reconstruction Web historique.

Titres : SSTK, FICO, PENG, QFIN, FMC, ICHR, CWH, ABR, CLS, APP, HUBG.
Le sous-ensemble est choisi après observation du premier run : ce n'est pas
une validation hors échantillon et il ne représente pas l'ensemble du TOP100.

- Même contexte archivé : identité locale, prix, score/rang Oracle, horizon H20.
- Même seuil de confiance subjective 0,75, deux sources récentes distinctes,
  âge maximal 30 jours, LONG/SHORT/ABSTAIN autorisés.
- Paramètres du parent conservés : plafond cinq retenus ; le plafond actuel
  de trois de l'IHM n'est pas appliqué rétroactivement à ce diagnostic.
- GPT `gpt-6-luna` : une recherche Web + analyse par titre.
- DeepSeek `deepseek-flash` : une analyse par titre sur la **même réponse Web**,
  sans nouvelle recherche payante implicite. Au plus 22 générations.
- Accès aux deux modèles confirmé par métadonnées HTTP 200 avant les appels.
- Aucun retry automatique, aucune modification des seuils après observation.

**Limite essentielle :** DeepSeek voit les traces et la synthèse Web produites
par GPT, incluant son avis préliminaire. Il ne lit pas indépendamment l'ensemble
des articles. Une concordance ne prouve donc pas deux confirmations indépendantes.
Une confiance plus élevée n'est pas un meilleur taux de réussite : les notes
des deux modèles ne sont pas des probabilités calibrées comparables.

## Archivage et suivi

Module : `service/llm_directional/provider_comparison.py`.
Répertoire : `artifacts/research/llm_directional/provider-11-20261011-v1`.

- `protocol.json` : configuration et entrées parent figées ;
- `progress.json` et `run.log` : progression ;
- `gpt_report.json`, `deepseek_report.json` : rapports séparés ;
- `report.json` : décisions, confiance, sources, exclusions, éligibilité et accord.

Nouveaux runs : `llm-research-provider-11-20261011-v1-gpt` et
`llm-research-provider-11-20261011-v1-deepseek`. Requêtes/réponses archivées dans
les tables LLM US habituelles, avec `research_only=true` et lien parent.
Le moteur refuse leur passage au risque/exécution. Les anciens runs ne sont
pas modifiés ; aucune prédiction Oracle, aucun ordre et aucun batch lancé.

Le compteur de progression correspond aux tentatives d'analyse terminées, pas
à une certification du nombre d'appels facturés. Une preuve GPT manquante bloque
le titre DeepSeek correspondant, sans lancer une nouvelle recherche.

Ne pas relancer le même test automatiquement. Le répertoire existant refuse
un second lancement payant. Une nouvelle génération exige une demande distincte.

## Résultat

Test terminé le 11 octobre, de **00:31:32 à 00:38:48 Paris** (7 min 16 s).
Les 22 tentatives ont été effectuées, sans relance et sans nouvelle recherche
Web pour la branche DeepSeek. Configuration IHM laissée sur GPT, inchangée.

| Fournisseur | Réponses valides | LONG brut | SHORT brut | ABSTAIN | Erreurs | Éligibles / retenus |
|---|---:|---:|---:|---:|---:|---:|
| GPT gpt-6-luna | 11 | 1 | 3 | 7 | 0 | 0 / 0 |
| DeepSeek deepseek-flash | 9 | 0 | 1 | 8 | 2 | 0 / 0 |

| Titre | GPT : avis / confiance subjective | DeepSeek : avis / confiance subjective |
|---|---|---|
| SSTK | ABSTAIN / 0,62 | ABSTAIN / 0,60 |
| FICO | ABSTAIN / 0,74 | Erreur : réponse tronquée |
| PENG | LONG / 0,66 | ABSTAIN / 0,50 |
| QFIN | SHORT / 0,63 | SHORT / 0,55 |
| FMC | SHORT / 0,65 | Erreur : réponse tronquée |
| ICHR | ABSTAIN / 0,72 | ABSTAIN / 0,65 |
| CWH | ABSTAIN / 0,78 | ABSTAIN / 0,62 |
| ABR | SHORT / 0,67 | ABSTAIN / 0,50 |
| CLS | ABSTAIN / 0,79 | ABSTAIN / 0,60 |
| APP | ABSTAIN / 0,82 | ABSTAIN / 0,68 |
| HUBG | ABSTAIN / 0,72 | ABSTAIN / 0,70 |

Sept des neuf paires valides sont concordantes ; PENG et ABR passent d'un avis
directionnel GPT à ABSTAIN DeepSeek. FICO/FMC ne sont pas inclus dans ce
dénominateur : une erreur technique n'est pas une abstention.
Tous les avis LONG/SHORT valides restent sous 0,75. Les avis ABSTAIN au-dessus
de 0,75 expriment une confiance dans l'abstention, pas une hausse/baisse.
Les rapports détaillent séparément les sources insuffisantes ou exclues.

### Deux erreurs DeepSeek : budget partagé avec le raisonnement

Les RAW confirment `finish_reason=length` et exactement 6 000 tokens de
complétion pour FICO et FMC. Dont **5 703 tokens de raisonnement pour FICO** et
**5 184 pour FMC** : le JSON final a été tronqué. Ce n'est pas une erreur de clé
API ni une décision directionnelle négative. Les réponses sont archivées et
refusées, jamais complétées artificiellement.

GPT : run COMPLETED. DeepSeek : run FAILED car deux réponses invalides ;
comparaison globale **PARTIAL_FAILED**. Aucun candidat publié et aucun lien
risque/exécution créé. Le hash du snapshot parent reste inchangé.

Conclusion : le transport réel et l'archivage DeepSeek fonctionnent, mais son
budget de raisonnement/sortie nécessite une qualification technique avant usage
opérationnel. Ce petit diagnostic ne démontre aucun avantage D1/D10 de l'un ou
de l'autre. Une éventuelle reprise limitée aux deux erreurs, avec budget explicite,
exige une nouvelle autorisation ; elle ne doit pas être mélangée au protocole initial.
