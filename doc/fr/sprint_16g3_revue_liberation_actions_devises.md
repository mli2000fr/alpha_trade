# Sprint 16-G3 — Revue de libération, actions et devises

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

**Statut final : infrastructure livrée, validation shadow bloquée par les données.**
Voir la [clôture bornée du Sprint 16](sprint_16_cloture_bornee.md).
Les mentions de non-clôture ci-dessous décrivent les étapes historiques de revue.

État au 8 octobre 2026 : **dossier technique livré et exécuté ; libération non approuvée**.
Le Sprint 16 complet n'est pas clôturé. Aucun shadow, serving, ordre, entraînement,
inférence ou écriture SQL n'a été activé. Aucune collecte externe supplémentaire
n'a été lancée ; seules les archives locales ont été utilisées.

## Objectif et place dans le flux

16-F confirme les données réellement connues avant l'ouverture du 8 octobre.
16-G1 sépare les blocages locaux de la réserve globale de continuité.
16-G2 reconstruit un nouvel ancrage Full + Delta sans réparer rétroactivement
les lacunes historiques. 16-G3 rassemble les preuves pour une seconde revue,
réexamine les déclarations d'opérations sur titres et distingue explicitement
devise nominale et devise de cotation.

```text
Confirmation 16-F figée à 09:00 Paris
  → 233 candidats passant les contrôles locaux hors continuité
  → rejeu 16-G2 : 233 concordances, 34 archives vérifiées
  → dossier 16-G3 + grille de revue non remplie
  → revue indépendante + qualifications encore requises
  → futur contrat prospectif distinct (pas encore activé)
```

Un dossier préparé automatiquement n'est pas une seconde revue indépendante.
L'acceptation de son enveloppe informatique ne constitue pas une autorisation
de production et ne prouve pas l'identité ou l'indépendance du signataire.

## Résultat exécuté

Rapport de référence :
`artifacts/fr/research/release_review_16g3/anchor-20261008-v2/report.json`.
Grille associée :
`artifacts/fr/research/release_review_16g3/anchor-20261008-v2/independent_review_template.json`.
Le dossier v1 est conservé ; v2 ajoute les chemins explicites des rapports sources.

| Contrôle | Résultat | Portée exacte |
|---|---:|---|
| Candidats diagnostiques | 233 | Pas un univers négociable autorisé |
| Contrôles fournisseur d'actions | 233 / 233 | Fenêtre observée, intégrité et corrections |
| Événements fournisseur effectifs dans cette fenêtre | 0 | Pas une certification indépendante d'absence |
| Actions indépendamment qualifiées | 0 | Réserve conservée |
| Devises de cotation indépendamment qualifiées | 0 | EUR nominal uniquement |
| Séances de features antérieures à l'ancrage, par candidat | 13 | Couverture de fenêtre encore à qualifier |
| Concordances ISIN/MIC issues de 16-G2 | 233 / 233 | Nouvelle chaîne technique uniquement |
| Modèle exécuté / release approuvée | Non / Non | Lineage et empreintes seulement |

La décision auditée reste **8 octobre 2026 à 09:00 Paris (07:00 UTC)**.
Le dossier a été produit après cette décision. Il ne rend pas rétroactivement
utilisable une qualification réalisée après l'ouverture. La qualification
technique du rejeu 16-G2 s'est achevée à 19:27 Paris.

## Implémentation et contrôles

Service : `service/fr/release_review_16g3.py`.

1. Reconstruire le dossier 16-G1 depuis la confirmation figée : marché FR,
   populations, horodatages, empreintes et absence de capacités d'exécution.
2. Vérifier que 16-G2 est lié à la même confirmation et à la même décision,
   sans divergence, anomalie ou capacité serving/ordres/SQL.
3. Comparer populations et couples ISIN/MIC ; refuser les doublons.
4. Recalculer les SHA-256 des archives du rejeu par lecture en blocs. Le dossier
   réutilise le résultat du parsing 16-G2 : ce n'est pas un second parseur
   indépendant et tous les XML ne sont pas relus une nouvelle fois.
5. Relire les observations d'actions opérationnelles et du bootstrap,
   uniquement si observées et disponibles avant l'heure de décision.
6. Appliquer les corrections fournisseur : une réponse plus récente remplace
   les déclarations antérieures dans sa fenêtre. Deux corrections contradictoires
   à disponibilité identique sont refusées. Une réponse incomplète ou un événement
   non qualifié reste visible comme réserve, jamais comme succès implicite.
