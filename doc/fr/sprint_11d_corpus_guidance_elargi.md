# Sprint 11-D — Élargissement et validation du corpus de guidance FR

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

**Suite datée 11-E :** [complément gratuit et dossier de seconde revue](sprint_11e_completion_gratuite_guidance.md).
Les chiffres ci-dessous décrivent la vague11-D figée. La suite collecte126 PDF
supplémentaires et propose15 paires cumulées11-D/11-E (9 UP/6 DOWN), encore sans
GO entraînement. Trois réserves documentaires sont levées en première lecture,
mais seuls deux événements recoupent le pool Oracle sur30j. Seconde revue
indépendante autorisée ; Sprint11 reste ouvert, pas de payant indispensable établi.

État au 4 octobre 2026 : **première vague élargie collectée et revue ; pas de GO entraînement**.
Cette passe poursuit la guidance sémantique. Elle ne refait ni le modèle AMF,
ni les compteurs DILA testés en [11-C](sprint_11c_evenements_guidance_ablation.md).
Une révision de prévision financière n'est pas une prédiction de rendement D1/D10.

## 1. Ce qui a été fait

Les métadonnées publiques INFO-FINANCIERE/DILA ont été interrogées à nouveau
pour 2018–2025, sur les ISIN du référentiel FR330. La collecte ne lit aucun
prix, label Oracle, rendement futur ou PnL. Les archives originales, compteurs
du serveur, empreintes et date de collecte sont conservés.

| Étape | Résultat |
|---|---:|
| Exports par mots-clés, avec compteurs concordants | 6/6 |
| Nouveaux candidats distincts dans le référentiel | 105 |
| Documents sélectionnés avant lecture des PDF | 17 |
| Émetteurs sélectionnés | 16 |
| Émetteurs absents de l'échantillon PDF initial | 16/16 |
| PDF récupérés et texte extrait | 17/17 |
| Documents revus texte + page originale rendue | 17/17 |
| Annonces avec paire prospective chiffrée comparable | 4 |
| Dont hausses / baisses | 3 / 1 |

Le tri déterministe utilise la graine `fr-guidance-11d-20261004-v1`, donne
priorité aux nouveaux émetteurs, limite à deux documents par ISIN et plafonne
les catégories de titres UP/DOWN à dix chacune, la catégorie non directionnée
à quatre. Les titres ne sont que des candidats : Bouygues fournit un faux
positif climatique ; Virbac fournit une republication. Le titre anglais
« revised upward » ne reçoit pas automatiquement un signe UP dans cette version.
Ne pas changer rétroactivement la sélection après avoir vu les documents.

Les six mots-clés sont `objectifs`, `perspectives`, `previsions`, `guidance`,
`warning`, `avertissement`. Leurs exports contiennent respectivement
756, 453, 115, 229, 4 et 5 lignes, qui se recouvrent : ne pas sommer ces lignes
pour compter des annonces distinctes. Ce filtre n'est pas un inventaire
exhaustif des publications, ni une preuve de couverture quotidienne.
**88 des 105 candidats n'ont pas encore été revus en PDF.**

## 2. Paires admises dans le registre documentaire

Admission signifie ici revue sémantique de premier niveau, pas éligibilité ML/PIT.

| Émetteur / date | Métrique, exercice | Ancienne prévision | Nouvelle prévision | Réserve conservée |
|---|---|---|---|---|
| Kumulus Vape, 29/07/2021 | CA annuel 2021 | 30 M EUR | 32 M EUR | 22,5 M EUR est le réalisé 2020, pas la cible ancienne |
| Pluxee, 19/04/2024 | Marge EBITDA récurrent, exercice clos 31/08/2024 | au moins 34,5 % | au moins 35 % | taux/périmètre constants, coûts standalone inclus ; seuils, pas valeurs exactes |
| Icade, 29/11/2024 | CFNC des activités abandonnées, 2024 | 0,80 EUR/action | 1,03 EUR/action | composante Santé/intérêts seulement, dividende non récurrent ; pas le CFNC Groupe |
| Thales, 17/10/2019 | Croissance organique Groupe, 2019 | bas de la fourchette 3–4 % | environ 1 % | ancien objectif dans la note 3 ; périmètre et change constants, note 1 |

