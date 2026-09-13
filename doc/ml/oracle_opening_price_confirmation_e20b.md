# E20-B — Confirmation Oracle strictement price-only

## Objet et état

E20-B cherche à savoir si la trajectoire des prix juste après l'ouverture peut
séparer les futurs D1 et D10 parmi les événements Oracle TOP20. Le harnais est
implémenté, testé et **en attente de données compatibles**. Il ne faut pas
confondre cet état avec un résultat positif ou négatif.

Cette étape précède toute utilisation du volume. Elle permet de répondre à une
question simple et falsifiable : l'information directionnelle vient-elle déjà
du prix, ou faut-il une information de microstructure supplémentaire ?

## Source et portée

| Élément | Contrat |
|---|---|
| Population | événements Oracle TOP20 OOF avec label de qualité valide |
| Séance observée | prochaine séance NYSE J+1 |
| Source | Alpaca historical stocks bars |
| Feed | SIP consolidé retardé |
| Ajustement intraday | `raw` |
| Fenêtre | 09:30–10:30 New York |
| Colonnes admises | `open`, `high`, `low`, `close` |
| Colonnes interdites | volume minute/cumulé, trade count, VWAP |
| Serving/backtest | aucun changement |

Le plan Alpaca Basic autorise la recherche historique SIP lorsque la fin de la
requête est âgée d'au moins quinze minutes. Cela ne donne pas une confirmation
SIP temps réel à 09:30. Pour une décision réelle à 10:00, les données utilisées
par la recherche ne seraient disponibles gratuitement qu'après 10:15.

## Construction causale des checkpoints

La première barre admissible entre 09:30 et 09:35 fournit `opening_price`. Si
la première transaction arrive plus de cinq minutes après 09:30, le titre est
inéligible : le harnais n'invente pas une ouverture.

Pour chaque checkpoint `m ∈ {5,15,30,60}` :

```text
fenêtre admise = 09:30 ... 09:(30+m-1)
price_m        = close de la dernière barre admise
return_m       = price_m / opening_price - 1
range_m        = max(high) / min(low) - 1
max_up_m       = max(high) / opening_price - 1
max_down_m     = min(low) / opening_price - 1
close_location = (price_m - min(low)) / (max(high) - min(low))
```

La dernière barre ne peut pas être âgée de plus de trois minutes au checkpoint.
Une barre postérieure ne peut jamais modifier un checkpoint antérieur. Les tests
unitaires verrouillent cette propriété anti-lookahead.

## Politique primaire pré-enregistrée

La seule politique autorisée à décider du verdict est :

```text
checkpoint = 30 minutes
seuil absolu = 0,50 %

return_30m > +0,50 % → LONG
return_30m < -0,50 % → SHORT
sinon                  → ABSTENTION
```

Les checkpoints 5/15/60 minutes et les seuils 0/0,25/0,50/1,00 % sont exportés
comme diagnostics secondaires. Ils ne peuvent pas remplacer la politique
primaire après lecture des résultats sans nouvelle confirmation indépendante.

## Mesures et gates

Les mesures comprennent couverture prix, taux d'abstention, part LONG,
précision directionnelle, précision D1/D10, rendement cible H signé, stabilité
par fold et semestre, ainsi qu'un intervalle bootstrap par blocs de 21 séances.

Pour ouvrir une ablation incrémentale ajoutant le volume, la politique primaire
doit satisfaire simultanément :

- au moins 126 dates et 5 000 événements observés ;
- couverture prix d'au moins 60 % ;
- au moins 1 000 décisions, dont 500 événements D1/D10, et un taux de sélection
  d'au moins 15 % ;
- précision directionnelle d'au moins 52 % ;
- précision D1/D10 d'au moins 55 % ;
- borne basse à 95 % du rendement cible signé strictement positive ;
- au moins 60 % des folds et 60 % des semestres positifs.

Un passage donne `GO_RESEARCH_VOLUME_ABLATION`, jamais une promotion production.
Un manque de matière donne `BLOCKED_INSUFFICIENT_DATA`. Un échec statistique
avec matière suffisante donne `NO_GO_PRICE_ONLY` et ferme la piste prix seule.

## Limite économique essentielle

`signed_target_return` utilise le rendement H20 du label Oracle, calculé depuis
la date du signal. Il sert à mesurer la direction, **pas** à revendiquer le PnL
d'une entrée à 10:00. Si E20-B passe, un replay séparé devra reconstruire prix
d'entrée après le checkpoint, coûts, gap, liquidité et lifecycle.

## Commandes

### Backfill historique rapide

Le backfill rapide ne remplit pas les tables minute : cela représenterait
environ 35 millions de barres dans la table canonique, puis presque autant dans
la table de versions. Il interroge uniquement les couples séance/symbole déjà
figés dans le TOP20 OOF, ne garde que `t/o/h/l/c`, agrège les checkpoints et
écrit un Parquet compact par séance.

Le répertoire stable
`artifacts/research/oracle_opening_price_backfill/<batch>-h20/` contient :

- `state.json` : état atomique de reprise et empreinte de l'Oracle ;
- `session_features/YYYY-MM-DD.parquet` : partition idempotente par séance ;
- `price_only_features.parquet` : consolidation des partitions disponibles ;
- `report.json` : volumétrie, état complet/partiel et contrat fournisseur.

Une interruption ne demande aucune option spéciale : relancer exactement la
même commande reprend les séances non terminées. Le programme refuse de
réutiliser l'état si le fichier Oracle, le batch, l'horizon ou la configuration
ont changé.

```powershell
python -u -m modelFactory.oracle_opening_price_backfill --batch-id model-factory-20260909051302-323684 --horizon 20
```

Smoke limité à une séance :

```powershell
python -u -m modelFactory.oracle_opening_price_backfill --batch-id model-factory-20260909051302-323684 --horizon 20 --max-sessions 1
```

Le backfill historique est une acquisition rétrospective. Son horodatage de
téléchargement ne prétend pas être la disponibilité originale en 2018–2025 ;
la causalité de l'expérience vient du fait que seules les minutes postérieures
au signal J et antérieures au checkpoint choisi sont utilisées.

Collecte manuelle, après 10:46 New York :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\forward_pit_launcher.ps1 -BatchName oracle_opening_window_sync -Force
```

Audit de disponibilité :

```powershell
python -u -m modelFactory.oracle_opening_window_availability_audit
```

Évaluation E20-B :

```powershell
python -u -m modelFactory.oracle_opening_price_confirmation --batch-id model-factory-20260909051302-323684 --horizon 20 --features-path artifacts/research/oracle_opening_price_backfill/model-factory-20260909051302-323684-h20
```

Les sorties sont placées sous
`artifacts/research/oracle_opening_price_confirmation/` : features, événements
appariés, synthèses par politique/fold/semestre et `report.json` canonique.

Voir aussi [collecte Alpaca](oracle_opening_window_alpaca.md),
[audit E20-A](oracle_opening_window_availability_e20a.md) et
[registre des expériences](experiences_done.md).
