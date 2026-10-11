# Options FR — collecte quotidienne partielle MiFIR + FIRDS

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Statut et activation

Le batch `fr_options_mifir_trade_sync` est implémenté, mais livré avec
`enabled: false` dans `batch_fr.yaml`. Il apparaît dans **Workflow & Orchestration
→ Batch → France**, au même titre que les autres collectes FR.

Pour l'utiliser : passer cette section à `enabled: true`, conserver
`status: ACTIVE_RESEARCH`, puis installer/réinstaller le batch depuis cette page.
Le bouton d'exécution immédiate utilise le même launcher et les mêmes notifications
mail/Telegram que les autres batchs FR. Les destinataires et secrets restent ceux
du système de notification existant. L'installation et l'activation ne sont pas
réalisées automatiquement par l'implémentation.

Simulation sans réseau, sans archive et sans écriture SQL :

```powershell
python -m service.fr.operational_batch_15a --batch fr_options_mifir_trade_sync --batch-config batch_fr.yaml --dry-run
```

Après activation, exécution avec notifications : utiliser le bouton de la page
Batch ou sa commande PowerShell affichée. Une exécution Python directe produit
le bilan structuré mais **ne déclenche pas elle-même les notifications** : le
launcher commun assure cette fonction.

## Ce que l'on récupère

La collecte télécharge le fichier public Euronext des transactions différées
**Paris, dérivés actions/indices, précédent jour de négociation**, puis interroge
ESMA FIRDS pour les ISIN effectivement échangés. La jointure utilise l'ISIN de
l'option et l'ISIN du sous-jacent, jamais un rapprochement approximatif de noms.

Informations conservées : lignes originales, prix, quantité déclarée, devise,
horodatages de transaction/publication, identifiant de transaction, lieu de
négociation/publication, indicateurs de modification/différé, et contrat FIRDS
(sous-jacent, strike, échéance, call/put, multiplicateur, style et livraison
lorsque renseignés). Les réponses brutes et leurs empreintes sont archivées.

**Ce n'est pas une chaîne options complète.** Il manque notamment intérêt ouvert,
NBBO, tailles bid/ask, Greeks complets et historique qualifié des ajustements.
La quantité déclarée n'est pas encore certifiée comme un volume de contrats :
pas de ratio put/call de volumes certifié. Le champ correspondant reste nul.

Toutes les observations restent `ml_eligible: false`, sans écriture canonique,
sans insertion SQL et sans utilisation par les modèles/backtests. La référence
FIRDS courante ne constitue pas une preuve historique PIT qualifiée. L'heure
de disponibilité conservatrice est l'heure d'observation de la collecte ; on
ne remplace pas cette heure par la publication initiale du trade.

## Univers et couverture

`identities_file` désigne le référentiel FR vérifié du Sprint 6-C, commun aux
collectes FR. La sélection retient toutes ses identités actuelles actives,
uniques et vérifiées : ISIN valide, symbole `.PA`, noms de référence présents.
Les identités ambiguës/inactives sont exclues avec leur motif. Il ne s'agit ni
du TOP20 Oracle, ni des trois titres du pilote, ni de l'univers US.

Le fichier source couvre plus d'instruments que cet univers. On résout ses
ISIN puis on conserve les options dont le sous-jacent appartient à l'univers.
Les instruments numériques non-ISIN restent visibles dans les diagnostics et
dans le brut ; ils ne sont pas joints arbitrairement à FIRDS.

Un titre sans trade accepté peut ne pas avoir de transaction ce jour-là,
ne pas avoir d'option cotée, ou présenter des lignes exclues. **L'absence de
trade ne permet pas de distinguer ces situations**, ni de déclarer une couverture
complète des options. La liste `symbols_without_accepted_trade` les expose.

## Calendrier et limites de reprise

Horaire : **06h Europe/Paris, lundi à samedi** (avancé le 10/10 pour l'absence
07:30–20:00 ; [horaires et réserves](../operations/horaires_fr_cn_presence_pc.md)). La récupération vise le fichier
du précédent jour de négociation ; lundi peut reprendre le vendredi déjà reçu.
Cela évite les ambiguïtés de conversion heure New York/Paris : cette source est
Paris. Le fichier n'est pas demandé pendant la séance du jour courant.

Le fournisseur conserve les fichiers sur une fenêtre courte : aucun backfill
J−7/J fidèle n'est promis. `max_source_age_days: 7` est un contrôle de fraîcheur,
**pas** une profondeur de téléchargement. Il autorise les week-ends/jours fériés
mais rejette une source vide, future, datée du jour courant ou trop ancienne.
Un PC éteint plusieurs jours peut manquer des observations irrécupérables.

