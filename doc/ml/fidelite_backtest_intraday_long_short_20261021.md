# Fidélité du backtest intraday LONG / SHORT — 21 octobre 2026

## Verdict de livraison

**Adaptateur de composants natifs livré et testé ; parité historique complète
non qualifiée. Aucune grille de paramètres ni nouvelle performance annuelle.**

GO utilisateur : renforcer d'abord la fidélité LONG et SHORT avant l'optimisation
SL/trailing/H/TP proposée. Le travail reste en recherche, sans raccordement
automatique à l'exécution PAPER/live, sans modification des modèles ou batchs.

Ce n'est pas un moteur entièrement nouveau qui remplacerait les règles de
production. `backtesting/research_intraday_native.py` appelle les primitives
existantes du moteur natif pour comptabiliser les fills et revalider des
contraintes à des instants intraday explicites. Les fichiers natifs historiques
n'ont pas été modifiés. Les anciennes expériences scellées restent inchangées.

## Ce qui est maintenant partagé et contrôlé

| Couche | Implémentation réutilisée / renforcement |
| --- | --- |
| Entrées / sorties / cash / PnL | `BacktestEngine._try_open_entries` et `_try_close_positions`, `_RunState` |
| Valorisation | Mark-to-market, gross exposure et buying power natifs |
| Taille | `PositionSizer`, puis `ConstraintChecker` ; réduction demi-taille explicite |
| Coûts | `TradingCostModel` commun ; commission, demi-spread et slippage non comptés deux fois |
| Direction | Fonctions `core.direction` communes : LONG et SHORT, SL/TP/trailing symétriques |
| Signaux | Deux clôtures5m terminées, entrée au prochain open contigu ; reconstruits et audités sur les archives parentes |
| Protections | Gap au prix d'ouverture ; collision stop/TP conservatrice ; extrêmes ne relèvent le stop qu'après la barre |
| Chronologie | La vente intrabar ne finance pas un achat au début de la même barre ; stops/échéances connus avant nouvelles entrées |
| Calendrier | Séances distinctes des barres5m ; durée d'emprunt et settlements ne comptent jamais chaque barre comme une séance |
| Historique de trading | Trackers natifs de transactions/pertes réutilisés une seule fois, sans double enregistrement |
| Défaillance | Une mutation native échouée interdit de poursuivre le même état en mémoire |

Compte sur marge, **gross plafonné à1x dans cet adaptateur**, pas autorisation
implicite de levier2x. Pour le SHORT, le crédit de la vente entre dans le cash,
mais l'equity retranche la dette de titres ; ce cash ne crée pas du pouvoir
d'achat supplémentaire. Les nouvelles entrées SHORT sous2000USD sont bloquées
par une hypothèse explicite de politique de compte, pas une certification du
tarif/règlement historique exact de chaque compte.

Le dimensionnement conserve le principe du témoin demi-position : quantité
complète bornée par le risque, le poids par titre et le budget disponible, puis
fraction entière de cette cible et revalidation des contraintes communes.
Le prix courant et un ATR de **séance antérieure** doivent être qualifiés.
Un ATR issu de la journée encore en cours n'est pas utilisé à l'insu du test.
La sortie H reste décidée par la stratégie appelante à partir du calendrier.
L'adaptateur accepte un ensemble d'expirations à l'open et interdit une entrée
sur une campagne ainsi expirée. Pas de renforcement dans cette livraison.

### Ce que le partage de composants ne signifie pas

Ce n'est **pas encore tout `PortfolioBuilder` rejoué en intraday**. Son contexte
de régime, ses corrélations, filtres événementiels, contrôles de drawdown et
contraintes de compte doivent être exportés/qualifiés pour cette stratégie et
cet instant. Le ledger `OraclePortfolioLedger` et `OraclePortfolioSession`
existants sont journaliers ; aucune barre5m n'a été déguisée en jour pour les
faire artificiellement passer.

Les confirmations, le suivi des stops5m et le traitement des événements sont
des politiques explicites de l'adaptateur ; ce ne sont pas les reçus du watcher
courtier. Ni les latences d'armement, ni les exécutions partielles, la profondeur,
les suspensions et les liquidations de marge du courtier ne sont certifiées.

## Dividendes et splits

Les événements doivent être fournis avec identité, date effective et provenance
qualifiées. Rien n'est appliqué automatiquement depuis une table brute.

- Split : quantité multipliée par le ratio ; entrée, stop, plus haut/bas et
  niveaux de protection divisés par ce ratio. Le cash et le flux initial ne
  sont pas débités une deuxième fois.
- Dividende cash : droit positif LONG / obligation négative SHORT pour les
  titres détenus **avant** la date ex. L'achat à la date ex n'en bénéficie pas.
- Le droit/obligation entre dans l'equity à la date ex, mais le cash n'est
  transféré qu'à la date de paiement. Le règlement est idempotent.
- Identifiant rejoué identique : pas de double paiement. Identifiant réutilisé
  avec un autre contenu : erreur.
