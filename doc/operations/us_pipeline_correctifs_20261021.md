# US Pipeline — statuts, qualification SIP et import de séance

## État après intervention

Les correctifs techniques sont livrés ; **la couverture de cours du 20 octobre
2026 reste insuffisante sur le fichier de 1 790 titres**. Le seuil de 95 % n'a
pas changé, ni l'univers, ni les horaires, ni les protections d'exécution.
Aucun pipeline complet, appel LLM ou ordre n'a été lancé pendant l'intervention.

Le run nocturne `us_pipeline-20261020223850-60293c80` reste honnêtement `FAILED` :
sa collecte a persisté 9 915 barres, mais seulement **1 648/1 790** titres avaient
une barre SIP qualifiée du 20 octobre, soit **92,067 %**. SPY était présent.
Les 142 absences empêchent le passage aux étapes suivantes. Réexécuter ne
supprime pas ce contrôle et les compteurs historiques ne sont pas réécrits.

## 1. Statut trop long et faux RUNNING corrigés

Le run `us_pipeline-20261021072915-2a214683`, lancé à 09h29 Paris le 21 octobre,
avait décidé de ne pas travailler : séance US du 21 non clôturée. L'enregistrement
de `SKIPPED_SESSION_NOT_CLOSED` dépasse les **24 caractères** de
`pit_collection_runs.status`, et la finalisation était hors du bloc de traitement
des erreurs. Le processus était terminé, mais la ligne restait `RUNNING`.

À présent :

- statut court **`SKIPPED`**, motif exact dans `details_json.skip_reason` ;
- pas d'élargissement de colonne, migration ou troncature arbitraire du motif ;
- un échec de finalisation tente de fermer la ligne en `FAILED`, conserve les
  compteurs acquis et les transmet via `BatchRunError` ; une indisponibilité SQL
  totale ne peut évidemment pas garantir l'écriture de secours ;
- `SKIPPED` n'est pas assimilé à une exécution réussie pour le secours ;
- la sélection de séance n'a pas été modifiée : lancement avant clôture → skip,
  sans repli silencieux sur la veille.

**Une seule ligne historique corrigée** : le faux RUNNING ci-dessus devient
`SKIPPED`, avec fin réelle déduite du journal (07:29:17 UTC), motif, erreur de
persistance initiale et date de réparation conservés. Ce n'est pas une collecte
réussie. Le run nocturne en échec reste inchangé.

Réconciliation ciblée, sans exécuter le workflow :
`scripts/research/us_pipeline_skip_reconcile.py`. Garde sur identifiant, base US,
début exact, statut RUNNING, absence de fin et journal terminal ; préimage et
postimage dans
`artifacts/operations/us_pipeline_remediation/20261021-skip-repair`.
Le script refuse une autre ligne ou une seconde application.

## 2. Absences : contrôle réel en lecture seule

Le dossier
`artifacts/operations/us_pipeline_remediation/20261021-v2`
contient les reçus Alpaca, métadonnées locales et détail des 142 symboles.

| Classement au moment de l'audit Alpaca | Nombre | Barres SIP du 20 octobre retournées |
| --- | ---: | ---: |
| OTC actifs présents dans la liste des actifs | 96 | 0 |
| Absents de la liste d'actifs retournée | 45 | 0 |
| IAC, présent mais inactif/non négociable | 1 | 0 |

Les métadonnées **locales**, elles, marquaient 98 de ces titres OTC, 43 actifs
NYSE/NASDAQ et un inactif. Elles ne sont pas identiques au référentiel retourné
maintenant par Alpaca. L'absence d'une liste ne prouve pas à elle seule une
radiation : changement de symbole, périmètre fournisseur ou identité restent
à qualifier. **Aucun mapping ou retrait automatique n'a été appliqué.**

