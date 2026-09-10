# Faisabilité des données de prêt de titres

## Verdict

Audit réalisé le 7 septembre 2026.

**Statut : `BLOCKED_NO_PIT_HISTORY`.** Les données présentes dans l'application
ne permettent pas de tester proprement `borrow fee`, `utilization` ou
`shares available` sur les événements Oracle historiques. Cette piste n'est pas
rejetée économiquement : elle est non testable avec les sources actuellement
disponibles.

## Données locales

- Alpaca fournit à l'instant courant `shortable` et `borrow_status` au niveau de
  l'actif. Ce snapshot sert au gate de risque live, sans historique local.
- Eroya expose le short interest et le short volume déjà évalués, mais aucun
  historique borrow fee/utilization/shares available dans le catalogue intégré.
- Le backtest utilise un taux d'emprunt paramétrique ; ce coût ne constitue pas
  une feature observée et ne doit jamais être présenté comme un signal PIT.

Le statut Alpaca est utile pour empêcher une vente à découvert non exécutable.
Il ne permet pas d'apprendre une relation passée avec D1/D10.

## Évolution Alpaca de septembre 2026

Alpaca déprécie `easy_to_borrow` au profit de `borrow_status` et annonce la
suppression de l'ancien champ le 22 septembre 2026 :

https://docs.alpaca.markets/us/changelog/2026-06-05-borrow-status-6b96a5a

Les deux chemins live de l'application consomment désormais le nouveau champ en
priorité, conservent le fallback legacy et restent fail-closed si la valeur est
absente ou inconnue. Une valeur inconnue sur un actif shortable devient HTB et
exige un locate ; elle ne devient jamais ETB implicitement.

## Sources externes examinées

### Alpaca

Le statut ETB/HTB et les quotes de locate sont des informations actuelles et
spécifiques au compte. La documentation consultée ne propose pas un historique
PIT pluriannuel directement exploitable pour la recherche :

https://docs.alpaca.markets/us/docs/margin-and-short-selling

### Interactive Brokers

IBKR documente les shares shortables et fee rates courants via TWS/FTP. Cela
peut servir à une collecte prospective, mais ne fournit pas dans le contrat
consulté le panel historique 2018–2025 requis :

https://interactivebrokers.github.io/tws-api/tick_types.html

### FINRA SLATE

SLATE doit à terme publier activité de prêt et distribution des taux par titre.
Son lancement est toutefois repoussé au 28 septembre 2028. Il ne peut donc pas
alimenter la campagne actuelle :

https://www.finra.org/filing-reporting/slate

## Condition de reprise

Réouvrir uniquement avec un panel qui fournit, pour chaque symbole et date :

- timestamp de disponibilité vérifiable ;
- borrow fee ou rebate rate ;
- quantité disponible ;
- utilization si disponible ;
- changements de statut ETB/HTB/non-shortable ;
- couverture quotidienne suffisamment dense avant la décision J.

Le premier gate est une couverture d'au moins 60 % du pool Oracle, avec au
moins 40 % chaque année. Sans ce gate, aucun modèle ne doit être entraîné.

Une collecte prospective Alpaca/IBKR peut être utile au risque d'exécution et à
une future étude, mais elle ne remplace pas une validation historique OOF.
