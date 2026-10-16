# News US — seconde revue bornée du financement, 16 octobre 2026

**Suite clôturée** : les quatre derniers textes et toutes les associations
éligibles sont désormais examinés. Voir le [bilan final](news_financement_cloture_corpus_20261016.md).
Les décomptes « quatre textes restants » ci-dessous décrivent l'état à la fin
du deuxième lot, avant cette dernière étape.

## Conclusion

**Second lot livré : 20 textes présélectionnés et 10 témoins nouveaux, tous lus.**
Aucun nouveau financement primaire entièrement qualifié pour le **titre associé**
dans ce lot. Cela ne signifie ni absence de financements dans les news, ni
absence d'effet des financements sur les prix, ni échec d'un backtest.

Les deux lots totalisent 60 couples et **56 textes distincts**, dont **36 des
40 textes présélectionnés éligibles** du corpus figé. Quatre textes éligibles
présélectionnés restent non lus ; les autres articles sans mot-clé ne sont pas
exhaustivement relus. Les 33 couples présélectionnés non annotés comprennent
aussi des associations de textes déjà lus : ce ne sont pas 33 nouveaux textes.

Pas de nouvelle collecte, API fournisseur, API GPT/DeepSeek, écriture SQL,
changement d'univers actif/batch/modèle, entraînement, rendement ou backtest.
La couverture des prix a été vérifiée par **lecture SQL uniquement**.

## Sélection figée avant lecture

Parent : `artifacts/research/us_news_event_qualification/20261016-complete-review-v1/full/`.
Premier lot : même racine, `bounded_review/`. Empreintes des deux dossiers
contrôlées ; refus si source modifiée ou tronquée.

Ordre croissant de `evidence_key`, au plus 20 couples présélectionnés puis
10 témoins, **un couple par texte**, exclusion des 26 textes du premier lot.
Pas de sélection par prix, résultat futur, score Oracle ou caractère prometteur.
Les informations de prix présentes dans les corps d'articles ne sont pas des
critères de sélection et aucun rendement n'a été recalculé.

Fenêtre inchangée : publication depuis le 14 octobre 2026, borne supérieure
**16 octobre 2026 à 13:48:49.600646 UTC**, soit 15:48:49 Paris. Le temps actuel
ne remplace pas silencieusement cette borne. La lecture et sa qualification
ont leur propre heure réelle ; aucune annotation n'est rétrodatée.

Une lecture supplémentaire par le même assistant **n'est pas une revue humaine
indépendante**. Chaque note conserve une citation exacte et ses positions dans
le corps archivé. Les affirmations de l'article ne deviennent pas des faits
vérifiés indépendamment par leur simple présence dans une archive EODHD.

## Cas importants

| Titre associé | Lecture de l'archive | Traitement |
| --- | --- | --- |
| GSK | Enregistrement d'ADS lié aux plans salariés, plafond annoncé de 3,0498 milliards USD | `SHELF_ONLY` ; ni cash levé, ni nombre réellement émis, ni prix d'offre prouvés. Ne pas comparer directement prix LSE et ADS US. |
| CWT | Prix de 125 millions USD de notes du groupe et 150 millions USD d'obligations hypothécaires de sa filiale | Dette, pas émission d'actions ordinaires. La mention d'émission d'actions dans les risques génériques n'est pas une autre opération annoncée. |
| NVDA | Communiqué d'offre IonQ : actions ordinaires et warrants | Émetteur **IONQ**, Nvidia partenaire ; aucune dilution NVDA démontrée. Même famille que le résumé IonQ du premier lot. |
| ABBV | Début de cotation d'Iambic et rappel de son IPO | Émetteur **IAM**, AbbVie partenaire ; ne pas multiplier les événements à chaque reprise. |
| BAC | Placement de nouvelles actions de Bending Spoons dans un résumé multi-sociétés | Émetteur Bending Spoons ; BAC apparaît pour une amende et ses résultats. |
| GOOGL | Projet d'IPO de Jio, avec Google et Meta comme investisseurs historiques | Pas émission de GOOGL ; documents indiens sous-jacents non téléchargés ni validés ici. |
| NICE | Cérémonie d'ouverture de marché de **TSXV: NICE / Ni-Co Energy** et rappel de cotation en juillet | Collision de ticker avec le NICE US ; aucune promotion automatique d'identité. |
| OWL | Projet de prêt de Stack Infrastructure, société détenue par Blue Owl | Dette de société détenue, pas émission d'actions OWL. Prêt proposé, pas clôture certifiée. |
| AFL | Confirmation de notes de crédit et références à de la dette/shelf existants | Pas de nouvelle offre d'actions prouvée. |
| TSLA | Rumeur de fusion, rémunération et rappel d'une IPO de SpaceX | Ni opération confirmée ni nouveau financement primaire Tesla. |
| MSCI | Règles d'indices Indonésie/Turquie et flottants | Pas émission d'actions MSCI. Les mentions de nombres d'actions concernent les indices. |

IONQ, IAM et BSP **ne figurent pas dans le fichier courant figé** de 1 790
titres, empreinte contrôlée. Ils n'y ont pas été ajoutés. Cette vérification
du fichier courant ne prouve pas une composition historique PIT.

