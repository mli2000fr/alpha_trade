
Tu es un **expert senior Python, architecture logicielle, data engineering et systèmes de trading**, avec une forte expertise en **swing trading**, en **fiabilité des pipelines batch**, en **qualité des données de marché** et en **gestion du risque opérationnel**.

Tu vas auditer le projet **Alpha Trade**, une infrastructure dédiée au **swing trading**, utilisant principalement les données de marché fournies par **Alpaca**.

---

# 1. Objectif de ta mission

Ton objectif est de réaliser un **audit approfondi, rigoureux et professionnel** de l’infrastructure actuelle du projet, afin d’identifier :

- les points faibles de l’architecture ;
- les risques techniques, fonctionnels et opérationnels ;
- les défauts de conception ou d’implémentation ;
- les risques d’erreurs silencieuses ou de corruption de données ;
- les insuffisances en matière de validation, monitoring, logs, tests ou documentation ;
- les opportunités d’amélioration ;
- les priorités d’action pour rendre le projet **plus robuste, plus fiable, plus maintenable et plus facile à faire évoluer**.

Tu dois ensuite proposer un **plan d’action détaillé, priorisé et concret**.

---

# 2. Sources à analyser

Tu dois impérativement t’appuyer sur :

1. **la documentation du répertoire `doc/`** ;
2. **le code source réel du projet** ;
3. les éventuels fichiers de configuration, scripts, tables, pipelines, points d’entrée CLI et composants techniques liés au module audité.

Important :
- la documentation peut être **incomplète**, **partiellement obsolète** ou **moins précise que le code** ;
- en cas de divergence entre documentation et implémentation, **le code source fait foi** ;
- tu dois signaler explicitement les écarts entre documentation et implémentation lorsqu’ils sont significatifs.

---

# 3. Contexte métier et technique à prendre en compte

Voici les contraintes réelles du projet ; ton audit doit impérativement en tenir compte.

## Contexte de trading
- Le projet est orienté **swing trading**.
- Il s’agit principalement d’un fonctionnement **cash**, sans besoin de haute fréquence.
- Les pipelines sont exécutés **une fois par jour**.
- Il n’y a **pas de besoin de streaming**, ni de traitement **temps réel**.
- Il est acceptable de faire des traitements plus lourds si cela améliore la **fiabilité**, la **cohérence** et la **robustesse**.

## Volume de données
- Pour chaque symbole, on peut avoir jusqu’à **10 ans d’historique**, avec **une barre journalière par jour**.
- L’objectif n’est pas de minimiser le coût CPU à tout prix, mais de privilégier les traitements **stables**, **déterministes** et **auditables**.

## Réinitialisation de la base
- Je vais **réinitialiser toutes les tables** pour repartir sur une base saine.
- Tu ne dois donc **pas** privilégier des choix motivés par la **rétrocompatibilité avec des données existantes**.
- Tu peux recommander des changements de schéma, de conventions ou de logique si cela améliore fortement la qualité de l’infrastructure.

## Contrainte sur les données Alpaca
- Je n’ai **pas d’abonnement Alpaca payant**, seulement l’**API gratuite**.
- Cela implique des limites de couverture de certaines données de marché.
- En particulier, certaines données via **IEX** ne représentent qu’environ **2 % à 3 % des flux**, ce qui peut affecter la qualité des métriques liées au **volume**, à la **liquidité** ou à certains filtres de sélection.

Tu dois donc :
- analyser explicitement l’impact de cette contrainte sur le projet ;
- identifier les pipelines, filtres, métriques ou hypothèses potentiellement biaisés ;
- déterminer si certains calculs deviennent peu fiables avec cette couverture partielle ;
- recommander, si nécessaire, des **API gratuites complémentaires ou alternatives**, suffisamment **fiables**, **réalistes** et **adaptées** à un projet de swing trading batch quotidien ;
- privilégier des solutions **simples**, **robustes**, **maintenables** et cohérentes avec le projet.

## Politique sur les prix
- Je ne veux **pas de variantes de prix complexes**.
- Je veux rester **simple**.
- Alpaca retourne déjà des données de type **`split_adjusted`** ou **`all`**.
- Tu dois déterminer **quelle option est la plus adaptée au projet**, en expliquant clairement ton choix.
- Tu dois privilégier une convention de données **simple, stable, cohérente et facile à maintenir**.

---

# 4. Périmètre de l’audit

Tu dois analyser le projet **module par module** et **pipeline par pipeline**.

Tu dois couvrir, lorsque c’est pertinent pour le module audité :

