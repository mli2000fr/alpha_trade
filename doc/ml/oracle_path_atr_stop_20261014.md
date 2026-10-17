# TOP5 Oracle parcours — SL5 fixe contre SL ATR borné

## GO et protocole figé — 14 octobre 2026

Une comparaison unique, pas une nouvelle grille ni un entraînement. Les années
2024–2026 ont déjà été vues : résultats exploratoires, pas nouveau holdout.
Question : les récupérations après SL5 se traduisent-elles en un avantage net
lorsqu'on élargit le stop en conservant le même budget de risque ?

| Bras | SL choisi à J | TP | Trailing |
| --- | --- | ---: | ---: |
| FIXED_SL5 | 5 % | 20 % | 15 % |
| ATR1_BOUNDED_5_10 | `min(10 %, max(5 %, ATR20_J / close_J))` | 20 % | 15 % |

Un ATR représente une unité naturelle de true range ; bornes5/10 reprises
du périmètre des stops fixes déjà étudié. **Pas un coefficient optimal**,
aucune recherche de multiplicateurs/bornes après lecture des rendements.
Cette règle borne l'expérience, pas une recommandation pour le live.

## Chronologie et risque identique

- ATR20 **natif risque** : moyenne des20 true ranges sur OHLC split-adjusted
  archivés, préfixe<=J. Pas d'ATR réécrit pour tromper le sizer ou la liquidité.
  La normalisation adj_close du diagnostic de features n'est pas injectée dans
  les garde-fous : on utilise exactement les prix du risque et de l'exécution.
- Fraction SL choisie à J close, quantité approuvée à J ; entréeJ+1 open,
  protections ancrées au fill effectif. Ne pas recalculer la fraction avec les
  HIGH/LOW/close de J+1 et ne jamais élargir le stop d'une position déjà ouverte.
- Même budget nominal **2 % de l'equity** par entrée, avant multiplicateurs
  régime/volatilité/circuit natifs. Ce n'est PAS `.4*SL` pour le bras ATR :
  passer de5 à10 % divise approximativement la quantité par deux.
- Le gap autorisé<=3 % peut faire varier le risque dollar effectif au fill ;
  cette variation est contrôlée/archivée, pas présentée comme un budget exact
  préservé sans limite malgré un prix d'entrée différent. Gaps de sortie au
  stop peuvent dépasser le pourcentage nominal, comme dans le témoin.
- Plafond position40 % equity et exposition entrée2×, autres limites natives
  secteur/ADV/compte/breaker maintenues. Aucune réduction progressive
  supplémentaire d'exposition ; seule la taille cohérente avec le stop change.
- TP20 inchangé. Trailing15 sur sommet de séance précédente, activation quand
  il ne desserre pas le SL initial, effet à la séance suivante.
  Changer le SL change mécaniquement cette activation, pas le pourcentage15.
- Pas d'ajout à un titre déjà détenu, pas de sortie temporelleH20 ni terminale,
  positions encore ouvertes valorisées MTM. Capital initial4000USD par année.

La sous-classe recherche `ATRRiskConfig` ne change que la distance de stop
utilisée par le sizer natif. Elle conserve les overrides et limites natifs ;
aucun core de risque, modèle, YAMLlive ou protection du courtier modifié.

## Six portefeuilles appariés

| Test | Oracle CatBoost parcours | Fold causal |
| --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 |
| 2026 jusqu'au30septembre | `model-factory-20261014113232-bc35a7` | 2025-12-10 |

Reprendre les TOP5/admissions à J archivés par le sélecteur, nouveaux modèles
et empreintes contrôlés. Pas de nouvel entraînement, changement de TOP5 ou
remplacement des candidats à prix futurs inconnus. Mêmes prix locaux corrigés,
macro quotidienne, secteurs actuels explicitement acceptés et règleSTRICT des
corporate actions : preuve cash/prix/volume détenu inconnue => cas échoué.

Frais canoniques identiques, financement débit6,5 % ACT/360, maintenances
génériques conservées. Secteurs/univers actuels nonPIT, prix réajustés actuels,
macro sans vintages de publication certifiés, dividendes incomplets et marge/
spreads/fills hypothétiques restent des réserves. Pas parité broker certifiée.

Avant conclusion, le témoin FIXED_SL5 doit reproduire **exactement** les trades
et la courbe quotidienne du précédent FIXED_REFERENCE dans chaque année.
Contrôler le SL/TP/trailing et le budget par décision, fill et lot clos, cash,
latent, financement et dates. Gain net/DD, capital final, gains/pertes réalisés,
taux gagnants clos, levier moyen/max, stops effectivement exécutés rapportés.

Gate exploratoire figé : six cas complets, témoin exact, rendement ATR supérieur
et drawdown pas pire que SL5 dans **chaque** période. Sinon
`NO_GO_STABLE_ATR_STOP_ADVANTAGE`. Un échec technique reste `PARTIAL_FAILED`.
Même gate passé : aucune promotionLIVE automatique ; confirmation nouvelle
nécessaire. Pas d'autre coefficient ATR/profil/filtre lancé dans ce GO.

## Suivi et artefacts

```powershell
python -u -m scripts.research.us_oracle_path_atr_stop --output artifacts/research/us_oracle_path_atr_stop/20261014-v1 --workers 3
```

Protocole/empreintes figés avant calcul ; `progress.json` global et dans chaque
cas, `report.partial.json`, `report.json`, `annual-summary.csv`, décisions de
stop, fills tentés/committés, trades et equity. Second contrôle technique par
le même assistant, sans le présenter comme une revue humaine indépendante.
Résultats publiés séparément pour préserver ce protocole et ses empreintes.
