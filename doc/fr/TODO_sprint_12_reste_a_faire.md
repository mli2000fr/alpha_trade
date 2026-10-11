# TODO — Reprise et clôture du Sprint 12 France

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Plan / TODO : ne vaut ni validation des données, ni autorisation broker. Les dépendances et blocages actuels priment sur l'ordre des sprints. [Référence actuelle](README.md).
<!-- doc-status:end -->

Date de référence : 4 octobre 2026.

**Après 13-D :** [robustesse exploratoire](sprint_13d_robustesse_economique.md)
terminée avec 96 scénarios ; aucun GO de promotion. Les preuves strictes de ce
TODO restent nécessaires. Aucun résultat 2026 n'a été consulté.

**État actuel après 13-C :** [réparations et conclusion exploratoire](sprint_13c_reparations_decision_economique.md).
Quatre barres absentes complétées uniquement dans l’overlay fournisseur depuis
Yahoo et six dates de paiement documentées sous réserves explicites ; aucun
flag de qualification stricte ni archive SQL promu. Les 24 cellules exploratoires
aboutissent, mais les tâches strictes ci-dessous restent ouvertes. Les décisions
de différer/ne pas démarrer décrivent le contexte antérieur, pas une interdiction
actuelle de l’expérience autorisée.

Mise à jour après nouveau GO utilisateur : le
[Sprint 13-A](sprint_13a_protocole_validation_economique.md) a démarré pour geler
le protocole et vérifier les gates. L’interdiction antérieure de sa préparation
est levée. **Sprint 12 reste ouvert et le rejeu économique réel reste bloqué.**
La décision de différer ci-dessous décrit l’état antérieur à ce nouveau GO ;
les tâches restantes et exigences strictes demeurent valables.

## 1. Décision de reprise

**Sprint 12 ouvert, travaux différés au profit d'une autre expérience choisie
par l'utilisateur. Sprint 13 non démarré, y compris sa préparation.**

Ce document mémorise les tâches restantes ; il ne déclenche aucune collecte,
aucun entraînement, aucun rejeu ni modification de données. Attendre un
nouveau Go explicite avant de reprendre ces travaux ou d'engager le Sprint 13.
L'autre expérience n'est pas encore définie ici : ne pas en inventer le
protocole ni lui attribuer les résultats historiques du Sprint 12.

## 2. État acquis à conserver

- 12-A : contrat de coûts configurable et règles fiscales historiques ;
  qualification des titres/dates incomplète.
- 12-B : moteur économique de recherche, cash EUR, quantités entières,
  commissions/spread/slippage/taxes séparés, créances de dividendes et splits
  simples ; inconnus bloquants. Cela ne constitue pas une parité complète
  avec un futur moteur FR de production.
- 12-C : règle standard de règlement T+2 documentée et preuves ponctuelles
  de prix/événements. Ce ne sont pas des règlements ou fills observés.
- 12-D : dossiers publics et demandes de preuves sur les fenêtres exactes
  de détention ; événements corroborés ponctuellement, pas couverture globale.
- 12-E : 21 379 chemins, 118 titres, folds 6/7 ; 16 032 chemins passent les
  contrôles partiels, **zéro chemin entièrement qualifié économiquement**.
  Couverture partielle des intentions Oracle : 30,24 % ; contrôle uniforme :
  74,99 %. Les populations ne doivent pas être comparées après suppression
  rétrospective de leurs cas bloqués.
- 12-F : classement de 40 titres fiscalement inconnus qui affectent Oracle ;
  pièces X-FAB relues, absence de dividendes 2024–2025 documentée. Continuité
  fiscale annuelle et autres familles d'opérations non qualifiées.

Dernier dossier fiscal global : **137/209 couples positifs qualifiés en
recherche, 72 inconnus sur 47 titres**. Les chiffres 112/209 et 97 inconnus
des premiers comptes rendus 12-C restent des jalons historiques, pas l'état
actuel. Les preuves partielles 12-F n'ont promu aucun couple supplémentaire.

## 3. Tâches restantes et conditions de clôture

### A. Fiscalité par instrument et date — priorité élevée

- [ ] Reprendre le classement des intentions figées, avec deux mesures :
  toutes les intentions affectées et celles des huit premiers rangs.
