# Sprint 16-G — nouvelle fenêtre prospective distincte

**Statut final : préparation archivée, sans lancement automatique le 13 octobre.**
Le Sprint 16 est clos administrativement avec validation shadow bloquée :
[décision et qualification bornée](sprint_16_cloture_bornee.md).
Les commandes ci-dessous restent reproductibles, mais leur poursuite nécessite
un nouveau GO ; attendre la date ne lève pas les réserves de données.

## Préparation livrée le 8 octobre 2026

Le trou ESMA du 9 septembre ne doit pas être contourné en déclarant l'ancien
test qualifié. Un nouveau protocole de préparation a été créé, sans modifier
les tests des 7 et 8 octobre, les batchs, les modèles ou la base.

- Protocole : `config/research_fr/prospective_window_16g.json`.
- Service local : `service/fr/prospective_window_16g.py`.
- Dernier inventaire : `artifacts/fr/research/prospective_window_16g/preparation-20261008-v2/report.json`.
- Statut : `FUTURE_WINDOW_PREPARED_NOT_RELEASED`.

Le Full officiel du **12 septembre** peut ancrer une fenêtre complète ne
contenant aucune des trois séances réservées. Le calendrier XPAR de
l'application donne **21 séances du 14 septembre au 12 octobre inclus**.
La première décision suivante est le **13 octobre 2026 à 09:00 Paris**,
soit 07:00 UTC. Cette date est une borne technique minimale, **pas une
promesse d'autorisation**. Il ne s'agit pas de 21 jours calendaires.

## Inventaire effectivement observé

Inventaire v2 préparé le **8 octobre à 22:01:02 Paris** :

| Pilote | Séances clôturées avec barre valide archivée | Séance clôturée manquante | Séances pas encore clôturées |
|---|---:|---|---|
| Airbus AIR.PA | 19 / 19 | aucune | 9 et 12 octobre |
| L'Oréal OR.PA | 18 / 19 | 8 octobre | 9 et 12 octobre |
| Sanofi SAN.PA | 18 / 19 | 8 octobre | 9 et 12 octobre |

Le premier inventaire v1, quelques minutes auparavant, n'avait encore la
barre du 8 octobre pour aucun des trois titres. L'évolution d'Airbus est
compatible avec une collecte quotidienne encore en progression ; ces deux
instantanés sont conservés, sans réécrire le premier.

Le master opérationnel disponible couvre le **7 octobre**, pas encore le 8.
Les réserves `MASTER_STALE_OR_WRONG_SESSION` et
`MASTER_CONTINUITY_UNQUALIFIED` restent visibles. Aucune erreur d'intégrité
d'archive n'a été rencontrée pendant cet inventaire. Les réponses fournisseur
dividendes/splits ne couvrent pas encore toute la future fenêtre.

Les valeurs précédentes décrivent l'état **au moment de la préparation**,
pas les données qui seront connues le 13 octobre. Les séances futures ne
sont ni imputées ni inventées.

## Fonctionnement et garde-fous

La préparation utilise uniquement les observations et réponses brutes locales
des collectes opérationnelles et du bootstrap historique. Elle vérifie les
liens SHA256, retient les versions effectivement disponibles au cutoff et
réutilise le validateur de bars. Pas de lecture de `latest.json` comme preuve
historique, pas de réseau, pas de SQL, pas de chargement du modèle.

Deux phases existent :

1. **`prepare`** : inventaire à l'heure réelle du lancement. Peut être répété
   dans un nouveau répertoire, avant ou après la date prévue. Ne confirme
   jamais la disponibilité à l'ouverture.
2. **`confirm`** : interdit avant l'ouverture réelle du 13 octobre. Après
   cette heure, reconstruit l'inventaire avec un cutoff figé à **09:00 Paris**,
   même si la commande est lancée à 15:00 ou le lendemain. Les observations
   reçues après 09:00 sont exclues. Statut
   `OPENING_INVENTORY_CONFIRMED_NOT_RELEASED` : le mot « confirmed » porte
   sur l'exécution du contrôle d'inventaire, pas sur une permission de trading.

