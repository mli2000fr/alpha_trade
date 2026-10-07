# Sélections Oracle concentrées — protocole exploratoire et préparation

Pré-enregistrement du 6 octobre 2026. **Cette étape prépare les candidats
et les preuves de prix ; elle ne calcule aucun portefeuille ni PnL.**
Suite de la [qualification des prix suspects](us_extreme50_price_qualification.md).

## Question et limites de l'expérience

La fréquence des mouvements H20 ≥50 % augmente parmi les scores Oracle
les plus élevés. Cela ne dit ni dans quel sens entrer, ni si ces mouvements
sont capturables avec les stops et les coûts de l'application. On cherche
à mesurer ensuite si une sélection plus concentrée améliore réellement le
portefeuille, sans entraîner de modèle ni optimiser ses sorties.

Les périodes ont déjà été examinées : **c'est une expérience exploratoire,
pas une nouvelle confirmation indépendante**. Aucune conclusion sur le
profit ou la direction n'est possible à partir de cette préparation.

## Données figées

- Batch Oracle H20 : `model-factory-20261003082853-e98332`.
- Univers statique de l'audit initial : 1 798 titres ; empreinte
  `d57d85d35c18717cc44747cdd99b2b0c8e48319a902402f19c515c2e8fb0001f`.
- Les masques de sélection sont repris des panels archivés, pas recalculés
  après inspection des rendements.
- Période principale préparée : **1er janvier 2025–30 septembre 2026**.
  L'entraînement s'arrêtait au 31 décembre 2024. Cela évite de mélanger
  entraînement et période économique, sans certifier à soi seul l'ensemble
  des horodatages de production des scores.
- 2020–2024 restent descriptifs ; un rejeu économique sur ces années exige
  une qualification supplémentaire des folds/lineages OOF.
- Barres supplémentaires du 1er octobre au 31 décembre 2024 : préchauffage
  des calculs de risque/ATR, pas entrées de portefeuille.

L'univers actuel comporte un risque de survivance. Aucune absence de titre
radié ne sera présentée comme preuve d'absence de perte historique.

## Trois politiques ; deux sens distincts

| Politique | Pool quotidien | Classement pour priorité d'entrée |
|---|---|---|
| P1 : Oracle TOP20 % | Percentile Oracle ≥0,80 du panel initial | Score Oracle décroissant |
| P2 : Oracle TOP10 | Dix premiers scores Oracle | Même ordre |
| P3 : Intersection TOP10 | Dix premiers Oracle parmi Oracle ET ATR TOP20 % | Même ordre |

La définition des TOP20 % est celle de l'audit initial : seuil inclusif et
rangs moyens en cas d'égalité. Le pool peut dépasser exactement 20 %.
Pour les TOP10, l'ordre secondaire est le symbole alphabétique, comme dans
le panel archivé. Ne pas changer cette convention pour améliorer un résultat.

Les trois pools sont préparés pour **LONG-only et SHORT-only séparés**.
L'Oracle n'indique pas le sens : ces deux bras évaluent une exposition
imposée, pas une prédiction directionnelle. Aucun Per-Symbol, filtre
sentiment ou DIP ne sera ajouté à cette comparaison.

Un contrôle compare les masques P2/P3. S'ils sont identiques sur une période,
leurs résultats ne constitueront pas deux preuves différentes. Les lignes
sélectionnées ne sont pas forcément des trades : disponibilité du capital,
positions déjà ouvertes, concentration et risque interviennent ensuite.

## Contrat économique à respecter avant le replay

Les intentions sont enregistrées dans `protocol.json` :

- capital initial 4 000 USD ; au plus huit positions ; fractions autorisées ;
- entrée au **prochain open de séance régulière**, jamais à la clôture qui
  a servi aux features ; disponibilité effective du score avant cet open
  à contrôler ;
- sizing du moteur canonique, identique pour les trois pools ; pas de
  sizing personnalisé choisi après résultats ;
- stop initial 2,5×ATR ; TP `min(3×ATR, 7 %)` ; trailing canonique risk-based
  et activation watcher à vérifier contre le moteur, sans approximation
  de recherche ;
- pas de time-stop, **pas de sortie forcée à H20** ; liquidation terminale
  commune au 30 septembre 2026 avec coûts ;
- gap maximal 3 %, exposition secteur maximale 50 %, drawdown maximal
  15 %, récupération 0,92, volatilité annuelle cible 13 % ;
- commissions 1 bps/jambe, slippage 2 bps/jambe, financement annuel 7,5 %
  seulement lorsqu'un financement est réellement utilisé.

