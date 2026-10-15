# Protections personnalisées — qualification du dataset OOF

## GO et périmètre figé — 14 octobre 2026

Suite du diagnostic de marge théorique : préparer les exemples historiques et
qualifier les variables à J, **sans entraîner le sélecteur**, optimiser un seuil,
calculer un nouveau portefeuille, écrire SQL ou toucher au live/batchs.
Trois profils conservés : SL5 partout ; COURT trailing10/TP10,
REFERENCE trailing15/TP20, LARGE trailing20/TP30. Pas de profils supplémentaires.

## Population historique

Les dix folds CatBoost de la comparaison de recherche
`artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path`
sont encore présents. Ce ne sont pas les trois anciens dossiers annuels supprimés.
Leurs poids, contrats, features et prix sont vérifiés par empreintes ; aucun fit.
Les dates de disponibilité train/validation de chaque fold doivent précéder
strictement sa première décision hors échantillon.

Recalcul des scores sur **toutes** les lignes observables des features archivées,
avec rangs cross-sectionnels sur l'univers complet, avant qualification future.
Les anciens OOF conditionnés à la qualité future ne définissent jamais le TOP5 :
ils servent uniquement à vérifier la reproduction des scores CatBoost sur leurs
clés d'origine (tolérance absolue 1e-7). TOP5 score décroissant, symbole croissant
en cas d'égalité. Pas de remplacement par le rang suivant après exclusion.

Développement : décisions 2018-07-05…2021-12-31, labels entièrement disponibles
**avant le 1er janvier 2022**. Validation : décisions 2022, labels disponibles
**avant le 1er janvier 2023**. Contrôle chronologique : 2023 dans les folds
existants, jusqu'au 7 juillet. Aucun résultat 2024–2026 n'entre dans ce dataset.
Les frontières sont purgées par disponibilité du label, pas seulement par date
du signal. Pas de partage aléatoire entre dates ou titres.

### Nouveaux modèles fournis pour les tests suivants

