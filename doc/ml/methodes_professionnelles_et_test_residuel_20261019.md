# Méthodes professionnelles et premier essai avec Alpha Trade

## Objet et périmètre

GO utilisateur : rechercher comment travaillent les professionnels puis tester
une approche avec les données de l'application. Étude bornée et hors production,
sur archives locales, sans achat, téléchargement de données fournisseur, appel
LLM, écriture SQL ou ordre. Les historiques déjà explorés ne deviennent pas un
nouvel échantillon vierge parce que l'hypothèse change.

La consultation des publications ci-dessous est une recherche documentaire,
pas une alimentation de nouvelles données de marché ni une garantie de droits
de redistribution des documents.

## Ce que les sources permettent réellement de retenir

| Famille | Principe documenté | Situation dans Alpha Trade |
|---|---|---|
| Tendance et diversification | Combiner des moteurs et horizons différents, avec contrôle des risques et de l'exécution | De nombreux signaux prix/régime et règles de sortie ont déjà été étudiés ; un nouveau nom ne justifie pas de les retester comme inédits |
| Momentum résiduel | Séparer la performance propre d'un titre de sa composante systématique | E17/E18 ont déjà étudié le momentum résiduel H120 et son attribution ; pas de nouvelle promesse de cette famille |
| Arbitrage statistique de résidus | Détecter un déséquilibre relatif et couvrir le facteur commun ; chercher sa normalisation, pas un gagnant absolu | **Premier essai choisi ici**, adaptation mono-facteur SPY avec modèle de retour à la moyenne et suivi quotidien |
| Événementiel et anticipations | Exploiter une surprise ou une révision disponible à la décision | Les historiques PIT de consensus ne sont pas reconstituables en inventant les états passés ; leur collecte prospective reste distincte |

Sources primaires consultées le 19 octobre 2026 :

