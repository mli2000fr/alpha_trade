# Couverture CALL/PUT — audit du 29 octobre 2026

Lecture seule SQL et réponses brutes archivées, sans appel fournisseur, ordre,
écriture SQL ou changement des batchs/configurations. Cutoff du second passage :
29 octobre 2026 à 20:21:19 UTC, soit 21:21:19 Paris. Séance examinée : **28 octobre**,
derniers runs terminés disposant de données à cet instant, pas collecte du 29.

## Univers et périmètre collecté

Les deux batchs actifs `oracle_options_indicative_snapshot` et
`options_delayed_bars_sync` prennent `config/univers_batch/stock_bars_daily.txt`,
**13 105 titres**, sans `max_symbols`. Les **1 790 titres** de
`config/univers_batch/univers_filtred_tradable.txt` sont tous inclus. Le TOP20
du filtre après Oracle ne limite pas ces collectes.

La collecte ne conserve pas une chaîne exhaustive : cibles d'échéance 5/10/20
jours et tolérance, strikes sélectionnés, prix de référence du sous-jacent.
Le snapshot applique une fenêtre de strikes ±20 %, un échantillonnage de surface,
des contrôles bid/ask et un minimum d'OI de 10 lorsqu'elle existe. Il ajoute une
paire directionnelle commune lorsque possible. Les barres retardées prennent
un CALL et un PUT proches du cours par échéance retenue, pas tous les contrats.

La référence SIP de découverte provient des trente dernières minutes d'une
séance disponible. Sans référence, le collecteur saute le titre avant la demande
de chaîne. Cela ne prouve pas l'absence d'options pour ce titre.

## Données du dernier passage sur l'univers tradable

| Disponibilité | Titres |
| --- | ---: |
| Au moins un snapshot conservé | 1 529 / 1 790 |
| Au moins une barre de volume 30Min enregistrée par le run | 1 079 / 1 790 |
| Paire OI compatible au même strike, 15–25 jours, distance <=5 % du cours J | 813 |
| Paire de volumes CALL/PUT compatible, 15–25 jours | 547 |
| Deux features combinées qualifiées par le constructeur canonique | **447** |

Répartition exclusive du diagnostic (ordre de priorité des causes, pas causes
mutuellement exclusives dans les données brutes) :

| Cause retenue | Titres |
| --- | ---: |
| Deux features qualifiées | 447 |
| Aucun snapshot conservé dans le dernier run | 261 |
| Snapshot présent mais aucune barre de volume dans le dernier run | 473 |
| Données présentes, paire OI requise absente | 338 |
| Données présentes, paire de volumes requise absente | 271 |
| Total | 1 790 |

Les trois premiers motifs sont déterminés avant la recherche de paires ;
un titre sans volume peut aussi ne pas avoir de paire OI qualifiée.

### Les 261 titres sans snapshot conservé

Les réponses brutes permettent de distinguer :

- **144** : pas de référence SIP récente, donc chaîne non demandée. Exemples
  AAGIY, ACA, ACVA, ADDYY, AMWD. À investiguer/réparer, sans inventer de prix.
- **87** : chaîne retournée non vide mais aucun contrat conservé après sélection
  et contrôles. Exemples ACEL (4 contrats bruts), AHRT (2), AKR (6), AMSF (6).
- **30** : réponse de snapshots vide dans la fenêtre demandée. Exemples AGNCP,
  AGNT. Cela ne certifie pas l'absence de toute option sur toutes les échéances.

## Compteurs des batchs et limites

Snapshot : `oracle_options_indicative_snapshot-20261028211115-b80fd0ef`,
statut `COMPLETED_WITH_WARNINGS`, 36 172 contrats conservés, deux échecs techniques
sur l'univers large : ALL.PRI et FTW.WS. Ils n'expliquent pas les manques généraux.
Le compteur `symbols_without_options` inclut aussi les contrats éliminés par
les contrôles ; ne pas le présenter comme « sociétés dépourvues d'options ».

Volumes : `options_delayed_bars_sync-20261028210004-5f8b6315`, statut `COMPLETED`,
27 357 barres persistées, zéro échec technique. Le compteur `covered_underlyings`
de 5 605 est alimenté dès la sélection de contrats au catalogue, avant réception
des barres ; il ne mesure pas la couverture réelle des volumes. Absence de barre
peut correspondre à aucun échange sur les contrats retenus ou à une absence de
données fournisseur ; cet audit ne convertit jamais l'absence en volume nul.

`stock_option_snapshots.volume` est volontairement NULL : ce endpoint ne fournit
pas le volume quotidien. Le filtre lit ce volume dans `stock_option_bars_delayed`.
Le flux options indicatif et les volumes historiques `UNVERIFIED_OPRA` ne sont
pas des prix d'exécution certifiés ni une preuve de pouvoir prédictif.

Prochaine investigation utile : références SIP manquantes et couverture des
volumes réellement reçus, puis paires du TOP20 exact. Ne pas forcer des scores
aux titres sans données ni abaisser les exigences après observation des prix.

## Preuves reproductibles

Script `scripts/operations/audit_options_universe_coverage_20261029.py`.
Rapport `artifacts/operations/options_universe_coverage/20261029T202119Z/report.json`.
Liste complète `artifacts/operations/options_universe_coverage/20261029T202119Z/tradable_coverage.csv`.
Le premier passage à `20261029T201918Z` est conservé ; le second ajoute
l'attribution des snapshots manquants à partir des payloads bruts.

