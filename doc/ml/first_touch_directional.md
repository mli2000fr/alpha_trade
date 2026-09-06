# E4 — Direction par première barrière symétrique touchée

## Statut

E4 est une expérience de recherche autonome. Elle ne modifie ni les modèles
servis, ni `model_predictions`, ni la cascade du backtest. Un artefact E4 porte
toujours `research_only=true` et `serving_ready=false`.

Le point de départ est un batch Oracle Extreme déjà entraîné et son cache OOF
`_oracle_oof_gate.parquet`. E4 travaille exclusivement sur les événements qui
appartiennent au TOP20 Oracle OOF. Le score Oracle sert de filtre de population,
jamais de feature directionnelle.

## Question testée

Les expériences précédentes ont montré que :

- la prévision du rendement directionnel moyen est proche de zéro ;
- les têtes de risque extrême LONG et SHORT détectent mieux les accidents mais
  leur asymétrie ne donne pas la direction ;
- un rendement terminal à H20 mélange le chemin, le timing et le sens.

E4 pose donc une question plus élémentaire :

> Parmi les événements dont l’Oracle prévoit une forte amplitude, le prix
> touche-t-il d’abord une barrière haussière ou une barrière baissière ?

La formulation conserve explicitement les cas où les données journalières ne
permettent pas de connaître l’ordre intraday et ceux où aucun mouvement assez
fort ne se développe.

## Chaîne de données

```text
Oracle Extreme OOF
        │
        ├── percentile extrême >= 80 % ──> population TOP20
        │                                  (score non fourni au modèle)
        │
        └── features PIT au signal J ─────> CatBoost multiclasses mutualisé
                                             │
                                             ├── P(UP_FIRST)
                                             ├── P(DOWN_FIRST)
                                             ├── P(AMBIGUOUS)
                                             └── P(NO_TOUCH)
                                                      │
                   gagnant UP/DOWN + marge suffisante ┤
                                                      ▼
                                             LONG / SHORT / ABSTAIN
```

## Contrat temporel et prix

Pour un signal daté `J` :

1. les features et l’ATR sont arrêtés à la clôture de `J` ;
2. l’entrée théorique intervient à l’open de la séance tradable suivante ;
3. l’événement est écarté si le gap absolu entre le close `J` et cet open
   dépasse 3 % ;
4. aucune barrière ne peut être déclenchée pendant la séance d’entrée ;
5. les séances suivantes sont parcourues dans l’ordre, jusqu’à H20 inclus.

L’ATR utilise le lissage de Wilder sur 14 séances. Sa valeur est calculée à
`J`, sans high/low de la séance d’entrée. La distance commune aux deux côtés
vaut :

```text
distance = min(3 × ATR_J, 7 % × prix_entrée)
barrière_haute = prix_entrée + distance
barrière_basse = prix_entrée - distance
```

Un plancher d’ATR égal à 0,1 % du prix d’entrée évite une distance nulle ou
absurde sur un actif très peu volatil.

## Les quatre classes

### `UP_FIRST`

La barrière haute est franchie avant la barrière basse. Un gap d’open au-dessus
de la barrière compte comme une touche haussière.

### `DOWN_FIRST`

La barrière basse est franchie avant la barrière haute. Un gap d’open sous la
barrière compte comme une touche baissière.

### `AMBIGUOUS`

Le high et le low d’une même barre journalière franchissent les deux barrières.
Avec de l’OHLC quotidien, l’ordre réel est inconnu. E4 ne choisit pas une règle
optimiste ou pessimiste : le cas devient une classe à part entière.

### `NO_TOUCH`

Aucune barrière n’est atteinte pendant les 20 séances observables après
l’entrée. Cette classe signifie « amplitude insuffisante selon le contrat E4 »,
pas nécessairement absence totale de variation.

## Modèle

Le modèle est un CatBoost multiclasses unique, mutualisé sur tous les symboles
du TOP20 Oracle. Le profil de features par défaut est
`config/features/shared_direction/shared.json`.