Une annonce demeure **une observation**, même si elle révise deux métriques.
Un seuil « au moins » n'est jamais transformé en estimation ponctuelle exacte.
Pour Thales, le registre conserve la fourchette et le qualificatif « bas » :
il n'invente pas une ancienne prévision de 3,5 %.
Pour Pluxee, l'ancien « croissance à deux chiffres » reste qualitatif ; on ne
l'invente pas sous forme d'une fourchette numérique afin d'augmenter le support.

Le corpus précédent avait trois révisions prospectives haussières
(Lagardère, Aubay, Orange). En ajoutant les quatre nouvelles, les deux vagues
documentaires fournissent **sept annonces : six UP, une DOWN**, sans les
promouvoir automatiquement en sept événements Oracle utilisables. Il faudra
encore les rattacher aux sessions, aux preuves de cotation et au pool OOF.

## 3. Documents non promus et actions nécessaires

| Document | Classification | Pourquoi / travail restant |
|---|---|---|
| Nexity, 04/01/2021 | estimation d'une période terminée | les révisions portent sur 2020 ; les cibles 2021 n'ont pas d'ancien comparateur |
| Klépierre, 01/08/2023 | ancienne guidance manquante | 2,24 EUR est le réalisé 2022 ajusté ; rechercher la cible 2023 publiée précédemment |
| Vente-unique, 12/05/2021 | ancienne guidance manquante | nouvelle croissance 30–40 %, CA >150 M EUR ; ancienne cible du même exercice absente |
| Virbac, 20/12/2019 | ancienne guidance manquante | nouvelle croissance 6–7 % ; comparaison avec 2018 réalisé non suffisante |
| Schneider Electric, 30/11/2021 | ancienne guidance manquante | nouvelles ambitions 2022–2024, sans anciennes valeurs sur le même horizon |
| Ipsos, 15/10/2024 | ancienne guidance manquante | croissance annuelle ramenée vers 1 %, ancienne cible absente ; les 2,4 % réalisés à neuf mois ne la remplacent pas |
| Nexans, 24/07/2024 | changement explicite de périmètre | EBITDA 670–730 → 750–800 M EUR inclut La Triveneta Cavi ; obtenir une comparaison pro forma avant d'utiliser une surprise opérationnelle |
| Renault, 29/07/2022 | périmètre à vérifier | marge ~3 % → >5 %, retrait Russie/IFRS5 ; retrouver l'ancien communiqué pour vérifier le périmètre |
| Assystem, 24/10/2024 | périmètre à vérifier | CA ~620 → ~610 M EUR, marge ~7 → ~6,5 % ; rapprocher la note cessions/acquisitions de l'ancienne cible |
| Maisons du Monde, 26/10/2021 | périmètre à vérifier | Modani cédé ; ancienne marge exprimée en variation de 50 bps du réalisé 7,3 %, pas en cible de 7,3 % |
| Bouygues, 16/12/2020 | objectif non financier | baisse d'émissions carbone, pas baisse de bénéfice ou de chiffre d'affaires |
| Virbac, dépôt 17/07/2023 | republication | PDF daté du 03/07 après Bourse ; croissance 4–6 → 0–4 % observée, mais retrouver l'original et dédoublonner avant admission |
| Bastide, 15/02/2024 | confirmation, pas nouvelle révision | maintien des perspectives après cession Distrimed ; 8,4 % est un réalisé de référence, pas une nouvelle paire de révision |

Ces réserves ne signifient pas « aucune information utile ». Elles empêchent
seulement de fabriquer une variable homogène `nouvelle_guidance - ancienne_guidance`
à partir de nombres de nature différente.

## 4. Dates : ce qui est prouvé et ce qui ne l'est pas

Le registre distingue la date interne du communiqué, les transmissions AMF /
marché / émetteur, et `observed_at`, date réelle de notre téléchargement.
Le maximum des transmissions explicitement zonées est conservé comme
`transmission_proxy_at`. La conversion vers la journée française utilise
`Europe/Paris`, pas une heure fixe UTC.

**`historical_web_available_at` reste NULL.** Une métadonnée reconstruite
aujourd'hui ne prouve pas à elle seule que l'URL publique était téléchargeable
à cette seconde dans le passé. Le téléchargement 2026 ne devient jamais une
observation historique 2019. Virbac, déposé le 17 juillet avec un PDF daté du
3 juillet, n'est surtout pas antidaté au 3 juillet à partir de ce seul PDF.

