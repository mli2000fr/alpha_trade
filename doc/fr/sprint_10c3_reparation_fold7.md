# Sprint 10-C3 — priorité à la réparation documentaire du fold 7

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Décision

Le Sprint 10 doit être traité avant le Sprint 11. L'audit général de fiabilité
EODHD/Euronext reste distinct : il ne constitue pas un gate de clôture du sprint.
Ne pas confondre terminer l'étude avec obtenir un résultat ML positif : un
NO-GO correctement confirmé est également une conclusion valable.

## Diagnostic exécuté le 3 octobre 2026

Audit des 27 séances manquantes du test fold 7, sur les sources gelées :
126 séances attendues, 99 utilisables ; le gate inchangé de 80 % en exige 101.
Les 2 424 lignes candidates ont été retracées jusqu'aux fenêtres feature et label.
2 158 lignes comportent une corroboration de prix manquante ; il s'agit de
compteurs de candidats, pas de transactions ni de 2 158 erreurs EODHD prouvées.

**Aucune lacune ESMA n'a été trouvée dans les fenêtres de ces candidats.**
Il est donc raisonnable d'essayer cette réparation indépendante du fold 3.
Les six lacunes ESMA du fold 3 restent ouvertes : elles ne sont pas effacées.

| Séance source bloquante | Titres concernés distincts |
| --- | ---: |
| 2025-03-26 | 90 |
| 2025-04-23 | 9 |
| 2025-04-07 | 2 |
| 2025-03-07 | 1 |
| 2025-03-13 | 1 |
| 2025-04-11 | 1 |

Total : **104 couples titre/date**, sur 90 titres distincts. Le 26 mars 2025
affecte de nombreuses séances de décision parce que les features utilisent
une fenêtre rétrospective et que les labels H5 exigent un chemin complet.
La réparation d'une barre source peut donc rétablir plusieurs observations,
mais cela doit être mesuré après reconstruction, jamais présumé.

Les quelques références Euronext locales examinées corroborent les quatre
prix EODHD pour DG, PEUG et VETO au 26 mars ; RMS diffère sur les quatre prix.
C'est un premier rapprochement, **pas une admission** ni une preuve d'erreur.
Les séries ajustées demandent une convention compatible.

## Collecte ciblée terminée et rapprochement effectué

Les 90 titres ont été récupérés avec TLS vérifié. Sur les 104 couples demandés,
98 concordent avec les **quatre OHLC EODHD** à la tolérance 0,0001 EUR.
Les 104 couples diffèrent de Yahoo sur au moins un champ OHLC.
Cela ne prouve pas que chaque donnée Yahoo est erronée sous toutes les
conventions ; cela apporte une seconde corroboration aux barres EODHD pour
les 98 couples. Les volumes restent séparés et le paramètre Euronext ajusté
est conservé explicitement.

Six couples restent non résolus, tous le 26 mars 2025 : ADP, AIR, BOL, CA,
ODET et RMS. Ils ne doivent pas être promus par extrapolation.

Rapport : `euronext_targeted_20261003/evidence_review.json` dans le répertoire
fold7_repair. SHA256 du manifeste des demandes :
`08c64f8e322b052fa4abbcdea75ba60662dee6428a46e49865de7179759401e0`.
SHA256 du rapport de collecte :
`39c2522d5e09ebac8247f45d9d8e163158e4f268f4203de1c1c62fdf57386f92`.

**État historique avant reconstruction (désormais dépassé, voir bilan ci-dessous).** La nouvelle
corroboration doit entrer dans une preuve de recherche versionnée : aucun
statut canonique/live et aucune date de publication officielle historique
inventée à partir de l'observation effectuée aujourd'hui.

`modelFactory/fr_fold7_price_requests.py` prépare la liste exhaustive, déduplique
les couples et joint ISIN/MIC historique et valeurs EODHD/Yahoo. Pas de sélection
selon performance future ni remplacement d'un titre difficile.

`modelFactory/fr_fold7_euronext_proofs.py` récupère uniquement la fenêtre
nécessaire de chaque titre, avec TLS vérifié, en respectant la restriction
publique. Le lecteur utilise les en-têtes, distingue Last de Close et lit
Number of shares ; les séparateurs de milliers sont gérés. Les payloads et
HTML sont conservés ; un échec reste explicitement visible.

