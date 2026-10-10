# Sprint 5 France — clôture technique et décision de gate

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Date : 2 octobre 2026. Ce document clôt **l'exécution technique de collecte et de staging** du Sprint 5, mais **pas son gate d'admission au canonique / ML**. Verdict formel : `NO_GO_CANONICAL_AND_ML`. Le verdict est recalculable avec `python -m service.fr.sprint5_gate` et archivé dans `artifacts/fr/eodhd/backfill_2016/sprint5_gate.json`.

**Décision ultérieure de périmètre :** le premier univers canonique/ML/backtest FR ne cherchera pas à admettre les dates 2016–2017. Elles demeurent dans l'archive brute et les audits, mais la validation nécessaire au GO limité porte sur **2018 et après**, avec date d'entrée propre à chaque instrument et sans lever les autres gates.

L'[audit complémentaire des intervalles ESMA, des prix 2016, des radiés et des actions sur titres](sprint_5_intervalles_esma_prix_radies_actions_2026-10-02.md) suit l'avancement du GO limité sans lever ce veto.

**Décision actualisée du GO limité 2018–2026 :** le [rapport de finalisation](sprint_5_finalisation_go_limite_2018_2026.md) porte maintenant le verdict `GO_RESEARCH_J1`. Le manifeste contient 561 001 barres de 330 titres, dont 36 radiés (10,91 %). L'historique public Euronext corrobore 5 733 séances exactes de 34 radiés récents. Aucune promotion canonique n'a eu lieu : production, live et serving restent interdits.

**Suite — GO limité demandé :** le [protocole de sous-ensemble vérifié](sprint_5_sous_ensemble_verifie.md) préqualifie 490 codes, dont 167 radiés dans le snapshot courant. Un contrôle indépendant ESMA FIRDS a depuis observé 306 de leurs ISIN sur `XPAR` à au moins une des quatre dates vérifiées ; ce sont toujours des **candidats à vérifier**, pas des instruments admis : 0 possède toutes les preuves requises pour le canonique.

## 1. Résultat effectivement obtenu

Le fournisseur EODHD est accessible avec le forfait Historical All-World. Le backfill `2016-01-01 → 2026-10-01` couvre **1 552 codes `Common Stock` en EUR** dans la liste Paris `PA` : **630 actifs aujourd'hui et 922 radiés aujourd'hui**. Les trois familles EOD, splits et dividendes sont archivées par code, avec hash SHA-256 et heure d'observation. Les **4 656 payloads** ont été indexés dans `fr_raw_payloads` ; l'import répété a gardé le même total.

La migration France `0004_fr_provider_staging` ajoute un staging **sans `instrument_id`** : `fr_provider_universe_staging`, `fr_provider_bars_staging`, `fr_provider_actions_staging`, `fr_staging_progress`. La migration `0005_fr_staging_quality_version` versionne le classifieur (`fr_eod_v2`) afin qu'une correction des règles force un reclassement reproductible. Toutes ces tables sont uniquement dans `alpha_trade_fr`. L'ingestion complète et sa seconde exécution ont donné :

| Contrôle en base France | Résultat |
| --- | ---: |
| Symboles provider en staging | 1 552 |
| Payloads indexés et checkpoints terminés | 4 656 / 4 656 |
| Barres EOD en staging | 2 101 100 |
| Actions sur titres en staging | 4 940 : 428 splits + 4 512 dividendes |
| Barres `VALID` selon qualité mécanique, avec volume positif | 1 899 128 |
| Barres à volume nul (`ZERO_VOLUME`) | 193 867 |
| Autres barres en quarantaine | 8 105 |
| Barres dans `stock_bars_daily` canonique | **0** |
| Instruments/listings FR canoniques | **0 / 0** |

L'idempotence a été vérifiée **après reclassement v2** : la seconde exécution du staging a sauté les **4 656** payloads déjà validés et n'a ajouté aucune ligne. Le gate exige désormais que les 4 656 checkpoints portent la version actuelle du classifieur. L'import ne crée aucun symbole négociable ni statut historique fictif. Les barres portent `observed_at` et `available_at` au moment réel du backfill ; elles ne prétendent pas être observables en 2016. Le volume EODHD est ajusté des splits, distinct d'un volume brut inconnu. Le `adjusted_close` du fournisseur intègre aussi les dividendes et n'est pas une feature historique PIT automatique.

## 2. Quarantaine prix et actions sur titres

