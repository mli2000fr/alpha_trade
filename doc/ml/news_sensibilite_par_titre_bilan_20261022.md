# News : des titres plus « fidèles » au sentiment ?

22 octobre 2026. **AUDIT RÉTROSPECTIF TERMINÉ / AUCUN SOUS-UNIVERS VALIDÉ.**

L'idée n'est pas rejetée universellement, mais cette règle ne fournit pas une
liste exploitable de titres prévisibles. Le signal recherché doit rester
présent **après une décision possible**, pas seulement être associé à un
mouvement déjà réalisé. Les résultats ci-dessous ne justifient ni une blacklist,
ni un nouvel entraînement, ni une intégration en production.

[Protocole figé avant calcul](news_sensibilite_par_titre_protocole_20261022.md).
Artefacts : `artifacts/research/us_news_symbol_sensitivity/20261022-v1/`.

## Périmètre effectivement étudié

- Univers courant : **1 790 titres**, pas seulement TOP10 ou TOP20 % Oracle.
- Publications janvier 2025–30 septembre 2026 : **365 053 lignes article/titre**.
- **688 heures UTC exactement minuit** réservées, aucune heure inventée.
- **364 365 lignes horodatées**, regroupées en **185 374 décisions titre/open**.
- **1 752 titres avec news**, 38 sans news dans cette archive ; aucun titre du
  fichier courant n'est absent de l'archive de prix. Absence de news ≠ absence
  définitive de couverture fournisseur, ni titre intrinsèquement imprévisible.
- 795 970 barres quotidiennes, 1 790 titres + SPY ; 270 lignes invalides réservées.
- Déduplication première occurrence du hash par titre : zéro doublon retiré.
  Cela ne prouve pas l'absence de reprises reformulées ou de news sur le même événement.

Les titres d'articles actuels et secteurs ont été lus en transaction SQL
READ ONLY, sans nouvelle collecte. Tous les 364 365 couples horodatés ont un
hash concordant avec cet enrichissement. Cela **ne prouve pas une disponibilité
historique** ni une attribution correcte de chaque article à l'émetteur.

## Horloge : association et mouvement restant séparés

Décision à la première ouverture NYSE strictement postérieure à publication+5min.
Une news en séance ne donne donc pas accès à l'open déjà passé ; une news trop
proche de l'open attend le prochain. Les décisions de publications tardives du
30 septembre peuvent tomber le 1er octobre. Prix observés jusqu'au 9 octobre :
toutes les fins de parcours indisponibles restent inconnues, jamais imputées à zéro.

« Pont vers l'entrée » = dernier close avant la publication → open de décision.
Ce pont inclut du mouvement avant **et** après l'article : ce n'est pas une
mesure causale exacte d'une réaction à la news.

À H1 en 2026, sur les groupes forts disponibles :

| Ton | Pont brut vers l'open | Mouvement restant dans le sens du ton, open→close |
|---|---:|---:|
| Positif seul | +0,621 % | +0,015 % |
| Négatif seul | −0,567 % | +0,005 % pour le sens SHORT |

La relation prix/ton est donc surtout visible dans le pont, pas dans un grand
mouvement restant à capter à l'ouverture. Ce constat est compatible avec une
réaction rapide, des articles relatant le mouvement ou des facteurs communs ;
il ne départage pas ces causes. Une éventuelle réaction intraday immédiate n'est
pas mesurée par cet audit quotidien.

## Sélection sur 2025, liste figée pour 2026

Par titre, réservation chronologique de fenêtres non chevauchantes **tous tons
confondus**, avant lecture du futur. Les groupes mixtes, sans score fort ou au
parcours incomplet consomment également leur créneau : aucune sélection du
point de départ le plus favorable. Labels train entièrement terminés avant 2026.

H5 est primaire. H1/H10/H20 sont des analyses secondaires, pas une compétition
permettant de promouvoir a posteriori le meilleur horizon.

