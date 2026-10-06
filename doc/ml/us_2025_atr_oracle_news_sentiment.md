# US 2025 — Croisement ATR / Oracle H20 et news à sentiment fort

## Synthèse des variantes testées — mise à jour du 4 octobre 2026

Ces expériences sont **terminées comme analyses descriptives**, sans GO
trading. La sélection de départ des tests directionnels est l'intersection
ATR20 TOP20 × Oracle TOP20 : **67 084 couples symbole/séance**, soit
**14,92 %** des 449 500 couples de l'univers sur 250 séances de 2025.
Une même action peut apparaître plusieurs jours : les effectifs ne sont
ni des nombres de trades ni des observations statistiquement indépendantes.

| Variante | Règle exacte | Couples positifs | D10 parmi positifs | Couples négatifs | D1 parmi négatifs |
|---|---|---:|---:|---:|---:|
| Base sans news | Intersection ATR20 × Oracle seule | 67 084 | 22,18 % | 67 084 | 18,15 % |
| J, au moins un article | Maximum quotidien >0,9 | 3 830 | 25,22 % | 4 371 | 17,34 % |
| J−3 à J, au moins un par séance | Quatre séances non vides, maximum >0,9 chacune | 147 | 24,49 % | 240 | 18,75 % |
| J−3 à J, tous les articles | Quatre séances non vides, chaque article scoré >0,9 | 0 | Non calculable | 5 | 20,00 % (1 cas) |
| **J, tous les articles** | **Séance non vide, chaque article scoré >0,9** | **1 610** | **25,78 %** | **1 948** | **17,56 %** |

Les colonnes positif/négatif correspondent respectivement à
`positive_score` et `negative_score`, jamais à un signe appliqué au même
score. D1/D10 sont les vrais déciles de rendement ajusté H20 dans **tout
l'univers quotidien**, non dans le sous-groupe filtré. Un score de sentiment
0,9 n'est pas une probabilité de rendement futur ni une probabilité D10/D1.

**Correction de lecture importante :** la variante « maximum quotidien »
et la variante « tous les articles » sont deux expériences distinctes.
Les résultats de la section 13 ne satisfaisaient pas la demande finale
« tous les articles » ; les sections 14 et 15 la traitent sur le corpus
scoré. On conserve les anciens résultats pour tracer cette différence,
pas pour les présenter comme équivalents.

### Conclusions et limites communes

- L'ATR ressemble fortement au classement Oracle (recouvrement 74,54 %
  pour ATR20), mais leur intersection contient encore les deux directions.
- À J, les news positives enrichissent modestement les D10. Exiger tous
  les articles donne +3,60 points face à la base, mais conserve 18,88 % D1.
- Les news négatives à J n'enrichissent pas les D1. La règle négatif ⇒ SHORT
  n'est pas validée par ces résultats.
- Quatre séances de news fortes réduisent drastiquement le support ;
  cinq cas négatifs avec « tous les articles » ne permettent pas de conclure.
- L'archive ne contient que les articles dont l'inférence a réussi.
  Les articles bruts non scorés ne sont pas couverts par la condition
  « tous » : la conformité exhaustive à tous les articles reste à vérifier.
- Les scores archivés de 2025 ont des dates de création postérieures à
  2025. PIT non certifié ; J peut inclure des publications après l'heure
  d'entrée envisagée. Ce n'est pas un backtest causal.
- Aucun test de significativité avec regroupement par date/symbole,
  confirmation multi-annuelle ou résultat net de frais n'a été produit.
  Les variantes ont été explorées successivement sur la même année :
  ne pas sélectionner la meilleure a posteriori et annoncer un alpha OOS.

### Où retrouver les détails

- Sections 1–10 : périmètre, croisement ATR/Oracle et fenêtres de news.
- Section 11 : répartition réelle D1–D10 de l'intersection.
- Section 12 : sentiment fort à J, maximum quotidien.
- Section 13 : quatre séances, maximum quotidien.
- Section 14 : quatre séances, tous les articles scorés.
- Section 15 : J uniquement, tous les articles scorés (dernière demande).

### Artefacts et reproduction

Tous les résultats sont dans `artifacts/research/us_atr_oracle_sentiment/` :

| Dossier | Contenu / commande de reproduction |
|---|---|
| `audit-20261004-v1` | Panel Oracle/ATR, articles scorés, fenêtres et rapport initial |
| `intersection-realized-20261004-v1` | Labels natifs H20 et répartition de l'intersection |
| `intersection-sentiment-j-20261004-v1` | `python -m scripts.research.us_intersection_sentiment_deciles` |
| `intersection-sentiment-jminus3-j-20261004-v1` | Même commande avec `--consecutive` |
| `intersection-sentiment-all-articles-jminus3-j-20261004-v1` | Même commande avec `--all-articles` |
| `intersection-sentiment-all-articles-j-20261004-v1` | Même commande avec `--all-articles --same-day-only` |

