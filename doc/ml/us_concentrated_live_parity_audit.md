# Backtest concentré US — audit préalable de parité avec le portefeuille live

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

Date : 7 octobre 2026. Demande : un véritable backtest avec la logique du
portefeuille live, et non une approximation de sizing à partir de tapes unitaires.

## Verdict

Le [replay exploratoire](us_concentrated_portfolio_replay.md) n'est **pas** une
parité complète live. Ses rendements ne doivent pas être utilisés comme réponse
à cette nouvelle exigence. Ajouter `--phase2-mode risk_execution` au lancement
standard ne suffit pas non plus à résoudre les écarts décrits ci-dessous.

Cet audit n'active aucun compte, ne transmet aucun ordre, n'écrit aucune donnée
SQL et ne change aucun modèle ou paramètre live.

## 1. Écart structurel confirmé : compte vide en phase risque historique

Dans `backtesting/risk_bridge.py`, `build_phase2_risk_result` prépare les entrées
pour les dates historiques avant l'exécution du portefeuille. Le snapshot injecté
au builder (autour des lignes 655–670) fixe :

```python
account={
    'equity': float(cfg_for_day.account_equity),
    'cash': float(cfg_for_day.account_equity),
    'settled_cash': float(cfg_for_day.account_equity),
    'buying_power': float(cfg_for_day.account_equity) * 2.0,
}
positions=[]
orders=[]
```

Le code indique explicitement que le backtest simule un compte frais chaque
jour à cette étape. Le simulateur conserve ensuite ses positions/cash et peut
réduire/refuser les quantités, mais cela ne reconstitue pas rétroactivement la
décision du PortfolioBuilder sur le véritable état détenu.

Le live, dans `risk_management/cli.py`, capture et transmet un snapshot
opérationnel au `PortfolioBuilder`, avec compte, positions et ordres. Il injecte
aussi notamment contexte de régime, transition, trackers, et selon le mode
les données de liquidité et de borrow.

**Conséquence :** la décision risque historique doit être appelée au fil du
portefeuille, avec son état courant, et non sur une liste pré-approuvée à compte
vide. Un provider d'equity seul ne suffit pas : positions et ordres doivent être
présents, et le buying power ne doit pas être arbitrairement égal à deux fois
l'equity si le profil ne le permet pas.

## 2. Ordonnancement temporel à corriger/qualifier

La boucle du simulateur valorise des positions avec `mtm_close` au jour courant
avant l'ouverture de nouvelles entrées (`backtesting/simulator.py`, notamment
lignes 1049, 1136 et 1294–1297). Pour une décision exécutée à l'open du même jour,
ce close ne doit pas déterminer le capital ou les garde-fous de cette entrée.

Il faut figer le moment de décision effectivement reproduit : décision à J
après clôture puis exécution à J+1, ou nouvelle décision à l'open J+1. Ce ne sont
pas les mêmes informations disponibles. Les règles de gap d'exécution peuvent
revalider/refuser l'ordre à J+1, sans transformer la clôture future en information
connue à J.

Le nouveau moteur quotidien doit ordonner explicitement : règlement, états
ordres/fills, décisions, gaps à l'open, sorties/annulations, nouvelles entrées,
événements intraday et clôture. Il ne faut pas financer un ordre antérieur avec
un produit de vente ultérieur. Les événements simultanés demandent une convention
déterministe commune avec le contrat d'exécution simulé.

## 3. Différence de politique de sélection à résoudre

Les tapes concentrées existantes portent explicitement
`FORCED_RESEARCH_SIDE_NOT_DIRECTIONAL_MODEL` : Oracle amplitude sélectionne
les candidats, puis la recherche force le côté LONG.

À l'inverse, `PortfolioBuilder.build`, autour des lignes 707–737, exige une
prédiction directionnelle sélectionnable avec le côté et sa probabilité. Il
exclut les symboles qui n'en disposent pas. L'Oracle d'amplitude ne fournit pas
à lui seul cette probabilité directionnelle.

Il ne faut donc pas fabriquer `P(LONG)=0.9` ou `1.0` pour faire passer les gates
du builder et annoncer une parité live. Il existe deux contrats différents :

1. **Politique expérimentale Oracle pur LONG-only**, mais portefeuille, risque,
   exécution et coûts communs au live. Le côté LONG est une décision de stratégie
   explicite, pas une prédiction. Ce contrat nécessite une prise en charge explicite
   de cette politique dans le chemin commun, sans désactiver clandestinement les
   gates directionnels des autres modes.
