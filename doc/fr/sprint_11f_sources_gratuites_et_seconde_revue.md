# Sprint 11-F — Sources gratuites, comparabilité et seconde revue

État vérifié le 4 octobre 2026. Recherche FR uniquement.

**Suite :** [11-G, seconde passe documentaire](sprint_11g_seconde_passe_documentaire.md)
sur 33/33 fiches, dont 32 pages contrôlées visuellement pour 27 fiches. Même IA, donc pas une
seconde revue indépendante. Les 33 décisions humaines restent PENDING.

## Verdict actuel

Suite de qualification : [11-H — arbitrage et disponibilité PIT](sprint_11h_arbitrage_et_disponibilite_pit.md).
38 PDF intègres, aucune disponibilité historique Web qualifiée dans le dossier ;
arbitrages proposés mais 33 décisions indépendantes encore PENDING.

**Sprint 11 reste ouvert : corpus élargi, mais pas encore de dataset guidance
autorisé ni de démonstration directionnelle.** Les sources gratuites ne sont pas
déclarées épuisées. Aucun abonnement n'est actuellement démontré indispensable.
Le blocage immédiat est une seconde lecture indépendante et un support temporel
insuffisant, pas le prix d'un fournisseur.

Aucun modèle AMF/DILA de 11-C n'a été réentraîné. Aucune table canonique, aucun
modèle de serving et aucun batch de production n'ont été modifiés par cette passe.
Les publications sont choisies sans regarder les rendements futurs. La période
2026 reste réservée à une confirmation ultérieure.

## 1. Collecte effectivement disponible

| Passe | PDF extraits | Échecs d'extraction |
|---|---:|---:|
| 11-D, première lecture | 17 | 0 |
| 11-E, candidats restants et premières publications antérieures | 119 | 0 |
| 11-E, complément d'antécédents | 7 | 0 |
| 11-F, antécédents Ubisoft et SMCP | 8 | 0 |
| Total unique du dossier v4 | **151** | **0** |

Ce total n'inclut pas les 24 documents du POC de septembre. Extraction réussie
ne signifie ni validation sémantique, ni disponibilité historique prouvée.
Le filtre lexical signale 122 documents, y compris des comparaisons avec des
résultats passés : ces occurrences ne sont pas des labels automatiques.
La revue manuelle exhaustive des 151 documents n'est pas achevée.

La dernière collecte a obtenu les exports officiels complets par ISIN :
Ubisoft 534 lignes sur 534 annoncées ; SMCP 44 sur 44. Quatre publications
antérieures par émetteur ont été sélectionnées avant lecture, dans un historique
borné, puis archivées avec leur empreinte. Ces exports complets ne prouvent pas
que toute publication Web possible a été retrouvée.

Rapport de cette recherche :
[free-sources-20261004-v1](../../artifacts/fr/research/guidance_completion_11e/free-sources-20261004-v1/source_audit_report.json).

## 2. Sources et ce qu'elles prouvent

| Source gratuite | Usage | Limite à conserver |
|---|---|---|
| INFO-FINANCIERE/DILA, API `flux-amf-new-prod` | Métadonnées des dépôts ; exports par ISIN ; contrôle du nombre de lignes | Reconstruction actuelle, pas capture historique quotidienne |
| PDF officiels DILA | Ancienne/nouvelle prévision, exercice, unités et notes | Date écrite dans le communiqué différente de première disponibilité prouvée |
| Archives financières SMCP | Page officielle des résultats H1 2019, effectivement récupérée | Page actuelle ne prouve pas son contenu exact au jour de 2019 |
| Archives financières Virbac | Recherche de la prévision antérieure et de la publication initiale | Une republication du 17 juillet ne prouve pas une disponibilité le 3 juillet |
| Wayback, endpoint de disponibilité | Recherche d'une capture antérieure à la décision | Les requêtes de cette passe ont reçu HTTP 429 ; aucune capture qualifiée obtenue |

Un 429 signifie une limitation temporaire d'accès, pas une absence de données.
La récupération directe d'un document Virbac a aussi rencontré une interruption
réseau ; sa copie DILA existait déjà dans le corpus. Aucune protection n'a été
contournée et aucune erreur réseau n'a été transformée en preuve d'absence.

