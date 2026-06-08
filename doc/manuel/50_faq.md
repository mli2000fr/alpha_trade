# 50. FAQ — questions fréquentes des débutants

## Démarrage

### ❓ Combien de temps avant de pouvoir gagner de l'argent ?

Comptez **6 mois minimum** : 2 mois en simulate + 3 mois en paper +
1er trade live à petite échelle. Tout ce qui va plus vite est dangereux.

### ❓ Combien faut-il pour démarrer ?

Techniquement 100 USD suffisent (Alpaca permet les fractional shares).
Réellement, 1 000 → 2 000 € est un bon point de départ pour amortir les
frais et constituer 3 lignes diversifiées.

### ❓ Faut-il connaître le code Python ?

Non pour utiliser l'IHM. Oui pour modifier des paramètres avancés
(`config.yaml`).

### ❓ L'application fonctionne-t-elle sur Mac / Linux ?

Possible mais non testé. La doc cible Windows.

## Fonctionnement

### ❓ Pourquoi 0 candidat retenu aujourd'hui ?

Plusieurs causes :
1. Marché baissier généralisé (RSI < 90 partout).
2. Filtres trop stricts pour votre preset.
3. Pipeline pas exécuté aujourd'hui (vérifiez page Vue d'ensemble).
4. Données pas à jour (step 2 a échoué).

Voir [05_page_screening.md §5](05_page_screening.md).

### ❓ Pourquoi ma page est vide ?

Voir [51_depannage.md §1](51_depannage.md).

### ❓ Le ML peut-il prédire l'avenir ?

**Non.** Il estime une probabilité conditionnelle basée sur des patterns
historiques. La probabilité 0.65 signifie « historiquement, dans des
conditions similaires, le cours a monté de +2 % en 5 jours dans 65 % des
cas ». Ce n'est pas une garantie.

### ❓ Combien de trades par mois sur 2 000 € ?

Avec preset `capital_0_2000_eur` et 3 positions max : ~10-30
trades/mois (rotation tous les 5-10 jours en moyenne).

## Argent et performance

### ❓ Combien je peux gagner par mois avec 2 000 € ?

En espérance long terme : 1-2 % / mois (~20-50 €). En réalité : très
volatil, des mois à -200 €, d'autres à +500 €.

### ❓ Et si je perds tout ?

C'est possible. C'est pourquoi vous ne devez investir que de l'argent que
vous pouvez perdre **intégralement** sans impact sur votre vie.

### ❓ Puis-je faire du levier (margin) ?

**Non, pas avant 25 000 USD.** Le levier multiplie les pertes. Le preset
`capital_0_2000_eur` impose `cash` automatiquement.

### ❓ Faut-il déclarer aux impôts ?

**Oui.** Voir [20_gestion_petit_capital_2000eur.md §6](20_gestion_petit_capital_2000eur.md).

## Erreurs fréquentes

### ❓ « Insufficient buying power » lors d'un ordre

Le compte n'a plus assez de cash. Causes :
- positions ouvertes immobilisent le cash,
- ordres limit en attente immobilisent le cash en `pending`,
- erreur de calcul `target_quantity` (rare).

### ❓ « Order rejected: insufficient settled cash »

Le compte n'a pas assez de cash settled pour ouvrir une nouvelle ligne.
Après une vente, les fonds sont réutilisables au settlement simplifié `T+1`.

### ❓ Watcher rouge

Le processus est tombé. Relancez :
```powershell
python run_execution_protection_watch.py
```

### ❓ « DB indisponible »

Voir [51_depannage.md §2](51_depannage.md).

### ❓ Pipeline bloqué « En cours » depuis 2h

Probablement le step 2 (import bars) coincé. Solution :
1. Page **🛟 Supervision Ops** → kill le PID concerné.
2. Relancez juste ce step.

## Stratégie

### ❓ Quelle est la stratégie sous-jacente ?

**Momentum swing trade long-only** : on achète les actions qui montent
fort (force relative > 90), proches de leur plus haut 52 semaines, avec
un boost de sentiment news positif et une probabilité ML > 55 %.

### ❓ Puis-je faire du short ?

Non actuellement supporté.

