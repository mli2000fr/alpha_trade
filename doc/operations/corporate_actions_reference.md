# Corporate actions — dividendes, splits et réconciliation

Retour : [corporate actions](../17_corporate_actions.md)

`provider.py` définit l'interface et implémentations Alpaca/EODHD. `engine.py` orchestre sync/apply ; `processors.py` applique ; `db_io.py` persiste ; `reconciliation.py` vérifie ; Yahoo sert de cross-check.

La sync normalise type, symbole, dates, ratio/montant et provider vers un événement unique. Le scope portfolio-only part des positions broker snapshot. L'application crée une row distincte liée à l'événement.

Dividende : calculer cash depuis quantité éligible et montant, écrire `portfolio_cash_ledger` une seule fois. Split : multiplier quantité et diviser cost basis selon ratio, conserver valeur notionnelle hors marché. Les prix étant split-adjusted, ne pas réajuster la série.

États pending/applied/failed permettent reprise. Avant replay, vérifier application et ledger. La réconciliation compare positions/cash et signale écarts. Un cross-check divergent n'écrase pas silencieusement le provider canonique.

## Contrat fonctionnel complet

Le module ne modifie jamais `stock_bars` ni `stock_bars_daily`. Les prix sont déjà split-adjusted en amont. Il ne traite que la comptabilité du portefeuille : quantité et coût moyen pour les splits, cash pour les dividendes. Le total return est donc MTM des positions plus ledger cash cumulé.

## Types et états

`CaType` accepte `cash_dividend`, `special_dividend`, `split` et `reverse_split`. `CaStatus` accepte `pending`, `applied`, `skipped`, `failed`. `CorporateActionEvent` conserve provider/id provider, symbole, type, ex-date, montant/devise ou ratio, dates announcement/record/payable, payload brut, id DB et erreur.

`validate()` contrôle symbole, type, ex-date et les champs propres au type. Un dividende exige un montant positif. Un split exige les composantes de ratio valides. L'ingestion et l'application revalident toutes deux : une ancienne ligne corrompue ne passe pas parce qu'elle est déjà en DB.

## Clé d'idempotence

L'événement calcule une clé stable depuis ses attributs métier. L'application recalcule une clé scopée par `account_id` et vérifie aussi la clé legacy. Cela permet d'appliquer un même événement sur deux comptes sans double application dans un même compte, tout en reconnaissant les événements antérieurs à la migration multi-comptes.

## Synchronisation pas à pas

1. valider `batch_size >= 1` ;
2. résoudre `symbols=None` comme scope global, `[]` comme aucun travail ;
3. si `skip_existing` avec liste, retirer les symboles ayant déjà des événements ;
4. découper la liste en lots ordonnés ;
5. appeler `provider.fetch_events(symbols,start_date,end_date)` ;
6. valider chaque événement ;
7. insérer immédiatement après chaque appel provider ;
8. compter `fetched`, `inserted`, `duplicates`, `invalid`.

Avec `symbols=None`, `skip_existing` est ignoré avec warning car le repository ne peut pas exclure proprement un scope global sans liste résolue. L'absence de symboles n'est pas une erreur provider.

## Scope portfolio-only

Le CLI résout les positions du compte à partir des snapshots broker. Il faut donc avoir exécuté/synchronisé `execution_engine` au moins une fois. Le scope réduit quota et bruit. `--all-symbols` est une opération différente et plus coûteuse. Le provider effectif suit la configuration/résolution du module, tandis que Yahoo reste un contrôle indépendant.

## Application pas à pas

1. charger les événements pending avec `ex_date <= as_of` ;
2. charger le dernier snapshot de positions du compte, ou l'override de test ;
3. construire `PositionSnapshot` par symbole ;
4. revalider l'événement ;
5. vérifier la clé d'idempotence scopée/legacy ;
6. vérifier une quantité détenue positive ;
7. dispatcher au processeur du type ;
8. écrire application et éventuel ledger ;
9. mettre à jour la position en mémoire pour les événements suivants ;
10. marquer l'événement appliqué ;
11. en exception, stocker un message tronqué et compter failed.

