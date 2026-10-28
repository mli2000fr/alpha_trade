# Winner — SPY, plans en attente et contrôle du gap, 28 octobre 2026

## Nouvelle tentative

Filtre `opt-917380c30aab40cbb99362b3ead15e7c`, risque `404615885b1041ac`,
exécution `619852eab35b421e`, lancée à 12:55 Paris.
Deux plans LONG ont été créés, P et OKTA, sans ordre ni fill.
Le refus effectif était `NATIVE_RISK_REJECTED: SPY daily source ambiguous`.
Le 403 SIP du préchargement commun restait un avertissement distinct.

## Corrections livrées

La revalidation Winner lisait directement les deux sources de SPY. Elle passe
désormais par `common.daily_bar_sources.load_daily_close_series` : préférence
configurée, EODHD prioritaire ici, SIP conservé pour les dates sans EODHD,
une ligne par séance et cutoff explicite. Aucun prix futur, doublon intra-source,
source inconnue, prix invalide ou clôture de cutoff manquante n'est accepté.
Le préflight du breaker utilise la même série brute et la même priorité ;
il n'est plus limité à EODHD ni à une suppression arbitraire des doublons.
La vérification en base retrouve 7 674 séances uniques jusqu'au 27 octobre.

Le diagnostic de réconciliation distingue maintenant un plan PENDING exact,
sans opération, parent, lot ou fill, d'une position attendue chez le broker.
Cette distinction demande aussi une lecture OMS réussie et zéro intention,
soumission et fill. Une position broker inattendue reste signalée ; les autres
contrôles et les données indisponibles ne sont pas transformés en succès.
Le bilan console affiche les plans en attente et leurs motifs.

Le watcher avait aussi quitté après trois erreurs SQL : son identifiant de
verrou dépassait la longueur admise. Les propriétaires de verrou sont désormais
aléatoires, uniques même à horloge identique et bornés à 32 caractères. Aucun
changement de schéma ni élargissement du verrou n'est nécessaire.

Validation ciblée finale : 137 tests passent, incluant priorité des sources,
cutoff, plans sans effet, positions inattendues, verrous uniques et chemins
Winner/risque/exécution. Une simulation du risque sans ordre et sans écriture
métier a été menée sur les deux plans.

## Blocage restant, conservé explicitement

Les plans figent `order_type=market`, `max_entry_gap_pct=0.03` et
`standard_entry_quote_check_enabled=false`. Sans quote, le contrôle d'un
écart de prix temps réel de 3 % est impossible. Le risque refuse les entrées
au lieu de désactiver cette limite ou d'inventer un prix courant.

Le watcher a été redémarré avec les correctifs et est sain. Son premier cycle
confirme la disparition du refus SPY et le refus explicite lié au gap. Aucun
ordre n'est envoyé ; les deux plans restent PENDING, sans opération ni lot.
Leur claim n'est pas libérée : les plans existent, le watcher en est le
continuateur. Relancer 12 ou effacer ses reçus ne résoudrait pas ce contrat.

Journaux : `artifacts/operations/watcher_spy_source_repair_20261028/watcher-c0370fde/`.
État et proposition de suite : `artifacts/operations/execution_spy_source_20261028/report.json`.

## Proposition à valider

Pour travailler sans SIP avant ouverture, une adaptation possible est un ordre
limite DAY plafonné à +3 % de la référence approuvée, avec revalidation du
sizing au plafond et protections fondées sur le fill réel. Ce serait un
plafond de prix d'achat, pas une prétendue mesure d'un gap courant ni un
contrôle symétrique du gap à la baisse. Le prix peut ne jamais être exécuté.

| Titre | Quantité approuvée maximale | Référence | Plafond proposé |
| --- | ---: | ---: | ---: |
| P | 1 | 138,73 $ | 142,89 $ |
| OKTA | 1 | 226,07 $ | 232,85 $ |

Il s'agit uniquement d'une proposition : les termes figés des deux plans
n'ont pas été modifiés et aucun nouveau mode de soumission n'est encore
activé. Toute adaptation devra préserver la lignée des plans, l'absence
de doublons et la revalidation native du risque.

### Suite autorisée

L'utilisateur a ensuite autorisé le mode limite conditionnel lorsque les
cotations sont désactivées. Cette adaptation est implémentée dans
`winner_standard_entry`, la revalidation native, la réservation et le pont
broker : voir [le contrat actualisé](winner_standard_entry_quotes.md).
Les mêmes plans et leurs plafonds de 3 % sont conservés, sans nouvelle
admission. Une prévalidation a trouvé puis corrigé l'usage du capital par
défaut dans le collecteur de risque. Le blocage restant est factoriel
(expositions non qualifiées, champs sources nuls) ; il est maintenu.
