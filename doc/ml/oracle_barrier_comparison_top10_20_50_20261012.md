# Oracle terminal H20 contre Oracle TP avant SL — TOP10, TOP20 et TOP50

> Mise à jour du 12 octobre : le [raccordement AVB a ensuite terminé six scénarios 2026](oracle_merger_replay_2026_20261012.md).
> La validation prédictive reste réservée : fractions non valorisées et features
> AVB contaminées par une fausse baisse de 63,7 %. Les résultats ci-dessous
> conservent le premier protocole et ses blocages ; ils ne sont pas promus.
> Les features et rangs ont ensuite été corrigés, sans retrait de titre ni
> réentraînement. La [nouvelle grille TP/SL](oracle_tp_sl_grid_20261012.md)
> conserve ces archives et rapporte séparément les replays corrigés 2026.

## Périmètre figé, autorisé le 12 octobre 2026

Les nombres **10, 20 et 50 sont des nombres de titres par séance**, pas des
pourcentages de l'univers. La comparaison ne réentraîne aucun modèle, ne
modifie aucune branche servie, n'écrit pas en SQL et ne transmet aucun ordre
au courtier. Le diagnostic AVB a seulement effectué deux requêtes Alpaca
en lecture : métadonnées de l'actif et barres SIP historiques.

- Ancienne référence : `model-factory-20261003082853-e98332`, **branche de
  recherche corrigée** `oracle-h20-numeric-effect-20261007-v1/corrected/2024-01-08`.
  Le répertoire original ne contient pas le modèle exécutable localement :
  il ne faut pas présenter cette comparaison comme celle du binaire original.
- Nouveau modèle : `model-factory-20261011221400-867a1e/oracle_barrier`,
  têtes LONG et SHORT du fold `2024-01-08`.
- Dernières disponibilités des labels de validation : 5 janvier 2024 ;
  aucun entraînement/validation utilisé ne voit 2025 ou 2026.
- Période externe commune : **2 janvier 2025 → 3 septembre 2026**, 419 séances,
  univers statique de **1 790 titres**, 173 features et 747 961 lignes scorées.
  Ces années ont déjà été étudiées : ce n'est pas un holdout vierge.
- Deux stratégies de portefeuille : anciens meilleurs scores puis LONG,
  nouveaux meilleurs scores de la tête LONG puis LONG.

Les paramètres d'apprentissage des deux branches ne sont pas identiques.
On compare deux modèles réellement figés, **pas l'effet causal du seul changement
de label à hyperparamètres constants**.

## Contrat commun de sélection, risque et exécution

1. Classement à J par score décroissant, puis symbole croissant en cas d'égalité.
2. Sélection des N premiers **avant** consultation des résultats futurs.
   Un rendement inconnu n'est pas remplacé par le titre suivant.
3. Entrée à l'ouverture J+1, soumise au filtre de gap et aux refus du moteur natif.
4. **SL fixe 7 % et TP fixe 20 % du prix réellement exécuté**, sans trailing.
5. Vingt séances de détention incluant l'entrée : sortie à l'ouverture de la
   21e séance (`entry_index + 20`). Aucune high/low de cette dernière séance
   ne doit intervenir avant cette sortie horaire.
6. Mêmes moteurs de risque, sizing, coûts, règlement du cash et lifecycle.
   Capital initial **4 000 USD par cohorte annuelle**, preset `capital_2001_5000`,
   huit positions maximum, mêmes contraintes de secteurs, corrélations,
   liquidité, exposition, régime et drawdown.

Les scores bruts de l'ancien et du nouveau modèle n'ont pas la même échelle.
Le sizing reçoit donc **le même percentile de rang** pour les deux stratégies,
sans prétendre qu'il s'agit d'une probabilité directionnelle calibrée. Le sizing
reste le sizing natif fondé notamment sur l'ATR : remplacer le stop exécuté
par 7 % ne revient pas à recalculer toutes les tailles avec un risque constant
à 7 %. Cette convention est identique dans les deux branches.

TOP50 ne signifie pas cinquante positions ouvertes. Les refus de risque, le
capital et les positions déjà détenues déterminent ce qui est réellement acheté.
Les cohortes 2025 et 2026 sont indépendantes ; les derniers achats ont leur
queue d'expiration complète, éventuellement dans l'année suivante. Leur
rendement final n'est donc **pas strictement un rendement calendaire au 31/12**.

### Prix et réserves de preuve

Les labels et le replay utilisent les OHLC ajustés actuels sur une base commune.
Les dividendes sont implicites dans les ajustements, pas certifiés comme
événements cash historiques. Les secteurs sont actuels/non PIT, conformément
à l'acceptation antérieure de l'utilisateur. Les dates de publication originales
des valeurs macro ne sont pas certifiées champ par champ.

