# Engagement audit externe — Lettre de mission template

> Sprint S25.2 — Phase G.

## 1. Contexte

Alpha Trade est une plateforme de trading algorithmique long-only
US-equity construite en Python 3.13 (~50 000 lignes). Le présent
document définit les termes d'une **revue externe indépendante** par un
ingénieur senior buy-side.

## 2. Périmètre

| # | Domaine | Profondeur |
|---|---|---|
| 1 | Architecture (`doc/architecture/c4_*.md`) | Lecture + diagramme |
| 2 | Multi-broker abstraction (`core/`, `service/`) | Lecture du contrat |
| 3 | Risk management (`risk_management/`) | Code review + tests |
| 4 | Execution engine (`execution_engine/`) | Code review + replay |
| 5 | Audit chain HMAC (`database/audit_chain.py`) | Validation cryptographique |
| 6 | Conformité fiscale (`tax/wash_sale.py`) | Lecture règles + tests |
| 7 | DR drill (`scripts/dr_drill.yml`) | Reproduction locale |
| 8 | Reporting mensuel (`reporting/`) | Lecture 3 mois consécutifs |
| 9 | Lineage (`lineage/`) | Validation traçabilité |
| 10 | Documentation (`doc/`) | Lecture exhaustive INDEX |

Hors périmètre : optimisation algorithmique, performances absolues,
décisions de produit.

## 3. Livrables attendus

* **`external_audit_report_<auditor>_<date>.md`** suivant le template
  `doc/external_audit_findings_template.md` (résumé exécutif, méthodologie,
  findings par sévérité, plan correctif).
* Liste exhaustive des findings (P0/P1/P2/P3).
* Recommandations stratégiques.
* Signature PGP du rapport + checksum SHA-256.

## 4. Critères d'acceptation

* Rapport rendu < 12 mois ;
* 0 finding **P0** non traité dans les 2 semaines suivant la livraison ;
* Tous les findings P1 planifiés dans un sprint suivant l'audit ;
* Signature PGP vérifiable avec la clé publique de l'auditeur.

## 5. Effort & budget

| Phase | Effort | Coût estimé |
|---|---|---|
| Découverte (lecture doc) | 1 j | 1 000 € |
| Code review approfondi | 3-5 j | 3 000-5 000 € |
| Reproduction / pen-test léger | 1-2 j | 1 000-2 000 € |
| Rédaction rapport | 1 j | 1 000 € |
| **Total** | **6-9 j** | **6 000-9 000 €** |

## 6. Calendrier indicatif

| Date | Étape |
|---|---|
| J0 | Signature engagement + NDA |
| J0 + 5 | Accès repo (read-only branch tag) |
| J0 + 30 | Rapport préliminaire |
| J0 + 45 | Rapport final + signature PGP |
| J0 + 60 | Findings P0 traités |

## 7. NDA

Auditeur signe le NDA standard `doc/external_audit_nda_template.pdf`
(à fournir séparément). Code source confidentiel — pas de
republication ni de reverse engineering au-delà du périmètre.

## 8. Modalités de livraison

* Dossier `doc/external_audit/<auditor_id>_<date>/` (commit dans repo
  privé) :
  * `report.md` — rapport rendu ;
  * `report.md.sig` — signature PGP ASCII-armored ;
  * `report.md.sha256` — checksum.
* Push vers branche `audit/external-<date>`.
* Vérification CI : `python scripts/check_external_audit_freshness.py`
  exit 0.

## 9. Suivi des findings

Reportés dans `doc/pre_audit_findings.md` (section dédiée) avec
mention `source: external` et identifiant `EX-NNN`.

