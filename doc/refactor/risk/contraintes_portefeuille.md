# Contraintes et optimisation du portefeuille

Retour : [références Risk](README.md)

Les contraintes portent sur portefeuille existant + deltas. Gross somme les absolus, net soustrait shorts. Caps : position, secteur, nombre, sleeves, gross/net, corrélation, facteurs, capacité et buying power.

`concentration_constraints.py` applique les limites directes. `correlation_filter.py` utilise la matrice de rendements. `factor_model.py` construit expositions, rendements facteurs, covariance EWMA, décomposition systématique/spécifique et contraintes implicites. Les historiques insuffisants doivent dégrader/écarter selon politique, pas produire une corrélation nulle inventée.

`PortfolioOptimizer` inclut holdings, no-trade bands, turnover costs et MCTR. Il peut réduire une taille lorsque permis. Après chaque acceptation, il recalcule les budgets. Le résultat contient poids cibles, rejets, coûts/turnover et diagnostics.

`PortfolioBuilder` applique scoring de régime, concentration et neutralité nette puis crée les entrées. L'ordre est déterministe. Tests : position préexistante, secteur inconnu, côtés opposés, caps serrés, fractional et égalités de rang.

