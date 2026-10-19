# Axe information économique — révisions observées, 19 octobre 2026

**Mise à jour fournisseur reçue ensuite** : [précisions EODHD](consensus_eodhd_precisions_support_20261019.md).
Unités/devise DOCN-FUN et horizons clarifiés ; base EPS par item et identités
d'analystes indisponibles. Les chiffres et verdicts du pilote initial ci-dessous
restent datés et ne sont ni recalculés ni promus par cette réponse.

## Conclusion et périmètre du GO

**Pilote de données terminé, validation directionnelle bloquée par la
qualification et le manque de dates indépendantes. Ce n'est pas un résultat
négatif sur l'efficacité des révisions.** Aucun rendement, entraînement,
backtest, appel GPT/DeepSeek, API fournisseur ou ordre lancé dans ce pilote.

Le GO porte sur le premier axe : information économique nouvelle — révisions
EPS/revenus, guidance et surprise de publication — pour le TOP10 Oracle.
Avant toute lecture de prix futurs, la priorité a été fixée aux **changements
entre snapshots EODHD effectivement reçus**, et non à une nouvelle tentative
sur le parseur de guidance E21 ou sur un calendrier de résultats courant.

Les écritures sont uniquement des scripts/tests de recherche, artefacts locaux
et documentation. **Aucune modification SQL, modèle, configuration ou batch**.
Les collectes et blocages de fournisseurs existants sont préservés.

## Ce qui avait déjà été testé

- Révisions Yahoo : effet H10 initial favorable sur dix dates, mais dégradé
  après contrôle du secteur/momentum ; une seule date indépendante. Source
  désactivée, pas de restauration ici.
- DDR-5 / surprise EPS : une jointure sur `earnings_date` ne prouve pas que
  l'estimation était connue avant l'annonce. Ancien résultat non réutilisable
  comme preuve PIT stricte.
- Guidance E21 : défauts de couverture, extraction ancienne/nouvelle/réalisée,
  périodes et unités. Les cas ponctuels identifiés ne constituent pas un
  corpus directionnel représentatif. Ce pilote ne réactive pas E21 sous un
  autre nom.

