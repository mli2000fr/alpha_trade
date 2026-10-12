# Oracle — trailing sur la grille TP/SL, 12 octobre 2026

## Protocole fixé avant les rendements

Demande initiale : ajouter un trailing puis refaire les couples TP/SL, ancien
Oracle terminal et nouveau Oracle « TP avant SL », TOP10/20/50, 2025 et 2026.
**Précision de l'utilisateur avant lancement : TP 20 % / SL 10 %.** La nouvelle
campagne se limite donc à ce couple pour isoler la sensibilité au trailing.
Il s'agit d'une **expérience de recherche séparée**, pas d'une activation live.
Les deux modèles restent figés, et les trades restent **LONG uniquement**.

La grille sans trailing est terminée et auditée :
[72 cas et réparations communes](oracle_tp_sl_grid_20261012.md).
Les mêmes inputs réparés sont réutilisés, aucun titre n'est retiré ou ajouté.

- Test principal : trailing **10 %** sur TP20/SL10, 12 portefeuilles.
- Sensibilité bornée : **5 % et 15 %** sur le même couple, deux modèles,
  deux années et trois tailles de sélection, soit 24 cas supplémentaires.
- Total : **36 nouveaux portefeuilles**, comparés aux 12 références TP20/SL10
  OFF déjà calculées. Un contrôle séparé OFF reproduit deux références 2026.
- Aucune optimisation automatique ou choix du meilleur pourcentage après pertes.
  10 % est une hypothèse de départ, pas un optimum ni une recommandation générale.

## Contrat d'exécution

Le trailing est une distance en dessous du **plus haut déjà observé**, pas un
objectif de rendement. Le SL fixe est conservé tant que le trailing ne peut
pas le remplacer sans le relâcher. Le moteur natif remplace le SL après une
activation ; l'adaptateur de recherche fixe donc le seuil :

`activation = max(prix d'entrée réel, stop initial / (1 − trailing))`.

Exemple entrée 100, SL10 = 90, trailing10 : activation dès que le plus haut
atteint **100** ; le trailing remplaçant est au minimum 90.
Après un plus haut à 115, son niveau devient **103,50** à la séance suivante.
Avec trailing15 et SL10, activation vers 105,88 ; avec trailing5, le SL initial
reste actif le jour d'entrée, puis le trailing peut être activé dès la séance suivante.

| Trailing | High d'activation pour entrée 100 / SL90 | Stop après high115 | High nécessaire pour stop100 |
| ---: | ---: | ---: | ---: |
| 5 % | 100 | 109,25 | 105,26 |
| 10 % | 100 | 103,50 | 111,11 |
| 15 % | 105,88 | 97,75 | 117,65 |

Ces niveaux s'appliquent à la séance suivante selon la convention retenue,
avant frais ; un stop100 ne garantit pas un rendement net nul et un gap peut
sortir plus bas. Un trailing plus large protège moins tôt mais laisse davantage
de marge aux fluctuations. Il n'est pas équivalent à un SL initial de 15 %.

Les barres sont journalières : la convention n'imite pas un watcher intraday
tick par tick. Le plus haut de J est connu après observation de la barre et
ne resserre le stop qu'à J+1. Pas de stop recalculé avec le futur high de la
barre dont on examine déjà le low. Priorité conservative si TP et stop sont
touchés dans une même barre. Un gap baissier sort au prix d'ouverture réel,
même sous le SL ; un gap favorable au TP est vendu au prix limite du TP.

Le TP20 fixe demandé reste actif. Sinon, on mélangerait effet du trailing
et suppression du TP. Expiry à l'ouverture de la **21e séance depuis l'entrée**,
vingt séances détenues incluant l'entrée J+1. Capital 4 000 USD par cas,
risque/sizing ATR natifs, coûts, huit positions maximum, secteurs et contraintes
inchangés. Le trailing peut libérer du capital et changer les entrées suivantes :
on compare des portefeuilles complets, pas seulement les mêmes trades isolés.

## Périmètre et réserves

- Décisions 2025 du 02/01 au 31/12, sorties jusqu'au 30/01/2026.
- Décisions 2026 du 02/01 au 03/09, sorties jusqu'au 05/10/2026.
- Les TOP sont des nombres de candidats classés par score, pas des pourcentages
  et pas des achats automatiques de tous les titres.
- Les deux modèles ont des hyperparamètres différents ; comparaison économique,
  pas une ablation causale du seul label d'entraînement.
- Secteurs actuels/non PIT acceptés, macro/screener et ajustements non certifiés,
  prix/volumes réparés prospectivement non PIT ; mêmes réserves que OFF.
