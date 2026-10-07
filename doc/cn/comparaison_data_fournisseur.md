# Comparaison des fournisseurs de données Chine pour Alpha-Trade

## Décision opérationnelle du 22 septembre 2026

Le premier socle est désormais **gratuit** : BaoStock fournit le référentiel, le calendrier, les barres, les statuts ST/suspension, les facteurs et les indices. AKShare est réservé aux enrichissements validés endpoint par endpoint. RQData et Tushare ne sont plus des dépendances du POC ; ils pourront être évalués plus tard pour les données directionnelles.

Cette décision permet d’entraîner l’Oracle Extreme d’amplitude à H5/H10/H15/H20. Elle ne prétend pas résoudre D1/D10. Les sections Tushare ci-dessous restent un inventaire des données payantes potentiellement utiles, pas le plan d’implémentation actif.

Voir : [Sprint 6 — sources gratuites BaoStock](./sprint_6_sources_gratuites_baostock.md).

---

## Objet du document

Ce document compare les données accessibles avec le niveau **Tushare Pro 10 000 points** aux données américaines actuellement collectées ou manquantes dans Alpha-Trade.

L’objectif n’est pas de reproduire en Chine les expériences déjà menées sur le marché américain avec les mêmes familles de données. La recherche vise prioritairement des informations :

- historiquement disponibles et datées ;
- exploitables sans fuite temporelle (`point-in-time`, ou PIT) ;
- absentes des données US actuelles ;
- structurellement liées au sens futur d’un mouvement extrême ;
- utilisables pour distinguer D1 et D10 après sélection par un Oracle Extreme.

Les prix, volumes, indicateurs techniques, fondamentaux classiques, sentiments génériques et données short classiques ne doivent pas être considérés comme nouveaux simplement parce qu’ils proviennent d’un autre marché.

## Résumé de la recommandation

Les trois familles Tushare les plus intéressantes pour une recherche D1/D10 réellement nouvelle sont :

1. les prévisions sell-side historiques permettant de reconstruire un **consensus analystes PIT** et ses révisions ;
2. les flux institutionnels quotidiens publiés dans le **Dragon and Tiger List** ;
3. la microstructure chinoise des limites de cours : verrouillage, rupture, file d’ordres et répétition des limites.

Les autres familles sont secondaires, redondantes avec les expériences US ou dérivées de données déjà testées.

## Comparaison principale

