# Sprint 8-B — Revue des chemins extrêmes et support réel des folds

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Réalisé le 3 octobre 2026, à la suite des [labels Sprint 8-A](sprint_8a_labels_et_contrat_evaluation.md). **Aucun entraînement, aucune modification de cible, aucun assouplissement des gates.** Le lot mesure le support après jointure aux features et produit un dossier vérifiable des chemins extrêmes.

## 1. Résultat et décision

Les labels bruts sont reproductibles, mais le support n'autorise pas encore une comparaison générale H5/H10/H20 prix versus benchmark :

| Horizon | Folds entièrement couverts prix-only | Folds entièrement couverts sur support commun prix/benchmark |
|---|---|---|
| H5 | 4, 5 et 6 | Aucun |
| H10 | Aucun | Aucun |
| H20 | Aucun | Aucun |

Un fold « entièrement couvert » signifie que train, validation et test satisfont les critères de données ci-dessous. Ce n'est ni une validation ML, ni un verdict de rentabilité. Les autres folds restent archivés avec les phases/reasons qui échouent ; leurs observations ne sont pas supprimées des sources.

**Orientation recommandée :** conserver le prix-only H5 comme seul candidat à un pilote supervisé limité, après revue des réserves documentaires. Ne pas annoncer une comparaison benchmark ou un entraînement H20 validé ; ne pas descendre les seuils après ce bilan pour rendre ces expériences vertes. Les gaps de référence/prix et la censure des chemins sont désormais des freins plus importants que le nombre de features.

## 2. Jointure et support commun

Sources gelées : labels 8-A, panel prix 7-A2 et panel enrichi 7-B. Les SHA-256 sont inscrits dans `config/labels_fr/fr_labels_review_v1.yaml`. Les clés `(decision_session_date,research_uid)` doivent être uniques dans chaque panel, et `(decision_session_date,research_uid,horizon)` dans les labels. Les univers prix et benchmark doivent coïncider ; chaque label doit retrouver sa candidate. Une feature disponible après la décision déclenche une erreur.

Pour chaque fold/horizon/phase :

1. sélectionner les dates de décision dans les bornes figées ;
2. vérifier que le chemin est VALID et que la cible est mature avant la frontière autorisée ;
3. exiger le label Oracle connu ;
4. appliquer soit `profile_row_ready`, soit `common_row_ready` ;
5. recalculer le nombre de **lignes effectivement utilisables** par date après ces masques ;
6. ne compter comme utilisables que les dates avec au moins 20 lignes.

On ne recalcule pas les labels D1/D10 sur ce sous-univers de features : leur dénominateur reste celui de 8-A. La cross-section de support porte sur l'entraînement/évaluation, pas sur une nouvelle définition de vérité terrain. Les deux modèles d'une éventuelle comparaison doivent consommer les mêmes clés du support commun ; le prix-only sur sa couverture originelle est une expérience différente.

Le support commun doit être inclus dans celui du prix-only. Les comptes comprennent labels Oracle positifs/négatifs, D1/D10, titres, lignes radiées et séances couvertes. Les comptes D1/D10 sont descriptifs ; le gate actuel exige deux classes Oracle, pas un seuil directionnel de performance.

## 3. Critères et frontières temporelles

Règles de disponibilité 8-A conservées :

- train : `label_available_session_date < validation_start` ;
- validation : `label_available_session_date < test_start` ;
- test développement : `label_available_session_date <= 2025-12-31` ;
- features : disponibilité maximale ≤ instant de décision.

Les dates de séance représentent des ouvertures XPAR : un label publié le jour de la frontière n'est pas admis dans le split précédent. Les fenêtres train conservent les 21 séances de purge/séparation déjà figées. La confirmation 2026 ne sert pas à choisir les chemins examinés ni les gates.

Une phase passe si au moins 80 % de ses séances officielles ont au moins 20 lignes utilisables, au moins 40 séances sont utilisables et les deux classes Oracle existent. Les séances sans observations sont incluses au dénominateur. Les règles 20/80 %/40 reprennent les seuils de couverture précédents ; elles ne sont pas choisies sur une performance. Elles ne font pas appel au futur état global du semestre comme signal de trading.

### Supports H5 prix-only admis

| Fold | Phase | Séances utilisables / attendues | Lignes Oracle | Positifs Oracle | D1 | D10 |
|---|---|---:|---:|---:|---:|---:|
| 4 | Train | 831 / 1 008 | 66 905 | 13 718 | 6 376 | 7 098 |
| 4 | Validation | 120 / 126 | 9 871 | 2 025 | 958 | 1 059 |
| 4 | Test | 104 / 126 | 7 281 | 1 495 | 682 | 761 |
| 5 | Train | 957 / 1 134 | 77 316 | 15 856 | 7 381 | 8 210 |
| 5 | Validation | 104 / 126 | 7 281 | 1 495 | 682 | 761 |
| 5 | Test | 109 / 126 | 8 628 | 1 740 | 802 | 893 |
| 6 | Train | 1 077 / 1 260 | 85 928 | 17 625 | 8 192 | 9 117 |
| 6 | Validation | 103 / 126 | 8 162 | 1 642 | 758 | 843 |
| 6 | Test | 126 / 126 | 10 200 | 2 087 | 968 | 1 093 |

Ces folds expanding partagent des historiques d'entraînement ; ce ne sont pas trois essais indépendants. Leurs tests chronologiques sont disjoints selon le plan 8-A. Le bilan ne prouve pas une couverture continue depuis 2019 ni une robustesse des titres radiés.

