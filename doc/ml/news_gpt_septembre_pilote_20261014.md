# Pilote GPT sur les news stockées — septembre 2026

GO utilisateur du 14 octobre 2026, crédit API limité. Étude locale distincte du
filtre GPT/Web de production et de la faisabilité « dilution nouvelle ».
Ni modèle, configuration, batch, ordre, ni ligne SQL modifiés.

## Protocole figé avant les réponses et les rendements

Les cinq premières séances US de septembre : **1, 2, 3, 4 et 8 septembre 2026**.
TOP5 d'origine, sans remplacement par les rangs suivants. Source :
`artifacts/research/us_oracle_path_protection_selector/20261014-v1/candidates.parquet`.
Modèle annuel 2026 : `model-factory-20261014113232-bc35a7`, CatBoost parcours,
fold `2025-12-10`, entraînement/validation disponibles avant les dates étudiées.
Aucun nouveau scoring ni apprentissage Oracle.

25 couples titre/date, huit titres distincts. Fenêtre fixée aux 24 heures avant
la clôture NYSE, strictement avant celle-ci. Le week-end/les jours fériés ne sont
pas intégralement couverts par cette fenêtre ; aucune optimisation de fenêtre.
Le choix de ce mois répond à l'exemple de l'utilisateur, pas aux gains observés.

GPT lit seulement titre, résumé et extrait de corps déjà stockés. L'extrait est
borné à 2 400 caractères ; toute troncature est déclarée. Les empreintes des
corps sources et les paquets exacts sont archivés. Aucun Web, outil, accès à la
base ou donnée de prix transmis au LLM. Les instructions dans les textes sont
traitées comme des données non fiables.

Le LLM extrait au maximum trois faits accompagnés de citations textuelles et
qualifie BULLISH, BEARISH ou ABSTAIN. Une réponse directionnelle exige une
identité correspondante, un fait matériel et des citations effectivement présentes
dans les champs fournis. Sa confiance n'est pas une probabilité de rendement.
L'identité locale est actuelle/non PIT et ne certifie pas l'association fournisseur.
La nouveauté par rapport à dix articles antérieurs n'est **pas** qualifiée ici.

**Une seule règle testée :** veto d'un achat LONG pour BEARISH, fait matériel,
identité concordante, preuves contrôlées et confiance >=0,75, seuil figé avant
les résultats. Pas d'ordres SHORT ni de modèle entraîné. Sans article utilisable :
UNKNOWN, pas « neutre » ; le bras veto conserve ces candidats comme la baseline.
ABSTAIN n'est pas une erreur technique. Réponse invalide : arrêt et conservation
de la réponse payée, jamais une relance automatique pour obtenir une autre opinion.

## Coût et reprise

Modèle GPT lu dans `config.yaml` : `gpt-6-luna`. Aucune substitution et aucun
changement du fournisseur de production, qui peut rester DeepSeek.
Au maximum huit requêtes, 1 800 tokens de sortie par requête et 240 000 octets
UTF-8 de requêtes cumulées. Raisonnement `none`, outils absents, `store:false`.
Plafond conservateur de tokens **0,05 USD** : les requêtes entières et une marge
d'encadrement de 2 000 tokens par requête sont bornées avant le premier appel.
Ce n'est pas une interrogation du solde bancaire/API ni une garantie sur la TVA,
le change, les autres traitements concurrents ou une modification des tarifs.

