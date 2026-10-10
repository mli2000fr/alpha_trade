# Options FR : POC transactions MiFIR + référentiel FIRDS

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Décision et état au 6 octobre 2026

Suite au GO, un batch quotidien partiel pour tout l'univers FR est maintenant
implémenté : `fr_options_mifir_trade_sync`, livré désactivé en attendant
l'activation utilisateur. Voir [collecte quotidienne](options_mifir_collecte_quotidienne.md).
Les mentions « POC manuel » ci-dessous concernent le pilote historique, pas
ce nouveau collecteur avec orchestration et notifications.

**POC technique confirmé sur trois sous-jacents, collecte complète non activée.**
Le service est `service/fr/mifir_options_poc.py` ; les rapports le nomment
`fr_options_mifir_delayed_trades_poc`. Aucun import/lecture de fichier Excel,
aucune requête SQL, table, tâche Windows, modification de modèles ou branchement
au backtest/live. Tout reste fichier de recherche avec `ml_eligible=false`.

À la demande de l'utilisateur, le service, les tests et la documentation de
l'ancien POC Excel sont retirés. Ses artefacts existants restent conservés
comme preuves historiques, sans nouvel usage dans ce POC. Ne pas confondre
les conditions MiFIR avec une autorisation rétroactive sur les Excel.
Le message du batch `fr_options_snapshot` explique la nouvelle piste et ses
limites ; `enabled=false` et son statut de fournisseur complet non qualifié
restent inchangés. Le POC est manuel, sans notifications de batch planifié.

## Deux sources indépendantes