Dans ce second lot, 17 couples n'établissent pas l'identité du titre associé
comme émetteur/sujet de la clause examinée. Les 13 rapprochements textuels
restants ne sont pas 13 financements qualifiés. Une association contextuelle
du fournisseur peut être légitime : aucun mapping ou article n'a été effacé.

## Deux limites révélées

1. **Les témoins ne sont pas nécessairement neutres.** Le transcript Bloomberg
   associé à BAC parle d'un investissement supplémentaire de Berkshire dans
   Bending Spoons sans employer les mots-clés de présélection. Le résumé
   présélectionné précise séparément des actions nouvellement émises. Les deux
   textes appartiennent à une même famille ; ne pas les compter comme deux
   événements BAC. Ce cas montre un manque de rappel du dictionnaire, pas un
   taux de rappel estimé ni un signal validé. Les règles figées n'ont pas été
   modifiées après cette observation.
2. **Droits d'usage distincts de l'accès technique.** Deux notices MSCI archivées
   contiennent des restrictions explicites de réutilisation, notamment pour
   bases de données et usages IA/ML. Ce constat est une réserve à instruire,
   pas un avis juridique ni une autorisation déduite de l'abonnement EODHD.
   Aucun de ces textes n'est promu en feature ou signal ; aucun batch n'a été
   modifié ou suspendu dans ce travail.

## Couverture intraday du second lot

| Résultat technique | Couples |
| --- | ---: |
| Barres absentes ou fenêtre invalide | 23 |
| Pas assez de place près de l'ouverture/clôture | 2 |
| Fenêtre encore future à la borne figée | 4 |
| Fenêtre complète, source unique | 1 |

La fenêtre complète est celle du résumé associé à **TSM** ; ce n'est pas un
financement qualifié de TSM. Les 24 fenêtres achevées finissaient avant la
disponibilité réelle des preuves de news : les cours autour de la publication
ne suffisent donc pas à simuler une stratégie utilisant notre réception réelle.
Les barres du rattrapage précédent sont datées de leur réception réelle ; leur
présence actuelle ne démontre pas leur disponibilité à l'ancien cutoff.

Pas de nouveau rattrapage des 23 trous : télécharger davantage de prix ne
résoudrait pas l'identité, l'instrument ou la nouveauté. Le verdict reste
`BLOCKED_DATA_FEASIBILITY`, pas un résultat financier négatif.

## Fichiers et reproduction

- Second pack immuable : `artifacts/research/us_news_event_qualification/20261016-second-bounded-review-v1/`.
  `protocol.json`, `evidence.json`, notes/citations dans
  `technical_review_filled.json`, décisions dans `technical_review_result.json`.
- Notes de lecture reproductibles :
  `scripts/research/us_news_financing_second_reading_notes_20261016.json`.
  Elles sont liées aux textes lus, pas un classifieur de nouvelles journées.
- Couverture et bilan :
  `artifacts/research/us_news_financing_feasibility/20261016-second-bounded-review-v1/` :
  `report.json`, `intraday_windows.json`, `completion_summary.json`.
- **64 tests ciblés passent** à la vérification finale, dont sélection stable/disjointe, refus de sources
  modifiées, citations exactes et absence de validation de nouveauté automatique.
  Les tests SQLite en mémoire ne modifient pas la base métier.

```powershell
python -u -m scripts.research.us_news_financing_second_review_20261016 --parent artifacts/research/us_news_event_qualification/20261016-complete-review-v1/full --prior artifacts/research/us_news_event_qualification/20261016-complete-review-v1/bounded_review --output artifacts/research/us_news_event_qualification/NOUVEAU-SECOND-LOT
python -u -m scripts.research.us_news_financing_second_review_20261016 --pack artifacts/research/us_news_event_qualification/NOUVEAU-SECOND-LOT --notes scripts/research/us_news_financing_second_reading_notes_20261016.json
python -u -m scripts.research.us_news_financing_feasibility --pack artifacts/research/us_news_event_qualification/NOUVEAU-SECOND-LOT --output artifacts/research/us_news_financing_feasibility/NOUVELLE-COUVERTURE
```

Toujours un dossier neuf. Un premier lancement du bilan a bien écrit le fichier
mais a échoué à afficher un objet date en console ; l'affichage JSON est corrigé,
le fichier existant vérifié et conservé, sans écrasement. Les essais de tests
avec les options globales du dépôt ont rencontré les permissions temporaires
puis le seuil de couverture globale ; l'exécution ciblée `--no-cov` hors sandbox
réussit. Aucune modification de ces options globales du projet.

## Suite bornée, pas lancement financier

Ce lot est clôturé. Une clôture exhaustive de la présélection éligible demanderait
la lecture des **quatre textes encore nouveaux**, puis le rattachement prudent
des associations non annotées ; elle ne serait pas une revue exhaustive des
6 720 articles. Un éventuel élargissement du dictionnaire sera une nouvelle
version à tester, pas une correction rétrospective du protocole courant.
Les prochaines collectes quotidiennes fourniront d'autres dates réellement
observées. Pas de nouvel entraînement ni de promesse de bénéfice D1/D10.

Voir [premier bilan](news_financement_validation_revue_20261016.md) et
[rattrapage intraday](news_financement_identites_intraday_20261016.md).
