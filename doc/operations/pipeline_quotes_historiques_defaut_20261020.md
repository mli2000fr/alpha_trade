# Étape 4 — historique SIP par défaut, 20 octobre 2026

## Incident et correction

Le lancement du 20 octobre à 08:02 appelait `/v2/stocks/quotes/latest?feed=sip`,
sans dates et sur 12 329 titres `active-tradable`. Le refus HTTP 403 concernait
donc une demande SIP **temps réel**, pas la collecte historique de clôture.
Le raccordement des barres SIP à l'étape 1 ne confère pas les droits temps réel.

Le bouton standard de **4. Sync Latest Quotes** utilise désormais par défaut
une fenêtre historique et le fichier d'univers configuré. Aucun fallback IEX
ni remplacement des quotes par des barres OHLC n'est ajouté.

## Paramètres

```yaml
market_data:
  quotes_historical_feed: sip
  pipeline_quotes:
    mode: historical
    symbol_source: universe-file:config/univers_batch/univers_filtred_tradable.txt
    lookback_days: 7
```

- `mode: historical` : dernière séance NYSE clôturée depuis au moins vingt
  minutes, avec le calendrier strict, jours fériés et demi-séances compris.
- `lookback_days` : fenêtre en jours calendaires avant cette séance ; défaut 7.
  Le collecteur n'attend pas une quote pour chaque jour non négociable.
- `symbol_source` : fichier configuré, pas d'élargissement implicite vers tous
  les symboles éligibles. Un choix explicitement fourni par l'opérateur reste
  prioritaire. Une source de configuration inconnue est refusée.
- `mode: latest` : option explicite, également proposée dans **Paramètres Data
  Integrity → Quotes — mode de collecte**. Ce mode nécessite les droits SIP
  temps réel et ne récupère pas de dates fictives pour masquer un refus.

Le flux SIP est explicitement présent dans la commande (`--feed sip`). Le choix
du fournisseur de barres reste indépendant de ces paramètres de quotes.

## Dates et périmètre effectifs

À 08:02 Paris le **20 octobre 2026**, en l'absence de fenêtre personnalisée :

```powershell
python -u -m dataIntegrityEngine.sync_latest_quotes --batch-size 200 --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt --from-date 2026-10-12 --to-date 2026-10-19 --feed sip
```

Cette commande est un exemple de collecte : elle n'a pas été lancée pendant le
correctif. La fenêtre et le fichier effectifs sont affichés dans le bloc de
l'étape 4, avec l'aperçu de commande. La date de trading des autres étapes
n'est pas réécrite par le résolveur des quotes.

Une `trade_date` plus ancienne borne le choix de séance ; elle n'est pas
avancée vers une séance plus récente. Le matin, le week-end, un jour férié ou
avant clôture +20 min, la dernière séance prête est retenue, pas le jour civil
précédent supposé négociable. Une fenêtre historique explicitement choisie est
conservée ; les contrôles de disponibilité du collecteur s'appliquent toujours.

Dans un workflow interactif, la fenêtre est figée avant les étapes enfants et
journalisée : elle ne change pas parce que l'étape 4 arrive après minuit ou
après une nouvelle clôture. Le batch `us_pipeline` garde sa fenêtre explicite
J−7/J issue de `batch.yaml`, et force le mode historique même si la page est
configurée en temps réel. Aucun horaire ni périmètre du batch n'est changé ici.

Le bloc **Récupération historique sur période** conserve les dates et choix
d'univers personnalisés. Il reconnaît aussi les fichiers `config/univers_batch/`
non présents dans l'ancien catalogue de fichiers. Son aperçu ne retombe plus
sur `active-tradable` lorsqu'il reçoit un tel fichier. Ce lancement impose
toujours le mode historique, même si le bouton standard est réglé en temps réel.

## Garanties conservées

- Aucune réactivation du batch autonome `latest_quotes_sync`.
- Aucun nouvel abonnement ni achat ; les droits broker ne sont pas modifiés.
- Pas de collecte temps réel de secours si le calendrier ou la configuration
  ne peuvent pas être qualifiés : l'étape 4 est désactivée avec explication.
- Reprise, archivage brut, qualité du bid/ask, provenance SIP et upsert dans
  `stock_quote_snapshots` restent ceux du collecteur historique existant.
- Pas de purge, de migration SQL, de modification du filtre de spread ou des
  protections des positions.
- L'exécution de nouvelles entrées conserve son contrôle SIP temps réel : une
  quote historique de clôture ne remplace jamais cette autorisation.
- La CLI appelée directement **sans dates** conserve son mode `latest` ; le
  correctif rend les dates explicites dans les lancements de la page Pipeline.

## Vérification

Tests dédiés : matin du 20 octobre, avant/après clôture +20 min, passage à
minuit, week-end, férié US, changements d'heure, demi-séance, fenêtre explicite,
source configurée et personnalisée, refus IEX/configuration invalide, choix
temps réel explicite et fenêtre figée dans un workflow isolé. Les tests IHM
vérifient le sélecteur de mode et le bouton historique sans collecte réelle.

Test fournisseur borné : **une seule quote AAPL**, séance du 19 octobre,
fenêtre 19:45–20:00 UTC, flux SIP, compte `default`. Quote reçue à
**19:59:59.97504411 UTC**, bid 342,94 / ask 342,99. Aucun enregistrement SQL,
ordre ou notification. La session de ce test vérifie les certificats Certifi
et Windows ; aucune désactivation TLS. Une première tentative avec la session
Requests standard a rencontré le certificat local de l'environnement et a été
interrompue, sans contourner la vérification TLS.

Les tests plus larges ont aussi fait apparaître des réserves hors de cette
correction, non masquées par des modifications du code métier :

- assertion ancienne du test de migration quotes attendant la tête 0107,
  alors que le dépôt a déjà une tête 0109 ;
- deux tests d'arrêt de processus restant `running` dans l'environnement
  Windows restreint, sur des étapes sans collecte quotes ;
- tests E2E anciens supposant une liste de champs sentiment inchangée et un
  compte `cash`, alors que la configuration actuelle utilise `margin`.

Dernier passage ciblé : **358 tests réussis, trois désélectionnés** (l'assertion
de tête de migration et les deux tests d'arrêt Windows décrits ci-dessus).
Les deux réserves E2E anciennes sont issues d'un passage élargi distinct.
Cela ne constitue pas une validation de tout le pipeline, de la couverture de
tout l'univers ou du passage d'un ordre. Aucun pipeline réel complet n'est relancé.

Implémentation : `ihm/services/pipeline_quote_scope.py`, générateur de commandes,
page Pipeline, paramètres Data Integrity et gel des options du workflow.
