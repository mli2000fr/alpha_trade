# Sprint 15-D4 — Contrat temporel et couverture Dragon/Tiger × Oracle

Audit du 30 septembre 2026. **Verdict : couverture suffisante pour un examen exploratoire, mais archive non certifiée PIT et aucun GO ML.** Aucun modèle, table, batch, backtest ou serving modifié.

## Question et périmètre

Avant de tester la direction, quelle part des décisions Oracle CN H20 TOP20 possède un événement Dragon/Tiger déjà connu ? Les quatre semestres OOF 2024H1–2025H2 proviennent du Sprint 10-B, LightGBM H20. Le TOP20 est calculé chaque date sur tout l'univers valide, avant jointure aux événements. Le warm-up débute au 01/11/2023 pour ne pas censurer les fenêtres de 20 séances de début 2024.

L'archive Eastmoney RPT_DAILYBILLBOARD_DETAILSNEW a été réconciliée par identité date–marché–titre aux sources officielles SSE/SZSE sur 16 séances en [15-D3](./sprint_15d3_robustesse_historique_dragon_tiger.md). Ici, cinq périodes sont paginées et vérifiées contre le compteur annoncé ; chaque réponse est empreintée SHA-256. Les payloads bruts ne sont pas conservés. Seuls date, code, marché et motif autorisés passent le filtre ; rendements futurs D1–D30 et texte de succès rétrospectif sont exclus avant analyse. Les avis de financement qui ne relèvent pas de Dragon/Tiger sont également exclus. Plusieurs motifs pour un titre et une date représentent un seul événement.

## Contrat de temps et d'identité

- Événement de séance J : **interdit pour une décision J**.
- Proxy optimiste : premier accès à la décision de la prochaine séance ouverte, J+1.
- Stress prudent : premier accès à J+2.
- Couverture fraîche : dernier événement disponible âgé de 1–5 ou 1–20 séances pour J+1, 2–5 ou 2–20 pour J+2. Les séances sont celles du calendrier CN_A, non des jours calendaires.
- Le code de marché est résolu via le mapping BaoStock sh./sz. et les bornes historiques valid_from/valid_to à la **date de l'événement**, avec instrument_type equity. Une ambiguïté fait échouer l'audit ; les absences sont comptées.

**J+1 n'affirme pas que toutes les lignes étaient diffusées avant l'ouverture de J+1.** L'heure de publication historique et les corrections ligne par ligne restent inconnues. J+2 est une sensibilité, pas une certification. Les empreintes prouvent ce qui a été reçu aujourd'hui, pas la vintage originelle.

## Résultats

Les périodes contiennent 44 172 lignes annoncées par le fournisseur, dont 3 137 de warm-up. Après assainissement et dédoublonnage : **32 469 événements titre–séance actions A, tous résolus par mapping historique**. Le dénominateur Oracle est **464 834 observations titre–séance OOF**.

| Accès | Couverture ≤ 5 séances | Part TOP20 | Couverture ≤ 20 séances | Part TOP20 |
| --- | ---: | ---: | ---: | ---: |
| J+1 | 67 101 | 14,435 % | 160 916 | 34,618 % |
| J+2 | 56 423 | 12,138 % | 153 154 | 32,948 % |

| Semestre | TOP20 | ≤ 5 J+1 | ≤ 5 J+2 | ≤ 20 J+1 | ≤ 20 J+2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024H1 | 117 162 | 13,633 % | 11,476 % | 32,025 % | 30,492 % |
| 2024H2 | 125 221 | 15,330 % | 13,027 % | 37,561 % | 35,881 % |
| 2025H1 | 116 793 | 14,333 % | 12,020 % | 34,095 % | 32,415 % |
| 2025H2 | 105 658 | 14,378 % | 11,950 % | 34,584 % | 32,786 % |

La fenêtre 20 séances couvre davantage mais peut porter un événement déjà ancien. Les mêmes titres répétés à plusieurs décisions sont comptés plusieurs fois : ces nombres ne sont ni des trades indépendants, ni une taille d'échantillon statistique indépendante. La couverture n'est pas une métrique de précision D1/D10.

## Gate suivant

**15-D4 = GO_COVERAGE_RESEARCH_PROXY, NO_GO_PIT_CERTIFIED, NO_GO_ML_OR_PRODUCTION.** Pour un éventuel 15-D5, vérifier d'abord les droits et limites de l'API, collecter prospectivement les heures de diffusion/corrections, qualifier les motifs et montants de sièges ainsi que leurs unités. Puis pré-enregistrer une comparaison appariée sur les mêmes décisions Oracle, contrôlant le mouvement déjà réalisé en J, avec D1-veto, LONG/SHORT, abstention, coûts et semestres OOF séparés. En l'absence de ces gates, conserver les événements comme données descriptives.

Reproduction : [code](../../service/market/cn_dragon_tiger_coverage_15d4.py), [tests](../../tests/test_cn_dragon_tiger_coverage_15d4.py), [rapport machine](../../artifacts/research/cn_dragon_tiger_15d4/coverage-20260930/report.json). Le code lit la base sans écrire et refuse d'écraser un dossier de résultat non vide.