Configuration de référence :

| Paramètre | Valeur |
|---|---:|
| Loss / métrique de validation | `MultiClass` |
| Pondération des classes | `Balanced` |
| Itérations maximales | 600 |
| Profondeur | 6 |
| Learning rate | 0,03 |
| Early stopping | 60 itérations |
| Contexte symbole/secteur | aucun |
| Seed | 42 |

La pondération équilibrée évite que `NO_TOUCH` ou une autre classe dominante
écrase les classes directionnelles. Le modèle final est réentraîné sur toute la
population labellisée avec la médiane du nombre d’itérations retenu par les
folds.

## Walk-forward et prévention des fuites

Le découpage reprend le moteur causal partagé :

- train expansif minimal : 504 dates ;
- validation : 126 dates ;
- test strictement OOS : 126 dates ;
- pas : 126 dates ;
- maximum : 12 folds ;
- purge : 20 séances, égale à l’horizon de la cible.

La validation pilote uniquement l’early stopping. Les seuils de décision et les
gates sont préfixés ; aucun seuil n’est optimisé sur les folds de test.

La période réellement disponible peut être plus courte que `--end-date`. Le
contrat enregistre donc séparément les dates demandées et les dates effectives
du cache Oracle OOF. Avec le batch Oracle utilisé pendant E3/E4, le cache OOF
s’arrête actuellement en juillet 2025 : une commande finissant en décembre 2025
n’évalue pas artificiellement les mois absents.

## Politique de décision

La classe de probabilité maximale doit être `UP_FIRST` ou `DOWN_FIRST`. Si le
gagnant est `AMBIGUOUS` ou `NO_TOUCH`, la décision est `ABSTAIN`.

Ensuite :

```text
marge = |P(UP_FIRST) - P(DOWN_FIRST)|

si gagnant = UP_FIRST   et marge >= 0,10 : LONG
si gagnant = DOWN_FIRST et marge >= 0,10 : SHORT
sinon                                  : ABSTAIN
```

La marge primaire 0,10 est fixée avant le run. Les marges 0,00, 0,05, 0,10 et
0,15 sont toutes publiées à titre diagnostique. Elles ne doivent pas être
choisies après lecture de la meilleure performance OOS.

## Évaluation statistique

Le rapport contient :

- distribution des quatre classes ;
- accuracy globale ;
- balanced accuracy, moyenne des recalls par classe ;
- F1 macro sur les quatre classes ;
- matrice de confusion complète ;
- AUC directionnelle calculée uniquement entre les vrais `UP_FIRST` et
  `DOWN_FIRST`, avec le score normalisé
  `P(UP)/(P(UP)+P(DOWN))` ;
- stabilité de l’AUC par fold.

L’accuracy seule ne suffit pas : un modèle qui prédit toujours la classe la plus
fréquente peut sembler correct sans résoudre la direction.

## Évaluation économique

Pour éviter que la cible E4 décide elle-même du résultat financier, la mesure
économique réutilise les deux replays indépendants `barrier_race_v1` d’E3 :

- rendement net si le même événement était joué LONG ;
- rendement net s’il était joué SHORT ;
- stop 2,5 ATR ;
- TP `min(3 ATR, 7 %)` ;
- sortie maximale H20 ;
- spread, commission, slippage et borrow fee inclus.

Ces rendements ne sont ni des features ni la cible d’entraînement. Ils servent
uniquement après la prédiction OOS pour comparer la décision E4 à :

- une décision aléatoire 50/50 sur exactement les mêmes événements ;
- toujours LONG ;
- toujours SHORT ;
- le meilleur des deux côtés statiques, calculé sur la population évaluée.

Le replay E3 n’est pas le lifecycle production : il n’utilise pas le trailing
risk-based PROD. Par conséquent, une réussite E4 serait une preuve de signal
directionnel, pas une validation finale de stratégie.