Les rapports conservent effectifs, déciles, couverture des vrais déciles,
sources et empreintes SHA256. Les scripts refusent d'écraser un dossier
existant : pour reproduire, prévoir un nouveau chemin de sortie dans une
copie/adaptation du script, sans supprimer les preuves archivées.
Les noms de groupes JSON `POSITIVE_AT_J`/`NEGATIVE_AT_J` sont historiques :
la règle réelle se lit dans `sentiment_sessions_required` et `article_rule`
pour les variantes strictes, ainsi que dans les notes du rapport.

Ces calculs n'ont entraîné aucun modèle, lancé aucun backtest, ni écrit de
prédictions/labels en SQL. Les fichiers de recherche et leur documentation
sont indépendants du serving. Pour aller plus loin : vérifier d'abord
l'exhaustivité des articles, leurs dates de disponibilité, puis confirmer
une règle figée sur une autre période avant un éventuel rejeu économique.

## 1. Demande et périmètre

L'année **2025 pour les deux expériences** a été confirmée par l'utilisateur.
Le fichier demandé avec une faute de frappe a été rapproché du fichier réel :
`config/univers/univers_filtred_tradable.txt` (1 798 symboles au lancement).
Oracle : `model-factory-20261003082853-e98332`, horizon entraîné **H20**.

Ce travail est une expérience US indépendante. Il ne démarre pas le Sprint 13
France et ne reprend pas les travaux différés du Sprint 12 France.

Le batch a été entraîné sur une période se terminant le 31 décembre 2024.
Ses prédictions stockées en base couvraient seulement le 5 juillet 2018 au
9 juillet 2024 : elles ne permettaient pas directement de mesurer 2025.
L'expérience calcule donc de nouveaux scores 2025 avec les champions existants,
sans fit et sans modification de `oracle_extreme_predictions`.

## 2. Expérience 1 — Est-ce qu'ATR TOP20 ressemble à Oracle TOP20 ?

Pour chaque séance J, retenir les titres du fichier dont les deux scores
sont disponibles. Les deux classements portent sur **la même intersection**,
pas sur deux univers de tailles différentes.

L'ATR est comparé sous deux variantes du moteur de features existant :

- `atr_14_norm` : moyenne glissante 14 barres du True Range / cours ;
- `atr20_pct` : moyenne glissante 20 barres du True Range / cours.

Le True Range considère le range haut-bas et les écarts par rapport à la
clôture précédente. Le calcul réutilise les conventions d'ajustement du
moteur US. **H20 désigne la cible Oracle**, pas obligatoirement la fenêtre ATR :
ATR14 et ATR20 sont deux références distinctes, pré-spécifiées ici.

Les TOP20 sont obtenus avec un rang percentile quotidien >= 0,80, comme le
gate Oracle existant. Les ex aequo utilisent le rang moyen ; l'effectif peut
donc différer légèrement de 20 % exacts. Pas de seuil de probabilité global.

La statistique principale répond exactement à la question :

`nombre de titres dans ATR TOP20 ET Oracle TOP20 / nombre dans ATR TOP20`.

Les chiffres sont calculés en **couples symbole/séance**, pas en simples
symboles distincts apparus une fois dans l'année. Le rapport comprend :
croisement agrégé, médiane/minimum/maximum quotidien, nombre de séances à
au moins 90 % de recouvrement, et Jaccard intersection/union. Les effectifs
quotidiens sont conservés pour vérification.

Un fort recouvrement signalerait une proximité de classement ; il ne
prouverait ni équivalence des modèles ni précision sur les vrais extrêmes.

## 3. Expérience 2 — Sentiment > 0,9 autour du signal Oracle

Source effective : `news_ticker_sentiment`, colonnes `positive_score` et
`negative_score`, reliée à `news_raw` par `article_id`. Les inférences en
échec sont exclues. La date retenue est `news_raw.effective_trade_date`.
Les timestamps de publication et de scoring sont exportés séparément.

Un sentiment fort signifie **strictement > 0,9** sur l'une des deux
probabilités. Il ne s'agit pas d'un score négatif inférieur à -0,9.
Par symbole et séance, le maximum des scores est retenu : un article fort
suffit ; répéter un article ne donne pas plus de poids à cette séance.
Positif et négatif sont analysés séparément, même si les deux apparaissent
dans une même fenêtre.

### Orientation et fenêtres

J est la séance à laquelle Oracle classe le titre. Une news à T=J+k a le
lag k. J−3/J+3 sont ici **trois séances US**, non trois jours calendaires.

| Fenêtre | News considérées | Interprétation |
|---|---|---|
| Avant uniquement | J−3 à J−1 | Association sans date de news future |
| Même séance | J | Nécessite une convention horaire pour une décision intraday |
| Avant et même séance | J−3 à J | Candidate à un audit prédictif, pas un signal PIT déjà certifié |
| Après uniquement | J+1 à J+3 | Association rétrospective uniquement |
| Symétrique | J−3 à J+3 | Réponse descriptive à la fenêtre demandée |
| Chaque lag séparément | −3, −2, −1, 0, +1, +2, +3 | Localiser l'association sans mélanger avant/après |