**Ce document ne prétend pas que ces paramètres suffisent à reproduire
le moteur.** Avant exécution il reste à figer le contrat complet de sizing,
priorité intrabar, protection, macro/secteurs PIT, sizing short et coûts.
Les valeurs implicites de `BacktestConfig` ne sont pas toutes canoniques :
par exemple son time-stop vaut `True` par défaut. Ne pas lancer un simulateur
minimal en pensant obtenir automatiquement la production.

`common/trading_costs.py` définit par défaut un **half-spread** de 5 bps,
commission 1 bps et slippage 2 bps par jambe : 16 bps aller-retour avant
financement/emprunt. Ce spread est une hypothèse, pas une quote observée.
Le moteur traite aussi spread réel/fallback et frais legacy ; sa résolution
doit être contrôlée pour éviter omission ou double comptage. Le protocole
machine laisse explicitement ce contrôle comme préalable, pas comme zéro.

Les disponibilités et frais historiques de borrow manquent : un bras SHORT
peut être exploratoire avec hypothèses clairement déclarées, mais **ne peut
pas être certifié économiquement réalisable** avec le seul taux générique.

Attention à `cascade.oracle_atr_enabled: true` : ce filtre ne doit pas être
réappliqué implicitement à P1/P2, sinon le benchmark Oracle seul disparaît.
P3 utilise précisément l'intersection déjà figée. Aucun paramètre de
production n'est changé pour cette préparation.

## Extraction et qualification des chemins

Script `scripts/research/us_concentrated_replay_prepare.py` :

1. sélectionne l'union des trois masques dans les panels 2025–2026 ;
2. conserve les candidats même si leurs labels futurs sont manquants,
   invalides ou immatures ;
3. extrait en **SELECT uniquement** les OHLCV, ajustements, sources et
   identifiants de tous les symboles nécessaires ;
4. archive par année, avec reprise sur les fichiers complets déjà présents ;
5. relève les prix futurs manquants, volumes nuls, barres remplies, ruptures
   quotidiennes ≥50 %, changements d'identifiant et réserves INDV/GRND ;
6. exporte les contrôles sans suppression ni remplacement de candidat.

Le calendrier utilisé pour ce diagnostic est celui des barres SPY observées,
avec volume positif et non remplies : **proxy**, pas calendrier officiel
indépendamment certifié. La fenêtre de contrôle va de J à la vingtième
séance suivante. Elle est déterminée par ce calendrier, **pas par la présence
d'un label favorable**. L'entrée proposée est J+1.

Un grand saut est une demande de revue, pas une preuve d'erreur. Une fenêtre
sans drapeau local n'est pas indépendamment certifiée. Les candidats proches
de la fin de septembre restent présents avec maturité incomplète : ne pas
les exclure parce que leur rendement H20 est inconnu.

Les barres sont archivées pour tout l'horizon d'observation des symboles
sélectionnés : les futurs chemins de lifecycle peuvent dépasser H20. Les
contrôles H20 ne certifient pas ces prolongations ; une fois les trades
rejoués, leur intégralité devra aussi être examinée.

Les exclusions éventuelles doivent distinguer :

