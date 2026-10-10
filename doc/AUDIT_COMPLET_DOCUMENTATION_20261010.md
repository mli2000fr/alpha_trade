# Révision du corpus documentaire — 10 octobre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Archive conservée pour traçabilité : les commandes, paramètres et promotions ci-dessous décrivent leur époque, pas une consigne actuelle. Ne pas réactiver un batch sur la base de ce texte. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Résultat et périmètre

La révision couvre l'ensemble de `doc` : 665 Markdown au départ, plus les
CSV/TXT/JSON/YML annexes. Aucun fichier documentaire n'est laissé hors du
registre. Les guides courants, comptes rendus de recherche, plans et archives
sont distingués explicitement, sans changer les chiffres des expériences.

Les références API sont régénérées depuis les déclarations Python des packages
métier, services, IHM, outils et trois arbres Alembic, ainsi que les points
d'entrée racine. La liste exacte, les signatures/lignes et les SHA-256 sont
dans [l'inventaire machine](audit/inventaire_sources.json) et le
[décompte par package](reference/modules_generes.md).

Le bilan antérieur [ciblé](AUDIT_MISE_A_JOUR_20261010.md) conserve ses chiffres
historiques ; il ne décrit plus le périmètre de cette révision élargie.

## Corrections de fond issues des sources

- Collectes : plus de consigne d'activation du consensus Yahoo, FINRA ou FRED
  bloqués ; `pit_data_quality_daily` retiré, pas à réactiver temporairement.
  Catalogue actuel distinct des handlers et tables historiques.
- Ouverture US : Alpaca **IEX**, pas SIP ; volume non consolidé. Options et
  ouverture collectent l'univers stable, sans dépendre d'un TOP20 quotidien.
- SEC : lookback configuré de sept jours ouvrés, annexes EX-99 séparées et
  plafonnées ; collecte/normalisation/qualification ML distinctes.
- Pipeline : `us_pipeline` paramétrable 1–14, sélection du vendredi,
  PAPER/account, watcher avant 12, corporate actions 13/14, date US figée.
- EODHD : clôture réelle + délai de publication pris en compte ; gate J
  exigeant cours canoniques, 95 % de l'univers et benchmark ; J−1 n'est pas
  un succès. Échec et compteurs d'import conservés.
- Oracle-only/GPT : date de séance commune, refus des fenêtres inéligibles
  avant les appels et échec explicite pour zéro prédiction ; horizon de
  l'artefact, recherche shadow séparée, amplitude différente de direction.
- Labels Oracle : calendrier NYSE, vraies barres aux deux extrémités sans
  target ffill, quarantaine des rendements suspects, motifs et sources ;
  population historique conservée pour réparation. Ce builder ne calcule pas MFE/MAE.
- Dataset Oracle : segmentation des discontinuités, scope avant rangs XS,
  aliases dédupliqués, whitelist stricte et exclusion des targets non qualifiées.
- Configuration : priorité exacte des overrides racine/env ; valeurs YAML
  locales différentes des defaults Python ; aucun secret dans les inventaires.
- Bases : migrations US/CN/FR séparées ; DDL versionné ≠ schéma déployé.
  Staging FR ≠ promotion canonique ; CN bloqué ≠ chaîne quotidienne validée.
- Sauvegardes, horaires, droits/prudence, protections et simulations FR :
  guides d'exploitation rapprochés des propriétaires actuels et de leurs
  restrictions ; pas de validation broker nouvellement revendiquée.

## Réorganisation et préservation

Les consignes opérationnelles communes convergent vers les guides propriétaires
et le catalogue courant, pas vers des copies de comptes rendus de sprints.
L'index est maintenant organisé par domaines US/ML, CN, FR, opérations,
contrats et archives. Un registre couvre aussi les fichiers non Markdown.
Les anciennes références déplacées sont réparées ; les preuves absentes
restent identifiées comme telles, sans lien trompeur ni résultat inventé.
La note FR `todo_etape.txt` devenue obsolète est retirée : les README/TODO FR
actuels la remplacent. Les autres résultats historiques sont conservés.
Le fichier vide `experiences/campagnes_global_ranking/global_per_symbol_test/test_global_per_symbol.md`
est également supprimé ; il ne contenait aucun résultat. Ces retraits sont
récupérables dans Git.

Nouvelles références automatiques : [configurations](reference/configuration_generee.md),
[batchs déclarés](reference/batchs_generes.md), [navigation](reference/navigation_generee.md),
[schémas/migrations](reference/schema_et_migrations_generes.md) et
[modules](reference/modules_generes.md).

## Vérification et limites explicites

- 1 137 modules Python analysés, 9 204 déclarations, aucune erreur AST.
- 31 tests documentaires réussis : générateur, liens IHM, encodage, maintien
  des chiffres historiques, absence de valeurs secrètes et idempotence.
  Les actifs JSON/YML de monitoring sont parsés et leurs métriques rapprochées
  de l'exporteur ; pas de validation runtime PromQL/Grafana revendiquée.
- Chaque fichier présent est recensé dans le registre ; les liens locaux
  sont contrôlés sur le corpus final. Le rapport machine donne le décompte exact.

Le [contrôle de liens](audit/controle_liens.json) porte sur l'existence des
cibles locales ; il ne teste ni URLs distantes ni ancres. Les erreurs de
parsing AST sont recensées dans l'inventaire. L'index est vérifié contre les
fichiers présents, et la génération est contrôlée pour être reproductible
sans modifications au passage suivant. Les tests du générateur ne remplacent
pas les tests métier ni une nouvelle revue juridique.

Il s'agit d'un audit documentaire **statique** : pas d'appel fournisseur,
d'entraînement, de modification de modèle/config métier, d'écriture SQL,
de changement de tâche ou d'ordre broker. Aucun état opérationnel actuel en
base/Windows n'a été revalidé ici. Les durées/chiffres datés dans les anciens
audits gardent leur date de mesure.

Tous les fichiers sont traités structurellement ; cela ne veut pas dire que
chaque phrase des centaines de rapports historiques a été revalidée, ni que
tous leurs runs ont été reproduits. Les protocoles et résultats datés restent
des preuves de recherche, pas des consignes actuelles.

Entretien : [procédure et sources de vérité](MAINTENANCE_DOCUMENTAIRE.md).
