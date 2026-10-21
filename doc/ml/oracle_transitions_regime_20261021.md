# Diagnostic des transitions de régime SPY

## Protocole borné, avant les calculs d'attribution

GO du21octobre2026. Diagnostic des résultats déjà scellés, **aucun nouveau
backtest, entraînement, appel fournisseur/LLM, SQL écrit ou ordre**. Aucune
modification des modèles, protections, paramètres, univers ou veto d'entrée.

Primaire :SL7/TR15/H20/sansTP, plafond1x,B4DD15,4kUSD indépendants chaque année,
LONG et SHORT séparés. Sensibilité : les cinq voisins déjà utilisés dans l'audit
de robustesse, pas nouveaux paramètres choisis selon les résultats du jour.
2025 et2026au30septembre ;24comptes existants, pas24réplications indépendantes.

### Régime et temporalité

Il s'agit du **régime de prix SPY** employé dans les replays : cours de clôture
au-dessus/en-dessous de ses moyennes50/200séances. BULL=au-dessus des deux,
CORRECTION=au-dessus200mais pas50, REBOUND=au-dessus50mais pas200,
SLIDE=en-dessous des deux. **Pas le régime macro complet VIX/VXN/MOVE de l'application.**

Le régime à la séanceJ utilise seulement la clôture qualifiée deJ−1 et son
historique. Reconstituer le contexte antérieur à2025 pour éviter une fausse
transition le1erjour, puis vérifier l'accord avec les437contextes scellés.
Daily split-adjusted, pas ffill ni disponibilité applicative PIT inventée.

Partition primaire causale et exclusive, fixée sans grille de fenêtres :

- Jour d'un changement observé :D0.
- Quatre séances suivantes :D1àD4.
- Primaire «transition récente»=D0àD4 depuis le **dernier** changement observé.
- «Stable»=aucun changement sur les cinq dernières séances de décision.

Un nouveau changement remet le compteur àzéro ; une date n'appartient qu'à
une catégorie primaire. Aucun changement futur n'est utilisé pour étiqueter
une entrée. La phase future de «retour à l'état précédent en cinq séances»
reste un résultat rétrospectif, pas un feature ni la preuve d'un faux signal.

### Mesures

Variation quotidienne d'equity après frais, conservée exactement enUSD,
séparée entre lots achetés aujourd'hui et lots détenus depuis la veille.
Pour ces derniers, mesurer aussi le PnL de prix entre closeveille/openjour,
puis le solde intraday/coûts. Ne pas confondre une perte déjà subie à l'ouverture
avec une nouvelle entrée que B4 aurait pu empêcher à cette heure.

Emprunt reconnu à la sortie ou au MTM annuel, comme le moteur historique ;
pas de charge quotidienne économique fictive. Financement séparé. Sommes par
lots/jour/année doivent reconstruire les marques5m et le PnL original.

Comparer nombre de séances, dollars perdus/gagnés, masse des journées
perdantes, exposition et PnL par1000USD-séances de capital indicatif.
Normaliseur descriptif=max(grossclôtureveille,grossmoyen5minjour), pour ne pas
effacer l'exposition d'une position liquidée au gap. **Pas un replay à exposition
égale, ni un rendement cumulable ou un effet causal de la transition.**

Analyser séparément les cohortes d'entrée par phase : trades fermés et taux de
gagnants, positions ouvertes/MTM et censure, durée. Ne pas attribuer tout le
PnL d'un trade au régime de sa sortie ou supposer des trades indépendants.

### B4 et fenêtres rétrospectives

Documenter chaque déclenchement B4 : régime, distance au dernier changement,
réductions/sorties et première allocation pleine ultérieure ; absence de
reprise avant la fin du compte =censure, pas délai infini ni reprise au reset
du1erjanvier. **B4 répond au drawdown du compte**, il n'est pas censé couper
automatiquement à chaque changement de régime. La distance observée entre
les événements ne prouve donc ni une latence anormale ni une causalité.

Fenêtres alignées rétrospectivement−5..+10séances autour de chaque transition :
les cinq jours «avant changement» ne sont pas une information connue à leur
date. Les fenêtres peuvent se chevaucher ; ne pas les additionner comme du
PnL indépendant ni en faire un veto d'entrée prêt à déployer.

### Limites et sortie

Même213campagnes/72titres avec disponibilité future des prix, survivants et
OracleparcoursCatBoost de recherche ; pas tout TOP10 ni LightGBMproduction.
Hypothèses fills/borrow/CA et historique retraité héritées. Années déjà examinées,
pas holdout neuf, aucun test de significativité naïf ni nouveau seuil choisi
sur les pertes. Ancien horizonOracleJ+H, pas nouveau contrat de détention live.

