# Sprint 16-F — Remédiation prospective

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

**Mise à jour du 8 octobre :** confirmation exécutée à 18:53 avec coupure
inchangée à 09:00 ; master frais couvrant le 7 octobre, 244 features calculables,
233 passages locaux hors continuité, zéro candidat libéré. Voir le
[bilan et plan de libération 16-G](sprint_16g_bilan_et_plan_de_liberation.md).
Les mentions de confirmation encore à exécuter ci-dessous décrivent la préparation
du 7 octobre, pas l'état courant.

7 octobre 2026 : correctifs livrés, rattrapage à terminer et qualifier.
**Shadow, serving, ordres et SQL restent interdits.**

## Résultat initial immuable

La confirmation du 7 octobre, exécutée à 14 h 57 Paris, conserve sa coupure
à 9 h : 242 features calculables sur 330 identités, zéro candidat.
Rapport : `artifacts/fr/research/opening_confirmation_16f/opening-20261007-v1/report.json`.
Les données reçues ensuite ne peuvent pas réparer rétroactivement cette décision.

## Causes identifiées

- Le passage dividendes/splits du 6 octobre à 23 h a échoué après **19 réponses
  sur 588** : refus Windows de remplacement du checkpoint. Les réponses brutes
  déjà observées restent archivées ; la collecte n'était pas complète.
- Le master exécuté à 20 h couvre J−1 : à l'ouverture suivante, il manque
  structurellement la dernière séance attendue par les features.
- La base ESMA conserve 55 dates de publications absentes/inconnues, dont le
  9 septembre 2026. Une mise à jour récente ne répare pas cette continuité.
- Les collecteurs EODHD suivent les **294 actifs actuels S6C**, tandis que le
  manifeste comprend 330 identités historiques/réservées : ne pas annoncer une
  couverture servable de 330 après collecte des 294.

Motifs du contrôle initial : couverture div/splits incomplète sur 271/272 titres,
warmup incomplet sur 39, volume nul incompatible avec les features sur 49,
identités terminées/réservées sur 30, devise à prouver sur 6, dividende non
qualifié sur 7. Ces catégories se chevauchent. Aucun prix n'est imputé.

## Correctifs

### Écritures JSON Windows

`service/fr/eodhd_daily_15b.py::atomic`, partagé par les outils FR : temporaire
UUID puis remplacement atomique, dix tentatives bornées sur refus d'accès ou
partage Windows, attente plafonnée à 0,5 seconde. Aucun effacement de destination
ni repli vers un JSON écrit partiellement en place. Les erreurs non transitoires
restent bloquantes ; un refus permanent conserve l'ancien checkpoint.

### Disponibilité ESMA

`security_master_daily_15e` date désormais le référentiel complet **après**
téléchargement, vérification et rejeu. La réception de l'index n'est pas assimilée
à la disponibilité du référentiel. Une collecte traversant 9 h ne peut ainsi
être artificiellement antédatée par son heure de début. Anciennes versions
inchangées, continuité historique jamais forcée à true.

### Horaires et fenêtres dans batch_fr.yaml

| Batch | Modification | Limite maintenue |
|---|---|---|
| fr_security_master_sync | **7 h Paris**, toujours catalogue J−1 | Toutes les partitions obligatoires, continuité historique requise |
| fr_corporate_actions_sync | **J−31/J** à 23 h, deux requêtes par titre | Observations fournisseur, pas preuve officielle des ajustements |
| fr_daily_bars_sync | Inchangé : J−7/J à 22 h | Barres/volumes invalides non imputés |

La tâche existante `AlphaTrade-FrSecurityMasterSync` se déclenche chaque heure
et relit le YAML : pas de réinstallation nécessaire pour ce changement.
Les horaires sont Paris, pas UTC ou New York. Si le PC/session ou les publications
ne sont pas disponibles à 7 h, aucun succès n'est inventé. Fragments manquants :
checkpoint non avancé. Aucune tâche ni aucun batch en cours arrêté par la remédiation.

31 jours réduisent le défaut de warmup mais ne garantissent pas 21 séances
autour de toutes les fêtes : le contrôle des 21 séances XPAR reste inchangé.

## Rattrapage isolé et suivi

Lancement du 7 octobre à 22 h 19 Paris, après clôture et sécurité 22 h :

```powershell
python -u -m service.fr.data_readiness_16c --output-dir artifacts/fr/research/data_readiness_16c/bootstrap-remediation-20261007-v1 --end-date 2026-10-07
```

Collecte barres puis actions, dans un nouveau dossier, sans modifier l'ancien
bootstrap ni les opérations. L'interruption de la conversation a arrêté ce
processus après 122 titres barres checkpointés sans erreur fournisseur ; la
reprise conserve la même fenêtre et utilise `--resume`. Ne pas lancer une
deuxième instance ; vérifier le PID avant tout retrait de verrou orphelin.

```powershell
Get-Content F:\projets\log\batch_fr\sprint16f-remediation-20261007-v1\stdout-resume.log -Tail 15
Get-Content F:\projets\log\batch_fr\sprint16f-remediation-20261007-v1\stderr-resume.log -Tail 15
Get-Content F:\projets\artifacts\fr\research\data_readiness_16c\bootstrap-remediation-20261007-v1\progress.json
Test-Path F:\projets\artifacts\fr\research\data_readiness_16c\bootstrap-remediation-20261007-v1\report.json
```

Les logs et `windows/*.json` donnent l'avancement par titre ; les compteurs
de `progress.json` sont consolidés à la fin du handler de chaque étape.
Rapport final attendu : `COLLECTED_PENDING_QUALIFICATION`, pas GO serving.

