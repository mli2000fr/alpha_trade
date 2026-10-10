# TODO — Sprint 18-C après la clôture CN du 8 octobre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Plan / TODO : ne vaut ni validation des données, ni autorisation broker. Les dépendances et blocages actuels priment sur l'ordre des sprints. [Référence actuelle](README.md).
<!-- doc-status:end -->

**Statut au 1er octobre : en attente de la séance du 8 octobre. Ne rien lancer maintenant.** Le plan prospectif de 12 intentions est déjà figé ; le contrat de recherche CN 2026 est installé et le préflight est `READY_FOR_RESEARCH_ATTEMPT`. Aucun job quotidien shadow n'est installé.

## À faire après clôture, manuellement

1. Vérifier que le 8 octobre est une séance ouverte effective dans `market_sessions`, que l'heure de clôture canonique est passée et que la collecte BaoStock/canonique du jour est terminée. Ne pas suppléer une barre absente avec une donnée ultérieure ou ajustée.
2. Vérifier les 12 instruments du plan : barre brute, statut de négociation, volume, `available_at`, limites individuelles et facteurs non classifiés. Les absences et suspensions doivent rester visibles ; elles ne justifient pas de modifier la sélection figée.
3. Relancer le préflight en lecture seule :

   ```powershell
   python -m service.market.cn_shadow_runner_18c --phase preflight --decision-date 2026-10-08
   ```

   Exiger `READY_FOR_RESEARCH_ATTEMPT` et zéro `blocking_reasons`. Vérifier également que le marché CN live reste désactivé.
   Après la clôture canonique, exécuter aussi l'inventaire détaillé des 12 intentions :

   ```powershell
   python -m service.market.cn_shadow_runner_18c --phase observation-preflight --decision-date 2026-10-08
   ```

   Cette phase est **read-only** et renvoie `authorizes_attempt=false` dans tous les cas. Avant que la séance et sa clôture canonique existent, `WAITING_FOR_SESSION` est normal (constaté au 01/10). Avant la clôture, `WAITING_FOR_CLOSE` est normal. Après clôture, examiner `observations` et `issues` : barres brutes disponibles, statut, open/close, volume, limites, facteurs non classifiés, provenance et `observed_at_utc`. Une barre absente n'est jamais imputée en fill ; le rapport ne lance ni `attempt` ni `mark`.
4. Seulement après les trois vérifications, exécuter **une fois** la tentative shadow, avec opt-in explicite des règles et coûts de recherche :

   ```powershell
   python -m service.market.cn_shadow_runner_18c --phase attempt --decision-date 2026-10-08 --allow-research-rules --allow-research-proxy
   ```

   Contrôler `artifacts/research/cn_shadow_18c/reports/attempt-2026-10-08.json` et les preuves individuelles sous `attempts/2026-10-08/` : exactement 12 résultats, états et motifs de non-fill, IDs/version des règles, profil de coût, horodatages, `not_broker_execution=true`, aucune écriture DB et aucun appel broker. En cas de données insuffisantes, rapporter `UNVERIFIABLE` plutôt qu'inférer un fill.
5. Après une **séance ultérieure réellement clôturée** et ses données disponibles (le 9 octobre seulement si cette séance est confirmée), lancer la phase `mark` avec sa date. Comparer les variations de prix séparément des tentatives ; ne pas les appeler rendement réalisé ou profit net.
6. Mettre à jour le document 18-C avec les nombres réels de `HYPOTHETICAL_FILL`, `NOT_FILLED`, `UNVERIFIABLE` et les raisons. Ne pas conclure que l'Oracle prédit LONG sur cet échantillon : le pilote porte sur l'exécution hypothétique, pas sur un GO directionnel ou production.

## Conditions d'arrêt

- Préflight revenu à `BLOCKED_CONTRACT` ou contrat modifié/ambigu.
- Plan ou export Oracle dont l'empreinte ne correspond plus.
- Clôture non passée, barres/limites canoniques indisponibles ou statut contradictoire.
- Preuve de tentative déjà publiée avec un état différent.
- Toute tentative d'activer le routage broker, le paper/live CN ou un scheduler pour ce pilote.

Le contrat de coûts reste `RESEARCH_PROXY` : commission et slippage sont des hypothèses. Pour un usage économique ou réel, il faudra un courtier, ses frais constatés, une preuve de liquidité à l'ouverture et une validation indépendante.