La requête historique était figée sur la séance, `feed=sip`, `adjustment=split`,
`asof=-`, sans repli IEX ni autre fournisseur. Elle n'a retourné de barre pour
aucun des 142 symboles. Les métadonnées consultées maintenant ne deviennent pas
pour autant une preuve PIT historique. Les anciennes barres locales ne sont pas
utilisées à la place de J.

Le dossier V1 est une tentative interrompue sur erreur de certificats du client
assets standard. V2 utilise la session TLS vérifiée du projet pour cette lecture,
sans désactivation des certificats, et aboutit. Le programme est
`scripts/research/us_pipeline_missing_bars_audit.py`, lecture SQL/API seulement.
Il ne sert pas à produire une nouvelle liste tradable.

## 3. ACVA et isolation des anciennes barres invalides

L'archive fournisseur ACVA sur le 13–20 octobre contient trois barres valides
les 13, 14 et 15, puis une barre du 16 à **volume, nombre de transactions et VWAP
nuls**. Elle ne contient pas de barre du 20. L'ancien convertisseur refusait
toute la transaction du symbole à cause de cette observation ancienne.

Le collecteur de séance isole désormais les anciennes observations invalides,
les signale dans `rejected_history_bars` et garde les autres dates valides.
Le convertisseur strict de B3 n'est pas modifié.

- Une barre **J invalide** bloque toujours le symbole et ne peut pas être
  remplacée par une ligne déjà présente dans la base.
- Une absence à J reste `NO_TARGET_BAR`, même si des barres précédentes valides
  ont été persistées ; **ACVA ne devient donc pas couvert au 20 octobre**.
- Dates dupliquées et horodatages ambigus restent bloquants.
- Droits/quota restent des arrêts globaux, sans repli IEX ; les symboles non
  tentés sont comptés séparément comme `pending_symbols`.
- Les transactions des deux tables restent par symbole ; les compteurs ne
  progressent qu'après commit.

Le replay hors ligne du reçu ACVA produit bien trois dates valides, une
observation ancienne rejetée et **aucune présence à J**. Aucun cours artificiel
ni remplissage en SQL n'a été effectué pendant cette vérification.

Les nouveaux bilans distinguent `symbol_failures` (absence J, erreur d'import,
droits/quota), `symbol_errors`, `rejected_history_bars`, symboles tentés et en
attente. Une absence normale de réponse fournisseur n'est plus confondue avec
une exception technique sans explication.

## 4. Résumé du workflow

Une anomalie d'affichage supplémentaire transformait les champs imbriqués
`target_coverage.coverage_ratio` et `minimum` en compteurs entiers : 0,92067 et
0,95 devenaient tous deux zéro. Cela n'était **pas** la valeur utilisée par le
contrôle bloquant de l'importeur, dont le résumé enfant est resté exact.

Le résumé parent conserve maintenant le dernier snapshot de couverture entier,
avec ratio, seuil, benchmark, date et symboles manquants. Il ne somme pas des
photographies de couverture successives. Les anciens artefacts restent inchangés.

## Tests et décision restante

Les tests ciblés couvrent la largeur SQL réelle (CHECK SQLite), finalisation en
échec, compteurs, transmission PAPER/LLM/watcher existante, couvertures exactes,
seuil 95 %, origine SIP des deux tables, isolation d'une ancienne barre invalide,
refus d'une barre J invalide, doublons, timestamps et arrêt droits/quota.
**210 tests ciblés passent**, sans échec ni test ignoré. Le résultat final de la suite figure dans
`artifacts/tmp/us-pipeline-remediation-20261021-v3.xml`.

**La correction du logiciel ne rend pas le flux SIP disponible pour tous les
titres du fichier.** Pour débloquer cette étape il reste un choix explicite :
qualifier un univers quotidien compatible SIP, ou ajouter une source autorisée
complémentaire pour les titres voulus. Il ne faut ni abaisser le seuil, ni
retirer silencieusement les absents du dénominateur, ni remplacer J par J−1.
Le run complet n'a pas été relancé car les étapes 10–12 peuvent déclencher des
appels LLM et des ordres PAPER.
