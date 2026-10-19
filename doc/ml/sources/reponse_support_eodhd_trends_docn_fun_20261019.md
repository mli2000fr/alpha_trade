# Réponse EODHD — Trends DOCN / FUN

Provenance : texte de réponse du support transmis par l'utilisateur dans cette
conversation, contexte daté du 19 octobre 2026. La date propre du courriel, son
expéditeur et ses en-têtes ne sont pas fournis ; aucune heure n'est inventée.
Pas de connexion à la messagerie ou de vérification indépendante de l'expéditeur.
Les liens automatiques DOCN.US/FUN.US du collage sont rendus en texte simple ;
ils ne sont pas traités comme des sources à consulter.

## Texte communiqué

> EPS basis. In most cases the EPS in Trends is non-GAAP, but there are exceptions, and the convention can differ by company. There is no field identifying the basis (GAAP or non-GAAP, basic or diluted) for a specific record, so this cannot be resolved from the endpoint.
>
> 1. Currency and scale. The Trends records have no currency field. Values are in full units, not thousands or millions: for example, revenueEstimateAvg 306,723,910 for DOCN.US. The reporting currency is given in the Financials section of the Fundamentals API (currency_symbol), and for both DOCN.US and FUN.US it is USD.
> 2. Fiscal dates. Yes, dates are normalized to the end of the month in which the fiscal period ends. If a period ends in the first days of a month, the end of the previous month is used. For FUN.US, June 30, 2026 is the fiscal quarter ended June 28, 2026, and September 30, 2026 is the fiscal third quarter of 2026. The FUN.US records refer to the currently listed Six Flags Entertainment Corporation.
> 3. Different horizons. Each fiscal period usually has two records. +1q is the last snapshot taken while that quarter was still the "next" quarter. 0q is the current snapshot, taken once it became the current quarter. The current estimate is therefore the 0q record, and the +1q record is the previously stored forecast for the same period. The dates of the snapshots are not stored, so the reference date of each horizon cannot be resolved from the endpoint.
> 4. Contributor changes. Only aggregate values are provided: average, low, high and the number of analysts, with no per-analyst identity. Changes in contributor composition therefore cannot be distinguished from revisions by existing contributors.

## Conservation

Cette copie documente une précision reçue maintenant. Elle ne prouve pas que
la convention était déjà qualifiée dans Alpha-Trade à une ancienne entrée.
Les anciens protocoles, constats JSON et rapports scellés restent inchangés.
