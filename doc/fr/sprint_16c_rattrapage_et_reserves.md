# Sprint 16-C — Rattrapage de démarrage et qualification des réserves

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## État au lancement, 6 octobre 2026

**Collecte terminée et audit de warmup réalisé ; ni clôture complète 16-C ni GO shadow.**
Le [16-B](sprint_16b_assemblage_quotidien_pit.md) a identifié l'absence de warmup
prospectif, la date du master et sa continuité. Le 16-C lance un rattrapage
isolé et documente précisément les preuves qui restent manquantes. Aucun
modèle, batch planifié, paramètre global ou base SQL n'est modifié.

## 1. Rattrapage autorisé et périmètre

Service : `service/fr/data_readiness_16c.py`.

Il réutilise les collecteurs EODHD existants, en les appelant avec une fenêtre
locale de **31 jours calendaires**, sans modifier `batch_fr.yaml` (qui demeure
en J−7/J). Ce sont :

1. OHLCV quotidien ;
2. dividendes et splits, deux requêtes par titre.

Le périmètre est celui du collecteur quotidien : **294 symboles actifs actuels**
du référentiel S6C figé, parmi les 330 identités de recherche. Ce choix n'est
pas une certification d'univers historique tradable ; les 36 autres ne sont
pas réintroduits arbitrairement ni remplacés par des tickers US.
Budget nominal : 294 requêtes de barres + 588 requêtes d'actions = **882**,
hors retries réseau. Cadence reprise de la configuration, 0,5 seconde minimum
entre requêtes selon le collecteur. Pas de nouveau fournisseur ni abonnement.

La fenêtre initiale est **4 septembre–5 octobre 2026**. Avant 22h Paris, le
wrapper interdit de demander le jour courant ; il vérifie aussi que la date
finale est une séance clôturée. Le 6 octobre, la barre du jour devra provenir
du passage quotidien habituel après clôture, pas d'une requête anticipée.

Toutes les observations sont conservées sous :

`artifacts/fr/research/data_readiness_16c/bootstrap-20261006-v1/`

Les collecteurs quotidiens existants continuent d'utiliser leurs propres
répertoires opérationnels. Aucun lock ou fichier `latest` existant n'est
supprimé. Le nouveau run a son propre verrou et des dossiers séparés :

- `eodhd_daily/` : raw, observations, latest et fenêtres ;
- `corporate_actions/` : raw, observations, latest et fenêtres ;
- `progress.json` : étape et bilan mis à jour aux transitions ;
- `report.json` : bilan final, même en erreur détectée.

Les compteurs par symbole en cours de collecte sont dans `stdout.log` ;
`progress.json` n'est pas mis à jour après chaque symbole, mais au début et à
la fin de chaque étape. Un compteur à zéro pendant une étape n'indique donc
pas nécessairement un arrêt. Le collecteur conserve ses checkpoints par titre.

## 2. Heure réelle de disponibilité

Le téléchargement d'une barre de septembre effectué le 6 octobre devient
disponible **le 6 octobre à son observation réelle**, pas en septembre.
Le nouveau bootstrap ne peut pas réparer la décision passée du 6 octobre à
09h Paris. Pour un contrôle après collecte, choisir une ouverture ultérieure
dont les archives de la séance précédente sont déjà disponibles.

L'adaptateur 16-B accepte désormais `--bootstrap-dir` et combine les
observations de démarrage avec les observations des collecteurs quotidiens.
Il continue à sélectionner la dernière version connue **avant** la décision.
Les empreintes, fenêtres et horodatages sont contrôlés de la même manière,
quel que soit le répertoire. Aucun remplissage avec un ancien panel J+1 supposé.

## 3. Audit ESMA : ce qui est réellement connu

Base utilisée par la collecte quotidienne :
`artifacts/fr/esma_firds/replay_2018/history_2026_observed_v2.json`.

Empreinte :
`26d83366b3b3dfe97eb121b19b9633e1f1ac99423b796355eb90b2f038b59540`.

Cette base est complète **au sens des fichiers indexés présents**, jusqu'au
1er octobre 2026 ; aucun fichier listé n'est manquant localement. Elle conserve
55 dates sans Delta : 31 en 2018, 5 en 2019, 4 en 2020, 7 en 2021, 5 en 2022,
1 en 2023, 1 en 2025 et 1 en 2026. La réserve récente est **2026-09-09**.

Le 6 octobre, un nouvel appel direct à l'index officiel FIRDS, filtre
`file_type:DLTINS` et `publication_date` du 9 septembre 2026, retourne
**`numFound: 0`**. Source technique :
`https://registers.esma.europa.eu/solr/esma_registers_firds_files/select`.

