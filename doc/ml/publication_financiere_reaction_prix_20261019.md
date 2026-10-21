# Publication financière + réaction du prix — faisabilité TOP10, 19 octobre 2026

**Suite réalisée après ce premier audit** : [reconstitution SEC des 93 cas](reconstitution_annonces_financieres_sec_20261019.md).
154 originaux récupérés, 70 annonces de trimestre rapprochées, 27 cas à quatre
montants non ambigus dans un tableau cohérent. Après recalage, sept accords
provisoires, pas une performance. Les anciens comptes ci-dessous restent ceux
de l'audit initial ; ils ne sont pas remplacés silencieusement par les nouveaux.
Le bilan suivant explicite aussi le biais qu'introduirait un backtest recalé
sur une cohorte sélectionnée à partir du classement d'une date ultérieure.

## Conclusion opérationnelle

**Audit de faisabilité terminé ; efficacité non testée.** Une bibliothèque
locale permet de reconstruire des observations trimestrielles, mais elle ne
prouve pas que le dépôt correspond à la première annonce des résultats.
Sur le TOP10, l'accord comptabilité/prix produit seulement **24 candidats sur
trois années partielles ou complètes**, à **22 dates**. Ce ne sont ni des
trades exécutés, ni des gains, ni des observations déjà pleinement qualifiées.

Le test n'est pas abandonné comme inefficace. Deux limites sont maintenant
mesurées : chronologie de la vraie annonce à reconstituer, puis faible nombre
d'occasions dans le strict TOP10. Aucun abonnement ni attente de clarification
du consensus EODHD n'est nécessaire pour cette reconstitution SEC.

**Aucun entraînement, retour H10/H20, backtest économique, appel fournisseur ou
LLM, ordre, écriture SQL, changement de configuration ou de production.**
Lecture SQL READ ONLY / REPEATABLE READ, session UTC puis ROLLBACK ; les copies
et calculs sont limités au dossier de recherche. Aucun batch lancé.

## Hypothèse distincte des essais antérieurs

Les anciens essais de surprise EPS brute, compteurs 8-K ou sentiment général
n'ont pas démontré d'avantage suffisant. Ici, on demande simultanément :

- une évolution trimestrielle du revenu et de la marge opérationnelle ;
- une réaction de marché observée après disponibilité de l'information ;
- une présence dans le TOP10 Oracle, sans remplacement par le rang suivant.

Une amélioration par rapport au même trimestre de l'année précédente **n'est
pas une surprise par rapport au consensus des analystes**. Aucun consensus
courant n'a été injecté dans une ancienne date d'annonce.

## Protocole figé avant les calculs

Protocole créé le **19 octobre 2026 à 20:27:36 UTC / 22:27:36 Paris** dans
`artifacts/research/us_earnings_reaction_readiness/20261019-v1/`.
Sources, scripts, tests, univers et caches identifiés par empreintes.

### Classement Oracle utilisé

- Référence historique de recherche H20 de
  `us_h10_h20_frozen_comparison/20261019-v1` : modèles CatBoost annuels
  walk-forward déjà entraînés, mêmes données corrigées que la comparaison H10.
- **Pas** une nouvelle exécution des anciens identifiants annuels de production,
  ni un choix de champion sur les performances de ce test.
- Seules les colonnes date/symbole/score/rang ont été chargées depuis les scores ;
  pas les labels, amplitudes réalisées ou résultats des précédents essais.
- Les rangs sont recomputés et vérifiés : score décroissant, symbole croissant
  en cas d'égalité, TOP10 avant qualification comptable et prix.
- **6 690 couples titre/date**, 669 séances et 160 titres distincts :
  2024 entière, 2025 entière selon le support archivé, 2026 jusqu'au
  **1er septembre**, pas jusqu'à fin septembre ou octobre.
- Le TOP10 courant du 16 octobre est seulement un contexte d'inventaire
  documentaire ; il n'étend pas artificiellement ce support historique.

### Signal comptable sans modèle

Comparaison au même trimestre de l'année précédente :

1. Revenu en hausse **et** marge opérationnelle en hausse → motif LONG.
2. Revenu en baisse **et** marge opérationnelle en baisse → motif SHORT.
3. Désaccord, stabilité ou données manquantes → abstention.

La marge est calculée par `résultat opérationnel / revenu`. Ce n'est pas une
moyenne de marges historiques, un EPS ajusté ou une surprise analyste.
L'EPS dilué direct est conservé à titre de contexte, sans être une condition
supplémentaire choisie après les résultats.

### Reconstruction des chiffres, séparée du mapper de production

Lecture exclusive des companyfacts SEC **déjà en cache** :

- clé accession + début/fin de période + tag + unité, jamais `fy/fp` seuls ;
- faits directs couvrant 70 à 110 jours : pas de chiffre annuel assimilé au
  quatrième trimestre, ni soustraction YTD reconstruite sans preuve ;
