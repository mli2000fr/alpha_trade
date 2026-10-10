# US — Audit figé du désaccord Oracle × ATR

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

4 octobre 2026, protocole avant résultats. Aucun entraînement, SQL write,
modèle ou batch modifié. Réutilisation des panels causaux déjà calculés
2019–2025 et janvier–mars 2026 du batch H20 e98332.

## Groupes et labels

À J, même univers commun avec Oracle, ATR20/prix et volatilité60 finis.
Oracle TOP20 = percentile quotidien moyen >=0,8 (composant officiel).
ATR TOP20 = percentile quotidien moyen ATR20/prix >=0,8. Les ex æquo
suivent la définition précédente ; les effectifs effectifs sont publiés.

Quatre groupes disjoints exhaustifs : BOTH, ORACLE_ONLY, ATR_ONLY, NEITHER.
Les labels natifs H20 de l'univers complet sont joints après classement.
Labels invalides/manquants non supprimés avant les gates, pas de déciles
recalculés sur un sous-ensemble. Les indicateurs d'amplitude sont le taux
`oracle_extreme10` natif (deux queues de 10 %) et la moyenne du rendement
terminal absolu H20. Ce n'est pas MFE/MAE, ni la range intrapériode.

## Comparaison à volatilité comparable

Strates fixées : date × décile ATR quotidien × tercile volatilité60
quotidien. Seuils de rang, pas de coupe optimisée sur les labels. Retenir
les cellules où chaque côté contient au moins cinq labels valides.

Comparer séparément :
- BOTH contre ATR_ONLY : valeur Oracle parmi les ATR TOP20 ;
- ORACLE_ONLY contre NEITHER : valeur Oracle hors ATR TOP20 ;
- Oracle retenu contre Oracle non retenu sur toutes les strates communes.

Pondération par minimum des deux effectifs de cellule puis poids égal
par date. Publier support et couverture, deltas amplitude/D10/D1/rendement.
Ne pas comparer directement ORACLE_ONLY et ATR_ONLY comme s'ils étaient
de même niveau d'ATR : les gates les séparent structurellement.

Intervalle exploratoire : bootstrap temporel mobile blocs21 séances,
500 répétitions, seed20261004, uniquement sur deltas journaliers. Réserves :
jours sans support, observations chevauchantes, multiplicité, univers
survivant et choix d'hypothèses après audits précédents. Pas de validation
prospective ni de preuve causale.

## Régime et lecture

Lire les modes actuels archivés à J, sans les recalculer/persister.
LONG autorisé = normal et allow_new_entries=1 ; inconnu séparé.
Publier mois, semestres, années, groupes de régime ; missing macro signalé.
2026 uniquement T1 (la couverture H1 ne crée pas de nouveaux panels).

Fenêtres de lecture 2019–2022, 2023–2025 et 2026T1, sans prétendre qu'elles
sont intactes. Un enrichissement D1+D10 sans dominance directionnelle est
un avantage d'amplitude, pas un modèle LONG. Aucun filtre productif proposé
sur la seule moyenne d'un groupe. Coûts, portefeuille et exits exclus.

Sortie : `artifacts/research/us_atr_oracle_sentiment/oracle-atr-disagreement-20261004-v1/`.
Script : `scripts/research/us_oracle_atr_disagreement.py`. progress.json,
report.json, cohortes par année et comparaisons journalières pour traçabilité.
