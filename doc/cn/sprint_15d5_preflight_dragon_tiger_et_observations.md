# Sprint 15-D5 — Préflight directionnel Dragon/Tiger et observation prospective

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Audit exécuté le 30 septembre 2026. **Verdict : NO_GO pour entraînement/backtest/serving historique ; GO pour constituer un journal prospectif de recherche des publications officielles.** Aucun modèle, table, batch planifié, portefeuille ou serving n'a été modifié.

## Pourquoi ne pas lancer immédiatement une ablation

Le [Sprint 15-D4](./sprint_15d4_contrat_temporel_couverture_dragon_tiger.md) mesure la couverture Oracle TOP20 de l'archive Dragon/Tiger, mais son rapport ne conserve que des agrégats. Il ne permet donc pas d'apparier chaque candidat événementiel à un témoin du **même jour, du même board, du même score Oracle et du même mouvement de prix déjà observé**. Sans cet appariement, on peut confondre une information directionnelle avec les critères réglementaires qui ont fait publier le titre après sa séance anormale. Les quatre semestres OOF ne disposent pas non plus, dans le rapport D4, d'un croisement simultané semestre × décile × événement pour vérifier la stabilité du signe.

La consultation des [conditions publiques d'Eastmoney](https://about.eastmoney.com/home/protocol) ne fournit pas une autorisation claire pour conserver/réutiliser l'archive comme jeu d'entraînement ou produit dérivé. Ce constat n'est pas un avis juridique ; il impose une clarification des droits avant une campagne ML sur cette source. Les [pages de publication SSE](https://www.sse.com.cn/disclosure/diclosure/public/inquirydata/index.shtml) et [SZSE](https://www.szse.cn/disclosure/deal/public/index.html) montrent les événements datés, mais les réponses inspectées ne prouvent pas l'heure historique de première diffusion ni les corrections telles que visibles à l'époque. Les proxys J+1/J+2 demeurent des sensibilités, pas des vintages PIT.

## Signal brut déjà observable — non exploitable tel quel

Le protocole de lecture a été fixé avant le calcul : **primaire = J+2, événement âgé au plus de cinq séances** ; J+1 et fenêtre 20 séances sont descriptifs. En lisant uniquement les comptes D4 :

| Population Oracle TOP20 H20 | D1 | D10 | Part D1 parmi D1+D10 |
| --- | ---: | ---: | ---: |
| Événement J+2 ≤ 5 séances | 19 526 | 7 704 | 71,71 % |
| Aucun événement dans cette fenêtre | 89 769 | 56 928 | 61,19 % |

Une liste récente accompagne donc davantage de futurs D1 que de D10 dans cette **comparaison brute**. Ce n'est pas la précision d'un veto : les groupes ne sont pas appariés, les dates/titres répétés ne sont pas indépendants, et le mouvement de la séance déclenchant la publication n'est pas contrôlé. Le rapport machine calcule aussi J+1 et la fenêtre 20, sans sélectionner a posteriori le meilleur résultat. Aucune simulation de rendement ou de coût n'a été réalisée.

Le préflight échoue volontairement fermé si le rapport D4 inclut un événement du même jour ou un mapping historique non résolu. Il inscrit explicitement droits, heure de publication, corrections et analyse appariée comme **non qualifiés**.

## Journal prospectif officiel de recherche

Un [collecteur manuel de recherche](../../service/market/cn_dragon_tiger_prospective_15d5.py) lit les listes SSE principal + STAR et SZSE pour une séance demandée. Chaque passage écrit un **nouveau snapshot**, sans écraser les précédents, avec heure UTC effectivement observée, empreintes des réponses officielles, identité date/bourse/code/motif, et empreinte des champs de la ligne. Le journal compare le dernier passage pour compter premières observations, retraits et changements de payload. Il ne persiste ni nom de siège, ni montant, ni rendement futur ; il n'écrit pas en base et n'est pas planifié.

L'heure observée prouve seulement que **notre système a vu la réponse à cette heure**, pas que la bourse l'a publiée à cet instant. Les passages portant sur une date antérieure au jour courant chinois sont marqués retrospective=true et pit_usable=false. Même les observations du jour restent pit_usable=false jusqu'à vérification des droits, de la complétude, du délai de diffusion et du contrat de décision pré-ouverture. La première apparition dans le journal n'est pas inférée d'une date de transaction.

Smoke réel sur la séance du 02/09/2025 : **76 lignes de motifs officiels** reçues et enregistrées, observation le 29/09/2026 22:25 UTC, correctement marquée **rétrospective et non PIT**. Ce nombre de motifs ne doit pas être lu comme 76 titres uniques. Aucun passage du jour courant ni programmation quotidienne n'a été activé.

Commande manuelle pour une future séance, après clôture CN : python -m service.market.cn_dragon_tiger_prospective_15d5 --date AAAA-MM-JJ. Une seconde exécution le même jour crée un snapshot distinct et révèle corrections ou retards ; elle ne modifie pas le premier.

## Gate 15-D6 éventuel

Avant tout entraînement : (1) clarifier les droits d'utilisation de la source choisie ; (2) construire une série prospective suffisante avec heures de première observation, retards et corrections mesurés ; (3) certifier la disponibilité **avant la décision** ; (4) pré-enregistrer une analyse appariée par date, board, score Oracle et rendement antérieur, avec décisions J+1 et J+2 séparées ; (5) vérifier LONG/D10 et veto D1 sur chaque semestre, avec abstention, coûts, contrôle des titres/dates répétés et intervalle par blocs temporels. Si ces conditions ne sont pas remplies, Dragon/Tiger reste une donnée descriptive.

Reproduction : [préflight](../../modelFactory/cn_dragon_tiger_preflight_15d5.py), [rapport calculé](../../artifacts/research/cn_dragon_tiger_15d5/preflight-20260930-v2/report.json), [tests](../../tests/test_cn_dragon_tiger_15d5.py), [smoke officiel](../../artifacts/research/cn_dragon_tiger_15d5/observations-smoke/2025-09-02/). Le premier essai de préflight a écrit un rapport identique puis a échoué seulement sur l'affichage d'une clé ; la version v2, relancée dans un dossier neuf, est la référence.
