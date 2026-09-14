# E21-B — Extraction structurée et comparabilité de la guidance

## Livré : socle conservateur de recherche

Service : `service/forward_pit/guidance_structured.py`. Aucun accès réseau,
aucune écriture SQL, aucun entraînement ni modification du serving.
Le premier passage a lu 14 documents distincts, extrait 85 candidats
numériques, sans erreur de hash. **Zéro paire automatiquement approuvée.**
Ce résultat est volontaire : identifier une fourchette n'identifie pas encore
une prévision annuelle comparable. Les documents du smoke sont des données
de développement, pas une validation indépendante.

Artefact : `artifacts/research/guidance_structured/e21b-20260914-v1/`.
`report.json` décrit la couverture ; `review_queue.json` contient les 85
candidats avec contexte, source, hash, URL, accession, CIK, date d'acceptation
et date de collecte. Les sources identiques sont dédupliquées par
CIK/accession/hash. Un hash incohérent ou chemin hors collection est rejeté.

## Champs et validation

### Résultat de la collecte 2023–2024 et revue bornée

Collecte terminée : ABM neuf dépôts / neuf annexes, TTC dix dépôts / dix
annexes, aucune erreur réseau, aucun dépôt tronqué. Aucune page ancienne
supplémentaire n'était nécessaire : submissions.recent couvre déjà cette
fenêtre. L'extension de lecture des archives n'a donc pas été exercée en
réseau dans ce run ; elle est couverte par tests unitaires.

Extraction gelée, sans retouche après lecture : 19 documents, 65 candidats,
zéro erreur de hash. Suggestion de mesure unique pour 18/65 candidats ; une
année fiscale candidate pour 38/65 ; échelle explicite pour 19/65. Ce sont
des taux de présence, pas des précisions : absence d'échelle million/milliard
est normale pour de nombreux EPS en USD/action. Pas de score sémantique
global revendiqué sans annotation exhaustive des faux positifs et manquants.

Revue assistant des textes locaux : 16 fourchettes annuelles d'EPS ajusté
retenues (quatre publications par société et année fiscale FY2023/FY2024),
retrouvées numériquement 16/16. Leurs douze différences successives nominales
se répartissent en trois hausses, quatre baisses de milieu et cinq inchangées.
Une fourchette resserrée est distinguée d'un effondrement des deux bornes.
Ce décompte n'est ni une accuracy directionnelle, ni douze événements de
trading validés ; définitions et disponibilité restent non approuvées.

Exemples revus : ABM FY2024 passe de 3,20–3,40 à 3,30–3,45, puis 3,40–3,50,
puis 3,48–3,55 USD/action. TTC FY2023 passe de 4,70–4,90 à la même fourchette,
puis 4,70–4,80, puis 4,05–4,10. TTC FY2024 conserve 4,25–4,35 jusqu'en juin,
puis abaisse à 4,15–4,20 en septembre. ABM FY2023 conserve 3,40–3,60 jusqu'en
juin, puis resserre à 3,40–3,50. Ne pas fusionner ces EPS ajustés avec les
hausses GAAP liées aux éléments de comparabilité.

Artefacts : `artifacts/research/guidance_structured/e21b-2023-2024-v1/`
contient `report.json`, `review_queue.json` et `manual_reference.json`.
La référence documente accession, période et fourchette, avec exclusions.
Une même valeur apparaît parfois plusieurs fois dans titre/corps ; ces
occurrences ne sont pas des événements supplémentaires. Les communiqués de
décembre 2024 annonçant FY2025 ne sont jamais joints aux prévisions FY2024.

Statut : collecte et smoke numérique réussis, **résolution sémantique
automatique encore insuffisante / DATA_NOT_READY**. La revue est celle de
l'assistant, pas une annotation humaine indépendante. Les nouvelles dates
restent désormais des données explorées ; ne pas les réutiliser comme
confirmation intacte après adaptation du parseur. Aucun rendement consulté.
Prochaine action : extraction ciblée par phrase/section et en-tête de tableau,
distinction prévision ancienne/nouvelle/réalisée, puis corpus de nouveaux
émetteurs réservé à validation avant lecture.

Les suggestions regex reconnaissent EPS, revenus/ventes, billings, résultat
opérationnel et EBITDA, quelques années fiscales et dates explicites, et
une échelle million/milliard écrite près de la fourchette. Elles ne résolvent
pas automatiquement les en-têtes de tableaux ni une période fiscale ambiguë.
Les contextes contenant plusieurs mesures ne produisent pas de mesure unique.
Les hypothèses de change/tarifs et changements de définition nécessitent revue.

Chaque candidat possède six champs `validated`, initialement nuls :

- `metric` : mesure canonique ; ne pas confondre billings et revenus.
- `period` : période exacte, idéalement dates de début/fin fiscales.
- `unit` : USD/action, USD million, etc. Aucune conversion implicite.
- `basis` : GAAP ou définition non-GAAP déterminée.
- `definition_id` : définition économique versionnée, commune aux deux sources.
- `scope` : groupe ou segment identifié.

Pour approuver : renseigner ces champs, `reviewer`, `review_status=APPROVED`,
`validated_statement_role=NEW_FORECAST` ou `PRIOR_FORECAST`,
`assumptions_reviewed=true` et `definition_change=false` après vérification.
Ne pas approuver un résultat réalisé, une autre période, un segment distinct,
une unité incertaine ou une mesure redéfinie sans retraitement.