- comparaison historique contenue dans la **même accession** que le chiffre
  courant, avec calendrier 52/53 semaines toléré ;
- unités USD pour revenu/résultat opérationnel, USD/shares pour EPS ; pas de
  conversion ou d'échelle inventée ;
- amendements exclus ; plusieurs tags revenus discordants réservés, pas
  sélection du chiffre qui produit le signal souhaité ;
- observation originale retenue par trimestre ; publications répétées du même
  trimestre non comptées comme de nouvelles annonces.

Une comparaison retraitée dans la publication courante peut être disponible
à cette publication ; elle n'est jamais projetée avant cette date. L'égalité
de tags ne certifie toutefois pas à elle seule l'absence de fusion, scission,
changement de périmètre ou changement d'identité du titre.

### Réaction observée et entrée éventuelle

Une date de dépôt seule ne justifie aucune heure inventée. Convention
conservatrice : **première séance NYSE complète strictement après le dépôt**.
Réaction = rendement clôture précédente → clôture de cette séance pour le
titre, moins celui de SPY sur les mêmes bornes.

L'accord comptabilité/prix exige le même signe. Une éventuelle entrée se fait
à l'ouverture **suivante**, après observation de la réaction. Le classement
Oracle utilisé est celui de la clôture d'observation, pas un classement choisi
après les mouvements futurs. La vraie annonce peut précéder le dépôt : cette
convention ne résout pas ce problème et ne suffit pas à qualifier le signal.

Les prix ajustés sont un proxy de recherche : OHLC cohérents, volume positif,
barres non remplies et stabilité de fournisseur/base/instrument sur les deux
séances. Seules les bornes nécessaires sont exportées ; aucun parcours futur
n'est utilisé pour choisir ou classer les candidats. Pas de parité broker,
bid/ask ou total return affirmée.

Trois bras prévus si les preuves sont qualifiées : comptabilité seule,
réaction seule, accord des deux. Même TP10/SL5, dix séances, sans trailing,
gaps conservés, ambiguïté OHLC perte d'abord, coûts 8 bps par jambe et stress
20 bps. H20 secondaire ; **aucune de ces performances n'a été calculée ici**.

## Données disponibles et limites de couverture

- 156/160 titres ont un cache companyfacts raccordable par mapping courant.
  DNNGY, EXPI, KALV et SATS n'ont pas de cache raccordé par cette procédure.
  Ils restent dans la couverture manquante, sans substitution.
- Les caches utilisés représentent environ 406 Mio. Ils sont actuels : leur
  date de réception ne devient pas une date de réception historique.
- Sur ces titres et le périmètre local retenu : **1 510 observations de
  trimestre**, dont **1 161** reconstructibles numériquement avec revenu et
  résultat opérationnel comparables. Ces observations comprennent aussi des
  périodes de contexte hors des dates de décision historiques.
- Réserves non exclusives : revenu courant absent 155, résultat opérationnel
  courant absent 102, tags revenus discordants 94, comparaison de revenu
  absente 9, comparaison de résultat opérationnel absente 4, intervalle
  trimestriel ambigu 1. Un manque n'est pas remplacé par zéro.
- **2 102 lignes SEC normalisées** copiées pour contrôler la disponibilité du
  pipeline existant ; elles ne sont pas utilisées comme substitut automatique
  aux faits trimestriels directs.
- **156 métadonnées de dépôts** pour ces titres, dont 11 originaux 10-Q/10-K.
  Les dépôts RAW de l'univers observé commencent en septembre 2026, après
  la fin du support historique des scores de cette étude.
- Sur les 93 candidats historiques TOP10 : **zéro accession présente dans
  ce RAW local**, donc aucune preuve de première annonce/réception historique
  certifiée par ce corpus. Cela ne signifie pas que la SEC ne les possède pas.
- Le tableau d'inventaire mentionne aussi les sources Finnhub/FMP/Yahoo encore
  présentes dans la table générale. **Aucune valeur Yahoo n'est utilisée ici,
  aucune source suspendue n'est réactivée.**

## Bilan TOP10 — nombres d'occasions, pas de performance

| Année | Dépôts coïncidant avec le TOP10 | Chiffres comparables | Accord LONG | Accord SHORT | Total accord |
|---|---:|---:|---:|---:|---:|
| 2024 | 34 | 26 | 5 | 5 | 10 |
| 2025 | 40 | 27 | 4 | 5 | 9 |
| 2026 au 1er septembre | 19 | 15 | 5 | 0 | 5 |
| **Total** | **93** | **68** | **14** | **10** | **24** |

Les 68 incluent des motifs comptables stables/mixtes conduisant à l'abstention.
Les 93 réactions prix sont techniquement calculables ; cela ne certifie pas la
nouveauté ou le périmètre comptable. Les 24 accords concernent 21 titres et
22 séances de décision : pas 24 preuves de réussite, ni 24 événements pleinement
validés. L'absence de SHORT en 2026 n'est pas un résultat de rentabilité.