2. **Politique de sélection live directionnelle**, avec vraies probabilités
   Per-Symbol/bundle et même cascade/gates. Il faut les artefacts et prédictions
   historiques correspondants. Les candidats et donc les résultats ne seront
   plus nécessairement ceux des tapes concentrées Oracle pur.

Le choix conditionne l'expérience. La configuration actuelle affiche aussi
`cascade.live_oracle_tradable_policy: off` et `live_oracle_batch_id: null` : les
tapes ne prouvent pas une identité avec la sélection actuellement activée live.

## 4. Données nécessaires à la parité des décisions

| Entrée | Exigence | Limite actuelle du replay exploratoire |
|---|---|---|
| Secteur | Même mapping que live, versionné et disponible à la décision | Bucket commun conservateur 50 %, pas secteurs réels |
| Macro/régime | Même provider, calcul, transition et politique de données manquantes | Contexte non rejoué |
| Univers négociable | Même filtrage/PIT, puis même classement/cascade | Membership historique figée, tradabilité non certifiée |
| Prédictions | Même contrat de stratégie et mêmes probabilités réelles si requises | LONG forcé, pas direction ML |
| Compte | Equity, cash réglé/non réglé et buying power réellement simulés | Adaptateur stateful disponible, pas builder live complet |
| Positions/ordres | Snapshot et trackers continus, pas compte vide quotidien | Chemin standard phase risque pré-calculé à compte vide |
| Liquidité | Quotes/spreads/ADV disponibles à la décision selon les gates actifs | Spread de coût hypothétique, pas équivalent aux quotes historiques |
| Prix/actions sur titres | Identités, événements et cours exploitables, réserves explicites | Cas LBRDK non qualifié, overlay BAND observé après les faits |
| Borrow | Nécessaire si SHORT activé | Non qualifié dans le dossier LONG |

L'utilisation d'un secteur actuel ne devient pas PIT en changeant le nom du
champ. Une quote gratuite indicative n'est pas une preuve de NBBO historique.
Les limites de données doivent rester séparées de la parité logicielle.

## 5. Architecture requise

Une boucle chronologique unique doit posséder le ledger de portefeuille et
appeler le chemin risque commun à chaque décision :

```text
Informations disponibles à l'instant de décision
  + état simulé compte / positions / ordres / trackers
  → snapshot opérationnel normalisé
  → régime / transition / politique de sélection commune
  → PortfolioBuilder et toutes les contraintes actives
  → ordres approuvés avec quantités et ancres
  → broker simulé / contrôles de gap
  → protections / watcher / lifecycle communs
  → fills / frais / règlements / événements
  → état suivant, utilisé par la prochaine décision
```

Ne pas recopier manuellement les règles du builder dans un second moteur.
Les variantes sans TP et expiration à vingt séances restent des politiques
de sortie contrefactuelles : la référence doit d'abord passer la parité avant
de substituer une seule règle de sortie à la fois.

## 6. Critères de validation avant publication d'un rendement

- Même input de décision, même configuration résolue, mêmes quantités,
  approbations/rejets, ordre des candidats, ancres et motifs que le chemin live
  exécuté sans broker réel sur des fixtures contrôlées.
- Positions existantes, ordres en attente, achats non financés, cash réglé et
  non réglé, capacités de marge, concentration et secteurs effectivement testés.
- Régime défensif, transitions, breaker, ramp-up, corrélation et options actives
  du profil testés ; aucune neutralisation cachée pour obtenir des trades.
- Aucun close futur dans la décision ; pas d'entrée sur données manquantes
  transformées implicitement en valeurs neutres.
- Parité gap stop/TP et résolution intraday conservatrice, watcher et annulations.
- Frais sur **tous** les chemins de fermeture, y compris fermetures forcées,
  et liquidations terminales explicitement distinguées.
- Réconciliation equity/cash/PnL/frais, plafonds et quantités invariants.
- Rapport distinguant parité du code, couverture historique PIT et hypothèses
  de microstructure : OHLC journalier ne garantit pas les fills d'un courtier.

## Statut à l'issue de cet audit

**Parité complète non acquise.** Aucun nouveau rendement présenté comme live.
Le contrat de sélection a été confirmé : **Oracle pur LONG-only**, sans
probabilités directionnelles artificielles. Ensuite, l'implémentation doit porter sur
la boucle commune stateful et sur la qualification des entrées historiques,
pas sur un nouveau réglage de seuils ou de TP après observation des pertes.

