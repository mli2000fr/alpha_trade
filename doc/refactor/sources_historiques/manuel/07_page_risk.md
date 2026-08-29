# 7. Page ⚖️ Risk — gestion du risque

## À quoi sert cette page

Voir les **décisions de risque** : combien acheter de chaque ligne, où
placer le stop-loss / take-profit, quels candidats sont rejetés et pourquoi.

## Concepts clés

### Risk per trade (`risk_per_trade_pct`)

Le **% du capital** que vous acceptez de perdre par trade si le stop est
touché. Standard : **1 %** (ou 1.5 % en micro-compte). Sur 2 000 €, 1.5 % =
**30 €** de perte max par trade.

### Sizing par stop

Plutôt que d'acheter « X € par ligne », on calcule la quantité d'actions
telle que `(prix d'entrée - stop) × quantité = montant_risqué`.

Exemple : action à 50 $, stop à 47 $ (3 $ de risque), montant_risqué 30 €
(~32 $) → quantité ≈ 10 actions.

### Stop-loss

Ordre automatique de vente déclenché si le cours touche un seuil bas. Sa
fonction : limiter la perte. **Sans stop-loss, vous ne devriez jamais
trader.**

### Take-profit & trailing stop

- **Take-profit** : ordre automatique de vente à un seuil haut, pour
  empocher le gain.
- **Trailing stop** : stop qui « monte » avec le cours, sécurisant le gain
  en laissant courir.

### R-multiple

Unité de mesure : 1R = montant risqué initial. Un trade qui rapporte 3R =
3× le risque. La métrique cible long terme : **espérance > 0.3R / trade**.

## Lecture du tableau

| Colonne | Signification |
|---|---|
| `symbol` | Ticker |
| `decision` | `long` / `flat` / `rejected` |
| `target_quantity` | Nb d'actions à détenir |
| `target_notional` | Valeur USD cible |
| `entry_price` | Prix d'entrée prévu |
| `stop_loss` | Prix du stop |
| `take_profit` | Prix du TP |
| `conviction_score` | Score combiné (technique + ML + sentiment) |
| `rejection_reason` | Si `rejected` : pourquoi |

## Raisons de rejet courantes

| `rejection_reason` | Explication |
|---|---|
| `sector_cap_exceeded` | Trop de positions dans le même secteur |
| `correlation_too_high` | Trop corrélé à une autre ligne déjà retenue |
| `notional_below_min` | Ticket calculé < `risk_min_position_notional` |
| `max_positions_reached` | Vous avez atteint `risk_max_positions` |
| `no_stop_distance` | Stop trop proche du prix d'entrée (impossible à placer) |

## Contraintes appliquées

Encart en haut de page :
- **Capital total** : equity du compte
- **Capital disponible** : cash non investi
- **Positions ouvertes / max** : ex. 2 / 3
- **Exposition par secteur** : pourcentages

## Modifier les paramètres risk

Page **⚙️ Paramètres / Santé** → onglet « Risk ». Tous les seuils sont
explicités. Ils sont automatiquement initialisés depuis votre **preset de
capital** mais vous pouvez les surcharger.

## Pour un micro-compte 2 000 €

Le preset `capital_0_2000` impose :
- 3 positions max (concentration assumée),
- 1.5 % de risque par trade (~30 €),
- 200 USD minimum par ticket (sous ce seuil les frais mangent l'alpha).

Voir [20_gestion_petit_capital_2000eur.md](20_gestion_petit_capital_2000eur.md).

## Pièges courants

- ❌ Augmenter `risk_per_trade_pct` à 5 % « pour gagner plus » → vous
  pouvez perdre 50 % du capital en 10 trades.
- ❌ Désactiver les stops « pour ne pas se faire sortir » → ruine assurée.
- ❌ Ignorer `rejection_reason: correlation_too_high` → vous concentrez le
  risque sans le savoir.

## Pour aller plus loin

- Doc technique : [doc/risk_management.md](../backup/risk_management.md).
- Glossaire : [30_glossaire_financier.md](30_glossaire_financier.md).

