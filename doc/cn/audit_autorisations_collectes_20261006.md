# CN — Audit des autorisations des collectes planifiées

Date de vérification : 6 octobre 2026. Périmètre : configuration et chemins de code actuels, conditions publiques des fournisseurs. Audit documentaire et technique, pas consultation juridique ni garantie d'absence de litige.

### Décision appliquée après l'audit — 6 octobre 2026

Sur GO utilisateur, les trois collecteurs externes ont été suspendus par précaution dans `batch.yaml` : `cn_oracle_prospective_daily` (`BLOCKED_BAOSTOCK_RIGHTS`), `cn_dragon_tiger_after_close` et `cn_dragon_tiger_before_open` (`BLOCKED_SSE_SZSE_AUTOMATION`), tous avec `enabled: false`. Les raisons et étapes de déblocage sont visibles dans la page Batch. Ces statuts bloquent l'exécution même si `enabled` est remis à true seul ; les runners exigent `RESEARCH_ONLY`. Le catalogue passe donc de 6 à **3 batchs CN activés**. L'inventaire ci-dessous décrit l'état au moment de l'audit, avant cette décision.

Aucune donnée ni archive n'a été supprimée ; aucune tâche Windows ni aucun processus en cours n'a été modifié. Contrôle qualité et appariement restent actifs, mais peuvent signaler l'absence de nouvelles collectes. Les suspensions ne constituent pas un constat d'illégalité.

## 1. Conclusion opérationnelle

Le catalogue CN contient **13 batchs, dont 6 activés dans la configuration**. Neuf sections sont dans `batch_cn.yaml` et quatre dans `batch.yaml`. Ne lire que le premier fichier aurait manqué les collectes Dragon/Tiger et le propriétaire quotidien des barres, D9.

Les collectes externes actuellement activées sont :

- `cn_oracle_prospective_daily` : SDK BaoStock, puis calcul Oracle local ;
- `cn_dragon_tiger_after_close` et `cn_dragon_tiger_before_open` : publications officielles SSE et SZSE.

Les trois autres batchs activés sont une sauvegarde, un contrôle local et un appariement local. Ils ne téléchargent pas de nouvelles données fournisseur.

**Aucune interdiction explicite équivalente à celle relevée pour l'accès automatisé Yahoo FR n'a été établie pour ces trois collecteurs dans le périmètre examiné. Cela ne certifie pas tous leurs usages.** Les téléchargements non commerciaux SSE/SZSE sont expressément prévus ; BaoStock documente l'API et le stockage local pour analyse. Les droits d'utilisation professionnelle/live, de redistribution et certaines modalités d'automatisation restent à qualifier.

Recommandations : conserver le périmètre interne non commercial seulement si c'est bien l'usage réel ; ne pas présenter ces sources comme « libres pour tout usage » ; obtenir une confirmation écrite avant promotion professionnelle/live. Si l'exigence est une autorisation écrite couvrant exactement chaque accès automatisé, suspendre par précaution les trois collecteurs externes jusqu'à cette confirmation. Cette dernière option est une mesure de prudence, **pas un constat d'illégalité**.

Cet audit n'a modifié aucun code, aucune configuration, aucune tâche Windows et aucune donnée SQL. Il n'a exécuté aucun collecteur de marché. Les seules requêtes externes nouvelles ont servi à lire la documentation et les conditions publiques.

## 2. Grille de lecture

Il faut distinguer : accès technique, autorisation de collecte, stockage, analyse/ML, usage professionnel ou trading, publication et redistribution. Un accès HTTP réussi, un SDK gratuit, une licence MIT, une étiquette `RESEARCH_ONLY` ou une quarantaine ne règlent pas à eux seuls ces droits.

- **LOCAL** : pas de nouvel accès externe ; les droits des données d'origine continuent à compter.
- **RECHERCHE SOUS CONDITIONS** : base documentaire favorable au périmètre indiqué, sans extension automatique au live/commercial.
- **À CONFIRMER** : portée de l'autorisation insuffisamment claire ; absence de preuve n'est pas preuve d'interdiction.
- **DÉSACTIVÉ** : configuration inactive, sans certification de ce que ferait une exécution manuelle ou d'anciennes collectes.

