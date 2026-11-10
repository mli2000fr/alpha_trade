# TOP20 % Oracle → A2 → risque — backtest économique

GO utilisateur du9novembre2026 après l'audit de fréquence : tester le pool
TOP20 % directement avec A2. **Recherche uniquement, aucune modification de
config.yaml, du pipeline ou des comptes, aucun ordre ni téléchargement.**

## Périmètre figé

- 01/01/2021–01/10/2026,4 000USD continus, sans reset annuel.
- Mêmes Oracles H10 annuels que Q051, univers contractuel1 790, TOP358àJ.
- **Aucun filtre per-symbol/per-sector/options/GPT** avant A2 dans ces essais.
- A2 inchangé : range20M15 figé àJ, impulsion12M15 avant le range≥2ATR,
  ATR14, largeur0,8–5ATR, deux contacts espacés ; premier rebond confirmé àJ+1,
  disponibilité closeM15+930s puis open5m suivant ; expiration à la fin deJ+1.
- Position complète, SL5 %, pas de TP/trailing/renforcement, sortie open11
  depuis l'entrée effective ; déjà détenu/actif : aucun nouvel achat.
- Budget d'entrée volatilité portefeuille annualisée20 % sur60séances
  antérieures, régime SPYJ>98 %SMA200. **Ce budget n'est pas un plafond DD20.**
- Risque par entrée1,25 %, poids20 %, maximum20positions, minimum50USD,
  plafond achats1×/capacité margin2×, B4/DD15/facteurs/corrélation/secteurs off,
  configuration native vérifiée contre le témoin archivé.
- Frais/slippage8pb par opération et financement annuel6,5 % ; deux stress
  fixes25pb par opération. Aucun seuil/poids recherché après observation du PnL.

## Cinq nouveaux replays

| Identifiant | Entrée | Coût par opération |
|---|---|---:|
| A2 | Signal A2 après délai, prix de l'open5m effectif |8pb|
| OPEN_COMMON | OpenJ+1 sans motif, même contexte passé qualifié |8pb|
| WAIT_COMMON | Attente fixe10h30NY sans motif, même contexte passé qualifié |8pb|
| A2_COST25 | Même A2, coûts renforcés |25pb|
| OPEN_COMMON_COST25 | Même témoin open, coûts renforcés |25pb|

La cohorte commune contient314 028candidats dont le contexte est connu àJ.
Ce n'est pas un filtre fondé sur la couverture future du chemin. A2 est
représenté par2 835événements causaux confirmés, dont2 452après régime ; les
événements sans prix exécutable ne sont pas supprimés en silence : refus et
réserves de couverture enregistrés par le moteur. Aucun TOP5 ajouté après A2.
Priorité Oracle originale entre candidats exécutables au même instant.

L'absence de motif ne réserve aucun capital. Pour accélérer le replay A2,
seuls ses événements sont transmis à l'horloge, avec interdiction d'exécuter
avant leur disponibilité. Parité économique du moteur vérifiée entre cohorte
complète et événements seuls, budget vol20actif : mêmes courbes/trades.
L'attente fixe utilise une horloge et n'interprète aucun motif de prix.

## Référence et comparabilité

