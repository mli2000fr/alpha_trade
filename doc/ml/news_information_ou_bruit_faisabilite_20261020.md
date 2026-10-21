# TOP10 Oracle : mouvement informationnel ou bruit — faisabilité

## Conclusion du 20 octobre 2026

**Audit borné livré ; comparaison causale non encore faisable sur ces archives.**
Ce n'est pas un résultat négatif de trading : aucun prix, rendement futur,
TP/SL réalisé, capital ou performance n'a été chargé/calculé.

Deux panneaux distincts ont été examinés :

| Panneau | Sélections | Textes disponibles | Lecture bornée | Résultat documentaire |
|---|---:|---|---:|---|
| TOP10 historique, janvier 2026 | 200, 20 séances, 28 titres | 418 couples article/titre, 409 articles, sur 110 sélections | 30 couples | Six candidats factuels propres au titre, mais zéro version prouvée disponible à la décision historique |
| TOP10 connu avant l'ouverture du 19 octobre | 10, une date | Cinq couples récents sur trois titres, plus 75 couples de contexte antérieur | Les cinq récents | Reçus temporels valides, mais aucune nouvelle annonce propre au titre entièrement qualifiée |

Les **90 sélections historiques sans texte dans les paquets** et les **sept
titres récents sans texte retrouvé dans la fenêtre** restent `UNKNOWN`.
Ils ne deviennent pas un groupe « sans annonce ». Sans couverture qualifiée,
la comparaison « avec information contre sans information » serait trompeuse.

**Aucun nouvel entraînement, appel fournisseur/LLM/Web, achat, écriture SQL,
ordre ou changement de production.** Lecture locale historique et SELECT-only
des versions news déjà en base pour le panneau récent. Aucun job laissé actif.

## Hypothèse distincte et portée du GO