Le statut `enabled` décrit les fichiers, non une vérification des tâches réellement installées ou des processus en cours.

## 3. Inventaire exhaustif du catalogue

| Batch | Activé | Source effective / activité | Qualification et mesure proposée |
|---|---:|---|---|
| `cn_db_backup` | Oui | MySQL local `alpha_trade_cn` → `backups/cn/db` | LOCAL. Maintenir ; ne pas partager les dumps sans droits sur leur contenu. |
| `cn_master_calendar_sync` | Non | BaoStock, référentiel/calendrier | DÉSACTIVÉ, doublon D9. Même réserve de droits BaoStock si réactivé. |
| `cn_daily_market_data_sync` | Non | BaoStock, OHLCV/facteurs/indices | DÉSACTIVÉ, doublon D9. Ne pas créer un deuxième collecteur canonique. |
| `cn_historical_backfill` | Non | BaoStock, collecte historique | DÉSACTIVÉ. API documentée ; vérifier volume, règles d'accès et portée de réutilisation avant nouveau backfill. |
| `cn_baostock_smoke` | Non | BaoStock, essai borné | DÉSACTIVÉ. Un smoke valide la technique, pas une licence. |
| `cn_staging_quality_daily` | Non | Contrôle local | LOCAL, remplacé par 17-C. |
| `cn_daily_quality_17c` | Oui | Tables CN et fichiers D6/D9/D10 | LOCAL. Pas de nouveau téléchargement. |
| `cn_akshare_enrichment` | Non | AKShare ; liste d'endpoints vide | DÉSACTIVÉ. Qualifier chaque fournisseur sous-jacent avant activation ; MIT ne couvre pas les données tierces. |
| `cn_tushare_optional` | Non | API Tushare, futur connecteur | DÉSACTIVÉ. Conditions personnelles/non commerciales restrictives ; clarifier stockage, traitement et ML avant usage. |
| `cn_dragon_tiger_after_close` | Oui | SSE principal + STAR, SZSE | RECHERCHE SOUS CONDITIONS. Téléchargement non commercial prévu ; automatisation exacte et promotion live à confirmer. |
| `cn_dragon_tiger_before_open` | Oui | Mêmes publications officielles, réobservation | Même qualification. Pas de fournisseur Eastmoney dans ce chemin quotidien. |
| `cn_oracle_prospective_daily` | Oui | BaoStock → tables canoniques CN → LightGBM local figé | RECHERCHE API DOCUMENTÉE ; périmètre professionnel/live À CONFIRMER. D9 est le propriétaire quotidien des données. |
| `cn_dragon_tiger_daily_match` | Oui | Appariement de fichiers Oracle et snapshots déjà collectés | LOCAL. Le champ `provider` mentionne SSE/SZSE, mais cette étape ne refait pas leur collecte. |

Les contrôles/sauvegardes locaux ne doivent pas être suspendus automatiquement parce qu'une source nécessite une clarification. Une restriction ultérieure de conservation devra toutefois être appliquée aussi aux copies et sauvegardes.

## 4. BaoStock : API officielle, mais pas licence universelle

### Chemin réellement exécuté

`service/market/cn_oracle_daily_15d9.py` appelle `prepare` et `run_all` de `dataIntegrityEngine/cn_sprint7c_incremental.py`. La collecte passe par le service BaoStock et son SDK dans `service/baostock/client.py`, avec `login()` et les requêtes documentées. Ce chemin ne scrape pas une page Eastmoney et n'utilise pas AKShare comme source des barres.

Les familles concernées sont le référentiel, le calendrier, les barres quotidiennes, les facteurs d'ajustement et les indices. Le stockage inclut notamment `cn_staging_rows`, `market_sessions`, `stock_bars_daily` et `instrument_adjustment_factors`. Les calculs Oracle ultérieurs sont locaux.

### Éléments documentaires

