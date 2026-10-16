# Consensus EODHD et macro producteurs publics — 10 octobre 2026

## Décisions et preuves réelles

**Mise à jour du 11 octobre 2026** : après souscription Calendar & News signalée
par l'utilisateur, compte et `/calendar/trends` répondent HTTP 200. Les constats
403 ci-dessous sont des preuves datées antérieures, pas l'accès actuel.
[Collecteur EODHD dédié et smoke](../operations/eodhd_consensus_snapshot.md).
Yahoo reste bloqué ; aucun historique PIT ancien n'est ajouté par l'abonnement.

Mise à jour du même jour : l'utilisateur a de nouveau désactivé la collecte
analystes Yahoo US (`enabled: false`, `BLOCKED_YAHOO_AUTOMATED_ACCESS`).
Les données restaurées sont conservées ; Calendar & News est envisagé pour
construire des snapshots quotidiens, sans souscription ni activation confirmée.
Le support EODHD, dans la réponse transmise par l'utilisateur, confirme les
estimations courantes, points de comparaison et compteurs de révisions dans
ce forfait, mais exclut un véritable historique as-known/PIT sur tous les plans.
La qualification des droits de stockage/ML et de la couverture reste à faire.

- Consensus EODHD : **accès non disponible avec la clé actuelle**, pas de nouvel achat.
- Macro : premier périmètre producteur-direct BLS/H15 livré, archivé en base US et planifié.
- Short volume : maintien de `enabled: false` et `BLOCKED_FINRA_PREDICTIVE_USE` ; aucune dépense.
- Aucun modèle, ordre ou moteur de régime modifié. Les changements préexistants de `config.yaml` ne font pas partie de cette livraison.

La qualification publique réduit les incertitudes de licence ; ce document n'est pas une garantie juridique générale. L'usage doit rester conforme aux conditions et à la situation personnelle/professionnelle réelle.

## 1. Consensus : produit, accès et droits avant achat

