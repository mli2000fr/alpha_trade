# Oracle TOP10 : confirmation d'une tendance persistante

## Protocole figé avant calcul

GO du 21 octobre 2026. Une hypothèse et un seuil, aucune grille d'optimisation.
Filtre **d'entrée seulement** ; pas de sortie supplémentaire sur tendance, pas
de renforcement, pas d'entraînement ni d'écriture SQL ou d'appel fournisseur.

À l'heure du premier signal de cassure intraday déjà figé, utiliser uniquement
la séance boursière précédente et les données antérieures. Pour chacune des
trois dernières séances terminées :

- LONG : close > EMA20 > EMA50, EMA20 > sa valeur cinq séances auparavant,
  ADX14 ≥ 20 ;
- SHORT : close < EMA20 < EMA50, EMA20 < sa valeur cinq séances auparavant,
  ADX14 ≥ 20.

ADX mesure la force et n'attribue pas de sens. Même calcul que `_adx` dans les
features existantes (lissage EWM Wilder). EMA ajust=False ; 60 séances contiguës
valides minimales. Une barre manquante/synthétique/invalide interrompt la série,
sans remplacement par un état ancien. Pas de données de la séance en cours.
Un signal refusé n'est pas retenté plus tard ; aucun remplacement TOP11.

Témoin et filtre : mêmes candidats annuels archivés, même formule de taille,
SL7 %, trailing15 %, sans TP, demi-position, plafond de levier ×1, 4 000 USD
indépendants chaque année, B4 DD15 avec ses reprises et sorties natives.
Les protections, frais 8bps/jambe, emprunt SHORT hypothétique 0,3% annual/252
et financement ACT/360 restent ceux de la référence scellée DD15.
L'échéance historique reste J+20 depuis Oracle (attente incluse), pas le nouveau
contrat live de vingt séances après l'entrée puis open21. Taille effectivement
achetée et décisions B4 peuvent différer à cause du chemin de capital.

Deux années 2025 et 2026 jusqu'au 30 septembre ; huit comptes (témoin/filtre ×
LONG/SHORT × deux années). Recalcul des quatre témoins, reproduction obligatoire
des résultats et transactions scellés. Audit séparé des sorties, cash, frais,
emprunt, valorisation, risque quotidien et admission par le filtre.

Quatre fichiers ont évolué depuis la grille (raccordement du mécanisme de
renforcement, désactivé par défaut). Leurs anciennes copies sont vérifiées
contre les hashes scellés ; les versions utilisées sont explicitement hachées
dans le nouveau protocole. Il ne s'agit pas de prétendre un code identique :
la reproduction exacte des quatre témoins est exigée avant toute conclusion.
Les profils B4 figés sont réutilisés sans relecture des réglages YAML courants.

## Limites héritées

Même cohorte conditionnelle de **213 campagnes / 72 titres** : 119 en 2025,
94 en 2026, issue des TOP10 Oracle parcours CatBoost OOS de recherche, pas le
champion LightGBM production. Sélection par disponibilité future du parcours et
univers actuel : biais de couverture/survivants, pas tout le TOP10 historique.
2024 non qualifié en intraday. Prix daily retraités : date causale ne prouve pas
un reçu applicatif PIT ancien. Ni borrow/locates/fills réels ni parité live complète.
Les deux années ont déjà été étudiées ; hypothèse nouvelle mais pas holdout neuf.
Le résultat ne pourra pas être transformé en preuve de production.

## Exécution et résultats

Commande : `python -u -m scripts.research.us_oracle_persistent_trend`

Dossier : `artifacts/research/us_oracle_persistent_trend/20261021-v1`.
`progress.json` suit les huit comptes ; `eligibility.parquet` garde chaque
acceptation/refus et ses valeurs observées ; `annual-summary.csv` et `report.json`
conservent rendement, DD, gagnants/perdants, gains/pertes moyens, durées et
capital moyen. Les dossiers par bras gardent transactions, valorisations et audits.

## Résultats terminés et contrôlés

**8/8 comptes terminés, aucun échec**, environ 23 secondes hors préparation.
Les quatre témoins reproduisent les transactions, positions ouvertes et
métriques de la grille DD15. Les audits du moteur reconstruisent les sorties,
cash, frais, emprunt, valorisations et décisions B4. Une seconde implémentation
scalaire relit les **426 signaux** sans utiliser les fonctions EMA/ADX du filtre :
accord de toutes les décisions, erreur maximale des valeurs 7,82e-14.
Identité PnL/coûts pour huit comptes : erreur maximale 5,46e-12 USD.
**107 tests réussis**, dont causalité, trous de données, symétrie, comparaison
scalaire et garde des anciennes sources. Même assistant, pas revue humaine indépendante.

### Rendements et risque après coûts

Chaque ligne part indépendamment de 4 000 USD ; 2026 s'arrête au 30 septembre.
DD est présenté en amplitude positive de baisse depuis le pic, pas une perte
maximale garantie par le paramètre B4.