7. Préparer le manifeste existant, empreintes, features, transformations et
   horizon H5, sans charger/exécuter les modèles sérialisés.
8. Écrire un nouveau dossier isolé, sans écraser un dossier existant.

Chaque ligne expose sources, empreintes, fenêtres, dates d'observation et de
disponibilité, événements effectifs, contrôles locaux, devise nominale,
devise de cotation inconnue et séances pré-ancrage.
`serving_allowed`, `orders_allowed`, `sql_writes` restent false.

### Pourquoi zéro événement ne libère pas les actions

Les snapshots fournisseur couvrent les séances demandées et ne déclarent aucun
dividende/split effectif pour ces candidats dans cette fenêtre. Cela n'assure pas
l'exhaustivité du fournisseur ni toutes les autres opérations possibles
(fusion, échange de titres, changement de livrable, etc.). Les pièces émetteur
déjà qualifiées dans 16-E ne couvrent pas ces 233 candidats. Il manque une
preuve indépendante adéquate pour les intervalles nécessaires, ou une décision
explicite de changement de protocole. Aucun relâchement n'est appliqué ici.

### Pourquoi EUR reste une réserve

Le champ ESMA actuellement parsé est la devise nominale. Le service ne le
rebaptise pas devise de cotation. La preuve attendue doit identifier l'ISIN,
la place/MIC, la devise de négociation et son intervalle de validité, avec source
et disponibilité vérifiables. Une métadonnée actuelle ne prouve pas à elle seule
un intervalle historique. Aucun téléchargement depuis une source bloquée pour
droits/prudence n'est proposé pour combler cette réserve.

## Seconde revue : mode d'emploi

Remettre au relecteur le rapport v2, les rapports sources référencés et leurs
archives locales. Copier la grille sous un nouveau nom pour préserver le modèle
vierge ; ne pas inventer une revue ni remplir automatiquement les cases.

Le relecteur doit examiner :

- `full_fragments_and_official_checksums` : les deux fragments Full du 26 septembre,
  leurs checksums officiels et les empreintes locales ;
- `post_full_delta_coverage` : les 32 fragments Delta et la couverture du nouvel
  intervalle, sans confondre zéro événement cible et archive non lue ;
- `candidate_isin_mic_comparisons` : les 233 couples et la portée sémantique des
  attributs comparés ;
- `no_historical_backdating` : les 55 lacunes héritées et les dates réelles de
  disponibilité/qualification restent inchangées ;
- `remaining_release_reserves_acknowledged` : les réserves ci-dessus et celles
  du Sprint 15 ne sont pas résolues par l'acceptation de l'ancrage.

Renseigner `reviewer`, `reviewed_at` avec fuseau, `independence_declared`, les
réserves et, seulement si justifié, la décision
`ACCEPT_ANCHOR_FOR_PROSPECTIVE_CONTRACT_ONLY`. Le SHA-256 doit rester celui du
rapport effectivement relu ; sa modification exige une nouvelle revue.

La fonction `validate_review` refuse mauvaise empreinte, autre marché, checklist
incomplète, date future ou sans fuseau et activation serving/ordres. L'appelant
peut fournir `packet_created_at` pour refuser aussi une revue antérieure au dossier.
Le résultat reste `ATTESTATION_ENVELOPE_VALID_NOT_RELEASE`. **Aucun import
automatique de la grille ni bascule de configuration active n'est implémenté.**

## Futur adaptateur ancré — spécification, pas activation

Le consommateur devra être distinct de la chaîne historique actuelle :

1. charger ancrage, chaîne, empreintes et décision de revue ;
2. calculer la disponibilité effective au plus tôt après les qualifications
   requises, jamais simplement à la date inscrite dans le Full ;
3. résoudre chaque séance de la fenêtre de features, pas seulement la dernière ;
4. exiger les preuves actions/devises correspondant à ces intervalles ;
5. refuser les ambiguïtés et conserver `historical_continuity_confirmed:false` ;
6. vérifier parité features/transforms/modèle et protocole shadow approuvé avant
   de rendre une inférence possible, sans ordre par défaut.