| Donnée Tushare accessible avec 10 000 points | Profondeur annoncée | Situation équivalente aux États-Unis | Batch Alpha-Trade concerné | Écart réel | Priorité D1/D10 |
|---|---:|---|---|---|---:|
| Prévisions sell-side structurées (`report_rc`) | Depuis 2010 | Snapshots actuels, mais pas d’historique profond de tous les vintages et révisions | `analyst_snapshot_collection` | Manque US majeur : révisions EPS, bénéfice, revenus et objectifs connues à chaque date historique | **P0** |
| Recommandations et objectifs de cours des courtiers | Plus de dix ans selon Tushare | Informations courantes partielles, sans historique PIT complet | `analyst_snapshot_collection`; ancien `business_quant_analyst_snapshot` désactivé | Nouveau : upgrades, downgrades et révisions d’objectifs | **P0** |
| `top_inst` : achats et ventes institutionnels du Dragon and Tiger List | Depuis 2005 | Aucun équivalent journalier et attribué | Aucun batch équivalent | Très nouveau : flux signé, attribué et déclenché par un mouvement anormal | **P0** |
| `top_list` : titres et motifs de mouvements anormaux | Depuis 2005 | Scanners de mouvements, mais pas de publication officielle équivalente | Aucun équivalent exact | Spécifique à la Chine et directement compatible avec Oracle Extreme | **P0** |
| Limites haussières, baissières et ruptures de limite | Historique selon l’endpoint | Les actions US n’ont pas le même régime quotidien de limites | Aucun équivalent exact | Nouvelle structure de marché | **P0** |
| Heure de verrouillage et de rupture, reliquat d’ordres et succession de limites | Historique structuré dans les listes spécialisées | L’historique des imbalances US manque ; seules certaines données d’ouverture ont été testées | `oracle_opening_window_sync`; `auction_imbalance_sync` désactivé ou bloqué | Beaucoup plus riche que le simple prix et volume d’ouverture US | **P0** |
| Recommandations mensuelles des courtiers (`broker_recommend`) | Historique mensuel | Pas de portefeuille consolidé de convictions | `analyst_snapshot_collection` n’est pas équivalent | Nouveau, mais fréquence faible | P1 |
| Enquêtes et visites institutionnelles | Selon couverture Tushare | Pas de collecte US équivalente | Aucun | Peut révéler l’attention institutionnelle avant un mouvement | P1 |
| Transactions de blocs avec acheteur et vendeur | Historique daté | Pas de collecte US consolidée des blocs signés | `latest_quotes_sync` ne remplace pas cette donnée | Nouveau, sous réserve d’auditer la qualité du sens acheteur/vendeur | P1 |
| Prévisions de résultats publiées par l’émetteur (`forecast`) | Historique daté par `ann_date` | Guidance présente dans certains filings, mais extraction historique incomplète | `sec_edgar_incremental`; expériences guidance E21 fermées | Plus directement structuré que les PDF et 8-K US | P1 |
| Marge par titre : financement acheté, remboursé et encours | Depuis 2010 | Pas de série US quotidienne centralisée identique | Aucun équivalent exact | Plus précis que le short volume, mais famille déjà partiellement explorée | P2 |
| Prêt de titres, quantité vendue et encours | Depuis 2010 selon endpoint | Historique de borrow difficilement disponible à bas coût | `borrow_status_snapshot`; `finra_short_volume_sync` | Plus complet, mais appartient à une famille déjà étudiée | P2 |
| Rachats d’actions | Depuis 2011 | Présents dans les filings SEC, mais moins directement structurés | `sec_edgar_incremental`; `sec_corporate_events_normalize` | Structuration supérieure, sans constituer une nouvelle famille | P2 |
| Variations de participations des actionnaires | Historique daté | Form 4 et autres filings SEC | `sec_edgar_incremental`; normalisations SEC | Même famille que les insiders US déjà testés | P3 |
| Nantissement d’actions | Depuis 2004/2014 selon endpoint | Pas d’équivalent aussi courant aux États-Unis | Aucun batch direct | Spécifique à la Chine, potentiellement utile comme risque baissier | P2 |
| Déblocage d’actions restreintes | Historique | Partiellement reconstructible depuis les filings | `sec_edgar_incremental` | Plus structuré, utile comme pression vendeuse potentielle | P2 |
| Flux par taille de transaction | Depuis 2010 | Volumes, quotes et order-flow partiels | `latest_quotes_sync`; expériences volume et microstructure | Sens généralement inféré, pas nécessairement institutionnel ou certifié | P3 |
| Coût moyen des positions et taux de gagnants (`cyq_perf`) | Depuis 2018 selon la documentation récente | Aucun dataset natif US | Aucun | Calcul algorithmique depuis prix, volume et rotation ; information non observée directement | Faible |
| Distribution des « chips » et coûts de détention | Historique selon endpoint | Aucun équivalent natif | Aucun | Donnée dérivée par un modèle Tushare, pas un registre réel des portefeuilles | Faible |
| OHLCV, ajustements, calendrier et indicateurs quotidiens | Historique complet | Déjà disponible | `daily_bars_sync`, `corporate_actions_sync`, `latest_quotes_sync` | Aucun apport directionnel nouveau | Exclure |
| Fondamentaux et ratios | Historique complet | Déjà alimentés principalement depuis SEC | `sec_edgar_incremental`, `market_cap_sync`, normalisations SEC | Doublon fonctionnel | Exclure |
| Calendrier et annonces de résultats | Historique | Déjà collecté | `earnings_calendar_sync` | Doublon fonctionnel | Exclure |

