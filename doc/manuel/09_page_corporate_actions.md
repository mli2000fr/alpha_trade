# 9. Page 📑 Corporate Actions — dividendes, splits, etc.

## À quoi sert cette page

Voir les **événements corporate** (dividendes, splits, fusions, spin-offs)
qui touchent vos positions, et leur application dans votre cash ledger.

## Concepts essentiels

| Terme | Définition simple |
|---|---|
| **Dividende** | L'entreprise vous verse une part de ses bénéfices (ex. 0.50 $/action) |
| **Split** | L'action est divisée (ex. split 2-for-1 : 100 actions → 200 actions, prix divisé par 2) |
| **Reverse split** | L'inverse (regroupement) |
| **Ex-date** | Date à partir de laquelle l'action se traite « ex-dividende » (sans le droit au dividende à venir) |
| **Pay-date** | Date du versement effectif |

## Lecture des sections

### Section 1 — Dernière synchronisation

Date / heure du dernier `corporate_actions sync` (récupération depuis le
provider Alpaca) et résumé.

### Section 2 — Application

Date / heure du dernier `corporate_actions apply` (mise à jour de votre
ledger).

### Section 3 — Workflow (sync + apply)

Historique des runs combinés.

## Quand lancer

- **Sync** : 1×/semaine ou avant chaque date de dividende attendue.
- **Apply** : juste après le sync.

> 💡 Le **pipeline complet** (page 🔄 Pipeline) lance déjà ces 2 étapes.
> Vous n'avez normalement rien à faire ici.

## Lancement manuel

Page **🔄 Pipeline** → **Centre d'exécution avancé** → bloc « Corporate
Actions ». Options :
- `corporate_actions_skip_existing` : ignorer les events déjà connus (perf).
- `corporate_actions_use_custom_window` : limiter à une fenêtre (ex. 7
  derniers jours).
- `corporate_actions_batch_size` : nb de symboles par appel (défaut 25).

## Pièges courants

- ❌ Oublier de lancer pendant 1 mois → votre cash divergera des relevés
  Alpaca.
- ❌ Activer `skip_existing` puis se demander pourquoi un nouveau dividende
  manque (les events « pending » du provider ne sont pas re-vérifiés).

## Pour aller plus loin

- Doc technique : [doc/corporate_actions.md](../corporate_actions.md).
- Glossaire : [30_glossaire_financier.md](30_glossaire_financier.md).

