# Sprint 12-F — Priorités fiscales Oracle et opérations sur titres

## 1. Résultat au 4 octobre 2026

La passe classe les **40 titres** dont une fiscalité non qualifiée affecte
effectivement les intentions Oracle du protocole 12-E. Les 72 couples
émetteur/année encore inconnus dans le dossier fiscal global ne sont pas tous
présents dans cette politique. Il faut donc distinguer le stock de cas fiscaux
du sous-ensemble qui bloque Oracle.

Les pièces officielles X-FAB 2023, 2024 et 2025 ont été téléchargées et les
pages utiles lues. Elles documentent le siège belge de l'émetteur, les actions
ordinaires, leur identité et l'absence de dividendes décidés ou payés en
2024–2025. Cette qualification est **partielle et rétrospective** : aucun
nouveau couple fiscal annuel n'a été promu, aucun chemin économique n'est
déclaré entièrement qualifié.

Deux pièces Nexity supplémentaires ont été recherchées mais leurs serveurs
ont répondu **403**. Les résultats indexés ne remplacent pas les documents
archivés. Aucun contrôle d'accès n'a été contourné.

Le Sprint 12 reste ouvert. Les sources gratuites ne sont pas déclarées
épuisées ; cette passe n'a pas demandé d'achat ni abaissé les exigences.

## 2. Périmètre et classement

Entrée : `artifacts/fr/research/exploitable_scope_12e/audit-20261004-v2/policy_intent_coverage.parquet`.
Le registre utilise uniquement les intentions figées `oracle_top20_long`
avec `tax_qualified=false`. Il ne lit aucun rendement futur. Les doublons et
intentions marquées comme ayant utilisé une cible future sont refusés.

| Titre fournisseur | ISIN | Intentions Oracle affectées | Parmi les huit premiers rangs | Années fiscales à résoudre |
|---|---|---:|---:|---|
| XFAB.PA | BE0974310428 | 248 | 104 | 2024, 2025 |
| OSE.PA | FR0012127173 | 238 | 203 | 2024, 2025 |
| VLA.PA | FR0004056851 | 234 | 146 | 2024, 2025 |
| MEDCL.PA | FR0004065605 | 200 | 89 | 2024, 2025 |
| NXI.PA | FR0010112524 | 198 | 83 | 2024, 2025 |
| ELIOR.PA | FR0011950732 | 196 | 61 | 2024, 2025 |
| ADOC.PA | FR0011184241 | 191 | 174 | 2024, 2025 |
| SESG.PA | LU0088087324 | 171 | 52 | 2024, 2025 |

Il s'agit d'**intentions, pas de transactions remplies**, ni de nombre de
positions simultanées. Les huit premiers rangs donnent une seconde mesure
de priorité, sans simuler la capacité effective du portefeuille. Pour cette
mesure, OSE, Adocia et Valneva sont particulièrement prioritaires. Le fichier
`tax_priorities.json` conserve les 40 titres, pas uniquement ce tableau.

## 3. Contrat fiscal : ce qui permet réellement de conclure

La doctrine BOFiP archivée précise le rôle du siège en France et la distinction
avec les titres étrangers représentatifs d'actions françaises (§80–90). Pour
les cas français, la capitalisation pertinente est celle du **1er décembre
précédant l'année fiscale**, et non une capitalisation actuelle ou du
31 décembre. Le dépassement du seuil se vérifie avec le cours et le nombre
de titres selon la convention juridique applicable (§100–110).

