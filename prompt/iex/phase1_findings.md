# Phase 1 EODHD — Findings & décision Go/No-Go

> **Date** : 2026-04-29
> **Source** : `artifacts/eodhd_cache/phase1_smoke_20260429T094918.json`
> **Réf. plan** : `prompt/iex/plan_eodhd.md` (Phase 1) + `prompt/iex/phase1_checklist.md`
>
> **⚠️ Contexte d exécution** : smoke test lancé **AVANT souscription du plan EODHD** (compte évaluation/free tier). Les KO observés (bulk 423, splits 403, TQQQ 402) sont **attendus et imputables au plan non souscrit**. Ce document reste valide comme **baseline pré-souscription** : il sera ré-exécuté après upgrade pour confirmer le go définitif. **Décision pratique : GO conditionnel Phase 2** — l implémentation démarre, les tests live re-tournent après souscription.

---

## 1. Synthèse

| Critère checklist §3 | Seuil OK | Mesuré | Verdict |
|---|---|---|---|
| Bulk `/eod-bulk-last-day/US` HTTP 200 | 200 | **423 Locked** (×3 jours) | ❌ **BLOQUANT** |
| Bulk `payload_size` ≥ 7000 | ≥ 7000 | n/a (pas de payload) | ❌ |
| Bulk latence < 10 s | < 10 s | 0.6 s (fail rapide) | n/a |
| `/eod/NVDA.US` HTTP 200 | 200 | 200 | ✅ |
| `/eod/NVDA.US` ≥ 20 rows / 30 j | ≥ 20 | 21 | ✅ |
| `/eod/NVDA.US` champs requis | OHLCV + `adjusted_close` | tous présents | ✅ |
| Splits NVDA présents (10:1 + 4:1) | format `N/M` | **403 Forbidden** | ❌ **BLOQUANT** |
| Mapping ≥ 19/20 | ≥ 19 | 19/20 | ✅ (à la limite) |
| Aucun 401 / 403 / 429 | 0 | 1×403 + 1×402 + 3×423 | ❌ |

**Critère go/no-go global (checklist §6)** : ❌ **NO-GO** — 2 critères bloquants sur 4.

---

## 2. Détail des anomalies

### 2.1 Bulk `/eod-bulk-last-day/US` → HTTP 423 Locked
- 3 jours de bourse testés (J-1=2026-04-28, J-2=2026-04-27, J-3=2026-04-24).
- Latence ~0.6 s = fail immédiat côté gateway, pas un blocage applicatif.
- HTTP 423 « Locked » côté EODHD = ressource non débloquée pour le plan/token courant.
- **Diagnostic** : plan souscrit incompatible avec l'endpoint bulk.

### 2.2 Splits `/splits/NVDA.US` → HTTP 403 Forbidden
- Endpoint splits dédié non accessible.
- Cohérent avec un plan « EOD Historical Data US » sans les options All-In-One.

### 2.3 TQQQ → HTTP 402 Payment Required
- Seul KO du panel mapping (19/20).
- ETF leveragé non couvert par le plan actuel.
- Impact projet : à ajouter dans `service/eodhd/symbols_exceptions.json` (Phase 2)
  **ou** confirmer que TQQQ est hors univers Alpha Trade.

### 2.4 Endpoint `/eod/{ticker}.US` → ✅ pleinement fonctionnel
- 19/20 symboles du panel OK (Large caps, BRK.A/B avec mapping `BRK-A/B.US`,
  GOOG/GOOGL conservant le `.`, ETFs simples, ADRs).
- Volume reporté pour NVDA (28/04) : **185 627 016** — cohérent SIP, pas IEX-only.
- `adjusted_close` présent → permet la déduction split-only sans `/splits/` dédié.

---

## 3. Hypothèse plan souscrit

Le profil d'erreurs (`bulk=423` + `splits=403` + `leveraged_etf=402`) correspond à
un plan **« EOD Historical Data US »** basique (~$19.99) **sans** :
- accès bulk daily,
- endpoint splits dédié,
- couverture ETFs leveragés / produits dérivés.

