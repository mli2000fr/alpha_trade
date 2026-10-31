# Calendrier des résultats : correction des anciennes estimations

Correction du 30 octobre 2026, à partir de quatre réponses Finnhub archivées.

## Évolution : désactivation explicite avec -1

À la demande utilisateur, les sept presets de `config/capital_presets.yaml`
utilisent désormais `selector_earnings_blackout_days: -1`.

- `-1` désactive ce contrôle : aucune exclusion pour `earnings_blackout` dans
  un nouvel univers publié avec ce réglage. Le sélecteur ne vérifie plus la
  couverture du calendrier pour ce filtre et n'effectue plus sa lecture dédiée.
- `0` garde le blocage le jour de l'annonce uniquement.
- Une valeur positive conserve la fenêtre de protection existante.
- Les autres valeurs négatives sont refusées.

Le champ de l'écran accepte également `-1`. En interne, le profil du sélecteur
normalise cette valeur en `None` (contrôle désactivé). La publication d'univers
ne requiert plus la table du calendrier lorsque ce contrôle est désactivé.
Les nouveaux résultats du sélecteur neutralisent aussi les anciens flags
`earnings_blackout` hérités des scores, pour ne pas réactiver le veto en aval.
La collecte du calendrier et les autres protections restent indépendantes.

Cette évolution ne modifie pas les anciennes décisions. Après changement, il
faut republier l'univers (étape 6), puis renouveler les étapes 10 et 11 pour
évaluer de nouvelles décisions. Aucun ordre n'a été lancé par ce changement.

Validation de cette évolution : 92 tests ciblés réussis. Une passe élargie sur
`tests/test_alpha_scanner.py` rencontre cinq échecs sur des fixtures SQLite de
barres daily sans colonne `data_source`, désormais exigée par la sélection des
fournisseurs. Cette requête de sélection n'a pas été modifiée ici ; ces cinq
tests ne valident donc pas l'exécution complète du scanner.

## Problème et comportement corrigé

La clé `(symbol, earnings_date)` conservait une ancienne estimation lorsque
le fournisseur déplaçait une annonce. Le sélecteur pouvait alors bloquer un
titre sur une date devenue obsolète.

Les collectes Finnhub attachent désormais leur provenance, l'année fiscale
et l'heure de réception à chaque ligne normalisée. Lorsqu'une réponse contient
un réalisé EPS ou revenus, le writer rapproche les anciennes prévisions du
même titre et trimestre à moins de 30 jours. Il exige un seul réalisé dans
cette fenêtre, une identité d'instrument identique lorsqu'elle est disponible,
et une observation de la prévision plus ancienne que la réponse reçue.

L'ancienne ligne complète et la réponse de remplacement sont enregistrées dans
`stock_earnings_calendar_date_corrections`, puis la ligne obsolète est retirée
du calendrier actif, dans la même transaction. Une répétition de cette ancienne
prévision ne la réinsère pas tant que le réalisé correspondant est présent.
Une réponse sans réalisé ne peut plus effacer un réalisé déjà connu.

Les dates distantes, autres périodes, identités différentes, réponses ambiguës
ou sans année fiscale ne sont pas rapprochées. Les valeurs nulles et zéro sont
distinguées. Un réalisé SEC daté du dépôt n'est pas une preuve de date d'annonce
et ne déclenche pas cette correction.

La table d'archive est créée si nécessaire avant l'écriture métier ; son DDL est
dans `database/sql/stock/stock_earnings_calendar_date_corrections.sql`.
Si l'archivage échoue, le retrait et l'upsert de ce lot sont annulés.

## Correction appliquée et fenêtre à zéro

Pour la séance signal du **29/10/2026** :

| Titre | Date actuelle Finnhub | Anciennes estimations archivées | Bloqué avec ±2 jours | Bloqué avec 0 jour |
| --- | --- | --- | --- | --- |
| BAND | 29/10 | aucune | oui | oui |
| COHU | 28/10 | 27 et 29/10 | oui | non |
| UCTT | 27/10 | 26 et 28/10 | oui | non |
| SIMO | 28/10 | aucune | oui | non |

`selector_earnings_blackout_days` est défini dans `config/capital_presets.yaml`,
par preset de capital. La fenêtre est en **jours calendaires**, bornes incluses.
**0 signifie le jour de l'annonce uniquement**, pas la désactivation du filtre.
Lors de la correction initiale, le réglage opérationnel de deux jours avait été
conservé. L'évolution ci-dessus le remplace désormais par `-1`.

La disparition de ce motif ne garantit pas l'acceptation : les autres contrôles
de risque continuent à s'appliquer. Un nouvel univers doit être publié avec le
nouveau réglage pour que le risque puisse le consommer. Un ancien run de risque
ou de filtre conserve ses liaisons aux snapshots exacts déjà archivés.

Le snapshot `universe-eb5c1ce459704828a4735e5d85ef4c3d` et ses quatre exclusions
ont été vérifiés inchangés. Les informations reçues le 30/10 ne sont pas
réinjectées dans une décision historique du 29/10 comme si elles étaient connues
auparavant. Aucun risque ni ordre n'a été relancé pendant cette correction.

Preuves locales :
`artifacts/operations/earnings_calendar_reconciliation/20261030T002614Z/`
contient `finnhub_response.json`, `before_calendar.json` et `report.json`.

## Validation

51 tests ciblés réussis : rapprochement et refus prudents, trace complète,
non-réapparition d'une estimation remplacée, collecte/reprise, writer de
référence et publication de l'univers. Les fenêtres 0, 1 et 2 jours sont
vérifiées sur les quatre titres. La correction SQL réelle a archivé quatre
lignes et confirmé que l'ancien snapshot n'avait pas changé.
