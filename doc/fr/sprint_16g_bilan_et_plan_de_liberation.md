# Sprint 16-G — Bilan du 8 octobre et plan de libération

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Statut

**Statut final : infrastructure livrée, validation shadow bloquée par les données.**
Clôture administrative avec réserves, décidée après la dernière qualification
bornée du 8 octobre : [bilan de clôture faisant foi](sprint_16_cloture_bornee.md).
Le reste du document conserve la chronologie ; ses anciennes étapes de reprise
ne constituent plus des travaux automatiquement engagés. Aucun GO shadow/live.
Ce bilan ne modifie ni modèle, ni configuration de sécurité, ni base SQL,
ni tâche planifiée. Les contrôles restent bloquants.

Source : `artifacts/fr/research/opening_confirmation_16f/opening-remediation-20261008-v1/report.json`.
Protocole : `config/research_fr/opening_confirmation_16f_remediation.json`.

## Résultat confirmé

La décision reste fixée au **8 octobre 2026, 09:00 Europe/Paris**.
L'audit effectué à **18:53:43 Paris** n'utilise que les versions archivées
observées/disponibles avant cette coupure. Il s'agit d'un audit tardif de
disponibilité, pas d'une prédiction ni d'un ordre exécuté à 09:00.

| Mesure | Résultat |
|---|---:|
| Identités du manifeste | 330 |
| Features numériques calculables | 244 |
| Features calculables avec pour seul motif local la continuité du master | 233 |
| Titres ayant au moins un autre obstacle local | 97 |
| Lignes candidates assemblées | 0 |
| Erreurs d'intégrité barres/actions/master | 0 |
| Pièces archivées et revues connues à la décision | 7 sur 8 |
| Serving / ordres / écritures SQL | interdits |

Les 233 ne sont ni un univers négociable certifié ni des signaux Oracle.
Ils n'ont franchi ni les réserves indépendantes de release ni une inférence.
Le motif de preflight `INSUFFICIENT_CROSS_SECTION` découle des zéro lignes
assemblées : ce n'est pas la preuve que l'univers manque intrinsèquement de titres.

## Problème de fraîcheur résolu, continuité historique non résolue

Le master sélectionné couvre le **7 octobre**, a été réellement observé le
**8 octobre à 07:01:17 Paris**, et n'a aucune anomalie déclarée. Son âge à
09:00 est de 1,98 heure ; retard de couverture : zéro séance.

Ses deux attestations sont distinctes :

- `delta_publication_continuity_confirmed: true` : la chaîne quotidienne concernée passe.
- `historical_continuity_confirmed: false` : la continuité historique n'est pas certifiée.

Ne pas confondre réception du master courant, présence de fragments quotidiens,
réconciliation d'un Full et preuve de continuité de tous les intervalles historiques.
La première est résolue pour cette décision ; les autres preuves ne sont pas
remplacées automatiquement. Aucun besoin de relancer la même confirmation pour
réparer un prétendu lancement trop tardif.

## Blocages et action attendue

Les compteurs par motif sont **non exclusifs**.

| Blocage | Titres | Action et critère de sortie |
|---|---:|---|
| Continuité historique master | 330 | Identifier les intervalles affectés par les publications manquantes ; preuve indépendante ou reconstruction/réconciliation documentée. Aucun passage manuel du booléen à true. |
| Volume nul incompatible avec le profil | 47 | Vérifier séance, cotation et source ; correction seulement avec preuve. Sinon exclusion datée de l'éligibilité, sans effacer le titre de l'historique. |
| Fenêtre de 21 séances incomplète | 39 | Distinguer radiation/suspension/absence fournisseur ; reprise ciblée si les barres existent. Jamais d'imputation pour franchir ce gate. |
| Couverture dividendes incomplète | 36 | Comparer collecte prévue et identité ; les titres hors périmètre actuel ne sont pas automatiquement des pannes. Réponse vide != preuve indépendante d'absence d'événement. |
| Couverture splits incomplète | 36 | Même démarche, avec qualification des ratios et dates si événement. |
| Identité terminée ou réservée | 30 | Conserver les exclusions datées ; ne pas réactiver un titre sur son seul ticker. |
| Dividende dans la fenêtre non qualifié | 10 | Vérifier détachement, montant, devise/modalités et effet sur les features figées ; pièce archivée puis transformation testée. |
| Devise nominale non EUR | 6 | Prouver la devise de cotation avec intervalle effectif ; ne pas assimiler devise nominale et devise de transaction. |

