# Incident étape 10 — couverture Oracle 0/1790

Diagnostic du 27 octobre 2026, vérifié en base en transaction READ ONLY.
Aucun ordre, appel fournisseur, entraînement, nouvelle prédiction ou écriture
SQL de production réalisé pour ce diagnostic.

## Cause technique corrigée

Modèle : `model-factory-20261016180250-3b0515`, séance signal : 26 octobre 2026.
Les deux tables Oracle contiennent 1 647 scores et 1 647 lignes de traçabilité.
Leurs colonnes `created_at` sont des **TIMESTAMP MySQL**, affichées selon le
fuseau de la session SQL (`SYSTEM`, Paris, UTC+1 ce jour-là).

La requête du filtre comparait cette représentation locale à une borne UTC
naïve. Exemple vérifié : création affichée `2026-10-27 01:17:54` Paris,
soit `2026-10-27 00:17:54 UTC`. Avec un cutoff `00:18:01 UTC`, l'ancienne
requête retournait zéro, la requête corrigée retourne 1 647.

Le lecteur compare maintenant `UNIX_TIMESTAMP(created_at)` à l'instant UTC,
pour **les scores et leur lineage**, et reconstitue l'heure UTC pour l'archive.
Pas de décalage fixe codé en dur, de modification du fuseau serveur, de retrait
du cutoff, ni d'inclusion de données futures. Toutes les signatures de modèle,
de features et les conditions de causalité des 1 647 lignes relues sont valides.

## Second blocage réel — non contourné

- Univers fichier demandé : **1 790 titres**, identique à l'univers du contrat.
- Prédictions : **1 647**, soit **92,01 %**.
- Seuil configuré : **95 %**, conservé.
- **143 titres sans score ont tous zéro barre daily au 26 octobre 2026**.

Cela ne prouve pas que les 143 titres sont radiés ou définitivement non
disponibles. Certaines dernières barres sont anciennes ; d'autres s'arrêtent
aux 15/16/22 octobre. Il faut distinguer un retard rattrapable, une absence de
couverture du fournisseur, un changement d'identité et un titre non actif.
Ne pas prédire J à partir d'un cours ancien, fabriquer une barre, réduire le
dénominateur aux seuls titres réussis ou abaisser le seuil sans décision explicite.

Le correctif technique **ne rend donc pas cette collecte complète**. Sans
rattrapage/qualification ou changement explicite de politique, une relance
restera bloquée à 1 647/1 790 et ne publiera aucune sélection options.

## Exploitation

Une couverture insuffisante produit désormais un résumé FAILED avec les
compteurs et une archive locale `artifacts/options_directional/opt-*/failure.json`
comprenant la liste complète des absents. Cette archive n'autorise aucun ordre
et ne remplace pas un `report.json` scellé. La résolution automatique du dernier
run de même date/modèle/univers/compte/preset ne revient pas à un succès plus ancien.
L'avertissement `triton not found` est distinct de ce blocage.

Tests ciblés : horloges SQL UTC/Paris été-hiver/autre fuseau, exclusions futures,
cutoff avec fuseau explicite, couverture véritablement insuffisante, archive
d'échec et absence de substitution par une ancienne sélection.
