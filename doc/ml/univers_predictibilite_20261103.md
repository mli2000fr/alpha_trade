# Actions ordinaires : fiabilité par symbole et intersection de trois sources

Campagne lancée le 3 novembre 2026, **terminée le 4 novembre**.
**5 254 titres audités,21 944 modèles annuels, zéro erreur de modélisation ;
intersections non qualifiables faute d'historique options/consensus.**

Suite demandée le 4 novembre : réduction à **TOP100**, avec les mêmes scores,
critères et périodes. Voir [l'audit TOP100](univers_predictibilite_top100_20261104.md).
Le TOP1500 ci-dessous est préservé comme référence ; les reçus des intersections
pointent désormais vers cette variante TOP100.

## Demande et périmètre figé

Les 5 254 symboles de `config/univers_batch/action_ordinaire.txt`, sans restriction
au TOP Oracle et sans filtre de taille. La question porte sur les titres dont
une prévision LONG est plus fiable dans le temps, pas sur les meilleurs scores
LONG à une seule date. Maximum 1 500 symboles par source ; aucun remplissage avec
des données absentes ni exigence artificielle de 1 500 qualifiés.

Le lot initial de5 253 a été terminé et revu avant une correction d'identité
du fichier source : **PFBC, Preferred Bank, est une action ordinaire**, pas une
action préférentielle. Le nom d'émetteur avait été pris à tort pour un type.
PFBC a été ajouté et audité séparément avec huit modèles identiques en méthode,
sans réentraîner les autres titres ni choisir son inclusion selon ses résultats.
Le protocole initial est préservé ; `scope-amendment-pfbc.json` relie l'ancien
snapshot du fichier, sa nouvelle empreinte et le complément vérifié.

L'utilisateur a demandé deux cibles séparées, puis l'intersection des trois
listes correspondantes (modèles, options, consensus) pour chacune :

1. **winner_h10** : proxy daily LONG à l'ouverture suivante, SL5 %, sans TP ni
   trailing, dix séances de détention, sortie open11 ; cible positive si le
   rendement net des frais est positif. Gap sous stop au prix d'ouverture
   défavorable. Ce n'est pas un replay de confirmation Winner 2×5m, ni un
   portefeuille avec frais de financement et contraintes de capital.
2. **parcours_h20** : à partir de l'ouverture suivante, maximum du high et
   minimum du low durant vingt séances. LONG si le pic haussier dépasse en
   amplitude absolue le pic baissier ; égalités inconnues. Les deux pourcentages,
   leurs premières séances d'occurrence et l'ordre des pics restent enregistrés.
   Deux pics le même jour : ordre intraday inconnu, jamais inventé depuis OHLC.
   Cette cible de parcours n'est pas un rendement réalisable ni un TP-first.

Sorties prévues : `symbol_trade_winner_h10.txt` et
`symbol_trade_parcours_h20.txt`, sous `config/univers_batch`, avec un reçu d'audit.
Ces fichiers ne sont raccordés à aucun batch, risque ou exécution.

## Modèles et évaluation dans le temps

LightGBM indépendant par titre, cible et année, sans modèle commun de secours.
Les hyperparamètres sont fixes (120 arbres, profondeur3, sept feuilles,
learning_rate0,03, régularisation1/10, un thread par modèle). Vingt-quatre
features prix/tendance/volatilité/volume et SPY, reprenant la famille du précédent
test par symbole ; aucun sentiment/consensus actuel injecté dans le passé.

Lectures daily depuis 2016 : elles fournissent le recul et la chauffe nécessaires
pour conserver au moins756 observations d'entraînement effectives avant la
calibration de2022. Le contrôle technique sur un titre avait montré qu'un début
en2018 n'en laissait que747/738 après chauffe et purge ; la lecture a été étendue
avant le gel de la campagne, sans observer ses performances pour choisir un seuil.

Pour l'année Y : fit avant Y−1 et calibration Platt sur Y−1 (minimum126 lignes,
40 exemples de chaque classe au fit et15 en calibration). Les labels doivent
être matures avant chacune des frontières. Modèles renouvelés annuellement.

Classement de fiabilité sur **2023,2024,2025 hors entraînement**. Le contrôle2026
jusqu'au2novembre est enregistré séparément et ne détermine pas l'ordre ni
l'admission dans les listes. Les années déjà explorées ne sont pas présentées
comme un nouveau holdout vierge.

On prédit toutes les séances qualifiées ; l'évaluation principale retire le
chevauchement par une phase globale figée (`session_index mod horizon =0`).
Les prévisions LONG les plus élevées sont définies par le quantile70 % des
probabilités calibrées de l'année précédente, pas par un seuil choisi sur le test.