- [ ] Traiter d'abord les cas les plus matériels : XFAB, OSE, VLA, MEDCL,
  NXI, ELIOR, ADOC, SESG. OSE/ADOC/VLA sont particulièrement présents dans
  les huit premiers rangs ; ces rangs ne sont pas des fills effectifs.
- [ ] Rapprocher émetteur, ISIN, classe et année fiscale ; conserver les
  changements d'identité et les titres représentatifs séparément.
- [ ] Pour les émetteurs français, obtenir la preuve pertinente au
  1er décembre 2023/2024 ou une qualification fiscale historique explicite
  rapprochée à l'ISIN. Une capitalisation actuelle ou au 31 décembre ne suffit pas.
- [ ] Pour X-FAB/SES, qualifier continuité du siège et nature exacte du titre ;
  ne pas généraliser deux photographies annuelles à toutes les dates entre elles.
- [ ] Appliquer les dates de règlement et les taux historiques du contrat,
  pas un taux de 0,4 % rétroactif sur toutes les années.
- [ ] Exporter les décisions positives, négatives explicitement prouvées et
  inconnues dans un **nouveau** dossier versionné, avec source, empreinte,
  intervalle d'effet, justification et limites de revue.

Critère : aucune taxe silencieusement nulle ; inconnu ≠ exonéré. Ne jamais
déduire l'exonération du préfixe de l'ISIN ou de l'absence d'un nom dans une
liste mal rapprochée. Les documents juridiques doivent rester vérifiables.

### B. Opérations sur titres — couverture, pas seulement événements connus

- [ ] Reprendre les fenêtres exactes 12-D et construire une matrice
  instrument × intervalle × famille d'événement.
- [ ] Compléter les événements encore incomplets : décision finale,
  détachement, paiement, montant/ratio, devise, classe et modalités cash/actions.
- [ ] Distinguer proposition d'AG et résolution adoptée ; acompte et solde ;
  date de paiement et date de détachement ; montant brut et net.
- [ ] Conserver et raccorder les preuves ponctuelles 12-C/12-D sans leur
  attribuer une couverture supérieure à celle qu'elles prouvent.
- [ ] Enregistrer l'absence annuelle de dividendes X-FAB comme preuve de
  cette seule famille, pas comme absence de splits/droits/fusions/scissions.
- [ ] Qualifier séparément splits/regroupements, droits, restitutions de
  capital, fusions, scissions, radiations et changements de classe rencontrés.
- [ ] Pour les journées sans événement, obtenir une preuve de couverture
  de la source sur tout l'intervalle. Une liste fournisseur vide ne suffit pas.
- [ ] Si un événement complexe est rencontré, implémenter et tester son
  traitement comptable, ou maintenir le chemin bloqué explicitement.

Critère : cash-flows et quantités réconciliables avec les pièces, sans
double comptage ni utilisation simultanée de prix ajustés et d'ajustements
comptables. Les deux pièces Nexity en 403 ne sont pas des preuves acquises ;
une reprise doit chercher une archive publique autorisée, sans contourner l'accès.

### C. Prix, statut d'exécution et règlement

- [ ] Résoudre les quatre journées de prix officiels encore recherchées :
  ERA/GLE/MEDCL/VCT, 30 juillet 2024, avec convention de série explicite.
- [ ] Raccorder l'overlay Artois `NO_OPENING_TRANSACTION` du 10 octobre 2024
  au refus d'achat causal. Ne pas utiliser 9 550 EUR comme ouverture exécutable.
- [ ] Recontrôler les neuf chemins invalidés pour prix et les cinquante
  chemins à champs d'événements bloquants ; ces comptes sont ceux du dossier
  initial, pas un nombre d'événements distincts encore tous non résolus.
- [ ] Vérifier suspensions, radiations, gaps, calendrier et prochain prix
  réellement accessible pour chaque entrée/sortie concernée.
- [ ] Réutiliser les preuves du calendrier standard T+2 déjà qualifiées,
  sans annoncer des règlements réels observés. Vérifier l'année fiscale au
  passage décembre/janvier et les éventuelles exceptions rencontrées.

Critère : aucun fill fabriqué par interpolation, substitution de clôture ou
suppression a posteriori d'un chemin invalide.

### D. Qualification historique et disponibilité PIT

- [ ] Décomposer le flag historique global actuellement faux : identité,
  admissibilité à la date, données de signal, données d'exécution et événements.
