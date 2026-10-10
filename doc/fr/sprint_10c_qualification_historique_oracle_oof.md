# Sprint 10-C — Qualification de davantage d'historique Oracle OOF FR

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Conclusion du 3 octobre 2026

**Suite exécutée :** la [tentative de réparation 10-C1](sprint_10c1_reparation_fold3.md)
trace les lacunes jusqu'aux preuves source. Six publications ESMA non retrouvées
et des écarts de prix empêchent une réparation vérifiée ; fold3 toujours705/882.
Aucun masque forcé, aucune donnée ancienne écrasée. 105 tests FR passent.

**L'audit est terminé, mais aucun fold supplémentaire n'est encore qualifié.**
Sur les données gelées, les folds Oracle H5 complets restent **4, 5 et 6**.
Un profil alternatif d'entraînement glissant sur 504 séances améliore plusieurs
couvertures train, mais ne débloque ni les premiers folds ni le dernier test.
Il ne suffit donc pas de réentraîner pour obtenir une confirmation directionnelle
multi-fold. Il faut résoudre des lacunes de données/profil puis requalifier.

Cette étape ne produit aucun modèle, aucune prédiction nouvelle et aucun résultat
de performance. La conclusion de [10-B](sprint_10b_modele_directionnel_mutualise_h5.md)
reste `LIMITED_PILOT_INSUFFICIENT_OOS_FOLDS`. « Qualifié » signifie ici support
des données, pas avantage ML, rentabilité ou autorisation de trading.

## Pourquoi davantage d'OOF est nécessaire

Un modèle directionnel conditionnel doit apprendre sur les événements sélectionnés
par un Oracle qui **n'a pas été entraîné sur ces événements**. Des scores issus du
train Oracle ne conviennent pas. Le protocole 10-B réutilise les scores validation
et test de la branche Oracle arbres **fixée**, et non un champion choisi à l'aide
des labels de cette même validation. Les doublons date/titre retiennent le dernier
modèle disponible à la date de décision.

Avec les trois folds Oracle actuels, cette histoire commence le 2 février 2023 et
couvre 459 séances jusqu'au 23 janvier 2025. Le train directionnel ne dispose que
de 0/105/219 séances aux folds 4/5/6. Le minimum reste 126 séances et 100 exemples
par classe. Seul le fold 6 avait franchi ces contrôles dans 10-B.

## Périmètre et contrat de qualification

- Marché `FR_EQ`, calendrier officiel XPAR, labels H5, profil prix-only existant.
- Huit folds historiques du Sprint 8, dates VAL/test inchangées.
- Fin développement : 31 décembre 2025 ; aucune évaluation de 2026.
- Au moins 20 candidats par séance après chemin valide, maturité du label,
  profil prix prêt et cible Oracle connue.
- Au moins 80 % des séances officielles attendues, au moins 40 séances utilisables,
  présence des deux classes Oracle dans **chaque** phase.
- Train : disponibilité du label strictement antérieure au début VAL.
  VAL : strictement antérieure au début test. Test : au plus fin développement.
- Embargo existant de 21 séances conservé ; aucune interpolation des labels,
  aucun retrait de dates difficiles pour améliorer artificiellement la couverture.
- Les statuts semestriels ex post ne remplacent pas les masques causaux par ligne.
- Les rendements et AUC ne servent pas à sélectionner les nouvelles fenêtres.

Deux plans sont audités séparément : le train **cumulatif original**, puis le
train **glissant 504 séances**. Le second est un contrat de recherche distinct,
pas un correctif aux résultats 9-A/10-B et pas un nouveau défaut de production.
Il conserve la fin train et les bornes VAL/test. Aucun entraînement glissant n'a
été effectué.

## Résultats précis

Les déficits ci-dessous sont des minima arithmétiques pour le seul gate de
couverture ; ils ne garantissent pas la réparabilité ni les autres critères.

| Fold | Train cumulatif utilisable/attendu | Train glissant utilisable/504 | Phase bloquante supplémentaire | Admis complet |
|---|---:|---:|---|---|
| 0 | 386/504 | 386/504 | VAL 88/126 | Non |
| 1 | 459/630 | 379/504 | Aucune | Non |
| 2 | 585/756 | 379/504 | Aucune | Non |
| 3 | 705/882 | 400/504 | Aucune | Non |
| 4 | 831/1008 | 445/504 | Aucune | Oui |
| 5 | 957/1134 | 498/504 | Aucune | Oui |
| 6 | 1077/1260 | 492/504 | Aucune | Oui |
| 7 | 1170/1386 | 465/504 | Test 99/126 | Non |

Le fold 3 cumulatif atteint **79,93197 %**, pas 80 % : il faut au moins 706/882.
Le glissant atteint 400/504, soit 79,36508 % : il faut au moins 404, donc quatre
séances supplémentaires. Un affichage arrondi à 0,80 ne doit pas l'admettre.

Le fold 7 test atteint **78,57143 %** : il faut 101/126, soit deux séances
supplémentaires. Les 27 séances non utilisables s'étendent du **19 mars au
28 avril 2025**. Ce blocage n'est pas corrigé par davantage de données train.

## Ce que contiennent les fichiers de lacunes

Pour chaque plan/fold/phase, le diagnostic exporte toutes les séances officielles
avec moins de 20 lignes effectivement utilisables, et quatre compteurs successifs :

