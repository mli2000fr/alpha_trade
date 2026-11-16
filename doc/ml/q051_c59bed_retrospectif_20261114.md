# Q051 vol20 + régime — même batch c59bed sur 2021–2026

**TERMINÉ ET VALIDÉ LE 15 NOVEMBRE 2026 — AVEC ANTICIPATION AUTORISÉE.**
Historique IHM : `20261114_q051_c59bed_retrospective`.

| Mesure globale | Résultat |
| --- | ---: |
| Capital initial | 4 000,00 USD |
| Capital final valorisé | **11 630,38 USD** |
| Gain net valorisé | **7 630,38 USD** |
| Rendement cumulé | **+190,76 %** |
| DD maximal intraday | **−28,04 %** |
| Trades clôturés | 979 |
| Gagnants / perdants | 365 / 614 |
| Taux gagnant / perdant | 37,28 % / 62,72 % |
| Gain moyen gagnant / perte moyenne perdant | +69,43 / −29,48 USD |
| Détention moyenne gagnant / perdant | 14,50 / 5,36 jours calendaires |
| Capital engagé moyen | 2 607,40 USD |
| Engagement moyen / equity courante | 45,49 % |
| Capital engagé maximal | 8 487,22 USD |
| Frais cumulés / intérêts de marge | 947,85 / 0,00 USD |

Le maximum engagé peut dépasser le dépôt initial, car le portefeuille capitalise
les gains ; le plafond d'achat reste 1× de l'equity courante, pas 1× des 4 000USD
initiaux. Les moyennes d'engagement utilisent les observations du replay.

| Année | Capital de fin | Rendement annuel | DD de l'année | Trades | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2021 | 4 635,98 USD | +15,90 % | −16,89 % | 170 | 35,88 % |
| 2022 | 4 031,97 USD | −13,03 % | −23,97 % | 67 | 20,90 % |
| 2023 | 5 197,68 USD | +28,91 % | −14,94 % | 187 | 40,11 % |
| 2024 | 6 343,94 USD | +22,05 % | −10,06 % | 193 | 39,38 % |
| 2025 | 6 751,66 USD | +6,43 % | −19,46 % | 205 | 33,17 % |
| 2026, jusqu'au 13 novembre | 11 630,38 USD | +72,26 % | −7,74 % | 157 | 45,22 % |

Validation finale **PASS** : 1 474 séances du 4 janvier2021 au13novembre2026,
totaux gagnants/perdants, rendement final, produit des rendements annuels et
parité des métriques IHM. Même poids Oracle et même tête LONG par titre
vérifiés sur2 619 007lignes ;7 098signaux avant admission au portefeuille.
Les dates de modèles restent explicites, et les contrats d'origine sont inchangés.

Le statut économique reste **INCOMPLETE_COVERAGE** :19dates de signal sous
le seuil93 % de l'univers complet, et protections OHLC journalières lorsque
les5m sont absentes/incompatibles. Le complément TKOMY est décrit ci-dessous.
Ce résultat **ne valide pas une performance prédictive hors échantillon** et
ne doit pas être comparé comme une ablation équitable à la référence annuelle
causale. Il n'a remplacé ni les modèles ni les prédictions du pipeline PAPER.
Zéro écriture SQL et zéro appel broker ; deux requêtes fournisseurs de réparation.

Rapports natifs : `result/report.json`, `result/annual-summary.csv` et
`final-validation.json` sous la racine du test. Copies et courbe consultables
dans l'historique Backtest, libellé **Q051 vol20 + régime — même batch c59bed —
AVEC ANTICIPATION — 2021–2026**.

## Demande et statut

Le 14 novembre 2026, l'utilisateur demande un portefeuille continu du
1er janvier 2021 au 13 novembre 2026, 4 000 USD au départ, avec le seul batch
`model-factory-20261114122842-c59bed` et le profil Q051 vol20 + régime.
Il autorise explicitement que le modèle ait appris sur les données prédites.

Ce choix est **rétrospectif, avec anticipation**, sans valeur de validation
hors échantillon. Le batch original ne possède pas de modèles LONG annuels
2021–2024 et son premier fold Oracle causal commence le 31 mars 2022.
La simulation n'invente pas ces anciens modèles et ne réécrit pas leurs dates.

Calcul lancé sous :
`artifacts/research/us_q051_same_batch_retrospective/20261114-v1/`.
Suivi : `progress.json`. Journal :
`artifacts/research/us_q051_same_batch_retrospective_20261114-v1.log`.

## Protocole figé avant calcul

- Dernier fold Oracle vérifié du batch : mêmes poids sur toute la période.
- Dernière tête LONG disponible de chaque titre, généralement année 2027,
  avec date de disponibilité réelle conservée : mêmes poids par titre sur
  toutes les années, pas de réentraînement.
- Variables de marché calculées à chaque date historique ; pas de rendement
  futur chargé pour décider du classement.
