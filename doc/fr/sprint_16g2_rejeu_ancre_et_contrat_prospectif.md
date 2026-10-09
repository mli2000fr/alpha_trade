# Sprint 16-G2 — Rejeu ancré et contrat prospectif distinct

**État au 8 octobre 2026 : rejeu technique terminé, 233/233 concordants,
zéro anomalie ; contrat prospectif en brouillon, aucun GO serving.**

## But et périmètre

Reconstruire séparément l'état courant des candidats diagnostiques depuis
le **Full officiel ESMA du 26 septembre 2026**, puis chaque Delta du
**27 septembre au 7 octobre inclus**. Comparer les attributs du résultat au
master effectivement connu à l'ouverture du 8 octobre.

Ce travail ne corrige ni les 55 lacunes historiques ni les identités avant
le nouvel ancrage. Il ne modifie ni checkpoint, ni SQL, ni modèle, ni tâches.
Il n'autorise ni serving, ni ordre, ni inférence shadow.

## Implémentation

Service : `service/fr/anchor_replay_16g2.py`.

1. Revalider le rapport de confirmation et son dossier via 16-G1.
2. Vérifier les deux fragments Full, reçus, empreintes et intégrité ZIP/XML.
3. Charger l'index historique jusqu'au 1er octobre et la **version immuable du
   master sélectionné à la décision**, jamais le checkpoint mutable courant.
4. Réunir les Deltas et exiger tous les fragments de chaque date calendaire.
   Absence d'une date != preuve d'absence de changement, y compris le week-end.
5. Vérifier MD5 publié lorsqu'il existe, SHA-256, ZIP/XML, puis parser les
   événements pour les ISIN/MIC cibles. Contrôler les SHA déclarés par le master.
6. Appliquer Full puis Deltas chronologiquement dans une structure en mémoire
   nouvelle. Ne pas utiliser les anciennes versions du master comme état initial.
7. Comparer six attributs : devise nominale, CFI, nom, première date de cotation
   déclarée, terminaison déclarée et début de publication déclaré.

Les dates d'initialisation et fichiers d'origine diffèrent légitimement entre
un Full récent et une chaîne historique : le rapprochement compare les attributs,
pas l'égalité textuelle de leurs versions complètes. Une terminaison, version
finale manquante/ambiguë, anomalie d'événement ou différence d'attribut reste
en réserve. Aucun remplacement par un autre titre après constat du résultat.

**Indépendance limitée :** l'état initial vient d'un autre Full officiel que
celui de la longue chaîne historique, mais le parseur et le moteur d'événements
sont des bibliothèques partagées. C'est une reconstruction séparée, pas une
seconde revue humaine ni une validation par un fournisseur indépendant.

## Run et suivi

```powershell
python -u -m service.fr.anchor_replay_16g2 --confirmation-report artifacts/fr/research/opening_confirmation_16f/opening-remediation-20261008-v1/report.json --anchor-dir artifacts/fr/esma_firds/full_reconciliation_2026 --historical-dir artifacts/fr/esma_firds/replay_2018 --output-dir artifacts/fr/research/anchor_replay_16g2/full0926-to1007-20261008-v1
```

Le run relit **34 archives : 2 Full et 32 Deltas**. Aucun téléchargement.
Le dossier de sortie doit être nouveau. Journal append-only par archive :

```powershell
Get-Content artifacts/fr/research/anchor_replay_16g2/full0926-to1007-20261008-v1/journal.jsonl -Tail 5
Test-Path artifacts/fr/research/anchor_replay_16g2/full0926-to1007-20261008-v1/report.json
Test-Path artifacts/fr/research/anchor_replay_16g2/full0926-to1007-20261008-v1/failure.json
```

Le rapport final contient les preuves, anomalies, comparaisons par titre,
compteurs et un contrat prospectif brouillon. Un échec conserve le journal
et produit `failure.json`. Pas de réutilisation silencieuse d'un dossier existant.

## Contrat proposé, non activé

`config/research_fr/prospective_anchor_16g2_draft.json` est un **brouillon**,
pas une configuration chargée par le serving. Aucun code existant ne change
de politique via ce fichier.

Le contrat distingue trois temps : date du Full / validité de référence,
réception réelle des preuves et achèvement réel de qualification. Une archive
nommée « 26 septembre » ne rend pas le nouveau contrat connu ce jour-là.
La disponibilité opérationnelle future doit être au moins le maximum des
horodatages réellement observés et du terme de la qualification.

Le booléen historique existant reste false. Le périmètre prospectif ne peut
commencer que depuis l'ancrage qualifié, avec chaîne quotidienne contrôlée.
Si l'on exige 21 séances de features entièrement postérieures au Full :

