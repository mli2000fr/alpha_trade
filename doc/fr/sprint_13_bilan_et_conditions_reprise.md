# Sprint 13 France — Bilan, limites et conditions de reprise

Date : 4 octobre 2026. Ce document est le point d'entrée pour reprendre le
travail sans confondre résultats exploratoires et validation stricte.

## 1. Décision du propriétaire du projet

La branche exploratoire du Sprint 13 est terminée. Sa validation stricte reste
bloquée ; elle n'est ni réussie ni déclarée complète. **Le Sprint 14 n'est pas
autorisé à démarrer à ce stade** : le propriétaire souhaite travailler sur
autre chose avant de reprendre l'intégration France.

Ne pas lancer automatiquement un autre sprint, une confirmation 2026, un
entraînement ou une activation de serving à la lecture de ce document. Une
nouvelle autorisation explicite est nécessaire pour reprendre les travaux.

Le NO-GO économique concerne la politique LONG H5 étudiée, pas l'ensemble du
marché français ni un rejet définitif de l'Oracle d'amplitude.

## 2. Ce que le Sprint 13 devait vérifier

L'objectif est de déterminer si une politique de trading apporte une valeur
nette suffisamment stable : coûts, taxes, drawdown, exposition, rotation,
concentration des gains et comparaison à des références. Un bon score ML ou
un portefeuille gagnant sur une seule fenêtre ne suffit pas.

Deux niveaux ont été distingués :

- **Strict** : chemins économiques appuyés par des preuves historiques
  suffisamment qualifiées, notamment prix, statuts, opérations sur titres,
  dates de disponibilité et fiscalité.
- **Exploratoire fournisseur** : hypothèses explicites sur les données
  fournisseur et réparations documentées, sans promotion en preuve stricte.
  Les résultats servent à diagnostiquer une stratégie, pas à autoriser le live.

## 3. Travaux réalisés

| Étape | Réalisation | Rapport |
|---|---|---|
| 13-A | Gel du protocole, conservation des intentions et contrôle des gates | [Protocole](sprint_13a_protocole_validation_economique.md) |
| 13-B | Assemblage des tapes et reporting ; branche fournisseur séparée | [Assemblage](sprint_13b_assemblage_tapes_reporting.md), [exploration fournisseur](sprint_13b_exploratoire_fournisseur.md) |
| 13-C | Réparations documentées, 24 scénarios économiques terminés, attribution et décision | [Réparations et décision](sprint_13c_reparations_decision_economique.md) |
| 13-D | Retard d'entrée, plafond par titre, combinaison et baseline : 96 scénarios, zéro blocage | [Robustesse](sprint_13d_robustesse_economique.md) |

Les 24 baselines du 13-D reproduisent exactement les résultats du 13-C.
60 tests ciblés passent après le 13-D ; cela ne signifie pas que toute la
suite de tests de l'application a été exécutée. Les travaux économiques
restent dans des artefacts de recherche, sans modification des modèles,
écriture SQL canonique ou modification des réglages de production.

## 4. Comprendre les folds et l'écart de performance

Un fold est une fenêtre de test Walk-Forward hors de la période d'entraînement
du modèle correspondant. Les nombres 6 et 7 sont des identifiants de fenêtres,
pas des niveaux de qualité ou deux modèles à choisir après observation.

| | Fold 6 | Fold 7 |
|---|---|---|
| Dates des décisions d'entrée | 29 juillet 2024 au 23 janvier 2025 | 24 janvier au 23 juillet 2025 |
| Fin de tape, liquidation et cashflows inclus | 30 janvier 2025 | 1er octobre 2025 |
| Capital de départ indépendant | 4 000 EUR | 4 000 EUR |
| Oracle LONG H5 baseline, nominal | −23,89 % | +63,81 % |

Le fold 7 ne commence pas avec le capital restant après le fold 6. Ne pas
additionner les rendements comme un portefeuille continu. La fin de tape du
fold 7 en octobre couvre notamment les paiements de dividendes après sortie ;
elle n'autorise pas de nouvelles entrées jusqu'en octobre.

Le scénario nominal présenté comprend commission, spread, slippage et taxes
modélisées. Les éligibilités fiscales positives connues restent taxées ; les
inconnues ne sont pas taxées dans cette hypothèse, avec un autre scénario
où elles le sont. Ce n'est pas une preuve d'exonération ni un rendement net de
toute fiscalité personnelle.

L'écart de rendement est d'environ 87,70 points. Sur le fold 7 baseline :

- PnL Oracle total : **2 552,46 EUR**.
- Meilleur trade Abivax : **2 674,89 EUR**.
- Contribution cumulée des autres trades : **−122,43 EUR**.

