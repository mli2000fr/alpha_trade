# Audit externe IA — Alpha Trade

_Date : 2026-05-13_

## 1. Résumé exécutif

- **Décision** : **GO conditionnel**
- **Niveau de maturité perçu** : bon sur l’architecture, la documentation et les garde-fous d’exécution ; insuffisant sur la fiabilité des métriques qualité et l’hygiène de la chaîne ML.
- **Constat principal** : le dépôt montre une vraie structuration “production-minded” (préflight live, gestion multi-comptes, runbooks, docs C4, tests nombreux), mais plusieurs signaux empêchent de considérer l’application comme prête pour un audit externe formel sans réserves.
- **Priorités immédiates** :
  1. fiabiliser les métriques de qualité (`coverage.json` / seuils CI),
  2. remettre le lint au vert,
  3. sécuriser le chargement d’artefacts ML,
  4. aligner la politique de secrets réellement appliquée avec la documentation.

### Synthèse courte

Alpha Trade est un dépôt ambitieux et déjà très avancé : architecture modulaire, forte documentation, mécanismes de préflight, gestion des comptes broker, et une base de tests large. En revanche, la chaîne de confiance qualité/sécurité n’est pas totalement cohérente aujourd’hui : la couverture publiée est incompatible avec les objectifs annoncés, le lint n’est pas vert, et le sous-système ML charge encore des artefacts via des primitives de désérialisation risquées. En l’état, je recommanderais **un passage en production seulement avec plan d’actions court et vérification CI renforcée**, et **pas encore un audit externe formel “sans réserve”**.

---

## 2. Périmètre et méthode

### Documents et modules relus

- `README.md`
- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- `pytest.ini`
- `mypy.ini`
- `config.yaml`
- `doc/external_audit_checklist.md`
- `doc/external_audit_findings_template.md`
- `doc/pre_audit_findings.md`
- `doc/architecture/c4_context.md`
- `doc/architecture/c4_container.md`
- `doc/architecture/c4_component.md`
- `run_execution.py`
- `execution_engine/state_machine.py`
- `core/secrets.py`
- `database/connection.py`
- `service/alpaca/accounts.py`
- `service/_http_retry.py`
- `service/alerting.py`
- `ihm/services/db.py`
- `ihm/services/queries.py`
- `modelFactory/predictor.py`
- `modelFactory/trainer.py`

### Vérifications exécutées

- `python -u scripts/run_pre_audit_checklist.py --min-score 0`
  - **Résultat** : `score=50.0/50 ok=21 warn=0 fail=0`
- `python -u scripts/check_no_todo.py`
  - **Résultat** : `OK : 0 marqueur TODO/FIXME/XXX`
- `python -m pytest tests/test_state_machine.py tests/test_execution_state_machine.py tests/test_config_no_literal_secrets.py tests/test_broker_interface_contract.py --no-cov -q`
  - **Résultat** : succès
- `ruff check execution_engine core service risk_management database modelFactory ihm`
  - **Résultat** : échec, findings réels dans `modelFactory/*`
- Lecture du `coverage.json` existant
  - **Résultat** : `percent_covered = 3.587868087521281` (~4%), `covered_lines = 1552`, `num_statements = 37237`

### Limites de cet audit

Cet audit est **un audit statique de dépôt** complété par quelques vérifications non destructives. Il **ne valide pas** :

- un run complet avec MySQL réel,
- un run `paper`/`live` contre broker,
- la fraîcheur réelle de tous les artefacts métiers,
- la remédiation CVE effective au moment du déploiement,
- la conformité réglementaire au sens juridique.

---

## 3. Points forts

### 3.1 Architecture et découpage

Le dépôt est bien structuré par domaines (`execution_engine`, `risk_management`, `service`, `core`, `database`, `ihm`, `backtesting`, etc.). La séparation des responsabilités est lisible et cohérente avec une plateforme de trading algorithmique.

### 3.2 Documentation au-dessus de la moyenne

Le projet dispose de :

- C4 niveau contexte / conteneurs / composants,
- runbooks (`doc/disaster_recovery.md`, `doc/runbook_24_7.md`, etc.),
- documentation fonctionnelle et technique,
- checklist d’audit et templates de findings.

