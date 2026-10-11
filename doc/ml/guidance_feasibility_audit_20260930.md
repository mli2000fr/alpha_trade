# Guidance : audit de faisabilité du 30 septembre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

**Verdict : faisabilité documentaire ponctuelle confirmée ; DATA_NOT_READY pour un test directionnel.** Deux révisions explicites de ventes sont retrouvées, mais chez un seul émetteur. L'audit ne justifie ni un entraînement D1/D10 ni la réouverture du parseur E21 sous forme d'une B9.

## Périmètre et traçabilité

Travail autorisé : relire les échecs E21, examiner les données conservées, constituer un petit corpus distinct et décider de la faisabilité avant les rendements. Aucune base SQL interrogée ou modifiée, aucun rendement de marché utilisé, aucun modèle entraîné, aucun code de production modifié. Les chiffres anciens ci-dessous sont ceux des comptes rendus, pas des résultats recalculés.

Protocole enregistré avant recherche des publications : `work/guidance_feasibility_20260930/protocol.json`. Annotations structurées : `work/guidance_feasibility_20260930/corpus_review.json`. Inventaire et empreintes locales : `work/guidance_feasibility_20260930/local_evidence.json`.

Les sources officielles ont été consultées avec l'outil web. Les URL, dates affichées, sections et valeurs sont consignées. Aucun HTML brut des sources web ni hash historique de leur contenu n'est archivé dans ce run. La revue est une lecture par assistant des pages et sections pertinentes : ce n'est ni une annotation humaine indépendante ni une mesure exhaustive du rappel documentaire.

## État des données locales

- `artifacts/research` absent dans ce checkout au moment de l'audit.
- Aucun fichier `collection_report`, `review_queue`, `manual_annotations`, `role_reference` ou `validation_report` retrouvé par la recherche de noms dans le workspace, y compris les fichiers ignorés, hors `.git`.
- `artifacts/sec_cache` contient 1 646 fichiers Company Facts et `company_tickers.json`. Un fichier Company Facts a été inspecté : il expose des namespaces de faits comptables. Ce cache n'est pas un corpus identifié d'anciennes/nouvelles guidances.
- Les sources Python, tests et documents E21 restent présents. L'absence locale des artefacts ne prouve pas leur absence dans une base ou une sauvegarde extérieure ; celles-ci n'ont pas été auditées.

## Pourquoi B4 à B8 ont échoué

| Campagne | Précision classée documentée | Couverture NEW documentée | Défaut principal |
|---|---:|---:|---|
| B4 | 94,1 % | 14,5 % | Headings non reconnus ; note inline corrompant une borne |
| B5 | 68,2 % | 100 % | Sept anciennes prévisions classées nouvelles ; annexes ANF manquées |
| B6 | 85,1 % | 97,1 % | Sept paires de valeurs historiques prises pour des intervalles ; couverture BWA/CCK non démontrée |
| B7 | 100 % | 62,1 % | Abstention excessive ; quatre fourchettes de revenus manquées ; rappel NEW bout en bout 58,1 % |
| B8 | 100 % | 41,5 % | Couverture APOG 1/6 ; montants sans zéro initial et portée des headings ; rappel global non mesurable |

Source : [validation E21-B4 à B8](guidance_table_validation_protocol_e21b4.md). Ces chiffres portent sur les corpus et règles de chaque campagne : ils ne forment pas une courbe de progrès comparable à population constante. Les 100 % de B7/B8 sont conditionnels aux décisions prises, avec un petit support. Ils ne prouvent pas une extraction exhaustive.

L'échec cumule quatre niveaux : inventaire des publications, récupération des bonnes annexes, extraction du rôle et des nombres, puis appariement sémantique/PIT. Améliorer seulement la regex ne répare pas les quatre.

## Petit corpus figé avant lecture

Choix raisonné, non aléatoire : DECK, ULTA, ETSY ; communiqués de résultats publiés du 1er avril au 31 août 2024. Deux publications identifiées par émetteur. Aucun remplacement après découverte d'une absence de guidance. Aucun de ces tickers n'a été retrouvé dans les documents et tests E21 recherchés ; cela ne prouve pas qu'ils sont inconnus de l'ensemble du projet.

