# Pilote de faisabilité des données de prêt de titres après Oracle

## Décision du 1er octobre 2026

**`SAMPLE_READY / BLOCKED_NO_PROVIDER_HISTORY`**. L'Oracle d'amplitude corrigé garde une AUC OOF de 0,7581, mais le rejeu directionnel D1/D10 reste à 0,4811. Le projet n'a toujours pas de panel historique point-in-time de frais d'emprunt et de quantité disponible. Le statut Alpaca courant, le short interest périodique et le short volume déjà présents ne permettent pas de tester cette hypothèse sur les neuf folds 2021–2025 ; le short volume ne mesure d'ailleurs pas les positions ouvertes ou le stock empruntable, comme le précise [FINRA](https://www.finra.org/rules-guidance/notices/information-notice-051019).

Le pilote est désormais **prêt à recevoir un extrait**, sans achat ni entraînement prématuré : [liste de 50 titres](borrow_pilot_50_symbols_20261001.csv) et harnais `work/borrow_pilot_20261001/audit_provider_sample.py`. La sélection prend dix titres dans chacun de cinq quintiles de liquidité historique, sous les conditions d'au moins 30 événements Oracle et deux années OOF. Elle utilise un hash déterministe pour choisir les titres, sans consulter leurs D1/D10 futurs. Elle contient **29 267 événements TOP20**, dont 6 416 D1 et 6 472 D10, répartis sur huit années et dix secteurs. Ces comptes de labels servent seulement à caractériser l'échantillon après sa sélection.

Cette liste sert à vérifier couverture, identité et disponibilité, **pas à conclure à un alpha**. Le choix parmi l'univers historique connu conserve ses biais de survivants ; demander séparément au fournisseur dix titres radiés avec identifiant permanent et dates de radiation pour auditer ce point.

## Extrait à demander, avant tout devis complet

Fournir les 50 titres du CSV pour **2018-07-05 à 2025-07-11**, idéalement dès 2016 pour calculer les variations retardées. Une ligne par titre, observation et version. Champs minimaux :

| Champ | Exigence |
|---|---|
| `symbol`, `security_id` | Ticker historique et identifiant permanent ; historique des changements de ticker et corporate actions. |
| `observation_at`, `available_at` | Horodatages avec fuseau/offset ; le second est la première disponibilité réelle au client, non la date d'un backfill actuel. |
| `borrow_fee_bps` | Taux et unité documentés : indicatif, nouveau prêt, prêt en cours, bid/ask ou coût effectivement exécutable. |
| `shares_available` | Quantité prêtable à l'instant observé, avec définition de l'univers des prêteurs. |
| `utilization_pct` | Facultatif pour le premier gate, recommandé avec `shares_on_loan` et `lendable_supply`. |
| versions/corrections | Horodatage de chaque correction, annulation et changement méthodologique ; ne jamais remplacer silencieusement le passé. |

Exiger également la profondeur historique par champ, les jours sans couverture, la latence de publication, le traitement des splits/radiations, les droits de stockage local et de recherche ML, et la différence entre disponibilité de marché estimée et **locate propre au courtier**. Une mesure agrégée de prêt ne garantit pas qu'un SHORT était effectivement réalisable chez Alpaca.

Le harnais accepte un CSV avec les six premiers champs obligatoires et `utilization_pct` facultatif. Il rejette les timestamps sans offset et les doublons non versionnés. Pour un signal de date J, il exige une observation au plus tard à la clôture de J, une première disponibilité au plus tard à **09:25 ET à la séance Oracle suivante**, au plus une séance d'âge, ainsi qu'un taux, une quantité et un identifiant. Il mesure la couverture par année, secteur, quintile de liquidité et décile. Le seuil de faisabilité de l'échantillon est **≥60 % des événements au total et ≥40 % dans chaque année**. Un succès sur 50 titres n'autorise qu'un audit de couverture sur tout le TOP20 ; il ne valide ni modèle ni trade.

Commande locale une fois un extrait reçu :

```powershell
& 'C:\Users\limin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'work/borrow_pilot_20261001/audit_provider_sample.py' 'CHEMIN_VERS_EXTRAIT.csv' --report 'work/borrow_pilot_20261001/provider_coverage.json'
```