- Fraction issue d'un split nécessitant cash-in-lieu, fusion/changement
  d'identité ou modalités inconnues : refus explicite, pas de valeur inventée.

Cela livre des mécanismes testés, **pas la qualification de tous les événements
historiques** ni leur raccordement automatique au calendrier du portefeuille.

## Deux niveaux de preuve pour les cours et les quotes

1. **Simulation historique sur événements de marché** : une quote SIP
   téléchargée aujourd'hui, correctement datée dans le passé, peut servir à
   un backtest avec une hypothèse de diffusion/latence documentée. Ne pas la
   rejeter uniquement parce qu'elle a été téléchargée tard.
2. **Rejeu exact de ce que notre application savait alors** : il faut en plus
   le reçu historique et son horodatage réel de réception. Un téléchargement
   actuel ne reconstitue pas ce reçu. Ne jamais antidater `collected_at`.

Le premier niveau améliore la simulation ; il ne constitue pas le second.
Dans les deux cas, une quote de clôture ne sert pas à tarifer une entrée à9:40.
L'inventaire exige quote SIP datant d'au plus300secondes, bid/ask et tailles
valides, empreinte et chemin d'archive, puis revue du reçu brut. Une ligne
candidate n'est pas automatiquement une preuve qualifiée de liquidité/fill.

Mode strict de l'adaptateur : reçus de quote, contexte de risque natif et
couverture des opérations sur titres ; pour SHORT, statut/emprunt et modalités
de coût supplémentaires. Le contexte de risque est lié au côté, à la config,
au cash/positions et à la quantité approuvée. Un secteur inconnu ne devient
pas un secteur neutre. Ces reçus restent à produire par une chaîne qualifiée ;
le simple fait de renseigner des booléens dans un JSON ne prouve pas son origine.

Mode `strict=False` : tests ou recherche sous hypothèses, **jamais promotion**.
Le coût de sortie sans quote de sortie est marqué hypothétique, même si l'entrée
avait une quote. Le statut de composant n'est pas un certificat de parité globale.

## Emprunt SHORT : convention de calcul explicite

Le moteur canonique sait appliquer un taux constant annualisé sur le notionnel
d'entrée et un nombre de séances/252. Ce taux est une hypothèse par défaut,
pas une archive de facture courtier.

Le mode strict peut consommer un reçu de taux constant **uniquement** s'il
certifie explicitement cette convention `ANNUAL_252_ENTRY_NOTIONAL` et sa
couverture. Le taux qualifié est appliqué au titre, sans fuite vers un autre
titre. Les conventions variables, calendrier360, notionnel de marché quotidien,
locates/arrondis et rappels ne sont pas convertis silencieusement en252.
Elles restent à raccorder. Un statut manquant n'est jamais réputé ETB gratuit.
Cette restriction évite de qualifier abusivement les coûts HTB Alpaca réels.