Source : [BOFiP, périmètre des titres taxables](https://bofip.impots.gouv.fr/bofip/7570-PGP.html/identifiant=BOI-TCA-FIN-10-10-20151221).
La version archivée apporte la règle de périmètre, pas un taux unique valable
pour toutes les dates. Le taux historique et sa date d'effet restent gérés
dans le protocole fiscal existant ; ne pas appliquer rétroactivement 0,4 %.

Ne sont jamais des preuves suffisantes :

- absence d'un nom dans la liste BOFiP sans rapprochement exact d'identité ;
- préfixe FR/BE/LU de l'ISIN pris isolément ;
- appartenance actuelle à une catégorie de capitalisation ;
- extrait fournisseur dépourvu de date historique ;
- siège à deux clôtures annuelles supposé inchangé chaque jour entre elles.

La fiscalité s'applique selon l'année/date de règlement retenue dans 12-E,
pas automatiquement selon l'année du signal ou de l'exercice comptable.

## 4. X-FAB : qualification précise et limites

Pièces : rapports annuels issus de la page officielle
[investisseurs X-FAB](https://www.xfab.com/investors/), archivés avec SHA-256.
Les liens de téléchargement signés peuvent expirer ; les copies et leurs
empreintes font partie du dossier de reprise.

| Champ | Rapport / pages PDF | Conclusion admise |
|---|---|---|
| Action ordinaire directe | 2023 p61 ; 2024 p57 ; 2025 p58 | 130 781 669 actions émises aux clôtures documentées |
| Ticker et ISIN | 2023 p127 ; 2024 p132 | XFAB, BE0974310428, cotation Euronext Paris |
| Siège émetteur | 2023 p129 ; 2024 p134 ; 2025 p156 | Siège déclaré à Tessenderlo / Tessenderlo-Ham en Belgique |
| Dividendes | 2024 p58 ; 2025 p59 | Aucun dividende décidé ou payé pendant 2024 et 2025 |

Le nombre d'actions aux clôtures n'est **pas** une preuve d'absence de toute
opération intermédiaire. La localisation d'une filiale française n'est pas
le siège de l'émetteur de l'action.

Statut fiscal enregistré dans le nouveau registre :
`FOREIGN_ORDINARY_SCOPE_EVIDENCE_REVIEWED_ANNUAL_CONTINUITY_PENDING`.
Pour lever le blocage annuel, rechercher des statuts/historique de registre
de l'émetteur avec effet daté, ou une preuve fiscale historique explicite
rapprochée à cet ISIN. Ne pas interpréter ce statut comme exonération admise
par le moteur. Les rapports ESEF prévalent selon la réserve publiée dans le
rapport PDF ; un désaccord éventuel doit rester bloquant.

## 5. Compléter les opérations sur titres, famille par famille

La preuve annuelle X-FAB complète la **famille dividendes**, sans accorder
une couverture globale. Elle est indépendante de la liste vide du fournisseur.
Il reste à qualifier séparément splits/regroupements, droits, restitutions
de capital, fusions, scissions, radiations et changements de classe.

Pour chaque événement présent, conserver au minimum : identité ISIN/classe,
nature, décision finale, détachement, paiement, ratio/montant/devise,
modalités cash/actions, traitement brut/net, source et empreinte. Pour une
absence, conserver une preuve de couverture de la famille sur tout
l'intervalle de détention, pas simplement zéro événement reçu.

Les 12-D/12-C conservent leurs faits ponctuels : Planisware, Virbac, ABC,
Argan, Lectra, SES, STIF, OPM, Vetoquinol, Jacquet, Robertet et Ipsos. Ils ne
sont pas réécrits ni promus implicitement par 12-F. En particulier :

- proposition d'AG ≠ résolution adoptée ;
- montant annuel ≠ solde payable si un acompte existe ;
- paiement ≠ détachement ;
- certificat/FDR ≠ action sous-jacente ;
- montant net encaissé ≠ montant brut annoncé ;
- consultation aujourd'hui ≠ disponibilité historique connue du modèle.

Nexity : la recherche a identifié une présentation d'AG 2025 proposant
l'absence de distribution au titre de 2024 et un communiqué semestriel 2024
mentionnant l'adoption de la suspension au titre de 2023. Les téléchargements
ont échoué avec 403. **Aucun champ n'est qualifié à partir de ces seuls résultats
de recherche**. Même récupérées, ces pièces ne couvriraient pas toutes les
distributions extraordinaires ou opérations de capital possibles.

## 6. Dossiers, reproduction et contrôle

- Collecteur borné : `service/fr/priority_evidence_12f.py`.
- Registre contrôlé : `service/fr/priority_review_12f.py`.
- Lecture technique PDF : `scripts/research/inspect_priority_pdf.py`.
- Tests : `tests/test_fr_priority_review_12f.py`.
- Sources lues : `artifacts/fr/research/priority_evidence_12f/xfab-20261004-v1`.
- Revue et priorités : `artifacts/fr/research/priority_evidence_12f/review-20261004-v1`.
- Échecs Nexity tracés : `artifacts/fr/research/priority_evidence_12f/extended-20261004-v2/report.json`.

La revue est liée aux empreintes exactes des pièces lues manuellement ; un
nouveau rapport d'un autre contenu ne peut pas hériter automatiquement de
ces conclusions. Chaque sortie exige un dossier neuf. Les sources restent
observées en octobre 2026 ; `available_at_for_strategy` demeure non qualifié.

```powershell
python -u -m service.fr.priority_review_12f --output artifacts/fr/research/priority_evidence_12f/nouvelle-revue --sources artifacts/fr/research/priority_evidence_12f/xfab-20261004-v1 --intentions artifacts/fr/research/exploitable_scope_12e/audit-20261004-v2/policy_intent_coverage.parquet
```

Aucune connexion SQL, écriture canonique, migration, relance de modèle,
modification d'ordre, consommation de performance 2026 ou modification de
batch en cours. Le registre fiscal antérieur conserve 72 couples inconnus :
les nouvelles preuves partielles ne les font pas disparaître artificiellement.

Validation : 11 tests ciblés passent sur 12-E/12-F (`--no-cov`), dont les
refus des pièces différentes de celles relues, des sources altérées, des
labels futurs et des écrasements de dossier. Ruff passe sur les quatre
fichiers Python ajoutés. Ce n'est pas un test intégral de l'application.

## 7. Prochaine passe

**Reprise différée sur décision utilisateur du 4 octobre 2026.** Le reste du
Sprint 12 est centralisé dans le [TODO de reprise](TODO_sprint_12_reste_a_faire.md).
L'utilisateur souhaite une autre expérience avant le Sprint 13 ; ne pas
commencer ce dernier ni sa préparation. Les étapes ci-dessous ne sont pas
des travaux actuellement lancés.

1. Prioriser OSE/ADOC/VLA selon les huit premiers rangs ; rapprocher les
   identités et les règles annuelles de 2024 et 2025.
2. Pour les titres français non listés, obtenir cours et capital émis au
   1er décembre 2023/2024 avec preuve indépendante, ou une liste fiscale
   historique explicite rapprochée à l'ISIN. Ne pas calculer avec le cours actuel.
3. Pour X-FAB et SES, vérifier continuité du siège et classe du titre.
4. Qualifier les décisions et dates des événements restants ; compléter
   la couverture négative de chaque famille sur les fenêtres exactes 12-D.
5. Créer un nouveau dossier fiscal/CA puis refaire 12-E **sans changer
   les intentions**. Mesurer les blocages levés, pas un rendement optimisé.

Références : [12-E](sprint_12e_perimetre_exploitable.md),
[12-D](sprint_12d_levee_blocages_gratuits.md),
[catalogue gratuit](catalogue_sources_gratuites_validation_historique.md).