L'idée proposée distingue une première variation liée à une annonce concrète
d'une variation sans cause identifiable dans un corpus suffisamment couvert.
Une [étude NBER sur les nouvelles identifiables et les mouvements extrêmes](https://www.nber.org/papers/w18725)
motive cette distinction ; elle ne démontre pas sa validité dans notre
univers, sur notre TOP10 ou après nos coûts.

Ce n'est pas une nouvelle règle « sentiment positif → LONG ». Il faudrait
d'abord prouver : bon sujet, fait précis, date de disponibilité, nouveauté
par rapport aux annonces déjà connues, puis qualifier la réaction initiale.
Les commentaires de cours, opinions, simples calendriers et reprises ne sont
pas automatiquement de nouvelles annonces opérationnelles.

Le GO portait sur un **petit audit de faisabilité**. Le plan éventuel suivant
reste une expérience distincte : réaction initiale disponible à la décision J,
entrée à l'ouverture suivante, H10 TP10/SL5 inchangé, références appariées
continuation/retournement et prix seuls. Ce plan n'a pas été exécuté ici.
Les seuils de mouvement initial ne sont pas optimisés après inspection des prix.

## Sélection historique : pas de nouveau modèle, ni avis GPT relu

Sources scellées :
`artifacts/research/us_news_gpt_top20_history/20261015-v1/months/2026-01/`.

- Classement original TOP20, gardant les rangs 1–10 avant lecture des textes.
- Parcours H20 CatBoost annuel `model-factory-20261014113232-bc35a7`,
  fold `2025-12-10`, disponibilité du modèle avant janvier ; poids/profil
  identifiés par les empreintes déjà figées. Les rangs et cibles sont vérifiés.
- **200 couples titre/date**, dix par séance ; pas de remplacement après
  absence de news ou qualification défavorable.
- Seules les colonnes de sélection, scores et lineage sont chargées. Aucun
  label futur, ancien résultat de backtest ou avis directionnel GPT utilisé.
- Paquets et métadonnées déjà archivés : fenêtre originale de **24 heures
  avant la clôture de J**, pas une fenêtre modifiée pour récupérer plus de cas.
  Elle ne couvre pas intégralement tous les week-ends.

Les 418 couples ont une version du corps liée par empreinte aux métadonnées,
mais **280 extraits sont tronqués**. Un extrait non marqué tronqué peut aussi
être une courte dépêche ou se terminer par « Continue Reading » : cela ne
prouve pas l'accès à l'intégralité de la publication originale.

**Zéro occurrence** passe la garde conservatrice exigeant première insertion
et dernière modification du texte et de son association avant la décision.
Une publication fournisseur datée de janvier, importée/modifiée plus tard,
n'est pas une archive du texte tel qu'il était connu en janvier. Nous
n'avons pas remplacé ces versions par les corps courants en base.

### Revue historique prédéfinie

Présélection par mots du titre : annonce, résultats, accord, contrat,
régulateur, acquisition, financement, guidance, etc. Ce n'est **pas** un
classificateur validé d'événement. Les titres sont ordonnés par SHA-256 de
symbole/article, puis au plus **20 présélectionnés et 10 autres** sont lus.
Pas de sélection selon cours, gain/perte, sentiment ou avis GPT.

Une même association article/titre n'est pas recomptée comme plusieurs
lectures ; un article associé à deux titres exige deux contrôles de sujet.
Les sources portant une réserve MSCI restent exclues de la lecture, sans
requalification juridique. Aucune URL source n'est téléchargée dans cet audit.

| Catégorie des 30 couples lus | Nombre |
|---|---:|
| Candidats à une annonce factuelle | 12 |
| Opinions / valorisation / attentes | 8 |
| Commentaires de mouvements déjà observés | 3 |
| Reprise explicitement rétrospective | 1 |
| Mixte ou non résolu | 6 |

**Six des douze candidats factuels concernent un autre émetteur** : USAR
associé à MP, Sandisk à WDC, Sanmina à CLS, Lynas à MP, SLB à COHR et une
acquisition de Jabil à CLS. Une information sectorielle peut éventuellement
affecter un pair, mais c'est une autre hypothèse ; on ne transfère pas les
résultats ou acquisitions à la mauvaise société.

Les six candidats concernant bien le titre sont associés à **CLS, CODI,
MLTX, SRPT et WDC**. Deux articles CLS décrivent le même trimestre et des
chiffres communs : pas six événements indépendants démontrés. Pour CODI,
un ancien trimestre publié avec retard n'est pas automatiquement une vieille
annonce : l'original serait nécessaire. Pour MLTX/SRPT, les résumés
réglementaires/cliniques ne certifient ni première annonce ni horaire.

Ce sont des candidats à approfondir, **pas des annonces nouvelles pleinement
qualifiées**, encore moins des directions ou trades gagnants.

## Panneau prospectif : disponibilité réelle, pertinence à revoir

Le classement est celui du **16 octobre**, enregistré le 17 et déjà disponible
avant l'ouverture du 19. Le protocole choisit explicitement de figer ce
préfiltre avant la séance du 19, puis d'examiner les publications jusqu'à sa
clôture. **Ce n'est pas une reconstitution d'un Oracle du 19 après clôture**,
ni une disponibilité du score dès la clôture du 16. Une éventuelle réaction
initiale serait celle du 19 et l'entrée suivante celle du 20 ; aucun de ces
prix n'a été chargé.

Fenêtre récente : **16 octobre 20 h UTC → 19 octobre 20 h UTC**, week-end
inclus. Contexte demandé : trente jours avant le cutoff, sans garantie de
couverture sur ces trente jours. L'archive versionnée a démarré plus récemment.

Lecture transactionnelle de `news_raw_versions`, `news_ticker_map_versions`
et `news_archive_observations`, sans utiliser les projections courantes :

- reçus texte et mapping de `PROVIDER_COLLECTION`, scellés strictement avant
  le cutoff ; pas de backfill transformé en ancien reçu ;
- dernière observation par flux, y compris les récurrences A→B→A ;
- mapping intégral lié à la **même version** du texte ;
- publication avec fuseau explicite et cohérente avec la normalisation ;
- contrôle des empreintes des textes et des snapshots de mapping ;
- bornes et plafonds de requêtes explicites ; débordement = troncature,
  jamais couverture complète ou absence de news.

Résultat : **cinq couples récents et 75 de contexte**, sans troncature de cette
requête bornée. L'audit recoupe **88 versions de texte, 617 versions de mapping
et 757 observations scellées**. Ce décompte inclut les prédécesseurs nécessaires
à la reconstruction, pas 617 annonces nouvelles.

Les reçus en attente n'ont pas été recensés globalement : le snapshot le
signale explicitement. « Pas de troncature SQL » ne veut pas dire que le
fournisseur a couvert toutes les publications possibles ou que tous les
symboles ont été collectés complètement.

### Les cinq couples récents lus

| Association archivée | Lecture | Réserve |
|---|---|---|
| FMC, valorisation après baisse de guidance | Reprise d'un fait déjà annoncé | Communiqué FMC antérieur archivé le **15 octobre à 11 h 30 UTC** |
| FMC, outlook et fair value | Même intervalle de revenus Q3 65–125 M | Même communiqué antérieur ; pas une première annonce du 17 |
| FMC, objectifs et narratifs d'analystes | Synthèse mixte | Dates propres des nouvelles révisions non qualifiées |
| FUN, récapitulatif hebdomadaire | Section Six Flags et incident identifiable | Date/heure de l'incident et première publication non prouvées ; pas automatiquement une annonce du lundi |
| **TXG**, valorisation de **Terex/TEX** | **Autre société** | Ne pas utiliser ce texte comme information de 10x Genomics |

La répétition FMC est positivement appuyée par le texte antérieur dans
l'archive, avec identité, disponibilité et citation vérifiées. La nouveauté des
trois autres cas reste inconnue, pas artificiellement validée ou négative.

Les titres sans texte récent retrouvé sont BAND, CCOI, COHR, DOCN, ICHR, MXL et
UCTT. Ils ne sont pas certifiés sans annonce. Zéro nouvelle annonce propre au
titre entièrement qualifiée dans ce petit panneau récent.

## Ce qui bloque exactement le test et ce qui est livré

Le contraste nécessite deux groupes interprétables. Aujourd'hui :

1. Historique : textes rétrospectifs, versions disponibles à la décision non
   prouvées, extraits souvent incomplets ;
2. Récent : reçus disponibles, mais cas surtout repris/commentés ou sujet
   erroné, plus trop peu de dates ;
3. Groupe « sans cause identifiée » : couverture du corpus non certifiée,
   donc absence et ignorance indissociables.

Verdict : `BLOCKED_CAUSAL_CONTRAST_NOT_EFFICACY_FAILURE`.
**Pas un NO_GO statistique de l'hypothèse**, pas de modèle entraîné et pas de
probabilité de continuation/retournement estimée.

Racine : `artifacts/research/us_news_information_vs_noise/20261020-v1/`.

- `protocol.json` figé avant revue, sans prix ;
- `historical-top10.parquet`, `historical-availability.parquet`, paquets de
  couples et revue historique ;
- snapshot brut versionné récent, couples récents/contexte et revue récente ;
- `readout-v1/` : notes de lecture, citations, preuves de reprise et bilan ;
- `audit.json` : `PASS_OFFLINE_FEASIBILITY_AND_REVIEW_AUDIT`.

Notes versionnées :
`doc/ml/sources/news_information_vs_noise_review_20261020.json`.
Scripts : `scripts/research/us_news_information_vs_noise_{feasibility,readout,audit}.py`.
**97 tests ciblés passent, dont 13 nouveaux** : couverture/troncature,
échantillonnage, citations exactes, versions/empreintes, reçus et absence de
promotion UNKNOWN→NEW. Même assistant, **pas seconde revue humaine indépendante**.
La restriction de socket locale a nécessité une exécution autorisée du lecteur
READ ONLY ; aucune collecte externe ni écriture SQL effectuée.

## Suite raisonnable, non lancée automatiquement

- Ne pas calculer une performance en appelant les 90 cas sans texte
  « sans news » : cela ne répondrait pas à l'hypothèse.
- Conserver les archives prospectives existantes et les classements réellement
  disponibles. Examiner de nouvelles dates avant lecture de leurs résultats.
- Traiter d'abord le sujet et les reprises : le cas TXG/TEX mérite une
  qualification du rapprochement avant utilisation LLM/directionnelle. Ce
  travail n'a **pas modifié** les mappings de production ni les batchs.
- Si un test historique purement exploratoire est explicitement souhaité,
  il devra garder la réserve de version/PIT et ne pas être présenté comme une
  stratégie historiquement exécutable. Aucun tel test n'a été lancé ici.
- Élargir dates, rangs ou familles d'annonces nécessite un nouveau périmètre
  explicite, pas une sélection opportuniste des quelques cas favorables.
