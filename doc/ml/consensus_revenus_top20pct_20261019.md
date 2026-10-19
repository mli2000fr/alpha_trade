# Consensus de revenus seuls — extension au TOP20 % Oracle

## Conclusion

**Extension calculée et auditée, sans résultat d'efficacité pour le moment.**
Le classement disponible comporte 1 743 titres : `ceil(20 % × 1 743)` donne
**349 titres**, retenus avant de regarder leur couverture consensus. Les dix
premiers restent séparés des rangs 11 à 349 ; ils ne sont pas remplacés si une
preuve manque.

Sur ces 349 titres, **346 ont une paire de snapshots `0q` comparable**.
Parmi les paires techniquement cohérentes et à nombre d'analystes revenus
inchangé, on observe **36 hausses et 28 baisses de prévisions**. Ces 64 variations
ne sont ni 64 trades qualifiés, ni 64 prédictions correctes.

Les seules variations disposant de l'appui documentaire devise/période prévu
dans le dossier restent DOCN et FUN. L'élargissement révèle davantage de
candidats à qualifier, **pas encore un avantage directionnel démontré**.

## Sources et protocole

Extension distincte du [pilote TOP10](consensus_revenus_observes_20261019.md),
qui reste inchangé, ainsi que ses artefacts scellés.

Dossier : `artifacts/research/us_consensus_revenue_top20/20261019-v1/`.
Protocole figé le **19 octobre 2026 à 21:24:53 UTC / 23:24:53 Paris**, avant
tout accès à des résultats futurs de cette expérience.

- Même source immuable : observations réellement collectées du 11 au
  18 octobre ; aucune ancienne version du consensus inventée.
- Univers : fichier figé `config/univers_batch/univers_filtred_tradable.txt`,
  1 790 titres ; dénominateur du TOP20 % = les **1 743 scores disponibles**,
  pas le nombre de lignes de consensus ni les seules paires valides.
- Oracle parcours H20 : `model-factory-20261016180250-3b0515`, scores du
  16 octobre créés le 17, disponibles avant l'ouverture du 19.
- Une seule cohorte sélectionnable dans ce dossier : entrée du **19 octobre**.
  Les dates sans score contemporain restent manquantes, sans reprise du score
  du 16 pour les entrées précédentes ou suivantes.
- Score décroissant, symbole croissant en cas d'égalité ; modèle, cible,
  horizon, disponibilité et unicité du classement contrôlés.
- Même règle revenus seuls : hausse stricte → motif LONG ; baisse stricte →
  motif SHORT ; stabilité, absence ou comparaison non qualifiée → abstention.
  Aucun EPS utilisé, aucun seuil optimisé.
- Même émetteur, fournisseur, période fiscale et `0q`, dernier état disponible
  avant chacune des deux ouvertures NYSE successives. La disponibilité inclut
  la fin du run, pas seulement la date fiscale ou l'heure de l'item.
- Au moins trois analystes revenus à chaque borne ; nombre inchangé dans le
  groupe primaire. Les changements de nombre sont séparés, même s'ils donnent
  une forte variation de moyenne. Nombre constant ≠ mêmes analystes garantis.
- La devise et la période des sociétés non revues restent inconnues. Une
  cotation US ne permet pas de supposer USD. Le dernier ancrage `0q` reste un
  candidat, pas une preuve que la période est courante et non encore publiée.

Cette extension est **exploratoire** : elle est décidée après examen des
features du TOP10 et après l'entrée du 19. Elle n'est pas une validation
indépendante pré-enregistrée et ne qualifie aucune entrée live.

## Couverture et variations descriptives

| Périmètre | Sélectionnés | Paires présentes | Paires techniquement cohérentes | Revenus en hausse, analystes inchangés | Revenus en baisse, analystes inchangés |
|---|---:|---:|---:|---:|---:|
| TOP10 | 10 | 10 | 10 | 1 | 2 |
| Rangs 11–349 | 339 | 336 | 328 | 35 | 26 |
| TOP20 % complet | **349** | **346** | **338** | **36** | **28** |

Le TOP20 % complet est l'union des deux premiers groupes, **pas un troisième
échantillon indépendant**. La table décrit des variations du consensus ; elle
ne contient aucun taux de succès boursier.

Parmi les 338 paires techniquement cohérentes :

- 64 variations à nombre inchangé et ≥3 analystes : 36 hausses / 28 baisses ;
- 233 revenus inchangés avec nombre inchangé et ≥3 analystes ;
- 26 variations avec changement du nombre d'analystes : 13 hausses / 13 baisses ;
- 15 observations stables avec nombre absent ou inférieur à trois.

Réserves conservées, sans remplacement par les titres de rang suivant :

- **Trois paires absentes** : TKOMY, rang 42 ; HUBG, rang 164 ; AA, rang 225.
- **Huit paires techniquement réservées**, faute de revenu positif exploitable
  à une borne au moins : SSTK, MLTX, SA, PCVX, XENE, IMVT, EGO et SNEX.