### ❓ Puis-je trader des cryptos / forex / options ?

Non, l'app est conçue pour **US stocks** uniquement.

### ❓ Pourquoi pas de buy & hold long-terme ?

Le moteur est calibré pour des horizons 2-10 jours. Pour du long-terme,
préférez un ETF MSCI World en DCA.

### ❓ Puis-je modifier la stratégie ?

Oui via les paramètres (page Settings) et le code Python. Mais cela
demande une bonne compréhension. Lisez d'abord
[doc/selector.md](../selector.md) et [doc/risk_management.md](../risk_management.md).

## Questions opérateur (session mai 2026)

> Bloc Q/R consolidé suite à l'usage paper multi‑comptes.
> Chaque réponse cite les fichiers/fonctions sources pour permettre l'audit.

### ❓ 1. Est-ce normal que la colonne `content` de la table `news_raw` soit toujours `NULL` ?

**Oui, c'est normal aujourd'hui.**

- Le schéma déclare bien `content MEDIUMTEXT NULL`
  (`database/sql/news/news_raw.sql` ligne 5).
- L'ingestion (`event_sentiment/ingestion.py` ligne 37) fait :
  `content = str(payload.get("content") or payload.get("body") or "").strip() or None`.
- L'API news Alpaca utilisée
  (`service/alpaca/clientNewsAlpaca.py::iter_news_pages`) ne renvoie que
  `headline` et `summary` ; il n'y a **aucun champ `content` ni `body`** dans
  la réponse standard. La colonne reste donc systématiquement `NULL`.
- Conséquence métier : `event_sentiment/scoring.py::_choose_text` (ligne 135)
  retombe toujours sur `headline + summary`. Ce n'est pas bloquant : le score
  de sentiment fonctionne, mais il est plus pauvre qu'un score basé sur un
  article complet.
- **Pour enrichir** `content`, il faut brancher un fournisseur qui retourne le
  texte intégral (Benzinga, Finnhub Premium news‑content, NewsAPI…) puis
  exposer le champ dans `clientNewsAlpaca` ou un nouveau client.

### ❓ 2. L'exécution n'a jamais vendu d'actions — est-ce normal ? Comment le risk management gère-t-il la vente ?

**Le `risk_management/` ne génère AUCUN ordre de vente.** Toutes les ventes
sont déléguées au moteur d'exécution sous forme d'**enfants OCO** posés à la
suite d'un BUY filled.

Chaîne complète :

1. `risk_management/portfolio_builder.py` produit uniquement des intents
   `side="buy"` (sizing ATR, budget, contraintes secteur).
2. `execution_engine/order_intents.py` construit, pour chaque BUY, deux
   enfants vendeurs :
   - `build_take_profit_intent` (ligne 106) → ordre LIMIT `sell` à
     `entry × (1 + take_profit_pct)`.
   - `build_initial_stop_intent` (ligne ~158) → ordre STOP `sell` au plus
     bas du stop ATR.
   - `build_trailing_stop_intent` (ligne ~196) → trailing STOP qui s'arme
     soit en R‑multiple, soit en pourcentage.
3. `execution_engine/children_submission.py` (ligne 83) soumet ces enfants
   **après le fill du parent BUY**.
4. Filet de sécurité : `execution_engine/protection_watcher.py`
   (`_arm_missing_protections`, lignes 330‑423) repère les positions filled
   sans TP/SL et arme les protections manquantes.

**Pourquoi vous n'avez encore rien vu vendre :**

- soit aucun BUY n'a été *filled* (marché fermé, ordre rejeté, etc.),
- soit les seuils TP/SL n'ont jamais été touchés par le marché (cas le plus
  courant à court terme),
- soit le watcher de protections n'a jamais été lancé après l'execution :
  les enfants OCO ne sont alors pas posés et le broker ne peut pas vendre.

Critère de vente exécutée par Alpaca : prix touche le `take_profit_price`
ou le `stop_price` armé côté broker. Aucune logique de vente discrétionnaire
côté Alpha Trade.

### ❓ 3. Les ordres sont‑ils persistés en base ? Comment l'application sait‑elle quels titres sont détenus et en quelle quantité ?