La confirmation ne répare pas automatiquement le référentiel global et ne
qualifie pas implicitement les opérations sur titres ou les devises. Les
capacités serving, ordres, écriture SQL et entraînement restent désactivées.

## Preuves restant à obtenir avant l'inférence

État de la recherche documentaire : [revue ciblée du pilote du 8 octobre](sprint_16g_revue_sources_pilote_20261008.md).
Les éléments retrouvés sont ponctuels ; il ne suffit pas d'attendre le
13 octobre pour qualifier les devises ou l'exhaustivité des opérations.
L'accès direct au miroir DILA a ensuite permis d'archiver les six PDF du
pilote et de lire leurs 16 pages. Ce progrès lève le problème de consultation,
pas les deux réserves de qualification ; l'élargissement reste conditionné.

| Domaine | Preuve attendue |
|---|---|
| Bars | 21 séances valides pour chaque titre, observations réelles avant le cutoff, aucune imputation |
| Identité | Full du 12 et chaque fragment Delta jusqu'au 12 octobre vérifiés, événements rejoués, ISIN/MIC actif sur chaque séance |
| Devise | Preuve de **devise de cotation**, couple ISIN/MIC et intervalle ; pas simple devise nominale FIRDS ou monnaie du dividende |
| Opérations | Avis effectifs vérifiés, dates/ratios/montants pertinents et périmètre de couverture ; une liste vide de communiqués n'est pas une preuve exhaustive d'absence |
| Disponibilité | Réception et qualification réellement achevées avant la décision ; aucun document consulté plus tard antidaté |
| Modèle / opérations | Parité features/transformation et revue de release, avec les réserves opérationnelles Sprint 15 explicitement traitées |

Le rapport fournit une grille des champs nécessaires pour raccorder les preuves
de devise et d'opérations : source et empreinte, ISIN/MIC, dates effectives,
observations et date de qualification. La préparation n'a pas trouvé ni validé
ces preuves à la place du relecteur ; les indicateurs restent `false`.

**Trois titres servent à qualifier la méthode, pas à former un TOP20 Oracle.**
Le minimum transversal de 20 titres du contrat Oracle est conservé. Après
qualification du pilote, élargir à suffisamment de titres qualifiés avant
une sélection Oracle ; ne pas abaisser le minimum pour obtenir artificiellement
un résultat. Aucune inférence ni sélection de portefeuille n'a été exécutée.

## Commandes

Nouvel inventaire, sans attendre le 13 :

```powershell
python -u -m service.fr.prospective_window_16g --phase prepare --output-dir artifacts/fr/research/prospective_window_16g/nouvel-inventaire
```

**Seulement à partir du 13 octobre à 09:00 Paris**, contrôle figé de disponibilité :

```powershell
python -u -m service.fr.prospective_window_16g --phase confirm --output-dir artifacts/fr/research/prospective_window_16g/confirmation-20261013-v1
```

Conserver les collectes quotidiennes normalement configurées. Aucun nouveau
run long, aucune tâche planifiée supplémentaire ni suivi automatique créé.
Le présent protocole ne remplace pas le brouillon 16-G2 ancré au 26 septembre :
c'est une préparation distincte exploitant la reconstruction du 12 septembre,
pas une modification silencieuse de l'ancien contrat actif.

## Vérification

**176 tests ciblés Sprint 16 passent**, dont 14 nouveaux cas de préparation
prospective : calendrier XPAR et date minimale, interdiction de raccourcir la
fenêtre, activation refusée, pilote figé, doublons, inventaire des dates futures,
confirmation prématurée refusée, cutoff maintenu lors d'une confirmation tardive
et absence de release implicite. Les dates futures injectées dans les tests
sont des fixtures, pas une exécution réelle anticipée de la confirmation.

```powershell
python -m pytest tests/test_fr_*16*.py --no-cov -q
```

Suite ciblée, pas qualification globale de l'application. Voir le
[bilan du rejeu pré-ancrage](sprint_16g_reparation_preancrage.md) et le
[pilote devises/actions](sprint_16g_pilote_devises_actions.md).
