# Vidéo onboarding opérateur — Script (10-15 min)

> Sprint S25.3 — Phase G. Script destiné à la production de la vidéo
> jointe à `doc/onboarding_operator.md`.

## Cible audience

Opérateur backoffice / quant junior reprenant la plateforme :
* connaît Python ;
* nouveau sur la plateforme ;
* doit lancer un pipeline paper et lire les résultats en < 60 min.

## Spec technique vidéo

* Format : MP4 H.264, 1080p, 30 fps.
* Audio : voix-off + sous-titres VTT (français).
* Capture écran : OBS / ScreenStudio.
* Hébergement : `doc/onboarding_assets/onboarding_v1.mp4`
  (commit pointer + lien S3/Drive si > 50 Mo).

## Découpage scènes

### Scène 1 — Introduction (0:00 → 0:45)
* Vue d'ensemble plateforme (slide titre + diagramme C4 niveau 1).
* « En 15 minutes vous saurez : installer, lancer un pipeline paper,
  lire les résultats, intervenir en cas d'incident. »

### Scène 2 — Installation (0:45 → 2:30)
* Terminal : `git clone`, `python -m venv`, `pip install -e ".[dev]"`.
* Édition `config.yaml` (focus champs : `broker.mode = paper`,
  `database.host`).
* Vérification : `pytest -m unit -q --no-cov`.

### Scène 3 — Tour de l'IHM (2:30 → 5:30)
* `streamlit run ihm/app.py`.
* Sidebar — 5 sections : **Accueil → Workflow → Trading → Recherche →
  Conformité**.
* Page **🏠 Vue d'ensemble** : KPI principaux.
* Page **🚀 Execution** : ordres en cours, OCO actifs.
* Page **📜 Compliance & Audit** : 6 onglets (HMAC, DR, CVE, Cov+Mut,
  TLAPS+Fuzz, Sandbox).

### Scène 4 — Lancement pipeline paper (5:30 → 9:00)
* Page **🔄 Pipeline** : bouton « Lancer pipeline complet ».
* Étapes : screener (200 symb.) → selector → risk → execution paper.
* Suivi temps réel via supervision_ops.
* Lecture résultats : page **📊 Screening** + **🧪 Backtesting**.

### Scène 5 — Lecture résultats (9:00 → 11:30)
* Page **🔀 Parité Backtest ↔ Live** : interpréter `divergence_score`.
* Page **🤖 ML / Prédictions** : champion model.
* Page **⚖️ Risk** : décisions refusées.
* Téléchargement snapshot conformité (bouton compliance_audit).

### Scène 6 — Intervention en cas d'incident (11:30 → 14:00)
* Cas 1 : sandbox nightly rouge ⇒ ouvrir
  `doc/sandbox_health_runbook.md`.
* Cas 2 : CVE critique apparue ⇒ ouvrir `doc/runbook_24_7.md`.
* Cas 3 : divergence parité > seuil ⇒ workflow.
* Slack `#alpha-trade-ops` pour escalade P0/P1.

### Scène 7 — Conclusion (14:00 → 15:00)
* Récap : 5 commandes essentielles imprimables (`doc/onboarding_cheatsheet.md`).
* Liens : `doc/INDEX.md`, `doc/glossary.py`, runbooks.
* Contact équipe.

## Timecodes & sous-titres

Les sous-titres VTT seront générés depuis le présent script (transcription
fidèle). Synchroniser au tournage.

## Captures écran requises

1. Terminal install (zoom).
2. Sidebar IHM hiérarchique.
3. Page compliance_audit avec 6 onglets.
4. Page parity avec courbes.
5. Notification Slack incident.

## Checklist post-production

- [ ] MP4 1080p < 200 Mo.
- [ ] VTT français vérifié.
- [ ] Watermark version (v1.0 — date).
- [ ] Hébergement + lien dans `doc/onboarding_operator.md` mis à jour.
- [ ] Tag git `onboarding-video-v1.0`.