Route examinée : `/api/calendar/trends`, avec `symbols=AAPL.US`. Elle fournit des estimations EPS/revenue et des éléments de tendance/révision. Elle relève des offres Fundamentals, All-In-One ou Corporate Events Calendar & News Feed, pas de la simple offre historique de prix. [Documentation du produit](https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits), [offres](https://eodhd.com/pricing).

Le test borné réalise deux GET et aucun achat : compte **200**, consensus **403**. Ce 403 prouve l'échec d'accès actuel, pas sa cause commerciale exacte. Le type mensuel/annuel d'abonnement n'identifie pas les produits activés. Rapport : `artifacts/research/eodhd_consensus/qualification-20261010-v1/report.json`. Ni valeurs de consensus, ni coordonnées du compte, ni token archivés.

Les conditions EODHD permettent stockage/manipulation/analyse privée non commerciale pour les utilisateurs non professionnels ; elles restreignent partage, redistribution et usages commerciaux. Une confirmation spécifique reste demandée pour ML local, modèles dérivés et conservation après résiliation. Ne pas réactiver Yahoo comme solution de contournement. [Conditions EODHD](https://eodhd.com/financial-apis/terms-conditions).

### Attention au faux historique PIT

Les lignes sont ancrées sur des périodes fiscales ; leur date n'est pas la date à laquelle un investisseur connaissait le consensus. Les paramètres de fenêtre ne reconstruisent pas d'anciens snapshots. Les points « il y a 7/30/60/90 jours » ne prouvent pas un historique intégral de vintages. La réponse est organisée par groupes de symboles, avec des nombres pouvant être des chaînes. Pas d'entraînement historique avant qualification de ce contrat.

### Demande à transmettre au support, pas encore envoyée

Contact officiel : support@eodhistoricaldata.com ; cas commercial : sales@eodhistoricaldata.com.

1. Quel produit exact autorise `/calendar/trends` sur notre compte existant ? Pourquoi le GET AAPL.US retourne-t-il 403 ? Peut-on obtenir un échantillon autorisé sans achat préalable ?
2. Confirmer les droits de collecte automatisée et d'archivage quotidien append-only, avec sauvegardes, pour notre univers US complet d'environ 1 790 titres.
3. Confirmer l'analyse quantitative, le ML local et la conservation des données et modèles dérivés après résiliation, pour une application personnelle non redistribuée.
4. Préciser les limites de symboles par requête, quotas, couverture EPS/revenue, nombres d'analystes, révisions, unités et périodes fiscales.
5. Fournissez-vous les heures exactes de disponibilité, historiques de révision et corrections ? Sinon, confirmer que l'on reçoit seulement un état courant à archiver prospectivement.
6. Chiffrer le produit minimal adapté ; aucun achat ne sera fait avant confirmation écrite du produit et des droits.

Ensuite seulement : petit pilote de couverture, identités/périodes/unités, puis batch dédié sur tout l'univers. L'envoi éventuel de ces données à un LLM externe nécessite une qualification distincte : il n'est pas inclus dans ce pilote.

Rejouer le contrôle technique dans **un nouveau dossier** :

```powershell
python -m service.eodhd.consensus_qualification --output-dir artifacts/research/eodhd_consensus/qualification-NOUVELLE-DATE
```

Le contrôle conserve seulement état HTTP, compteurs et schéma ; un HTTP 200 ne lève pas la réserve de droits.

## 2. Macro : périmètre réellement livré

**Correctif du 16 octobre 2026** : H15 affichait `2026 Oct 12*`, dont l'astérisque
de note faisait échouer la lecture. Le parseur accepte désormais ce suffixe
précis et conserve l'en-tête brut/son annotation en métadonnées (parser v2).
Les autres suffixes inconnus, dates invalides et colonnes dupliquées restent
rejetés. Les valeurs `n.a.` ne sont pas imputées. Le changement de métadonnées
peut créer une nouvelle version technique au premier passage, pas nécessairement
une révision du taux. Disponibilité FIRST_OBSERVED et anciens enregistrements
inchangés, aucune rétrodatation.

Vérification réelle sans SQL : HTTP 200, 25 observations sur cinq dates
(8, 9, 12, 13 et 14 octobre), cinq observations sous la date annotée et quatre
valeurs absentes conservées. 406 tests ciblés du périmètre Fed/news/runner
passent. Pas de collecte macro complète relancée dans cette correction.

| Producteur | Identifiant natif | Mesure et unité | Correspondance à qualifier |
| --- | --- | --- | --- |
| BLS | CUSR0000SA0 | CPI ensemble, CVS, indice base 1982–1984=100 | CPIAUCSL |
| BLS | CUSR0000SA0L1E | CPI hors alimentation/énergie, CVS, même base | CPILFESL |
| BLS | LNS14000000 | Chômage CVS, pourcentage | UNRATE |
| BLS | CES0000000001 | Emploi non agricole CVS, milliers de personnes | PAYEMS |
| Federal Reserve Board H15 | H15_TREASURY_CMT_NOMINAL_3M | Taux nominal constant maturity 3 mois, % | DGS3MO / base de pente 10Y−3M |
| Federal Reserve Board H15 | H15_TREASURY_CMT_NOMINAL_2Y | Même famille, 2 ans, % | DGS2 |
| Federal Reserve Board H15 | H15_TREASURY_CMT_NOMINAL_10Y | Même famille, 10 ans, % | DGS10 |
| Federal Reserve Board H15 | H15_TREASURY_CMT_NOMINAL_30Y | Même famille, 30 ans, % | DGS30 |
| Federal Reserve Board H15 | H15_FED_FUNDS_EFFECTIVE_DAILY | Fed funds effectif **quotidien**, % | Pas interchangeable avec FEDFUNDS mensuel |

Les correspondances ci-dessus servent au futur raccordement, pas à un renommage déjà appliqué. La pente 10Y−2Y ou 10Y−3M pourra être dérivée de valeurs de même date effectivement disponibles. Les lignes TIPS ne sont jamais confondues avec les taux nominaux malgré leurs mêmes libellés de maturité.

### Autorisations et limites

- BLS : les données sont publiques et les conditions API n'imposent pas de contrôle sur l'utilisation secondaire. Respect des limites, citation de la source et date de récupération. [Conditions API](https://www.bls.gov/developers/termsOfService.htm), [copyright](https://www.bls.gov/opub/copyright-information.htm), [API](https://www.bls.gov/developers/api_signature.htm).
- Réserve fédérale : les informations du Board sont généralement dans le domaine public, sauf indication contraire ; ne pas extrapoler cela aux contenus tiers. Seules les familles de taux identifiées sont importées. [Conditions](https://www.federalreserve.gov/disclaimer.htm), [H15](https://www.federalreserve.gov/releases/h15/).

Mention à conserver pour les analyses BLS :

> BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov.

Aucune clé requise pour ces deux routes. BLS v1 : une requête regroupant les quatre séries et les deux années courantes ; pas de balayage lourd ni contournement des quotas. H15 : une page officielle et ses cinq dates récentes. HTTPS vérifié avec les certificats système, jamais `verify=False`.

### Base et disponibilité PIT

Nouvelle table **`alpha_trade.macro_public_observation_versions`** : provider, native_series_id, metric_key, début/fin de période, fréquence, valeur brute/numérique, unité, métadonnées/notes, hash, observed_at, available_at, source_url et run_id.

`available_at = observed_at = fin de réception/validation UTC`, base `FIRST_OBSERVED`. Aucune heure officielle de publication inventée. Les valeurs 2025 téléchargées en octobre 2026 sont utilisables seulement à partir de cette réception, **pas pour simuler une décision 2025**. Les anciens vintages FRED ne sont pas reconstruits par cette collecte.

`pit_raw_payloads` conserve chaque réponse et son hash ; `pit_collection_runs` conserve les compteurs/états. H15 conserve son HTML source décodé, le charset et l'empreinte du corps reçu. Les traces RAW répétées sont normales ; elles prouvent les passages.

La table normalisée ne réinsère pas une version identique à la dernière observée : la première disponibilité reste inchangée. Une révision A→B puis un retour B→A crée trois versions, pas seulement deux. La sérialisation par verrou MySQL couvre la transaction et son commit. Les comparaisons future ML devront sélectionner la dernière version dont `available_at <= decision_time`, **y compris si sa valeur est NULL** ; ne pas récupérer automatiquement une ancienne valeur non nulle pour masquer une correction.

Trois valeurs BLS manquantes dans le premier snapshot sont conservées comme NULL et comptées ; elles ne deviennent jamais zéro. L'absence d'une série, une réponse API en échec ou un schéma ambigu fait échouer le batch, avec détails et compteurs préservés. Les réussites d'un autre producteur restent persistées.

### Résultats et planification

Smoke sans SQL : **82 observations / 4 séries BLS**, **25 observations / 5 séries H15**. Rapport : `artifacts/operations/public_macro_qualification/public-macro-smoke-20261010190622-c78eaf12/report.json`.

Première collecte en base : **2 requêtes demandées, 2 reçues, 107 nouvelles versions, 0 échec**. Répétition immédiate : **0 nouvelle version, 107 inchangées**. Anciennes tables métier et modèles inchangés.

Batch **`public_macro_snapshot_sync`**, P4, actif en recherche, visible dans Workflow & Orchestration → Batch → US. Horaire : **23:15 Europe/Paris, lundi–vendredi**, hors absence 07:30–20:00. Tâche `AlphaTrade-PublicMacroSnapshotSync` installée via le launcher invisible commun ; le launcher filtre les triggers horaires techniques. Compte interactif : session Windows ouverte et PC allumé requis. Pas de réveil du PC ni de serveur distant implicitement livré.

Compteurs : demandés/reçus = requêtes producteur ; persistés = nouvelles versions, pas nombre de jours. Les notifications email/Telegram sont raccordées au launcher existant. Les deux tests lancés directement en Python ne prouvent pas la livraison d'une notification ni la réussite d'une prochaine tâche planifiée.

Si les cinq dates H15 récentes ne couvrent plus une longue absence, une lacune reste possible ; BLS pourra récupérer les niveaux révisés sur deux années, **pas les publications intermédiaires manquées**. Ce n'est pas une promesse de reconstruction fidèle J−7/J pour chaque série.

```powershell
# Exécution immédiate avec les notifications communes
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/forward_pit_launcher.ps1 -BatchName public_macro_snapshot_sync -Force

# Réinstallation de cette seule tâche, si nécessaire
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install_forward_pit_task.ps1 -BatchName public_macro_snapshot_sync

# Contrôle public sans SQL, avec archive locale datée
python -m service.forward_pit.public_macro --dry-run --archive-dir artifacts/operations/public_macro_qualification
```

DDL indépendant : `database/sql/forward_pit/public_macro_observation_versions.sql`, aussi intégré au DDL Forward PIT de référence. Migration **0096_public_macro_versions** après 0095. La table a été créée directement avec ce SQL sur alpha_trade ; **la version Alembic déployée n'a pas été avancée**. L'upgrade futur est idempotent pour cette création. Ne pas lancer cette migration sur alpha_trade_cn/fr. Un downgrade détruirait les nouvelles archives : ce n'est pas une commande d'exploitation normale.

## 3. Ce qui n'est pas encore remplacé

| Famille | Suite publique possible | État |
| --- | --- | --- |
| GDP et PCE/core PCE | BEA, API officielle et tables NIPA | Conditions examinées ; connecteur et mappings non livrés, clé gratuite à demander si nécessaire |
| Production industrielle | Federal Reserve G17 | Périmètre et séries à qualifier avant ajout |
| Ventes de détail | Census Bureau | Séries, unités et révisions à qualifier avant ajout |
| VIX/VIX9D/VXN/VIX3M | Cboe, producteur non gouvernemental | Droits d'archivage/ML à confirmer séparément ; circuit EODHD actuel inchangé |
| MOVE | ICE, producteur privé | Pas traité comme donnée publique gouvernementale ; circuit EODHD inchangé |
| Spreads de crédit ICE/BofA | Producteur/licence adaptée | Pas remplacés gratuitement par supposition |

BEA : clé sur [le formulaire officiel](https://apps.bea.gov/api/signup/), pas de nouvel abonnement. Les [conditions API](https://apps.bea.gov/API/_pdf/bea_api_tos.pdf) prévoient analyse/récupération et attribution ; leur examen ne prouve pas qu'un dataset BEA aurait les mêmes vintages que FRED. Ajouter la mention de non-endossement prévue par BEA lors du raccordement. Ne pas archiver le paramètre UserID de l'API dans le RAW.

La collecte directe est donc la **première tranche** du remplacement, pas le remplacement complet de la macro en production. FRED reste désactivé. Promotion des consommateurs après contrôle de couverture, unités, timestamps et jointures as-of ; aucune performance D1/D10 déduite de la simple présence des données.

## 4. Vérification et code

- `service/eodhd/consensus_qualification.py` : qualification bornée, sans souscription ni archivage consensus.
- `service/forward_pit/public_macro.py` : parseurs BLS/H15, contrôles de schéma, versions et persistance.
- `common/public_data_http.py` : TLS natif vérifié.
- `batch.yaml` et `service/forward_pit/batch.py` : catalogue et handler standard.
- `tests/test_public_macro_and_eodhd_qualification.py` : unités, absence de fuite temporelle, TIPS/nominal, idempotence/réversion, états HTTP, confidentialité et compteurs d'échec partiel.

Validation ciblée finale : **178 tests réussis**, incluant le socle Forward PIT,
le catalogue IHM, les horaires compatibles avec l'absence et les blocages de
droits existants. Ce n'est pas un passage de la totalité des tests du projet.

Le short volume demeure en attente, à la fois pour droits et pour absence de bénéfice directionnel stable démontré. Pas de nouveau fournisseur payant recherché ni de réactivation FINRA dans cette livraison.
