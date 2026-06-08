# Simulation et Objectifs de Performance : Trading Algorithmique sur Actions US (2020-2025)

Ce document récapitule les métriques de performance, les objectifs de rentabilité logiques et les contraintes techniques pour une application de **Swing Trading Algorithmique** opérant exclusivement sur le marché américain (NYSE / NASDAQ) sur la période charnière **2020-2025**.

---

## 1. Synthèse des Objectifs de Rendement Logiques

En trading algorithmique professionnel, la rentabilité brute n'est jamais analysée seule. Elle est systématiquement mise en perspective avec le **Drawdown Maximal (DD max)**, c'est-à-dire la perte maximale historique essuyée par le capital.

### Les Profils de Performance Types
| Profil de l'Algorithme | Rendement Annuel Moyen | Drawdown Max Toléré | Comportement Attendu |
| :--- | :---: | :---: | :--- |
| **Conservateur** | 10% à 15% | 5% à 7% | Stratégie axée sur la préservation du capital. Idéal pour battre l'inflation et les rendements bancaires avec une volatilité minimale. |
| **Professionnel / Équilibré** | 15% à 25% | 8% à 12% | Cible standard des fonds quantitatifs. Bat régulièrement les indices de référence (S&P 500) sur le long terme. |
| **Agressif** | 25% à 40% | 15% à 20% | Maximisation des tendances à forte volatilité (ex: Tech/Growth). Nécessite une tolérance psychologique élevée aux fluctuations. |

> **La Règle d'Or Professionnelle :** Le ratio Rendement Annuel / Drawdown Maximal doit idéalement être supérieur ou égal à **2:1**. Viser 40% de gain par an en acceptant un drawdown de 40% n'est pas une stratégie viable à long terme.

---

## 2. Analyse Comparative : Trajectoires de Capital (2020 - 2025)

La période 2020-2025 a concentré une décennie d'événements macroéconomiques majeurs : le krach éclair du COVID-19 (2020), la bulle spéculative post-pandémie (2021), le resserrement monétaire agressif et le marché baissier (2022), suivis de l'explosion haussière liée à l'Intelligence Artificielle (2023-2025).

Voici la simulation mathématique de l'évolution d'un capital initial de **10 000 $** soumis aux intérêts composés, selon la nature de la stratégie.

### Option A : Stratégie "Long-Only" (Achat uniquement)
Un algorithme purement acheteur est dépendant de la direction globale du marché. Pour être considéré comme performant, son unique arme en marché baissier est la coupure rapide des positions et la mise en **liquidités (100% Cash)**.

*   **2020 - 2021 (Phase Haussière) :** Captation des fortes tendances de swing. Le capital progresse rapidement.
*   **2022 (Année de Crise) :** L'indice S&P 500 subit -19.4% et le Nasdaq -33.1%. L'algorithme détecte le retournement macroéconomique, coupe ses positions et reste neutre. **Résultat cible : entre 0% et -5%** (préservation réussie).
*   **2023 - 2025 (Reprise Haussière) :** Réactivation des achats dès la validation du pivot de tendance.
*   **Résultat cumulé cible (6 ans) :** **+100% à +150%** *(Capital final : ~22 000 $ à 25 000 $)*.

### Option B : Stratégie "Long/Short" (Achat et Vente à découvert)
L'activation du Short transforme l'application en outil "tout-terrain", capable d'extraire de la valeur de la panique et des marchés baissiers.

*   **2020 - 2021 (Phase Haussière) :** Performance similaire ou légèrement supérieure au marché.
*   **2022 (Année de Crise) :** Au lieu d'être neutre, l'algorithme capitalise sur l'effondrement des capitalisations américaines en swinguant à la baisse. **Résultat cible : +15% à +35%**.
*   **2023 - 2025 (Reprise Haussière) :** Reprise des positions acheteuses, complétée par de brefs shorts lors des corrections intermédiaires.
*   **Résultat cumulé cible (6 ans) :** **+180% à +350%** *(Capital final : ~28 000 $ à 45 000 $)*.

---

## 3. Spécificités Techniques du Marché Américain (NYSE / NASDAQ)

L'implémentation du Short sur les actions US nécessite d'intégrer des contraintes réglementaires et de friction strictes au sein du code de l'application.

### 1. La Réglementation de Marge (Mise à jour FINRA)
*   **Cadre historique :** La règle *Pattern Day Trader* (PDT) imposait un solde minimum permanent de 25 000 $ sous peine de blocage du compte en cas de transactions fréquentes.
*   **Cadre actuel :** L'accès à la marge intraday en temps réel est désormais conditionné à un dépôt minimum de **2 000 $** pour les comptes sur marge standards. Cela offre une flexibilité accrue pour les algorithmes de capital modéré exécutant du swing de courte durée.

### 2. La Classification des Titres pour le Short
Le script de gestion des ordres de l'application doit impérativement interroger l'état des stocks de titres du courtier avant d'émettre un signal de vente à découvert :
*   **ETB (Easy to Borrow) :** Grandes capitalisations (Mega/Large Caps) disposant de volumes de prêt massifs. Les ordres de Short s'exécutent instantanément au marché. **C'est le terrain de jeu recommandé pour l'algorithme.**
*   **HTB (Hard to Borrow) :** Actions de taille moyenne ou petite, ou sous forte pression vendeuse. Nécessite une procédure de "localisation" manuelle ou payante. Les frais de détention nocturne (*Borrow Fees*) peuvent grimper de 5% à plus de 30% par an, détruisant l'espérance de gain d'un swing trade gardé plusieurs semaines.
*   **Filtre de Code Recommandé :** Instaurer une règle stricte : *`IF Asset_Status == HTB OR Market_Cap < 2B USD THEN Block_Short_Order`*.

### 3. La Règle de Restriction des Ventes à Découvert (SEC Rule 201)
Également appelée *Alternative Uptick Rule*, elle se déclenche automatiquement si une action perd plus de **10%** sur sa valeur de clôture de la veille. 
*   **Conséquence pour l'algo :** L'interdiction formelle de shorter "au marché" au prix acheteur (*Bid*). L'algorithme doit obligatoirement soumettre des ordres limités au-dessus du prix actuel (*Ask*). 
*   **Gestion des erreurs :** Le code doit être conçu pour ne pas boucler ou générer des rejets d'ordres critiques si la Rule 201 est active sur le ticker ciblé.

---

## 4. Check-list de Validation d'un Backtest (2020-2025)

Si vous évaluez les résultats historiques fournis par votre application ou un tiers sur cette période, vérifiez les points suivants pour vous assurer qu'ils ne sont pas sur-optimisés (*Overfitted*) :

- [ ] **Modélisation des frais de nuit (Swap/Borrowing) :** Les gains en Short en 2022 intègrent-ils le coût réel du maintien des positions d'un jour à l'autre ?
- [ ] **Slippage et Écart d'Exécution :** Le backtest prend-il en compte un écart réaliste entre le signal théorique et le prix d'exécution réel (surtout lors des ouvertures de marché US en *Gap*) ?
- [ ] **Survie au biais de survivance :** L'algorithme a-t-il testé des actions qui ont fait faillite ou ont été radiées de la cote entre 2020 et 2025, ou s'est-il basé uniquement sur les entreprises survivantes et performantes d'aujourd'hui ?
- [ ] **Performance relative (Alpha) :** L'algorithme fait-il réellement mieux que le marché ajusté au risque, ou a-t-il simplement acheté du Nvidia avec un effet de levier masqué ?