La source, les bornes numériques et le contexte sont immuables lors de
l'import d'une revue : le service vérifie leur correspondance aux candidats
recalculés. Une erreur numérique doit être corrigée dans l'extracteur, pas
masquée dans le fichier de revue.

## Contrat temporel et rapprochement

`historical_available_at` requiert un timestamp avec fuseau et une
`availability_evidence` documentant la source. La collecte actuelle n'est
jamais assimilée à une publication historique. Pour cette branche SEC,
la disponibilité retenue doit être au moins l'acceptation SEC : c'est une
borne conservatrice, pas une estimation de la première diffusion presse.
Une source publiée antérieurement doit relever d'un contrat distinct.

`compare` s'abstient si les champs manquent/diffèrent, le CIK diffère, la
chronologie est invalide, les bornes sont non finies/inversées ou les bases
et hypothèses ne sont pas résolues. Sinon, il calcule uniquement la différence
des milieux et HIGHER/LOWER/UNCHANGED. `stock_direction` reste nul.

`pair_reviewed` groupe par CIK et identité sémantique, puis compare les
publications adjacentes disponibles. Ce n'est que le prédécesseur **observé**.
Un dépôt manquant peut cacher une révision intermédiaire ; toutes ces paires
conservent `ml_eligible=false` tant que l'exhaustivité n'est pas validée.
Deux annexes à la même heure ne deviennent pas deux révisions chronologiques.

## Exécution et revue

```powershell
python -m service.forward_pit.guidance_structured --manifest artifacts/research/guidance_historical_backfill/e21-20260914-smoke2/collection_report.json --manifest artifacts/research/guidance_historical_backfill/e21-20260914-retry-json/collection_report.json
```

Copier la queue dans un fichier de revue séparé, annoter sans modifier les
champs immuables, puis ajouter `--reviewed chemin/queue_reviewed.json` à la
même commande. Un nouveau répertoire de sortie est créé. Les paires et
exclusions apparaissent dans `reviewed_pairs.json`. Aucune pair du smoke
n'est autorisée artificiellement faute de preuve de disponibilité historique.

## Reste à faire avant DATA_READY

### Collecte historique bornée lancée le 14 septembre 2026

Le backfill lit désormais les pages anciennes `filings.files` dont les dates
recouvrent la fenêtre, avec noms SEC contrôlés, limite de pages configurable
et colonnes fusionnées en conservant leur alignement. L'inventaire indique
les pages manquantes, le nombre de dépôts éligibles et les éventuelles
troncatures. Les documents restent limités à deux annexes et 2 Mo chacun :
un inventaire de dépôts complet ne garantit pas un corpus d'annexes complet.

Run : ABM et TTC, 2022-10-01 à 2024-12-31 ; plafond 24 dépôts par société,
deux pages historiques par société. Les dates n'ont pas été utilisées dans
le smoke 2025, mais les émetteurs sont connus ; ne pas revendiquer une
validation indépendante par émetteur. La période 2022 sert à rechercher
des prédécesseurs pour la revue 2023–2024.

Résultats : `artifacts/research/guidance_historical_backfill/e21b-historical-2023-2024-v1/`.
Logs : `log/batch/e21b-historical-2023-2024-v1/stdout.log` et `stderr.log`.
`progress.json` est actualisé avant chaque requête puis clôturé à la fin ;
`collection_report.json` apparaît en fin de collecte, y compris en cas d'erreur
gérée. Ne pas confondre fichier présent et collecte réussie : lire `status`,
`errors` et les compteurs de couverture. Aucun passage quotidien modifié.

```powershell
Get-Content F:/projets/log/batch/e21b-historical-2023-2024-v1/stdout.log -Tail 10 -Wait
Test-Path F:/projets/artifacts/research/guidance_historical_backfill/e21b-historical-2023-2024-v1/collection_report.json
```

80 tests E21 et collecteur ciblés passent après l'extension. À la fin,
contrôler les téléchargements manquants avant extraction et annotation.

1. Collecter un corpus indépendant multi-années : le backfill actuel ne lit
   que submissions.recent et ne garantit pas les prédécesseurs. Il faut les
   pages anciennes, une liste de dépôts attendus et un inventaire des manquants.
2. Séparer documents de développement et de validation par accession/hash,
   avec émetteurs et années non utilisés pour développer les règles.
3. Annoter tous les candidats d'un sous-échantillon, y compris réalisés,
   périodes trimestrielles et faux positifs ; rechercher aussi les prévisions
   que le parseur a manquées pour mesurer le rappel.
4. Mesurer fidélité des bornes, mesure, période, unité et base, taux d'abstention,
   faux positifs et couverture des prédécesseurs. Fixer les critères avant
   consultation des rendements. Les 85 candidats ne constituent pas 85 révisions.
5. Valider preuves temporelles et sécurité master historique ; aucun test ML
   avant ces contrôles. Puis protocole OOF LONG/SHORT H5/H10/H20 net de coûts.

**E21-B est en cours : socle et smoke livrés, extraction sémantique automatique
complète et validation indépendante non acquises.** Ne pas transformer ce
statut de données insuffisantes en NO_GO directionnel.

Voir [smoke historique et annotations](guidance_historical_smoke_e21.md) et
[audit initial de disponibilité](guidance_pit_availability_e21a.md).

Suite : [classification des rôles et validation A/ADBE](guidance_role_validation_e21b.md).
