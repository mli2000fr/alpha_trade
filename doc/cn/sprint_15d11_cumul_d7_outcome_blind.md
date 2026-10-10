# Sprint 15-D11 — Cumul prospectif D7, sans connaissance des issues

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Le [journal D10](./sprint_15d10_appariement_d7_quotidien.md) produit un appariement indépendant par séance de décision. D11 additionne ces seules séances pour savoir **si le protocole D7 dispose enfin d'un échantillon exploitable**. Il ne lit jamais les rendements futurs, les déciles D1/D10, les labels, les ordres ou les résultats de backtest.

## Entrées admises

- Export Oracle D8 prospectif de chaque séance, dont l'empreinte et l'heure de publication sont contrôlées ; un export encore avant son cutoff n'entre pas dans le cumul.
- Rapport D7 et paires D10 de la même séance, avec le protocole et les candidats figés. Les empreintes du journal de passage D10 doivent correspondre aux deux fichiers. Un dossier incomplet, modifié, doublonné ou avec une colonne d'issue future bloque le cumul.
- Chaque export Oracle dont le cutoff est passé doit avoir un appariement quotidien ; sinon `missing_daily_matches` le signale et le statut devient `INCOMPLETE_PROSPECTIVE_JOURNAL`. Un échec du collecteur officiel ne devient jamais une absence d'événement.

Le rapport totalise les séances, candidats, exposés Dragon/Tiger, exposés appariés et paires. L'équilibre est recalculé sur **toutes les paires effectivement produites**, et non comme moyenne trompeuse des équilibrages journaliers. Les seuils sont chargés de [sprint15d7_dragon_tiger_protocol.yaml](../../config/research_cn/sprint15d7_dragon_tiger_protocol.yaml) : au moins 60 séances, 200 exposés, 80 % d'exposés appariés, deux trimestres calendaires et différences standardisées absolues au plus 0,10 pour le rang Oracle et le rendement préalable. Chaque gate est affiché séparément ; le statut de disponibilité n'est pas une preuve de signal directionnel.

Commande reproductible ; choisir un **nouveau nom de sortie** à chaque contrôle, car un rapport existant n'est jamais écrasé :

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_dragon_tiger_cumulative_15d11 --output artifacts/research/cn_dragon_tiger_15d11/readiness-AAAAMMJJ.json
```

Le [premier contrôle réel du 30 septembre](../../artifacts/research/cn_dragon_tiger_15d11/readiness-20260930.json) retourne `WAITING_FOR_FIRST_PROSPECTIVE_MATCH`, zéro séance et zéro lacune : l'export du 8 octobre est bien publié, mais sa décision n'a pas encore eu lieu. C'est attendu. Le 8 octobre après 09:15 Shanghai, D10 pourra produire la première séance ; D11 signalera ensuite explicitement si cette séance manque. Le contrôle des issues H20, les intervalles de confiance et toute conclusion D1/D10 restent une étape **ultérieure**, après maturité et satisfaction des gates.
