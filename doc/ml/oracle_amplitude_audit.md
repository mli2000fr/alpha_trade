# E6 — Audit direction-neutral de l’amplitude Oracle

## Décision recherchée

Les expériences E2 à E5 n’ont pas trouvé de signal directionnel OOF suffisamment
stable pour séparer D1 de D10. E6 change donc de question : **l’Oracle concentre-t-il
réellement de l’amplitude future, même si son sens reste inconnu ?**

Cette vérification précède obligatoirement toute étude d’une stratégie neutre en
direction (straddle/strangle ou autre exposition à la volatilité). Une option a un
coût, une volatilité implicite et une exposition au temps : un simple mouvement
absolu positif ne suffit pas à démontrer sa rentabilité.

## Source et absence de fuite

La population vient exclusivement de `_oracle_oof_gate.parquet` du batch Oracle.
Ce fichier contient le score produit sur les fenêtres de test walk-forward pour
tout l’univers quotidien, pas uniquement les observations retenues.

- signal connu : clôture de J ;
- score : `directional_oracle_extreme_pct`, percentile cross-sectionnel OOF ;
- TOP20 : percentile supérieur ou égal à 0,80 ;
- entrée de mesure : open de J+1 ;
- exclusion : gap absolu supérieur à 3 % ;
- aucun signe futur, D1/D10 ou rendement futur ne participe à la sélection ;
- une fenêtre H incomplète est censurée, jamais raccourcie.

Le contrôle est apparié par date afin d’éviter qu’un semestre volatil, contenant
plus d’observations, domine mécaniquement le résultat.

## Mesures d’amplitude

Pour H3, H5, H10 et H20, où H compte les séances détenues en incluant J+1 :

| Mesure | Définition | Interprétation |
|---|---|---|
| `abs_terminal_return` | valeur absolue du rendement open J+1 → close H | déplacement net sans le sens |
| `max_up_excursion` | plus haut de la fenêtre / entrée − 1 | amplitude disponible côté hausse |
| `max_down_excursion` | 1 − plus bas de la fenêtre / entrée | amplitude disponible côté baisse |
| `max_abs_excursion` | maximum des excursions hausse et baisse | mesure primaire d’amplitude atteignable |
| `max_abs_excursion_capped_100pct` | excursion précédente plafonnée à 100 % | mesure primaire robuste, sans domination par quelques titres |
| `realized_range` | (plus haut − plus bas) / entrée | étendue totale parcourue |
| `realized_vol` | racine de la somme des log-rendements au carré | variation réalisée du chemin |
| `barrier_hit` | excursion max ≥ min(3×ATR14, 7 %) | fréquence d’un mouvement économiquement notable |

L’ATR est calculé à J. Les high/low de la séance d’entrée sont inclus dans E6,
car une exposition ouverte à l’open peut subir ou capter le mouvement intraday.
Ce contrat diffère volontairement des labels de première touche E4, où les exits
ne pouvaient pas intervenir le jour d’entrée.

Les historiques contiennent aussi des discontinuités de symbole ou de
restructuration non corrigées par `adj_close` (par exemple un passage de quelques
centimes à plusieurs dizaines de dollars). Une fenêtre est donc censurée si deux
clôtures adjacentes présentent un facteur supérieur à 4 dans un sens ou l’autre.
Le résultat principal plafonne en plus chaque excursion à 100 %. Les métriques
brutes et les médianes quotidiennes restent exportées pour audit.

## Comparaisons

Chaque jour, le module compare :

```text
TOP20 Oracle (80e–100e percentile)
 ├── contre REST80 (0e–80e percentile)
 └── contre NEXT20 (60e–80e percentile)
```

Le premier contrôle mesure la concentration générale. Le second est plus dur :
il vérifie que le seuil TOP20 apporte quelque chose par rapport aux candidats
juste sous le seuil.

Les sorties incluent : moyenne de chaque groupe, lift absolu et relatif, part des
jours à lift positif, IC de Spearman quotidien score/amplitude, intervalle normal
à 95 %, détail semestriel et courbe par décile Oracle.

## Gates préfixés pour ouvrir E6-B

La piste options n’est ouverte que si les six conditions passent sur la mesure
primaire H20, sans modifier leurs seuils après observation :

