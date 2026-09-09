# P0i — Évaluation holdout de l'Oracle dynamique shadow

## Verdict

P0i est **GO pour la détection d'amplitude en shadow**, y compris sur 2026H1.
Il reste **NO-GO pour une consommation trading directe**, car l'Oracle ne prédit
pas le sens et le diagnostic signé redevient presque équilibré en 2026.

Le batch évalué est `model-factory-20260909051302-323684`. Les scores proviennent
du run shadow `oracle-shadow-20260909091757-323684`, jamais des tables de serving.

## Pourquoi les labels du run shadow n'ont pas été utilisés tels quels

Le run contenait 489 511 scores sur 243 séances. Ses rendements réalisés étaient
présents en 2025H2, mais absents sur les 253 697 lignes de 2026H1 : la prédiction
relisait les labels associés au batch d'entraînement, dont la fenêtre s'arrêtait
au 31 décembre 2025.

P0i a donc reconstruit les labels H20 depuis `stock_bars_daily`, en mode
`dry-run`, avec le même univers quotidien P0b. Cette reconstruction :

- ne modifie aucune table ;
- utilise le prix ajusté, sinon le close ;
- exige une vraie barre à D et D+20 ;
- rejette les changements de source et discontinuités connues ;
- rejette les ruptures de prix non expliquées supérieures à 20× ;
- recalcule TOP10 et BOTTOM10 dans l'univers admis du jour.

Elle produit 462 461 labels valides sur 230 dates, du 14 juillet 2025 au
10 juin 2026. Les treize dernières séances du shadow n'ont pas vingt séances
futures disponibles dans les données et ne sont pas évaluées. Parmi les lignes
dont l'horizon est réalisé, seuls 237 labels sont invalides : 236 sorties sans
barre réelle et une rupture extrême de prix non ajustée.

## Résultats principaux

| Mesure | Ensemble | 2025H2 | 2026H1 |
|---|---:|---:|---:|
| lignes valides | 462 461 | 235 814 | 226 647 |
| séances | 230 | 120 | 110 |
| AUC extrême | **0,7742** | 0,7774 | **0,7727** |
| précision TOP10 | **49,12 %** | 49,95 % | **48,21 %** |
| précision TOP20 | **44,19 %** | 44,74 % | **43,59 %** |
| rappel TOP20 | 44,23 % | 44,78 % | 43,63 % |
| rendement absolu moyen du TOP20 | **12,20 %** | 11,02 % | **13,49 %** |
| lift d'amplitude TOP20 | **1,757** | 1,801 | **1,709** |
| rétention de l'amplitude extrême TOP20 | 68,68 % | 69,45 % | 67,84 % |

La prévalence d'un vrai extrême est de 20 %. Une précision TOP20 de 44,19 %
signifie donc que le gate contient environ 2,21 fois plus de vrais extrêmes que
le hasard. Le TOP20 affiche une amplitude absolue H20 moyenne de 12,20 %, contre
environ 6,98 % dans l'univers quotidien complet.

Le bootstrap mobile par blocs de 21 séances donne, pour le lift TOP20 moins un,
un intervalle à 95 % de `[0,692 ; 0,812]`. Même la borne basse reste très loin
de zéro. En 2026H1, l'intervalle reste `[0,601 ; 0,809]` : le signal d'amplitude
survit à la période où les stratégies directionnelles ont échoué.

## Monotonie correcte pour un modèle d'amplitude

La métrique historique `decile_monotonicity` de l'ancien comparateur reposait
sur le rendement **signé** moyen. Elle n'est pas adaptée à un Oracle qui cherche
indifféremment D1 et D10. P0i utilise le rendement absolu.

| Décile du score | Rendement absolu H20 moyen |
|---:|---:|
| 1 | 1,72 % |
| 2 | 2,97 % |
| 3 | 4,71 % |
| 4 | 5,53 % |
| 5 | 6,26 % |
| 6 | 7,01 % |
| 7 | 7,92 % |
| 8 | 9,41 % |
| 9 | 10,87 % |
| 10 | **13,59 %** |