Les tests synthétiques vérifient le cutoff de 09:25, le report d'une publication tardive à la séance suivante, l'âge maximal d'une séance et le rejet des timestamps sans offset. Le panel réel se charge correctement : 29 267 événements, 1 764 séances OOF, 50 titres. **Aucun extrait fournisseur n'a été reçu ; aucune couverture réelle ni AUC n'a été calculée.**

## Historisation Alpaca existante : audit et correctif

Le batch prospectif `borrow_status_snapshot` est déjà activé à 08:45 ET avec secours à 09:25 ET. La table locale contient **22 734 snapshots, 1 759 symboles et 13 journées**, du 13 au 30 septembre 2026. Les payloads RAW complets sont conservés. Ils ne contiennent toujours pas la série historique 2018–2025 de `borrow_fee_bps` ou `shares_available` requise pour le test D1/D10.

L'audit en lecture seule des 13 payloads a détecté **12 tickers dupliqués par jour** : l'actif inactif/non tradable précède l'actif actif/tradable. L'ancien collecteur conservait la première ligne par `INSERT IGNORE`, produisant **156 lignes datées `NOT_SHORTABLE` alors que l'actif actif était `EASY`**. La réconciliation complète et la liste exacte des 156 lignes sont conservées dans `work/borrow_pilot_20261001/alpaca_history_reconciliation.json` et `alpaca_snapshot_corrections.csv`. Aucun historique SQL n'a été réécrit ; ces lignes doivent être corrigées depuis le RAW ou écartées de toute analyse prospective.

Le collecteur sélectionne désormais l'actif actif/tradable avant l'insertion et utilise le nouveau champ `borrow_status`, avec fallback legacy et valeur inconnue traitée comme locate requis. [Alpaca a annoncé](https://docs.alpaca.markets/us/changelog/2026-06-05-borrow-status-6b96a5a) la dépréciation de `easy_to_borrow` au profit de `borrow_status`. Dans les 13 RAW locaux, les deux champs sont encore présents ; le risque lié à la disparition du legacy est donc préventif, tandis que le défaut des tickers dupliqués est observé. Un test de régression couvre les deux cas.

## Sources capables de répondre au cahier des charges

1. [S&P Global Securities Finance](https://www.spglobal.com/market-intelligence/en/solutions/products/securities-finance) annonce des historiques point-in-time et des données quotidiennes d'offre, demande et frais. C'est le premier candidat pour un extrait ancien sur les 50 titres ; il faut vérifier la définition exacte de `available_at` et les droits d'export.
2. [S3 Partners](https://www.s3partners.com/articles/market-structure-sentiment-portfolio-impact) décrit un historique point-in-time depuis 2015, avec taux, utilisation et disponibilité. Ses [modalités de livraison](https://www.s3partners.com/) incluent API et fichiers ; demander les observations et versions brutes, pas seulement un score propriétaire.
3. [EquiLend DataLend](https://www.equilend.com/solutions/data-insights) annonce frais, utilisation, soldes et disponibilité. La profondeur et la disponibilité point-in-time de **chaque champ** restent à confirmer sur l'extrait demandé.

Les pages produit établissent l'existence de ces familles de données, **pas** leur couverture effective sur notre échantillon, leur prix, ni leur aptitude à prédire D1/D10. Aucun fournisseur n'a été contacté et aucun achat n'a été lancé.

Une [demande d'échantillon prête à envoyer](borrow_sample_request_20261001.md) est conservée comme brouillon local. Elle ne partage que la liste des 50 tickers, sans labels ni scores Oracle ; aucun message n'a été envoyé.

## Suite conditionnelle

Si un extrait passe le gate PIT/identité/couverture, mesurer ensuite le même contrat sur les **582 700 événements** du nouveau TOP20 Oracle. Seulement après cette vérification, pré-enregistrer un ajout minimal de `borrow_fee_bps`, variation 5/20 séances, `shares_available` et `utilization_pct` au témoin P0g corrigé, avec neuf folds gelés, comparaison appariée des mêmes événements et coût/locate SHORT séparés. Si l'échantillon échoue, ne pas entraîner de modèle sur les lignes survivantes : cela créerait une sélection de couverture.
