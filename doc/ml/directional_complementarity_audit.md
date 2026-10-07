# Audit de complementarite des signaux directionnels faibles

## Question et portee

Peut-on combiner des scores faibles qui ne sont pas exploitables seuls ? Cet
audit recherche de l'information differente entre familles, avant d'autoriser
un modele de combinaison. Il ne construit pas un portefeuille, ne recherche
pas de poids optimaux et n'entraine aucun modele directionnel supervise.

Il complete le [consensus historique](oof_consensus_audit.md), deja NO_GO.
Le [Meta Oracle A/B](meta_oracle_execution.md) visait l'amplitude : ses scores
ne sont pas assimiles a des predictions du sens LONG/SHORT.

## Inventaire disponible et exclusions

L'ancien dossier `oof-consensus-20260906-0802c8` et les anciennes familles
references dans `config/research/oof_consensus_0802c8.json` ne sont plus presents
dans les artefacts locaux. Le nouveau diagnostic ne pretend donc pas couvrir
toutes les experiences historiques.

| Source | Traitement | Motif |
| --- | --- | --- |
| Dual-threshold `shared-dual-threshold-20260909124129-323684` | inclus H3/H10/H20 | scores OOF evenementiels, meme Oracle et cibles compatibles |
| Ranker `conditional-oracle-ranker-20260909124132-323684` | inclus H3/H10/H20 | meme population ; score oriente vers les rendements croissants |
| D1/D10 `shared-direction-20260909075129-323684` | exclu du panel principal | seulement 179 605 extremes realises, contre 402 017 evenements des deux autres familles ; intersection conditionnee au futur |
| Ancien ranker `0e94ac` | exclu | autre univers Oracle, ne pas melanger les contrats |
| Daily regime `shared-daily-regime-20260909140214-323684` | hors audit cross-sectionnel | score identique pour tous les titres d'une date ; devrait faire l'objet d'un audit temporel distinct |
| E20 price/volume d'ouverture | exclu de la decision a J | observation J+1 apres ouverture et autre batch Oracle ; utilisable seulement dans une experience a instant de decision commun |
| Anciennes familles signed-return, path-aware, first-touch et donnees Eroya | non alignees ici | anciens artefacts absents ou batch/cible differents ; pas de reconstruction de predictions manquantes |
| Alphas fondamentaux H120/H180, momentum long | exclus H3/H10/H20 | horizon et population differents ; performance de facteur != prediction D1/D10 conditionnelle Oracle |

La sauvegarde ML disponible ne suffit pas a prouver que les anciens fichiers
sont recuperables : aucune restauration massive de sauvegarde n'est effectuee.

## Contrat d'alignement et controles

Oracle : `model-factory-20260909051302-323684`, H20. Pour chaque horizon cible,
la cle est `date + symbol`. Les scores sont lus par le chargeur existant du
consensus, qui normalise les cles et refuse les doublons. L'intersection est
stricte, sans imputation d'un score manquant. Les rendements futurs doivent
coincider a tolerance numerique serree entre sources. Les valeurs infinies sont
refusees. Chaque evenement doit appartenir au `_oracle_oof_gate.parquet`
canonique, avec `directional_oracle_oof_available` et `directional_oracle_eligible` vrais.

Apres intersection, les rangs sont recalcules quotidiennement sur la meme
population, pour ne pas confondre difference de couverture et difference de
classement. Les familles ne sont ni inversees apres lecture des resultats ni
selectionnees pour maximiser le score. Les empreintes SHA256 des sources et du
gate sont conservees. Les sorties OOF ne contiennent pas toutes les bornes de
train par evenement : la provenance repose aussi sur le contrat des producteurs
amont, et ne constitue pas un nouvel audit exhaustif de fuite de ces producteurs.

## Mesures de complementarite

1. IC quotidien du score avec le rang du rendement realise, puis moyenne
   equiponderee par date : pouvoir de classement individuel.
2. Correlation quotidienne des rangs de deux familles : redondance des scores.
3. Erreur de rang `rang_score - rang_realise`, puis correlation des erreurs.
   Cette correlation contient un terme cible commun ; elle ne prouve pas a
   elle seule que les modeles sont inutiles ou ont les memes erreurs de trading.
4. Erreurs conjointes et corrections mutuelles pour le classement relatif
   haut/bas autour de 0,5, en excluant les egalites. Ce sont des erreurs de
   classement relatif, PAS une precision LONG/SHORT absolue : la moitie basse
   peut monter dans un marche haussier, et les rangs ne sont pas des probabilites.
