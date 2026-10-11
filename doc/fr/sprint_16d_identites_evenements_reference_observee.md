# Sprint 16-D — Identités, événements réservés et référence connue à la décision

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

État : qualification technique et revue documentaire du 6 octobre 2026.
Suite : [16-E — preuves locales et décision réelle](sprint_16e_preuves_et_decision_reelle.md).
La suite a reçu la pièce Oeneo et confirmé le paiement annoncé SPIE dans
son PDF ; les réserves PIT et de traitement des événements demeurent.
**Aucun shadow, serving, ordre, entraînement ou changement SQL n'est activé.**
Le résultat ne constitue pas un GO de production. Les réserves conservées
ci-dessous sont des conditions de libération, pas des erreurs à ignorer.

## 1. Périmètre et preuves locales

Ce travail poursuit le [bilan du rattrapage 16-C](sprint_16c_rattrapage_et_reserves.md)
et le [contrat quotidien 16-B](sprint_16b_assemblage_quotidien_pit.md).
L'univers candidat contient 330 identités ; la collecte de démarrage concernait
294 titres actifs. La fenêtre de features se termine le 5 octobre 2026 et
nécessite 21 séances. Le bilan au soir du 6 octobre n'est **pas** un rejeu de
décision à l'ouverture du même jour.

Rapports à conserver :

- `artifacts/fr/research/data_readiness_16c/qualification-20261006-v1/report.json` : ancien contrôle, 223 passages locaux ;
- `artifacts/fr/research/data_readiness_16c/qualification-20261006-v2/report.json` : contrôle corrigé, 233 passages locaux ;
- `artifacts/fr/research/observed_reference_16d/opening-20261006-v1/report.json` : référence effectivement connue avant l'ouverture du 6 octobre.

Les sources du bootstrap et les valeurs numériques ne sont pas réécrites.
L'empreinte du jeu numérique reste
`c6e61d8fdc11b14a8923a221f02201a7463343b85f4a92c0a26234640f23a856`.

## 2. Faux blocage d'identité corrigé

L'ancien contrôle traitait deux versions applicables sur deux MIC comme deux
cotations actives, même si l'une était terminale. Un MIC désigne une place ou
un segment de négociation, pas un second émetteur.

Exemples observés :

| Symbole EODHD | Version active | Ancienne version terminale | Conclusion locale |
| --- | --- | --- | --- |
| ALAIR.PA | ALXP, premier jour déclaré 27/06/2023 | XMLI, fin déclarée 26/06/2023 | Une seule place active |
| ALECP.PA | ALXP, premier jour déclaré 18/11/2021 | XPAR, fin déclarée 17/11/2021 | Une seule place active |

`identity_resolution` dans `service/fr/daily_feature_adapter_16b.py` applique
désormais ces étapes :

1. Retenir les versions dont l'intervalle couvre la date examinée.
2. Refuser plusieurs versions simultanées **au sein du même MIC** : ce cas
   reste ambigu, même si une des versions semble terminale.
3. Écarter les versions `TermntdRcrd` / `CancRcrd`, les fins de cotation déjà
   effectives et les premières cotations encore futures.
4. Exiger exactement un MIC actif résiduel ; zéro ou plusieurs restent réservés.
5. Contrôler l'ISIN et un CFI de type action, puis conserver le MIC réellement
   résolu dans la ligne candidate, pas le premier MIC de la liste statique.

Les dix titres calculables débloqués **localement** sont ALAIR, ALECP, ALHRG,
ALINV, ALKEY, ALMKT, ALU10, ALUNT, ALVAP et ALVAZ, tous avec suffixe `.PA`.
Les ambiguïtés réelles ne sont pas désactivées et la preuve historique
indépendante de négociabilité reste distincte.

## 3. Devise nominale : ne pas la confondre avec la devise de cotation

Le lecteur FIRDS actuel alimente `currency` depuis `NtnlCcy` : c'est la devise
nominale. Ce champ seul ne certifie pas la devise utilisée pour les prix EODHD
ou les exécutions. La nouvelle résolution l'expose comme `nominal_currency`
et indique `trading_currency_independently_verified: false`.

| Titre calculable | ISIN | Devise nominale FIRDS | Réserve maintenue |
| --- | --- | --- | --- |
| ALAMA.PA | GB00BNKGZC51 | GBP | Devise de cotation à prouver séparément |
| EC.PA | GA0000121459 | USD | Devise de cotation à prouver séparément |
| MLZAM.PA | ZM0000000037 | ZMW | Devise de cotation à prouver séparément |

Le motif est `NON_EUR_NOMINAL_REQUIRES_TRADING_CURRENCY_PROOF`.
Ce n'est ni une preuve que leurs prix sont faux, ni une autorisation de les
convertir. Une devise nominale EUR ne devient pas non plus une preuve
indépendante de cotation EUR. Cette limite reste dans la qualification globale.

