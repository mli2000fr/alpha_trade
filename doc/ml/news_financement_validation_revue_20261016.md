# News US : collecte validée et revue bornée du financement — 16 octobre 2026

**Clôture du diagnostic figé** : [bilan final des 40 textes éligibles et 73 associations](news_financement_cloture_corpus_20261016.md),
sans événement nouveau entièrement qualifié pour l'expérience et sans nouveau
backtest. Les constats ci-dessous restent ceux de la première revue.

**Actualisation ultérieure** : le rattrapage ciblé a terminé (4 776 barres,
10 fenêtres complètes sur le premier lot). Une [seconde revue bornée](news_financement_seconde_revue_20261016.md)
de 30 textes nouveaux est également livrée, sans événement primaire entièrement
qualifié du titre associé. Les décomptes ci-dessous restent le constat daté du
premier audit avant rattrapage, pas l'état courant de toutes les barres.

**Suite livrée le même jour** : [diagnostic d'identité et préparation intraday](news_financement_identites_intraday_20261016.md).
Cause des trous explicitée : historiques locaux arrêtés au 9 octobre, plans
jusqu'au 10, donc hors annonces 14–16. Garde-fou de recherche sans approbation
automatique et demande de rattrapage de 15 titres préparés, pas de collecte lancée.

## Conclusion

**L'alimentation est validée sur le cycle, pas le signal directionnel.**
La collecte complète couvre les 1 790 titres du fichier courant. Le corpus
archivé est figé sans troncature. Les 20 couples présélectionnés et 10 témoins
ont été lus : **aucun événement de financement primaire entièrement qualifié**
dans cet échantillon. Ce n'est pas la preuve d'absence d'événement dans le
corpus non relu, ni un résultat négatif de backtest.

La vérification intraday ne permet pas encore de mesurer une réaction : aucune
fenêtre complète de barres 5 minutes sur ces 30 couples. Pas d'entraînement,
calcul de rendement, backtest économique, nouvel appel fournisseur, GPT,
DeepSeek, écriture SQL, ordre ou changement de batch pendant ce travail.

## 1. Fin et validation de la collecte

Run : `eodhd_news_ingestion_sync-20261016121131-5ed4d540`, lancé à 14h11 Paris,
terminé le 16 octobre à **14h59:49 Paris**, durée launcher 48 min 18 s.
La fin SQL, le rapport local et le launcher sont concordants ; notifications
email/Telegram OK consignées. Le succès n'est pas déduit d'un fichier seul.

| Mesure | Valeur |
| --- | ---: |
| Titres du fichier courant | 1 790 |
| Terminés par ce passage | 1 005 |
| Déjà terminés dans le cycle, ignorés | 785 |
| Échecs / titres restants | 0 / 0 |
| Occurrences d'articles reçues | 7 028 |
| Nouvelles versions brutes archivées | 3 568 |
| Titres sans article conservé | 202 |
| Tentatives HTTP | 1 018 |

Audit final SQL **READ ONLY**, schéma `alpha_trade`, timeout serveur 15 s :

- `pit_collection_runs.status=COMPLETED`, cinq compteurs SQL/fichier égaux ;
- **1 790 checkpoints réussis** dans l'univers et le cycle concernés ;
- 6 558 versions de mapping de ce passage contrôlées ;
- zéro reçu de mapping non scellé, référence brute absente ou fournisseur incohérent.

Verdict : `VALIDATED_COLLECTION_ONLY`. Empreinte du fichier univers courant
conservée ; la taille égale ne certifie pas à elle seule sa composition
historique au début de chaque passage. Le dernier run valide le cycle via
reprise ; il n'a pas interrogé les 1 790 titres à la même heure.

Preuve :
`artifacts/research/us_news_financing_feasibility/full-run-validation-20261016-success-v1/report.json`.
Les anciens rapports FAILED et le run orphelin réconcilié restent des preuves
datées ; ils n'ont pas été réécrits en succès.

## 2. Périmètre temporel et export exhaustif

- Publications recherchées : à partir du **14 octobre 2026 à 00h00 UTC**.
- Borne figée : **16 octobre à 13h48:49.600646 UTC**, soit 15h48:49 Paris,
  après la fin de collecte et avant la préparation de la revue.
- Sources : versions immuables et reçus `PROVIDER_COLLECTION`, jamais une
  reconstitution depuis les seules projections courantes de news/sentiment.
- L'export conserve également les publications plus anciennes reçues dans
  cette période ; elles restent explicitement réservées, pas des annonces nouvelles.

6 720 articles distincts dépassaient la limite de 5 000 par lecture. Export
en quatre intervalles d'identifiants disjoints, ouverts à droite, sous la même
transaction de lecture : **1 740 + 1 632 + 1 688 + 1 660 = 6 720**. La somme et
l'union sont comparées au décompte SQL total ; aucune partition tronquée.
Les bornes couvrent aussi les identifiants non EODHD, sans les éliminer par
une hypothèse de format de ticker. Manifestes et empreintes sont conservés.

| Population figée | Taille |
| --- | ---: |
| Articles distincts de l'archive exportée | 6 720 |
| Reçus/versionnements nécessaires à leur état | 17 629 |
| Couples article/symbole dans l'univers | 11 399 |
| Couples avec mot-clé de financement | 134, dans 73 textes distincts |
| Couples sans réserve de date/corps/horodatage | 4 192, dans 2 595 articles |
| Couples présélectionnés parmi ces éligibles | 73, dans 40 textes distincts |
| Revue bornée | 20 couples présélectionnés + 10 témoins, 26 textes distincts |

Les 20 cas et 10 témoins sont les premiers par **empreinte stable des preuves**
au sein des groupes éligibles respectifs. Aucun prix, score Oracle, rendement
futur ni succès économique n'intervient dans la sélection. Les articles exclus
pour date ancienne ou corps insuffisant restent dans le dossier parent.
La revue ne prétend pas mesurer le rappel de la présélection : des formulations
absentes du dictionnaire peuvent être manquées.

Dossier : `artifacts/research/us_news_event_qualification/20261016-complete-review-v1/`.
`full/` conserve le corpus ; `bounded_review/` conserve les 30 couples choisis,
leurs citations, annotations et références. Ne pas additionner ces dossiers
comme s'ils représentaient deux populations indépendantes.

## 3. Lecture technique, émetteur, instrument et nouveauté

Les 26 corps archivés ont été lus ; les destinations URL sont masquées dans
l'affichage de lecture, mais le texte original et les positions exactes des
citations restent intacts. Même assistant : **pas une seconde revue humaine
indépendante**. Aucun champ n'est déclaré connu avant la lecture effective.

Les références `stock_metadata` ont été lues et figées pour les tickers
sélectionnés. Ce sont des métadonnées **actuelles**, non PIT ; plusieurs dates
de synchronisation sont absentes et n'ont pas été inventées.

| Exemple | Ce que dit réellement l'archive | Décision de revue |
| --- | --- | --- |
| FLEX | Placement de dette convertible de SentinelOne dans un article multi-entreprises | Pas une émission de FLEX |
| BAC | Offre d'actions d'IonQ ; BAC est cité pour ses résultats et une sanction | Pas une émission de BAC |
| BN | 6 millions d'actions préférentielles canadiennes, à C$25, pour C$150 millions | Financement décrit et émetteur identifié ; instrument séparé des actions ordinaires, nouveauté antérieure non certifiée |
| NVMI | Dette convertible d'ONTO émise en mai ; Nova est un concurrent cité | Ni nouvelle ni émission de NVMI |
| PRMB / COKE | Rétrospective trimestrielle sur une cession d'un actionnaire ; COKE dans un lien connexe | Secondaire, pas nouveau financement primaire démontré |
| SNPS | Placement explicitement daté de 2025 | Rappel historique |
| AEP | Offre explicitement annoncée en mai 2026 | Rappel historique |
| SUN | Stardust Solar, **TSXV:SUN / OTCQB:SUNXF** | Pas **NYSE:Sunoco SUN** ; débentures convertibles, annonce précédente rappelée |
| RGLD | Red Lake Gold, **CSE:RGLD**, clôture d'une tranche annoncée le 31 août | Pas **NASDAQ:Royal Gold RGLD** |
| SYY | Accord social ; offre d'actions seulement dans « MORE ON SYSCO » | Lien annexe, pas nouvelle annonce prouvée dans ce corps |
| COST / EADSY | Résultats d'Elite Express / Aircastle et mentions de financement anciennes ou génériques | Pas émission de Costco / Airbus |
| TAK | IPO d'Iambic, ticker IAM, avec Takeda comme relation/partenaire | Pas dilution de TAK ; ne pas compter chaque reprise de l'IPO comme un événement distinct |
| FBK, témoin | Article sur First BanCorp **FBP** | Pas FB Financial **FBK** |
| JPM / SFM, témoins | Morgan Stanley / Vital Farms comme sujet, JPM ou Sprouts cités comme comparateur/partenaire | Relation contextuelle, pas identité d'émetteur |

**Un mapping fournisseur n'est pas nécessairement une erreur** : partenaires,
concurrents et articles sectoriels peuvent être associés légitimement au titre.
Mais il ne constitue jamais, seul, une preuve que le titre émet des actions.
Les 15 couples dont le sujet de la clause diffère du symbole ne sont donc pas
présentés comme 15 erreurs de données. Aucun mapping ni article n'a été effacé.

BN n'est pas déclaré « sans intérêt » : une émission de préférentielles peut
avoir un effet sur les actions ordinaires. Elle reste un candidat distinct à
qualifier, sans assimilation automatique à une émission ordinaire dilutive.
L'absence de comparaison certifiée avec les annonces antérieures et reprises
empêche ici sa promotion en événement nouveau pleinement qualifié.

Résultat : **30 annotations RESERVED**, zéro événement nouveau entièrement
qualifié, zéro candidat tradable. Les 53 autres couples présélectionnés éligibles
n'ont pas été relus dans cette borne. Pas de conclusion d'absence globale ni
de validation d'un effet directionnel. Les URL Yahoo/Seeking Alpha/CNBC sont
celles des payloads EODHD archivés ; aucune nouvelle collecte directe Yahoo,
ouverture de page ou API LLM n'a été réalisée.

## 4. Couverture intraday, sans rendement ni causalité

Convention existante : six barres 5 minutes terminées avant et six après la
publication, flux et fournisseur non mélangés, calendrier NYSE officiel,
barres brutes non synthétiques et volume positif. La barre contenant une
publication hors grille n'est pas affectée arbitrairement à l'avant ou l'après.
Hors séance : dernière demi-heure de la séance précédente et première demi-heure
de la séance suivante. Ce choix est un diagnostic de couverture, pas un ordre.

| Résultat sur les 30 couples | Nombre |
| --- | ---: |
| Fenêtre achevée mais barres absentes | 24 |
| Place insuffisante autour de la publication en séance | 1, BN juste après l'ouverture |
| Fin de fenêtre encore future à la borne figée | 5 |
| Fenêtre complète, source unique | 0 |

Les 24 requêtes de fenêtres achevées retournent **zéro barre**, pas seulement
quelques OHLC invalides. Le cas BN ne justifie pas d'inventer une fenêtre
symétrique intraday. Les cinq fenêtres futures restent futures à la borne du
dossier, même si le temps a avancé depuis. Aucun téléchargement de rattrapage.

Les 24 fenêtres achevées finissaient aussi **avant la disponibilité réelle de
leurs preuves archivées**. Même des barres téléchargées plus tard ne rendraient
pas ces annonces exploitables historiquement à l'heure de publication par notre
application. Une étude rétrospective publication/prix serait descriptive ; une
simulation exécutable doit partir de `available_at` puis du prochain instant
d'exécution admissible.

Latence observée entre publication et première association qualifiée disponible,
sur 2 595 articles éligibles : min **0,61 h**, médiane **27,55 h**, max **60,47 h**.
Sur les 30 couples de revue : médiane **30,30 h**. Ces délais incluent le premier
rattrapage J−7/J et les pannes ; **ce n'est pas une mesure de latence nominale
EODHD ni du fonctionnement quotidien futur**. Pas d'heure de réception ancienne
inventée pour transformer ces données en signal historique.

L'auditeur a été actualisé pour distinguer le nouveau batch d'ingestion
quotidien du scoring sentiment de l'étape 8, toujours hebdomadaire. Le rapport
intraday `v1`, conservé, mentionnait à tort l'absence d'ingestion quotidienne
comme blocage parce qu'il ne regardait que les étapes de `us_pipeline`.
Le rapport **v2** le remplace pour ce constat : ingestion séparée configurée,
sans prétendre que les scores sentiment sont recalculés quotidiennement.

Rapport final :
`artifacts/research/us_news_financing_feasibility/20261016-complete-review-v2/completion_summary.json`.

## 5. Tests, limites et prochaine borne

**74 tests de recherche ciblés passent** : partitionnement et frontières,
absence de promotion d'un corpus tronqué, sélection stable, citations exactes,
rejet des textes inconnus/modifiés, dates sans rétrodatation, couverture et
séparation ingestion quotidienne/scoring hebdomadaire. Tests SQL en mémoire,
aucune écriture dans la base métier.

La borne demandée est livrée. La suite utile serait de **qualifier l'émetteur,
la place, l'instrument et la nouveauté avant tout score**, puis de définir une
mesure de réaction à partir de la disponibilité réellement observée et d'une
couverture intraday explicite. Ce travail ne justifie ni nouvel entraînement
directionnel ni backtest de performance aujourd'hui. Les collectes quotidiennes
existantes restent inchangées ; le suivi automatique précédemment clôturé
n'a pas été réactivé et la tâche manuelle terminée reste sans déclencheur.

### Reproduction — toujours dans des dossiers neufs

```powershell
python -u -m scripts.research.us_news_daily_run_validation --run-id eodhd_news_ingestion_sync-20261016121131-5ed4d540 --output artifacts/research/us_news_financing_feasibility/NOUVELLE-VALIDATION
python -u -m scripts.research.us_news_financing_completion_20261016 --validation artifacts/research/us_news_financing_feasibility/NOUVELLE-VALIDATION --output artifacts/research/us_news_event_qualification/NOUVEAU-DOSSIER --cutoff 2026-10-16T13:48:49.600646Z
python -u -m scripts.research.us_news_financing_review_20261016 --pack artifacts/research/us_news_event_qualification/NOUVEAU-DOSSIER/bounded_review
python -u -m scripts.research.us_news_financing_feasibility --pack artifacts/research/us_news_event_qualification/NOUVEAU-DOSSIER/bounded_review --output artifacts/research/us_news_financing_feasibility/NOUVELLE-COUVERTURE
```

Le script de lecture est lié aux 26 textes effectivement relus ; il refuse
les autres textes. Ce n'est pas un classifieur générique à appliquer à de
nouvelles journées. La disponibilité de ses annotations est celle de la lecture
effective, jamais la date de publication.
