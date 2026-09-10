# Audit de l'anomalie D10 — ruptures de continuité WFRD et CHRD

## Statut

Audit terminé le 7 septembre 2026. Le défaut a ensuite été corrigé dans le
générateur de labels et dans les consommateurs aval. La migration est livrée,
mais les labels historiques ne deviennent valides qu'après son application et
la reconstruction explicite du batch.

Périmètre :

- batch de labels : `model-factory-20260904192500-0802c8` ;
- expérience : `temporal-d1d10-v2-a-20260906-0802c8` ;
- horizon : H20 ;
- source prix impliquée : `stock_bars_daily.data_source='eodhd_eod'`.

## Verdict

La moyenne D10 anormalement élevée est causée principalement par deux séries
qui concatènent une ancienne action annulée et une nouvelle action émise après
restructuration :

- WFRD, en décembre 2019 ;
- l'historique aujourd'hui rattaché à CHRD, en novembre 2020.

Ces ruptures ne sont pas des rendements actionnariaux. Les anciennes actions
ont été annulées ; diviser le prix de la nouvelle action par le dernier prix de
l'ancienne crée donc un rendement fictif.

## Preuves dans les prix locaux

| Série | Dernier prix avant rupture | Premier prix après rupture | Rendement journalier calculé | Interprétation |
|---|---:|---:|---:|---|
| WFRD | 0,019 le 13/12/2019 | 24,50 le 20/12/2019 | +128 847 % | ancienne action annulée, nouvelle action après Chapter 11 |
| CHRD/Oasis historique | 0,12 le 19/11/2020 | 31,00 le 20/11/2020 | +25 733 % | ancienne action Oasis annulée, nouvelle action émise |

Dans les deux cas :

- `close == adj_close` ;
- `data_adjustment='split'` ;
- une seule source est présente sur les dates concernées : `eodhd_eod` ;
- aucune opération historique correspondante n'est présente dans
  `corporate_actions_events`.

L'anomalie n'est donc ni un doublon SQL ni une divergence entre deux sources.
Elle se trouve déjà dans la série split-only persistée.

## Propagation dans les labels H20

Le générateur Oracle calcule :

`future_return = prix[D+20] / prix[D] - 1`

puis classe tous les rendements finis de la date. Il ne contrôle actuellement
ni la continuité de l'action ni une rupture de corporate action.

Contamination identifiée :

| Série | Dates de signal contaminées | Labels avec rendement > 100 fois | Maximum |
|---|---|---:|---:|
| WFRD | 21/11/2019–13/12/2019 | 16 | 2 148,68 fois |
| CHRD | 23/10/2020–19/11/2020 | 20 | 434,89 fois |
| Total | — | **36** | — |

Ces 36 lignes représentent seulement 0,058 % des 62 033 observations D10 du
Dataset A, mais 67,66 % de la somme de leurs rendements.

| Mesure D10 Dataset A | Moyenne | Médiane |
|---|---:|---:|
| Données actuelles | 67,98 % | 18,15 % |
| WFRD et CHRD entièrement retirés | 21,88 % | 18,12 % |
| Rendements plafonnés à +1 000 % pour le diagnostic | 22,55 % | 18,15 % |

La médiane était donc saine ; la moyenne ne l'était pas. Le chiffre annuel
D10 2019 du rapport, +281,63 % en moyenne contre +17,08 % en médiane, ne doit
pas être utilisé comme estimation économique.

## Sensibilité du verdict Temporal V2

Par prudence, la sensibilité a retiré **toutes** les observations WFRD et CHRD
des prédictions OOF, pas uniquement les 36 lignes connues comme contaminées.

| Variante | Population | AUC same-date | AUC globale | Top 10 % = D10 | Bottom 10 % = D1 |
|---|---|---:|---:|---:|---:|
| T0 Logistic | originale | 0,51429 | 0,51466 | 53,11 % | 51,75 % |
| T0 Logistic | sans WFRD/CHRD | **0,51544** | **0,51604** | 53,05 % | 52,13 % |
| T2 Logistic N5 | originale | 0,51119 | 0,51215 | 52,63 % | 50,46 % |
| T2 Logistic N5 | sans WFRD/CHRD | **0,51143** | **0,51253** | 52,60 % | 50,62 % |

Après exclusion conservatrice, T2 N5 reste environ 0,0040 sous T0. Le
`NO_GO_DATASET_A` est donc robuste et n'a pas été provoqué par ces ruptures.

## Deuxième défaut révélé : forward-fill du prix de sortie

`load_close_matrix()` pivote les prix puis applique un `ffill()` sans limite.
Le prix à D+20 peut donc être un ancien prix reporté lorsqu'aucune barre réelle
n'existe à la date de sortie.

Sur les 890 928 labels H20 du batch, 103 utilisent une date de sortie sans
barre réelle correspondante. Dans la fenêtre Temporal V2, 22 cas sont présents :

- APG : 15, aucun dans D1/D10 ;
- WFRD : 6, tous dans D1/D10 ;
- VSH : 1, aucun dans D1/D10.

