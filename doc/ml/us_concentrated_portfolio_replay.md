# Portefeuille stateful des variantes de sorties US

Qualification du 7 octobre 2026. **Adaptateur de recherche, pas activation live
ni certification de parité complète avec PortfolioBuilder.**

Nouvelle exigence utilisateur : véritable backtest en parité live. Voir
[l'audit de raccordement complet et ses prérequis](us_concentrated_live_parity_audit.md).
Les résultats ci-dessous ne satisfont pas à eux seuls cette exigence.

## Objet et périmètre

Raccorder les sorties figées de [l'expérience précédente](us_concentrated_exit_variants.md)
à un compte unique : capital occupé, positions simultanées, quantité réellement
finançable et frais. Les anciennes tapes à une action par candidat n'étaient
pas un portefeuille et ne permettaient pas ce calcul.

Le nouveau point d'entrée est
`scripts/research/us_concentrated_portfolio.py`. Aucun modèle n'est entraîné,
aucune donnée SQL n'est écrite et aucun paramètre live n'est modifié.

Les archives utilisées sont celles de `prepare-20261006-v1`,
`tapes-history-20261006-v1`, `exit-variants-history-20261007-v1` et du contrat
`contract-validation-20261006-v3`, sous
`artifacts/research/us_concentrated_replay/`. Les empreintes des sources et
des tapes sont vérifiées avant le calcul. La correction de volume BAND reste
un overlay local de recherche, non une correction PIT en production.

## Portefeuille et ordre des opérations

Chaque variante repart **une seule fois** de 4 000 USD au 1er janvier 2025.
Elle conserve ensuite son propre cash et ses positions jusqu'au 30 septembre
2026. Aucun réinitialisation quotidienne ou par candidat.

1. Régler les éventuels flux en attente.
2. Valoriser les positions déjà détenues à l'ouverture observée du jour.
3. Appliquer le breaker de drawdown et son allocation dégradée.
4. Retenir les candidats classés Oracle, hors positions déjà détenues et dans
   la limite des places disponibles.
5. Calculer les quantités, puis réutiliser les fonctions natives d'ouverture.
6. Exécuter les sorties explicites de la variante avec le ledger natif.
7. Comptabiliser les intérêts éventuels et valoriser à la clôture.

La clôture du jour n'est **pas** utilisée pour financer ou dimensionner une
entrée prise à l'ouverture du même jour. C'est une différence volontaire
avec l'ordonnancement observé dans la boucle quotidienne générique du moteur ;
le moteur partagé n'a pas été modifié pendant ce raccordement.

Les ouvertures sont traitées avant **toutes** les sorties du jour : une vente
du jour, même sur gap, ne finance pas rétroactivement l'achat à l'open.
C'est une convention conservatrice figée, pas une reconstruction tick par tick.

## Quantités et contraintes

La proposition vient du véritable `PositionSizer` de l'application :

`quantité ATR = equity disponible × risque par trade × multiplicateur / (2,5 × ATR20)`.

L'ATR est recalculé avec `BacktestEngine._compute_atr`, exactement comme pour
l'assemblage unitaire, à la date de décision J. Vingt observations OHLC sont
exigées. L'entrée a lieu à J+1 ; son open n'entre pas dans l'ATR de J.

Le profil figé est `capital_2001_5000`, dont les valeurs résolues sont conservées
dans chaque fichier `*-config.json`, notamment :

- risque par trade : 1,25 % de l'equity courante ;
- maximum huit positions, 25 % par position, exposition brute maximale 100 % ;
- fractions d'action autorisées ; minimum notionnel 155 USD ;
- cible de volatilité annuelle 13 %, calculée sur les rendements EOD antérieurs ;
- breaker à 15 % et reprise à 0,92, avec allocation dégradée ;
- aucune fermeture forcée implicite par le breaker : les sorties restent figées.

La quantité proposée est plafonnée par les budgets de cash/coûts, position,
secteur, exposition brute et side, et ADV si cette contrainte est configurée.
Les quantités sont approuvées avant ouverture ; toute modification silencieuse
par le moteur déclenche une erreur. Les rejets natifs restent enregistrés.

### Réserve sectorielle importante

Le secteur historique PIT n'est pas qualifié. Tous les symboles sont donc placés
dans **un seul bucket conservateur `UNQUALIFIED_PIT_SECTOR`, plafonné à 50 %**.
On n'invente ni secteurs historiques ni un secteur différent par symbole.
Ce choix borne fortement le déploiement du capital et interdit de présenter
ces résultats comme une parité complète avec le portefeuille réel/live.

Le contexte macro historique n'est pas rejoué. Les probabilités directionnelles
ne sont pas inventées : les côtés LONG sont forcés pour cette expérience
d'amplitude, indépendamment d'un modèle directionnel.

## Sorties, gaps et coûts

Les quatre variantes conservent leurs dates/prix/reasons explicites. Le stop
initial, le TP et le trailing ne sont pas recalibrés en fonction des pertes.
L'expiration est vingt séances **après l'entrée à J+1**, pas vingt séances
après le signal. Le gap traversant le stop d'une position détenue sort à l'open ;
un gap favorable au TP utilise la limite conservatrice, avant une ambiguïté
intraday ultérieure. L'expiration utilise le close ; la liquidation terminale
reste une hypothèse pour les horizons tronqués.

Les métadonnées de protection historiques conservées ne signifient pas qu'un
ordre TP désactivé par une variante aurait été envoyé à un courtier : ce sont
les sorties explicites qui pilotent le replay. Les anciennes traces de watcher
ne constituent pas une certification de transactions/OCO réels.

Le ledger natif applique commission, spread et slippage **aux deux jambes**,
sans déplacer une deuxième fois le prix explicite de sortie. Le sizing réserve
les coûts d'entrée. Les intérêts de marge restent natifs ; ils sont nuls dans
les résultats ci-dessous. Le contrat rejette les modes non pris en charge :
commission tiered, surcharge d'impact volume, round-trip forcé, multiplicateur
d'exposition, offset d'entrée ou exécution différente de `next_open`.

Une réconciliation finale impose :

`equity finale = 4 000 + somme PnL nets des trades − intérêts de marge`.

Elle passe à une précision meilleure que 10⁻⁶ USD pour les quatre variantes.

## Validation et résultats exploratoires

**66 tests ciblés passent**, incluant dix tests propres au raccordement :
quantités ATR, cash/frais, plafond sectoriel, doublons, blocage d'un chemin
réservé, invariance du sizing à une clôture future et raccordement bout en bout
du résolveur de gap au ledger. Rapport : `portfolio-tests-20261007.xml`.
Ce ne sont pas tous les tests du dépôt et ce n'est pas une preuve de fills réels.

### Dix meilleurs scores Oracle par jour

`ORACLE_TOP10` signifie **dix titres**, pas 10 % de l'univers. Archive retenue :
`portfolio-top10-20261007-v5/report.json` (versions précédentes conservées).

| Variante | Trades | Equity finale USD | Rendement net | Frais cumulés USD |
|---|---:|---:|---:|---:|
| TP + trailing, sans expiration | 74 | 3 596,79 | −10,08 % | 29,08 |
| TP + trailing, expiration après 20 séances | 77 | 3 623,30 | −9,42 % | 30,05 |
| Sans TP, stop fixe, expiration après 20 séances | 28 | 3 527,59 | −11,81 % | 9,70 |
| Sans TP, trailing, expiration après 20 séances | 38 | 3 753,02 | −6,17 % | 12,97 |

Tous atteignent au plus huit positions. L'exposition brute moyenne EOD sur
la période complète est faible (4,91–5,97 %) : bucket sectoriel conservateur,
positions occupées, minimum notionnel et mécanisme de drawdown limitent les
entrées. **Ne pas désactiver ces contraintes après observation des résultats.**
Le breaker limite les nouvelles entrées ; ce n'est pas une garantie que le
drawdown maximal reste sous 15 %, puisque les positions détenues peuvent perdre.

La version sans TP avec trailing perd moins ici, mais reste perdante. Cela ne
prouve pas qu'elle maximise les gains, ni qu'elle est déployable.

### TOP20 % Oracle

Archive : `portfolio-top20-20261007-v3/report.json`. Les quatre variantes ont
terminé le replay exploratoire, sans certification complète ni promotion.

| Variante | Trades | Equity finale USD | Rendement net | Frais cumulés USD |
|---|---:|---:|---:|---:|
| TP + trailing, sans expiration | 75 | 3 577,16 | −10,57 % | 29,42 |
| TP + trailing, expiration après 20 séances | 75 | 3 566,04 | −10,85 % | 29,56 |
| Sans TP, stop fixe, expiration après 20 séances | 30 | 3 526,13 | −11,85 % | 10,21 |
| Sans TP, trailing, expiration après 20 séances | 38 | 3 671,71 | −8,21 % | 13,13 |

Le TOP20 % désigne le réservoir de candidats, pas une obligation d'acheter tous
ces titres : huit positions au maximum, cash, minimum notionnel et overlays
continuent de s'appliquer. L'exposition brute moyenne EOD reste entre 4,98 % et
5,88 %. Ces pertes ne démontrent aucun avantage économique à promouvoir.

### Qualification LBRDK et ordre du contrôle

Le candidat LBRDK à l'exécution du 7 juillet 2026 rencontre une barre du
20 juillet à volume nul, OHLC tous égaux à 30,845 ; cette répétition continue
ensuite dans l'archive. `is_filled=0` ne suffit donc pas à qualifier cette barre.
Le dernier jour à volume positif précédant cette anomalie est le 17 juillet.
La cause (événement sur titre, radiation, défaut fournisseur ou autre) n'est
pas établie par ce seul contrôle. Il faut une preuve de prix et/ou de traitement
de l'événement avant de résoudre le chemin.

Les premiers essais v1/v2 bloquaient le replay dès la sélection de LBRDK, avant
de vérifier sa quantité. Ce contrôle était trop précoce : dans le portefeuille
final, LBRDK ne reçoit aucune quantité le 7 juillet (raison
`SIZING_OR_PORTFOLIO_CAP`). Par exemple, pour la variante courante, equity
3 577,16 USD, proposition ATR 9,687635 actions, facteur drawdown 0,1 et quantité
approuvée zéro après seuil notionnel. La qualité de ses prix futurs n'a pas
servi à calculer ce refus d'entrée.

Le contrôle du chemin intervient désormais après le sizing fondé sur J : un candidat
non finançable est rejeté pour ce motif connu à l'entrée, sans consulter son
statut futur. Une quantité positive impose ensuite un chemin qualifié.
On ne retire pas rétroactivement LBRDK pour afficher un PnL favorable, et on ne
remplace pas le candidat par le suivant. Un chemin non qualifié avec quantité
positive bloque la variante entière, au lieu de devenir un filtre informé par
le futur. Cette distinction est couverte par un test de non-régression.

## Réexécution et suites autorisées

```powershell
python -m scripts.research.us_concentrated_portfolio --policy ORACLE_TOP10 --output artifacts/research/us_concentrated_replay/portfolio-top10-NOUVEAU_RUN
python -m scripts.research.us_concentrated_portfolio --policy ORACLE_TOP20 --output artifacts/research/us_concentrated_replay/portfolio-top20-NOUVEAU_RUN
```

Choisir un nouveau répertoire pour préserver les rapports existants. Le calcul
est local, sans entraînement ni SQL. `protocol.json`, les configurations,
`progress.json`, `report.json` et les parquets trades/approvals/exposure/events
permettent de retracer le résultat. En cas de blocage, le rapport en donne la
cause ; aucun portefeuille partiel n'est présenté comme résultat complet.

Prochaine qualification : résoudre la preuve LBRDK, puis les secteurs et le
contexte historique, tradabilité/identités/actions sur titres et lineage des
scores. Une comparaison économique certifiée et une intégration live restent
distinctes de ce premier raccordement exploratoire.