Les buffers de fin décembre 2024 et début janvier 2026 évitent de tronquer
les fenêtres des premières et dernières séances 2025. Les jours d'ancrage
évalués restent exclusivement en 2025.

### Deux dénominateurs, deux questions

1. **P(Oracle TOP20 | sentiment fort dans la fenêtre)** : nombre de couples
   symbole/J avec news forte ET TOP20, divisé par tous les couples avec news forte.
2. **P(sentiment fort dans la fenêtre | Oracle TOP20)** : même intersection,
   divisée par tous les couples TOP20 Oracle.

Le taux de base du TOP20 sur le panel et l'enrichissement par rapport à ce
taux sont également rapportés. Ne pas comparer à « 20 % » en oubliant les
effectifs réels et les ex aequo. Le dénominateur ne se limite pas aux seuls
articles autour des titres déjà sélectionnés par Oracle.

Une même news peut contribuer à plusieurs J voisins : les observations
sont corrélées. Les pourcentages décrivent des associations ; ils ne sont
pas un test de causalité ni une mesure statistique indépendante par article.
L'absence de news dans la base n'est pas la preuve d'une absence de news réelle.

## 4. Réponse du prix, à titre descriptif

Le rapport donne aussi le rendement réalisé clôture ajustée J → J+20,
sa valeur absolue moyenne et la fréquence de rendement positif pour chaque
groupe de sentiment. Le chemin doit couvrir vingt séances de marché ; une
séquence de vingt barres avec des séances absentes est rejetée pour ce rendement.
Les barres suivantes servent uniquement à maturer cette mesure ex post :
elles ne participent ni à la prédiction Oracle ni au classement à J.

Ce n'est pas un gain de portefeuille : pas de frais, pas d'exits, pas de
prix d'entrée à l'ouverture. Ce n'est pas une mesure directe D1/D10 et
l'appartenance au TOP20 **prédit** Oracle n'est pas la vérité réalisée H20.

## 5. Limites de disponibilité et biais

- Univers actuel statique : biais de sélection historique possible.
- Features et prix locaux disponibles aujourd'hui : révisions historiques
  possibles, sans certification nouvelle de leur disponibilité en 2025.
- Scores de sentiment potentiellement produits après 2025 : leur date de
  scoring est exportée et le nombre concerné est compté. Un lag négatif ne
  suffit pas à certifier le PIT du scoring/ingestion.
- Le champ `predictive_window` du rapport désigne uniquement une fenêtre
  sans lag futur ; **il ne certifie pas un signal historiquement tradable**.
- Le profil Oracle dynamique du batch contient notamment le short-score.
  L'inférence reproduit son générateur existant ; une faible couverture du
  contexte screener peut affecter les scores et doit rester une réserve.
- Une confiance FinBERT de 0,95 n'est pas P(prix en hausse)=0,95.
- Aucun seuil, univers ou champion choisi selon les rendements 2025.
- Un deuxième fournisseur de barres pour un même symbole/date déclenche
  un arrêt, plutôt qu'un mélange silencieux de séries.

## 6. Implémentation et surveillance

Script isolé : `modelFactory/us_atr_oracle_sentiment_audit.py`.
Tests : `tests/test_us_atr_oracle_sentiment_audit.py`.

```powershell
python -u -m modelFactory.us_atr_oracle_sentiment_audit --batch-id model-factory-20261003082853-e98332 --universe config/univers/univers_filtred_tradable.txt --output artifacts/research/us_atr_oracle_sentiment/nouveau-dossier
```

Sortie du lancement du 4 octobre :
`artifacts/research/us_atr_oracle_sentiment/audit-20261004-v1`.
Journal : `log/batch/us-atr-oracle-sentiment-20261004/stderr.log`.

Étapes dans `progress.json` : `FEATURES`, `ORACLE_INFERENCE`, `NEWS_LOAD`,
`ANALYSIS`, `COMPLETED`. `report.json` contient les résultats, `failure.json`
un éventuel échec. Le dossier existant est refusé ; ne pas relancer dans le
même dossier pendant que le premier run travaille.

Le démarrage a chargé 1 877 069 barres sur 1 798 titres, plus SPY et le contexte
screener. Le calcul des features est la partie principale du travail, pas un
entraînement. Trois tests ciblés passent ; Ruff passe. Aucun test complet de
l'application n'est revendiqué.

Écritures : uniquement fichiers de recherche et logs. Pas de SQL INSERT,
UPDATE, DELETE ou DDL ; pas de modèle réentraîné ; aucun batch existant touché.
Les sorties conservent empreintes du fichier d'univers et du champion utilisé.

