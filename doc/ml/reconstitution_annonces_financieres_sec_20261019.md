# Annonces financières SEC — reconstitution des 93 cas, 19 octobre 2026

## Bilan

**Les 93 cas ont été examinés ; toutes leurs preuves ne sont pas qualifiées.**
Les archives publiques ont permis de récupérer **154 dépôts originaux** pour
68 émetteurs. Aucun échec de téléchargement, aucun abonnement supplémentaire.

| Étape | Cas |
|---|---:|
| Cohorte initiale, inchangée | 93 |
| Annexe de résultats mentionnant explicitement le trimestre attendu | 70 |
| Encore TOP10 à la date de réaction recalée, parmi ces 70 | 65 |
| Quatre montants retrouvés dans les tableaux de l'annonce | 28 |
| Quatre montants non ambigus dans un même tableau/annexe | 27 |
| Chiffres de l'annonce, prix utilisables et TOP10 recalé | 23 |
| Accord provisoire comptabilité et réaction relative au marché | **7 : 4 LONG, 3 SHORT** |

**Sept accords ne signifient pas sept trades gagnants.** Aucun rendement futur,
PnL, entraînement ou backtest n'a été calculé. Aucune donnée SQL, configuration,
batch, modèle ou ordre modifié. Pas d'appel GPT/DeepSeek ni d'API payante.

La recherche demandée est terminée sur son périmètre borné. Le prochain test
devra reconstruire une cohorte choisie uniquement avec les informations
disponibles à la nouvelle date de décision : les 93 cas initiaux ne constituent
pas cette cohorte, même après vérification des nouveaux rangs.

## Acquisition publique autorisée et traçable

