# Simulation shadow locale — 164 titres XPAR

## Résultat du 9 octobre 2026

Le flux de recherche local fonctionne : **164 titres scorés, zéro exclusion,
33 candidats TOP20**. Les 14 features ont passé la vérification arithmétique
indépendante de leurs formules et de la transformation utilisée à l'entraînement.

Il s'agit d'un **rejeu technique rétrospectif**, pas d'un shadow qualifié ni d'une
performance économique. La liste des 164 titres a été créée le 9 octobre après
l'ouverture. Elle ne pouvait pas être utilisée pour sélectionner historiquement
les titres à cette ouverture. Les scores ont eux-mêmes été calculés après coup ;
leurs dates de création ne sont pas rétrodatées.

Archives finales :
`artifacts/fr/research/local_shadow_simulation/replay-20261009-v2/`.

- `report.json` : statut, dates, réserves, empreintes, population et exclusions.
- `scores.json` : classement complet, scores, features et disponibilité des inputs.
- `top20.json` : les 33 premiers scores, sans aucun filtre de rendement futur.
- `exclusions.json` : motifs de rejet ; liste vide pour ce rejeu.

La version v1 reste archivée ; v2 ajoute la traçabilité du code et le retard
effectif de calcul par rapport à l'instant de décision.

**47 tests ciblés réussis** : qualification du sous-ensemble, adapter quotidien,
parité des features et nouveau flux local. Sont notamment vérifiés le TOP20,
les scores invalides, les identités dupliquées, les changements de protocole ou
d'implémentation, et le refus d'inférence avant une décision future.

## Modèle et règles

- Modèle existant **Oracle amplitude H5**, champion `trees` du fold 7 réparé.
  Aucun modèle H20 américain n'est utilisé, aucun réentraînement n'est lancé.
- 14 features du profil FR court, 21 séances closes du 10 septembre au 8 octobre.
- Cutoff de données : ouverture XPAR du 9 octobre, **09:00 Paris / 07:00 UTC**.
- Sélection : `ceil(20 % × nombre de titres effectivement scorés)` ; 33 pour 164.
- Départage des scores égaux : règle déterministe du pilote FR, graine 17.
- Scores bruts non calibrés : **amplitude potentielle**, ni LONG/SHORT ni
  probabilité calibrée de gain. Le TOP20 est recalculé dans ce sous-ensemble ;
  ce n'est pas automatiquement le TOP20 de tout l'univers FR d'entraînement.

Premiers titres du rejeu : MAAT.PA, MEDCL.PA, OPM.PA, HDP.PA et SIGHT.PA.
Ce ne sont pas des recommandations d'achat. Aucun rendement, PnL ou portefeuille
directionnel n'a été calculé : l'Oracle seul ne détermine pas le sens.

## Contrôles et réserves

Le service `service.fr.local_shadow_simulation` reste isolé, **sans SQL, réseau,
courtier, entraînement ni ordre**. Il ne change pas le preflight de production,
ne promeut pas les données et ne lève pas les clôtures avec réserves des sprints
16–18. Il est une voie explicite de diagnostic exploratoire autorisée ici.

Il vérifie : liste exacte et unique des 164 identités, ISIN/UID/MIC, observations
et versions connues avant cutoff, empreintes des bruts, OHLCV et volumes positifs,
21 séances de warmup, identité XPAR à la séance de features, couverture fournisseur
des dividendes/splits, parité des 14 features, modèle local épinglé par hash,
ordre des features, classes binaires et validité des scores. Une erreur d'intégrité
d'archive bloque les scores ; moins de 20 candidats valides bloque l'inférence.

La continuité ESMA, la preuve indépendante de devise de négociation, les opérations
sur titres et la release du modèle restent réservées. Une réponse fournisseur
vide n'est pas une preuve indépendante d'absence d'événement. Les réserves figurent
dans chaque score ; `orders_allowed` et `serving_allowed` restent faux.

## Protocole prospectif figé — prochaine séance du 12 octobre

Le protocole final a été enregistré avant la séance du lundi **12 octobre 2026** :

`artifacts/fr/research/local_shadow_simulation/protocol-20261012-v2/protocol.json`.

Il fixe la population, H5, TOP20, minimum transversal 20, graine, modèle et
empreintes de code/formules. La version initiale v1 est conservée mais **ne pas
l'utiliser** : v2 inclut la traçabilité complète du code. Si le modèle, la source
ou l'implémentation changent, le protocole échoue plutôt que les accepter en silence.

Prérequis : le passage quotidien FR existant doit avoir archivé les barres et la
couverture fournisseur des événements jusqu'au **9 octobre**, ainsi que le
référentiel de cette séance. Les archives réellement reçues après l'ouverture
du 12 octobre ne seront pas utilisées pour réparer rétroactivement cette décision.

**À lancer le 12 octobre après 09:00 Paris**, idéalement peu après l'ouverture :

```powershell
python -u -m service.fr.local_shadow_simulation --phase prospective --protocol artifacts/fr/research/local_shadow_simulation/protocol-20261012-v2/protocol.json --subset artifacts/fr/research/usable_subset/qualification-20261009-v2/research_provider_inputs_xpar.json --bootstrap-dir artifacts/fr/research/data_readiness_16c/bootstrap-remediation-20261007-v1 --output-dir artifacts/fr/research/local_shadow_simulation/prospective-20261012-v1
```

Le service refuse toute inférence anticipée. Chaque titre est revérifié : la liste
figée ne garantit pas 164 scores si des inputs deviennent indisponibles. Un titre
rejeté n'est pas remplacé par un autre hors protocole. Les données absentes ne
sont pas imputées. `report.json` indique les scores et exclusions réellement obtenus.

Cette commande n'est **pas planifiée automatiquement**. Si elle est lancée tard,
le retard et la disponibilité réelle des scores restent archivés : elle ne crée
pas de faux signal disponible à 09:00. « Prospectif » désigne ici une population
et un protocole figés avant la séance, pas une release de trading indépendante.

## Suite

Après la séance prospective, examiner fraîcheur, stabilité du classement et
exclusions, puis choisir explicitement une période de suivi. Une performance
réalisée ne pourra être évaluée qu'après maturité des labels et qualification des
prix concernés ; aucune promesse directionnelle ou économique n'est déduite du
rejeu actuel. Aucun batch existant ni blocage fournisseur juridique n'est modifié.

Référence : [qualification du sous-ensemble](sous_ensemble_reellement_utilisable_20261009.md).