Les pages de résultats officielles permettent d'inventorier les publications trimestrielles sélectionnées. Elles ne garantissent pas l'absence d'une révision intermédiaire publiée lors d'une conférence, d'un autre 8-K ou d'une autre communication.

| Émetteur / date | Lecture sur les ventes annuelles | Conclusion documentaire |
|---|---|---|
| ULTA, 30 mai 2024 | FY2024 : ancienne fourchette 11,7–11,8 Md USD ; nouvelle 11,5–11,6 | Révision explicite dans un même tableau |
| ULTA, 29 août 2024 | FY2024 : ancienne fourchette 11,5–11,6 ; nouvelle 11,0–11,2 | Deuxième révision explicite ; ancienne valeur corroborée par mai |
| DECK, 23 mai puis 25 juillet 2024 | FY2025 se terminant le 31 mars 2025 : objectif approximatif de 4,7 Md USD maintenu | Objectif ponctuel, pas fourchette ; cession Sanuk annoncée en juillet : comparabilité de périmètre à vérifier |
| ETSY, 1er mai puis 31 juillet 2024 | Indications GMS, take rate, croissance et marge ; aucune paire de prévisions annuelles de revenus en dollars identifiée | Abstention pour la cible choisie ; GMS n'est pas le chiffre d'affaires |

Sources officielles, lues le 30 septembre 2026 :

