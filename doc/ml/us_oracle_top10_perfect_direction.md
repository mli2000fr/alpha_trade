# Oracle TOP10 — Simulation avec direction positive connue a posteriori

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Objectif et statut

Expérience demandée le 7 octobre 2026 : mesurer ce que donnerait le portefeuille
si l'on savait reconnaître les futurs rendements positifs parmi les **dix
premiers titres prédits chaque jour par l'Oracle Extreme H20**.

**Attention : simulation contrefactuelle avec connaissance du futur. Ce n'est
ni un modèle directionnel, ni une stratégie déployable, ni une validation OOS
de la capacité à reconnaître D1/D10.** Elle permet de mesurer l'intérêt
économique potentiel d'une direction correcte avec le portefeuille existant.

## Sélection figée

1. Conserver les dix premiers scores Oracle originaux de chaque date.
2. Qualifier leur cible réalisée H20 : rendement fini, qualité de cible valide,
   endpoints locaux qualifiés et date de sortie postérieure à la date du signal.
3. Référence appariée `OBSERVED_TOP10` : conserver ces candidats observables.
4. Filtre parfait `PERFECT_POSITIVE_TOP10` : conserver uniquement ceux dont le
   rendement cible est strictement positif.
5. Ne jamais remplacer un candidat exclu par le onzième ou un autre titre.

La positivité désigne le rendement de la cible Oracle **close J → close J+20**,
pas le PnL de la transaction, dont l'entrée se fait à l'ouverture suivante.
Un positif n'est pas nécessairement D10 : plusieurs déciles peuvent être positifs.
Un rendement final positif peut subir un stop avant son rebond ; le résultat
n'est donc pas une borne supérieure mathématique de tout PnL envisageable.

## Couverture et biais d'observation

Sur les 437 séances du 2 janvier 2025 au 30 septembre 2026 :

- 4 370 couples date/titre dans le TOP10 initial ;
- 4 190 avec cible qualifiée ;
- 2 290 positifs, 1 893 négatifs, 7 nuls ;
- 180 non évaluables, exclus des **deux** politiques comparées.

Les nombres représentent des occurrences quotidiennes, pas des titres uniques
ni des trades. Le filtre parfait conserve environ 54,65 % des occurrences
évaluables. La référence appariée évite de traiter les labels inconnus comme
des perdants ou de comparer des périodes observables différentes.

## Portefeuille et exécution

