# Audit étendu SIP / barres locales US — janvier à septembre 2026

Réalisé le 11 octobre 2026 à la demande de l'utilisateur. **Audit terminé, sans écriture SQL, correction de cours, changement de fournisseur ou entraînement.**

## Conclusion

Alpaca SIP gratuit a servi l'historique journalier de **1 692 des 1 790 titres** de l'univers demandé. L'accord de prix avec les barres locales EODHD est excellent pour la grande majorité des observations. **Le remplacement intégral sans traitement des exceptions n'est néanmoins pas validé** : 98 historiques absents, conventions d'ajustement différentes et anomalies ponctuelles de prix/volume restent à qualifier.

Cet audit étend l'[audit de 24 titres et sensibilité Oracle](us_daily_alpaca_eodhd_oracle_audit.md). Il ne recalcule pas les scores Oracle sur l'univers complet et ne démontre pas l'équivalence économique des backtests.

## Protocole et données

- Univers figé avant téléchargement : `universe-file:univers_filtred_tradable.txt`, résolu vers `config/univers/univers_filtred_tradable.txt`. 1 790 titres. Empreinte du fichier et liste complète archivées dans `protocol.json`.
- Période inclusive : 2026-01-01 à 2026-09-30 ; **187 séances US** selon le calendrier du projet, sans fallback lundi–vendredi.
- Table réellement comparée : **`alpha_trade.stock_bars_daily`**, appelée « stock_bars » dans la demande.
- Instantané local pris avant appels Alpaca : 332 219 lignes. Toutes portent `data_source=eodhd_eod`, `data_adjustment=split` ; 332 214 non remplies et cinq `is_filled=1`.
- SHA256 de l'instantané parquet : `d54c2614207a6c73743c0d89cbb87b2f71da610f478bbdd5da376ff9e4d5061d`.
- Alpaca compte `default`, `feed=sip`, `timeframe=1Day`, `adjustment=split`, `asof=-`, bornes temporelles explicites. 72 lots de 25 titres au maximum, pagination, cache par lot et progression avec reprise.
- Les jours Alpaca sont convertis en date New York. Aucun remplissage, remapping ou suppression de titre silencieux. Permissions/rate limit/erreurs réseau arrêtent l'audit ; un symbole invalide est isolé par subdivision du lot.
- Contrôle des OHLC positifs, finis, high/low cohérents, dates de séance, unicité des clés. Comparaison primaire limitée aux barres communes locales non remplies et déclarées split. Les exclusions sont conservées.
- Connexions MySQL en `SET TRANSACTION READ ONLY`. Toutes les écritures sont des fichiers de recherche ; aucun INSERT, UPDATE, DELETE ou migration.

## Couverture réelle

| Mesure | Résultat |
|---|---:|
| Titres demandés / présents localement | 1 790 |
| Titres avec au moins une barre SIP | 1 692, soit 94,525 % |
| Titres SIP avec les 187 séances | 1 644 |
| Titres SIP avec historique partiel | 48 |
| Titres sans aucune barre SIP | 98 |
| Barres SIP reçues | 313 410 |
| Barres communes comparées | 313 408 |
| Barres locales sans équivalent SIP | 18 811 |
| Barres SIP absentes localement | 2 : IAC, 1er et 2 juin 2026 |
| Échecs techniques / HTTP | 0 |
| Barres communes exclues du contrôle de prix | 0 |

Une réponse vide n'est pas classée comme succès de couverture. Aucun résultat ne garantit qu'un titre aurait dû coter toutes les 187 séances : le référentiel historique d'identité/listing n'est pas qualifié par cet audit.

### Les 98 absences

Le référentiel **actuel** des actifs Alpaca (consulté en lecture seule) identifie **96 des 98 titres comme OTC**. KYOCY et TOELY n'ont pas été retrouvés dans les listes actives/inactives consultées. Il ne faut pas inventer une cause certaine pour ces deux cas.

Les 98 noms et métadonnées sont dans `coverage-with-current-assets.csv`. Le champ courant `tradable=true` de certains OTC ne prouve pas que leur historique est disponible via le flux SIP. La documentation distingue l'accès OTC du SIP. Ces titres ne sont pas retirés de l'univers et aucune source de fallback n'est activée.

### Identités / aliases

