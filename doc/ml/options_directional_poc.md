# E7 — Options directionnelles après Oracle

## Statut

Campagne terminée le 6 septembre 2026 : `NO_GO` pour la surface 45 DTE testée.
Aucun modèle de serving, aucune table applicative et aucune règle de backtest
n'ont été modifiés.

## Question testée

E6-B1/B2 a rejeté l’achat systématique d’un straddle, mais ce résultat ne dit
pas si la **forme de la surface d’options** contient une information signée.
E7 teste une hypothèse distincte :

> Dans le TOP20 Oracle OOF, les prix relatifs, spreads, profondeurs et volumes
> des puts et calls observés à la clôture du signal J permettent-ils de mieux
> distinguer les futurs D1 et D10 ?

Le POC ne cherche pas à gagner avec les options. Les options servent uniquement
de features PIT pour choisir LONG ou SHORT sur le sous-jacent à J+1.

## Disponibilité réelle des données

La chaîne snapshot Eroya expose IV, Greeks et open interest, mais seulement dans
l’état courant. Elle ne peut pas être jointe rétroactivement à 2022–2025.

Pour l’historique, le contrat utilisable repose sur :

- le référentiel de contrats avec `as_of=J` ;
- les quotes NBBO horodatées, disponibles depuis le 7 mars 2022 ;
- les agrégats journaliers de transactions pour le volume ;
- les cours actions locaux pour le close connu à J.

L’IV historique n’est pas fournie directement. Le POC conserve donc en primaire
des ratios de prix observables. Une IV approximative peut être reconstruite à
partir des midpoints et d’un forward inféré par parité call-put, mais elle reste
diagnostique à cause des dividendes, taux et imperfections de cotation.

## Contrat PIT

```text
Clôture de la séance J
    ├── score Oracle OOF et TOP20 connus
    ├── close action J connu
    └── dernière quote options avant 15:55 ET connue
                         │
                         ▼
         calcul des features directionnelles
                         │
                         ▼
                décision pour l’open J+1
```

Il est interdit d’utiliser :

- une quote ou un trade postérieur à 15:55 ET le jour J ;
- l’open ou le gap de J+1 pour construire la feature ;
- un snapshot courant de Greeks, IV ou open interest ;
- une expiration/strike sélectionné avec un rendement futur ;
- une interpolation silencieuse lorsqu’une jambe manque.

## Échantillon préfixé

- source : événements de l’audit amplitude
  `oracle-amplitude-audit-20260906094826-0802c8` ;
- population : Oracle TOP20 OOF ;
- période NBBO : 2022-03-07 au 2025-07-11 ;
- calendrier : une date déterministe au centre de chaque semestre, comme le
  pilote E6-B ;
- tous les symboles Oracle de la date sont conservés ;
- expiration : 35–55 jours calendaires, cible 45 DTE ;
- strikes : paire ATM et ailes symétriques proches de -5 %/+5 %.

Le même snapshot 45 DTE est évalué contre les directions réalisées H3, H10 et
H20. Cela évite trois collectes et un choix de DTE a posteriori. Une term
structure multi-expiration ne sera ouverte que si cette première surface passe
les gates.

## Features primaires

| Feature | Définition | Orientation LONG préfixée |
|---|---|---|
| `otm_price_risk_reversal` | log(mid call +5 % / mid put -5 %) | valeur élevée = bullish |
| `atm_call_put_mid_log_ratio` | log(mid call ATM / mid put ATM) | valeur élevée = bullish |
| `wing_skew_asymmetry` | décroissance aile call moins décroissance aile put | valeur élevée = bullish |
| `otm_quote_depth_imbalance` | profondeur call OTM contre put OTM | valeur élevée = bullish |
| `atm_quote_depth_imbalance` | profondeur call ATM contre put ATM | valeur élevée = bullish |
| `call_put_volume_log_ratio` | log((volume call + 1)/(volume put + 1)) sur les strikes retenus | valeur élevée = bullish |
| `approx_iv_risk_reversal` | IV call OTM moins IV put OTM, forward par parité | valeur élevée = bullish, diagnostic |
| `approx_downside_skew` | IV put OTM moins IV ATM | signe inversé pour LONG, diagnostic |

Sont aussi conservés pour l’audit de qualité : DTE, distance réelle des strikes,
spread relatif de chaque jambe, âge de la dernière quote, volume nul et taux de
résolution de l’IV.

## Évaluation

L’étape E7-A est un audit univarié, sans modèle :

- IC de Spearman quotidien avec le rendement H3/H10/H20 ;
- AUC D10 contre D1 dans le pool Oracle de chaque date ;
- rendement des 20 % hauts et bas du score orienté LONG ;
- stabilité par année/fold et par semestre ;
- couverture, concentration symbole et liquidité ;
- séparation direction contre amplitude terminale absolue.

Les gates sont fixés avant collecte. Une feature primaire obtient seulement
`GO_RESEARCH` si elle réunit simultanément : couverture ≥ 40 %, IC quotidien
orienté ≥ 0,03, AUC D10/D1 ≥ 0,53, signe d’IC positif dans au moins 3 années sur
4, spread haut-bas positif et lift favorable des deux côtés. Les IV
approximatives ne peuvent pas, seules, produire un GO.

Si aucun score ne passe, la piste de surface 45 DTE est `NO_GO`. Si un score
passe, E7-B devra effectuer une ablation modèle sur exactement les mêmes folds :
baseline directionnelle contre baseline + bloc options, suivie d’une période de
confirmation distincte.

