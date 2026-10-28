# Open interest public Euronext Paris — collecte SQL FR

Ajout du 27 octobre 2026 sur demande utilisateur. Batch
`fr_options_open_interest_sync`, fournisseur `Euronext_public`, base physique
`alpha_trade_fr`. Collecte anonyme des réponses de la page publique, sans
abonnement commercial ni utilisation d'un compte courtier.

**Depuis le 28 octobre : [SQL est le stockage principal](stockage_sql_principal_20261028.md).**
Réponses, progression et bilans sont écrits directement en base. Les chemins
de ressources hérités ne désignent plus des fichiers à écrire ou relire.

## Périmètre et horaires

Configuration dans `batch_fr.yaml`, section `fr_options_open_interest_sync` :

- Activé en recherche ; lundi à samedi, **06:30 et 20:30 Europe/Paris**.
- Identités vérifiées actives S6C FR, rapprochement **ISIN exact** avec le
  répertoire public des options Paris. Un titre sans produit public n'est pas
  considéré comme une panne technique ni comme un OI nul.
- Produits standards, variantes américaine/européenne conservées séparément ;
  produits dont le nom comporte `weekly` ou `mini` exclus par défaut.
- Les **trois premiers mois proposés** par produit : pas une couverture de
  toutes les échéances, ni la fenêtre américaine de 15–25 jours.
- Pause d'une seconde entre requêtes ; budgets 800 requêtes, 200 produits,
  12 pages de répertoire et 20 minutes. Une requête commencée peut finir après
  le budget, avec timeout de 30 secondes. Pas de lancement pendant l'absence
  07:30–20:00 et aucun besoin d'allumer le PC à ces heures.

Les horaires capturent des observations successives ; ils ne garantissent
aucune heure de publication OI par Euronext. Une observation manquée n'est pas
reconstituée rétroactivement. La collecte n'a pas de checkpoint historique :
chaque passage observe le contenu public courant, sans écraser les précédents.

## Requêtes utilisées

