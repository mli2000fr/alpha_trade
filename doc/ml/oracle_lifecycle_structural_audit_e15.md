# E15 — Audit structurel du lifecycle Oracle H20

## Statut

`FAIT_NO_GO_OR_BLOCKED` — aucun contrat n'est promu. L'audit isole clairement
les effets du trailing et du TP, mais le candidat primaire échoue et le contrat
sans TP, très favorable globalement, ne survit ni à la confirmation récente ni
à la sensibilité d'investabilité.

Artefact canonique :
`artifacts/research/oracle_lifecycle_structural_audit/oracle-lifecycle-audit-20260911164445`.

Le premier run `oracle-lifecycle-audit-20260911163948` est supplanté : le run
canonique ajoute la sensibilité `tradable degraded` aux huit contrats.

## Question de recherche

E12 a montré que le lifecycle PROD retire environ 2,12 points aux événements
Oracle H20. E13 et E14 n'ont pas trouvé de veto pré-entrée capable d'éviter ce
coût. E15 teste donc directement deux mécanismes :

1. le trailing est-il activé trop tôt ?
2. le take-profit coupe-t-il trop fortement la queue positive ?

Il s'agit d'un audit factoriel, pas d'une recherche du meilleur paramètre.

## Matrice pré-enregistrée

Quatre règles de trailing sont croisées avec le TP PROD activé ou absent :

| Trailing | Avec TP | Sans TP |
|---|---|---|
| PROD dès la deuxième séance | `prod` | `prod_no_tp` |
| Activation après un peak antérieur de +0,5R | `trail_after_0_5r_tp` | `trail_after_0_5r_no_tp` |
| Activation après un peak antérieur de +1R | `trail_after_1r_tp` | `trail_after_1r_no_tp` |
| Aucun trailing, stop initial maintenu | `no_trailing_tp` | `no_trailing_no_tp` |

Le candidat primaire figé avant le run est `trail_after_0_5r_tp`. Les six
autres contre-factuels hors PROD et primaire sont uniquement diagnostiques.
Aucun seuil intermédiaire n'est évalué.

## Contrat commun

- Oracle TOP20 strictement OOF du batch
  `model-factory-20260909051302-323684` ;
- LONG-only ;
- 37 659 événements dédupliqués par symbole ;
- 34 541 chemins exécutables et 3 118 rejets de gap 3 % ;
- entrée à l'open ajusté J+1 ;
- stop initial 2,5 ATR calculé avec l'ATR disponible au close J ;
- trailing à distance 2,5 ATR ;
- TP, lorsqu'il existe : `min(3 ATR, 7 %)` ;
- résolution intraday conservatrice ;
- coûts aller-retour : 6 bp ;
- sortie terminale à H20 ;
- capacité dynamique de huit positions, priorité Oracle ;
- une sortie intraday en J ne libère la place qu'à partir de J+1.

L'activation +0,5R/+1R utilise uniquement le peak des séances déjà terminées.
Un franchissement pendant J ne peut activer le trailing qu'à la séance suivante.

La parité du contrat `prod` avec le simulateur E12 est couverte par un test
unitaire exact sur date, motif, durée et rendement.

## Résultats portefeuille

| Contrat | Trades | Net moyen | Moyenne/date | Win rate | Q05 | Q01 | Durée moyenne |
|---|---:|---:|---:|---:|---:|---:|---:|
| PROD | 2 013 | +0,276 % | +0,311 % | 62,30 % | -16,31 % | -22,65 % | 6,97 j |
| **+0,5R avec TP** | **1 808** | **+0,330 %** | **+0,227 %** | **64,71 %** | **-17,77 %** | **-24,18 %** | **7,74 j** |
| +1R avec TP | 1 804 | +0,358 % | +0,346 % | 66,02 % | -17,65 % | -23,36 % | 7,75 j |
| Aucun trailing, TP | 1 803 | +0,367 % | +0,360 % | 66,11 % | -17,66 % | -23,37 % | 7,75 j |
| PROD sans TP | 1 058 | +1,810 % | +1,809 % | 41,97 % | -16,61 % | -23,51 % | 13,04 j |
| +0,5R sans TP | 985 | +0,993 % | +0,868 % | 43,35 % | -18,31 % | -23,82 % | 14,00 j |
| +1R sans TP | 914 | +1,166 % | +1,076 % | 47,70 % | -18,99 % | -24,34 % | 15,06 j |
| Aucun trailing, aucun TP | 851 | +1,094 % | +0,983 % | 43,95 % | -18,85 % | -23,67 % | 16,06 j |

Les nombres de trades diffèrent parce que chaque contrat libère les huit places
à des dates différentes. E15 fournit donc aussi une comparaison événement par
événement sur les 34 541 mêmes signaux.

## Verdict du candidat primaire +0,5R avec TP

Sur événements appariés, le delta quotidien vaut seulement `+0,0419 %`, IC95
`[-0,0330 % ; +0,1179 %]`. Après reconstruction de la capacité, il devient
`-0,0830 %`, IC95 `[-0,4011 % ; +0,2227 %]`.

Le contrat améliore 11 semestres sur 15 en valeur moyenne, mais cette mesure
masque les poids temporels :