C’est un vrai accélérateur pour la reprise, l’exploitation et l’auditabilité.

### 3.3 Garde-fous d’exécution sérieux

`run_execution.py` contient plusieurs protections utiles :

- préflight obligatoire en live,
- confirmation renforcée du compte live,
- arrêt explicite si l’equity broker est indisponible,
- persistance best-effort des rapports de préflight.

Sur une application d’exécution d’ordres, c’est un bon signal de maturité opérationnelle.

### 3.4 Gestion des secrets et du multi-compte bien pensée

Les intentions de conception sont bonnes :

- placeholders `${VAR}` dans `config.yaml`,
- scanner de secrets dans `core/secrets.py`,
- registre multi-comptes dans `service/alpaca/accounts.py`.

### 3.5 Résilience réseau présente

`service/_http_retry.py` implémente retry exponentiel, circuit breaker et masquage des paramètres sensibles dans les logs. C’est exactement le type de brique transverse attendu sur un système dépendant de plusieurs providers externes.

### 3.6 Base de tests étendue

Le répertoire `tests/` est très fourni et couvre visiblement de nombreux axes : unitaires, intégration, property-based, formels, IHM, exécution, backtesting, sécurité documentaire.

---

## 4. Findings priorisés

## P1 — Majeur

### P1-01 — La métrique de couverture publiée n’est pas fiable au regard des objectifs annoncés

**Preuves**

- `pytest.ini` impose `--cov-fail-under=70`.
- Le `coverage.json` présent dans le dépôt indique environ **3.59 %** de couverture (`1552 / 37237` lignes), dernière modification observée : `2026-05-12 23:43:25`.
- La checklist d’audit vise même `>= 90 %` global et `>= 95 %` sur les modules critiques.

**Analyse**

Soit l’artefact `coverage.json` est **obsolète / partiel**, soit la chaîne de publication de la couverture est **incohérente** avec les seuils déclarés. Dans les deux cas, la gouvernance qualité n’est pas fiable.

**Risque**

- faux sentiment de sécurité,
- difficulté à défendre la qualité en audit externe,
- incapacité à détecter proprement une régression critique.

**Recommandation**

- régénérer la couverture en CI sur un workflow canonique,
- publier un artefact signé / horodaté par pipeline,
- échouer si le rapport publié ne correspond pas au seuil configuré,
- distinguer clairement couverture “workspace locale” et couverture “baseline CI”.

---

### P1-02 — Le lint n’est pas vert sur le périmètre principal audité

**Preuves**

Le lint `ruff` a échoué, avec notamment des findings dans :

- `modelFactory/predictor.py`
- `modelFactory/run_predict.py`
- `modelFactory/run_train.py`
- `modelFactory/tabular_baseline.py`

Exemples relevés :

- `F821 Undefined name 'Engine'`
- imports non triés
- annotations anciennes `Optional[...]`
- nombreuses indentations par tabulations (`W191`)

**Analyse**

La qualité statique est bonne sur une partie du dépôt, mais pas suffisamment homogène. Le module ML semble en retard par rapport au niveau d’exigence affiché dans la documentation d’audit.

**Risque**

- dette technique accrue sur la partie ML,
- baisse de maintenabilité,
- perte de confiance dans les garde-fous CI annoncés.

**Recommandation**

- remettre `ruff check .` au vert avant audit externe,
- isoler `modelFactory/` dans une campagne de remédiation dédiée,
- ajouter une règle CI simple : pas de merge si lint rouge.

---

### P1-03 — Chargement d’artefacts ML via désérialisation risquée

**Preuves**

- `modelFactory/predictor.py:137` → `pickle.load(fh)`
- `modelFactory/predictor.py:153` → `pickle.load(fh)`
- `modelFactory/predictor.py:159` → `pickle.load(fh)`
- `modelFactory/trainer.py:153` → `torch.load(..., weights_only=False)`

**Analyse**

`pickle.load` et certains usages de `torch.load` sont des surfaces classiques d’exécution de code arbitraire si un artefact est compromis. Même si les artefacts sont internes aujourd’hui, un audit sérieux considérera ce point comme un risque supply chain / intégrité.