Voir [l'audit des anciens signaux](signaux_directionnels_faibles_audit_20261014.md).

## Inventaire réel en base

Lecture seule du 19 octobre 2026, fin d'inventaire **21 h 37 Paris**.
Univers figé : `config/univers_batch/univers_filtred_tradable.txt`, **1 790 titres**.

| Famille | Couverture constatée | Réserve |
|---|---|---|
| Consensus EODHD | **1 778 titres**, huit dates du 11 au 18 octobre ; **1 170 331 lignes** dans l'univers | Huit observations quotidiennes, pas des années de vintages ; tous les marqueurs fiscal/unités/PIT historique restent faux |
| Calendrier résultats | 13 584 lignes, 1 484 titres | Table courante modifiable ; pas de version d'estimation pré-annonce certifiée par cette table |
| Dépôts SEC | 1 454 dépôts, 731 titres, fichiers datés du 3 septembre au 16 octobre | Disponibilité reçue à partir du 14 septembre ; ne pas antidater la réception à la date de dépôt |
| Événements SEC structurés | Neuf lignes 8-K dans l'univers | Pas un corpus complet d'annonces de résultats ou de guidance |
| Annexes SEC séparées | 592 références, dont 552 avec contenu, selon les groupes de types exportés | Dernière disponibilité de ces annexes séparées au 3 octobre ; ne prouve pas l'absence de textes EX-99 intégrés aux soumissions principales |
| Oracle courant récent | 1 743 scores, une date : **16 octobre** | Batch exact `model-factory-20261016180250-3b0515`, cible parcours **H20**, pas l'Oracle H10 du test PCA |

L'inventaire exporte les métadonnées, dates, colonnes et statuts, pas les mots
de passe. Une première tentative confinée a échoué sur la socket locale
(`WinError 10013`) avant lecture SQL ; le dossier v1 est conservé comme tel.
Le dossier v2 contient l'inventaire réussi, sans remplacement du v1.

### Attention au sens de l'historique EODHD

La [documentation officielle Calendar/Trends](https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits)
décrit des enregistrements ancrés sur de nombreuses fins de périodes fiscales,
avec des libellés `0q/+1q/0y/+1y` répétés. Une ancienne fin de période n'est
pas une date de snapshot de consensus. Les champs J−7/30/60/90 reçus aujourd'hui
ne créent pas de nouvelles observations réellement archivées à ces dates.
La réponse écrite du support déjà conservée dans le projet ne certifie pas
d'archive historique « as-known » ; ce pilote utilise uniquement les vraies
réceptions du 11 au 18 octobre.

## Données et protocole du pilote

1. Inventaire sans prix ni rendements ; protocole scellé avant export détaillé.
2. Export borné des périodes déclarées du 13 juin 2026 au 22 novembre 2027,
   observations du 11 au 18 octobre, reçues avant le cutoff d'inventaire.
   Le reste du contenu historique fournisseur n'est pas présenté comme étudié.
3. **98 600 lignes**, 1 760 titres avec paires dans ce sous-ensemble récent.
4. Appariement par fournisseur, symbole, fin de période déclarée et horizon
   brut identiques. Deux observations successives, au plus 72 heures d'écart.
   Aucun pont entre deux trimestres ou entre `0q` et `+1q`.
5. Comparaison de `eps_avg` et `revenue_avg`, en conservant aussi les nombres
   d'analystes, intervalles, valeurs manquantes et preuves brutes.

Hypothèse primaire figée : EPS **et** revenus en hausse → candidat LONG ;
les deux en baisse → candidat SHORT ; désaccord, stabilité ou manque →
abstention. Aucun seuil d'amplitude optimisé.

Pour être recevable, une paire doit avoir une identité fiscale, des unités,
une devise et une définition de métrique comparables qualifiées, au moins
trois analystes EPS et revenus à chacune des observations, des runs terminés,
un payload cohérent et une disponibilité antérieure à l'entrée. La disponibilité
retenue est le maximum observation/réception/insertion/fin du run : pas un
horaire optimiste inventé.

`historical_pit_qualified=false` n'est **pas en soi un rejet** d'une collecte
prospective : une réception actuelle peut être utilisée ensuite. En revanche,
elle ne devient pas rétrospectivement une estimation connue des années auparavant.

### TOP10 figé

Classement du batch exact du 16 octobre, score décroissant et symbole en cas
d'égalité, sur l'univers tradable, avant inspection des features :

**CCOI, ICHR, BAND, FUN, UCTT, FMC, MXL, COHR, TXG, DOCN.**

Pas de filtrage GPT et pas de remplacement par les rangs suivants. La lignée
Oracle indique une disponibilité de modèle antérieure au signal ; les scores
ont été inscrits le 17 octobre, avant l'ouverture du lundi 19. Cutoff d'entrée
du dossier : **19 octobre à 13 h 30 UTC / 15 h 30 Paris**.

La cible d'évaluation éventuelle est distincte du préfiltre Oracle H20 :
**TP10 avant SL5 sur dix séances**, entrée à l'ouverture suivant la décision,
ambiguïté journalière traitée prudemment, expiration distincte. Aucun résultat
de cette cible n'a été lu ici. Pour ce dossier entrant le 19, les dix séances
se termineraient le **30 octobre après clôture NYSE**, sous réserve de prix
qualifiés. Atteindre cette date ne suffit pas à créer un échantillon indépendant.

## Résultats de qualification, pas de performance

- **86 222 paires** de périodes/observations, pas autant de trades indépendants.
- **86 134** paires techniquement cohérentes au niveau de l'item brut,
  des champs normalisés, des heures et du statut de collecte.
- 84 occurrences de paires avec intervalle EPS incohérent et quatre avec
  intervalle de revenus incohérent ; réservées, pas corrigées en SQL.
- **Zéro paire pleinement qualifiée** pour une entrée directionnelle. Les
  marqueurs fiscaux/unités restent faux, statut `RESEARCH_ONLY`, devise absente.
  Ces faux sont aussi des valeurs par défaut du collecteur : ils signifient
  « non validé », pas « démontré incorrect » pour chaque enregistrement.
- Un échantillon fixé sans rendements : vingt émetteurs avec changements,
  dix témoins inchangés, plus les dernières paires de périodes du TOP10.
  **102 paires, 204 lignes** contrôlées contre **50 réponses fournisseur déjà
  archivées** : 204/204 retrouvées, empreintes exactes, zéro enveloppe invalide.
  Ce résultat ne certifie pas automatiquement les autres enveloppes du corpus.
- Dernières paires TOP10 : 72 comparaisons de périodes, dix titres présents ;
  aucune hausse/baisse conjointe nouvelle sur la dernière comparaison de week-end.

Les motifs se recouvrent. Parmi toutes les paires : 19 790 ont un nombre
d'analystes absent ou <3 à une extrémité, 2 678 manquent d'EPS ou de revenus.
Un compteur de révisions baissières à sept jours absent n'est jamais remplacé
par zéro. Un changement de moyenne du consensus n'est pas nécessairement une
révision par les **mêmes** analystes.

## Diagnostic de la semaine : ne pas confondre absence de nouveauté et absence d'information

Après lecture des features seulement, sans prix futurs, un diagnostic **distinct
et explicitement non confirmatoire** compare la première et la dernière vraie
observation du 11 au 18 octobre. Il ne remplace pas la règle adjacente figée
et ne fournit pas une performance de nouvelle stratégie.

12 374 comparaisons de périodes : 767 hausses conjointes, 806 baisses conjointes,
10 801 mixtes/stables/manquantes. Ce ne sont ni des probabilités ni des signaux
de trading qualifiés. Parmi le TOP10, exemples de périodes déclarées :

| Titre | Période fournisseur | EPS moyen : variation relative | Revenus moyens : variation relative | Réserve |
|---|---|---:|---:|---|
| DOCN | 2026-09-30, `0q` | +0,189 % | +0,022 % | Petites variations ; nombres d'analystes inchangés, définition/unités encore à qualifier |
| FUN | 2026-09-30, `0q` | −0,588 % | −0,174 % | Nombres d'analystes inchangés ; normalisation de date fiscale à vérifier |
| FMC | 2026-09-30, `0q` | −25,849 % | −58,279 % | Forte modification de la population d'analystes ; pas interprétable directement comme une baisse de guidance |
| BAND | 2026-12-31, `0y` | −0,166 % | −0,019 % | Annuel, pas trimestre ; composition d'analystes modifiée |

Les six autres titres n'ont pas de mouvement conjoint des deux moyennes dans
ce diagnostic. Cela n'exclut pas une variation d'une métrique seule.

### Réserve concrète FMC

Dans les items du trimestre déclaré au 30 septembre, du 16 au 17 octobre :
revenus moyens **866 672 520 → 361 586 890**, analystes revenus **10 → 5** ;
EPS moyen **0,1041 → 0,0786**, analystes EPS **15 → 9**.
Il s'agit bien des nombres reçus, mais on ne sait pas si la différence reflète
des révisions individuelles, une modification de contributeurs, une base
différente ou une anomalie fournisseur. Ne pas annoncer que FMC a abaissé
ses ventes de 58 % sur cette seule base.

## Vérifications publiques bornées : contexte partiel, pas déblocage automatique

- [DOCN, publication officielle du 4 août 2026](https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Second-Quarter-2026-Financial-Results/default.aspx)
  : trimestre de guidance au 30 septembre, revenus exprimés en millions de
  dollars et EPS dilué non-GAAP. Cela aide à vérifier le contexte émetteur,
  mais ne prouve ni que le consensus EODHD est sur cette même définition EPS,
  ni que la guidance d'août est la dernière connue en octobre.
- [FUN, communiqué SEC du deuxième trimestre 2026](https://www.sec.gov/Archives/edgar/data/1999001/000199900126000094/sixflags-exh991xq22026.htm)
  : le trimestre réel se termine le **28 juin**, pas le 30 juin fournisseur.
  Cela montre la nécessité d'une correspondance entre ancrage calendaire
  fournisseur et calendrier fiscal ; ne pas assimiler ces dates sans preuve.
- [FMC, résultats et perspectives officiels](https://investors.fmc.com/financials/quarterly-results/)
  : les perspectives distinguent revenu hors Inde et EPS ajusté. La
  comparabilité de périmètre est donc une question réelle ; cette page ne
  justifie pas le saut observé dans le consensus d'octobre.

Lecture documentaire actuelle, non seconde revue humaine indépendante ;
pas de HTML fournisseur historique nouvellement archivé par ces consultations,
pas de requalification globale en base. Pour refaire un test strict sur
2024–2025, ces pièces actuelles ne remplacent pas des vintages de consensus.

## Ce qu'il reste, de façon bornée

1. Revue bornée **DOCN et FUN terminée** : 112/112 lignes vérifiées contre
   16 enveloppes, identités concordantes ; période DOCN confirmée, rattachement
   fiscal FUN et définitions exactes du consensus encore réservés. Quatre
   documents publics archivés, une expiration conservée sans contournement.
   L'utilisateur a depuis envoyé les questions et transmis la réponse : unités
   complètes/USD DOCN-FUN, ancrages FUN et rôle de `0q`/`+1q` clarifiés ;
   base EPS par item et contributeurs inconnus. **Pas de nouveau signal qualifié**
   ni de qualification rétroactive à l'ouverture du 19.
   [Bilan et questions précises](qualification_consensus_docn_fun_20261019.md).
   Cette recherche publique bornée est close ; FMC reste réservé sur la
   composition/base.
2. Ne pas reconstruire les surprises d'annonces passées depuis le calendrier
   courant. Il faut un consensus archivé **avant** l'annonce et un réalisé
   publié **après**, avec période et définition compatibles.
3. Ne pas réentraîner ou lancer un backtest économique maintenant. La collecte
   prospective existe déjà ; préserver ses snapshots et ses enveloppes sans
   nouvelle activation ici.
4. Après qualification, suivre les horizons arrivés à maturité. La confirmation
   figée demande au moins **50 dates d'entrée distinctes et 100 épisodes TOP10
   sans chevauchement** sur de nouvelles périodes, pas seulement davantage
   de lignes ou le passage d'une seule date de maturité.

**Aucun abonnement supplémentaire n'est démontré indispensable à ce stade.**
Les obstacles actuels sont le sens et la comparabilité des observations, puis
la durée indépendante disponible. Un grand nombre de lignes ne les résout pas.

## Artefacts et contrôles

- Inventaire : `artifacts/research/us_directional_information/20261019-v2/`.
- Pilote : sous-dossier `observed-revisions-v1/` : protocole, snapshots, runs,
  scores et TOP10, paires, échantillon, enveloppes, contrôles et rapport scellés.
- Diagnostic distinct : `window-diagnostic/`, bornes, script et entrées identifiés
  par empreinte, jamais utilisé comme validation hors échantillon.
- **113 tests passent**, dont 23 nouveaux sur le pilote et six sur le diagnostic :
  aucune fausse rétroactivité, séparation fiscale/horizon, doublons, timestamps,
  source brute/normalisation, absence de qualification et compteurs manquants.
  Groupe ciblé, pas une certification de tous les tests du projet.

Les phases `snapshot` et `proofs` ne font que lire la base existante en
transaction READ ONLY / REPEATABLE READ, puis ROLLBACK ; les autres sont offline.
Les commandes du script exigent des dossiers frais ou des phases non déjà
terminées : ne pas écraser le dossier achevé. Aucun run de calcul ne reste actif.
