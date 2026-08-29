# Fiscalité — détecteur de wash sale

Retour : [reporting, lineage et formal](reporting_lineage_formal.md)

## Périmètre

`tax/wash_sale.py` implémente une approximation auditable de la règle américaine des 30 jours. Une vente à perte est marquée si une acquisition du même symbole existe entre vente−30 jours et vente+30 jours. La perte non déductible est reportée sur le lot de remplacement choisi.

Le module ne produit pas de liasse, ne contacte pas le broker et ne modifie pas les lots persistés. Il retourne un `WashSaleReport`.

## Entrées et calcul

`Lot` contient id, symbole, date, quantité signée et prix. Positif = acquisition, négatif = disposition. Les lots doivent déjà intégrer corporate actions.

`realized_pnl_per_sale` est recommandé : un PnL négatif identifie la perte. Sans mapping, le code compare la vente au prix moyen pondéré de tous les achats antérieurs/contemporains et calcule `(avg-sale_price) × abs(qty)`. Cette heuristique peut diverger du FIFO fiscal.

Les remplacements du même symbole dans la fenêtre inclusive sont triés par distance à la vente puis date. Le premier est retenu. Plusieurs ventes peuvent cumuler leur report sur le même lot.

## Sortie

`WashSaleAdjustment` conserve ids de vente/remplacement, symbole, perte, dates. `total_disallowed_loss` somme les ajustements. `adjusted_cost_basis` contient l’ajustement monétaire à ajouter, pas le basis final complet.

## Limites

- « substantially identical » réduit au même symbole ;
- aucune option, IRA, comptes liés ou conjoint ;
- pas de short-against-the-box ;
- pas d’allocation partielle selon quantités ;
- un seul remplacement par vente ;
- CA supposées appliquées ;
- aucune validation juridiction/devise ;
- heuristique imprécise sans PnL réalisé.

Une validation broker et professionnelle reste nécessaire.

## Tests

Tester J−30/J+30 et hors fenêtre, vente gagnante, PnL absent, plusieurs remplacements, égalité de distance, plusieurs ventes, autre symbole, fractions et split déjà appliqué.

