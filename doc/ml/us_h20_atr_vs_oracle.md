# Pilote US H20 — ATR seul contre Oracle Extreme

## Protocole figé avant exécution (3 octobre 2026)

But : mesurer la valeur ajoutée de l'Oracle sur une règle simple de volatilité. Ce n'est ni un test directionnel D1/D10, ni un backtest économique.

Source : archive E22 `artifacts/research/oracle_trajectory/e22-h20-20260915190508/o0_baseline_oos.parquet`, accompagnée de son `report.json`. Batch d'origine : `model-factory-20260909051302-323684`. L'archive contient 12 folds OOF, issus d'un entraînement expansif et d'une validation pour l'early stopping. Le code E22 purge les labels train non disponibles avant validation et les labels validation non disponibles avant test. Aucune nouvelle estimation du modèle n'est effectuée ici. Le pilote ne mesure donc pas le dernier batch de serving.

Cible conservée : `oracle_extreme10`, union des TOP/BOTTOM 10 % des rendements futurs signés dans l'univers de labellisation US H20. Les déciles ne sont pas recalculés sur le sous-ensemble comparé. Les labels sont rapprochés des lignes `target_quality_valid=1` actuelles de `global_oracle_labels` : une divergence avec l'archive bloque le test.

Trois sélections quotidiennes, chacune de `ceil(20 % × N)` titres :

- Oracle : probabilité OOF décroissante ;
- ATR : `atr20_pct` décroissant, aucune estimation ;
- aléatoire : classement par SHA256(seed=17, date, symbole), reproductible et indépendant des labels.

Même univers observable pour les trois politiques : lignes de l'archive avec un ATR fini, au minimum 20 titres par séance. Les scores Oracle doivent appartenir à [0,1], chaque couple date/symbole doit être unique et chaque date doit appartenir à un seul fold. Les ex æquo ont le même départage indépendant des labels. Les cibles inconnues/invalides sont exclues **de l'évaluation, pas du classement** ; couverture inférieure à 95 % → arrêt. Les compteurs documentent cette réserve.

## Calcul ATR fidèle au moteur US

`TR(J) = max(high-low, |high-close(J−1)|, |low-close(J−1)|)` ; `ATR20 = moyenne roulante de 20 TR` ; `atr20_pct = ATR20 / close`.

Réutilisation de `_build_adjusted_price_frame`, `_atr_value` dans `modelFactory/features.py`, et du découpage de `modelFactory/oracle/security_continuity.py`. Le ratio adj_close/close est appliqué aux OHLC, avec le fallback du moteur existant. Warm-up de 1 100 jours calendaires. Pas de volume, sentiment ou variable future dans le classement ATR.

## Mesures et interprétation

Précision : proportion de vrais extrêmes parmi les titres sélectionnés et évaluables. Rappel : proportion des extrêmes évaluables du jour retrouvés. Lift : précision / prévalence du jour. Moyennes à poids égal par séance ; détail par semestre et fold. Recouvrement : nombre de titres communs Oracle/ATR / nombre sélectionné ; Jaccard : intersection / union.

La différence appariée quotidienne Oracle−ATR exprime la valeur ajoutée de classement en points de précision. Ce pilote descriptif ne recherche pas de seuil optimal et ne décide pas un déploiement. Les séances H20 se chevauchent : ne pas les traiter comme des observations indépendantes pour calculer une significativité naïve.

## Exécution et sorties

`python -m modelFactory.us_atr_oracle_pilot`

Lectures SQL uniquement dans `alpha_trade` ; aucun upsert, aucune migration, aucun artefact de serving. Sorties sous `artifacts/research/us_atr_oracle/us-h20-<date UTC>` : `report.json`, `daily_metrics.parquet`, `comparison_panel.parquet`. Le rapport contient les hashes de provenance et la couverture. Le répertoire existant n'est jamais écrasé. Tests : `tests/test_us_atr_oracle_pilot.py`.

Réserves : univers historique de recherche et non audit de négociabilité production ; ajustements de prix disponibles aujourd'hui et non millésimes archivés quotidiennement ; univers incomplet/radiations pouvant introduire des biais. Aucune preuve de capacité LONG/SHORT ou de rentabilité nette ne peut être tirée de ces métriques d'amplitude.

## Résultats

Exécution terminée : `artifacts/research/us_atr_oracle/us-h20-20261003173850/report.json`.

