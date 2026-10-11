# Sprint 6-B France — historique et liquidité PIT J+1

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Date de clôture : 3 octobre 2026. Verdict : **`GO_6B_TRAINING_UNIVERSE`**.

Le Sprint 6-B résout le premier état `UNKNOWN` du contrat 6-A : il détermine quelles observations France possèdent assez d’historique et de liquidité pour alimenter ultérieurement un panel d’entraînement. Il ne rend toujours aucune ligne tradable ou servable.

## Politique pré-enregistrée

Les seuils ont été écrits dans [config/universe_fr_s6b.yaml](../../config/universe_fr_s6b.yaml) avant le calcul complet :

| Paramètre | Valeur |
| --- | ---: |
| Disponibilité | séance XPAR suivante (`J+1`) |
| Historique minimal | 252 observations admissibles |
| Fenêtre de liquidité | 20 séances XPAR |
| Observations minimales dans la fenêtre | 15 |
| Clôture minimale | 1,00 € |
| Valeur échangée moyenne minimale | 500 000 € |

La valeur échangée est calculée avec `close brut × volume fournisseur`. Les titres dont le manifeste Sprint 5 signale un historique de split fournisseur sont déjà exclus en amont. Aucun seuil n’a été ajusté après lecture des résultats.

## Règle temporelle

Pour une barre source de la séance `J` :

- la décision associée est datée de la prochaine séance officielle XPAR ;
- seules les barres admissibles de `J` et des séances antérieures sont utilisées ;
- la fenêtre de 20 porte sur les **séances de marché**, pas sur les 20 dernières observations disponibles ;
- une séance manquante réduit donc le nombre d’observations et peut rendre la liquidité insuffisante ;
- aucune barre de `J+1` ne peut influencer le snapshot.

Les barres 2016–2017 ne servent pas de warm-up, car le Sprint 5 les a placées hors du périmètre exploitable. L’année 2018 constitue donc volontairement une période de chauffe de 252 observations et ne contient aucune ligne entraînable.

## Résultats complets

| Mesure | Résultat |
| --- | ---: |
| Snapshots observables analysés | 561 001 |
| `training = ELIGIBLE` | 170 046 |
| `training = INELIGIBLE` | 390 955 |
| Symboles présents dans le manifeste | 490 |
| Symboles entraînables au moins une fois | 168 |

### Motifs

| Motif | Lignes |
| --- | ---: |
| Valeur échangée moyenne < 500 000 € | 260 407 |
| Historique < 252 observations | 78 900 |
| Prix < 1 € | 33 276 |
| Moins de 15 observations sur 20 séances | 18 372 |
| Tous les gates franchis | 170 046 |

### Répartition par année de décision

| Année | Éligibles | Inéligibles |
| --- | ---: | ---: |
| 2018 | 0 | 49 553 |
| 2019 | 18 501 | 38 676 |
| 2020 | 22 549 | 37 202 |
| 2021 | 23 136 | 39 973 |
| 2022 | 21 815 | 44 316 |
| 2023 | 20 870 | 46 846 |
| 2024 | 21 474 | 49 114 |
| 2025 | 23 294 | 50 079 |
| 2026 | 18 407 | 35 196 |

## Persistance et identité

La migration France `0007_fr_liquidity_research` a été appliquée uniquement à `alpha_trade_fr`. Elle crée :

- `fr_liquidity_runs` : provenance, politique, empreintes, compteurs et état ;
- `fr_liquidity_snapshots` : métriques par symbole fournisseur et séance de décision.

La base contient 561 001 snapshots et exactement 561 001 clés uniques `(run, symbole, séance de décision)`. Une seconde exécution a terminé en 0,81 seconde sans insertion supplémentaire.

Les 561 001 `instrument_id` sont `NULL` par conception. La table `instruments` France est encore vide et le `GO_RESEARCH_J1` interdit de transformer implicitement les symboles EODHD en identités canoniques. Les données restent donc du **staging de recherche versionné**.

## Artefacts

- rapport : `artifacts/fr/sprint6b_liquidity/report.json` ;
- snapshots compressés : `artifacts/fr/sprint6b_liquidity/liquidity_snapshots.jsonl.gz` ;
- service reproductible : `service/fr/universe_liquidity_6b.py` ;
- migration SQL : `database/sql/fr/migration_fr_0007_liquidity_research.sql`.

Commande sans écriture SQL :

```powershell
python -u -m service.fr.universe_liquidity_6b
```

Commande avec persistance idempotente :

```powershell
python -u -m service.fr.universe_liquidity_6b --persist
```

## Limites maintenues

- aucune capitalisation PIT historique ;
- aucun spread historique ;
- aucune appartenance sectorielle datée ;
- aucun benchmark France validé ;
- aucun rendement économique validé pour les actions sur titres ;
- aucun live, paper trading, serving ou univers de backtest tradable.

## Étape suivante

Mise à jour du 3 octobre 2026 : le [Sprint 6-C](sprint_6c_identite_benchmark_secteurs.md) est réalisé avec `GO_6C_RESEARCH_PRICE_ONLY`. Les identités de recherche et le benchmark sont persistés ; les secteurs historiques et la promotion canonique restent ouverts. Les points ci-dessous décrivent le contrat initial de 6-C.

Le Sprint 6-C doit traiter séparément :

1. la résolution d’identité recherche vers `instrument_id`, sans promotion silencieuse ;
2. la sélection d’un benchmark large France, sans utiliser implicitement CAC 40 ou SPY ;
3. une taxonomie sectorielle et des appartenances datées ;
4. la couverture et les états `UNKNOWN` de ces nouvelles données.

Le périmètre `training` peut maintenant être construit depuis les snapshots 6-B. Les périmètres `tradable` et `servable` restent bloqués.
