# Message au support EODHD — copie du brouillon préparé

Statut actualisé : brouillon préparé le 19 octobre 2026, ensuite envoyé par
l'utilisateur, qui a transmis la réponse. Aucun envoi par l'assistant.
Voir [le bilan de la réponse](consensus_eodhd_precisions_support_20261019.md).
Le texte ci-dessous reste la copie du message préparé ; aucun destinataire inventé.
L'extrait JSON associé est une sélection de champs, pas une réponse API complète.
Il ne contient ni token, ni URL authentifiée, ni identifiant de compte.

**Subject: Calendar/Trends field definitions — DOCN.US and FUN.US consensus snapshots**

Hello EODHD Support,

Thank you for your earlier clarification that you do not provide true historical
point-in-time earnings estimates. This request is different: we now archive the
Calendar/Trends responses actually received each day and need to interpret their
fields consistently. We are not requesting a higher plan or historical vintages.

Could you clarify the following for DOCN.US and FUN.US, using the records with
`date=2026-09-30` observed on October 11 and October 18, 2026?

1. **EPS basis.** Are `earningsEstimateAvg` and `epsTrendCurrent` GAAP or
   adjusted/non-GAAP, and basic or diluted? Can the convention differ by company
   or period, and where is it identified? The glossary describes `epsActual` as
   non-GAAP, but we do not want to assume this defines the consensus fields too.

2. **Currency and scale.** Which reporting currency and numerical scale apply
   to EPS and `revenueEstimateAvg` for these records? Is there a field or
   authoritative reference identifying them? The received trend items do not
   specify these explicitly; we do not want to infer them from trading currency.

3. **Fiscal dates and issuer identity.** For FUN.US, the issuer's Q2 release
   states a quarter ending June 28, 2026, while trend records use June 30.
   Are dates normalized to calendar quarter-ends? Which exact fiscal period
   does September 30, 2026 represent? Please also confirm that these records
   refer to the post-merger Six Flags entity, CIK 0001999001.

4. **Different horizons for the same date.** On October 18, the same
   `date=2026-09-30` appears with different `period` values and EPS averages:

   | Symbol | `0q` | `+1q` |
   |---|---:|---:|
   | DOCN.US | 0.3186 | 0.2842 |
   | FUN.US | 2.0811 | 2.1470 |

   What reference date does each horizon use? How should we distinguish the
   current estimate from a previously stored forecast for the same fiscal
   period, without merging these records or simply selecting the last one?

5. **Contributor changes.** Can the analyst population change while the
   reported analyst count remains unchanged? Do revision counts distinguish
   revisions by existing contributors from changes in contributor composition?

I can provide the attached selected-field excerpt from our received snapshots.
Please identify any fields that cannot be resolved from this endpoint rather
than assuming that every record uses the same conventions.

Thank you for your help.

Best regards,
Ming LI

---

Pièce facultative : `extrait_support_eodhd_consensus_docn_fun_20261019.json`,
dans ce même dossier. Les dates d'observation sont celles de notre collecte,
pas des dates de publication ou des vintages certifiés par EODHD.
Ne pas joindre les enveloppes complètes ni les variables d'environnement.
