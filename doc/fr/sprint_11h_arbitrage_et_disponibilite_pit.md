# Sprint 11-H — Arbitrage préparatoire et qualification PIT

État du 4 octobre 2026. Suite de la [seconde passe technique 11-G](sprint_11g_seconde_passe_documentaire.md).

## Résultat et limites

La vérification du dossier `second-review-20261004-v4` confirme :

- 33 fiches, 33 décisions indépendantes `PENDING` ; aucun second lecteur renseigné.
- 38 PDF de preuve uniques ; leurs 38 empreintes correspondent au dossier.
- Zéro champ `historical_web_available_at` renseigné pour ces preuves.
- Toutes les fiches conservent `training_eligible=false`.

L'absence de champ renseigné n'est pas une preuve que les communiqués n'étaient
pas publics. Elle signifie que le dossier ne possède pas encore la qualification
requise par son contrat PIT strict. Les données ne doivent pas être antidatées.

Le présent document fournit un **arbitrage technique proposé**, pas des décisions
de revue indépendante. La même IA ne peut pas se déclarer indépendante de sa
première lecture. Ni un nouveau prompt, ni une nouvelle session ne suffisent.
Le validateur existant exige un lecteur identifié, une date, une justification,
une décision explicite et les contrôles sémantiques pour toute acceptation.
Il conserve l'inéligibilité ML même après validation sémantique.

## 1. Pièces et intégrité

Dossier :
[README du dossier v4](../../artifacts/fr/research/guidance_completion_11e/second-review-20261004-v4/README.md).

Grille à remplir par le second lecteur :
[second_review.json](../../artifacts/fr/research/guidance_completion_11e/second-review-20261004-v4/second_review.json).

Empreinte SHA-256 de la grille avant et après cette qualification technique :
`92e1c1ab6a988a49c3f3fb67e9ab3791e1d92d61a0a29f56233ded7d05cbca67`.
La grille n'a pas été modifiée. Les copies PDF sont intègres, mais leur intégrité
depuis la collecte de 2026 ne prouve pas une disponibilité identique en 2019–2025.

## 2. Arbitrages proposés, à valider

| Cas | Arbitrage technique proposé | Pièce ou décision encore requise |
|---|---|---|
| Nexans octobre 2022 | Maintenir la contradiction du PDF français. Les sources officielles anglaises retrouvées corroborent 580–600 M€, mais l'ancienne plage 560–590 chevauche encore la nouvelle. Une corroboration de bornes ne suffit pas à faire passer la règle stricte de séparation. | Archiver et contrôler les documents corroborants, dater leur disponibilité, décider d'une politique explicite de révisions à intervalles chevauchants. Aucun choix opportuniste entre pages. |
| SMCP septembre 2023 | Ancienne marge exprimée par une amélioration contre le réalisé 2022 de 9,2 % : encodage proposé `greater_than(9.2)`, non point exact. Nouvelle plage 7–9 % entièrement inférieure. | Validation indépendante du comparatif et de la définition de marge ; nouvelle version du manifeste avant de promouvoir ce cas complexe. |
| Arcure décembre 2024 | Garder `RESERVE` pour une direction stricte : point central abaissé, mais plage 18,2–20 touchant l'ancienne cible 20. Corriger dans une future version l'affirmation trop absolue selon laquelle 18,2 n'est pas une nouvelle borne. | Distinguer cible centrale et intervalle ; ne pas inventer une probabilité. Une politique sur centres de plages serait un protocole séparé. |
| Aramis avril 2022 | Événement mixte : CA relevé, marge dégradée. Pas de label global UP. | Si usage ultérieur, label par métrique avec règle d'agrégation pré-enregistrée ; ne pas sélectionner seulement le CA favorable. |
| Ubisoft septembre 2024 | Ne pas fabriquer d'ancienne cible annuelle numérique à partir du réalisé précédent. Garder la réserve annuelle ; le trimestre constitue une autre tâche. | Source comparable pour l'ancienne cible annuelle ; ou protocole trimestriel distinct, après réconciliation de la coquille d'exercice. |
| SMCP décembre 2019 | Réserve maintenue : traitement de De Fursac et comparaison au réalisé 2018 non complètement réconciliés. | Même périmètre pour ancienne/nouvelle guidance, preuve du comparatif 2018 et opérateur « stable ». |
| Klépierre août 2023 | Hausse déclarée de cash-flow par action, mais hypothèses de cessions actualisées. Ne pas qualifier la hausse de surprise à périmètre constant. | Arbitrer si le protocole admet une révision publiée avec hypothèses changées. Sinon réserver la paire, même si elle figurait parmi les propositions initiales. |
| Aramis décembre 2021 | Relèvement de plancher annuel ; ancien périmètre à corroborer avec le nouveau périmètre au 30 septembre 2021. | Ancienne source et notes de périmètre, pas seulement rappel numérique. |
| Bastide mars 2025 | Hausse proposée de marge opérationnelle courante ; ne pas ajouter un opérateur « au moins » à l'ancienne valeur sans pièce. | Contrôle du périmètre et de la définition dans l'ancienne cible. |

