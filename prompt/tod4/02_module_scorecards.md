# 02 — Scores détaillés par module

---

## 1. Documentation

**Note : 7.0 / 10**

### Résumé
La documentation est abondante (~30 fichiers dans `doc/`), structurée, et couvre l'essentiel des modules. Les conventions sont centralisées dans `doc/CONVENTIONS.md`. Quelques incohérences résiduelles (provider news, défaut `bars_provider`) et une certaine redondance entre DOC_FONCTIONNELLE.md et DOC_TECHNIQUE.md.

### Points forts
- Documentation riche et organisée
- Conventions centralisées
- Matrice de lineage exhaustive
- Runbooks opérateur détaillés

### Faiblesses
- Incohérence provider news par défaut (README vs docs techniques)
- Redondance entre fichiers
- Certains docs POC non marqués comme tels
- Pas de glossaire centralisé

### Risques principaux
- Opérateur qui suit une doc obsolète et lance une mauvaise commande
- Confusion sur le provider à utiliser

### Pour atteindre 10/10
- Aligner tous les docs sur le code réel (provider news, défauts)
- Supprimer les redondances
- Ajouter un glossaire
- Marquer les docs POC/non activés
- Générer un index automatiquement (déjà fait via `scripts/generate_doc_index.py`)

---

## 2. Configuration

**Note : 6.5 / 10**

### Résumé
Le système de configuration est bien pensé (YAML centralisé, presets de capital, résolution multi-comptes). Quelques incohérences entre le défaut config et le défaut documenté, et l'absence de validation automatique de la cohérence inter-paramètres.

### Points forts
- Presets de capital détaillés par tranche
- Résolution multi-comptes propre
- Secrets en variables d'environnement
- Scanner de secrets littéraux

### Faiblesses
- Défaut `bars_provider` incohérent doc/code
- Pas de validation de cohérence entre presets et profil strict
- Certains paramètres legacy non nettoyés
- Pas de test automatique de la validité des fichiers YAML

### Risques principaux
- Preset inapproprié pour un compte réel
- Paramètres contradictoires non détectés

### Pour atteindre 10/10
- Aligner les défauts code/doc
- Ajouter une validation de cohérence inter-paramètres
- Ajouter des tests de configuration automatisés
- Nettoyer les paramètres obsolètes

---

## 3. DataIntegrityEngine

**Note : 8.0 / 10**

### Résumé
Module mature et bien conçu. Le provider switch EODHD/Alpaca est propre, le sanitizer est robuste, les audits sont tracés. Points d'amélioration : homogénéisation des résumés de run, exposition multi-comptes, persistance SQL des résumés.

### Points forts
- Provider switch maîtrisé (no-op contrôlé)
- Sanitizer avec reconstruction glissante
- Détection d'anomalies (Rolling MAD)
- États `history_status` riches
- Auto-récupération SPY

### Faiblesses
- Résumés de run hétérogènes entre scripts
- Pas de persistance SQL uniforme des résumés
- Multi-comptes peu exposé en CLI

### Risques principaux
- Perte de traçabilité si résumé non capturé
- Univers vide si `history_status` mal interprété

### Pour atteindre 10/10
- Uniformiser les `run_summary` (schéma commun)
- Persister tous les résumés en SQL
- Exposer le multi-comptes dans toutes les CLI
- Ajouter une commande `validate` pour vérifier l'intégrité des données

---

## 4. Database

**Note : 7.5 / 10**

### Résumé
Schéma SQL bien structuré, migrations Alembic en place, support multi-comptes via `account_id`. Quelques tables listées dans la doc qui n'existent peut-être pas dans le code.

### Points forts
- Schéma organisé par domaine (stock/, news/, ml/, risk/, execution/, corporate_actions/)
- Migrations Alembic
- Colonne `account_id` sur les tables critiques
- Contraintes CHECK pour les conventions

### Faiblesses
- Tables ML listées dans lineage matrix non confirmées
- Pas de test d'intégrité des migrations
- Pool de connexion modeste (2+3)

### Risques principaux
- Migration incomplète ou schéma désynchronisé
- Performance sous charge

