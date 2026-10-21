# TOP10 LONG — sortie figée pour départ raté à la première clôture

## Verdict

**TERMINÉ / RÈGLE NON RETENUE / AUCUNE PROMOTION.** La sortie anticipée réduit
certaines pertes mais abandonne davantage de gains : sur toutes les occasions
appariées, la moyenne baisse en2024,2025 et2026. Sans chevauchement, amélioration
en2024 seulement, dégradation2025 et effet quasi nul2026. Aucun seuil retouché
après les résultats, aucun modèle entraîné.

Cet essai suit un GO distinct après
[l'audit des états quotidiens](oracle_top10_suivi_quotidien_audit_20261019.md).
Il teste une **première sortie exécutable**, et non l'addition des avantages
des différents états d'une même position.

## Règle figée

- Même TOP10 Oracle H10 à J, mêmes quatre clôtures croissantes jusqu'à J+2,
  mêmes entrées LONG openJ+3 ; aucun remplacement ni nouveau signal d'achat.
- Référence **TP10/SL5**, sans trailing, dix séances entrée comprise, expiration
  closeJ+12. Protections et frictions supposées inchangées :8bps par jambe.
- Si la position est encore ouverte après la séance d'entrée, observer le
  plus haut de **cette seule séance** relativement au prix d'entrée.
- Si cette progression maximale est strictement inférieure à
  **2,202691127293545 %**, demander la sortie à l'open suivant, soit J+4.
  C'est la borne exacte du premier tertile pondéré appris sur2024 dans l'audit,
  pas une valeur arrondie utilisée différemment ou optimisée sur2026.
- Si la règle ne se déclenche pas, conserver la politique native ; **ne pas
  réessayer le signal les soirs suivants**.
- Un TP/SL consommé pendant la séance d'entrée reste consommé : pas de
  décision fictive au close. Au prochain open, les protections gap restent
  prioritaires sur la demande de sortie quotidienne.
- Contrôle de durée : sortir au prochain open après **toute** première clôture
  survivante, même si la progression a été bonne. Pas d'autre règle ni seuil.

Entrées, notionnels unitaires et coûts d'entrée identiques ; capital libéré
non réinvesti, pas de nouveau trade à la place de la position sortie. Les mêmes
708 occasions sont conservées dans tous les bras, y compris celles où aucune
décision quotidienne n'est possible. Tous les montants sont exprimés en
rendement du notionnel d'entrée, pas en PnL d'un portefeuille de4000USD.

## Résultats appariés après frictions supposées

2024 et2025 : dates de signal annuelles ; 2026 : jusqu'au1er septembre, comme
les études sources. **Moyennes par occasion, pas rendements annuels composés.**

| Signaux | Positions | Référence TP10/SL5 | Sortie départ raté | Écart | Gagnants référence → règle |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | 232 | +0,915 % | +0,747 % | −0,168 point | 43,10 →41,81 % |
| 2025 | 255 | −0,756 % | −0,982 % | −0,226 point | 32,16 →29,41 % |
| 2026 | 221 | −0,415 % | −0,470 % | −0,055 point | 32,13 →32,58 % |

Les intervalles descriptifs95 % par blocs d'entrée de vingt séances sur
l'écart moyen sont respectivement **[−0,673 ; +0,341]**,
**[−0,815 ; +0,376]**, **[−0,639 ; +0,653]** points. Pas de gain robuste
démontré. L'absence de significativité ne transforme pas les points estimés
négatifs en bénéfice.

### Pertes atténuées contre gains sacrifiés

| Signaux | Demandes de sortie | Sorties quotidiennes exécutées | Priorité protection au prochain open | Perdants de référence améliorés | Gagnants de référence amputés | Gagnants devenus perdants |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 105 | 101 | 4 | 63 | 37 | 16 |
| 2025 | 87 | 86 | 1 | 55 | 31 | 15 |
| 2026 | 40 | 36 | 4 | 23 | 13 | 9 |

Au total **141 pertes améliorées contre81 gains réduits**. Le nombre n'est
pas suffisant : la valeur des gains abandonnés dépasse celle des pertes
atténuées sur la moyenne globale. Un gagnant amputé peut rester gagnant ;
seuls40 deviennent perdants/non positifs, pas les81.

Gain moyen de la règle parmi **tous les perdants de référence** :
+1,718/+1,173/+0,783 points ; parmi **tous les gagnants de référence** :
−2,658/−3,178/−1,827 points. Chaque moyenne a son propre dénominateur, donc
ne pas les additionner sans les effectifs correspondants.

## Contrôle de durée et sans chevauchement

Sortir tous les survivants après la première clôture donne
**+0,033/−0,496/−0,710 %** par occasion en2024/2025/2026. Cela ne fournit pas
non plus une amélioration transversale. La règle MFE fait mieux que cette
sortie systématique en2024/2026 mais moins bien en2025 ; ni contrôle n'est
choisi a posteriori pour remplacer le protocole.

Le contrôle sans chevauchement conserve l'adhésion des positions de référence,
attendant la fin de leur fenêtre native de dix séances avant une autre entrée
du même titre. Il ne crée pas de réentrées supplémentaires grâce à une sortie
plus rapide et continue à travers les frontières annuelles.

| Signaux | Positions indépendantes | Référence | Départ raté | Écart |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 128 | +0,700 % | +1,288 % | +0,588 point |
| 2025 | 141 | −0,338 % | −0,514 % | −0,176 point |
| 2026 | 108 | −0,732 % | −0,719 % | +0,013 point |

L'avantage2024 est dans la période de découverte ; il n'est pas confirmé de
façon transversale. Écart2026 minuscule et intervalle **[−0,745 ; +0,882]** point.

## Pourquoi l'audit descriptif ne prédisait pas ce résultat

L'indice initial portait sur des **états de position pondérés**, parfois à
plusieurs dates d'un même trade, et son signal le plus stable concernait une
comparaison avec **trois séances supplémentaires**. Le présent essai ne prend
qu'une décision à la première clôture et la compare à toute la sortie native
restante. Les états futurs n'existent plus après une vraie sortie.

Un avantage descriptif moyen par état ne démontre donc pas une stratégie
exécutable. Cet essai était nécessaire pour mesurer précisément les gagnants
sacrifiés et confirme qu'il ne faut pas entraîner ou activer automatiquement
un modèle sur la seule AUC univariée.

Le seuil provient de2024, mais le choix d'étudier cette feature a été fait
**après examen historique des trois années** dans l'audit précédent. Les
résultats2025/2026 ne sont donc pas une nouvelle confirmation indépendante ou
un holdout vierge. Pas de TP/SL, seuil, jour de décision ou population ajustés
après lecture de cette perte.

## Validation et traçabilité

**157 tests passent**, dont douze de ce replay : première clôture uniquement,
seuil strict exact, décision indépendante du futur, sortie au prochain open,
TP/SL intraday et gaps prioritaires, contrôle de durée et parité de référence.
Audit `PASS_EXPLORATORY_REPLAY_ONLY` : 708 issues de référence exactement
reproduites, **2 124 lignes** pour les trois bras, coûts/clés d'entrée
identiques, sorties appariées aux contrefactuels au prochain open déjà audités,
même contrôle sans chevauchement, aucun réinvestissement.

Dossier `artifacts/research/us_top10_failed_start_replay/20261019-v1/` :
`protocol.json`, `matched-trades.parquet`, `annual-comparison.csv`,
`report.json`, `final-audit.json`, `progress.json`.
Script `scripts/research/us_top10_failed_start_replay.py`, phases
`prepare/run/audit/all`.

Réserves : univers courant survivant, prix/OST et PIT historiques partiellement
qualifiés, frictions hypothétiques plutôt que fills réels, pas de capital,
levier, DD agrégé ou contraintes de portefeuille. Aucun SQL, API/LLM,
réentraînement, ordre ou changement de modèle/batch/configuration de production.
**Clôture de cet essai négatif ; pas de recherche automatique d'un autre seuil.**