**Risque**

- exécution arbitraire lors du chargement d’un artefact altéré,
- compromission de l’environnement d’inférence ou d’entraînement,
- difficulté à justifier la sûreté de la chaîne ML en audit.

**Recommandation**

- migrer vers des formats natifs/sûrs dès que possible (`.txt`, `.cbm`, états JSON, `safetensors` selon le cas),
- utiliser `torch.load(..., weights_only=True)` quand c’est possible,
- signer ou au minimum hacher les artefacts avant chargement,
- restreindre le chargement aux répertoires d’artefacts approuvés.

---

### P1-04 — Politique de secrets incohérente entre la documentation et le code réel

**Preuves**

- `README.md` indique que les sentinelles DB `pass`, `user`, `changeme` sont rejetées.
- `core/secrets.py` interdit explicitement `pass`, `password`, `changeme`, etc.
- `database/connection.py` documente l’inverse : le commentaire précise une tolérance historique sur `user` / `pass`, et `_FORBIDDEN_PLAINTEXT` n’inclut pas `user` ni `pass`.

**Analyse**

Le contrôle de sécurité annoncé n’est pas appliqué uniformément. En audit, cela sera interprété comme une divergence entre la politique et son enforcement.

**Risque**

- configuration faible acceptée selon le point d’entrée,
- ambiguïté opérationnelle,
- défaut de traçabilité des garanties sécurité.

**Recommandation**

- choisir une politique unique,
- l’appliquer dans tous les chemins d’accès DB,
- ajouter un test de non-régression explicite sur `database/connection.py`,
- corriger soit la doc soit le comportement, idéalement les deux en même temps.

---

## P2 — Important mais non bloquant immédiat

### P2-01 — Surface SQL dynamique encore trop large dans certaines couches de lecture

**Preuves**

Interpolations relevées notamment dans :

- `ihm/services/queries.py`
- `risk_management/db_io.py`
- `database/repositories/bars.py`
- `database/async_loaders.py`
- `backtesting/report.py`

Exemples : `LIMIT {limit}`, fragments `WHERE {where_clause}`, noms de table interpolés.

**Analyse**

Une partie de ces interpolations semble construite à partir de fragments internes et non d’entrées brutes utilisateur, donc le risque n’est pas automatiquement critique. En revanche, la surface est plus large que souhaitable pour une application censée se présenter à un audit externe.

**Risque**

- exposition future à injection SQL si un appelant amont change,
- difficulté de revue,
- dette de sécurité latente.

**Recommandation**

- borner/caster systématiquement les `limit`,
- passer par des listes blanches pour les identifiants dynamiques,
- paramétrer tout ce qui peut l’être,
- centraliser les helpers SQL “dynamiques sûrs”.

---

### P2-02 — Hygiène de dépendances perfectible pour un contexte production

**Preuves**

- beaucoup de dépendances runtime ne sont pas figées dans `pyproject.toml` / `requirements.txt` ;
- `requirements.txt` contient des dépendances qui relèvent plutôt du dev/test (`pytest`, `testcontainers[mysql]`).

**Analyse**

L’absence de verrouillage fort complique la reproductibilité et l’analyse CVE. Le mélange runtime/dev alourdit les environnements de prod et brouille la séparation des responsabilités.

**Risque**

- dérive de versions,
- surface supply chain élargie,
- incidents de déploiement difficiles à reproduire.

**Recommandation**

- introduire un fichier de contraintes/lock pour la prod,
- retirer les dépendances de test du runtime,
- documenter un cycle de mise à jour dépendances + scan CVE.

---

### P2-03 — Le pré-audit automatisé donne un signal positif utile mais potentiellement trompeur

**Preuves**

- `scripts/run_pre_audit_checklist.py` retourne `50.0/50`.
- Mais le script lui-même précise qu’il ne couvre qu’un **extrait** des items “programmables” de la checklist complète.

**Analyse**

Le score est utile comme indicateur de présence documentaire/structurelle, mais il ne prouve pas à lui seul l’aptitude à un audit externe formel.

**Risque**

- surévaluation de la préparation réelle,
- confusion entre conformité documentaire et qualité exécutable.