Tous les enregistrements portent `training_eligible: false`. La revue est
effectuée par le même agent : **pas de seconde validation indépendante**.
Le corpus est donc `MANUAL_REVIEW_COMPLETE_NOT_TRAINING_GO`, pas GO_PIT.

## 5. Artefacts, code et contrôles

- [Protocole de collecte figé](../../artifacts/fr/research/guidance_corpus_11d/corpus-20261004-v1/protocol.json).
- [Bilan métadonnées](../../artifacts/fr/research/guidance_corpus_11d/corpus-20261004-v1/metadata_report.json).
- [PDF et empreintes](../../artifacts/fr/research/guidance_corpus_11d/corpus-20261004-v1/pdf_report.json).
- [Rapport de revue avec provenance par document](../../artifacts/fr/research/guidance_corpus_11d/corpus-20261004-v1/review_report.json).
- [Manifeste de revue versionné](../../config/research_fr/guidance_review_11d_v1.json).
- [Service de collecte et validation](../../service/fr/guidance_corpus_11d.py).
- [Point d'entrée recherche](../../modelFactory/fr_guidance_corpus_11d.py).
- [Tests dédiés](../../tests/test_fr_guidance_corpus_11d.py).

Le validateur vérifie l'empreinte exacte des PDF, la couverture unique du
manifeste, l'existence des pages, les transmissions avec fuseau, la chronologie,
la période encore ouverte, les valeurs numériques finies, les bornes et le
signe. Il refuse les périmètres non vérifiés et interdit aux documents en
réserve d'exposer des paires admises. **Ce validateur contrôle le contrat de la
revue humaine ; il ne comprend pas automatiquement toute la sémantique d'un PDF.**

La reprise PDF conserve la date de première observation des fichiers déjà
archivés, vérifie leur empreinte et ne les antidate pas. Le repli réseau DILA
est limité au même nom et chemin de fichier ; aucun contournement TLS.
PDF limités à 8 Mo/80 pages pour cette vague.

Rejouer la validation locale, sans réseau ni modèle :

Vérification finale : **37 tests ciblés passants**, comprenant la collecte/revue11-D,
le POC guidance, la qualification11-B et le pilote11-C. Ruff passe sur les trois
fichiers de code/test11-D. La suite applicative complète n'a pas été exécutée.
Les tests ciblés utilisent `--no-cov` : le seuil de couverture global du projet
n'est pas une mesure pertinente pour ce seul sous-ensemble. Le premier appel
avec la couverture globale a échoué sur ce seuil, pas sur une assertion de test.

```powershell
python -u -m modelFactory.fr_guidance_corpus_11d review --output artifacts/fr/research/guidance_corpus_11d/corpus-20261004-v1
python -m pytest --no-cov tests/test_fr_guidance_corpus_11d.py tests/test_fr_guidance_feasibility.py tests/test_fr_event_data_qualification_11b.py tests/test_fr_event_direction_11c.py -q
```

Pour une nouvelle vague, utiliser un nouveau dossier et protocole/manifeste,
sans remplacer les artefacts ni réviser les exclusions en fonction des rendements.
L'étape `pdf` requiert `pypdf` ; ce poste utilise la bibliothèque du runtime
documentaire existant sans installation dans l'environnement de l'application.

## 6. Prochaine action, sans relancer AMF/DILA

1. Retrouver les anciennes prévisions des cinq cas incomplets, uniquement
   dans des publications antérieures à leur révision.
2. Vérifier les anciens périmètres Renault/Assystem/Maisons du Monde et
   retrouver le dépôt original Virbac du 3 juillet ; dédoublonner par annonce,
   pas seulement par URL ou nombre de métriques.
3. Étendre la revue aux candidats restants, avec davantage de baisses et
   d'exercices/émetteurs distincts, sans sélection par rendement.
4. Faire contrôler les paires par un second lecteur ; qualifier les preuves de
   disponibilité ou garder explicitement une analyse proxy retardée.
5. Mesurer le support par fold et les intersections Oracle avant de
   pré-enregistrer une expérience guidance séparée. Aucun gain D1/D10 n'est démontré.

**Sprint 11 complet reste ouvert.** Aucun modèle AMF/DILA réentraîné, aucune
table canonique modifiée, aucun batch existant touché, aucun abonnement demandé.
