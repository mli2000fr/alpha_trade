# TOP10 prédit — allocation égalisée, 2023–2024

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Hypothèse et audit préalable

Suite autorisée le 7 octobre 2026. Garder la sélection et les sorties, modifier
uniquement la répartition des montants proposés. Aucun filtre directionnel.
La référence a un SL fixe 7 %, mais des tailles fondées sur ATR.

Audit des 318 positions de référence : montant initial 155,44 à 707,90 USD,
médiane 304,85 USD. Perte théorique au stop 10,88 à 49,55 USD, hors gaps/frais.
Les quartiles de montants croissants produisent respectivement 245,15 / 454,42 /
260,34 / 117,01 USD de PnL. Rendements moyens bruts : 2,10 / 2,39 / 1,07 / 0,59 %.
Ces quartiles mélangent dates, titres et niveaux d'equity : **pas une preuve
causale qu'il faut réduire les grandes positions**. Aucun seuil de quartile
n'est utilisé pour décider les ordres.

## Alternative unique figée

Pour chaque décision quotidienne et configuration risque déjà résolue :

1. Calculer les propositions natives ATR pour les prix des candidats TOP10 à J.
2. Conserver les rejets natifs ATR/prix/notional minimum ; ne pas les ressusciter.
3. Additionner les notionnels proposés positifs et diviser par leur nombre.
4. Proposer ce même montant pour chaque candidat initialement positif.
5. Appliquer ensuite les facteurs d'allocation, corrélations, contraintes de
   portefeuille/liquidité/secteur/budget et exécution natifs, sans les contourner.

Le total proposé est préservé **avant** les facteurs et contraintes, sous réserve
de l'arrondi des quantités. Cela n'implique ni égalité des poids exécutés ni
égalité de l'exposition finale. Les candidats déjà détenus ou écartés plus tard
participent à la normalisation initiale. On ne réalloue pas a posteriori pour
atteindre une exposition choisie à partir des rendements futurs.

Avec SL7 identique pour tous, égaliser les montants égalise également le risque
théorique initial avant contraintes ; pas besoin d'un troisième scénario
« risque égal » redondant. Les gaps et frais empêchent tout plafond garanti.

Référence inchangée : capital continu 4 000 USD, huit positions maximum, LONG,
TOP10 prédit, SL initial 7 % du fill réel, sans TP/trailing, sortie vingt séances
après la séance d'entrée, liquidation terminale fin 2024. Aucun veto J+5.

## Implémentation et garanties

Script `scripts/research/us_top10_equal_sizing.py`. Le runner de recherche
accepte une fabrique de session, avec la session native par défaut.
La session expérimentale remplace le builder uniquement pendant son appel
synchrone `decide`, dans un processus dédié séquentiel ; restauration même
en cas d'exception. Aucun fichier de risque/live ou configuration de production
n'est changé. Aucun SQL lu/écrit, aucun entraînement.

Les champs natifs `sizing_method` et de risque initial ATR restent des champs
legacy : **ne pas les interpréter comme preuve d'un sizing ATR dans l'arm
EQUAL_PROPOSALS**, ni comme perte au SL7. Le protocole nomme explicitement
l'alternative ; le SL effectif est porté par les protections archivées et
la perte théorique réelle se recalcule depuis fill × quantité × 7 %.

Deux runs depuis les mêmes archives : BASELINE, puis EQUAL_PROPOSALS. La courbe
quotidienne BASELINE doit correspondre exactement à la référence précédente,
sinon arrêt. Les configurations risque/marché et le hash des secteurs sont vérifiés.

## Lecture attendue et limites

Comparer rendement net, drawdown, Sharpe, exposition moyenne, concentration,
coûts et nombre de positions ; un gain dû à davantage d'exposition n'est pas
automatiquement une meilleure allocation. Aucune sélection de coefficient
ni optimisation de seuil. Les données 2023–2024 ont déjà été examinées : test
exploratoire, avec réserves OOF complètes, survivance, secteurs actuels NON-PIT,
macro non certifiée par vintage et prix non certifiés indépendamment.

## Lancement et suivi

```powershell
python -u -m scripts.research.us_top10_equal_sizing --output artifacts/research/us_concentrated_replay/top10-equal-sizing-2023-2024-20261007-v1
Get-Content F:\projets\artifacts\research\us_concentrated_replay\top10-equal-sizing-2023-2024-20261007-v1\progress.json
```

Les sous-dossiers donnent l'avancement par séance. `size-audit.json` archive
l'audit préalable ; `protocol.json` archive la règle et les hashes ; le rapport
final n'est produit qu'après les deux scénarios. Aucun paramètre ne sera ajusté
pendant le run. La stabilité sur d'autres périodes sera une étape séparée,
sans prétendre que 2025–2026 déjà exploré est un holdout intact.

## Résultats — 7 octobre 2026

Deux scénarios COMPLETED, parité journalière exacte de BASELINE confirmée.

| Mesure | Référence ATR | Propositions égalisées |
|---|---:|---:|
| Net 2023–2024 | +26,92 % | +21,69 % |
| Capital final | 5 076,91 USD | 4 867,56 USD |
| 2023 | +42,47 % | +46,32 % |
| 2024 | −10,92 % | −16,83 % |
| Drawdown maximal | −18,97 % | −19,19 % |
| Sharpe | 0,68 | 0,61 |
| Exposition brute moyenne / equity | 49,57 % | 42,67 % |
| Positions closes | 318 | 319 |
| Gagnantes | 33,65 % | 31,66 % |
| Profit factor | 1,21 | 1,18 |

L'égalisation perd 5,23 points de rendement cumulé, avec moins d'exposition
mais un drawdown légèrement plus profond. Elle gagne 3,84 points en 2023,
puis perd 5,92 points supplémentaires en 2024 ; elle n'améliore donc pas
la robustesse sur ces deux années. Aucune exposition future n'a été utilisée
pour remettre artificiellement les résultats à la même échelle.

Cinq meilleurs trades : 1 085,23 USD pour 867,56 USD nets dans l'alternative,
contre 1 095,03 USD pour 1 076,91 USD nets dans la référence. Concentration
toujours majeure. Réconciliation cash <3e-12 USD, zéro fill oublié et zéro
ordre rejeté pour budget incompatible au commit.

Verdict : **NO_GO pour promouvoir cette allocation égalisée**. Conserver
le sizing ATR comme référence de recherche ; pas d'optimisation maintenant
d'un mélange ATR/égalisation sur les pertes 2024. Ces résultats ne rejettent
pas toutes les méthodes de sizing, seulement cette alternative figée.

Attention télémétrie : le champ générique `sizing_unchanged: true` produit par
le runner commun reste legacy dans les rapports de ce run ; il est incorrect
pour EQUAL_PROPOSALS. L'arm, le protocole, le code spécialisé et les quantités
archivées font foi : le sizing expérimental a bien été modifié. Les courbes
et résultats ci-dessus ne reposent pas sur ce drapeau.
