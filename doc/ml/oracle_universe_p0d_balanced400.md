# P0d — Univers Oracle équilibré de 400 symboles

## Décision

P0d produit un nouvel échantillon de recherche de 400 symboles à partir de
`config/univers/univers_filtred.txt`. Il remplace l'ancien choix manuel/statique
pour les smoke tests et les campagnes d'ablation Oracle.

Ce fichier n'est pas un univers de production et ne transforme pas un backtest
2026H1 en test OOS indépendant. Sa qualité PIT est `RECONSTRUCTED_GRADE_B` : les
barres et dates de capitalisation sont antérieures au cutoff, mais les données
SEC ont été rétrospectivement collectées en 2026 et le secteur/type provient du
snapshot courant de `stock_metadata`.

Livrable canonique :

```text
config/univers/oracle_balanced_400_202512.txt
```

Artefact d'audit canonique :

```text
artifacts/research/universe_selection/p0d-20260908181608/
```

## Objectif et rôle

Le but n'est pas de sélectionner les titres qui ont historiquement généré les
meilleurs D1/D10. Ce serait une fuite de cible. P0d construit une population :

- suffisamment ancienne, liquide et négociable ;
- sans mini-cap ni capitalisation inconnue ;
- dominée par les mid caps, tout en conservant les large caps ;
- couvrant tout le spectre de volatilité et de bêta ;
- diversifiée sectoriellement ;
- déterministe et entièrement traçable.

Usages admis : smoke tests, ablations de features, comparaison rapide de
formulations et entraînements pilotes. Pour l'Oracle mutualisé final, la cible
reste l'univers large à admission quotidienne P0b dès que son intégration dans
le pipeline d'entraînement est verrouillée.

## Sources réellement utilisées

| Information | Source code/SQL | Temporalité |
|---|---|---|
| population candidate | `config/univers/univers_filtred.txt` | fichier courant |
| OHLCV, `is_filled` | `stock_bars_daily` | uniquement `date <= 2025-12-31` |
| ancienneté et dernière barre | `stock_bars_daily` | uniquement avant cutoff |
| capitalisation | dernière ligne `stock_fundamentals_daily.trade_date <= cutoff` | date historique, collecte ultérieure possible |
| secteur, statut, type, tradabilité | `stock_metadata` | snapshot courant, non PIT strict |
| benchmark bêta | SPY dans `stock_bars_daily` | trailing 126 séances au cutoff |

Le code exécuté est `modelFactory/oracle_balanced_universe.py`. Il ne lit ni
les labels Oracle, ni les rendements futurs, ni les scores ML, ni les PnL.

## Contrat de sélection

### Cutoff et reproductibilité

```text
selection_cutoff = 2025-12-31
seed             = 20251231
source SHA-256   = 39cce48cf0b8e92512382e2566bd008aa31aabd2dae07f592499136ee1a4df04
commit Git       = beb91c7d51ac441d9c0f8d3daf793d323d10fe4a
```

La sortie est triée par symbole et contient une ligne, des virgules sans espace
et un unique saut de ligne final. Son SHA-256 est :

```text
97465fa2002337f066854fb055fbb2d3818645a37676c4ab9d07b5f8e9947301
```

### Gates d'éligibilité

Un titre est rejeté si au moins une condition est vraie :

| Gate | Seuil |
|---|---:|
| historique disponible au cutoff | moins de 504 séances |
| fraîcheur de la dernière barre | antérieure à la cinquième dernière séance SPY |
| dernier cours ajusté | moins de 10 USD |
| volume moyen trailing 20 j | moins de 100 000 actions |
| dollar-volume moyen trailing 20 j | moins de 10 MUSD |
| barres `is_filled=1` trailing 252 j | plus de 2 % |
| bêta trailing 126 j | manquant |
| capitalisation | manquante ou inférieure à 500 MUSD |
| âge de la capitalisation au cutoff | plus de 365 jours |
| statut | différent de `active` |
| tradable / bars_available | différent de 1 |
| classe d'actif | différente de `us_equity` |
| type non ordinaire détecté | ETF, ETN, warrant, rights d'acquisition/souscription, preferred ou unité SPAC |

Le détecteur de type a été resserré pendant P0d. Il ne rejette plus une banque
simplement nommée « Preferred Bank », un ADR dont la description contient
« right to receive », ni une société cotée sous forme de partnership/common
units. Il exclut en revanche explicitement les instruments non ordinaires.

Les motifs sont enregistrés séparément et les comptes sont non exclusifs : un
même titre peut échouer plusieurs gates.

### Quotas sur les 400 retenus

Capitalisation :

| Strate | Définition | Quota exact |
|---|---|---:|
| small | 500 MUSD à 2 MdUSD | 40 |
| mid | 2 à 10 MdUSD | 260 |
| large | au moins 10 MdUSD | 100 |