| État de la barre staging | Lignes | Traitement |
| --- | ---: | --- |
| `VALID` | 1 899 128 | Prix OHLC plausible, volume positif et séance XPAR selon bibliothèque ; **pas** encore MIC/identité/PIT validés. |
| `ZERO_VOLUME` | 193 867 | OHLC plausible mais aucun volume négocié déclaré ; conserver pour enquête, ne pas traiter comme séance tradable. Le volume EODHD est split-ajusté, sans preuve indépendante de sa valeur. |
| `PLACEHOLDER` | 5 237 | Prix `999999.9999` et volume nul ; rejet du canonique. |
| `BAD_OHLC` | 1 657 | Haut/bas incompatibles avec ouverture/clôture ; rejet. |
| `BAD_PRICE` | 16 | Prix nul, manquant ou non valide ; rejet. |
| `NON_SESSION` | 1 195 | Date hors calendrier XPAR ; rejet ou enquête sur la place réelle. |

Le rapport brut compte 1 197 barres hors calendrier : deux chevauchent une autre catégorie de la table et le staging les classe par **motif prioritaire**. La quarantaine totalise ainsi **201 972** barres, dont 193 867 pour volume nul. Une barre sans volume peut correspondre à une absence de transaction ou à une convention fournisseur : elle n'est pas automatiquement un prix corrompu, mais elle ne démontre pas une exécution possible. Il n'y a ni date dupliquée par code, ni hash corrompu, ni ligne EOD hors fenêtre. **100 codes** n'ont aucune barre EOD sur la fenêtre. Exemple vérifié : `ALADO.PA` contient un prix artificiel daté du 25 décembre 2019, jour fermé à Paris.

L'[audit corporate actions](../../service/fr/corporate_actions_audit.py) a comparé, sans les modifier, les ratios de split aux clôtures voisines : **368/428** sauts de prix sont compatibles à ±25 %, **47** discordent, **9** n'ont que des prix voisins trop éloignés et **4** n'ont pas de prix de part et d'autre. Le seuil de 25 % sert seulement à trier les vérifications ; il ne valide pas économiquement tous les 368. Parmi les dividendes, **245** sont annoncés dans une devise autre que EUR et **2 942** n'ont pas de date de déclaration renseignée. Aucun facteur d'ajustement, conversion de devise ou événement fusion/droit n'a été reconstruit arbitrairement.

## 3. Pourquoi le gate reste NO_GO