Une capture proposée par une archive doit être antérieure ou égale à la limite
de décision. Il faut encore vérifier le contenu et son empreinte ; une réponse
`available` seule n'autorise pas un label PIT.

## 3. Dossier actif : version v4

[Dossier à remettre au second lecteur](../../artifacts/fr/research/guidance_completion_11e/second-review-20261004-v4/README.md).

- 23 annonces proposées après première lecture : **13 UP et 10 DOWN**.
- 6 cas complexes réservés, sans direction autorisée.
- 4 autres classifications : période passée, confirmation sans révision,
  objectif non financier, résultat passé et cible d'un nouvel exercice.
- 33 fiches au total, toutes encore en attente de seconde lecture.
- `training_eligible=false` : rien n'est autorisé pour le ML.

Les anciennes versions v1/v2/v3 restent des preuves datées. Pour le travail
actuel, utiliser v4 et non additionner les effectifs des différentes versions.

Les huit propositions supplémentaires de v3, reprises dans v4, sont :

| Émetteur / annonce | Métrique de la même période future | Ancienne → nouvelle | Première lecture |
|---|---|---|---|
| Sodexo, 20/03/2025 | Croissance organique annuelle FY2025 | 5,5–6,5 % → 3–4 % | DOWN |
| Plastic Omnium, 24/09/2021 | Marge opérationnelle annuelle | au moins 6 % → 4–5 % | DOWN |
| Renault, 17/10/2019 | Marge opérationnelle annuelle | environ 6 % → environ 5 % | DOWN |
| Maisons du Monde, 09/10/2023 | EBIT annuel | 65–75 M€ → 40–50 M€ | DOWN |
| Capgemini, 28/10/2021 | Croissance annuelle à changes constants | 12–13 % → 14,5–15 % | UP |
| Ipsen, 23/10/2024 | Marge opérationnelle des activités annuelle | strictement >30 % → strictement >31 % | UP |
| Rexel, 29/06/2021 | Croissance annuelle à jours constants | 5–7 % → 12–15 % | UP |
| Aramis, 09/12/2021 | CA FY2022 | >1,5 Md€ → >1,6 Md€ | UP, périmètre à confirmer |

Les symboles « environ », « au moins » et « strictement supérieur » restent
dans le manifeste et les fiches : ne pas assimiler un plancher à une prévision
ponctuelle exacte. Les anciennes prévisions ne doivent pas être remplacées par
les résultats réalisés du précédent exercice.

## 4. Cas réservés : ne pas fabriquer une direction

| Cas | Motif |
|---|---|
| SMCP 2023 | Sémantique de bornes à vérifier |
| Arcure 2024 | Intervalle et incertitude à vérifier |
| Nexans octobre 2022 | Nouvelle guidance différente entre deux pages du même PDF |
| Aramis avril 2022 | Hausse du CA mais dégradation de la marge : événement mixte |
| Ubisoft septembre 2024 | Ancienne cible annuelle qualitative ; le résultat passé n'est pas l'ancienne prévision |
| SMCP décembre 2019 | Ancienne marge ancrée sur 2018 ; exclusion de De Fursac dans l'ancien périmètre à réconcilier |

Les comparateurs chevauchants ou les changements de périmètre ne sont pas
promus en paires strictes pour augmenter artificiellement le nombre de labels.
Les doublons français/anglais et les confirmations ultérieures ne deviennent
pas plusieurs événements d'entraînement.

## 5. Recouvrement avec les données Oracle figées

Le contrôle utilise le même pool de **9 661 observations**, empreinte SHA-256
`8b251ed6c0028d7bff179fae7a8c0eeedf4c54fb606bfb1a356446e7c988766b`.
Les labels doivent être matures et leurs chemins valides. La phase du fold
Oracle ne remplace pas le découpage des folds directionnels externes.

| Décalage prudent / fenêtre d'exposition | Annonces recoupées | Observations |
|---|---:|---:|
| 1 jour / 7 jours | 4 | 10 |
| 1 jour / 30 jours | 4 | 26 |
| 2 jours / 7 jours | 3 | 9 |
| 2 jours / 30 jours | 3 | 24 |