### Pour atteindre 10/10
- Vérifier et documenter toutes les tables
- Ajouter des tests de migration
- Optimiser le pool pour la production
- Ajouter une table `run_summaries` centralisée

---

## 5. Service / Providers

**Note : 7.0 / 10**

### Résumé
Les clients API (Alpaca, EODHD, Finnhub, Stooq) sont bien isolés derrière des adaptateurs. Le registre multi-comptes est propre. Points faibles : gestion des quotas EODHD, absence de mock réaliste pour les tests d'intégration.

### Points forts
- Isolation des providers
- Registre multi-comptes (AccountRegistry)
- Retry avec backoff
- Cache EODHD (disque)

### Faiblesses
- Pas de simulation de rate limiting dans les tests
- Gestion des quotas EODHD basique
- Pas de health check proactif des providers

### Risques principaux
- Épuisement du quota EODHD en production
- Indisponibilité provider non détectée avant le run

### Pour atteindre 10/10
- Ajouter un health check pré-run
- Implémenter un circuit breaker par provider
- Ajouter des mocks réalistes pour les tests
- Monitorer les quotas

---

## 6. Screener

**Note : 7.5 / 10**

### Résumé
Le screener 3 passes (liquidité, force relative, range historique) est fonctionnel et parallélisé. L'alignement avec le profil strict est bon. Points faibles : résumés de run moins riches que le sanitizer, pas de mode PIT natif (délégué au backfill).

### Points forts
- Parallélisme (ProcessPoolExecutor)
- Aligné sur STRICT_SWING_CASH_FILTERS
- Conservation du snapshot précédent si run vide
- Isolation des chunks en erreur

### Faiblesses
- Résumé de run moins détaillé que d'autres modules
- Pas de persistance SQL du résumé (stdout uniquement)

### Risques principaux
- Univers vide non détecté assez tôt

### Pour atteindre 10/10
- Enrichir le run_summary (breakdown par filtre)
- Persister les résumés en SQL
- Ajouter un mode `--validate` pour tester les seuils

---

## 7. Selector (AlphaScanner)

**Note : 8.0 / 10**

### Résumé
Le scanner multi-facteurs est bien conçu : Minervini, VCP, neutralisation sectorielle, enrichissement quotes/earnings PIT. Le profil strict partagé est une excellente pratique.

### Points forts
- Profil strict partagé (`STRICT_SWING_CASH_FILTERS`)
- Neutralisation sectorielle cross-sectorielle
- Enrichissement PIT (quotes, earnings)
- Filtres cohérents avec le swing trading

### Faiblesses
- Dépendance aux quotes IEX (biais documenté mais réel)
- Pas de fallback si quotes absentes

### Risques principaux
- Univers vide si marché peu directionnel
- Biais quotes IEX qui exclut de bons candidats

### Pour atteindre 10/10
- Ajouter un mode fallback sans quotes
- Exposer les métriques de filtrage dans le run_summary
- Ajouter un test de sensibilité aux seuils

---

## 8. Event Sentiment

**Note : 7.0 / 10**

### Résumé
Le pipeline NLP (FinBERT) est fonctionnel avec un scope mixte bien pensé. Points faibles : complexité, dépendance à un provider news unique, manque de validation du score.

### Points forts
- Scope mixte (import large, scoring candidats)
- Fallback COALESCE pour rétrocompatibilité
- Niveau 4 contextuel optionnel
- Fusion quant + sentiment + macro

### Faiblesses
- Complexité du pipeline (5+ étapes)
- Provider news par défaut ambigu
- Pas de calibration automatique des poids
- Absence de validation externe du score FinBERT

### Risques principaux
- Score sentiment bruité qui dégrade le signal quant
- Univers de news trop restreint

### Pour atteindre 10/10
- Clarifier le provider news par défaut
- Ajouter une calibration des poids
- Simplifier le pipeline ou le documenter mieux
- Ajouter un test de corrélation sentiment/performance

---

## 9. ModelFactory

**Note : 6.5 / 10**

### Résumé
La gouvernance multi-modèles (LSTM + LightGBM + CatBoost + global) est ambitieuse et bien architecturée. Points faibles : complexité, risque d'overfitting, persistance DB incomplète.