Qualification minimale de l'historique :150 observations OOS dans chacune des
trois années, AUC annuelle non chevauchante calculable, au moins45/24 observations
indépendantes H10/H20 et huit prévisions LONG retenues. Tri : écart des bornes
Wilson précision LONG / fréquence de base, puis pire AUC annuelle et AUC agrégée.
Les AUC, Brier, référence historique du titre, couverture et précision sont conservés.

La revue finale compare également, sans reclasser les titres, les AUC et les
écarts de précision LONG sur les fenêtres2026 non chevauchantes du TOP1500 et
des autres titres historiquement qualifiés. Ce sont des médianes descriptives
par titre, pas un rendement de portefeuille ni un test indépendant de tous les
essais déjà conduits sur cette année.

Un TOP1500 reste un **classement exploratoire**, pas1500 avantages prouvés. Le
drapeau supplémentaire de cohérence (écart des bornes positif et AUC>0,5 sur les
trois années) n'est pas une certification : comparaisons nombreuses par symbole,
absence de correction de multiplicité et d'épreuve prospective indépendante.

## Couverture options et consensus : restriction démontrée avant tout tri

L'inventaire SQL initial en lecture seule couvre5 253titres ; le complémentPFBC
porte la couverture du fichier courant aux nombres suivants :

| Source | Symboles avec données | Première disponibilité globale |
|---|---:|---|
| Daily EODHD/SIP | 5 254 | Profondeur variable, parfois très ancienne ; présence ne signifie pas historique complet |
| Snapshots options Alpaca indicative | 3 021 | 12 septembre2026 |
| Volume options Alpaca 30Min | 3 085 | 14 septembre2026 |
| Consensus EODHD | 4 585 | 11 octobre2026 |

Sur le lot initial : parmi les3 020titres avec snapshots,2 767 ont au moins une OI renseignée et2 270
ont des OI renseignées pour les deux types CALL et PUT, pas nécessairement le
même jour ni sur une paire ATM/échéance qualifiée.4 424titres ont des compteurs
de révisions renseignés dans des lignes0q. Ce sont des présences de champs,
pas des preuves de fiabilité directionnelle.
PFBC a des snapshots et du consensus, mais aucun volume30Min archivé dans le
contrôle complémentaire : la couverture jointe snapshots+volume reste2 830titres.

Pour le mélange volume+OI, les deux sources doivent être disponibles. Des
barres de volume d'options anciennes ne reconstituent pas une ancienne OI.
Les points EPS à J−7/30/60/90 reçus en octobre ne constituent pas un historique
as-known de signaux disponibles à ces dates passées.

Pour chaque symbole/source/cible, calcul d'une borne **optimiste** du nombre de
fenêtres matures non chevauchantes : tous les jours de bourse depuis la première
réception sont supposés utilisables, même si les paires de contrats, les unités,
la fraîcheur ou les reçus ne sont pas encore qualifiés. Minimum préalable :20
fenêtres indépendantes. Si même cette borne est insuffisante, aucun score de
fiabilité n'est produit. Cela évite une lecture brute volumineuse inutile et
n'assimile pas ces nombres à des observations réellement validées.

Avec l'historique actuellement archivé, les listes fiables options/consensus et
donc les intersections ne peuvent pas être remplies. Des fichiers finaux vides
seront accompagnés du statut `UNQUALIFIED_EMPTY_DO_NOT_USE_FOR_TRADING`. Une liste
vide signifie **preuves insuffisantes**, pas « aucun titre prévisible existe ».

Au cutoff prix du2novembre, bornes maximales constatées : optionsH10 trois
fenêtres indépendantes (26sessions matures au mieux), optionsH20 une
(16sessions) ; consensusH10 une (sixsessions), consensusH20 zéro. Tous restent
sous le minimum préalable20, avant même les contrôles fins de contrats/reçus.

## Traçabilité et limites

Racine : `artifacts/research/us_predictable_symbols/20261103-v1/`.
`protocol.json` est figé avant le fit global ; `inventory-report.json`, les
couvertures Parquet, `source-reliability-gates.parquet`, `progress.json` et
`campaign.log` permettent de suivre l'audit. Chaque titre a ses cours exportés,
panels, probabilités OOS, modèles Joblib et preuves de dates dans `symbols/`.

Les deux séries de labels vectorisées ont été contrôlées contre la référence
SL/gaps/frais ; huit tests ciblés passent (maturité, données inconnues, deux pics,
ordre ambigu, absence d'influence2026 sur le rang, phase non chevauchante et AUC
inconnue en l'absence d'une classe). Un contrôle réel AAPL a
vérifié le raccordement avant le gel, sans servir à optimiser les paramètres.

Priorité daily configurée EODHD/SIP, doublons contrôlés et identités qualifiées ;
pas de remplissage des fenêtres manquantes, ni mélange de sources dans un label.
Prix historiques reconstitués et univers courant survivant : aucune prétention
d'archive de prix prospectivement disponible. Les transactions de lecture sont
propres aux groupes de titres, pas un snapshot SQL global unique ; les entrées
locales sont figées et hachées par titre.