**Recommandation**

- renommer ce score en “score automatisable partiel”,
- afficher explicitement le ratio `items vérifiés / items totaux`,
- compléter par un registre de preuves manuelles.

---

## P3 — Améliorations opportunistes

### P3-01 — Séparation runtime / exploitation IHM à clarifier côté credentials DB

**Preuves**

`ihm/services/db.py` permet la saisie manuelle des credentials DB et leur stockage en `session_state` Streamlit.

**Analyse**

Le choix peut être pratique en exploitation, mais sur une machine partagée ou un poste peu durci, ce n’est pas idéal. Ce n’est pas un finding critique en soi, mais la posture sécurité dépend beaucoup de l’environnement opérateur.

**Recommandation**

- privilégier l’injection via environnement/vault,
- conserver le mode saisie uniquement en mode administrateur ou environnement de support.

---

## 5. Évaluation par domaine

| Domaine | Appréciation | Commentaire |
|---|---:|---|
| Architecture | 8/10 | Bonne modularité, docs C4 présentes, responsabilités lisibles |
| Qualité code | 5/10 | Suite de tests abondante, mais métriques qualité incohérentes et lint non vert |
| Sécurité applicative | 6/10 | Bonnes intentions (secrets, préflight, retry), mais incohérences et désérialisation risquée |
| Observabilité / ops | 7/10 | Runbooks, préflight, summaries, watcher et artefacts présents |
| Gouvernance / auditabilité | 6/10 | Documentation solide, mais preuves automatiques encore fragiles |

**Note globale indicative** : **6.4 / 10**

---

## 6. Recommandations priorisées impact / effort

| Priorité | Action | Impact | Effort |
|---|---|---:|---:|
| 1 | Régénérer et fiabiliser la couverture CI, publier un artefact canonique | Très fort | Moyen |
| 2 | Corriger les findings `ruff` du sous-système `modelFactory/` | Fort | Faible à moyen |
| 3 | Remplacer `pickle.load` / durcir `torch.load` et signer les artefacts ML | Très fort | Moyen |
| 4 | Unifier la politique d’acceptation des secrets DB (`user`/`pass`) | Fort | Faible |
| 5 | Réduire les interpolations SQL dynamiques | Moyen | Moyen |
| 6 | Séparer strictement dépendances runtime / dev et verrouiller les versions | Moyen | Moyen |
| 7 | Requalifier le score du pré-audit automatisé | Moyen | Faible |

---

## 7. Verdict

### Ce qui me ferait dire “prêt pour audit externe formel”

- `ruff` vert sur l’ensemble du périmètre cible,
- couverture cohérente, reproductible et alignée avec les seuils affichés,
- suppression ou isolement strict des désérialisations risquées,
- politique de secrets homogène et testée de bout en bout,
- idéalement un run CI documenté servant de preuve horodatée.

### Verdict actuel

Le projet est **nettement au-dessus d’un prototype** et montre une vraie intention de production. En revanche, il reste **des écarts de gouvernance qualité et de sécurité de la chaîne ML** qui justifient un **GO conditionnel**, pas un blanc-seing.

---

## 8. Annexes — traces de vérification

### Commandes exécutées

```powershell
python -u scripts/run_pre_audit_checklist.py --min-score 0
python -u scripts/check_no_todo.py
python -m pytest tests/test_state_machine.py tests/test_execution_state_machine.py tests/test_config_no_literal_secrets.py tests/test_broker_interface_contract.py --no-cov -q
ruff check execution_engine core service risk_management database modelFactory ihm
```

### Résultats marquants

- Pré-audit automatisé : `50.0/50` sur le sous-ensemble programmable
- TODO/FIXME/XXX applicatifs : `0`
- Sous-ensemble de tests critiques : `OK`
- Lint Ruff : `KO`
- Couverture publiée observée : `~3.59 %`

---

## 9. Conclusion courte

Le socle technique est sérieux et bien documenté, mais **les preuves de qualité publiées ne sont pas encore suffisamment cohérentes pour soutenir un audit externe de haut niveau sans remédiation préalable**. La trajectoire est bonne ; les corrections prioritaires sont ciblées et réalistes.