Cela confirme seulement que l'archive n'est toujours pas proposée par cet
index. Cela ne prouve **pas** qu'il n'y a eu aucun changement cette journée.
On ne change donc ni `publication_continuity_confirmed` ni
`historical_continuity_confirmed` en `true`.
Les précédentes réconciliations Full valident des états à une date donnée,
pas chaque état intermédiaire des journées manquantes.

## 4. Pourquoi le master récent reste une difficulté de timing

Le collecteur tourne à 20h Paris et traite les publications jusqu'à J−1.
Pour une décision à l'ouverture de J, sa version observée la veille couvre
normalement J−2. Le contrôle strict de 16-B attend J−1. C'est une **différence
structurelle de cadence/disponibilité**, pas un bug d'heure affichée.

Le rattrapage de prix ne la résout pas. Avant de libérer un shadow il faudra
choisir et qualifier explicitement l'une de ces solutions :

- obtenir avant l'ouverture un référentiel complet couvrant la séance requise,
  si les archives officielles sont publiées à temps ;
- définir un contrat prospectif de « dernier état officiel effectivement
  connu », avec borne de fraîcheur et abstention sur les cas incertains,
  sans prétendre connaître les changements non encore publiés ;
- repartir d'un Full officiel récent réconcilié pour le **prospectif**, puis
  suivre les Delta complets. Cela ne répare pas rétroactivement 2018–2026.

Aucune de ces solutions n'est activée automatiquement ici. L'horizon H5 et
les features du modèle ne doivent pas être changés à la volée pour contourner
ce gate. Aucun nouvel entraînement n'est nécessaire pour examiner cette preuve.

## 5. Identités et opérations sur titres

Le prochain assemblage devra produire la liste explicite des ISIN admissibles,
ambiguës, terminés, à devise incompatible et à alias non vérifié. Les statuts
réservés ne sont pas changés simplement pour augmenter le nombre de candidats.
La présence de volume nul empêche l'utilisation du profil figé mais n'autorise
pas à déclarer automatiquement une radiation.

Les dividendes/splits récupérés par EODHD restent des observations fournisseur.
Les événements dans la fenêtre, les modalités cash/actions et l'exclusion des
historiques à splits devront être vérifiés contre les pièces disponibles.
La collecte de 31 jours améliore la couverture ; elle ne transforme pas ces
événements en preuves officielles indépendantes.

## 6. Commande, surveillance et reprise

Commande initiale :

```powershell
python -u -m service.fr.data_readiness_16c --end-date 2026-10-05 --output-dir artifacts/fr/research/data_readiness_16c/bootstrap-20261006-v1
```

Journal prévu : `log/batch_fr/sprint16c-bootstrap-20261006-v1/`.

```powershell
Get-Content F:\projets\log\batch_fr\sprint16c-bootstrap-20261006-v1\stdout.log -Tail 20
Get-Content F:\projets\log\batch_fr\sprint16c-bootstrap-20261006-v1\stderr.log -Tail 20
Test-Path F:\projets\artifacts\fr\research\data_readiness_16c\bootstrap-20261006-v1\report.json
```

Quand `report.json` existe, lire `status` :

- `COLLECTED_PENDING_QUALIFICATION` : appels terminés, pas de GO données ;
- `PARTIAL_COLLECTION` : une étape en échec, erreurs et compteurs conservés ;
- `FAILED` : erreur de préparation ou autre arrêt détecté.

Ne pas lancer un deuxième processus concurrent sur ce dossier. Après un arrêt,
vérifier qu'aucun processus ne tourne avant toute intervention sur un verrou.
La reprise explicite conserve la même date finale :

```powershell
python -u -m service.fr.data_readiness_16c --end-date 2026-10-05 --output-dir artifacts/fr/research/data_readiness_16c/bootstrap-20261006-v1 --resume
```

Après terminaison et disponibilité des archives requises, exemple de contrôle
pour une ouverture future, **sans serving** :

```powershell
python -m service.fr.daily_feature_adapter_16b --decision-date 2026-10-07 --bootstrap-dir artifacts/fr/research/data_readiness_16c/bootstrap-20261006-v1 --output-dir artifacts/fr/research/daily_feature_adapter_16b/decision-20261007-bootstrap-v1
```

L'exemple du 7 octobre n'est pas une promesse de GO : les données du 6 octobre
doivent être déjà observées, le run terminé avant 09h, et les réserves master
et opérations sur titres restent applicables. Ce contrôle n'est pas encore
exécuté à la création de cette note.

## 7. Gate de clôture

### Bilan réel après terminaison

Le run s'est terminé le **6 octobre 2026 à 20:30:02 Paris**, en environ
9 min 51 s, avec `COLLECTED_PENDING_QUALIFICATION`.

| Étape | Demandés | Reçus | Persistés | Échecs | Alertes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Barres | 294 titres | 294 titres | 6 414 barres | 0 | 4 |
| Dividendes/splits | 588 payloads | 588 payloads | 588 payloads | 0 | 0 |