Le replay réutilise l'orchestrateur, le ledger et les primitives de portefeuille
décrits dans [l'audit de parité](us_concentrated_live_parity_audit.md), avec les
mêmes règles de régime, sizing, concentration, capital disponible, protections,
gaps et coûts. Capital initial : 4 000 USD ; huit positions au maximum.
Il ne transforme pas toutes les occurrences sélectionnées en transactions :
les contraintes de portefeuille et de risque restent actives.

Deux politiques sont comparées avec chacune quatre sorties figées :

| Variante | TP | Trailing | Échéance |
|---|---|---|---|
| `CURRENT_NO_EXPIRY` | Oui | Oui | Pas d'échéance fixe |
| `REFERENCE_20_AFTER_ENTRY` | Oui | Oui | 20 séances après l'entrée |
| `NO_TP_FIXED_SL_20_AFTER_ENTRY` | Non | Non, stop initial conservé | 20 séances après l'entrée |
| `NO_TP_TRAILING_20_AFTER_ENTRY` | Non | Oui | 20 séances après l'entrée |

Le stop initial est dynamique (2,5 × ATR), **pas un stop fixe de 7 %**.
Toutes les positions encore ouvertes sont liquidées en fin de replay.
Le TP canonique, lorsqu'il est actif, est limité à 7 % avec sa formule ATR.

## Données et limites conservées

- Univers d'origine : `config/univers/univers_filtred_tradable.txt`, 1 798 titres.
- Oracle : `model-factory-20261003082853-e98332`.
- Sélection **Oracle seul** ; pas d'intersection Oracle × ATR dans ce test.
- Secteurs actuels non PIT explicitement acceptés pour cette recherche.
- Macro archivée de la référence ; sa présence ne certifie pas toute la lineage PIT.
- Corrections fournisseur de volume BAND/GPRE appliquées aux copies de barres,
  pas en base ; elles ne constituent pas des preuves indépendantes historiques.
- Fills simulés sur OHLC quotidien ; pas une reproduction de fills de courtier.
- L'utilisation volontaire des rendements futurs rend toute performance du filtre
  parfait impropre à une annonce de performance prédictive réelle.

## Reproduction, sorties et surveillance

Script dédié : `scripts/research/us_concentrated_perfect_direction.py`.
Commande lancée :

```powershell
python -u -m scripts.research.us_concentrated_perfect_direction --output artifacts/research/us_concentrated_replay/perfect-direction-top10-20261007-v1
```

Le dossier contient :

- `coverage.json` et `ex_post_membership.parquet` : sélection et couverture ;
- `protocol.json` : avertissements, sources et empreintes ;
- `progress.json` : nombre de simulations terminées sur huit ;
- sous-dossiers politique/variante : progression quotidienne, trades et rapports ;
- `report.json` : agrégation finale ;
- `stdout.log` / `stderr.log` : traces de lancement.

Lecture de surveillance :

```powershell
Get-Content artifacts/research/us_concentrated_replay/perfect-direction-top10-20261007-v1/progress.json
Get-Content artifacts/research/us_concentrated_replay/perfect-direction-top10-20261007-v1/stderr.log -Tail 10
```

Aucun entraînement, écriture SQL, modification de production ou interruption
d'un batch existant. Tests : 17 tests ciblés passants, dont deux nouveaux sur
la sélection figée, l'absence de réapprovisionnement et les labels inconnus.
Un smoke de cinq séances × huit simulations est terminé avant le lancement complet.

## Interprétation à appliquer aux résultats

### Résultats terminés — 7 octobre 2026

Les huit simulations terminent leurs 437 séances, avec zéro position finale,
zéro fill Phase 3 oublié et une réconciliation cash/PnL meilleure que 1e-6 USD.
Les rendements ci-dessous sont cumulés, non annualisés, nets des coûts simulés
du contrat décrit plus haut. Le capital final est celui du filtre parfait.

| Sorties | Référence appariée | Direction positive parfaite | Capital final | Drawdown parfait | Sharpe parfait |
|---|---:|---:|---:|---:|---:|
| TP + trailing, sans échéance | −10,66 % | +121,80 % | 8 871,84 $ | −4,20 % | 3,90 |
| TP + trailing, échéance 20 séances | −9,95 % | +123,23 % | 8 929,04 $ | −4,20 % | 3,94 |
| Sans TP, stop initial, échéance 20 séances | −3,29 % | +195,62 % | 11 824,71 $ | −6,49 % | 3,33 |
| Sans TP, trailing, échéance 20 séances | +4,18 % | +141,98 % | 9 679,26 $ | −7,86 % | 2,97 |

La référence diffère légèrement du précédent replay TOP10 intégral : les 180
occurrences sans cible qualifiée sont retirées ici des deux politiques.

Résultats du filtre parfait, sans réinitialiser le capital entre années :

| Sorties | 2025 | Janvier–septembre 2026 | Trades clôturés | Trades gagnants | Profit factor | Exposition brute moyenne / equity |
|---|---:|---:|---:|---:|---:|---:|
| TP + trailing, sans échéance | +48,98 % | +48,87 % | 332 | 86,14 % | 2,94 | 24,14 % |
| TP + trailing, échéance 20 séances | +48,79 % | +50,03 % | 335 | 85,97 % | 3,01 | 23,42 % |
| Sans TP, stop initial, échéance 20 séances | +67,15 % | +76,86 % | 148 | 79,73 % | 5,84 | 41,57 % |
| Sans TP, trailing, échéance 20 séances | +65,57 % | +46,15 % | 171 | 67,84 % | 3,40 | 38,11 % |

Les 2 290 occurrences positives incluent 1 296 D10 (56,59 %) : cette expérience
ne sélectionne donc pas exclusivement les D10. Le rendement réel positif H20
n'implique pas 100 % de trades gagnants : le gap d'entrée, les protections et
la sortie vingt séances après l'entrée ne coïncident pas exactement avec la
cible close J → close J+20.

**Conclusion : le potentiel économique d'une direction correcte est important
sur ce jeu de données. Aucune nouvelle capacité prédictive n'a été démontrée.**
La variante sans TP/stop initial est la meilleure en rendement dans ce scénario
clairvoyant, pas une recommandation de la promouvoir en production. Les
contraintes, trajectoires et capitaux évoluent différemment après filtrage :
l'écart n'est pas une simple somme du PnL des perdants supprimés.

Comparer chaque variante uniquement à sa référence appariée : rendement net,
capital final, drawdown, nombre de trades et résultats séparés 2025/2026.
Un fort gain indiquerait un potentiel économique **si** une direction pouvait
être prédite, mais ne prouverait pas que les features actuelles le permettent.
Une perte malgré le filtre parfait montrerait que l'endpoint positif seul ne
suffit pas avec les entrées, protections et contraintes étudiées. Ce diagnostic
ne doit pas servir à optimiser les sorties rétrospectivement sans nouveau protocole.