Période du **8 juillet 2019 au 11 juillet 2025**, 1 512 séances, 12 folds, 2 466 symboles distincts et 2 557 086 observations communes. Aucune ligne sans ATR, aucun label inconnu/invalide dans cette intersection, aucune divergence cible entre l'archive et les labels SQL actuels. 512 031 sélections par politique, comptées comme événements quotidiens et non trades indépendants. SHA-256 OOF : `aace8266a6abe71df49a32bedec9bbeb1158424abea529b4d3d031e4396e8d46`.

| Sélection TOP20 | Précision moyenne quotidienne | Rappel | Lift |
|---|---:|---:|---:|
| Oracle O0 H20 OOF | 44,19 % | 44,23 % | 2,21 |
| ATR20 / prix | 42,54 % | 42,58 % | 2,13 |
| Référence aléatoire | 20,02 % | 20,03 % | 1,00 |

Valeur ajoutée Oracle : **+1,65 point de précision**, soit environ +3,87 % relativement à ATR. Oracle gagne sur **12/12 folds**, 75,79 % des séances ; 3,84 % sont à égalité. Recouvrement moyen Oracle/ATR : **81,16 %** ; Jaccard : 68,45 %. Ce fort recouvrement est compatible avec un rôle important de la volatilité, mais ne démontre pas causalement quelles features le modèle utilise.

| Semestre | ATR | Oracle | Écart Oracle−ATR |
|---|---:|---:|---:|
| 2019H2 | 43,79 % | 45,87 % | +2,08 points |
| 2020H1 | 40,23 % | 40,33 % | +0,11 point |
| 2020H2 | 41,16 % | 42,85 % | +1,69 point |
| 2021H1 | 44,89 % | 45,37 % | +0,47 point |
| 2021H2 | 44,23 % | 45,51 % | +1,28 point |
| 2022H1 | 43,77 % | 45,72 % | +1,94 point |
| 2022H2 | 44,89 % | 45,96 % | +1,07 point |
| 2023H1 | 40,66 % | 42,55 % | +1,89 point |
| 2023H2 | 43,24 % | 44,93 % | +1,69 point |
| 2024H1 | 40,26 % | 42,70 % | +2,44 points |
| 2024H2 | 41,81 % | 44,31 % | +2,51 points |
| 2025H1 | 41,57 % | 44,24 % | +2,67 points |
| 2025H2, 8 séances seulement | 41,88 % | 42,39 % | +0,51 point |

### Réserve qualité historique et sensibilité

L'[audit des splits](oracle_split_label_audit_20260930.md) et le [réentraînement corrigé](oracle_split_corrected_oracle14_p0g_replay_20261001.md) expliquent que les corrections NVIDIA ont été appliquées **en mémoire, sans écriture SQL**. Les fichiers corrigés référencés dans `work/guidance_pit_followup_20260930/` ne sont plus présents ici. La concordance archive/SQL n'est donc **pas une validation indépendante de leur exactitude**. Le pilote porte sur l'archive E22 historique, pas sur l'Oracle corrigé 14 folds, ni sur le nouveau batch courant.

Sensibilité descriptive ajoutée après découverte de cette réserve : retirer toutes les observations de 20 séances avant et 20 séances à partir de chacun des splits NVIDIA du 20/07/2021 et 10/06/2024. Cela retire 80 séances entières, garde 1 432 séances et évite d'effacer uniquement les mauvaises étiquettes sélectionnées. Résultat : Oracle **44,22 %**, ATR **42,62 %**, aléatoire **20,02 %**, soit **+1,61 point** Oracle−ATR. La conclusion descriptive ne dépend donc pas uniquement de ces fenêtres. Cette exclusion ne corrige pas les features/labels historiques dans les trains des folds ; **elle ne remplace pas le rejeu sur une archive corrigée**. Le calcul est reproductible par `split_window_sensitivity(comparison_panel)` dans le module du pilote.

### Conclusion et suite

L'ATR seul est un témoin très fort sur US H20. L'Oracle historique apporte un gain modeste et régulier au-delà de l'ATR, contrairement au pilote FR H5 où le gain était presque nul. Les marchés, horizons, univers et cibles ne sont toutefois pas identiques : ne pas comparer directement leurs niveaux de précision.

Ne pas remplacer ou déployer un modèle sur ce seul pilote. La confirmation propre doit reprendre les mêmes comparaisons sur le cache Oracle corrigé lorsqu'il sera restauré, puis éventuellement sur une période hors entraînement distincte. Aucun signal de sens LONG/SHORT ni résultat économique n'a été validé ici. Six tests ciblés passent ; les moteurs d'entraînement, prédiction, backtest et live ne sont pas modifiés.