Rapport diagnostic :
`artifacts/fr/research/fold7_repair/fr-fold7-test-repair-4047b4e2e9d5/report.json`.
Demandes : `artifacts/fr/research/fold7_repair/price_evidence_requests.json`.
Collecte : `artifacts/fr/research/fold7_repair/euronext_targeted_20261003`.

```powershell
Test-Path F:\projets\artifacts\fr\research\fold7_repair\euronext_targeted_20261003\report.json
```

Ce fichier signifie collecte terminée, **pas réparation admise**.

## Suite obligatoire, dans cet ordre

1. Revoir chaque couple demandé et les quatre OHLC officiels ; distinguer
   données absentes, convention ajustée non compatible et vraie corroboration.
   Ne pas valider une journée entière parce que sa clôture seule correspond.
2. Formaliser une preuve indépendante versionnée et hashée pour chaque barre
   effectivement corroborée. Une divergence non expliquée reste bloquante.
3. Reconstruire de nouveaux manifestes, snapshots, panels et labels, sans
   écraser les sources gelées ni modifier 20 titres minimum/80 % de couverture.
4. Requalifier train/validation/test du fold 7 et les autres folds. Mesurer les
   séances effectivement récupérées et les motifs toujours présents.
5. Si le fold 7 devient complet, générer de véritables scores Oracle OOF puis
   refaire le contrôle du support directionnel. Son admission peut apporter
   un deuxième test directionnel aux côtés du fold 6 ; ce n'est pas garanti
   avant génération des événements et validation de leur support.
6. Rejouer le protocole directionnel figé, champion choisi sur VAL seulement.
   Cette robustesse multi-fold historique ne devient pas un OOS final neuf :
   ces périodes ont déjà été explorées. Aucune sélection du meilleur arbre sur TEST.
7. Si les preuves ne permettent pas la reconstruction, consigner le blocage
   réel et la source encore requise. Ne pas déclarer le Sprint 10 terminé avec
   une confirmation multi-fold fictive, et ne pas forcer le fold 3.

Le moteur d'audit `fr_fold3_repair_audit.py` accepte désormais `--fold` et
`--phase`, avec fold 3/train conservés par défaut. Il ne modifie pas les sources.
Les tests vérifient le ciblage explicite et la déduplication des demandes de prix.
Douze tests ciblés de diagnostic/requêtes/qualification passent.

## Bilan exécuté — reconstruction et confirmation multi-fold

La reconstruction est terminée dans
`artifacts/fr/research/fold7_repair/rebuild-20261003-v1`.
Son rapport complet est `confirmation/report.json` ; la qualification sans fit
est référencée par `rebuild_report.json`.

### Preuves et périmètre de modification

`modelFactory/fr_fold7_rebuild.py` revérifie la collecte TLS, les hashes du
ledger et du rapport, l'identité ISIN/MIC, le paramètre adjusted=Y, le payload
chiffré et sa correspondance avec le HTML décodé. Il relit les archives EODHD
et recalcule la concordance des quatre OHLC (tolérance 0,0001 EUR). Les statuts
du rapport de revue ne suffisent pas à eux seuls à admettre une barre.

Seules 98 lignes du **nouveau** manifeste perdent le motif de corroboration
manquante. Aucun autre motif ESMA, identité ou corporate action n'est retiré.
Les six divergences restent bloquantes. Les prix, le volume et les archives
sources ne changent pas. L'univers reste à 330 titres ; le nombre de lignes
RESEARCH_J1_ELIGIBLE passe de 561 001 à 561 099, sur 811 954 lignes totales.

La preuve est observée en octobre 2026 : elle n'invente ni publication PIT en
2025 ni validation canonique/live. Les flags historiques PIT, corporate action,
rendement économique et admission canonique restent faux. L'hypothèse J+1 de
recherche et les limitations adjusted=Y sont conservées.

La reconstruction réutilise les moteurs 6-B/6-C/7-A/profil court/8, leurs seuils
et leur calendrier ; les copies des configurations sont dans le dossier du
run. Les anciennes configurations et les anciens artefacts ne sont pas écrasés.

### Qualification réelle du fold 7