1. [Euronext — TRADES FILES](https://marketdata.euronext.com/data-reporting-service/trades-file),
   catégorie `EQUITY_INDEX_DERIVATIVES`, période `PREVIOUS_TRADING_DAY`, Paris `PAR`.
   Le formulaire public publie la route de téléchargement employée ; aucune URL
   privée devinée. Le téléchargement est un **ZIP contenant un CSV**, pas un CSV
   nu. Un préambule copyright contient des virgules : il ne doit pas servir
   d'en-tête. Le lecteur repère `TradingDateTime,...` et vérifie le schéma.
2. **ESMA FIRDS**, registre public, interrogation ciblée des ISIN effectivement
   rencontrés, MIC `XMON`, enregistrements parents publiés / dernières références
   reçues. Aucun téléchargement de tous les Full options. 80 ISIN par requête,
   au plus 2 000 ISIN distincts dans ce POC. Il a fallu 13 requêtes pour cette séance.
   Toutes les réponses JSON brutes et les reçus sont archivés. Une réponse
   tronquée ou contenant des instruments non demandés fait échouer.

Le POC passe par la publication publique du registre, pas par un flux Optiq,
les fichiers commerciaux de calcul de marges ou un fournisseur de courtage.
Le référentiel actions FIRDS existant du projet ne suffit pas à lui seul :
il portait principalement sur les actions `FULINS_E`, pas sur ces options.

### Droits d'usage : ne pas mélanger les sources

Les [conditions spécifiques Delayed Trade Data](https://www.euronext.com/delayed-data-terms-conditions)
prévoient l'utilisation gratuite sans restriction générale hors distribution.
Les conditions applicables à la redistribution doivent être respectées, notamment
pour une diffusion payante. Le périmètre retenu ici est **usage interne Alpha Trade**,
pas revente de données. Les conditions publiques ont été examinées, pas un
contrat de redistribution négocié ; revalider avant tout usage différent.

Le [legal notice ESMA Registers](https://registers.esma.europa.eu/publication/legalNoticePage)
autorise la reproduction sauf indication contraire, avec attribution ESMA et
conditions relatives aux transformations/publications. Conserver cette provenance
et ne pas laisser croire à une validation du produit par ESMA.

Ce POC distingue autorisation d'usage de qualification du contenu : des données
réutilisables ne sont pas automatiquement fiables/exhaustives ou éligibles au ML.

## Résultat réel : séance du 5 octobre 2026

Le ZIP MiFIR reçu contient **40 514 lignes** toutes options et futures dérivés
Paris confondus, pour 1 071 identifiants distincts. Ce n'est pas le nombre
de transactions actions ni le nombre de contrats des trois sociétés.

- 993 identifiants ont la forme et le checksum ISIN valides ; les 993 sont
  retrouvés dans FIRDS/XMON, sans ambiguïté dans cette observation.
- 78 identifiants sont numériques, non-ISIN, pour **101 lignes**. Ils sont
  conservés bruts et listés mais **non joints à FIRDS**. Aucune assimilation
  automatique à un ISIN, aucun identifiant inventé ; leur nature reste à qualifier.
- 3 lignes `CANC` apparaissent dans le fichier source global. Aucune n'appartient
  aux transactions retenues sur les trois sous-jacents dans ce POC.
- Après jointure FIRDS et contrôles, 335 lignes / 138 séries d'options du pilote
  sont acceptées pour **inspection technique**, pas pour le ML.

| Sous-jacent FIRDS | Symbole pilote | Lignes acceptées | Séries traitées | Calls / puts (lignes) | Somme quantités call / put déclarées |
|---|---|---:|---:|---:|---:|
| FR0000120321 — L'Oréal | OR.PA | 21 | 14 | 13 / 8 | 78 / 42 |
| FR0000121972 — Schneider Electric | SU.PA | 221 | 92 | 80 / 141 | 1 079 / 2 526 |
| FR0000120644 — Danone | BN.PA | 93 | 32 | 46 / 47 | 430 / 207 |

Ce périmètre englobe les options trouvées via leur sous-jacent FIRDS, notamment
des mini-options, contrairement au premier test limité aux classes standard
de l'Excel. Les chiffres plus élevés ne sont donc pas une amélioration ML.
319 lignes portent un multiplicateur 100 et 16 un multiplicateur 10 ; un
multiplicateur global 100 ferait des erreurs. Les échéances vont du 09/10/2026
au 16/06/2028. Ce résultat sur une séance / trois sociétés ne démontre pas
la couverture des 330 titres FR ou de l'univers actif ni un historique complet.

**Les sommes de quantités ne sont pas encore certifiées en nombre de contrats.**
Les deux champs d'unité du CSV étaient vides sur toute la séance. Le POC garde
`quantity_unit_qualified=false` et `put_call_contract_volume_ratio=null`.
L'audit documentaire ultérieur précise que ces champs concernent la mesure
des matières premières : leur absence ne prouve pas une quantité options invalide.
La certification reste bloquée faute de mapping actuel et de réconciliation
indépendante, pas simplement à cause de ces champs vides. Voir
[qualification univers et unités](options_mifir_qualification.md).
Ne pas utiliser directement ces sommes comme volume en actions, notionnel EUR
ou ratio directionnel validé. La présence d'options de multiplicateurs différents
et de trades wholesale exige une définition explicite des agrégats futurs.

## Jointure et caractéristiques

```text
Trade MiFIR : MifidInstrumentID (ISIN), Venue=XMON
   → référence FIRDS unique (ISIN, MIC)
   → CFI option OC / OP + drv_option_type CALL / PUTO
   → drv_underlng_isin = ISIN de la société pilote
   → strike, devise, expiration, multiplicateur, style, livraison
   → ligne de recherche en quarantaine
```

FIRDS emploie **PUTO**, pas `PUT`. Le code normalise vers `PUT` tout en
conservant `source_option_type=PUTO`. Il contrôle la cohérence avec CFI `OP...` ;
`CALL` doit correspondre à `OC...`. Le code ne lit ni ne déduit le strike
d'une chaîne de nom/ticker. Les futures sont exclus grâce au CFI.
Source : [spécifications fonctionnelles FIRDS](https://www.esma.europa.eu/document/firds-reference-data-functional-specifications-v210).

Exemple effectivement observé : ISIN option `FREX03807457`, L'Oréal sous-jacent
`FR0000120321`, CALL, strike 410 EUR, expiration 20/11/2026, multiplicateur 100.
Le trade montre prix 3,24, quantité déclarée 1, transaction
`2026-10-05T08:49:43.100566Z`, publication `08:49:43.100650Z`.
Un prix d'option n'est pas le prix de l'action et n'indique pas le sens du trade.

## Traitement conservateur des événements

Les lignes sont regroupées par `(Venue, VenueOfPublication, TradeUniqueIdentifier)`.

- Doublons exactement identiques : un seul exemplaire retenu.
- `CANC` dans le groupe : groupe exclu, même si l'original précède/suit l'annulation.
- Modification différente de `-` (dont amendement) : groupe mis à l'écart,
  sans tenter de reconstruire la dernière version sans specification complète.
- Même identifiant avec plusieurs contenus non identiques : conflit, groupe exclu.
- Prix/quantité non finis, nuls/négatifs, prix autre que monétaire EUR,
  timezone absente, publication avant transaction/après observation : exclusion.
- Déféré, agrégation de plusieurs transactions ou prix manquant : exclusion
  de l'échantillon technique ; conserver la ligne brute et le motif.
- Dates antérieures à l'admission ou postérieures à l'expiration : exclusion.
- Références multiples non identiques : ambiguïté, pas de sélection opportuniste.

Le traitement n'est **pas encore un reconstructeur complet RTS/MMT** : liens
entre corrections à identifiants distincts, annulations reçues le lendemain,
agrégations et report différé nécessitent qualification. Les tests synthétiques
vérifient les règles conservatrices ; la séance réelle ne teste pas toutes
les situations. Un futur collecteur devra reconsidérer des journées déjà agrégées
quand une correction tardive arrive, sans créer de doublons.

## Horodatages, référence courante et PIT

`TradingDateTime` = exécution ; `PublicationDateTime` = publication initiale du
trade. Cette dernière n'est **pas** l'heure de disponibilité sur le site différé :
un écart de microsecondes dans le CSV ne signifie pas un accès gratuit temps réel.
Le dispositif annonce 15 minutes après publication et disponibilité au moins
24 heures. Il ne fournit pas ici un historique 2018–2026 arbitrairement demandable.

Les reçus enregistrent l'heure UTC locale après réception. `available_at` du
résultat vaut l'observation après réception des deux sources ; aucune rétrodatation.
`firds_publication_at` reste distinct de la date du trade et de notre collecte.
Même si les références retrouvées ont ici une publication antérieure aux trades,
une référence **courante** ne prouve pas sa version historiquement consultable
à chaque ancienne décision. `historical_pit_qualified=false` et
`historical_reference_pit_qualified=false` restent imposés.

La récupération prospective est donc concrète ; un backtest historique sur
plusieurs années ne devient pas possible avec cette seule séance.

## Contenu absent

Open Interest, bid/ask et tailles, carnet, IV/Greeks complets, côté agresseur,
historique des deliverables/ajustements ne sont pas fournis/qualifiés ici.
Le POC ne reconstitue pas l'OI à partir de quantités échangées et n'utilise pas
de settlement/IV Excel en fallback. Un put négocié peut être vendu, couvert
ou inclus dans un spread : le volume put/call seul ne prouve pas D1/D10.

## Exécution, archives et supervision

Commande manuelle réseau, depuis F:\projets :

```powershell
python -u -m service.fr.mifir_options_poc --download-public-poc
```

La période est **la séance précédente du service**, pas une date choisie par
l'utilisateur. Lire `trade_dates` dans le rapport ; ne pas présumer la date
du PC ni de J−1 calendaire. Le mode réseau est un opt-in, jamais implicitement
déclenché lors de l'import. Aucun batch en cours n'est modifié.

Archives sous `artifacts/fr/research/mifir_options_poc/<horodatage>-<identifiant>/` :

- `source_page.html` et son reçu : formulaire / conditions consultés ;
- `trades.zip`, reçu avec SHA256 et disclaimer CSV ;
- `firds-*.json`, reçus SHA256 par requête et `firds_documents.json` ;
- `contracts.json`, `accepted.json`, `rejected.json` ;
- `report.json` : couverture, erreurs, exclusions, unités/PIT/licence et statut.

Un premier essai a signalé les identifiants non-ISIN. Le téléchargement réussi
est `20261005T223618-bd9deed4` ; sa première analyse excluait les puts avant
normalisation correcte de `PUTO`. La relecture corrigée de ses mêmes archives,
**sans nouveau téléchargement**, est `20261005T223817-bdbf18b3`.
Les tentatives et leurs rapports ne sont pas effacés ni maquillés.

```powershell
python -u -m service.fr.mifir_options_poc --trades-zip artifacts/fr/research/mifir_options_poc/20261005T223618-bd9deed4/trades.zip --reference-json artifacts/fr/research/mifir_options_poc/20261005T223618-bd9deed4/firds_documents.json
```

Relecture offline : pas de réseau, nouveau dossier, mêmes règles de traitement.
Les nouveaux reçus d'observation ne sont pas une nouvelle collecte fournisseur.
Une erreur produit un rapport `FAILED` avec son message et un exit non nul ;
les fichiers déjà reçus restent disponibles. Pas de contournement de 403/429,
login ou CAPTCHA ; TLS vérifié. Budgets : 16 Mo ZIP, 64 Mo CSV, 100 000 lignes,
2 000 ISIN, 80 ISIN/requête, 400 documents/réponse, délai 0,5 s entre requêtes.
Pas de dépendance optionnelle tableur : uniquement bibliothèque standard et
les imports normaux du package `service` déjà présents dans le projet.

## Tests et suite

Tests dédiés : `tests/test_fr_mifir_options_poc.py`. Ils couvrent préambule CSV,
ZIP, jointure, CALL/PUTO et CFI, multiplicateurs, identifiants, ambiguïtés,
annulations, amendements, doublons, prix/quantités/horaires, droits d'accès
techniques bornés, exclusion des futures, absence de réseau implicite,
quarantaine et rapport d'échec. Les tests ne prétendent pas certifier le flux.
Résultat de vérification : **27 tests dédiés passants**, plus **12 tests existants
du runner FR passants** (39 au total sur cette sélection). Pas de revendication
de suite complète ni de notification/installation Windows testée ici.

Prochaine étape avant activation d'une **collecte partielle clairement nommée** :
qualifier unités et corrections, répéter quelques séances, élargir la couverture
FR par sous-jacent ISIN, définir reprise et déduplication temporelle. Le besoin
complet `fr_options_snapshot` reste bloqué faute d'OI/bid-ask/ajustements qualifiés.
L'absence de ces champs n'interdit pas une future collecte partielle de trades,
mais aucun gain de direction ou d'amplitude n'est démontré par ce POC.