**Oui, tout l'audit trail est persisté en DB**, par compte (`account_id`) :

- `execution_order_requests` — intents canoniques (parent + enfants OCO).
- `execution_broker_orders` — ordres miroirs côté broker.
- `execution_broker_fills` — exécutions partielles/complètes.
- `execution_positions` — positions canoniques agrégées par compte.
- `execution_position_lots` — lots FIFO/LIFO pour la fiscalité.
- `broker_positions_snapshots` — snapshot read‑only du broker à chaque cycle.

Repository : `execution_engine/db_io.py`
(`snapshot_broker_positions` ligne 1244, `replace_execution_positions`
ligne 1279, `load_execution_positions` ligne 1479).

L'IHM page **Compte Alpaca** affiche **deux sources distinctes** :

| Tableau IHM                          | Source                                                          |
|--------------------------------------|------------------------------------------------------------------|
| Positions ouvertes (broker)          | Appel REST live `AlpacaTradingClient.get_positions`              |
| Ordres canoniques d'exécution (DB)   | Lecture `execution_order_requests` / `execution_broker_orders`   |
| Historique des ordres (broker)       | Appel REST live `AlpacaTradingClient.list_orders(status="all")`  |

→ Le broker reste la **source de vérité** pour ce qui est réellement détenu ;
la DB est la **source de vérité auditée** pour la généalogie de chaque ordre.
La réconciliation se fait à chaque cycle d'exécution et à chaque tick du
watcher.

### ❓ 4. Je change de compte Alpaca — faut-il nettoyer des tables ou des répertoires ?

**Non, en principe rien à nettoyer**, à condition que le nouveau compte ait
un `account_id` différent (ou un *label* différent dans la `AccountRegistry`,
cf. `service/alpaca/accounts.py`).

- **Toutes les tables `execution_*` portent un `account_id`** (cf.
  `database/sql/migration_add_account_id.sql`). Les requêtes filtrent
  systématiquement par compte (ex. `replace_execution_positions` ligne 1287 :
  `DELETE ... WHERE account_id = :account_id`).
- Il n'y a donc **pas de mélange** entre vos 3 comptes : les positions
  canoniques de l'ancien compte restent en base mais ne sont plus relues.
- Si vous **remplacez physiquement** le compte n°2 par un autre Alpaca tout
  en réutilisant le même `account_id` / label : vous devez purger les
  anciennes lignes pour ce compte, sinon la prochaine réconciliation
  comparera votre nouveau portefeuille broker à un état canonique obsolète.
  En pratique : `DELETE FROM execution_positions WHERE account_id = :id;`
  puis `DELETE FROM broker_positions_snapshots WHERE account_id = :id;`
  (faire de même pour `execution_order_requests`, `execution_broker_orders`,
  `execution_broker_fills`, `execution_position_lots` si vous voulez un
  reset complet).
- **Artefacts ML** (`artifacts/`) : actuellement **partagés entre comptes**
  (étapes 3 → 10 du pipeline sont globales, cf.
  `ihm/pages/pipeline.py::_build_pipeline_scope_alert_lines`). Pas besoin de
  les nettoyer lors d'un changement de compte.
- **Secrets** : la clé API Alpaca du nouveau compte doit être enregistrée
  via la page Settings → vault (cf. `common/config_vault.py`).

**Recommandation** : créez un nouveau `account_id` distinct pour le
remplaçant plutôt que de réutiliser celui de l'ancien — vous gardez l'audit
trail historique et évitez toute purge.

### ❓ 5. Que se passe‑t‑il si je vends manuellement une action (depuis Alpaca ou depuis la page Compte Alpaca de l'IHM) ?

**Côté broker** : l'ordre est exécuté immédiatement et la position
disparaît de votre compte Alpaca.

**Côté Alpha Trade** :

1. **L'ordre N'EST PAS écrit en DB tout de suite.** La vente manuelle
   passe par `AlpacaTradingClient.close_position(symbol)` (cf.
   `ihm/services/alpaca_accounts.py` lignes 48‑58) qui ne touche pas le
   schéma `execution_*`.
