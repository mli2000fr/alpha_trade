# Anticiper les périodes défavorables au Winner TOP20 : audit borné

25 octobre2026. Demande : reconnaître avant d'engager du capital des contextes
défavorables comparables à2024. Audit, pas nouveau portefeuille ni activation.
Les essais antérieurs macro/dynamique/transition n'ont pas donné de veto stable :
voir `oracle_path_protections_dynamiques_20261014.md`,
`oracle_transitions_regime_20261021.md` et
`us_2019_2026_audit_regimes_combinaison.md`. Ce n'est pas un nouveau modèle.

## Périmètre et six hypothèses, avant calcul des résultats

Trades réellement admis par SL5/min70 et SL1/min70, TOP20,4kUSD continu2020–24,
archives identiques, frais inclus. Primaire SL5, SL1 sensibilité non indépendante.
Informations arrêtées à la dernière clôture de séance officielle précédant
l'entrée réelle ; donc pas de plus haut ni de clôture du jour d'achat en feature.

1. SPY sous sa SMA50.
2. Volatilité SPY20 au-dessus de sa médiane glissante126.
3. Moins de50% du TOP20 Oracle courant avec rendement20 positif. Minimum16
   titres renseignés ; calcul sur les20rangs originaux, pas la sous-cohorte
   sélectionnée par les données FUTURES. Ce n'est pas la breadth de tout le marché.
4. Momentum20 du titre inférieur au SPY sur20séances.
5. ATR20/titre ≥5% à la clôture précédente.
6. Gains cumulés inférieurs aux pertes cumulées des20 derniers trades déjà
   CLÔTURÉS de cette même stratégie. Les trades ouverts ne sont pas étiquetés
   gagnants/perdants ; après modification de politique ce suivi devrait être shadow.

Pas de recherche de seuils supplémentaires, combinaisons de flags ou choix
sectoriel rétrospectif. Macro VIX/taux/news/consensus sans vintage qualifiée non
utilisés. Daily split-ajusté fourni par l'archive, pas de disponibilité PIT inventée.

## Choix et évaluation chronologiques

Développement : entrées2020–22, sortie réelle ET maturité commune open21
connues avant2023. Au moins60trades/20dates par état globalement, et15trades/
10dates par état dans au moins deux ans. Flag défavorable si écart moyen de
rendement net unitaire négatif dans deux ans minimum et moyenne équipondérée
annuelle négative. Choisir UN seul flag, le plus négatif sur développement.
Sceller ce choix avant les agrégats de2023/24 ; ne pas changer après résultats.

Les six flags seront décrits pour transparence ; seul le choix de développement
est primaire. Vérification séparée2023 et2024 : ≥20trades/10dates par état,
écart négatif et borne supérieure du bootstrap en grappes de mois <0 dans
CHAQUE année ; sensibilité SL1 également négative dans les deux années.
3000tirages, graine4271. Les grappes ne garantissent pas l'indépendance entre mois.

Mesure : rendement net du trade réel par dollar d'entrée ; taux gagnant,
gains/pertes, masse des pertes et des gains identifiée par le flag, montants
engagés à l'origine. Classement par ANNÉE D'ENTRÉE, différent du précédent
diagnostic par année de sortie. Maturité commune open21 obligatoire : ne pas
conserver les seuls stops précoces en fin2024 en excluant les gagnants ouverts.
Information absente = inconnue, jamais état favorable inventé.

## Limites et décision

Périodes déjà vues, héritage OOF/survivants/coverage future/historiques révisés.
Trades acceptés conditionnés aux protections existantes : pas de causalité
d'une réduction de capital, ni d'exposition égale entre états. Le B4 réduit déjà
l'allocation ; cet audit ne démontre pas un apport INCRÉMENTAL sur le B4.
Les titres/dates/positions se répètent, SL1 n'est pas une réplication indépendante.
Une faiblesse observée dans le passé est réactive : elle ne prouve pas qu'on
prévoit le premier retournement à venir. Retirer des PnL historiques n'est pas
un replay de portefeuille, ne pas calculer un faux capital final filtré.

Même si tous les critères passent, conclusion limitée à une candidature pour
un replay distinct ultérieur. Sinon absence de signal robuste, sans élargir
l'audit indéfiniment. Aucune modification des risques, modèle, batch ou ordres.

Commande : `python -u -m scripts.research.us_winner_anticipation_audit_20261025`.
Sorties : `artifacts/research/us_winner_anticipation_audit/20261025-v1`.
Protocole/choix figés, contextes d'entrée par stratégie, agrégats et réserves.
Archives locales uniquement ; zéro SQL/API/LLM/entraînement/nouveau backtest.
