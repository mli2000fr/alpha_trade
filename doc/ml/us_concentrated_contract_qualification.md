# Sélections concentrées US — MP/BAND et contrat du moteur

Audit et correction du 6 octobre 2026. Suite du [protocole de préparation](us_concentrated_replay_protocol.md).
**Mise à jour : contrat technique corrigé et validé sur fixtures synthétiques**
(section 8). Les sections 1–7 conservent le constat initial et ses réserves.
La parité économique historique complète n'est pas encore certifiée.
**Aucune performance économique historique calculée.** Ne pas confondre des tests unitaires
passants avec la validation d'un portefeuille réellement exécuté.

## 1. Périmètre et éléments reproductibles

Source figée : `artifacts/research/us_concentrated_replay/prepare-20261006-v1`.
Résultat retenu : `artifacts/research/us_concentrated_replay/qualification-contract-20261006-v2/report.json`.
Le dossier contient les deux réponses EODHD brutes, leurs empreintes, les
configurations résolues et les empreintes des sources du moteur et de `config.yaml`.
Le premier essai v1 reste une trace de développement : son adaptateur héritait
incorrectement du capital YAML, détecté puis corrigé par les nouveaux tests.

Script : `scripts/research/us_concentrated_contract_audit.py` ; tests :
`tests/test_us_concentrated_contract_audit.py`. Il lit uniquement les fichiers
archivés et effectue, avec `--refresh`, deux requêtes EODHD bornées. Aucune
connexion SQL, écriture en base, modification de prix local, de modèle, de
configuration opérationnelle ou de batch. Les consultations fournisseurs sont
datées d'aujourd'hui : elles ne démontrent pas ce que le fournisseur publiait à J.

Validation : **102 tests ciblés passants**, dont sept nouveaux contrôles sur
la qualification, les paramètres résolus, la consommation des quantités et
les gardes de contrat. Quatre avertissements pandas préexistants/non bloquants.
La fonction `require_economic_gate` refuse un contrat encore bloqué ou dont
les empreintes source ont changé. Elle est disponible pour le futur adaptateur ;
elle n'a pas été greffée au moteur de production et ne prouve pas la parité
bout-en-bout à elle seule.

```powershell
python -m scripts.research.us_concentrated_contract_audit --output artifacts/research/us_concentrated_replay/qualification-contract-20261006-v2
```

Sans `--refresh`, réutilisation des réponses archivées dans ce dossier.
Avec `--refresh`, nouvelle observation fournisseur et remplacement de ces
réponses : utiliser un **nouveau dossier** pour préserver la version retenue.

## 2. MP — saut réel corroboré, pas une erreur à supprimer