La [présentation officielle BaoStock](https://www.baostock.com/helpDocsHome?file=home.md) décrit une plateforme gratuite, des API Python et le stockage local pour analyse. Sa [page de disclaimer](https://www.baostock.com/disclaimer), version V1.0.0 obtenue le jour de l'audit, comporte une clause de propriété intellectuelle restrictive sur les contenus du site. Le protocole utilisateur lu concerne le **商城**, la place de marché technique : ne pas l'appliquer automatiquement à toute l'API de données. Ces textes n'établissent pas une licence universelle de production ou redistribution.

Lecture retenue : le téléchargement SDK et l'analyse locale ont une base documentaire positive. La portée exacte des restrictions générales du site sur les données SDK, les modèles entraînés et un usage live doit être confirmée. La gratuité seule n'y répond pas.

### Reproductibilité de la lecture

Le site est une application JavaScript ; une extraction HTML simple renvoie parfois seulement une coquille. L'audit a suivi ses propres ressources publiques :

1. page d'accueil → script `assets/index-DUQ-MKvt.js` ;
2. route `/disclaimer` → composant `assets/Disclaimer-g1HSkr2p.js` ;
3. appel de lecture utilisé par ce composant : `GET /articleMall/api/contract?contract_status=1&contract_type=5` ;
4. documentation : appel de lecture `POST /helpdocs/api/markdown/home.md`, sans création de contenu ;
5. protocole de la place de marché : `GET /articleMall/api/contract?contract_status=1&contract_type=1`.

Aucun compte, secret, contournement TLS ou contournement d'un refus d'accès n'a été employé. Les contenus n'ont pas été intégralement reproduits dans ce document. Les URLs des ressources compilées sont une preuve de méthode à cette date, pas des interfaces stables à intégrer dans l'application.

### Clarification à demander

Contact public : `baostock@163.com`. Décrire précisément : collecte quotidienne de l'univers CN par SDK depuis la France ; stockage privé SQL et sauvegardes ; nettoyage, facteurs, ML/backtests ; conservation après arrêt ; éventuel trading pour compte propre ; absence de redistribution. Demander aussi les limites d'appels et le régime des sorties/modèles dérivés. Ne pas supposer que « compte propre » est nécessairement non commercial.

## 5. SSE/SZSE : observations Dragon/Tiger officielles

### Conditions publiques

Les déclarations officielles de [SSE](https://www.sse.com.cn/home/legal/) et [SZSE](https://www.szse.cn/application/laws/) autorisent consultation et téléchargement à des fins non commerciales, sous réserve du respect de leurs déclarations et de la loi. Elles réservent leurs droits de propriété intellectuelle, interdisent de perturber leurs services et exigent une permission écrite pour les usages visant à vendre leurs contenus à autrui avec profit.

Cette base est favorable aux observations privées non commerciales. Elle ne nomme pas notre robot ni ne fournit un contrat API pour ses volumes ; elle ne doit pas être transformée en autorisation générale de diffusion, de vente ou de production. Le seul fait de viser un rendement pour compte propre ne permet pas ici de conclure définitivement sur la qualification commerciale.

### Endpoints et contenu

Dans `service/market/cn_dragon_tiger_pilot_15d2.py` :

- SSE principal : `https://query.sse.com.cn/marketdata/tradedata/queryAllTradeOpenDate.do` ;
- SSE STAR : `https://query.sse.com.cn/marketdata/tradedata/queryKCBTradeInfo.do` ;
- SZSE : `https://www.szse.cn/api/report/ShowReport/data`.

`service/market/cn_dragon_tiger_prospective_15d5.py` importe seulement `official_sse` et `official_szse`. Il conserve date, code, place, motif, empreinte et horodatage d'observation. Les noms et montants de sièges reçus par l'appel SSE sont supprimés avant persistance. Cette minimisation **ne vaut pas exemption de droits** sur les données reçues.

Les en-têtes actuels comportent un User-Agent générique et un Referer ; pas de mécanisme de résolution de CAPTCHA ou de rotation de proxy identifié dans ce chemin. Un tel en-tête ne constitue toutefois pas une autorisation. Respecter toute limitation ou refus ; ne pas augmenter pagination/parallélisme sans qualification. Les retries techniques ne doivent pas servir à forcer un accès refusé.

`service/market/cn_dragon_tiger_daily_15d10.py` lit les exports et appelle l'audit d'appariement : ce n'est pas un troisième collecteur externe. La qualification PIT est distincte des droits : `pit_usable=False` n'autorise ni n'interdit juridiquement une collecte.

## 6. Eastmoney, AKShare et Tushare : pas de promotion implicite

### Eastmoney : ancien POC, pas fournisseur des snapshots quotidiens

Le pilote historique 15-D2 possède aussi `vendor_eastmoney`, utilisé pour réconciliation. Son endpoint `datacenter.eastmoney.com` est distinct des deux fonctions officielles importées par le collecteur quotidien. Ne pas déclarer les batchs Dragon/Tiger actifs « Eastmoney » à cause de cet import de module.

Les [conditions Eastmoney](https://about.eastmoney.com/home/protocol), datées du 18 juillet 2025, réservent les droits sur leurs contenus et posent des restrictions sur la copie, la fourniture à des tiers et les produits dérivés des données de marché. Aucun droit spécifique à notre pilote n'a été retrouvé. Recommandation : **ne pas relancer la branche Eastmoney historique ni l'activer comme fallback sans autorisation adaptée**. Ce constat ne décide pas à lui seul du sort juridique des anciennes données ; ne rien effacer automatiquement.

### AKShare

Le [projet officiel](https://github.com/akfamily/akshare) indique un usage académique des données ; sa licence MIT porte sur le logiciel. Chaque endpoint dépend de sa source. Une source publique, un wrapper gratuit ou un test de schéma ne remplace pas la vérification des conditions du fournisseur. Garder `cn_akshare_enrichment` désactivé jusqu'à une qualification endpoint par endpoint, y compris la conservation et les dérivés.

### Tushare

L'[accord de service officiel](https://tushare.pro/document/1?doc_id=405) décrit une permission personnelle, non transférable, non commerciale, révocable et limitée dans le temps, avec une formulation de consultation personnelle. Ne pas déduire qu'un achat de points autorise toutes nos opérations SQL/ML ou un service commercial. Le connecteur reste désactivé ; demander une confirmation ou un contrat correspondant avant activation. Les contraintes techniques d'accès depuis la France sont une question séparée.

## 7. Actions proposées, sans changement réalisé

1. Conserver les sauvegardes, contrôles et appariements locaux.
2. Ne pas activer AKShare/Tushare ou relancer le POC Eastmoney sur la seule base de la gratuité.
3. Pour BaoStock, archiver une réponse fournisseur couvrant notre usage concret ; ne pas promouvoir la collecte vers un usage professionnel/live avant clarification.
4. Pour SSE/SZSE, limiter l'interprétation favorable aux observations internes non commerciales ; confirmer les modalités automatisées et les dérivés avant élargissement d'usage.
5. Si une suspension de précaution est décidée, viser les trois collecteurs externes nommés en conclusion, puis vérifier aussi les tâches Windows existantes. Modifier seulement YAML ne termine pas nécessairement un processus déjà lancé.
6. Futur garde-fou possible, à implémenter après GO : registre des sources et autorisations avec usage, endpoints, date/version, preuve, restrictions, limites, stockage/suppression, échéance et interdiction de fallback non qualifié.

Cet audit ne couvre pas exhaustivement chaque ancienne expérience CN, toutes les licences de dépendances, les conditions privées non communiquées ni toutes les obligations réglementaires d'un déploiement de trading. Aucun avis « aucun risque juridique » ne doit être déduit de l'absence d'une restriction trouvée dans ces pages.

## 8. Fichiers de référence inspectés

- `batch_cn.yaml`, sections CN de `batch.yaml` ; catalogue CN de `ihm/services/batch_management.py` ;
- `service/baostock/client.py`, `service/baostock/ingestion.py` ;
- `dataIntegrityEngine/cn_sprint7c_incremental.py` ;
- `service/market/cn_oracle_daily_15d9.py` ;
- `service/market/cn_dragon_tiger_pilot_15d2.py` ;
- `service/market/cn_dragon_tiger_prospective_15d5.py` ;
- `service/market/cn_dragon_tiger_schedule_15d6.py` ;
- `service/market/cn_dragon_tiger_daily_15d10.py`.

Pour la comparaison, voir [audit des collectes FR](../fr/audit_autorisations_collectes_20261006.md). Les verdicts FR ne doivent pas être transposés à une source CN différente.
