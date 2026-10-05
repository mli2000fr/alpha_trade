# Collectes FR séparées : consensus, borrow et options

## État courant : collecte quotidienne activée en quarantaine

Le 05/10/2026, l'utilisateur a autorisé la collecte sur l'ensemble du
référentiel FR actif. `fr_consensus_snapshot` est désormais `enabled: true`,
`ACTIVE_RESEARCH`, avec reprise quotidienne. **Le protocole courant, les
limites et le chemin vers ML/backtest sont décrits dans
[consensus_collecte_quotidienne.md](consensus_collecte_quotidienne.md).**

Le suivi ponctuel Codex du 6 octobre a été mis en pause, remplacé par le batch.
Les sections ci-dessous conservent l'historique du pilote et de sa revue :
leurs mentions « planification désactivée » et « suivi demain » ne décrivent
plus l'état actuel. Le CLI `service.fr.consensus_snapshot` utilise maintenant
le mode univers complet de `batch_fr.yaml`, même pour un lancement manuel.
Borrow/options restent désactivés comme collectes complètes. Le POC Excel
Euronext a été abandonné et son service retiré. Le nouveau
[POC MiFIR + FIRDS](options_mifir_firds_poc.md) confirme une chaîne publique
indépendante pour les transactions différées et les caractéristiques des
options. L'intérêt ouvert, bid/ask, ajustements et unités ne sont pas qualifiés ;
le besoin complet options n'est pas déclaré débloqué.

Au 6 octobre, le batch partiel `fr_options_mifir_trade_sync` est implémenté
pour tout le référentiel FR actif, mais livré `enabled: false` pour activation
par l'utilisateur. [Documentation de la collecte et des compteurs](options_mifir_collecte_quotidienne.md).
Il utilise le launcher commun mail/Telegram et reste exclusivement en quarantaine.

## Périmètre et décision du 5 octobre 2026

L'ancienne réserve `fr_consensus_borrow_options` n'avait aucun collecteur
qualifié. Son entrée a été retirée de `batch_fr.yaml` le 6 octobre 2026 à la
demande de l'utilisateur ; elle n'apparaît plus dans la page Batch. Trois entrées distinctes dans
`batch_fr.yaml` la remplacent. Elles apparaissent automatiquement dans
Workflow & Orchestration → Batch → France, avec leur statut et leurs motifs.
Aucune tâche Windows existante n'est installée, supprimée ou modifiée ici.
Les enchères mentionnées dans l'ancienne réserve ne sont pas implémentées.

| Collecte | État | Besoin |
|---|---|---|
| `fr_consensus_snapshot` | Pilote implémenté, planification désactivée | Qualifier Yahoo, couverture, identité et licence |
| `fr_borrow_snapshot` | Désactivée, fournisseur manquant | Disponibilité et frais d'emprunt horodatés |
| `fr_options_snapshot` | Désactivée, fournisseur manquant | Contrats FR, ajustements, cotations et droits d'usage |

## POC consensus Yahoo

Service : `service/fr/consensus_snapshot.py`, adaptateur Yahoo déjà installé
dans `service/yahoo`. Le pilote configurable contient OR.PA, SU.PA et BN.PA,
trois sociétés actives du référentiel S6C. Budget : trois titres, plafond
technique dix ; appels séquentiels avec intervalle configurable >= 1 seconde.
Le nombre de requêtes physiques est supérieur au nombre de titres et dépend
de yfinance (authentification/cookies/endpoints). Ne pas promettre un quota Yahoo.

Pour chaque titre, on recueille :

- nombre d'analystes, recommandation moyenne et libellé ;
- objectifs de cours bas, moyen, médian, haut ;
- tableaux d'estimations EPS et revenus par période ;
- tendances EPS : estimation courante et valeurs antérieures lorsque proposées.

Les méthodes Yahoo peuvent renvoyer un tableau vide sans lever d'exception.
Cela produit `EMPTY_OR_UNAVAILABLE`, pas une preuve qu'aucun analyste ne couvre
la société. Les familles absentes restent nulles/vides, jamais zéro inventé.
Toute identité contradictoire, réponse sans consensus ou erreur bloquante
fait échouer le pilote, même si les titres précédents ont été archivés.
Le rapport conserve les erreurs et la couverture par titre/famille.

