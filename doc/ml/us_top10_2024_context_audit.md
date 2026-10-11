# Pourquoi le TOP10 Oracle LONG se dégrade en 2024

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

Audit réalisé le 7 octobre 2026, sans entraînement, accès SQL, veto supplémentaire
ou modification des paramètres. Script : `scripts/research/us_top10_2024_context_audit.py`.
Artefacts : `artifacts/research/us_concentrated_replay/top10-2024-context-20261007-v1`.

## Résumé

La référence est TOP10 **prédit**, LONG, sizing ATR, SL initial fixe 7 %, sans
TP/trailing, sortie vingt séances après entrée. 2023 +42,47 %, 2024 −10,92 %.
Le problème immédiat est le déplacement des candidats d'une composition
haussière en 2023 vers davantage de D1 et moins de D10 en 2024. L'amplitude
moyenne baisse aussi. Aucun signe de marché global baissier ou manque macro
ne suffit à expliquer cette dégradation. Aucune règle anticipatrice n'est
validée par cet audit descriptif.

## Régime global : la perte existe en marché BULL

Le régime SPY est celui du runner au close du signal : close vs SMA50/SMA200,
calculés avec warm-up. Ce n'est pas une observation future.

| Candidats en régime BULL | 2023 | 2024 |
|---|---:|---:|
| Séances | 171 | 216 |
| Part réelle D1 | 22,34 % | 31,25 % |
| Part réelle D10 | 35,09 % | 19,07 % |
| Rendement H20 moyen brut | +6,46 % | −1,18 % |

En CORRECTION, les candidats 2024 ont 17,22 % de D1 et 35,28 % de D10,
rendement moyen +7,70 %, sur 36 séances. Ces chemins H20 se chevauchent :
36 séances ne sont pas 36 événements indépendants.

Attribution des **trades clos en 2024**, selon le régime à leur signal :
BULL, 145 positions et −678,96 USD ; CORRECTION, 11 positions et +415,20 USD.
Le PnL total réalisé est −263,76 USD. Ce n'est pas la variation d'equity annuelle
(environ −622,07 USD) : environ 358,31 USD de plus-values latentes fin 2023 sont
également consommés. Les positions transannuelles ne sont pas des trades ouverts
exclusivement en 2024. L'attribution ne simule pas le retrait d'un régime.

Toutes les positions clôturées dans ces deux années avaient été signalées en
mode opérationnel `normal`. Le moteur observait aussi `capital_preservation`
sur 14 séances en 2023 et 10 en 2024, où les nouvelles entrées LONG étaient
bloquées. Il ne faut pas confondre ce mode avec les quatre états de tendance SPY.
Un veto baissier supplémentaire n'est donc pas justifié par ces chiffres.

## Secteurs : changement de composition insuffisant pour expliquer

Les secteurs sont des métadonnées **actuelles NON-PIT**. Les sorties se
dégradent notamment en Biotechnology : 20 trades clos en 2023, +251,17 USD,
puis 28 en 2024, −362,14 USD, 14,29 % gagnants. Energy est négatif dans les
deux années (−144,23 puis −177,24 USD). Life Sciences Tools & Services perd
118,14 USD en 2024, correspondant aux trades TXG. Les classements actuels
doivent être conservés comme réserve, pas pris pour vérité historique.

Sur les secteurs présents dans les deux années (2 238 occurrences 2023,
2 493 en 2024), on réapplique les poids sectoriels 2023 aux taux 2024 :

| Mesure à poids sectoriels 2023 fixes | 2023 | 2024 standardisé |
|---|---:|---:|
| D1 | 22,56 % | 28,12 % |
| D10 | 36,60 % | 18,84 % |
| Rendement H20 moyen brut | +6,67 % | +0,002 % |

La dégradation persiste à composition comparable. Cela n'isole pas un effet
causal : les titres, dates et caractéristiques changent au sein des secteurs.
Ne pas exclure a posteriori Biotechnology ou Energy sur la base des pertes.

## Concentration : toujours présente, mais pas accrue en 2024