## 7. Premier résultat calculé sur le panel produit

Le panel contient 449 500 couples symbole/séance : 1 798 titres et 250 dates
présentes en 2025. Les deux sélections ATR comptent chacune 90 000 couples.

| Référence | Intersection avec Oracle TOP20 | Part du TOP20 ATR aussi dans Oracle TOP20 |
|---|---:|---:|
| ATR14 / prix | 66 659 | 74,07 % |
| ATR20 / prix | 67 084 | 74,54 % |

Ces résultats proviennent de `oracle_atr_panel.parquet` créé par ce run,
pas d'une statistique d'entraînement. Le taux de 90 % n'est pas atteint sur
l'agrégat annuel. Une intersection élevée est compatible avec un Oracle
qui capte fortement la volatilité habituelle ; elle ne prouve pas que son
information supplémentaire est inutile.

Le rapport final est `COMPLETED_DESCRIPTIVE_NOT_CAUSAL`. Aucune des 250
séances n'atteint 90 % de recouvrement. Le maximum quotidien est 79,72 %
pour les deux variantes ; les minimums sont 65,28 % (ATR14) et 66,67 % (ATR20).
Ne pas assimiler le nombre de dates présentes à une certification
d'exhaustivité du calendrier ou de qualité PIT des barres.

## 8. Résultats news terminés — association avec le TOP20 Oracle

206 409 observations article/symbole en 2025 sur 1 747 des 1 798 titres.
36 947 observations ont un score positif >0,9 ; 28 606 un score négatif >0,9.
Ce ne sont pas des articles tous uniques : un article peut concerner
plusieurs titres. Les fenêtres sont dédoublonnées en couples symbole/J.

Taux de base d'appartenance au TOP20 : **20,02 %**.

| News forte présente | Positif : P(TOP20 Oracle \| news) | Négatif : P(TOP20 Oracle \| news) |
|---|---:|---:|
| J−3 à J−1 | 19,12 % (12 055 / 63 048) | 24,37 % (12 414 / 50 931) |
| J uniquement | 19,35 % (5 157 / 26 650) | 25,34 % (5 335 / 21 053) |
| J−3 à J | 19,16 % (14 892 / 77 733) | 24,17 % (15 243 / 63 065) |
| J+1 à J+3 | 19,32 % (12 226 / 63 286) | 24,40 % (12 461 / 51 079) |
| J−3 à J+3 | 19,15 % (21 748 / 113 552) | 23,53 % (21 787 / 92 573) |

Les news positives fortes ne sont pas davantage présentes dans le TOP20
que le taux de base. Les négatives présentent une association modeste :
sur J−3/J−1, +4,35 points et un enrichissement de 1,22×, pas une probabilité
de succès directionnel de 24,37 %.

La présence de news négatives avant J est associée au TOP20 dans les deux
semestres : 23,10 % au premier et 25,30 % au second. Les positives restent
proches ou en dessous de la base : 18,87 % puis 19,26 %. Ce contrôle ne
constitue pas un test d'incertitude ni une neutralisation par titre/ATR/secteur.

**Sens inverse du conditionnement :** parmi les 90 000 couples TOP20,
24,16 % ont une news positive forte dans J−3/J+3, et 24,21 % une négative
forte. Ces groupes peuvent se chevaucher : ne pas additionner les deux
pourcentages comme une couverture exclusive.

## 9. Réponse réelle du prix parmi les candidats Oracle

Lecture complémentaire de `symbol_day_windows.parquet`, sur J−3/J−1 :

| Groupe | Couples symbole/J | Rendement H20 moyen signé | Variation H20 absolue moyenne | Fraction de hausses H20 |
|---|---:|---:|---:|---:|
| Tout l'univers | 449 500 | +1,02 % | 7,65 % | 53,48 % |
| Oracle TOP20 entier | 90 000 | +2,13 % | 11,90 % | 53,77 % |
| Oracle TOP20 + news positive forte avant J | 12 055 | +3,35 % | 11,95 % | 57,36 % |
| Oracle TOP20 + news négative forte avant J | 12 414 | +3,59 % | 12,21 % | 56,62 % |

Les groupes positifs **et négatifs** ont ici un rendement moyen positif.
Donc la règle « news négative >0,9 ⇒ SHORT » n'est pas justifiée par ce
diagnostic. Un rebond après mauvaise nouvelle, une sélection de titres ou
un effet de marché sont des explications possibles, pas démontrées ici.

Les moyennes sont descriptives, pondérées par couples symbole/séance ; elles
peuvent être dominées par certains titres ou extrêmes. Les horizons et les
fenêtres se chevauchent. Elles ne prouvent pas un gain statistiquement robuste,
ni un gain net exploitable. La différence de fréquence de hausse avec Oracle
seul ne doit pas être interprétée comme un test D1/D10 concluant.

## 10. Réserve PIT et décision de recherche

