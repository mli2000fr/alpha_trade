# US — Collectes prospectives : couverture et premier contrôle directionnel

Audit du 10 octobre 2026, terminé. Demande : vérifier les données déjà collectées
quotidiennement sur **tout l'univers tradable**, pas seulement les 11 titres GPT.
Lecture seule de `alpha_trade` ; aucun entraînement, appel fournisseur, ordre,
changement de configuration ou écriture SQL. Les seuls ajouts sont des scripts,
tests et rapports de recherche locaux.

## Conclusion

Les options sont suffisamment présentes pour commencer des diagnostics courts.
L'écart call/put du volume retardé montre une association descriptive faible
à H5/H10, à confirmer. **Aucun avantage directionnel exploitable H20 n'est
démontré.** Les premières options observées le 14 septembre ne sont pas encore
arrivées à maturité H20 selon la convention de cette étude.

Deux normalisations SEC nécessitent une remédiation avant usage : extraction
8-K/6-K très insuffisante et confusion déclarant/titre détenu dans le 13F.
Les données brutes et annexes sont conservées et permettent un travail local,
sans nouveau fournisseur. Aucune correction du code de production n'a été faite
pendant cet audit.

## Périmètre et fichiers

- Univers : `config/univers_batch/univers_filtred_tradable.txt`, **1 790 titres**.
- Fenêtre d'inventaire : réception/modification du 10 septembre au 10 octobre
  inclus ; fenêtre des observations directionnelles : avant le 10 octobre.
- Prix disponibles jusqu'au **9 octobre 2026**.
- Les principales observations quotidiennes commencent le 13/14 septembre :
  vingt séances environ, pas un mois complet d'observations indépendantes.
- Rapports :
  [inventaire JSON](../../artifacts/research/us_prospective_directional_audit/20261010-v1/inventory.json),
  [qualité des champs](../../artifacts/research/us_prospective_directional_audit/20261010-v1/field_quality.json),
  [contrôle directionnel](../../artifacts/research/us_prospective_directional_audit/20261010-v1/directional_report.json).
- Matrices auditées : `prospective_features.parquet` et
  `feature_outcome_pairs_h3/h5/h10/h20.parquet` dans le même répertoire.

## Ce qui existe réellement

Couverture = au moins une observation sur la fenêtre, **pas** couverture de
chaque titre à chaque séance. Les lignes sont des articles, contrats, barres ou
événements ; elles ne sont pas autant d'échantillons indépendants.

| Famille | Lignes / titres de l'univers | Contenu et réserve |
|---|---|---|
| Options indicatives | 231 519 / **1 651 (92,2 %)** | 196 725 IV/Greeks présents, 142 007 open interest présents ; aucun volume dans ce snapshot. Quotes indicatives, pas NBBO officiel. |
| Options : barres retardées | 188 444 / **1 569 (87,7 %)** | Volume et nombre de transactions positifs présents ; provenance `UNVERIFIED_OPRA`, recherche seulement. |
| Catalogue options versionné | 74 762 / **1 630** | Référentiel de contrats, échéances, strikes et métadonnées. Ne prouve pas une direction. |
| Disponibilité short Alpaca | 36 554 / **1 751 (97,8 %)** | Shortable/easy-to-borrow ; pas short interest, borrow fee, utilization ou shares on loan. |
| News avec sentiment | 11 581 / **1 268 (70,8 %)** | Sentiments calculés avec succès pour des journées de trade du 10/09 au 09/10. Leur présence ne prouve pas leur disponibilité historique. |
| Fenêtre d'ouverture | 2 318 572 / **1 653 (92,3 %)** | Barres SIP retardées, dont reprises de séances antérieures. Disponibles à la réception, pas rétroactivement à 09:30. Pas de nouvelle ablation ouverture ici. |
| Dépôts SEC bruts | 1 222 / **655 (36,6 %)** | 804 dépôts 8-K/A et 350 dépôts 6-K/A, plus comptes et 13F ; corpus événementiel, absence d'événement ≠ défaut de couverture. |
| Événements SEC normalisés | **4 / 4** | Beaucoup trop peu par rapport au RAW ; catégories/texte non qualifiés. |
| Consensus/révisions analystes | **0** | Les cinq tables Yahoo ont été alimentées puis purgées le 6 octobre lors du nettoyage autorisé des sources bloquées ; le batch Yahoo reste bloqué. La table Business Quant est distincte et son batch désactivé. |
| Short volume FINRA | **0** | Famille suspendue ; aucune réactivation ni analyse prédictive. |

