# Oracle parcours H10 contre H20 — prix puis modèles dédiés

## Périmètre

GO du 19 octobre 2026 : qualification bornée des prix suspects puis comparaison
de deux **cibles d'amplitude distinctes**, sans remplacer les modèles existants.
Ce n'est pas un nouveau modèle LONG/SHORT « TP avant SL ». Les deux Oracle
apprennent l'amplitude ; TP10/SL10 sert à évaluer leurs sélections séparément
en LONG et en SHORT.

## 1. Qualification des prix : défauts réels et réserves distinctes

22 requêtes historiques Alpaca SIP, onze titres × raw/split, du 1er janvier 2023
au 30 septembre 2026. Aucun achat supplémentaire, ordre ou SQL. TOELY n'est pas
interrogé, déjà non couvert dans l'audit SIP archivé. Les réponses exactes sont
conservées, sans en-têtes d'authentification. Les fenêtres d'octobre de l'ancienne
archive plus large ne font pas partie de cette qualification.

| Titre | Constat et référence officielle | Traitement de recherche |
| --- | --- | --- |
| KLAC | Split 10 pour 1, négociation ajustée le 12 juin 2026 ([émetteur/EX-99.1](https://ir.kla.com/sec-filings/all-sec-filings/content/0001193125-26-212093/d116682dex991.htm)) ; archive mélangeant des échelles ×10 | Facteur 0,1 seulement lorsqu'il est corroboré sur les quatre OHLC par SIP ; 939 séances contrôlées |
| MLI | Split 2 pour 1, négociation ajustée prévue le 1er juillet 2026 ([émetteur](https://ir.muellerindustries.com/sec-filings/all-sec-filings/content/0000089439-26-000025/ex-99_16302026stocksplit.htm)) ; mélange d'échelles ×2 | Facteur 0,5 corroboré par SIP, sans écrêtage des mouvements |
| SBS | Document du 27 avril annonçant le split ADR 5 pour 1 et l'ex-date prévue au 7 mai ([émetteur](https://api.mziq.com/mzfilemanager/v2/d/9e47ee51-f833-4a23-af98-2bac9e54e0b3/6120c301-1988-3129-0a1b-47cf798497bf?origin=2)) ; transition d'échelle concordante avec SIP | Facteur 0,2 corroboré ; le document annonce un calendrier, pas une certification de chaque cours ou fill |
| DD | Regroupement 1 pour 3, négociation ajustée prévue le 24 juin 2026 ([émetteur](https://www.investors.dupont.com/news-and-media/press-release-details/2026/DuPont-Announces-Reverse-Stock-Split-and-Reaffirms-2026-Financial-Guidance/default.aspx)) ; mélange ×3, mais aussi une autre différence de base | Facteur 3 sur le bloc récent corroboré ; bloc ancien uniquement remis à une échelle uniforme, non certifié en prix absolu |
| DD/Qnity | Séparation effective le 1er novembre 2025, négociation régulière Q le 3 novembre, distribution d'une action Q pour deux DD ([DuPont](https://www.dupont.com/news/dupont-completes-separation-of-qnity-electronics.html)) | L'ancienne série ajuste la distribution, SIP « split » non : ni prix total-return inventé, ni facteur 7,17 présenté comme split. Parcours traversant/après le 3 novembre et nouvelles features depuis cette date réservés |
| TOELY | Rupture apparente le 13 juillet ; l'événement ordinaire 1:5 du 1er octobre ne prouve pas la base ADR TOELY ([émetteur](https://www.tel.com/ir/stocks/info/)) | Aucune correction inventée ; parcours traversant/après le 13 juillet et features depuis cette date réservés |

Normalisation dans une **copie de recherche uniquement** : OHLC/adj_close et VWAP
sur la même échelle, volume inversement proportionnel. Tolérance de concordance
inter-fournisseurs fixée à 0,5 % sur tous les OHLC pour autoriser le facteur connu.
Les vrais chocs ne sont pas plafonnés : la comparaison des autres titres distingue
une variation compatible avec le second fournisseur d'une incohérence d'échelle.
Elle n'est pas une certification indépendante de prix d'exécution.

**3 420 lignes normalisées**, dont 711 anciennes lignes DD dont le niveau SIP
n'est pas corroboré : leur remise à une échelle uniforme ne change pas leurs
rendements internes et n'est pas rebaptisée preuve indépendante. Les fichiers
d'univers, `stock_bars_daily` et les archives précédentes restent inchangés.

La copie corrigée ne rend pas les **features archivées** automatiquement correctes.
Elles sont réservées dès le premier mélange constaté : KLAC/DD/MLI le 1er juin,
SBS le 7 mai 2026, plus réserves DD/Qnity et TOELY ci-dessus. Pas de suppression
globale de ces symboles ni de prétention que ces versions étaient disponibles PIT.
Avant une transition, une remise à l'échelle uniforme préserve les ratios de prix ;
les features non qualifiées après transition ne sont pas utilisées à l'entraînement
ou au scoring du nouveau protocole.

### Influence sur les résultats précédents

Contrôle à anciens scores et adhésions **figés**, sans réentraînement : les LONG
TOP20 % retenus conservent leurs moyennes 2025/2026 (SL10 +1,25/−0,26 % ; sans SL
+3,11/+1,10 %). Les corrections touchent les références globales et d'autres bras,
mais ne suffisent pas à expliquer la fragilité directionnelle déjà constatée.
Il s'agit d'une sensibilité, pas de la performance d'un modèle entièrement réparé.

Traçabilité :
`artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/` :
`report.json`, `normalization-ledger.csv`, `shock-review.csv`,
`quality-reserves.json`, `research-prices.parquet`, `frozen-sensitivity.csv`.
Premières tentatives conservées : qualification hors fenêtre d'octobre, puis
refus de forcer la base DD/Qnity ; aucune métrique ne les remplace silencieusement.

## 2. Comparaison pré-enregistrée des modèles

- Univers courant 1 790 titres, même fichier et mêmes sources que précédemment.
- **Deux cibles distinctes** : TOP20 % du maximum absolu high/low pendant dix ou
  vingt séances, depuis le close ajusté de J ; maturité J+H+1.
- Même matrice pour les deux modèles. 172 features : profil historique, moins
  `selector_short_score` dont la disponibilité PIT n'est pas certifiée. Rangs
  cross-sectionnels recalculés sur l'admission observable à J, avant la qualité
  future. Cette référence H20 est donc nouvelle, pas une reproduction des scores
  des trois anciens batches annuels.
- Même algorithme **CatBoost**, mêmes paramètres figés (profondeur 4,
  300 itérations maximum, learning rate 0,03, seed42), sans balayage d'algorithmes.
- Trois folds annuels : 2024, 2025, 2026. **504 dates train glissantes +126 dates
  validation**, embargo commun de 21 séances ; mêmes lignes d'apprentissage dont
  les deux labels sont qualifiés. Même garde de maturité H20 pour les deux modèles.
- Arrêt anticipé sur validation uniquement, jamais sur les résultats du test.
- Test 2024/2025 complet en dates de signal ; 2026 jusqu'au 1er septembre pour
  comparer des parcours complets avec l'observation de prix au 30 septembre.
- Scoring de tous les titres observables ; sélection de `ceil(0,2 × N)` par score,
  puis symbole pour les égalités. Labels futurs manquants non remplacés par le
  rang suivant. Précision d'amplitude mesurée contre les deux cibles H10 et H20.
- Exécution hypothétique **TP10/SL10**, entrée open J+1, sans trailing, sorties
  close10 **et** close20 si aucun seuil. Ainsi, les deux modèles sont comparés
  à durée identique ; pas seulement H10/10 contre H20/20, qui confondrait deux effets.
- LONG et SHORT évalués séparément ; pas de nouvelle tête directionnelle ni de
  filtre de confiance par symbole entraîné dans cette comparaison.
- Frictions 8 bps par jambe, emprunt SHORT supposé 0,3 %/an, gaps au prix d'open,
  collision OHLC stop-first sauf ouverture résolvant l'ordre. Épisodes sans
  chevauchement supplémentaires, espacement de référence vingt séances.

Les années ont déjà été explorées, l'univers est survivant et la disponibilité
des versions historiques de toutes les données n'est pas certifiée : même avec
des folds causaux, ce n'est pas un holdout prospectif vierge ou un PnL live certifié.

## 3. Résultats terminés : H10 ne débloque pas la direction

**Six modèles réellement entraînés, comparaison et audit terminés. Pas de
promotion.** Un Oracle d'amplitude H10 sélectionne presque les mêmes titres que
son témoin H20 : intersection des TOP20 % de **95,16 % en 2024, 95,11 % en 2025
et 95,64 % en 2026**. Il ne devient pas un prédicteur de sens en raccourcissant
sa cible d'amplitude. Cet essai ne mesure pas les performances d'un nouveau
classifieur directionnel H10, qui n'a pas été entraîné.

### LONG, mêmes TP10/SL10 et mêmes durées pour les deux modèles

Moyenne **par occasion** après frictions hypothétiques ; pas rendement annuel
d'un portefeuille. Chaque titre sélectionné est acheté LONG dans ce bras,
sans prétendre que le modèle d'amplitude a choisi LONG.

| Signaux | H10, sortie au plus tard séance 10 | H20, même sortie séance 10 | H10, sortie au plus tard séance 20 | H20, même sortie séance 20 |
| --- | ---: | ---: | ---: | ---: |
| 2024 | +0,054 % | +0,078 % | +0,196 % | +0,222 % |
| 2025 | +0,425 % | +0,400 % | +0,551 % | +0,510 % |
| 2026 au 1er septembre | +0,112 % | +0,083 % | +0,112 % | +0,062 % |

Taux gagnant LONG, durée 10 : H10 **50,23 / 53,46 / 51,34 %**, H20
**50,32 / 53,37 / 51,19 %** (2024/2025/2026). Ces taux incluent les sorties
avant échéance ; ils ne représentent pas la précision d'une direction prédite.

Référence tous les titres observables achetés LONG, mêmes TP/SL : durée 10,
**+0,137 / +0,201 / +0,190 %** ; durée 20,
**+0,420 / +0,250 / +0,300 %**. Le TOP20 % n'apporte donc pas un supplément
transversal : mieux en 2025, moins bien en 2024 et 2026 sur ces moyennes.
Les intervalles par blocs du supplément face à l'univers comprennent zéro
dans les trois années, pour les deux modèles et les deux durées LONG.

### SHORT, mêmes protections

| Signaux | H10, durée 10 | H20, durée 10 | H10, durée 20 | H20, durée 20 |
| --- | ---: | ---: | ---: | ---: |
| 2024 | −0,666 % | −0,692 % | −0,981 % | −1,014 % |
| 2025 | −1,119 % | −1,096 % | −1,419 % | −1,381 % |
| 2026 au 1er septembre | −0,855 % | −0,826 % | −0,988 % | −0,942 % |

Tous les bras SHORT moyens restent négatifs. Acheter ou shorter aveuglément
le TOP20 % n'est pas une nouvelle décision directionnelle apprise.

### Robustesse : ne pas présenter quelques points de base comme une solution

Différences de moyennes quotidiennes appariées H10 moins H20, en **points de
pourcentage par occasion**, intervalles descriptifs à 95 % par blocs de vingt
séances. Même calendrier et même durée dans chaque comparaison :

| Signaux | LONG durée 10 : écart [intervalle] | LONG durée 20 : écart [intervalle] |
| --- | ---: | ---: |
| 2024 | −0,024 [−0,044 ; −0,005] | −0,027 [−0,055 ; +0,001] |
| 2025 | +0,025 [+0,001 ; +0,048] | +0,041 [+0,014 ; +0,071] |
| 2026 | +0,029 [+0,004 ; +0,075] | +0,050 [+0,030 ; +0,086] |

Certaines petites différences excluent zéro dans cette description, mais leur
signe change entre 2024 et les années suivantes. Pas de correction de sélection
multiple ni de nouveau test prospectif ; ce n'est pas un avantage directionnel
robuste justifiant un remplacement.

Contrôle sans chevauchement, LONG durée 10 : H10
**−0,651 / +0,665 / +0,464 %**, H20 **−0,629 / +0,525 / +0,373 %**.
Durée 20 : H10 **−0,137 / +0,770 / +0,405 %**, H20
**−0,169 / +0,608 / +0,324 %**. Les épisodes sont espacés sur la fenêtre commune
de vingt séances ; ce contrôle ne simule pas le recyclage du capital à dix séances.

## 4. Détection d'amplitude et couverture

Part du TOP20 % prédit appartenant au véritable TOP20 % de l'amplitude :

| Signaux | Vrai H10, modèle H10 | Vrai H10, modèle H20 | Vrai H20, modèle H10 | Vrai H20, modèle H20 |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 45,91 % | 45,82 % | 46,28 % | 46,29 % |
| 2025 | 49,89 % | 49,73 % | 50,44 % | 50,36 % |
| 2026 | 50,34 % | 50,19 % | 49,77 % | 49,84 % |

Les deux modèles concentrent davantage le véritable TOP20 % qu'une sélection
aléatoire (environ 20 % de recouvrement attendu), mais ni le signe ni l'ordre
TP/SL n'en découlent. L'écart de précision entre
H10 et H20 est minuscule sur leur cible commune. Ce ne sont pas des précisions
TOP10 : le périmètre est bien le **TOP20 %**, jusqu'à 358 titres par séance.

| Signaux | Dates | Occasions sélectionnées par modèle | Parcours qualifiés, modèle H10 | Parcours qualifiés, modèle H20 |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 252 | 90 216 | 90 216 | 90 216 |
| 2025 | 250 | 89 500 | 89 480 | 89 480 |
| 2026 | 167 | 59 358 | 58 721 | 58 714 |

Dans ce dernier tableau, **H10/H20 désigne le modèle** : chaque exécution exige
le même parcours de prix qualifié sur vingt séances, y compris pour une sortie
plus courte. Couverture d'exécution 100 % en 2024, 99,978 % en 2025,
98,927/98,915 % en 2026. Les manquants ne sont ni remplacés ni comptés perdants.

La qualification de la **cible de classement réel** est plus stricte que celle
d'un seul parcours : au moins 95 % de parcours qualifiés dans la coupe du jour.
En 2026, dix dates sans label H10 (4–17 juin) et vingt sans label H20
(20 mai–17 juin) échouent ce contrôle, avec environ 92–93 % de couverture
globale. Exemple du 4 juin : 135 parcours sur 1 773 invalides/manquants ; leurs
symboles ne sont pas remplacés par ceux dont le futur est connu. Les moyennes
d'amplitude reposent donc sur **93,85/93,84 %** des sélections pour la cible H10
et **87,73/87,72 %** pour H20 en 2026, pas sur toute l'année sans réserve.

Ces trous restent visibles ; le GO était une qualification bornée des ruptures
connues, pas une certification de toutes les données ou une réparation SQL globale.

## 5. Contrôles et décision

**91 tests passent.** Audit final `PASS_EXPLORATORY_ONLY` sur les six modèles :
empreintes des sources/données/poids, mêmes lignes d'entraînement et validation,
labels H20 matures avant le pli suivant, mêmes clés de scoring observables à J,
rangs et TOP20 % exacts, réserves respectées, rechargement des poids identique,
sorties/coûts et moyennes reproduits. Les modèles sont entraînés aujourd'hui
sur des fenêtres historiques ; aucun fichier de modèle n'est déclaré avoir
existé en 2024. Ce n'est pas une certification PIT de toutes les features.

**Conclusion : pas de remplacement de l'Oracle H20, ni de filtre LONG/SHORT
promu.** H10 demeure une référence de recherche disponible, pas une nouvelle
solution directionnelle. Les corrections de prix sont utiles techniquement mais
n'expliquent pas à elles seules l'échec des anciens filtres. Ne pas enchaîner
automatiquement d'autres horizons, protections ou seuils sur ces mêmes années.
Une éventuelle expérience distincte nécessitera un GO et une hypothèse figée ;
les collectes prospectives existantes ne sont pas modifiées.

## 6. Artefacts et reproduction

Dossier : `artifacts/research/us_h10_h20_frozen_comparison/20261019-v1/`.
Suivi : `progress.json` ; par année, `2024-done.json`, `2025-done.json`,
`2026-done.json` seulement après les deux modèles de l'année.
Modèles locaux : `models/2024/H10`, `models/2024/H20`, puis 2025/2026 ;
contrats `serving_ready: false`. Sources et données scellées par empreintes.
`report.json`, `execution-comparison.csv`, `amplitude-comparison.csv`,
`paired-model-comparison.json`, `final-audit.json` conservent résultats,
couvertures, références et intervalles. Aucun artefact antérieur n'est écrasé.

Scripts : `us_h10_price_readiness`, `us_h10_h20_common_data`,
`us_h10_h20_frozen_comparison`, `us_h10_h20_comparison_audit` sous
`scripts/research/`. Aucun SQL, ordre, appel LLM ni nouvelle collecte de consensus.
Les seuls nouveaux appels fournisseur sont les 22 lectures SIP bornées de l'audit.