**206 409 / 206 409 observations sentiment 2025 ont `created_at` après
la fin de 2025.** Ce timestamp peut être affecté par une création ou une
reconstitution actuelle de la base ; il ne prouve pas que les articles étaient
absents historiquement. En revanche, le dossier ne prouve pas que ces scores
étaient utilisables en 2025. Aucune promotion vers un backtest PIT/live.

Conclusion : proximité ATR/Oracle forte mais <90 % ; faible association
news négatives/amplitude prédite ; pas de correspondance simple entre signe
FinBERT et direction H20. L'utilité incrémentale n'est pas encore démontrée.

Proposition uniquement, **non lancée** : comparer les candidats Oracle avec
et sans news forte avant J sur des contrôles appariés en ATR, titre, régime et
couverture news ; séparer réaction initiale/rebond et confirmer hors de 2025.
Cela aiderait à distinguer information supplémentaire et simple sélection
de titres habituellement volatils. Le Sprint 13 France demeure non démarré.

## 11. Intersection ATR TOP20 × Oracle TOP20 dans les vrais déciles H20

Complément demandé par l'utilisateur : quel pourcentage du total reste,
et où se situent réellement les candidats retenus ?

Les labels stockés du batch s'arrêtaient au 31 décembre 2024. Les labels
2025 ont donc été reconstruits par **le constructeur natif `build_labels`,
en `dry_run=True`**, sans INSERT/UPDATE. Les gardes natives de source,
identité, prix aux deux extrémités et rupture extrême sont conservées.
449 500 labels sont valides selon ces gardes ; aucun label indisponible ou
invalidé. Cela ne constitue pas une certification PIT additionnelle.

Les vrais déciles sont classés par rendement ajusté réalisé J→J+20 dans
**tout l'univers quotidien**, jamais à l'intérieur de l'intersection. D1
désigne les pires 10 % ; D10 les meilleurs 10 %. Les gates ATR/Oracle sont
figés avant la jointure avec ces informations futures.

### Taille du groupe

- ATR14 × Oracle : 66 659 / 449 500 = **14,83 %** de l'univers.
- ATR20 × Oracle : 67 084 / 449 500 = **14,92 %** de l'univers,
  soit environ **268 titres par séance**, contre 360 pour un TOP20 seul.

Oui, l'approximation est 74,5 % × 20 % ≈14,9 %. Les chiffres exacts diffèrent
légèrement car la règle percentile >=0,80 garde 20,02 % ici.

### Répartition réelle : variante ATR20

Pourcentages calculés **à l'intérieur de chaque groupe sélectionné** :

| Décile réel H20 | ATR20 TOP20 seul | Oracle TOP20 seul | Intersection ATR20 × Oracle |
|---|---:|---:|---:|
| D1 | 16,67 % | 18,17 % | 18,15 % |
| D2 | 9,75 % | 9,74 % | 9,53 % |
| D3 | 7,50 % | 7,50 % | 7,09 % |
| D4 | 6,82 % | 6,55 % | 6,40 % |
| D5 | 6,54 % | 6,08 % | 5,94 % |
| D6 | 6,61 % | 6,07 % | 6,02 % |
| D7 | 7,08 % | 6,65 % | 6,53 % |
| D8 | 8,28 % | 7,68 % | 7,68 % |
| D9 | 10,99 % | 10,50 % | 10,49 % |
| D10 | 19,75 % | 21,06 % | 22,18 % |
| **D1 + D10** | **36,42 %** | **39,23 %** | **40,33 %** |

L'univers entier est à 19,97 % en D1+D10, légèrement différent de 20 % à
cause des effectifs/rangs. Le flag natif `oracle_extreme10` peut inclure un
rang situé exactement à 90 %, différent du strict regroupement D1+D10 :
les chiffres du tableau utilisent bien les déciles, pas ce flag de frontière.

Conclusion : l'intersection enrichit légèrement la sélection Oracle en
vrais extrêmes (+1,10 point), mais conserve à la fois des D1 et des D10 ;
elle ne résout pas le problème directionnel. Les candidats Oracle qui ne
sont pas dans ATR20 TOP20 contiennent encore **36,01 % de vrais D1/D10**.
Les retirer n'est donc pas éliminer uniquement des erreurs.

La variante ATR14 donne 18,23 % D1, 22,31 % D10 et 40,53 % D1+D10 dans
l'intersection. Pas de choix a posteriori d'une variante gagnante ni de test
de rentabilité lancé.

Reproduction et contrôle :

- Script : `modelFactory/us_atr_oracle_realized_audit.py`.
- Test : `tests/test_us_atr_oracle_realized_audit.py` (un test ciblé passe ; Ruff passe).
- Sorties : `artifacts/research/us_atr_oracle_sentiment/intersection-realized-20261004-v1`.
- `native_realized_labels.parquet` conserve labels/qualité/provenance ;
  `report.json` conserve effectifs, répartitions, inconnus et empreintes.

