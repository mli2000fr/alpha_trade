# Oracle TP20/SL10 — modèles annuels, 13 octobre 2026

## Protocole figé avant lecture des résultats

Campagne séparée après la remise à zéro des modèles US. Aucun entraînement,
écriture SQL, appel broker ou changement des modèles/configurations live.
Répertoire : `artifacts/research/us_oracle_annual_models/20261013-v1`.

| Année testée | Modèle fourni | Fin annoncée | Fin du contrat enregistré | Fold utilisé | Dernière disponibilité de validation |
| --- | --- | --- | --- | --- | --- |
| 2024 | `model-factory-20261013124901-f62825` | 2024-12-31 | **2024-11-30** | 2023-12-05 | 2023-12-04 |
| 2025 | `model-factory-20261013124908-f1b59f` | 2025-12-31 | **2025-11-30** | 2024-12-05 | 2024-12-04 |
| 2026 | `model-factory-20261013125014-9be3d2` | 2026-09-30 | 2026-09-30 | 2025-12-10 | 2025-12-09 |

Débuts enregistrés : 2014-12-01, 2015-12-01 et 2016-12-01. Les deux premières
fins diffèrent donc de la description utilisateur ; aucun réentraînement
automatique pour les changer. Ce sont bien les modèles fournis qui sont testés.

Les dates de fin demandées ne sont **pas** les dates de fit des poids utilisés.
Ces campagnes walk-forward n'effectuent pas un refit final sur toutes les
données jusqu'à leur fin demandée. À chaque décision J, le script choisit le
fold le plus récent dont le démarrage est au plus tard J et dont les labels
d'apprentissage **et de validation**, pour les deux heads, sont disponibles
strictement avant J. Aucun fold futur n'est utilisé. L'extrapolation après
la fin du test OOF initial est comptée dans le manifeste ; elle n'est pas
présentée comme une extension des prédictions OOF archivées.

Les trois contrats ont été contrôlés : TP20/SL10, vingt séances, deux heads
LightGBM entraînés, 1 790 symboles identiques, 173 features et mêmes options.
Ils portent `serving_ready=false` : ce test ne vaut pas promotion production.

## Portefeuille et sélection

- LONG uniquement : classement décroissant du score du head LONG, égalités
  départagées par symbole. Le modèle possède un head SHORT, également calculé
  et archivé, mais celui-ci ne choisit pas le sens des ordres de cette baseline.
- TOP10 primaire ; TOP20 et TOP50 secondaires, sans remplacement d'un titre
  rejeté par les contraintes de portefeuille par un gagnant connu a posteriori.
  Le champ `rank` des trades est le rang des entrées acceptées par le constructeur
  du portefeuille ; il peut différer de `selection_rank`, rang initial du modèle.
  L'audit vérifie l'appartenance au TOP figé, pas une fausse égalité de ces rangs.
- TP fixe 20 %, SL fixe 10 %, sans trailing. Entrée à l'ouverture J+1 ; sortie
  temporelle à l'ouverture de la 21e séance depuis l'entrée si encore détenu.
- Capital réinitialisé à 4 000 USD chaque année, coûts/sizing/régime et contraintes
  natifs conservés. Les gains annuels ne sont pas composés entre les années.
- Décisions 2024 et 2025 complètes ; 2026 jusqu'au **3 septembre 2026**, comme
  les comparaisons précédentes, avec les prix de dénouement jusqu'au 9 octobre.
- Un SL10 n'est pas une garantie de perte maximale : les gaps peuvent le dépasser.

## Données et traçabilité

Réutilisation des matrices et tapes corrigées, archivées et vérifiées par
empreintes dans `us_oracle_tp20_sl10_new/20261012-v6`. Les anciens poids ont été
supprimés sur demande : on ne prétend pas les recharger ni reproduire leur fit.
Les nouveaux poids, leurs contrats, les sources communes et le code exécuté
sont figés par empreintes. Chaque score conserve son fold ; le protocole garde
les bornes de disponibilité et le calendrier de sélection des folds.

Réserves inchangées : univers actuel survivant, secteurs actuels non PIT acceptés,
prix ajustés rétrospectifs, vintages macro non certifiées par champ, protections
et opérations sur titres simulées et non fills réels. 2024–2026 ont déjà été
examinées : ce ne sont pas des holdouts vierges. Les corrections AVB/EQR/VMRK,
BAND/GPRE/ATEX et le changement TOELY/TELWY sont conservés, sans double ajustement.
Un défaut de prix/volume d'une position tenue doit arrêter le cas, jamais supprimer
silencieusement un perdant de la sélection.

## Exécution et suivi

```powershell
python -u -m scripts.research.us_oracle_annual_models --output artifacts/research/us_oracle_annual_models/20261013-v1
Get-Content artifacts/research/us_oracle_annual_models/20261013-v1/progress.json
python -u -m scripts.research.us_oracle_annual_result_audit --root artifacts/research/us_oracle_annual_models/20261013-v1
```