L'endpoint `/eod/{ticker}.US` reste pleinement opérationnel (c'est le cœur du plan EOD).

> **À vérifier** : page de souscription EODHD (https://eodhd.com/cp/dashboard).
> Le plan « All-In-One » ($99.99) débloque bulk + splits dédiés + fundamentals.

---

## 4. Options de remédiation

### Option A — Upgrade plan « All-In-One » ($99.99/mois)
- ✅ `plan_eodhd.md` reste **inchangé**.
- ✅ Architecture « 1 seul appel bulk → 2 tables » préservée (§3.6).
- ❌ +400 % de coût d'abonnement vs annonce initiale ($19.99 → $99.99).
- ⏱ Effort : relancer `python scripts/eodhd_phase1_smoke.py --bulk-days 3` puis Phase 2.

### Option B — Pivot « per-symbol EOD » (plan actuel $19.99 conservé)
- Remplacer le bulk par une boucle `/eod/{ticker}.US?from=J-1&to=J-1` sur l'univers actif
  (~500 symboles S&P 500 + watchlist).
- **Coût quotidien** : ~500 calls / 100 000 = **0.5 % du quota** → marge largement OK
  même avec backfill et retries.
- **Splits** : déduits du ratio `close / adjusted_close` sur l'historique `/eod/`
  (test NVDA 28/04 : ratio = 1.0 ⇒ pas de split récent). Plus besoin de `/splits/`.
- **Volume SIP** : conservé (objectif P0 audit atteint).
- ✅ Budget tenu, qualité de la donnée préservée.
- ❌ `plan_eodhd.md` à amender (§3.6, §5.4, §6 Phase 2-3, §8.1, §10).
- ❌ ~+1 j de dev supplémentaire (orchestration boucle, parallélisme borné, rate-limit local).

### Option C — Tickets support EODHD
- Le code 423 « Locked » (vs 403 « Forbidden » pour les splits) suggère une ressource
  *temporairement* indisponible plutôt qu'un refus de plan. Il est possible que le
  bulk soit en théorie inclus mais nécessite une activation manuelle.
- ⏱ Effort : 1 ticket support, attente de réponse 24-72h.
- À combiner avec Option B en attendant.

---

## 5. Recommandation

> **Option B + ticket support (Option C)** :
> - Lancer immédiatement le ticket EODHD pour clarifier le statut du bulk.
> - En parallèle, amender `plan_eodhd.md` pour la stratégie « per-symbol EOD »
>   (réversible si Option A retenue plus tard — l'`/eod/` reste utilisé même en
>   architecture bulk pour le backfill historique).
> - Décision finale (A vs B) après réponse support, sans bloquer Phase 2.

---

## 6. Décisions à figer (checklist §4)

- [ ] **Plan retenu** : ☐ A (All-In-One) ☐ B (per-symbol $19.99) ☐ C (attente support)
- [x] **Mapping symboles validé** : règles `<TICKER>.US` (large caps, ADRs, ETFs, GOOG/GOOGL),
      `<TICKER>-<CLASS>.US` (BRK.A/B, BF.B). **Exception connue** : TQQQ KO sur plan basique.
- [x] **Quota Phase 1 observé** : ~25 calls effectifs (3 bulk fail + 1 eod + 1 splits fail + 20 mapping)
      sur 100 000 → 0.025 % consommé. Aucun risque de saturation.
- [ ] **Convention split** : non vérifiable (endpoint 403). Décision déportée :
      utiliser `adjusted_close / close` de `/eod/` comme source de vérité.
- [ ] **`bulk_publish_offset_hours`** : non mesurable tant que bulk inaccessible.

---

## 7. Prochaines étapes (en attente arbitrage utilisateur)

1. Arbitrage Option A / B / C.
2. Si B : patch `plan_eodhd.md` §3.6 + §5.4 + §6 + §10.
3. Re-run smoke test après upgrade plan (si A) ou directement Phase 2 (si B).

 python scripts/eodhd_phase1_smoke.py --bulk-days 3 à tester après upgrade pour confirmer le go définitif.
