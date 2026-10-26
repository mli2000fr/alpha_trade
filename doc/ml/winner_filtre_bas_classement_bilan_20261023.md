# Veto des derniers rangs estimés : bilan des deux protocoles

23 octobre 2026. **DEUX CALCULS TERMINÉS ET AUDITS PASSÉS ; PAS DE PROMOTION.**
La règle faible volatilité20/60 d'abord ne confirme pas une amélioration stable
sur 2025 ET 2026. Elle améliore 2025 mais enlève beaucoup de gains en 2026.
Les filtres gardent les 7 ou 5 meilleurs estimés des dix Oracle d'origine,
priorité Oracle inchangée, sans remplacement par TOP11 ni choix des vrais perdants.

## 1. Winner natif actuel : six comptes annuels

[Protocole scellé](winner_filtre_bas_classement_protocole_20261022.md).
Archive `artifacts/research/us_winner_bottom_rank_filter/20261022-v2`.
SL7/TR15/sansTP, demi-position, aucun renforcement, sizing/risque natifs,
B4 DD15, exposition effective 1x, deux clôtures5m, vingt séances depuis le fill
puis open21. Chaque année/bras repart de 4 000 USD, frais8bps par jambe.

| Année | Variante | Rendement net | Capital final USD | DDmax | Gagnants / perdants | Capital brut moyen USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2025 | Winner seul | −11,83 % | 3 526,84 | 15,73 % | 9 / 44 | 340,90 |
| 2025 | Garder7 | +0,51 % | 4 020,56 | 14,71 % | 31 / 85 | 1 167,82 |
| 2025 | Garder5 | +3,98 % | 4 159,27 | 11,84 % | 29 / 65 | 962,71 |
| 2026 au30/09 | Winner seul | **+19,96 %** | **4 798,24** | **10,92 %** | 38 / 82 | 1 844,19 |
| 2026 au30/09 | Garder7 | +1,57 % | 4 062,66 | 12,57 % | 30 / 80 | 1 345,17 |
| 2026 au30/09 | Garder5 | +7,61 % | 4 304,48 | 12,21 % | 28 / 70 | 1 296,77 |

Taux gagnants2026 : 31,67 / 27,27 / 28,57 %. Six/cinq/cinq positions ouvertes
au terme pour Winner/Garder7/Garder5 ; elles sont valorisées, pas déclarées
gagnantes. En2025, zéro/sept/trois ouvertes. Pas de liquidation artificielle.

Les effets d'exposition comptent : Winner2025 passe en allocation B4 réduite
le10avril,183séances ; les deux variantes filtrées n'y passent pas. Une courbe
moins mauvaise laisse davantage de budget aux entrées suivantes. Ne pas
confondre effet portefeuille et preuve d'une meilleure direction unitaire.

32 tests ciblés ; les six comptes puis l'auditeur séparé passent :617 achats
confirmés,65 échéances vérifiées, cash/frais/PnL/positions/DD réconciliés.
Secteurs actuels, OST non exhaustives, OHLC sans quotes/fills historiques,
cohorte future commune1428/1027 sur2510/1880signaux : pas parité live intégrale.

## 2. Réplication de l'ancien +12,92 % : seul le veto change

[Protocole scellé](winner_legacy_filtre_protocole_20261023.md).
Archive `artifacts/research/us_winner_legacy_bottom_filter/20261023-v1`.
HALF_CONTROL historique : SL5/TR15/sansTP, risque planifié2 %, huit positions,
plafond plein25 %, cash positif1x, pas B4/secteurs/corrélation natifs. Échéance
J+20 depuis Oracle attente comprise, pas vingt séances détenues. Autres rangs
Oracle et anciennes213campagnes. **Compte continu**2025→30/09/2026, pas reset.

| Variante | Rendement2025 | Rendement2026 | Capital final continu USD | DD2025 | DD2026 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ancien Winner seul | +12,92 % | **+33,19 %** | **6 016,01** | 14,38 % | 15,56 % |
| Garder7 | +13,86 % | +14,53 % | 5 216,21 | 12,40 % | 12,91 % |
| Garder5 | **+15,60 %** | +11,87 % | 5 173,03 | **8,07 %** | **8,82 %** |

Frais8bps/jambe inclus. Le filtre réduit le risque mais aussi l'exposition :
capital moyen2025/2026 de1 634,90/2 066,48USD pour le témoin,1 254,39/1 229,16
pour Garder7 et915,24/918,33 pour Garder5. Pas une comparaison à risque égal.

Stress25bps, sizing/cash entièrement rejoués : témoin+7,90/+23,64 %, Garder7
+10,42/+10,31 %, Garder5+12,88/+7,24 %. Même absence d'amélioration transversale.

30 tests passent ; **les quatre tableaux de chaque témoin8/25bps reproduisent
exactement les archives** (marks/lots/orders/fills). Six reconstructions de
stops/sizing/frais/cash passent. Ratio J identique sur2727observations communes,
416dates complètes, une date inconnue laissée sans filtre, sans inventer un
mauvais rang. Aucun changement des prix, du timing ou du budget du témoin.

## Interprétation et statut

L'utilisateur avait raison de rappeler +12,92 %. Le premier nouveau témoin
n'était pas sa réplication ; les différences de contrat ci-dessus l'expliquent,
et le second protocole répond à la question à conditions identiques.
Le veto n'améliore ni les deux années ni le capital cumulé de la référence.
Une réduction du DD via moins d'exposition ne démontre pas de sélection prédictive.

La sonde avait déjà échoué en validation2022/maxT ; ces années avaient déjà été
regardées. Tests exploratoires postérieurs, pas holdout indépendant ni revue
humaine indépendante. Aucun modèle entraîné, filtre activé en production,
nouveau provider/LLM/broker, YAML ou moteur modifié. Ne pas retoucher le sens
du ratio pour sauver2026. L'audit des pertes est documenté séparément dans
[le bilan descriptif](winner_audit_pertes_bilan_20261023.md).