- La grille n'est pas une validation hors échantillon nouvelle ; pas de promotion.
- Pas d'entraînement, d'écriture SQL, de changement de configuration live, de
  courtier contacté ou d'ordre envoyé.

## Implémentation et validation

Adaptateur isolé : `scripts/research/us_oracle_barrier_trailing_grid.py`.
Les moteurs opérationnels et la grille sans trailing ne sont pas modifiés.
Tests : `tests/test_us_oracle_barrier_trailing_grid.py` : protections ancrées
au fill, activation sans relâchement, absence d'anticipation du high, collisions,
gaps, TP/expiry, cash et reproduction OFF.
Audit indépendant `scripts/research/us_oracle_barrier_trailing_audit.py` : pour
chaque sortie trailing, recalcul depuis les prix observés avant la sortie,
contrôle du prix de gap et de la filiation du lot après conversion.
Tests correspondants : `tests/test_us_oracle_barrier_trailing_audit.py`.
Les empreintes des inputs, modèles, preuves, moteurs, configuration et résultats
OFF sont figées au lancement et vérifiées à la fin ; reprise par cas, sans
résurrection d'un portefeuille échoué au milieu.

Commande de campagne :

```powershell
python -u -m scripts.research.us_oracle_barrier_trailing_grid --inputs artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1 --baseline artifacts/research/us_oracle_barrier_comparison/tp-sl-grid-20261012-v2 --output artifacts/research/us_oracle_barrier_comparison/trailing-grid-20261012-v1 --workers 3
```

Ne pas lancer deux instances sur le même répertoire. Pour un contrôle initial,
ajouter `--smoke` et utiliser un autre `--output`. Les quatre cas smoke incluent
deux OFF et deux trailing10, TOP10 2026 TP20/SL10.

Suivi : `progress.json` (compteurs), `events.log` (cas terminés), et les
`STRICT/progress.json` de chaque cas (séances). Le rapport complet comparatif
est `summary.md`, publié **seulement après vérification** de tous les cas.

## État final — 35 cas qualifiés, 1 bloqué par LBRDK

Protocole fixé ; 18 tests de l'adaptateur et 6 tests de l'audit indépendant
passent. Les 21 tests de la grille TP/SL d'origine passent également.
Le premier smoke a conservé quatre simulations mais échoué au post-traitement :
lecture erronée de `direction` au lieu du champ natif `side`, corrigée et couverte
par des tests. Rejeu de contrôle dans `trailing-smoke-20261012-v2`.
Les quatre cas V2 sont terminés : références OFF TOP10 2026 TP20/SL10 reproduites
exactement, y compris leurs séries quotidiennes et toutes leurs transactions. Deux portfolios trailing10
complets, **296 sorties** vérifiées par l'audit indépendant des plus hauts
antérieurs et des gaps. Cash réconcilié, aucune créance non valorisée.

Campagne terminée dans `trailing-grid-20261012-v1` : **35 cas complets, un échec**.
Les inputs, modèles, preuves et codes figés sont inchangés en fin de calcul.
Le statut global reste `PARTIAL_FAILED` / `FAILED` ; il n'est pas changé en succès.
La synthèse indépendante est `partial-summary.json` / `partial-summary.md`.
Le PnL arrêté au milieu du cas échoué n'est ni publié ni ajouté aux comparaisons.
Tous les **18 cas du nouveau modèle** sont qualifiés ; 17 sur 18 de l'ancien.
Régression globale : **192 tests passent**, avertissements connus pandas/fixtures
de corrélation constante seulement ; aucun test échoué.

Audit indépendant des 35 cas : **8 565 transactions**, **6 227 sorties trailing**
vérifiées contre le high des séances antérieures, l'activation sans relâchement
du stop, le prix de gap et le lifecycle. Erreur cash maximale
**5,00 × 10⁻¹² USD** ; aucune créance non valorisée dans les résultats complets.

### Nouveau modèle LONG — rendement net de cohorte

| Année | N | Sans trailing | Trailing5 | Trailing10 | Trailing15 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | 10 | +12,39 % | −2,44 % | −0,09 % | +0,84 % |
| 2025 | 20 | +10,34 % | +3,78 % | +5,59 % | +2,36 % |
| 2025 | 50 | +8,81 % | +14,34 % | +1,47 % | +3,78 % |
| 2026 | 10 | +18,93 % | −4,34 % | +7,90 % | +15,97 % |
| 2026 | 20 | +22,10 % | +0,30 % | +1,86 % | +15,63 % |
| 2026 | 50 | +22,10 % | +0,75 % | +1,97 % | +15,63 % |

