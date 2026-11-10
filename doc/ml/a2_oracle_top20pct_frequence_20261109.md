# A2 sur TOP20 % Oracle — audit de fréquence

Demande utilisateur du9novembre2026 : élargir le scénario à TOP20 % Oracle
puis A2, pour augmenter le nombre de signaux. Période01/01/2021–01/10/2026,
mêmes Oracles H10 annuels et univers contractuel de1 790titres.

**Comptage de signaux uniquement à ce stade : aucun rendement, entraînement,
appel fournisseur, écriture SQL, ordre ou réglage de production.**

## Hypothèse et comparaisons

La variante principale passe directement des **358candidats Oracle à A2**,
sans plafonnement préalable aux cinq scores LONG per-symbol. A2 conserve ses
paramètres : range20M15 figé àJ, impulsion12M15≥2ATR, ATR14, largeur0,8–5ATR,
deux contacts espacés, rebond àJ+1, disponibilité+930s puis open5m suivant.
Le filtre de régime reste SPYJ>98 %SMA200. Pas de modification de SL5/open11
ou du budget vol20/régime pour un éventuel replay ultérieur.

Quatre cohortes sur **les mêmes données** pour séparer l'effet de l'élargissement
Oracle de celui du retrait du classement per-symbol :

| Cohorte | Pipeline compté |
|---|---|
| OLD_TOP5_SAME_DATA | Ancien TOP10 % Oracle → TOP5 per-symbol avec seuils → A2 |
| ORACLE_TOP10PCT_DIRECT | TOP10 % Oracle,179candidats → A2 sans per-symbol |
| ORACLE_TOP20PCT_DIRECT | **TOP20 % Oracle,358candidats → A2 sans per-symbol** |
| ORACLE_TOP20PCT_PER_SYMBOL_TOP5 | TOP20 % Oracle → TOP5 per-symbol avec les mêmes seuils → A2 |

Les seuils per-symbol des contrôles restent score>0,50/AUC calibration≥0,50,
connue avant le signal ; aucun score n'est réentraîné ou réinterprété. Les
modèles d'amplitude Oracle ne prédisent pas une direction ; A2 impose ici une
politique LONG à tester, pas une direction déjà certifiée.

## Archives et qualité

516 594couples séance/titre,1 443séances,1 174titres distincts sur l'ensemble
de la période. Les candidats sont fixés par Oracle avant lecture du motif,
sans sélection par rendement ou chemin futur complet.

Prix : archives originales du témoin, compléments de l'étude TOP358, puis
contexte SIP récupéré précédemment en SQL. Les anciens prix sont prioritaires,
aucune moyenne entre sources ou substitution d'une ligne déjà archivée.
Les empreintes des fichiers sont contrôlées contre leurs manifestes scellés.
Pas de nouvelle requête fournisseur ou de nouveau téléchargement.

Le calcul des M15 et des ranges a été vectorisé pour traiter le pool élargi.
Neuf tests passent sur le détecteur, dont deux nouveaux : agrégation identique
à la version scalaire avec trous, et règles/ATR/touches identiques sur201
fenêtres dont une positive. À la fin, les24confirmations précédemment détectées
doivent être préservées avec la même heure d'exécution. Un manque de contexte
reste inconnu, jamais un signal négatif.

Comptages après régime, titres distincts, occasions espacées de11séances et
présence d'un open5m compatible avec le daily sont distingués. Un signal doté
de prix ne devient pas automatiquement un achat : détention, capital et risque
du portefeuille restent à appliquer. Les signaux répétés ne sont pas tous
indépendants. Les années ont déjà été explorées, ce n'est pas un holdout inédit.

## Suivi

Racine : `artifacts/research/us_a2_oracle_top20pct/20261109-v1/`.
Script : `scripts/research/us_a2_oracle_top20pct_20261109.py`.
Accélération : `scripts/research/us_a2_bulk_frequency.py`.
`request.json` fige le périmètre ; `progress.json` suit le comptage ;
`comparison.csv`, `annual-frequency.csv`, `validation.json` et `report.json`
seront écrits à la fin. Journaux par année dans `inputs/audits/` et événements
horodatés dans `inputs/a2-events.parquet`.

## Bilan terminal

**AUDIT TERMINÉ, FRÉQUENCE SUFFISANTE SUR LE POOL DIRECT, AUCUN PNL CALCULÉ.**
Les paramètres et horaires A2 sont inchangés. Les6 073décisions de l'ancien
pilote correspondent exactement, y compris motifs de rejet, couverture,
qualification du range et confirmations. Les24confirmations et leurs heures
d'exécution sont conservées. Compteurs candidats/annuels recomptés : PASS.

| Périmètre avant A2 | Candidats | Contexte qualifié | Ranges | Confirmations | Après régime | Titres | Espacés11séances | Prix d'exécution qualifié |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ancien TOP10 % → TOP5 per-symbol |6 073|4 153|97|24|22|21|22|20|
| TOP10 % Oracle directement |258 297|169 836|5 196|1 458|1 243|366|1 111|1 193|
| **TOP20 % Oracle directement** |**516 594**|**314 028**|**10 217**|**2 835**|**2 452**|**537**|**2 190**|**2 368**|
| TOP20 % → TOP5 per-symbol |7 083|4 197|108|23|23|20|23|20|

Le gain principal vient du retrait du plafonnement per-symbol :22→1 243signaux
à pool Oracle10 % inchangé. Passer ensuite le pool direct de10 % à20 % donne
1 243→2 452, soit1 209signaux supplémentaires (+97,3 %). Conserver TOP5
per-symbol malgré TOP20 % donne23signaux seulement et ne résout pas la rareté.
Le pool20 % direct donne environ111fois l'effectif initial après régime,
mais les populations et la sélection directionnelle diffèrent : ce facteur
ne mesure aucun gain de performance.

### Variante principale par année

| Année d'entrée | Confirmations | Après régime | Titres distincts | Prix qualifié |
|---|---:|---:|---:|---:|
|2021|455|455|214|426|
|2022|495|181|115|164|
|2023|513|492|233|482|
|2024|411|411|209|393|
|2025|493|450|236|446|
|2026 au01/10|468|463|249|457|

2 452signaux sur878séances actives parmi1 443, moyenne1,70par séance sur toute
la période, maximum22sur une séance. Ils ne seront pas tous exécutés :
prix, positions déjà détenues, risque, capital et covariance restent à appliquer.
2 190occasions espacées par titre ne sont pas2 190observations statistiquement
indépendantes entre secteurs ou régimes. Le gate de fréquence précédemment
fixé passe pour les pools Oracle directs10 %/20 %, échoue pour les deux TOP5
per-symbol.

314 028/516 594contextes sont qualifiés (60,79 %) ;202 566restent inconnus.
Les prix sont qualifiés pour2 368des2 452signaux après régime ;84restent
sans preuve d'exécution compatible. Ces réserves interdisent de présenter
le résultat comme une couverture complète de l'univers ou comme un taux
de réussite directionnelle. Aucun rendement/DD A2 n'a été calculé ici.

**Conclusion : oui, TOP20 % Oracle → A2 sans TOP5 per-symbol fournit un
échantillon suffisant pour un backtest économique exploratoire.** Le retrait
du filtre per-symbol change aussi la qualité de sélection ; l'avantage financier
reste à tester avec les protections vol20/régime,SL5/open11 et les mêmes coûts.