Cette soustraction est une attribution comptable, **pas un backtest sans
Abivax**. Retirer le titre changerait le cash et les décisions du portefeuille.
Capter un grand gagnant peut être un objectif légitime d'une politique
d'amplitude ; ce qui manque ici est la démonstration que ces événements
compensent régulièrement les pertes et coûts dans différentes périodes.

## 5. Ce que les sensibilités ont montré

| Variante Oracle, nominal | Fold 6 | Fold 7 |
|---|---:|---:|
| Baseline | −23,89 % | +63,81 % |
| Entrée retardée d'une séance | −27,91 % | +93,46 % |
| Budget d'entrée plafonné à 10 % par titre | −20,03 % | +49,40 % |
| Retard et plafond | −24,13 % | +69,38 % |

Le retard conserve la clôture H5 originale : détention raccourcie, pas nouveau
H5 après l'entrée retardée. Le classement reste celui du signal initial,
sans confirmation de prix ni nouvelle sélection. Le plafond concerne le budget
d'entrée frais inclus ; il n'impose pas un rééquilibrage après un bond de cours.

Le retard améliore la seconde fenêtre mais aggrave la première. Le plafond
réduit les drawdowns et l'exposition sans rendre le premier fold rentable.
Aucune variante Oracle n'est positive sur les deux folds, même dans
l'hypothèse nominale favorable aux éligibilités fiscales inconnues.

Ces variantes ont été figées avant leur calcul mais **après observation des
résultats de développement**. Elles sont donc des sensibilités exploratoires,
pas une nouvelle confirmation indépendante. Il ne faut pas sélectionner le
+93,46 % puis le présenter comme une preuve de robustesse.

## 6. Travaux stricts restant ouverts

| Reste à faire | Dépendance / limite |
|---|---|
| Fermer les preuves historiques prix, statuts, opérations sur titres et PIT | Réserves du Sprint 12 ; concordance fournisseur ne suffit pas à tout qualifier |
| Qualifier la fiscalité inconnue des chemins utilisés | Ne pas assimiler absence de preuve à exonération |
| Qualifier un benchmark FR dividendes réinvestis | Pas d'alpha annoncé contre une référence inadéquate |
| Rejouer les portefeuilles strictement qualifiés | Dépend des preuves ci-dessus |
| Sensibilités secteurs, capitalisations et segments de cotation | Métadonnées historiques/PIT nécessaires, pas seulement actuelles |
| Comparaison direction/abstention | Aucune politique directionnelle validée à promouvoir actuellement |
| Revue finale formalisée du Sprint 13 | Peut conclure NO-GO ou blocage ; un gain n'est pas exigé pour documenter une décision |

Les détails actionnables sont conservés dans le
[TODO Sprint 12](TODO_sprint_12_reste_a_faire.md). On ne prétend ni que toutes
les sources gratuites possibles ont été épuisées, ni qu'un abonnement payant
résoudrait automatiquement ces réserves. Aucun achat n'est décidé.

La confirmation 2026 reste réservée et non consultée. Ne pas l'utiliser pour
choisir un seuil, un retard, un plafond ou un sous-univers qui corrigerait les
pertes du développement. Une confirmation de promotion nécessite une politique
retenue et figée avant sa consultation.

## 7. Options de reprise, après nouvelle autorisation

**Option A — Reprendre la validation stricte.** Relire le TODO des preuves,
identifier celles réellement accessibles, qualifier les chemins et le
benchmark, puis reprendre les comparaisons strictes et la revue finale. Ne
pas masquer les chemins inconnus en les supprimant après observation.

**Option B — Avancer sur l'application en recherche uniquement.** Le Sprint 14
prévoit IHM/CLI FR, sélecteurs, historiques, logs et progression. Il pourrait
être entrepris sans validation économique positive, à condition d'afficher les
limites et de bloquer paper/live et promotion de stratégie. Cette option est
une recommandation discutée, **pas une autorisation actuelle**.

**Décision actuelle : ne commencer aucune de ces options.** Le propriétaire
souhaite faire une autre activité avant de revenir sur les sprints FR.

## 8. Artefacts à conserver

- Résultats 13-C : `artifacts/fr/research/provider_exploratory_13b/exploratory-20261004-v8`.
- Attribution 13-C : `artifacts/fr/research/provider_exploratory_13b/decision-20261004-v1`.
- Résultats finaux 13-D : `artifacts/fr/research/robustness_13d/fixed-20261004-v2`.

Conserver protocoles, hashes, ledgers et rapports, pas seulement les tableaux
de rendement. Les anciens dossiers sont des jalons archivés, pas des
expériences indépendantes à additionner.
