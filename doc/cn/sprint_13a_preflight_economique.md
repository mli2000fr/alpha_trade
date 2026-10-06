# Sprint 13-A — Préflight économique CN_A (sans lecture des rendements)

## Décision

**Préflight terminé ; replay économique comparatif bloqué par les corporate
actions non classifiées.** Le protocole a été [figé avant l'audit](../../config/research_cn/sprint13a_economic_preflight.yaml),
puis les huit semestres H20 2022H1–2025H2 ont été relus dans les artefacts
de prédictions Walk-Forward. Le [rapport complet](../../artifacts/cn/economic/sprint13a/sprint13a-9e6ce73e55ea48f7/report.json)
donne les effectifs par semestre, politique et board, avec hashes des
sources. Le code de l'[audit](../../modelFactory/cn_economic_preflight.py)
ne charge que `market_code`, `session_date`, `instrument_id`, `board_code`,
`oracle_top20`, `baseline_score` et `rank_score` ; il ne lit ni D1/D10,
ni rendement futur, ni validité de label, ni éligibilité future.

Ce sont des **fenêtres de candidats**, pas des positions effectivement
prises. La période et les modèles ont déjà été inspectés aux Sprints
10–11 : « OOS » qualifie ici les prédictions par rapport à leurs folds
d'entraînement, **pas** une confirmation indépendante de la politique
choisie aujourd'hui. Aucun GO économique ou live n'est possible au
Sprint 13-A.

## Contrat gelé pour le futur replay

Le protocole H20 conserve quatre politiques connues : Oracle TOP20 pur ;
Oracle avec veto du bas 20 % par réversion ; Oracle avec veto du bas 20 %
par score LightGBM ; et Oracle avec sélection LONG du haut 20 % par
LightGBM. Le pool quotidien doit compter au moins 20 candidats. Les
comparaisons futures utiliseront 100 000 CNY de cash initial, des tickets
de 10 000 CNY, au plus 8 positions, LONG uniquement, sans pyramiding.
Pour Oracle seul, aucun score d'amplitude individuel n'est présent dans
l'artefact ranking : la priorité entre ses candidats sera une permutation
déterministe par hash, moyennée sur cinq seeds `0–4`. Cela évite de lui
injecter implicitement le score directionnel d'une politique concurrente.

Un signal est produit **après** la clôture J. Un achat n'est tenté qu'à
l'ouverture J+1 et est annulé s'il ne passe pas cette séance ; aucune
entrée retardée n'utilisera un signal périmé. La sortie est décidée après
20 séances complètes **depuis le fill hypothétique réel du replay**, puis
tentée à l'ouverture suivante. Si la sortie est bloquée, la position
reste détenue et l'ordre de sortie est reporté, sans liquidation fictive.
Il faudra donc compléter le replay 12-B avec une sortie liée à la date
du fill avant de lancer le protocole complet ; une vente programmée sur
la date du signal initial pourrait liquider une autre position et serait
incorrecte. Les comparateurs prévus sont CSI 300 buy-and-hold et
momentum top20 sur le même univers ; les coûts sont base/stress et les
fills base/conservateur. Aucun de ces choix ne sera retouché sur les
résultats 2022–2025.

## Audit de disponibilité des actions d'entreprise

La fenêtre de contrôle d'un candidat J est **J+1 à J+21 inclus** : une
entrée au prochain open, 20 séances complètes, puis une sortie au prochain
open. Si J+21 n'est pas présent dans le calendrier local, le candidat
est `censored_exit`, pas un gain/perte nul. Toute ligne actuelle de
`cn_corporate_actions` est `UNCLASSIFIED_FACTOR_EVENT` et le replay 12-B
la classe `UNRESOLVED` tant que split, dividende, droits, distribution
ou correction ne sont pas vérifiés. Une telle ligne sur la fenêtre
rend le candidat **exposé**, pas automatiquement perdant.

| Politique H20 | Candidats | Fenêtre complète | Avec action non classifiée | Part des fenêtres complètes |
| --- | ---: | ---: | ---: | ---: |
| Oracle TOP20 | 958 676 | 937 100 | 56 350 | **6,01 %** |
| Réversion veto bas 20 % | 766 547 | 749 297 | 46 222 | **6,17 %** |
| LightGBM veto bas 20 % | 766 547 | 749 297 | 44 255 | **5,91 %** |
| LightGBM LONG haut 20 % | 192 129 | 187 803 | 10 842 | **5,77 %** |

Pour Oracle pur, 2 713 candidats croisent une action **le jour même de
l'entrée théorique**, 20 croisent une date de radiation dans la fenêtre,
et 21 576 sont censurés par la fin de l'historique. La couverture de
fenêtre complète est **97,75 %** : elle dépasse le seuil fixé à 95 %.
En revanche, les 6,01 % d'exposition aux actions non classifiées
dépassent le seuil de **5 % fixé avant calcul**. Les trois autres
politiques le dépassent également. Le verdict automatique est donc
`BLOCKED_ACTION_NORMALIZATION`.

Dans `alpha_trade_cn`, la période 2022–2025 contient **16 325 lignes
de facteur non classifiées sur 4 347 instruments** (2022 : 3 385 ;
2023 : 3 705 ; 2024 : 4 580 ; 2025 : 4 655). L'exposition des candidats
est nettement saisonnière : environ 9–10 % pour Oracle en premier
semestre contre environ 2–4 % au second. Par board Oracle, les taux
sont CHINEXT **6,71 %**, STAR **6,53 %**, SH_MAIN **5,97 %** et SZ_MAIN
**4,71 %**. La présence d'un board sous 5 % ne justifie pas de changer
après coup l'univers ou le gate global.

## Interprétation et limites

- Un candidat exposé peut ne jamais être acheté, faute de cash, de lot,
  de fill ou de place dans le portefeuille. Le taux ci-dessus ne mesure
  donc **pas** la part des positions réellement contaminées.
- L'absence d'une ligne dans `cn_corporate_actions` ne prouve pas qu'il
  n'y a eu aucun dividende ou autre événement : la source courante
  enregistre les **changements de facteur détectés**, pas une base
  exhaustive de distributions vérifiées.
- Les actions sont lues comme faits historiques corrigés. Leur
  `available_at` n'est pas une feature de décision ici ; aucun événement
  futur n'est utilisé pour sélectionner un signal.
- Le protocole de sortie liée au fill et les benchmarks ne sont pas
  encore implémentés dans un run comparatif. Le rapport actuel ne
  contient **aucun PnL**, Sharpe ni drawdown.

## Prochaine intervention nécessaire

**Mise à jour 13-A2 (26/09/2026)** : la [normalisation ciblée](sprint_13a2_normalisation_actions.md)
a abaissé la part de fenêtres avec événement non résolu à 0,51–0,65 %
selon la politique, sous le gate pré-enregistré de 5 %. Le résultat
13-A ci-dessus demeure le constat initial ; aucun seuil n'a été changé.
Cela ne prouve pas encore que les droits sont correctement appliqués au
cash et à l'inventaire du replay.

Le Sprint 13-A2 a rapproché ex-date, termes cash/actions et facteur
avec une source de distributions distincte. Les cas sans preuve restent
`UNRESOLVED` ; le rapport conserve leur nombre et leur exposition.
La disponibilité historique des annonces n'est pas déduite de la date
à laquelle nous avons récupéré ces réponses.

Enfin, le replay devra lier chaque sortie à son fill d'entrée, puis
exécuter la comparaison 13-B selon les coûts et scénarios figés. Les
résultats 2022–2025 resteront exploratoires ; une confirmation
indépendante exigera une période CN ultérieure non utilisée pour les
choix de politiques.
