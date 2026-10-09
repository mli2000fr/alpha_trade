# Sprint 17-B — Trading212 Invest DEMO, qualification en lecture seule

## Résultat du 8 octobre 2026

**Mise à jour du 9 octobre (Paris) :** les six endpoints répondent désormais
HTTP 200, historique inclus. La nouvelle preuve est
`artifacts/fr/research/trading212_demo_17b/demo-20261008223330840725/report.json`.
Le dossier porte une date UTC du 8 ; la lecture a eu lieu à 00 h 33 Paris le 9.
Voir [17-D](sprint_17d_reconciliation_simulee.md). Les résultats ci-dessous
décrivent la première lecture et ne remplacent pas cette nouvelle preuve.

Le compte de démonstration est accessible et sa devise principale est **EUR**.
Le POC a exécuté six GET ; cinq ont réussi et l'historique des ordres a répondu
HTTP 403. Statut : **PARTIAL_READONLY_NOT_RELEASED**. Aucune écriture SQL,
aucun ordre, aucun appel au compte réel, aucune activation de batch ou de route.

Preuves locales :
`artifacts/fr/research/trading212_demo_17b/demo-20261008213019198788/report.json`.
La première version du rapport nommait ce succès partiel
`FAILED_READONLY_NOT_RELEASED` et affichait zéro pour l'historique indisponible ;
le collecteur distingue désormais succès partiel et historique inconnu (`null`).
Cette preuve originale reste conservée sans modification.

| Lecture | Résultat |
| --- | --- |
| Compte | HTTP 200, EUR |
| Places / calendriers | HTTP 200, 17 entrées |
| Instruments | HTTP 200, 17 048 entrées, tous marchés confondus |
| Positions | HTTP 200, aucune position |
| Ordres ouverts | HTTP 200, aucun ordre |
| Historique des ordres | HTTP 403, indisponible, pas un historique vide |

Le contrôle porte sur **233 titres du dossier de revue FR**, et non sur
l'intégralité de l'univers FR : 171 correspondances uniques ISIN + STOCK + EUR,
1 ambiguë et 61 absentes. Ce résultat décrit le référentiel du courtier, pas
la négociabilité historique ni l'acceptation effective d'un ordre.
`instrument_matches.json` détaille les absences et ambiguïtés.

## Sécurité et reproductibilité

Module : `service/fr/trading212_demo_17b.py`. Identifiants exclusivement dans
`TRADING212_DEMO_API_KEY` et `TRADING212_DEMO_API_SECRET`.
Les valeurs et en-têtes d'authentification ne sont jamais affichés.
Le client n'expose que six endpoints GET autorisés, une fois chacun, sur
`https://demo.trading212.com`. Redirections interdites, TLS vérifié, aucun
retry automatique, aucune pagination supplémentaire, aucune bascule LIVE.
L'historique se limite à une page de 50 éléments ; une suite éventuelle est
signalée comme tronquée, jamais suivie aveuglément.

Les réponses originales, horodatages et empreintes SHA-256 sont archivés
localement. **Les fichiers `*.private.json` contiennent potentiellement des
données privées de compte : ne pas les publier ni les joindre à un rapport
public.** Le rapport de synthèse ne contient ni identifiant ni solde du compte.

```powershell
python -u -m service.fr.trading212_demo_17b
python -m pytest tests/test_fr_trading212_demo_17b.py tests/test_fr_broker_contract_17a.py --no-cov -q
```

34 tests passent sur ces deux modules : restriction DEMO/GET, appels uniques,
redirections et erreurs HTTP, masquage des erreurs transport, limite de taille,
jointure des calendriers, ambiguïtés, devise, archives et zéro ordre/SQL.

## Réserves et prochaine étape

1. Vérifier la permission **History – Orders** de la clé DEMO. Le 403 peut
   provenir d'une permission ou restriction du compte ; sa cause précise
   n'est pas démontrée. Ne pas activer **Orders – Execute** pour ce POC.
2. La jointure `workingScheduleId` utilise les identifiants des calendriers
   imbriqués dans les places, pas l'identifiant de la place elle-même.
   Un nom de place/calendrier ou une cotation en EUR **ne prouve pas le MIC
   réel d'exécution XPAR**. Ce point demeure non qualifié.
3. Ce module n'est pas un `ExecutionBrokerPort`. Réconciliation des fills,
   protections, annulation, idempotence et parité du portefeuille restent à
   implémenter/qualifier avant toute exécution.
4. Les réserves de données/signal du Sprint 16 restent en vigueur. Le Sprint
   17 n'est pas terminé, et aucun GO PAPER ou LIVE n'est accordé.

Documentation officielle consultée : [API Trading212](https://docs.trading212.com/api).
L'API est bêta ; l'accès DEMO et l'accès réel sont distincts.

Voir [17-A](sprint_17a_preparation_execution.md) et
[planning FR](sprint_planning_integration_marche_francais.md).