Les résultats par candidat excluent les chemins inconnus et les collisions
TP/SL dont l'ordre intrajournalier est indéterminable. Le portefeuille ne peut
pas éliminer rétrospectivement ces trades : il utilise le moteur conservateur
natif (stop prioritaire en collision quotidienne, TP limité à son prix limite
sur gap favorable, gap SL au prix d'ouverture). **Les résultats de labels ne
sont donc ni des ordres exécutés ni un PnL de portefeuille.**

## Contrôle des versions des features

Les contrats de colonnes, options et univers coïncident. Les checksums des
modèles, des archives et des sources sont enregistrés. Un contrôle sur
6 300 lignes d'entraînement communes, 129 features de base après conversion
float32, ne retrouve aucune différence.

Un contrôle supplémentaire sur les 10 475 lignes externes des 25 premiers
titres retrouve **125 valeurs révisées de `selector_short_score`**, et aucune
autre feature différente à la tolérance du contrôle. Les valeurs historiques
du screener en base ont évolué depuis le 7 octobre.

La comparaison conserve donc **la même archive externe immuable du 7 octobre
pour les deux modèles**, plutôt que mélanger versions anciennes et actuelles.
Les rangs transversaux sont reconstruits sur l'ensemble commun éligible à J,
jamais par shard ni sur les seuls futurs gagnants. Ce contrôle échantillonné
n'est pas une certification exhaustive de disponibilité PIT du screener.
L'éligibilité à J dépend de la barre de J ; les défauts futurs restent des
résultats inconnus, jamais un filtre de classement.

## Premières mesures par candidat — calcul terminé

Taux de TP 20 % atteint avant SL 7 %, parmi les chemins qualifiés. Chaque
observation est un **titre × séance**, pas un trade indépendant : les fenêtres
et les titres réapparaissent. Les pourcentages ne sont pas des rendements.

| Année | Nombre | Ancien : TP | Nouveau LONG : TP | Inconnus ancien / nouveau |
| --- | ---: | ---: | ---: | ---: |
| 2025 | 10 | 28,53 % | 27,52 % | 1 / 0 sur 2 500 |
| 2025 | 20 | 27,92 % | 24,97 % | 3 / 3 sur 5 000 |
| 2025 | 50 | 25,40 % | 24,15 % | 5 / 9 sur 12 500 |
| 2026 au 03/09 | 10 | 25,55 % | 23,90 % | 11 / 33 sur 1 690 |
| 2026 au 03/09 | 20 | 25,45 % | 23,80 % | 16 / 52 sur 3 380 |
| 2026 au 03/09 | 50 | 25,18 % | 22,98 % | 45 / 104 sur 8 450 |

Le nouveau modèle ne démontre pas de gain de fréquence TP dans ces six
comparaisons. Il réduit aussi certains taux de SL ; les expirations et les
refus de portefeuille empêchent de déduire directement un gain/perte net.
Les inconnus, plus fréquents dans la nouvelle sélection en 2026, sont signalés
et ne doivent pas être interprétés comme des échecs ou succès connus.

Un bootstrap descriptif **apparié par dates**, blocs circulaires de vingt
séances, 2 000 répétitions, seed 12026, conserve les dénominateurs qualifiés :

| Année | Nombre | Écart TP nouveau − ancien | Intervalle descriptif 95 % |
| --- | ---: | ---: | ---: |
| 2025 | 10 | −1,01 point | [−5,08 ; +2,99] |
| 2025 | 20 | −2,94 points | [−5,64 ; −0,42] |
| 2025 | 50 | −1,26 point | [−2,28 ; −0,23] |
| 2026 | 10 | −1,65 point | [−4,27 ; +0,84] |
| 2026 | 20 | −1,65 point | [−3,85 ; +0,33] |
| 2026 | 50 | −2,19 points | [−3,63 ; −0,92] |

Ces intervalles tiennent compte d'une partie de la dépendance temporelle,
pas de toute la concentration par titre, et ne sont pas corrigés pour les
comparaisons multiples. Ils n'établissent aucune alpha future. Le fichier
`candidate-uncertainty.json` fournit aussi les bornes sur **tous** les candidats :
TP connus / total jusqu'à (TP connus + inconnus) / total, sans leur inventer un
résultat. Le bootstrap ne transforme pas les inconnus en labels.

### Direction automatique : diagnostic distinct, seuil inchangé 0,55

On classe le maximum des deux scores, puis on conserve uniquement les choix
dont ce maximum atteint 0,55 et dont les deux scores diffèrent. Ce n'est pas
la stratégie LONG du tableau précédent.

- 2025 : 32, 62 et 121 choix pour TOP10/20/50, **tous SHORT**, aucun TP observé.
- 2026 : **abstention sur tous les candidats**, pour les trois nombres.
- Aucun seuil n'est diminué après observation ; aucun calibrateur n'est appris.
- Aucun PnL SHORT n'est présenté sans qualification historique de l'emprunt.

Ce diagnostic ne justifie pas de promouvoir le choix LONG/SHORT automatique.

## Portefeuilles 2025 — terminés, capital et coûts appliqués

Les six portefeuilles 2025 sont terminés. Le cash est réconcilié ; aucun
rendement du tableau ne provient d'une simple moyenne des labels gagnants.

| N titres | Ancien : rendement cohorte close | Nouveau LONG : rendement cohorte close | DD ancien | DD nouveau |
| --- | ---: | ---: | ---: | ---: |
| 10 | −5,42 % | +7,33 % | −12,52 % | −9,37 % |
| 20 | −3,61 % | +12,05 % | −15,21 % | −9,42 % |
| 50 | −4,91 % | +17,37 % | −15,70 % | −8,25 % |

La cohorte inclut les sorties finales jusqu'au 30 janvier 2026, sans nouveaux
achats après le 31 décembre 2025. Les rendements **valorisés au 31/12/2025**
sont respectivement ancien/nouveau : TOP10 −4,83 % / +7,67 % ;
TOP20 −5,60 % / +10,06 % ; TOP50 −4,64 % / +17,69 %.
Les positions encore ouvertes à la coupe ne sont pas liquidées fictivement.

Le modèle LONG TP-avant-SL améliore donc ce replay 2025, **malgré moins de TP
par candidat** : risque, expirations, recouvrement des candidats et capital
disponible expliquent pourquoi ces deux mesures ne sont pas interchangeables.
Cela ne valide pas encore l'automatisme LONG/SHORT ni une supériorité stable
sur les deux années.

### Blocages 2026 et remédiation bornée

Les trois anciens portefeuilles échouaient à la valeur macro du 5 octobre,
**après les dernières sorties J21**, sans position ni nouvelle décision.
La remédiation autorise uniquement cette queue devenue cash : aucun chiffre
macro n'est inventé. Une macro absente avec une position ouverte reste bloquante.
Les anciens résultats sont conservés, et les trois replays concernés sont
recalculés dans une destination distincte.

La remédiation est **terminée** : neuf portefeuilles complets, trois bloqués.
Erreur de réconciliation cash maximale sur les neuf : inférieure à 10⁻¹¹ USD.

| N titres | Ancien 2026 à la coupe du 03/09 | Ancien : cohorte close au 05/10 | DD cohorte | Nouveau 2026 complet |
| --- | ---: | ---: | ---: | --- |
| 10 | +4,46 % | +6,11 % | −11,00 % | BLOQUÉ AVB |
| 20 | +0,53 % | −1,01 % | −10,76 % | BLOQUÉ AVB |
| 50 | +4,74 % | +4,53 % | −10,76 % | BLOQUÉ AVB |

Les trois nouveaux portefeuilles s'arrêtent sur AVB le 17 août 2026. Un GET
historique Alpaca SIP confirme l'arrêt des barres au 14 août, et son référentiel
classe AVB inactif ; le référentiel SQL local le classe encore actif. Les trois
OHLC communs au 12–14 août ont un facteur Alpaca / SQL d'environ **2,793** :
on ne doit pas raccorder naïvement prix et quantités sur deux bases différentes.

Le [communiqué du 12 août](https://investors.avalonbay.com/sec-filings/all-sec-filings/content/0001104659-26-094930/tm2622947d1_ex99-1.htm)
annonce la conversion de chaque action AVB en **2,793 actions** du successeur,
puis le ticker **VMRK à partir du 18 août**. Le
[8-K de clôture](https://investors.avalonbay.com/sec-filings/all-sec-filings/content/0001104659-26-097833/tm2623381d1_8k.htm)
confirme la fusion du 17 août et la suspension d'AVB avant l'ouverture.

Le moteur de ce replay ne traite pas cette migration de positions/protections
et les éventuelles fractions payées en cash. **Il serait faux de remplir AVB
avec des prix fabriqués, de le supprimer après coup, de forcer une vente avant
la fusion ou de doubler une conversion déjà reflétée dans les ajustements.**
Le nouveau PnL 2026 complet reste donc bloqué par ce lifecycle, pas par un
besoin de réentraîner. Les données de recherche, la preuve de fusion et les
parcours partiels sont conservés. Les rendements inconnus restent inconnus.

À titre de **diagnostic du préfixe commun au 14 août**, avant le blocage, les
rendements valorisés de l'ancien sont +9,42 % / +5,52 % / +7,59 % pour
TOP10/20/50 ; ceux du nouveau sont +18,51 % pour les trois nombres, DD −6,22 %.
Les parcours de portefeuille du nouveau coïncident jusqu'à cette date malgré
le nombre de candidats différent. Ce n'est pas un nouveau test préspécifié :
la coupe est dictée par l'échec, les positions restent ouvertes et le reste
de l'année est inconnu. **Aucun rendement pleinement réalisé 2026 du nouveau
modèle n'est annoncé sur cette base.**

Suite autorisée par le GO suivant, désormais documentée dans la
[remédiation AVB](oracle_merger_replay_2026_20261012.md) : qualifier la base AVB/VMRK, l'historique du
successeur, la conversion des quantités/prix de protection, le traitement des
fractions et les contraintes du portefeuille, puis relancer ces trois cas.
Une série synthétique de continuité éventuelle doit être séparée d'un replay
certifié du lifecycle ; elle ne doit pas être présentée comme des bars AVB réels.

## Exécution, reprise et suivi

Source : `scripts/research/us_oracle_barrier_comparison.py`.
Les extensions de `us_concentrated_live_portfolio.py` sont **réservées à la
recherche** et préservent les contrats des variantes existantes par défaut.
**130 tests ciblés réussis**, sans base ni courtier, incluant les 64 tests déjà
existants du modèle/audit et 66 tests des contrats de comparaison/replay : TP/SL ancrés sur le fill,
expiry à l'ouverture, collision le jour d'expiration, refus d'une queue trop
courte, inconnus non remplacés, égalités déterministes et garde SELECT-only.
La couverture globale du dépôt n'est pas validée par cette suite ciblée.
Une exécution avec la couverture globale activée a échoué sur son seuil de
70 %, sans échec d'assertion : cette sélection partielle ne couvre qu'environ
9 % du dépôt. La vérification ciblée finale, sans couverture globale, est :

```powershell
python -m pytest --no-cov tests/test_oracle_barrier.py tests/test_oracle_barrier_top10_audit.py tests/test_us_oracle_barrier_comparison.py tests/test_us_oracle_barrier_comparison_summary.py tests/test_us_concentrated_live_portfolio.py tests/test_us_concentrated_fixed_stop.py tests/test_us_concentrated_exit_variants.py -q -o addopts=
```

```powershell
python -u -m scripts.research.us_oracle_barrier_comparison --output artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2
Get-Content artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2/progress.json
```

Ne jamais lancer deux processus sur la même destination. Les sources et
contrats doivent rester identiques pour une reprise ; les modèles ne sont
jamais réentraînés. Les exécutions terminées sont conservées, les autres
repartent du début de leur portefeuille en raison de l'état du cash/trackers.

**La commande originale n'est plus à relancer dans V2** après la remédiation :
elle refuserait à raison le changement d'empreinte du driver. V2 est l'archive
immuable du premier replay, avec six échecs initiaux. La commande de remédiation
exacte, terminée, est :

```powershell
python -u -m scripts.research.us_oracle_barrier_comparison_remediation --source artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2 --output artifacts/research/us_oracle_barrier_comparison/cash-tail-remediation-20261012-v2
```

Le rapport consolidé conserve les six succès 2025 et les trois replays ancien
Oracle 2026 remédiés, avec leurs répertoires/sources exacts. Le dossier
`cash-tail-remediation-20261012-v1` conserve uniquement un échec de préflight
lié aux séparateurs de chemins Windows ; aucun portefeuille n'y a été exécuté.

- [Protocole](../../artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2/protocol.json).
- [Mesures par candidat](../../artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2/candidate-report.json).
- [Contrôle des versions](../../artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2/feature-version-audit.json).
- [Incertitude et bornes des inconnus](../../artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2/candidate-uncertainty.json).
- [Progression globale](../../artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2/progress.json).
- [Résultats 2025 lisibles](../../artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2/report.md).
- [Progression de la remédiation cash-only](../../artifacts/research/us_oracle_barrier_comparison/cash-tail-remediation-20261012-v2/progress.json).
- [Rapport final consolidé](../../artifacts/research/us_oracle_barrier_comparison/cash-tail-remediation-20261012-v2/report.md).
- [Synthèse JSON — résultats complets et préfixe partiel distingués](../../artifacts/research/us_oracle_barrier_comparison/cash-tail-remediation-20261012-v2/summary.json).
- [Preuve d'événement AVB](../../artifacts/research/us_oracle_barrier_comparison/avb-evidence-20261012-v1/official-event.json).

V1 conserve l'arrêt prudent du contrôle de versions, avant toute simulation de
portefeuille. V2 documente cette différence, conserve les inputs communs figés
et exécute la comparaison autorisée.
