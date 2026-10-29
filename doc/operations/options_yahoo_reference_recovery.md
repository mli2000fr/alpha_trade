# Rattrapage des références d'options après Alpaca — 29 octobre 2026

Évolution demandée explicitement : après la recherche SIP, essayer Yahoo pour
les prix de référence encore manquants **dans l'univers tradable seulement**.
Ce prix sert à sélectionner les strikes à collecter, pas à exécuter un ordre,
calculer un spread ou remplacer les cours canoniques du modèle.

## Paramétrage

Les deux blocs de `batch.yaml`, `oracle_options_indicative_snapshot` et
`options_delayed_bars_sync`, contiennent désormais :

```yaml
yahoo_reference_recovery:
  enabled: true
  symbols_file: config/univers_batch/univers_filtred_tradable.txt
  pause_min_seconds: 1.0
  pause_max_seconds: 5.0
  timeout_seconds: 20.0
```

Mettre `enabled: false` dans le bloc concerné désactive son rattrapage. Les
anciens appels sans cette section restent sur leur comportement antérieur.
Les batchs collectent toujours les options sur `stock_bars_daily.txt` ; seuls
les manques appartenant aussi au fichier tradable sont proposés à Yahoo.
Le TOP20 du filtre n'intervient pas dans cet univers de collecte.

## Parcours, validation et provenance

1. Collecter les références Alpaca comme auparavant, avec SIP explicite.
2. Calculer les manques et leur intersection avec le fichier tradable.
3. Lire le cache commun, puis demander les cours journaliers Yahoo manquants,
   séquentiellement, un symbole par requête chart. Une référence Alpaca trouvée
   n'est jamais écrasée par une référence Yahoo.
4. Retenir uniquement une clôture USD de la séance exacte, après clôture
   officielle US : identité du symbole, type action/ETF, fuseau New York,
   tableaux cohérents, OHLC positifs/finis et volume positif. Pas de prix d'une
   ancienne séance ni de bougie quotidienne inachevée. `adjclose` et le prix
   courant des métadonnées ne servent pas de référence. Une opération de split
   postérieure à J exposée dans la réponse fait réserver la référence plutôt
   qu'inverser arbitrairement un ajustement fournisseur.
5. Utiliser le prix validé pour la découverte des contrats Alpaca, puis
   conserver les contrôles existants d'échéance, strike, liquidité et OI.

Les horodatages d'options ne sont pas antérieurs à la récupération de leur
référence. Les prix Yahoo ne sont pas injectés dans `stock_bars_daily` ni
renommés SIP. Retrouver un prix ne prouve pas qu'Alpaca possède une chaîne
CALL/PUT pour le titre ; les cas vides restent visibles dans les compteurs.

## Cache SQL et pauses partagées

Les preuves sont stockées dans **`pit_raw_payloads`** :

- `provider = yahoo_finance` ; `endpoint = /v8/finance/chart` ;
- `entity_key = option-yahoo-reference-v1:SYMBOLE:AAAA-MM-JJ` ;
- `run_id` et `batch_name` du collecteur demandeur ;
- réponse, paramètres sans secrets, statut HTTP, référence normalisée,
  protocole, dates de réception/disponibilité UTC et hash.

Chaque preuve est publiée dans une transaction courte séparée de l'import
d'options. Un verrou MySQL partagé sérialise cache/vérification/pause/requête
entre les deux collecteurs. Le commit précède sa libération : un second
collecteur voit donc la preuve avant d'envisager un appel identique.

Les références positives de date J exacte sont réutilisables 24 h ; les réponses
vides ou les refus sont conservés 30 minutes afin de ne pas figer une absence
indéfiniment. Les références du cache sont revérifiées sur le hash, le périmètre
et leur réponse brute. Une erreur de publication interdit d'utiliser un prix
fraîchement obtenu mais non archivé.

Avant un nouvel appel, une pause cible uniforme de **1 à 5 secondes** est tirée.
Le temps déjà écoulé depuis la dernière réponse est déduit. Il n'y a pas de
requêtes parallèles, retries de requête Yahoo, rotation d'hôte, impersonation
de navigateur ou repli vers un autre endpoint pour contourner un refus.
Les pauses et le temps de requête sont mesurés séparément ; la durée globale
du rattrapage inclut pauses, attente du verrou et lectures du cache.

## Arrêts et notifications

- **⛔ ACCÈS REFUSÉ (401/403)** : arrêt immédiat du rattrapage.
- **🚦 LIMITE ATTEINTE (429)** : arrêt immédiat, aucun retry ni changement d'hôte.
- **⚠️** : erreur de preuve/verrou, ou arrêt après trois erreurs techniques.

Les données Alpaca déjà valides sont conservées et le collecteur continue
sur ses références disponibles. Un arrêt Yahoo ajoute un avertissement : le
runner publie `COMPLETED_WITH_WARNINGS` s'il termine, pas un succès silencieux
du rattrapage. Si une autre erreur provoque ensuite un échec du batch, les
compteurs Yahoo restent attachés à l'erreur et au résumé final.

`pit_collection_runs.details_json.yahoo_reference_recovery` et le résumé normalisé
contiennent notamment `status`, `calls`, `elapsed_seconds`, `http_seconds`,
`pause_seconds`, `recovered`, `cache_hits`, `remaining`, `stop_http_status`,
`recovered_symbols` et `remaining_symbols`.

Le notificateur email/Telegram lit le résumé du run courant. Exemple fictif :

> 🚦 Yahoo : LIMITE ATTEINTE (429) — rattrapage arrêté · 12 appels en 43.2 s
> (pauses incluses) · 8 références récupérées, 0 depuis le cache · 136 titres
> restant sans référence

`calls` désigne les appels HTTP réellement tentés, y compris le refus final,
et exclut les lectures du cache. Ce n'est pas un nombre fixe de 97 appels :
les manques sont recalculés chaque jour et les réponses vides comptent aussi.

## Portée de l'activation et validation

Cette demande active seulement ces deux rattrapages de prix. Le batch Yahoo
de consensus et les anciens fallbacks secteurs/capitalisations restent bloqués
ou retirés. L'accessibilité technique et la demande utilisateur ne valent pas
autorisation contractuelle Yahoo ni certification des prix pour l'exécution.

Validation hors ligne : ciblage des manques tradables, priorité Alpaca, dates/
devises/identités/splits, cache partagé, pauses et comptages, arrêts 401/403/429,
échec de commit, branchement des deux collecteurs et notifications simulées.
Vérification réelle du verrou et des lectures du cache sur le schéma existant,
sans écriture de données ni appel fournisseur. Pas de batch relancé, ordre ou
notification réelle envoyé pendant cette livraison.

Bilan de validation : **154 tests réussis** sur le rattrapage, collecteurs,
notifications et configurations. Relecture hors ligne des archives du test
Yahoo : **97/97 références positives acceptées par le nouveau normaliseur**,
sans nouvel appel réseau. Le résultat reste un contrôle du raccordement et
de la qualification technique, pas un test de rendement.

Sources : `service/forward_pit/yahoo_option_references.py`, les deux collecteurs
dans `batch.py`/`options_delayed.py`, `outcomes.py` et `scripts/send_batch_email.py`.
