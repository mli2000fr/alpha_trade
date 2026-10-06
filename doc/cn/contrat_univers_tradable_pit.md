# CN_A — Convention de radiation et contrat de négociabilité PIT

Statut au 25 septembre 2026 : **contrat figé, testé et utilisé par les 1 942 snapshots du Sprint 8 ; audit global `PASS`**. Ce document complète l'[audit Sprint 7-B](sprint_7b_audit_final_2026_09_24.md) et la [validation Sprint 8](sprint_8_validation_finale_2026_09_25.md).

## Date de radiation : borne inclusive, avec exception terminale explicite

Dans `instruments`, `delisting_date` reste une **borne inclusive de vie du titre** : une séance ouverte à cette date peut posséder une barre et ne doit pas être supprimée mécaniquement. Parmi les 223 actions radiées du périmètre 2018–2025, **200 ont une barre à `delisting_date` et 23 n'en ont pas**. La date seule ne prouve donc ni l'exécution ni son impossibilité.

Le contrôle de couverture attend les séances ouvertes de `listing_date` à `delisting_date` inclusivement. Une absence n'est acceptée comme **exception terminale documentée** que si elle porte exactement sur `delisting_date`, jour ouvert du calendrier, et si aucune barre n'existe. L'exception reste visible dans `cn_canonical_coverage_metrics.details_json.delisting_day_no_bar` ; elle n'est ni transformée en fausse barre ni soustraite silencieusement du dénominateur. `unexplained_missing` doit rester à zéro. Le recalcul `cn-s7b-coverage-20260924183751-a8341df5` donne 23 exceptions terminales, zéro autre absence et 31/31 segments `PASS`.

Pour le replay d'exécution : sans barre ce jour-là, **aucun fill vérifiable** ; dès le lendemain de `delisting_date`, le titre est exclu. Cela conserve les titres radiés dans l'historique pré-radiation, sans biais de survivance.

## Deux temps différents : décision et vérification

Le futur univers ne doit jamais appliquer à l'ouverture une information apparue après clôture :

1. **Avant séance / décision** : vérifier la fenêtre de cotation et seulement les statuts et limites dont `available_at <= decision_at`. Le résultat `CANDIDATE` signifie « peut être étudié », non « ordre exécutable ».
2. **Après séance / replay** : vérifier présence de barre, statut source et limite dérivée. Ces constats servent à qualifier l'exécutabilité des opérations simulées et à auditer les anomalies, **pas** à effacer ex post un candidat de la sélection du matin.

Le contrat déterministe est dans [cn_tradability_contract.py](../../service/market/cn_tradability_contract.py), avec tests dans [test_cn_tradability_contract.py](../../tests/test_cn_tradability_contract.py). Le futur Sprint 8 doit brancher ce contrat aux lignes PIT et enregistrer séparément candidats initiaux, rejets et fills non vérifiables.

| Cas | Décision avant séance | Vérification de séance | Règle |
|---|---|---|---|
| 23 dates de radiation sans barre | Ne pas anticiper l'absence si elle est encore inconnue | `EXCLUDED / NO_SESSION_BAR` | Aucun fill inventé ; exception terminale visible en couverture |
| 8 lignes `SUSPENDED|SOURCE_CONFLICT` | Exclure seulement si le conflit est déjà connu à `decision_at` | `EXCLUDED / SOURCE_STATUS_CONFLICT` | `is_tradable=0` reste conservé ; jamais traité comme `TRADE` |
| 181 lignes `OBSERVED_OUTSIDE_DERIVED_LIMIT_V1` | Ne pas utiliser la contradiction OHLC du soir le matin | `UNVERIFIABLE / UNVERIFIED_PRICE_LIMIT` | Exclure du sous-ensemble de fills certifiés jusqu'à limite indépendante ou règle validée |
| Limite absente | Ne pas en inférer une borne de prix | `UNVERIFIABLE / UNVERIFIED_PRICE_LIMIT` | Même politique prudente |
| Séance ordinaire avec barre et politique de limite connue | Candidat si les autres règles PIT passent | `DATA_CHECKS_PASSED` | Ne prouve pas le passage d'un ordre : il faut encore coûts, carnet, participation et règles d'exécution |

Les 181 limites restent **dérivées et non officielles** ; `UNVERIFIABLE` ne signifie pas que le titre était réellement impossible à négocier. Les retirer rétroactivement de l'échantillon des signaux créerait une fuite d'information. Pour les rapports, publier les résultats principaux avec la population candidate figée et un sous-ensemble de fills vérifiés, ainsi que le taux et le coût potentiel des cas non vérifiables.

## Ce qui reste au Sprint 8

- Construire le snapshot quotidien du référentiel et des statuts `as-of`, sans utiliser `is_active` actuel pour reconstruire le passé.
- Appeler le contrat avant sélection et après replay, avec `decision_at` et `available_at` explicites ; conserver les raisons et les compteurs par jour.
- Vérifier sur la population complète les 23, 8 et 181 cas ; les nombres sont ceux du backfill 2018–2025, non des constantes applicatives.
- Valider les règles de suspension, limites officielles si disponibles et microstructure avant de déclarer les simulations de fills réalistes. Aucun GO live ou backtest de production n'est implicite dans le `PASS` de couverture.