Un plan de revue supplémentaire est figé dans `integrity-review-plan.json` avant
lecture des performances pour choisir des exclusions : quarantaine des historiques
à plusieurs instrument_id ou franchissant une rupture prédécesseur/successeur
validée (registre WFRD/CHRD). Les modèles déjà ajustés sur ces historiques restent
des artefacts d'audit, mais ne peuvent qualifier l'émetteur courant dans le rang.
Les résultats avant revue sont conservés ; les dates/empreintes de tous les fits
et des probabilités de trois titres fixés à l'avance seront revérifiées.

Les labels exigent la fenêtre de prix complète, même lorsqu'un stop aurait été
touché plus tôt : cela produit une sélection rétrospective de qualité des données,
pas une règle de disponibilité exploitable en live. Les pics nuls signifient
aucune excursion de ce sens ; l'ordre enregistré porte sur les extrema OHLC,
pas sur un événement économique distinct lorsqu'un de ces extrema vaut zéro.

Aucun fournisseur, LLM, entraînement de production, écriture SQL ou ordre broker.
L'inventaire daily initial trop large a atteint la limite de30secondes ; reprise
par200 titres avec l'index primaire, autres extractions réutilisées. L'audit de
modèles lit ensuite les cours par50 titres avec trois traitements, chacun en
transaction READ ONLY, et sauvegarde seulement des fichiers de recherche.

## Résultats terminés

| Cible | Historique prix OOS qualifié | TOP modèle | TOP options qualifié | TOP consensus qualifié | Intersection |
|---|---:|---:|---:|---:|---:|
| Proxy LONG SL5/H10 | 2 392 | 1 500 | 0 | 0 | 0 |
| Pic dominant sur le parcoursH20 | 1 996 | 1 500 | 0 | 0 | 0 |

Les autres titres sont audités mais ne remplissent pas les conditions d'historique,
de classes ou de nombre de prévisions évaluables. CHRD etWFRD sont écartés de la
qualification par émetteur : leurs historiques traversent des ruptures d'identité
validées. Les listes OI/consensus vides signifient insuffisance de preuves, pas
performance négative mesurée ou absence de biais haussier à une date donnée.

Les meilleurs1 500 modèles ne constituent pas1 500avantages démontrés : seuls
FTS etHOMB passent le contrôle supplémentaire de cohérence exploratoireH10
sur2023–2025 ; aucun pourH20. En2026, leurs signaux LONG indépendants ne sont
respectivement que trois etdeux (deux etun gagnants), insuffisants pour conclure.

### Contrôle2026 sans reclassement

| Cible | AUC médiane des TOP1500 | AUC médiane des autres titres qualifiés | Observations indépendantes médianes par titre |
|---|---:|---:|---:|
| Proxy LONG SL5/H10 | 0,5111 | 0,5000 | 18 |
| Pic dominant parcoursH20 | 0,5000 | 0,5000 | 9 |

L'écart médian de précision LONG par rapport au taux de base du titre est de
+0,66pointH10 et+4,17pointsH20 dans les TOP1500. Ces petits nombres de fenêtres,
les comparaisons multiples et les dépendances entre sociétés interdisent de
transformer ces descriptions en preuve de robustesse ou de rendement.
Pas de nouvel avantage économique démontré ni de promotion.

### Fichiers et intégrité

Les six listes sont sous la racine de recherche :
`{winner_h10,parcours_h20}-{model,options,consensus}-top1500.txt`.
Les deux listes `model` contiennent chacune1 500symboles ; les quatre listes
options/consensus restent vides. Les CSV `*-per-symbol-ranking.csv` et
`*-per-symbol-audit.csv` gardent l'ordre, les scores et la couverture de tous les
titres. Les probabilités et les deux pics H20 sont dans les Parquet par titre.

Les fichiers demandés `config/univers_batch/symbol_trade_winner_h10.txt` et
`symbol_trade_parcours_h20.txt` sont **vides**, chacun accompagné d'un reçu
`.audit.json` au statut `UNQUALIFIED_EMPTY_DO_NOT_USE_FOR_TRADING`.

`completion-audit.json` vérifie :5 254 reçus dans chaque cible,1 500symboles
distincts dans chaque liste modèle, tous présents dans le fichier courant,
aucune perte du symbole littéralNA à la lecture CSV,21 944empreintes/dates
de modèles contrôlées, zéro dépassement de frontière de fit/calibration,
72probabilités reproduites sur l'échantillon fixé et huit modèlesPFBC ajoutés
sans refit des autres. Dix tests ciblés passent. Aucun appel fournisseur/LLM,
ordre, écritureSQL ni modification des modèles/pipelines de production.