2. À la **prochaine réconciliation** (cycle d'exécution suivant ou tick du
   watcher), `snapshot_broker_positions` met à jour
   `broker_positions_snapshots` puis `replace_execution_positions`
   recalcule la position canonique → la ligne disparaît.
3. Les **ordres OCO enfants** (TP/SL) restent posés côté broker **mais
   sans position pour les couvrir** : Alpaca les annulera automatiquement
   dès qu'il détecte qu'il n'y a plus de quantité à protéger (sinon le
   watcher détecte l'incohérence et déclenche un `cancel`).
4. **L'audit trail historique** (parent BUY, enfants OCO posés, fills) reste
   intact en DB ; seule la position courante change.

**Conséquence pratique** : c'est sûr de vendre manuellement, mais l'IHM
peut afficher un état désynchronisé pendant quelques dizaines de secondes,
le temps que les caches Streamlit (`get_live_positions`, `get_execution_orders`)
soient invalidés.

### ❓ 6. Page Compte Alpaca — différence entre « Ordres canoniques d'exécution (DB) » et « Historique des ordres (broker) » ? Une vente depuis « Positions ouvertes (broker) » est‑elle enregistrée en DB ?

**Différence des deux tableaux :**

| Tableau IHM                              | Provenance                                              | Contient quoi ?                                                |
|------------------------------------------|---------------------------------------------------------|------------------------------------------------------------------|
| 📋 Ordres canoniques d'exécution (DB)    | `get_execution_orders(account_id)` → tables `execution_*` | **Tous les ordres générés par Alpha Trade** (parent + enfants OCO), avec lineage `intent_id`, `parent_intent_id`, `run_id`. |
| 🧾 Historique des ordres (broker)        | `AlpacaTradingClient.list_orders(status="all", limit=200)` | **Tous les ordres vus par Alpaca** : générés par Alpha Trade **+** générés manuellement (site web, app mobile, IHM Compte Alpaca, API tierce). |

**Vente depuis « Positions ouvertes (broker) » → DB ?**

- ❌ **Pas immédiatement** : la vente apparaît tout de suite dans
  « Historique des ordres (broker) » mais **PAS** dans
  « Ordres canoniques d'exécution (DB) », car aucun `OrderIntent` parent
  n'a été créé par Alpha Trade pour cette vente.
- ✅ **Indirectement** : la position concernée disparaîtra de
  `execution_positions` au prochain cycle de réconciliation (cf. Q5). Le
  fill broker est *journalisé* dans `broker_positions_snapshots` mais la
  vente elle‑même n'a pas de ligne dans `execution_order_requests`.
- Pour adopter formellement une vente manuelle dans l'audit canonique, il
  faudrait créer un mécanisme « adoption d'ordre orphelin » (non implémenté
  à ce jour ; c'est un trou connu, voir aussi Q8). -- complément d'info: 
  implémenté depuis mai 2026 : le watcher de protections peut désormais créer 
  un `OrderIntent` parent fictif pour adopter une position filled sans lineage (cf. Q8).

### ❓ 7. Si je sélectionne le compte « live » (Alive) dans le dropdown Compte Alpaca, toutes les exécutions seront‑elles automatiquement en live ?

**Non.** Le dropdown ne change que la *cible de lecture* des pages IHM
(`st.session_state["selected_account_id"]`, cf. `ihm/app.py` lignes 101‑107).
Il ne déclenche **aucun ordre** par lui‑même.

Pour qu'une exécution parte en live, il faut **trois conditions cumulées** :