Sources : historique officiel des dépôts sur `data.sec.gov/submissions/`, puis
soumissions originales sous `www.sec.gov/Archives/edgar/data/`.
Les [API SEC](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
exposent les historiques d'émetteurs et des fichiers complémentaires pour les
périodes anciennes. La [politique développeur](https://www.sec.gov/about/developer-resources)
demande une collecte identifiée et modérée.

Contrat appliqué ici :

- `SEC_EDGAR_USER_AGENT` existant, sans enregistrer son contact dans les reçus ;
- TLS vérifié ; au plus deux requêtes par seconde, séquentielles ;
- hôtes et chemins SEC strictement autorisés, pas de redirection suivie ;
- une tentative par URL, réponses conservées, pas de contournement 403/429 ;
- bornes de 400 requêtes, 350 Mio cumulés, 20 Mio par document ;
- pas de collecte générale du site, pas de téléchargement d'options/news commerciales.

Résultat : **68 réponses d'historique et 154 documents, soit 222 requêtes**,
toutes réussies. Les documents représentent 168 431 852 octets, environ
161 Mio, hors métadonnées. URL, date réelle de récupération, HTTP, empreinte
SHA-256 et corps d'origine sont conservés. Aucun secret, token ou URL
authentifiée n'a été ajouté au dossier.

Dossier :
`artifacts/research/us_earnings_release_reconstruction/20261019-v1/`.
Il est distinct de la base et de l'audit précédent. Les anciens rapports sont
conservés, sans écrasement. Les captures publiques actuelles **ne sont pas
des réceptions Alpha-Trade en 2024 ou 2025**.

## Comment les annonces ont été recherchées

Les 93 accessions et les 68 CIK sont figés depuis le précédent audit. Pour
chaque cas, recherche des originaux 8-K/6-K entre la fin du trimestre ou les
60 jours précédant le dépôt, selon la borne la plus récente, et la date de ce
dépôt. Amendements exclus de cette première recherche. Aucune sélection selon
un cours ou rendement futur.

Au plus douze dépôts par cas étaient admis ; aucune troncature cachée.
Tous les historiques nécessaires dans ce périmètre ont été obtenus. Cela ne
certifie pas une recherche mondiale exhaustive ni les communiqués IR hors SEC.

Les annexes sont séparées du formulaire principal. Un rapprochement temporel
exige une mention explicite du trimestre attendu dans une annexe de résultats.
La première annexe SEC repérée est retenue, pas la dernière qui donnerait des
chiffres plus commodes.

**23 cas n'ont pas passé ce rapprochement explicite.** Ce n'est ni un échec
HTTP, ni la preuve qu'aucun résultat n'a été publié. Dates formulées autrement,
absence de l'annexe attendue dans cette fenêtre ou structure différente restent
des réserves ; ils ne sont pas automatiquement reclassés « sans événement ».

Exemple de structure : APP renvoie à une lettre aux actionnaires **EX-99.2**,
en plus du communiqué EX-99.1. Le contrôle des tableaux a donc conservé les
autres annexes EX-99 ; il ne prétend pas interpréter les images ou tous les
formats possibles. Aucun parser générique n'a promu seul une annonce.

## Recalage temporel conservateur

On conserve séparément :

1. date déclarée du communiqué, lorsqu'elle est examinée ;
2. acceptation SEC avec offset explicite, telle que fournie par son historique ;
3. réception réelle de notre copie aujourd'hui.

La séance de réaction retenue pour la reconstitution publique est la première
séance NYSE dont **l'ouverture est strictement postérieure à l'acceptation SEC**.
Acceptation préouverture : séance du jour possible. Acceptation pendant/après
la séance : séance complète suivante. L'entrée éventuelle serait à l'ouverture
suivante, après observation de la réaction. Aucune heure ou timezone n'a été
inventée à partir d'une date seule.

L'acceptation SEC n'est pas nécessairement la toute première diffusion IR.
Ce choix conservateur ne prétend donc pas mesurer exactement le choc initial
sur le cours. Il donne une disponibilité publique vérifiable, pas une preuve
de réception opérationnelle historique.

Sur les 70 rapprochements : **36 dates de réaction avancent**, 34 restent
identiques, aucune n'est repoussée. Le TOP10 du nouveau jour est relu dans
l'archive H20 de recherche déjà figée ; cinq cas n'y figurent plus. Aucun
remplacement par le rang suivant.

Exemples : BILL passe du 12 au 9 février 2024 ; AOSL du 7 au 6 février 2025 ;
TTMI du 4 mai au 30 avril 2026. Ces différences ne sont pas des profits calculés.

## Les chiffres du 10-Q ne sont pas antidatés

Le document trimestriel postérieur ne suffit pas à certifier ce que disait
l'annonce antérieure. Ses valeurs servent uniquement de **cibles de vérification** :
elles doivent être retrouvées dans le document diffusé plus tôt.

Contrôles sur les tableaux originaux :

- revenu et résultat opérationnel, trimestre courant et même trimestre précédent ;
- en-têtes trimestriels et ordre des années ; pas six/neuf mois pris pour un trimestre ;
- unité explicitement repérée en milliers ou millions ;
- nombres littéraux, parenthèses négatives conservées ; tiret manquant non remplacé par zéro ;
- rapprochement limité à la moitié de l'unité de présentation pour les arrondis ;
- lignes d'exploitation, pas EBITDA ajusté assimilé au résultat opérationnel ;
- pour le recalage, les quatre nombres doivent appartenir à **un même tableau
  cohérent dans une même annexe**. Pas de mélange entre tableaux.

28 cas passent le rapprochement initial ; 27 passent ce dernier contrôle.
HLF, accession `0000950170-24-051335`, reste réservé : les rapprochements ne
donnent pas un quartet non ambigu dans un même tableau cohérent.

Les variations recalculées utilisent ensuite **les montants publiés dans
l'annonce**, non les valeurs plus précises du 10-Q. La comptabilité en hausse
est définie par revenu et marge opérationnelle tous deux en hausse, la baisse
par les deux en baisse ; sinon abstention. Une hausse minime de nombres
arrondis n'est pas une surprise économique démontrée.

Ces correspondances techniques ne certifient pas toutes les acquisitions,
scissions, changements de périmètre, retraitements ou identités historiques.
Les extraits/tableaux ont été examinés ; pas de lecture humaine intégrale de
154 soumissions ni de seconde revue indépendante annoncée.

## Résultat des features recalées — aucun résultat de trading

| Année de la cohorte initiale | Quatre nombres dans un tableau cohérent | Features calculables et TOP10 recalé | Accords provisoires |
|---|---:|---:|---:|
| 2024 | 12 | 11 | 1 LONG |
| 2025 | 12 | 9 | 1 LONG, 3 SHORT |
| 2026 au 1er septembre | 3 | 3 | 2 LONG |
| **Total** | **27** | **23** | **4 LONG, 3 SHORT** |

Motifs comptables et prix concordants dans ce diagnostic : HPK deux fois,
LASR, QDEL, TTMI, TXG et W. Ce ne sont pas des recommandations ou ordres.
Par exemple, une marge qui s'améliore peut rester négative ; cela ne signifie
pas que l'entreprise devient bénéficiaire.

Ces **sept** accords ne sont pas les **24** anciens accords calculés autour
des dépôts, ni les **24** cas du rapprochement de tableaux intermédiaire encore
TOP10. Chaque chiffre correspond à une étape différente, avec ses réserves.

## Point bloquant pour un véritable backtest : sélection à la date correcte

Les 93 cas ont été sélectionnés initialement parce que le titre était TOP10 à
la date d'observation **du 10-Q**. Pour les annonces plus anciennes, cette
condition peut dépendre d'un classement qui n'existait pas encore à l'entrée.
Vérifier à nouveau que le titre était TOP10 le jour de l'annonce ne supprime
pas cette condition future ayant servi à constituer l'échantillon.

**Trois des sept accords provisoires présentent ce problème : LASR, QDEL,
TTMI.** Les quatre autres ne deviennent pas pour autant une validation de
stratégie représentative. Nous ne calculons pas un PnL sur les sept, ni sur les
quatre restants après sélection, en prétendant avoir testé la stratégie.

La suite correcte est de repartir de la population complète des publications
sur le périmètre temporel retenu, puis de sélectionner **uniquement selon le
TOP10 disponible à la date de réaction corrigée**, avant toute lecture des
rendements futurs. Cela peut ajouter des cas absents de la liste initiale :
ce serait une nouvelle cohorte figée, pas une extension au TOP20 %.

Cette reconstitution plus large n'a pas été lancée dans le travail borné aux
93 cas. Aucun nouvel apprentissage n'est justifié avec sept accords, encore
moins une promotion live ou une affirmation d'efficacité directionnelle.

## Scripts, archives et vérifications

- `us_earnings_release_reconstruction.py` : protocole, découverte, acquisition,
  rapprochement temporel ; chaque URL archivée, phases achevées non écrasables.
- `us_earnings_release_table_review.py` : vérification des montants des annexes,
  dossier immuable `table-review-v1/`.
- `us_earnings_release_recalage.py` : montants de l'annonce et réaction prix à
  J seulement, dossier `recalage-v1/` ; aucun parcours futur utilisé.
- `us_earnings_release_reconstruction_audit.py` : contrôles d'empreintes,
  reproduction des 27 calculs de montants/réactions, contrôle des 93 cas et des
  nouvelles dates, signalement explicite du biais de sélection future.
- `selection-causality.json` détaille les réserves cas par cas.
- Les tests couvrent accès autorisés, absence d'heure inventée, première séance
  complète, tableaux/échelles/arrondis, absence de mélange et causalité.
- **189 tests ciblés passent**, dont 35 nouveaux pour cette reconstitution.
  Ce total couvre les douze fichiers du groupe de régression, pas tous les
  tests de l'application.

Le rapport final distingue preuve/source/features et autorisation d'un test
économique. **Aucun test économique n'a été lancé** ; aucun job de collecte de
ce dossier ne reste actif.
