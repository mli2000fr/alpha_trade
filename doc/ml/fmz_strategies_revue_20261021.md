# FMZ : pistes utiles pour Alpha Trade et limites des exemples

Date : 21 octobre 2026. Statut : **REVUE DOCUMENTAIRE / AUCUN BACKTEST LANCÉ**.

> **Suite demandée par l'utilisateur : lecture du texte utile et du code des
> 1 000 fichiers terminée.** La sélection actualisée, contenant uniquement les pistes à tenter,
> se trouve dans [fmz_pistes_a_tester.md](fmz_pistes_a_tester.md).
> Le présent document conserve le bilan du premier criblage et des24lectures
> ciblées ; les compteurs de ce premier criblage restent historiques.
> Mise à jour du suivi au 22 octobre : les 1 000 documents du périmètre sont
> examinés, jusqu'à The-Bollinger-Band inclus. Sept hypothèses retenues à la
> clôture de lecture ; aucune supplémentaire après la tranche 901–1000.
> Depuis, [P01](oracle_compression_p01_bilan_20261022.md) et
> [P02](oracle_partial_p02_bilan_20261022.md),
> [P06](oracle_gain_lock_p06_bilan_20261022.md) et
> [P05](oracle_low_channel_p05_bilan_20261022.md) et
> [P03](oracle_retest_p03_bilan_20261022.md) ont été testées et non confirmées
> transversalement. [P04](oracle_dual_thrust_p04_bilan_20261022.md) est testée,
> mais son effectif est insuffisant pour conclure.
> [P07](oracle_rejection_p07_bilan_20261022.md) est clôturée au contrôle de
> fréquence : zéro motif sur112occasions couvertes, **aucun backtest économique**.
> Les sept hypothèses sont traitées, aucune promotion ; pas sept preuves
> d'inefficacité universelle. Ce n'est pas la
> lecture des 5 807 Markdown ni une promotion de stratégie.
> Le 708 est le README/index, pas une stratégie ; ses 5 810 liens ne sont pas
> autant de pages lues. Exemples techniques inclus, images non certifiées.

## Conclusion du premier criblage — historique, sélection actuelle dans le lien ci-dessus

Deux concepts méritent un protocole distinct, pas une intégration immédiate :

1. **Compression puis expansion** : parmi les candidats Oracle, attendre la
   sortie d'une consolidation avant la cassure, plutôt qu'accepter toute
   cassure du plus haut précédent.
2. **Sortie partielle** : vendre une fraction après un premier gain, conserver
   un solde sous stop dur et trailing. C'est différent du renforcement gagnant
   et du TP qui ferme toute la position.

Ce sont des hypothèses, **pas deux avantages démontrés**. Elles portent surtout
sur la chronologie d'entrée/sortie. Rien dans cette revue ne démontre que la
direction D1/D10 de l'Oracle serait désormais résolue.

Volume/VWAP, KAMA et bornes intraday fournissent des variantes secondaires.
Ils ne constituent pas des informations nouvelles simplement parce qu'un
autre nom de stratégie les combine.

## Périmètre du premier criblage — historique

