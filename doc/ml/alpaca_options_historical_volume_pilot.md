# Historique options Alpaca — pilote de volume call/put

## Accès réel vérifié le 10 octobre 2026

Compte principal `default`, appels GET uniquement. Le catalogue des contrats AAPL
expirés de janvier 2025 renvoie HTTP 200 avec pagination. Les barres journalières
des contrats `AAPL250117C00200000` et `AAPL250117P00200000` entre le 2 et le
10 janvier 2025 renvoient HTTP 200 et 12 barres. Il s'agit donc bien d'un accès
historique et non du seul snapshot du jour.

L'ajout explicite de `feed=opra` à l'endpoint bars est refusé (HTTP 400,
`unexpected query parameter(s): feed`). Le test ne contourne pas ce refus : il
utilise l'endpoint historique sans ce paramètre. La provenance reste
`UNVERIFIED_OPRA`. L'accès réussi ne démontre ni la licence de redistribution,
ni l'exhaustivité consolidée, ni la disponibilité d'un historique OI/IV/Greeks.

IEX est un feed **actions** : sa restriction de volume à une seule place ne doit
pas être transposée aux options. Inversement, le feed `indicative` des snapshots
options n'est pas assimilé à des quotes OPRA réelles. Ce pilote n'utilise pas
les snapshots indicatifs.

Preuves : `artifacts/research/alpaca_options_history/20261010-smoke/`.

## Protocole figé avant téléchargement

- Univers : `config/univers_batch/univers_filtred_tradable.txt`, hash conservé.
- Sous-ensemble : 40 titres au plus, triés par dollar volume médian de décembre
  2024 ; au moins 15 barres qualifiées dans ce mois. Aucun résultat futur ne
  sert à choisir les titres.
- Période du signal : 2–31 janvier 2025. Prix pour les sorties jusqu'au 7 mars.
- Catalogue expiré : racine standard correspondant exactement au sous-jacent,
  taille 100 ; échéances entre le 17 janvier et le 25 février 2025. Strikes
  téléchargés dans une fourchette ±30 % du prix médian de décembre 2024.
- Chaque jour : CALL/PUT de même strike et échéance ; échéance la plus proche
  de 20 jours calendaires dans 15–25 jours, puis strike ATM le plus proche dans
  ±5 %. Les deux barres doivent exister ; une barre manquante n'est pas imputée
  comme volume zéro.
- Signal : `log1p(volume_call) - log1p(volume_put)`, orientation positive figée.
- Entrée : ouverture de la prochaine séance US. Sortie : clôture de la Hème
  séance, séance d'entrée incluse ; H3/H5/H10/H20.
- Labels : D1/D10 des rendements signés sur tout l'univers de prix qualifiés,
  pas seulement sur les titres ayant des options. Couverture minimale 90 %.
  OHLC cohérents, volumes positifs, barres non remplies, ajustement split.
- Mesures : AUC globale, AUC par date et deux moitiés chronologiques.
- Aucun entraînement, optimisation de seuil, écriture SQL ou ordre courtier.

## Limites de ce premier pilote

Un mois et un sous-ensemble liquide ne valident pas un avantage stable. Les
rendements se chevauchent. L'univers est le fichier actuel : biais de survie.
Le catalogue est observé aujourd'hui, pas une chaîne archivée telle que connue
en janvier 2025. Des splits postérieurs peuvent désaligner le spot ajusté des
strikes historiques et réduire la couverture ; aucune correction de strike
n'est inventée. Les racines ajustées sont exclues.

La disponibilité historique avant l'ouverture suivante est une hypothèse,
pas une preuve PIT indépendante. Une évaluation économique nécessiterait
ensuite dates de disponibilité qualifiées, contrôles de prix/actions sur titres,
coûts, risque et validation sur davantage de périodes.

Ce signal ATM apparié n'est pas exactement le signal agrégé sur les strikes
collectés du premier audit prospectif : les AUC ne sont pas directement
comparables. Ce pilote ne prouve pas davantage l'intérêt historique de l'open
interest, puisqu'il n'en télécharge pas de série.

## Exécution et reprise

`python -u -m scripts.research.alpaca_options_historical_volume_test`

Réponses API mises en cache après pagination complète. Une reprise relit ces
fichiers et ne télécharge que les requêtes manquantes. Les erreurs et couvertures
sont explicites. Ne pas lancer deux instances sur le même dossier.

Suivi : `artifacts/research/alpaca_options_history/20261010-volume-pilot/progress.json`.
Résultat final : `report.json` dans le même dossier ; barres et couples
signal/rendement conservés en Parquet. Deux tests locaux couvrent l'appariement
ATM/orientation et l'absence d'imputation d'un PUT manquant.

## Résultat

Téléchargement et test exploratoire en cours ; aucune conclusion directionnelle
ou économique n'est déclarée avant le rapport final.