| Horizon | Cellules titre/ton train examinées | Historique minimum suffisant | Tous critères avant correction multiple | Après correction BH5 % |
|---|---:|---:|---:|---:|
| H1 | 3 122 | 250 | 5 | **0** |
| **H5 primaire** | **2 936** | **5** | **0** | **0** |
| H10 | 2 751 | 4 | 0 | **0** |
| H20 | 2 329 | 3 | 1 | **0** |

Le déficit d'effectif est important à H5/H10/H20 une fois les répétitions et
chevauchements retirés. Les 185 374 groupes ne sont donc pas autant de preuves
indépendantes par titre et par ton. Les minima n'ont pas été diminués pour
faire apparaître des candidats.

La correction Benjamini–Hochberg est appliquée à toutes les cellules train
observées de chaque horizon, y compris sous-dimensionnées. Les tests binomiaux
et cette correction restent descriptifs : dépendances marché/secteur résiduelles,
années déjà explorées et sélection de l'univers courant empêchent une garantie
statistique prospective.

## Cinq candidats H1 : avantage fragile, pas une liste de trading

Sélection avant correction multiple, puis observation de 2026 sans réajustement.
« Alignement » ci-dessous = signe du rendement **en excès de SPY** correspondant
au ton, pas taux de trades TP/SL gagnants.

| Titre | Ton retenu sur 2025 | Événements 2026 | Alignement excès SPY | Retour signé moyen après friction illustrative |
|---|---|---:|---:|---:|
| ATI | Positif | 49 | 57,14 % | −0,057 % |
| CAH | Positif | 68 | 47,06 % | −0,130 % |
| CCJ | Négatif | 33 | 60,61 % | −0,175 % |
| OXY | Négatif | 37 | 43,24 % | −0,129 % |
| UNH | Négatif | 40 | 62,50 % | +0,125 % |
| Ensemble | Deux tons | **227** | **53,30 %** | **−0,076 %** |

Avant friction, moyenne signée de l'ensemble **+0,084 %** ; coût illustratif
fixé à 0,16 % aller-retour, d'où −0,076 %. Ce n'est pas une comptabilité de
portefeuille : ni capital contraint, ni sizing, ni marge, ni emprunt SHORT,
ni SL/TP, ni bid/ask réels. Le coût réel peut différer. Quatre mois sur neuf
ont une moyenne de ce proxy positive.

Comparaison aux autres titres du même ton aux mêmes dates : delta équipondéré
par date **+0,208 point**, 131 dates comparables. Cela n'annule pas le rendement
absolu après friction négatif. La moyenne excès secteur courant vaut +0,081 % ;
les secteurs sont actuels/non PIT et ne constituent pas une neutralisation complète.

**UNH n'est pas validé** : candidat choisi au milieu de milliers de comparaisons,
ne franchissant pas la correction multiple ; pas preuve d'une propriété naturelle.
Aucun des cinq candidats H1 n'a un rendement terminal absolu >50 % dans ces
observations, mais cela ne certifie pas leurs prix/identités ou les contrôles.

À H20, **GIS négatif** passe les règles avant correction sur **huit** événements
2025. Les cinq observations 2026 sont favorables (+9,97 % de retour signé moyen
après friction), mais **cinq est inférieur aux dix requis**, et le test multiple
échoue. Ne pas transformer ce joli petit effectif en signal exploitable.

## Familles d'information : inventaire, pas qualification des événements

Des titres d'articles ont été routés par mots-clés en résultats/guidance,
analystes, financement, acquisitions, multiple ou autre. Exemple H5/2026 après
espacement, ton fort et prix disponibles : 2 261 groupes résultats/guidance,
216 analystes, 72 acquisitions, 2 482 multiples, 6 839 autres.

**Ce n'est pas un test validé titre × événement économique nouveau** : pas de
relecture exhaustive de l'émetteur réel, des chiffres, de la nouveauté et des
reprises. « Multiple » signifie notamment plusieurs catégories dans le groupe
ou le titre, pas nécessairement plusieurs événements vérifiés. Aucun modèle,
seuil, liste par famille ou signal consensus n'a été entraîné/testé ici.

