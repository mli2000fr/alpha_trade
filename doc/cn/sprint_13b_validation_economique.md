# Sprint 13-B — Replay économique OOS CN_A (recherche)

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## État et décision actuelle

Le lanceur est implémenté et testé. Un **premier passage diagnostique**
sur 2022H1 et seed 0 a été exécuté ; la campagne de couverture des huit
semestres est lancée. **Aucun GO économique ou live n'est prononcé.**
Les prédictions Walk-Forward 2022–2025 ont déjà servi aux Sprints 10–11 :
ce replay n'est donc pas un holdout indépendant et ne doit pas être
optimisé sur ses rendements.

Le [préflight 13-A](sprint_13a_preflight_economique.md) et le
[rapprochement 13-A2](sprint_13a2_normalisation_actions.md) sont requis.
La [remédiation 13-B2](sprint_13b2_remediation_positions.md) documente
les positions bloquées constatées après les 40 sous-runs diagnostiques.
Les 14 630 distributions vérifiées sont chargées depuis l'artefact A2
hashé, sans mise à jour des tables canoniques. Les 1 695 événements
incertains restent non résolus. Le gate pré-enregistré de 5 % sur les
fenêtres **candidates** est passé ; cela ne garantit pas qu'une position
réellement détenue ne croise jamais un événement incertain.

## Contrat d'exécution

Le [protocole gelé](../../config/research_cn/sprint13a_economic_preflight.yaml)
impose le signal après la clôture J, l'ordre d'achat seulement à
l'ouverture J+1 et son annulation en cas de non-fill cette séance.
Chaque fill est hypothétique, fondé sur une barre quotidienne : aucun
fill de courtier n'est prétendu. Au plus huit positions LONG, ticket
10 000 CNY, capital initial 100 000 CNY, sans pyramiding ni nouveau
signal sur une position ouverte. La sortie H20 est **programmée depuis
le fill d'achat**, à la clôture de la vingtième séance complète,
pour une première tentative à l'ouverture suivante. Une vente bloquée
par suspension ou limite est reportée, jamais exécutée fictivement.

Le replay [CN](../../service/market/cn_portfolio_replay.py) applique
les lots/tick, T+1, cash disponible et cash retirable, règles de board,
statut et limites de prix, contraintes de participation au volume et
coûts de recherche. Les dividendes cash sont acquis seulement si le
titre est détenu avant l'ex-date, comptés comme créance puis crédités
au paiement. Une distribution d'actions modifie les quantités ; un
résidu fractionnaire sans traitement vérifié reste bloquant. Les
dividendes sont **avant impôt** : les taxes propres à la durée de
détention de l'investisseur ne sont pas connues. Les résultats sont
donc, au mieux, une borne de recherche favorable, pas un PnL net
exécutable.

Pour les quatre politiques Oracle gelées, le pool et les masques
viennent des mêmes Parquets OOS H20 que 13-A, lus avec les sept seules
colonnes de sélection sans label ni rendement futur. Le comparateur
momentum choisit le haut 20 % du `relative_return_20` sur le **même
univers complet**, sans gate Oracle, et passe par le même replay.
Le CSI 300 est affiché comme indice prix brut contextuel ; ce n'est
pas un ETF négociable et ses frais ne sont pas simulés. Pour éviter
que l'ordre arbitraire des candidats Oracle détermine la conclusion,
les cinq seeds de permutation hash `0–4` figées au protocole sont
appliquées à chaque politique ; les politiques veto restent de simples
veto, sans classement supplémentaire caché.

Les scénarios sont `base` et `conservative`, chacun avec les profils
de coûts `cn_a_research` et `cn_a_research_stress`. Les fenêtres sont
rejouées par semestre avec cash réinitialisé ; les dernières dates
sans fenêtre J+21 dans le semestre ne reçoivent pas de nouvelle entrée.
On ne présente pas cette discontinuité comme une série live continue.
Chaque run conserve journal compressé, courbe quotidienne, nombres de
non-fills et frais. L'agrégateur refuse de publier une moyenne de
rendement si un run du groupe est invalide.

## Premier smoke 2022H1 — diagnostic, pas classement

Sur la seed 0, fill `base`, coût `cn_a_research`, Oracle pur a généré
87 804 signaux candidats mais seulement 37 achats et 35 ventes
hypothétiques ; 86 238 tentatives ont trouvé le portefeuille déjà à
capacité maximale. Deux **positions détenues** ont rencontré des
facteurs non résolus : `sz.003038` le 30/03/2022 (aucune ex-date
distribution correspondante) et `sz.300327` le 31/05/2022 (termes
déclarés incompatibles avec le saut de facteur). Le mark final indiqué
par le moteur n'est **pas un rendement interprétable** pour cette
variante ; les positions sont conservées en quarantaine, pas vendues
à un prix inventé.

Les deux politiques veto testées sur le même semestre ont également
rencontré deux positions non résolues. La politique LightGBM LONG top20
n'a pas eu de position non résolue dans ce smoke, mais son résultat sur
une seed et un semestre ne peut pas servir à choisir une stratégie.
Le CSI 300 brut a reculé de 9,54 % sur ce semestre ; cette donnée
contextuelle n'est pas directement comparable à un portefeuille avec
frais, cash et fills.

Le smoke a aussi révélé puis corrigé un défaut : une tentative d'achat
refusée sur un événement de facteur inconnu marquait auparavant le
portefeuille comme non résolu **sans détention**. Seules les positions
effectivement touchées invalident maintenant le mark ; un test de
régression le vérifie.

## Lancement et suivi

Le [lanceur](../../modelFactory/cn_economic_replay_13b.py) est en lecture
seule de `alpha_trade_cn` et ne publie aucun signal live. Une campagne
complète est coûteuse (8 semestres × 5 politiques × 5 seeds × 2 fills ×
2 coûts) ; elle ne doit pas être lancée avant de connaître la fréquence
des blocages. Le premier passage (30/40 sous-runs produits) s'est arrêté
en 2025H1 : `instrument_id=1236`, radié le 27/05/2025, avait son dernier
statut `SUSPENDED` et sa dernière barre le 26/05. La validation exigeait
à tort un statut sur la séance de radiation sans barre. Le chargeur
accepte désormais l'absence de statut **uniquement quand la barre manque
aussi** : aucun ordre ne peut alors être exécuté et toute position détenue
reçoit un mark `stale`/invalide. Une barre présente sans statut reste
bloquante. La base CN et les anciennes sorties n'ont pas été modifiées.
Les tests de non-régression couvrent les deux cas.

Le diagnostic relancé après ce correctif fixe une seule seed, le fill base
et le coût base sur les huit semestres :

```powershell
python -u -m modelFactory.cn_economic_replay_13b --seeds 0 --scenarios base --cost-profiles cn_a_research
Get-Content log/batch/cn-sprint13b-diagnostic-retry-20260926/stdout.log -Tail 20
Get-Content log/batch/cn-sprint13b-diagnostic-retry-20260926/stderr.log -Tail 20
```

Les runs complets ou partiels possèdent chacun un identifiant fondé
sur les hashes du protocole, des preuves et du code ; ils ne sont pas
mélangés. Une reprise ne réexécute pas un rapport individuel déjà
présent avec la même provenance. Aucun résultat ne change les seuils
gelés. Si des événements non résolus touchent beaucoup de positions,
la suite sera une normalisation **ciblée sur les fills réellement
touchés**, puis le même replay, sans exclusion a posteriori des titres
qui auraient perdu.
