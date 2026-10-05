# Sprint 15-F — Pilote INPI comptes annuels

**État actuel après extension :** le batch recherche les correspondances sur les
330 identités S6C et collecte par lots les 254 correspondances retenues, en
quarantaine uniquement. Les sections « dix émetteurs » ci-dessous conservent
l'historique du pilote, elles ne décrivent plus la portée actuelle. Voir
[extension, exclusions, quotas et reprise](inpi_univers_collecte_securisee.md).

## Accès validé le 5 octobre 2026

`INPI_USERNAME` et `INPI_PASSWORD` sont configurés hors YAML. Le client lit
l'environnement puis les variables utilisateur Windows sans exposer les secrets.
TLS est vérifié ; les redirections sont refusées. Le token reste en mémoire.

Le login et les routes directes `/bilans` et `/bilans-saisis` fonctionnent.
Le 403 des routes générales des entreprises signifie des droits différents,
pas une impossibilité de récupérer les comptes autorisés.

Preuve réelle :
`artifacts/fr/operations/validation_15f/20261005T194709-4a5b8fc3/report.json`.
Statut `ACCESS_VERIFIED`, six appels, zéro écriture SQL. Émetteur vérifié :
AB SCIENCE, AB.PA, FR0010557264, SIREN 438479941, d'après son
[rapport financier](https://www.ab-science.com/wp-content/uploads/2024/11/RFS_AB_Science_S12024_18_11_2024_EN.pdf).

| Exercice/type | Pages | Cellules | Valeurs non vides |
| --- | ---: | ---: | ---: |
| 2020 / C | 6 | 87 | 207 |
| 2021 / C | 5 | 86 | 205 |
| 2021 / K | 4 | 34 | 68 |

Trois références PDF et trois comptes saisis reçus, trois comptes saisis lus.
Le curseur indique d'autres pages : ce n'est pas un historique exhaustif.
C désigne les comptes sociaux complets ; K les comptes consolidés. Les C ont
`codeSaisie=01` (incohérences source), le K `00`. Ces compteurs prouvent la présence
de données, pas leur validité comptable. Ne pas mélanger social et consolidé.

## Sécurité et PIT

Le pilote conserve un résumé public, des codes CERFA et le SHA256 du JSON.
Ni PDF ni JSON intégral ni profil de connexion ne sont archivés. Les documents
retirés/non publics sont refusés. Le smoke est limité à AB SCIENCE pour éviter
d'attribuer à un autre SIREN cette identité vérifiée.

Clôture, dépôt, modification et observation sont distincts. Un compte ancien
retourné aujourd'hui n'est pas automatiquement un vintage disponible au dépôt.
La disponibilité du smoke est datée après réception ; le premier rapport est
une preuve d'accès, pas une certification PIT historique.

## Avant activation générale

La promotion générale des fondamentaux reste interdite. La collecte en
quarantaine a été activée ensuite, selon la section finale ci-dessous. Pour
utiliser effectivement ces comptes dans l'application, il faut encore :

1. Étendre la vérification ISIN → personne morale/SIREN du pilote à l'univers, sans confondre
   groupe coté et filiale dont le site porte les mentions légales.
2. Mesurer couverture, confidentialité, social/consolidé et exercices accessibles.
3. Implémenter pagination, quotas, reprise, versions et retraits réglementaires.
4. Normaliser CERFA, unités, devise, durée et contrôles comptables.
5. Qualifier les dates réellement disponibles et le contrat de stockage avant
   création de tables/migrations ; tester idempotence et notifications.

INPI ne remplace pas consensus analystes, borrow ou options. Aucun gain D1/D10
n'est démontré à ce stade.

Commande du smoke initial : `python -m service.inpi.accounts_smoke`.
Rapports uniques sous `artifacts/fr/operations/validation_15f`, sans SQL.
Contrat : [documentation officielle v6.1](https://www.inpi.fr/sites/default/files/2026-09/documentation%20technique%20API_comptes_annuels%20v6-1-AA.pdf).

## Pilote dix émetteurs réalisé le 5 octobre 2026

Le pilote autorisé est terminé, sans écriture SQL, sans entraînement, sans
activation ni modification d'une tâche Windows. Les dix correspondances ont été
rapprochées des identités locales qualifiées pour la recherche et de publications
légales des émetteurs. Il ne s'agit pas d'un référentiel légal exhaustif certifié.

Les preuves d'identité et alias acceptés sont dans `config/inpi_pilot_fr.json`.
La référence locale est `artifacts/fr/sprint6c_reference/identities.jsonl.gz` ;
son hash figure dans le rapport. Un SIREN désigne la personne morale, pas le
groupe économique : Arkema SA utilise 445074685, pas Arkema France 319632790.

| Symbole | ISIN | SIREN | Personne morale vérifiée |
| --- | --- | --- | --- |
| AB.PA | FR0010557264 | 438479941 | AB Science |
| ABCA.PA | FR0004040608 | 400343182 | ABC Arbitrage |
| AC.PA | FR0000120404 | 602036444 | Accor |
| ADOC.PA | FR0011184241 | 487647737 | Adocia |
| AKE.PA | FR0010313833 | 445074685 | Arkema |
| BB.PA | FR0000120966 | 552008443 | Société BIC |
| BN.PA | FR0000120644 | 552032534 | Danone |
| OR.PA | FR0000120321 | 632012100 | L'Oréal |
| SU.PA | FR0000121972 | 542048574 | Schneider Electric SE |
| UBI.PA | FR0000054470 | 335186094 | Ubisoft Entertainment |

### Résultats et portée

Rapport brut de contrôle :
`artifacts/fr/operations/inpi_pilot/20261005T200549-71b34631/report.json`.
Rapprochements indépendants des chiffres : `financial_review.json`, dans le
même dossier. Le rapport initial est conservé sans modification.

- 109 appels, dix émetteurs accessibles, 40 comptes structurés publics lus.
- Pagination des deux listes terminée dans le budget pour chaque SIREN.
  Cela signifie seulement que ces routes n'ont plus retourné de page suivante,
  pas que tous les comptes de la société sont disponibles dans INPI.
- 36 égalités actif/passif, trois échecs et une égalité non vérifiable.
- Neuf comptes sans réserve dans les contrôles techniques implémentés ;
  31 nécessitent une revue. Aucun des 40 comptes n'est entièrement certifié.
- Douze rapprochements de chiffres, sur dix sociétés : onze concordent,
  un diverge. Ce ne sont pas douze validations d'exercices complets.

Les deux comptes sociaux les plus récents et les deux consolidés les plus
récents disponibles sont examinés. Deux documents du même exercice peuvent
donc être sélectionnés : c'est volontaire pour détecter les versions, et non
la preuve de deux années distinctes. Les documents retirés/non publics sont
exclus. Une liste tronquée par le budget est signalée non exhaustive.

### Comment lire les chiffres

Le parseur applique uniquement les layouts C/K. Les codes viennent de la
documentation INPI ; il ne devine pas les rubriques par leur position.

| Champ de recherche | Cellule N | Signification / réserve |
| --- | --- | --- |
| `assets_net` | CO / m3 | Total actif net |
| `liabilities_total` | EE / m1 | Total du passif **incluant les capitaux propres**, pas dette financière seule |
| `equity` | DL / m1 | Capitaux propres de la liasse |
| `cash` | CF / m3 | Disponibilités de la liasse, pas automatiquement une mesure IFRS universelle |
| `revenue` | FJ / m3 | Total chiffre d'affaires ; sémantique à revoir pour sociétés financières |
| `income` social C | DI / m1 | Résultat social |
| `income` consolidé K | P2 / m1 | Résultat part du groupe |

`amounts_source_units` conserve exactement les montants saisis : pas de
multiplication automatique par 1 000, ni de remplacement par un chiffre voisin.
Un champ vide reste `null`, jamais zéro. Une devise EUR ne prouve pas que la
cellule est exprimée en euros plutôt qu'en milliers d'euros. L'équilibre du
bilan ne prouve pas l'unité ni la justesse des autres rubriques.

### Vérifications externes ciblées

Les montants attendus, unités du document, cellules et tolérances sont figés
dans `config/inpi_pilot_financial_checks_fr.json`. Pour les publications
arrondies à 0,1 million EUR, la tolérance absolue est 50 000 EUR ; les autres
comparaisons utilisent les montants publiés convertis explicitement en euros.

| Émetteur | Contrôle | Résultat |
| --- | --- | --- |
| AB Science | CA consolidé 2021 1,607 M€, actif 21,271 M€ | Deux concordances |
| ABC Arbitrage | Résultat consolidé 2024 26,8 M€, arrondi | 26,845 M€ dans la tolérance |
| Accor | CA consolidé 2024 5 606 M€ | Concordance |
| Adocia | CA consolidé 2024 9,320 M€ | Concordance |
| Arkema | CA consolidé 2024 9 544 M€ | Concordance |
| BIC | CA consolidé 2024 2 196,6 M€, arrondi | 2 196,635 M€ dans la tolérance |
| Danone | CA consolidé 2024 27 376 M€ | Concordance |
| Danone | CA consolidé 2025 27 283 M€ publié | INPI 27 376 M€ : écart +93 M€, revue requise |
| L'Oréal | CA consolidé 2024 43 486,8 M€ | Concordance |
| Schneider Electric | CA consolidé 2024 38 153 M€ | Concordance |
| Ubisoft | CA IFRS15 exercice clos mars 2025 1 899,2 M€ | Concordance ; ne pas utiliser les net bookings à la place |

Chaque lien primaire et repère de lecture est conservé dans le manifeste
des contrôles et recopié dans `financial_review.json`. Les documents officiels
sont indépendants du JSON INPI, mais cette lecture par le même opérateur ne
constitue pas une seconde revue humaine indépendante.

### Anomalies à arbitrer avant toute utilisation automatique

1. **Danone, comptes sociaux 2022/2023** : le contrôle actif/passif échoue,
   et l'actif net 2023 est négatif (-421 M€). Ne pas rendre ces lignes utilisables.
2. **L'Oréal social 2025** : actif 35,5515 Md€ contre passif 355,515 Md€,
   rapport dix. Le code source signale déjà des incohérences. Aucun redressement
   automatique n'a été appliqué.
3. **Danone consolidé 2025** : le CA 27,376 Md€ reproduit le montant publié
   pour 2024 ; le communiqué 2025 annonce 27,283 Md€. Cela indique une cellule,
   un exercice ou une saisie à vérifier, pas une autorisation de réaffecter
   arbitrairement le montant à N-1.
4. **Schneider social 2024** : actif 22 809 180 dans les unités source,
   contrairement aux montants en milliards des exercices voisins. Suspect
   d'échelle, mais non certifié : comparer le compte social officiel avant
   toute conversion. Un bilan équilibré ne suffit pas.
5. **BIC consolidé 2024** : deux versions, actif 2,838733 Md€ versus
   2,834556 Md€ ; trésorerie présente dans une version et absente dans l'autre.
   La version la plus récemment modifiée ne peut pas être rétrodatée au dépôt
   de la première pour un backtest.
6. **Ubisoft social mars 2025** : cellules essentielles vides et code de
   saisie 19. Présence d'un document ne signifie pas présence d'un bilan exploitable.
7. **Couverture** : le pilote ne retrouve pour AB Science que des exercices
   structurés allant jusqu'à 2021 ; d'autres publications existent. Plusieurs
   résultats/trésoreries sont absents ailleurs. Ne pas transformer ces lacunes
   en zéros ni extrapoler 10/10 à tout l'univers.

### PIT et prochaines étapes

`available_at` est l'observation effective **après** réception du document.
`dateCloture`, `dateDepot`, `updatedAt` et cette observation sont distinctes.
Le pilote est prospectif au 5 octobre 2026 : il ne permet pas d'injecter ces
versions actuelles dans des backtests 2018–2025 sans qualifier leurs vintages.

Avant activation : arbitrer les anomalies sur les comptes officiels, figer
les conversions et périmètres consolidés, choisir une politique de versions
et retraits, puis implémenter stockage séparé FR, reprise/idempotence et
notifications. L'accès fournisseur est débloqué ; la qualification comptable
et PIT ne l'est pas encore. L'activation ultérieure du batch concerne uniquement
la quarantaine décrite ci-dessous, pas les données utilisables. Aucun gain
D1/D10 n'est démontré.

### Reproduire sans toucher à la base

```powershell
python -m service.inpi.accounts_pilot
python -m service.inpi.pilot_review --report artifacts/fr/operations/inpi_pilot/20261005T200549-71b34631/report.json
python -m pytest tests/test_inpi_accounts_smoke.py tests/test_inpi_accounts_pilot.py --no-cov -q
```

Le pilote crée un dossier unique ; il est limité à dix sociétés, quatre pages
de dix documents par route/SIREN et quatre comptes détaillés par société. Il
ne télécharge pas de PDF ni ne conserve le JSON intégral ; seules les rubriques
publiques sélectionnées, métadonnées et hashes sont enregistrés. Une seconde
exécution du rapprochement refuse d'écraser `financial_review.json` existant :
conserver/renommer la revue précédente avant relance si nécessaire.

Validation locale : **23 tests ciblés passants**, sans nouvel appel réseau.

## Activation de la collecte sécurisée — 05/10/2026

Après GO utilisateur, `fr_fundamentals_sync` est **activé dans `batch_fr.yaml`**,
avec `status: ACTIVE_RESEARCH`, `collection_mode: quarantine_only`, quotidien
du lundi au vendredi à **20:00 Europe/Paris**. La clôture boursière n'est pas
nécessaire pour des comptes annuels : on observe les documents disponibles.
Les tâches Windows ne sont pas installées automatiquement par cette évolution.

### Avertissement visible dans l'IHM

Dans **Workflow & Orchestration → Batch → France**, le commentaire en encadré
d'avertissement indique en gras :

**COLLECTE UNIQUEMENT — COMPTES EN QUARANTAINE. NON UTILISABLES PAR LE ML,
LES BACKTESTS OU LE LIVE.**

Il précise les dix sociétés concernées, l'absence d'écriture SQL et la nécessité
de qualifier unités, exercices, versions et disponibilité PIT. L'état actif
signifie que la collecte peut fonctionner, **pas** que les données sont validées.

### Ce qui est réellement archivé

Le client `service/inpi/secure_collection.py` s'intègre au runner FR existant,
sans connexion SQL et sans modification des modèles. Il archive désormais le
JSON public complet d'un compte sélectionné, afin de permettre une qualification
future reproductible. Le pilote initial, lui, ne conservait que des résumés.

Les objets sont sous
`artifacts/fr/operations/fr_fundamentals_sync/quarantine/objects/<SHA256>.json`.
Les versions identiques partagent un seul objet : la relance vérifie son hash
et ne le réécrit pas. Les contenus différents restent distincts. Chaque passage
conserve séparément son manifeste d'observation, ses références et ses contrôles
dans `observations/<horodatage>/`. Les rapports de run sont enregistrés par le
runner dans `operations/runs/fr_fundamentals_sync` et visibles dans la page Batch.

Tous les documents, y compris ceux sans incohérence comptable détectée, portent
dans le manifeste `qualification_state=QUARANTINED_UNQUALIFIED`,
`ml_usable=false`, `canonical_go=false`, `historical_pit_qualified=false`.
Les consommateurs ML/backtest existants ne lisent pas ce nouveau stockage.
Aucune table métier, migration ou nouvelle feature n'est créée.

Les documents retirés, confidentiels, hors SIREN autorisé, à dénomination non
rapprochée ou à confidentialité interne non publique sont refusés. Login,
profil utilisateur et token ne sont jamais archivés. Un retrait futur n'efface
pas automatiquement les anciennes preuves archivées : une gestion formelle
des retraits et des droits reste obligatoire **avant toute promotion**.

La portée reste le manifeste vérifié de dix sociétés, pas les 330 titres FR.
Maximum : 130 appels et 128 Mio par passage, quatre pages de dix références
par route/SIREN, puis deux comptes sociaux et deux consolidés. Un verrou empêche
les passages simultanés. Un budget atteint ou un échec fournisseur produit un
échec visible ; les comptes déjà reçus restent en quarantaine.

### Compteurs et notifications

`demandés` compte les émetteurs ; `reçus/persistés` compte les observations de
comptes publics archivés, pas seulement les nouveaux fichiers. `new_objects_count`
indique le nombre d'objets nouveaux ; `quarantined_count` la quarantaine.
La même observation peut donc être persistée à plusieurs passages sans dupliquer
l'objet documentaire. Les incohérences comptables sont détaillées dans le
rapport (`qualification_issues_count`) ; elles ne sont pas des erreurs de
transport et ne rendent pas la collecte brute échouée à elles seules.

L'installation et le lancement depuis l'IHM utilisent le wrapper FR commun :
compteurs, mail et Telegram selon leur configuration existante. Un lancement
Python direct émet les compteurs mais ne déclenche pas lui-même ces notifications.

### Utilisation

Installer/réinstaller **ce batch FR** depuis la page Batch pour programmer les
passages ; le bouton « Lancer immédiatement » autorise la collecte manuelle.
Pour vérifier la configuration sans réseau ni écriture :

```powershell
python -m service.fr.operational_batch_15a --batch fr_fundamentals_sync --dry-run
```

Pour une collecte manuelle des dix sociétés, sans les notifications du wrapper :

```powershell
python -u -m service.fr.operational_batch_15a --batch fr_fundamentals_sync
```

La qualification progressive est un travail distinct : choisir document,
périmètre/exercice, unité et champ ; les rapprocher des publications ; arbitrer
les réserves ; qualifier les versions et dates de disponibilité. Aucun bouton
ni option ne peut promouvoir automatiquement ces comptes aujourd'hui.

Validation réelle après activation : passage du 05/10/2026 à 22:20 Paris,
**10 émetteurs / 40 observations publiques archivées / zéro échec**, 109 appels,
227 953 octets de JSON. Rapport :
`artifacts/fr/operations/fr_fundamentals_sync/observations/20261005T202032544976Z/report.json`.
Le smoke immédiatement précédent avait archivé quatre objets AB Science ;
le passage complet les a réutilisés et n'a créé que 36 nouveaux objets. Les
40 comptes restent en quarantaine, dont 31 avec des réserves techniques.
**48 tests ciblés passants** après intégration : client, contrôles, archive,
budgets, confidentialité, idempotence, runner FR et catalogue IHM.
Vérification élargie aux collecteurs FR existants : **69 tests passants**.
