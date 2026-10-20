# Oracle parcours H20 — compte partagé et renforcement d'un gagnant

## Objet et portée

GO utilisateur du 20 octobre 2026 : confirmer le LONG simple H20 dans un
portefeuille à capital partagé, puis le comparer à un ajout sur une position
gagnante, sans augmenter le plafond **planifié par campagne**.

**Simulation de recherche séparée, pas parité complète avec PAPER/live.** Le
ledger natif fonctionne à la journée et refuse une nouvelle entrée sur un titre
déjà détenu. Il n'a pas été modifié. Ce simulateur conserve la chronologie des
barres de cinq minutes, un compte de trésorerie commun et des lots séparés.
Il n'applique pas les contrôles natifs secteurs/corrélations/régimes,
circuitbreakers ni le lifecycle complet d'un courtier.

L'hypothèse de pyramiding — augmenter une position déjà gagnante — est
différente d'une seconde tentative **après sortie**, étudiée dans
[les campagnes H5/H10/H15/H20](oracle_campagnes_h5_h10_h15_h20_20261020.md).
L'origine pédagogique est notamment la définition
[Interactive Brokers de pyramiding](https://www.interactivebrokers.com/campus/glossary-terms/pyramiding/),
pas une preuve de rentabilité ni une reproduction d'un fonds.

## Sources figées et biais de couverture

Tout est réutilisé hors ligne depuis le dossier scellé
`artifacts/research/us_oracle_campaign/20261020-v1`. Aucun nouvel appel API,
entraînement, appel LLM ou accès SQL n'est nécessaire.

- Oracle **PATH_H20 CatBoost OOS de recherche**, scores annuels archivés,
  TOP10 à J, pas le LightGBM de production et pas une prévision directionnelle.
- 6 690 lignes TOP10 initiales ; admission avant contrôle des prix, avec blocage
  vingt séances par titre commun à tous les bras : 673 campagnes.
- Cohorte qualifiée de vingt et une séances complètes J..J20 : **119 campagnes
  en 2025 et 94 en 2026**, 213 au total. Toutes ont un premier signal LONG
  observable, mais certaines entrées sont refusées par le portefeuille.
- **2024 non testable : aucune campagne intraday qualifiée.** Ce n'est pas un
  rendement nul et ce n'est pas une année silencieusement retirée d'un bilan.
- Couverture conditionnelle : 47,98 % et 55,29 % des campagnes admises en
  2025/26. Les autres restent inconnues, sans remplacement ni rendement zéro.
- Le contrôle exige toute la trajectoire de vingt séances, donc utilise une
  information future de **qualité de données**, pas un filtre réalisable tel
  quel à l'entrée. Cela crée un biais de sélection important. Ces résultats
  ne décrivent pas tout le TOP10 historique.
- Univers tradable actuel : biais de survivants. Données SIP historiques
  retraitées ; cohérence OHLC intraday/daily à une échelle constante, mais pas
  certification externe des prix, des bid/ask ou des exécutions.

Le protocole est écrit avant le calcul portefeuille ; les sources, candidats,
barres et calendriers sont hachés. Les anciennes colonnes de gain/perte ne
servent pas à sélectionner les entrées. 2025/26 ayant déjà été examinées,
ce n'est cependant **pas un nouveau holdout vierge**.

## Contrat de portefeuille

### Capital et priorité

- **4 000 USD initiaux**, un seul compte continu du 1er janvier 2025 au
  30 septembre 2026 ; pas de remise à 4 000 au changement d'année.
- LONG seulement, actions entières, aucun levier, trésorerie non négative.
- Huit titres maximum ; allocation par titre au moment d'un achat au plus
  25 % de l'equity avant frais de cet achat. Dérive de poids autorisée ensuite.
- Les stops/expirations connus à l'open passent avant les nouveaux achats.
  Les entrées initiales passent avant les ajouts. À heure identique : date
  du signal, rang Oracle, symbole, identifiant de campagne.
- Un titre détenu n'est pas acheté dans une autre campagne. Aucun remplacement
  par le onzième rang ; aucune recherche d'un prix ultérieur plus accessible
  après un refus de capital ou une quantité entière nulle.
- Un produit de vente **intrabar** ne finance pas un achat à l'open de cette
  même barre. Pour dimensionner les ordres, seules les ouvertures simultanées
  des titres détenus sont utilisées, jamais les high/close de la barre courante.

### Entrée et protections identiques

Premier nouveau franchissement LONG de chaque campagne : deux clôtures 5m
consécutives strictement au-dessus du high de la séance précédente complète ;
la clôture précédant ces deux barres doit être à l'intérieur ou au contact.
Entrée au prochain open contigu de la même séance, jamais dans la barre signal.

- **SL initial 5 %**, trailing **15 %** du plus haut observé dans les barres
  déjà terminées, aucun TP fixe.
- Chaque lot conserve ses propres entrée, stop et plus haut. Aucun déplacement
  artificiel à breakeven seulement dans le bras avec ajout.
- Un nouveau high ne relève le stop qu'après la barre complète ; il ne sert
  pas à fabriquer un stop plus avantageux au sein de cette même barre.
- Gap sous le stop : sortie à l'ouverture réellement observée. Les pertes
  peuvent dépasser le budget planifié.
- Sortie forcée à **l'open de la dernière barre 5m de J+20** : 15:55 New York
  normalement, 12:55 en demi-séance. Ni high ni clôture de cette dernière barre
  ne sont utilisés. L'attente et le renforcement ne prolongent pas la campagne.
- Un stop intrabar est localisé dans l'intervalle ; son heure conservée est
  la fin de barre, pas une heure d'exécution prétendument connue à la seconde.

### Trois bras figés

| Bras | Entrée initiale | Renforcement |
| --- | --- | --- |
| `FULL_BASE` | Quantité complète autorisée | Aucun |
| `HALF_CONTROL` | Moitié entière de cette quantité | Aucun |
| `HALF_ADD_ONE` | Même règle de demi-taille | Un seul ajout après confirmation à +5 % |

Quantité complète à l'entrée : minimum entier entre le budget de risque
**2 % de l'equity**, la limite de poids 25 % et la trésorerie avec frais.
Le risque par action réserve SL5 % plus les deux jambes de friction. La quantité
cible complète et le budget 2 % sont ensuite figés pour cette campagne.
Ce sont des plafonds, pas des risques systématiquement consommés.

L'ajout exige deux closes terminés de la même séance au moins **5 % au-dessus
de l'entrée initiale**. Achat à l'open suivant, à condition que le lot initial
soit encore détenu et que cet open reste au-dessus du seuil. Pas de moyenne
à la baisse, de troisième lot ou d'ajout après sortie de la position initiale.
Une première tentative annulée/refusée consomme le droit d'ajout.

Sa quantité ne dépasse ni la quantité complète cible moins la quantité initiale,
ni le cash disponible, ni le poids de 25 % courant, ni le risque résiduel figé.
Le risque utilisé additionne les pertes déjà réalisées et la perte jusqu'aux
stops connus des lots ouverts, avec réserve de frais. Les gains ne rechargent
pas ce budget. Aucun budget plus grand n'est accordé à cause de l'ajout.
**Le risque global effectivement engagé et les drawdowns ne sont pas pour
autant identiques entre les bras.**

### Coûts et comptabilité

Base : **8 bps par jambe exécutée**, coûts totaux hypothétiques, sans commission
fixe supplémentaire. Stress : **25 bps par jambe**. Le stress refait le calcul
des quantités, de la trésorerie et des décisions : pas un simple retrait de
frais aux mêmes transactions. Pas de fiscalité, dividendes ou autres flux
d'opérations sur titres modélisés ; ces limites interdisent la parité PAPER.

À l'achat : cash − quantité × prix − frais. À la vente : cash + quantité × prix
− frais. Equity = cash + valeur des positions. Les marques toutes les cinq
minutes incluent les séances sans transaction. Le taux de gagnants est calculé
par **campagne terminée**, tous ses lots réunis, pas par lots artificiellement
séparés. Le gain/perte réalisé d'une campagne est attribué à son année de sortie
finale ; il peut différer du PnL annuel marqué si la position traverse décembre.

## Résultats après frais

Le portefeuille 2026 reprend le capital et les éventuelles positions de fin
2025. Rendement annuel = fin d'année / capital de début d'année − 1.
2026 s'arrête au **30 septembre**, pas au 31 décembre.

### Base 8 bps par jambe

| Variante | 2025 | 2026 au 30/09 | Capital final | Cumul depuis 4 000 USD |
| --- | ---: | ---: | ---: | ---: |
| Entrée complète | +19,76 % | +13,46 % | 5 435,25 USD | +35,88 % |
| Demi-position seule | +12,92 % | +33,19 % | 6 016,01 USD | +50,40 % |
| Demi-position + ajout gagnant | +18,20 % | +21,74 % | 5 755,91 USD | +43,90 % |

| Variante | DD max 2025 | DD max 2026 | Gagnants 2025 | Gagnants 2026 |
| --- | ---: | ---: | ---: | ---: |
| Entrée complète | −28,20 % | −21,49 % | 29/104 = 27,88 % | 25/82 = 30,49 % |
| Demi-position seule | −14,38 % | −15,56 % | 31/110 = 28,18 % | 33/93 = 35,48 % |
| Demi-position + ajout | −20,35 % | −24,49 % | 25/108 = 23,15 % | 24/89 = 26,97 % |

Les DD sont des baisses depuis un plus haut d'equity marqué aux barres/fills,
sur chaque année avec son capital initial, pas un maximum intratick certifié.
Les taux de gagnants restent faibles : résultat positif grâce à certains gros
gains, pas grâce à une direction correctement identifiée sur la majorité.

### Stress 25 bps, simulations entièrement recalculées

| Variante | 2025 | 2026 au 30/09 | Capital final |
| --- | ---: | ---: | ---: |
| Entrée complète | +11,75 % | +6,27 % | 4 750,13 USD |
| Demi-position seule | +7,90 % | +23,64 % | 5 336,56 USD |
| Demi-position + ajout | +11,75 % | +11,53 % | 4 985,44 USD |

### Ce que le contrôle change dans l'interprétation

Au tarif de base, l'ajout termine **320,66 USD au-dessus de l'entrée complète**,
mais **260,10 USD sous la demi-position seule**. Il améliore le témoin demi-taille
en 2025, mais lui est inférieur en 2026 ; son DD 2026 est plus important.
En stress, le classement cumulé reste demi-position, ajout, entrée complète.
Cela **ne confirme pas un avantage transversal propre au renforcement**.

- Entrée complète : **186 campagnes achetées**, 27 refus de quantité nulle
  (trésorerie/granularité/prix) ; exposition moyenne aux marques 59,67/56,70 %.
- Demi-position : **203 campagnes achetées**, huit refus huit-positions et deux
  quantités nulles ; exposition moyenne 37,54/36,70 %.
- Avec ajout : **197 campagnes initiales**, **91 ajouts**, onze refus de quantité
  initiale nulle et cinq de nombre de positions ; trois ajouts refusés par les
  plafonds, deux annulés sur gap sous le seuil. Exposition 46,98/45,24 %.

Le compte demi-taille conserve davantage de cash, accède à plus d'occasions et
paie moins de frais. Les effets de capital modifient les entrées suivantes :
98 des 197 campagnes initiales communes au bras avec ajout ont une quantité
différente de leur homologue demi-taille. Ce n'est donc pas une comparaison
appariée où tous les achats initiaux seraient strictement identiques.

Les lots ajoutés totalisent +120,43 USD de net au tarif de base (+79,20 USD en
stress). **Ce chiffre n'est pas leur contribution causale incrémentale** : le
cash mobilisé empêche ou modifie d'autres transactions. Le bilan du portefeuille
entier demeure la comparaison pertinente.

Concentration importante : les trois meilleures campagnes réalisées du bras
entrée complète dépassent le total net réalisé de chacune des deux années
(1 413,72/711,16 USD puis 1 547,20/724,09 USD). Même constat pour le bras avec
ajout. Ce descriptif ne devient pas une règle d'exclusion rétroactive, ni une
preuve que ces gagnants auraient été identifiés d'avance.

## Conclusion et prochaine décision

**Calcul et audit terminés** : `PASS_SHARED_CASH_RESEARCH_AUDIT`, six variantes,
1 353 lots, 2 706 achats/ventes, 203 868 marques de compte et 1 470 ordres/tentatives
contrôlés. Vérification séparée des premiers signaux, prix, stops, quantités,
trésorerie, capital porté entre années et bilans. Verdict scellé :
`EXPLORATORY_ONLY_NO_PROMOTION`. Les 42 tests passent. La relecture automatique
par le même assistant ne remplace pas une revue humaine indépendante.

**Résultats exploratoires positifs sur le sous-ensemble qualifié, pas validation
de production.** Le contrôle de trésorerie change sensiblement le résultat et
rend la demi-position sans ajout plus intéressante dans cette comparaison.
Il ne faut pas transformer ce constat a posteriori en nouveau paramétrage
« optimal ». Pas d'ajustement du seuil +5 %, du SL ou du trailing après résultat.

Le renforcement n'est pas promu. Une suite nécessiterait un nouveau GO et un
périmètre de données plus représentatif, puis la qualification native de
l'exécution et des opérations sur titres. Aucun modèle, donnée SQL, batch,
ordre PAPER/live ou configuration de production n'a changé.

## Reproduction et traces

Dossier : `artifacts/research/us_oracle_pyramiding/20261020-v1`.

- `protocol.json` : règles et hachages avant calcul.
- `prepared.json`, `coverage.parquet`, `candidates.parquet`, `bars.parquet`,
  `calendar.parquet` : cohorte, signaux et prix figés, sans nouvel accès SQL.
- Six sous-dossiers bras/coûts : `orders.parquet`, `fills.parquet`,
  `lots.parquet`, `marks.parquet` avec tous les refus, lots et valeurs de compte.
- `annual-summary.csv`, `report.json` : bilans ; le premier rapport reste
  immuable et annonce l'audit en attente.
- `review.json` : attribution descriptive et effet des refus/concentration,
  pas optimisation ou nouvelle simulation.
- `test-results.xml` : **42 tests passent**, dont 25 nouveaux et les 17 de
  l'expérience parente ; 80 chemins aléatoires supplémentaires contrôlent les
  sorties avec une implémentation vectorielle distincte.
- `final-audit.json` : résultat du contrôle séparé signaux/prix/quantités/stops/
  cash/equity/calendrier/rendements, **PASS** ; fait foi sur le statut de livraison.
  Même assistant, **pas une seconde revue humaine indépendante**.

Commandes pour un **nouveau dossier vide** :

```powershell
python -u -m scripts.research.us_oracle_pyramiding --phase prepare --output artifacts/research/us_oracle_pyramiding/NOUVEAU-DOSSIER
python -u -m scripts.research.us_oracle_pyramiding --phase replay --output artifacts/research/us_oracle_pyramiding/NOUVEAU-DOSSIER
python -u -m scripts.research.us_oracle_pyramiding_audit --output artifacts/research/us_oracle_pyramiding/NOUVEAU-DOSSIER
python -u -m scripts.research.us_oracle_pyramiding_review --output artifacts/research/us_oracle_pyramiding/NOUVEAU-DOSSIER
```

Un dossier terminé n'est jamais écrasé. Le protocole refuse des sources modifiées
et la préparation vérifie les archives scellées de l'expérience parente.
