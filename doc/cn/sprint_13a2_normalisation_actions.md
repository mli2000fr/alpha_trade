# Sprint 13-A2 — Normalisation ciblée des actions d'entreprise CN

## Objet et état

**Collecte et audit terminés le 26/09/2026.** Les 13 984 réponses
attendues sont en cache, les quatre journaux d'erreur sont vides, et
le [rapport final](../../artifacts/cn/corporate_actions/sprint13a2/report.json)
est complet. Sur 16 325 événements, **14 630** distributions sont
réconciliées et **1 695** restent `UNRESOLVED`. Le seuil de 5 % est
désormais respecté par les quatre politiques, mais **aucun GO économique
ou live** n'en découle : le replay ne comptabilise pas encore ces droits.

Le [préflight 13-A](sprint_13a_preflight_economique.md) a constaté
**16 325** changements de facteur BaoStock non classifiés en 2022–2025.
Entre **5,77 % et 6,17 %** des fenêtres de candidats H20 sont exposées,
au-dessus du seuil de **5 %** figé avant l'audit. A2 vérifie la nature
économique de chaque événement avec une source *distincte* du facteur.
Cela ne change ni les politiques ML, ni le gate, ni la base canonique,
ni la production.

La source choisie est `baostock.query_dividend_data(yearType=operate)`.
Le champ `dividOperateDate` est l'ex-date ; les champs d'annonce du plan,
record et paiement, cash avant impôt par action, actions gratuites et
conversion de réserve servent de preuve. Les données sont rapprochées
par symbole BaoStock et **ex-date exacte**. Le ratio du facteur doit
également correspondre au prix théorique ex-droit calculé à partir de la
clôture brute précédente :

```text
ratio attendu = clôture précédente × (1 + actions nouvelles par action)
                / (clôture précédente − cash par action avant impôt)
ratio observé = nouveau facteur / ancien facteur
erreur relative maximale = 0,1 %
```

Une ligne est `EVIDENCED_DISTRIBUTION` seulement si elle est unique à
l'ex-date, le symbole et les dates sont cohérents, ses termes sont
chiffrés et le facteur est réconcilié. Les cas sans concordance, à terme
manquant, rights issue, fusion, correction ou contradiction restent
`UNRESOLVED`. Une réserve BaoStock vide vaut zéro **uniquement** pour un
dividende cash explicite dont le texte ne mentionne ni actions gratuites
ni transfert ; autrement elle reste inconnue. Le texte du fournisseur
n'est jamais utilisé seul pour affirmer un split.

Les réponses et leur date de récupération sont conservées dans
`artifacts/cn/corporate_actions/sprint13a2/queries/`, une réponse par
symbole et année d'ex-date. Elles sont des **faits historiques récupérés
aujourd'hui**, non une preuve que notre système les connaissait à la
date d'annonce. Ce Sprint ne les utilise pas comme features de décision.
La base `alpha_trade_cn` n'est consultée qu'en lecture ; aucune ligne
`cn_corporate_actions` n'est réécrite. Le replay 12-B continue à traiter
ces lignes en `UNRESOLVED` tant qu'un ledger économique vérifié n'y est
pas raccordé.

## Lancement reprenable

Le [collecteur](../../modelFactory/cn_corporate_action_a2.py) recense
**13 984 couples symbole/année** pour les 16 325 événements. Un POC
borné de dix requêtes a obtenu 9 distributions réconciliées et 1
facteur discordant. Cet échantillon n'est **pas représentatif** et ne
permet aucun verdict sur le gate.

```powershell
# Un seul processus, reprend les caches déjà présents :
python -u -m modelFactory.cn_corporate_action_a2

# Ou quatre processus indépendants, chacun dans une console distincte :
python -u -m modelFactory.cn_corporate_action_a2 --shard-index 0 --shard-count 4
python -u -m modelFactory.cn_corporate_action_a2 --shard-index 1 --shard-count 4
python -u -m modelFactory.cn_corporate_action_a2 --shard-index 2 --shard-count 4
python -u -m modelFactory.cn_corporate_action_a2 --shard-index 3 --shard-count 4

# Après fin des quatre : synthèse et gate sans nouveau téléchargement :
python -u -m modelFactory.cn_corporate_action_a2 --finalize-only
```

Chaque réponse réussie est persistée atomiquement. Une erreur fournisseur
interrompt le seul processus concerné ; sa relance reprend au premier
couple non mis en cache. `--max-new-groups 10` limite un pilote. Le
fichier `progress-shard-i-of-4.json` est indicatif ; le nombre de fichiers
dans `queries/` mesure la progression globale. Ne pas lancer deux
processus avec **le même** index de shard en parallèle.

## Résultat du gate et limites

Le gate pré-enregistré est recalculé **seulement** si les 13 984
réponses sont disponibles. Elles le sont toutes. Le rapport applique
le **même seuil de 5 %** aux quatre politiques inchangées :

| Politique H20 | Fenêtres complètes | Croisant une action non résolue | Part |
| --- | ---: | ---: | ---: |
| Oracle TOP20 pur | 937 100 | 4 782 | **0,5103 %** |
| Réversion veto bas 20 % | 749 297 | 4 013 | **0,5356 %** |
| LightGBM veto bas 20 % | 749 297 | 3 835 | **0,5118 %** |
| LightGBM LONG haut 20 % | 187 803 | 1 214 | **0,6464 %** |

Les 1 695 événements non résolus se répartissent notamment entre
**1 122** facteurs incompatibles avec les termes déclarés, **349**
sans ex-date correspondante, **135** aux termes économiques invalides,
**70** au ratio de réserve inconnu et **19** ex-dates ambiguës. Ils ne
sont pas éliminés silencieusement du futur replay.

Les prédictions lues restent les mêmes Parquets Walk-Forward OOS déjà
inspectés, avec uniquement les colonnes de sélection sans label ni
rendement futur. Le passage sous le seuil autorise seulement la
préparation d'un replay de recherche **en quarantaine**, pas un GO
économique ou live. Les événements classés devront être appliqués au
cash/inventaire dans le replay avant de calculer un PnL crédible.

BaoStock peut manquer d'autres actions (notamment droits et corrections)
ou réviser ses données historiques. L'absence de ligne ou un cache vide
n'est pas preuve d'absence d'action. Les données manquantes restent
explicitement une limite de couverture ; la période 2022–2025 demeure
exploratoire, pas une confirmation indépendante de la stratégie.
