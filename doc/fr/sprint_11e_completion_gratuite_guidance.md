# Sprint 11-E — Complément gratuit et dossier de seconde revue guidance

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Date : 4 octobre 2026. Marché FR. Recherche uniquement.

**Actualisation v4 :** consulter [11-F, sources gratuites et seconde revue](sprint_11f_sources_gratuites_et_seconde_revue.md).
151 PDF, 23 paires proposées (13 UP/10 DOWN), 6 cas complexes et 4 autres
classifications ; seconde lecture toujours en attente. Quatre annonces recoupent
le pool Oracle à 1j/30j : 26 observations, seulement 4 exposées au train par fold.
61 tests ciblés passent. Les nombres v2 ci-dessous sont conservés comme état
historique de la première passe, pas comme effectifs actuels.

## Statut

**Sprint 11 reste ouvert. Aucun fournisseur payant n'est démontré indispensable.**
La collecte gratuite a été élargie et trois anciennes prévisions manquantes
retrouvées. Une seconde lecture indépendante a été autorisée par l'utilisateur.
Il reste aussi à obtenir un support suffisant dans les événements Oracle et à
qualifier la disponibilité historique. Aucun gain D1/D10 n'est démontré.

Cette passe ne refait ni les modèles AMF/DILA de 11-C, ni un backtest économique.
Aucune table canonique, modèle de serving ou batch en cours n'est modifié.
Les rendements ne servent pas à sélectionner les documents ; annonces étudiées
jusqu'en 2025, confirmation 2026 réservée.

## 1. Sources gratuites et collecte

11-D avait identifié 105 nouveaux candidats à partir de six exports officiels
DILA (objectifs, perspectives, prévisions, guidance, warning, avertissement).
Dix-sept avaient été relus. 11-E a collecté les **88 candidats restants** et
**31 publications antérieures** via les exports complets de huit ISIN : Klépierre,
Vente-unique, Virbac, Schneider, Ipsos, Renault, Assystem, Maisons du Monde.
Les huit compteurs API correspondent aux nombres de lignes exportées.

**Sept autres publications** corrigent les omissions du filtre de titres :
les publications financières ne contiennent pas toujours les mots recherchés.
Ce complément cherche les antécédents de cas déjà identifiés, sans sélectionner
par performances ni modifier rétroactivement le protocole initial.

| Passe | PDF sélectionnés | Extraits | Échecs |
|---|---:|---:|---:|
| 11-D | 17 | 17 | 0 |
| 11-E : restants et antécédents | 119 | 119 | 0 |
| 11-E : complément antécédents | 7 | 7 | 0 |
| Total | 143 | 143 | 0 |

Le total exclut les 24 PDF du POC de septembre. **Extrait ne signifie pas
validé sémantiquement** : la revue complète des 143 PDF n'est pas achevée.
Le tri lexical repère un comparateur potentiel dans 114 documents. Les résultats
réalisés produisent aussi des occurrences. Les 29 documents sans occurrence
ne sont pas automatiquement rejetés.

Sources : API publique `flux-amf-new-prod` de info-financiere.gouv.fr et PDF DILA.
Le fallback HTTPS emploie le même nom/chemin officiel sur echanges.dila.gouv.fr,
pas un autre document ni une désactivation TLS. SHA-256, URL, transmissions et
date de collecte sont archivés. Les copies du dossier conservent les empreintes.

## 2. Réserves levées et cas restant complexes

| Cas | Ancienne preuve retrouvée | Première conclusion |
|---|---|---|
| Klépierre 2023 | Février p6 : CFNC 2,35 €/action ; août p5 : au moins 2,40 | UP ; 2,24 est le réalisé ajusté 2022, pas la vieille cible |
| Assystem 2024 | Septembre p3 : CA environ 620 M€, cession/acquisitions déjà incluses ; octobre p2 : environ 610 | DOWN sur CA seulement ; marge non promue |
| Ipsos 2024 | Juillet p7 : prévision annuelle proche de 3 % ; octobre p1 : environ 1 % | DOWN ; réalisé neuf mois 2,4 % non utilisé comme vieille cible |
| Vente-unique | Ancien 150 M€ avant septembre 2022, nouveau avant septembre 2021 | Accélération d'horizon, pas deux chiffres du même exercice |
| Virbac juillet 2023 | PDF daté 3 juillet, dépôt Repeat le 17 juillet | Ne pas antidater sans preuve du dépôt initial |
| Schneider | Nouvelle stratégie 2022–2024 | Ne pas comparer à une ancienne guidance annuelle |