- [ULTA mai — tableau Fiscal 2024 Outlook](https://www.ulta.com/investor/news-events/press-releases/detail/185/ulta-beauty-announces-first-quarter-fiscal-2024-results).
- [ULTA août — tableau Fiscal 2024 Outlook](https://www.ulta.com/investor/news-events/press-releases/detail/187/ulta-beauty-announces-second-quarter-fiscal-2024-results).
- [DECK mai — perspectives FY2025](https://ir.deckers.com/news-events/press-releases/detail/240/deckers-brands-reports-fourth-quarter-and-full-fiscal-year-2024-financial-results).
- [DECK juillet — perspectives FY2025 et cession Sanuk](https://ir.deckers.com/news-events/press-releases/detail/237/deckers-brands-reports-first-quarter-fiscal-year-2025-financial-results).
- [ETSY mai — guidance Q2 et perspectives annuelles](https://investors.etsy.com/news-events/press-releases/detail/26/etsy-inc-reports-first-quarter-2024-results).
- [ETSY juillet — guidance Q3 et perspectives annuelles](https://investors.etsy.com/news-events/press-releases/detail/22/etsy-inc-reports-second-quarter-2024-results).

Calculs descriptifs ULTA : le milieu passe de 11,75 à 11,55 Md USD, soit −0,20 Md / −1,7021 %, puis de 11,55 à 11,10, soit −0,45 Md / −3,8961 %. Ces pourcentages mesurent la révision de prévision, jamais un rendement boursier. Les deux événements appartiennent au même émetteur et ne constituent pas deux preuves indépendantes de généralisation. La corroboration entre mai et août ne crée pas un troisième événement.

DECK constitue un contrôle important : une hausse de l'EPS prévu ne doit pas devenir une hausse des ventes prévues. Le maintien nominal de 4,7 n'est pas transformé en label comparable tant que l'effet de la cession n'est pas clarifié. Aucun exemple de hausse de ventes n'est observé dans ce petit corpus ; on ne cherche pas un émetteur de remplacement pour en fabriquer un.

## Limites concrètes dans le code actuel

1. **Détection limitée aux fourchettes dollar.** `guidance_audit.py:39` cherche deux bornes ; le motif à la ligne 44 exige un chiffre avant la décimale. Les objectifs ponctuels comme DECK et certaines formes `$.xx` échappent à cette représentation. Le commentaire de `guidance_structured.py` reconnaît explicitement l'absence des points et pourcentages. Il faut représenter point, intervalle, borne unilatérale et absence séparément ; ne pas inventer une fourchette à partir d'un point approximatif.
2. **Appariement conçu entre publications.** `guidance_structured.py:173` rejette `old_at >= new_at`. Une ancienne et une nouvelle prévision explicitement affichées dans le même communiqué possèdent le même instant documentaire : ce chemin les rejette. Ce garde est pertinent pour un prédécesseur chronologique, mais insuffisant pour un événement OLD/NEW porté par un seul document. Une future représentation doit distinguer ces deux modes. Pour la paire dans un même document, la disponibilité de l'événement est celle du communiqué nouveau ; il ne faut pas inventer une date plus ancienne pour contourner le garde.
3. **Prédécesseur observé, pas forcément autoritatif.** `pair_reviewed()` rapproche les lignes adjacentes du groupe sémantique, mais ne prouve pas l'exhaustivité des publications. Un événement explicitement ancien/nouveau, les doublons prose/tableau et une publication manquante doivent être traités au niveau de l'événement. Le code conserve à juste titre `historical_predecessor_completeness_validated=false` et `ml_eligible=false`.
4. **Inventaire des dépôts distinct de la couverture des annexes.** `guidance_backfill.py` limite à deux annexes et 2 Mo ; le mode index JSON choisit certains noms. `inventory_complete_for_requested_items` ne certifie pas que toutes les annexes pertinentes ont été collectées. La voie actuelle ne justifie pas un backfill massif.
5. **Couverture et exactitude sont distinctes.** Dans `guidance_role_evaluation.py:86`, le gate NEW utilise la part non abstention, pas le rappel correct NEW ; le rapport expose aussi une mesure NEW correctement classée. Les anciens échecs restent des échecs, mais une validation future doit explicitement imposer le rappel correct de bout en bout et le contrôle des paires, pas seulement la couverture des candidats détectés.

Ces constats proviennent d'une lecture statique. Aucun résultat de tests d'exécution du parseur n'est revendiqué. Le parseur n'a pas été retouché sur ce nouveau corpus.

## Décision et chemin utile

| Question | Verdict |
|---|---|
| L'information ancienne/nouvelle existe-t-elle dans des sources officielles ? | Oui, deux révisions ULTA explicitement lisibles |
| Le cache local fournit-il aujourd'hui un dataset de guidance prêt ? | Non démontré ; anciens corpus de recherche absents ici |
| Le parseur E21 peut-il être déclaré généralisable ? | Non ; limites historiques et de représentation toujours présentes |
| Les six publications valident-elles la chaîne PIT ? | Non ; heure historique, contenu original et inventaire intermédiaire non validés |
| Peut-on lancer un modèle directionnel maintenant ? | Non ; zéro événement ML-éligible dans ce run |
| Faut-il conclure que la guidance ne prédit rien ? | Non ; aucun pouvoir prédictif mesuré |

La voie raisonnable est un corpus de référence revu, construit au niveau des événements, avant toute nouvelle automatisation. Ce corpus DECK/ULTA/ETSY devient dès maintenant un corpus exploré : une correction du parseur sur ces exemples exigera une autre confirmation.

Une suite de collecte/annotation pourrait être bornée à dix émetteurs supplémentaires choisis par identifiants et disponibilité documentaire, sans rendement, avec deux années de publications et recherche de prédécesseurs. Le nombre dix est un budget de pilote proposé, pas un seuil de puissance statistique ni un gate déjà franchi. Aucune telle collecte n'est exécutée dans cet audit.

Le contrat minimal par événement doit conserver : identité et accession/source, période fiscale, mesure, unité, périmètre, type de valeur, anciennes/nouvelles valeurs, preuves de rôle et de comparabilité, disponibilité de l'événement, liens au prédécesseur lorsqu'il est nécessaire, état de revue et motif d'abstention. Une même révision ne doit être comptée qu'une fois malgré plusieurs citations.

Avant ML : inventaire des publications et des exclusions, snapshots sources avec hash, adjudication humaine indépendante, rappel mesuré sur documents complets, précision au moins 95 %, rappel NEW correct de bout en bout au moins 80 %, aucun faux intervalle accepté, validation séparée des paires et du PIT. Ce sont des critères de passage, pas des résultats obtenus. Restaurer les anciens artefacts aiderait la reproductibilité mais ne suffirait pas à franchir ces gates.

**Recommandation : conserver la piste guidance comme recherche de données supervisée ; ne pas investir maintenant dans un nouveau classifieur ni une B9 de règles ad hoc.** La faisabilité d'un petit corpus annoté est établie ; celle d'un historique automatique suffisamment dense et PIT ne l'est pas.