- Inférence sur les 1 790 membres du modèle lorsqu'ils ont des données.
  TOP179 Oracle → classement LONG → TOP5, puis score>0,50 et AUC de calibration
  ≥0,50, sans remplacement d'un candidat qui échoue aux seuils.
- L'AUC de calibration du modèle choisi peut être future par rapport à une
  décision historique : c'est une composante du biais explicitement autorisé.
- Positions complètes LONG uniquement, achat à l'ouverture J+1, sans deux
  confirmations 5m. SL5 %, aucun TP, trailing ni renforcement, sortie open11.
- Risque1,25 %, poids maximal20 %, vingt positions, minimum50USD,
  plafond d'achat1×, compte margin de capacité2×. Quantités entières.
- Budget de volatilité20 %, covariance60séances antérieures, SPYJ>98 %SMA200.
  B4/DD15, facteurs, corrélation, limites sectorielles et options/GPT désactivés.
- Frais8pb par opération, financement6,5 % annuel sur débit, capital continu,
  sans remise à zéro annuelle. Capital final valorisé, sans vente finale forcée.

## Isolation et limites de couverture

Aucun appel fournisseur/broker ni écriture SQL. Les scores vont uniquement
dans des fichiers Parquet de recherche. Ils ne sont jamais injectés dans les
tables de prédictions utilisables par le pipeline PAPER. Les contrôles causaux
du prédicteur normal restent actifs et inchangés.

Les dates insuffisamment couvertes par rapport au seuil Oracle93 % sont
listées dans `result/oracle-coverage.csv`. Elles ne sont pas déclarées conformes :
le résultat garde le statut de couverture incomplète et le TOP179 n'est pas
réduit proportionnellement aux titres présents. Aucun score absent n'est inventé.
Protections intraday qualifiées quand disponibles ; repli OHLC journalier
conservateur selon le mode journalier existant, sans téléchargement de secours.

Les limites sur les événements d'entreprise et le cycle de vie des titres
restent celles du moteur de replay existant. Un événement non qualifié n'est
pas ignoré pour obtenir artificiellement un résultat terminé.

## Livrables prévus

Prédictions par année et leurs empreintes, classement complet avec dates des
poids, signaux retenus, configurations, courbes du capital, trades, événements,
résumé annuel, rendement, DD maximal, taux gagnant/perdant, gains/pertes moyens
et capital engagé moyen/maximal. Import final dans l'historique IHM avec le
libellé **AVEC ANTICIPATION**, sans présenter ce résultat comme celui d'une
stratégie réalisable historiquement.

Script dédié :
`scripts/research/us_q051_same_batch_retrospective_20261114.py`.
Il exige `--allow-in-sample-lookahead`. Les seize tests initiaux passent
(classement sans remplissage, choix de poids fixes, paramètres Q051 natifs,
budget vol/régime et conservation du caractère biaisé dans l'import IHM).

## Reprise du 15 novembre : TKOMY

Le premier replay a atteint le 19 octobre 2026, puis s'est arrêté parce qu'une
position TKOMY était détenue alors que les cours canoniques s'arrêtaient au
16 octobre. Aucun résultat économique complet n'a été déclaré pour cette
tentative. `first-attempt-progress.json` et `first-attempt-isolation.json`
conservent l'échec d'origine, sans violation d'isolation.

Récupération séparée : Alpaca SIP refusé (`DailyHistoryBlocked`), puis un GET
Yahoo réussi, 27 séances historiques en USD du 8 octobre au 13 novembre.
Sept séances communes permettent de vérifier les quatre prix OHLC : écart
relatif maximal **0,0000034 %**, compatible avec les arrondis numériques.
Aucun split dans cette fenêtre. Les vingt séances manquantes du 19 octobre
au 13 novembre sont qualifiées, sans remplacement des lignes canoniques.
Parmi les candidats d'octobre susceptibles d'être détenus au passage de cette
lacune, TKOMY est le seul titre dépourvu de ces cours.

Les réponses brutes, l'heure réelle de récupération, leurs empreintes et les
preuves de qualification restent dans `price_recovery/`. Source distincte
`yahoo_daily_research` : elle n'est pas présentée comme du SIP, ni comme une
preuve archivée à la date historique. La base SQL reste inchangée.

Le script de reprise
`scripts/research/us_q051_retrospective_daily_repair_20261115.py` applique ces
vingt lignes aux seuls prix manquants du replay. Il réutilise tous les scores
déjà calculés et vérifiés. Les paramètres, candidats et poids ne changent pas.
Le portefeuille est rejoué depuis le début, faute de checkpoint comptable
intermédiaire. Aucun nouveau téléchargement pendant cette deuxième simulation.
Journal : `artifacts/research/us_q051_same_batch_retrospective_20261115-resume.log`.
Sept tests supplémentaires vérifient la réparation (identité, devise, splits,
OHLC, recouvrement et interdiction d'écraser les lignes existantes) ; la suite
ciblée de reprise passe avec quatorze tests.
