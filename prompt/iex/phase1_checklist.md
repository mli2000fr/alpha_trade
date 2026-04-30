# Phase 1 EODHD - Checklist de cadrage

> **Statut 2026-04-29 (re-run post-souscription, 10:37 UTC)** : 🟢 **GO complet Phase 5** — tous les critères go/no-go du §6 sont satisfaits :
> - Bulk HTTP 200 sur 3 jours, payload_size 50 102 / 50 596 / 50 646 (×7 le seuil), latence 4.5–6.8 s
> - Splits NVDA 200 OK avec 10:1 (2024-06-10) et 4:1 (2021-07-20) au format `N.000000/1.000000`
> - Mapping 20/20 (TQQQ désormais accessible avec All-In-One)
> - Aucun 401/403/429
>
> Voir `artifacts/eodhd_cache/phase1_smoke_20260429T103746.json` et `phase1_findings.md`.

> **Objectif** : valider empiriquement la viabilite EODHD avant d investir dans le module `service/eodhd/` (Phase 2). Tous les artefacts ici sont jetables - ils ne participent pas au pipeline.
>
> **Reference** : `prompt/iex/plan_eodhd.md` Phase 1.
---
## 1. Prerequis utilisateur (manuel)
- [ ] **Souscrire EODHD** : https://eodhd.com/cp/pricing - plan **All-In-One** ou **US Stock & ETF** (19,99 $/mois).
- [ ] **Recuperer le token** depuis https://eodhd.com/cp/dashboard.
- [ ] **Definir la variable d environnement** :
  ```powershell
  # PowerShell, scope utilisateur (persistant) :
  [Environment]::SetEnvironmentVariable("EODHD_API_TOKEN", "<votre_token>", "User")
  # ou ponctuellement dans la session courante :
  $env:EODHD_API_TOKEN = "<votre_token>"
  ```
- [ ] **Verifier la definition** :
  ```powershell
  if ($env:EODHD_API_TOKEN) { "OK" } else { "MISSING" }
  ```
## 2. Smoke tests automatises
Une fois le token en place :
```powershell
# 1 jour ouvre (J-1) - cout ~125 calls
python scripts/eodhd_phase1_smoke.py
# 3 jours ouvres pour observer la regularite de publication du bulk - cout ~325 calls
python scripts/eodhd_phase1_smoke.py --bulk-days 3
# Sans la batterie de mapping (economise 20 calls)
python scripts/eodhd_phase1_smoke.py --skip-mapping
```
Le script ecrit un resume dans `artifacts/eodhd_cache/phase1_smoke_<TIMESTAMP>.json`.
## 3. Criteres de validation
### 3.1 Bulk daily (`/eod-bulk-last-day/US`)
| Critere | Seuil OK | Action si KO |
|---|---|---|
| HTTP status | 200 | Verifier token + plan souscrit |
| `payload_size` | >= 7000 symboles US | Plan limite a un sous-univers ? |
| `latency_s` | < 10 s | Acceptable jusqu a 30 s pour un univers complet |
| Disponibilite du jour J | bulk J-1 dispo avant 04:00 UTC | Si delai > 4h apres cloture, augmenter `bulk_publish_offset_hours` |
### 3.2 Endpoint EOD (`/eod/NVDA.US`)
| Critere | Seuil OK |
|---|---|
| HTTP status | 200 |
| `rows` | >= 20 sur 30 jours (jours ouvres) |
| `first_row` contient | `open`, `high`, `low`, `close`, `adjusted_close`, `volume` |
### 3.3 Splits (`/splits/NVDA.US`)
Validation **CRITIQUE** pour la reconstruction split-only (cf. `plan_eodhd.md` 5.4).
| Critere | Attendu |
|---|---|
| Presence du split 10:1 du 2024-06-10 | `{"date":"2024-06-10","split":"10/1"}` |
| Presence du split 4:1 du 2021-07-20 | `{"date":"2021-07-20","split":"4/1"}` |
| Format `split` | chaine `"N/M"` parsable en `float(N)/float(M)` |
### 3.4 Mapping symboles (20 cas)
| Categorie | Symboles | Attendu |
|---|---|---|
| Large caps simples | AAPL, MSFT, NVDA, AMZN, META, TSLA | `<TICKER>.US`, >= 5 rows sur 10 jours |
| Classes A/B (point -> tiret) | BRK.B, BRK.A, BF.B | `<PREFIX>-<CLASS>.US` |
| Multi-classes Alphabet | GOOG, GOOGL | `<TICKER>.US` (point conserve pour Alphabet) |
| ETFs | SPY, QQQ, IWM, VTI, TQQQ | `<TICKER>.US` |
| ADRs | BABA, TSM, NVO | `<TICKER>.US` |
| Mid cap edge | AAOI | `AAOI.US` |
**Critere de reussite** : >= 19/20 succes. Tout KO inattendu doit etre ajoute dans la future
`service/eodhd/symbols_exceptions.json` (Phase 2).
## 4. Decisions a figer en sortie de Phase 1
- [ ] **Latence bulk** : moyenne empirique sur 3 jours -> decide la valeur finale de `eodhd.bulk_publish_offset_hours` dans `config.yaml` (par defaut : 2 h).
- [ ] **Tableau d exceptions de mapping** : symboles qui derogent a la regle `<TICKER>.US` ou `<TICKER>-<CLASS>.US`.
- [ ] **Quota observe** : ratio (calls consommes Phase 1) / 100 000 - doit rester < 1 %.
- [ ] **Convention split** : confirmer que `splits["split"]` est bien `"N/M"` partout.
## 5. Cout estime Phase 1 complet
| Test | Calls EODHD |
|---|---|
| Bulk J-1 (x3 jours) | 100 x 3 = 300 |
| `/eod/NVDA.US` | 1 |
| `/splits/NVDA.US` | 1 |
| Mapping 20 symboles | 20 |
| **Total** | **~325** |
Sur quota journalier de 100 000 -> < 0,4 %. **Pas de risque de saturation.**
## 6. Critere go/no-go pour passer en Phase 2
- Bulk J-1 stable sur 3 jours (latence < 10 s, taille > 7000).
- Splits NVDA conformes au format attendu (10:1 et 4:1 presents).
- Mapping symboles >= 19/20 succes.
- Aucun appel HTTP 401 / 403 / 429.
Si tous les criteres sont verts -> **Phase 2** : developper `service/eodhd/clientEodhd.py` + adapter split-only + tests golden.
---
## Annexe - Pourquoi pas le module `service/eodhd/` des maintenant ?
Phase 1 = **validation empirique**. Le module officiel arrive en Phase 2 avec :
- `RetryPolicy` + telemetry maison,
- erreurs typees (`EodhdQuotaExceeded`, etc.),
- cache disque structure,
- tests unitaires mockes.
Le script `scripts/eodhd_phase1_smoke.py` est **deliberement minimaliste** (urllib stdlib, aucune dependance projet) pour qu on puisse le lancer sur un poste neuf et l archiver apres Phase 2 sans dette technique.