La fenêtre actuelle de 21 séances va du 9 septembre au 7 octobre : 13 séances
précèdent le Full du 26 septembre. Un ancrage seul ne les qualifie pas. Avec
uniquement le nouvel intervalle, la fenêtre 28 septembre–26 octobre pourrait
être utilisée au plus tôt à l'ouverture du **27 octobre**, sous toutes les autres
conditions. Ce n'est ni un GO ni une obligation d'attendre sans agir : une preuve
antérieure adéquate pourrait couvrir les séances manquantes.

## Reproduction et tests

Pour produire un autre dossier, choisir un **nouveau** répertoire de sortie :

```powershell
python -u -m service.fr.release_review_16g3 --confirmation-report artifacts/fr/research/opening_confirmation_16f/opening-remediation-20261008-v1/report.json --replay-report artifacts/fr/research/anchor_replay_16g2/full0926-to1007-20261008-v1/report.json --output-dir artifacts/fr/research/release_review_16g3/nouvelle-revue
```

**97 tests ciblés passent**, dont 24 nouveaux tests 16-G3 : corrections fournisseur,
couverture incomplète, événements réservés, ambiguïtés, enveloppes invalides,
intégrité/populations/identités, erreurs d'archives et interdictions d'exécution.
Ce n'est pas toute la suite de l'application ni une revue humaine indépendante.

## Prochaine décision nécessaire

### Demande de contre-revue par le même assistant

Le 8 octobre, l'utilisateur a demandé que l'assistant effectue lui-même une
seconde lecture « comme une deuxième personne ». Cette demande autorise une
**contre-revue technique distincte**, pas une fausse attribution à un autre
relecteur. Elle est enregistrée sous
`SAME_ASSISTANT_TECHNICAL_COUNTER_REVIEW`, avec `independence_declared:false`.
Elle ne remplit pas la grille `INDEPENDENT_HUMAN_ATTESTATION` et n'active rien.

Service : `service/fr/technical_counter_review_16g.py`.
Le contrôle lit les XML avec SAX, séparément du lecteur ElementTree utilisé
pour le premier rejeu. Il vérifie les jours et numéros de fragments, les
empreintes MD5 publiées enregistrées dans le rejeu, les couples cibles, les
attributs du Full et la présence éventuelle d'événements Delta cibles.
Les empreintes MD5 sont confrontées aux valeurs archivées, sans nouvelle
consultation de l'index officiel. Il utilise les mêmes sources : il ne fournit
pas une confirmation par un second fournisseur.

Pour ce contre-contrôle, un événement Delta cible entraîne une réserve : ce
lecteur ne réutilise pas l'application d'événements du premier moteur pour
prétendre à une vérification distincte du même résultat. Les preuves actions,
devises et séances pré-ancrage restent des questions séparées.

Ce travail permet de poursuivre les contrôles techniques sans faire patienter
l'utilisateur pour une seconde personne. Toute promotion opérationnelle reste
soumise à une décision explicite sur le protocole et aux preuves nécessaires ;
l'assistant ne s'attribue pas une indépendance humaine ni une compétence de
certification externe.

### Contrôle de remise exécutable — suite du 8 octobre

Service ajouté : `service/fr/release_review_check_16g.py`.
Résultat réel :
`artifacts/fr/research/release_review_16g3/handoff-check-20261008-v1/report.json`.

**3 606 fichiers distincts ont été revérifiés par SHA-256** : rapports sources,
preuves du modèle (sans désérialisation), archives d'actions et archives du rejeu.
Ce nombre est celui des fichiers distincts contrôlés, pas des titres ou des
événements d'entreprise. Aucun écart d'empreinte détecté.

Le contrôle distingue :

- `MISSING` : aucune grille fournie ;
- `PENDING_NOT_ATTESTED` : grille liée au bon rapport, toujours en attente ;
- `ATTESTATION_ENVELOPE_VALID_NOT_RELEASE` : enveloppe déclarative correctement
  remplie, sans certification automatique du signataire ni approbation de release ;
- erreur bloquante : empreinte, population, horodatage, périmètre ou revue invalide.

La grille vierge réelle retourne **`PENDING_NOT_ATTESTED`**. Le statut global
est `HANDOFF_VERIFIED_NOT_RELEASED`. Les listes nominatives de réserves contiennent
233 titres pour les preuves pré-ancrage, 233 pour la devise de cotation et 233 pour
les actions indépendantes. Même une attestation valide ne supprime aucune de ces
réserves et ne change pas les booléens actifs de l'application.

