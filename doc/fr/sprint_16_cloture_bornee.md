# Sprint 16 — Clôture bornée du 8 octobre 2026

## Décision finale

**Infrastructure livrée, validation shadow bloquée par les données.**

À la demande de l'utilisateur, la qualification est arrêtée au sous-ensemble
déjà étudié, sans élargissement documentaire, nouvelle collecte externe,
abonnement, entraînement ou modification des critères. Le Sprint 16 est clos
administrativement avec réserves explicites : **pas de GO shadow ni de GO live**.
Ce statut n'est pas une réussite complète des critères initiaux de validation.

Ce document fait foi pour le statut courant. Les mentions « non clos » et
« prochaine étape » des comptes rendus précédents décrivent leur état historique.
Les rapports de calcul et les décisions d'ouverture ne sont pas réécrits.

## Dernière qualification bornée

Population figée : AIR.PA / NL0000235190, OR.PA / FR0000120321 et
SAN.PA / FR0000120578, place XPAR. Ce pilote de trois titres n'est pas un
univers Oracle qualifié : le minimum transversal de vingt reste inchangé.

Un dernier inventaire local a été exécuté, sans réseau, SQL ni inférence :
`artifacts/fr/research/prospective_window_16g/closure-bounded-20261008-v1/report.json`.
SHA-256 : `7858d0e839a030f16325c6dbd3946b7de0079e48e12d066804b1cb704d013378`.

| Contrôle | AIR | OR | SAN |
|---|---|---|---|
| Barres valides sur les séances déjà closes | 19/19 | 19/19 | 19/19 |
| Séances closes manquantes | 0 | 0 | 0 |
| Erreur de validation des barres | Aucune | Aucune | Aucune |
| Devise observée sur XPAR le 7 octobre | EUR | EUR | EUR |
| Devise qualifiée sur toute la fenêtre | Non | Non | Non |
| Opérations sur titres indépendamment qualifiées | Non | Non | Non |
| Couverture observée dividendes/splits complète | Non | Non | Non |
| Autorisation de serving | Non | Non | Non |

Les séances du 9 et du 12 octobre sont futures à cet inventaire, pas des
données manquantes à imputer. La fenêtre proposée de 21 séances n'est donc
pas encore complète. La continuité future du référentiel et la release globale
restent également non qualifiées.

La preuve MiFIR du 7 octobre est ponctuelle, reçue le 8 octobre à 22:22 Paris.
Elle ne vaut ni intervalle complet, ni absence d'opérations, ni preuve connue
à l'ouverture du 8 octobre. Rapport :
`artifacts/fr/research/issuer_pilot_16g/mifir-currency-20261008-v2/report.json`.
SHA-256 : `caa124ec7649014f8af5c422cb708512f8929f02ba347e9cb381a7cc896470d9`.

**Conclusion : aucun des trois titres n'est libéré.** Les preuves gratuites
déjà disponibles dans ce dossier ne suffisent pas au contrat retenu. Cela
ne démontre pas qu'aucune autre source gratuite n'existe ou qu'un abonnement
résoudrait les réserves ; aucune nouvelle prospection n'est engagée.

## Livrables conservés et limites

- Contrat de prédiction, preflight et assemblage quotidien PIT.
- Contrôles de disponibilité, identités, barres et opérations, avec rejets explicites.
- Rejeux ESMA et dossiers de qualification versionnés, sans antidatage.
- Vérification de parité des features/transformation et tests ciblés.
- Préparation d'une future fenêtre prospective, non libératrice.

Les **200 tests ciblés Sprint 16** ont passé lors de la dernière validation
du code. Ils ne prouvent ni l'exhaustivité des sources, ni la performance ML,
ni une parité opérationnelle complète de serving. Aucune vraie inférence
shadow ni évaluation prospective à maturité n'a été réalisée dans ce sprint.
Le shadow effectif reste un livrable non réalisé, pas une fonctionnalité certifiée.

## Reste transféré, sans poursuite automatique

Une reprise nécessitera un **nouveau GO** et des éléments concrets :

1. Une preuve admissible de devise de cotation couvrant l'intervalle retenu,
   par ISIN/MIC, dates effectives et disponibilité réelle.
2. Des opérations sur titres qualifiées et une couverture de fenêtre documentée ;
   ne jamais transformer une réponse fournisseur vide en preuve d'absence.
3. Un référentiel continu et des barres valides sur toute la fenêtre de décision.
4. Une population suffisante qualifiée, puis revue de release modèle/opérations.
5. Une inférence shadow sans ordres et son évaluation après maturité des labels.

La date du **13 octobre à 09:00 Paris** reste une possibilité technique du
protocole archivé, **pas une tâche à lancer automatiquement ni une promesse de GO**.
Les collectes quotidiennes existantes ne sont ni arrêtées ni reconfigurées.
Aucune activation ou modification de modèle, de batch ou de base n'est réalisée.

Le choix d'un courtier relève du Sprint 17 et n'est pas la cause de ce blocage
shadow. Un travail sur un autre sprint ne doit pas être présenté comme une
validation implicite de celui-ci.

## Références

- [Bilan détaillé et chronologie](sprint_16g_bilan_et_plan_de_liberation.md).
- [Fenêtre prospective préparée](sprint_16g_nouvelle_fenetre_prospective.md).
- [Preuve ponctuelle MiFIR](sprint_16g_preuve_devise_mifir.md).
- [Planning général FR](sprint_planning_integration_marche_francais.md).