Fondamentaux : 46 lignes SEC correspondant à des dates du mois, pour 46 titres,
avec accession ; 40 valeurs EPS/revenue, 43 ROE, 42 croissances de revenu.
Les 7 632 lignes Yahoo et 3 752 Finnhub correspondantes servent à la
capitalisation, sans EPS/revenue/ROE. Ne pas confondre capitalisation et nouvelles
features comptables. Le total de 74 572 lignes récemment récupérées inclut
beaucoup de périodes anciennes et ne représente pas autant de nouveaux dépôts.

Earnings : 93 événements datés dans le mois sur 54 titres, dont 47 paires
estimate/actual EPS et revenu. Table actuelle mutable, sans archive de chaque
révision et sans `available_at` par version : une surprise historique ne peut
pas être injectée automatiquement avant sa disponibilité réelle.

Les tables de quotes et de features journalières de sentiment contiennent aussi
des historiques anciens recalculés/récupérés récemment. La date d'événement
n'est jamais assimilée à la date de première réception.

### Pourquoi les tables analystes sont vides — vérification complémentaire

Les logs du 5 octobre prouvent que la collecte fonctionnait : 1 766 titres
avec données sur 1 798 demandés, 13 868 estimates, 6 808 tendances et autant de
révisions, 1 766 targets et 5 496 recommandations sur ce run. L'absence actuelle
ne signifie donc pas que le mois de collecte avait échoué.

Le rapport `artifacts/operations/blocked_collectors_purge/us-20261006T053041290993Z.json`
est `complete: true` et documente la suppression demandée des lignes Yahoo :
538 648 estimates, 156 592 tendances, 156 592 révisions, 74 576 targets,
223 101 recommandations et 59 journaux de run. Les cinq tables et le journal
sont désormais entièrement vides. `stock_analyst_consensus_snapshots` est aussi
vide, mais dépend du batch Business Quant désactivé ; il ne fait pas partie
des cinq tables Yahoo purgées.

`analyst_snapshot_collection` a `enabled: false` et
`status: BLOCKED_YAHOO_AUTOMATED_ACCESS`. Le launcher saute la collecte même si
la tâche Windows reste installée ; `-Force` ne contourne pas le blocage.
`business_quant_analyst_snapshot` est également désactivé, avec le statut
`REPLACED_BY_YAHOO`, qui ne signifie pas que Yahoo est encore actif aujourd'hui.
Le message de remplacement est une description historique, pas une preuve de
collecte actuelle. Aucune réactivation ni restauration n'a été faite ici.

Les données SEC ne sont pas concernées par cette purge. Vérification globale
de la base US : 8 716 dépôts, dont 8 656 avec texte ; 4 381 annexes référencées,
dont 4 169 avec contenu binaire. La réparation des normalisations peut donc
repartir du RAW conservé, sous réserve des documents manquants et identités
encore ambiguës ; elle ne justifie pas de jeter les collectes précédentes.

## Protocole du premier contrôle directionnel

Hypothèses fixées avant lecture des résultats ; aucun seuil choisi sur les pertes :

1. Sept variables simples : IV call moins put, log(1+OI call) moins log(1+OI put),
   log(1+volume call) moins log(1+volume put), sentiment net moyen, nombre
   d'articles, easy-to-borrow et shortable.
2. Snapshots options : racines standards uniquement ; call/put au **même strike
   et à la même échéance**, à ±5 % du spot, échéance commune la plus proche de
   vingt jours calendaires dans la plage 15–25 jours. Pas d'assimilation à vingt
   séances. OI et volume sont deux features distinctes.