Source : [répertoire public Paris](https://live.euronext.com/en/markets/paris/stock-options/list),
pagination contiguë. Les trois requêtes suivantes sont celles du site public :

```text
GET /en/ajax/getUnderlying/{code}/DPAR/options
GET /en/ajax/getPricesOptionsForm/{code}/DPAR
POST /en/ajax/getPricesOptionsAjax/stock-options/{code}/DPAR
     ps=999 ; md[]=mois sélectionnés
```

Le premier contrôle l'ISIN ; le deuxième fournit les sélecteurs de mois.
La soumission `POST /en/ajax/submitOptionsForm/stock-options/{code}/DPAR`
est d'abord effectuée, avec les mêmes mois et `ps=999` (« All strikes »),
afin d'appliquer le choix à la session publique. La requête de rafraîchissement
retourne ensuite les lignes CALL et PUT par strike ; les mois réellement
retournés doivent couvrir ceux demandés, sinon le passage est incomplet.
Exemple de produit :
[L'Oréal OR4](https://live.euronext.com/en/product/stock-options/or4-dpar).
Le collecteur respecte le `robots.txt` courant et s'identifie
`AlphaTrade-Research/1.0`. Aucun contournement d'accès : refus robots,
HTTP 401/403/429 ou redirection arrêtent le passage, sans nouvelle tentative.

## Tables

Migration FR `0011_fr_public_option_oi`, après 0010 :

| Table | Contenu |
|---|---|
| `fr_option_oi_public_runs` | Identifiant du passage, horaires UTC, configuration, compteurs, couverture et erreurs |
| `fr_option_oi_public_responses` | Réponse brute intégrale, empreinte SHA256, requête, HTTP, réception et disponibilité SQL, statut du parseur |
| `fr_option_oi_public_contracts` | Sous-jacent/ISIN, produit DPAR, CALL/PUT, strike, mois, OI brut/numérique, volume affiché, règlement, réserves et ligne JSON source |

Clé d'une observation : réponse + produit/côté/strike/sélecteur de mois.
Une relance est une nouvelle observation horodatée, pas un doublon à écraser.
Les réponses sont engagées avant parsing ; un parsing échoué conserve le brut
avec `available_at=NULL`. Contrats et statut de parsing sont engagés ensemble,
puis la disponibilité SQL est estampillée à l'heure réelle après commit.

Les corps HTML/JSON complets sont dans la table dédiée des réponses.
Progression et bilans sont conservés dans les ressources SQL communes et
`fr_collection_runs`. Les nouvelles acquisitions ne créent plus de copies
locales `raw/`, `receipts/` ou `reports/`. Les anciens fichiers sont conservés.

## Qualité : ne pas confondre une valeur avec une preuve d'OI exploitable

- `open_interest` : entier non négatif uniquement ; `-` reste NULL. Les valeurs
  décimales sont `INVALID`, jamais arrondies en nombres de contrats.
- Anomalie réellement observée : certains PUT renvoient un `open_interest`
  décimal égal au prix de règlement. La réponse et la valeur brute sont
  conservées. Même une valeur entière égale au règlement est écartée par
  prudence (`AMBIGUOUS_SETTLEMENT`).
- `NUMERIC_ONLY` signifie « syntaxe entière non ambiguë selon ces contrôles »,
  pas OI certifié ni nombre validé indépendamment.
- `expiry_month=2026-12-01` signifie **décembre 2026**, sans prétendre à une
  échéance le 1er décembre. `expiration_date` reste NULL.
- `volumeDate` n'est pas une date d'OI : `oi_reference_date` reste NULL.
- Les côtés ne sont pas additionnés entre variantes de produits, pas de ratio
  CALL/PUT agrégé ni de score combiné volume/OI.
- `ml_eligible=false`, `directional_filter_ready=false` ; ni trading, ni
  alimentation du filtre américain, ni qualification historique inventée.

Le runner peut terminer **SUCCESS** si le périmètre configuré a été acquis et
stocké. Le statut de données du passage SQL reste **PARTIAL** : les dates OI
et d'expiration réelles ne sont pas prouvées. Ce succès d'acquisition ne
signifie donc pas que tous les titres ont des options, un OI valide ou un
signal utilisable. Une panne technique, limite de budget, chaîne illisible
ou refus d'accès rend le runner **FAILED** ; les acquisitions partielles restent
stockées, sans afficher une couverture complète.

## Exécution et suivi

```powershell
python -u -m service.fr.operational_batch_15a --batch fr_options_open_interest_sync --batch-config batch_fr.yaml
```

Dans la page Batch FR, même lancement manuel et installation Windows que les
autres collecteurs FR. Nom de tâche : `AlphaTrade-FrOptionsOpenInterestSync`.
Le launcher relit les horaires du YAML ; chaque passage est protégé par le
mutex Windows et le verrou MySQL du collecteur.

Log : `log/batch_fr/fr_options_open_interest_sync.txt` pour un lancement via
le launcher. Avancement et bilan : page Batch FR ou requête SQL :

```sql
SELECT operational_run_id, status, started_at, finished_at, summary_json
FROM alpha_trade_fr.fr_collection_runs
WHERE batch_name = 'fr_options_open_interest_sync'
ORDER BY started_at DESC LIMIT 1;
```

Les statistiques sont actualisées pendant les écritures SQL, puis le bilan
final est enregistré. L'heure de fin du passage et `data_status` distinguent
une acquisition terminée d'une qualification financière encore partielle.

## Validation

Tests : `tests/test_fr_public_options_oi.py` et tests du catalogue/stockage FR.
Vérifient les transactions réelles SQLite hors réseau, la traçabilité du brut,
les identités, la pagination, les refus, budgets, valeurs invalides et dates
non inventées. Le test réel MySQL et ses compteurs sont consignés ci-dessous
après exécution ; aucune performance directionnelle n'est déduite de ce test.

### Vérifications réelles du 27 octobre

- Migration 0011 appliquée à `alpha_trade_fr`.
- **73 tests passent**, catalogue et archivage commun inclus.
- L'essai public OR4 après soumission du formulaire retourne effectivement
  décembre 2026, juin 2027 et décembre 2027, soit 142 lignes CALL/PUT.
  L'ancien essai compact sur trois titres est conservé comme passage limité
  `fr-public-oi-20261027213532-7bd6113a` : ce n'est pas une preuve de couverture
  des trois mois, avant correction de la soumission du formulaire.
- Tâche `AlphaTrade-FrOptionsOpenInterestSync` installée et vérifiée : lanceur
  FR via `wscript.exe //B`, catalogue `batch_fr.yaml`, workspace `F:\projets`.
- Premier passage complet lancé : `fr-public-oi-20261027213946-583a33d4`,
  294 titres de référence, 98 produits correspondant à 62 titres découverts.
  Terminé depuis : **62 titres avec chaîne publique, 16 184 observations,
  zéro erreur technique**. Les données restent PARTIAL pour qualification,
  sans prétendre que les 294 titres disposent tous d'options.
- Contrôle SQL en lecture seule à 21:43:36 UTC : 137 corps de réponse vérifiés
  par SHA256 ; 4 992 observations, dont 422 CALL numériques, 2 074 CALL
  manquants et 2 496 PUT invalides. Les dates exactes restent NULL et les
  indicateurs ML restent faux. Ce sont des compteurs intermédiaires, pas une
  mesure de couverture finale ni des contrats économiques indépendants.

Preuve : `artifacts/fr/research/public_options_oi_20261027/sql-verification-v1.json`.
Le bilan final du passage et les erreurs éventuelles se lisent dans les
rapports indiqués ci-dessus, sans refaire de téléchargement pour les consulter.
