# 8. Page 🚀 Execution — envoyer les ordres au broker

## À quoi sert cette page

Voir et superviser les **runs d'exécution** : quels ordres ont été envoyés
au broker (Alpaca), lesquels ont été remplis (`fills`), événements,
réconciliation broker.

## ⚠️ Avant tout : vérifiez le badge en haut à droite

| Badge | Effet d'un clic « Lancer » |
|---|---|
| 🟡 **SIMULATE** | Aucun ordre envoyé, calcul local uniquement |
| 🟢 **PAPER** | Ordres envoyés au compte paper Alpaca (faux argent) |
| 🔴 **LIVE** | **Ordres envoyés au compte réel — argent réel engagé** |

> 🛑 Si vous voyez 🔴 LIVE et que vous ne le voulez pas : descendez immédiatement
> sur **Paramètres / Santé** → **Mode d'exécution** → repassez en `paper`.

## Lecture des sections

### Section 1 — Runs récents

Tableau des derniers runs `run_execution` :

| Colonne | Signification |
|---|---|
| `run_id` | Identifiant unique |
| `started_at` | Heure de lancement |
| `status` | `running` / `completed` / `failed` |
| `mode` | `simulate` / `paper` / `live` |
| `n_orders_submitted` | Ordres envoyés |
| `n_fills` | Ordres exécutés |
| `pnl_usd` | Gain/perte du run |

### Section 2 — Ordres (orders)

Détail ordre par ordre : `symbol`, `side` (BUY/SELL), `qty`, `limit_price`,
`status` (`accepted` / `filled` / `cancelled` / `rejected`).

### Section 3 — Fills

Les ordres effectivement exécutés au marché : `symbol`, `qty`, `price`,
`time`.

### Section 4 — Positions broker

Vos positions actuelles côté broker : `symbol`, `qty`, `avg_entry_price`,
`market_value`, `unrealized_pl`.

### Section 5 — Réconciliation

Compare positions broker ↔ DB locale. Statuts :
- 🟢 `SAFE_AUTO` : tout correspond
- 🟡 `MANUAL_REVIEW` : différence à analyser
- 🔴 `BLOCKED` : divergence majeure (intervention requise)

### Section 6 — Watcher de protection

Affiche le statut du processus 24/7 qui vérifie que les stop-loss / TP
sont bien en place chez le broker. Voir
[12_page_supervision_ops.md](12_page_supervision_ops.md).

## Lancer un run d'exécution

Le run d'exécution est lancé via la page **🔄 Pipeline** (étape 12). Vous
pouvez aussi le lancer seul :

1. Page Pipeline → **« Centre d'exécution avancé »** → **« Lancer
   Execution seul »**.
2. Confirmez le mode (`simulate` / `paper` / `live`).
3. Suivez en temps réel.

## Premier ordre en paper trading — checklist

- [ ] Compte Alpaca paper créé
- [ ] Variables `ALPACA_API_KEY` / `_SECRET` dans `.env` (paper)
- [ ] Compte sélectionné dans la sidebar
- [ ] Badge 🟢 PAPER visible
- [ ] Pipeline complet exécuté juste avant (≤ 24h)
- [ ] Page Risk affiche au moins 1 décision `long`
- [ ] Vous comprenez le sizing affiché
- [ ] Vous avez lu [52_securite_et_argent_reel.md](52_securite_et_argent_reel.md)

Si tous coches : cliquez « Lancer Execution » en mode `paper`.

## Annulation d'urgence (« kill switch »)

> ⚠️ **GAP CONNU** : à la date de rédaction, le bouton « Annuler tous les
> ordres » n'est **pas encore exposé dans l'IHM** (cf. matrice IHM↔CLI).
> En attendant, ouvrez PowerShell et tapez :
>
> ```powershell
> python -m execution_engine cancel-all --account <votre_account_id> --confirm-account <votre_account_id> --broker-mode paper --reason "annulation manuelle"
> ```
>
> Remplacez `paper` par `live` si vous êtes en argent réel.

## Pour passer en live (un jour)

Voir la checklist détaillée :
[52_securite_et_argent_reel.md](52_securite_et_argent_reel.md).

## Pièges courants

- ❌ Lancer Execution sans avoir lancé Risk juste avant → rien à exécuter.
- ❌ Lancer Execution avec un compte mal sélectionné → ordres sur le
  mauvais portefeuille.
- ❌ Statut `MANUAL_REVIEW` ignoré → vos chiffres divergent du broker
  jour après jour.

## Pour aller plus loin

- Doc technique : [doc/execution_engine.md](../execution_engine.md).
- Watcher : [12_page_supervision_ops.md](12_page_supervision_ops.md).