Source : [dépôt public fmzquant/strategies](https://github.com/fmzquant/strategies/tree/master).

- Commit figé : `7853bb2bf262c4567ac238d3552d97f0e50cb801`.
- Dépôt : 5 807 fichiers Markdown à la racine dans ce snapshot.
- Plage demandée : **1 000 fichiers**, bornes incluses, du premier `1-2-3-…`
  à `The-Bollinger-Band-Automated-Trading-Strategy.md`.
- L'estimation initiale 1 025 utilisait le tri culturel de PowerShell ; le
  résultat final utilise l'ordre ordinal des noms, conforme au classement Git.
- Arbre GitHub complet obtenu, indicateur de troncature faux. Le listing Web
  limité à 1 000 fichiers ne suffit pas à inventorier tout le dépôt.
- **1 000 contenus intégraux archivés et empreintes Git vérifiées** : 9 948 027
  octets, 212 795 lignes. Aucun téléchargement en échec.
- Criblage automatique sur ces 1 000 contenus, puis **lecture ciblée du code
  de 24 fichiers** : entrées, sorties, disponibilité des variables, protections,
  cohérence avec le titre et transposition à Alpha Trade.
- Ce n'est **pas une revue manuelle ligne par ligne des 1 000 implémentations**,
  ni une compilation PineScript/FMZ, ni une validation des graphiques/images.
  À ce premier stade, les 976 autres fichiers étaient au niveau du criblage
  documentaire. La lecture séquentielle ultérieure atteint désormais le 1 000 ;
  son checkpoint distinct fait foi, pas ce compteur historique de 24 sources.
- Les liens secondaires FMZ/TradingView et images ne sont pas tous audités.
  La demande est traitée sur les documents GitHub de la plage indiquée.

L'inventaire donne une ligne pour chaque fichier, le lien au commit figé,
les familles détectées, les alertes textuelles et les notes des 24 revues :

- [Inventaire des 1 000 fichiers](../../artifacts/research/fmz_strategy_review/20261021-v1/index.md).
- [Rapport et compteurs](../../artifacts/research/fmz_strategy_review/20261021-v1/report.json).
- [Résultats individuels et empreintes](../../artifacts/research/fmz_strategy_review/20261021-v1/screening.json).
- [Annotations des 24 lectures ciblées](sources/fmz_revue_ciblee_20261021.json).

## 1. Compression puis expansion : premier candidat

Sources examinées :
[BB/Keltner](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/BB-Keltner-Squeeze%E4%BA%A4%E6%98%93%E7%AD%96%E7%95%A5BB-Keltner-Squeeze-Trading-Strategy.md),
[Squeeze Momentum](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Squeeze-Momentum-Indicator.md),
[variante sur retournement](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Squeeze-Momentum-on-Reversal-Strategy.md).

### Ce que l'on peut en tirer

L'Oracle choisit un titre susceptible de connaître une grande excursion ; il
ne dit pas si l'entrée doit avoir lieu immédiatement. Une séquence
**consolidation → sortie de compression → cassure confirmée** est une hypothèse
de timing différente de « le titre est déjà en hausse depuis plusieurs jours ».

Une volatilité daily élevée et une compression intraday locale peuvent
coexister : on ne remplace donc pas mécaniquement l'ATR par un classement des
titres les moins volatils.

### Pourquoi ne pas copier les scripts

- Le BB/Keltner examiné ne contrôle qu'une borne pour définir son état.
- Dans les deux Squeeze Momentum, le multiplicateur de largeur BB déclaré
  n'est pas celui utilisé dans le calcul.
- Les ordres de ces deux variantes se fondent sur l'inflexion de l'oscillateur,
  **sans exiger l'état de compression calculé**.
- L'un mélange déclaration d'indicateur et appels d'ordres ; ce n'est pas un
  composant exécutable qualifié pour notre infrastructure.

### Expérience éventuelle, à figer avant calcul

Comparer la cassure Winner témoin avec la même entrée exigeant une compression
bilatérale antérieure puis sa sortie. Exemples de paramètres de départ, **pas
un optimum découvert** : BB 20 périodes/2 écarts-types, Keltner 20/1,5 ATR,
observation en bougies régulières closes de cinq minutes. La durée minimale
de compression, le délai entre sa sortie et la cassure et le reset de séance
restent à fixer dans le protocole ; ne pas les chercher sur les pertes connues.

Oracle, univers, capital et protections doivent rester identiques. Ajouter
ni VWAP ni filtre macro dans cette première comparaison. Mesurer nombre
d'entrées, délai, excursion encore disponible et PnL net, pas seulement une
précision directionnelle sur le mouvement déjà consommé. Séparer LONG/SHORT ;
pas de SHORT économique qualifié sans disponibilité et coûts d'emprunt.

## 2. Prendre une partie du gain, laisser courir le reste

Le script **AlphaTrend + KAMA + Risk Management** contient une fermeture de
50 % à un seuil de gain, puis conserve une partie de la position. Son lien,
son empreinte et le texte exact du code sont dans l'inventaire et l'annotation
`AlphaTrend与KAMA`.

L'idée pertinente pour Alpha Trade n'est pas son croisement KAMA/AlphaTrend :
c'est la séparation **gain partiellement réalisé / potentiel conservé**.

Proposition de contraste borné, non lancé :

- Témoin : entrée Winner, SL7/TR15/H20, sans TP, avec le contrat actuel.
- Variante : mêmes entrées et quantités ; vendre 50 % à +10 %, laisser le
  solde sous les protections existantes et l'échéance open21.
- Conserver un stop dur ; ne jamais l'élargir après une perte. Pas de remise
  automatique au prix d'entrée, de réentrée ou de renforcement ajouté au test.
- Ajouter les frais de sortie, les arrondis/actions entières et le cash libéré
  au moteur. Le script source ne reproduit pas notre chronologie de fills.

Ces valeurs servent à définir une seule comparaison intelligible, pas à
recommander des paramètres de production. Une sortie partielle peut améliorer
la régularité **ou réduire le rendement** en coupant les rares très grands
gagnants : la concentration observée dans nos recherches rend cette réserve
particulièrement importante.

La grille antérieure teste des TP fermant la position entière. Cela ne prouve
pas le résultat d'une liquidation partielle, et ne justifie pas de relancer
toutes les grilles avant cette comparaison simple.

## 3. Pistes secondaires et recouvrement avec les expériences existantes

| Famille | Lecture pour Alpha Trade | Priorité actuelle |
|---|---|---|
| VWAP, PVT, MFI, volume | Une confirmation locale de cassure est testable, mais prix/volume et VWAP existent déjà. Un volume OHLCV élevé ne prouve pas des achats institutionnels ni le sens des agressions. | Secondaire, pas nouvelle information prouvée. |
| KAMA / rapport d'efficacité | Déplacement net divisé par somme des mouvements : distinguer trajectoire régulière et bruit, pas déterminer le sens à lui seul. | Secondaire ; ne pas ressusciter automatiquement le filtre de tendance abandonné. |
| Opening Range / bornes de séance | Des bornes initiales remplacent le plus haut de veille ; la séance et l'heure deviennent partie du signal. | Très proche d'E20 et des cassures déjà testées ; pas priorité sans différence explicite. |
| Donchian / Darvas | Autres définitions de bornes et stops de structure. | Variantes de notre famille cassure ; pas alpha neuf établi. |
| Retour à la moyenne RSI/Bollinger/Keltner | Acheter un excès puis attendre un retour. | Nos tests de retour à la moyenne/pullback sont négatifs ou non confirmés ; pas relance automatique. |
| Entropie / noms « IA » / « Black-Scholes » | Le nom ne démontre ni apprentissage, ni information supplémentaire, ni asymétrie exploitable. | Pas prioritaire sans contrat statistique clair. |
| Order flow/HFT | Requiert transactions avec sens d'agression et parfois carnet/latence. | Les bougies 5m ne suffisent pas ; autre infrastructure/horizon. |

Rapprochements locaux vérifiés :

- `modelFactory/features.py` contient déjà `close_to_vwap`, `volume_ratio_20`,
  `vol_ratio_20_60`, `atr_ratio_5_20`, distances et pentes de moyennes.
- [E20-C volume/VWAP](oracle_opening_volume_ablation_e20c.md) : avantage
  incrémental générique non confirmé ; E20-D rejette la politique symétrique.
- [Cassure TOP10 H10](oracle_top10_cassure_intraday_tp10_sl5_20261019.md) :
  résultat négatif. Ne pas présenter une nouvelle durée d'indicateur comme
  une confirmation de ce test.
- [Tendance persistante](oracle_tendance_persistante_20261021.md) : abandonnée
  à la demande de l'utilisateur. La revue ne l'active ni ne la relance.
- [Retour à la moyenne](retour_moyenne_intraday_20261020.md) et
  [pullback E10](oracle_pullback_long.md) : anciens résultats conservés.
- [Renforcement gagnant](oracle_portefeuille_renforcement_gagnant_20261020.md) :
  pas avantage stable contre demi-position témoin. Une prise de bénéfice
  partielle est une autre intervention, pas une preuve contraire.

## 4. Anomalies concrètes : ne pas importer le code tel quel

### Premier fichier 1-2-3 + EMA/MACD

La description demande une quatrième clôture au-delà de la troisième ; le
code la compare à la première bougie du motif. Pas de stop dur et quantités
fixes. C'est une recette de signal à auditer, pas une preuve de direction
supérieure à celle des modèles déjà testés.

### Donchian « no repaint »

Les calculs utilisent `lookahead_on` sur des données d'autres temporalités.
Selon la temporalité et le décalage, cela peut introduire des valeurs futures ;
le libellé « no repaint » ne suffit pas. Plus directement, les conditions de
filtrage calculées ne sont pas utilisées dans le bloc final qui envoie les
ordres. Il peut donc afficher des filtres sans trader selon ces filtres.
[Code source](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Donchian-Breakout-no-repaint.md).

`lookahead_on` n'est pas automatiquement une preuve de fuite : une expression
décalée et le contexte doivent être contrôlés. Voir la
[documentation TradingView sur les données multi-timeframes](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/).

### Dernier fichier Bollinger automatisé

Le code ajoute après baisse sous le prix moyen, avec une taille proportionnelle
à la position déjà détenue. Le facteur 1,55 peut amplifier rapidement l'exposition.
Ce n'est **pas** le renforcement d'une position gagnante de Winner. Le stop
sur prix moyen n'offre pas un budget de risque initial invariant. Déclaration
de stratégie commentée et déclenchements de sortie sur clôture : pas parité
avec nos protections. **Écarté en l'état.**
[Source](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/The-Bollinger-Band-Automated-Trading-Strategy.md).

### Autres écarts observés

- `Price-Action-Pyramiding-5…` : le « 3 % stop » du titre sert de condition
  d'achat après baisse ; aucun stop protecteur n'est transmis dans la sortie.
- `Keltner-Channel-Pullback…` : une branche nommée vente entre en LONG.
- `AI-Driven-Dynamic-Volatility…` : règles ATR/EMA/VWAP, pas modèle entraîné.
  La taille calculée n'a pas la relation simple à la volatilité annoncée.
- `MORNING-CANDLE…` : un `stop` transmis à une entrée est un déclencheur
  d'entrée, pas le stop-loss de la position.
- Plusieurs exemples réécrivent le SL depuis chaque clôture : le stop peut
  reculer. Notre contrat interdit de desserrer le stop initial.

Ces constats sont des lectures statiques du code fourni, pas des résultats
de compilation, ni un diagnostic de toutes les variantes de ces familles.

## 5. Bilan du criblage intégral

Les catégories ne sont pas exclusives. Dans les noms de fichiers : 264
correspondances tendance, 245 momentum/oscillateurs, 90 cassures, 68 gestion
de sortie, 68 retour à la moyenne/Bollinger, 11 volume/VWAP, trois compression.
Ce sont des comptes de correspondances textuelles, pas des classifications
expertes exhaustives ni des stratégies indépendantes.

Sur les contenus complets :

- 878 mentionnent les marqueurs de places/paires crypto recherchés : cela
  ne signifie pas que toutes leur logique sont incompatibles avec les actions.
- 16 contiennent le marqueur explicite `lookahead_on` ; 97 un appel de données
  multi-timeframes, 44 un marqueur de pivot/zigzag. Chaque usage doit être
  qualifié avant de conclure à une fuite.
- 35 contiennent du vocabulaire d'averaging/grille/martingale : la présence
  dans une réserve de la description ne prouve pas que le code l'exécute.
- 140 contiennent une déclaration de commission ou slippage recherchée :
  cela ne valide pas les coûts. Son absence ne prouve pas que FMZ n'a pas
  appliqué de frais externes au script.
- 279 contiennent une mention de licence recherchée. Ce décompte ne constitue
  pas une autorisation générale de copie ; chaque source et ses conditions
  doivent être qualifiées avant réutilisation. Aucun code distant exécuté.

Les captures de rendement ne constituent pas des backtests vérifiés sur
Alpha Trade. Les crypto-futures 24/7 n'ont pas les mêmes séances, gaps,
emprunts, arrondis, levier, univers ou coût d'exécution que nos actions US.

## 6. Suite recommandée, sans lancement implicite

**Premier choix : une seule expérience compression → cassure**, avec la
politique Winner actuelle comme témoin. La sortie partielle vient ensuite,
indépendamment, si l'on souhaite étudier la restitution des excursions.

Avant tout calcul économique :

1. Couverture réelle de `stock_bars_intraday` SIP, trous et archives vides
   explicités ; téléchargement en cours non interrompu par cette revue.
2. Scores Oracle réellement OOS par période. Un modèle entraîné avec des
   données récentes ne peut pas sélectionner causalement les titres de 2016.
3. Comparaison chronologique sans sélection par couverture future, pas seulement
   les 213 anciennes campagnes à fenêtres complètes.
4. Signaux sur barres closes, entrée au prochain instant exécutable ; pas
   exécution fictive au prix qui a servi à confirmer le signal.
5. Capital partagé, frais, risque et levier identiques ; gaps, actions sur
   titres, stocks disponibles et protections chronologiques conservés.
6. Choix limité au développement puis validation ultérieure ; 2025/2026 ont
   déjà été beaucoup consultées, ce ne sont plus des périodes vierges.

Aucun nouveau signal, entraînement, stratégie de production, ordre, appel
LLM, écriture SQL ou réglage de batch n'a été lancé. Seuls des documents publics
GitHub et une documentation TradingView ont été consultés. Le criblage et ses
tests s'exécutent hors des téléchargements Alpaca.

## Reproductibilité technique

Outil : `scripts/research/fmz_repository_review.py`, huit tests ciblés.
Il vérifie l'arbre non tronqué, les deux bornes et les empreintes Git de chaque
fichier, conserve les sources brutes et distingue annotations ciblées et
criblage textuel. Aucun module téléchargé n'est importé ou exécuté.

```powershell
python -u -m scripts.research.fmz_repository_review `
  --output artifacts/research/fmz_strategy_review/20261021-v1 `
  --targeted-review doc/ml/sources/fmz_revue_ciblee_20261021.json
```

Le snapshot existant est relu localement. Un nouveau dossier résoudrait le
master du moment : noter son commit avant toute comparaison. Les limites
de ce travail restent une revue documentaire et 24 lectures de code ciblées,
pas une certification de 1 000 stratégies.