### Points forts
- Gouvernance multi-modèles
- Sélection automatique du champion
- Artefacts signés SHA-256
- Support GPU/CPU

### Faiblesses
- `model_predictions` ne persiste pas le modèle utilisé
- Risque d'overfitting sur petits symboles
- Complexité élevée pour l'opérateur
- Entraînement séquentiel obligatoire sur GPU unique

### Risques principaux
- Overfitting non détecté
- Inférence sur un champion inapproprié
- Traçabilité ML incomplète en DB

### Pour atteindre 10/10
- Ajouter `selected_model` et `decision_threshold` dans `model_predictions`
- Implémenter un test de walk-forward
- Ajouter un détecteur de drift en production
- Simplifier l'UX opérateur

---

## 10. Risk Management

**Note : 8.0 / 10**

### Résumé
Module mature avec sizing ATR/Kelly, contraintes de portefeuille, circuit breaker, filtre de corrélation. L'intégration avec la couche Market-Aware est un plus.

### Points forts
- Sizing ATR + Kelly conditionnel
- Circuit breaker (drawdown, daily loss)
- Filtre de corrélation
- Score de conviction (quant + ML)
- Intégration Market-Aware

### Faiblesses
- Kelly activé seulement ≥ 25 k$ (pertinent mais restrictif)
- Pas de backtest du risk management isolé

### Risques principaux
- Sizing inapproprié si ATR mal estimé
- Circuit breaker trop permissif sur petit compte

### Pour atteindre 10/10
- Ajouter un backtest spécifique du risk management
- Permettre un Kelly minimum sur petits comptes
- Ajouter un stress test de scénarios extrêmes

---

## 11. Execution Engine

**Note : 8.5 / 10**

### Résumé
Le module le plus mature du projet. La chaîne canonique (targets → requests → orders → fills → positions/lots → reconciliation) est exemplaire. Idempotence, TCA, contraintes de compte, préflight, kill switch : tout y est.

### Points forts
- Chaîne canonique complète et tracée
- Idempotence (SHA-256)
- TCA (slippage, implementation shortfall)
- Contraintes compte (margin/cash/PDT/swing_only)
- Préflight + kill switch
- Réconciliation

### Faiblesses
- Pas de gestion des ordres partiellement fillés
- Timeout de fill peut être trop court en live

### Risques principaux
- Erreur de manipulation en mode live (malgré les garde-fous)
- Fill partiel non géré

### Pour atteindre 10/10
- Gérer les fills partiels
- Ajouter un mode `--what-if` pour simuler sans soumettre
- Améliorer le reporting post-exécution

---

## 12. Corporate Actions

**Note : 7.5 / 10**

### Résumé
Module bien conçu avec séparation sync/apply, idempotence, cash ledger. La synchronisation en fin de pipeline est justifiée mais contre-intuitive.

### Points forts
- Séparation sync/apply
- Idempotence (clé SHA-256 scopée)
- Cash ledger pour dividendes
- Stratégie `split` cohérente

### Faiblesses
- Positionnement en fin de pipeline (justifié mais surprenant)
- Pas de réconciliation automatique post-apply

### Risques principaux
- Événement CA manqué si sync pas fait
- Double ajustement si bug d'idempotence

### Pour atteindre 10/10
- Ajouter une réconciliation automatique post-apply
- Ajouter une alerte si événements non appliqués depuis N jours
- Permettre un sync pré-exécution pour les dividendes connus

---

## 13. Backtesting

**Note : 8.0 / 10**

### Résumé
Module très complet avec PIT, contraintes de compte réalistes, phases de fidélité, diagnostic screener. La qualité est élevée pour un backtest sur mesure.

### Points forts
- Point-in-time strict
- Contraintes compte (margin/cash/PDT/swing_only)
- Phases de fidélité (2/3/4/5/7)
- Diagnostic screener avec recommandations
- Reporting structuré (report.json)

### Faiblesses
- Pas de parallélisation des runs
- Cache Parquet non branché par défaut
- Pas d'analyse de sensibilité automatisée

### Risques principaux
- Illusion de performance si données PIT incomplètes
- Sur-optimisation via les paramètres de diagnostic

