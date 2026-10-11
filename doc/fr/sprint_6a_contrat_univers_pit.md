# Sprint 6-A France — contrat d’univers PIT

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Date de clôture : 3 octobre 2026. Verdict : **`GO_6A_CONTRACT_ONLY`**.

Le Sprint 6-A transforme le `GO_RESEARCH_J1` du Sprint 5 en un contrat exploitable sans lui attribuer des garanties qu’il ne possède pas. Il sépare quatre périmètres qui ne doivent jamais être confondus :

1. **observable** : ligne historique autorisée par le manifeste limité Sprint 5 ;
2. **training** : ligne observable ayant ensuite passé les contrôles d’historique et de liquidité ;
3. **tradable** : ligne utilisable par un rejeu économique ;
4. **servable** : ligne autorisée en prédiction opérationnelle ou en live.

À ce stade, seul le premier périmètre peut être positif. `training` reste `UNKNOWN` jusqu’au Sprint 6-B. `tradable` et `servable` sont systématiquement `PROHIBITED`.

## Résultat sur le manifeste complet

Le contrôle a relu le rapport et le manifeste du Sprint 5, vérifié le SHA-256 annoncé, puis classé les 811 954 couples symbole/séance sans écriture métier.

| Mesure | Résultat |
| --- | ---: |
| Lignes analysées | 811 954 |
| Symboles présents | 490 |
| Séances présentes, rejets compris | 2 243 |
| `observable = ELIGIBLE` | 561 001 |
| `observable = INELIGIBLE` | 250 953 |
| `training = UNKNOWN` | 561 001 |
| `training = INELIGIBLE` | 250 953 |
| `tradable = PROHIBITED` | 811 954 |
| `servable = PROHIBITED` | 811 954 |

Les 561 001 lignes observables correspondent exactement aux lignes `RESEARCH_J1_ELIGIBLE` du Sprint 5. Le contrôle ne promeut donc aucune ligne supplémentaire. Les 490 symboles représentent tous les titres rencontrés dans le manifeste ; seuls 330 possèdent au moins une ligne de recherche admissible, dont 36 radiés.

Le rapport reproductible est stocké dans `artifacts/fr/sprint6a_universe_contract/report.json`.

## Politique pré-enregistrée

La politique est [config/universe_fr.yaml](../../config/universe_fr.yaml). Elle verrouille :

- `FR_EQ` et la route `fr_primary` ;
- la période 2018-01-01 au 2026-10-01 ;
- les MIC `XPAR`, `ALXP` et `XMLI` déjà admis par le contrat Sprint 5 ;
- un historique minimal futur de 252 séances ;
- le gate de liquidité en attente de 6-B ;
- `no_live`, `no_paper`, `no_serving` et `no_canonical_write` ;
- l’interdiction d’activer les périmètres tradable et servable.

Toute modification de la politique change son empreinte SHA-256. Une politique qui active le trading ou le serving est rejetée au chargement.

## Persistance préparée

La migration Alembic France `0006_fr_universe_contract` a été appliquée exclusivement à `alpha_trade_fr`. Elle crée :

### `fr_universe_runs`

Une ligne par snapshot de séance et politique, avec date de séance, heure de décision, latence de disponibilité, versions et empreintes, SHA-256 du manifeste, tier `RESEARCH_J1`, compteurs par périmètre et détails d’audit.

### `fr_universe_decisions`

Une ligne par instrument et snapshot, avec quatre états séparés, quatre motifs principaux, les raisons complètes et les états explicites de liquidité, capitalisation et spread. Une valeur absente reste `UNKNOWN`, jamais zéro.

Les deux tables sont actuellement **vides par conception**. Les remplir avant 6-B créerait de faux snapshots entraînables. La migration ne touche ni la base US ni la base CN.

## Commandes reproductibles

Audit du contrat complet :

```powershell
python -u -m service.fr.universe_contract_6a
```

Migration de la base France, lorsque `LOGIN_DB_FR` et `PASSWORD_DB_FR` sont disponibles :

```powershell
python -m alembic -c alembic_fr.ini upgrade head
```

## Ce que 6-A ne fait pas

6-A ne calcule pas encore l’ancienneté glissante, l’ADV/turnover, le spread historique, la capitalisation PIT, le benchmark France, les secteurs datés ni les conditions économiques des actions sur titres. Il ne publie aucun univers utilisable par le live, le paper trading, le serving ou le backtest économique.

## Gate suivant : Sprint 6-B

Le Sprint 6-B doit calculer, avec disponibilité J+1 :

1. le nombre de séances historiques réellement présentes avant chaque décision ;
2. la récence de la dernière barre connue ;
3. le prix de clôture connu ;
4. le volume et la valeur échangée glissante sur 20 séances ;
5. les états `KNOWN`, `UNKNOWN` et les motifs d’insuffisance ;
6. la couverture par année, symbole et statut actif/radié ;
7. une politique de seuils pré-enregistrée avant toute mesure économique.

Seulement après ce gate, `training` pourra passer de `UNKNOWN` à `ELIGIBLE` ou `INELIGIBLE`. Le périmètre `tradable` restera bloqué tant que les rendements économiques et actions sur titres ne seront pas validés.