## 4. Dividendes : revue des modalités, sans libération rétroactive

Les six titres calculables avec dividende dans la fenêtre sont BNP, GLE,
ODET, SBT, SPIE et TRI. ACAN, ALGTR et ARTO sont également concernés dans
l'univers complet, mais leurs chemins numériques ont d'autres réserves.
Ils ne disparaissent donc pas du dossier au motif qu'ils sont non calculables.

### 4.1 Modalités publiées vérifiées ou corroborées

Les sources sont consultées pendant cet audit. **Une publication ancienne
retrouvée aujourd'hui n'était pas nécessairement archivée par l'application
avant la décision passée.** Les dates ci-dessous sont des dates annoncées,
pas des preuves bancaires de paiement exécuté.

| Symbole | Montant par action | Détachement annoncé | Paiement annoncé | Niveau de revue actuel |
| --- | --- | --- | --- | --- |
| BNP.PA | 3,23 EUR | 24/09/2026 | 28/09/2026 | Modalités d'acompte confirmées dans le communiqué émetteur |
| GLE.PA | 0,75 EUR | 05/10/2026 | 07/10/2026 | Modalités confirmées dans le communiqué diffusé par l'émetteur ; paiement encore futur à la date de l'audit |
| ODET.PA | 380 EUR | 25/09/2026 | 29/09/2026 | Dividende exceptionnel et calendrier confirmés sur le site émetteur ; record date annoncée 28/09 |
| SBT.PA | 0,35 EUR | 30/09/2026 | 02/10/2026 | Modalités corroborées par le communiqué d'AG indexé ; téléchargement du PDF primaire refusé (403), pièce locale non qualifiée |
| SPIE.PA | 0,32 EUR | 15/09/2026 | Non confirmé par la page consultée | Montant et détachement confirmés ; EODHD indique 17/09, à vérifier séparément |
| TRI.PA | 2,40 EUR | 29/09/2026 | À compter du 01/10/2026 | Deuxième acompte décidé, calendrier confirmé dans le PDF émetteur, page 3 |

Sources précises :