Les dix déciles sont strictement croissants ; la monotonie de Spearman sur
l'amplitude vaut 1,0. C'est une preuve plus directement exploitable que le
Brier ou la moyenne signée.

## 2026 : amplitude préservée, direction absente

Le TOP20 shadow contient les deux queues. Sur les vrais extrêmes qu'il retrouve :

| Diagnostic non utilisé comme gate | 2025H2 | 2026H1 |
|---|---:|---:|
| extrêmes réalisés positifs | 54,73 % | **51,27 %** |
| tous candidats TOP20 à rendement positif | 56,50 % | **51,40 %** |

En 2026H1, la répartition positive/négative est donc presque 50/50 alors que
l'AUC extrême reste à 0,7727. Cela tranche la question : l'Oracle continue à
identifier les gros mouvements ; la perte des stratégies directionnelles ne
vient pas d'un effondrement du détecteur d'amplitude.

Le rendement signé moyen positif du TOP20 ne doit pas être interprété comme une
capacité LONG : les queues ne sont pas symétriques en magnitude et ce résultat
ne constitue ni une probabilité directionnelle, ni un gate stable.

## Univers, rotation et concentration

- 1 925 à 2 105 titres admis par séance, médiane 2 005 ;
- 2 360 symboles admis au moins une fois ;
- turnover Jaccard quotidien moyen : 0,78 % ; maximum : 1,72 % ;
- 877 symboles apparaissent au moins une fois dans le TOP20 évalué ;
- le symbole le plus fréquent ne représente que 0,248 % des sélections ;
- les dix symboles les plus fréquents représentent 2,48 %.

Le résultat n'est donc pas porté par quelques titres et l'admission P0b ne crée
pas une rotation quotidienne excessive.

## Référence OOF antérieure

Il n'existe pas de prédictions d'un Oracle fixe sur les mêmes dates : les trois
batches témoins disponibles s'arrêtent au 11 juillet 2025. P0i ne fabrique donc
pas une fausse comparaison appariée.

À titre de contexte seulement, le P0f OOF du 15 juillet 2024 au 11 juillet 2025
avait une AUC de 0,7661 et un lift TOP20 de 1,696. Le shadow suivant atteint
respectivement 0,7742 et 1,757. Les périodes ne sont pas identiques ; ces deltas
ne sont pas une preuve causale, mais ils ne montrent aucun vieillissement
manifeste du dernier champion.

## Décision

1. Valider P0i pour la fonction **détection d'amplitude**.
2. Ne pas réouvrir l'optimisation D1/D10 à partir de ces mêmes données.
3. Ne pas envoyer le shadow au backtest ou au trading.
4. Ouvrir P0j comme canary shadow quotidien avec suivi de dérive et labels
   retardés H20.
5. Ne promouvoir un gate de trading que lorsqu'une source directionnelle
   indépendante aura passé son propre holdout.

## Reproduction

Labels post-hoc sans écriture en base :

```powershell
python -u -m modelFactory.oracle.build_labels --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2025-07-14 --end-date 2026-06-30 --universe-mode pit_dynamic_bars --symbols-file config/univers/univers_filtred.txt --dry-run --output-parquet artifacts/research/oracle_universe_p0i/labels_h20_20250714_20260630.parquet
```

Évaluation :

```powershell
python -u -m modelFactory.oracle_universe_p0i_evaluate --shadow-dir artifacts/models/oracle/shadow/model-factory-20260909051302-323684/oracle-shadow-20260909091757-323684 --labels artifacts/research/oracle_universe_p0i/labels_h20_20250714_20260630.parquet --reference-batch model-factory-20260909051302-323684 --reference-start 2024-07-14 --reference-end 2025-07-11
```

Artefacts officiels :

```text
artifacts/research/oracle_universe_p0i/p0i-20260909100956/report.json
artifacts/research/oracle_universe_p0i/p0i-20260909100956/by_semester.csv
artifacts/research/oracle_universe_p0i/p0i-20260909100956/by_month.csv
artifacts/research/oracle_universe_p0i/p0i-20260909100956/amplitude_by_score_decile.csv
```
