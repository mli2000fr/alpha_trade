# PCA de onze ETF — test de retour à la moyenne, 19 octobre 2026

## Objet et statut

GO pour la suite de [l'essai sectoriel](facteurs_sectoriels_retour_moyenne_20261019.md).
Le protocole et les sources ont été figés avant le calcul. **Replay terminé :
`NO_ROBUST_PCA_ETF_IMPROVEMENT`, sans promotion.** Audit technique final terminé :
`PASS_EXPLORATORY_ETF_PCA_ONLY`.

Il s'agit d'une **PCA de onze ETF sectoriels**, pas d'une PCA de toutes les
actions, ni d'une réplication des performances d'une société de gestion.
L'hypothèse est de mieux isoler le mouvement spécifique du titre en retirant
plusieurs mouvements communs, plutôt que SPY seul ou son seul ETF sectoriel.

La référence conceptuelle est [Avellaneda–Lee, Statistical Arbitrage in the
U.S. Equities Market](https://math.nyu.edu/~avellane/AvellanedaLeeStatArb20090616.pdf).
Notre PCA d'ETF reste différente de leur PCA sur les rendements d'actions.
Le calcul utilise le problème spectral symétrique documenté par
[NumPy](https://numpy.org/doc/stable/reference/generated/numpy.linalg.eigh.html).

## Périmètre, données et absence d'actions externes

- Les **1 593 titres** raccordés de l'expérience sectorielle, et le sous-ensemble
  **TOP10 Oracle amplitude H10** figé à J. Les autres titres ne remplacent pas
  ceux exclus ou les résultats inconnus.
- Signaux de 2024 au **1er septembre 2026**, suivi des prix archivé jusqu'au
  30 septembre 2026. Les années ont déjà été examinées : ce n'est pas un nouvel
  échantillon de confirmation vierge.
- Uniquement les archives locales déjà scellées : prix actions normalisés,
  scores Oracle H10 et onze ETF `eodhd_eod`, ajustement déclaré `split`.
- **Aucune requête SQL, collecte fournisseur, API LLM, écriture SQL, nouvel
  entraînement Oracle, modification de batch ou ordre.** La PCA et les
  régressions sont des estimations statistiques glissantes de recherche.

Les ETF sont XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV et XLY.
Les sources inconnues/IEX/Yahoo, barres invalides ou synthétiques et alertes
d'ajustement héritées restent exclues, sans correction inventée.

## Protocole figé avant résultats

### Trois composantes, sans optimisation de leur nombre

À la clôture de J :

1. Prendre les **252 rendements close/close passés**, jusqu'à J inclus, soit
   253 prix. Aucun comblement de données manquantes ; sources et métadonnées
   stables sur toute cette fenêtre pour les onze ETF.
2. Centrer et réduire chaque ETF par sa moyenne et son écart-type historiques
   (`ddof=1`). Extraire les **trois composantes principales** de la matrice de
   corrélation. Trois est un choix figé, pas le gagnant d'une recherche de seuils.
3. Projeter les **60 derniers rendements** dans cette même base calculée à J.
   Ne pas assembler 60 rendements de facteurs issus de 60 bases tournantes.
4. Régression du rendement du titre sur ces trois facteurs avec constante.
   Convertir les trois coefficients en **onze coefficients ETF réellement
   représentables**, puis construire le résidu cumulé et l'AR(1)/score OU du
   protocole parent (variance d'innovation SSE/57).

Les composantes sont recalculées avec le passé à chaque date. Leur signe est
arbitraire : inverser un vecteur propre ne doit changer ni le résidu ni la
couverture finale. Les tests vérifient cette invariance, ainsi que l'invariance
à l'ordre des ETF et la reconstruction d'un préfixe historique.

Écart-type nul, séparation insuffisante entre les troisième et quatrième
valeurs propres, ou régression de rang insuffisant : pas de modèle qualifié,
pas de facteur artificiellement complété.

### Comparaisons équitables, pas des trades identiques

Trois bras : **SPY**, **ETF sectoriel assigné**, **PCA3 ETF**.
Même univers et même support d'entrée : historique PCA suffisamment long,
61 prix propres titre/SPY/ETF assigné, et même proxy de liquidité du parent.
Le premier jour supporté par la PCA est le **4 janvier 2024** ; les 2 et
3 janvier ne sont donc utilisés dans aucun bras de cette comparaison.

Chaque bras produit son propre résidu, son signal, ses épisodes et ses sorties.
Une différence de moyennes ne constitue pas une comparaison causale sur les
mêmes positions. Le supplément par date se limite aux dates comportant des
entrées dans les deux bras, sans remplacer les dates absentes par zéro.

Le contrôle de qualité future est également commun : titre, SPY et onze ETF
de J à J+11. Une entrée inconnue reste archivée et n'est jamais remplacée.
Les épisodes sont choisis **avant** ce contrôle : premier signal par
titre/bras/périmètre, blocage jusqu'à J+11 même si la sortie est plus précoce.
Seuls ces épisodes sans chevauchement sont rejoués ; pas de second PnL fondé
sur toutes les entrées superposées.

### Exposition, exécution et coûts de toutes les jambes

Si `h` désigne les coefficients de couverture ETF et `sign` le sens du titre :

```text
poids titre = sign / (1 + somme(abs(h)))
poids ETF j = -sign × h[j] / (1 + somme(abs(h)))
```

Pour SPY et le secteur, un seul coefficient positif est non nul. Pour la PCA,
les coefficients peuvent avoir les deux signes. La somme de leurs valeurs
absolues doit être dans `]0 ; 3]`, analogue au plafond bêta du parent.
L'exposition brute initiale vaut 1 ; cela ne garantit ni même volatilité, ni
neutralité en dollars, ni neutralité parfaite aux facteurs hors échantillon.

- Entrée J+1 open si `s < -1,25` : LONG titre, couverture opposée ; si
  `s > +1,25` : SHORT titre, couverture opposée.
- Même validité OU : `0 < b < exp(-1/30)` et sigma d'équilibre > 1e-8.
- Quantités et couverture **figées à l'entrée**, sans rééquilibrage quotidien.
- Sortie des jambes au prochain open après normalisation ±0,5, invalidation
  du modèle quotidien ou perte brute de panier ≤ −5 % observée au close.
  Au plus dix séances complètes, sortie à l'open J+11. Le seuil quotidien
  n'est pas un SL intraday garantissant une perte maximale de 5 %.
- Contrôle : mêmes jambes conservées dix séances, sans sortie OU anticipée.
- **8 bps par dollar exécuté à chaque jambe**, entrée et sortie ; stress à
  20 bps. Emprunt hypothétique 0,3 % annuel de l'exposition short initiale,
  jours calendaires/365. Pas de facteur synthétique gratuit, pas de netting
  de couvertures entre plusieurs trades supposé gratuitement.

## Critères de résultat

Critères absolus hérités sur 2025 **et** 2026 : au moins 100 épisodes, bornes
basses des IC95 par opération et à poids égal par date positives, net moyen
positif sous stress, et vingt meilleurs gagnants représentant moins de 50 %
des contributions positives. Bootstrap par blocs de vingt séances, 2 000
tirages et graine fixés, sans rendre les titres du même jour indépendants.

Pour annoncer une amélioration, le supplément PCA moins **chacune** des
références SPY/secteur doit également avoir un IC95 strictement positif dans
les deux années. Aucun seuil, nombre de facteurs, TP/SL ou sens favorisé ne
sera choisi après observation des résultats.

## Résultats

Tous les résultats suivants sont **nets moyens par exposition brute initiale
d'occasion**, et non des rendements annuels d'un portefeuille capitalisé.
Les trois bras peuvent déclencher des titres/sens/dates différents.

### Univers retenu, épisodes sans chevauchement, sortie OU

| Année | SPY | ETF sectoriel | PCA trois facteurs | Épisodes PCA |
|---|---:|---:|---:|---:|
| 2024 | −0,052 % | −0,073 % | **−0,160 %** | 12 655 |
| 2025 | +0,001 % | −0,126 % | **−0,095 %** | 12 619 |
| 2026* | −0,148 % | −0,042 % | **−0,077 %** | 8 202 |

*Signaux jusqu'au 1er septembre ; suivi archivé jusqu'au 30 septembre.*

Les IC95 PCA sont respectivement **[−0,242 ; −0,070] %**, **[−0,176 ; −0,006] %**
et **[−0,191 ; +0,054] %**. Sous coûts stressés :
**−0,401 / −0,335 / −0,318 %**. Les taux gagnants de 49,96 / 51,60 / 53,24 %
ne suffisent donc pas à compenser les pertes et frais. Aucun avantage robuste
contre SPY et le secteur n'est confirmé simultanément en 2025 et 2026.

### TOP10 Oracle H10, mêmes règles

| Année | SPY | ETF sectoriel | PCA trois facteurs | Épisodes PCA | Gagnants PCA |
|---|---:|---:|---:|---:|---:|
| 2024 | +0,654 % | +0,199 % | **+0,226 %** | 75 | 54,67 % |
| 2025 | +0,865 % | +0,784 % | **+0,196 %** | 35 | 60,00 % |
| 2026* | −0,105 % | +0,333 % | **−0,277 %** | 8 | 50,00 % |

2024 change légèrement par rapport au rapport sectoriel précédent, car le
support d'entrée est maintenant commun à la fenêtre PCA de 253 prix ;
l'adhésion sans chevauchement est recalculée depuis cette première date.
Ce n'est pas une modification des rendements d'un même trade.

IC95 TOP10 PCA : **[−0,465 ; +0,751] %** en 2024 et **[−0,793 ; +0,899] %**
en 2025. L'IC 2026 n'est **pas estimé** : seulement huit occasions, trop peu
de blocs de dates (minimum cinq pour le bootstrap). Ne pas le remplacer
par `[0 ; 0]`, ni interpréter 50 % gagnants comme une probabilité fiable.
Sous stress : **−0,015 / −0,044 / −0,518 %** ; les trois moyennes deviennent
négatives. Aucun gain directionnel D1/D10 validé.

### Pourquoi si peu de TOP10 en 2026 ?

Diagnostic de couverture effectué **après** le replay, sans modifier de seuil
ou relancer une variante. Comptages de couples titre/date parmi les rangs
TOP10 originaux raccordés au périmètre, pas de remplaçant hors TOP10 :

| Étape | 2024 | 2025 | 2026* |
|---|---:|---:|---:|
| Données passées communes + liquidité utilisables | 2 138 | 1 920 | 1 547 |
| OU/numérique invalide | 14 | 14 | 17 |
| OU valide, mais couverture au-delà du plafond | 1 279 | 1 433 | 1 422 |
| Modèle et exposition acceptés | 845 | 473 | 108 |
| Déviation déclenchant une entrée | 231 | 96 | 19 |
| Épisodes indépendants qualifiés | 75 | 35 | 8 |

En 2026, **91,92 %** des 1 547 cas utilisables échouent au plafond de
couverture après validité OU. La somme absolue médiane des coefficients ETF
vaut **5,13**, contre un plafond figé de 3 (2024 : 3,31 ; 2025 : 4,19).
Dans l'univers large, la médiane est seulement 1,69 / 1,66 / 1,63.
Cela décrit une difficulté de couverture de ces titres extrêmes par ces ETF,
**pas une preuve d'impossibilité de toute PCA ou de toute prédiction**.
Le plafond n'est pas relevé après observation des résultats.

Les trois composantes captent une part médiane de **76,30 % de la variance
standardisée des onze ETF**. Ce chiffre ne mesure ni la variance expliquée des
titres Oracle, ni une précision de direction, ni un taux de trades gagnants.

### Couverture et contrôles

**542 285 candidats**, dont 541 664 à chemin futur qualifié. Parmi les
104 191 épisodes sélectionnés sans chevauchement **avant** qualification,
124 sont inconnus et non remplacés : SPY 24, secteur 49, PCA 51.
**104 067 épisodes** sont donc rejoués selon deux politiques, soit
**208 134 lignes de sorties**. Aucun cas TOP10 inconnu dans ce périmètre.

**170 tests passent**, dont 27 nouveaux : PCA/SVD, OLS/OU, causalité par
préfixe et perturbation future, signe des composantes, permutation des ETF,
fenêtres incomplètes, qualité future, coûts et emprunt des jambes, gaps et
sortie au prochain open. Ce groupe ciblé n'est pas une certification de
couverture de tests de l'ensemble de l'application.

Audit final terminé : **208 134 lignes de sorties**, **542 285 candidats**,
**3 186 estimations scalaires PCA/SVD + OLS/OU**, **50 préfixes historiques** et
**162 287 chemins titre/date** contrôlés. L'implémentation de contrôle utilise
une SVD et des régressions scalaires, distinctes de la diagonalisation de
corrélation et des calculs vectorisés du replay.

Les **140 946 lignes de référence SPY/secteur** rejouées correspondent aux
mêmes entrées du parent : mêmes sorties, écart net maximal **1,11e−16**
(arrondi machine). Leur sélection indépendante peut changer au début de 2024
avec le support commun ; les valeurs d'un trade commun ne changent pas.
Le certificat `final-audit.json` lie le rapport à son empreinte ; il ne
certifie pas une rentabilité, des données historiquement PIT ou une parité broker.

Le diagnostic de couverture est conservé dans `coverage-explanation.json/.csv`.
Son script et ses entrées sont identifiés par empreinte ; il explique les
exclusions après résultat et ne modifie ni le protocole ni les paramètres.

### Décision

**Ne pas promouvoir cette règle PCA3 ETF.** L'univers large est négatif ; le
TOP10 ne gagne pas de façon robuste et sa couverture 2026 est insuffisante.
L'échec est limité à cette adaptation et à ce plafond, pas à toutes les
méthodes professionnelles. Aucun seuil n'est retouché pour embellir le bilan.

## Limites avant toute utilisation réelle

La PCA n'utilise pas le secteur attribué à un titre, mais la comparaison reste
limitée à l'univers sectoriel retenu et son mapping actuel **non PIT**.
Les ETF sont des proxies de grandes capitalisations, imparfaits pour les
small caps et ADR. Le calendrier des données et les prix ajustés ne prouvent
pas, à eux seuls, leur disponibilité historique exacte à l'heure de décision.

Cashflows de dividendes, locates, financement/marge réels, capital disponible,
quantités entières et exécution multi-jambes ne sont pas certifiés ici.
Une moyenne de panier positive ne prouverait pas une précision D1/D10 ou un
rendement annuel exploitable. Une PCA complète des actions n'est pas testée.

## Artefacts et reproduction

`artifacts/research/us_pca_etf_residual_reversion/20261019-v1/` contient le
protocole, les empreintes, bases PCA, scores, coefficients de couverture,
candidats y compris inconnus, prix des jambes et bilans.

```powershell
python -m scripts.research.us_pca_etf_residual_reversion --phase prepare --output <nouveau-dossier>
python -m scripts.research.us_pca_etf_residual_reversion --phase build --output <même-dossier>
python -m scripts.research.us_pca_etf_residual_reversion --phase summarize --output <même-dossier>
python -m scripts.research.us_pca_etf_residual_reversion_audit --output <même-dossier>
python -m scripts.research.us_pca_etf_reversion_diagnostics --output <même-dossier>
```

Suivi : `progress.json` pour le replay, `audit-progress.json` pour les contrôles.
Ne pas lancer deux instances sur le même dossier. Le rapport achevé est
immuable. L'audit scalaire par seconde implémentation du même assistant n'est
pas une revue humaine indépendante.
