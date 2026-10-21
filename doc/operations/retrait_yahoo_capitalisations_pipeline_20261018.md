# Capitalisations, B2 et étape 13 sans Yahoo — 18 octobre 2026

## Livré et périmètre exact

À la demande utilisateur, retrait de Yahoo sur trois chemins :

1. `market_cap_sync` : SEC puis Finnhub, sans requête ni fallback Yahoo.
   `common.market_cap` et le publieur d'univers suivent
   `sec_edgar_then_finnhub` ; les anciennes stratégies Yahoo sont refusées,
   pas interprétées silencieusement comme une permission de télécharger.
   Les observations Yahoo déjà présentes ne sont pas sélectionnées par ces
   nouvelles stratégies. Aucune donnée SQL n'a été supprimée/réétiquetée.
2. **B2**, mise à jour secteurs/fondamentaux `stock_metadata` : Finnhub par
   défaut dans le CLI, le builder et l'IHM. Yahoo retiré de ce choix et refusé
   en entrée ; les anciennes sélections Streamlit sont ramenées à Finnhub.
   EODHD reste une option, avec son fallback Finnhub sur refus d'accès ; aucun
   abonnement supplémentaire ou accès Fundamentals EODHD n'est présumé acquis.
3. **13**, opérations sur titres : fournisseur principal Alpaca/EODHD inchangé,
   `--cross-check none` explicite. Le CLI sync/run et l'IHM ne permettent plus
   de choisir Yahoo ; aucun appel au contrôleur Yahoo depuis ces chemins.
   Les anciennes traces d'audit ne sont pas effacées. Aucun ordre exécuté.

**Correction de l'inventaire initial :** B2 est un bloc auxiliaire, pas l'étape
numérique 2 (Data Sanitizer). `us_pipeline.steps`/`steps_friday` ne lancent pas
B2. Les défauts partagés incluaient Yahoo pour cette option, mais cela ne
signifiait pas qu'il était collecté par chaque workflow quotidien. Data Sanitizer
reste inchangé. 13 n'est lancé que si explicitement sélectionné ; les listes
actuelles s'arrêtent à 12. Pas de changement d'univers, horaire ou liste d'étapes.

Ce n'est **pas** un retrait de tous les anciens outils Yahoo du dépôt : les
scripts de recherche, connecteurs manuels d'autres pages, dépendance yfinance
et lecteurs d'archives recensés précédemment sont hors de ces trois chemins.
Les collectes analystes bloquées restent bloquées ; aucun ancien outil relancé.

## Quotas, reprise et compteurs

`batch.yaml` conserve les 13 105 symboles du grand fichier et le seuil de 95 %.
Il ajoute :

```yaml
provider: sec_edgar_then_finnhub
primary_provider: sec
fallback_providers: "finnhub"
finnhub_request_interval_seconds: 1.1
finnhub_refresh_after_days: 3
coverage_reference_symbols_file: config/univers_batch/univers_filtred_tradable.txt
```

Les appels Finnhub ne concernent que les trous SEC sans snapshot Finnhub récent.
Un trou SEC signifie désormais une **capitalisation non calculable/qualifiée**,
pas seulement un nombre d'actions absent.
La fenêtre de réutilisation (trois jours) est distincte des 365 jours tolérés
pour la **couverture** : un snapshot vieux de plusieurs mois ne dispense pas
du rafraîchissement régulier. Lundi/jeudi restent les passages configurés.
La pause entre symboles est de 1,1 s au minimum ; elle ne garantit pas à elle
seule le respect d'un quota partagé avec d'autres processus/comptes.
Un coupe-circuit ouvert arrête cette série d'appels : le reliquat est compté
`deferred`, non téléchargé, pas assimilé à une réponse vide ou un succès.
Les écritures réussies restent conservées ; la couverture finale est relue.

`details_json.providers` distingue demandés, persistés, échecs, différés,
couverture déjà présente, observations réutilisées et symboles nouvellement
couverts. `coverage_scopes` mesure le grand fichier et le fichier tradable ;
un log de fin expose ces deux périmètres. Le statut reste décidé sur le
grand fichier : **pas de passage automatique au vert en utilisant les seuls
titres tradable**, pas d'abaissement du seuil.

La couverture du batch signifie désormais une **capitalisation effectivement
calculée et enregistrée**, ou une capitalisation Finnhub enregistrée, disponible
au cutoff. Des actions SEC sans cours qualifié ne comptent pas comme couverture.
Le publieur conserve son calcul actions SEC × cours de son propre snapshot en
mode `strict`, ou une capitalisation Finnhub ; Yahoo n'est plus une branche de secours.
La classification Finnhub doit rester harmonisée avec les groupes sectoriels
de l'application ; aucune nouvelle taxonomie historique n'est inventée.

## Calcul enregistré : vérification locale du 18 octobre