### Hypothèse secteurs explicitement acceptée — 7 octobre 2026

L'utilisateur a explicitement autorisé l'utilisation des **secteurs actuels**
pour le rejeu historique. Le précontrôle accepte cette substitution uniquement
avec `--sector-policy current_explicitly_accepted` (le défaut reste
`historical_pit`). Le mapping commun `_load_sector_mapping` est archivé avec
son empreinte ; il privilégie la colonne `provider_sector` lorsqu'elle existe,
conformément à son implémentation, sans inventer de secteur manquant.

Cette autorisation lève l'exigence de secteurs historiques PIT pour cette
expérience, **pas** les contrôles de couverture des secteurs, de macro,
d'exécution ou de portefeuille. Les secteurs actuels peuvent différer de ceux
connus aux dates simulées : le rapport doit donc conserver `sector_pit=false`.
Aucune date de disponibilité historique n'est antidatée et aucune donnée SQL
n'est modifiée. Cette hypothèse ne vaut pas certification de parité complète.

Précontrôle exécuté avec cette politique : **156 835 / 156 835 couples
date/symbole couverts**, aucun secteur manquant ; macro présente sur les
**437 / 437 séances** attendues. Rapport et mapping figé :
`artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/`.
Les dates macro sont couvertes, mais leurs timestamps ne constituent pas une
preuve de vintage de chaque champ. Les 18 tests ciblés secteurs/Oracle pur
passent. Aucun PnL n'a été lancé par ce précontrôle ; l'intégration
chronologique du ledger et la revalidation d'exécution restent nécessaires.

## Avancement du raccordement chronologique — 7 octobre 2026

### Décision de risque persistante

`backtesting/oracle_portfolio_session.py` fournit désormais une session de
risque Oracle pur LONG pour **un portefeuille entier**, et non une session
recréée chaque jour. Elle appelle le `PortfolioBuilder` commun au live ;
elle ne recopie pas le calcul de sizing dans un moteur indépendant.

- Compte, positions, ordres et buying power viennent obligatoirement du
  snapshot du ledger simulé daté de J. L'equity initiale n'est pas réinjectée
  arbitrairement à chaque séance.
- Le régime de J est obligatoire et transmis au builder, avec les permissions
  de transition lorsqu'elles sont fournies. Aucun régime neutre n'est inventé.
- Les garde-fous structurels, les plafonds du régime et la politique de compte
  sont appliqués par les fonctions communes. `account_long_only` décrit le
  compte réel, pas simplement le choix d'une stratégie LONG dans un compte marge.
- Les trackers de confirmation, concentration, pertes consécutives et rotation
  sont conservés entre décisions. Les compteurs de trades/pertes sont alimentés
  par les ouvertures/fermetures réellement exécutées, pas par les approbations.
- Un identifiant de fill déjà reçu ne compte pas deux fois ; un contenu
  contradictoire avec le même identifiant est refusé. Une ouverture désigne ici
  une position ouverte, et non chaque fragment de fill partiel.
- Les prix futurs sont tronqués avant ATR, ADV et corrélation. Les barres de J,
  l'ATR20 complet, l'ordre des décisions et les dates des snapshots sont vérifiés.
- Une exception après mutation des trackers rend la session inutilisable :
  il faudra repartir d'un checkpoint validé plutôt que doubler les compteurs.

### Exécution à la séance suivante

`simulate_phase3_execution_replay` accepte l'option explicite
`enforce_live_gap_filter=True`. Elle utilise
`split_entry_intents_by_gap_filter`, la règle d'exécution partagée avec le live,
**après** approbation de risque et **avant** tout fill ou protection. Les rejets
figurent dans `diagnostics.gap_rejections`. Son défaut reste `False` pour ne
pas modifier implicitement les anciens replays.

Les tests raccordent la session de risque à cette exécution et aux protections
de phase 4 : date J+1, quantité réelle, quantités fractionnelles, gap positif ou
négatif, frontière à 3 %, absence d'open, et conservation de quantité après
la chaîne de retries synthétiques. Ces retries restent des scénarios simulés,
pas des observations de broker ; leurs horaires ne certifient pas un fill réel
à l'open et devront être distingués dans le rapport historique.

### Validation et reste à faire

**196 tests ciblés passent**, avec 10 avertissements pandas existants de
concaténation de frames vides (pas une validation de la suite entière).
Rapport : `artifacts/research/us_concentrated_replay/oracle-session-tests-20261007.xml`.

