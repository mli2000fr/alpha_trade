# E20-A — Disponibilité PIT de la fenêtre d’ouverture après Oracle

## Verdict

E20-A est terminé en `BLOCKED_NO_OPENING_WINDOW_DATA`. Ce verdict ne rejette
pas l’hypothèse directionnelle : il établit que les données locales ne permettent
pas encore de la tester.

Aucune règle LONG/SHORT n’a été évaluée, aucun modèle n’a été entraîné et aucune
table de serving n’a été modifiée.

Artefact canonique :

```text
artifacts/research/oracle_opening_window_availability/e20a-opening-availability-20260913211726
```

## Population Oracle auditée

La référence est le batch dynamique P0f
`model-factory-20260909051302-323684`, fichier `_oracle_oof_gate.parquet`.

| Mesure | Valeur |
|---|---:|
| Événements TOP20 OOF | 582 306 |
| Dates de signal | 1 763 |
| Symboles | 1 472 |
| Première date de signal | 2018-07-05 |
| Dernière date de signal | 2025-07-10 |
| Séances d’ouverture attendues J+1 | 2018-07-06 → 2025-07-11 |

## Disponibilité locale observée

`stock_opening_window_bars` existe, mais contient zéro ligne. Il n’existe donc
aucun chevauchement événement × symbole entre l’Oracle et la fenêtre J+1.

Le seul run `oracle_opening_window_sync` enregistré a été lancé le dimanche
13 septembre 2026. Il s’est terminé `COMPLETED_WITH_WARNINGS` : 1 798 symboles
demandés, zéro reçu et zéro persisté, parce que le NYSE était fermé. Ce résultat
est normal et ne constitue pas une panne Alpaca.

## Contrat des gates

E20-A distingue deux niveaux d’autorisation :

| Niveau | Minimum |
|---|---|
| E20-B règles simples | 126 séances, 5 000 événements, couverture OPEN ≥ 70 %, fenêtre 30 min complète ≥ 60 % |
| E20-C modèle mutualisé | 378 séances, 20 000 événements, quatre semestres, mêmes gates de couverture |

Une fenêtre 30 minutes est considérée complète à partir de 24 barres sur les
30 minutes attendues. Toute ligne dont `available_at < bar_timestamp` viole le
contrat PIT ; le taux accepté est zéro. Le contrat attendu est
`provider=alpaca`, `feed=sip`, `adjustment_mode=raw`.

Tous les gates de volume et de couverture échouent actuellement. Le contrôle
temporel ne détecte aucune violation, mais il ne porte sur aucune barre.

## Point essentiel : collecter seulement demain ne suffit pas pour l’ancien Oracle

Les scores OOF de la référence s’arrêtent en juillet 2025. Des fenêtres
d’ouverture collectées à partir de septembre 2026 ne peuvent pas être jointes à
ces anciens signaux. Deux voies scientifiquement valides existent :

1. backfiller les minutes Alpaca 2018–2025 avec un contrat fournisseur, une
   capacité et une couverture validés ;
2. accumuler conjointement de nouveaux scores Oracle shadow et les fenêtres
   J+1 prospectives, puis attendre la maturité des gates.

La seconde voie exige également la reprise de barres quotidiennes fraîches : un
Oracle ne peut pas produire un signal nouveau à la clôture J si son univers EOD
reste figé.

## Sorties du harnais

La commande :

```powershell
python -u -m modelFactory.oracle_opening_window_availability_audit
```

produit :

- `report.json` : population, contrat, runs de collecte, gates et verdict ;
- `opening_symbol_session_coverage.parquet` : couverture minute par titre/séance ;
- `oracle_coverage_by_session.csv` : couverture des événements Oracle par date ;
- `oracle_coverage_by_symbol.csv` : biais de couverture par titre.

Ces fichiers resteront vides ou nuls tant qu’aucune barre Opening Window ne sera
persistée sur une date compatible avec un signal Oracle.

## Prochaine action autorisée

Ne pas ouvrir E20-B ni E20-C. Après un premier run réussi un jour de marché,
relancer E20-A pour contrôler la collecte. Ensuite, choisir explicitement entre
un backfill historique Alpaca et une validation prospective conjointe. Aucun
seuil directionnel ne doit être choisi avant ce choix.

Voir aussi [collecte Opening Window](oracle_opening_window_alpaca.md) et
[registre des expériences](experiences_done.md).