## Consensus analystes : ce que fournit réellement Tushare

### Consensus pré-calculé et consensus reconstruit

Tushare fournit, via l’interface `report_rc`, les prévisions individuelles issues des rapports sell-side. Le fournisseur ne doit pas être supposé fournir uniquement une valeur agrégée prête à l’emploi nommée « consensus ».

Cette granularité est préférable pour Alpha-Trade : elle permet de reconstruire le consensus qui était réellement disponible à chaque date, au lieu d’utiliser une valeur actuelle susceptible d’avoir été révisée rétrospectivement.

Les champs annoncés comprennent notamment :

- le titre ;
- la date du rapport (`report_date`) ;
- la période fiscale visée ;
- le chiffre d’affaires prévisionnel ;
- le résultat opérationnel prévisionnel ;
- le bénéfice net prévisionnel ;
- l’EPS prévisionnel ;
- le PE prévisionnel ;
- le rendement prévisionnel ;
- le ROE prévisionnel ;
- l’EV/EBITDA prévisionnel ;
- la recommandation ;
- l’objectif de cours minimal et maximal ;
- l’institution ou le courtier ;
- la date de mise à jour Tushare.

L’historique est annoncé depuis 2010. L’interface exige formellement au moins 8 000 points ; le niveau 10 000 points permet son extraction avec les quotas supérieurs associés aux données spéciales.

Références :