Les quatre annonces recoupées à 1 jour / 30 jours sont Assystem octobre 2024
(20 observations), Maisons du Monde octobre 2023 (4), Icade novembre 2024 (1)
et Sodexo mars 2025 (1). Les 26 observations portent 5 D1 et 4 D10, sans être
26 annonces indépendantes.

| Fold directionnel externe | Train exposé | Validation exposée | Test exposé |
|---|---:|---:|---:|
| 6 | 4 | 0 | 21 |
| 7 | 4 | 21 | 1 |

Le train exposé ne contient aucun D10 dans ces folds. Il est impossible de
conclure sur une séparation D1/D10 robuste à partir de ce support. **Aucun fit
guidance n'a été lancé ; les seuils préenregistrés ne sont pas abaissés.**
Ce n'est pas un NO-GO statistique de la guidance en général.

## 6. Comment effectuer la seconde revue

1. Ouvrir le README du dossier v4 puis les PDF locaux indiqués, pages et notes.
2. Ne pas consulter les rendements ni sélectionner selon les résultats boursiers.
3. Pour chaque fiche de `second_review.json`, renseigner le lecteur, la date,
   la décision `ACCEPT`, `REJECT` ou `RESERVE` et une justification.
4. Pour accepter une paire, vérifier les quatre champs : ancienne valeur bien
   prévisionnelle ; même période/métrique/périmètre ; bornes et qualificatifs
   corrects ; absence de doublon.
5. Un cas complexe ne peut pas être accepté simplement en cochant ces champs :
   sa preuve et sa classification doivent d'abord être révisées dans une
   nouvelle version du manifeste.
6. Conserver les décisions divergentes ; une première lecture par l'IA ne
   constitue pas une seconde revue indépendante.

La validation technique est disponible avec :

```powershell
python -m service.fr.guidance_completion_11e validate-second-review --output artifacts/fr/research/guidance_completion_11e/second-review-20261004-v4
```

Cette validation ne rend pas les données automatiquement admissibles au ML :
le contrat PIT et les effectifs doivent encore passer leurs propres gates.

## 7. Travail restant, ordre et arrêt honnête

1. Obtenir la seconde lecture autorisée par l'utilisateur et arbitrer les
   divergences, sans déléguer à l'IA une prétendue revue humaine indépendante.
2. Terminer la revue des candidats déjà téléchargés : un filtre lexical seul
   ne permet pas de déclarer une source épuisée.
3. Rechercher uniquement les antécédents et périmètres manquants des cas
   documentés ; conserver les indisponibilités techniques séparément des
   documents réellement absents.
4. Requalifier les dates historiques. Un proxy de transmission reconstruit
   n'est pas une preuve stricte de ce qui était observable à l'époque.
5. Recalculer le support sans changer le pool, les folds ou les gates pour
   obtenir un résultat favorable. Un élargissement de périmètre nécessiterait
   un protocole distinct, pas une correction silencieuse de celui-ci.
6. Tester l'apport guidance seulement si revue, disponibilité et effectifs
   deviennent suffisants ; sinon clôturer ce pilote `BLOCKED_DATA_NOT_READY`
   avec les pièces manquantes précises, sans annoncer un gain ni demander un
   abonnement non justifié.

## 8. Implémentation et contrôles

`service/fr/guidance_free_sources_11f.py` réalise la collecte bornée des
antécédents et les essais d'archives publiques. `guidance_completion_11e.py`
assemble les preuves, contrôle les empreintes des manifests de base récursifs,
prépare la revue et mesure le support sans entraînement.

61 tests ciblés passent pour 11-B à 11-F et le POC ; Ruff passe sur les fichiers
de cette évolution. Il ne s'agit pas d'une validation de toute l'application.
Les tests couvrent notamment le refus d'une base modifiée, des identifiants
dupliqués et d'une capture d'archive postérieure à la limite historique.

Références : [11-E](sprint_11e_completion_gratuite_guidance.md),
[catalogue des sources gratuites](catalogue_sources_gratuites_validation_historique.md),
[planning](sprint_planning_integration_marche_francais.md).