- BNP : [communiqué des résultats T2 2026](https://invest.bnpparibas/document/2q26-pr).
- Société Générale : [communiqué de l'émetteur diffusé le 30 juillet 2026](https://www.globenewswire.com/news-release/2026/07/30/3335727/0/fr/Soci%C3%A9t%C3%A9-G%C3%A9n%C3%A9rale-R%C3%A9sultats-du-2%C3%A8me-trimestre-et-du-1er-semestre-2026.html).
- Odet : [site officiel, annonces financières](https://www.compagniedelodet.net/).
- Oeneo : [espace investisseurs, communiqué d'AG du 22 juillet 2026](https://oeneo.com/espace-investisseurs/?annee=2026), [diffusion du communiqué d'AG](https://www.webdisclosure.fr/press-release/oeneo-epa-sbt-compte-rendu-de-lassemblee-generale-mixte-du-22-juillet-2026-zAUfAP4pOPL).
- SPIE : [résultats semestriels publiés le 30 juillet 2026](https://www.spie.com/fr/journalistes/actualites/resultats-semestriels-2026).
- Trigano : [communiqué du 23 septembre 2026, page 3](https://trigano-finance.com/download/26918/08af5f02bd94ebd46c44f8b35705f922/).

### 4.2 Anomalies et preuves qui restent nécessaires

Le champ fournisseur `declarationDate` n'est pas adopté comme date de
disponibilité PIT. Notamment, EODHD indique le 26 mars pour le dividende
Trigano de septembre, alors que le communiqué consulté du 23 septembre
décrit le deuxième acompte et distingue le premier acompte d'avril.
Société Générale porte une `declarationDate` fournisseur au 30 avril, alors
que le communiqué consulté est du 30 juillet et mentionne la décision du
29 juillet. Ces décalages nécessitent une qualification du champ fournisseur,
pas un remplacement aveugle par une date trouvée sur le Web.

Pour Odet et Oeneo, des dates de paiement manquent dans le payload EODHD.
Les annonces retrouvées complètent le dossier documentaire, **pas la base**.
Les montants concordants ne suffisent pas à qualifier le traitement cash,
l'ajustement des barres, les droits des porteurs et la disponibilité de la preuve.

Statut conservé : `UNQUALIFIED_DIV_IN_FEATURE_WINDOW`. Pour le lever, il faut :

1. Archiver la pièce autorisée et son empreinte, avec heure réelle de réception.
2. Relier l'événement à l'ISIN, au détachement et à ses modalités définitives.
3. Vérifier les modalités restant partielles et les trois titres non revus.
4. Déterminer l'effet sur les features et le traitement économique sans doubler
   un ajustement déjà présent dans les prix.
5. Fixer `available_at` à une heure prouvée ; faute de preuve de disponibilité
   historique, conserver l'heure réelle d'observation pour l'usage prospectif.

Cette revue de liens et de modalités n'est pas encore une archive locale
hashée de toutes les pièces. Aucun paiement réalisé n'est certifié ici.

## 5. Contrat du dernier référentiel effectivement connu

Le nouveau service `service/fr/observed_reference_16d.py` décrit un référentiel
diagnostique. Configuration : `config/research_fr/observed_reference_16d.yaml`.
Il ne remplace **pas** les exigences strictes de l'assemblage 16-B.

Pour une heure de décision horodatée avec fuseau :

1. Exiger que la séance servant aux features soit déjà clôturée.
2. Relire seulement les versions locales observées avant cette heure, en
   vérifiant les empreintes et les erreurs d'archive.
3. Sélectionner la dernière version connue, non une version reçue plus tard.
4. Exposer séparément `selected_coverage_end` et `selected_observed_at`.
5. Compter le retard en **séances XPAR**, pas en jours calendaires.
6. Refuser une couverture future, plus d'une séance de retard ou une
   observation vieille de plus de 96 heures.
7. Résoudre les identités à la dernière date couverte. Ne pas les déclarer
   négociables à la décision si une séance intermédiaire n'est pas observée.

Les bornes sont configurables vers des valeurs plus strictes : retard 0 ou 1,
âge 1 à 96 heures. Le contrat refuse l'activation du serving/ordres/SQL ou un
changement vers US/CN par simple surcharge de configuration.

### Exemple réel : ouverture du 6 octobre 2026

| Élément | Valeur |
| --- | --- |
| Décision examinée | 06/10/2026 09:00 Europe/Paris, soit 07:00 UTC |
| Séance des features | 05/10/2026 |
| Dernière référence connue à cette heure | Couverture jusqu'au 04/10/2026 |
| Réception de cette référence | 05/10/2026 19:28:39 UTC, soit 21:28:39 Paris |
| Âge de l'observation | Environ 11,52 heures |
| Retard de couverture | Une séance XPAR : 05/10/2026 |
| Statut | `KNOWN_REFERENCE_DIAGNOSTIC_ONLY` |

Le nouveau master couvrant le 5 octobre, reçu le 6 octobre au soir, ne peut
pas être injecté dans ce diagnostic d'ouverture. Une observation récente
ne signifie pas une couverture récente : les deux dates sont indépendantes.

Le rapport conserve `MASTER_CONTINUITY_UNQUALIFIED`,
`INDEPENDENT_REFERENCE_QUALIFICATION` et, si retard,
`UNOBSERVED_SESSION_NOT_PROVEN_UNCHANGED`. Le Delta ESMA du 9 septembre
reste absent de l'index officiel contrôlé ; aucune absence de modification
n'est inventée. Toutes les identités gardent
`tradability_at_decision_verified: false`.

Commande de diagnostic, avec un dossier nouveau à chaque exécution :

```powershell
python -m service.fr.observed_reference_16d --decision-at 2026-10-06T09:00:00+02:00 --feature-session 2026-10-05 --output-dir artifacts/fr/research/observed_reference_16d/opening-20261006-v2
```

## 6. Bilan et frontière de libération

| Mesure | Avant correctif | Après correctif |
| --- | --- | --- |
| Jeux numériques complets | 242 | 242 |
| Passages des contrôles locaux | 223 | 233 |
| Titres libérés pour serving | 0 | 0 |

Les neuf calculables encore réservés sont les trois devises nominales et
les six événements ci-dessus. Des réserves globales demeurent pour tous,
dont la continuité ESMA, la qualification indépendante et la revue de release.
Une meilleure résolution d'identité n'est pas un gain prédictif D1/D10.

La suite est de transformer les modalités revues en preuves locales
qualifiées, compléter les devises de cotation et observer une décision avec
la couverture réellement disponible. Un éventuel protocole acceptant une
référence retardée devra être explicitement approuvé ; le diagnostic présent
n'accorde pas cette autorisation. Ne pas contourner les réserves en passant
`tradable` ou `qualification` à vrai manuellement.

## 7. Non-régression

Tests : anciens MIC terminaux, ambiguïtés réellement actives, devise nominale,
retard d'une/deux séances, fraîcheur, couverture future, séance non clôturée,
interdiction d'activer le serving par configuration, plus contrats 16-A/16-B,
bootstrap 16-C, features et collecteurs FR. La campagne ciblée comporte
67 tests passants ; cela ne signifie pas que tous les tests du projet ont été
réexécutés ni que les réserves de données ont disparu.