| Année | Batch demandé |
| --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` |
| 2025 | `model-factory-20261014113226-102eca` |
| 2026 | `model-factory-20261014113232-bc35a7` |

Cette qualification vérifie leurs poids/contrats, le même univers/générateur,
les mêmes colonnes et choisit uniquement le dernier fold disponible **avant**
la première décision de l'année. Une campagne entraînée jusqu'au milieu/fin
de l'année testée n'autorise pas à utiliser son dernier fold en début d'année.
Pas de fit sur les labels de test, ni choix de protections sur leur rendement.
Ces identifiants sont enregistrés pour la prochaine comparaison ; cette étape
ne lance ni entraînement du sélecteur ni backtest avec ces nouveaux modèles.
Les précédents résultats 2024–2026 restent attachés à leurs anciens identifiants.

## Variables autorisées pour ce premier dataset

Liste fixée avant lecture des nouveaux résultats : rendements et range J,
gap déjà connu à J, volume relatif20, volatilités20/60, RSI14, ATR20/close,
distances SMA20/50, momentum5/20/60/120, ratio de volatilités, position dans
le range20, force relative titre/SPY20/60 ; marché SPY : moyenne des rendements
20, volatilité20, distance SMA50, close>SMA200, volatilité20>volatilité60.
Rang Oracle1…5 disponible à J. Identité du titre/date : clés, pas features.

Recalcul causal depuis les barres locales et les closes SPY archivés dans les
features. Les valeurs SPY communes doivent être cohérentes entre titres ; pas
de remplacement par une macro récupérée aujourd'hui. Vérification par préfixe :
tronquer au jour J ne change pas la ligne de features J. Comparaison des variables
recalculées aux valeurs archivées à J ; tolérance de représentation float32
relative1e-4/absolue1e-4. Aucun remplissage silencieux d'une variable manquante.

Historique requis à J : 121 séances consécutives OHLCV qualifiées et identité
constante ; benchmark au moins201 closes consécutifs connus. Les moyennes et
fenêtres ne traversent pas une rupture d'identité connue. Les canaris par préfixe
ne certifient pas les vintages historiques du fournisseur : les prix sont des
historiques ajustés actuels. Certaines valeurs de cache sont float32.

Exclus du premier jeu : VIX/VXN/MOVE/taux/sentiment macro, sentiment/news,
consensus, fondamentaux, secteur actuel, scores selector (dont short_score),
identité du titre, date/année ou résultat futur. Le score Oracle reste en
métadonnée : il utilise notamment un selector_short_score dont la lineage
historique n'est pas certifiée. Le rang/périmètre Oracle hérite aussi de cette
réserve amont ; aucune prétention de PIT strict sur l'ensemble de la sélection.
On n'invente pas les nouvelles données prospectives sur 2018–2023.

## Labels et exécutions hypothétiques

60 séances, entrée J+1 incluse, coût unitaire et résolution des protections
identiques au diagnostic ; stop d'abord en ambiguïté, trailing effectif à la
séance suivante, gaps conservateurs, pas de H20 ni vente terminale fictive.
Toute fenêtre ouverte à60 est MTM. Disponibilité commune = clôture J+60,
y compris les trades sortis plus tôt. Open J+1, prix d'entrée, gap J+1,
résultats et disponibilité sont dans les labels/journal, **jamais les features**.

Objectifs préparés : avantages de COURT et LARGE face à REFERENCE, en points
de rendement unitaire net ; pas classification arbitraire des ex aequo. Les trois
rendements restent archivés. Un sélecteur futur devra être comparé aussi à un
profil constant sélectionné sur développement/validation seulement.
La pertinence d'un objectif borné à60 pour une détention finale illimitée reste
à qualifier avant un replay économique. Les coûts unitaires ne sont pas ceux
du portefeuille à levier variable, avec réinvestissement et limites de capital.

Les chemins futurs doivent être qualifiés sur les mêmes60 séances pour les trois
profils : barres présentes/cohérentes, volume positif, non remplies, identité
constante, pas de rupture connue. Les contrôles rétrospectifs n'en font pas des
filtres live. Entrée gap absolu J+1 limité à3 %. Prix sur base split de l'archive,
aucun ajustement dividend/adj_close ajouté une seconde fois aux labels.
Exclusions et purges conservées avec raisons, sans éliminer simplement les pertes.

## Livrables, contrôles et critères de préparation

Artefacts séparés :
`artifacts/research/us_oracle_path_protection_dataset/20261014-v1`.
Protocole/empreintes avant calcul, reprise par fold/chunk, progress.json,
features à J séparées des outcomes, index complet et journal des exclusions.

Inventaire des familles de features et leur statut de lineage, taux de
couverture, comptages développement/validation/contrôle2023, dates maximales
de disponibilité, ex aequo et tailles après espacement d'un même titre60 séances.
Ce dernier contrôle ne remplace pas l'échantillon original.

Prêt **pour un pilote exploratoire seulement** si tous les contrôles de
reproduction/chronologie/prefixe passent, chaque split contient au moins100
exemples qualifiés et30 dates, et chaque variable autorisée a au moins95 % de
couverture sur les candidats admis à J. Ce gate évalue la préparation technique,
pas la taille statistique effective suffisante, ni la prédictibilité du bon profil.
Les candidats répétés, les secteurs non utilisés, l'univers de survivants actuel,
les vintages de prix non archivés à chaque date et la réserve du score Oracle
amont restent explicitement signalés. Aucun GO automatique d'entraînement.

## Résultat terminé — préparation, pas entraînement

Verdict : `READY_FOR_EXPLORATORY_PILOT_NOT_TRAINED`. Le gate de préparation
technique passe ; la prédictibilité du bon profil n'a pas été testée ici.

### Comptes et purge

Les dix folds ont scoré **2 152 562 lignes observables**, avant filtre de qualité
future, contre2 146 823 clés des anciens OOF conditionnés. Les scores CatBoost
sont reproduits sur toutes ces anciennes clés avec **écart maximal zéro**.
Le TOP5 est figé sur les scores du pool observable :6 300 candidats originaux.

6 233 candidats passent les contrôles à J ;5 115 ont des outcomes communs
qualifiés. Exclusions :1 109 gaps J+1 >3 %,67 historiques/identités J non
qualifiés,9 fenêtres futures à OHLCV absent/non positif. Aucun remplacement.
Les9 chemins inconnus sont réservés pour les trois profils et conservés dans
le journal ; leur retrait n'est pas une règle live ni une suppression de perdants.

Parmi les5 115 :254 labels du développement et210 de validation débordent
sur l'année suivante. Ils restent archivés mais sont **purgés** des splits.

| Split | Exemples prêts | Dates | Titres | Exemples non chevauchants | Dernière décision | Dernier label disponible |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Développement2018–2021 | 3 342 | 794 | 85 | 209 | 2021-10-06 | 2021-12-31 |
| Validation2022 | 752 | 185 | 44 | 65 | 2022-10-05 | 2022-12-30 |
| Contrôle2023 partiel | 557 | 128 | 31 | 39 | 2023-07-07 | 2023-10-02 |

Les colonnes non chevauchantes rappellent la petite taille effective : il ne
faut pas considérer3 342 candidats quotidiens comme3 342 trades indépendants.
Les chiffres indiquent une préparation exploitable pour un petit pilote,
pas une puissance statistique garantie. Le contrôle2023 n'est pas un nouveau
holdout vierge au regard des nombreuses expériences précédentes.

### Qualification des features

**24 variables** :16 titre,7 marché/relatif,1 rang Oracle. Toutes sont finies
sur les6 300 candidats originaux ; cela ne dispense pas du contrôle de
121 barres/identité à J, qui réserve67 observations. Aucune imputation.
148 titres ont figuré dans la sélection ; **404 canaris de préfixe exacts**
et comparaison de toutes les variables recalculées aux valeurs archivées,
dans la tolérance de représentation float32. Pas d'utilisation de prix futurs,
gap J+1, outcome, identité du titre ou année comme feature.

Les macros archivées sont uniquement inventoriées dans `lineage-inventory.json` :
dates en base ne prouvent pas la publication/disponibilité historique. Elles
ne sont pas ajoutées au jeu primaire. La même prudence vaut pour news,
consensus, secteur actuel et selector_short_score. Le rang Oracle hérite
cependant de la réserve de lineage de son modèle amont ; PIT strict non certifié.

Les résultats des trois profils sont identiques sur53,98 /56,12 /47,58 % des
exemples des trois splits.65,0 /68,4 /58,3 % sont négatifs avec les trois.
Les deux objectifs restent des **avantages continus face à REFERENCE**, pas
une classe de meilleur profil attribuée artificiellement aux ex aequo.
Aucun seuil, poids ou réglage n'a été choisi à partir de ces résultats.

### Trois nouveaux modèles annuels qualifiés, tests pas encore lancés

| Test | Batch fourni | Fold causal retenu | Dernier label de validation du fold |
| --- | --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 | 2023-12-04 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 | 2024-12-04 |
| 2026 | `model-factory-20261014113232-bc35a7` | 2025-12-10 | 2025-12-09 |

CatBoost explicite dans les trois contrats, mêmes173 features/générateur et
univers1 790 que l'OOF historique. Poids intacts, folds retenus inchangés pendant
chacune des périodes testées. Les fins de training demandées dans les campagnes
(2024-11-30,2025-11-30,2026-09-30) ne servent pas à justifier l'usage de leur
dernier fold : seuls les folds ci-dessus peuvent être utilisés au début de l'année.
Les nouveaux scores annuels et backtests ne sont pas encore calculés ici.
Les anciens résultats de marge théorique restent attachés aux anciens modèles.

### Vérification finale et suite

**35 tests ciblés réussis** (12 dataset,23 diagnostic). Contrôle arithmétique
distinct dans `completion-audit.json` : clés candidates/features/index/labels/
exclusions identiques, entrées J+1 et disponibilité commune J+60, avantages
COURT/LARGE recomputés, aucune variable future dans X, frontières purgées,
empreintes présentes et les trois contrats annuels revérifiés.

La prochaine étape, sous nouveau GO, serait un **petit sélecteur à deux
objectifs d'avantage relatif**, architecture/hyperparamètres et décision
figés avant fit, développement2018–2021, validation2022, contrôle2023 puis
nouveaux modèles annuels2024–2026. Il doit battre REFERENCE et un constant
choisi sans lire les résultats des tests ; ne pas ajuster après des pertes.
Le corpus OOF permet un pilote exploratoire, pas une promotion automatique.
Un résultat défavorable doit pouvoir clore cette piste sans multiplier les profils.

Rapport : `artifacts/research/us_oracle_path_protection_dataset/20261014-v1/report.json`.
Features séparées : `decision-features.parquet`. Résultats : `outcomes.parquet`.
Index/purges : `dataset-index.parquet`. Rejets : `excluded.parquet`.
Scores/reprises : sous-dossiers `folds`. Pas de run encore en cours.

### Suite réalisée après un nouveau GO, le même 14 octobre

Le sélecteur et les douze comparaisons annuelles ont désormais été exécutés
dans un dossier distinct. Le statut « pas entraîné » ci-dessus décrit cette
**étape de préparation**, pas l'état de la suite. Résultat de la suite : choix
LARGE constant, aucune personnalisation utile, `NO_GO_STABLE_PERSONALIZATION`.
[Protocole du fit, modèles annuels et résultats économiques](oracle_path_selecteur_protections_20261014.md).