Un événement sans position est `skipped`, pas `applied`. Une absence globale de positions produit un warning et chaque événement est traité selon cette règle.

## Calcul d'un dividende

`cash_amount = round(qty * amount_per_share, 2)`. La quantité et le coût moyen restent inchangés. L'application trace avant/après et `cash_impact`. Le ledger utilise `entry_type=dividend_credit`, devise de l'événement et une description explicite.

Le code se base sur le snapshot de position fourni au moment de l'application. Pour une exactitude fiscale parfaite autour des record dates, il faudrait un historique de détention adapté ; ne pas présenter le calcul actuel comme une reconstitution lot/date complète si le snapshot ne la fournit pas.

## Calcul d'un split

`raw_new_qty = old_qty * ratio` et `new_cost_basis = old_cost / ratio`. Pour ratio >= 1, la quantité est arrondie à 6 décimales. Pour reverse split, le code prend le floor et isole la fraction.

Si la fraction dépasse 0,001, le cash-in-lieu est estimé par `fraction * avg_entry_price` et arrondi à 2 décimales. C'est une approximation au cost basis, pas nécessairement le cash exact versé par l'émetteur/broker. Le ledger porte `cash_in_lieu`.

## Ordre de plusieurs événements

Après un split, le `position_map` en mémoire est mis à jour avant l'événement suivant. L'ordre des pending rows fourni par le repository est donc fonctionnellement important. Les événements d'un même symbole/date doivent être ordonnés de façon déterministe et testés.

## Tables et transactions

- events : faits provider normalisés, statut et erreur ;
- applications : preuve avant/après par compte ;
- cash ledger : flux financiers par compte ;
- broker position snapshots : source de quantité détenue.

L'application et son ledger doivent être atomiques dans le repository. Si l'application est insérée mais pas le ledger, la reprise idempotente risque de sauter le cash ; ce scénario doit être couvert par transaction/test.

## CLI opérateur

```powershell
python -m corporate_actions sync --portfolio-only --account default
python -m corporate_actions apply --as-of 2026-08-29 --account default
python -m corporate_actions status
python -m corporate_actions run --portfolio-only --account default
```

Les options sync incluent symbols, all-symbols/portfolio-only, skip-existing, batch-size, start/end, account et contrôles provider. Toujours lire `--help` du code courant.

## Réconciliation

Après apply, comparer quantité et cost basis attendus aux positions broker, puis cash ledger aux relevés. `CaReconcileDiff` décrit les écarts. Le cross-check Yahoo compare les dividendes mais ne réécrit pas le provider canonique sans décision explicite.

## Scénarios de panne

| Symptôme | Cause probable | Reprise |
|---|---|---|
| zéro événement | scope vide, provider, dates | vérifier positions/scope et fenêtre |
| beaucoup de duplicates | replay normal ou clé trop large | inspecter clés, ne pas purger |
| invalid | mapping/type/montant/ratio | conserver payload et corriger adapter |
| no position | snapshot absent ou compte faux | synchroniser broker et reprendre |
| ledger absent | transaction partielle | geler et réparer atomiquement |
| split double | idempotence/account | vérifier application scoped/legacy |
| cash-in-lieu différent | approximation vs broker | rapprocher relevé et ajuster explicitement |

## Tests obligatoires

Validation de chaque type ; duplicate sync ; idempotence par compte et legacy ; dividende fractionnaire ; split forward/reverse ; seuil fraction 0,001 ; plusieurs événements successifs ; absence position ; exception repository ; scope EODHD portfolio ; total return avec dividendes ; preuve Z3 d'idempotence.

## Modifier le module

Pour ajouter un type : étendre type/validation, adapter providers, migration éventuelle, processeur pur, dispatch engine, application/ledger, réconciliation, CLI/status, tests d'idempotence et cette documentation. Ne jamais ajouter une modification des prix dans ce module sans revoir la convention globale.
