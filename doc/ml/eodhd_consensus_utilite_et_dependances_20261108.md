# Audit avant résiliation EODHD — consensus US et dépendances fournisseur

Audit terminé le 8 novembre 2026. Aucun abonnement, batch, modèle ou compte
modifié. Aucune écriture SQL, nouvelle inférence, requête fournisseur ou appel LLM.
Documentation publique EODHD consultée pour distinguer les produits Calendar/News
des cours EOD : https://eodhd.com/pricing et
https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits.

## Conclusion

Pas de gain directionnel démontré par les règles de consensus favorables testées.
Les taux gagnants LONG sont inférieurs au témoin admissible sans filtrage positif
des mêmes données. Les TOP10/20/50 disponibles ne confirment pas d'avantage.
Cela ne démontre pas l'inutilité universelle du consensus : historique court,
répétitions par titre, un seul départ mûr H20, conventions fournisseur non résolues.
Le consensus seul ne justifie pas actuellement son maintien comme filtre de
trading. Il reste une archive prospective potentiellement utile à la recherche.

L'annulation totale n'est cependant pas neutre pour l'application : macro US
réseau, consensus US/FR, IPO US, barres FR et corporate actions FR conservent
des routes EODHD. Il faut distinguer cette dépendance logicielle des droits
effectifs d'un abonnement Calendar/News, qui ne sont pas un abonnement cours EOD.

## Données et règles figées

- Inventaire SQL global : 8 993 093 lignes, 5 750 symboles, snapshots du
  11/10 au 07/11/2026 ; beaucoup de périodes fiscales, pas autant de signaux.
- Univers courant : `config/univers_batch/univers_filtred_tradable.txt`, 1 790 titres.
  Extraction bornée `0q`, périodes fournisseur du 01/06/2026 au 31/03/2027 :
  106 067 lignes, 1 725 titres. 33 875 décisions sur 20 séances d'entrée
  du 12/10 au 06/11. Cutoff réel figé : 08/11/2026 20:47:46.927914 UTC.
- Horloge conservatrice : maximum observation, disponibilité, ingestion et fin
  de run COMPLETED, strictement avant l'ouverture ; fraîcheur 4 jours.
  Ancrage fiscal le plus récent à ±100 jours, puis dernier snapshot disponible.
- Contrôle normalisation/hash brut, identité symbole/période/0q, reçu achevé et
  fourchettes basse/moyenne/haute. 33 875 lignes contrôlées, zéro échec brut/reçu.
  Ce contrôle technique ne certifie pas les conventions économiques.
- EPS : ≥3 analystes. EPS30 = (eps_current − eps_30d_ago)/abs(eps_30d_ago),
  dénominateur non nul. Révisions30 = (up30 − down30)/(up30 + down30), zéro si
  aucun changement ; une donnée manquante n'est jamais convertie en zéro.
- Revenus observés : changement de moyenne entre deux vrais snapshots `0q` de
  même période, connus avant deux ouvertures successives, nombre déclaré
  d'analystes inchangé et ≥3, moyennes positives et fourchettes cohérentes.
  Nombre inchangé ne signifie pas les mêmes analystes identifiés.
- Favorable LONG = indicateur strictement positif ; zéro neutre. Trois règles
  séparées, aucun apprentissage, mélange, poids ou seuil optimisé sur les résultats.
- Prix : Alpaca SIP split uniquement, OHLC strictement positifs et cohérents,
  non remplis, instrument_id stable, pas de rupture connue. Volume nul ne supprime
  pas un cours OHLC valide. Aucun fallback EODHD, Yahoo ou prix inventé.
- H5/H10/H20 = cinq/dix/vingt séances officielles, entrée à l'ouverture de la
  première séance admissible. 16/11/1 dates mûres pour EPS/révisions ; revenus
  15/10/0 dates. Absences de prix conservées comme absences, pas comme pertes.

## Taux gagnant : LONG TP10/SL10, frais inclus

Ce diagnostic par signal n'est pas un portefeuille Winner : pas de capital partagé,
levier, dimensionnement, frais de financement ni interdiction de doublons détenus.
Entrée à l'ouverture, TP +10 %, SL −10 %, sinon vente à la clôture H. Si les
deux barrières sont touchées dans la même bougie daily, SL prioritaire ; gaps
défavorables conservés. Frais forfaitaires 0,16 point de rendement aller-retour.
Un gagnant = rendement de cette opération après ces frais > 0. Ce n'est ni
« TP touché » seul, ni « clôture H en hausse », ni une vente au sommet.