La pièce `GLE_TERMS` n'est pas validée/connue à cette décision. Les sept autres
pièces revues n'autorisent pas automatiquement un ajustement de cours ou un
intervalle de devise : `action_adjustment_qualified` et
`historical_currency_interval_qualified` restent false dans le diagnostic.

## Ce qui peut avancer localement

1. Conserver ce rapport immuable et comparer les prochaines ouvertures dans de
   nouveaux dossiers/protocoles, avec leurs véritables heures de disponibilité.
2. Préparer une liste **diagnostique** des 233 titres et les preuves requises
   titre par titre ; aucune promotion collective basée sur ce seul nombre.
3. Auditer les cas locaux restants par priorité : identités réellement actives,
   barres de la fenêtre, événements, devises. Une exclusion justifiée réduit
   le périmètre, elle ne qualifie pas le référentiel restant par elle-même.
4. Écrire les tests du traitement d'événements et de l'éligibilité avant toute
   évolution du contrat de release.

## Ce qui exige une nouvelle preuve ou une décision de protocole

- La continuité historique ne peut pas être résolue par une relance à une autre heure.
- Une alternative prospective à étudier serait un nouveau point d'ancrage
  officiel courant, vérifié et versionné, puis une continuité observée à partir
  de cet ancrage. Cela **ne certifierait pas rétroactivement** l'historique.
  Ce serait un contrat de recherche distinct à spécifier et valider, pas un
  assouplissement silencieux de `master_at`.
- Les qualifications indépendantes du master/actions, la revue modèle et les
  réserves Sprint 15 nécessitent des preuves explicites. L'outil actuel est
  volontairement diagnostic-only : même un meilleur taux de couverture ne
  constitue pas une implémentation complète de serving.

## Ordre de reprise recommandé

**16-G1 :** dossier de qualification du sous-ensemble diagnostic, avec provenance,
intervalles d'identité et matrice de réserves. Examiner en priorité si un ancrage
courant officiel permet un futur protocole prospectif sans réécrire l'historique.

**16-G2 :** qualifier ce contrat et les événements/devise des titres retenus ;
résoudre ou exclure explicitement les cas incompatibles. Tout changement de
périmètre/protocole doit précéder l'évaluation et être archivé.

**16-H :** seulement après les gates de libération, implémenter puis exécuter
une vraie inférence shadow, sans ordres, avec contrat modèle/features et journal
des rejets. Attendre la maturité des labels et la fenêtre prospective fixée
avant de déclarer le Sprint 16 complet.

**Sprint 17 :** reste conditionné au choix d'un courtier/API France ; ce choix
n'est pas nécessaire pour poursuivre les qualifications ou le shadow sans ordres.

## Vérification technique

Le 8 octobre, **46 tests ciblés passent** : confirmation/remédiation 16-F,
adaptateur quotidien 16-B, référence observée 16-D, qualification/preuves 16-E
et qualification bootstrap 16-C. Ce résultat prouve les contrôles testés,
pas la qualité indépendante des données ni la rentabilité du modèle.

## 16-G1 exécuté — dossier de qualification et inventaire d'ancrage

Outil reproductible : `service/fr/qualification_dossier_16g.py`.
Il ne lit que les archives locales, refuse un rapport hors FR, futur, avec
cutoff incohérent, doublons ou erreurs d'intégrité, et vérifie les empreintes
du master. Il n'appelle aucun fournisseur, modèle, SQL ni courtier.

Dossier complet généré :
`artifacts/fr/research/qualification_dossier_16g/opening-anchor-20261008-v1/report.json`.
La matrice couvre les **330 titres**, avec ISIN/MIC, devise nominale, calculabilité,
motifs locaux, séances absentes, pièces émetteur et réserves globales.
`local_candidates.json` énumère les **233** titres passant les contrôles locaux
hors continuité. Ce fichier JSON est diagnostique, **pas un nouvel univers tradable**.
Chaque ligne reste `servable: false` et `identity_independently_qualified: false`.

### Contrôle du Full officiel déjà archivé