| Phase H5, train cumulatif | Séances utilisables | Couverture | Gate |
|---|---:|---:|---|
| Train | 1 170 / 1 386 | 84,42 % | admis |
| Validation | 120 / 126 | 95,24 % | admis |
| Test | 126 / 126 | 100 % | admis |

Le test passe de 99 à 126 séances, sans abaisser 80 % ou le minimum de 20
titres. Les folds Oracle complets deviennent 4/5/6/7. Le fold 3 reste exclu.
La capacité théorique de train directionnel devient 219 dates au fold 6 et
312 au fold 7 ; elle est ensuite vérifiée sur de vrais événements Oracle OOF.

### Scores Oracle et direction : résultats observés

`modelFactory/fr_fold7_confirmation.py` génère les scores OOF puis entraîne
la direction. Deux profils explicitement versionnés acceptent 4/5/6/7 :
`fr_oracle_h5_fold7_repaired_v1` et `fr_direction_h5_fold7_repaired_v1`.
Les profils initiaux v1 restent figés sur 4/5/6 ; un ajout de fold dans ces
anciens profils est toujours rejeté. Hyperparamètres, seed, features, gates,
purge, fractions TOP20 et sélection champion sur VAL restent identiques.
La branche arbres Oracle pour constituer les événements est toujours fixée,
pas choisie a posteriori sur TEST. 2026 n'est pas évaluée.

Oracle : précision quotidienne moyenne du TOP20 proche de 41,58 %, lift moyen
2,033. Mais avantage moyen sur ATR de **+0,195 point de pourcentage** seulement,
contre +2 points exigés : `NO_GO_INCREMENTAL_PILOT`. Détecter l'amplitude ne
prouve donc pas un avantage suffisant sur la référence simple ATR.

Direction : 9 661 événements sur 585 séances archivées, quatre modèles fit
(deux variantes sur chacun des folds 6 et 7). Les folds 4/5 restent bloqués
pour manque de train directionnel OOF (0/105 dates, minimum 126).

| Test | Champion VAL | AUC D10 vs D1 | LONG brut H5 | SHORT brut H5 | Spread |
|---|---|---:|---:|---:|---:|
| Fold 6 | logistique | 0,4967 | −0,733 % | +0,649 % | −0,084 % |
| Fold 7 | arbres | 0,5210 | +0,782 % | −2,761 % | −1,979 % |

Les rendements sont les moyennes quotidiennes des sélections, **pas un rendement
portefeuille** : prix bruts, sans coûts/dividendes/contraintes de vente à découvert.
Le spread additionne le rendement LONG et le rendement signé SHORT.

Moyenne égale par fold des champions retenus :

- AUC 0,5088, sous le gate 0,53 ;
- delta AUC vs momentum 20 : −0,0041, sous +0,01 requis ;
- IC quotidien 0,0272, sous 0,03 requis ;
- spread −1,032 %, sous +0,20 % requis.

Verdict : **NO_GO_DIRECTIONAL_PILOT** avec deux folds réellement évalués.
La réparation de données a levé le manque de support ; elle n'a pas révélé une
direction D1/D10 exploitable avec ce protocole prix-only H5. Ne pas substituer
un non-champion sur TEST, ajuster les seuils sur ces résultats, ou lancer du live.
Ce constat ne rejette pas toutes les informations directionnelles possibles.
Ces périodes déjà explorées constituent une robustesse historique, pas un OOS
final neuf. La représentativité des radiés reste limitée dans les folds.

### Clôture et suites

La tâche de réparation et de confirmation multi-fold du Sprint 10 est terminée.
La piste directionnelle testée est clôturée **NO-GO**, pas GO production ni
validation économique. Les autres tâches du planning (ranking/abstention,
économie, fournisseurs additionnels) ne deviennent pas automatiquement réalisées.
Les lacunes documentaires ESMA du fold 3 restent consignées, mais ne bloquent
plus la conclusion de cette confirmation à deux folds.

37 tests ciblés de diagnostic, qualification, reconstruction, versions de
protocoles, pilote Oracle et direction passent ; Ruff passe sur les fichiers concernés. Aucun SQL, serving,
batch de collecte ou audit général de fiabilité EODHD/Euronext n'est modifié.