Dans le résultat primaire, `asof=-` empêche Alpaca de remapper implicitement les anciens tickers. Un contrôle distinct avec `asof=2026-09-30` a récupéré **436 correspondances de dates locales supplémentaires** sur des titres partiellement couverts, notamment AGNT, AHRT, CVSA, EFOR, MRSH, ONT, P et RYZ.

Il reste 556 lignes locales sans SIP sur des titres ayant au moins une barre SIP ; 436 sont donc potentiellement expliquées par le remapping. **Elles ne sont pas fusionnées dans le résultat primaire** : continuité d'identité à qualifier auparavant. Le remapping peut aussi retirer des historiques d'anciens tickers (EXPI dans ce contrôle) : ne pas l'activer indistinctement.

## Prix : très proche dans la grande majorité, pas partout

Écart absolu = `abs(prix_SIP / prix_local - 1)`. 1 bp = 0,01 %. Quantiles empiriques, pas intervalles de confiance.

| Champ | Médiane | 95e percentile | 99e percentile | Observations au-delà de 1 % |
|---|---:|---:|---:|---:|
| Ouverture | 0 % | 0 % | 0,0338 % | 0,4828 % |
| Plus haut | 0 % | 0,0128 % | 0,0563 % | 0,4598 % |
| Plus bas | 0 % | 0,0122 % | 0,0553 % | 0,4569 % |
| Clôture | 0 % | 0 % | 0 % | 0,4512 % |

- **99,142 %** des clôtures sont exactement identiques dans les valeurs numériques lues.
- **98,813 %** des couples titre/date ont leurs quatre OHLC à moins de 0,1 % ; **99,501 %** à moins de 1 %.
- 1 563 couples titre/date, sur **148 titres**, ont au moins un prix divergent de plus de 1 %. Liste intégrale conservée, pas exclue des statistiques globales.
- Les moyennes absolues (environ 0,284–0,286 % selon le champ) sont tirées vers le haut par ces cas ; communiquer uniquement la médiane masquerait des risques importants.
- Aucun écart OHLC supérieur à 1 % dans les 34 713 couples comparés de septembre. Cela ne résout pas rétroactivement les divergences plus anciennes.

### Grands écarts : contrôle brut versus ajusté

Vingt titres ayant les plus grands écarts ont fait l'objet d'un second téléchargement **SIP raw**. Contrôle diagnostic borné, sans correction ou exclusion a posteriori.

| Titre | Exemple d'écart / constat |
|---|---|
| DD | 2026-05-26 : close local 49,46 ; SIP split 148,38. Facteur 3 ; médiane de l'écart de close SIP raw/local = 0. |
| HON | Facteur SIP split/raw médian 2 ; médiane raw/local = 0, mais des jours restent divergents. |
| KLAC | Facteur SIP split/raw médian proche de 0,1 ; prix locaux et raw proches sur la majorité des dates. |
| MNST, MLI, SFBS | Facteurs médians proches de 0,5 ; différences de convention/vintage à vérifier. |
| RUSHA, SNEX | Facteurs médians proches de 2/3. |
| AVB, CLBK, ANAB, AZN, BDX, REZI, ATRO, LBRDK, LEG | Des écarts importants persistent avec raw ; ne pas tout attribuer aux splits. |

Pour DD, 106 dates ont un écart de clôture supérieur à 1 % avec split contre 12 avec raw ; HON 121 contre 7 ; KLAC 106 contre 5. Cela soutient une **différence de convention/vintage d'ajustement**, pas la conclusion automatique « SIP faux » ou « EODHD faux ».

Les barres locales peuvent avoir été ajustées avant des opérations ultérieures, les barres SIP lors du téléchargement actuel. Sans contrôle des opérations et versions disponibles lors de l'ingestion, on ne peut pas arbitrer les prix corrects. Le paramètre `asof` concerne le remapping des tickers, pas un historique PIT de toutes les révisions de prix.

Les grands écarts ne sont donc pas acceptables comme des « petites différences normales ». Qualification nécessaire avant remplacement automatique ou rejeu historique.

## Volume et VWAP

Sur les 313 222 couples avec volume local strictement positif :

- Ratio SIP/local médian **1,00006595**, soit environ +0,0066 %.
- 95e percentile du ratio **1,00282573**, soit environ +0,2826 %.
- **96,059 %** des volumes SIP/local s'écartent d'au plus 1 %.
- 186 volumes locaux nuls pour une barre commune, contre zéro volume SIP nul. Ils ne sont pas divisés par zéro ni cachés.

