# Filtre net après Oracle parcours — protocole actif TP15/SL7

> L'utilisateur a autorisé la suite après cette préparation : voir
> [l'exécution, les contrôles et le bilan](oracle_path_profit_filter_tp15_sl7_resultats_20261015.md).
> Les mentions « pas encore calculé » de cette fiche décrivent son état initial.

Le 15 octobre 2026, l'utilisateur remplace **TP10/SL10 par TP15/SL7** avant tout
calcul de nouvelles cibles, entraînement ou replay économique. Ce choix n'est
pas le résultat d'une optimisation de cette expérience : aucun gain nouveau
n'a été mesuré. Les anciens résultats TP10/SL10 ne sont pas réétiquetés.

## Contrat actif

- LONG, **TP +15 %, SL −7 %** du fill ; sans trailing.
- Les **20 premiers titres** de l'Oracle parcours CatBoost, rang d'origine.
- Entrée open J+1, garde de gap 3 %, vingt séances détenues, expiration open J+21.
- Disponibilité des labels J+22 ; mêmes règles de qualité, de gaps et collision
  conservatrice. Un stop ne garantit pas une perte maximale de 7 % lors d'un gap.
- Cible : résultat positif net du trade de référence, y compris une expiration
  bénéficiaire sans TP. Coûts natifs et financement de référence inchangés ;
  ce résultat unitaire n'est pas le PnL exact d'un portefeuille.
- Même ticket de référence de 1 600 USD à J, mêmes 24 features, petit LightGBM,
  seuil 0,50, mêmes périodes purgées et gates de validation.
- Futurs replays : 4 000 USD par an, levier maximal x2, cap position 40 %, formule
  de risque `0,4 × SL` soit **2,8 % avant gardes natives** au lieu de 4 %.
  Ce n'est ni une promesse de risque effectivement consommé ni la taille finale.

Le témoin sans filtre **et** le portefeuille filtré devront tous deux employer
TP15/SL7. **Une nouvelle baseline TP15/SL7 est nécessaire** : les capitaux et
trades TP10/SL10 du point 1 ne sont pas des témoins financiers valides pour ce
nouveau couple. Leur préparation fournit seulement le gabarit de données,
calendrier, coûts et gardes, pas les protections ni leurs résultats économiques.

## Versionnement et traçabilité

- Paramètres actifs : `config/research/oracle_path_profit_filter_tp15_sl7.json`.
  Cet amendement hérite explicitement du protocole précédent ; le préparateur
  produit ensuite un **JSON complet résolu** et en fige les empreintes.
- Préparateur : `scripts/research/us_oracle_path_profit_filter_tp15_sl7_protocol.py`.
- Dossier : `artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-protocol-v1`.
- Le dossier initial `20261015-protocol-v1`, ses sources, tests et paramètres
  TP10/SL10 restent inchangés. Leurs entrées sont recontrôlées, puis référencées
  dans le nouveau manifeste, sans recopier inutilement les prix ou les scores.
- Seuls le couple TP/SL, le nom de variante et l'exigence du nouveau témoin sont
  amendés ; pas de changement des features, seuil d'acceptation ou périodes.

Population réutilisable : **25 200 candidats / 1 260 séances historiques**,
13 780 candidats récents. Cette population ne dépend pas du couple TP/SL ;
les nouveaux labels TP15/SL7, eux, **ne sont pas encore calculés**.

```powershell
python -u -m scripts.research.us_oracle_path_profit_filter_tp15_sl7_protocol --output artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-protocol-v1
```

Statut attendu : `PREPARED_NOT_TRAINED`. Aucun entraînement, SQL, appel GPT,
backtest, ordre ou paramètre de production modifié par cette préparation.
La reprise vérifie les empreintes ; impossible d'écraser le dossier parent.

Préparation exécutée et vérifiée : `PREPARED_NOT_TRAINED`, TP 0,15 / SL 0,07,
nouveau témoin requis. **22 tests ciblés passent**, y compris la conservation
de l'ancien contrat et le rejet des modifications de features/seuil/périodes
non demandées. Les empreintes des entrées et sorties ont été recontrôlées
séparément ; les anciens paramètres restent à TP10/SL10.

Les [constats de non-doublon, features, règles temporelles et réserves](oracle_path_profit_filter_tp10_sl10_20261015.md)
restent valables, sauf les anciennes valeurs TP10/SL10 expressément remplacées
ici. Le principe demeure une réplication bornée, pas une nouvelle famille de
signal. 2024–2026 restent des périodes explorées, non des holdouts vierges.

La prochaine étape reste, sur nouveau GO, de construire et vérifier les cibles
**TP15/SL7** avec parité native, puis les features J, couverture et purge, avant
l'éventuel petit entraînement. Pas de reprise automatique de la préparation des
cibles TP10/SL10, ni de retouche des gates sur les pertes récentes.