| Sens / année | Sans filtre | Avec filtre | DD sans filtre | DD avec filtre | Capital final filtré |
| --- | ---: | ---: | ---: | ---: | ---: |
| LONG 2025 | +26,83 % | +1,29 % | 22,36 % | 14,08 % | 4 051,69 USD |
| LONG 2026 | +16,94 % | +13,11 % | 20,32 % | 13,93 % | 4 524,23 USD |
| SHORT 2025 | −24,72 % | −15,07 % | 37,05 % | 21,61 % | 3 397,05 USD |
| SHORT 2026 | −25,61 % | −2,23 % | 27,63 % | 5,97 % | 3 910,96 USD |

| Sens / année | Trades clos sans → avec | Gagnants sans → avec | Capital brut moyen sans → avec |
| --- | ---: | ---: | ---: |
| LONG 2025 | 100 → 7 | 37,00 % → 28,57 % | 2 483,21 → 187,09 USD |
| LONG 2026 | 73 → 18 | 34,25 % → 44,44 % | 1 961,11 → 796,04 USD |
| SHORT 2025 | 94 → 28 | 27,66 % → 25,00 % | 1 161,73 → 683,16 USD |
| SHORT 2026 | 61 → 6 | 19,67 % → 16,67 % | 714,00 → 160,49 USD |

Les positions ouvertes 2025 restent valorisées : sept LONG et huit SHORT pour
le témoin, zéro LONG et deux SHORT pour le filtre. Aucune position ouverte fin
de période 2026. Les taux de gagnants concernent les seuls trades clos ; les
rendements incluent la valorisation des positions ouvertes et leurs coûts.

### Gains/pertes et durées dans le bras filtré

| Sens / année | Gagnants / perdants | Gain moyen | Perte moyenne | Détention gagnant / perdant |
| --- | ---: | ---: | ---: | ---: |
| LONG 2025 | 2 / 5 | +386,72 USD | −144,35 USD | 13,00 / 4,80 séances |
| LONG 2026 | 8 / 10 | +139,77 USD | −59,40 USD | 13,88 / 5,90 séances |
| SHORT 2025 | 7 / 21 | +100,96 USD | −62,11 USD | 15,29 / 4,33 séances |
| SHORT 2026 | 1 / 5 | +204,19 USD | −58,65 USD | 17,00 / 4,20 séances |

### Qu'a réellement sélectionné le filtre ?

Tous les signaux ont assez de données daily qualifiées : aucun refus technique.
Le filtre accepte seulement **7/119 LONG 2025**, **19/94 LONG 2026**,
**31/119 SHORT 2025** et **6/94 SHORT 2026**. Admission par filtre ne garantit
pas achat : capital, risque, état de portefeuille et échéance s'appliquent ensuite.

L'attribution descriptive des transactions du témoin, à tailles strictement
inchangées, aide à ne pas confondre sélection et variation du capital :

| Transactions du témoin | Gardées par la règle | Gagnants gardés | Gagnants rejetés |
| --- | ---: | ---: | ---: |
| LONG 2025 | 4/100 | 25,00 % | 37,50 % |
| LONG 2026 | 14/73 | 35,71 % | 33,90 % |
| SHORT 2025 | 27/94 | 25,93 % | 28,36 % |
| SHORT 2026 | 6/61 | 16,67 % | 20,00 % |

Ce ne sont **pas** des backtests de sous-portefeuilles autonomes. Le compte
filtré a un chemin de trésorerie/B4 différent et peut acheter d'autres signaux
qui étaient auparavant refusés : par exemple sept LONG achetés en 2025 contre
quatre trades clos du témoin satisfaisant la règle. La hausse du taux gagnant
LONG 2026 dans le replay complet ne peut pas être attribuée uniquement à la
qualité directionnelle du filtre.

## Conclusion bornée

**Pas de validation pour activer ce filtre en production.** La règle stricte
réduit l'activité et le DD, mais ne démontre pas de gain directionnel stable :
elle élimine la plupart des gains LONG 2025 et les SHORT restent perdants avant
même les coûts dans les deux années. Les rares observations filtrées rendent
les estimations très fragiles. La réduction des pertes SHORT s'accompagne
d'une forte baisse du capital exposé, sans amélioration du taux de gagnants.
Sans témoin d'exposition appariée, on ne peut pas mesurer une contribution
causale propre de la persistance au-delà du fait de moins trader.

Ce résultat concerne **cette règle complète uniquement**, pas l'impossibilité
de toute stratégie de tendance. Aucun assouplissement de seuil après résultat,
nouveau modèle, changement de configuration ou activation PAPER/live effectué.

Contrôles : `final-review.json`, `post-review.json`, `cost-audit.csv`,
`baseline-trades-gate-attribution.csv`. Tests :
`artifacts/tmp/persistent-trend-tests-final-20261021.xml`.
