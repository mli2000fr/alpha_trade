# Protections OCO, break-even, trailing et watcher

Retour : [références Execution](README.md)

Le `ProtectionContract` décrit SLA, stop/TP et état attendu. `build_oco_group` relie les enfants ; `check_protection_state` vérifie couverture et cohérence. Les enfants sont soumis après fill et leur quantité ne dépasse jamais la position.

`protection_watcher.py` synchronise positions/ordres, identifie protections manquantes/orphelines, applique transitions break-even/trailing et écrit heartbeat/événements. Il ne sélectionne pas de nouveaux trades.

`protection_break_even.py` évalue le progrès minimal. `protection_transition.py` calcule le nouvel état ; `protection_state_bridge.py` assure la persistance. Le peak, le côté, le moment d'activation et le previous peak font partie du contrat.

Une position manuelle peut être adoptée seulement si politique active, compte correct et stop dédié. En live, watcher malsain est un probe critique. Toute analyse doit distinguer protection configurée, soumise, acceptée et effectivement active.

## Pourquoi le watcher existe

L'executor ne peut pas garantir que tous les enfants sont soumis au même instant que l'entrée : partial fill, indisponibilité broker ou interruption peuvent laisser une position sans protection. Le watcher assure la convergence après le run. Il rafraîchit systématiquement l'état broker au début de chaque cycle, même si des items pending existent déjà, afin de détecter les opérations manuelles récentes.

## Entrées du cycle

Le repository retourne trois ensembles : `ProtectionWatchItem` en attente de transition, parents filled sans enfants ouverts, et positions broker orphelines sans parent ENTRY. Chaque ensemble a son traitement et ses compteurs ; ils ne doivent pas être fusionnés en une simple liste de positions.

## Traitement d'un item suivi

Le watcher résout broker/config par `(broker_mode, account_id)` avec cache, observe parent/enfants et vérifie le trigger. Un item non déclenché reste pending. Un item terminal n'est pas resoumis. Si un trailing existe déjà, le compteur `skipped_existing_trailing` évite le doublon.

Lors d'une transition initial stop → trailing, il faut annuler/remplacer dans un ordre qui évite une fenêtre non protégée et un double stop. Les échecs d'annulation et de soumission sont séparés. L'événement et l'état DB doivent refléter ce que le broker a accepté, pas uniquement l'intention.

## Filet de sécurité protections manquantes

Pour chaque parent ENTRY rempli sans take-profit ni stop ouvert, `_arm_missing_protections` reconstruit TP et SL depuis le parent, le fill et la configuration. Les métriques `armed_missing_protections` et `..._failed` mesurent le rattrapage. Les quantités proviennent du fill/position observé.

Pour une entrée adoptée manuellement, `use_manual_buy_stop=true` choisit le pourcentage de stop dédié. Cette règle évite d'appliquer arbitrairement le stop ML/ATR d'un trade qui n'a jamais eu de target risque.

## Adoption d'un achat orphelin

`adopt_orphan_buy` crée un parent `adopted_entry` idempotent à partir de la position broker. Le watcher construit ensuite une row synthétique contenant run, compte, symbole, quantité, prix moyen et clés, puis arme TP/SL. L'adoption réussie et l'échec d'armement ont des compteurs distincts.

Une position short manuelle ou un cas non supporté ne doit pas être traité comme achat long par défaut. Le scope actuel doit être vérifié dans `orphan_adoption.py` avant extension.

## Time-stop effectif

Après protections/orphelins, `_apply_time_stop_exits` examine les positions stagnantes selon `load_time_stop_config_from_yaml`. Les compteurs distinguent candidates, triggered, submitted et failed. Le simple fait que la config contienne une durée ne prouve pas un fill : neutralisation, trailing actif, jours de marché et ordre rejeté peuvent produire zéro sortie.

## Mode once et mode service

Le run unitaire produit un summary par execution run. Le mode service boucle avec interval actif/idle, heartbeat, max iterations et compteur de failures consécutives. Son summary expose cycles with work, idle cycles, heartbeat count, dernière activité et état d'arrêt.

Un heartbeat vivant ne garantit pas que les protections convergent ; surveiller aussi failures, pending et missing protections. Inversement, un cycle idle peut être normal si aucune position n'est ouverte.

## Run summary

Les champs importants sont : source exec run, trade date, account, broker mode, watched/triggered/transitioned/pending/terminal, existing trailing, cancel/submit failures, missing protections, fractional blocked, orphan adoption et time-stop. Le summary est persisté dans les business summaries avec parent/entity run links.

## Quantités fractionnaires

Certaines protections broker ne supportent pas les fractions selon order type/politique. `fractional_policy_blocked_items` rend ce cas visible. Ne pas arrondir silencieusement vers une quantité supérieure à la position. Si une fraction reste non protégée, l'incident doit rester ouvert.

## Commandes et exploitation

Le script de watcher accepte un run/compte, limite et modes once/service selon son CLI. `run_execution.py --auto-watcher` lance un processus détaché après exécution. L'IHM possède un bridge Windows et une supervision de heartbeat.

Procédure avant live : lancer once sur paper, vérifier zéro protection manquante, comparer ordres broker, tester restart service, simuler partial fill/rejet, puis vérifier que le preflight live bloque un watcher stale.

## Incidents

| Incident | Réponse |
|---|---|
| cancel stop échoue | réobserver broker avant submit trailing |
| TP existe, stop manque | armer uniquement le membre manquant |
| deux trailing ouverts | geler remplacement, réconcilier et annuler l'excédent |
| position orpheline | vérifier compte/origine, adopter si autorisé |
| fractional blocked | réduire/fermer selon politique ou escalader |
| service crash loop | inspecter consecutive failures et dernière exception |
| time-stop inattendu | vérifier config effective, séances et état trailing |

## Tests

Trigger atteint/non atteint, trailing déjà présent, cancel failure, submit failure, partial fill, filet missing TP/SL, orphan idempotent, stop manuel, fractionnaire, time-stop neutralisé/actif, heartbeat, mode idle et isolation multi-comptes.
