# France — état actuel et parcours documentaire

État rapproché des sources le **10 octobre 2026**. Marché FR_EQ, base
alpha_trade_fr isolée, alias fr_primary, EUR, calendrier XPAR.
Le contexte marché reste désactivé pour l'exécution broker ; les collectes
de recherche explicitement actives ont leur catalogue propre batch_fr.yaml.

## Pour reprendre l'application

1. [État multi-marchés et parcours actuels](../ETAT_ACTUEL_IMPLEMENTATION.md).
2. [Catalogue des batchs actifs/bloqués](../operations/catalogue_batchs_actuel.md),
   [horaires compatibles avec le PC](../operations/horaires_fr_cn_presence_pc.md).
3. [Publication quotidienne SQL en staging](publication_quotidienne_staging_sql.md) :
   EODHD n'est pas promu automatiquement vers les barres canoniques.
4. [Remédiation et audit de couverture](remediation_collectes_couverture_20261009.md).
5. [Simulation shadow locale XPAR 164](simulation_shadow_locale_xpar_164.md) :
   exercice local, pas PAPER broker ni preuve de GO production.
6. [Clôture Sprint 17 avec réserves](sprint_17_cloture_avec_reserves.md),
   [capacités Trading212](sprint_17g_decision_capacites_trading212.md).
7. [Sprint 18 — préparation livrée, canary bloqué](sprint_18_preparation_exploitation.md),
   [TODO de reprise](TODO_reprise_exploitation_sprints_16_18.md).

## Ne pas confondre les périmètres

Les 330 identités S6C, les 294 marquées actives et les 164 XPAR du shadow ne
sont pas trois mesures de couverture identiques. L'univers fournisseur global
ne devient pas automatiquement un univers PIT validé. Les sprints de recherche
et leurs métriques restent datés, avec leurs preuves et leurs exclusions.
Trading212 DEMO EUR est raccordé pour lectures et qualifications bornées,
pas pour une exécution autonome SL/TP/parité autorisée.

INPI et consensus Yahoo sont actuellement désactivés pour droits/prudence.
MiFIR/FIRDS reste une collecte partielle en quarantaine, ni Excel Euronext
automatisé, ni Open Interest/NBBO complets. Une case activée dans le catalogue
n'est pas une validation de licence pour d'autres usages.

[Planning historique des sprints](sprint_planning_integration_marche_francais.md) :
document de progression, pas preuve que tous les gates de mise en production
sont levés. Lire les clôtures et TODO récents avant de relancer un lot.
