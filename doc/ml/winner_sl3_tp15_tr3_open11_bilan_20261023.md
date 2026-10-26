# Winner SL3 / TP15 / trailing3 / open11 : comparaison au TP7

23 octobre 2026. **TERMINÉ ET AUDITÉ / EXPLORATOIRE / PAS DE PROMOTION.**
[Protocole](winner_sl3_tp15_tr3_open11_protocole_20261023.md).
Canonique : `artifacts/research/us_winner_sl3_tp15_tr3_open11/20261023-v1`.

## Conclusion

Relever seulement le TP de7à15 % améliore le rendement net sur les deux années
observées et augmente légèrement le taux gagnant. Mais2025 reste perdante et
son drawdown augmente légèrement. Ce n'est donc pas une domination sur tous
les critères, ni une validation indépendante de la stratégie.

Capital initial4000USD parannée, frais8bps/jambe inclus. SL3/TR3/open11 et tous
les autres paramètres inchangés. Les référencesTP7 sont les comptes déjà
audités, réutilisés sans les réécrire ni les rejouer.

| Année | TP | Capital final USD | Rendement net | DDmax | Gagnants / perdants | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | 7 % | 3 652,94 | −8,68 % | **9,68 %** | 56 / 122 | 31,46 % |
| 2025 | 15 % | **3 702,14** | **−7,45 %** | 10,00 % | 58 / 124 | **31,87 %** |
| 2026 au30/09 | 7 % | 4 172,07 | +4,30 % | 3,67 % | 68 / 105 | 39,31 % |
| 2026 au30/09 | 15 % | **4 308,79** | **+7,72 %** | **3,63 %** | 69 / 104 | **39,88 %** |

DifférenceTP15−TP7 : rendement environ+1,23/+3,42points ; taux gagnant
+0,41/+0,58point. DD aggravé d'environ0,32point en2025, réduit de0,04en2026.
Une position ouverte valorisée fin2026, aucune fin2025, commeTP7 ; les taux
gagnants ne portent que sur les trades clôturés. Comptes remis à4000parannée :
ne pas présenter leurs capitaux comme une seule courbe continue.

## Gain/perte, activité et capital

| Mesure TP15 | 2025 | 2026 au30/09 |
| --- | ---: | ---: |
| Trades clôturés | 182 | 173 |
| Gains cumulés nets USD | +852,30 | +1 331,55 |
| Pertes cumulées nettes USD | −1 150,16 | −1 042,97 |
| Gain moyen net USD | +14,69 | +19,30 |
| Perte moyenne nette USD | −9,28 | −10,03 |
| Profit factor réalisé | 0,741 | 1,277 |
| Frais USD | 135,32 | 133,78 |
| Capital brut utilisé moyen USD | 236,38 | 284,20 |
| Part moyenne de l'equity engagée | 6,19 % | 6,75 % |
| Capital brut utilisé maximal USD | 2 401,56 | 2 338,32 |
| Séances gagnantes moyennes, entrée incluse | 2,17 | 2,03 |
| Séances perdantes moyennes, entrée incluse | 1,45 | 1,42 |
| Jours calendaires moyens gagnants | 1,78 | 1,36 |
| Jours calendaires moyens perdants | 0,75 | 0,67 |

TP7 utilisait206,65/241,62USD de capital brut moyen. Le TP plus éloigné laisse
parfois vivre une position plus longtemps ; les flux de cash et les admissions
suivantes divergent. Même formule de sizing, pas une liste de trades ou de
quantités nécessairement identique après divergence.

## Le trailing3 reste la sortie dominante

| Motif de sortie TP15 | 2025 | 2026 |
| --- | ---: | ---: |
| Stop intrabar, initial ou remonté | 157 | 148 |
| Gap sous stop | 22 | 17 |
| TP15 touché intrabar | **2** | **5** |
| TP15 sur gap | 0 | 0 |
| Stop remonté puis cours déjà inférieur | 1 | 3 |
| Ouverture de la11e séance | **0** | **0** |

Un « stop » peut donc être une sortie gagnante après remontée, pas forcément
une perte de3 %. Le gagnant médian net ne rapporte que **+2,10 % / +2,82 %**,
pas15 %. Le perdant médian est à−1,96/−2,15 %. La différence de rendement vient
d'un mélange d'amplitudes réalisées, d'activité et de capital ; ce n'est pas
une amélioration démontrée de la précision directionnelle.

Tous les trades clôturés sortent avant l'open11 : l'échéance est raccordée mais
ne déclenche ici aucune vente. Le TP7 précédent avait17/29sortiesTP ouTPgap,
contre2/5avecTP15. Ni high futur ni vente au sommet supposée.

## Ce qui reste identique

MêmeTOP10OracleparcoursH20, attente20, confirmation de cassure deux clôtures5m,
HALF sans renforcement et sans réachat d'un titre détenu, même prioritéOracle.
Même1428/1027signaux admissibles, mêmes archivesSIPraw/régulières5m et daily,
même risque/B4DD15 et plafond effectif1x. Le TP est le seul champ de règle
différent ; les manifestes sous-jacents sont identiques. L'allocationB4 reste
à1 dans les deux années de cette variante.

Un risque/exposition plus faible ne doit pas être présenté comme une comparaison
à risque égal avec le WinnerSL7/TR15/open21 d'origine (+19,96 %en2026).
Pas d'autorisation implicite d'augmenter le levier ou les tailles.

## Vérification et fichiers

29tests ciblés passent, dont adaptationTP15, différence de configuration limitée
au TP, restauration même sur erreur, collisionstop-prioritaire etTPgap plafonné.
Smoke5séances2025 :11achats/11sorties reconstruits àTP15 explicite, pas un bilan
annuel. Deux comptes complets ensuite : **356achats et355sorties** vérifiés,
cash/frais/positions/PnL/DD réconciliés. Scalaire appelé explicitement avecTP15,
empreinte de l'adaptateur dans l'audit, sourcesTP7 conservées intactes.
Comparaison finale et rapports scellés revérifiés. Même assistant, pas revue humaine.

Dans le dossier canonique :

- `comparison-tp7-tp15.csv` : comparaison demandée, quatre lignes année/TP.
- `comparison-audit.json` : empreintes des référencesTP7, duTP15 et du tableau.
- `variant-metrics-audited.csv` : métriquesTP15 et durées en séances.
- `annual-summary.csv` : référence nativeSL7 etTP15 ; ce n'est PAS le tableauTP7/TP15.
- Sous-dossiers annuels : trades, événements, courbes5m/daily, B4, refus entiers.

Aucune modification de production, entraînement, SQL, nouveau téléchargement,
appel fournisseur/LLM/broker ni ordre. Cohorte conditionnée par couverture future,
univers survivant, secteurs actuels, inventaireOSTvide/non exhaustif, dailySPY
révisable et absence de quotes/fills certifiés : pas de parité live intégrale.
Années et variantes déjà explorées ; pas un holdout inédit. Ne pas retenir ce
paramètre comme « optimal » sur la seule progression de deux essais.