## 4. Revue des chemins — protocole

La sélection porte exclusivement sur le développement : chemins VALID dont le label est disponible au plus tard le 31 décembre 2025. Pour chaque semestre/horizon, prendre les deux rendements les plus faibles et les deux plus élevés, avec ordre déterministe date/UID pour la sélection d'audit seulement ; ajouter les chemins valides des titres actuellement radiés, puis dédupliquer. Ce tri ne modifie pas la règle de tie des labels.

**325 cas** sont exportés avec toutes les barres du chemin, le ratio entrée/sortie recalculé et les payloads fournisseur splits/dividendes vérifiés par hash.

- 0 cas contiennent un split déclaré par le fournisseur dans leur intervalle ;
- 37 contiennent un événement dividende ;
- 58 contiennent au moins un mouvement clôture/clôture supérieur à 30 % en valeur absolue.

Ces catégories se recouvrent éventuellement. Une alerte ne supprime pas un label : un grand mouvement peut être un vrai événement économique. Le seuil de 30 % est un seuil de revue, pas un filtre d'entraînement ni un seuil prédictif. L'absence de split dans ces 325 cas n'est pas une preuve générale de complétude de la source corporate actions.

Les dividendes signalent que le rendement reste brut, non total return. Un dividende dont l'ex-date tombe le jour d'entrée ne doit pas être automatiquement ajouté comme un cash-flow acquis au détenteur ; il faut vérifier calendrier de détention, ex-date, record date et paiement avant toute correction économique. Ce lot n'en effectue aucune.

## 5. Lecture ciblée des extrêmes

### ABVX.PA — juillet 2025

Le dossier contient notamment le chemin H20 du 1er juillet au 29 juillet : ouverture 6,60 €, clôture finale 60,40 €, soit +815,15 % brut. Le 22 juillet clôture à 8,90 €, puis le 23 juillet ouvre à 42,60 € et clôture à 54,30 €. Aucun split n'est déclaré dans cet intervalle par le payload contrôlé.

Une source primaire indépendante confirme la publication par Abivax de résultats positifs de phase 3 le 22 juillet 2025 à 22 h 05 CEST, avant la séance du 23 juillet. La chronologie est donc **compatible avec un véritable saut événementiel**, et ne justifie pas de supprimer automatiquement le cas comme erreur de prix. Le communiqué ne valide toutefois pas les prix exacts ni la possibilité d'exécuter à ces cours. [Communiqué officiel Abivax](https://ir.abivax.com/news-releases/news-release-details/abivax-announces-positive-phase-3-results-both-abtect-8-week).

### ALNOV.PA — mars/avril 2020

Le chemin H20 du 13 mars au 14 avril présente une ouverture à 1,27 € et une clôture à 5,64 €, soit +344,09 % brut, sans split déclaré dans l'intervalle. Un communiqué officiel du 29 avril 2020 décrit l'activité de tests COVID-19 et leur distribution internationale. Cela apporte un **contexte événementiel plausible**, pas une validation documentaire de chaque séance du chemin, et cette publication postérieure ne devient pas une feature PIT des entrées de mars. [Communiqué officiel Novacyt](https://novacyt.com/fr/investors/rns/covid-19-update-and-notification-of-final-results-tugc1709j0puh4a/).

Les autres grands mouvements ne sont pas considérés validés par ces deux exemples. L'état général reste `human_official_event_validation=PENDING`. Le dossier facilite la revue documentaire, sans prétendre remplacer des avis d'opération officiels, des règlements de radiation ou un second historique de prix.

## 6. Artefacts et reproduction

- Configuration : `config/labels_fr/fr_labels_review_v1.yaml`.
- Module : `modelFactory/fr_labels_review.py`.
- Tests : `tests/test_fr_labels_review.py`.
- Artefacts : `artifacts/fr/labels/review/fr-label-review-dff472deaf9a/`.
- `report.json` : 144 combinaisons fold × horizon × phase × profil, états, causes, comptes et empreintes.
- `cases.json` : les 325 chemins et leurs événements fournisseur.

```powershell
python -u -m modelFactory.fr_labels_review --verify-rebuild
```

Deux reconstructions identiques, hash du dossier de cas `7ac6216728b06a276d6614a54f59eade220ac82c25cbd5aba122946e7ff9fade`. Aucun téléchargement massif ni mutation des sources, labels ou panels.

185 tests ciblés passent, dont neuf nouveaux : jointures multi-horizons, doublons/univers divergents, fuite feature, inclusion du support commun, maturité aux frontières, test ne traversant pas la confirmation, sélection de cas hors 2026 et recalcul du minimum cross-section après masques. Ruff passe. Cette suite n'est pas l'ensemble des tests applicatifs.

## 7. Ce qui reste avant promotion

Le lot 8-B est terminé comme **audit technique**, pas comme validation économique. Les réserves J+1 reconstruite, cinq radiés faiblement représentés, corporate actions/revue documentaire et données secteur/taille restent présentes.

Pour avancer sans dissimuler ces réserves, un prochain lot peut préparer un pilote Oracle **H5 prix-only sur les folds 4/5/6**, explicitement recherche-only : baseline mécanique, modèle simple, seuils/folds figés et confirmation 2026 non consultée pour l'ajustement. Il faudra documenter le périmètre limité et ne pas déclarer le Sprint 8 global « GO économique ». H10/H20 et benchmark restent bloqués selon les gates actuels ; leur réouverture exige amélioration vérifiable de la couverture ou nouvelle expérience de données pré-enregistrée, pas un assouplissement opportuniste.