Même le PAPER Alpaca comporte des différences avec le réel : impact, latence,
file d'attente, frais et dividendes ne sont pas entièrement reproduits.
[Documentation Alpaca PAPER](https://docs.alpaca.markets/us/docs/paper-trading).
Pour les règles/prêts/marge, utiliser le contrat propre au compte et à la période,
pas rétroactivement un tarif actuel.
[Documentation Alpaca marge/SHORT](https://docs.alpaca.markets/us/docs/margin-and-short-selling).

## Inventaire historique réellement exécuté

Archives Oracle parentes : `us_oracle_campaign/20261020-v1`. Même cohorte
qualifiée de **213 campagnes**, 119 en2025 /94 en2026 ; recherche CatBoost
PATH_H20 OOS TOP10, pas LightGBM de production. Premier signal LONG et premier
signal SHORT de chacune : **426 cas techniques**, pas426 occasions indépendantes.
2024 absent. Couverture future complèteJ..J20 et univers courant : les biais de
sélection/survivants de l'expérience parente restent présents.

Deux lectures bornées de `alpha_trade` seulement, chacune en transaction
`REPEATABLE READ / READ ONLY`, suivie de `ROLLBACK`. Aucun nouvel appel fournisseur.

| Source | Lignes dans la fenêtre /72titres | Conclusion bornée |
| --- | ---: | --- |
| `stock_quote_snapshots` | 31630 sur72titres | **0/426** cas avec quote fraîche candidate à l'entrée, même au seul niveau événement de marché ; pas une bande intraday |
| `stock_borrow_status_snapshots` | 1008 sur72titres | **1/213** cas SHORT avec snapshot candidat dans les24h avant décision ; statut à relire, pas frais/locates/recalls qualifiés |
| `corporate_actions_events` | 0 | Journal applicatif vide pour cette fenêtre ; ne signifie pas absence d'événement |
| `corporate_action_source_events` | 20 sur13titres | 13 `cash_dividend` Alpaca,7 `dividend` BusinessQuant ; source staging distincte, pas automatiquement réconciliée/appliquée |

Le premier inventaire des trois tables est réutilisé à l'identique pour le
bilanv2 après vérification de l'empreinte des candidats : pas seconde collecte,
pas modification de la base. Le complément staging est un second inventaire
READ ONLY séparé, avec sa propre empreinte et ses timestampsUTC.

Les20lignes staging n'attestent pas une couverture annuelle exhaustive. La
valeur normalisée seule ne qualifie ni devise, date de paiement, doublons entre
fournisseurs, changements d'identité, ni payload original. Aucun split présent
dans ces20lignes ne signifie pas que la période n'a connu aucun split.

**Aucun des426cas ne satisfait aujourd'hui toutes les conditions de parité
complète.** Ce n'est ni426trades perdants ni un échec du modèle : ce sont des
preuves manquantes dans cette qualification plus exigeante. Le rapport n'a
calculé aucun nouveau PnL ni remis en cause arithmétiquement l'ancien compte
de recherche ; son interprétation reste conditionnelle.

## Tests et audit

**83tests passent** :41nouveaux et42de non-régression des expériences parentes.
Les nouveaux couvrent notamment LONG/SHORT natifs, conservation du cash/PnL,
frais une fois par jambe, quotes strictes, coût d'emprunt/convention, jours
distincts des barres5m, split/dividendes, dates ex/paiement, refus après échec,
échéance, anti-doublon des trackers et protection conservatrice. Soixante
sorties aléatoires sont comparées à la formule indépendante des flux signés.

Audit séparé des426signaux et des compteurs temporels par implémentation scalaire,
sources et fichiers hachés : **`PASS_COMPONENT_TESTS_AND_READ_ONLY_INVENTORY`**.
Même assistant ; pas revue humaine indépendante, pas certificat de tous les
chemins natifs ou d'exécutions de courtier.

## Artefacts et reproduction

Dossier faisant foi : `artifacts/research/us_intraday_fidelity/20261021-v2`.

- `protocol.json`, `prepared.json`, `candidates.parquet`, `coverage.parquet`.
- `snapshot.json`, `quotes.parquet`, `borrow.parquet`, `actions.parquet`.
- `readiness.parquet`, `report.json`, `test-results.xml`, `final-audit.json`.
- `source-actions.parquet`, `source-actions.json` : complément staging distinct.

Le prototypev1 est conservé mais **supplanté parv2** avant livraison. Ses sources
initiales sont copiées dans `20261021-v1/source-prototype`. Les correctionsv2
distinguent le niveau événement du reçu d'application, lient le taux d'emprunt
à sa convention et synchronisent les trackers natifs. Aucun résultat ancien
de portefeuille n'est écrasé ni recalculé discrètement.

Commandes pour un **nouveau dossier** :

```powershell
python -u -m scripts.research.us_intraday_fidelity_readiness --phase prepare --output artifacts/research/us_intraday_fidelity/NOUVEAU
python -u -m scripts.research.us_intraday_fidelity_readiness --phase snapshot --output artifacts/research/us_intraday_fidelity/NOUVEAU
python -u -m scripts.research.us_intraday_fidelity_readiness --phase report --output artifacts/research/us_intraday_fidelity/NOUVEAU
python -m pytest tests/test_research_intraday_native.py tests/test_us_intraday_fidelity_readiness.py tests/test_us_oracle_pyramiding.py tests/test_us_oracle_campaign.py -o addopts='' --junitxml=artifacts/research/us_intraday_fidelity/NOUVEAU/test-results.xml
python -u -m scripts.research.us_intraday_fidelity_audit --output artifacts/research/us_intraday_fidelity/NOUVEAU
python -u -m scripts.research.us_intraday_fidelity_action_inventory --output artifacts/research/us_intraday_fidelity/NOUVEAU
```

`snapshot` et le complément lisent SQL ; les autres commandes fonctionnent sur
les artefacts. Les commandes refusent les résultats terminés à écraser.

## Suite bornée, sans optimisation prématurée

1. Qualifier la possibilité de récupérer des **quotes historiques autour des
   entrées et sorties** pour une simulation de marché, avec hypothèse de
   diffusion déclarée ; ne pas promettre des reçus d'application rétroactifs.
2. Exporter le contexte natif régime/secteurs/corrélations et décisions pour
   cette stratégie intraday, puis comparer les premières divergences de règles.
3. Qualifier les sources/actions historiques, leurs payloads et modalités de
   paiement, puis brancher uniquement les événements admis à l'adaptateur.
4. Pour SHORT : source historique de statut ETB/HTB, frais, locates et rappels ;
   à défaut, conserver un scénario explicitement hypothétique, pas « complet ».
5. Valider le suivi/armement prospectif PAPER avant tout déploiement. Rien n'est
   activé dans cette livraison, et aucune collecte payante n'est engagée.

Le but est une simulation mieux contrôlée, pas une promesse de reconstruire à
l'identique des transactions jamais passées. La grille144LONG+144SHORT n'a pas
été lancée ; aucun entraînement, SQL écrit, ordre ou changement de production.