- première séance de la fenêtre : 28 septembre ;
- 21e séance XPAR : **26 octobre** ;
- première ouverture théorique suivante : **27 octobre 2026 à l'ouverture XPAR**.

Ce n'est **ni une date de GO promise ni une obligation d'attendre sans travailler**.
Les revues, qualifications d'événements/devise et parité modèle peuvent avancer
avant. Une preuve distincte couvrant une fenêtre antérieure pourrait changer
cette borne, mais pas une imputation ou un changement silencieux de protocole.
La date retenue devra aussi respecter la fraîcheur du master et la qualification
effective achevée avant la décision.

La fenêtre d'observation shadow et la maturité des labels restent à figer
avant son lancement ; H5 n'autorise pas à évaluer le lendemain. Ni réentraînement
ni recherche de seuil sur les résultats observés n'est autorisé par ce brouillon.

## Conditions de sortie

- Rejeu complet et intègre ; chaque divergence/anomalie examinée.
- Concordance des identités cibles et revue indépendante de l'ancrage.
- Identités sur toute la fenêtre de features, actions et devises qualifiées.
- Parité features/transforms/modèle, revue de release et réserves Sprint 15.
- Protocole prospectif approuvé, sans ordre et avec disponibilité réelle.

Une concordance de 233/233 à la date finale ne démontrerait pas à elle seule
la validité de chaque journée ni la négociabilité. Elle ne clôturerait pas
le Sprint 16 complet.

## Résultat du run réel

Terminé le **8 octobre 2026 à 19:27:29 Paris**. Rapport :
`artifacts/fr/research/anchor_replay_16g2/full0926-to1007-20261008-v1/report.json`.

| Mesure | Résultat |
|---|---:|
| Archives relues et vérifiées | 34 |
| Full / Deltas | 2 / 32 |
| Archives avec checksum MD5 officiel vérifié | 34 / 34 |
| Journées de publication Delta manquantes sur le nouvel intervalle | 0 |
| Candidats comparés | 233 |
| Attributs concordants avec le master connu à la décision | **233 / 233** |
| Divergences / anomalies du rejeu | **0 / 0** |
| Enregistrements Full cibles | 233 |
| Événements Delta pour ces ISIN/MIC pendant cet intervalle | 0 |
| Lacunes historiques héritées, conservées | 55 |
| Titres autorisés au serving par ce travail | 0 |

Le zéro événement Delta ne résulte pas d'archives ignorées : les 32 fragments
ont été lus et leurs publications vérifiées. Il signifie qu'aucun événement
cible n'a été trouvé dans **ce flux et ce périmètre**. Il ne signifie ni zéro
événement d'entreprise ni absence de suspension ou de difficulté de négociation.

Statut exact : `ANCHORED_REFERENCE_MATCHED_NOT_RELEASED`.
`post_full_chain_technically_complete` est true pour ce nouvel intervalle ;
`historical_continuity_confirmed` reste false. Le champ `qualified_at` désigne
la fin de la vérification technique, **pas une approbation de release**.
Cette nouvelle preuve n'était pas qualifiée à l'ouverture du 8 octobre :
elle ne réécrit donc pas le résultat bloqué de la confirmation 16-F.

**69 tests ciblés passent**, dont 11 pour le rejeu 16-G2 : chaîne complète,
publication ou fragment manquant, empreinte altérée, différence sémantique,
événement sans antécédent, doublon du master, terminaison, et brouillon désactivé.
Compilation et contrôle du diff passent également. Aucun accès réseau,
entraînement, inférence, ordre ou écriture SQL pendant le run.

## Suite concrète — 16-G3

Préparer la revue de libération du nouvel ancrage : faire vérifier les preuves
et le périmètre ISIN/MIC, fixer une disponibilité opérationnelle réelle,
qualifier les actions/devises et spécifier l'adaptateur **distinct** capable
de consommer cet ancrage sans modifier le booléen de l'historique.
Traiter les réserves opérationnelles Sprint 15 en parallèle, sans dépendre
d'une attente passive jusqu'au 27 octobre. Aucun entraînement supplémentaire
n'est justifié par la seule concordance du référentiel.

Mise à jour : le [dossier de revue 16-G3](sprint_16g3_revue_liberation_actions_devises.md)
est produit. La revue indépendante et la libération ne sont pas acquises ;
les déclarations fournisseur d'actions et EUR nominal restent distinguées
des preuves indépendantes nécessaires. Aucun adaptateur actif n'a été basculé.