Volatilité trailing 20 séances, quintiles calculés dans les titres éligibles :

| Q1 | Q2 | Q3 | Q4 | Q5 |
|---:|---:|---:|---:|---:|
| 60 | 80 | 100 | 100 | 60 |

Bêta trailing 126 séances contre SPY, quintiles calculés dans les titres
éligibles : 80 titres par quintile. L'algorithme remplit d'abord les quintiles
les moins représentés, puis les secteurs les moins représentés, sans modifier
les quotas exacts capitalisation × volatilité.

Contraintes supplémentaires : maximum 40 titres par secteur et maximum 60
listings étrangers/ADR détectés par proxy. La sélection finale n'atteint aucun
de ces plafonds.

## Résultats du run canonique

| Mesure | Résultat |
|---|---:|
| candidats uniques | 2 696 |
| candidats éligibles | 995 |
| symboles sélectionnés | 400 |
| doublons | 0 |
| mid / large / small | 260 / 100 / 40 |
| volatilité Q1/Q2/Q3/Q4/Q5 | 60 / 80 / 100 / 100 / 60 |
| bêta Q1/Q2/Q3/Q4/Q5 | 80 / 80 / 80 / 80 / 80 |
| secteurs distincts | 44 |
| plus gros secteur | 16 symboles, soit 4 % |
| proxy ADR/étranger | 14 |
| chevauchement avec l'ancien `ticket_mid_cap_400` | 101 symboles |

Principales exclusions non exclusives :

| Motif | Nombre |
|---|---:|
| capitalisation manquante ou < 500 MUSD | 1 515 |
| capitalisation âgée de plus de 365 jours | 1 520 |
| ETF/ETN/autre instrument non ordinaire | 739 |
| dollar-volume 20 j < 10 MUSD | 659 |
| volume 20 j < 100 000 | 247 |
| cours < 10 USD | 50 |

Le chevauchement limité à 101/400 confirme que P0d n'est pas une simple remise
en forme de l'ancien univers. Il modifie fortement la population expérimentale.

## Artefacts et lecture

| Fichier | Contenu |
|---|---|
| `manifest.json` | cutoff, seed, commit, hashes, seuils, quotas, distributions et avertissements |
| `symbol_audit.csv` | toutes les variables et le verdict de chaque candidat |
| `exclusions.csv` | candidats rejetés et liste complète des motifs |
| `selected_400.csv` | 400 retenus avec strates et métadonnées |
| `allocation.csv` | quotas demandés/disponibles/servis par cellule cap × volatilité |
| `strata_summary.csv` | contrôle synthétique des cellules finales |
| `report.md` | résumé humain du run |

## Reproduction et renouvellement

Commande depuis la racine du projet :

```powershell
python -m modelFactory.oracle_balanced_universe --source config/univers/univers_filtred.txt --cutoff 2025-12-31 --seed 20251231 --output-file config/univers/oracle_balanced_400_202512.txt
```

Pour un renouvellement, ne pas écraser silencieusement la version précédente :
changer le suffixe `YYYYMM`, figer le nouveau cutoff et conserver l'artefact.
Suivre le contrat complet dans
[`oracle_universe_selection_playbook.md`](oracle_universe_selection_playbook.md).

## Limites et interdictions

1. Les 400 symboles ne doivent pas être décrits comme les « meilleurs » : ils
   sont équilibrés, pas optimisés sur la cible.
2. La capitalisation historique datée ne prouve pas qu'elle était disponible au
   modèle à cette date ; elle a été collectée ultérieurement.
3. Secteur et type viennent du snapshot courant. Les changements historiques de
   classification, delistings et survivorship ne sont donc pas totalement
   reconstruits.
4. La sélection arrêtée au 31 décembre 2025 ne peut pas servir à revendiquer une
   confirmation indépendante sur 2026H1 avec les données actuelles.
5. Aucun résultat de modèle n'a encore été produit par P0d. La qualité de
   l'échantillon ne démontre pas une amélioration de l'Oracle.

## Étape suivante préfixée : P0e

P0e doit comparer, à configuration Oracle strictement identique :

1. l'ancien univers 400 ;
2. `oracle_balanced_400_202512.txt` ;
3. lorsque l'admission quotidienne est intégrée au trainer, l'univers large P0b.

La comparaison porte d'abord sur les prédictions OOF communes : AUC/PR-AUC,
calibration brute, rappel des extrêmes, amplitude capturée, stabilité par fold,
semestre, cap, volatilité, bêta et secteur. Aucun seuil ne sera choisi sur
2026H1. P0d n'est promu que si le gain est stable et ne vient pas d'une seule
strate.