L'évaluation est rétrospective 2025 sur l'univers statique demandé. Elle ne
prouve pas une robustesse multi-annuelle, un gain net, ni une disponibilité
historique stricte des données.

## 12. Sentiment strictement supérieur à 0,9 à J dans l'intersection

L'intersection ATR20 TOP20 × Oracle TOP20 est figée : **67 084 couples
symbole/séance**, soit 14,92 % des 449 500 observations de 2025. On conserve
ensuite les couples ayant au moins un article positif ou négatif dont le
score est **strictement >0,9**, à la séance J (`effective_trade_date`). Les
déciles réalisés H20 restent ceux de l'univers quotidien entier.

| Décile réel H20 | Intersection sans filtre news | Positive >0,9 à J | Negative >0,9 à J |
|---|---:|---:|---:|
| D1 | 18,15 % | 18,96 % | 17,34 % |
| D2 | 9,53 % | 8,80 % | 10,11 % |
| D3 | 7,09 % | 7,28 % | 7,89 % |
| D4 | 6,40 % | 6,03 % | 5,65 % |
| D5 | 5,94 % | 4,91 % | 5,90 % |
| D6 | 6,02 % | 5,04 % | 5,74 % |
| D7 | 6,53 % | 6,06 % | 6,04 % |
| D8 | 7,68 % | 7,57 % | 8,67 % |
| D9 | 10,49 % | 10,13 % | 9,88 % |
| D10 | 22,18 % | 25,22 % | 22,76 % |

- Positif : **3 830 couples**, 459 symboles distincts ; 5,71 % de
  l'intersection, 0,85 % de l'univers. **966 vrais D10** : précision 25,22 %,
  +3,05 points par rapport à l'intersection sans filtre. Cela ne capture
  que **6,49 %** des 14 877 vrais D10 présents dans l'intersection.
- Négatif : **4 371 couples**, 451 symboles distincts ; 6,52 % de
  l'intersection, 0,97 % de l'univers. **758 vrais D1** : précision 17,34 %,
  −0,81 point. Cela capture **6,22 %** des 12 177 vrais D1 de l'intersection.
  Le groupe contient davantage de D10 (995) que de D1 : ce filtre ne
  démontre pas de signal SHORT.

Les groupes ne sont pas exclusifs : **838 couples ont les deux sentiments
forts**, éventuellement dans des articles différents. Si on exclut ces
conflits, le positif seul donne 783 D10 / 2 992 = **26,17 %** ; le négatif
seul donne 597 D1 / 3 533 = **16,90 %**. Cette sensibilité descriptive n'est
pas une nouvelle politique de trading validée.

**Limites :** les dates de scoring enregistrées sont postérieures à 2025 ;
la disponibilité PIT des scores n'est pas certifiée. La séance J ne garantit
pas une disponibilité avant l'entrée. Aucun gain économique, causal ou
hors échantillon additionnel n'est démontré par ces répartitions.

Reproduction : `python -m scripts.research.us_intersection_sentiment_deciles`.
Résultats :
`artifacts/research/us_atr_oracle_sentiment/intersection-sentiment-j-20261004-v1/report.json`.
La comparaison gère les conflits et distingue précision et couverture ;
les deux tests ciblés de `test_us_atr_oracle_realized_audit.py` passent,
ainsi que Ruff. Aucune écriture SQL, aucun entraînement ou backtest.

## 13. Quatre séances consécutives de sentiment fort, J−3 à J

Filtre dans la même intersection figée : chacune des quatre séances de
bourse J−3, J−2, J−1, J doit avoir au moins un article avec le score du
côté étudié strictement >0,9. Une séance sans article/score échoue ; aucun
report du dernier score. Il s'agit du maximum quotidien, pas de l'exigence
que tous les articles soient >0,9. ATR/Oracle sont requis à J seulement.

| Décile H20 | Positif quatre séances | Négatif quatre séances |
|---|---:|---:|
| D1 | 25,85 % (38) | 18,75 % (45) |
| D2 | 6,12 % (9) | 9,58 % (23) |
| D3 | 5,44 % (8) | 6,67 % (16) |
| D4 | 4,08 % (6) | 6,25 % (15) |
| D5 | 9,52 % (14) | 8,75 % (21) |
| D6 | 6,80 % (10) | 5,00 % (12) |
| D7 | 2,04 % (3) | 5,83 % (14) |
| D8 | 6,80 % (10) | 10,00 % (24) |
| D9 | 8,84 % (13) | 10,83 % (26) |
| D10 | 24,49 % (36) | 18,33 % (44) |

Positif : 147 couples, 40 symboles distincts ; négatif : 240 couples,
56 symboles. Seulement 0,22 % et 0,36 % de l'intersection subsistent.
Les observations se chevauchent temporellement : elles ne représentent
pas autant de trades ou d'événements indépendants.

