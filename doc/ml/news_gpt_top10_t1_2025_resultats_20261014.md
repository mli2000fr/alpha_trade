# TOP10 Oracle + GPT sur les news — résultats janvier–mars 2025

> Complément du 15 octobre : à la demande de l'utilisateur, les 213 réponses
> ont ensuite été importées dans `alpha_trade.llm_news_analysis_cache`, avec
> leurs preuves et le panneau des 600 candidats. Relecture depuis SQL identique,
> sans nouvel appel ni changement de ce résultat. Les huit réponses du pilote
> septembre sont aussi conservées. [Guide du cache SQL](../signals/news_analysis_cache.md).

## Conclusion

**Moins de pertes dans ce replay, mais pas de rentabilité ni de signal prédictif
validé.** Capital de 4 000 USD : Oracle seul finit à **3 509,82 USD (−12,25 %)** ;
avec les seuls veto GPT valides, **3 751,81 USD (−6,20 %)**, avant environ
0,09 USD d'API. Écart : **+242,00 USD / +6,05 points** avant API, **+241,91 USD**
après cette estimation. Le drawdown maximal aux clôtures recule de 24,34 % à
16,99 %, sans devenir faible.

Statut : `COMPLETED_PARTIAL_SIGNAL_EXPLORATORY_NOT_PIT`. Ce résultat ne justifie
**ni promotion live ni activation d'un filtre**. Les textes ne sont pas certifiés
historiquement disponibles et le LLM peut connaître les événements postérieurs.

## Périmètre et protocole

Voir la [préparation et ses contrôles](news_gpt_top10_t1_2025_preparation_20261014.md).
Le GO payant distinct a été donné le 14 octobre ; plafond initial 0,50 USD,
porté à 1 USD pendant le traitement. Le processus déjà lancé a conservé son
plafond plus strict de 0,50 USD. Aucune dépense supplémentaire n'était nécessaire.

- 60 séances du 2 janvier au 31 mars 2025 ; dix titres, pas 10 %, par séance.
- 600 couples titre/date, **35 titres distincts** ; observations très répétées.
- Oracle parcours CatBoost annuel `model-factory-20261014113226-102eca`, fold
  `2024-12-05`, entraînement/validation disponibles avant le trimestre, poids
  inchangés. Les 300 TOP5 archivés sont reproduits exactement.
- News existantes : publication précise dans les 24 h strictement avant clôture
  NYSE J, sans Web, téléchargement complémentaire ni élargissement de fenêtre.
- GPT `gpt-6-luna`, uniquement référence d'émetteur, texte/extraits et publication.
  Ni score Oracle ni prix/cible/rendement futur transmis. Schéma/prompt inchangés.
- Règle primaire : **veto d'achat LONG** si fait matériel BEARISH, émetteur
  concordant, citations exactes et confiance >=0,75. La confiance n'est pas une
  probabilité calibrée. BULLISH ne reçoit pas d'allocation supplémentaire.
- UNKNOWN, erreur technique et ABSTAIN restent candidats comme dans Oracle seul.
  Aucun SHORT et aucun remplacement par le 11e titre.
- **TP20/SL5, sans trailing**, entrée au prochain open, sortie au prochain open
  après vingt séances de détention si aucune protection n'a déjà exécuté.
  Il ne s'agit pas du précédent couple TP20/SL10.
- Capital continu de 4 000 USD, levier maximal 2, contraintes natives conservées :
  sizing, capital, concentration, régime, circuit breaker, contrôle du gap de 3 %
  et refus des entrées contraintes. Pas de renforcement d'un titre détenu.
- Frais/spread/slippage du moteur identiques ; financement simulé à 6,5 % annuel,
  ACT/360 sur le débit. Ce n'est pas une reconstitution du tarif historique d'un
  courtier ni de fills réels. Un stop à 5 % ne limite pas une perte à 5 % en gap.