### Identité, provenance et PIT

Le pilote exige une identité S6C unique, vérifiée et active et une réponse Yahoo
avec même symbole, devise EUR et place Paris. Ce contrôle n'est **pas** une
certification du rattachement Yahoo/ISIN. Les premiers snapshots restent
`identity_qualified=false`. Une revue actuelle explicite des trois titres a
ensuite été ajoutée (voir ci-dessous) : les nouvelles observations conformes
portent `identity_qualified=true` dans le seul périmètre
`CURRENT_PILOT_MAPPING_ONLY`, sans promotion de leurs données au ML.

Chaque réponse structurée est archivée par SHA256. Dans un même dossier,
deux réponses identiques partagent un objet ; chaque passage ajoute une
observation. Les dossiers POC sont séparés et peuvent donc conserver chacun
leur copie. `available_at=observed_at` UTC, après réception. Les valeurs
« 7daysAgo », « 30daysAgo », etc. reçues aujourd'hui ne sont pas présentées
comme des snapshots historiquement disponibles à ces anciennes dates.

**Quarantaine uniquement : aucune écriture SQL, aucun entraînement, aucun
backtest, aucun serving.** Les objectifs de cours ont un horizon analyste qui
n'est pas automatiquement H20 ; aucune capacité D1/D10 n'est démontrée.
Les recommandations ne remplacent pas les estimations EPS et vice versa.

### Exécuter et lire le résultat

Depuis F:\projets :

```powershell
python -u -m service.fr.consensus_snapshot --dry-run
python -u -m service.fr.consensus_snapshot
```

Le CLI POC est une exécution manuelle explicite, indépendante de `enabled=false`
du scheduler. Résultats :
`artifacts/fr/operations/fr_consensus_snapshot/poc/<observation>/report.json`,
`objects/` et `observations/`. Aucun ancien run n'est écrasé.
Ce CLI ne déclenche pas de notification email/Telegram. Le raccordement au
runner FR est présent pour une activation ultérieure ; son launcher commun
assure les notifications habituelles. Ne pas activer avant qualification.

Étapes restantes : inspecter les valeurs/identités, répéter à une autre date,
mesurer stabilité et couverture, vérifier licence et limites d'accès, puis
seulement décider d'une collecte quotidienne. Un abonnement aux barres EODHD
et l'accès INPI ne suffisent pas à débloquer consensus/borrow/options.

## Borrow et options

AMF collecte les positions courtes publiques, pas la possibilité d'emprunter
un titre ni son coût. Garder `fr_amf_short_sync` séparé.
Pour les options, qualifier une source réellement Euronext/FR et non les
contrats américains. Ne pas remplir bid/ask, intérêt ouvert ou Greeks avec
des substituts non équivalents. Les deux collectes restent sans handler et
échouent fermées si une configuration essaie de les activer.

## Résultat du premier passage réel

Rapport du 05/10/2026, 23:14 Paris :
`artifacts/fr/operations/fr_consensus_snapshot/poc/20261005T211454184549Z/report.json`.
Trois demandés, trois reçus et archivés, zéro échec, zéro alerte de famille.

| Symbole | Nombre d'analystes annoncé | Objectif moyen EUR |
|---|---:|---:|
| OR.PA | 24 | 417,96 |
| SU.PA | 23 | 327,80 |
| BN.PA | 22 | 78,93 |

Les trois tableaux EPS, revenus et tendance EPS sont présents pour chaque
titre. Leur présence ne certifie ni exactitude des chiffres, ni exhaustivité,
ni validité PIT historique. L'objectif moyen n'est pas une prévision H20.
Une première tentative a échoué TLS sans archiver de consensus. Le transport
curl_cffi a ensuite été raccordé aux autorités de confiance système et certifi
déjà utilisées par les services FR : TLS et vérification de nom restent actifs,
aucun `verify=False`. Le certificat de confiance n'est pas ajouté à l'application
globalement. Un verrou commun protège désormais POC et runner contre les
collectes concurrentes. Dix-sept tests ciblés ont validé le catalogue FR et
les contrôles d'identité, absences, dry-run et idempotence des objets.

Décision : faisabilité technique du petit pilote **positive** ; source,
identités et données encore à qualifier. Aucun gain directionnel testé.
Ne pas étendre ou activer automatiquement la collecte quotidienne.