- ingestion et collecte de données ;
- validation et qualité des données ;
- stockage et cohérence base de données ;
- transformations intermédiaires ;
- calculs métiers ;
- sélection de titres / screening / scoring ;
- backtesting ;
- exécution des ordres ;
- synchronisation broker ;
- gestion des positions ;
- rapprochement / reconciliation ;
- logging, alerting, monitoring ;
- gestion des erreurs ;
- configuration ;
- documentation ;
- stratégie de tests.

Tu dois raisonner de manière **concrète**, sur la base du projet réel, et non produire une liste générique de bonnes pratiques.

---

# 5. Attentes méthodologiques

Je veux une analyse de niveau **expert et professionnel**.

Tu dois être :

- **rigoureux** ;
- **méthodique** ;
- **critique** ;
- **concret** ;
- **orienté production** ;
- **orienté fiabilité et réduction du risque opérationnel**.

Tu ne dois pas te limiter à dire qu’un point est “améliorable” :
tu dois expliquer :
- **ce qui pose problème** ;
- **pourquoi c’est un risque** ;
- **dans quelles conditions cela peut échouer** ;
- **quel est l’impact probable** ;
- **quelle amélioration proposer** ;
- **quel niveau de priorité attribuer**.

Tu dois rechercher en particulier :
- les erreurs silencieuses ;
- les hypothèses implicites non vérifiées ;
- les traitements non idempotents ;
- les schémas de données fragiles ;
- les points de couplage excessif ;
- les logiques difficiles à tester ;
- les risques de divergence entre données broker, ordres, fills et positions ;
- les trous de supervision ;
- les dépendances externes insuffisamment contrôlées ;
- les choix techniques qui compliquent inutilement la maintenance.

---

# 6. Axes d’analyse obligatoires

Ton audit doit impérativement couvrir les axes suivants.

## 6.1 Robustesse et fiabilité
Analyse :
- la gestion des erreurs ;
- les garde-fous ;
- l’idempotence ;
- la reprise sur incident ;
- la cohérence des étapes de pipeline ;
- les scénarios partiels ou intermédiaires ;
- la résistance aux cas limites.

## 6.2 Qualité et cohérence des données
Analyse :
- la validation des données entrantes ;
- la détection des valeurs manquantes, incohérentes ou dupliquées ;
- la gestion des trous de données ;
- la cohérence temporelle ;
- l’alignement des calendriers ;
- la cohérence des prix, volumes et corporate actions ;
- la pertinence du choix entre `split_adjusted` et `all`.

## 6.3 Impact des limites Alpaca gratuites
Analyse spécifiquement :
- l’impact de la couverture partielle IEX ;
- les risques sur les filtres de volume et de liquidité ;
- les effets potentiels sur la sélection des titres ;
- les biais possibles dans les scores, screenings ou validations ;
- les alternatives gratuites crédibles ou sources complémentaires pertinentes.

## 6.4 Architecture et maintenabilité
Analyse :
- la séparation des responsabilités ;
- le couplage entre modules ;
- la lisibilité du code ;
- la duplication ;
- la complexité évitable ;
- la qualité des interfaces ;
- la facilité d’évolution.

## 6.5 Exécution, ordres, positions et réconciliation
Si le module audité touche à l’exécution, tu dois examiner :
- la robustesse du workflow d’ordre ;
- la traçabilité des demandes d’ordre ;
- la cohérence entre intentions, ordres broker, fills et positions ;
- les états incohérents possibles ;
- les mécanismes de verrouillage ;
- la qualité des rapprochements et de la réconciliation.

## 6.6 Observabilité et exploitation
Analyse :
- la qualité des logs ;
- la présence d’identifiants de corrélation ;
- la facilité de diagnostic ;
- les métriques utiles ;
- les alertes ;
- la capacité à détecter les anomalies rapidement ;
- l’auditabilité globale du système.

## 6.7 Performance et scalabilité raisonnable
Analyse :
- si les performances sont adaptées à un batch quotidien ;
- si certains traitements sont inutilement fragiles ou coûteux ;
- si le design restera viable avec davantage de symboles ou davantage d’historique ;
- si les accès base ou calculs peuvent devenir des goulots d’étranglement.

## 6.8 Sécurité et sûreté opérationnelle
Analyse :
- la gestion des secrets ;
- la validation des entrées critiques ;
- les protections contre les opérations destructrices ;
- les risques de mauvaise configuration ;
- les garde-fous autour des actions sensibles.

## 6.9 Qualité du code Python
Analyse :
- l’organisation du code ;
- la clarté des responsabilités ;
- le typage ;
- les interfaces ;
- la dette technique ;
- la facilité de lecture, d’évolution et de revue.

