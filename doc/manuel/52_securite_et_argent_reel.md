# 52. Sécurité & passage en argent réel — checklist obligatoire

> ⚠️ **Lisez ce document en entier avant tout passage en mode `live`.**
> Pas de raccourci. Pas d'exception.

## ⚖️ Avertissement légal et financier

- Cette application est **un outil**. Vous restez **seul responsable** de
  vos décisions d'investissement.
- Les performances passées (backtest) **ne préjugent pas** des
  performances futures.
- Le trading boursier comporte un **risque de perte totale** du capital.
- Les auteurs déclinent toute responsabilité en cas de pertes financières.

## 🔒 Sécurité technique

### Avant le live

- [ ] Sauvegarde DB faite : `mysqldump alpha_trade > backup_YYYYMMDD.sql`.
- [ ] `.env` non versionné dans Git (vérifiez `.gitignore`).
- [ ] Mots de passe **différents** entre paper et live.
- [ ] Activé l'authentification 2FA sur le compte Alpaca.
- [ ] Compte bancaire associé à Alpaca **vérifié**.
- [ ] Adresse mail de notification Alpaca **active**.
- [ ] Téléphone configuré pour les alertes broker.
- [ ] Test : recevoir un email Alpaca de confirmation d'ordre paper.
- [ ] Antivirus à jour, machine non partagée.
- [ ] Watcher de protection 💚 et stable depuis 7 jours minimum.

## 📊 Validation stratégique

### Pré-requis backtest (≥ 3 ans)

- [ ] Sharpe ratio ≥ 1.0
- [ ] Max drawdown ≤ 20 %
- [ ] Nombre de trades ≥ 100
- [ ] Espérance positive après frais (commission 25 bps + slippage 15 bps)
- [ ] Walk-forward activé
- [ ] Résultats reproductibles (mêmes paramètres → mêmes nombres)

### Pré-requis paper trading (≥ 3 mois consécutifs)

- [ ] P&L net positif ou neutre sur 3 mois (les 3 derniers).
- [ ] Aucun ordre rejeté pour erreur de configuration.
- [ ] Aucune divergence DB ↔ broker (page réconciliation = 🟢).
- [ ] Watcher 100 % uptime sur la période.
- [ ] Vous comprenez **chaque** rejet de la page Risk.
- [ ] Vous comprenez **chaque** trade exécuté (raison d'entrée et de sortie).

## 💰 Validation financière personnelle

- [ ] Le capital investi représente **moins de 5 %** de votre patrimoine.
- [ ] Vous avez une **épargne de précaution** de 6 mois de dépenses, indépendante.
- [ ] Vous **n'avez pas** de crédit conso à taux > 5 %.
- [ ] Vous pouvez **perdre 100 %** du capital investi sans impact sur votre vie.
- [ ] Vous n'avez **emprunté à personne** pour investir.
- [ ] Vous avez **prévenu votre conjoint(e)** si applicable.

## 🇫🇷 Validation réglementaire (France)

- [ ] Compte étranger Alpaca déclaré (formulaire **3916** annuel).
- [ ] Vous savez que les plus-values sont imposées à **30 %** (PFU).
- [ ] Vous savez que les dividendes US ont une retenue à la source de **15 %**
      (récupérable via le formulaire W-8BEN signé chez Alpaca).
- [ ] Vous avez consulté un comptable si nécessaire.

## 🧠 Validation psychologique

- [ ] Vous êtes prêt(e) à voir **-15 %** de drawdown sans paniquer.
- [ ] Vous **n'allez pas** modifier la stratégie après une mauvaise série.
- [ ] Vous **n'allez pas** ajouter du capital après une bonne série.
- [ ] Vous tiendrez un **journal de trading** (raison, leçon).
- [ ] Vous accepterez de **suspendre** la stratégie si elle décroche.

## 🚀 Procédure de bascule live

### Étape 1 — Capital très réduit

1. Créez un **second compte Alpaca live** (en plus du paper).
2. Créditez-le de **500 € seulement** au début.
3. Configurez les credentials dans le `.env`.
4. Page Settings → mode → `live`.
5. Page Comptes Alpaca → vérifiez que le bon compte est sélectionné.
6. **Arrêtez le pipeline. Allez prendre un café. Revenez.**
7. Lancez UNIQUEMENT Execution.
8. Surveillez les ordres en temps réel.

### Étape 2 — Premier mois

- Limitez à 1 position simultanée.
- Vérifiez P&L chaque soir.
- Notez chaque trade dans votre journal.

### Étape 3 — Montée progressive

| Mois | Capital live | Conditions |
|---|---|---|
| M+1 | 500 € | premier mois |
| M+2 | 1 000 € | si M+1 ≥ -2 % |
| M+3 | 1 500 € | si M+2 ≥ 0 % cumulé |
| M+4 | 2 000 € | si M+3 ≥ 0 % cumulé |

## 🛑 Quand arrêter immédiatement

- Drawdown > 25 % depuis le début.
- 5 trades perdants consécutifs.
- Divergence DB ↔ broker non résolue en 24h.
- Watcher tombé > 1h en pleine séance.
- Doute sur la configuration → repassez en paper.

## 🆘 En cas de panique

1. **Kill switch** : annuler tous les ordres ouverts :
   ```powershell
   python -m execution_engine cancel-all `
     --account <votre_account_id> `
     --confirm-account <votre_account_id> `
     --broker-mode live `
     --reason "panique - investigation"
   ```
2. Connectez-vous à <https://app.alpaca.markets> directement → vendez
   manuellement si besoin.
3. Coupez le watcher.
4. Repassez en paper, investiguez, re-validez avant de revenir en live.

## ✅ Signature symbolique

Avant le 1er ordre live, écrivez sur papier :

> « Je, [votre nom], déclare avoir lu et compris les risques. Je
> n'investis que [montant] que je peux perdre. Je m'engage à respecter
> les règles d'or de [40_workflow_type_swing_2000eur.md](40_workflow_type_swing_2000eur.md) §
> Règles d'or. »
>
> Date : [...]   Signature : [...]

Cela peut sembler ridicule. Ça ne l'est pas.

## Pour aller plus loin

- [doc/pre_live_checklist.md](../pre_live_checklist.md) — checklist
  technique complète (audience opérateur expert).
- [doc/runbook_24_7.md](../runbook_24_7.md).