Dossier : `artifacts/research/us_oracle_regime_transitions/20261021-v1`.
Commande : `python -u -m scripts.research.us_oracle_regime_transitions`.
Fichiers : contexte causal, attribution quotidienne/cohortes, synthèses de
phase et d'entrées, événements B4, fenêtres rétro et manifeste des sources.
## Résultats terminés et audités

**24comptes existants analysés, aucun nouveau replay.** Les437régimes scellés
et leurs dates de source sont reproduits depuis le SPY daily avec warmup
avant2025. Les décompositions lots/jour/année retombent sur les PnL d'origine.
Audit séparé : calcul scalaire des régimes et reconstruction par cash+variation
de valeur d'inventaire, **5244observations compte-jour**, erreurmax1,71e-12USD.
**14tests réussis**, ycompris causalité, retours rapides, LONG/SHORT, aller-retour
dansla journée et frais/emprunt des positions ouvertes. Mêmeassistant, pas
revuehumaineindépendante. Rapport tests :
`artifacts/tmp/oracle-regime-final-tests-20261021.xml`.

### 1. Des transitions plus fréquentes en2026

| Période | Changements observés | Nouveau changement sous5séances | Séances classées D0–D4 | Séances stables |
| --- | ---: | ---: | ---: | ---: |
| 2025 | 13 | 3 | 57/250=22,80% | 193 |
| 2026au30septembre | 21 | 13 | 66/187=35,29% | 121 |

Dans cet échantillon, les13retours rapides2026 ramènent aussi au régime
précédent sous5séances, contre3en2025. Cette connaissance est **postérieure**
au changement : elle ne permet pas de qualifier d'avance un signal de «faux».
Ce constat décrit davantage d'allers-retours du SPY autour de ses seuils,
pas nécessairement un changement macroéconomique structurel identifié.

### 2. PnL effectivement produit pendant les phases

RéférenceSL7/TR15/H20/sansTP, B4DD15, plafond1x ;4kUSD indépendants par an/sens.
Ce sont des **contributions enUSD sur les journées**, pas des rendements de
stratégies «ne trader que cette phase». Les durées et expositions diffèrent :

| Sens / année | PnL D0–D4 | PnL stable | Moyenne/jour D0–D4 | Moyenne/jour stable |
| --- | ---: | ---: | ---: | ---: |
| LONG2025 | +171,16USD | +902,11USD | +3,00USD | +4,67USD |
| LONG2026 | −344,72USD | +1022,49USD | −5,22USD | +8,45USD |
| SHORT2025 | −15,18USD | −973,45USD | −0,27USD | −5,04USD |
| SHORT2026 | −604,21USD | −420,39USD | −9,15USD | −3,47USD |

Normalisation descriptive par capital indicatif :LONG2026−2,87USD par1000USD-
séances enD0–D4 contre+3,66USD stable ;SHORT−10,14contre−4,45USD. Ce n'est ni
un contrôle à exposition égale ni un rendement prévisible à la décision.

**La masse des pertes LONG n'est pas disproportionnellement concentrée sur
ces fenêtres en nombre de jours** :22,33%des dollars des journées perdantes
en2025pour22,80%des séances ;34,84%en2026pour35,29%des séances. La différence
de PnL net vient aussi de gains beaucoup plus élevés en périodes stables,
pas d'une explosion de toutes les pertes juste après bascule. Les expositions
restent différentes, et les pertes d'un compte sont interdépendantes.
SHORT2026 :40,87%de la masse des journées perdantes pour35,29%des séances,
mais ce motif ne se retrouve pas de la même manière en2025.

### 3. Positions déjà détenues contre nouvelles entrées

Décomposition LONG2026 pendantD0–D4 :

- Lots détenus depuis la veille : **−435,37USD**.
- Lots achetés le jour même, sur cette seule journée : **+90,65USD**.
- Total : **−344,72USD**.

Le PnL de prix overnight de ces fenêtres est−62,19USD ; la majorité du solde
défavorable des lots déjà détenus se produit donc ensuite enintraday/coûts,
pas uniquement dans les gaps. Bloquer les achats du jour ne ferait pas
disparaître mécaniquement ces pertes : positions/capital/B4 changeraient, ce
qui demanderait un vrai replay distinct, non lancé ici.

Autre question, distincte : que deviennent **sur toute leur vie** les trades
entrés enD0–D4 ? Les cohortes d'entrée fermées donnent :