Source : `artifacts/fr/esma_firds/full_reconciliation_2026`.
Full du **26 septembre 2026**, deux fragments `FULINS_E`, index et reçu de
téléchargement présents. ZIP/XML, MD5 officiels et SHA-256 du reçu vérifiés
à nouveau. Les enregistrements du Full ont été relus pour les ISIN/MIC cibles,
pas seulement les compteurs d'une ancienne réconciliation.

| Contrôle | Résultat |
|---|---:|
| Couples du manifeste présents une seule fois dans le Full | 300 / 330 |
| Couples des candidats diagnostiques présents une seule fois | **233 / 233** |
| Candidats diagnostiques absents ou dupliqués dans le Full | 0 |
| Candidats diagnostiques avec date de terminaison non sentinelle déclarée | 0 |

L'ancienne réconciliation `full_reconciliation_2026_observed_v2.json` indique
345 enregistrements cibles actifs et zéro divergence. Ce compteur porte sur
les **couples** de sa population, pas sur 345 symboles de ce dossier.
Il ne faut pas le confondre avec les 300 couples du MIC sélectionné ici.

L'index historique contient également les 14 archives Delta du 27 septembre
au 1er octobre, toutes présentes sur disque. Le checkpoint quotidien contient
18 archives ultérieures. **Cette présence n'est pas encore un rejeu indépendant
de la chaîne ancrée** : numérotation, checksums, événements et état final doivent
être vérifiés ensemble avant de qualifier un nouvel ancrage.

Les 55 dates historiques manquantes ne sont ni supprimées ni déclarées résolues.
Le Full du 26 septembre est au milieu de la fenêtre de features actuelle,
qui commence le 9 septembre : il ne prouve pas à lui seul les identités sur
toute cette fenêtre. Aucune disponibilité PIT n'est déduite du nom des fichiers
ou de leurs dates de modification. Un éventuel contrat prospectif devra fixer
un horodatage de qualification réel et conserver ce distinguo.

### Reproduction

```powershell
python -u -m service.fr.qualification_dossier_16g --confirmation-report artifacts/fr/research/opening_confirmation_16f/opening-remediation-20261008-v1/report.json --anchor-dir artifacts/fr/esma_firds/full_reconciliation_2026 --output-dir artifacts/fr/research/qualification_dossier_16g/nouvelle-revue
```

Le dossier de sortie doit être nouveau ; les rapports et revues existants ne
sont jamais écrasés. Le reçu et l'index du Full sont identifiés par empreinte.

**58 tests ciblés passent**, dont 12 nouveaux cas du dossier : séparation
qualification locale/globale, garde FR/PIT, populations et identités, archives
altérées, fragments Full incomplets et absence de promotion automatique.

**Suite 16-G2 :** vérifier/rejouer séparément la chaîne Full du 26 septembre
→ Delta jusqu'au master courant, comparer les identités des 233 titres et
préparer le contrat prospectif avec qualification réelle. Cela n'autorise
ni à passer le booléen historique à true ni à déclarer le Sprint 16 terminé.

**16-G2 engagé après GO :** [rejeu ancré et contrat prospectif distinct](sprint_16g2_rejeu_ancre_et_contrat_prospectif.md).
Le brouillon `config/research_fr/prospective_anchor_16g2_draft.json` garde tous
les droits de serving/ordre/SQL à false et n'est pas chargé par les services actifs.

**Résultat final 16-G2 :** 34 archives contrôlées, 233/233 candidats concordants,
zéro divergence et zéro anomalie. Le rejeu est terminé techniquement ; la revue
de libération et le contrat prospectif restent à qualifier en 16-G3. Le bilan
bloqué à l'ouverture du 8 octobre n'est pas réécrit après cette nouvelle preuve.

## Complément 16-G du 8 octobre — preuve ponctuelle MiFIR

Le [POC MiFIR actions](sprint_16g_preuve_devise_mifir.md) observe EUR sur XPAR
le 7 octobre pour AIR, OR et SAN. Réception le 8 octobre à 22:22 Paris : le
dossier de l'ouverture n'est pas réparé rétroactivement. La devise sur tout
l'intervalle, les opérations sur titres et les autres réserves restent à
qualifier. Aucun serving, élargissement ni batch activé. 200 tests ciblés passent.
