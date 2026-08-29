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

## ⚠️ Cas particulier : marché fermé au moment du run (overnight cash swing)

En presets `paper` / `live`, l'execution utilise par défaut le profil
`overnight_cash_swing` qui autorise la soumission d'ordres en dehors des
heures de marché (`allow_outside_rth=True`). Conséquence importante :

- l'**entrée** est soumise immédiatement (statut `accepted` / `pending_new`) ;
- elle ne sera **remplie** qu'à la prochaine ouverture (RTH) ;
- TP/SL ne peuvent être armés **qu'après** le fill.

> 🛡️ **Filets de sécurité (sprint S26)** — depuis avril 2026, deux mécanismes
> garantissent que TP/SL finissent toujours par être armés :
>
> 1. **Phase 7b dans l'executor** : si l'entrée se remplit pendant le run
>    (ex. ouverture pendant l'exécution), TP/SL sont armés immédiatement
>    après `BrokerStateSynchronizer.sync`. Métriques visibles dans le
>    `run_summary` : `children_armed_post_sync` (ok) /
>    `children_armed_post_sync_failed` (erreur).
> 2. **Watcher de protection** (`execution_engine/protection_watcher.py`) : à
>    chaque tick, repère les positions remplies sans TP/SL et les arme.
>    Métriques : `armed_missing_protections` /
>    `armed_missing_protections_failed`. Événement audit
>    `CHILDREN_SUBMITTED` avec `trigger="watcher_safety_net"`.
>
> 👉 **Conséquence opérateur** : si vous lancez l'execution la veille au
> soir (overnight), **lancez aussi un watcher** (Task Scheduler ou NSSM)
> sinon les positions remplies à l'ouverture suivante resteront sans
> protection broker-side jusqu'au prochain run executor.

**Comment vérifier que TP/SL sont bien armés sur vos positions actuelles ?**

> ℹ️ Le **TP cible** se règle maintenant dans **Pipeline** → *Centre
> d'exécution avancé* → *Execution* → *Stratégie de protection — sortie*.
> Le **trailing stop (%)** (`trailing_stop_pct`) s'y règle aussi : c'est le
> pourcentage utilisé pour les ordres `trailing_stop` broker-side / fallback.
> Le **stop initial** reste calculé automatiquement par le step **11 Risk**
> (ATR / `risk_per_share`).

1. Page **Execution** → section *Ordres* : filtrez sur `intent_role` =
   `take_profit` et `initial_stop` / `trailing_stop`. Chaque entrée
   `FILLED` doit avoir ses 2 enfants ouverts.
2. Page **Supervision Ops** → bloc *Watcher* : surveillez
   `armed_missing_protections`. Une valeur > 0 indique que le watcher
   vient de combler des protections oubliées (normal en exploitation
   overnight, anormal si récurrent en intraday).
3. SQL rapide :
   ```sql
   SELECT symbol, COUNT(*) FROM execution_order_requests
   WHERE intent_role='entry' AND side='buy' AND status IN ('FILLED','PARTIALLY_FILLED')
     AND NOT EXISTS (
       SELECT 1 FROM execution_order_requests c
       WHERE c.parent_request_id = execution_order_requests.intent_id
         AND c.intent_role IN ('take_profit','initial_stop','trailing_stop')
         AND c.status NOT IN ('CANCELLED','REJECTED','EXPIRED')
     )
   GROUP BY symbol;
   ```
   Doit retourner **0 lignes** en régime nominal.

## Lancer un run d'exécution

Le run d'exécution est lancé via la page **🔄 Pipeline** (étape 12). Vous
pouvez aussi le lancer seul :

1. Page Pipeline → **« Centre d'exécution avancé »** → **« Lancer
   Execution seul »**.
2. Confirmez le mode (`simulate` / `paper` / `live`).
3. Suivez en temps réel.

> ℹ️ Pour le flux `run`, le launcher canonique reste `run_execution.py`.
> `python -m execution_engine` est conservé surtout pour compatibilité
> historique sur `run` et pour le kill switch `cancel-all`.

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

Le bouton **« Kill switch / Annuler tous les ordres »** est désormais exposé
dans la page **Execution**.

Utilisation recommandée :

1. vérifiez le compte sélectionné ;
2. utilisez `dry-run` si vous voulez d'abord lister les ordres ouverts sans
   rien annuler ;
3. en `live`, ressaisissez exactement l'identifiant du compte demandé par
   l'écran ;
4. déclenchez ensuite l'annulation globale.

Si l'IHM n'est pas accessible, la CLI native de secours reste :

```powershell
python -m execution_engine cancel-all --account <votre_account_id> --dry-run
python -m execution_engine cancel-all --account <votre_account_id> --broker-mode live --confirm-account <votre_account_id> --reason "annulation manuelle"
```

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

- Doc technique : [doc/execution_engine.md](../backup/execution_engine.md).
- Watcher : [12_page_supervision_ops.md](12_page_supervision_ops.md).