| Sens / année | Entrées D0–D4 : gagnants / tradesfermés | Entrées stables | PnL fermé D0–D4 | PnL fermé stable |
| --- | ---: | ---: | ---: | ---: |
| LONG2025 | 38,10% /21 | 36,71% /79 | +67,22USD | +1051,76USD |
| LONG2026 | 22,73% /22 | 39,22% /51 | −760,18USD | +1437,95USD |
| SHORT2025 | 43,48% /23 | 22,54% /71 | +506,95USD | −1521,78USD |
| SHORT2026 | 19,05% /21 | 20,00% /40 | −530,94USD | −493,65USD |

En2025, positions ouvertes séparées :LONG2récentes/5stables,SHORT2récentes/6stables.
Leurs MTM sont dans le fichier de cohortes mais pas dans ces taux de trades
fermés. En2026, aucune position ouverte finale. Il ne faut pas confondre
PnLdujourd'entrée+90,65 et PnLàlasortiedescohortesrécentes−760,18 : les pertes
peuvent survenir plus tard, éventuellement lorsque le régime est devenu stable.

### 4. Même régime, conclusion variable selon l'année

Dans le seul état **BULL**, LONG :

| Période | BULLrécent : PnL / séances | BULLstable : PnL / séances |
| --- | ---: | ---: |
| 2025 | +486,87USD /21 | +1215,23USD /158 |
| 2026 | −367,94USD /36 | +1069,12USD /103 |

La différence persiste ennormalisationparcapital :BULLrécent+7,16puis−5,33USD
par1000USD-séances en2025/26 ;BULLstable+2,57puis+4,23USD. Le résultat négatif
2026ne vient donc pas seulement d'un mélange d'états plus baissiers, mais
l'effet n'est pas stable entre années. À l'inverse,CORRECTIONrécent LONGest
négatif2025(−508,21USD/21séances) et positif2026(+95,10USD/25séances).
Les effectifs sont petits et l'exposition/identité des titres diffère.

Une période «stable» signifie seulement que **l'étiquette n'a pas changé** :
le marché peut continuer de baisser fortement dans unSLIDE stable.

### 5. Sensibilité aux cinq voisins de paramètres

Pour2026LONG, quatre profils sursix (référence,H15,trailing20,TP10) ont du
PnLnégatif récent et positif stable. **SL5 et trailing10 présentent le motif
inverse**. En2025LONG, les phases récentes restent positives pour cinqprofils
sursix ;TP10estnégatif dans les deux catégories. Aucun filtre universel de
transition ne peut être affirmé à partir de cette sensibilité.
Les six profils ne sont pas six confirmations indépendantes : mêmes titres,
dates et prix largement communs.

### 6. Déclenchements B4 et reprises

| Compte référence | Déclenchement | Régime | Séances depuisdernierchangement | Retouràallocationpleine |
| --- | --- | --- | ---: | --- |
| LONG2025 | 4avril | SLIDE | 6 | 10juillet,65séancesaprès |
| SHORT2025 | 29mai | BULL | 11 | Nonobservéavantfin2025 |
| LONG2026 | 19mars | CORRECTION | 13 | 4mai,31séancesaprès |
| LONG2026 | 27juillet | CORRECTION | 1 | Nonobservéau30septembre |
| SHORT2026 | 6avril | SLIDE | 10 | Nonobservéau30septembre |

Un seul des cinq déclenchements se situe dansD0–D4. Les quatre autres ne
disparaîtraient pas par simple interdiction des fenêtres récentes. Ces délais
ne sont **pas** une mesure prouvée de «retard fautif» :B4estpilotéparleDDducompte,
pasparunobjectifdechangerimmédiatementavecl'étiquetteSPY. Les reprises31/65
séances et censures méritent d'être connues, mais aucune nouvelle réduction
d'exposition n'est imposée et aucune protection n'est désactivée par cet audit.

## Conclusion bornée

**Diagnostic terminé ; aucun veto de transition validé.**2026montre davantage
de changements rapides et un contraste défavorable auLONGde référence après
transition, mais pas une concentration disproportionnée de sa masse de pertes
par rapport au nombre de séances. Le signal varie avec l'année, l'état et les
protections ; une partie importante des pertes concerne déjà les positions
détenues, et non les seules nouvelles entrées.

On ne peut pas transformer ces constats en «éviterD0–D4aurait rapporté X» :
cela exigerait un protocole et un véritable replay séparés, puis un futur
échantillon jamais regardé. Les fenêtres avantchangement et les retours rapides
restent rétrospectifs, jamais des features disponibles àleurdate.

Rapports : `phase-summary.csv`, `entry-cohort-summary.csv`,
`regime-stratified-summary.csv`, `profile-sensitivity.csv`, `b4-trip-timing.csv`,
`transition-counts.csv`. Contrôles : `final-review.json`, `post-review.json`.
Aucun modèle, batch, configuration de production, univers, base SQL ou ordre modifié.
