# E21-A — Disponibilite PIT des revisions chiffrees de guidance

> **Archive d'une piste fermée.** E21 a été clôturée le 15 septembre 2026 au
> statut CLOSED / SUSPENDED_DATA_NOT_READY après les validations E21-B4 à B8.
> Ce document décrit l'audit initial ; il ne constitue plus un plan actif.

## Decision

Audit execute le 14 septembre 2026 : **BLOCKED_DATA_NOT_READY**. L'hypothese
directionnelle n'est ni validee ni rejetee. Aucun modele, poids, seuil ou
backtest n'a ete entraine ou optimise. Aucune table ou configuration de batch
n'a ete modifiee. Les consultations en base sont uniquement des SELECT.

Artefact : `artifacts/research/guidance_pit_availability/e21a-20260914-v1`.
Service : `service.forward_pit.guidance_audit` ; quatre tests cibles passent.

## Hypothese nouvelle et distinction avec les experiences precedentes

Mesurer une hausse/baisse des perspectives publiees par l'entreprise pour une
metrique et une periode fiscale identiques : chiffre d'affaires, EPS, marge,
EBITDA. Ce n'est ni le signe de la surprise EPS realisee (deja NO_GO), ni une
categorie de 8-K, ni un sentiment generique. Une nouvelle fourchette de revenus
ne constitue pas une revision si on ne connait pas l'ancienne fourchette pour
la meme periode. Une comparaison avec les revenus realises l'annee precedente
ne remplace pas cette ancienne guidance.

La premiere strategie a tester, si les donnees deviennent pretes, serait
event-driven et independante d'Oracle. Oracle pourrait etre un comparateur
secondaire a population et instant de decision identiques ; il ne doit pas
etre impose avant de savoir si le signal economique existe.

## Couverture observee

Univers : `config/univers_batch/univers_filtred_tradable.txt`, 1 798 symboles.

| Mesure locale | Resultat |
| --- | ---: |
| Depots dans sec_filing_raw | 2 050 |
| Dates de depot | 3 au 11 septembre 2026 |
| Depots lies a l'univers retenu | 203 |
| Annexes referencees dans sec_filing_documents | 1 311 |
| Annexes avec content_blob non NULL | 0 |
| Annexes sans acceptance_datetime du depot parent | 64 |
| Emetteurs de l'univers avec au moins deux dates de depot 8-K/6-K | 9 |
| Documents 8-K/6-K lies a l'univers, contenu <= 2 Mo | 147 |
| Echantillon lu : un document par emetteur, maximum 100 | 100 |
| Documents avec au moins un passage candidat | 23 |
| Passages candidats non confirmes | 69 |
| Paires ancienne/nouvelle guidance confirmees | 0 |
| Derniere barre quotidienne locale | 10 juillet 2026 |

Le dernier cours trouve en base est en juillet, mais la periode de recherche
disponible annoncee par l'utilisateur s'arrete au 30 juin 2026. Dans les deux
cas, les depots locaux de septembre sont posterieurs : aucune evaluation
historique directionnelle n'est possible sur ces documents avec les cours
actuellement disponibles. Ne pas utiliser un document de septembre pour une
decision de juin.

Les 69 passages ne sont pas 69 revisions. Le taux 23/100 n'est pas une
estimation representative de la frequence de guidance : echantillon borne,
deterministe, filtre par taille, emetteur et liaison au ticker. Les neuf
emetteurs multi-dates ne prouvent pas l'existence de neuf paires comparables.

## Blocage du collecteur d'annexes : URL des documents

Le dernier run `sec_edgar_incremental-20260914040003-5bfab1f9` indique
`discovered=1311`, `downloaded=0`, `oversized=2`. Le statut est
`COMPLETED_WITH_WARNINGS`. Les lignes en base sont donc des descripteurs de
documents, pas des annexes effectivement archivees.

Cause identifiee dans `service/forward_pit/batch.py` :

