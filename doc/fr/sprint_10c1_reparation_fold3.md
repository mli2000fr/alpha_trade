# Sprint 10-C1 — Tentative de réparation des lacunes du fold 3

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Résultat

**Réparation bloquée par des preuves source manquantes ou divergentes.**
L'audit a été exécuté le 3 octobre 2026. Aucune admission n'a été forcée,
aucune barre ni feature n'a été interpolée et aucun seuil n'a été réduit.
Le fold 3 reste à **705/882 séances utilisables, soit 79,93197 %**, sous les
706 séances requises. Aucun modèle nouveau n'a été entraîné.

Le manque arithmétique d'une séance, signalé dans
[10-C](sprint_10c_qualification_historique_oracle_oof.md), ne signifiait donc
pas qu'une simple correction informatique pouvait la rendre admissible.

## Périmètre exact de l'audit

Train cumulatif du fold 3 : 31 janvier 2019–8 juillet 2022, H5, profil prix court
figé de 14 features. Les lignes des **177 séances non utilisables** ont été
jointes aux labels et aux preuves du manifeste Sprint 5.

Pour chaque candidat :

- relecture des features et vérification du masque `profile_complete` par
  finitude des 14 valeurs ;
- vérification du décalage feature source → décision, exactement une séance XPAR ;
- recherche des preuves d'admission sur les 21 séances de la plus longue fenêtre
  de feature, sans franchir une barre non admise ;
- recherche des preuves sur le chemin du label, de la décision à J+5 inclus ;
- export des raisons de rejet par titre/date source, séparément pour le passé
  des features et pour le chemin futur du label.

**14 997 lignes candidates** ont été tracées. Les classes et rendements de 2026
n'ont pas été examinés. Aucune modification des tables, des batches en cours,
des anciens artefacts ou des configurations de production.

## Origine des lacunes

| Cause présente dans les fenêtres examinées | Lignes candidates touchées |
|---|---:|
| `MISSING_DELTA_PUBLICATION_DAY` | 12 219 |
| `INDEPENDENT_PRICE_CORROBORATION_MISSING` | 2 452 |
| `MANIFEST_ROW_MISSING` | 68 |
| `MULTIPLE_ACTIVE_TARGET_MICS` | 5 |

Ces compteurs ne sont **pas exclusifs** : une ligne peut cumuler plusieurs causes.
Ils comptent les candidats affectés par une cause dans leur fenêtre, pas les
fichiers absents ni les barres à télécharger.

138 des 177 dates ont au moins un candidat touché par une publication ESMA
manquante dans sa fenêtre de feature ou son chemin H5. Les six dates source sont :

```text
2019-05-22
2019-06-18
2020-05-11
2021-01-04
2021-01-27
2021-06-07
```

Une seule source journalière non admise peut invalider le label de journées
antérieures et interrompre ensuite les features à fenêtre glissante. C'est
pourquoi les journées décisionnelles touchées sont bien plus nombreuses que
les six publications absentes.

### Vérification des sources ESMA

Pour chacune des six dates, l'index officiel a été interrogé sans filtre de date
de publication, sur `file_name:DLTINS_<date>*` : **zéro résultat**. Cela évite de
conclure à un manque uniquement à cause du filtre temporel du téléchargement
initial. Les requêtes supplémentaires `FULINS_E_<date>*` donnent aussi zéro.

Les noms d'archives directs `01of01` à `01of04` ont été testés sur le serveur
officiel ; `01of21` a également été testé pour le 4 janvier 2021, en raison du
format du lendemain. Tous ces tests renvoient **HTTP 404**.

Cela signifie « non retrouvées par ces recherches », **pas** « preuve qu'aucune
archive n'existe ailleurs ». Le rapport conserve les URLs, les réponses de l'index,
les statuts HTTP et les heures de vérification. Ni une absence de résultat ni un
404 n'autorisent à supposer une journée sans changement.

### Écarts de prix

Certaines lacunes ne viennent pas d'ESMA. Les rapports de corroboration montrent
des différences effectives entre EODHD et Yahoo, notamment le 19 octobre 2020.
Exemples lus dans le rapport historique existant :