`service.forward_pit.market_cap_calculations` calcule le produit et le stocke dans
**`alpha_trade.stock_market_cap_daily`**. Les faits d'origine de
`stock_fundamentals_daily` ne sont pas réécrits. Le batch appelle ce calcul après
SEC, puis matérialise le complément Finnhub après son rafraîchissement ciblé.

- Dernière séance NYSE clôturée et confirmée depuis au moins 30 minutes ;
  calendrier réel, demi-séances et changements d'heure compris. Le délai est
  configurable dans `batch.yaml` (`close_confirmation_delay_minutes`).
- `close` canonique, pas `adj_close` ajusté des dividendes ; source explicite
  `eodhd`/`eodhd_eod` ou `alpaca_sip`. Valeur strictement positive et finie,
  `is_filled=0`, cours de la séance de référence exactement (pas une ancienne
  clôture substituée discrètement).
- ADR/classes ambiguës connues, instruments collectifs et splits connus depuis
  la date de mesure des actions sont écartés du produit SEC et envoyés au
  fallback. Aucun ratio ADR ou facteur d'ajustement n'est inventé. Ce contrôle
  conservateur n'est pas une certification exhaustive des identités/classes.
- Source, montant, devise USD selon le contrat US existant, nombre d'actions,
  close/source/date du prix, identifiant du fait SEC/Finnhub, accession,
  date du fait, disponibilité, heure réelle de calcul et run sont conservés.
  Le résultat est une **estimation**, pas une capitalisation officielle certifiée.
- `observation_date` est le jour UTC du calcul et `available_date` au plus tôt
  le lendemain UTC, conformément au contrat quotidien conservateur. Pas de
  prétention de disponibilité historique à la date de dépôt SEC.
- Une empreinte des entrées et du jour d'observation interdit les doublons
  identiques. Un changement d'entrée crée une nouvelle version traçable ;
  une relance ne réécrit pas l'heure de première observation.

Résultat **réellement enregistré**, sans appel fournisseur, avec les cours du
16/10 et une disponibilité au 19/10 :

| Mesure | Résultat |
|---|---:|
| Produits SEC × close | 1 393 |
| Capitalisations Finnhub complémentaires | 2 296 |
| Total enregistré / grand fichier | **3 689 / 13 105 = 28,15 %** |
| Titres du fichier tradable couverts | **1 784 / 1 790 = 99,66 %** |
| Lignes ajoutées lors de la seconde exécution identique | **0** |
| Produits stockés différents de `shares_outstanding × reference_close` (> 0,01 USD) | **0** |

Parmi 4 355 titres avec actions SEC admissibles : 2 659 sans cours à la séance
de référence, 146 avec ambiguïté ADR/classe et 157 instruments collectifs ont été
écartés du produit. Finnhub peut en couvrir une partie. Sur le fichier tradable,
les six manquants restent **BK, EQR, EXPI, FDP, IAC, SATS**, sans suppression de
symboles ni changement de politique. L'écart avec les audits ci-dessous vient
de leur comptage d'**entrées potentielles**, pas de capitalisations calculées.

Rapports :

- `artifacts/operations/market_cap_no_yahoo/calculated-20261018-v1/report.json` ;
- `artifacts/operations/market_cap_no_yahoo/calculated-20261018-repeat-v1/report.json`.

La vérification locale n'est **pas** un nouveau run de collecte ; le statut du
dernier `market_cap_sync` n'a pas été remplacé. `persisted` dans le batch additionne
les lignes de faits bruts et les nouvelles observations dérivées ; leur détail
figure séparément dans `details_json.calculation`.

### Installation additive et reprise locale

La migration `0109_market_cap_daily` est fournie. La base inspectée étant au
head `0108_sip_bar_defaults`, et la chaîne suivante incluant une autre branche,
seule cette table a été installée : **aucune migration étrangère au périmètre
n'a été exécutée, aucun head Alembic n'a été falsifié**. Le head existant reste
inchangé. La migration formelle est idempotente lorsque ses prédécesseurs seront
effectivement appliqués. Les contrôles runtime vérifient la table et ses colonnes.

```powershell
python -m database.market_cap_snapshots --install-schema
python -u -m service.forward_pit.market_cap_calculations --symbols-file config/univers_batch/stock_bars_daily.txt --output artifacts/operations/market_cap_no_yahoo/calculated-nouveau-dossier
```

La première commande ne crée que la table US, sans toucher aux faits ni aux
versions Alembic. La seconde utilise les données **déjà présentes**, sans appel
réseau fournisseur ; dossier de sortie neuf obligatoire. Les tranches SEC et
Finnhub sont transactionnelles et une reprise identique est idempotente.

## Audits initiaux des entrées disponibles, sans écriture SQL

