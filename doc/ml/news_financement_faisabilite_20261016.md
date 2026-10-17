# News de financement + réaction du prix — faisabilité du 16 octobre 2026

> Suite opérationnelle du même jour : [ingestion quotidienne sécurisée livrée](../operations/eodhd_news_ingestion_sync.md).
> TLS EODHD corrigé, nouveau batch séparé installé ; smoke 3 titres/48 occurrences/
> 18 nouvelles versions, reprise sans appel. Le présent audit reste le constat
> **antérieur à cette remédiation**, pas un état courant réécrit. La qualification
> de nouvelles annonces et l'expérience financière restent ouvertes.

## Verdict

**`BLOCKED_DATA_FEASIBILITY` : pas encore de corpus permettant de tester un
signal directionnel.** Ce n'est pas un échec économique du signal, ni une
preuve d'absence d'annonces dans le marché. Aucun entraînement, calcul de
rendement, ordre, écriture SQL ou changement de batch/configuration.

Suite au GO : contrôle de la collecte, requalification technique bornée du
corpus existant et couverture des barres intraday. La famille reste celle
définie antérieurement : **nouvelle émission primaire d'actions**, pas dette,
revente par des actionnaires, autorisation shelf ou rappel d'une ancienne opération.

## Collecte : trois constats distincts

1. `config.yaml:us_pipeline.steps` contient `[1,2,3,4,5,6,7,9]` : **pas de
   News/Sentiment du lundi au jeudi** dans ce workflow. `steps_friday` contient
   aussi 8. Les plans figés des séances du 13, 14 et 15 octobre confirment
   l'omission. Le succès global du pipeline n'est donc pas une preuve de
   collecte de news. Ni configuration ni tâche Windows modifiées.
2. Au cutoff du dossier, les archives ne contiennent toujours que **55 articles,
   110 reçus confirmés**, du pilote du 15 octobre (21:33–21:34 UTC, soit
   23:33–23:34 Paris). Aucun reçu en attente. Comparaison avec le dossier V3
   antérieur : mêmes articles et couples article/titre, pas de nouvelle collecte
   prospective constatée dans ces tables. Cela ne signifie pas que `news_raw`
   est vide ni qu'aucune collecte ancienne n'a jamais fonctionné.
3. Les 12 763 checkpoints `eodhd_news` ont `news_ingested_at=NULL` : 12 762
   affichent `success`, un `running`. Ces statuts et leurs watermarks anciens ne
   certifient pas une ingestion récente et archivée. Le checkpoint `running`
   n'a pas été supprimé ni présumé orphelin ; un workflow est en cours pendant
   l'audit, sans étape 8 sélectionnée. Les autres lancements manuels et tâches
   externes ne sont pas certifiés par cette lecture.

Une tentative HTTPS de diagnostic, avec le transport ordinaire
`requests.Session` utilisé par `NewsIngestionService`, reproduit
**`SSLCertVerificationError`**, avant réponse HTTP. Une tentative maximum,
aucun texte inséré ni checkpoint déplacé. Le pilote précédent disposait d'un
adaptateur de confiance système vérifié, limité à son propre processus : il
n'a pas corrigé le transport de production. **Ne jamais utiliser `verify=False`.**

## Qualification des annonces

Univers courant : `config/univers_batch/univers_filtred_tradable.txt`, 1 790
titres, empreinte liée au dossier source. Ce n'est pas un univers historique PIT.

| Mesure | Résultat |
| --- | ---: |
| Articles distincts archivés | 55 |
| Couples article/titre dans l'univers | 112 |
| Couples présélectionnés par mots-clés | 3 |
| Textes distincts correspondants | 1 |
| Couples relus techniquement / textes distincts | 13 / 9 |
| Nouvelles annonces primaires qualifiées dans cette revue | **0** |

Les trois présélections concernent toujours le texte rappelant un financement
SNPS de **2025**, également associé à KEYS et SIEGY (concurrents). Les témoins
montrent aussi les confusions KEYS Royaume-Uni/US et SO/SCCO : quatre couples
avec mauvaise identité apparente de l'événement/marché dans la revue.

La requalification réutilise la lecture technique des **mêmes textes figés**,
avec nouvelles attestations et citations vérifiées. Ce n'est ni un nouveau
classifieur validé, ni une seconde personne indépendante, ni une lecture des
55 textes. Les autres articles restent non approuvés : un dépistage par
mots-clés peut manquer des annonces. Aucun rappel exhaustif n'est revendiqué.

Les réserves portent sur identité, nouveauté, corps court, dates et citations.
L'outil ne transforme pas un ticker fournisseur en émetteur certifié. Une
analyse produite aujourd'hui ne reçoit jamais une disponibilité historique
antérieure à sa validation effective.

## Couverture intraday — diagnostic seulement

Pour chaque couple du corpus, sans sélection par prix, classement Oracle ou
résultat futur, rechercher **six barres 5 minutes avant et six après** :