| Titre/date | Champ | EODHD | Yahoo |
|---|---|---:|---:|
| AB.PA, 2020-10-19 | close | 10,20 | 10,26000023 |
| AC.PA, 2020-10-19 | close | 23,22 | 23,23999977 |
| AIR.PA, 2020-10-19 | close | 66,19 | 65,72000122 |

Ces différences ne sont pas seulement un problème d'arrondi en virgule flottante.
Elles ne déterminent pas quel fournisseur est correct. Augmenter arbitrairement
la tolérance ou prendre systématiquement Yahoo/EODHD ne constitue pas une
réparation vérifiée. La présence d'OHLCV dans une archive ne suffit pas à lever
le contrôle de corroboration.

## Vérifications effectuées et limites

Le masque de complétude recalculé correspond exactement au masque du panel gelé.
Les tests existants de formules, de fenêtres consécutives et de causalité des
features passent. Aucun défaut de calcul justifiant une correction des valeurs
n'a été démontré pendant cette intervention. Cela ne remplace pas une validation
indépendante de tous les prix ni une preuve PIT complète.

Les 68 candidats avec une ligne de manifeste absente restent exclus ; on ne
transforme pas une absence en admission. Les conflits MIC restent également
signalés. Aucun patch au calcul des features n'a été appliqué uniquement pour
améliorer le pourcentage de couverture.

## Déblocage possible

**Complément du 3 octobre 2026 :** une correction officielle gratuite des
clôtures du 19 octobre 2020 a été trouvée et rapprochée de 84 titres.
Elle corroborre EODHD seul pour 78 clôtures, les deux fournisseurs pour quatre,
et aucun pour deux. Le fold reste bloqué : voir le
[rapport 10-C2](sprint_10c2_audit_prix_independants.md) pour les limites OHLCV,
les conventions de séries et les preuves ESMA toujours manquantes.

1. **Preuves ESMA historiques** : retrouver les archives manquantes auprès d'une
   autre archive officielle ou obtenir une confirmation documentaire du statut
   de publication de ces journées. Une preuve vérifiable doit identifier la date,
   la couverture et la provenance. Un Full ultérieur n'est pas rétrodaté.
2. **Prix divergents** : obtenir une troisième source historique indépendante
   pour les dates/titres en désaccord, idéalement les prix officiels Euronext, puis
   déterminer quelle version est justifiée. La résolution doit porter sur tous
   les cas d'une même anomalie documentée, pas sur un titre choisi pour franchir
   le seuil.
3. **Reconstruction** : après preuves nouvelles, reconstruire le manifeste,
   les snapshots de liquidité et les panels/labels sous de nouveaux hashes et
   répertoires, avec comparaison avant/après. Les sources gelées sont conservées.
4. **Requalification** : vérifier à nouveau toutes les phases du fold 3 avec
   les gates inchangés, avant toute génération de scores Oracle OOF.

À défaut de preuve nouvelle, il faut conserver ce fold bloqué. Un nouveau plan
de fenêtres pourrait faire l'objet d'un protocole de recherche distinct, mais
ne doit pas être présenté comme une réparation du fold existant.

## Livrables et commandes

Script : `modelFactory/fr_fold3_repair_audit.py`.
Tests dédiés : `tests/test_fr_fold3_repair_audit.py`.

Rapport exécuté :
`artifacts/fr/research/fold3_repair/fr-fold3-repair-4ccc07603d2f/report.json`.
Le fichier `row_diagnostics.parquet` contient les 14 997 lignes avec les features
manquantes et les dates/raisons des obstacles de leurs deux fenêtres.

```powershell
# Diagnostic local uniquement
python -m modelFactory.fr_fold3_repair_audit

# Diagnostic + vérification des sources officielles (lecture réseau)
python -m modelFactory.fr_fold3_repair_audit --probe-official
```

Le script vérifie les hashes du panel, des labels et du manifeste ; il ne répare
pas silencieusement ces sources. Un dossier existant n'est jamais écrasé. Sans
nouveaux probes réseau, utiliser un `--output-root` distinct pour répéter un
diagnostic identique. Les dates de contrôle réseau sont archivées et font varier
l'identifiant d'une nouvelle vérification.

**105 tests ciblés FR passent**, dont trois nouveaux tests garantissant qu'une
preuve manquante ou rejetée n'est pas admise, que le manifeste reste inchangé et
que seules les fenêtres/titres demandés sont examinés.