Le 9 juillet 2025, clôture 30,03 $ ; le 10 juillet, 45,23 $, soit **+50,616 %**.
La nouvelle réponse EODHD reproduit ces cours et le volume du 10 juillet :
**86 416 200**. Le [8-K officiel du 10 juillet](https://www.sec.gov/Archives/edgar/data/1801368/000119312525157310/d43796d8k.htm)
documente le partenariat avec le Department of Defense. La clôture à 45,23 $
est également corroborée par [CNBC](https://www.cnbc.com/2025/07/10/pentagon-to-become-largest-shareholder-in-rare-earth-magnet-maker-mp-materials.html).
Cette dernière preuve a été consultée via son résultat indexé : accès direct
refusé par robots.txt. Ce n'est pas une certification boursière de tout l'OHLCV.

**Décision : ne pas exclure MP à cause du saut.** Les 17 drapeaux TOP10
correspondent à 17 fenêtres chevauchantes sur cet événement, pas à 17 incidents.
Le mouvement ne constitue pas un split artificiel identifié par cet audit.

Attention à la réalisabilité : l'open du 10 juillet est **48,10 $**, soit un
gap d'environ **+60,17 %** contre la clôture précédente. Une entrée issue du
signal du 9 juillet doit être rejetée avec un gap maximal de 3 % ; elle ne
peut pas capturer fictivement la hausse depuis 30,03 $. Une position ouverte
antérieurement est un autre cas, à traiter par son lifecycle réel. Aucun de
ces cas n'a encore été valorisé économiquement.

## 3. BAND — volume local obsolète confirmé par le fournisseur

| Barre du 18 juin 2026 | Archive locale | EODHD relu le 6 octobre |
|---|---:|---:|
| Open | 51,615 | 51,615 |
| High | 52,50 | 52,50 |
| Low | 48,50 | 48,50 |
| Close / adjusted close | 51,39 | 51,39 |
| Volume | **0** | **1 997 781** |

Il existe donc une **correction fournisseur disponible**, sans changement
des prix de cette barre. Les huit fenêtres TOP10 réservées traversent la même
barre. Ce volume n'a **pas été écrit en base ni injecté silencieusement dans
les archives préparées**. Il faudra un overlay de recherche versionné ou une
correction de données explicitement autorisée, puis recalculer les contrôles
de chemins et toute mesure ADV/impact dépendant du volume.

La relecture du même fournisseur ne remplace pas une preuve indépendante de
volume consolidé. Un volume Alpaca IEX éventuel ne serait pas interchangeable
avec ce volume consolidé. Aucun arrêt de cotation n'est déduit du zéro local.

## 4. Sizing : résolution explicite, pas 1/8 du capital par défaut

L'adaptateur de recherche fige **4 000 $**, huit positions, fractions autorisées,
preset `capital_2001_5000`, H20, stop 2,5 ATR. Le preset résout actuellement
`risk_per_trade_pct=0.0125`, donc budget de risque brut 50 $ avant les autres
ajustements. Le `PositionSizer` calcule :

`quantité proposée = equity × risk_per_trade_pct × risk_multiplier / (ATR20 × multiple_stop)`.

Pour prix 100 $, ATR 2 $, multiplicateur de risque 1 : dix actions proposées.
Ce n'est **pas** la quantité finale : contraintes de poids, secteur, exposition,
liquidité, régime et allocation du portefeuille peuvent la réduire/rejeter.
ATR absent : rejet explicite, pas remplacement par une quantité arbitraire.

Piège reproduit : `load_risk_config(equity=4000, ...)` seul pouvait restituer
100 000 $ dans la configuration locale. La **CLI existante** passe déjà
`cli_overrides['account_equity']=args.equity` ; l'audit ne démontre donc pas un
bug général des backtests CLI. Le nouvel adaptateur applique la même protection.

Le futur replay doit consommer les quantités effectivement approuvées/remplies
des tapes du pipeline : `filled_qty`, sinon `approved_shares`, sinon `target_shares`.
Le simulateur peut retomber sur son sizing interne si ces données manquent.
**Le futur adaptateur devra refuser ce fallback** ; le contrôle est spécifié
mais la comparaison bout-en-bout des tapes n'est pas encore réalisée.

## 5. Lifecycle : contrat historique distinct des défauts actuels

| Élément | Intention de recherche figée | Résolution courante à surveiller |
|---|---|---|
| Stop H20 | 2,5 ATR explicite | map H20 à 3,5 ATR sans override |
| TP H20 | min(3 ATR, 7 %) explicite | map H20 min(4 ATR, 13 %) |
| Trailing LONG | risk-based, aucun plancher fixe | défaut exécution / CLI à 7 % |
| Time-stop | OFF explicite | YAML ON, 20 jours ouvrés |
| Activation trailing | 0R, transition watcher | dépend de la tape effective |
| Entrée | prochaine séance, open ; gap 3 % | pas clôture du signal |
| Sortie H20 forcée | aucune | H20 est une cible, pas une règle de sortie |

Le chargeur sans sélection explicite d'horizon résout actuellement H10 : les
maps H20 ci-dessus s'appliquent **si H20 est sélectionné**. Le rapport conserve
les deux informations pour ne pas attribuer automatiquement H20 à tout appel.
L'option `--trailing-long-risk-based` supprime le plancher LONG dans la CLI.
Passer uniquement stop/TP ne désactive pas le time-stop chargé via
`ExecutionConfig`. Le watcher comporte des gardes (ordre de sortie existant,
progression vers TP, etc.) : ON ne signifie pas que chaque position sortira à
20 jours, mais on ne peut pas annoncer OFF ou zéro fill sans contrôler la tape.

Le constructeur de recherche fige aussi `swing_only=False`, profil `custom`,
compte margin, gap 3 %, secteur 50 %, drawdown 15 %, récupération 92 %,
volatilité cible 13 %. Ces paramètres reproduisent l'intention de recherche,
**pas une certification de l'identité avec les défauts live**, où le profil
overnight et `swing_only=True` existent. Le choix doit être identique entre
les politiques comparées et explicite dans le futur replay.

Chaîne requise : pipeline → phase2 risk_execution → phase3 execution_replay
→ phase4 protection_replay → phase5 watcher_replay → phase7 exit_lifecycle_replay.
Il reste à comparer, ordre par ordre, quantité, prix d'entrée, protection
initiale, activation/remplacement du trailing, raison et date de sortie,
annulation OCO et liquidation terminale. Des tests isolés ne suffisent pas.

## 6. Coûts : anomalie de convention empêchant la certification

`common/trading_costs.py` définit `spread_bps` comme un **demi-spread**,
payé à chaque jambe. Le simulateur reçoit un spread bid/ask **complet**, le
divise par deux à l'entrée et à la sortie, et ajoute encore une pénalité
d'exécution de **5 bps à l'entrée**, distincte des 2 bps de slippage du modèle.
Or son fallback reprend la valeur du modèle partagé sans conversion explicite.

À commission 1 bps et slippage 2 bps par jambe, sans impact additionnel :

| Paramètre spread numérique | Modèle partagé, aller-retour | Simulateur, approximation premier ordre |
|---|---:|---:|
| 5 bps | 16 bps | 16 bps |
| 10 bps | 26 bps | 21 bps |

L'égalité à 5 bps est **fortuite**, pas une preuve de parité. Ces nombres sont
une décomposition algébrique des branches sources, pas des PnL exécutés :
les frais réels s'appliquent à des notionnels différents, avec possible impact
ADV, spreads observés, financement et commissions particulières.

Avant performance, choisir et tester une convention unique : quote complète
ou demi-spread, transformation du fallback, statut de la pénalité additionnelle
de 5 bps, absence de double comptage. **Aucun changement du moteur commun n'a
été fait dans cet audit.** Il ne faut pas masquer cet écart avec un coefficient
de coût choisi pour obtenir un meilleur PnL.

Les shorts ont une réserve supplémentaire : disponibilité et tarif de borrow
historiques non certifiés. Le code de sortie transforme actuellement les jours
calendaires de détention en `holding_sessions` avant division par 252. Cette
approximation doit être explicitée/corrigée avant toute certification de coût
SHORT ; un taux fixe hypothétique n'est pas une preuve d'emprunt possible.

## 7. Conclusion et suite nécessaire

MP : saut et clôture corroborés, pas exclusion automatique. BAND : prix
reproduits, correction de volume fournisseur identifiée mais non appliquée.
Contrat de recherche explicite et empreinté ; **parité moteur non déclarée acquise**.

Ordre des travaux restant avant un replay économique :

1. Valider/corriger la convention de coûts du moteur, avec tests de cash-flows
   LONG/SHORT sur prix plats, gaps, spreads observés/absents et financement.
2. Confirmer le lifecycle voulu : historique 2,5/3/7 %, risk-based, time-stop
   OFF, ou production courante ; ne pas changer d'hypothèse implicitement.
3. Construire et comparer les tapes complètes avec les mêmes configurations ;
   bloquer tout sizing de secours ou protection manquante.
4. Versionner l'overlay BAND et trier les autres réserves TOP20 ; une qualification
   MP/BAND ne certifie pas tous les candidats du benchmark.
5. Calculer ensuite seulement la performance, LONG exploratoire séparé du SHORT
   tant que le borrow n'est pas qualifié. P2/P3 sont des masques identiques,
   donc ne pas les compter comme deux confirmations indépendantes.

## 8. Correction et validation du contrat technique — après GO

Résultat retenu :
`artifacts/research/us_concentrated_replay/contract-validation-20261006-v3`.
Les runs v1/v2 ont été remplacés par v3 après ajout des gardes de protections,
d'exposition et de fill absent ; les conserver comme traces, pas
comme attestation des sources actuelles.

### 8.1 Coûts réellement corrigés dans le simulateur

En mode canonique ou avec un `TradingCostModel` explicite :

- `TradingCostModel.spread_bps` reste un **demi-spread** ;
- le fallback du simulateur devient **2 × ce demi-spread**, puisqu'une quote
  est un spread complet ; un override `fallback_spread_bps` exprime également
  un spread complet. Zéro est maintenant un override valide ;
- spread et slippage sont des coûts monétaires aux deux jambes, sans changer
  une deuxième fois le prix du fill Phase 3 ni les ancres de protections ;
- suppression des 5 bps supplémentaires à l'entrée en mode canonique ;
- une quote valide remplace le fallback, elle ne s'y ajoute pas ;
- le mode `cost_round_trip_bps` paie exactement C/2 par jambe, sans un deuxième
  C/2 sur le prix d'entrée ni commissions fixes superposées ;
- le borrow canonique compte les intervalles de **séances**, divisés par 252 :
  vendredi → lundi représente une séance, pas trois. Le tarif demeure une
  hypothèse et non une preuve de disponibilité d'emprunt.

Sur un aller-retour synthétique à prix plat, deux actions à 100 $,
demi-spread 5 bps, commission 1 bps et slippage 2 bps par jambe :
coût exact 0,32 $, soit 16 bps du notionnel d'entrée. Avec demi-spread 10 bps,
coût 0,52 $, soit 26 bps. LONG et SHORT sont testés séparément. Sur un prix
variable, les frais se calculent sur les notionnels de chaque jambe : ne pas
soustraire aveuglément 16 bps du rendement brut pour reproduire les cash-flows.

Les chemins legacy sans modèle canonique conservent la pénalité historique
de prix ; le scénario de coût absolu est corrigé dans les deux modes. Les
anciens runs **canoniques** ne sont donc pas garantis bit-à-bit reproductibles
après correction, notamment sur leurs prix d'entrée et ancres de protections.
Ne pas présenter une différence de futur PnL comme un progrès du modèle ML.
Les modèles, leur calibration et leurs labels n'ont pas été modifiés.

### 8.2 Contrat de recherche unique et gardes effectives

`frozen_backtest_config(start, end)` construit désormais tout le contrat,
pas seulement le risque et l'exécution : capital 4 000 $, H20, huit positions,
fractions, stop 2,5 ATR, TP min(3 ATR, 7 %), trailing risk-based LONG/SHORT,
0R, time-stop OFF, entrée prochaine séance, gap 3 %, secteur 50 %, drawdown
15 %, recovery 92 %, cible de volatilité 13 %, financement 7,5 % annualisé.
Les overlays secteur/DD/volatilité sont effectivement raccordés au simulateur,
pas seulement inscrits dans `RiskConfig`. Le plafond gross du preset est
également injecté explicitement dans `ExecutionConfig` : sa valeur résolue
est **1,0 × equity** dans ce dossier, sans levier implicite.

`require_replay_quantities=True` interdit un sizing de secours, rejette les
quantités invalides/non finies et arrête si les contraintes du simulateur
réduisent une quantité déjà remplie sur la tape. Une telle réduction doit être
résolue en amont et non comptabilisée comme si le fill initial avait eu lieu.

`require_replay_protections=True` impose la chaîne 3/4/5/7 complète et les
coûts canoniques. Le moteur refuse protections manquantes, doublons ambigus,
calendrier incohérent, mauvais sens stop/TP, état watcher invalide, activation
antérieure à l'entrée et sortie explicite invalide. Le fill de la tape doit
correspondre à l'open de la séance suivante à la précision du cent ; le moteur
utilise ensuite ce fill exact pour la comptabilité et les protections.
Ces deux gardes sont **opt-in, désactivées par défaut hors de ce contrat**.

Les défauts live de stop/TP/trailing/time-stop n'ont pas été changés. Cette
expérience utilise un contrat historique **explicite**, qui n'est pas présenté
comme identique à toute configuration live actuellement chargée.

### 8.3 Validation : fonctions réelles, données synthétiques

Les fixtures utilisent `PortfolioBuilder` (sizing et approbation), le replay
d'exécution Phase 3, les protections Phase 4, le watcher Phase 5, les sorties
Phase 7 puis **le véritable `BacktestEngine`**, sans copier son simulateur.
Pour TP, stop initial et trailing, dans les deux sens : comparaison de quantité,
prix et date d'entrée, stop/TP, taux de trailing, prix/date/motif de sortie et
annulation OCO. Les gates de sélection sont neutralisés seulement dans ces
fixtures pour forcer les cas à tester ; les probabilités synthétiques ne sont
pas une preuve de directionnalité de l'Oracle.

**37 tests de contrat passent**, aucun ignoré, résultats JUnit dans `tests.xml`.
Ils couvrent aussi coûts plats, spread observé, coûts absolus, multiplicateur,
borrow, gap, quantité/clipping invalide, fill déclaré absent malgré un ordre
approuvé, protections absentes et absence de
sortie H20 forcée quand time-stop OFF. Les avertissements pandas sont connus,
non bloquants. **329 tests ciblés élargis passent**, zéro échec, zéro test ignoré.
Cette batterie de non-régression est archivée séparément
dans `regression-tests.xml`.

`resolved_contract.json` contient les paramètres réellement résolus ;
`report.json` archive leurs empreintes et celles des modules/tests du contrat.
La garde économique continue de refuser ces rapports pour un PnL historique :
la validation technique n'efface pas les réserves de données et de tapes.

### 8.4 BAND : correction versionnée, sans SQL

`band_volume_overlay.parquet` contient exactement une correction :
BAND / 2026-06-18, volume 0 → **1 997 781**, avec empreinte de la réponse
EODHD et date d'observation. Les OHLC ont été contrôlés identiques. Ni les
parquets de préparation ni les tables de production n'ont été réécrits.
Le futur assembleur devra appliquer explicitement cet overlay à sa copie de
recherche, l'archiver dans sa lineage et recalculer l'ADV si utilisé. Cette
correction observée en octobre ne devient pas artificiellement une preuve
disponible en juin. Les scores Oracle figés ne sont pas recalculés.

### 8.5 Ce qui n'est pas encore certifié

Il reste les tapes **historiques** jour par jour et les réserves TOP20 de prix,
identités et tradabilité. La liquidation terminale devra être explicite, avec
coûts, plutôt qu'une valorisation MTM assimilée à une sortie gratuite.
Les chemins de force-close défensif/breaker/recherche, commissions tiered et
fills réels du courtier sont hors de cette attestation synthétique ; certains
force-close historiques ne facturent pas de frais de sortie. Ils ne doivent
pas être activés/réutilisés sous prétexte que ces fixtures passent.
Le financement est une hypothèse par séance et le borrow SHORT reste non qualifié.

Commande de revalidation (nouveau dossier obligatoire) :

```powershell
python -m scripts.research.us_concentrated_contract_validate --output artifacts/research/us_concentrated_replay/contract-validation-NOUVELLE_VERSION
```

Elle ne lance aucun backtest historique, aucun entraînement ni aucune requête SQL.