1. lift relatif moyen TOP20/REST80 de l’excursion plafonnée à 100 % ≥ 10 % ;
2. lift positif sur au moins 55 % des jours ;
3. Spearman quotidien moyen ≥ 0,03 ;
4. lift positif dans au moins 60 % des semestres ;
5. lift de `max_abs_excursion` positif sur H3/H5/H10/H20 ;
6. lift positif du taux de touche de barrière H20.

Ces gates établissent une valeur de classement de l’amplitude. Ils ne constituent
pas une preuve de profitabilité options. E6-B devra encore comparer volatilité
réalisée et implicite au moment PIT, spread, liquidité, theta et IV crush.

## Exécution

```powershell
python -u -m modelFactory.oracle_amplitude_audit --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2018-07-05 --end-date 2025-07-11 --horizons 3,5,10,20 --log-level INFO
```

`--symbols-limit` est réservé aux tests techniques. Il ne doit pas servir au
verdict scientifique, car prendre les premiers symboles par ordre alphabétique
modifierait la composition cross-sectionnelle.

## Artefacts

Le répertoire `artifacts/models/shared_directional/oracle-amplitude-audit-*`
contient :

- `report.json` : contrat, population, résultats, gates et décision E6-B ;
- `event_metrics.parquet` : métriques par date/symbole ;
- `daily_metrics.parquet` : comparaisons journalières appariées ;
- `decile_metrics.csv` : relation score/amplitude par décile.

Le module est **research-only** : il ne modifie ni serving, ni prédictions, ni
backtest, ni tables de production.

## Résultat canonique du 6 septembre 2026

Source : `model-factory-20260904192500-0802c8`. Artefact robuste :
`oracle-amplitude-audit-20260906094826-0802c8`.

Population : 630 883 lignes du gate, 399 symboles, 1 764 dates OOF entre le
5 juillet 2018 et le 11 juillet 2025. Après disponibilité de l’entrée, filtre de
gap et fenêtre future complète, 600 717 observations H20 sont mesurables
(`95,22 %`). Cinquante fenêtres supplémentaires ont été censurées par le contrôle
de rupture de prix.

| Horizon | TOP20 excursion max plafonnée | REST80 | NEXT20 | Lift relatif TOP20/REST80 | Jours avec lift positif | Spearman quotidien | Touche barrière TOP20/REST80 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| H3 | 7,86 % | 4,29 % | 5,64 % | +85,7 % | 99,9 % | 0,551 | 42,6 % / 13,5 % |
| H5 | 10,52 % | 5,71 % | 7,55 % | +86,3 % | 100,0 % | 0,555 | 62,8 % / 26,6 % |
| H10 | 15,31 % | 8,32 % | 11,00 % | +86,7 % | 99,9 % | 0,563 | 86,2 % / 52,3 % |
| H20 | 22,07 % | 12,05 % | 15,92 % | +86,4 % | 100,0 % | 0,570 | 97,6 % / 79,2 % |

Le rendement terminal absolu H20 est également nettement supérieur : `14,06 %`
dans le TOP20 contre `7,61 %` dans le REST80. La médiane brute par observation
confirme que le résultat n’est pas produit par la moyenne : `17,78 %` contre
`9,05 %` pour le BOTTOM60 et `13,33 %` pour le NEXT20.

La relation est strictement croissante sur les dix déciles : l’excursion H20
plafonnée passe de `8,50 %` au décile 1 à `25,19 %` au décile 10. Le lift H20 est
positif dans tous les semestres complets. Il diminue toutefois de `+11 à +17 points`
pendant 2020–2022 à environ `+7,5 à +8,6 points` pendant 2023–2025. `2025H2` ne
contient que huit dates et ne doit pas être interprété isolément.

### Verdict E6-A

Les six gates préfixés passent. **L’Oracle possède une valeur d’amplitude OOF
forte, monotone et stable ; son échec précédent concerne bien le sens, pas la
détection des grands mouvements.** E6-B, étude économique d’une exposition
direction-neutral, est donc ouverte. Ce verdict ne signifie pas encore qu’un
straddle est rentable : l’écart entre mouvement réalisé et volatilité implicite,
le spread, le theta, la disponibilité historique PIT et l’IV crush restent à
mesurer.