1. `execution_mode == "live"` dans `PipelineLaunchOptions` (sélecteur
   Pipeline → mode d'exécution).
2. **Confirmation explicite** : case « ✅ Confirmer le mode LIVE » + ressaisie
   du label live (`live_confirmed`, cf.
   `ihm/pages/pipeline.py` ligne 388 :
   `execution_locked = ... and not live_confirmed`).
3. **Clic explicite** sur « ▶️ Lancer en arrière‑plan » de l'étape 12.

Tant que ces trois étapes ne sont pas franchies, même avec un compte live
sélectionné, **aucun ordre réel n'est envoyé**. Un bandeau rouge
« 🔴 MODE LIVE ACTIF » s'affiche en haut de la page Pipeline
(cf. `ihm/pages/pipeline.py` lignes 109‑114) dès que les 3 conditions sont
réunies.

### ❓ 8. Si le workflow complet se termine **avant l'ouverture du marché**, les TP/SL ne sont pas posés ? Le watcher rattrape‑t‑il ? Et un achat manuel sur le site Alpaca ?

**Cas 1 — workflow terminé avant ouverture :**

- L'étape 12 envoie le **parent BUY** au broker. Hors session, l'ordre reste
  en `pending` / `accepted` (selon TIF) et **n'est pas filled**.
- Tant qu'aucun fill, `execution_engine/children_submission.py` **ne pose
  pas** les enfants TP/SL (logique « on‑fill »).
- À l'ouverture, le BUY se remplit. **Si rien d'autre ne tourne, les TP/SL
  ne seront jamais posés** → vous serez nu sur cette ligne jusqu'au
  prochain cycle d'exécution.

**Solution = lancer le watcher** :

- Filet de sécurité : `execution_engine/protection_watcher.py`
  (`_arm_missing_protections`, lignes 330‑423). Toutes les `service_interval`
  secondes (30 s par défaut), il :
  1. interroge le broker pour lister les positions filled,
  2. les compare aux enfants OCO présents dans
     `execution_order_requests`,
  3. pour chaque position **sans TP ni SL armés**, reconstruit un
     `OrderIntent` parent à partir des données DB (`parent_intent_id`,
     prix d'entrée, ATR, etc.) et soumet TP + initial_stop (ou trailing
     en fallback).
- Vous pouvez le lancer :
  - depuis la **page Pipeline** (panneau 12.bis) avec les boutons
    `▶️ Run watcher once` ou `🔁 Démarrer service local` (ajoutés en mai 2026),
  - depuis **Supervision Ops** (mêmes boutons),
  - en CLI : `python run_execution_protection_watch.py --mode service --account <id>`,
  - via Task Scheduler / NSSM (scripts PowerShell `scripts/windows/`).

**Cas 2 — achat manuel sur le site Alpaca :**

- ⚠️ **Le watcher ne peut PAS armer automatiquement** un achat manuel.
- Raison technique : `_arm_missing_protections` se branche sur la
  ligne `parent_intent_id` (cf. `protection_watcher.py` ligne 354 :
  `intent_id=str(row["parent_intent_id"])`). Or un achat passé directement
  sur Alpaca **n'a pas d'`OrderIntent` parent en DB** → la requête de jointure
  ne le voit pas, le watcher ne sait pas quel TP/SL il *devrait* poser
  (pas de stop ATR de référence, pas de paramètre `take_profit_pct` calé sur
  un signal).
- ✅ **Workaround manuel** :
  1. Soit posez vous‑même les ordres OCO depuis l'interface Alpaca
     (Bracket order).
  2. Soit créez un `OrderIntent` parent fictif côté Alpha Trade reflétant
     l'achat manuel (pas d'IHM dédiée aujourd'hui ; il faut passer par un
     script).
- 💡 **Évolution possible** (non implémentée) : ajouter une routine
  d'« adoption d'orphelin » qui crée automatiquement un `OrderIntent`
  parent à partir d'un fill broker sans lineage, avec des TP/SL par défaut
  configurables. (réalisé depuis mai 2026 : cf. `protection_watcher.py` ligne 370 : 
  si un fill est détecté sans parent_intent_id, le watcher peut créer un intent 
  parent fictif pour lui permettre d'armer les protections).

**Règle d'or opérationnelle** : si vous lancez le pipeline avant l'ouverture,
**lancez aussi le service local du watcher** (ou planifiez un Task Scheduler
qui se déclenche à l'ouverture du marché US, 15 h 30 Paris). C'est le seul
moyen de garantir que vos lignes seront protégées dès qu'elles sont
remplies.

---

## Pour aller plus loin

- Dépannage : [51_depannage.md](51_depannage.md)
- Sécurité : [52_securite_et_argent_reel.md](52_securite_et_argent_reel.md)
- Glossaire : [30_glossaire_financier.md](30_glossaire_financier.md)