Pour vérifier une future grille remplie, remplacer `--review` par son chemin
dans `artifacts/fr` et choisir un nouveau dossier de sortie :

```powershell
python -u -m service.fr.release_review_check_16g --packet artifacts/fr/research/release_review_16g3/anchor-20261008-v2/report.json --review artifacts/fr/research/release_review_16g3/anchor-20261008-v2/independent_review_template.json --output-dir artifacts/fr/research/release_review_16g3/nouveau-controle
```

Le contrôle vérifie systématiquement que la date d'une attestation acceptée
est postérieure à la création du dossier. Il n'exécute aucun modèle, aucun accès
réseau et aucune écriture SQL. Ses écritures sont limitées à un nouveau rapport
de recherche. Le code de sortie zéro signifie **contrôle diagnostique exécuté**,
pas « autorisé en production » : lire `review_status` et les réserves.

**106 tests ciblés passent**, dont 9 nouveaux tests de remise : revue absente,
grille vierge, attestation valide restant non libératoire, dossier modifié,
empreintes, revue antidatée, fichier modèle altéré, chemin hors périmètre et
population incohérente. Ils remplacent le bilan précédent de 97 pour cette suite
élargie ; ils ne représentent pas tous les tests de l'application.

### Résultat final de la contre-revue technique

Run terminé le **8 octobre 2026 à 19:58:01 Paris** :
`artifacts/fr/research/release_review_16g3/technical-counter-review-20261008-v1/report.json`.
Statut : `TECHNICAL_COUNTER_REVIEW_PASSED_WITH_RESERVES`.

| Vérification de seconde passe | Résultat |
|---|---:|
| Archives entièrement relues avec SAX | 34 / 34 |
| Enregistrements XML parcourus, toutes populations confondues | 12 232 565 |
| Enregistrements Full correspondant aux couples candidats | 233 |
| Couples candidats absents ou dupliqués | 0 |
| Différences d'attributs face au master figé | 0 |
| Événements Delta correspondant aux couples candidats | 0 |
| Fichiers de preuve revérifiés par le contrôle de remise | 3 606 |
| Empreinte du dossier relu encore concordante | Oui |

Le compte de 12 232 565 est celui des enregistrements XML parcourus, pas de
titres distincts ni d'événements propres à l'univers candidat. Le résultat
confirme la lecture technique de l'ancrage et l'absence de modification cible
dans les Delta examinés. Il ne prouve pas l'absence d'opérations sur titres.

La seconde passe demandée à l'assistant est **terminée** ; il n'est pas nécessaire
de relancer ce même audit ni d'attendre un relecteur humain pour poursuivre les
travaux techniques autorisés. Elle ne remplit pas le champ historique
`INDEPENDENT_ANCHOR_REVIEW` de l'ancien protocole : les rapports figés et leurs
réserves sont conservés, sans les réécrire comme une attestation humaine.
La suite utile porte sur les preuves manquantes et non sur une troisième passe
des mêmes ZIP : actions/devises, couverture de toute la fenêtre de features,
parité features/modèle et réserves opérationnelles Sprint 15. Une éventuelle
libération devra expliciter le protocole de revue retenu au lieu de supposer
une indépendance que ce travail n'a pas.

**114 tests ciblés passent**, dont 8 tests du lecteur et de ses garde-fous :
extraction des couples exacts, distinction devise nominale/cotation, Delta cible,
jours et fragments manquants, doublons, dates incohérentes et impossibilité
d'utiliser cette contre-revue comme attestation humaine indépendante.
Aucun nouvel entraînement, aucune activation et aucune écriture SQL.

Suite exécutée : [parité arithmétique et fenêtre d'identité](sprint_16g_parite_features_et_fenetre.md).
Suite documentaire : [pilote AIR/OR/SAN, devises et opérations](sprint_16g_pilote_devises_actions.md).
Les 233 candidats passent les 14 comparaisons brutes et transformées. Les
réserves d'actions/devises et de fenêtre pré-ancrage ne sont pas levées par ce
succès. La suite ciblée élargie compte 146 tests passants.

Références : [bilan 16-G](sprint_16g_bilan_et_plan_de_liberation.md),
[rejeu 16-G2](sprint_16g2_rejeu_ancre_et_contrat_prospectif.md),
[planning FR](sprint_planning_integration_marche_francais.md),
[clôture opérationnelle Sprint 15](sprint_15g_bilan_cloture_operationnelle.md).