Réponses scellées à 21:51:05 UTC ; protocole économique enregistré à 21:51:20 UTC,
**avant** lecture des résultats futurs et avant les deux portefeuilles. Les règles
étaient déjà définies en préparation ; aucun seuil ajusté sur le PnL. Queue
d'expiration prévue jusqu'au 30 avril, sans nouvelle décision après le 31 mars.

## Réponses, coût et erreurs

| État sur les 600 couples | Nombre |
| --- | ---: |
| BULLISH techniquement valide | 26 |
| BEARISH valide, déclenchant un veto LONG | 26 |
| ABSTAIN valide | 143 |
| Réponse techniquement invalide, conservée UNKNOWN | 18 |
| Sans texte qualifié dans la fenêtre, aucun appel | 387 |

**213 réponses payées uniques, aucun retry et aucun appel Web.** 591 353 tokens
d'entrée, dont 584 240 d'écriture de cache, et 30 110 de sortie. Estimation
conservatrice : **0,0887963 USD**, majoration d'écriture du cache incluse, remise
de lecture ignorée. Hors taxes, change et autres tâches du compte. Tarif standard
vérifié sur la [fiche officielle du modèle](https://developers.openai.com/api/docs/models/gpt-6-luna).

Premier arrêt après 12 réponses : une citation PLTR n'existait pas dans le paquet.
Réponse brute conservée, jamais repayée ni corrigée artificiellement. La
continuation maintient la règle stricte : **15 erreurs de citations exactes et
3 JSON invalides**, distincts des 143 abstentions. Aucun des 18 cas ne peut veto.
« Valide » désigne ici le schéma, l'identité déclarée et la présence des citations,
pas une validation humaine du sens économique de tous les avis.

La borne initiale tous appels de la préparation omettait la majoration du cache.
La continuation corrige le contrôle : dépense observée conservatrice + borne du
prochain appel, cache compris, <=0,50 USD avant tout paiement. La marge nouvelle
jusqu'à 1 USD n'a pas été utilisée. Protocoles et preuves initiaux restent intacts.

## Portefeuilles appariés

Frais de trading et financement inclus ; coût API indiqué séparément.

| Mesure | Oracle seul | Oracle + veto GPT valides |
| --- | ---: | ---: |
| Capital initial | 4 000,00 USD | 4 000,00 USD |
| Capital final avant API | **3 509,82 USD** | **3 751,81 USD** |
| Gain/perte net avant API | −490,18 USD | −248,19 USD |
| Rendement | **−12,25 %** | **−6,20 %** |
| Drawdown maximal aux clôtures | −24,34 % | −16,99 % |
| Positions closes | 41 | 42 |
| Gagnantes / perdantes | 7 / 34 | 8 / 34 |
| Taux gagnant | 17,07 % | 19,05 % |
| Somme des PnL positifs, frais affectés inclus | +1 808,42 USD | +2 118,52 USD |
| Somme des PnL négatifs, frais affectés inclus | −2 282,37 USD | −2 350,04 USD |
| Intérêts de marge | −16,23 USD | −16,66 USD |
| Capital final après estimation API | 3 509,82 USD | **3 751,72 USD** |

Contrôle : capital initial + PnL des positions − intérêts = capital final,
écart numérique inférieur à 0,000001 USD. Toutes les positions sont closes.
Les deux portefeuilles peuvent avoir des tailles et des réentrées différentes
après un veto, d'où 42 positions contre 41 : aucun TOP11 ajouté.

### Mois, sans réinitialiser le capital

| Mois | Oracle seul | Avec veto GPT valides |
| --- | ---: | ---: |
| Janvier | +12,00 % | +11,79 % |
| Février | **−23,02 %** | **−16,39 %** |
| Mars | +1,77 % | +0,36 % |
| Avril, queue d'expiration uniquement | 0,00 % | 0,00 % |

Ces rendements mensuels se composent, ils ne s'additionnent pas. L'amélioration
provient de février, **pas d'un gain systématique chaque mois**. Les dernières
entrées effectives des deux bras sont le 20 février et les dernières sorties le
7 mars. Les gardes natives n'ont pas été forcées pour investir chaque jour ;
le test des 60 séances ne signifie donc pas 60 journées d'achats effectifs.

## Quels veto ont réellement changé un achat ?

26 couples BEARISH, sur 13 titres, ne signifient pas 26 pertes évitées. Seuls
trois correspondent à une position ouverte à l'open suivant dans Oracle seul :

| Décision J | Titre | Fait relevé dans les textes | PnL de cette position dans Oracle seul |
| --- | --- | --- | ---: |
| 21 janvier | TSLA | Revue/retrait d'aides et obligations favorables aux véhicules électriques | −10,21 USD |
| 6 février | AOSL | Marges et résultats dégradés, nouvelle baisse de marge attendue | −63,35 USD |
| 7 février | GPRE | Perte trimestrielle, revenus et marge éthanol dégradés | −88,93 USD |

Les autres veto interviennent sans nouvel achat correspondant dans la baseline
(contraintes natives ou titre déjà détenu, par exemple). Leurs PnL ne doivent pas
être inventés. **−162,49 USD sur ces trois positions n'est pas la différence
causale totale de portefeuille** : le capital libéré, le sizing et les décisions
ultérieures changent aussi. L'écart apparié final reste +242,00 USD avant API.

Diagnostic individuel distinct : 507 trajectoires techniquement qualifiées,
93 écarts prochain open >3 % exclus de ce seul diagnostic. Parmi les 20 cas
BEARISH qualifiés, 4 atteignent quand même TP20 avant SL5 ; parmi les 21 BULLISH,
seuls 3 le font. Ces petits nombres ne constituent donc pas un classifieur
LONG/SHORT établi et n'autorisent pas un filtre « acheter seulement BULLISH ».
Ces contrôles futurs n'ont pas sélectionné les candidats du portefeuille.

## Limites et décision

Textes insérés du 13 au 26 mai 2026 : aucune preuve locale de leur version
disponible en 2025. Date de publication seule utilisée pour cette exploration.
Connaissances du LLM postérieures au trimestre ; risque de mémorisation non
éliminé. Univers statique, références d'émetteur et secteurs actuels, vintage
macro non certifié. 18 réponses invalides sur 213, trois achats directement
concernés, pas de nouveau holdout indépendant ni revue humaine indépendante.

**À retenir : indice rétrospectif de réduction de certaines pertes, pas preuve
de performance prédictive.** Pas d'entraînement, SQL écrit, ordre courtier,
modification de modèle/batch/config ni activation en production. La suite utile,
si autorisée séparément, serait une observation prospective en shadow sur les
versions archivées à leur arrivée, avec les mêmes règles, pas une optimisation
des seuils sur ce trimestre ni une dépense jusqu'au plafond sans nécessité.

## Traçabilité

Run : `artifacts/research/us_news_gpt_q1_2025/20261014-v2`.

- `analysis.json`, `assessments.json`, `usage.json` et `api/` : réponses/coûts/proofs.
- `q1-results.json` : synthèse finale ; le `report.json` originel reste celui de
  la préparation à zéro appel, volontairement inchangé.
- `veto-impact.json` : 26 veto et présence/absence d'ouverture dans la baseline.
- `ORACLE_ONLY/` et `GPT_VALID_BEARISH_VETO/` : courbes, trades, décisions et journaux.
- `paid-completion-audit.json` : audit hors ligne réussi, pas une seconde revue
  scientifique indépendante. Empreintes, citations reparsées, dépenses, TP/SL,
  absence de renforcement et réconciliation vérifiés.

65 tests isolés réussis. Un premier lancement ciblé avec couverture globale a
terminé les tests mais échoué sur le seuil de couverture de toute l'application ;
relance isolée sans couverture globale : **65 passed**, sans changer les tests.
Scripts dédiés `us_news_gpt_q1_2025_run.py`, `..._continue.py`, `..._evaluate.py`
et `..._audit.py` dans `scripts/research/` ; aucune nouvelle entrée de production.