## Artefacts attendus

```text
artifacts/research/eroya_directional/options-directional-*/
  selected_events.parquet
  event_results.jsonl
  option_features.parquet
  collection_report.json
  evaluation_report.json
```

Le collecteur écrit une ligne de checkpoint après chaque événement. Un run
interrompu doit pouvoir reprendre sans refaire les appels déjà validés.

## Résultat de la campagne E7-A

### Collecte et population réellement évaluée

Artefact canonique :
`artifacts/research/eroya_directional/options-directional-20260906-0802c8/evaluation_report.json`.

| Élément | Résultat |
|---|---:|
| Événements Oracle TOP20 sélectionnés | 625 |
| Dates de signal | 8, une par semestre |
| Symboles dans la sélection | 155 |
| Surfaces complètes | 323, soit 51,68 % |
| Symboles avec au moins une surface complète | 114 |
| Observations avec rendement futur valide | 305 |
| Rejets sans surface 35–55 DTE conforme | 276 |
| Rejets pour désynchronisation des quotes | 16 |
| Rejets pour NBBO incomplet | 10 |

La couverture de collecte franchit le gate de 40 %, mais elle n'est pas dense :
presque la moitié des événements Oracle ne possède pas la surface stricte
requise. Les 323 observations complètes sont réparties de 32 à 51 par date. Le
symbole le plus représenté pèse 2,48 % et les dix premiers 22,91 % : il n'y a
pas de domination par un ticker unique, mais le petit nombre de dates reste la
limitation principale de la stabilité temporelle.

La surface sélectionnée respecte bien le contrat : DTE médian 45, plage 38–49.
Le décalage médian entre les quatre quotes est de 34 secondes et reste sous la
limite préfixée de 300 secondes. Les spreads relatifs médians sont néanmoins
élevés : 8,33 %/8,70 % sur les calls/puts ATM et 10,00 %/11,17 % sur les ailes.
Ces valeurs renforcent la prudence sur les ratios de prix, même si E7 utilise
les options comme information et non comme instruments tradés.

### Résultats directionnels

Le tableau retient, pour chaque horizon, le candidat le plus instructif. Aucun
ne passe l'ensemble des gates préfixés.

| Horizon | Feature | IC quotidien | AUC D10/D1 | Lift LONG | Lift SHORT | Stabilité annuelle | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| H3 | `wing_skew_asymmetry` | +0,0058 | 0,463 | +0,15 pt | -0,81 pt | 2/4 | rejeté |
| H10 | `approx_iv_risk_reversal` | +0,0352 | 0,548 | +1,54 pt | -0,81 pt | 2/4 | rejeté |
| H20 | `wing_skew_asymmetry` | +0,0165 | 0,556 | +1,58 pt | -0,04 pt | 2/4 | rejeté |

Lecture détaillée :

- H3 ne contient aucun signal exploitable. Même le meilleur IC est presque nul
  et l'AUC est inférieure à 0,50.
- À H10, l'IV approximative franchit isolément les gates IC et AUC, mais son IC
  devient négatif en 2024 et 2025. La tête LONG s'améliore, tandis que la queue
  SHORT se dégrade. De plus, cette feature était déclarée diagnostique : l'IV
  est reconstruite depuis les midpoints et une parité simplifiée, pas observée
  directement.
- À H20, l'asymétrie des ailes obtient une AUC de 0,556, mais un IC trop faible,
  seulement deux années positives et aucun lift SHORT. L'effet n'est donc ni
  bilatéral ni stable.
- Les autres ratios de prix et de profondeur sont faibles, inversés ou
  contradictoires selon l'horizon. Aucun score primaire ne franchit tous les
  garde-fous.

### Volume : résultat non testable, et correction effectuée

Eroya n'a retourné le volume journalier d'aucune des quatre jambes sur les 323
surfaces complètes (`volume_legs_available = 0`). La première version du POC
additionnait les valeurs absentes comme des zéros et produisait à tort un ratio
put/call constant égal à zéro. Le traitement a été corrigé : le ratio est
désormais manquant si les quatre jambes ne sont pas disponibles, y compris lors
de la réévaluation d'un ancien checkpoint.

Après correction, `call_put_volume_log_ratio` a une couverture et un nombre
d'observations égaux à zéro. Sa conclusion est `NON_TESTABLE`, et non un échec
prédictif. Le verdict global reste `NO_GO`, car cette variable constante ne
pouvait déjà faire passer aucun gate et aucune autre feature ne passe.

## Verdict et décision

La forme de la surface Options 45 DTE, construite depuis quatre quotes NBBO à
la clôture J, ne fournit pas une direction D1/D10 suffisamment stable dans le
TOP20 Oracle. Quelques effets LONG descriptifs à H10/H20 ne se généralisent pas
aux quatre années et détériorent la branche SHORT.

Conséquences :

- ne pas ouvrir l'ablation modèle E7-B ;
- ne pas ajouter ces features aux profils LONG/SHORT ou Oracle ;
- ne pas choisir un seuil, une échéance ou un sens après observation de ces
  huit dates ;
- conserver les artefacts pour éviter de répéter la même piste sous un autre
  nom ;
- considérer une nouvelle campagne Options uniquement avec une information
  réellement nouvelle : historique IV/Greeks/open interest PIT, volume fiable,
  davantage de dates indépendantes, ou microstructure alignée précisément sur
  l'heure d'entrée.