**Aucun backtest historique complet n'a été lancé à ce stade.** La session est
le composant de décision ; elle ne simule pas à elle seule le broker ni le
ledger. Restent à raccorder et valider dans une boucle quotidienne unique :

1. Construction chronologique du régime macro, de ses transitions et du PnL
   fourni au breaker, avec les données historiques archivées.
2. Ordres en attente, fills J+1, règlements et positions réellement détenues,
   puis snapshot à la clôture pour la décision suivante.
3. Gestion commune watcher/protections/sorties et événements de transition,
   sans réutiliser les anciennes tapes unitaires comme approbations de portefeuille.
4. Frais de tous les chemins, intérêt de marge, liquidation terminale et
   réconciliation cash/equity, puis nouvelle certification des empreintes source.
5. Smoke chronologique de bout en bout, puis référence historique avant
   comparaison des variantes de sortie.

Aucun modèle, batch en cours, réglage live ou contenu SQL n'a été modifié.

## Ledger incrémental et smoke de bout en bout — 7 octobre 2026

`backtesting/oracle_portfolio_ledger.py` raccorde maintenant les décisions de
la session à **un seul `_RunState` natif** et aux primitives comptables du
`BacktestEngine`. Il ne recopie ni le sizing ATR ni les formules de cash dans
un simulateur indépendant.

Le smoke exécute : clôture J → décision du builder commun → ouverture J+1 →
fill de la quantité approuvée → protection phase 4 → sortie → frais natifs →
snapshot réel suivant. Il vérifie notamment :

- l'equity d'ouverture ne dépend pas du close futur de la séance ;
- les achats débitent le cash, frais compris ; les ventes paient également
  les frais, y compris une liquidation terminale explicitement demandée ;
- en compte cash, les ventes créditent d'abord le cash non réglé, puis le
  cash réglé à T+1 ; une vente intraday ne finance pas un achat à l'open passé ;
- les intérêts de marge sont prélevés une seule fois, avant le snapshot
  utilisé pour la décision suivante ;
- un gap d'entrée refusé ne crée aucune position ni aucun débit ;
- un problème après mutation comptable rend le ledger inutilisable plutôt
  que de poursuivre avec un état partiellement modifié ;
- après liquidation, cash total = capital initial + PnL net des trades −
  intérêts, avec tolérance testée de 1e−9 sur les fixtures.

Les protections sont désormais calculées par les **phases 5 et 7 existantes**
sur un historique masqué au-delà de l'instant observé. À l'ouverture, même
le high/low de la séance courante est masqué. Le calendrier peut annoncer la
séance suivante pour une activation programmée, mais pas ses prix. Les gaps
sur positions détenues sont résolus avant les ambiguïtés intraday : stop
traversé → open réel simulé ; TP traversé → prix limite conservateur.

Les 13 tests du nouveau ledger passent isolément. Ils incluent le raccordement
watcher/lifecycle au TP, les gaps de sortie et l'impossibilité pour un high
futur de provoquer une sortie aujourd'hui. Ce sont des **fixtures synthétiques**,
pas encore les résultats des 437 séances historiques.

### État à la fin du raccordement du ledger (avant l'orchestrateur)

- Le ledger fournit des opérations incrémentales ; l'orchestrateur historique
  complet (régime macro, breaker, transitions, décisions, fills et clôtures)
  n'est pas encore assemblé ni lancé.
- Les annulations/remplacements des ordres protecteurs et les plans de
  réduction/liquidation de régime doivent être raccordés au suivi des ordres.
  Le snapshot du ledger expose pour l'instant les positions et le cash, pas
  un carnet complet d'ordres broker ; il ne faut pas le présenter comme tel.
- Les refus éventuels du ledger après les fills hypothétiques phase 3 sont
  explicitement journalisés. Une certification doit examiner ces divergences,
  pas traiter tous les fills hypothétiques comme des achats comptabilisés.
- Les barres sources doivent encore être qualifiées sur les chemins réellement
  détenus (volume, `is_filled`, identités/actions sur titres). Le raccordement
  ne transforme pas les anciennes réserves de données en preuves PIT.
- Le profil de volatilité cible, la continuité du breaker et les transitions
  restent à vérifier dans l'orchestrateur avant tout PnL historique publié.

Le rendement synthétique n'est pas une performance de stratégie. **Aucun run
historique de portefeuille complet n'a été lancé dans cette étape.**

## Raccordement historique et lancement — 7 octobre 2026