Q051 per-symbol +vol20/régime existant est conservé comme repère :
9 039,00USD/+125,98 %/DD−24,29 %. Sa reproduction intégrale a été validée
précédemment (courbes/trades/événements/risque identiques à l'octet).
Il utilise un autre périmètre et une archive de prix moins étendue : les
**contrôles appariés nouveaux**, pas ce repère seul, isolent l'effet d'entrée.

Tous les nouveaux essais partagent la même priorité de données que l'audit
de fréquence : prix initiaux, compléments de contexte, puis extensionTOP358,
sans remplacer de prix initial, avec empreintes vérifiées. Prix daily et
opérations sur titres supplémentaires pour les nouveaux symboles proviennent
des archives déjà figées. Aucun nouvel appel fournisseur ou SQL en écriture.
Le graphique final inclura également SPY en prix seuls, hors dividendes/frais.

## Qualification technique avant lancement

**114tests ciblés passent** : moteurs et protections existants, nouveau
raccordement, parité scalaire/vectorisée, indexation temporelle, parité
cohorte complète/événements, risque appliqué au vrai prix d'exécution.
Sur trois journées2021/2023/2026, les M15 du lecteur économique correspondent
exactement à celles du lecteur de détection (548/574/576symboles vérifiés).

Un test renforcé a reproduit un défaut sur données partielles : après une
entrée tardive102USD, le mark revenait à l'open daily99,50USD. Correctif limité
à l'entrée programmée : conserver le nouveau prix observé après achat. Le
chemin journalier standard (`scheduled=False`) reste identique. La reconstruction
du fichier avant ce seul patch retrouve son empreinte dans la qualification
précédente ; les autres fichiers du moteur sont inchangés. Pas de nouvelle
reproduction économique du témoin, qualifié avant ce correctif isolé.

## Bilans et limites

Capital final valorisé, rendement, DD intraday, trades fermés, gagnants/perdants,
PnL moyen et durée moyenne gagnants/perdants (jours calendaires), capital brut
moyen/maximal, bilans annuels, coûts et consommation de marge. Les frais sont
comptés dans le PnL des trades ; le financement est imputé au portefeuille.
Les positions encore ouvertes au01/10/2026 restent valorisées, pas artificiellement
clôturées pour améliorer le taux gagnant.

Les5m ne sont pas complets partout. Le secours OHLC daily après une entrée
tardive est une borne adverse : le creux peut précéder l'achat. Le bilan
comptera ces cas séparément. Pas de garantie de fills réels ou de secteurs
historiques PIT, ni de nouvel échantillon indépendant après les recherches
antérieures. Plus de signaux ne signifie pas plus de gagnants ou plus de capital
automatiquement engagé : le risque et la détention restent appliqués.

## Lancement et suivi

Racine : `artifacts/research/us_a2_top20pct_economic/20261109-v1/`.
Script : `scripts/research/us_a2_top20pct_economic_20261109.py`.
Utilitaires : `scripts/research/us_a2_replay_inputs_20261109.py`.
Préparation : `python -m scripts.research.us_a2_top20pct_economic_20261109 --phase prepare`.
Exécution : `python -m scripts.research.us_a2_top20pct_economic_20261109 --phase run --workers 2`.
Ne pas lancer une deuxième exécution sur cette racine.

`request.json`/`inputs/manifest.json` figent le protocole et les entrées ;
`preflight-validation.json` consigne les contrôles ; `progress.json` suit les
cinq cas et `cases/<cas>/progress.json` donne séances/date/temps écoulé.
Deux processus simultanés au lancement ; le 10 novembre, à la demande de
l'utilisateur, deux workers supplémentaires lancent les stress de frais pendant
que OPEN_COMMON et WAIT_COMMON continuaient. Quatre simulations étaient actives.
Les réussites sont importées dans l'historique IHM avant consolidation finale.
Résultats attendus : `comparison.csv`, `annual-comparison.csv`, `validation.json`,
`report.json`, `charts/capital-comparison.png`/SVG/CSV.

## Premier résultat —10novembre2026

**A2 terminé/importé ; campagne encore en cours (1/5), aucun échec déclaré.**
A2 : capital final valorisé **4 519,04USD**, rendement **+12,98 %**, DD maximal
intraday **−30,24 %** (daily−29,70 %), **824trades clôturés**,290gagnants et534
perdants, taux gagnant **35,19 %**. PnL moyen gagnant+49,93USD/perdant−26,20USD,
durée moyenne14,54/5,82jours calendaires. Capital brut moyen **1 879,46USD**,
43,41 %du capital courant en moyenne, maximum4 676,94USD. Frais678,44USD,
financement0USD ; sept positions encore ouvertes valorisées à la fin.

Rendements annuels (capital transmis, pas de reset) :2021+15,53 %,2022−2,80 %,
2023+5,64 %,2024−8,64 %,2025−17,42 %,2026au01/10+26,22 %.

Validation préliminaire du cas PASS :824trades et six comptes annuels recomptés,
831achats dont sept encore ouverts, heures closeM15+930s→open5m vérifiées,
quantités positives dans le budget vol20. **29entrées** ont une protection
quotidienne adverse le jour de l'achat, avec réserve de creux antérieur.
Statut natif **INCOMPLETE_COVERAGE** conservé, isolationCOMPLETED.
Preuve : `cases/A2/preliminary-validation.json` ; import IHM
`20261109_a2_20pct_a2_v1`.

Le résultat est inférieur au repère per-symbol vol20/régime +125,98 %/DD−24,29 %.
Il ne permet pas encore d'attribuer la différence au seul motif A2 : le pool et
la disponibilité des prix diffèrent, les deux contrôles appariés restent à finir.
À ce relevé : OPEN_COMMON737/1 443séances, WAIT_COMMON408/1 443 ; deux stress
encore en file. Aucun verdict final ni promotion avant consolidation.

## Accélération des deux variantes restantes — 10 novembre 2026

À 01h36 Paris : OPEN_COMMON 1 234/1 443, WAIT_COMMON 1 018/1 443,
A2_COST25 25/1 443, OPEN_COMMON_COST25 5/1 443. Les quatre cas avancent.
Le replay, les données et les règles figées restent identiques.

L'orchestrateur additionnel `scripts/research/us_a2_parallel_remaining_20261110.py`
utilise la création exclusive du dossier de résultat pour garantir un seul
calcul par cas. Le coordinateur initial peut ensuite rencontrer ces dossiers
déjà pris : ses reçus seront conservés sous `original-coordinator-*.json`.
Après sa sortie, le nouveau coordinateur vérifiera les cinq résultats et leurs
reçus d'isolation avant la consolidation finale. Une collision de réservation
ne doit pas être confondue avec un échec du calcul économique. Le suivi
additionnel est dans `parallel-progress.json` et chaque cas garde son propre
`progress.json`. Aucun run existant n'a été interrompu.

## Bilan final — 10 novembre 2026

**Cinq cas terminés, importés dans l'historique IHM et consolidés à 03h23 Paris.**
`validation.json` PASS : compteurs globaux/annuels, horloges des exécutions,
budget de volatilité et capital final cohérents. Isolation COMPLETED par cas.
Le statut natif INCOMPLETE_COVERAGE reste conservé pour les cinq simulations.

| Variante | Capital final USD | Rendement | DD intraday max | Taux gagnant | Trades fermés |
|---|---:|---:|---:|---:|---:|
| A2, 8pb/opération | 4 519,04 | +12,98 % | −30,24 % | 35,19 % | 824 |
| Ouverture J+1, 8pb/opération | 4 327,64 | +8,19 % | −36,30 % | 31,06 % | 2 733 |
| Attente 10h30 NY, 8pb/opération | 4 360,41 | +9,01 % | −36,64 % | 32,07 % | 2 728 |
| A2, 25pb/opération | 3 386,22 | −15,34 % | −44,27 % | 35,94 % | 807 |
| Ouverture J+1, 25pb/opération | 3 178,03 | −20,55 % | −46,27 % | 31,34 % | 2 569 |

Les coûts de 8 et 25 points de base représentent 0,08 % et 0,25 % par opération,
achat comme vente. Les capitalisations finales incluent les positions ouvertes.
A2 fait mieux que le contrôle ouverture de 4,78 points de rendement et 4,13
points de taux gagnant, avec 6,06 points de drawdown en moins. Il fait aussi
mieux que l'attente horaire simple. Il s'agit de différences descriptives,
sans preuve statistique sur un échantillon indépendant. Le stress des frais
rend les deux variantes perdantes ; l'amélioration relative demeure insuffisante
pour recommander un remplacement de la stratégie existante.

Le repère Q051 per-symbol vol20/régime reste à +125,98 % et DD−24,29 % ; ce
repère n'a pas le même univers de sélection, contrairement aux contrôles appariés.
Les secours daily peuvent inclure un creux précédant une entrée tardive :
29 achats A2, 194 achats à10h30, 31 achats A2 à frais augmentés ; zéro pour
les entrées à l'ouverture. Ces limites empêchent de présenter le bilan comme
une reproduction intégrale du live. Aucun changement de production.

Livrables : `comparison.csv`, `annual-comparison.csv`, `validation.json`,
`report.json`, et `charts/capital-comparison.png`/SVG/CSV sous la racine.
Le coordinateur additionnel a conservé les reçus initiaux de réservation puis
reconstruit le statut global à partir des cinq résultats finalisés, sans
recalculer un cas. `parallel-progress.json` : COMPLETED_EXPLORATORY,
acceleration_errors vide. Aucune simulation de cette campagne ne reste en cours.

## Abandon et contrôle de non-régression — 10 novembre 2026

L'utilisateur abandonne la piste A2. Aucun nouveau run ni activation prévu.
Le code, les rapports et les reçus restent conservés pour traçabilité.

Contrôles refaits après abandon :

- 114 tests passent en50,20secondes : Winner intraday, protection daily,
  replay options, raccordement backtest, entrée daily, budget portefeuille,
  détecteur A2 et inputs économiques.
- Les16sources du manifeste économique sont inchangées depuis la campagne.
- `winner_entry_timing_source` vautNone par défaut ; la recherche des appels
  explicites ne trouve que les scripts de cette expérience et les tests.
  Sans callback, le parcours d'entrée standard est conservé.
- Les quatre fichiers partagés modifiés sont limités au backtest :
  simulator.py, winner_intraday.py, winner_daily_entry.py,
  winner_portfolio_budget.py. Aucun branchement A2 au pipeline ou au watcher.
- Le replay Q051 de référence avait reproduit à l'octet equity-daily,
  equity-5m, trades, events, risk-5m et portfolio-risk-decisions ; les paramètres
  portefeuille sont identiques. Voir reference-postvalidated/validation.json
  sous artifacts/research/us_q051_range_support_a2/20261109-v1/.
- Le correctif ultérieur de mark conserve la branche standard avec
  scheduled=False ; il ne change que le prix porté après une entrée retardée
  de recherche sur une session intraday partielle.

Conclusion : aucune régression détectée sur les parcours contrôlés ; cette
expérience ne change pas le comportement actif du pipeline/live. Cela ne
constitue pas une garantie exhaustive sur tout le projet. Les ajouts facultatifs
ne sont pas retirés par un retour arrière global, qui risquerait d'effacer des
travaux distincts. Aucun paramètre actif n'est modifié par cet abandon.
