# Sprint 16-G — pilote identité, devise et opérations sur titres

## Objet et résultat au 8 octobre 2026

Pilote de qualification sur **AIR.PA, OR.PA et SAN.PA**, trois candidats du
dossier figé de 233 titres. Choix de grandes sociétés disposant de pages
investisseurs identifiables, sans sélection selon la performance future.
Ce pilote est un inventaire documentaire : **aucun titre n'est encore libéré**.

Rapport reproductible :
`artifacts/fr/research/issuer_pilot_16g/three-issuers-20261008-v1/report.json`.
Service : `service/fr/issuer_pilot_16g.py`.

| Titre | ISIN / place du dossier | Dividendes/splits déclarés dans la fenêtre | Versions de notices DILA disponibles avant décision |
|---|---|---:|---:|
| AIR.PA | NL0000235190 / XPAR | 0 | 0 |
| OR.PA | FR0000120321 / XPAR | 0 | 2 |
| SAN.PA | FR0000120578 / XPAR | 0 | 4 |

Fenêtre : 9 septembre–7 octobre 2026. Décision figée : 8 octobre à 09:00 Paris.
Les zéros fournisseur ne constituent pas une preuve indépendante d'absence.
Les zéros DILA ne constituent pas une preuve d'exhaustivité de la collecte.
Les six notices sont des versions de métadonnées, **pas six opérations sur titres**.

## Ce que les archives apportent effectivement

L'Oréal : deux notices, française et anglaise, relatives au capital et aux
droits de vote au 30 septembre. Sanofi : deux langues pour l'annonce d'alliance
avec Regeneron et deux pour la disponibilité de l'aide-mémoire des résultats T3.
Les documents associés n'ont pas été lus par le traitement d'inventaire initial. Leur titre ne
suffit pas à extraire une date effective, un ratio ou un montant d'ajustement.

Le service lit les observations DILA déjà archivées, vérifie le SHA256 des
réponses brutes et la concordance de leurs fenêtres. Il exclut les observations
et transmissions postérieures à la décision. Il ne lit pas `latest.json`, qui
peut contenir des informations plus récentes. Il conserve les différentes
versions de métadonnées et déduplique les observations répétées de la même
version ; une traduction reste une notice distincte, pas un second événement.

Les déclarations fournisseur du dossier sont rattachées à leurs observations
et réponses brutes vérifiées. Aucun nouvel appel réseau ni accès SQL n'est
effectué par le service. Un nouveau répertoire est exigé pour ne pas écraser
un rapport précédent.

## Lecture des sources primaires publiques

Consultation de pages HTML le 8 octobre, **postérieure à la décision figée**.
Ces notes ne sont pas des documents bruts archivés et horodatés avant 09:00.
Elles orientent la qualification ; elles ne doivent pas entrer rétroactivement
dans les features ou lever un contrôle PIT.