- inéligibilité connue avant décision (peut devenir filtre de trading PIT) ;
- anomalie découverte avec le futur (réserve d'évaluation, **pas veto PIT**) ;
- simple hypothèse fournisseur (analyse exploratoire distincte).

Pour une réserve rétrospective, ne pas prendre le onzième titre à la place
du dixième douteux : cela remplacerait la politique initiale après observation.
Il faudra publier les résultats fournisseur et la sensibilité réservée
séparément, sans qualifier automatiquement la seconde de backtest investissable.

## Fichiers et suivi

Dossier : `artifacts/research/us_concentrated_replay/prepare-20261006-v1/`.

- `protocol.json` : intentions figées et contrôles préalables explicites ;
- `candidates.parquet` : candidats, trois masques et réserves ;
- `bars-2024.parquet`, `bars-2025.parquet`, `bars-2026.parquet` : OHLCV en lecture seule ;
- `path_checks.parquet` : une ligne par candidat, open suivant, fenêtre et motifs ;
- `report.json` : couverture, drapeaux par politique et divergences de masques ;
- `progress.json` : étape de préparation ;
- empreintes SHA-256 des exports dans le rapport.

```powershell
python -m scripts.research.us_concentrated_replay_prepare
```

La relance reprend les extractions annuelles déjà archivées. Ne pas les
réutiliser pour un autre protocole : choisir un nouveau dossier. L'outil
refuse un protocole machine différent dans un dossier déjà figé.

## Reporting économique attendu — pas calculé à cette étape

Pour chaque politique et sens : rendement brut et net, commissions, spread,
slippage, financement, borrow ; drawdown, Sharpe, exposition brute/nette,
nombre de trades, win rate, durée de détention, rotation et capacité.
Publier aussi contribution des cinq principaux titres, dépendance aux plus
gros trades et résultats par année/semestre. Ne pas traiter des fenêtres H20
chevauchantes comme des trades indépendants.

Comparer P2/P3 à P1 sur les mêmes périodes et contrats. Aucun seuil de
confiance, poids, stop ou sens ne sera choisi sur le meilleur PnL observé.
Même un résultat positif restera exploratoire et exigera une confirmation
distincte avant une modification de production.

## Résultats de préparation — terminé le 6 octobre 2026

**156 835 candidats uniques**, 818 titres sélectionnés au moins une fois,
437 séances ; 408 884 barres archivées, SPY et préchauffage compris.
Ces effectifs ne sont pas des nombres de trades.

| Pool | Candidats jour/titre | Titres distincts | Sans drapeau local |
|---|---:|---:|---:|
| Oracle TOP20 % | 156 835 | 818 | 148 805 |
| Dix premiers Oracle | 4 370 | 138 | 4 145 |
| Dix premiers dans l'intersection | 4 370 | 138 | 4 145 |

**P2 et P3 sont exactement identiques sur les 437 dates** : zéro divergence
de masque. Dans ce TOP10 précis, ATR n'ajoute donc aucun filtrage. Un replay
identique ne constituerait pas une confirmation supplémentaire d'ATR.
La comparaison informative restante est surtout pool TOP20 % contre TOP10,
sous réserve que les contraintes du portefeuille produisent des trades différents.

Dans chacun des TOP10 :

- 200 fenêtres H20 incomplètes à la fin de l'observation : ce n'est pas
  une erreur de prix ;
- dix signaux du **30 septembre 2026** n'ont pas d'open suivant dans le
  périmètre qui s'arrête ce jour-là : ils ne peuvent pas ouvrir une position
  avant la liquidation terminale ;
- 17 fenêtres se chevauchent sur **un seul saut MP**, le 10 juillet 2025 :
  clôture 45,23 $, hausse locale +50,616 %, volume 86 416 200. Le
  [8-K officiel](https://www.sec.gov/Archives/edgar/data/1801368/000119312525157310/d43796d8k.htm)
  documente l'annonce du partenariat avec le Department of Defense ce
  même jour. L'événement est corroboré ; ce document ne suffit pas à
  certifier tous les prix de la fenêtre. **Ne pas exclure automatiquement MP** ;
- huit fenêtres BAND traversent la barre du **18 juin 2026**, volume nul,
  `is_filled=0`, clôture 51,39 $, source `eodhd_eod`. Ce sont huit occurrences
  de la même réserve de barre, pas huit incidents indépendants. Vérifier
  le volume et la présence d'échanges avant certification.

Ces catégories peuvent se recouvrir : ne pas additionner leurs compteurs
pour obtenir un nombre de candidats distincts réservés. Les motifs détaillés
restent dans `path_checks.parquet`. Aucune exclusion de ces lignes n'a été
appliquée à la sélection.

Pour le pool TOP20 %, les drapeaux incluent 7 041 fenêtres immatures,
666 fenêtres avec volume nul, 360 sans open suivant valide, 288 avec saut
≥50 %, 186 avec séance manquante et sept avec barre remplie. Ces compteurs
portent sur des fenêtres, pas sur autant de journées de prix distinctes.

### Prochaine action, avant toute performance économique

**Assemblage terminé et vérifié le 7 octobre :** voir les [tapes historiques](us_concentrated_historical_tapes.md).
Le pilote utilise les phases réelles et des unités techniques, pas des tailles
approuvées de portefeuille. Il a détecté des réserves de prix de sortie en gap
et de transitions du watcher après sortie. Le traitement complet a produit
284 828 tapes unitaires sur 437 séances ; 3 496 fichiers vérifiés sans écart
d'empreinte. Aucun PnL historique n'est calculé. La tape
portefeuille stateful et les réserves économiques restent à qualifier.

**Mise à jour du 6 octobre :** voir l'[audit MP/BAND et du contrat moteur](us_concentrated_contract_qualification.md).
Le saut MP est corroboré ; EODHD fournit désormais un volume BAND de
1 997 781 au lieu du zéro local. Aucune correction SQL appliquée.
Le contrat technique a ensuite été corrigé et validé sur fixtures synthétiques
(voir section 8 de cet audit). Les tapes historiques et réserves de données
empêchent encore de déclarer une certification économique complète.

Revoir le cas de volume BAND et les preuves de prix MP ; figer la résolution
effective du sizing/coûts/lifecycle dans le moteur. Pour le benchmark TOP20 %,
trier aussi les autres réserves sans les ignorer au motif que le TOP10 est
plus propre. L'extraction complète permet cette revue sans recommencer le
chargement SQL. La préparation ne lève pas automatiquement les réserves de
tradabilité historique, de borrow ou de preuve de prix indépendante.