Les quatre alertes sont des séances absentes : `ACAN.PA`, `ARTO.PA`,
`LHYFE.PA`, `PERR.PA`. La présence d'une réponse pour un titre ne garantit
pas qu'elle couvre toutes les séances demandées. Ne pas assimiler 0 échec
réseau à 100 % de couverture de features.

Le contrôle hors ligne `service/fr/bootstrap_qualification_16c.py`, réalisé
après terminaison, produit :
`artifacts/fr/research/data_readiness_16c/qualification-20261006-v1/report.json`.

- 330 identités examinées, dont 294 collectées ;
- **242 jeux de 14 features numériques complets**, soit 82,31 % des 294 ;
- **223 titres passant les contrôles locaux**, soit 75,85 % des 294 ;
- **0 titre libéré pour le serving** : les réserves globales sont conservées ;
- aucune erreur d'intégrité/lecture dans les archives examinées.

Ce contrôle porte sur la fenêtre finissant le **5 octobre**, à l'heure réelle
de l'audit le 6 octobre au soir. Son rôle est
`BOOTSTRAP_WINDOW_AUDIT_NOT_DECISION_REPLAY` : ce n'est ni une décision
rétroactive à l'ouverture du 6 octobre ni une confirmation déjà observée de
l'ouverture du 7 octobre. Aucun score Oracle n'est calculé.

Les 19 titres calculables mais localement réservés **dans le contrôle v1** se répartissent ainsi :

| Réserve | Titres |
| --- | --- |
| Version d'identité ambiguë | ALAIR, ALECP, ALHRG, ALINV, ALKEY, ALMKT, ALU10, ALUNT, ALVAP, ALVAZ |
| Devise/ISIN de la version non conforme | ALAMA, EC, MLZAM |
| Dividende dans la fenêtre à qualifier | BNP, GLE, ODET, SBT, SPIE, TRI |

Les symboles ci-dessus portent le suffixe fournisseur `.PA` dans le rapport.
Ces réserves ne prouvent pas à elles seules une mauvaise identité du titre :
elles signalent que le contrat strict actuel ne peut pas l'admettre sans
examen des versions/MIC et événements. Aucun symbole n'a été retiré du
fichier d'univers et aucun champ source corrigé automatiquement.

Sur toutes les 330 identités, le rapport relève aussi 48 chemins à volume
nul, 40 fenêtres incomplètes, 36 identités non couvertes par la collecte des
actions, 30 identités terminées/réservées, 15 versions ambiguës, 6 réserves
devise/ISIN et 9 dividendes. Ces motifs se chevauchent et ne s'additionnent
pas en un total de titres.

Le master observé au moment de cet audit couvre bien le **5 octobre** : la
réserve de date disparaît **pour ce contrôle de warmup**, mais la continuité
historique reste non qualifiée. Cela ne résout pas la cadence J−1/J−2 pour
les décisions à l'ouverture décrite plus haut.

Commande du contrôle, vers un nouveau dossier à chaque exécution :

```powershell
python -m service.fr.bootstrap_qualification_16c --bootstrap-dir artifacts/fr/research/data_readiness_16c/bootstrap-20261006-v1 --output-dir artifacts/fr/research/data_readiness_16c/qualification-20261006-v1
```

**Suite nécessaire :** qualifier les versions d'identité et les événements
du sous-ensemble calculable, puis fixer un contrat prospectif du référentiel
réellement connu avant décision. Ne pas promouvoir les 223 sur la seule
base de ce comptage. La reprise de la collecte n'est pas nécessaire pour
obtenir ce bilan ; les lacunes sont documentées, pas masquées.

**Mise à jour 16-D, même bootstrap :** le contrôle d'identité comptait à tort
des anciens MIC terminaux comme actifs. Après correction et revue des versions,
le rapport `qualification-20261006-v2/report.json` compte **242 calculables,
233 passages locaux et toujours 0 servable**. Les dix faux blocages de la
première ligne du tableau sont résolus ; les trois devises nominales et les
six événements restent réservés. Voir le
[dossier identités, événements et référence connue](sprint_16d_identites_evenements_reference_observee.md)
pour les sources, les limites de qualification et le contrat temporel.
Les chiffres v1 ci-dessus sont conservés pour tracer le correctif, pas comme
bilan actuel. Le nouveau diagnostic de référence ne relâche pas le serving.

16-C ne sera clos qu'après bilan du rattrapage, nouveau comptage des features
et qualification/documentation de l'univers utilisable à la décision.
Si les preuves indépendantes restent insuffisantes, le bilan devra l'indiquer
et conserver le shadow bloqué, plutôt que promouvoir une simple collecte.
Les réserves opérationnelles du Sprint 15 et la revue du modèle restent
distinctes. Aucun résultat D1/D10 supplémentaire n'est démontré ici.