- [Présentation Tushare des données sell-side](https://tushare.pro/document/1?doc_id=291)
- [Tarification et niveaux de points](https://tushare.pro/document/1?doc_id=290)

### Reconstruction PIT du consensus

Pour chaque titre, date de décision `J` et période fiscale :

```text
prévisions avec report_date <= J
→ regrouper par courtier et période fiscale
→ conserver la dernière prévision connue de chaque courtier
→ agréger seulement ces dernières prévisions
→ produire le consensus disponible à J
```

Les variables suivantes peuvent être produites :

| Variable | Définition |
|---|---|
| `consensus_eps_median` | Médiane des dernières prévisions EPS disponibles |
| `consensus_eps_mean` | Moyenne des dernières prévisions EPS |
| `consensus_eps_dispersion` | Écart-type ou MAD entre prévisions |
| `consensus_net_profit` | Médiane des bénéfices nets prévisionnels |
| `consensus_revenue` | Médiane des chiffres d’affaires prévisionnels |
| `consensus_target_price` | Médiane des objectifs de cours |
| `target_upside` | Objectif médian divisé par le cours disponible à `J` |
| `analyst_count` | Nombre de courtiers contribuant au consensus |
| `positive_revision_count` | Nombre de courtiers ayant relevé leur prévision |
| `negative_revision_count` | Nombre de courtiers ayant abaissé leur prévision |
| `revision_breadth` | `(révisions haussières - révisions baissières) / total` |
| `eps_revision_5d` | Variation du consensus EPS sur cinq jours |
| `eps_revision_20d` | Variation du consensus EPS sur vingt jours |
| `eps_revision_60d` | Variation du consensus EPS sur soixante jours |
| `dispersion_change` | Convergence ou divergence récente des analystes |
| `rating_upgrade_balance` | Nombre d’upgrades moins nombre de downgrades |
| `target_revision` | Variation récente de l’objectif médian |
| `forecast_freshness` | Âge de la prévision la plus récente |

### Contrat PIT obligatoire

Tushare indique que les données sell-side sont mises à jour le soir. Une prévision portant la date `J` ne doit donc pas être utilisée pour une décision prise avant sa disponibilité effective.

La règle prudente initiale doit être :

```text
report_date = J
available_at = prochaine séance de marché J+1
```

Avant tout backtest, il faudra vérifier si un horodatage de publication plus précis est présent et, si oui, remplacer cette règle prudente par le véritable instant de disponibilité.

Le pipeline devra également :

- conserver les lignes brutes sans les écraser ;
- séparer date du rapport, période fiscale et date d’ingestion ;
- conserver une seule dernière prévision par courtier et période lors de chaque snapshot ;
- ne jamais utiliser une révision publiée après la date de décision ;
- distinguer FY1, FY2, trimestres et exercices fiscaux décalés ;
- empêcher une nouvelle prévision de remplacer rétroactivement l’ancienne ;
- versionner les snapshots de consensus reconstruits ;
- enregistrer les règles d’agrégation et le nombre de contributeurs.

### Différence entre les interfaces financières

| Interface | Signification |
|---|---|
| `report_rc` | Prévisions individuelles des analystes et courtiers ; base du consensus reconstruit |
| `forecast` | Prévision de résultats publiée par l’entreprise elle-même |
| `express` | Résultats préliminaires publiés par l’entreprise |
| `income` | Résultats comptables réalisés |
| `broker_recommend` | Sélection mensuelle de titres par les courtiers |

La source prioritaire pour les révisions de consensus est `report_rc`, pas `forecast`.

## Pourquoi les batchs US actuels ne remplacent pas les données chinoises P0

### `analyst_snapshot_collection`

Ce batch collecte prospectivement les informations analystes accessibles aujourd’hui. Il construit un historique à compter de son activation, mais il ne fournit pas rétroactivement :

- la prévision connue à chaque date depuis 2010 ;
- la date de chaque révision historique ;
- la trajectoire complète des consensus EPS et revenus ;
- la dispersion historique entre courtiers ;
- la succession des objectifs de cours et recommandations.

L’historique de `report_rc` est donc complémentaire et réellement nouveau.

### `sec_institutional_ownership_normalize`

Les données américaines 13F sont généralement trimestrielles et publiées avec retard. Elles mesurent principalement une détention. Elles ne remplacent pas `top_inst`, qui décrit les achats et ventes institutionnels associés à une séance de mouvement anormal.

### `finra_short_volume_sync`

Le volume FINRA marqué short ne révèle pas :

- l’identité ou la catégorie des principaux acheteurs et vendeurs ;
- leur achat net ;
- leur concentration ;
- le motif réglementaire de sélection du titre ;
- les principaux desks acheteurs et vendeurs.

Il ne constitue donc pas l’équivalent du Dragon and Tiger List.

### `oracle_opening_window_sync`

Ce batch mesure le comportement d’ouverture, mais pas les mécanismes propres au marché chinois :

- limite quotidienne ;
- verrouillage à la limite ;
- rupture de limite ;
- nombre de verrouillages ;
- taille du reliquat d’ordres ;
- succession de séances à la limite.

### `sec_edgar_incremental`

SEC EDGAR contient de nombreuses informations mais sous forme de filings et d’annexes à détecter et extraire. L’interface chinoise `forecast` fournit directement des champs structurés tels que la date d’annonce, le type de prévision, les bornes de variation du bénéfice, les montants prévisionnels, le résumé et la cause annoncée.

Référence : [interface Tushare `forecast`](https://tushare.pro/document/2?doc_id=45).

## Données vendues séparément des 10 000 points

Le niveau 10 000 points ne débloque pas automatiquement toutes les familles Tushare. Certaines permissions restent indépendantes.

| Extension séparée | Tarif individuel affiché | Intérêt pour Alpha-Trade | Recommandation |
|---|---:|---|---|
| Questions-réponses officielles Shanghai et Shenzhen | 500 CNY/an | Corpus structuré et horodaté entre investisseurs et direction | À acheter après validation des blocs P0, ou avec le premier POC si le budget le permet |
| Bibliothèque complète de rapports de courtiers | 500 CNY/an | Texte intégral des rapports | Non indispensable tant que les prévisions structurées suffisent |
| Annonces et PDF | 1 000 CNY/an | Plus de dix ans d’annonces | Faible priorité car proche de SEC EDGAR |
| Enchère d’ouverture | 500 CNY/an | Donnée d’enchère quotidienne | Ne pas acheter sans confirmation écrite de la profondeur historique disponible |
| Minutes historiques | 2 000 CNY/an | Prix et volume intraday depuis 2009 | Ne pas acheter pour D1/D10 avant preuve qu’une microstructure supplémentaire est présente |

Les questions-réponses de Shenzhen disposent d’un historique annoncé depuis 2010 et contiennent la question, la réponse, la date et l’heure de publication.

Référence : [interface Shenzhen Interactive Easy](https://tushare.pro/document/2?doc_id=367).

## Sous-ensemble recommandé pour l’expérience

Il est inutile d’intégrer immédiatement toutes les interfaces du forfait. La première campagne doit se limiter aux blocs qui apportent une information nouvelle.

### Bloc `CN_P0_ANALYST_REVISIONS`

```text
révision EPS, bénéfice et revenus
variation de l’objectif de cours
upgrade et downgrade
dispersion du consensus
nombre de courtiers
fraîcheur des prévisions
largeur des révisions positives/négatives
```

### Bloc `CN_P0_INSTITUTIONAL_FLOW`

```text
achat institutionnel
vente institutionnelle
achat net
concentration des achats et ventes
nombre d’acheteurs et vendeurs
motif Dragon and Tiger
type de desk ou institution lorsqu’il est disponible
```

### Bloc `CN_P0_LIMIT_STRUCTURE`

```text
limite haute ou basse
heure du premier verrouillage
nombre de ruptures
heure du dernier verrouillage
taille du reliquat
nombre de séances consécutives à la limite
montant et variation de l’enchère
motif et thème du mouvement
```

### Bloc `CN_P1_SUPPLY_PRESSURE`

```text
transactions de blocs
décote ou surcote du bloc
déblocage d’actions
nantu00issement
réduction ou augmentation de participation
rachats d’actions
```

## Ordre expérimental recommandé

La campagne doit éviter de mélanger toutes les familles dès le départ :

1. construire un univers A-shares historique sans biais de survivance ;
2. appliquer les règles chinoises de suspension, titres `ST`, IPO récentes, T+1 et limites de cours ;
3. construire un Oracle Extreme chinois indépendant des modèles US ;
4. mesurer la baseline D1/D10 sur le TOP20 Oracle ;
5. tester uniquement les révisions de consensus ;
6. tester uniquement les flux institutionnels ;
7. tester uniquement la structure des limites ;
8. tester les interactions pré-enregistrées entre ces trois blocs ;
9. ajouter la pression d’offre uniquement en seconde vague ;
10. mesurer en Walk-Forward l’AUC, la précision conditionnelle, la couverture, la stabilité par année et la performance économique après coûts.

## Critères de décision

Une famille ne sera pas retenue simplement parce que son importance de feature est élevée. Elle devra :

- améliorer la séparation D1/D10 hors échantillon ;
- améliorer plusieurs folds et plusieurs années ;
- conserver un effet après neutralisation secteur, taille et régime ;
- fournir une courbe précision/couverture exploitable avec abstention ;
- améliorer le résultat économique net après coûts ;
- rester disponible au moment réel de la décision ;
- ne pas dépendre d’un petit nombre de titres ou d’événements exceptionnels.

## Décision d’achat recommandée

Pour la première campagne :

```text
Tushare 10 000 points                     1 000 CNY/an
Questions-réponses officielles (option)     500 CNY/an
```

Le niveau 15 000 points n’ajoute pas de nouvelle famille de données par rapport à 10 000 points ; il augmente principalement les plafonds d’appels sur les données spéciales. Il ne doit être acheté que si le téléchargement rencontre effectivement les limites du niveau 10 000.

La priorité reste la validation des données `report_rc`, `top_inst`/`top_list` et des événements de limite avant tout achat supplémentaire.