3. Barres options : même échéance pour call/put, contrats ATM choisis par le
   collecteur existant, somme des volumes ; ce n'est **pas** un flux signé
   d'achats/ventes et ce n'est pas le volume du snapshot.
4. Décision à 09:25 New York de la séance suivant le jour local d'observation.
   `available_at` doit précéder ce cutoff. Les publications/scorings reçus après
   le cutoff ne sont pas rétrodatés. Aucun report d'un sentiment manquant à zéro.
5. News : cutoff conservateur sur le maximum des timestamps de dernière
   modification news/sentiment, en plus de la publication. Une ancienne version
   écrasée ne peut pas être reconstruite. Cela exclut des données possiblement
   connues mais dont la valeur historique n'est plus certifiable.
6. Résultat = close de la H-ième séance, séance d'entrée incluse, divisé par
   l'open d'entrée moins un. Horizons H3/H5/H10/H20. **Convention spécifique à
   cette étude**, pas substitution silencieuse aux labels H20 close-to-close
   de l'Oracle existant.
7. Chemin complet de prix split-adjusted, non rempli, OHLC cohérent et volume
   positif ; au moins 90 % du fichier couvert. D1/D10 définis sur le **plein
   univers prix-qualified de chaque date**, pas recalculés parmi les titres
   possédant une feature. D1 = plus faibles rendements signés, D10 = plus élevés.
8. Contrôle sur tout l'univers disponible ; **pas de restriction au TOP20 Oracle**.
   Le batch actuel possède 16 dates de prédiction sur la fenêtre mais leur
   `created_at` n'est pas qualifié ici comme une décision prospective historique.

Une AUC de 0,50 signifie absence de séparation dans le sens fixé. Une AUC de
0,55 **ne signifie pas 55 % de trades gagnants**, ni un rendement de portefeuille.
Pas d'inversion des signaux après observation d'une AUC inférieure à 0,50.

## Résultats descriptifs

AUC groupée D1 contre D10, score orienté comme défini ci-dessus :

| Feature | H3 | H5 | H10 | H20 |
|---|---:|---:|---:|---|
| IV call − put | 0,511 | 0,522 | 0,520 | Aucune paire arrivée à maturité |
| OI call − put, logarithmes | **0,547** | 0,540 | 0,531 | Aucune paire arrivée à maturité |
| Volume call − put, logarithmes | 0,526 | **0,547** | 0,533 | Aucune paire arrivée à maturité |
| Sentiment net | 0,399 | 0,385 | Pas d'observation mature qualifiée | Idem |
| Easy-to-borrow / shortable | 0,498 | 0,498 | 0,497 | 0,500 sur **une seule date** |

Options : 17 dates d'entrée à H3, 15 à H5 et 10 à H10. Exemple H5 volume :
5 467 titre-dates avec feature et rendement, 1 426 dans D1/D10 ; AUC journalière
moyenne 0,553, 14 des 15 dates au-dessus de 0,50. Moitiés chronologiques :
0,545 environ puis 0,549. C'est un **candidat à confirmer**, pas un signal validé :
fenêtres chevauchantes, titres répétés et un seul environnement de marché.

L'OI H3 est moins homogène : AUC approximative 0,595 première moitié contre
0,523 seconde moitié. L'IV H10 change de sens entre moitiés : environ 0,450
contre 0,542. Pas de combinaison ni de seuil optimisés après cette lecture.

News : après cutoff conservateur, 1 128 titre-dates sur 658 titres possèdent
une feature ; seulement **deux dates d'entrée matures H3, une H5 et zéro H10**.
L'AUC faible ne permet ni un rejet définitif du sentiment, ni l'inversion du
signal. Le nombre d'articles a une association sur ces mêmes dates, lui aussi
beaucoup trop peu documenté pour promotion.

