# Sprint 15-D7a — rattrapage canonique CN 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Objet et frontière temporelle

Le protocole Dragon/Tiger 15-D7 requiert des candidats Oracle réellement prédits sur des séances 2026. La base `alpha_trade_cn` s'arrêtait au 31 décembre 2025 pour les barres canoniques. Ce rattrapage ajoute les séances closes du 1er janvier au 29 septembre 2026 ; il ne reconstitue ni prédictions prospectives passées, ni horodatages PIT de 2026 antérieurs à la collecte.

Le lot est limité à `alpha_trade_cn`, utilise BaoStock et ne modifie pas les tables US. Les lignes canoniques déjà présentes sont conservées (`INSERT IGNORE`), ainsi que leurs `observed_at`/`available_at`. Pour les nouvelles lignes, la disponibilité tient compte de l'heure de réception réelle du staging : une barre historique téléchargée aujourd'hui n'est donc pas présentée comme connue à sa date économique.

## Couverture et procédure

`dataIntegrityEngine.cn_sprint7c_incremental` expose trois actions :

1. `prepare` récupère le master, le calendrier et les quatre indices, sélectionne les titres actifs ou radiés recouvrant 2026 et construit un manifeste figé.
2. `run-chunk` collecte `daily` et `adj_factor` pour un sous-ensemble, puis promeut et enrichit uniquement les dates demandées. Les autres lignes du staging ne sont pas repromues.
3. `run-all` parcourt les sous-ensembles dans l'ordre, avec verrou exclusif, rapports par lot et `state.json` atomique. Un lot terminé est ignoré à la reprise ; un lot échoué peut être retenté sans écraser les lignes déjà promues.

Campagne figée le 30 septembre 2026 : **5 242 symboles, 210 lots de 25 au maximum**, dates 2026-01-01 à 2026-09-29. Manifeste : `config/univers_cn/canonical_incremental_2026.txt` ; index et listes : `config/univers_cn/sprint7c_chunks_2026/`.

Commande de reprise, depuis `F:\projets` :

```powershell
.\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint7c_incremental run-all --start-date 2026-01-01 --end-date 2026-09-29
```

Le 30 septembre, les 209 lots restant après le premier ont été lancés en arrière-plan. Suivi :

```powershell
$s = Get-Content F:\projets\artifacts\cn\sprint7c_2026\state.json -Raw | ConvertFrom-Json
[pscustomobject]@{Termines=@($s.chunks.PSObject.Properties.Value | Where-Object status -in @('COMPLETED','COMPLETED_WITH_WARNINGS')).Count; EnCours=@($s.chunks.PSObject.Properties.Value | Where-Object status -eq 'RUNNING').Count; Echecs=@($s.chunks.PSObject.Properties.Value | Where-Object status -eq 'FAILED').Count; Total=$s.chunk_count}
Get-Content F:\projets\log\batch\cn-sprint7c-2026\stderr.log -Tail 20
```

### Incident de connexion du lot 117 et reprise

La première campagne s'est interrompue au lot 117 après 116 lots terminés. La connexion TCP à BaoStock avait expiré ; l'impression du message chinois par la bibliothèque sous encodage Windows `cp1252` a ajouté un `UnicodeEncodeError`, masquant la cause réseau. Le runner retente désormais **uniquement la collecte** sur une erreur de transport/connexion BaoStock (5 tentatives, attente croissante), jamais une erreur de données ou de canonicalisation. Une relance avec `PYTHONIOENCODING=utf-8` rend le vrai message fournisseur visible.

Le lot 117 a réussi à la quatrième tentative, sans nouveau téléchargement des lots 1 à 116. Les lots 118 à 210 ont été relancés en arrière-plan ; consulter `log/batch/cn-sprint7c-2026/retry1.stderr.log` et le même `state.json`. Le test de reprise et les tests de distinction entre erreur réseau et erreur de schéma portent la suite ciblée à **36 tests réussis**. Cet incident n'est pas une anomalie des barres déjà canoniques.

Une fois les 210 lots terminés, auditer la couverture par séance et par marché, les absences, doublons, rejets, statuts/limites et facteurs. Ne pas ouvrir le serving Oracle CN sur la seule base d'un succès de collecte. Il faut encore produire les features 2026, prédire sur des dates postérieures à la disponibilité des données, et respecter le protocole de validation 15-D7. Le journal Dragon/Tiger du 29 septembre ne devient pas rétroactivement un échantillon apparié au moment de décision du 30 septembre.

## Contrôles effectués avant la campagne longue

- Pilote deux actions (`sh.600519`, `sz.000001`) : 180 séances ouvertes, 1 080 barres nouvelles actions + indices, 3 facteurs ; aucune ligne rejetée.
- Premier lot complet de 25 actions : 4 528 lignes reçues, 0 appel échoué, 5 220 barres promues, 28 facteurs, 0 rejet et aucune barre d'action attendue manquante.
- Empreinte des 2 922 séances antérieures à 2026 identique avant/après le premier lot (`SUM(CRC32(...)) = 6352500472294`). Les empreintes des deux titres historiques pilotes étaient également inchangées après leur promotion.
- 34 tests ciblés de canonicalisation et de reprise réussis avant le lancement des lots restants.

Ces contrôles valident l'exécution incrémentale initiale, pas encore la couverture finale de l'univers ni la qualité prédictive Oracle.

## Résultat final du 30 septembre 2026

La reprise s'est terminée : **210/210 lots `COMPLETED`, 0 avertissement, 0 échec**. Les rapports couvrent 5 242 actions, 940 207 lignes reçues, aucun appel en échec et aucune ligne rejetée. Les 1 734 appels vides incluent notamment les facteurs absents ; aucun des 210 rapports ne signale un symbole entièrement sans barre d'action.

Dans `alpha_trade_cn`, le contrôle en lecture seule constate 180 séances ouvertes et 92 jours fermés entre le 1er janvier et le 29 septembre 2026. Les barres canoniques 2026 sont au nombre de **936 103 pour 5 242 actions** et **720 pour quatre indices**, du 5 janvier au 29 septembre. Le nombre quotidien total de barres varie de 5 186 à 5 227 ; les écarts au produit « 5 242 × 180 » ne doivent pas être assimilés sans examen à des données perdues (dates de cotation, suspensions et statuts diffèrent). Aucun OHLC incohérent, horodatage `available_at < observed_at`, barre rattachée à une séance fermée ou observation prétendument antérieure à sa date économique n'a été trouvé. L'empreinte des 2 922 séances pré-2026 reste `6352500472294`, identique à celle calculée avant et après le pilote.

Le préflight Oracle 15-D7 a été ajusté : pour une décision avant ouverture en J, il exige les données de la **dernière séance terminée J−1**, et non une barre J encore inexistante. Après correction, le rapport `artifacts/research/cn_dragon_tiger_15d7/oracle-export-readiness-20260930-final.json` n'indique qu'un blocage : `NO_VALID_2026_PROSPECTIVE_ORACLE_CANDIDATE_EXPORT`. Le rattrapage rend possibles les étapes aval de recherche 2026, mais **ne crée pas lui-même les features, un modèle Oracle 2026, ni un export prospectif**. La décision du matin du 30 septembre ne peut plus être revendiquée comme prospective à partir de ces données reçues ensuite.
