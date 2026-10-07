# Sprint 12-B — Moteur de rejeu économique FR

État au 4 octobre 2026 : **moteur de recherche implémenté et testé ; rejeu des
données historiques réelles encore bloqué par leurs preuves**. Ce n'est ni une
mise en production, ni un GO de rentabilité, ni une clôture de tout le Sprint12.

Complément12-D : [refus causal sans transaction d'ouverture et revue gratuite](sprint_12d_levee_blocages_gratuits.md).
Le statut `opening_execution.status: NO_OPENING_TRANSACTION` exige ouverture
absente et preuves vérifiées ; il conserve un ordre rejeté sans coûts ni cash
consommé. Un simple prix manquant reste bloquant. Pas de tape réelle promue.

## 1. Périmètre et composants

Le service `service/fr/portfolio_replay_12b.py` est indépendant des moteurs US/CN.
Il ne lit ni n'écrit de table et ne modifie aucun modèle. La CLI est
`modelFactory/fr_portfolio_replay_12b.py`. Les tarifs viennent du fichier
`config/markets/fr_execution_research_v1.yaml`, les preuves fiscales de
`config/taxes/fr_ttf_eligibility.yaml`.

Le périmètre est LONG au comptant, EUR, actions entières, capital et capacité
paramétrables, sans emprunt, short ou empilement d'une même action. Pour la
comparaison11-A : 4 000EUR, 8positions, horizon5séances. Le service est aussi
testé sur de petites tapes synthétiques ; celles-ci ne prouvent aucun rendement
historique. La performance2026 est explicitement refusée.

Les intentions causales ATR TOP20, Oracle TOP20 et contrôle uniforme existent
dans le préflight11-A. Le moteur consomme leur ordre de priorité, **pas un
classement recalculé à partir des rendements futurs**. Un portefeuille séparé
doit être exécuté par politique et fold, ainsi que par scénario de coûts.
Ne pas concaténer deux folds en réinitialisant implicitement leurs positions.
Les sorties et paiements doivent être entièrement couverts par la tape.

## 2. Une séance dans le moteur

1. Traiter les opérations sur titres des positions détenues avant l'ouverture.
2. Créer les droits aux dividendes au jour ex ; payer les créances arrivées à
   échéance, y compris si l'action a déjà été vendue.
3. Valoriser les positions à l'ouverture et calculer le budget d'un ticket :
   equity d'ouverture divisée par capacité maximale. Une créance dividende
   appartient à l'equity mais n'est pas du cash disponible.
4. Parcourir les candidats par rang causal. Refuser les doubles positions et
   respecter la capacité ; dimensionner en actions entières, **frais inclus**.
5. Exécuter les achats à l'ouverture de décision. Les coûts sont retranchés du
   cash séparément du notionnel au prix de référence.
6. Exécuter les sorties à la clôture de la séance entrée+H. Les ventes ne
   financent aucun achat plus tôt dans cette même séance.
7. Enregistrer cash, positions, créances, valeur de marché et equity de clôture.

Une position sortie aujourd'hui peut être rachetée à la séance suivante, pas
plus tôt. Aucun TP, stop, trailing, filtre DIP ou optimisation des exits n'est
introduit ici. Les prix de référence restent OHLC **bruts**, pas adjusted_close.
Le spread/slippage ne sont pas aussi appliqués à un second prix adverse : cela
ferait payer deux fois les mêmes coûts.

Le cash est un cash économique disponible pour l'allocation ; ce moteur n'est
pas un simulateur des soldes bancaires disponibles au règlement. La date de
règlement est toutefois obligatoire pour la fiscalité. Un vrai courtier pourra
imposer d'autres contraintes, à qualifier dans un profil ultérieur.

## 3. Frais, fiscalité et réconciliation

Les quatre composantes restent distinctes : commission, spread, slippage,
taxes. Le profil utilisateur est1EUR par ordre exécuté, spread complet5bps dont
une moitié par exécution, slippage5bps par exécution. Les paramètres sont
remplaçables, ce sont des hypothèses, pas des observations bid/ask ou fills.

Le service appelle le calcul fiscal12-A, avec une **date de règlement fournie
et documentée**. Il n'invente pas T+2 à partir des seules séances XPAR : calendrier
de négociation et calendrier de règlement ne sont pas interchangeables.
L'assujettissement est résolu par ISIN, ticker éventuel et intervalle de dates
dans la liste configurable ; aucune ligne ne signifie **inconnu**, pas exonéré.
Les règles historiques du12-A sont conservées. Le stress multiplie les frais
d'exécution, pas le taux légal ; le prix d'acquisition fiscal reflète le coût
adverse modélisé. Le règlement après2025 est refusé dans cette première tape.

Deux identités partageant un ISIN sont refusées. Aucun netting général
intrajournalier ni déclaration fiscale agrégée de courtier n'est simulé. Voir
[12-A](sprint_12a_couts_taxes_operations_sur_titres.md) pour la portée fiscale.

Chaque fill produit un mouvement de cash et ses frais. Pour un trade :

`PnL brut = notionnel vente − notionnel achat + droits aux dividendes`

`PnL net = PnL brut − coûts achat − coûts vente`

À la fin, positions et créances doivent être soldées ; la somme des PnL nets
doit correspondre au cash final moins le capital initial. Sinon le rejeu est
bloqué. Les dividendes sont bruts : la fiscalité personnelle n'est pas modélisée.

## 4. Opérations sur titres et inconnus

Un dividende du jour d'achat ne donne pas de droit ; celui du jour de sortie
oui si la position était déjà détenue. Un paiement après vente conserve la
créance dans l'equity puis la crédite en cash à la date documentée. DeviseEUR,
montant non ajusté, date et preuve sont obligatoires.

Les splits simples à ratio entier documenté changent les quantités, sans
inventer de bénéfice. Un split créant des rompus bloque : la compensation en
cash n'est pas encore implémentée. Plusieurs événements simultanés pour un
instrument bloquent aussi car l'ordre et l'unité du dividende seraient ambigus.
Fusions, droits, spin-offs et événements complexes bloquent lorsqu'ils touchent
une position ; ils ne sont pas traités comme des splits par approximation.

Suspension, statut non exécutable, prix absent/non qualifié ou événement non
qualifié rencontré sur une position : **arrêt**, pas remplacement par le dernier
prix ni exclusion rétroactive du candidat. Le journal partiel est un diagnostic,
jamais une performance publiable. La couverture officielle CA doit être fournie
sur la fenêtre de détention ; une liste fournisseur vide n'en tient pas lieu.

## 5. Contrat de la tape JSON

Une tape concerne une seule politique/un seul fold. Champs obligatoires :

| Champ | Contenu |
|---|---|
| `schema_version`, `market_code`, `currency` | `1`, `FR_EQ`, `EUR` |
| `canonical_writes_enabled`, `serving_enabled` | Tous deux `false` |
| `initial_equity`, `max_positions`, `horizon` | Capital, capacité et séances de détention |
| `sessions`, `calendar_evidence` | Séances uniques ordonnées, preuve de calendrier |
| `instruments` | UID → `{isin,ticker}` ; identité stable et sans aliasISIN |
| `decision_at`, `entry_at` | Date séance → timestamps avec fuseau ; décision≤entrée |
| `candidates` | `{session,uid,rank,available_at}` ; disponibilité≤décision |
| `bars` | Séance → UID → `{open,close,tradable,economic_verified,evidence}` |
| `settlements` | Séance → `{date,evidence}` ; date de règlement achat vérifiée |
| `corporate_action_coverage` | UID → `{from,to,verified,evidence}` |
| `events` | Liste d'événements, vide seulement avec couverture qualifiée |

Pour un dividende : `id,uid,session,kind=DIVIDEND,payment_session,cash_per_share,
currency,verified,evidence`. Pour un split : `id,uid,session,kind=SPLIT,numerator,
denominator,verified,evidence`. Identifiants uniques, aucune date de paiement
inventée. Les preuves sont des références à des pièces validées, pas seulement
la chaîne«verified». L'assembleur ne doit pas mettre les flags à vrai d'après
la seule présence des champs. Ce contrat ne certifie pas lui-même une pièce.

## 6. Utilisation et résultat actuel

Audit seul, sans nouvelle collecte, sans calcul de PnL :

```powershell
python -u -m modelFactory.fr_portfolio_replay_12b --output artifacts/fr/research/portfolio_replay_12b/nouveau-audit
```

Résultat réel du4octobre :
`artifacts/fr/research/portfolio_replay_12b/preflight-20261004-v2/report.json`.
21 379 chemins, **0 chemin économique qualifié**, aucun ordre, `net_pnl=null`,
statut`BLOCKED_EXECUTION_EVIDENCE`. Le fichier
`execution_evidence_requests.parquet` conserve toute la population à qualifier,
sans retirer les50chemins dividendes ou9chemins prix problématiques. Les hashes
du préflight, scores et qualification sont vérifiés et leurs clés réconciliées.

Lorsque la tape et la liste fiscale seront réellement qualifiées :

```powershell
python -u -m modelFactory.fr_portfolio_replay_12b --input chemin/tape-qualifiee.json --output artifacts/fr/research/portfolio_replay_12b/nouveau-rejeu
```

Ajouter`--stress-multiplier 2` pour le scénario stressé ; utiliser un **nouveau**
dossier à chaque passage. Profil/éligibilité peuvent être remplacés avec
`--cost-profile` / `--eligibility`. Leur hash et celui de la tape sont conservés.
Un blocage produit un rapport et, après entrée dans le moteur, un journal partiel,
avec sortie CLI non nulle. Une violation de format provoque une erreur explicite.

Sorties d'un rejeu : `report.json` et `ledger.json`. Le journal contient ordres
exécutés/refusés, mouvements cash, créances, trades et courbe d'equity. Les
montantsDecimal sont sérialisés en chaînes pour préserver la précision.
Même un rejeu achevé reste`COMPLETED_ASSUMED_COST_RESEARCH`, sans GO de serving.

## 7. Validation et prochaine étape

Qualification complémentaire effectuée : [bilan12-C](sprint_12c_qualification_preuves_execution.md).
112couples titre/année positifs sur209 ; règlements standards documentés,
deux overlays partiels de dividendes et contrôle officiel des prix ciblé.
Le comparatif réel reste bloqué, pas de promotion des flags canoniques.

Tests dédiés : `tests/test_fr_portfolio_replay_12b.py`, en complément des tests
coûts12-A et préflight11-A. Ils contrôlent dimensionnement frais inclus,
réconciliation, fiscalité au règlement, cash non négatif, non-empilement,
rachat différé, dividendes, splits/rompus, inconnus bloquants, disponibilité
causale, identitéISIN, stress et absence de mutation de l'entrée.
`tests/test_fr_replay_audit_12b.py` vérifie aussi l'intégrité des identités et la
conservation des chemins bloquants. **27 tests ciblés passent**, Ruff passe sur
les nouveaux fichiers. Ce n'est pas l'exécution de toute la suite US/CN/FR.

Ce qui reste avant le Sprint13 comparatif réel :

1. Qualifier la liste fiscale ISIN/date sans classer les absents comme exonérés.
2. Qualifier le calendrier de règlement et les sources de prix/statut d'exécution.
3. Résoudre les événements de dividende et prouver la couverture CA ; gérer les
   événements complexes si la population retenue les rencontre.
4. Assembler les tapes par fold/politique depuis les intentions11-A inchangées,
   avec les mêmes données d'exécution, puis lancer coût nominal et stressé.

Pas de nouvel entraînement, pas de migration SQL, pas de modification des flags
canoniques. L'IHM et le moteur live FR ne sont pas activés par ce Sprint12-B.
