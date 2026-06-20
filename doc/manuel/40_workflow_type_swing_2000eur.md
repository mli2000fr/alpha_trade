# 40. Workflow type swing trader débutant ~2 000 €

> Journée type, heure par heure, pour une routine **swing trade discipline
> totale**. Adapté à un actif en France (UTC+1/+2) tradant sur Alpaca US.

## Hypothèses

- Capital : ~2 000 € (~2 150 USD).
- Preset : `capital_0_2000`.
- Mode : `paper` les premières semaines, puis `live` après validation.
- Compte : Alpaca cash, US stocks long-only.
- Horizon : 2-10 jours par trade.

## Lundi à vendredi (jours de bourse US)

### 🌅 Matin (avant ouverture US, 14h00 heure FR)

#### 14h30 — Pré-ouverture

1. Ouvrez l'IHM (`python run.py` si pas déjà lancée).
2. Page **🛟 Supervision Ops** → vérifiez le watcher 💚.
3. Page **🚀 Execution** → vérifiez les positions actuelles vs prévues.

#### 14h45 — Lancement Execution (paper ou live)

1. Page **🔄 Pipeline** → mode `paper` (ou `live`).
2. Cliquez **« Lancer Execution seul »** (pas tout le pipeline, qui a déjà
   tourné la veille).
3. Suivez l'envoi des ordres (page Execution).

#### 15h30 — Ouverture US

- Les ordres `market on open` sont remplis.
- Les ordres protecteurs (stop / TP) sont placés.
- Surveillez les **rejets** éventuels (insufficient buying power, etc.).

### 🌞 Journée (15h30 → 22h00)

- **Vous ne touchez à rien.** Les positions vivent leur vie.
- Le watcher veille en arrière-plan.
- Maximum : un coup d'œil rapide sur la page Execution toutes les 2-3 h.

> ⚠️ **Tentation à éviter** : modifier un stop ou prendre un profit en
> plein milieu de séance. Vous casseriez la discipline. Laissez les
> ordres protecteurs faire leur travail.

### 🌇 Soir (après clôture US, 22h00 heure FR)

#### 22h15 — Pipeline complet du soir

1. Page **🔄 Pipeline** → mode `simulate` (calculs uniquement).
2. Cliquez **« Lancer le workflow complet »** (durée 15-30 min).
3. Vous pouvez fermer le navigateur, ça continue.

#### 22h45 — Vérification

1. Page **🏠 Vue d'ensemble** : statut 🟢.
2. Page **📊 Screening** : nombre de candidats (50-150 attendus).
3. Page **⚖️ Risk** : décisions du jour.
4. Page **🤖 ML / Prédictions** : top probabilités.

#### 23h00 — Préparation lendemain

- Notez vos **3 lignes cibles** dans un carnet personnel.
- Si une décision vous semble bizarre (ex. trop concentré sur 1 secteur),
  vérifiez page Risk → `rejection_reason`.
- Allez vous coucher. Demain on exécute à 14h45.

## Week-end (samedi-dimanche)

| Tâche | Fréquence | Durée |
|---|---|---|
| Lancer pipeline complet (samedi 10h) | 1×/semaine | 30 min |
| Page **📑 Corporate Actions** : sync + apply | 1×/semaine | 5 min |
| Page **🧪 Backtesting** : tester un ajustement | 1× sur 2 semaines | 1 h |
| Lecture rétrospective de la semaine | 1×/semaine | 30 min |

## 1× par mois

| Tâche | Pourquoi |
|---|---|
| Backtest walk-forward sur 3 ans | Vérifier que la stratégie tient toujours |
| Backup de la DB (`mysqldump alpha_trade > backup.sql`) | Sécurité |
| Lecture page Compliance & Audit | Vérifier audit chain intacte |
| Vérifier mises à jour : `pip list --outdated` | Sécurité |
| Régler les ordres laissés ouverts trop longtemps | Hygiène portefeuille |

## 1× par trimestre

| Tâche |
|---|
| Re-entraînement ML complet (`rebuild-all`) |
| Re-calibration des poids sentiment (CLI `calibrate-sentiment-weights`) |
| Comparaison de votre P&L réel vs paper vs backtest (cohérence) |
| Bilan : continuer / ajuster preset / suspendre |

## Règles d'or

1. **Toujours** un stop-loss.
2. **Jamais** plus de 1.5 % du capital risqué par trade.
3. **Jamais** plus de 3 positions simultanées (en micro-compte).
4. **Pas** d'ordre intra-séance impulsif.
5. **Pas** de margin tant que < 25 000 USD.
6. **Pas** de live tant que paper < 0 sur le mois précédent.
7. **Tenir un journal** des trades (raison d'entrée, sortie, leçon).

## Pour aller plus loin

- Sécurité argent réel : [52_securite_et_argent_reel.md](52_securite_et_argent_reel.md)
- Dépannage : [51_depannage.md](51_depannage.md)
- FAQ : [50_faq.md](50_faq.md)