Cette section remplace le statut d'avancement précédent : l'orchestrateur
`scripts/research/us_concentrated_live_portfolio.py` est désormais assemblé.
Il raccorde les décisions au portefeuille natif ; ce n'est plus un calcul
de rentabilité de trades unitaires supposés indépendants.

### Ordre chronologique exact

1. Début de séance : règlements en attente et valorisation aux opens observés.
2. Sorties protectrices en gap des positions déjà détenues, sans high/low futur.
3. Réductions/liquidations décidées la veille par la machine de régime.
   Les réductions conservent une position et des protections sur le reliquat.
4. Ordres d'entrée approuvés la veille : phases 3/4, filtre de gap commun à 3 %,
   puis comptabilisation de la quantité effectivement remplie, sans nouveau sizing.
5. Protections intraday : watcher phase 5 et lifecycle phase 7 communs, priorité
   conservatrice pour les ambiguïtés OHLC. Les prix après la séance sont masqués.
6. Sorties de clôture pré-enregistrées : échéance éventuelle à `entry_index + 20`,
   puis liquidation terminale commune pour rendre les variantes comparables.
7. Intérêts de marge, valorisation de clôture, snapshot cash/positions/ordres.
8. Régime commun calculé depuis l'archive macro, transition, breaker persistant,
   volatilité cible SPY via les fonctions du chemin live, puis décision pour J+1.

Le tracker de trades compte les entrées réelles, jamais les simples approbations.
Les pertes consécutives portent sur le PnL agrégé d'une position entièrement
fermée : une réduction partielle n'est pas à elle seule une perte supplémentaire.
Les rechecks natifs sont synchronisés avec cette histoire avant les nouvelles
entrées. La trésorerie est réconciliée après liquidation : capital initial +
PnL net des positions − intérêts = cash final.

### Sélections et variantes figées

- `ORACLE_TOP10` : **dix titres**, les plus forts scores Oracle par séance ;
  ce n'est pas le décile de l'univers.
- `ORACLE_TOP20` : l'ensemble du pool **TOP20 % Oracle** préparé, trié par score.
- Pas de Per-Symbol directionnel ni de sélection rétrospective des futurs gagnants.
- Quatre variantes : TP/trailing sans échéance ; TP/trailing avec échéance 20 ;
  sans TP avec SL fixe/échéance 20 ; sans TP avec trailing/échéance 20.
- Capital 4 000 $, compte margin, plafond de base 8 positions, fractions,
  coûts canoniques, risque/contraintes de régime communs ; paramètres détaillés
  figés dans `contract.json` de chaque lancement.

Le précalcul optionnel des corrélations accélère uniquement le nouveau chemin
Oracle. Dix fixtures avec NaN, séries constantes et côtés opposés vérifient
les mêmes retenus/rejets que le calcul greedy historique ; près du seuil, le
calcul numérique historique est conservé. Le chemin directionnel reste inchangé.

### Validation et runs

235 tests ciblés passent (pas une affirmation sur toute la suite du projet).
Les quatre variantes ont terminé un replay historique borné à trente séances
dans `live-portfolio-smoke-20261007-v3`. Ce smoke précède l'ajout des contrôles
d'identité/`is_filled` et de synchronisation des trackers au lancement final ;
les tests de l'orchestrateur couvrent séparément l'échéance et la comptabilité.
L'ancien smoke v2 a été interrompu volontairement pour utiliser le précalcul ;
son `progress.json` ancien ne doit pas être lu comme un job encore actif.

Backtests de **437 séances, 2025–septembre 2026**, lancés en processus séparés :

- `artifacts/research/us_concentrated_replay/live-portfolio-oracle_top10-20261007-v1`
- `artifacts/research/us_concentrated_replay/live-portfolio-oracle_top20-20261007-v1`

Chaque processus exécute ses quatre variantes successivement. Voir `stderr.log`,
le `progress.json` par variante et, uniquement à la fin, le `report.json` global.
Les fichiers `*.partial.parquet` permettent de diagnostiquer un arrêt ; ils
ne constituent pas un backtest terminé ni un checkpoint complet de reprise.
En cas d'arrêt, relancer dans un nouveau répertoire après diagnostic, sans
prétendre que le portefeuille en mémoire peut être reconstruit avec le seul JSON.

Premier contrôle après lancement : `ORACLE_TOP10/CURRENT_NO_EXPIRY` et
`ORACLE_TOP10/REFERENCE_20_AFTER_ENTRY` ont terminé les 437 séances. Le premier
présente une réconciliation cash exactement nulle et aucun fill hypothétique
non comptabilisé. Les autres variantes continuent ; ce constat technique
ne suffit pas à conclure sur la comparaison économique complète.

