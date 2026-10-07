# Sprint 5 FR — exceptions d'identité prioritaires

État au 2 octobre 2026 : **preuves partielles ; aucun GO canonique global**. Ce document traite les exceptions d'identité et de cycle de vie qui concentrent une part importante des barres 2018–2020 sans couple ISIN/MIC observé dans le rejeu FIRDS. Il ne modifie ni les archives EODHD ni les tables FR.

## Décisions applicables au futur manifeste

| Code fournisseur | ISIN courant EODHD | Preuve officielle | Barres antérieures concernées | Décision |
| --- | --- | --- | ---: | --- |
| `STLAP.PA` | `NL00150001Q9` | [Euronext : admission de Stellantis le 18 janvier 2021](https://live.euronext.com/en/ipo-showcase/stellantis-nv), à la suite de la fusion PSA–FCA | 1 289 avant le 18 janvier 2021 | Ces barres ne peuvent pas être attribuées à l'ISIN courant. Elles décrivent un prédécesseur ou une série fournisseur rétropolée. Les exclure du manifeste de `NL00150001Q9` ; une éventuelle continuité économique devra être modélisée comme une relation d'entreprise distincte, jamais comme une identité d'instrument. |
| `URW.PA` | `FR0013326246` | [Euronext : cotation directe le 5 juin 2018](https://live.euronext.com/en/ipo-showcase/unibail-wfd-unibai) | 619 avant le 5 juin 2018 | Même décision : les barres antérieures ne portent pas l'ISIN courant et doivent rester hors du manifeste de cet instrument. Le prédécesseur doit avoir son propre instrument et sa propre période. |
| `MLGML.PA` | `FR0013371507` | [Euronext : introduction de Gour Medical le 1er décembre 2016](https://live.euronext.com/nl/product/equities/FR0013371507-XMLI), marché Euronext Access Paris (`XMLI`) | 0 avant l'admission ; la série commence le 1er décembre 2016 | L'absence dans notre rejeu FIRDS 2018 n'établit pas une fausse identité. La preuve Euronext confirme le même ISIN et le même segment dès la première barre. Classer le dossier `FIRDS_COVERAGE_GAP_REQUIRES_EURONEXT_NOTICE`, puis contrôler prix et suspensions ; ne pas le rejeter comme ticker recollé. |
| `ALAVE.PA` | `FR001400IV58` | L'ancienne ligne Euronext Access utilisait `FR0011668821` ([Euronext : admission initiale en 2014](https://live.euronext.com/en/ipo-showcase/les-toques-blanches-du-monde)). Après regroupement, le nouvel ISIN `FR001400IV58` est admis à compter du 22 août 2023. | 609 avant le 22 août 2023 | Les barres antérieures appartiennent à l'ancienne ligne et ne doivent pas être attribuées au nouvel ISIN. La continuité économique de l'émetteur n'autorise pas une continuité d'instrument. |

Le rejeu FIRDS jusqu'à fin 2021 apporte une nuance importante pour `URW.PA` : le premier `NewRcrd` de notre archive n'est observé que le 16 novembre 2021, mais il déclare explicitement une première négociation au 5 juin 2018. Il confirme donc la date Euronext sans justifier les barres antérieures ; l'absence de référence FIRDS observée entre juin 2018 et novembre 2021 doit être classée comme lacune de publication/observation, pas comme preuve de non-cotation.

## Suspensions et radiations contredites par les barres fournisseur

Les avis Euronext de cette section qualifient l'exécutabilité de la ligne, et pas seulement son identité. Une barre fournisseur datée pendant une suspension officielle ou après la date effective de radiation ne prouve pas qu'un ordre était exécutable sur Euronext Paris. Elle doit rester en quarantaine, même si son volume est positif.

| Code fournisseur | Avis Euronext | Constat dans l'archive EODHD | Décision |
| --- | --- | --- | --- |
| `SEQ.PA` / `FR0011352590` | [Euronext Sequana](https://live.euronext.com/en/product/equities/FR0011352590-XPAR) : suspension effective le 7 janvier 2019, reprise le 10 janvier 2019, nouvelle suspension le 8 mars 2019 et radiation effective le 19 juin 2019. | 3 barres du 7 au 9 janvier ; 60 barres du 8 mars au 9 août ; parmi elles, 20 barres du 19 juin au 9 août sont postérieures ou égales à la radiation. Volume fournisseur cumulé : 384 347 pendant la première suspension, 4 641 109 depuis la seconde suspension, dont 2 045 690 après radiation. | Conserver au maximum les séances strictement antérieures à chaque suspension et comprises dans une période officiellement négociable. Mettre en quarantaine toutes les barres du 7 au 9 janvier 2019 et toutes celles à partir du 8 mars 2019. Ne jamais promouvoir les 20 barres post-radiation. |
| `TOU.PA` / `FR0000039240` | [Euronext Toupargel](https://live.euronext.com/fr/product/equities/FR0000039240-XPAR) : suspension effective le 24 janvier 2019, reprise le 4 février 2019, nouvelle suspension le 22 octobre 2019 et radiation effective le 12 février 2020. Avis : `PAR_20190124_00845_EUR`, `PAR_20190201_01217_EUR`, `PAR_20191022_11657_EUR`, `PAR_20200210_01814_EUR`. | 5 barres du 25 janvier au 1er février ; 87 barres du 22 octobre 2019 au 28 avril 2020 ; parmi elles, 34 barres du 12 février au 28 avril sont postérieures ou égales à la radiation. Volume fournisseur cumulé : 486 476 pendant la première suspension, 11 820 044 depuis la seconde suspension, dont 5 709 268 après radiation. | Mettre en quarantaine les barres du 24 janvier au 3 février 2019 et toutes celles à partir du 22 octobre 2019. Ne jamais promouvoir les 34 barres post-radiation. |

Ces deux cas établissent qu'un volume EODHD positif ne suffit pas à déclarer une séance négociable. Le futur manifeste devra appliquer les intervalles officiels avant tout calcul de liquidité, de cible ML ou de rendement de backtest.

## Conséquence pour les données et le backtest

La clé historique doit être l'instrument, pas le ticker fournisseur. Pour `STLAP`, `URW` et `ALAVE`, le futur chargement canonique doit créer ou retrouver les instruments prédécesseurs, dater leurs listings, puis couper chaque symbole fournisseur à la date de changement. Une jointure continue sur `symbol` fabriquerait des rendements et des caractéristiques techniques à travers une fusion, une admission directe ou un regroupement.

`MLGML` démontre la limite inverse : une absence FIRDS n'est pas nécessairement une absence de cotation, surtout sur Euronext Access. La preuve officielle Euronext doit pouvoir compléter FIRDS avec une provenance distincte. Le futur manifeste doit donc stocker `evidence_source`, `effective_from`, `effective_to`, `observed_at`, `evidence_url` et un motif de décision, au lieu de réduire la validation à un booléen FIRDS.

## Règles de promotion pré-enregistrées

1. Ne promouvoir aucune barre `STLAP.PA` sous `NL00150001Q9` avant le 18 janvier 2021.
2. Ne promouvoir aucune barre `URW.PA` sous `FR0013326246` avant le 5 juin 2018.
3. Ne promouvoir aucune barre `ALAVE.PA` sous `FR001400IV58` avant le 22 août 2023.
4. Pour `MLGML.PA`, accepter la preuve d'identité Euronext à partir du 1er décembre 2016, mais conserver les gates indépendants de prix, suspension, actions sur titres et disponibilité PIT.
5. Ne pas réécrire les archives EODHD : appliquer ces limites dans le manifeste de promotion, avec les anciennes lignes représentées par des instruments séparés si elles sont finalement qualifiées.
6. Pour `SEQ.PA`, exclure les intervalles `[2019-01-07, 2019-01-09]` et `[2019-03-08, +∞[` de toute donnée tradable Euronext Paris.
7. Pour `TOU.PA`, exclure les intervalles `[2019-01-24, 2019-02-03]` et `[2019-10-22, +∞[` de toute donnée tradable Euronext Paris.
8. Une radiation borne définitivement la ligne concernée : aucune barre fournisseur ultérieure ne peut la rouvrir sans une nouvelle preuve officielle d'admission identifiant explicitement l'instrument et le MIC.

Ces règles résolvent le rattachement d'identité des principaux écarts. Elles ne valident pas les prix EODHD, les volumes, les actions sur titres ni l'exécutabilité des séances.