## Qualification et sondes publiques

Outil : `service/fr/opening_remediation_16f.py`. Après collecte terminée :

```powershell
python -u -m service.fr.opening_remediation_16f --bootstrap-dir artifacts/fr/research/data_readiness_16c/bootstrap-remediation-20261007-v1 --output-dir artifacts/fr/research/opening_remediation_16f/qualification-20261007-v1
```

Il qualifie le warmup connu **maintenant**, conserve l'empreinte du rapport initial,
expose les réserves et zéro servable. Ce n'est ni un rejeu de l'ouverture passée
avec les nouvelles données, ni la confirmation de l'ouverture future.

Sonde bornée déjà archivée dans
`artifacts/fr/research/opening_remediation_16f/catalogue-20261007-v1/report.json` :
9 septembre, zéro ZIP indexé (absence/inconnu, pas absence prouvée de changement) ;
7 octobre, quatre fragments indexés. La sonde n'a pas téléchargé ces ZIP ni
qualifié leur contenu. Les erreurs de sonde sont explicites et sanitizées.

## Nouvelle confirmation le 8 octobre

Protocole distinct : `config/research_fr/opening_confirmation_16f_remediation.json`.
Date de décision : **8 octobre à 9 h Paris** ; dernière séance attendue : 7 octobre.
Ancien protocole du 7 octobre inchangé. `--protocol` n'accepte que les JSON
dans `config/research_fr` ; tous les interdits restent vérifiés.

Après l'ouverture réelle et disponibilité du bootstrap terminé :

```powershell
python -u -m service.fr.opening_confirmation_16f --phase confirm --protocol config/research_fr/opening_confirmation_16f_remediation.json --output-dir artifacts/fr/research/opening_confirmation_16f/opening-remediation-20261008-v1
```

Un lancement à 15 h conserve la coupure 9 h. Avant l'ouverture, confirmation
refusée. Aucune automatisation de suivi créée. Un nouveau Full ESMA peut
réconcilier l'état courant, pas certifier chaque journée historique manquante.

## Gates toujours ouverts

Continuité historique ESMA, qualification indépendante des identités/actions,
traitement des dividendes/splits conforme aux formules figées, intervalles de
devise, revue de libération modèle et réserves opérationnelles Sprint 15.
L'amélioration de couverture ne vaut pas autorisation de shadow.

84 tests ciblés passent : collecteurs, ESMA, warmup, assemblage, preuves,
confirmation et remédiation. Suite complète non exécutée. Aucun entraînement,
prédiction modèle, SQL, changement de cours canonique ni ordre.

## Résultat du rattrapage et qualification — 7 octobre, après clôture

Le rapport final a été écrit à **22 h 39 min 57 Paris**. Sa présence ne signifie
pas succès complet : statut `PARTIAL_COLLECTION`.

- Actions : **588 réponses reçues et archivées**, zéro échec, fenêtre
  6 septembre–7 octobre. Ce sont des réponses titre/type, pas 588 événements.
  Leur statut reste `COLLECTED_NOT_QUALIFIED`.
- Barres : 294 titres demandés, 122 repris depuis le checkpoint, 172 traités
  pendant la reprise, dont **un échec PERR.PA** : réponse vide sur une fenêtre
  contenant des séances XPAR. Les compteurs consolidés indiquent 3 910 lignes
  persistées pendant la reprise ; ne pas présenter ce nombre comme la totalité
  de l'archive antérieure.
- Deux alertes de couverture fournisseur : FPG.PA manque la dernière séance ;
  LHYFE.PA manque 22 séances de la fenêtre. Une réponse HTTP valide ne certifie
  pas la couverture des séances.

Qualification exécutée et terminée dans
`artifacts/fr/research/opening_remediation_16f/qualification-20261007-v1/report.json` :

| Mesure | Résultat |
|---|---:|
| Identités du manifeste | 330 |
| Périmètre de collecte actuel | 294 |
| Features numériques calculables maintenant | **244** |
| Contrôles locaux passés, hors réserves globales | **233** |
| Titres autorisés au serving | **0** |
| Erreurs d'intégrité des archives barres/actions/master | **0** |

Les 244 ne sont pas une réécriture des 242 features connues à l'ouverture du
7 octobre : date de features et disponibilité des nouvelles observations
diffèrent. Les 233 ne sont ni une sélection Oracle, ni des ordres, ni une preuve
que la direction D1/D10 est prédictible.

Motifs par titre, non exclusifs : volume nul incompatible avec les features
46 ; warmup 21 séances incomplet 40 ; identité terminée/réservée 30 ; couverture
dividendes et splits incomplète 36 chacune ; devise nominale non EUR à prouver
6 ; dividende dans la fenêtre non qualifié 11. Les 36 identités hors collecte
actuelle ne doivent pas être assimilées à 36 pannes fournisseur.

Réserves globales : collecte partielle/échec d'étape, master encore trop ancien
ou couvrant la mauvaise séance, continuité ESMA non qualifiée, qualification
indépendante du master et des actions, revue de libération modèle et réserves
opérationnelles Sprint 15. Les 55 dates ESMA historiques restent ouvertes.

Suite : vérifier la publication du master couvrant le 7 octobre lors du passage
du **8 octobre à 7 h Paris**, puis exécuter la confirmation distincte après
9 h avec la commande ci-dessus. La confirmation peut diagnostiquer de nouveau
des blocages : ne pas annoncer un GO à l'avance. PERR/FPG/LHYFE restent exclus
des features ou en réserve selon le diagnostic, sans prix imputé ni retrait
silencieux de l'univers. Aucun nouveau processus de collecte n'est lancé par
cette qualification.