2026 signifie décisions jusqu'au 3 septembre, pas une année civile complète.
Ces cohortes repartent chacune de 4 000 USD ; ne pas additionner les rendements
comme s'ils provenaient d'un portefeuille continu de deux ans.

Le trailing réduit le rendement du nouveau modèle dans **17/18 comparaisons**.
Sa baisse maximale de capital n'est améliorée que dans **2/18** cas : trailing5,
TOP20 et TOP50 2026 ; ailleurs elle s'aggrave. Pour TOP10, DD sans trailing
−7,98 % / −6,57 % en 2025 / 2026 ; trailing10 −11,49 % / −6,66 %.
L'exception de rendement est TOP50 2025 trailing5, mais le DD s'aggrave aussi
(−5,85 % → −9,89 %) et le rendement 2026 chute de +22,10 % à +0,75 %.

### Ancien modèle — amélioration 2025 non confirmée en 2026

| Année | N | Sans trailing | Trailing5 | Trailing10 | Trailing15 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | 10 | −7,64 % | +8,19 % | −7,36 % | −10,63 % |
| 2025 | 20 | −6,97 % | +15,20 % | −5,48 % | −8,32 % |
| 2025 | 50 | −10,36 % | +23,39 % | −5,12 % | −7,43 % |
| 2026 | 10 | +16,09 % | +0,41 % | +6,72 % | +9,61 % |
| 2026 | 20 | +12,16 % | +4,96 % | +7,34 % | +2,10 % |
| 2026 | 50 | +12,16 % | **Bloqué LBRDK** | +6,98 % | +4,95 % |

Le trailing5 semble aider l'ancien modèle en 2025, mais les deux cas 2026
terminés de ce pourcentage régressent. Ne pas généraliser en omettant le
TOP50 manquant ni choisir 5 % parce qu'il a le meilleur résultat 2025.

### Cas LBRDK réservé et piste de remédiation

Ancien modèle TOP50 2026, trailing5 : arrêt au 20/07/2026,
`Unqualified held-position volume LBRDK/2026-07-20`. Une position réellement
financée est encore détenue, donc le contrôle de qualité ne peut être ignoré.
Le risque natif décide à J ; on ne retire pas LBRDK rétroactivement à l'entrée
en utilisant son défaut futur, ni on ne remplace le candidat par le suivant.

L'archive `lbrdk-volume-refresh-20261007-v1` reproduit chez EODHD le même volume
nul et OHLC tous égaux à 30,845. Il ne s'agit donc pas d'une correction de
compteur ou d'une panne du trailing.

Autre piste déjà disponible, **non intégrée** :
`artifacts/research/us_sip_daily_universe/audit-20260101-20260930-20261011-v1/diagnostic-raw-split-local.csv`.
Pour le 20 juillet, SIP raw indique open31,03, high31,03, low30,165, close30,36,
volume935 227. Les 21/22 juillet divergent également ; le 17 juillet, les
OHLC sont proches mais close30,87 versus30,845. Le défaut n'est donc pas seulement
un volume nul : **prix, continuité d'identité et chemin complet** doivent être
qualifiés. Pas de substitution opportuniste du seul volume dans cette campagne.
Pour une reprise ultérieure : qualifier les preuves et unités, versionner des
inputs communs réparés, reconstituer les features/rangs si nécessaire, puis
vérifier les références OFF et relancer les cas affectés. Ne pas modifier les
archives actuelles ou écrire cette correction en SQL sans nouveau périmètre.

## Conclusion

**NO_GO_TRAILING_PROMOTION_TP20_SL10**, dans cette convention quotidienne et
sur ce périmètre : aucun avantage régulier démontré, particulièrement pour le
nouveau modèle. Conserver le scénario sans trailing comme référence de recherche.
Ce n'est pas une preuve qu'un trailing intraday ou une autre règle serait toujours
inutile, ni une validation live du scénario OFF. L'adaptateur reste disponible
pour une autre hypothèse explicitement figée ; aucun paramètre live n'est changé.

La campagne ne devient pas « 36/36 » : le cas ancien TOP50/trailing5 2026
reste techniquement à remédier. Le constat du nouveau modèle porte en revanche
sur l'intégralité de ses 18 cas, sans exclusion d'un échec.

Reproduire l'audit partiel, sans recalculer les modèles ou écrire en base :

```powershell
python -u -m scripts.research.us_oracle_barrier_trailing_partial_summary --root artifacts/research/us_oracle_barrier_comparison/trailing-grid-20261012-v1
```