- Devise/période non qualifiées dans ce dossier pour 347 des 349 titres, dont
  les cas absents. Les motifs se chevauchent ; leurs nombres ne s'additionnent
  pas pour former un total d'exclusions.

Les rangs les plus élevés parmi les 64 variations à qualifier sont notamment
CCOI (1), FUN (4), DOCN (10), STRL (17), STX (18), CWH (26), SDGR (32), TWLO (39)
et PRIM (40). Ce classement de travail utilise les features et le rang Oracle,
jamais le rendement futur. Aucun de ces noms n'est une recommandation d'achat.

## Vérification des archives

La vérification ne se limite plus à un échantillon de paires : les **692 lignes
normalisées** des 346 paires présentes ont été rapprochées de **518 enveloppes**
du fournisseur déjà conservées dans `pit_raw_payloads`.

Contrôles : statut HTTP, hash du corps, présence du hash de chaque item,
émetteur/période/horizon, valeurs normalisées des revenus, horodatages avant
les décisions et disponibilité du run terminé. **346/346 paires raccordées,
aucune enveloppe invalide.** Cela valide la traçabilité des montants, pas leurs
conventions fiscales ou leur pouvoir prédictif.

Lecture SQL uniquement des enveloppes existantes, transaction READ ONLY /
REPEATABLE READ, UTC puis ROLLBACK. Aucun appel fournisseur ou LLM, aucun
téléchargement supplémentaire, aucune écriture SQL.

## Motifs documentés et maturité

| Titre | Rang | Variation relative du revenu estimé | Analystes revenus | Motif de recherche |
|---|---:|---:|---:|---|
| DOCN | 10 | +0,0217 % | 15 → 15 | LONG |
| FUN | 4 | −0,1736 % | 13 → 13 | SHORT |

Ces valeurs et les deux motifs sont identiques au pilote TOP10. Les 62 autres
variations à nombre inchangé restent descriptives tant que les réserves
devise/période ne sont pas levées. Les 26 changements de nombre ne leur sont
pas ajoutés. Les appuis du support reçus après l'entrée ne sont pas présentés
comme des preuves utilisées en production avant cette entrée.

Cible d'évaluation conservée : **TP10 avant SL5 pendant dix séances NYSE à
partir de l'ouverture d'entrée**, expiration à la dixième clôture, gaps
conservés, priorité à la perte en cas d'ambiguïté intrajournalière. Il ne s'agit
pas ici des déciles de rendement terminal H20 ; l'Oracle H20 sert au préfiltre
d'amplitude. Les bras futurs devront partager les mêmes prix, coûts et règles.

**Zéro résultat H10 mature** pour cette cohorte. Sa dixième clôture est le
**30 octobre 2026, 20 h UTC / 21 h Paris**, sous réserve de prix qualifiés.
Pas de win-rate, AUC ou PnL calculé, pas de signal promu.

## Suite bornée

1. Prioriser la qualification devise/période des 62 variations encore réservées,
   en ordre Oracle, à partir de preuves adéquates ; ne pas qualifier d'office
   tous les titres et ne pas supprimer les réserves pour grossir l'échantillon.
2. Conserver de nouveaux snapshots et classements Oracle contemporains. Les
   collectes existantes ne sont pas modifiées par ce script ; il ne crée pas
   automatiquement une nouvelle cohorte chaque jour.
3. À maturité, évaluer sans changer TP/SL ou choisir les titres sur leur résultat.
   Présenter séparément TOP10 et rangs suivants, et analyser la dépendance
   entre dates/titres ainsi que les épisodes sans chevauchement.
4. Garder la confirmation sur de nouvelles dates : au moins 50 séances d'entrée
   et 100 épisodes qualifiés sans chevauchement, sans utiliser les 349 titres
   du 19 comme substitut à cette durée. La confirmation TOP10 reste distincte.

Pas d'automation, entraînement, changement de batch/modèle/configuration ou ordre.

## Livrables et tests

- `scripts/research/us_consensus_revenue_top20.py` : phases `build`, `proofs`,
  `finalize`, `audit` (préparation implicite ou `prepare`) dans un dossier neuf.
- `protocol.json`, `cohort.parquet`, `qualified-cohort.parquet`, `cohort.csv`,
  `proof-request.json`, `raw-receipts.parquet`, `oracle-coverage.json`,
  `report.json` et `audit.json` dans le dossier de l'extension.
- `cohort.csv` contient tous les rangs, valeurs, motifs bruts et motifs
  qualifiés, avec les réserves explicites ; pas de rendement futur.
- **234 tests ciblés passent**, dont 23 nouveaux pour cette extension. Audit
  scalaire des 349 rangs, dates, comparaisons et qualifications : PASS.

Cette revue technique est réalisée par le même assistant : elle n'est pas une
seconde revue humaine indépendante. Aucun calcul ne reste en cours.
