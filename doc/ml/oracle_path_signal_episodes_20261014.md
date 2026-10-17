# Oracle parcours TOP5 — une entrée exécutée par épisode de signal

## GO et protocole figé — 14 octobre 2026

Diagnostiquer les réentrées dans une même présence continue au TOP5, puis
comparer une seule règle si le mécanisme concerne suffisamment d'achats.
Pas d'entraînement, écritureSQL, ordre courtier, batch ou réglageLIVE modifié.
Les années2024–2026 ont déjà été examinées : pas nouveau holdout indépendant.

## Définition causale d'un épisode

- Présence continue dans le TOP5 original en séancesNYSE consécutives,
  **avant** les filtres de qualité à J et le risque. Les rangs1…5 proviennent
  des scores des nouveaux modèles annuels déjà archivés.
- Une absence observée du TOP5 clôt l'épisode ; un retour démarre le suivant.
  Une date de scoring manquante fait échouer la préparation : elle n'est pas
  inventée comme une absence. Aucun cooldown calibré sur les pertes.
- Qualité/régime/risk qui refuse une entrée ne crée pas un nouvel épisode.
  Changement de rang à l'intérieur du TOP5 ne renouvelle pas le signal.
- L'épisode de la décisionJ est celui de l'achatJ+1, indépendamment du TOP5
  futur à la clôtureJ+1. Début/âge observés seulement ; fin/durée future exclues
  de la table de décision et du filtre.
- **Un achat réellement exécuté** consomme l'épisode. Une simple approbation,
  un gap refusé, un ordre non committé ne le consomment pas. Retries de notification
  des fills idempotents, aucun double comptage.
- Le témoin autorise les réentrées natives ; le challenger bloque les nouveaux
  achats d'un épisode déjà consommé, sans toucher aux positions détenues.
  Une nouvelle entrée peut avoir lieu après sortieTOP5 puis retour, même si la
  sortie précédente était perdante. Pas de filtre dépendant du PnL futur.
- Aucune substitution par le rang6 ou suivant. Les gardes anti-renforcement,
  concentration, pertes consécutives et régime natifs sont conservés.

## Audit initial et gate technique

Classer les fills du témoin : premier achat du symbole dans l'année ; réentrée
dans un nouvel épisode ; réentrée dans le même épisode. Rapporter lots clos/
ouverts, PnL réalisé et taux gagnants à titre descriptif, sans soustraire les
pertes pour prétendre simuler un autre portefeuille.

Gate figé : **au moins10 réentrées réellement exécutées dans le même épisode
dans chacune des trois années**. C'est un seuil de matérialité opérationnelle,
pas une sélection sur la rentabilité des groupes. Si insuffisant : arrêt
`NO_GO_LOW_EPISODE_REPETITION`, aucun backtest ni ajustement du seuil.
Si suffisant : six portefeuilles,2 bras×3 années, règle inchangée même si le
PnL descriptif d'un groupe est positif. Aucun délai/seuil supplémentaire testé.

## Comparaison économique

| Test | Oracle CatBoost parcours | Fold causal |
| --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 |
| 2026 jusqu'au30septembre | `model-factory-20261014113232-bc35a7` | 2025-12-10 |

LONG explicite TOP5, SL5/TP20/trailing15 inchangés, budget2 % equity par entrée
avant limites natives, capital4000USD réinitialisé par année/bras, plafond
entrée levier2, tailles/frais/financement6,5 % ACT/360/maintenance natifs.
Pas de réduction progressive supplémentaire, pas de vente forcéeH20 ou
terminale ; ouverts MTM. Pas nouvelle inférence/modification de scores Oracle.

Les états de portefeuille **et d'épisodes consommés** repartent au début de
chaque année. Un épisode présent à la première séance est censuré à gauche :
une première entrée y est autorisée, faute de TOP5 du même modèle pour l'année
précédente. Ce n'est pas une qualification du suiviLIVE continu multi-années.
Corporate actions via le ledgerSTRICT existant, pas ticker retiré pour cacher
une perte. La présenceTOP5 est par symbole du modèle ; identités rebasées des
positions sont conservées par le ledger, pas nouvelle entrée fictive.

Témoins doivent reproduire exactement trades/courbes des FIXED_REFERENCE
archivés. Audit indépendant de calcul (même assistant, pas second humain)
de la construction des épisodes, des dates, du filtre avant décision, de la
consommation après fills, des stops/protections et de l'équité/financement.

Gate exploratoire : six cas complets, témoins exacts, rendement challenger
supérieur et DD pas pire dans **chaque** période ; sinon
`NO_GO_STABLE_EPISODE_ENTRY_ADVANTAGE`. Échec technique=`PARTIAL_FAILED`,
aucune conclusion financière sur un cas échoué. Pas promotionLIVE automatique.

Réserves des archives : univers actuel de survivants, secteurs nonPIT, prix
réajustés actuels, dividendes incomplets, macro sans vintages de publication
certifiés, marge/fills/spreads hypothétiques. La fraîcheur de rang n'est pas
une preuve de direction LONG, de nouveau catalyseur ou de rentabilité.

## Artefacts

```powershell
python -u -m scripts.research.us_oracle_path_signal_episodes --output artifacts/research/us_oracle_path_signal_episodes/20261014-v1 --phase audit
python -u -m scripts.research.us_oracle_path_signal_episodes --output artifacts/research/us_oracle_path_signal_episodes/20261014-v1 --workers 3
```

`protocol.json` avant calcul, `membership.parquet` causal, diagnostic des
entrées du témoin, progression globale/par cas, décisions/fills d'épisodes,
trades/equity, rapport annuel et contrôle final. Résultats dans un document
séparé pour ne pas modifier le protocole et ses empreintes après calcul.
