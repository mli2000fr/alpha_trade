# Q051 volatilité 20 % + régime — audit des stratégies de range M15

Date : 9 novembre 2026. **Revue de faisabilité uniquement ; aucun nouveau
backtest, entraînement, ordre, paramètre de production ou écran modifié.**

## Source et portée

Document lu : `C:/Users/PC ming/Downloads/ALPHA_TRADE_SPEC_STRATEGIE_VIDEO.md`.
SHA256 : `eb85aac9c6a1e0d203ca7690d2f667a3b4272eab752a4e96b07c1b697f5b7902`.
Le fichier se présente comme une reconstitution de travail, pas une transcription
certifiée de la vidéo. Les seuils chiffrés sont des hypothèses d'ingénierie.
La vidéo elle-même n'a pas été fournie ni contrôlée dans cette revue.
Les consignes d'implémentation incluses dans le document ne constituent pas
un GO utilisateur pour développer tout le module, les écrans ou le live.

## Référence conservée

Témoin : `artifacts/research/us_winner_q051_risk_budget/20261109-v1/REGIME_VOL20`.
01/01/2021–01/10/2026, 4 000 USD continus : +125,98 %, DD intraday −24,29 %,
36,17 % gagnants. Oracle H10 annuel, TOP10 % (179) puis TOP5 LONG per-symbol,
probabilité >0,50 et AUC de calibration du titre ≥0,50, aucun remplissage.
Entrée open J+1, position complète, SL5 %, sans TP/trailing/renforcement,
sortie open11. Risque 1,25 %, poids 20 %, plafond achats 1×, capacité margin2×,
B4/DD15 off. Budget de volatilité portefeuille20 % sur60 séances antérieures
et filtre d'entrée SPY J >98 % de sa SMA200. Frais8pb/jambe et financement6,5 %.
Ce budget de volatilité n'est ni un seuil DD20 ni une garantie de DD maximal.

## Chevauchement avec les anciennes expériences

| Proposition du document | Antécédent dans le registre | Décision de revue |
|---|---|---|
| A2 : impulsion haussière, range, retour au support et rebond confirmé | Pullbacks quotidiens E10 et retest P03 proches, mais aucune reproduction strictement identique trouvée | **Priorité**, hypothèse d'entrée LONG distincte ; pas d'avantage démontré |
| B : fausse cassure du haut puis SHORT | Q051 testé LONG-only ; ce serait une stratégie directionnelle et une exécution différentes | Pas d'ajout SHORT au témoin ; envisager séparément un veto avant entrée ou une sortie LONG |
| B symétrique : fausse cassure du bas puis LONG | P07 rejet baissier, mais autre unité/définition et zéro motif sur112 occasions couvertes | Seconde priorité éventuelle, audit de fréquence d'abord ; P07 n'a pas prouvé une perte économique |
| C1 : nouvelle base puis entrée au support | Même famille que A2, contexte de répétition | Ne pas compter comme expérience indépendante au départ |
| C2 : cassure, retest et confirmation | P03, premier retest confirmé : +5,72/−10,42 % en2025/2026, contre Winner commun +24,61/+1,94 % | Faible priorité ; pas une idée entièrement nouvelle |
| Sorties partielles / protection des gains | P02/P06 non confirmées transversalement | Garder les sorties Q051 au premier essai |
| Filtre de tendance H4 | Filtre de persistance déjà testé, autre définition | Ne pas l'empiler dès le départ |

Les anciens essais FMZ utilisaient une cohorte CatBoost parcours H20,
SL7/TR15 et d'autres conditions ; ils ne démontrent pas que ces règles échouent
nécessairement avec Q051. Ils empêchent de présenter les variantes proches
comme inédites et invitent à limiter les nouvelles comparaisons.

## Raccordement réel nécessaire

Les barres5m peuvent servir à construire des M15 : trois barres5m fermées,
contiguës, même séance régulière et même base de prix/fournisseur. Contrôler
horaires NYSE/DST, doublons, données synthétiques et volumes. La disponibilité
doit être celle du dernier composant. Ne pas reconstruire un signal M15 à
partir du simple OHLC quotidien lorsque les5m manquent. L'audit exhaustif de
couverture de ces nouveaux motifs reste à faire.

Deux verrous techniques explicites existent actuellement :

- `backtesting/winner_intraday.py` refuse un budget de volatilité lorsque
  `daily_entry=False` ou lorsque le renforcement est actif.