| Signal favorable | H5 : gagnants / observations | H10 | H20 |
| --- | ---: | ---: | ---: |
| EPS30 positif | 56,30 % / 8 572 | 60,52 % / 5 813 | 60,65 % / 526 |
| Révisions30 positives | 55,31 % / 9 254 | 60,09 % / 6 407 | 58,00 % / 619 |
| Hausse observée du consensus revenus | 58,19 % / 1 069 | 62,57 % / 839 | aucun cas mûr |

Pour le témoin révisions30 (tous les cas avec cet indicateur admissible, sans
retenir seulement les positifs) : 60,04 % / 65,06 % / 63,90 % à H5/H10/H20.
Effectifs témoins : 21 574 / 14 852 / 1 349. Les témoins EPS30 donnent
60,06 % / 65,09 % / 63,87 % ; revenus 59,59 % / 64,60 % / non disponible.
Les comparateurs concernent la même disponibilité technique de chaque indicateur.
Ils ne sont pas des backtests de portefeuille cumulés ni un contrôle causal de
secteur, momentum, capitalisation et régime.

Sans chevauchement de détention pour un même symbole, révisions30 favorables :
51,20 % H5 (2 340 cas), 54,36 % H10 (1 203), 58,00 % H20 (619, une seule date).
La corrélation entre titres et entre marchés sur les mêmes dates demeure.

## Plus grand mouvement pendant la période

Autre cible : comparer le maximum des HIGH au maximum absolu de baisse des LOW,
par rapport au prix d'ouverture. Les égalités ne comptent pas comme dominance
haussière. Ce maximum peut survenir après un stop ; ce n'est pas le rendement
d'un trade et ne mesure pas un TP avant SL.

| Révisions30 favorables | H5 | H10 | H20 |
| --- | ---: | ---: | ---: |
| Pic absolu dominant haussier | 57,39 % | 60,11 % | 62,04 % |
| Témoin sans filtrage positif | 61,48 % | 65,04 % | 66,94 % |
| AUC quotidienne moyenne du score de révisions | 0,455 | 0,442 | 0,427 |

Les AUC EPS30 sont 0,460 / 0,454 / 0,447 et revenus 0,491 / 0,492 / non
disponible. Un résultat inverse sur ces quelques dates n'autorise pas à inverser
le filtre en production. H20 correspond seulement à l'entrée du 12 octobre.

## Contrôle du périmètre Oracle

Le batch H20 historique `model-factory-20261016180250-3b0515` et ses scores
octobre ne sont plus présents. Le seul batch ayant encore des scores sur la
fenêtre est le modèle annuel H10 2026 `model-factory-20261107222627-db80b0`.
Contrat/folds/empreintes/antériorité qualifiés, couverture ≥93 % ; 4 dates de
signal du 09 au 14 octobre, entrées 12/13/14/15 octobre. Classement effectué
avant disponibilité du consensus et prix futurs, aucun remplacement par N+1.
Historique de disponibilité physique des scores non certifié : contrôle
rétrospectif causal du modèle, pas preuve de trading exécuté à ces dates.

LONG TP10/SL10, révisions30 strictement positives :

| Périmètre | H5 | H10 | H20 |
| --- | ---: | ---: | ---: |
| TOP10 | 19,05 % (21 cas, 8 titres) | 9,52 % (21 cas) | 20,00 % (5 cas) |
| TOP20 | 16,33 % (49 cas, 16 titres) | 4,08 % (49 cas) | 9,09 % (11 cas) |
| TOP50 | 14,66 % (116 cas, 37 titres) | 9,48 % (116 cas) | 3,85 % (26 cas) |

Témoins TOP20 sans sélection positive : 23,73 % H5 (59), 13,56 % H10 (59),
21,43 % H20 (14). H5/H10 seulement quatre dates, H20 une seule. Les titres
reviennent plusieurs jours, TOP10/20/50 sont imbriqués. Il n'y a pas d'avantage
démontré sur notre périmètre Oracle ; les effectifs ne permettent pas de
déclarer définitivement le consensus fiable ou inutile par titre.

## Dépendances EODHD hors sentiments

Configuration du dépôt vérifiée ; pas une certification d'installation des
tâches Windows ni un test des droits actuels de l'abonnement.

