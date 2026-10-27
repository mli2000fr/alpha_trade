# France — état actuel et parcours documentaire

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

État rapproché des sources le **10 octobre 2026**. Marché FR_EQ, base
alpha_trade_fr isolée, alias fr_primary, EUR, calendrier XPAR.
Le contexte marché reste désactivé pour l'exécution broker ; les collectes
de recherche explicitement actives ont leur catalogue propre batch_fr.yaml.

## Pour reprendre l'application

Collecte du **27 octobre 2026** : [open interest public Euronext Paris](options_open_interest_public.md),
batch `fr_options_open_interest_sync`, trois tables `fr_option_oi_public_*`.
Les OI numériques CALL/PUT sont distingués des absences et valeurs invalides.
Dates OI/expiration exactes non prouvées : ces observations restent exclues
du filtre directionnel et des modèles. Cela complète MiFIR sans modifier ses tables.

Stockage du **27 octobre 2026** : les [batchs FR publient désormais leurs données
et archives en SQL de recherche](batchs_stockage_sql_20261027.md). Calendrier,
référentiel, actions sur titres, positions AMF et annonces DILA ont leurs tables ;
les barres, le consensus et les options conservent leurs stockages existants.
Historique importé et reprise sans doublons vérifiée. Les batchs bloqués ne sont
pas réactivés ; les fichiers bruts restent conservés comme preuves.

Actualisation du **27 octobre 2026** : les [options MiFIR/FIRDS ont désormais
quatre tables SQL de recherche](options_mifir_stockage_sql.md) dans `alpha_trade_fr`.
Archives du 5 au 26 octobre importées, batch raccordé et reprise sans doublon
vérifiée. Les sources brutes sont conservées ; OI et qualification de volume
restent absents, sans promotion vers ML/trading.

Audit du **26 octobre 2026** : [direction LONG/SHORT des collectes P0/P1](audit_directionnel_p0_p1_resultats_20261026.md).
Six collectes de marché auditées,293codes courants ; aucune fenêtre H20 mûre
depuis les premiers snapshots réellement reçus le5octobre. H5/H10 restent
exploratoires, sans signal validé ni modification des batchs.
[Combinaison prix/AMF à poids égaux](p0_p1_combinaison_egale_resultats_20261026.md) :
petit gain de classement H5 sur50titres/sixdates seulement, pas de validation H20.

Actualisation du **15 octobre 2026** : [consensus quotidien EODHD](consensus_eodhd_collecte_quotidienne.md)
remplace Yahoo ; accès FR, 166 lignes de smoke et reprise idempotente vérifiés.
Stockage dans deux tables dédiées `alpha_trade_fr`, catalogue activé sur demande
utilisateur le 15 octobre ; installer/réinstaller la tâche Windows depuis l'IHM.

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
