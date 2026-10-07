# Sprint 11-B — qualification des sources événementielles gratuites FR

État exécuté le 4 octobre 2026. **Sprint 11 en cours, pas clôturé.**
Cette passe mesure la disponibilité des sources et leur raccord aux événements
Oracle ; elle ne mesure ni un gain directionnel, ni une performance économique.
Elle ne commande aucun abonnement, ne modifie aucune table et ne touche pas aux
batchs en cours. Aucun entraînement ou backtest n'a été lancé.

## 1. Une correction de vocabulaire importante

Le script `scripts/research/fr_public_disclosures_poc.py` utilise le flux DILA
INFO-FINANCIERE. Le mot AMF dans le nom de ce flux ne signifie pas que le script
collecte les positions courtes nettes publiques. L'ancien POC sur 18 titres
était une étude de titres d'annonces avec cours Yahoo, pas un test du registre
de positions courtes. Ses déciles sont ceux d'un petit panel, pas du marché FR.

La nouvelle collecte de positions courtes est donc indépendante et nécessaire.
L'échec d'une heuristique de titre ne condamne pas ce nouveau jeu de données.

## 2. Collecte AMF officielle effectuée

Source : [jeu AMF sur data.gouv.fr](https://www.data.gouv.fr/datasets/historique-des-positions-courtes-nettes-sur-actions-rendues-publiques-depuis-le-1er-novembre-2012).
Licence indiquée par le catalogue : `lov2`, Licence Ouverte 2.0.
La ressource CSV est découverte par l'API du catalogue : ne pas construire son
URL en devinant la date. Elle est copiée intégralement avec SHA256 et date réelle
de collecte. HTTPS reste vérifié ; le magasin standard a permis la collecte,
contrairement au premier essai avec le magasin de certificats de requests.

Artefact courant :
`artifacts/fr/research/event_data_11b/qualification-20261004-v2/report.json`.

| Mesure | Résultat |
| --- | ---: |
| Lignes acceptées, toutes dates | 40 888 |
| Lignes mises en quarantaine | 15 |
| Lignes publiées entre 2018 et 2025 | 26 657 |
| Lignes correspondant aux ISIN du référentiel FR | 9 577 |
| ISIN du référentiel avec au moins une ligne sur cette période | 95/330 |
| Groupes détenteur/ISIN/jour de publication avec mises à jour distinctes | 38 |

Les 15 rejets présentent une fin de publication antérieure au début ; deux
concernent des publications antérieures à 2026. Ils sont conservés avec leur
numéro de ligne et contenu, pas corrigés arbitrairement. Ce constat indique
une incohérence selon notre contrat de lecteur, pas une explication certaine
de la convention interne de l'AMF.

### Couverture annuelle des publications rapprochées

| Année | Lignes | ISIN distincts |
| --- | ---: | ---: |
| 2018 | 1 115 | 49 |
| 2019 | 1 169 | 34 |
| 2020 | 1 024 | 51 |
| 2021 | 670 | 36 |
| 2022 | 1 181 | 46 |
| 2023 | 1 121 | 44 |
| 2024 | 1 599 | 50 |
| 2025 | 1 698 | 58 |

Ce sont des déclarations, pas des titres quotidiennement shortables. Les
330 identités ne sont pas toutes tradables tous les jours. Les ratios du CSV
sont en pourcentage : `0.5` signifie 0,5 %, pas 50 %.

### Contrat PIT encore à finaliser

1. Date de position et date de publication sont distinctes. Ne jamais donner
   accès à une déclaration à sa date de position.
2. La date publique n'a pas une précision intraday. La passe de couverture
   exclut strictement toute publication du jour de décision.
3. L'export reçu aujourd'hui est une reconstruction actuelle de l'historique,
   pas une succession de fichiers archivés à chaque date ancienne. Il faut
   qualifier les rectifications et ce qu'attestent les champs de publication.
4. Plusieurs mises à jour le même jour n'ont pas d'ordre intraday démontré.
   Aucun choix « dernière ligne du fichier » n'est admis.
5. Les informations publiques sont censurées par le seuil réglementaire.
   Une dernière déclaration passée sous le seuil ne doit pas être portée
   indéfiniment comme une position courante connue.
6. Absence de déclaration = `NOT_OBSERVED`, pas ratio nul.
7. Les noms/LEI de détenteur demandent un contrat de continuité avant agrégation
   ou calcul de variation ; le LEI n'est pas systématiquement renseigné.

Verdict : **GO pour poursuivre la qualification de cette source gratuite**,
pas encore GO pour un signal directionnel ou un modèle de serving.

## 3. Audit des archives DILA existantes

Les 120 exports du POC guidance sont relus et hashés individuellement :
25 492 lignes de métadonnées ; 12 250 correspondent à 48 des ISIN du référentiel.
Les documents associés ne sont pas tous téléchargés/validés. Le POC comporte
24 PDF présélectionnés et ne doit pas être présenté comme une analyse complète
des 25 492 annonces.

Le raccord déduplique par ISIN et identifiant `uin_idt_uin`, pas seulement par
titre. Il prend la plus tardive des transmissions explicitement horodatées,
convertie en Europe/Paris. Un horaire sans fuseau n'est pas admis. Cela reste
un proxy de transmission, pas une preuve automatique de mise à disposition Web.

Un ISIN absent de ces 120 exports est **non collecté dans cet échantillon**,
pas un émetteur sans annonce. Il faut une collecte portant sur le véritable
univers FR avant de traiter l'absence comme une observation.

## 4. Raccord de couverture au pool Oracle réparé

Source figée :
`artifacts/fr/research/fold7_repair/rebuild-20261003-v1/confirmation/direction/fr-shared-direction-h5-6c203bea5a09/oracle_oof_pool.parquet`.

9 661 événements examinés. Aucune cible, aucun rendement ni décile n'entre dans
les compteurs. Fenêtre **sept jours calendaires antérieurs**, pas sept séances ;
jour de décision exclu. AMF compte les jours de publication distincts, DILA
les identifiants de documents distincts. Ce ne sont pas des features approuvées.

| Fold | Phase Oracle du pool | Événements | Avec publication AMF récente | Avec document DILA récent |
| --- | --- | ---: | ---: | ---: |
| 4 | validation | 2 023 | 302 | 171 |
| 5 | test | 96 | 35 | 15 |
| 5 | validation | 1 494 | 318 | 138 |
| 6 | test | 101 | 32 | 8 |
| 6 | validation | 1 681 | 429 | 167 |
| 7 | test | 2 276 | 488 | 291 |
| 7 | validation | 1 990 | 655 | 159 |

Ces phases sont celles du pool Oracle OOF. Elles ne doivent pas être renommées
automatiquement folds train/test d'un futur modèle directionnel. Les ensembles
de jours sources, le purging et la disponibilité des labels restent à qualifier
avant une expérience supervisée.

Sortie `oracle_event_coverage.parquet` : clés UID/ISIN/date/fold/phase, deux
compteurs et statut `COVERAGE_ONLY_NOT_PIT_ADMITTED`. Pas de prix ni de signal
LONG/SHORT fabriqué.

## 5. Guidance et autres branches

Le [POC guidance](poc_guidance_120_emetteurs.md) conserve quatre paires
comparables parmi douze PDF préfiltrés par titre. Ce n'est ni une base supervisée
suffisante, ni une preuve de gain D1/D10. Restent la jointure avec les anciennes
prévisions, la métrique/unité/période/périmètre, la citation exacte et une
validation indépendante sur d'autres émetteurs. Ces travaux sont encore
possibles avec les pièces publiques ; ils ne sont pas déclarés bloqués par
un abonnement.

INPI/RNE : disponibilité et calendrier pour les émetteurs cotés à qualifier,
pas de résultat de collecte ou de signal ajouté dans cette passe.
Consensus, borrow, enchères, options, quotes historiques : aucune nouvelle
source gratuite qualifiée dans cette passe ; branches suspendues, pas NO-GO
statistique. Aucun fournisseur payant ne sera commandé.

## 6. Ce qui manque pour terminer réellement le Sprint 11

- Finaliser le contrat de publication/vintage AMF et les mises à jour ambiguës.
- Collecter/qualifier DILA sur le véritable univers, pas seulement le POC120.
- Valider des événements et des paires de guidance hors de l'échantillon initial.
- Pré-enregistrer une ablation AMF puis DILA/guidance, séparément, contre la
  référence prix/Oracle figée. Établir les seuils de support avant les résultats.
- Produire des résultats prédictifs multi-fold LONG/SHORT, ou un blocage précis
  de support/PIT. Ne pas déclarer NO-GO ML sans expérience admissible.
- Conserver les branches indisponibles comme suspendues avec leur besoin précis.

Le Sprint 12 reste distinct : ses réserves fiscales/dividendes empêchent la
rentabilité nette qualifiée, mais ne remplacent pas l'évaluation prédictive.

## 7. Reproduction et vérification

Service transversal recherche : `service/fr/event_data_qualification_11b.py`.
Entrée CLI : `modelFactory/fr_event_data_qualification_11b.py`.
Une sortie existante est refusée afin de préserver les preuves antérieures.

```powershell
python -m modelFactory.fr_event_data_qualification_11b --output artifacts/fr/research/event_data_11b/nouvelle_qualification --oracle-pool artifacts/fr/research/fold7_repair/rebuild-20261003-v1/confirmation/direction/fr-shared-direction-h5-6c203bea5a09/oracle_oof_pool.parquet
```

17 tests ciblés passent (nouveau lecteur, POC DILA, faisabilité guidance).
Ruff passe après normalisation des imports. Pas de prétention à une suite
complète exécutée. Aucun processus de recherche lourd n'est resté en cours.