- `backtesting/winner_portfolio_budget.py::replay_protections` réserve le budget
  et le régime au mode journalier J+1.

Il faut donc un raccordement de recherche isolé des entrées M15 et de la
revalidation du budget au prix d'entrée effectif. Retirer simplement ces
conditions ne suffit pas : le wrapper de risque est actuellement appliqué
dans la branche `DAILY_ENTRY`. Les résultats LONG journaliers doivent rester
strictement identiques après adaptation. Aucun besoin de nouvelle table ou
d'interface produit pour le premier pilote sur archives.

Un filtre calculé uniquement sur les M15 de J puis appliqué à l'open J+1
permettrait de conserver le mode journalier ; c'est une hypothèse différente,
qui teste un contexte passé et non l'amélioration du prix d'entrée intraday.
Il ne faudrait pas le présenter comme une reproduction de A2.

## Premier protocole recommandé, à figer avant calcul économique

1. Conserver les candidats et modèles annuels du témoin : ne pas changer
   Oracle/per-symbol, ni remplacer un candidat absent par un titre classé plus bas.
2. Auditer d'abord la couverture et le nombre de motifs A2, sans sélectionner
   les règles en regardant les rendements futurs. Arrêter si l'effectif est trop
   faible ; ne pas assouplir les seuils après observation du PnL.
3. Tester A2 **LONG seulement**, comme remplacement de l'heure d'entrée,
   sur la séance J+1. Les données précédant cette séance peuvent fournir le
   contexte, mais l'Oracle de clôture J ne permet aucune entrée rétroactive en J.
   En absence de motif avant l'expiration fixée, ne pas acheter ce signal.
4. Geler les bornes avant d'évaluer le rebond ; confirmation sur une M15 fermée,
   puis achat au premier open5m réellement disponible après la décision et
   le délai de données. Une simulation de SIP différé doit intégrer le délai
   de15min30 dans l'heure de connaissance puis le prix d'exécution, sans
   exécution rétroactive à l'open immédiatement après la bougie observée.
5. Garder SL5 %, absence de TP/trailing, open11 depuis l'entrée effective,
   budget20 % et régime, sizing, capital et coûts du témoin. Les stops sous
   range, TP par R et sorties partielles du document sont d'autres expériences.
6. Comparer : témoin original complet ; témoin sur la couverture observable
   commune ; attente fixe prédéfinie sans motif ; A2. Évaluer le portefeuille
   et les occasions communes pour distinguer signal, délai, abstention et
   variation d'exposition. Une position déjà détenue n'est pas rachetée.
7. Rapporter rendement/DD, gagnants, gain/perte moyens, capital moyen engagé,
   délais/prix d'entrée, motifs/achats/exclusions, résultats annuels et coût
   renforcé. Ne pas conclure à partir du seul taux gagnant.

## Ambiguïtés à résoudre dans le protocole

- Vingt M15 de range représentent5h ; avec douze M15 d'impulsion avant le
  range, le contexte représente8h, davantage que les6h30 d'une séance US.
  Ne pas cumuler ces défauts avec une contrainte « tout dans la même séance ».
  Définir le traitement des séances précédentes et des gaps, ou une durée
  distincte, avant l'audit ; aucun choix après recherche du rendement maximal.
- Si les bornes sont le maximum/minimum de toutes les bougies de la fenêtre,
  le ratio de clôtures à l'intérieur est mécaniquement100 %. Le seuil80 %
  ne mesure alors pas la qualité. L'appliquer à un intervalle figé sur des
  bougies suivantes, ou abandonner ce critère redondant.
- Définir précisément le choix de fenêtre, la priorité entre ranges, les
  touches espacées, les invalidations et l'expiration. Le document propose
  de nombreuses options, pas une seule règle déjà exécutable sans arbitrage.
- Un veto B observé après l'achat ne peut pas annuler cet achat dans un
  backtest : ce serait une règle de sortie. Un veto d'entrée doit être connu
  avant l'exécution. Ne pas mélanger ces deux hypothèses.

**Conclusion : faisable, A2 prioritaire pour un pilote borné.** Ni rentabilité
démontrée ni reproduction certifiée de la vidéo. Les années2021–2026 ont déjà
servi à plusieurs recherches : un nouveau replay restera exploratoire, même
avec modèles annuels causaux. Aucune implémentation ou simulation lancée par
cette revue.