- [ ] Qualifier provenance, version et disponibilité à la décision des
  données effectivement utilisées par ATR/Oracle ; la guidance non validée du
  Sprint 11 reste hors de ces politiques et n'est pas une dépendance artificielle.
- [ ] Séparer les pièces ex post servant à reconstituer un cash-flow des
  informations autorisées comme features avant leur publication.
- [ ] Conserver `observed_at` réel ; ne pas antidater une collecte actuelle.
  Qualifier `available_at` par une preuve distincte lorsque nécessaire.

Critère : aucun flag global passé à vrai à partir d'un seul document ponctuel,
aucune information future introduite dans les décisions.

### E. Assemblage technique et vérification finale du Sprint 12

- [ ] Créer un nouveau dossier ancré sur les empreintes des preuves fiscales,
  prix/statuts, calendrier et opérations sur titres effectivement admises.
- [ ] Rejouer le diagnostic 12-E avec les **mêmes intentions**, sans changer
  scores, rangs, horizons ou univers pour éviter les cas bloqués.
- [ ] Rapporter les blocages levés et persistants par fold, politique,
  symbole et famille ; préserver les cas non qualifiés dans les exports.
- [ ] Assembler les données d'exécution et le ledger pour les politiques
  figées ; tester conservation cash/quantités/créances et décomposition des frais.
- [ ] Compléter les tests gap, suspension, split, dividende, absence de prix,
  taxe connue/inconnue, frontière d'année fiscale et événement complexe concerné.
- [ ] Documenter le niveau de parité effectivement vérifié. Ne pas déclarer
  la parité avec le backtest FR si seuls les services de recherche ont été testés.

Critère : contrat d'exécution reproductible et population commune qualifiée
sans coût inconnu masqué ni fill impossible. La validation de rentabilité,
les comparaisons nominal/stress et la confirmation finale appartiennent au
Sprint 13 : **ne pas les engager avec ce TODO**.

## 4. Ce qui ne constitue pas un déblocage

- Passer silencieusement à des données fournisseur présumées exactes.
- Retirer les titres/jours problématiques après lecture de leurs trajectoires.
- Déclarer toutes les sources gratuites épuisées après quelques 403.
- Acheter un extrait sans décision utilisateur.
- Confondre hypothèses configurables de spread/slippage avec quotes ou fills observés.
- Consulter 2026 pour choisir une politique, un seuil ou un sous-ensemble.

Un protocole exploratoire avec exigences différentes reste une option, mais
demande une décision explicite et un nouveau nom/version. Il ne clôture pas
automatiquement le protocole strict existant.

## 5. Dossier de reprise

Lire d'abord les rapports, puis les sources de vérité correspondantes :

| Élément | Référence |
|---|---|
| Coûts/fiscalité | [12-A](sprint_12a_couts_taxes_operations_sur_titres.md) |
| Moteur et invariants | [12-B](sprint_12b_moteur_rejeu_economique.md) |
| Qualification des preuves | [12-C](sprint_12c_qualification_preuves_execution.md) |
| Sources et demandes publiques | [12-D](sprint_12d_levee_blocages_gratuits.md) |
| Couverture et biais | [12-E](sprint_12e_perimetre_exploitable.md) |
| Priorités Oracle / X-FAB | [12-F](sprint_12f_priorites_fiscales_operations_titres.md) |
| Sources gratuites | [Catalogue](catalogue_sources_gratuites_validation_historique.md) |

Archives principales :

- `artifacts/fr/research/free_blocker_review/review-20261004-v6` ;
- `artifacts/fr/research/execution_public_requests/public-pass-20261004-v5` ;
- `artifacts/fr/research/exploitable_scope_12e/audit-20261004-v2` ;
- `artifacts/fr/research/priority_evidence_12f/review-20261004-v1` ;
- `artifacts/fr/research/priority_evidence_12f/extended-20261004-v2` ;
- `artifacts/fr/research/opening_evidence_overlay/artois-20261004`.

Vérifier les empreintes et ne pas écraser ces sorties. Les scripts 12-F
collectent ou enregistrent une revue partielle ; ils ne lèvent pas
automatiquement les gates 12-E. Aucun nouvel entraînement n'est requis pour
reprendre ces tâches de preuve et d'exécution. Préserver les batches en cours,
les bases US/CN et les routes de serving.
