# P0c — Audit des cibles Oracle corrigées de la volatilité

## Question

P0b a construit 3 926 243 observations H20 avec un univers quotidien bar-only
de 1 104 à 2 027 titres. P0c demande si une cible comparable entre niveaux de
volatilité réduit la domination des titres structurellement agités sans perdre
l'amplitude brute recherchée par Oracle.

Aucun modèle n'est entraîné. Toutes les variantes utilisent exactement les
mêmes dates, symboles et rendements futurs que P0b.

## Variantes

| Nom | Définition |
|---|---|
| `raw` | Rang quotidien du rendement H20 brut, contrat canonique |
| `vol_scaled` | Rang de `rendement H20 / volatilité20 ex ante` |
| `vol_strata` | Quintile de volatilité ex ante, puis rang H20 à l'intérieur de chaque quintile |
| `sector` | Rang H20 dans le secteur courant si le groupe contient ≥ 20 titres |

La volatilité est l'écart-type des log-rendements des 20 séances connues à J,
avec plancher 0,25 % par jour. Le secteur est diagnostique uniquement : la
métadonnée actuelle n'est pas une série historique PIT certifiée.

## Gates préfixés

Une nouvelle cible devait simultanément :

1. couvrir au moins 95 % des lignes ;
2. réduire d'au moins 15 % la concentration des tails dans les 20 % de symboles
   les plus contributeurs ;
3. conserver au moins 90 % de l'amplitude brute moyenne des tails canoniques ;
4. produire un lift d'amplitude positif pendant au moins 8 années sur 10 ;
5. utiliser uniquement des données PIT pour être promouvable.

Les seuils ne sont pas modifiés après observation.

## Résultats

| Variante | Couverture | Top20 symboles → tails | Amplitude brute tail | Rétention | Lift tail/rest | Jaccard avec brut | Années lift+ | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `raw` | 100 % | 52,2 % | 14,29 % | 100 % | 3,17x | 100 % | 10/10 | canonique |
| `vol_scaled` | 100 % | 40,9 % | 12,23 % | 85,58 % | 2,43x | 51,6 % | 10/10 | NO_GO |
| `vol_strata` | 100 % | 42,3 % | 12,84 % | 89,86 % | 2,64x | 56,4 % | 10/10 | NO_GO très proche |
| `sector` | 64,5 % | 47,5 % | 12,82 % | 89,75 % | 2,27x | 45,4 % | 10/10 | NO_GO + non-PIT |

La corrélation entre fréquence de tail et volatilité ex ante passe de 0,855 sur
le brut à 0,367 avec `vol_scaled` et 0,596 avec `vol_strata`. Les corrections
réduisent donc bien le biais structurel, mais au prix d'une amplitude économique
plus faible.

## Verdict

Aucune cible alternative n'est promue. `vol_strata` manque le gate de rétention
de très peu : 89,86 % contre 90 %. Modifier maintenant le seuil à 89 % serait
une optimisation a posteriori. Le rendement brut reste le label Oracle
canonique.

`vol_strata` peut rester un challenger pré-enregistré pour une future période
indépendante. Il ne doit ni remplacer les labels existants ni déclencher un
nouvel entraînement sur la même confirmation.

## Conséquence pour la sélection des symboles

P0c confirme qu'il faut construire `oracle_balanced_400` avec des quotas de
volatilité, tout en conservant le label brut. Sélectionner seulement les titres
les plus volatils renforcerait la concentration ; normaliser entièrement la
cible sacrifierait trop d'amplitude. L'équilibrage de la population est donc le
compromis autorisé pour les campagnes rapides.

## Artefacts

Répertoire :
`artifacts/research/oracle_universe_target_audit/p0c-20260908173325`.

- `target_assignments.parquet` : affectations des quatre cibles ;
- `variant_summary.csv` : métriques globales ;
- `yearly_summary.csv` : stabilité annuelle ;
- `summary.json` et `report.md` : contrat et verdict.

Script reproductible : `modelFactory/oracle_universe_target_audit.py`.