Le manifeste 11-D est conservé. Renault 2022 et Maisons du Monde 2021 restent
réservés sur les périmètres. D'autres antécédents restent à qualifier.

## 3. Quinze paires proposées, pas un dataset ML autorisé

Le dossier v2 contient **15 annonces proposées (9 UP / 6 DOWN)** et **2 cas
complexes réservés**. Il reprend les quatre paires de 11-D et ajoute onze paires
après lecture textuelle et inspection visuelle des pages. Les trois paires
initiales de 11-C restent dans leur rapport : non incluses dans ces 15 et dans
le contrôle de support ci-dessous.

| Annonce | Métrique | Ancienne → nouvelle | Sens |
|---|---|---|---|
| Kumulus 2021-07-29 | CA annuel M€ | 30 → 32 | UP |
| Pluxee 2024-04-19 | Marge EBITDA récurrent % | ≥34,5 → ≥35 | UP |
| Icade 2024-11-29 | CFNC activités abandonnées €/action | 0,80 → 1,03 | UP |
| Thales 2019-10-17 | Croissance organique annuelle % | bas de 3–4 → environ 1 | DOWN |
| Guerbet 2025-09-15 | Croissance CA taux/périmètre comparables % | 3–5 → environ −1 | DOWN |
| Guerbet 2025-12-02 | Même métrique | environ −1 → −5 à −4 | DOWN |
| Bastide 2025-03-19 | Marge opérationnelle courante % | 8,7 → ≥9,1 | UP |
| Kumulus 2022-05-05 | CA annuel M€ | 40 → 42 | UP |
| Pluxee 2024-07-03 | Croissance organique annuelle % | 15–17 → environ 18 | UP |
| Klépierre 2023-08-01 | CFNC annuel €/action | 2,35 → ≥2,40 | UP |
| Assystem 2024-10-24 | CA annuel M€ | environ 620 → environ 610 | DOWN |
| Ipsos 2024-10-15 | Croissance organique annuelle % | proche de 3 → environ 1 | DOWN |
| Ipsos 2023-09-14 | Même métrique | autour de 5 → 3–4 | DOWN |
| Renault 2023-06-29 | FCF opérationnel Automobile Md€ | ≥2 → ≥2,5 | UP |
| Engie 2023-06-30 | Résultat net récurrent part du groupe Md€ | moitié haute de 3,4–4,0 → 4,7–5,3 | UP |

Les « au moins » sont des planchers, pas des valeurs exactes réalisées. Les
« autour de » ne deviennent pas des prévisions ponctuelles précises. Les
qualificatifs restent attachés aux nombres. Les métriques multiples d'une
annonce ne créent pas plusieurs événements.