- [Airbus — informations sur l'action](https://www.airbus.com/en/investors/share-price-and-information) : ISIN NL0000235190, cotation notamment à Paris, changements de nom sans changement d'ISIN. La page mentionne des rachats d'actions en septembre 2026. Ils ne sont pas couverts par les seuls endpoints dividendes/splits. La valeur nominale d'un euro n'est pas une preuve de devise de négociation.
- [L'Oréal — l'action](https://www.loreal-finance.com/fr/laction) : action négociable FR0000120321, OR.PA, Euronext Paris. Ne pas substituer les codes de titres au nominatif bénéficiant de la prime de fidélité au code de négociation. L'affichage courant en euros ne prouve pas à lui seul l'intervalle historique complet.
- [Sanofi — actionnaires individuels](https://www.sanofi.com/en/investors/individual-shareholders) : action ordinaire SAN à Paris, ISIN FR0000120578 ; distinguer les ADS SNY cotés aux États-Unis.

Un rachat d'actions propres ne déclenche pas automatiquement une correction
du prix historique comme un split. Il faut distinguer événements informatifs,
événements affectant les droits du détenteur et ajustements applicables aux bars.
Ce constat ne révèle pas à lui seul une erreur EODHD.

## Réserves et prochaine action utile

Suite de la revue du 8 octobre : [preuves ponctuelles, accès DILA et limites
de qualification](sprint_16g_revue_sources_pilote_20261008.md). Les essais de
consultation PDF DILA n'avaient pas abouti. **Après GO, les six pièces ont été
archivées via le miroir officiel et leurs 16 pages examinées** ; la revue
complémentaire distingue ce résultat des anciens essais. Aucun événement n'a été certifié
à partir de son seul titre. La future date de décision ne lève pas à elle
seule les réserves de devise et d'opérations sur titres.

Pour les trois titres, la devise nominale est EUR dans le dossier, mais la
devise de cotation sur l'intervalle et les opérations sur titres ne sont pas
indépendamment qualifiées. Les treize séances précédant l'ancrage Full restent
réservées ; ce pilote ne les répare pas.

La prochaine action est de rechercher une preuve datée de la devise de
négociation et les avis d'opérations effectives couvrant la fenêtre, puis de
raccorder uniquement les avis vérifiés par ISIN/place/date. Une consultation
courante peut servir à une future décision, jamais être antidatée. Un corpus
de communiqués incomplet ne doit pas être certifié « aucun événement ».

Ne pas élargir automatiquement la collecte de sites investisseurs : une page
publique ne vaut pas autorisation de collecte massive. Ce pilote ne réactive
aucune source suspendue pour droits/prudence et ne change pas les autorisations
des batchs. Le pilote initial ne collectait aucun flux de cours Euronext ;
le POC ponctuel ajouté ensuite est décrit ci-dessous. Les notes de sources
ne constituent pas un avis juridique ni une nouvelle licence.

## Reproduire

Suite du travail : [reconstruction partielle pré-ancrage](sprint_16g_reparation_preancrage.md).
L'index Full du 12 septembre et ses Delta ouvrent une piste pour dix séances ;
les 9–11 septembre restent réservées. Les corroborations ponctuelles actions/
devises retrouvées sont détaillées dans ce document, sans libération implicite.

```powershell
python -m service.fr.issuer_pilot_16g --packet artifacts/fr/research/release_review_16g3/anchor-20261008-v2/report.json --output-dir artifacts/fr/research/issuer_pilot_16g/nouveau-pilote
python -m pytest tests/test_fr_issuer_pilot_16g.py -q --no-cov
```

Six tests couvrent population exacte, population incomplète, preuve altérée,
exclusion post-décision, absence de certification implicite des documents et
déduplication des observations. Aucun entraînement, aucune écriture en base,
aucune activation de serving ou d'ordres.

Vérification exécutée : **152 tests ciblés Sprint 16 passent**, dont ces six
nouveaux tests (`tests/test_fr_*16*.py`, `--no-cov`). Il s'agit d'une suite
ciblée, pas d'une mesure de couverture globale de l'application. Le premier
lancement des six tests avec la couverture globale par défaut a échoué sur
le seuil global de 70 %, sans échec d'assertion ; la suite ciblée a ensuite
été exécutée sans cette mesure globale inadaptée à ce sous-ensemble.

Voir aussi [parité des features](sprint_16g_parite_features_et_fenetre.md),
[dossier de revue](sprint_16g3_revue_liberation_actions_devises.md) et
[audit des autorisations](audit_autorisations_collectes_20261006.md).

## Complément du 8 octobre — devise observée sur une séance

Le [POC MiFIR actions](sprint_16g_preuve_devise_mifir.md) apporte une preuve EUR
sur XPAR le 7 octobre pour AIR, OR et SAN. Sa réception à 22:22 Paris le
8 octobre interdit de l'antidater à l'ouverture. La qualification de tout
l'intervalle et des opérations reste réservée. Suite ciblée : 200 tests passent.
