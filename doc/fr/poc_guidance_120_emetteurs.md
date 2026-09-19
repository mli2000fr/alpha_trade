# POC France — faisabilité des révisions de guidance (120 émetteurs)

Date : 17 septembre 2026. Statut : **test de faisabilité documentaire terminé ; aucun signal D1/D10 démontré**. Aucun entraînement, backtest, ordre ni table applicative n'a été modifié. Cette étude est le premier palier avant un éventuel test historique sur un univers français tradable.

## Question et périmètre

Peut-on reconstruire, à partir des publications réglementées françaises gratuites, une variable point-in-time telle que « nouvel objectif moins ancien objectif » ? Il faut d'abord vérifier l'accès, la stabilité des publications et la possibilité d'extraire des paires chiffrées. Ce POC **ne teste pas** si la variable prédit D1/D10.

Source : [API publique INFO-FINANCIERE/DILA](https://www.data.gouv.fr/dataservices/api-info-financiere). Les exports bruts ont été conservés, avec empreinte SHA-256 et date de collecte, sous [le dossier du run](../../artifacts/research/fr_guidance_feasibility/pilot-20260917-124430/metadata_report.json). Le script reproductible est [fr_guidance_feasibility.py](../../scripts/research/fr_guidance_feasibility.py).

## Échantillonnage préétabli

1. Recenser les ISIN `FR` ayant au moins deux dépôts datés de 2024–2025 dans le flux public : **636 groupes**.
2. Tirer de façon déterministe **120 émetteurs**, par quatre classes de fréquence des dépôts (2–9, 10–29, 30–99, 100+), graine `fr-guidance-20260917` : [liste figée](../../artifacts/research/fr_guidance_feasibility/pilot-20260917-124430/selected_issuers.json).
3. Exporter leurs métadonnées 2018–2025 et retenir les URL PDF avec titre financier : **120 exports réussis, 0 échec, 2 027 candidats**. Au premier passage, les 120 comptes de l'export coïncidaient avec `records.total_count`. Les JSON bruts sont conservés par ISIN.
4. Avant de lire les PDF, présélectionner **12 titres évoquant une révision** et **12 autres titres financiers**, maximum deux par émetteur et par catégorie : [sélection figée](../../artifacts/research/fr_guidance_feasibility/pilot-20260917-124430/selected_pdfs.json). Ce sous-échantillon est un test de parseur, non une estimation représentative de la fréquence de guidance dans les 120 émetteurs.
5. Retélécharger plus tard un échantillon déterministe de 20 exports : **0 changement de nombre de lignes, 0 changement d'octets, 0 erreur** lors de ce contrôle rapproché : [rapport de relecture](../../artifacts/research/fr_guidance_feasibility/pilot-20260917-124430/recheck_report.json). Le flux avait été instable pendant le POC antérieur sur 18 titres ; ce contrôle ponctuel ne garantit pas sa stabilité dans le temps.

Les 120 ISIN sont diversifiés **par fréquence de publication**, pas vérifiés par secteur, liquidité, type d'instrument ou appartenance à XPAR. Ne pas les traiter comme 120 actions ordinaires tradables, ni étendre directement à 500 titres.

## Lecture des 24 PDF

[Audit PDF détaillé](../../artifacts/research/fr_guidance_feasibility/pilot-20260917-124430/pdf_audit.json) et [synthèse](../../artifacts/research/fr_guidance_feasibility/pilot-20260917-124430/pdf_report.json) : 23/24 PDF lisibles par extraction de texte (au moins 500 caractères), 1 échec de lecture. Dix documents présentent automatiquement des mots suggérant « ancien » et « nouveau » ainsi que plusieurs nombres. **Cette cooccurrence n'est pas une paire de guidance validée.** Les tableaux PDF, les notes et les définitions comptables nécessitent encore une vérification humaine.

Lecture manuelle du texte des 12 PDF de la catégorie « titre de révision » :

| Émetteur / document | Classement conservateur | Motif |
| --- | --- | --- |
| Lagardère Publishing, 2021 | Paire comparable dans le PDF | Objectif de marge antérieur et nouvel objectif chiffrés. |
| Vallourec, 2024 | Paire comparable dans le PDF | Fourchette antérieure de RBE/EBITDA 2023 et estimation nouvelle. |
| Aubay, 2021 | Paire comparable dans le PDF | Deux fourchettes de chiffre d'affaires annuel. |
| Orange, 2025 | Paire comparable dans le PDF | Objectif antérieur et nouvel objectif de cash-flow organique 2025. |
| HOPIUM, 2025 | Faux positif | Regroupement d'actions et calendrier prévisionnel, pas révision de résultat. |
| Deux calendriers de communication financière, 2022 et 2023 | Faux positifs | Dates de publication prévues, pas objectifs économiques. |
| Vallourec, 2021 | Révision partielle | Nouvel objectif présent, valeur antérieure absente du même PDF. |
| Lectra, 2020 | Référence à une révision antérieure | Publication de résultats « en ligne » avec des objectifs déjà révisés. |
| Lectra, 2023 | Confirmation, pas nouvelle révision | Objectifs révisés plusieurs mois auparavant. |
| Valneva, 2023 | Non comparable directement | Ancien objectif et nouvel objectif ne recouvrent pas le même périmètre de revenus (effet PRV). |
| Entech, 2024 | Objectifs nouveaux seulement | Objectifs stratégiques sans ancienne valeur comparable dans le PDF. |

Ainsi **4/12** PDF préfiltrés par titre présentent une paire chiffrée directement comparable dans le même document. Ce nombre est un diagnostic de faisabilité sur un petit échantillon, pas une précision statistique généralisable. Pour les autres cas, une jointure vers l'annonce antérieure, un contrôle de périmètre comptable ou un rejet est nécessaire. Les deux PDF de calendrier ont motivé un garde-fou pour les **futurs** tirages ; la sélection figée ci-dessus n'a pas été réécrite a posteriori.

## Contrat nécessaire avant tout test directionnel

- Identifier chaque document par ISIN, URL, empreinte et horodatage ; vérifier l'heure réellement accessible au public. L'horodatage de transmission DILA seul ne prouve pas l'heure de disponibilité. Si celle-ci est incertaine, signal utilisable au plus tôt à la séance suivante, avec marge de sécurité.
- Extraire **métrique, unité, période cible, périmètre, ancien intervalle, nouveau intervalle** et preuve textuelle/page. « Revenus produits » et « revenus totaux avec PRV » ne forment pas une révision comparable.
- Rechercher l'ancienne guidance dans l'historique uniquement lorsqu'elle est antérieure et déjà publiée ; versionner les paires et faire contrôler manuellement un échantillon indépendant.
- Construire un univers XPAR d'actions ordinaires tradables **à chaque date**, avec prix corrigés des opérations sur titres. La sélection du présent POC n'est pas cet univers.
- Mesurer couverture (titres/jours), précision des paires, délai et émetteurs manquants. Puis seulement évaluer Oracle France et D1/D10 H5/H10/H20, en walk-forward avec embargo et OOS gelé ; comparer à Oracle/prix seuls et aux coûts FR. Une amélioration du classement sur les 12 PDF examinés serait sans valeur.

**Décision : GO pour un parseur de guidance supervisé et une validation PIT ; NO-GO pour prétendre déjà disposer d'une feature directionnelle exploitable.** Tester 500 titres ou entraîner un modèle maintenant amplifierait surtout les erreurs de labels et de disponibilité.