Exceptions sérieuses : ADEA possède un volume local **745** les 23–25 février et le 9 mars, alors que SIP retourne environ 1,64 à 2,74 millions ; WLY présente un volume local **995** sur plusieurs journées où SIP retourne environ 379–410 milliers. SHEL/2026-02-25 : local 62 588, SIP 7 075 179. Ce sont des **valeurs locales suspectes**, non corrigées ici ; obtenir la provenance/raw et qualifier avant d'imputer la faute au fournisseur ou à l'ingestion.

Le VWAP local correspond au proxy `(high + low + close)/3` sur tous les couples comparés. Le VWAP SIP est celui du flux : ce n'est pas une comparaison de deux champs sémantiquement identiques. Écart médian observé 0,2009 %, 95e percentile 0,8577 %, sans conclure à une erreur de source. Une bascule doit décider explicitement de cette convention pour les features du modèle.

## Décision opérationnelle

**GO pour préparer une substitution SIP sur le périmètre qualifié ; pas de GO pour écraser toutes les barres locales ou résilier toutes les dépendances EODHD.**

Avant bascule :

1. Qualifier splits/vintages et anomalies persistantes des 148 titres signalés, avec priorité aux facteurs importants et aux volumes quasi figés.
2. Qualifier les alias historiques, sans considérer automatiquement les histoires remappées comme la même identité économique.
3. Décider du traitement des 98 historiques absents : source distincte autorisée ou périmètre explicitement limité. Aucun fallback implicite IEX/OTC.
4. Vérifier les scores/classements Oracle sur l'univers complet avec convention OHLCV/VWAP identique ; l'audit d'inférence précédent ne portait que sur 23 titres.
5. Maintenir les autres dépendances EODHD (France, news) tant qu'elles ne disposent pas de remplaçant qualifié.

Accord statistique entre deux fournisseurs ne constitue pas une validation indépendante de marché. Aucun résultat de rendement ou de précision D1/D10 n'est calculé dans cette expérience.

## Fichiers et reprise

Dossier : `artifacts/research/us_sip_daily_universe/audit-20260101-20260930-20261011-v1`.

- `protocol.json`, `local-snapshot.json`, `local-bars.parquet` : univers, configuration et instantané avant téléchargement.
- `cache/chunk-*.json`, `sip-bars.parquet` : réponses historiques SIP et barres normalisées, sans clés d'API.
- `progress.json` : `COMPLETED` ; zéro échec technique.
- `report.json` : global, source et mois.
- `comparison-all.parquet` : toutes les correspondances et écarts, y compris les lignes non communes.
- `coverage-by-symbol.csv`, `coverage-with-current-assets.csv`, `missing-pairs.csv` : absences et métadonnées actuelles, non PIT.
- `price-outliers-above-1pct.csv`, `price-by-symbol.csv`, `excluded-pairs.csv` : cas à qualifier.
- `adjustment-diagnostics.json`, `diagnostic-raw-split-local.csv` : contrôle raw/split des vingt principaux cas.
- `alias-diagnostics.json`, `diagnostic-asof-remapping.json` : diagnostic séparé des changements de ticker.

Commandes :

```powershell
python -u -m scripts.research.us_sip_daily_universe_audit --output-dir artifacts/research/us_sip_daily_universe/audit-20260101-20260930-20261011-v1
python -u -m scripts.research.us_sip_daily_adjustment_diagnostics --output-dir artifacts/research/us_sip_daily_universe/audit-20260101-20260930-20261011-v1
```

La reprise conserve l'instantané local et les réponses en cache ; elle ne relit pas une base ayant changé pour mélanger les vintages. Choisir un nouveau dossier pour un nouvel audit. Dix tests ciblés passent (premier audit et audit étendu) avec `--no-cov`.

## Sources de référence

- [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) : SIP consolidé, accès historique à plus de 15 minutes, OTC et remapping.
- [Historical Stock Bars](https://docs.alpaca.markets/us/reference/stockbars) : `adjustment`, `feed`, `asof`, pagination.

Les constats chiffrés proviennent des réponses et instantanés archivés, pas des promesses de la documentation.