- publication en séance : exclure la barre contenant l'annonce si son heure
  n'est pas exactement une frontière 5 minutes ; fenêtres continues de 30 min ;
- publication hors séance : dernières 30 min de la séance précédente et
  premières 30 min de la suivante, selon calendrier NYSE, sans fallback ouvré ;
- pas de raccordement artificiel pour les annonces en séance trop proches de
  l'ouverture ou clôture ; fenêtres non terminées réservées ;
- prix bruts positifs/cohérents/finis, volume positif, barres non remplies,
  intervalle exact, séance régulière ; aucun forward-fill ;
- fournisseur/flux évalués **séparément**, jamais SIP+IEX assemblés.

| Statut technique des couples | Nombre |
| --- | ---: |
| Fenêtres complètes dans un seul flux | **4** |
| Fenêtres manquantes ou invalides | 95 |
| Place insuffisante dans la séance régulière | 13 |
| Fenêtres complètes parmi les trois présélections | **0** |

Les quatre fenêtres complètes concernent IRTC (deux articles), DLB et KEYS,
dans `alpaca_sip`. Ce sont des **témoins techniques non approuvés comme
événements**, pas quatre annonces qualifiées ni un signal LONG/SHORT.

Une réaction de 30 min n'est observable qu'à la fin de sa fenêtre. Une future
décision devra être postérieure **à la réaction et à la disponibilité réelle
des textes, mappings et analyses**. Une fenêtre autour d'une publication
ancienne nouvellement collectée peut servir au diagnostic rétrospectif, pas
à démontrer une stratégie disponible à l'époque. `observed_at` des barres est
conservé ; aucune disponibilité historique certifiée par cette seule couverture.

**Aucun rendement avant/après n'est calculé**, aucune causalité mesurée, aucun
test D1/D10 ou TP/SL lancé. Couverture technique et qualification événementielle
restent deux conditions distinctes.

## Livrables et reproduction

Code : `scripts/research/us_news_financing_feasibility.py` ; requêtes SQL
`READ ONLY`, base US imposée, timeout 15 s, 200 couples maximum, 240 barres par
requête maximum avec arrêt explicite si troncature. Pas de DDL, nouveau
fournisseur, appel GPT ou abonnement. Entrées et sorties liées par empreintes.

**81 tests ciblés passent** : fenêtres/bornes de séance et demi-séances,
publications sous-seconde, trous, barres invalides et doublons, séparation des
flux, empreintes et absence de régression archive/revue/collecte pilote.
Fixtures locales : aucune écriture SQL métier pendant les tests.

- Corpus/refonte de revue :
  `artifacts/research/us_news_event_qualification/20261016-feasibility-v1/`.
- Rapport définitif :
  `artifacts/research/us_news_financing_feasibility/20261016-v2/report.json`.
- Fenêtres, sources et barres exactes : `intraday_windows.json` et
  `intraday_rows.json` dans le même dossier.
- Diagnostic TLS :
  `artifacts/research/us_news_financing_feasibility/transport-20261016-v1.json`.

Incident local de rapport V1 : `SUM` MySQL retournait un `Decimal` non
sérialisable. Corrigé en compteur entier, **V1 partielle conservée**, V2
complète séparée ; pas d'incident de collecte ni de modification en base.

```powershell
python -u -m scripts.research.us_news_financing_feasibility --pack artifacts/research/us_news_event_qualification/20261016-feasibility-v1 --output artifacts/research/us_news_financing_feasibility/NOUVEAU_DOSSIER
```

Le dossier de sortie doit être nouveau. Rafraîchir auparavant le corpus avec
le collecteur de preuves existant et effectuer une revue liée à ce nouveau
dossier ; l'outil de lecture technique des neuf textes n'est pas applicable
automatiquement à de nouveaux articles.

## Prochaine borne, sur nouveau GO

1. Corriger/tester la confiance TLS du transport news ordinaire avec vérification
   des certificats et noms d'hôte, puis prouver un passage réel borné avec reçus.
2. Choisir explicitement une **ingestion quotidienne** compatible avec la plage
   PC 20h–7h30 : ajouter 8 en semaine ou séparer ingestion et scoring lourd
   hebdomadaire. Ne pas changer implicitement les listes voulues par l'utilisateur.
   Recharger J−7 ne recrée pas les heures de réception des jours PC éteint.
3. Accumuler/revoir les nouvelles annonces distinctes, puis obtenir les barres
   manquantes sur un périmètre déterminé par les événements, non les rendements.
4. Seulement si ce corpus passe : figer le protocole Oracle seul vs Oracle+
   événement/réaction, avec témoins, secteurs, périodes et protections identiques.
   D1/D10 à H20 et rentabilité TP/SL sont des objectifs séparés.

Pas d'entraînement ni de backtest financier autorisé par ce seul rapport.
