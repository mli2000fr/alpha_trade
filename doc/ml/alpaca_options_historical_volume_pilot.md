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

### Première séance réellement observée : 18 janvier 2024

Le sondage additionnel du 10 octobre 2026 interroge 12 contrats réels expirés :
CALL/PUT sur AAPL (strike 180), MSFT (400) et SPY (480), échéances 16 février
et 15 mars 2024. Les 12 identités sont confirmées par HTTP 200 avec le même
symbole retourné. La requête de barres journalières du 1er janvier 2023 au
29 février 2024 retourne 300 barres, sans pagination résiduelle.

Pour **chacun des 12 contrats**, la première séance est **2024-01-18**. Une
seconde requête bornée avant cette séance retourne HTTP 200 et zéro barre.
Les barres minute de cette première séance sont aussi accessibles : premier
timestamp observé **2024-01-18T14:30:00Z**, soit 09:30 New York / 15:30 Paris.

Ce résultat est antérieur au mois de février 2024 annoncé par la documentation
Alpaca consultée. Retenir le 18 janvier comme **début observé de cet échantillon
avec ce compte**, pas comme garantie universelle ou preuve de couverture complète
de tous les contrats. Ni les trades, ni les quotes, ni l'OI historique n'ont été
testés pour cette frontière. Pas d'écriture SQL ni d'ordre.

Script : `python -u -m scripts.research.alpaca_options_history_first_day`.
Preuves brutes, barres et rapport :
`artifacts/research/alpaca_options_history/20261010-first-day/report.json`.

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

Terminé le 10 octobre 2026 : **174 391 barres** téléchargées, aucune erreur API
sur les 40 titres examinés, **719 paires titre/jour**, 37 titres exploitables et
20 dates d'entrée. Les contrats hors règles et les paires manquantes sont exclus.

| Horizon | Couples D1/D10 | D10 / D1 | AUC globale | Première moitié | Seconde moitié |
| --- | ---: | ---: | ---: | ---: | ---: |
| H3 | 165 | 87 / 78 | 0,5102 | 0,5300 | 0,5045 |
| H5 | 180 | 93 / 87 | 0,4928 | 0,5379 | 0,4557 |
| H10 | 179 | 98 / 81 | 0,4755 | 0,4864 | 0,4518 |
| H20 | 145 | 98 / 47 | 0,5929 | 0,5664 | 0,6251 |

H3/H5/H10 ne montrent pas d'avantage directionnel probant. Le résultat H5 ne
confirme pas le 0,547 du premier audit prospectif, mais **ce n'est pas une
réplication exacte** : période, sous-ensemble et agrégation des strikes diffèrent.

H20 mérite une confirmation distincte, pas une promotion. Une AUC 0,593 n'est
ni un taux de trades gagnants, ni un rendement. Les 20 dates d'entrée se
chevauchent presque entièrement à H20 ; les deux moitiés ne sont donc pas
indépendantes. Aucun jour n'atteint le minimum de 20 observations D1/D10 requis
par la fonction commune pour une AUC quotidienne : cette mesure est absente,
pas nulle. L'effet peut refléter les titres/secteurs présents plutôt qu'une
information nouvelle sur la direction.

Conclusion : **accès historique gratuit confirmé sur cet échantillon ; avantage
directionnel stable non démontré**. Avant toute utilisation, élargir avec la même
règle à plusieurs mois disjoints et années, contrôler les prix bruts nécessaires
au matching des strikes et les dates de disponibilité, puis distinguer effet
de marché/secteur et apport du volume. Toujours aucun backtest économique,
entraînement, changement de modèle, ordre ou écriture SQL.

## Suite distincte autorisée : backfill SQL

L'utilisateur a ensuite autorisé l'alimentation de `stock_option_bars_delayed`
depuis le 20 janvier 2024 sur tout le fichier tradable. Cette opération distincte
écrit uniquement cette table, en barres 1Day, avec réception réelle et reprise.
Voir [le protocole et le suivi du backfill](alpaca_options_history_backfill.md).
Les résultats du pilote ci-dessus restent inchangés.