- [Man AHL — démarche d'investissement](https://www.man.com/ahl) : décrit une
  combinaison de stratégies et insiste sur diversification, risque et exécution.
  Cela ne publie pas les modèles ni les performances reproductibles d'un fonds
  accessible avec nos seules données.
- [Robeco — momentum résiduel](https://www.robeco.com/en-int/insights/2013/10/robecos-residual-momentum-less-risky-and-more-sustainable) : distingue rendement
  propre et rendement systématique. **Momentum** et **retour à la moyenne**
  restent des hypothèses différentes, pas interchangeables.
- [Avellaneda et Lee — Statistical Arbitrage in the U.S. Equities Market,
  version de juin 2009](https://math.nyu.edu/~avellane/AvellanedaLeeStatArb20090616.pdf) :
  examine des résidus contre facteurs PCA ou ETF sectoriels et des règles de
  retour à la moyenne estimées sur une fenêtre glissante. La performance publiée
  se dégrade sur une partie de leur propre période ; elle ne prédit pas la nôtre.
- [AQR — Trading Costs of Asset Pricing Anomalies](https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies) : montre que les coûts et la capacité
  peuvent absorber les rendements de retournement court terme. C'est une raison
  de tester les coûts, pas une preuve que notre essai doit réussir ou échouer.

Les sources professionnelles sont aussi des publications de leurs auteurs ou
gérants, pas une certification indépendante de résultats futurs.

## Adaptation choisie : ce n'est pas une réplication exacte

Le cache qualifié de cette recherche contient SPY, mais pas les onze ETF sectoriels.
Nous utilisons donc **un facteur marché SPY**, et non un substitut silencieux à
toute la structure sectorielle/PCA. Les limites sont inscrites avant calcul dans
`protocol.json` :

- pas d'ETF sectoriels, de PCA ni de volumes en « temps de trading » ;
- pas de filtre de capitalisation historique fiable équivalent à celui des auteurs ;
- couverture SPY fixée à l'entrée, sans rééquilibrage quotidien ni netting entre titres ;
- score non recentré sur la moyenne de l'univers ;
- sortie symétrique à ±0,5, limite dix séances et seuil de risque quotidien ajoutés.

Une issue négative réfuterait **cette adaptation sur nos données**, pas
l'arbitrage statistique professionnel dans son ensemble. Une issue positive ne
prouverait pas la reproductibilité des résultats d'un gérant.

### Question différente de D1/D10

Il s'agit d'évaluer un rendement **relatif couvert**, pas de prédire qu'un titre
terminera dans le décile mondial D10 ou D1. Un titre peut baisser et produire
un résultat positif relativement au marché ; inversement, une hausse absolue
peut perdre une fois sa couverture prise en compte.

## Données et causalité

- Univers : fichier actuel `config/univers_batch/univers_filtred_tradable.txt`,
  **1 790 symboles**, figé par empreinte, sans ajouter de titre après résultat.
- Prix : copie normalisée de recherche
  `artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet`,
  2023–septembre 2026. Les réserves DD/Qnity et TOELY restent en place.
- Deux périmètres annoncés avant résultat : univers tradable entier et
  **dix premiers rangs Oracle amplitude H10 à J**. Ce sont les mêmes scores
  annuels de recherche H10 déjà archivés, pas un nouvel Oracle ni une sélection
  des dix meilleurs rendements futurs.
- Signaux : 2024, 2025 et 2026 jusqu'au **1er septembre 2026** ; prix de suivi
  jusqu'au 30 septembre. Les informations de 2023 servent à l'historique glissant.
- Seuils et fenêtres uniques, choisis avant le replay, aucun concours de réglages
  gagnants sur 2025/2026.

Les OHLC sont mis sur la base `adj_close/close` du cache existant, sans forward-fill.
Barres artificielles, volumes non positifs, prix incohérents, changements de source,
d'identité ou d'ajustement invalident les fenêtres correspondantes. Les réserves
du cache sont héritées, sans nouvelle correction de prix ou suppression globale
de symbole.

L'univers est un snapshot actuel : les radiés et anciennes appartenances ne sont
pas intégralement reconstruits. Le cache daily normalisé n'est pas une certification
indépendante de tous les cours, dividendes et opérations sur titres.

## Règle exécutable de l'essai

### Calcul après la clôture J

1. Prendre **60 rendements quotidiens**, nécessitant 61 clôtures valides.
2. Estimer par OLS avec constante la composante liée à SPY.
3. Cumuler les résidus, puis estimer leur dynamique AR(1).
4. Construire un score d'écart à l'équilibre en unités de volatilité du résidu.
5. Retenir seulement un modèle numériquement admissible : bêta dans ]0 ; 3],
   coefficient AR dans ]0 ; exp(−1/30)[, écart-type d'équilibre positif.
6. Filtre causal de liquidité : close stocké ≥5 $ et moyenne sur vingt séances
   du produit close×volume ≥5 M$. C'est un **proxy d'archive**, pas une preuve
   indépendante de la capitalisation ou du spread historique.

Toutes les fenêtres s'arrêtent à J. Des tests de préfixe vérifient qu'altérer
les observations ultérieures ne change pas les scores antérieurs.

### Entrée à l'open J+1

- Score <−1,25 : **LONG titre / SHORT SPY** pour couvrir son bêta estimé.
- Score >+1,25 : **SHORT titre / LONG SPY**.
- Sinon, aucune entrée.

Avec un bêta β, les poids sont ±1/(1+β) sur le titre et ∓β/(1+β) sur SPY.
L'exposition brute initiale de chaque paire est donc **une unité**, pas une unité
de titre plus une couverture gratuite. Les quantités et le bêta restent fixés
pendant cette occasion. La neutralité estimée à l'entrée n'est pas garantie
pendant toute la détention.

### Observation quotidienne et sortie à l'open suivant

Après une clôture, sortir simultanément les deux jambes au prochain open si :

- LONG : score revenu au moins à −0,5 ; SHORT : score revenu au plus à +0,5 ;
- ou modèle de suivi devenu non admissible ;
- ou perte brute marquée de la paire ≤−5 % de son exposition brute initiale.

À défaut, sortir après dix séances complètes de détention, à l'open J+11.
Le seuil de risque est **observé en clôture**, pas un SL intraday garanti à5 %.
Un gap au prochain open peut l'aggraver. Aucun cours simultané titre/SPY
intrabar n'est inventé, aucun TP ni trailing ajouté.

## Comptabilité et comparaisons

- Frais hypothétiques : **8 bps de chaque montant exécuté**, aux deux jambes
  à l'entrée et aux deux jambes à la sortie, avec leurs montants réels relatifs.
- Stress figé : **20 bps par montant exécuté**, pas un recalibrage après pertes.
- Emprunt hypothétique : 0,3 % annuel de la jambe short, jours calendaires/365.
  Cela ne prouve ni un locate, ni un tarif historique, ni le coût réel des titres
  difficiles à emprunter.
- Pas d'intérêt sur les liquidités, de rebate, de financement à levier ni de
  traitement indépendant certifié des cashflows de dividendes.

Le résultat est rapporté **par unité brute initiale de paire**. Ce n'est pas un
rendement annuel de capital, un portefeuille à4000 €, une marge broker réelle
ou un ordre exécutable avec toutes les contraintes de l'application.

Contrôles figés sur les mêmes entrées :

1. conserver la même paire jusqu'à l'échéance dix séances ;
2. inverser les deux jambes, à la même sortie : témoin de signe, **pas une
   stratégie autonome**, car l'heure de sortie vient de la politique primaire ;
3. titre sans couverture à la même sortie : témoin de composante marché,
   **pas un risque identique** à la paire.

Dans les fichiers, `side` désigne le côté du titre de la politique primaire,
`executed_side` le sens effectivement pris par chaque contrôle.

### Chevauchement et données manquantes

Le bilan principal utilise des épisodes sans chevauchement par symbole, tous
sens confondus, sur la fenêtre maximale entière. La première occasion bloque
le symbole jusqu'à J+11 **avant** de vérifier la qualité future ; même une
occasion finalement non qualifiable reste bloquante. Pas de remplacement ni de
recyclage de ses données manquantes vers une occasion ultérieure plus favorable.

Toutes les séances titre/SPY de J à J+11 doivent être valides pour évaluer une
occasion. Le bilan tous signaux est secondaire. Un bootstrap par blocs de vingt
séances, partagé par les titres, limite l'illusion de multiplication d'occasions.
Il est présenté par trade et à poids égal par date, sans prétendre supprimer
toutes les dépendances ou le biais d'univers survivant.

### Critères annoncés avant résultat

Pour un même périmètre, politique primaire et épisodes sans chevauchement :
au moins100 occasions en2025 et2026, intervalle95 % entièrement positif dans
les deux années, pour la moyenne par occasion **et** par date, moyenne sous
stress positive, et moins de50 % des contributions positives portées par les
vingt meilleurs gagnants. Pas de choix d'une seule année favorable après lecture.

Même si ces critères passaient, l'autorisation resterait limitée à la recherche :
les données et périodes déjà observées ne permettent pas une promotion directe.

## Résultats et audit

**TERMINÉ — `NO_ROBUST_RESIDUAL_REVERSION`.** Les critères figés ne passent
dans aucun des deux périmètres. Aucune promotion ni changement de production.

### Couverture

Les 1 790 symboles ont une archive de prix. Le moteur a identifié **199 242
occasions de signal** sur les deux périmètres, dont **199 051 qualifiées** pour
le suivi futur. Ce ne sont pas des ordres ni des positions effectivement ouvertes.

| Périmètre | Année | Signaux avec chemin qualifié | Signaux non qualifiés |
|---|---:|---:|---:|
| Univers complet | 2024 | 76 704 | 1 |
| Univers complet | 2025 | 77 382 | 2 |
| Univers complet | 2026 | 44 134 | 188 |
| TOP10 H10 | 2024 | 451 | 0 |
| TOP10 H10 | 2025 | 274 | 0 |
| TOP10 H10 | 2026 | 106 | 0 |

En 2026, les188 inconnus de l'univers complet comprennent185 fenêtres avec
prix absent/invalide et trois fenêtres réservées sur la base de prix. L'adhésion
sans chevauchement a été arrêtée **avant** cette inspection future ; 33 épisodes
primaires restent non évaluables, sans remplacement (un en2025,32 en2026).

### Bilan principal : épisodes sans chevauchement

Rendement de chaque paire rapporté à son **exposition brute initiale totale**,
frais et emprunt hypothétiques déduits. Pas un rendement annuel de capital.

| Périmètre | Année | Occasions | Gagnantes nettes | Net moyen/occasion | Net sous stress20bps |
|---|---:|---:|---:|---:|---:|
| Univers complet | 2024 | 14 913 | 52,87 % | **−0,037 %** | −0,278 % |
| Univers complet | 2025 | 14 734 | 53,83 % | **−0,005 %** | −0,246 % |
| Univers complet | 2026 | 8 668 | 51,77 % | **−0,177 %** | −0,417 % |
| TOP10 H10 | 2024 | 153 | 52,94 % | **+0,598 %** | +0,356 % |
| TOP10 H10 | 2025 | 87 | 59,77 % | **+0,683 %** | +0,441 % |
| TOP10 H10 | 2026 | 47 | 53,19 % | **−0,169 %** | −0,411 % |

Intervalles95 % sur le net moyen :

| Périmètre | 2024 | 2025 | 2026 |
|---|---|---|---|
| Univers complet | [−0,146 ; +0,078] % | [−0,145 ; +0,142] % | [−0,434 ; +0,134] % |
| TOP10 H10 | [−0,099 ; +1,297] % | [−0,444 ; +1,949] % | [−0,884 ; +0,717] % |

Les moyennes à poids égal par date sont également archivées. Elles ne lèvent
pas l'incertitude et restent négatives pour l'univers complet dans les trois
années. TOP10 : effectifs faibles, concentration des gains élevée, et pas de
confirmation2026. Les vingt meilleurs gagnants représentent59,08/73,95/95,12 %
des contributions positives TOP10 en2024/2025/2026. L'univers complet est moins
concentré, mais sa moyenne nette n'est pas positive.

### Ce qui explique l'échec de la version testée

1. **Une moyenne brute faible n'est pas un avantage net.** Sur l'univers complet,
   les moyennes brutes sont **+0,128/+0,159/−0,012 %** par occasion. Les coûts
   moyens sont proches de0,160 % plus environ0,004 % d'emprunt. En2024–2025,
   ils absorbent la moyenne brute ; en2026, elle est déjà légèrement négative.
   Ces petites moyennes brutes ne constituent pas davantage une preuve statistique.
2. **Plus de50 % de gagnants ne suffit pas.** En2025, les gagnants de l'univers
   complet rapportent en moyenne+2,017 %, les perdants coûtent−2,363 %.
   Le profit factor reste environ0,995, malgré53,83 % de gagnants.
3. **Le suivi quotidien n'améliore pas systématiquement la détention fixe.**
   Le contrôle même paire jusqu'à dix séances donne−0,031/+0,038/−0,240 %
   sur l'univers complet et+0,738/+1,579/−0,275 % sur TOP10. Aucun profil
   ne devient transversalement validé ; on ne remplace pas automatiquement la
   politique primaire par le contrôle2025 le plus favorable.
4. **La couverture de marché ne neutralise pas le risque propre d'un émetteur.**
   Une opération d'entreprise ou une nouvelle importante peut rendre le retour
   à la moyenne inapproprié. Un modèle statistique admissible n'est pas une
   garantie économique de convergence.

Le contrôle sans couverture à la même sortie vaut+0,338/−0,082/−0,316 % sur
l'univers complet et+2,312/+1,405/−0,310 % sur TOP10. Il a une exposition et un
risque différents : ces moyennes ne démontrent pas que retirer la couverture
crée de l'alpha. Le contrôle de sens inverse n'apporte pas de solution stable.

### Diagnostic LONG TOP10 : ne pas le transformer en résultat validé

La sous-partie LONG titre / SHORT SPY est positive dans les trois années :
**+0,527/+1,600/+0,341 %**, mais sur **106/49/23 occasions** seulement.
Ses intervalles2024 et2026 incluent zéro ; celui de2026 est
**[−0,730 ; +1,327] %**. En2026, il n'y a que14 titres représentés.

Le sens LONG a été ventilé dans le bilan prévu, mais le choisir maintenant
comme nouveau candidat primaire serait une décision après résultats. Il ne
faut donc pas présenter ces chiffres comme une capacité fiable à reconnaître
D10, ni comme une stratégie LONG exploitable. Aucune sélection de titres,
de mois ou de nouveaux seuils n'a été ajoutée après lecture de ce diagnostic.

### Risque et recoupement de prix, sans supprimer les pertes

Une perte de5 % observée au close n'est pas un stop garanti. Exemples2026 de
l'univers complet, conservés dans le bilan :

| Titre / sens | Entrée | Prix titre entrée | Sortie | Prix titre sortie | Net de la paire |
|---|---|---:|---|---:|---:|
| CRNX SHORT | 6 juillet | 42,03 $ | 8 juillet | 83,52 $ | **−65,80 %** |
| KFRC SHORT | 22 avril | 33,28 $ | 29 avril | 46,07 $ | **−36,64 %** |
| BAND SHORT | 20 avril | 22,66 $ | 1er mai | 37,66 $ | **−27,83 %** |
| DKS LONG | 21 août | 181,25 $ | 26 août | 121,87 $ | **−24,28 %** |

Les huit opens de ces quatre exemples correspondent aux opens présents dans
le cache SIP quotidien déjà disponible :
`artifacts/research/us_sip_daily_universe/audit-20260101-20260930-20261011-v1/sip-bars.parquet`.
Ce recoupement post-calcul n'a modifié ni la sélection ni les rendements, et
n'est pas une qualification exhaustive indépendante des identités et cashflows.
Il ne justifie pas de plafonner ces pertes au seuil ou de retirer les symboles.

### Vérifications terminées

- **115 tests** passent dans la sélection de non-régression lancée,
  dont19 nouveaux pour cette adaptation ; le seuil global de couverture du
  projet est neutralisé pour ce groupe ciblé, pas déclaré satisfait.
- **796 204 lignes** de stratégie/contrôles revérifiées : prix d'entrée/sortie,
  côté exécuté, coûts des deux jambes, emprunt, sortie et échéance.
- **5 370 estimations OLS/OU** recoupées avec un calcul scalaire distinct.
- **58 contrôles de préfixe** réels, en plus des tests de mutation du futur.
- Audit : **`PASS_EXPLORATORY_ADAPTATION_ONLY`**. Il valide les contrôles
  techniques, pas la rentabilité. Seconde implémentation par le même assistant,
  pas une seconde revue humaine indépendante.

Les sources, paramètres, scores et prix sont scellés par empreintes. Aucune
donnée SQL, aucun modèle de production, batch, compte ou ordre modifié.

## Décision et portée pour Alpha Trade

**Ne pas intégrer cette règle en live/paper comme signal validé.** L'essai montre
notamment pourquoi il faut examiner rendement net, couverture et risque propre,
pas seulement un taux de réussite supérieur à50 %.

Cette version mono-facteur SPY n'a pas épuisé les méthodes professionnelles.
Une véritable étude sectorielle/PCA demanderait un protocole distinct, une
qualification de ses facteurs et de son univers, puis des coûts/exécutions
compatibles. Ce ne serait pas une simple activation d'un autre modèle Oracle.
Les résultats ci-dessus ne permettent pas de prédire qu'une telle étude réussirait.

La revue des publications et ce premier test sont clos ; pas d'optimisation
automatique supplémentaire après l'échec de la règle primaire.

### Suite autorisée le même jour : facteurs sectoriels

La vérification suivante a confirmé que les onze ETF étaient déjà présents
dans la **base**, même s'ils ne figuraient pas dans le **cache** de ce premier
essai. Un nouveau GO a ouvert une comparaison secteur/SPY à règles inchangées,
avec raccordements courants explicitement non PIT et exclusions conservatrices.
Voir [le protocole et les résultats sectoriels](facteurs_sectoriels_retour_moyenne_20261019.md).
Ce second run n'est pas une modification rétroactive des résultats SPY ci-dessus.
PCA reste une étape distincte, non exécutée dans ces deux essais.

## Reproduction

Code : `scripts/research/us_professional_residual_reversion.py` et
`scripts/research/us_professional_residual_reversion_audit.py`.
Tests : `tests/test_us_professional_residual_reversion.py`.
Artefacts : `artifacts/research/us_professional_residual_reversion/20261019-v1/`.

```powershell
python -m scripts.research.us_professional_residual_reversion --phase prepare --output <nouveau-dossier>
python -m scripts.research.us_professional_residual_reversion --phase build --output <même-dossier>
python -m scripts.research.us_professional_residual_reversion --phase summarize --output <même-dossier>
python -m scripts.research.us_professional_residual_reversion_audit --output <même-dossier>
```

Le calcul utilise uniquement les fichiers locaux scellés ; il ne doit pas être
confondu avec le lancement d'un nouveau batch, un entraînement ou une exécution.
