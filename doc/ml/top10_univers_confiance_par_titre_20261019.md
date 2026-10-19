# TOP10 Oracle : peut-on isoler des titres plus faciles à trader dans un sens ?

> Ce document concerne uniquement le TOP10. L'extension demandée ensuite aux
> **1 790 titres sans restriction Oracle** est terminée et documentée dans
> [le test de l'univers tradable complet](univers_tradable_complet_confiance_directionnelle_20261019.md).

## Conclusion

**TERMINÉ / EXPLORATOIRE / PAS D'UNIVERS PROMU.** La règle causale de confiance
par titre retient quelques affinités historiques LONG/SHORT, mais ne démontre
pas un sous-univers directionnel fiable et suffisamment diversifié.

Les 214 occasions retenues se réduisent à **vingt fenêtres sans chevauchement
par titre** : quinze en 2025 et cinq en 2026. Le résultat 2025 se dégrade dans
ce contrôle ; 2026 ne contient que MXL LONG. Aucun fichier d'univers, modèle,
batch ou paramètre de production n'est changé.

Il s'agit de sélectionner un **sens historiquement favorable pour un titre**,
pas de mesurer l'exactitude de GPT, du consensus ou d'un nouveau prédicteur.
Un titre structurellement haussier peut favoriser une règle toujours LONG
sans qu'un modèle sache anticiper ses retournements.

## Source et chronologie

Source scellée : `artifacts/research/us_top10_liquidity_gap/20261019-v2/`.
Les observations conservent les dix rangs originaux des modèles annuels :

| Année | Modèle Oracle parcours |
|---|---|
| 2024 | `model-factory-20261014113215-437ed1` |
| 2025 | `model-factory-20261014113226-102eca` |
| 2026 | `model-factory-20261014113232-bc35a7` |

- **2024 sert d'historique initial**, pas de résultat du filtre appris sur lui-même.
- Sélection mensuelle au premier jour de décision de chaque mois en 2025–2026.
- Historique roulant de 504 séances ; seuls les résultats de fenêtres de vingt
  séances **entièrement terminées avant la date de sélection** sont connus.
- Même si un stop est touché tôt, on attend la maturité complète pour utiliser
  l'observation. Pas de fuite des résultats de fin de mois dans sa sélection.
- Les vingt séances incluent l'entrée J+1. Les observations 2026 sont matures
  jusqu'au **1er septembre**, avec limite d'observation au 30 septembre.
- Années déjà explorées auparavant : validation chronologique, **pas nouvelle
  période indépendante encore jamais observée**.

## Règles figées avant le premier calcul

Chaque titre et chaque sens LONG/SHORT sont évalués séparément :

1. Au moins **huit fenêtres historiques sans chevauchement** pour le même
   titre/sens. Les apparitions successives dans le TOP10 ne sont pas comptées
   comme autant d'épisodes indépendants. On prend la première occasion
   chronologique puis attend la fin de ses vingt séances, sans choisir selon
   son résultat.
2. Borne inférieure Wilson à 90 % du taux TP20 avant SL7 supérieure au taux
   historique global du même sens.
3. Résultat moyen après coûts hypothétiques positif et supérieur à la moyenne
   historique globale du même sens.
4. Les deux moitiés chronologiques des épisodes doivent chacune avoir un
   résultat moyen positif et un taux de TP supérieur à la référence historique.

Huit épisodes et l'intervalle Wilson constituent un **filtre exploratoire**,
pas une preuve statistique de fiabilité : pas de correction des sélections
multiples par titre, ni indépendance garantie entre émetteurs ou régimes.

Règle d'utilisation :

- Si le titre repasse dans le TOP10 du mois suivant, appliquer le sens qualifié.
- Titres inconnus ou insuffisamment documentés : abstention, pas classement
  automatique parmi les « mauvais titres ».
- Si les deux sens passent : abstention pour le bras de sélection directionnelle.
- Aucun remplacement hors du TOP10 original.
- Une qualification mensuelle n'implique pas que le titre apparaîtra de nouveau
  dans le TOP10 : NBR qualifié SHORT en 2026 n'y génère aucune occasion retenue.

Le calcul ne recherche aucun seuil optimal et n'entraîne aucun modèle.
Les règles de sélection sont identiques dans les calculs v1 et v2 ; v2 ajoute
uniquement les contrôles sans chevauchement et par semestre.

## Protections et coûts

TP20/SL7 inchangés, entrée à l'ouverture J+1, vingt séances incluant l'entrée,
expiration à la clôture de la vingtième, sans trailing. Stop d'abord sur une
collision OHLC non résolue ; gap au-delà du stop exécuté à l'ouverture.

Hypothèses de friction : commission 1 bp, demi-spread 5 bp, slippage 2 bp
**par jambe**, soit environ 16 bp aller-retour ; les frais de sortie dépendent
du prix de sortie. Emprunt SHORT hypothétique 0,3 %/an sur le montant d'entrée
et `(séance de sortie − 1)/252`. Pas de certification des locates, rappels,
indemnisations de dividendes ou conditions réelles de courtier.

Ce sont des résultats par occasion à montant d'entrée normalisé, **pas une
performance de portefeuille** : aucun capital final, rendement annuel composé,
levier, contrainte de capital disponible ou DD de portefeuille n'est calculé.

## Résultats : toutes les occasions répétées

| Année | Filtre | Occasions | Titres | TP avant SL | Moyenne nette par occasion |
|---|---|---:|---:|---:|---:|
| 2025 | TOP10 tous LONG, référence | 2 500 | 87 | 29,84 % | +1,69 % |
| 2025 | Titres qualifiés LONG | 47 | 2 | 40,43 % | +3,25 % |
| 2025 | Titres qualifiés SHORT | 111 | 2 | 34,23 % | +2,30 % |
| 2025 | Sens choisi selon historique | 158 | 4 | 36,08 % | +2,59 % |
| 2026 | TOP10 tous LONG, référence | 1 658 | 75 | 27,08 % | +0,49 % |
| 2026 | Titres qualifiés LONG | 56 | 1 | 35,71 % | +2,40 % |
| 2026 | Titres qualifiés SHORT | 0 | 0 | — | — |

Ces colonnes ne doivent pas être comparées comme des portefeuilles de même
exposition ou de mêmes dates. Le détail comporte aussi les références tous
SHORT et les différences appariées par date, avec blocs de vingt séances.

La sélection retient seulement **6,32 % des occasions en 2025 et 3,38 % en
2026** ; respectivement 132/250 et 111/167 séances sans candidat. En 2025,
les intervalles appariés du bras combiné incluent zéro, y compris face aux
mêmes symboles pris aveuglément LONG ou SHORT.

### Titres effectivement sélectionnés, pas une liste recommandée

- 2025 LONG : **MXL 30 occasions, APP 17**.
- 2025 SHORT : **TXG 100 occasions, GPRE 11**.
- 2026 LONG : **MXL 56 occasions**, aucun autre titre/sens.

Les états qualifiés incluent aussi NBR SHORT, mais aucune de ses apparitions
testées ne correspond à une qualification active dans le TOP10.
La très grande majorité des états titre/mois manquent des huit fenêtres
historiques : on ne peut pas conclure que les autres titres sont imprévisibles.

## Contrôle décisif : ne pas réacheter quotidiennement le même mouvement

On retire les fenêtres qui se chevauchent pour un titre/sens, toujours dans
l'ordre chronologique et sans choisir les gagnantes. Ce n'est pas encore une
indépendance statistique totale entre émetteurs ou vis-à-vis du marché.

| Année | Filtre | Fenêtres non chevauchantes | TP avant SL | Moyenne nette par fenêtre |
|---|---|---:|---:|---:|
| 2025 | Titres qualifiés LONG | 5 | 2/5 = 40 % | +3,64 % |
| 2025 | Titres qualifiés SHORT | 10 | 1/10 = 10 % | −6,06 % |
| 2025 | Sens choisi, combiné | 15 | 3/15 = 20 % | −2,82 % |
| 2026 | Sens choisi, MXL LONG seulement | 5 | 3/5 = 60 % | +8,78 % |

Le chiffre 2026 repose sur cinq fenêtres d'un seul titre, pas sur une preuve
de généralisation. La différence 2025 rappelle combien les occasions
chevauchantes d'un même mouvement peuvent gonfler une impression de réussite.
La phase de départ des fenêtres est fixée par la première occasion ; aucune
recherche du meilleur décalage pour améliorer ces résultats.

Autre contrôle temporel : au second semestre 2025, les dix-sept occasions
encore sélectionnées sont toutes SHORT, sans aucun TP atteint, avec moyenne
nette **−7,14 % par occasion**. La faveur historique ne persiste donc pas
uniformément dans les périodes suivantes.

## Comparaison aux règles naïves

Pour les mêmes 158 couples date/titre sélectionnés en 2025 :

- sens choisi : moyenne nette +2,59 % ;
- toujours LONG : +1,39 % ;
- toujours SHORT : −0,38 %.

Mais les intervalles appariés restent trop larges pour promouvoir cet avantage.
En 2026 la sélection est **exactement MXL toujours LONG** : aucun supplément
de prévisibilité directionnelle n'est démontré au-delà de cette préférence.

## Décision et limites

**Ne pas créer un univers définitif « titres faciles » à partir de ce test.**
Quelques affinités existent dans l'échantillon, mais elles sont trop concentrées,
peu documentées et sensibles au chevauchement et à la période suivante.

Ce résultat ne prouve ni que tous les titres sont également prévisibles,
ni qu'aucun autre filtre ne pourrait fonctionner. Il ne valide pas non plus
un modèle individuel par symbole, non entraîné ici. Les futurs tests devraient
garder une période prospective réellement nouvelle et comptabiliser
explicitement la dépendance/concentration, plutôt que modifier les seuils
jusqu'à faire réussir 2025/2026.

Les réserves du diagnostic source restent applicables : univers courant
survivant, cours ajustés rétrospectivement, identité/prix non indépendamment
certifiés pour chaque gap, exécution OHLC approximative et hypothèses de coûts.
Les modèles annuels changent également : la fiabilité passée d'un titre sous
l'ancien modèle ne garantit pas sa fiabilité sous le nouveau.

## Livrables et reproduction

- Script : `scripts/research/us_top10_symbol_reliability.py`.
- Tests propres : dix ; avec les treize tests de parcours : **23 tests passent**.
- Résultat final : `artifacts/research/us_top10_symbol_reliability/20261019-v2/`.
- `protocol.json` : règles figées avant les calculs et empreintes des sources.
- `monthly-memberships.csv/.parquet` : statut par titre/sens/mois et motifs.
- `evaluations.parquet`, `selected-occasions.csv` : sélections et résultats.
- `nonoverlapping-test-summary.csv`, `semester-summary.csv` : contrôles.
- `report.json` : références naïves, comparaisons appariées, réserves.

```powershell
python -u -m scripts.research.us_top10_symbol_reliability --phase prepare --output artifacts/research/us_top10_symbol_reliability/NOUVEAU_DOSSIER
python -u -m scripts.research.us_top10_symbol_reliability --phase run --output artifacts/research/us_top10_symbol_reliability/NOUVEAU_DOSSIER
```

Les phases exigent des archives intactes et un dossier de résultat neuf.
**Aucun SQL, fournisseur, GPT/DeepSeek, entraînement, ordre ou changement
de production**. Le registre des expériences est mis à jour.