5. Information residuelle : projeter le score d'une famille sur les autres
   scores, et mesurer l'IC de ce qui ne peut pas etre explique lineairement.

La projection est ajustee uniquement sur les dates passees, avec minimum 252
dates, embargo 20 dates et blocs de test 126 dates. Elle n'utilise jamais les
rendements futurs pour ajuster ses coefficients ; les poids assurent une date
une voix, et ne sont pas des poids de combinaison supervises. Les residus
numeriques inferieurs a 1e-12 sont ramenes a zero pour eviter de classer du bruit
d'arrondi comme un signal. L'IC du score original est aussi publie sur exactement
les memes dates que l'IC residuel. Ce delta ne represente PAS la performance d'un
ensemble : le residuel n'est pas additionne a un expert de reference.

Les IC95 utilisent 2 000 bootstrap de blocs contigus de 21 dates, y compris pour
H3/H10 car les evenements sont selectionnes par Oracle H20. Le bootstrap n'est
pas realise ligne par ligne. Les intervalles sont ponctuels, sans correction
des comparaisons multiples : aucun resultat marginal n'autorise une promotion.

## Resultat canonique du 14 septembre 2026

Artefact : `artifacts/research/directional_complementarity/audit-20260914-v2`.
Par horizon : 402 017 evenements, 1 134 dates, 1 287 symboles, du 5 janvier 2021
au 11 juillet 2025. Ce ne sont pas 1,2 million d'evenements independants : les
horizons reutilisent les memes cles. 2025H2 est partiel.

| Horizon | Correlation scores | Correlation erreurs de rang | IC residuel dual-threshold | IC residuel ranker |
| --- | ---: | ---: | ---: | ---: |
| H3 | 0,218 | 0,605 | +0,0061 | +0,0160 |
| H10 | 0,198 | 0,597 | +0,0082 | +0,0074 |
| H20 | 0,103 | 0,563 | -0,0015 | -0,00001 |

Toutes les bornes basses des IC95 residuels sont negatives. Pour le ranker H3,
IC95 [-0,0008 ; +0,0295], avec 75 % des semestres positifs : signal faible
descriptif, pas demonstration. Son IC original sur les memes dates vaut
+0,0168 ; retirer la partie expliquee par dual-threshold ne l'ameliore pas.
A H20 les semestres residuels ne sont positifs que dans 50 % des cas. Aucun
des six diagnostics ne donne `DESCRIPTIVE_CANDIDATE` dans le rapport canonique.

Le run `audit-20260914-v1` est conserve mais SUPPLANTE : il utilisait des blocs
H+1 a H3/H10 et des dates de projection differentes. Son petit signal H3 apparent
ne doit pas etre cite comme une validation apres prise en compte d'Oracle H20.

## Conclusion et actions possibles

Verdict du rapport : `HISTORICAL_DIAGNOSTIC_ONLY`, sans promotion. Pas de
complementarite directionnelle demontree pour les deux familles disponibles,
surtout a H20. Une faible correlation de scores ne suffit donc pas a justifier
un ensemble massif. Ce resultat ne prouve pas qu'une interaction non lineaire
ou qu'une famille absente ne puisse apporter de l'information : elles ne sont
pas testees ici. Aucun rendement net ou gain portefeuille n'est etabli.

Avant un stacking supervise, il faudrait recuperer des OOF comparables de
familles nouvelles, aligner leurs instants de decision et documenter leurs
cibles et les dates de fin de train. Un eventuel stacking devrait utiliser des
OOF imbriques, une combinaison fortement regularisee, un test identique contre
le meilleur composant, puis un replay economique et une confirmation vraiment
non utilisee. Les anciennes periodes ayant deja servi a de nombreuses recherches,
elles restent exploratoires et ne redeviennent pas un holdout vierge.

## Reproduction et sorties

```powershell
python -u -m modelFactory.directional_complementarity_audit
```

La commande cree un nouveau repertoire horodate et refuse d'ecraser un
repertoire existant. `--output` permet de choisir un nouveau chemin.
Sorties : `report.json` (inventaire, provenance, limites, fenetres, semestres),
`pair_metrics.csv` et `incremental_metrics.csv`. Aucune table, cascade, batch
actif ou artefact de serving n'est modifie. Neuf tests cibles audit/consensus
passent, dont les controles de disponibilite temporelle de la projection,
independance aux cibles futures, absence de classement du bruit numerique et
refus de rendements incompatibles.