Le fichier global indique le cas courant ; le fichier
`<année>/BASELINE/<année>-TOP<n>/progress.json` indique sa séance courante.
Les cas déjà terminés et leurs empreintes sont vérifiés avant reprise ; un cas
interrompu est recalculé depuis son début. Un seul écrivain par répertoire.
`results-<année>.json` archive chaque cas terminé, puis `report.json` et
`report.md` rassemblent capital final, montants gagnants/perdants, taux de
réussite/perte, rendement, DD maximal et nombre de positions.
L'audit final recalcule ces métriques et le choix causal des folds, vérifie
l'appartenance des trades aux TOP figés, les contrats TP/SL/échéance, les
empreintes, les positions finales et la réconciliation du cash. Il conserve
aussi la comparaison avec la précédente baseline figée `6d6569`, à partir
de ses rapports archivés (ses poids ont été supprimés).

## Statut

Les **neuf cas sont terminés, zéro échec**. Audit final
`NINE_CAUSAL_ANNUAL_CASES_VERIFIED`, quatorze tests de contrat/causalité
passants, sources/code/poids inchangés, positions finales à zéro, écarts de
cash inférieurs à 10⁻⁶ USD. Aucun nouveau modèle ni variante entraîné.

## Résultats économiques exploratoires

Capital initial de chaque cas : 4 000 USD. Les montants gagnants/perdants
regroupent les jambes d'une même position, coûts canoniques inclus. Le rendement
inclut toute la liquidation de la cohorte, y compris la queue de janvier pour
2024/2025 ; il ne s'agit pas du mark-to-market au 31 décembre.

| Année | TOP | Capital final USD | Gains USD | Pertes USD | Gagnants % | Perdants % | Rendement % | DD maximal % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 10 | 4 051,49 | 2 437,10 | −2 385,61 | 40,52 | 59,48 | +1,29 | −11,34 |
| 2024 | 20 | 3 717,54 | 2 195,65 | −2 478,11 | 38,06 | 61,94 | −7,06 | −14,17 |
| 2024 | 50 | 3 717,54 | 2 195,65 | −2 478,11 | 38,06 | 61,94 | −7,06 | −14,17 |
| 2025 | 10 | 4 107,06 | 2 076,75 | −1 969,69 | 41,96 | 58,04 | +2,68 | −16,29 |
| 2025 | 20 | 3 818,95 | 1 898,21 | −2 079,26 | 39,87 | 60,13 | −4,53 | −15,95 |
| 2025 | 50 | 4 417,59 | 2 698,95 | −2 281,36 | 44,52 | 55,48 | +10,44 | −13,60 |
| 2026 partiel | 10 | 4 389,37 | 2 861,71 | −2 472,35 | 42,38 | 57,62 | +9,73 | −10,94 |
| 2026 partiel | 20 | 4 455,86 | 2 896,59 | −2 440,73 | 43,05 | 56,95 | +11,40 | −11,11 |
| 2026 partiel | 50 | 4 455,86 | 2 896,59 | −2 440,73 | 43,05 | 56,95 | +11,40 | −11,11 |

TOP20 et TOP50 identiques en 2024 et 2026 : l'élargissement du pool n'a pas
changé les positions effectivement exécutées avec le capital, les slots et
les contraintes du portefeuille. On n'achète pas automatiquement 50 titres.

## Comparaison avec la baseline précédente

Ancien `model-factory-20261012183840-6d6569` : fold figé début 2023, mêmes
données corrigées, TP20/SL10, LONG sans trailing et portefeuille annuel.
Ses métriques archivées sont contrôlées ; ses poids supprimés ne sont pas
réexécutés. Les points ci-dessous sont des différences de rendement, pas
des taux de croissance relative.

| Année | TOP10 ancien → annuel | TOP20 ancien → annuel | TOP50 ancien → annuel |
| --- | --- | --- | --- |
| 2024 | −2,26 % → +1,29 % | +16,44 % → −7,06 % | +16,44 % → −7,06 % |
| 2025 | −12,01 % → +2,68 % | −7,03 % → −4,53 % | −6,05 % → +10,44 % |
| 2026 partiel | +28,71 % → +9,73 % | +21,43 % → +11,40 % | +21,43 % → +11,40 % |

Conclusion : amélioration 2025, **pas de domination stable**. TOP10 devient
positif sur les trois périodes, mais son DD 2025 reste −16,29 %. TOP20/50
se dégradent nettement en 2024 et toutes les tailles perdent du rendement en
2026. Ce résultat ne justifie ni une promotion automatique des modèles
annuels ni l'affirmation qu'un modèle plus récent réduit toujours les pertes.
Les débuts de training, fenêtres/folds et données de fit diffèrent aussi :
on ne peut pas attribuer tout l'écart à l'âge du modèle seul.

Aucun filtre d'entrée, modèle de sortie ou TP/SL personnalisé relancé ici ;
aucun seuil ajusté après lecture de ces résultats. Les travaux prospectifs
nécessitent un GO distinct et un protocole figé.