Prix figés consultés le 14 octobre : 0,10 USD/M tokens d'entrée et 0,50 USD/M
de sortie, sans compter les réductions de cache dans l'estimation. Sources :
[fiche GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[sorties structurées](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

La requête est journalisée **avant** l'appel, la réponse complète avant son
interprétation. Une reprise réutilise cette réponse ; une tentative sans réponse
persistée est ambiguë et ne peut pas être automatiquement refacturée. Un échec
HTTP/transport arrête le pilote. La clé reste exclusivement dans l'environnement.

## Évaluation économique

Les réponses et leur sélection sont scellées avant de charger les prix futurs.
Diagnostic individuel : TP +20 % avant SL −5 %, entrée au prochain open, vingt
séances incluant l'entrée, expiration à l'open suivant, résolution OHLC prudente
et gaps. Ce diagnostic brut n'est pas additionné en rendement de portefeuille.

Comparaison de deux portefeuilles locaux : Oracle seul contre le même Oracle
avec veto GPT. Capital initial 4 000 USD, plafond de levier ×2, sizing/contrôles
natifs, frais/spread/slippage et financement identiques, pas de renforcement d'un
titre détenu. TP20/SL5, **sans trailing**, expiration après vingt séances de
détention. Entrées autorisées uniquement aux cinq dates figées ; suivi jusqu'au
7 octobre pour les sorties. Ce n'est pas la performance annuelle ni une copie
de son portefeuille initialisé en janvier. Les deux bras commencent en cash.

Prix et macro déjà archivés, empreintes vérifiées. Si la fin de la macro manque,
lecture des seules dates manquantes dans `stock_macro_indicators_daily`, après
scellement GPT, avec copie locale et réserve **vintage SQL actuel/non PIT**.
Jamais de régime neutre inventé ou de forward-fill. Les secteurs sont actuels ;
les fills OHLC, coûts et marge sont des hypothèses, pas des exécutions historiques
certifiées. Les données fournisseur/actions sur titres conservent leurs réserves.

## Limites déterminantes

Les 27 articles repérés au diagnostic ont été importés les 2–3 octobre. **Zéro
article du jour passe la garde locale conservatrice avant décision**. Les tables
prospectives créées le 14 octobre ne réparent pas cette histoire. Le texte publié
avant J peut avoir été modifié ultérieurement ; l'association peut être erronée.

Un LLM utilisé aujourd'hui peut avoir une connaissance externe/historique non
maîtrisée. L'instruction « uniquement ce texte » et l'absence de Web ne prouvent
pas une absence de contamination. Les citations justifient l'extraction, pas
l'indépendance de sa conclusion directionnelle.

25 couples mais seulement cinq dates et huit titres très répétés : observations
non indépendantes, aucune puissance statistique démontrée. Les refus natifs de
risque peuvent empêcher certains vetos GPT de changer effectivement les trades.
Un résultat positif serait une illustration rétrospective, **jamais une preuve
prédictive ni un motif d'activation du filtre en production**. Aucun réglage de
seuils/fenêtres sur ces résultats ; confirmation prospective séparée indispensable.

## Exécution et résultats

Script : `scripts/research/us_news_gpt_september_pilot.py`.
Phases séparées : `prepare`, `analyze`, `evaluate`, avec `--output` identique.
Tests isolés : `tests/test_us_news_gpt_september_pilot.py`, sans MySQL/API réels.

**Terminé : `COMPLETED_EXPLORATORY_NOT_PIT`, verdict
`NO_FILTER_ACTION_ON_THIS_SAMPLE`.** Artefacts :
`artifacts/research/us_news_gpt_september/20261014-v1`.

### GPT et coût réellement observés

Huit appels réussis, zéro relance, zéro appel Web. 19 750 tokens d'entrée et
796 de sortie. Estimation brute aux tarifs figés : **0,002373 USD** ; remise de
cache non déduite, taxes/change exclus et solde du compte non consulté.
La borne conservatrice calculée avant les appels était 0,0176142 USD, en deçà
du plafond général de 0,05 USD. Les réponses exactes et leurs consommations sont
dans `api/`, `usage.json`, `analysis.json` et `assessments.json`.

| Séance de décision | Titre | Avis GPT | Motif synthétique |
| --- | --- | --- | --- |
| 01/09 | CCOI | ABSTAIN | Participation à des conférences, pas de fait matériel directionnel. |
| 01/09 | MXL | ABSTAIN | Statistiques sectorielles, pas de fait spécifique démontré. |
| 01/09 | DOCN | ABSTAIN | Annonce de conférence, pas de développement matériel. |
| 02/09 | DOCN | ABSTAIN | Contexte macro, conférence et opinion tronquée. |
| 03/09 | DOCN | ABSTAIN | Croissance annoncée, mais extrait incomplet sur les marges et opinion promotionnelle. |
| 04/09 | MRVL | BULLISH | Croissance des résultats/data centers et perspectives relevées ; risques de marges signalés. |
| 08/09 | CCOI | ABSTAIN | Opinion et métriques rétrospectives, pas d'événement nouveau établi. |
| 08/09 | TXG | ABSTAIN | Article multi-titres et autre texte concernant Caterpillar. |

Les 17 autres couples titre/date sont **UNKNOWN_NO_QUALIFIED_TEXT**, sans appel
GPT. Aucune réponse BEARISH : **zéro veto**, donc aucun achat éliminé par la règle.
La confiance 0,82 sur MRVL est un score subjectif de preuves, pas 82 % de probabilité
de gain. Les fortes confiances d'ABSTAIN indiquent l'insuffisance des preuves,
pas une direction. Les huit réponses ont passé les contrôles de citations.
**19 des 27 extraits** étaient tronqués : il faut distinguer insuffisance des
textes fournis, exigence du protocole et capacité générale du LLM.

### Diagnostic des trajectoires

25 couples qualifiés sur cette tape fournisseur exploratoire, aucune exclusion
de prix/gap/identité dans le diagnostic individuel. 11/25 touchent TP20 avant
SL5 ; les25 se répartissent sur peu de titres et ne sont pas indépendants.
Ce n'est pas un taux de réussite de25 trades exécutés par le portefeuille.

Le seul avis BULLISH, **MRVL au 4 septembre**, correspond à une entrée théorique
au 8 septembre à 227 USD, puis **SL5 le 14 septembre à 215,65 USD**, soit −5 % brut.
Il n'a pas été acheté dans le portefeuille réel de cette simulation, qui détenait
d'autres titres et restait soumis à ses contraintes de capital/risque.
Ce diagnostic individuel n'est pas un backtest supplémentaire « BULLISH-only ».

### Portefeuilles appariés

| Mesure | Oracle seul | Oracle + veto GPT |
| --- | ---: | ---: |
| Capital initial | 4 000,00 USD | 4 000,00 USD |
| Capital final | **4 881,17 USD** | **4 881,17 USD** |
| Rendement net simulé | +22,03 % | +22,03 % |
| Drawdown maximal sur clôtures | −5,27 % | −5,27 % |
| Positions closes | 9 | 9 |
| Gagnantes / perdantes | 4 / 5 | 4 / 5 |
| Taux gagnant | 44,44 % | 44,44 % |
| Somme des PnL positifs | +1 237,87 USD | +1 237,87 USD |
| Somme des PnL négatifs | −353,10 USD | −353,10 USD |
| Financement débiteur | −3,60 USD | −3,60 USD |

Frais/spread/slippage natifs déjà dans les PnL ; coût des huit appels GPT séparé,
non imputé au portefeuille. Après cette dépense API, le filtre serait donc très
légèrement moins bon monétairement, sans différence de trading. Aucun avantage
directionnel démontré. Le gain de22,03% est celui de **cette courte cohorte Oracle**,
pas une performance attribuable à GPT, annualisable ou garantie.

Les neuf trades ne sont pas25 achats : un titre détenu n'est pas renforcé et le
capital/risque peut empêcher une entrée. Une nouvelle entrée après une sortie
reste autorisée si le titre revient dans les cinq candidats des dates figées.
Capital et PnL réconciliés à moins de10⁻⁶USD. Les courbes et trades des deux bras
sont égaux champ par champ, pas simplement proches sur leur rendement final.

### Arrêt technique puis continuation hors ligne

Le premier évaluateur a demandé **trop tôt** la présence de macro jusqu'au 7 octobre.
La tape se termine au 2 octobre et la base ne contenait pas les valeurs des 5–7 octobre.
Il s'est arrêté avant tout résultat économique. Le script et protocole initiaux
ont été conservés, sans changer une réponse GPT ni refaire un appel.

Une continuation technique distincte, documentée dans
`technical-evaluation-amendment.json`, laisse le **garde natif existant** vérifier
chronologiquement si la macro manque pendant une exposition. Aucune valeur
macro n'est créée, interpolée ou considérée neutre ; un manque avec position
ouverte continuerait à bloquer. Tous les titres étaient en fait sortis
le **23 septembre**. Les 5–7 octobre sont donc `NOT_REQUIRED_CASH_ONLY_EXPIRY_TAIL`
dans les deux journaux, sans position ni nouvelle entrée possible. Les deux
portefeuilles ont terminé sans désactiver de garde de risque.

Continuation : `scripts/research/us_news_gpt_september_pilot_review.py`.
**28 tests isolés réussis**, puis contrôle hors ligne des empreintes des entrées,
paquets/réponses, citations exactes, absence d'appel outil, consommation, courbes,
trades et absence de positions pendant les dates macro manquantes. Bilan
`completion-audit.json`. Aucun changement de règles, seuils, dates ou protections
après lecture des réponses ; aucun nouvel abonnement ni collecte fournisseur.

### Conclusion bornée

Le pilote démontre que l'analyse ciblée est techniquement faisable et peu coûteuse.
Il **ne démontre pas son efficacité directionnelle** : zéro veto, une seule
opinion favorable suivie d'un SL dans le diagnostic, textes incomplets/non PIT
et seulement cinq dates. Ne pas relâcher maintenant les critères ou explorer
d'autres prompts jusqu'à obtenir un gain sur ce même échantillon.
