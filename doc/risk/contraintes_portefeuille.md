# Contraintes et optimisation du portefeuille

Retour : [références Risk](README.md)

Les contraintes portent sur portefeuille existant + deltas. Gross somme les absolus, net soustrait shorts. Caps : position, secteur, nombre, sleeves, gross/net, corrélation, facteurs, capacité et buying power.

`concentration_constraints.py` applique les limites directes. `correlation_filter.py` utilise la matrice de rendements. `factor_model.py` construit expositions, rendements facteurs, covariance EWMA, décomposition systématique/spécifique et contraintes implicites. Les historiques insuffisants doivent dégrader/écarter selon politique, pas produire une corrélation nulle inventée.

`PortfolioOptimizer` inclut holdings, no-trade bands, turnover costs et MCTR. Il peut réduire une taille lorsque permis. Après chaque acceptation, il recalcule les budgets. Le résultat contient poids cibles, rejets, coûts/turnover et diagnostics.

`PortfolioBuilder` applique scoring de régime, concentration et neutralité nette puis crée les entrées. L'ordre est déterministe. Tests : position préexistante, secteur inconnu, côtés opposés, caps serrés, fractional et égalités de rang.

## Holdings existants

`HoldingSnapshot` contient côté, quantité, prix d'entrée/courant, classifications, PnL latent et ordre ouvert. `notional` est absolu ; `signed_notional` est positif long, négatif short. Le constructeur refuse un côté hors long/short.

L'optimiseur initialise gross, net, long gross et short gross depuis ces holdings. Une position avec ordre ouvert bloque un nouveau candidat du même symbole afin d'éviter des deltas concurrents.

## Tri et données candidates

Chaque candidat doit fournir symbol, side, edge, proposed quantity, price et éventuellement secteur/ADV. Les candidats sont triés par edge décroissant. Prix ou quantité <= 0 est rejeté. Un symbole déjà présent est traité comme nouvelle cible/delta, pas comme nouvelle position indépendante.

## Contraintes signées

Pour tester un candidat, l'optimiseur retire d'abord la contribution actuelle du symbole, puis ajoute la cible proposée. Il contrôle : nombre de positions, poids individuel, gross, net absolu, budget long et budget short CP-V2. Si la taille complète viole une limite, il peut calculer une quantité réduite compatible au lieu d'un rejet binaire.

Le nombre de positions doit distinguer remplacement d'une holding et ajout. Gross utilise absolus ; net conserve le signe. Un short réduit le net mais augmente le gross.

## No-trade bands

`NoTradeBand` possède bornes basse/haute de 20 % et notionnel minimal 250 par défaut. Si la quantité cible reste dans la bande autour de l'existant, aucun trade n'est généré. Même hors bande, un delta sous le minimum peut être ignoré.

Cette décision réduit turnover mais signifie que la position réelle diffère légèrement de la cible théorique. Le report doit conserver la raison et la quantité maintenue.

## Coûts de turnover

`TurnoverCosts` combine commission, half-spread et impact par participation ADV. Le coût s'applique au delta notionnel, pas à toute la position. Le paramètre `total_one_way_bps` fournit la base ; la participation ajoute un coût si ADV valide.

L'edge net du portefeuille doit être interprété après ce coût. Une rotation qui améliore marginalement le score mais coûte davantage doit rester dans la no-trade band ou être rejetée.

## MCTR

`compute_mctr` reçoit poids signés, covariance et ordre des symboles. Il calcule variance `w'Σw`, risque racine, marginal `(Σw)/σ` et contribution `w*(Σw)`. Une variance <= 0 renvoie une décomposition sans risque calculable. Le pire contributeur est la plus grande contribution positive.

L'ordre de covariance doit exactement correspondre à `symbols`. Une matrice mal alignée donne un résultat valide numériquement mais faux économiquement ; conserver le mapping et le tester.

## Résultat

`OptimizationResult` contient target weights/quantities, trades deltas, edge, risque, turnover %, coût, rejected, reduced, MCTR et audit trail. `to_dict` résume sans supprimer les raisons.

## Contraintes de concentration

Les contraintes directes couvrent position, secteur et regroupements disponibles. Elles doivent inclure holdings et nouveaux candidats. Un secteur `None` ne doit pas permettre un contournement : il appartient à une catégorie unknown ou suit la politique explicite.

## Corrélation et facteurs

La corrélation empirique utilise une fenêtre de rendements avant cutoff. `factor_model.py` construit expositions cross-sectionnelles, rendements facteurs et covariance EWMA avec half-life. Il décompose risque systématique/spécifique et peut filtrer les pires offenders.

Une feature facteur absente ou une covariance singulière doit produire fallback/diagnostic. Ne jamais utiliser des rendements futurs pour améliorer la matrice du jour.

## Neutralité nette

`PortfolioBuilder._enforce_net_exposure_neutrality` adapte la sélection selon les limites. « Neutralité » ne signifie pas forcément net zéro : elle suit les caps configurés et la disponibilité de candidats shorts. La réduction doit préserver les raisons/rangs.

## Exemple signé

Equity 100k : long 30k et short 10k donnent gross 40 %, net 20 %. Ajouter long 20k donne gross 60 %, net 40 %. Ajouter short 20k donne gross 60 %, net 0 %. Le second portefeuille n'est pas moins gross-riské malgré net nul.

## Fallback conservateur

Si covariance/facteurs indisponibles, l'optimiseur peut continuer avec contraintes simples seulement si la politique l'autorise et l'annonce. Un échec d'equity ou de positions existantes n'est pas un fallback admissible en live.

## Audit et diagnostic

Pour chaque candidat conserver edge, taille proposée, cap actif, taille réduite/rejet, coûts et totals avant/après. Diagnostiquer un portefeuille vide via rejected map ; un turnover nul via no-trade reasons ; un gross inattendu via holdings signés.

## Tests

Holdings avec ordre ouvert, remplacement même symbole, caps long/short, gross/net, réduction partielle, band boundaries, minimum notionnel, coût ADV, covariance vide/singulière/alignment, déterminisme et secteur inconnu.