Les appels FIRDS sont répartis en lots de 80 ISIN ; `max_reference_calls: 80`
borne leur nombre par exécution. Le dépassement échoue explicitement après
archivage du fichier source. `request_sleep_seconds` impose au moins 0,5 seconde
entre lots. Aucun contournement de refus d'accès, authentification ou CAPTCHA.

## Stockage, déduplication et erreurs

Racine : `artifacts/fr/operations/fr_options_mifir_trade_sync/`.

- `objects/<sha256>` : objets sources bruts, contrôlés avant réutilisation ;
- `checkpoints/<date-collecte>/<hash-requête>.json` : reçus FIRDS pour reprendre
  les lots déjà réussis dans la même journée ; nouvelle journée = nouvelle lecture ;
- `snapshots/<empreinte>.json` : analyse, contrats, lignes acceptées/rejetées,
  couverture, univers et provenance ;
- `attempts/*.json` : reçus et bilan de tentative, y compris les erreurs ;
- `.lock` : exclusion de deux collectes simultanées ;
- `artifacts/fr/operations/runs/fr_options_mifir_trade_sync/*.json` : bilan
  commun affiché dans l'IHM ;
- `log/batch_fr/fr_options_mifir_trade_sync.txt` : journal du launcher.

Même contenu transactions + référentiel + univers : même snapshot, pas d'ajout
d'une seconde copie métier. Une nouvelle réception est néanmoins tracée.
Un fichier corrigé ou un référentiel changé produit une **nouvelle version de
preuve**, pas une concaténation à utiliser telle quelle. Avant toute exploitation
future, il faudra sélectionner la bonne version de chaque journée et traiter
les corrections entre réceptions. Ces fichiers ne constituent pas encore une
table canonique de trades.

Doublons exacts de trade éliminés dans l'analyse ; annulations, modifications
non résolues, identifiants contradictoires, horodatages/prix/quantités invalides
ou lignes différées/agrégées non qualifiées sont exclus de l'échantillon accepté
mais conservés comme preuves. FIRDS manquant, ambigu ou contrat invalide :
échec explicite avec données partielles conservées, pas succès silencieux.
Après un plantage dur, vérifier que le processus est arrêté avant de supprimer
manuellement un verrou orphelin ; aucun déverrouillage automatique risqué.

## Lecture des compteurs et notifications

Les compteurs principaux ont l'unité **titres sous-jacents** :

- demandés : titres éligibles de l'univers ;
- reçus : titres avec au moins un trade accepté ;
- persistés : titres avec trade accepté dans un **nouveau** snapshot ; zéro
  lors d'une relance identique est normal ;
- échecs : au moins un en cas d'erreur bloquante, distinct des exclusions de lignes ;
- alertes : compteur commun, les exclusions détaillées restent dans le rapport.

`trade_rows`, `coverage` et `exclusion_counts` précisent le nombre de transactions,
de séries et les motifs de rejet. Une journée sans activité acceptée n'est pas
automatiquement un échec. Ce bilan est transmis au mécanisme mail/Telegram par
`::alpha_trade_run_summary::` et affiché par la page Batch. Les refus HTTP et
erreurs d'archivage remontent au runner, à son statut FAILED et au launcher.

## Relation avec l'ancien batch et suite

Un premier passage sur l'univers entier et l'audit des unités sont documentés
dans [qualification MiFIR/FIRDS](options_mifir_qualification.md) : 42 titres,
1 240 transactions et 611 séries sur la séance du 5 octobre 2026. Ces résultats
ne lèvent pas la quarantaine ni les données manquantes du besoin complet.

La piste Excel est retirée du code. Les anciens artefacts expérimentaux sont
gardés comme archives. `fr_options_snapshot`, qui désigne le besoin complet,
reste bloqué : la nouvelle collecte **ne le débloque pas intégralement**.

Avant ML : qualifier unités, timestamps et contrats ajustés, mesurer plusieurs
jours de couverture, construire des features uniquement à partir des snapshots
réellement disponibles avant décision, puis tester leur apport hors échantillon.
L'archivage relève déjà de la sauvegarde globale `artifacts/fr`.

Sources et pilote : [POC MiFIR/FIRDS](options_mifir_firds_poc.md),
[Euronext Delayed Trade Data](https://marketdata.euronext.com/data-reporting-service/trades-file),
[mentions ESMA](https://registers.esma.europa.eu/publication/legalNoticePage).
Usage interne selon conditions propres MiFIR et attribution ESMA ; une
redistribution payante exige une revue/licence distincte.