Ce défaut n'explique pas les énormes rendements positifs WFRD/CHRD, mais il
constitue une autre faiblesse du contrat de labels. Une target ne devrait pas
être déclarée disponible si son prix final provient d'un forward-fill.

## Pourquoi les contrôles existants n'ont pas bloqué

Le sanitizer calcule bien des anomalies par MAD et rendement absolu. Toutefois,
`detect_anomalies()` compte et persiste `is_anomaly`, puis
`_process_symbol()` enregistre quand même les barres et marque l'audit
`success`. Ce mécanisme est observatoire, pas bloquant.

Le générateur de labels :

1. utilise `COALESCE(adj_close, close)` ;
2. déduplique une éventuelle pluralité de sources en gardant la dernière selon
   l'ordre de `data_source` ;
3. applique un forward-fill sans âge maximal ;
4. accepte tout rendement fini, même supérieur à 100 fois ;
5. ne consulte pas un identifiant de sécurité ou un intervalle de continuité.

## Impact au-delà de Temporal V2

- **Métriques de moyenne/régression** : impact potentiellement majeur sans
  winsorisation ou filtre qualité.
- **Labels D1/D10 et Oracle Extreme** : 36 faux D10, impact numérique faible
  mais conceptuellement incorrect.
- **Features temporelles** : les rendements/momentums après la rupture sont
  également aberrants pendant leurs fenêtres rolling.
- **Backtests** : risque seulement si ces dates et symboles entrent dans le
  chemin tradé ; l'audit présent ne conclut pas sur chaque ancien backtest.
- **Temporal V2** : verdict inchangé selon la sensibilité OOF ci-dessus.

## Correctif appliqué

Le traitement n'écrête pas `future_return` : cela aurait laissé une fausse
observation dans D10 et aurait arbitrairement altéré de vrais mouvements.

Contrat désormais implémenté :

1. `raw_close` garde la présence effective des barres ; le `ffill` ne sert plus
   qu'à construire le calendrier commun.
2. Une target exige une barre réelle à D et D+H. L'absence produit
   `missing_start_bar` ou `missing_exit_bar`.
3. Les chemins WFRD et CHRD traversant les restructurations revues sont marqués
   `known_security_discontinuity` via
   `config/data_quality/security_discontinuities.json`.
4. Un saut journalier inexpliqué supérieur ou égal à 20 fois, ou inférieur ou
   égal à 1/20, met le chemin en quarantaine sous
   `extreme_unadjusted_price_jump`. Le rendement brut reste conservé pour audit.
5. Un changement de source entre les extrémités est tracé sous
   `price_source_mismatch`; un prix nul ou négatif sous `nonpositive_price`.
6. Seuls les rendements dont `target_quality_valid=1` participent au rang
   cross-sectionnel, à l'entraînement, aux audits, aux rapports et aux vues IHM.
   Les anciennes lignes ont la valeur par défaut 0 : le contrat est fail-closed.
7. Les features Oracle sont calculées sur des segments distincts avant et après
   une rupture connue ; aucune fenêtre rolling ne traverse le changement
   d'identité économique.

### Validation réelle en lecture seule

Le dry-run complet H20 du batch `model-factory-20260904192500-0802c8` donne :

| Mesure | Valeur |
|---|---:|
| Observations examinées | 890 928 |
| Labels valides | 890 789 |
| Quarantaines | 139 |
| `known_security_discontinuity` | 36 |
| `missing_exit_bar` | 103 |
| Dates sautées | 0 |

Les 36 faux rendements WFRD/CHRD et les 103 sorties forward-fillées sont donc
capturés exactement. Aucun autre rendement n'a été écrêté ou supprimé.

### Déploiement

1. Appliquer Alembic `0072_oracle_label_quality` ou le SQL
   `database/sql/ml/alter_global_oracle_label_quality.sql`.
2. Reconstruire les labels du batch voulu avec `modelFactory.oracle.build_labels`.
3. Réentraîner les modèles dont les targets ou features traversaient ces
   ruptures. Les artefacts existants ne sont pas corrigés rétroactivement.

## Références externes de contrôle

- [Weatherford 2021 Form 10-K — Chapter 11 et nouvelle entité](https://www.sec.gov/Archives/edgar/data/1603923/000160392322000051/wfrd-20211231.htm)
  confirme l'effet du plan au 13 décembre 2019, la création des nouvelles
  actions et l'annulation des intérêts du prédécesseur.
- [Oasis Form 8-K du 19 novembre 2020](https://www.sec.gov/Archives/edgar/data/1486159/000148615920000115/oas-20201119.htm)
  confirme l'annulation des anciens intérêts et l'émission de nouvelles actions.
- [Prospectus SEC Chord/Oasis](https://www.sec.gov/Archives/edgar/data/895421/000095010322012701/dp177380_424b2-w38.htm)
  confirme que CHRD ne commence à coter sous ce nom que le 5 juillet 2022 et
  que la série de prix de 2020 correspond à Oasis avant la création de Chord.
