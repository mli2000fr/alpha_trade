# P0b — Reconstruction dynamique bar-only de l'univers Oracle

## Objectif

P0b mesure l'effet d'un univers quotidien construit sans rétropager les
métadonnées courantes. La population candidate est constituée des 2 696
symboles de `config/univers/univers_filtred.txt`. Aucune table et aucun batch
n'ont été modifiés.

Artefact canonique :
`artifacts/research/oracle_universe_pit_audit/p0b-20260908172407`.

## Contrat quotidien

À chaque date entre 2016-01-01 et 2025-12-31, un symbole est admis avec :

- au moins 504 séances observées ;
- clôture ≥ 10 $ ;
- volume moyen trailing 20 jours ≥ 100 000 actions ;
- dollar-volume moyen trailing 20 jours ≥ 10 M$ ;
- taux de barres remplies trailing 252 jours ≤ 2 % ;
- barre réelle à J et J+20 ;
- aucune rupture de prix inexpliquée supérieure à 20x sur le chemin ;
- censure des ruptures d'identité WFRD et CHRD déjà enregistrées.

La capitalisation, le pays, le type de titre et le statut actuels ne sont pas
utilisés historiquement, car ils ne constituent pas une série PIT certifiée.

## Résultats de couverture

| Mesure | Résultat |
|---|---:|
| Lignes éligibles H20 | 3 926 243 |
| Dates | 2 514 |
| Symboles admis au moins une fois | 2 493 |
| Univers quotidien minimum | 1 104 |
| Univers quotidien médian | 1 550 |
| Univers quotidien maximum | 2 027 |

La population est désormais assez large chaque jour pour calculer des rangs
cross-sectionnels robustes. Le minimum de 20 titres n'est jamais proche d'être
atteint.

## Comparaison avec les anciens labels statiques 400

Population de référence : 890 789 anciens labels H20 valides du batch
`model-factory-20260907170018-0e94ac`.

| Comparaison | Résultat |
|---|---:|
| Anciennes lignes encore admises par les gates quotidiens | 67,7 % |
| Décile exactement identique | 45,4 % |
| Appartenance extrême identique | 90,1 % |
| Appartenance D1 identique | 94,9 % |
| Appartenance D10 identique | 95,2 % |
| Changement absolu médian de décile | 1 décile |
| Spearman quotidien médian des percentiles | 1,000 |

Le Spearman de 1,000 n'est pas une preuve que les labels sont identiques.
Ajouter des symboles ne change pas l'ordre relatif des 400 anciens rendements,
mais modifie leurs percentiles et les seuils des déciles. Environ 9,9 % des
observations comparables changent d'appartenance extrême.

Le fait que seulement 67,7 % des anciennes lignes passent les gates signifie
également que le fichier statique autorisait de nombreuses dates où le symbole
n'avait pas encore 504 séances, un prix suffisant ou la liquidité trailing
requise.

## Concentration persistante

Les 20 % de symboles les plus contributeurs produisent 52,2 % des tails du
nouvel univers, contre environ 41 % dans l'ancien panel de 400. L'élargissement
bar-only corrige l'admission historique, mais accentue la séparation entre une
majorité de titres calmes et une minorité structurellement volatile.

Conséquence : il ne faut pas sélectionner les symboles les plus mobiles pour
construire le prochain Oracle. Cette politique augmenterait encore la part de
l'identité/volatilité structurelle dans la cible.

## Verdict

P0b valide le mécanisme d'univers dynamique et montre un changement matériel de
labels. Il ne fournit pas encore un univers PIT complet :

- la liste candidate reste constituée de titres connus actuellement et omet
  potentiellement des sociétés historiquement radiées ;
- le type de titre, le pays et la capitalisation historique ne sont pas encore
  certifiés ;
- la concentration par volatilité reste très forte.

La prochaine étape P0c doit comparer, sur exactement ce panel :

1. rang du rendement H20 brut ;
2. rang du rendement H20 normalisé par la volatilité ex ante ;
3. rang à l'intérieur de strates de volatilité et de secteurs ;
4. stabilité des tails par semestre et cohorte de cotation.

Ces variantes sont des labels expérimentaux parallèles. Le label brut canonique
ne doit pas être remplacé avant de vérifier que l'Oracle conserve l'amplitude
négociable et gagne en information événementielle OOF.

Cette comparaison est terminée dans
[P0c — cibles corrigées de la volatilité](oracle_universe_p0c_targets.md).

## Fichiers produits

- `summary.json` : contrat et résultats synthétiques ;
- `dynamic_labels_h20.parquet` : labels dynamiques H20 ;
- `daily_universe.csv` : taille et stabilité quotidienne ;
- `symbol_tail_summary.csv` : concentration par symbole ;
- `comparison_static400.parquet` : correspondance avec les anciens labels ;
- `report.md` : rapport généré.