- développement jusqu'à 2022 : delta pratiquement nul, `-0,0006 %` ;
- confirmation depuis 2023 : `-0,2327 %` par date ;
- dégradation majeure en 2023H2 : `-1,40 point` ;
- Q05 : -17,77 % contre -16,31 % ;
- Q01 : -24,18 % contre -22,65 %.

Le candidat primaire échoue donc les gates de delta, confiance, confirmation et
queues de perte.

## Ce que fait réellement le retard du trailing

| Contrat avec TP | Take profits | Trailing stops | Stops initiaux | H20 |
|---|---:|---:|---:|---:|
| PROD | 1 214 | 686 | 12 | 101 |
| +0,5R | 1 130 | 69 | 457 | 152 |
| +1R | 1 150 | 2 | 498 | 154 |
| Aucun trailing | 1 152 | 0 | 497 | 154 |

Le retard ne « sauve » pas simplement les trades. Il transforme la majorité des
sorties trailing en stops initiaux plus profonds. Le win rate progresse parce
que davantage de chemins survivent jusqu'au TP, mais les pertes restantes sont
plus lourdes. À +1R, le résultat devient presque identique à l'absence totale de
trailing : seulement deux trailing stops sont encore déclenchés.

## Attribution du TP

Avec TP PROD, Q95 et Q99 sont tous deux plafonnés à `+6,94 %` net. Sans TP et
avec trailing PROD :

- Q95 : +34,96 % ;
- Q99 : +60,23 % ;
- moyenne des 10 % meilleurs trades : +40,22 % ;
- delta portefeuille global : +0,711 %, IC95 `[+0,078 % ; +1,277 %]`.

L'effet global est réel : après retrait des dix meilleurs trades, la moyenne du
contrat reste positive à environ +1,12 %. La concentration demeure néanmoins
forte : les 20 meilleurs trades représentent 69 % du gain total.

Surtout, le comportement change dans le temps :

- delta avant 2023 : +1,380 % par date ;
- delta depuis 2023 : -0,489 % ;
- 2020H2 : +8,68 % moyen ;
- 2021H2 : +2,77 % contre -1,73 % pour PROD ;
- 2024H2 : -0,99 % contre +1,70 % pour PROD.

Le très fort +32,67 % de 2025H2 repose sur trois trades seulement et ne constitue
pas une validation. Le contrat sans TP était diagnostique et ne peut pas être
promu après lecture de ces résultats.

## Sensibilité à l'investabilité

Les snapshots stricts `full` ne couvrent toujours que 60 dates. La sensibilité
`degraded` donne :

| Contrat | Trades | Net moyen | Moyenne/date |
|---|---:|---:|---:|
| PROD | 620 | -0,019 % | -0,043 % |
| +0,5R avec TP | 606 | +0,226 % | +0,174 % |
| +1R avec TP | 591 | +0,113 % | +0,082 % |
| Aucun trailing, TP | 591 | +0,102 % | +0,068 % |
| PROD sans TP | 529 | -0,360 % | -0,417 % |
| +0,5R sans TP | 508 | -0,256 % | -0,317 % |
| +1R sans TP | 479 | +0,057 % | -0,104 % |
| Aucun trailing, aucun TP | 457 | -0,198 % | -0,336 % |

L'avantage global du sans TP disparaît totalement. Certains grands gagnants du
pool large incluent des instruments comme `ETHE`, ce qui confirme que la
composition de l'univers est déterminante. Ces snapshots restent dégradés et ne
sont pas une preuve canonique, mais ils interdisent de considérer le résultat
large comme directement tradable.

## Gates primaires

| Gate | Résultat |
|---|---|
| Delta événement positif | PASS marginal |
| Borne basse IC95 événement > 0 | FAIL |
| Delta portefeuille positif | FAIL |
| Borne basse IC95 portefeuille > 0 | FAIL |
| Q05 non dégradé | FAIL |
| Q01 non dégradé | FAIL |
| Confirmation depuis 2023 positive | FAIL |
| Lift positif dans ≥ 70 % des semestres | PASS |
| Univers tradable PIT strict complet | FAIL |

Verdict : `NO_GO_OR_BLOCKED`.

## Conclusion et suite

E15 rejette l'hypothèse simple « le trailing est seulement activé trop tôt ».
Retarder son activation augmente la profondeur des pertes restantes et ne crée
pas de lift portefeuille robuste.

E15 montre aussi que le TP détruit une convexité historique importante, mais
que cette convexité est instable, concentrée et absente de la sensibilité
tradable. Il ne faut ni supprimer le TP, ni rechercher maintenant un autre
seuil ATR/R sur ces mêmes données.

Une suite scientifiquement défendable nécessite d'abord un univers tradable PIT
`full`. Ensuite seulement, un contrat sans TP ou TP dynamique pré-enregistré
pourrait être confirmé sur une période réellement nouvelle. En attendant, le
lifecycle PROD reste inchangé.

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_lifecycle_structural_audit --oracle-gate artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet --bootstrap-samples 2000 --log-level INFO
```

Tests : `tests/test_oracle_lifecycle_structural_audit.py` et tests E12 associés.