1. `_sec_filing_index_url` construit une page index au niveau du CIK.
2. `_download_sec_exhibits` passe le repertoire de cette page comme base URL.
3. `_sec_filing_index_documents` conserve uniquement le nom du fichier pour
   reconstruire les href non absolus, au lieu de resoudre leur chemin complet.

Les chemins `/Archives/edgar/data/CIK/ACCESSION_SANS_TIRETS/fichier.htm` perdent
donc le sous-repertoire de l'accession. Exemple d'erreur du run :
`https://www.sec.gov/Archives/edgar/data/1000230/ex_1014928.htm` renvoie 404.
Ce n'est pas une preuve que la source SEC est payante ou absente.

La [documentation SEC des chemins EDGAR](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
decrit ce sous-repertoire. Le correctif a implementer doit conserver les href
absolus ou racine-relatifs et resoudre les liens relatifs selon leur contexte,
avec validation du domaine SEC. Il devra etre teste sur ces trois cas, sur
les liens inline-XBRL eventuels et sur les index de depot. Aucun correctif de
ce collecteur ni reprise de ses runs n'a ete applique pendant cet audit.

## Lecture des documents principaux et verification de plausibilite

Certains `content_text` contiennent la soumission SGML complete, donc deja le
texte d'EX-99.1. Cela permet un smoke d'extraction meme quand les annexes
separees sont vides. D'autres contenus sont seulement le document principal :
ne pas supposer que tous incluent le communique de resultats.

Le repereur convertit HTML en texte visible, ignore scripts/styles, recherche
une mention de perspective avec une metrique et des nombres proches, et
conserve au plus cinq passages par document. C'est un outil de revue humaine
a rappel large, PAS un parseur de guidance valide. Les annees, montants et
pourcentages sont des indices, sans resolution automatique des unites.

Premiere revue qualitative des passages sauvegardes :

| Exemple | Ce qu'on observe | Ce qu'on ne peut pas en deduire |
| --- | --- | --- |
| OXM, 0000075288-26-000082 | baisse explicite de guidance ; ventes FY2026 1,430-1,470 milliard USD et EPS ajuste 1,60-2,00 USD | la comparaison FY2025 est un realise, pas l'ancienne guidance FY2026 ; delta non confirme |
| TTC, 0000737758-26-000041 | titre de communique annoncant une hausse de guidance annuelle | un titre ne donne pas les deux valeurs comparables |
| DOCU, 0001261333-26-000088 | hausse annoncee des perspectives FY2027 revenus/ARR | revenus et ARR sont deux metriques differentes ; pas de fusion en un delta |
| TSN, 0000100493-26-000067 | mise a jour de perspectives et pression sur les marges | le mot outlook n'est pas un label SHORT sans anciennes/nouvelles valeurs et calendrier |
| CASY, 0000726958-26-000084 | perspectives explicitement inchangees | ne pas classer toute nouvelle publication de guidance comme une hausse |
| AMBA, 0001193125-26-381923 | nouvelle guidance trimestrielle numerique | une prevision pour le trimestre suivant n'est pas une revision de la periode precedente |
| SFNC, 0001193125-26-381967 | projections de frais/restructuration et gains d'efficacite | ces projections ne sont pas directement une revision de revenu/EPS |
| NX | variations historiques de ventes proches d'un mot cle | realise historique, faux positif possible du repereur |
| ABBV | passage forward-looking/safe harbor mentionnant EPS guidance | clause generique, aucune valeur de revision validee dans ce passage |
| SBLK | outlook d'un tiers sur le marche du transport maritime | pas une guidance chiffree de l'emetteur |

Cette revue de passages ne constitue pas une annotation exhaustive des 69
extraits, une precision statistique du parseur ou une paire de revision
validee. `confirmed_revision_pairs=0` signifie qu'aucune paire n'a ete
confirmee ici, pas qu'aucune paire n'existe dans les documents complets.

## Contrat PIT requis avant toute cible ML

Une observation devra conserver CIK, ticker et validite historique du mapping,
accession, document, hash et passage source, metrique, base GAAP/non-GAAP,
periode fiscale cible et fin de periode, devise, unite, anciennes/nouvelles
bornes et date de publication de chaque prevision. EPS dilue et EPS ajuste
ne sont pas interchangeables. Marge en points de pourcentage != variation
relative. Refuser un delta relatif EPS quand l'ancienne valeur est proche de
zero ou change de signe sans regle economique pre-enregistree.

Une retractation de guidance est un evenement distinct : valeur absente !=
zero. Une reiteration est un evenement neutre, pas une nouvelle hausse.
Les corrections/amendements doivent etre versionnes, pas remplaces dans le
passe. Deduplication par source/accession et publication economique : un meme
communique repris dans un 8-K puis un 10-Q ne donne pas deux observations.

`acceptance_datetime` est une date d'acceptation SEC, pas necessairement celle
du communique original. Les champs DATETIME ne portent pas de timezone :
normalisation et verification ET/UTC restent obligatoires avant une entree.
Pour du live prospectif, la disponibilite ne doit jamais preceder la reception
du document et son traitement. `available_at` actuel represente la collecte.
Un backfill historique necessite un contrat d'archive historique distinct,
la preuve de publication et une latence de decision conservatrice ; ne pas
antidater arbitrairement les snapshots collectes aujourd'hui.

## Prochaine etape autorisable

1. Corriger la resolution des URL SEC et tester les liens ; reprendre les
   annexes sans contenu sans toucher aux batchs en cours.
2. Creer un POC de backfill borne de documents anterieurs au 30 juin 2026,
   independant du batch quotidien, d'abord sur quelques dizaines d'emetteurs.
   Recuperer au moins deux previsions de meme periode, y compris le
   predecesseur anterieur a la fenetre choisie.
3. Annoter manuellement un echantillon independant avec faux positifs et cas
   difficiles. Exiger la fidelite des nombres, periodes, GAAP, unites et sources,
   pas seulement la detection du mot guidance.
4. Mesurer le nombre de revisions uniques, emetteurs, annees et paires
   comparables. Pre-enregistrer les gates de couverture et qualite avant la
   lecture des rendements. Si insuffisant, rester BLOCKED, pas NO_GO ML.
5. Seulement apres DATA_READY : regle chiffree simple et OOF temporel, H5/H10/H20,
   entree apres disponibilite, benchmark meme secteur/date, net de couts,
   LONG/SHORT separes et controle des comparaisons multiples. Historique deja
   explore != confirmation independante. Ne pas faire un sweep de centaines
   de seuils ou lancer tout de suite un modele texte.

Les archives EDGAR sont accessibles gratuitement avec fair access et User-Agent
declare, mais gratuit ne signifie pas historique deja telecharge ni parseur
valide. Voir la [documentation officielle SEC](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).

## Reproduction

### Suite réalisée : correctif et smoke historique

Le blocage des URL décrit ci-dessus correspond à l'audit initial. Le correctif
est désormais appliqué ; 14 annexes historiques distinctes ont été récupérées
pour six émetteurs. Neuf comparaisons de mesures, représentant cinq paires de
publications, ont été revues manuellement ; leurs 18 fourchettes sont retrouvées
dans les textes. Le contrat PIT historique et l'extraction sémantique restent
à valider : ce n'est pas encore DATA_READY pour le ML.
Voir [backfill, valeurs vérifiées, exclusions et reproduction](guidance_historical_smoke_e21.md).

```powershell
python -u -m service.forward_pit.guidance_audit --universe-file config/univers_batch/univers_filtred_tradable.txt --sample-limit 100
```

Repertoire neuf horodate, sans ecrasement : `report.json`,
`manual_review_candidates.json`, `manual_review.md`. Pas de telechargement
reseau par ce service, pas de PDF/OCR, pas de nouvelles tables et pas d'usage
en prediction ou serving. Un premier essai SQL REGEXP sur les LONGTEXT avait
atteint le timeout MySQL ; le service final lit les contenus bornes et scanne
cote client, sans modifier les limites ou parametres du serveur.