## 6.10 Tests
Analyse :
- la présence ou l’absence de tests unitaires ;
- les tests d’intégration ;
- les scénarios de non-régression ;
- les cas d’échec ;
- les composants critiques insuffisamment couverts ;
- les moyens d’améliorer la confiance dans le système.

## 6.11 Documentation
Analyse :
- la qualité de la documentation existante ;
- les écarts avec le code ;
- les manques sur les points critiques ;
- les zones qui doivent être mieux documentées pour faciliter la maintenance future.

---

# 7. Ce que je veux comme livrables

Tu dois produire **deux livrables complémentaires** :

## Livrable 1 — Audit détaillé
Un audit structuré de l’existant, avec :
- les constats ;
- les risques ;
- les impacts ;
- les recommandations ;
- les priorités.

## Livrable 2 — Plan d’action
Un plan d’action **priorisé et concret**, visant à renforcer :
- la fiabilité ;
- la robustesse ;
- la maintenabilité ;
- la qualité des données ;
- la supervision ;
- la testabilité ;
- la capacité d’évolution du projet.

---

# 8. Format de restitution imposé

Structure impérativement ta réponse avec les sections suivantes.

## 1. Résumé exécutif
Fais une synthèse claire de :
- l’état général du module ou du projet ;
- son niveau de maturité ;
- les principaux risques ;
- les priorités immédiates.

## 2. Constat détaillé par module / composant / pipeline
Pour chaque point important, donne :
- le module ou composant concerné ;
- le constat ;
- le risque ;
- l’impact ;
- le niveau de criticité ;
- la recommandation.

## 3. Risques prioritaires
Classe les risques par niveau :
- **critique** ;
- **élevé** ;
- **modéré** ;
- **faible**.

## 4. Analyse spécifique des données de marché Alpaca gratuites
Ajoute une section dédiée qui précise :
- l’impact concret de l’offre gratuite Alpaca ;
- les biais potentiels liés à IEX ;
- les conséquences sur le volume, la liquidité et les filtres de sélection ;
- les contournements possibles ;
- les alternatives gratuites ou complémentaires pertinentes, avec :
  - avantages,
  - limites,
  - fiabilité,
  - pertinence pour ce projet.

## 5. Choix recommandé pour la politique de prix
Ajoute une section dédiée où tu :
- compares brièvement `split_adjusted` et `all` ;
- indiques l’option la plus adaptée au projet ;
- justifies ce choix ;
- expliques les implications pratiques pour les pipelines.

## 6. Quick wins
Liste les améliorations rapides à forte valeur ajoutée.

## 7. Recommandations structurelles
Liste les changements plus profonds à envisager pour assainir durablement l’infrastructure.

## 8. Plan d’action priorisé
Découpe les actions en :
- **court terme** ;
- **moyen terme** ;
- **long terme**.

## 9. Lacunes de tests, monitoring et documentation
Précise ce qui manque et ce qu’il faut mettre en place.

---

# 9. Niveau de précision attendu

Je ne veux pas une réponse générique.

Je veux une analyse :
- **contextualisée au projet réel** ;
- **argumentée** ;
- **précise** ;
- **directement exploitable** ;
- **orientée décision**.

Quand tu identifies un problème, indique clairement s’il s’agit principalement :
- d’un risque de **fiabilité** ;
- d’un risque de **cohérence des données** ;
- d’un risque de **maintenabilité** ;
- d’un risque **opérationnel** ;
- d’un risque de **sécurité / supervision** ;
- ou d’un problème de **performance / scalabilité**.

Lorsque c’est utile, appuie-toi explicitement sur :
- les fichiers ;
- les fonctions ;
- les classes ;
- les tables ;
- les pipelines ;
- les scripts ;
- les points d’entrée concernés.

---

# 10. Consignes de sortie et sauvegarde

Tu dois produire une synthèse claire et exploitable, puis la sauvegarder dans le fichier cible demandé.

Utilise la consigne suivante selon le module audité :

- si l’audit concerne l’exécution : sauvegarde la synthèse dans `prompt/refactor/audit_execution.md`
- si l’audit concerne `dataIntegrityEngine` : sauvegarde la synthèse dans `prompt/refactor/audit_dataIntegrityEngine.md`


---

# 11. Instruction finale

Commence par lire la documentation pertinente dans `doc/`, puis analyse le code réel du module concerné.

Réalise d’abord un **audit complet de l’existant**, puis propose un **plan d’action détaillé, priorisé et justifié**.

Sois **exigeant**, **méthodique**, **professionnel** et **concret**.  
Ton objectif est de faire émerger une infrastructure **solide, fiable, simple à maintenir et capable de supporter durablement les besoins du swing trading batch quotidien**.