Le seuil de faisabilité de confirmation proposé était 100 événements
indépendants et 50 séances distinctes, avec présence des trois années.
**L'accord TOP10 ne l'atteint pas, même avant les réserves documentaires.**
Ce seuil est une précaution de protocole, pas une garantie de puissance.
Nous n'élargissons pas discrètement au TOP20 % pour le franchir.

## Contre-exemple documentaire vérifié : OXM

Échantillon borné avant tout résultat futur : jusqu'à dix originaux trimestriels
récents de taille admissible, puis jusqu'à dix 8-K/6-K antérieurs des mêmes
émetteurs sur 45 jours. **Quatre fichiers récupérés depuis la base**, empreintes
du texte cohérentes avec la source : trois 10-Q (OXM/FIVE/KSS) et un 8-K OXM
contenant également son EX-99.1. Sept originaux dépassent la borne de 8 Mio
en caractères du présélecteur et un document est absent ; pas d'exhaustivité
annoncée. Aucun téléchargement supplémentaire pour les obtenir.

Le 8-K OXM `0000075288-26-000082`, daté du **3 septembre 2026**, indique en
Item 2.02 la diffusion des résultats du trimestre clos au 1er août ; l'EX-99.1
joint porte le même jour. Le 10-Q `0000075288-26-000084` est déposé le
**4 septembre**. Le 10-Q ne doit donc pas être étiqueté automatiquement comme
première annonce de ces résultats.

Les deux documents ont été reçus localement le **14 septembre**. Ni la date
de publication, ni le champ d'acceptation stocké ne prouvent une réception
Alpha-Trade le 3 ou le 4. Aucun fuseau non documenté n'est ajouté au champ
d'acceptation pour inventer un horaire d'annonce.

Le texte principal 8-K OXM a été relu ; pour les autres longs documents, la
revue est limitée aux sections et extraits identifiés, pas une lecture humaine
intégrale de toutes les annexes ni une seconde revue indépendante. Les limites
de cet échantillon n'altèrent pas le chiffre de zéro accession RAW retrouvée
pour les 93 événements historiques.

## Ce qui débloquerait réellement la suite

1. Retrouver pour les 93 cas historiques la publication de résultats pertinente :
   accession originale, 8-K Item 2.02/EX-99.1 et, si nécessaire, communiqué IR
   antérieur. Il s'agit de pièces SEC publiques, **pas d'un consensus payant**.
2. Confirmer le même trimestre, émetteur et périmètre ; identifier la première
   annonce, supprimer les répétitions sans sélectionner selon le rendement.
3. Recalculer une décision après disponibilité et séance de réaction réelles,
   puis vérifier le TOP10 à cette nouvelle date. **Ne pas garder mécaniquement
   les mêmes 24 cas après correction de la date d'annonce.**
4. Mesurer de nouveau le nombre d'événements. Si le strict TOP10 reste aussi
   rare, un test serait seulement exploratoire ; il ne justifierait pas un
   modèle dédié. Élargir au TOP20 % serait une expérience distincte nécessitant
   une décision explicite, pas une modification silencieuse du protocole.

Ce bilan clôt l'audit de faisabilité demandé. Il ne proclame ni que
l'événementiel fonctionne, ni qu'il échoue. La suite est une reconstitution
historique bornée des **vraies annonces**, non une nouvelle optimisation de
TP/SL ou une attente indéfinie de nouvelles lignes quotidiennes.

## Livrables et vérifications

- `scripts/research/us_earnings_reaction_readiness.py` : phases `prepare`,
  `snapshot`, `build`, sortie neuve et scellée ; pas de réexécution destructive.
- `scripts/research/us_earnings_reaction_source_audit.py` : reproduction scalaire
  de **1 161** observations comptables et **93** réactions TOP10, adhésion exacte
  aux rangs, accord des signes, séparation SGML du formulaire et de l'annexe,
  vérification des empreintes des quatre documents.
- Dans le dossier artefacts : `protocol.json`, `report.json`,
  `source-audit.json`, `filing-candidates.parquet`, `top10-candidates.parquet`,
  `reaction-price-inputs.parquet`, inventaire et documents/extraits scellés.
- **154 tests ciblés passent**, dont 25 nouveaux sur calcul/disponibilité/périodes
  et quatre sur la structure des sources. Ce total porte sur les huit fichiers
  du groupe collecteur/LLM-evidence/consensus/pilote/diagnostic/revues, pas sur
  l'ensemble du projet.
- Limites permanentes : univers survivant courant, mapping ticker/CIK courant
  non PIT, années déjà explorées, pas de véritable holdout inédit, pas de
  promotion de modèle ou d'activation live sur ces résultats.