| Fonction / batch | État configuré | Fournisseur / conséquence |
| --- | --- | --- |
| `eodhd_consensus_snapshot` US | activé P1 recherche | EODHD `/calendar/trends`, seul fournisseur |
| `eodhd_ipo_calendar_sync` US | activé P2 recherche | EODHD calendrier IPO |
| `fr_consensus_snapshot` | activé P3 recherche | EODHD Trends, pas Yahoo |
| `fr_daily_bars_sync` | activé P0 recherche | EODHD `/eod`, publication staging SQL |
| `fr_corporate_actions_sync` | activé P0 recherche | EODHD `/div` et `/splits`, preuves publiques annexes |
| Régime macro US | activé | SQL d'abord ; `market_regimes.macro_provider: eodhd` pour réseau volatilité VIX/VIX9D/VXN/VIX3M/MOVE ; taux 10 ans routé FRED |
| Pipeline US cours / B3 backfill | Alpaca | `market_data.bars_provider: alpaca`, pas EODHD principal |
| Intraday US | Alpaca SIP | `intraday_backfill.provider: alpaca` |
| Pipeline US étape 2 | défaut Finnhub | EODHD reste un choix manuel possible, pas le défaut du batch |
| Pipeline US earnings | Finnhub | étape 5 et ancrage partagé, pas EODHD |
| Pipeline US étape 13 | Alpaca selon bars_provider actuel | factory corporate actions sélectionne Alpaca |
| Batch US corporate actions autonome | Business Quant + Alpaca | distinct de l'étape 13 |
| `market_cap_sync` | SEC puis Finnhub | calcul actions × cours, pas EODHD principal |
| `daily_bars_sync` autonome | Business Quant | versions raw, pas upsert canonique ; distinct import Alpaca pipeline |
| Options, borrow, ouverture US | Alpaca | EODHD n'est pas la source principale de CALL/PUT/OI |
| `public_macro_snapshot_sync` | BLS + Fed | distinct du fournisseur des indices de volatilité du régime |
| Batchs CN | pas EODHD principal | Baostock/Akshare/Tushare/local selon batch activé |

La préférence de lecture `market_data.daily_bars_preferred_source: eodhd` reste
configurée : elle favorise des lignes EODHD déjà stockées lors des doublons.
Elle ne télécharge rien et ne rend pas un cours ancien à jour. Dernier daily
EODHD en SQL : 16/10/2026 ; SIP : 06/11/2026. Ne pas confondre préférence de
lecture et fournisseur de collecte.

Dépendances facultatives : récupération de trous intraday Winner, dans l'ordre
Alpaca SIP → Yahoo → EODHD ; ancienne popin générique de graphiques EODHD puis
Stooq. Les popins récentes du pipeline lisent SQL directement. CLI fondamentaux
et réparation Oracle peuvent encore appeler EODHD lorsqu'invoqués explicitement.

Hors périmètre demandé mais à préserver dans la décision : l'étape 8 collecte
les news EODHD même si le batch autonome `eodhd_news_ingestion_sync` est désactivé.
Le consensus peut nourrir le LLM, mais `llm_directional_filter.enabled: false` ;
le filtre options actif ne lit pas le consensus. Aucun avantage de trading actif
ne disparaîtrait de ce filtre options avec l'arrêt de Trends.

## Artefacts et validation

- Actif terminé : `artifacts/research/us_eodhd_subscription_audit/20261108-v5`.
- `report.json`, `comparison.csv`, `panel.parquet`, snapshots, `dependencies.json`,
  `review.json`. Tous les contrôles de maturité/absence sont conservés.
- 30 parcours relus par arithmétique indépendante, sélection SHA256 de
  symbole/date avant consultation du résultat ; 36 synthèses positives vérifiées.
  Même assistant, pas une revue humaine indépendante. Trois tests passent.
- v1 conservé : extraction réussie, ancien batch Oracle absent ; v2 reprend
  l'extraction et le H10 existant ; v3/v4 corrections de types SQL Decimal/null
  puis cible booléenne sklearn. v5 réutilise le panel v4 sans changer données,
  signaux ou issues, corrige seulement la synthèse AUC. Aucun résultat perdu
  transformé en résultat favorable, aucune ancienne archive écrasée.

Réserves sémantiques EODHD maintenues : devise absente de Trends, base EPS
GAAP/non-GAAP/basic/dilué non identifiée, fiscalité normalisée au mois,
contributeurs non identifiés. Les ratios observés ne lèvent pas ces réserves.
Pas de promotion des données ni d'autorisation de trading issue de cet audit.
