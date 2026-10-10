# Documentation — Intégration du marché chinois

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## État opérationnel du 10 octobre 2026

Lire d'abord [l'état actuel multi-marchés](../ETAT_ACTUEL_IMPLEMENTATION.md)
et [le catalogue des batchs](../operations/catalogue_batchs_actuel.md).
Les comptes rendus de sprints ci-dessous décrivent des livraisons et preuves
datées, pas une autorisation actuelle de collecte/serving.

D9 BaoStock est bloqué par prudence sur les droits ; D6 SSE/SZSE automatisé
également. D10 et l'audit 17-C activés peuvent manquer ces dépendances : ils
ne prouvent pas une chaîne quotidienne saine. Pas de broker CN autorisé.
Trois bases séparées US/CN/FR, alias cn_primary vers alpha_trade_cn. Le backup
et les fenêtres du PC sont documentés dans
[le planning actuel](../operations/horaires_fr_cn_presence_pc.md).

Ordre de lecture recommandé :

0. [Guide fonctionnel CN_A — prise en main de l'application](./doc_fonctionnel.md)
1. [Audit du code et roadmap](./roadmap_integration_marche_chinois_audit_code.md)
2. [Sprint planning détaillé](./sprint_planning_integration_marche_chinois.md)
3. [Architecture des bases, batchs et configurations](./architecture_bases_batchs_configuration_cn.md)
4. [Sprint 0 — baseline US et ADR](./sprint_0_baseline_us_et_adr.md)
5. [Sprint 1 - MarketContext et registre](./sprint_1_market_context.md)
6. [Sprint 2 — Référentiel instruments](./sprint_2_referentiel_instruments.md)
7. [Sprint 6 — sources gratuites BaoStock](./sprint_6_sources_gratuites_baostock.md)
8. [Comparaison des données fournisseurs](./comparaison_data_fournisseur.md)
9. [Actualisation des fournisseurs](./actualisation_fournisseurs_chine.md)
10. [Étude d’opportunité historique](./Étude%20d’opportunité%20—%20Extension%20d’α-Trade%20au%20marché%20actions%20chinois.md)

Le guide fonctionnel décrit les contrats implémentés ; roadmap/planning définissent
la cible et les suites. L'étude historique et le choix gratuit du Sprint 6
expliquent le contexte : ils ne lèvent pas les blocages actuels ci-dessus.

## Décisions normatives

- données US dans `alpha_trade` ;
- données Chine dans `alpha_trade_cn` ;
- code, contrats logiques, repositories, ML et backtest partagés ;
- `market_code` et `database_alias` obligatoires malgré l’isolation physique ;
- `config.yaml` et `batch.yaml` portent le chemin US/legacy ; quatre entrées CN de recherche restent dans batch.yaml jusqu'à une migration contrôlée ;
- `config_cn.yaml` et `batch_cn.yaml` réservés au chemin Chine ;
- suffixe `_cn` pour tout autre fichier de configuration, profil de features, univers ou manifeste propre à la Chine ;
- BaoStock a servi de primaire au Sprint 6 ; son propriétaire quotidien D9 est actuellement bloqué. AKShare, RQData et Tushare ne sont pas des remplaçants activés/qualifiés ;
- `config/databases.yaml` reste transversal et route les trois bases US/CN/FR.

En cas d’ambiguïté, [architecture_bases_batchs_configuration_cn.md](./architecture_bases_batchs_configuration_cn.md) prévaut pour la base, les batchs et les configurations ; la roadmap prévaut pour les impacts code ; le sprint planning prévaut pour l’ordre de réalisation.
- [Sprint 3 — contexte marché sur les runs, batches et univers](./sprint_3_contexte_marche_runs.md) — contrat parent, serving par marché, backfill US et garde cross-market.

- [Sprint 4 — calendrier et PIT multi-marchés](./sprint_4_calendrier_pit_multi_marches.md) — séances US/CN, segments, cutoffs dataset et compatibilité NYSE.

- [Sprint 5 — migration canonique US vers `instrument_id`](./sprint_5_migration_canonique_us.md) — backfill reprenable, double écriture, parité US et gate avant données CN canoniques.

- [Sprint 6 — sources gratuites BaoStock](./sprint_6_sources_gratuites_baostock.md) — base `alpha_trade_cn`, staging multi-fournisseurs, smoke réel et chemin Oracle amplitude.
- [Archive Sprint 6 Tushare](./sprint_6_connecteur_tushare_staging.md) — connecteur conservé mais non requis.
- [Sprint 7-B — canonicalisation historique](./sprint_7b_canonicalisation_complete.md) — 5 405 actions, backfill 2018–2025 et contrat des limites dérivées.
- [Audit et remédiation Sprint 7-B](./sprint_7b_audit_final_2026_09_24.md) — couverture, exceptions de radiation, suspensions contradictoires et correctif des limites ST.
- [Contrat d'univers tradable PIT](./contrat_univers_tradable_pit.md) — convention de radiation inclusive, exclusions des statuts contradictoires et limites inconnues, sans fuite temporelle.
- [Sprint 8 — Univers quotidien Point-in-Time](./sprint_8_univers_pit.md) — politique V1, snapshots avant séance, audit après clôture, migration CN et gate de validation.
- [Validation finale du Sprint 8](./sprint_8_validation_finale_2026_09_25.md) — 1 942 séances, contrôle complet PIT et traitement des exceptions.
- [Sprint 9 — Features CN price-only](./sprint_9_features_cn_price_v1.md) — panel PIT `cn_price_v1`, benchmark CSI 300, rangs transversaux et limites documentées.
- [Validation Sprint 9, 2018–2025](./sprint_9_validation_2018_2025.md) — 8,28 M lignes, audit global et limites sectorielles/ajustements.
- [Sprint 10-A — Labels Oracle CN](./sprint_10a_labels_oracle_cn.md) — H5/H10/H15/H20, disponibilité future, facteurs vérifiés et déciles D1–D10.
- [Sprint 10-A — Validation 2018–2025](./sprint_10a_validation_2018_2025.md) — audit des 32 artefacts, couvertures et quarantaine avant entraînement.
- [Sprint 10-B — Oracle amplitude Walk-Forward](./sprint_10b_oracle_walk_forward.md) — protocole pré-enregistré, folds OOS CN, baseline ATR et gate de recherche.
- [Sprint 10-C — Global ranking signé CN](./sprint_10c_global_ranking.md) — classement D1–D10 sur l'univers PIT et dans le TOP20 Oracle OOS.
- [Sprint 11-A — Diagnostic directionnel après Oracle](./sprint_11a_diagnostic_directionnel.md) — veto D1, sélection LONG, abstention et comparaison explicite à la réversion.
- [Sprint 11-B — Stress économique du veto D1](./sprint_11b_veto_economic.md) — coûts, lots et blocages CN ; replay indicatif, pas backtest portefeuille.
- [Sprint 12-A — Contrat d'exécution daté CN](./sprint_12a_contrat_execution.md) — règles 2018–2025 et coûts proxy installés dans alpha_trade_cn, fail-closed hors période et sans preuve de fill.
- [Sprint 12-B — Replay de portefeuille CN_A](./sprint_12b_replay_portefeuille_cn.md) — cash/inventaire T+1, non-fills et coûts détaillés ; fills de recherche hypothétiques, gate économique OOS encore ouvert.
- [Sprint 13-A — Préflight économique sans labels futurs](./sprint_13a_preflight_economique.md) — protocole H20 gelé ; 5,77–6,17 % des fenêtres candidates croisent une corporate action non classifiée, au-dessus du gate de 5 %.
- [Sprint 13-A2 — Normalisation ciblée des actions d'entreprise](./sprint_13a2_normalisation_actions.md) — collecte BaoStock reprenable, rapprochement ex-date/termes/facteur, puis relecture du gate inchangé.
- [Sprint 13-B — Replay économique OOS CN_A](./sprint_13b_validation_economique.md) — distributions A2 et sortie liée au fill ; 40 sous-runs diagnostiques, sans GO économique.
- [Sprint 13-B2 — Remédiation des positions détenues](./sprint_13b2_remediation_positions.md) — trois opérations sur titres rapprochées avec preuves séparées ; position suspendue censurée, sans sortie fictive.
- [Sprint 13-B3 — Audit des huit titres bloquants](./sprint_13b3_audit_huit_blocages.md) — campagne 480 replays, une preuve additive ciblée ; autres événements et sorties non vérifiées toujours censurés.
- [Sprint 13-B4 — Dilution des actions rachetées](./sprint_13b4_dilution_actions_rachetees.md) — trois droits économiques d'émetteur rapprochés du facteur de marché sans modifier la tolérance générale ; 24/24 cellules ciblées valides, sans GO économique.
- [Sprint 13-B5 — Matérialité et droits économiques](./sprint_13b5_materialite_et_preuve_economique.md) — trois ruptures supplémentaires documentées, 36/36 cellules ciblées valides ; replay homogène terminé, 462/480 cellules valides et 18 censurées, sans GO économique.
- [Sprint 13-C — Décision économique](./sprint_13c_decision_economique.md) — comparaison homogène de quatre politiques terminée ; 34/40 cohortes communes au coût standard, résultats moyens négatifs et aucun GO production.
- [Sprint 14-A — IHM de recherche CN_A isolée](./sprint_14a_ihm_recherche_isolee.md) — sélecteur US/CN sur Pipeline, Diagnostic ML et Backtesting ; CN en lecture seule, sans réutiliser les commandes US.
- [Sprint 14-B — Diagnostic des campagnes CN_A](./sprint_14b_diagnostic_campagnes_cn.md) — registre fermé Oracle, Ranking et directionnel, métriques H5/H10/H15/H20 et stabilité OOS par semestre, sans serving.
- [Sprint 14-C — Replay CN_A de recherche dans l'IHM](./sprint_14c_replay_recherche_ihm.md) — lancement d'une cellule du protocole 13-B avec préflight CN, historique et coûts/fills hypothétiques ; aucun live.
- [Sprint 14-D — Pipeline CN_A de recherche](./sprint_14d_pipeline_recherche_cn.md) — entraînement par fold et prédictions OOS Oracle/Ranking, sans prédiction future ni serving.
- [Sprint 15-A0 — audit des flux de capitaux PIT](./sprint_15a0_audit_money_flow_pit.md) — Eastmoney accessible mais limité à 120 séances récentes dans le smoke ; pas de GO historique 2018–2025 pour le ML.
- [Sprint 15-B0 — audit financement sur marge et prêt de titres PIT](./sprint_15b0_audit_margin_lending_pit.md) — archives officielles 2018/2020/2025 accessibles ; backfill pilote possible, ML suspendu jusqu'aux gates PIT et couverture.
- [Sprint 15-B1 — backfill pilote `融资融券` 2018–2025](./sprint_15b1_backfill_pilote_margin_lending.md) — 16 ancrages et 40 séances hebdomadaires collectés sans écriture en base ; couverture, réconciliation et PIT audités, pas encore de GO modèle.
- [Sprint 15-B2 — éligibilité et contrat PIT](./sprint_15b2_eligibilite_et_contrat_pit.md) — actions Shenzhen éligibles couvertes à 100 % sur 16 ancrages ; 3 019 transitions Shanghai en quarantaine, éligibilité SSE et vintages historiques non qualifiés, gate ML strict fermé.
- [Sprint 15-B3 — qualification des blocages](./sprint_15b3_qualification_blocages.md) — listes Shenzhen rapprochées sur 40 séances ; archives Shanghai stables à la relecture mais résidus non résolus ; prochaine voie proposée : dataset Shenzhen sous proxy, sans certification PIT ni modèle déployable.
- [Sprint 15-B4 — dataset Shenzhen et pré-enregistrement](./sprint_15b4_dataset_szse_et_preregistration.md) — collecte et audit final terminés : 1 942 séances, 2 229 667 observations, couverture 99,9996 %, aucun doublon ; 35 tests passent. Un ratio atypique à isoler avant B5 ; aucun entraînement ni PIT strict.
- [Sprint 15-B5 — features et jointures temporelles](./sprint_15b5_features_et_jointures_temporelles.md) — 24 jointures sous proxy produites et auditées, 47 tests passent ; anomalie isolée et labels inconnus préservés. Six folds bloqués par manque d'historique OOF, couverture finale restreinte ; aucun entraînement.
- [Sprint 15-B6 — calendrier et extension Oracle OOF](./sprint_15b6_calendrier_et_extension_oracle_oof.md) — audit : folds Oracle 2021 réalisables, 2020 trop court ; campagne directionnelle 2024–2025 pré-enregistrée. Les deux extensions Oracle 2021 sont terminées et leurs empreintes vérifiées ; aucun modèle directionnel.
- [Sprint 15-B7 — jointures 2021 et préflight directionnel](./sprint_15b7_jointures_2021_preflight_directionnel.md) — six jointures 2021, huit gates tâche × fold vérifiés sur populations réelles, 62 tests ciblés passent. Sous-proxy PIT et couverture XSHE étroite ; aucune preuve de performance ni serving.
- [Sprint 15-B8 — ablation directionnelle de la marge](./sprint_15b8_ablation_directionnelle_marge.md) — 64 entraînements de recherche sur quatre folds, 12 comparaisons prix seuls vs flux/encours/combiné : toutes `NO_GO_INCREMENTAL_MARGIN`. Aucun serving ni certification PIT.
- [Sprint 15-C0 — audit des analystes et prévisions PIT](./sprint_15c0_audit_analystes_pit.md) — base CN sans données analystes ; Eastmoney historique accessible mais archive non versionnée et couverture Oracle faible sur un petit échantillon ; ML historique suspendu, pilote prospectif conditionnel.
- [Sprint 15-D0 — audit des événements PIT](./sprint_15d0_audit_evenements_pit.md) — annonces officielles de résultats CNINFO historiques consultables mais signal récent rare ; Dragon/Tiger à auditer séparément et champs de rendements futurs Eastmoney exclus. Aucun entraînement ni serving.
- [Sprint 15-D1 — pilote des prévisions de résultats](./sprint_15d1_pilote_guidance_pit.md) — huit PDF CNINFO contrôlés et couverture sur tout l'Oracle OOF H20 : seulement 5,13 % de notices sous 20 jours ; archive non certifiée PIT, chiffres en quarantaine, aucun entraînement.
- [Sprint 15-D2 — audit Dragon/Tiger PIT](./sprint_15d2_audit_dragon_tiger_pit.md) — 228/228 couples marché–titre concordants sur quatre séances SSE/SZSE vs Eastmoney après filtre actions A ; heure de publication historique et valeur directionnelle non établies, aucun entraînement.
- [Sprint 15-D3 — robustesse historique Dragon/Tiger](./sprint_15d3_robustesse_historique_dragon_tiger.md) — 985/985 couples séance–marché–titre concordants sur 16 dates 2018–2025 ; 395/396 lignes SSE ont deux listes de sièges, PIT et intérêt D1/D10 non établis.
- [Sprint 15-D4 — contrat temporel et couverture Dragon/Tiger](./sprint_15d4_contrat_temporel_couverture_dragon_tiger.md) — 32 469 événements historiques mappés ; sur 464 834 décisions Oracle TOP20 OOF, couverture fraîche ≤ 5 séances de 14,435 % en J+1 ou 12,138 % en J+2. Ni PIT certifié ni GO ML.
- [Sprint 15-D5 — préflight directionnel et observation prospective](./sprint_15d5_preflight_dragon_tiger_et_observations.md) — déséquilibre brut D1/D10 non apparié, droits et heure historique non qualifiés ; journal officiel de recherche horodaté, sans entraînement ni batch planifié.
- [Sprint 15-D6 — collecte prospective Dragon/Tiger](./sprint_15d6_collecte_prospective_dragon_tiger.md) — deux observations officielles planifiées à 17:30 et 08:30 Shanghai, calendrier 2026 vérifié, premier passage réel 64 motifs ; recherche uniquement, PIT non certifié.
- [Sprint 15-D7 — protocole apparié Dragon/Tiger](./sprint_15d7_protocole_appariement_dragon_tiger.md) — pré-enregistrement outcome-blind et garde-fous temporels ; une séance disponible, attente des candidats Oracle OOS 2026, aucun résultat D1/D10 ni entraînement.
- [Sprint 15-D7a — rattrapage canonique CN 2026](./sprint_15d7a_rattrapage_canonique_2026.md) — collecte BaoStock bornée à 2026, promotion insert-only et reprise par 210 lots ; ne crée pas de prédictions prospectives rétroactives.
- [Sprint 15-D8 — export Oracle CN H20 prospectif](./sprint_15d8_export_oracle_prospectif.md) — modèle figé, univers pré-ouverture, cutoff 09:15 Shanghai et export TOP20 outcome-blind de recherche ; collecte quotidienne non encore planifiée.
- [Sprint 15-D9 — journal Oracle CN prospectif quotidien](./sprint_15d9_journal_oracle_prospectif_quotidien.md) — collecte J reprenable, score K après clôture, batch IHM/Windows et notifications, recherche uniquement.
# Journal D7 quotidien : [Sprint 15-D10 — appariement prospectif sans issues](./sprint_15d10_appariement_d7_quotidien.md).
# Cumul D7 : [Sprint 15-D11 — progression outcome-blind vers les gates](./sprint_15d11_cumul_d7_outcome_blind.md).
# Reprise ultérieure : [TODO Oracle CN × Dragon/Tiger D7–D11](./TODO_reprise_oracle_dragon_tiger_D7_D11.md).
# Industrialisation : [Sprint 17-A — audit opérationnel et suites 17-B/C/D](./sprint_17a_audit_exploitation_cn.md).
# Sauvegarde CN : [Sprint 17-B — dump isolé, restauration de preuve et planification](./sprint_17b_sauvegarde_restauration_cn.md).
# Qualité quotidienne CN : [Sprint 17-C — D9 propriétaire unique, audit D6/D9/D10 et gate de sept séances](./sprint_17c_qualite_quotidienne_proprietaire_collecte.md).
# Catalogue des tâches CN : [Sprint 17-D — préparation de la bascule contrôlée, en attente du premier cycle réel](./sprint_17d_preparation_bascule_catalogues.md).
# Exécution : [Sprint 18-A — contrat broker et verrou de marché](./sprint_18a_routage_broker_fail_closed.md) ; US Alpaca inchangé, CN paper/live interdit, shadow CN renvoyé à 18-B.
# Shadow CN : [Sprint 18-B — intentions, tentative hypothétique et rapprochement](./sprint_18b_shadow_execution_cn.md) ; moteur pur sans broker, sans batch ni autorisation live.
# Pilote prospectif : [Sprint 18-C — export Oracle figé et shadow post-clôture](./sprint_18c_pilote_shadow_prospectif.md) ; 12 intentions diagnostiques pour le 8 octobre 2026, contrat de recherche 2026 qualifié et préflight prêt, aucun ordre ni batch planifié.
# Reprise différée : [TODO Sprint 18-C après clôture du 8 octobre](./TODO_sprint_18c_post_cloture_2026_10_08.md) ; collecte canonique, tentative shadow manuelle et marque ultérieure.
# Contrat OMS : [Sprint 18-D — port complet et doubles mock/replay](./sprint_18d_port_oms_et_doubles.md) ; Alpaca US préservé, CN paper/live et doubles simulés refusés par le routeur.