Réserves montrées au lecteur : SMCP 2023 (ancienne amélioration sur réalisé
9,2 %, pas vieille cible exacte 9,2 %) ; Arcure 2024 (centre 19 M€, intervalle
18,2–20 recoupant l'ancienne cible 20). Pas d'insertion dans les 15 propositions.

## 4. Support Oracle et absence de nouvel entraînement

Pool H5 figé : **9 661 observations**, SHA-256
`8b251ed6c0028d7bff179fae7a8c0eeedf4c54fb606bfb1a356446e7c988766b`.
Jointure par ISIN. Jour proxy : transmission la plus tardive convertie Paris,
puis délai 1 ou 2 jours calendaires. Ce n'est pas une preuve vintage Web.

| Délai | Fenêtre | Annonces recoupant le pool | Observations / dates |
|---:|---:|---:|---:|
| 1 jour | 7 jours | 2 | 5 / 5 |
| 2 jours | 7 jours | 2 | 6 / 6 |
| 1 jour | 30 jours | 2 | 21 / 21 |
| 2 jours | 30 jours | 2 | 21 / 21 |

Dans la fenêtre30j, Assystem octobre2024 fournit20 observations et Icade
novembre2024 une. Les21 observations incluent3 D1 et4 D10 ; ce ne sont pas
21 annonces indépendantes. Masques directionnels existants, maturité des labels
et chemins VALID, délai1/fenêtre30j :

| Fold directionnel | Train exposé | Validation exposée | Test exposé |
|---|---:|---:|---:|
| 6 | 0 | 0 | 21 |
| 7 | 0 | 21 | 0 |

Les groupes Oracle fold/phase diffèrent des folds directionnels ; le rapport
conserve les deux sans les confondre. Aucun seuil abaissé. Pas de fit guidance
car les deux trains n'ont aucune exposition aux annonces proposées.
**Blocage de support, pas NO-GO statistique guidance, pas preuve qu'il faut payer.**

## 5. Dossier et seconde lecture

Dossier : `artifacts/fr/research/guidance_completion_11e/second-review-20261004-v2/`.

- `README.md` :17 fiches, liens PDF, pages et réserves.
- `pdfs/` : originaux copiés et vérifiés, dont trois anciennes publications.
- `second_review.json` : grille à compléter, décisions initiales PENDING.
- `first_review_pairs.json` :15 propositions non autorisées pour entraîner.
- `input_manifest.json` : manifeste résolu et empreintes des versions.
- `lexical_screen.json` : tri des143 documents, aucune validation automatique.
- `support_report.json` : couverture par annonce et partitions.
- `report.json` : statut global.

Pour chaque fiche : ACCEPT, REJECT ou RESERVE, nom/date du second lecteur,
justification. Une acceptation confirme explicitement : ancienne valeur
prospective, même période/métrique/périmètre, bornes/qualificatifs corrects et
pas de doublon. Le lecteur ne consulte pas les rendements. Les deux cas
complexes nécessitent un nouveau manifeste avant une acceptation.

Le lecteur peut annoter les fiches en texte et nous les rendre ; pas besoin
de manipuler du JSON. L'indépendance est une attestation humaine, pas une
propriété prouvée par le programme. Même après seconde lecture réussie,
`training_eligible` reste false : elle ne qualifie pas automatiquement le PIT.

```powershell
python -m service.fr.guidance_completion_11e validate-second-review --output artifacts/fr/research/guidance_completion_11e/second-review-20261004-v2
```

Cette commande doit refuser les décisions PENDING. Ne pas inscrire de validations
fictives pour la faire passer. La v1 est un état antérieur conservé ; utiliser v2.

## 6. Suite et clôture du sprint

1. Seconde lecture des17 fiches, acceptations et exclusions motivées figées.
2. Poursuivre la revue sémantique des candidats restants si la revue confirme
   la qualité de l'extraction ;114 comparateurs ne sont pas114 bonnes paires.
3. Étendre un historique équilibré et son intersection avec un pool Oracle
   qualifié, pas seulement compter des PDF.
4. Prouver la disponibilité historique, ou pré-enregistrer un pilote proxy
   retardé explicitement non admissible comme preuve de production.
5. Tester la guidance séparément seulement après support suffisant et protocole.

Ces travaux gratuits ne sont pas épuisés. Un achat exigerait d'identifier
précisément une preuve indispensable introuvable gratuitement ; ce constat
n'est pas établi. La remise du dossier attend la seconde lecture autorisée,
pas un achat. Sprint11 ne doit pas être artificiellement marqué terminé.

Vérification : **57 tests ciblés passants** (11-E/11-D/POC guidance/11-B/11-C),
Ruff passant. Tests ciblés avec `--no-cov`, suite applicative complète non exécutée.

Liens : [11-D](sprint_11d_corpus_guidance_elargi.md),
[11-C](sprint_11c_evenements_guidance_ablation.md),
[catalogue gratuit](catalogue_sources_gratuites_validation_historique.md),
[planning](sprint_planning_integration_marche_francais.md).