À H20, seul le snapshot borrow du dimanche 13 septembre, consommable à
l'ouverture du 14 septembre, est mature le 9 octobre. **Zéro observation options
H20 mature** : une observation options du 14 septembre est consommable le 15,
et sa vingtième séance est le **12 octobre 2026**, si les cours sont présents.
Une première date mature ne suffira pas à valider la stabilité.

## Anomalies et travaux proposés, non implémentés

### SEC événements : extraction HTML insuffisante

Le handler `normalize_sec_events` cherche `ITEM n.nn` en début de ligne dans
le document brut. Les titres HTML ne suivent généralement pas ce format ; des
références internes sont parfois capturées à la place d'en-têtes. Les quatre
résultats ARCC/STLD/USPH/PSKY contiennent des débuts tels que `contained in Item`,
`and shall not be deemed` ou des balises HTML. `event_type` n'est pas une
classification économique fiable.

Prochaine remédiation possible : lecture DOM et titres/sections, typage des
événements et rattachement des annexes, tests sur corpus annoté. **Ne pas compter
les quatre lignes comme quatre surprises/guidances directionnelles validées.**

### SEC 13F : confusion filer/issuer

Le handler `normalize_sec_ownership` copie `sec_filing_raw.symbol`, symbole du
déclarant, dans `issuer_symbol`, pour toutes ses lignes détenues. Exemple :
727 lignes étiquetées TMP représentent 418 noms d'émetteurs sur une accession.
Ces 727 lignes ne sont pas 727 positions sur TMP. D'autres déclarants sont
MTB-PL, STT-PG et PRK ; 57 187 lignes n'ont aucun symbole émetteur.
`report_period` est absent dans tous les groupes examinés.

Il faut distinguer déclarant et détenu, résoudre CUSIP/identités de manière
temporelle, extraire période, unités et amendements. **Ne pas utiliser
`issuer_symbol` actuel pour créer une feature directionnelle.**

### Supervision

Les runs `COMPLETED` ne garantissent pas la qualité métier : 25 normalisations
SEC événements sont terminées, mais quatre lignes seulement sur l'univers.
Les 26 collectes SEC `COMPLETED_WITH_WARNINGS` totalisent 18 123 échecs déclarés
sur un périmètre market-wide ; ce n'est pas 18 123 titres de notre univers
manquants. Les barres options ont vingt runs avec warnings, 144 échecs cumulés
et deux runs FAILED. Ces compteurs nécessitent une qualification par entité,
sans considérer les lignes conservées comme invalides par principe.

## Limites et suite raisonnable

- Échantillon court, dates/labels chevauchants, aucune significativité corrigée
  des comparaisons multiples ; pas de neutralisation secteur/taille.
- Univers actuel, pas univers historique sans biais de survivance.
- Disponibilité locale tracée, sans certification indépendante de fraîcheur,
  précision des IV/OI ou deliverables. Quotes indicatives/OPRA non attesté.
- Prix canoniques split-adjusted, pas total returns économiquement qualifiés ;
  aucun coût, taxe, stop/TP, risque portefeuille ou PnL calculé.
- Familles suspendues pour droits/prudence non réactivées ni exploitées.

Suite proposée : réparer les deux normalisations SEC ; figer le contrôle
call/put existant sans optimisation ; conserver les collectes autorisées puis
confirmer sur de nouvelles dates matures H20 et plusieurs périodes, avec
neutralisation secteur/taille et témoins. Le pilote n'est pas un GO de trading.

## Reproduction et vérification technique

```powershell
python -u -m scripts.research.us_prospective_directional_collection_audit
python -u -m scripts.research.us_prospective_directional_check
python -m pytest tests/test_us_prospective_directional_audit.py -q --no-cov
```

Les commandes lisent la base, écrivent uniquement les artefacts de recherche
locaux et n'interrogent aucun fournisseur. `field_quality.json` conserve le
contrôle SQL complémentaire des champs et normalisations. Cinq tests
synthétiques passent : fuseau NY, absences non imputées, orientation fixe,
déciles non recalculés dans le sous-groupe et aucune promotion automatique.