1. `label_rows` : lignes candidates présentes pour la date ;
2. `valid_mature_rows` : chemin valide et label disponible dans le split ;
3. `price_profile_ready_rows` : profil prix prêt parmi ces lignes ;
4. `oracle_known_ready_rows` : cible Oracle connue parmi ces lignes prêtes.

Le train cumulatif du fold 3 a **177 séances non utilisables**, réparties entre
2019 et janvier 2022 ; toutes ont zéro ligne à la dernière étape. La première
priorité est de comprendre pourquoi les lignes valides ne franchissent pas le
profil prix, puis les dates dont la cible manque. Ce n'est pas forcément une
absence d'OHLCV : admission des chemins, identité, qualité des features et
qualification cross-sectionnelle interviennent aussi.

Au fold 7 test, sur les 27 journées manquantes : 2 424 lignes candidates,
1 854 chemins valides, seulement 61 lignes prix prêtes au total, et zéro ligne
Oracle connue **et prix prête**. Les lignes censurées portent
`PATH_NOT_ADMITTED_OR_IDENTITY_CHANGED`. Certains labels existent hors du profil
utilisable : présence d'un label seule ne suffit pas.

Une « séance supplémentaire » implique au moins 20 titres réellement admissibles,
pas une barre ajoutée ou un flag forcé. Aucune réparation de ces sources n'a été
effectuée pendant cet audit.

## Marche à suivre pour obtenir une confirmation multi-fold

### Priorité 1 — Revue des lacunes du fold 3 cumulatif

Examiner l'ensemble des journées en échec, les rapports du profil prix gelé, les
barres et leurs preuves d'admission. Vérifier les fenêtres de calcul, les valeurs
manquantes, les identités et les chemins censurés. Corriger uniquement les défauts
documentés à la source, jamais une donnée en fonction de son rendement futur.
Recalculer les panels/labels concernés sous de nouveaux identifiants et hashes.
Ne pas écraser les sources gelées ni promouvoir une date au hasard pour atteindre
706. Si le blocage est légitime, conserver son exclusion.

Un fold Oracle 3 complet pourrait faire commencer l'histoire OOF dès février
2022. C'est un candidat pour donner suffisamment de train directionnel à plusieurs
folds ultérieurs, **pas encore une admission directionnelle démontrée**.

### Priorité 2 — Revue de mars/avril 2025

Même démarche pour le test Oracle du fold 7 : les nouvelles données doivent
permettre au moins 101 séances utilisables sans changer les dates ni les gates.
Le compteur potentiel train directionnel du fold 7 est de 312 séances sur les
dates actuelles, mais son test reste incomplet. Ne pas appeler ce fold « confirmé ».

### Priorité 3 — Générer puis requalifier le véritable OOF

Après réparation et nouvelle qualification complète : entraîner la branche
Oracle arbres fixée sur chaque train seulement, scorer VAL/test hors fit,
enregistrer dates de disponibilité, provenance et hashes ; dédupliquer causalement
par date/UID ; calculer TOP20 quotidien avant d'éliminer les déciles inconnus.
Vérifier ensuite le support **réel** des événements D1/intermédiaires/D10.
Le fichier de dates potentielles de cet audit n'est pas un pool TOP20 : il ne
contient ni scores ni sélection de modèle et ne doit pas alimenter 10-B.

### Priorité 4 — Confirmation directionnelle distincte

Reprendre les modèles/features/gates 10-B figés, champion choisi uniquement VAL,
au moins deux folds test complets. Ne pas promouvoir les arbres parce que leur
test précédent était meilleur. Les périodes 2024–2025 déjà observées constituent
une robustesse historique multi-fold, **pas un nouvel échantillon indépendant**.
Une confirmation finale intacte reste à réserver. Aucun résultat de cet audit
n'autorise le serving, le live ou une modification du lifecycle.

## Artefacts, exécution et vérification

Code : `modelFactory/fr_oracle_oof_qualification.py`.
Contrat : `config/research_fr/oracle_oof_qualification_v1.yaml`.
Tests : `tests/test_fr_oracle_oof_qualification.py`.

Rapport de référence :
`artifacts/fr/research/oracle_oof_qualification/fr-oracle-oof-qualification-7fe10ff3a653/report.json`.
Ce dossier contient pour chaque plan `*_potential_dates.parquet` et
`*_missing_sessions.parquet`. Le rapport archive les bornes et compteurs de chaque
phase, les folds admissibles, les déficits et les capacités en dates directionnelles.
Les classes directionnelles restent explicitement inconnues avant sélection OOF.

```powershell
python -m modelFactory.fr_oracle_oof_qualification
```

La commande vérifie les hashes des labels/panel et les disponibilités des features.
Elle n'utilise aucune API, aucun accès SQL, aucun fit. Une seconde exécution avec
le même fingerprint refuse d'écraser le dossier : utiliser un `--output-root`
distinct pour vérifier la reproductibilité. Les artefacts intermédiaires antérieurs
sont conservés ; le rapport ci-dessus fait référence.

**102 tests ciblés FR passent**, dont les nouveaux contrôles : maintien des bornes
et de l'embargo, rejet d'un calendrier/fenêtre invalide, exigence de trois phases
uniques, maturité stricte, déduplication et minimum de 20 candidats par jour.