Les quatre classifications hors tâche annuelle restent séparées : Bonduelle
(exercice déjà clos), Maisons du Monde du 26 octobre (confirmation de la baisse
financière, mais nouvel objectif d'économies distinct), Capgemini ESG et Exosens
(estimations passées/nouvel exercice ; objectif pluriannuel distinct). Leur rejet
de cette tâche ne veut pas dire que leurs communiqués n'ont aucune information.

### Corroborations gratuites repérées pendant cette passe

- [Nexans, communiqué anglais Q3 2022](https://www.nexans.com/app/uploads/2024/02/2022-10-26-pr-nexans-third-quarter-2022.pdf).
- [Nexans, présentation Q3 2022](https://www.nexans.com/app/uploads/2022/02/2022-10-26-presentation-nexans-q3-2022.pdf).
- [SMCP, ajustement de guidance 18 septembre 2023](https://www.smcp.com/app/uploads/2023/09/press-release-smcp-adjusts-its-2023-annual-guidance.pdf).
- [Klépierre, diffusion Euronext 1 août 2023](https://live.euronext.com/en/products/equities/company-news/2023-08-01-klepierre-2023-full-year-guidance-raised-least-eu240).

Ces URL et contenus indexés sont des pistes de corroboration observées aujourd'hui,
pas des archives historiques certifiées. Ils n'ont pas été ajoutés au manifeste
v4 ni assimilés à des copies locales contrôlées. La page Euronext affiche une
date/heure de diffusion ; un affichage actuel ne prouve pas à lui seul son état
historique. Ne pas utiliser les répertoires d'URL comme dates de disponibilité.

## 3. Contrat de date à respecter

| Information | Ce qu'elle établit | Utilisation autorisée |
|---|---|---|
| Date inscrite dans le PDF | Date revendiquée par l'émetteur | Champ documentaire, pas `available_at` automatique |
| Heure inscrite dans le PDF | Heure revendiquée, parfois sans fuseau | Indice à corroborer, pas heure d'entrée de trading |
| `transmission_proxy_day` DILA reconstruit | Jour historique rapporté par la source consultée actuellement | Analyse de sensibilité explicitement non stricte ; pas preuve de vintage |
| `observed_at` | Moment réel de la collecte actuelle, en UTC | Traçabilité ; ne pas le remplacer par la date du communiqué |
| Capture d'archive datée et contenu contrôlé | Contenu observable au plus tard à la capture, sous réserve de la fiabilité de l'archive | Borne de disponibilité, pas nécessairement première diffusion |
| Accusé de diffusion/version archivée horodatée | Événement de diffusion et version, si l'horodatage est suffisamment qualifié | Candidat à une disponibilité historique qualifiée |

Une date sans heure ne permet pas d'entrer à l'ouverture du même jour. Une
publication après clôture ne permet pas une décision à la clôture qui la précède.
Les fuseaux Europe/Paris et UTC doivent être conservés explicitement, avec
traitement de l'heure d'été et du calendrier des séances, sans simple ajout de
24 heures. Une capture bien plus tardive ne permet pas de déplacer son contenu
à la date initiale revendiquée.

Le lag d'une ou deux séances peut tester la sensibilité **sous hypothèse de date
de diffusion** ; il ne transforme pas une reconstruction actuelle en preuve PIT.
Pour un corpus strict, si aucune borne historique utilisable n'est prouvée,
la fiche reste `HISTORICAL_PIT_UNQUALIFIED` et hors jeu d'entraînement historique.

## 4. Qualification actuelle des 33 fiches

Les 33 fiches ont toutes un proxy de jour et une observation de collecte du
4 octobre 2026 ; aucune ne possède de disponibilité historique Web qualifiée
dans le dossier. Leur statut PIT strict est donc identique : **non qualifié**.
Il ne faut pas remplacer les 33 valeurs manquantes par leurs proxies.

Priorité de recherche, sans regarder les rendements :

1. Assystem 24/10/2024, Maisons du Monde 09/10/2023, Icade 29/11/2024 et
   Sodexo 20/03/2025 : ce sont les quatre annonces déjà recoupées avec le pool
   Oracle figé. Rechercher une preuve historique de diffusion et de version,
   non un meilleur score de trading.
2. Sources d'antécédents et de périmètre pour les cas du tableau d'arbitrage.
3. Les autres paires, suivant la même règle et sans sélectionner les futurs
   gagnants. Conserver un registre des tentatives, erreurs d'accès et absences.

Les 26 observations exposées à lag 1 / fenêtre 30 ne sont pas 26 annonces
indépendantes. Même une qualification réussie de leurs quatre événements ne
résoudrait pas automatiquement l'absence de D10 dans le train directionnel.

## 5. Remise au lecteur indépendant

Le lecteur doit consulter les pages et notes sans rendements, remplir les
33 décisions `ACCEPT`/`REJECT`/`RESERVE`, son identité, la date et les motifs.
Il peut accepter une classification hors tâche sans accepter un label ML.
Pour toute paire acceptée, il confirme explicitement : ancienne valeur
prévisionnelle, même exercice/métrique/périmètre, opérateurs corrects, absence
de doublon. Les cas complexes nécessitent d'abord une preuve et une version
de manifeste révisées : ne pas les accepter en forçant les cases de la grille.

Commande de validation, **après** remplissage réel de la grille :

```powershell
python -m service.fr.guidance_completion_11e validate-second-review --output artifacts/fr/research/guidance_completion_11e/second-review-20261004-v4
```

La commande échouerait actuellement sur les décisions PENDING. Ce comportement
est attendu et ne doit pas être contourné. Son succès futur ne qualifie ni le PIT
ni les effectifs ; il enregistre seulement la revue sémantique déclarée.

## 6. Point d'arrêt

La revue indépendante réelle manque encore. L'arbitrage final attend ses
décisions ; les preuves PIT historiques ne sont pas qualifiées. Aucun abonnement
n'est démontré indispensable et les sources gratuites ne sont pas déclarées
épuisées. Aucun code source, batch, modèle ou table canonique n'a été modifié
par cette qualification. Pas d'entraînement ni de backtest autorisé.