2023 : 99 titres uniques dans 2 500 occurrences TOP10 ; les dix plus fréquents
représentent 44,08 % des occurrences. 2024 : 109 titres dans 2 520 occurrences,
35,28 % pour les dix plus fréquents. HHI 0,02982 puis 0,02213.
Le TOP10 reste répétitif, mais une augmentation de sa concentration par titre
n'explique pas la baisse annuelle. Les titres changent : W/MLTX/ACIC dominent
2023 ; TXG/HOV/LMND dominent 2024. Les occurrences ne sont pas des trades.

## Folds et vieillissement : réserve technique, pas cause démontrée

Le manifeste contient douze champions, dernier `t_start=2024-01-08`, aucun
champion nouveau en juillet 2024. Le prédicteur historique choisit le dernier
champion dont t_start <= date de décision. Le début de janvier utilise donc
encore celui du 10 juillet 2023 ; à partir du 8 janvier, le même champion
sert le reste de 2024.

Sur ce même champion : D1 32,08 % / D10 19,50 % au premier semestre (120 jours),
puis D1 26,17 % / D10 23,44 % au second (128 jours). Le rendement moyen passe
de −0,26 % à +0,66 %. Le second semestre ne se dégrade donc pas uniformément
avec l'âge du modèle. Les quatre premières séances de 2024, sous le champion
précédent, sont aussi mauvaises, mais trop peu nombreuses pour conclure.

Date/fold sont confondus : sans scorer les mêmes dates avec deux modèles
qualifiés, on ne peut attribuer causalement le changement au champion.
`fold_start` ne certifie pas la totalité du train/validation, calibration,
publication des features ou membership historique. Le maintien d'un champion
au-delà de sa fenêtre test initiale ne doit pas être appelé aveuglément OOF
d'entraînement ; c'est un serving historique après origine du champion, sous
réserve de la provenance de toutes les données. Aucune réparation ou
réentraînement n'est engagé ici.

## Macro disponible, mais aucune anticipation établie

VIX/VIX9D/VXN/VIX3M/MOVE/ten_y/yield_10y_5d_pct/sentiment_score sont renseignés
sur les 250 séances 2023 et 252 séances 2024 de l'archive. Aucun manque observé
n'explique les pertes. Médianes : VIX 16,94→14,63 ; VXN 21,19→18,50 ;
MOVE 118,77→102,13 ; taux dix ans 3,87→4,25. Couverture quotidienne n'est pas
certification des heures de publication ni des vintages de révision.
Ces différences annuelles ne prouvent pas un signal prédictif, et aucun seuil
macro n'a été sélectionné sur les pertes. L'audit ne valide pas « faible VIX
donc éviter les LONG », ni l'inverse.

## Conclusion et suite limitée

On explique une partie de la dégradation : moins de hausses fortes, pertes
biotech et autres secteurs, sous-performance des candidats même en BULL.
On ne possède pas pour autant un signal d'abstention fiable connu à J.
Les essais J+5 et égalisation ont déjà dégradé les résultats : ne pas présenter
ce nouvel audit comme leur remplacement validé.

Une suite prudente serait qualifier la chaîne de provenance Oracle et comparer
la force relative titre/secteur avant signal avec une hypothèse distincte
pré-enregistrée. Cela nécessiterait les cours des pairs sectoriels, pas seulement
SPY et les titres sélectionnés, ainsi qu'une réserve explicite sur les secteurs
NON-PIT. Aucun veto, nouveau backtest ou entraînement supplémentaire lancé ici.

Les fichiers `candidate-groups.json`, `trade-attribution.json`,
`sector-standardization.json`, `macro-coverage.json`, `concentration.json` et
`context-panel.parquet` permettent de reproduire la lecture. Les hashes des
sources figurent dans le protocole ; le rapport est `COMPLETED_DESCRIPTIVE_ONLY`.

## Suite réalisée : provenance et faiblesse relative

Voir [l'audit dédié](us_top10_relative_sector_audit.md). La règle pré-entrée
rendement titre inférieur à ses pairs sur vingt séances + breadth sectorielle
inférieure à 50 % ne valide pas un veto : elle identifie une population plus
favorable aux LONG en 2023 et en 2024. Aucun filtre n'est promu. La provenance
Oracle reste partiellement documentée, sans certification PIT complète.