1. **Identité historique insuffisante.** **602** codes n'ont pas d'ISIN dans la liste fournisseur. Un appel supplémentaire à l'[API de mapping EODHD](https://eodhd.com/financial-apis/id-mapping-api-cusip-isin-figi-lei-cik-%E2%86%94-symbol) a récupéré 2 177 correspondances `PA`, mais **0 des 602** lacunes n'a été résolue. Les 950 lignes avec ISIN ne représentent que **872 ISIN distincts** ; **77 ISIN** sont partagés entre **155 codes** (souvent changements de ticker à étudier). Seuls **795 codes** ont un ISIN non partagé dans ce snapshot (491 actifs, 304 radiés), mais cela n'est pas un univers PIT historiquement complet. Exclure simplement les autres éliminerait beaucoup de radiés et créerait un biais de survie.
2. **MIC historique non entièrement prouvé.** `PA` est le code de place EODHD et ne prouve pas le segment de chaque titre : [Euronext distingue XPAR, Growth Paris `ALXP` et Access Paris `XMLI`](https://www.euronext.com/sites/default/files/2026-04/European%20Offering%20-%20OTC%20Settlement%20Flows%20English%20Version_0.pdf). L'audit des [fichiers officiels ESMA FIRDS Full/Delta](https://www.esma.europa.eu/sites/default/files/library/esma65-8-5014_firds_-_instructions_for_download_of_full_and_delta_reference_files.pdf) a trouvé **306 ISIN candidats présents sur XPAR à au moins un des quatre instantanés de 2020, 2022, 2024 et 2025**, dont 207 aux quatre. Il s'agit d'une **preuve ponctuelle** ISIN/MIC, mais pas encore d'une période de cotation continue validée pour chaque barre. Le staging et les `instrument_listings` canoniques restent donc à **0** ; aucune ligne n'a été inventée.
3. **Dates de cotation/radiation non prouvées.** « Actif » et « radié » sont les statuts du snapshot fournisseur actuel, pas des événements datés. La première/dernière barre observée n'est pas une date officielle d'IPO, suspension ou radiation. Le symbole peut avoir changé ou été réutilisé.
4. **Disponibilité historique non prouvée.** `observed_at` est l'heure du backfill 2026. Pour 2016–2025, aucune heure de publication et aucune version *as-of* des prix/corrections n'est disponible dans cette archive. Un backtest pourrait étudier une convention **assumée** « barre J utilisable J+1 » après validation explicite, mais ce n'est pas une preuve PIT exacte ; cette convention doit être stockée séparément de l'heure observée.
5. **Prix indépendant et actions sur titres.** Un classeur [Euronext Cash Markets Daily Reports](https://live.euronext.com/en/resources/statistics/nextday-cash) ne donne que des statistiques agrégées. En revanche, l'[export individuel Euronext](https://live.euronext.com/en/popout-page/getHistoricalPrice/FR0010208488-XPAR) a permis de comparer 509 séances sur chacun de sept titres actifs pré-enregistrés, depuis octobre 2024. Six concordent entièrement en OHLC ; `CCN.PA` présente quatre écarts de champ, dont une clôture différente de **2 €** le 7 septembre 2026. Un nouveau pilote Yahoo, avec chaîne TLS Windows corrigée sans désactiver la vérification, couvre les 10 actifs pré-enregistrés sur 2018–2025 : 17 408 séances communes et 63 écarts OHLC sur 69 632 champs comparés. Les 10 radiés pré-enregistrés restent absents de Yahoo. Une collecte distincte de l'historique public Euronext couvre désormais 34 radiés récents et ferme le gate anti-survivance de recherche, sans fermer les gates canonique et économique. Les années 2016–2017 sont hors du premier gate. Les 47 splits discordants, les dividendes non EUR et les autres événements complexes empêchent d'appliquer en bloc une série split-only/total-return.

Ces obstacles sont des **données de référence manquantes**, pas un échec réseau ou un défaut SQL. Le fichier `sprint5_gate.json` expose chaque drapeau ; l'archive et le staging sont complets, mais `identity_pit_verified`, `canonical_complete`, `historical_publication_verified`, `independent_price_reference_verified` et `corporate_actions_economically_checked` restent à faux.

## 4. Marche à suivre avant le Sprint 6 effectif

1. Poursuivre la référence titre **indépendante et datée** déjà amorcée avec ESMA : partir d'un Full, appliquer les `DLTINS` quotidiens et invalidations, vérifier ISIN/MIC/segment et événements d'entrée, suspension et radiation, y compris les radiés. Réconcilier les 602 sans ISIN et les 77 groupes multi-codes ; documenter chaque fusion/scission de mapping. Les quatre Full espacés ne prouvent pas les intervalles complets.
2. Étendre la comparaison indépendante Euronext récente aux périodes **2018–2024** et aux radiés via une source historique appropriée ; examiner et statuer sur les écarts `CCN.PA` avant toute promotion de ce titre. Vérifier aussi les splits ; ne pas utiliser Yahoo comme vérité canonique. Les années 2016–2017 sont conservées en archive/recherche mais ne bloquent plus ce premier GO limité.
3. Examiner les 47 discordances de split, 245 dividendes non EUR et dates de déclaration absentes ; définir explicitement les conventions de prix brut, split-only et total-return, puis des facteurs versionnés.
4. Choisir et approuver le niveau PIT voulu : **strict as-of** (nécessite une source historique de publications/corrections) ou **recherche avec hypothèse conservatrice J+1** clairement étiquetée et jamais présentée comme exacte. Garder `observed_at` historique de collecte séparé de toute disponibilité hypothétique.
5. Seulement ensuite créer les `instrument_listings` vérifiés et exécuter une promotion canonique sur le sous-ensemble admissible ; répéter la promotion, auditer `(instrument_id,session_date)` et produire la couverture par année, segment et statut.

Le **Sprint 6 — univers tradable PIT** peut être préparé en code, mais il ne peut pas recevoir un GO de données historiques sur ce seul staging. Cette séparation évite qu'un univers apparemment large soit bâti sur des symboles contemporains et des segments non prouvés.

## 5. Vérifications

- Archive complète : `artifacts/fr/eodhd/backfill_2016/summary.json` et `quality_report.json` ; tous les hashes vérifiés.
- Idempotence de l'archive et du staging : seconde exécution sans nouvel appel/fichier pour l'archive et **4 656 payloads sautés** dans le staging.
- Alembic FR : `0005_fr_staging_quality_version` sur `alpha_trade_fr` uniquement ; aucun batch planifié US/CN touché.
- Tests ciblés France et non-régressions calendrier/PIT/US/CN/client EODHD : **124 passés** lors de la clôture initiale, un avertissement de dépréciation existant. Le prototype ESMA a ses tests dédiés ; leur validation finale est à rapprocher du bilan courant.
- Données sous licence : les payloads restent sous `artifacts/` ignoré par Git ; ne pas les redistribuer.