## Réserves déterminantes

1. **Zéro groupe** dont le maximum des `updated_at` archivés précède l'entrée.
   Pas de vintage immuable prouvant news **et score** disponibles à la décision.
   Cela ne prouve pas leur indisponibilité historique, mais interdit la promotion PIT.
2. Univers actuel survivant ; secteurs actuels ; pas reconstitution de tous les radiés.
3. Prix quotidiens rétrospectivement split-adjusted ; registre des ruptures connues
   appliqué, pas certification complète des OST/identités ou des dividendes.
4. **668 lignes** à rendement terminal absolu >50 % recensées à H5/H10/H20,
   dont KLAC et d'autres symboles déjà réservés ; lignes chevauchantes et horizons
   multiples, pas 668 événements indépendants ni 668 erreurs prouvées.
   Elles restent visibles, sans suppression opportuniste, et peuvent affecter
   les références globales/sectorielles. Audit arithmétique ≠ qualification fournisseur.
5. Sentiment = ton du texte, pas probabilité de hausse ; cause et sujet de la
   news non vérifiés exhaustivement. Les articles peuvent relater le prix.
6. Les bonnes observations 2026 ont déjà pu influencer d'autres recherches :
   aucune « nouvelle validation vierge » revendiquée.

## Décision et livrables

**Aucun sous-univers production constitué.** L'audit ne montre pas une liste
robuste de titres « fidèles aux news ». Il ne rejette pas toutes les sensibilités
possibles, notamment intraday ou à des événements précisément qualifiés.

Pas de croisement TOP10 ni de backtest économique supplémentaire : aucune
liste n'a franchi le gate préalable. Pas d'entraînement, API fournisseur/LLM,
ordre, SQL écrit ou changement des modèles/batchs. Téléchargements non touchés.

- `news-events.parquet`, `events-H*.parquet` : observations et rendements/restes inconnus.
- `train-memberships-H*.csv` : toutes les cellules, effectifs, motifs implicites,
  listes avant/après correction ; aucune sélection fondée sur 2026.
- `test-symbols-H*.csv`, `test-matched-dates-H*.csv` : vérification séparée.
- `metadata/manifest.json` : enrichissement existant, horodatage et empreintes.
- `extreme-returns-reserve.csv` : réserves visibles, aucune correction SQL.
- `protocol.json`, `report.json`, `final-audit.json` : sources et résultats scellés.

**23 tests passent**, dont 20 propres à cet audit. Revue technique séparée :
185 374 horloges, reconstruction de l'espacement, **11 138 cellules** de sélection
et correction multiple, **1 658 vérifications scalaires de rendements**.
Même assistant : **pas une seconde revue humaine indépendante**.

Scripts : `scripts/research/us_news_symbol_sensitivity.py` et
`scripts/research/us_news_symbol_sensitivity_audit.py`.

Empreinte du rapport :
`e26baf6116d2844c695347033aca29896803fff9386450976644423ac4a7654e`.

Reproduction dans un dossier neuf :

```powershell
python -u -m scripts.research.us_news_symbol_sensitivity --phase prepare --output-dir artifacts/research/us_news_symbol_sensitivity/NOUVEAU
python -u -m scripts.research.us_news_symbol_sensitivity --phase metadata --output-dir artifacts/research/us_news_symbol_sensitivity/NOUVEAU
python -u -m scripts.research.us_news_symbol_sensitivity --phase run --output-dir artifacts/research/us_news_symbol_sensitivity/NOUVEAU
python -u -m scripts.research.us_news_symbol_sensitivity_audit --output-dir artifacts/research/us_news_symbol_sensitivity/NOUVEAU
```

`metadata` lit la base actuelle : un nouvel export n'est pas le même instantané.
Pour reproduire exactement, conserver les métadonnées et sources scellées du
dossier canonique. Aucun lancement ultérieur automatique prévu.