## Vérification fournisseur des 144 références manquantes

À la demande suivante, les **144 mêmes titres** ont été testés pour la même
séance du **28 octobre 2026**, depuis le 29 octobre 20:33:31 UTC (21:33 Paris).
Le rapport canonique ci-dessus est inchangé ; nouveau dossier indépendant :
`artifacts/operations/missing_option_reference_probe/20261029T203331Z/`.

| Source vérifiée | Cours exact du 28 octobre trouvé |
| --- | ---: |
| `stock_bars_daily`, toutes sources présentes pour ces titres/date | 0 / 144 |
| Alpaca SIP, bougie journalière brute, recherche de la journée entière | 0 / 144 |
| EODHD `/eod/{symbole}`, plage 28 octobre uniquement | **97 / 144** |

Les trois requêtes SIP groupées (48 symboles) répondent sans données de cette
séance, pas par refus d'accès. Le défaut initial n'est donc pas limité à la
fenêtre de trente minutes : l'élargissement au quotidien ne les récupère pas
dans ce test. Aucun fallback IEX, aucun symbole remplacé, `asof=-` conservé.

Les 144 requêtes EODHD sont allées à leur terme via le client existant et son
contrôle de quota/circuit, sans refus d'autorisation. **97** titres ont une
seule barre de date exacte, OHLC bruts positifs/finis et cohérents, volume
strictement positif ; **47** ne retournent aucune barre pour cette date.
Leur absence n'est pas déclarée équivalente à une radiation. Il reste à
qualifier identités, changements de ticker et dernière cotation pour les 47.
Les prix `adjusted_close` ne remplacent jamais les prix bruts dans ce test.

Exemples retrouvés : AAGIY (36,37 USD), ADDYY (88,44), ADRNY (36,59),
ADYEY (9,11), AKZOY (22,27), valeurs de clôture retournées pour le 28 octobre.
Exemples sans barre : ACA, ACVA, AMWD, ATKR, AVB, SEMR, LBRDK.

**97 prix disponibles ne signifient pas 97 chaînes d'options disponibles.**
Aucun nouveau catalogue/contrat d'options n'a été demandé, aucune feature ni
sélection n'a été publiée, aucun ordre envoyé. Le raccordement de cette
source alternative à la découverte des contrats n'est pas réalisé par ce test.
Les données restent en fichiers de diagnostic, sans écriture dans les tables
de marché ni modification de la configuration ou des batchs. Seuls les fichiers
de preuve et la comptabilité normale de quota EODHD ont été écrits.

Script : `scripts/operations/probe_missing_option_references_20261029.py`.
Rapport détaillé : `report.json` et réponses publiques dans `raw/` du dossier
ci-dessus, sans en-tête d'authentification ni clé API.
Liste complète par titre : `coverage_144.csv` dans ce même dossier.

## Vérification ponctuelle Yahoo des mêmes 144 titres

À la demande explicite de l'utilisateur, vérification ponctuelle le 29 octobre,
depuis 20:47:33 UTC (21:47 Paris). Aucun batch Yahoo réactivé ni changement
de sa politique d'accès : ce diagnostic ne constitue pas une permission du
fournisseur pour la collecte automatique. Aucun SQL, ordre ou import de prix.

Endpoint public chart Yahoo, journée du 28 octobre uniquement, une requête
par titre, pause de 1,5 seconde, aucune authentification, aucun retry, rotation
d'hôte ou contournement d'accès. Arrêt prévu sur HTTP 401/403/429 ; aucun de ces
refus rencontré. Les 144 requêtes sont terminées, aucun titre non testé.

| Disponibilité chez Yahoo | Titres |
| --- | ---: |
| Une barre OHLC de date exacte, prix positifs/cohérents | **97** |
| Historique retourné mais aucune barre de cette séance | **20** |
| Historique non fourni pour le symbole demandé | **27** |

Les 97 titres sont **exactement les mêmes que chez EODHD**, sans complément
pour les 47 autres. Les 97 métadonnées déclarent USD et les 97 volumes sont
positifs. Les symboles projet à point ont été demandés avec tiret chez Yahoo,
avec vérification du symbole retourné ; pas de substitution par une autre
cotation, autre devise, autre émetteur ou autre date.

Les prix ne sont pas tous identiques : écart absolu médian des closes Yahoo
contre EODHD environ 0,00000445 %, 95e percentile **0,423 %**, maximum
**1,064 % sur COVTY** (33,25 Yahoo contre 32,90 EODHD). Cela ne tranche pas
la vérité d'un fournisseur. Les conventions d'ajustement et l'identité ne
sont pas certifiées pour l'usage automatique par la seule présence d'un prix.
Les volumes des deux fournisseurs ne sont pas fusionnés.

Ce résultat porte sur des prix d'actions ; il ne confirme pas la disponibilité
de contrats CALL/PUT chez Alpaca pour les titres retrouvés.

Script : `scripts/operations/probe_yahoo_missing_references_20261029.py`.
Preuves : `artifacts/operations/yahoo_missing_option_reference_probe/20261029T204733Z/`
(`report.json`, `raw/`, `coverage_144.csv`, `comparison_eodhd.json`).

Suite autorisée le 29 octobre : [rattrapage Yahoo ciblé après Alpaca](options_yahoo_reference_recovery.md)
implémenté et activé par défaut dans les deux collecteurs d'options. Les bilans
ci-dessus restent ceux des collectes antérieures, avant ce raccordement.