## Métriques de la politique

Pour chaque marge :

- couverture : décisions LONG/SHORT divisées par tous les événements ;
- répartition LONG/SHORT ;
- précision de première touche ;
- rendement net moyen et médian ;
- win rate économique ;
- fréquence où le côté choisi rapporte plus que l’autre replay ;
- lift contre le choix aléatoire 50/50 ;
- lift contre le meilleur côté statique ;
- fréquence des pertes catastrophiques inférieures ou égales à -20 % ;
- CVaR 5 %, pire rendement et concentration du profit par symbole ;
- résultats par semestre et par fold.

## Gates préfixés

E4 ne peut être considéré prometteur que si tous les gates suivants passent :

| Gate | Seuil |
|---|---:|
| AUC directionnelle moyenne des folds | ≥ 0,53 |
| Folds avec AUC > 0,50 | ≥ 7 |
| Couverture à la marge primaire | ≥ 20 % |
| Précision directionnelle | ≥ 55 % |
| Lift de précision vs majorité | ≥ 3 points |
| Rendement net moyen | > 0 |
| Lift de rendement vs random 50/50 | ≥ 0,25 point |
| Folds avec lift positif | ≥ 7 |
| Folds avec rendement positif | ≥ 7 |
| Folds battant le meilleur côté statique | ≥ 7 |
| Part du premier symbole dans les contributions positives | ≤ 35 % |

Ces gates sont volontairement exigeants. Un bon F1 macro sans rendement, ou un
rendement positif concentré sur un symbole, ne valide pas la piste.

## Artefacts

Chaque run crée un répertoire sous
`artifacts/models/shared_directional/shared-first-touch-*` contenant :

- `contract.json` : contrat complet, période effective, population et métriques ;
- `metrics.json` : résultats globaux, folds, semestres et gates ;
- `oof_predictions.parquet` : probabilités et décisions reproductibles par
  événement OOS ;
- `first_touch_model.cbm` : modèle final de recherche ;
- `feature_profile.json` : copie exacte et hashée du profil utilisé.

Le modèle final existe pour reproductibilité. Le drapeau `serving_ready=false`
interdit de l’interpréter comme un modèle déployable.

## Commande de référence

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.first_touch_directional --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --barrier-atr-mult 3.0 --barrier-max-pct 0.07 --max-sessions 20 --max-entry-gap-pct 0.03 --primary-margin 0.10 --context-mode none --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --log-level INFO
```

## Interprétation des issues

- **Tous les gates passent** : répéter sur une vraie période de confirmation
  encore invisible, puis seulement étudier l’intégration au backtest.
- **AUC/F1 passent mais pas le rendement** : le modèle comprend l’ordre des
  barrières, mais ce contrat ne produit pas une décision économique utile.
- **Rendement passe mais pas la stabilité** : résultat probablement concentré
  ou dépendant du régime ; aucune promotion.
- **`AMBIGUOUS` domine** : les données journalières ne suffisent pas ; il faut
  des données intraday, pas une règle arbitraire.
- **`NO_TOUCH` domine** : le TOP20 Oracle et la barrière choisie ne décrivent pas
  le même événement d’amplitude.
- **AUC proche de 0,50 et lift nul** : la piste première touche est rejetée pour
  ces features et cette population.

## Limites

1. L’OHLC quotidien ne donne pas l’ordre intraday lors d’une double touche.
2. Les survivorship biases éventuels de l’univers source ne sont pas corrigés
   par E4.
3. La disponibilité OOF de l’Oracle borne la période réellement testable.
4. Les barrières 3 ATR / 7 % sont un contrat préfixé, pas des paramètres
   optimisés.
5. Le modèle final ne constitue pas une preuve OOS ; seules les prédictions des
   folds le sont.
6. Toute comparaison future de marges doit être faite sur une nouvelle période,
   sans sélectionner rétroactivement la meilleure marge de ce rapport.