Suivi en PowerShell depuis la racine du projet :

```powershell
Get-ChildItem artifacts/research/us_concentrated_replay/live-portfolio-oracle_top*-20261007-v1 -Recurse -Filter progress.json | ForEach-Object { $_.FullName; Get-Content $_.FullName }
```

### Réserves conservées

Ce raccordement assure un portefeuille chronologique avec les primitives
applicatives communes. **Il ne certifie pas une équivalence avec des fills
broker réels** : retries simulés, OHLC quotidien, spread/slippage hypothétiques.
Les ordres protecteurs du snapshot représentent les groupes économiques actifs,
pas une réplication de tous les messages et accusés de réception d'un courtier.
Le remplacement du groupe après réduction est atomique dans le replay.

Les secteurs actuels sont explicitement acceptés **non-PIT**. Les valeurs macro
archivées et leurs timestamps de table ne prouvent pas la disponibilité de chaque
champ à l'heure historique de décision. `data_quality` est conservé par séance.
Le benchmark reçoit un warm-up 2024 supplémentaire, lu seulement en consultation.
La correction fournisseur BAND reste une substitution de recherche observée
après coup, pas une modification SQL ni une preuve disponible historiquement.

Un volume nul/manquant sur une position détenue, une barre remplie artificiellement
ou un changement d'identité détecté provoque un arrêt explicite, sans suppression
rétrospective du trade perdant. Une absence de preuve d'action sur titres n'est
pas résolue par le raccordement comptable. Examiner aussi
`phase3_fills_not_committed` avant d'interpréter une performance publiée.

Aucun entraînement, aucune écriture SQL, aucun batch existant ni réglage live
n'a été modifié par ces lancements.

## Arrêt GPRE et relance versionnée — 7 octobre 2026

Le TOP20 v1 termine `CURRENT_NO_EXPIRY`, mais s'arrête dans
`REFERENCE_20_AFTER_ENTRY` après 365 séances : GPRE est détenu le 18 juin 2026
avec un volume local égal à zéro. Les deux variantes suivantes ne sont donc
pas exécutées dans cette campagne. Les quatre variantes TOP10 v1 sont terminées.
Ce n'est ni un échec d'entraînement ni une erreur de calcul du PnL : le contrôle
de qualification d'un chemin détenu a volontairement interrompu le replay.

Une requête EODHD bornée autour de cette date fournit :

| Champ | Archive locale | Nouvelle réponse EODHD |
|---|---:|---:|
| Open | 14,59 | 14,59 |
| High | 14,985 | 14,985 |
| Low | 14,22 | 14,22 |
| Close | 14,82 | 14,82 |
| Volume | 0 | **3 495 268** |

Les cours sont inchangés ; le fournisseur donne maintenant un volume positif.
Cela qualifie une correction fournisseur de volume, **pas une certification
indépendante** ni une preuve disponible au moment historique de décision.
Réponse brute, date d'observation, qualification et empreintes sont archivées
dans `artifacts/research/us_concentrated_replay/gpre-volume-refresh-20261007-v1`.
La base et les parquets sources restent inchangés.

Le runner accepte désormais `--volume-overlay` explicitement. Il contrôle la
qualification OHLC et les empreintes de la réponse brute et de l'overlay avant
application à une copie des barres. Un volume nul, négatif, non fini, ou un
désaccord OHLC ne permet pas cette réparation. Sept tests supplémentaires
couvrent cette qualification et le rejet d'une réponse modifiée ; les 38 tests
ciblés overlay/orchestrateur/ledger passent.

Les deux campagnes **v2** ont été relancées depuis le début, avec les mêmes
règles et le même overlay GPRE, pour maintenir des entrées comparables :

- `artifacts/research/us_concentrated_replay/live-portfolio-oracle_top10-20261007-v2`
- `artifacts/research/us_concentrated_replay/live-portfolio-oracle_top20-20261007-v2`

Les archives v1 sont conservées. Le `progress.json` ne contient pas l'état
complet du portefeuille : reprendre uniquement à la séance 366 aurait oublié
le cash, les positions, protections et trackers. Le redémarrage intégral évite
cette fausse reprise. Le contrôle des volumes reste actif ; aucune suppression
rétrospective de GPRE ou d'un trade défavorable n'a été appliquée.