Le positif ne s'améliore pas face au filtre J seul (25,22 % D10) et
conserve davantage de D1 que de D10. Le négatif est légèrement au-dessus
de la base en D1 (18,75 % contre 18,15 %), sans séparation convaincante.
23 couples, sur deux symboles, satisfont les deux côtés. Sans ces conflits,
le positif seul donne 36/124 =29,03 % D10 et 27/124 =21,77 % D1 ;
le négatif seul donne 34/217 =15,67 % D1. Ce petit échantillon et ces
sensibilités ne justifient aucune validation de stratégie.

Les limites PIT/rétrospectives de la section 12 s'appliquent toujours.
Reproduction : `python -m scripts.research.us_intersection_sentiment_deciles --consecutive`.
Rapport : `artifacts/research/us_atr_oracle_sentiment/intersection-sentiment-jminus3-j-20261004-v1/report.json`.

## 14. Correction de la demande : TOUS les articles, pas le maximum

La section 13 ne correspond pas à la condition finale demandée. Le nouveau
filtre exige **quatre séances non vides et chaque article scoré >0,9**,
du même côté, sur chacune. Un article <=0,9 ou sans score fait échouer
sa séance. La règle ne réutilise plus les maxima quotidiens.

Résultat 2025 dans les 67 084 couples ATR20 × Oracle : **aucun candidat
positif**, **5 couples négatifs sur 4 symboles**. Les cinq déciles réalisés
sont D1, D6, D7, D8 et D10, chacun une fois (20 %). Échantillon trop petit
pour conclure à une capacité directionnelle.

Attention : l'archive utilisée contient les inférences réussies, et non
tous les articles bruts sans inférence. Les cinq candidats satisfont donc
la règle sur **tous les articles scorés présents dans l'archive** ; ils ne
sont pas certifiés conformes si des articles non scorés supplémentaires
existent. Le zéro positif reste éliminatoire même avec ce périmètre plus
favorable. Les autres réserves PIT restent inchangées.

Reproduction : `python -m scripts.research.us_intersection_sentiment_deciles --all-articles`.
Rapport : `artifacts/research/us_atr_oracle_sentiment/intersection-sentiment-all-articles-jminus3-j-20261004-v1/report.json`.
Test dédié : `tests/test_us_sentiment_all_articles.py`.

## 15. Tous les articles >0,9, à J uniquement

Même intersection figée ATR20 × Oracle en 2025. Chaque article scoré de
la séance J doit avoir un score du côté testé strictement >0,9. Une
séance vide, un score manquant ou un seul article <=0,9 exclut le couple.
Les séances antérieures ne sont plus contraintes.

| Décile réel H20 | Tous positifs >0,9 à J | Tous négatifs >0,9 à J |
|---|---:|---:|
| D1 | 18,88 % (304) | 17,56 % (342) |
| D2 | 8,63 % (139) | 10,27 % (200) |
| D3 | 7,83 % (126) | 8,01 % (156) |
| D4 | 6,02 % (97) | 6,37 % (124) |
| D5 | 3,98 % (64) | 5,95 % (116) |
| D6 | 4,35 % (70) | 5,80 % (113) |
| D7 | 6,21 % (100) | 5,95 % (116) |
| D8 | 7,70 % (124) | 8,21 % (160) |
| D9 | 10,62 % (171) | 10,27 % (200) |
| D10 | 25,78 % (415) | 21,61 % (421) |

Positif : 1 610 couples sur 378 symboles, soit 2,40 % de l'intersection.
Négatif : 1 948 couples sur 389 symboles, soit 2,90 %. Aucun conflit des
deux groupes dans ce corpus. D10 positif : +3,60 points contre la base
22,18 %, mais 18,88 % de D1 subsistent. D1 négatif : −0,60 point contre
la base 18,15 % ; le filtre négatif n'enrichit pas les D1.

Les articles non scorés ne sont pas représentés dans l'archive ; ces
sélections restent des candidats sur le corpus scoré, pas une certification
de conformité sur tous les articles bruts. Les réserves PIT restent valables.
Aucun gain net ou stabilité multi-annuelle n'est démontré.

Reproduction : `python -m scripts.research.us_intersection_sentiment_deciles --all-articles --same-day-only`.
Rapport : `artifacts/research/us_atr_oracle_sentiment/intersection-sentiment-all-articles-j-20261004-v1/report.json`.

## 16. Seuil >0,95 à J et dix meilleurs par séance

La règle « tous les articles scorés de J » est conservée. Deux tests :
(a) chacun >0,95, (b) même filtre puis au plus dix titres par séance et
par côté dans l'intersection ATR20 × Oracle. Le classement utilise le
**minimum des scores des articles du jour**, décroissant : il représente
le score garanti par tous les articles. Ex aequo départagés par symbole.
Moins de dix éligibles : tous retenus, sans compléter avec des non-éligibles.
La sélection est faite avant lecture des déciles futurs.