### Pour atteindre 10/10
- Activer le cache Parquet par défaut
- Ajouter l'analyse de sensibilité dans la CLI standard
- Paralléliser les runs
- Ajouter un test de parité backtest/live

---

## 14. IHM

**Note : 7.5 / 10**

### Résumé
L'IHM Streamlit est fonctionnelle, bien organisée en pages, avec un workflow quotidien complet. Points faibles : pas de mode read-only DB, pas de responsive design, dépendance à Streamlit.

### Points forts
- Workflow quotidien 1→14
- Pages dédiées par domaine
- Sélecteur de compte multi-comptes
- Lancement des pipelines backend
- Résumés de run capturés

### Faiblesses
- Pas de mode read-only DB (l'IHM peut modifier)
- Rafraîchissement manuel (pas de websocket)
- Interface peu adaptée au mobile

### Risques principaux
- Lancement accidentel d'un pipeline en production
- Affichage de données sensibles

### Pour atteindre 10/10
- Implémenter un mode read-only DB
- Ajouter des confirmations pour les actions destructrices
- Améliorer le rafraîchissement (polling ou websocket)
- Ajouter un dashboard mobile simplifié

---

## 15. Observabilité / Run Summaries / Logs

**Note : 7.0 / 10**

### Résumé
Les logs fichiers avec rotation sont en place. Les `run_summary` structurés sont émis par plusieurs modules mais de façon hétérogène. Pas de centralisation, pas d'alerting.

### Points forts
- RotatingFileHandler (5 Mo, 3 backups)
- Format de log structuré
- Résumés stdout préfixés `::alpha_trade_run_summary::`
- Capture IHM des résumés

### Faiblesses
- Hétérogénéité des schémas de run_summary
- Pas de persistance SQL systématique
- Pas d'alerting (email/SMS/Slack)
- Pas de dashboard de monitoring

### Risques principaux
- Incident non détecté à temps
- Perte de résumé si stdout non capturé

### Pour atteindre 10/10
- Uniformiser le schéma des run_summary
- Persister tous les résumés en SQL
- Ajouter des alertes (email/Slack)
- Intégrer Prometheus/Grafana

---

## 16. Sécurité / Readiness Production

**Note : 7.0 / 10**

### Résumé
Les secrets sont gérés proprement (variables d'environnement, scanner de littéraux). Le préflight execution et le kill switch sont de bons garde-fous. Points faibles : pas de chiffrement DB, pas de Vault, pas d'audit de sécurité externe.

### Points forts
- Secrets en environnement (pas en clair dans config.yaml)
- Scanner de secrets littéraux
- Préflight exécution
- Kill switch
- Confirmation interactive pour le live

### Faiblesses
- Pas de chiffrement de la DB
- Pas de gestion de secrets type Vault/AWS SSM
- Pas d'audit de sécurité externe
- Pas de sandboxing des dépendances

### Risques principaux
- Vol de credentials si l'environnement est compromis
- Erreur de manipulation en live

### Pour atteindre 10/10
- Intégrer un vault (Vault, AWS SSM)
- Chiffrer les données sensibles en DB
- Ajouter un audit de sécurité externe
- Implémenter une séparation de privilèges

---

## 17. Qualité Logicielle Globale

**Note : 7.5 / 10**

### Résumé
Le projet a un bon niveau de qualité : lint (ruff), typage (mypy), tests (pytest), CI/CD (GitHub Actions). Points faibles : couverture de tests insuffisante sur certains modules, pas de tests E2E, duplication de code entre import_eodhd_bar et import_alpaca_bar.

### Points forts
- ruff configuré
- mypy configuré
- pytest avec couverture ≥ 60%
- CI/CD GitHub Actions
- Structure de package propre

### Faiblesses
- Pas de tests E2E
- Pas de tests d'intégration avec MySQL Docker
- Duplication entre les deux importeurs de barres
- Certains modules peu testés

### Risques principaux
- Régression non détectée sur un module peu testé
- Bug d'intégration entre modules

### Pour atteindre 10/10
- Ajouter des tests E2E
- Ajouter des tests d'intégration MySQL
- Réduire la duplication
- Augmenter la couverture à ≥ 80%
- Ajouter des tests de performance
