# Actualisation des fournisseurs de données Chine

## Décision

L’étude d’opportunité historique avait correctement identifié Tushare, RQData/Ricequant et Wind. La répartition des rôles doit être actualisée : **Tushare 10 000 points fournit déjà, via `report_rc`, les observations sell-side individuelles nécessaires à la reconstruction d’un consensus PIT**. RQData est donc un complément de validation et d’enrichissement, et non un prérequis au consensus.

## Comparaison actualisée

| Fournisseur | Apport différenciant | Tarif ou accès connu | Rôle recommandé |
|---|---|---|---|
| **Tushare Pro** | Prévisions sell-side individuelles, objectifs, ratings, Dragon and Tiger et événements de limites | 10 000 points : 1 000 CNY/an pour un particulier ; certaines familles séparées | **Source principale du POC** |
| **RQData / Ricequant** | Consensus agrégé, objectifs, ratings, analyst momentum, surprises et horodatages d’ingestion | Aucun prix public vérifiable ; abonnement et modules sur devis | **Essai puis validation complémentaire** |
| **CSMAR** | Prévisions analystes, recommandations, rapports, visites institutionnelles et bases académiques spécialisées | Devis ; accès souvent universitaire ou institutionnel | À utiliser via essai ou accès académique |
| **CNRDS** | Textes de rapports, médias financiers chinois et données alternatives | Accès principalement académique ou institutionnel | Source historique complémentaire |
| **Wind** | Couverture institutionnelle complète et support contractuel | Devis institutionnel, probablement hors budget POC | Exclu du POC personnel |
| **RESSET / SUNTIME** | Prévisions et recommandations complémentaires | Offre institutionnelle, tarif public non vérifié | Non prioritaire |
| **AKShare / BaoStock** | Prix, fondamentaux et données publiques | Gratuit | Ne pas utiliser comme source canonique PIT |

## RQData : apport réel

RQData apporte principalement :

- un consensus fournisseur déjà agrégé ;
- des objectifs de cours et ratings normalisés ;
- `consensus.get_analyst_momentum` ;
- `consensus.get_expect_prob` pour les surprises positives ou négatives ;
- `rice_create_tm` pour contrôler l’instant d’intégration ;
- une validation indépendante du consensus reconstruit depuis Tushare.

La documentation signale que certains modes peuvent intégrer des corrections historiques. Les paramètres de requête permettant de figer les valeurs historiques doivent être utilisés lorsqu’ils sont disponibles, puis audités avant tout backtest PIT.

## Tarif RQData

RQData ne publie pas de tarif fixe vérifiable pour les modules de consensus. L’offre payante est commercialisée sur devis. Un essai d’environ un mois est annoncé pour les données de base ; l’accès au consensus et aux données alternatives doit être demandé explicitement.

Contact publié par Ricequant :

```text
email     bd@ricequant.com
téléphone +86 755 2267 6337
```

Le devis doit être limité à :

```text
Marché       China A-shares
Usage        recherche personnelle non commerciale
Fréquence    daily
Historique   2010 à aujourd’hui
API          Python
Modules      consensus.get_comp_indicators
             consensus.get_price
             consensus.get_analyst_momentum
             consensus.get_expect_prob
             rapports analystes individuels
Budget       maximum 100 EUR/mois
```

## Gate d’achat

RQData ne sera acheté que si :

1. le module complet reste sous 100 EUR/mois ;
2. l’essai confirme la profondeur historique ;
3. les corrections historiques sont contrôlables de façon PIT ;
4. la couverture ou la stabilité dépasse le consensus Tushare reconstruit ;
5. une expérience OOS démontre un gain directionnel incrémental.

## Rôle des autres fournisseurs

CSMAR et CNRDS peuvent être supérieurs pour une recherche académique sur les textes, les analystes, les visites institutionnelles et les médias. Ils ne constituent pas actuellement un meilleur choix opérationnel que Tushare pour un POC personnel sous 100 EUR/mois. Ils doivent être considérés uniquement en cas d’essai ou d’accès universitaire.

Wind, RESSET et SUNTIME ne doivent pas être achetés pour le POC sans tarif public compatible et sans preuve que leur historique apporte une donnée absente de Tushare/RQData.

## Références

- [Tushare — données sell-side](https://tushare.pro/document/1?doc_id=291)
- [Tushare — points et tarifs](https://tushare.pro/document/1?doc_id=290)
- [RQData — consensus et données alternatives](https://www.ricequant.com/doc/rqdata/python/alternative-data)
- [RQData — présentation et demande d’essai](https://assets.ricequant.com/welcome/%E7%B1%B3%E7%AD%90RQData%E9%87%91%E8%9E%8D%E6%95%B0%E6%8D%AE%E8%A7%A3%E5%86%B3%E6%96%B9%E6%A1%88%E7%AE%80%E4%BB%8B.a528f1bd.pdf)
- [CSMAR — couverture officielle](https://csmar.com/en/)