| Décile réel H20 | Positif >0,95 | Positif >0,95 TOP10/jour | Négatif >0,95 | Négatif >0,95 TOP10/jour |
|---|---:|---:|---:|---:|
| D1 | 19,24 % | 19,24 % | 17,62 % | 17,80 % |
| D2 | 8,50 % | 8,50 % | 10,19 % | 10,47 % |
| D3 | 7,16 % | 7,16 % | 8,17 % | 7,87 % |
| D4 | 6,94 % | 6,94 % | 6,22 % | 6,22 % |
| D5 | 3,13 % | 3,13 % | 5,92 % | 6,14 % |
| D6 | 4,70 % | 4,70 % | 5,62 % | 5,43 % |
| D7 | 6,94 % | 6,94 % | 5,92 % | 6,14 % |
| D8 | 6,04 % | 6,04 % | 8,25 % | 8,11 % |
| D9 | 12,30 % | 12,30 % | 10,27 % | 10,47 % |
| D10 | 25,06 % | 25,06 % | 21,81 % | 21,34 % |
| Couples retenus | 447 | 447 | 1 334 | 1 270 |
| Symboles distincts | 215 | 215 | 345 | 337 |

Le cap TOP10 ne retire aucun positif : aucun jour n'a plus de dix
positifs éligibles. Il retire 64 couples négatifs. Passer de >0,9 à >0,95
n'améliore pas D10 positif (25,78 % →25,06 %), et les négatifs restent
sous la base en D1 (18,15 %). Support réduit, pas de GO directionnel.
Les limites PIT, articles non scorés et sélection exploratoire restent
inchangées. « Dix » signifie ici dix par séance, pas dix sur toute l'année.

Reproduction : commande de section 15 avec `--threshold 0.95`, puis
`--top-per-day 10` pour le second test, en donnant `--output` vers un
nouveau dossier. Rapports respectifs :

- `artifacts/research/us_atr_oracle_sentiment/intersection-all-j-095-20261004-v1/report.json`.
- `artifacts/research/us_atr_oracle_sentiment/intersection-all-j-095-top10-20261004-v1/report.json`.

Le paramètre `--output` permet maintenant de reproduire sans écraser les
preuves précédentes. Test dédié : seuil strict, classement par minimum,
exclusion des candidats hors intersection.

## 17. Sentiment >0,9 à J et prix relatif aux cinq moyennes

Dans l'intersection ATR20 × Oracle, on conserve « tous les articles
scorés de J >0,9 », sans cap TOP10 et sans seuil 0,95. On ajoute :

- Positif / recherche D10 : prix **strictement au-dessus de chacune**
  des SMA 5,10,20,50,100.
- Négatif / recherche D1 : prix **strictement au-dessous de chacune**
  des cinq SMA.

Calcul sur clôtures ajustées EODHD, même convention que le moteur
`features.py`, moyennes simples incluant J. Égalité ou moyenne manquante :
exclusion. Aucune moyenne manquante dans les 67 084 couples de départ.
Les SMA portent sur les dernières barres disponibles du titre, comme les
features natives, sans nouvel audit de continuité de chaque fenêtre SMA.

| Décile réel H20 | Positif + au-dessus des cinq SMA | Négatif + sous les cinq SMA |
|---|---:|---:|
| D1 | 20,31 % (117) | 15,19 % (115) |
| D2 | 8,68 % (50) | 9,78 % (74) |
| D3 | 7,29 % (42) | 8,45 % (64) |
| D4 | 5,56 % (32) | 6,21 % (47) |
| D5 | 3,82 % (22) | 7,00 % (53) |
| D6 | 4,34 % (25) | 5,68 % (43) |
| D7 | 5,90 % (34) | 5,94 % (45) |
| D8 | 7,29 % (42) | 9,25 % (70) |
| D9 | 10,07 % (58) | 11,10 % (84) |
| D10 | 26,74 % (154) | 21,40 % (162) |

576 couples positifs sur207titres,757négatifs sur277titres. Avant ajout
SMA :1 610positifs/25,78 %D10 et1 948négatifs/17,56 %D1. Après :+0,96point
en D10 positif, mais D1 positif augmente aussi de18,88 % à20,31 %. Côté
négatif, D1 recule de2,36points. Pas de signal SHORT démontré et aucune
preuve statistique ou économique d'amélioration LONG.

Les réserves de corpus scoré et de disponibilité PIT restent valables.
Les labels futurs n'entrent pas dans les conditions. Aucune écriture SQL,
aucun entraînement/backtest, serving inchangé.

Reproduction : `python -m scripts.research.us_sentiment_sma_deciles`.
Rapport/panel : `artifacts/research/us_atr_oracle_sentiment/intersection-all-j-09-sma5to100-20261004-v1/`.
Le panel conserve prix, cinq moyennes et conditions ; le rapport conserve
les empreintes et la comparaison au sentiment seul.