## Revue des identités actuelles et second passage

Revue du 05/10/2026 par l'assistant, à partir du référentiel local ESMA/S6C,
des pages officielles ouvertes et des métadonnées réellement renvoyées par
Yahoo. Ce n'est pas une seconde revue humaine indépendante, ni une validation
des valeurs du consensus par les sociétés.

| Yahoo | Nom Yahoo reçu | ISIN vérifié | Preuve officielle consultée |
|---|---|---|---|
| OR.PA | L'Oréal S.A. | FR0000120321 | [L'Oréal Finance : codes et action](https://www.loreal-finance.com/fr/laction) |
| SU.PA | Schneider Electric S.E. | FR0000121972 | [Euronext : instrument XPAR](https://live.euronext.com/en/product/equities/FR0000121972-XPAR) |
| BN.PA | Danone S.A. | FR0000120644 | [Danone : FAQ actionnaires, codes Reuters/ISIN](https://www.danone.com/investors/shareholders/faq-and-contact.html) |

Les trois réponses Yahoo indiquent `quoteType=EQUITY`, `exchange=PAR`,
`currency=EUR`. Les identités Yahoo (symbol, shortName, longName, quoteType,
currency, exchange, website) sont désormais archivées avec le contenu.
Les trois règles `identity_checks` de `batch_fr.yaml` imposent le même ISIN
local, le nom Yahoo exact et la classe EQUITY. La revue expire après 30 jours ;
une contradiction ou expiration fait échouer le titre, sans recherche floue
ni substitution d'ADR. Le site web Yahoo aide la revue mais n'est pas utilisé
comme preuve suffisante à lui seul. Les sources officielles ont été consultées
via navigateur de recherche, leurs URLs et date de revue sont conservées ;
leurs pages complètes ne sont pas archivées ici.

Référence revue :
`artifacts/fr/operations/fr_consensus_snapshot/poc/20261005T211946047491Z`.
Trois observations réussies, trois contrôles d'identité positifs, aucun échec
ou alerte. Les anciens dossiers restent immuables. Les passages supplémentaires
du 5 octobre servent aux contrôles techniques, **pas** à mesurer des révisions.

Un suivi attaché à ce chat, `deuxi-me-observation-consensus-fr`, prévoit un
second passage le **6 octobre 2026 à 20:00 Europe/Paris**, puis son arrêt après
livraison (ou blocage nécessitant l'utilisateur). Ce suivi n'active ni tâche
Windows ni batch quotidien ; la machine et l'application doivent rester
disponibles. Si indisponibles, reprise au prochain passage disponible :
conserver la date réelle, ne jamais inventer une observation du 6 octobre.

Exécution manuelle alternative, si le passage différé n'a pas eu lieu :

```powershell
python -u -m service.fr.consensus_snapshot --not-before 2026-10-06
python -u -m service.fr.consensus_revision_compare --baseline artifacts/fr/operations/fr_consensus_snapshot/poc/20261005T211946047491Z --later <dossier_POC_reussi_de_la_nouvelle_date>
```

Remplacer le dernier argument par le dossier réel, sans chevrons. Le second
CLI écrit `revision_comparison.json` dans ce dossier. Il vérifie les hashes,
les ISIN/règles de revue, les devises déclarées des tableaux et les observations
complètes. Deux dates **Europe/Paris** différentes et chronologiques sont
requises, pas seulement deux dates UTC ou deux dossiers distincts.

Comparaison des recommandations, objectifs et cellules EPS/revenus :
valeur avant/après, différence absolue, différence relative si dénominateur
non nul. Donnée apparue/disparue = changement de couverture, pas révision
numérique. Valeurs identiques = zéro changement, pas résultat négatif du ML.
La source utilise des périodes relatives `0q`, `+1q`, `0y`, `+1y` : une variation
n'est **pas certifiée révision à exercice constant** sans identifier l'exercice
fiscal sous-jacent. L'objectif de ce second passage est de tester la collecte
prospective et la détection de changements, pas la prédiction D1/D10.

Tests couvrant rejet même date Paris, valeurs identiques, données manquantes,
corruption de hash et contradictions d'identité :
`tests/test_fr_consensus_revision_compare.py` et
`tests/test_fr_consensus_snapshot.py`.