Deux audits **lecture seule** de la base `alpha_trade`, prix de référence du
**16 octobre 2026**, fenêtres de disponibilité explicites et âge maximal 365 j.
Les dates ne sont pas interchangeables : les snapshots reçus le 18 peuvent
être disponibles le 19 selon le contrat J+1 du collecteur.

| Périmètre | SEC actions disponibles | Finnhub total | Complément Finnhub hors SEC | Union SEC/Finnhub |
|---|---:|---:|---:|---:|
| Grand fichier, cutoff strict 18/10 | 4 355 | 1 858 | 395 | **4 750 / 13 105 = 36,25 %** |
| Grand fichier, cutoff opérationnel 19/10 | 4 355 | 3 688 | 2 225 | **6 580 / 13 105 = 50,21 %** |
| Tradable, chacun des deux cutoffs | 1 450 | 1 783 | 335 | **1 785 / 1 790 = 99,72 %** |

Il s'agit de **couverture du stock existant**, pas des compteurs d'un nouveau run.
Ni nouveau téléchargement ni écriture SQL. Le cutoff au 19 est celui utilisé
par le batch du 18, pas une prétention de disponibilité au 18. L'audit strict
au 18 est conservé séparément et ne bénéficie pas des observations disponibles
seulement le lendemain.

Pour 1 436 des 1 450 titres tradable couverts par des actions SEC, un close
strictement positif et non rempli est présent le 16/10 ; 14 n'en ont pas sous
ce filtre. En complétant avec les capitalisations Finnhub, le nombre avec
capitalisation disponible ou potentiellement calculable est **1 784 / 1 790
(99,66 %)**. Ce n'est ni une qualification d'actions sur titres, ni un cours
d'entrée négociable, ni une autorisation d'ordre.

Absence d'observation SEC/Finnhub sur le fichier tradable : **BK, EXPI, FDP,
IAC, SATS**. La liste avec capitalisation non calculable/disponible au cours de
référence ajoute **EQR** (actions SEC mais aucun cours satisfaisant ce contrôle,
pas de capitalisation Finnhub admissible). Pas d'exclusion automatique des
fichiers d'univers, pas de suppression de titres.

Rapports immuables :

- `artifacts/operations/market_cap_no_yahoo/audit-asof-20261018-v1/report.json`
  (cutoff strict 18/10) ;
- `artifacts/operations/market_cap_no_yahoo/audit-20261018-v1/report.json`
  (cutoff opérationnel 19/10).

Ils contiennent aussi toutes les listes manquantes et les empreintes des deux
fichiers d'univers. Le script `scripts/audit_market_cap_coverage.py` n'utilise
que des SELECT ; `sql_writes=false`, `provider_calls=0`.

```powershell
python -u -m scripts.audit_market_cap_coverage --as-of 2026-10-18 --price-date 2026-10-16 --output artifacts/operations/market_cap_no_yahoo/audit-asof-20261018-v2
```

Dossier neuf obligatoire. Le script refuse une autre base ou un prix postérieur
au cutoff. Les résultats ne requalifient pas rétroactivement l'historique PIT.

## Vérification et limites opérationnelles

335 tests ciblés passent : calcul et persistance, idempotence, provenance,
refus des prix remplis/IEX et des entrées futures, garde splits/ADR, calendrier,
installation additive, collecte/couverture, configuration, refus des
anciennes options Yahoo, réutilisation Finnhub, arrêt sur circuit ouvert,
publication sans Yahoo et disponibilité, B2, commandes sync/run, orchestration
US et contrats fondamentaux SEC. Les tests n'appellent pas les fournisseurs et
ne transmettent aucun ordre. Les fixtures obsolètes ont été isolées des réglages
de déploiement ; le test de montage TLS ne dépend plus d'un journal de clés système.

**Limites importantes :**

- Le grand fichier n'atteint pas 95 % : sans amélioration de couverture ou
  nouveau choix explicite de périmètre de contrôle, le prochain run peut
  rester FAILED. Le très bon taux tradable ne masque pas ce fait.
- Aucun run complet de collecte lancé dans cette intervention ; le statut
  FAILED du run précédent reste historique, pas effacé ou forcé à COMPLETED.
- Autre blocage préexistant repéré pendant les tests : `market_data.bars_provider`
  vaut Alpaca, alors que le builder du batch exige encore EODHD pour son
  contrôle de couverture J (`eodhd_import_require_target_coverage`). Cela peut
  bloquer **l'étape 1** avant tout le reste ; ce routage n'a pas été modifié
  dans le retrait Yahoo. Les tests d'orchestration fixent explicitement EODHD
  pour tester leur propre contrat, sans changer le déploiement.
- Les données anciennes et les autres chemins Yahoo du dépôt ne sont pas
  supprimés. Les gardes des nouvelles entrées, l'exécution et les protections
  existantes restent inchangés.
