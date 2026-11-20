# Reprise PAPER depuis l'étape 10 avec GPT — 20 novembre 2026

Demande : annuler les ordres du dernier batch puis rejouer 10/11/12 avec la
configuration actuelle de `us_pipeline`, recherche Web GPT et choix humain.

## Source et annulations confirmées

- Batch source : `us_pipeline-20261120002400-9f87a4a4`, terminé.
- Séance signal : **19 novembre 2026** ; achats prévus sur J+1.
- Sélection source : `q051-8f76aec4c7034ccba2012f37f9da0654`.
- Comptes exclusivement PAPER : `default`, `test1`, `test2`.
- Chaque compte : six ordres d'achat ASX, CTVA, FUTU, GLW, IONS et ZS.
- **18 annulations broker confirmées**, toutes sans remplissage.
- Après annulation : **0 ordre ouvert et 0 position sur chacun des comptes**.

Les annulations ont été réalisées sous le verrou d'exécution de chaque compte,
avec contrôle du symbole, client ID, run risque et run d'exécution exacts.
La réconciliation native a mis les opérations OMS à jour et les 18 campagnes
source à `CANCELED`, libérant leur clé active. Aucun historique n'a été effacé,
aucune position vendue, aucun autre ordre annulé.

Reçus et observations avant/après :
`artifacts/operations/us_pipeline_gpt_replay_20261120/cancellation.json` et
les fichiers `{account}-before.json`, `{account}-cancellation.json`.

## Nouveau passage

- Batch lancé : `us_pipeline-20261120072217-a0962812`.
- Nouvelle sélection : `q051-dd0979ee509f4a29a203fd60f8dcc916`.
- Workflow principal : `20261120_082218_74395568`.
- Étape10 : `20261120_082218_a04cfcba`.
- Modèle : `model-factory-20261118172104-2f6a31`, B témoin H10.
- Fournisseur configuré : OpenAI, modèle `gpt-6-luna`, mode `web_search`.
- Défaut : étapes **10 → 11 → 12**, puis **11 → 12** sur test1 et test2.
- Nouvelle prédiction et nouvelle analyse ; aucune ancienne réponse GPT reprise.
- Pas de recalcul des étapes1–9, pas de nouvelle collecte ni entraînement.
- SL5/open11 et protections du profil B conservés.

Le contrôleur ponctuel `scripts/operations/replay_us_pipeline_gpt_20261120.py`
construit de nouvelles options via `fresh_pipeline_options`, en conservant les
contrôles de calendrier réel (dernière séance clôturée), comptes PAPER,
verrous, workflow, watcher avant12 et dimensionnement natifs. Il utilise le
lanceur Windows existant et les reçus SQL/IHM normaux. Aucun YAML ni horaire
planifié n'a été modifié pour ce passage. L'autorisation explicite vise la
séance19 déjà finalisée ; ce n'est pas le bouton de rattrapage automatique.

Quand le tableau GPT est publié, le workflow **attend le choix humain** avant
de lancer11. La liste validée est partagée entre comptes, avec dimensionnement
propre à chacun. En cas d'expiration ou d'échec, aucun choix automatique ni
rejeu implicite d'ordres.

Suivi principal :
`artifacts/ihm_pipeline_runs/ml_predict/20261120_082218_a04cfcba/combined.log`.
Le lien entre le batch et la nouvelle sélection est dans
`artifacts/operations/us_pipeline_gpt_replay_20261120/replay.json`.

Deux anciennes lignes SQL `RUNNING` ne correspondaient à aucun processus ou
verrou actif. Elles n'ont pas été modifiées ; la vérification porte sur les
verrous natifs et les véritables runners. Une première tentative du contrôleur
se détectait elle-même à travers le parent Python du venv Windows : corrigé
en excluant les ancêtres du processus, sans assouplir les verrous du workflow.
Ces préparations n'ont déclenché aucun appel GPT ni nouvel achat.

## Issue du passage réel

Le run a terminé **FAILED**, à **08:31:41 Europe/Paris**, avant l'étape11.
Oracle et le classement LONG ont été recalculés ; couverture Oracle :
1 638 / 1 733 négociables, **94,52 %**, minimum 93 %. Dix candidats ont été
transmis au transport GPT : GLW, FUTU, CTVA, ZS, IONS, ASX, AGNT, STX, FLEX, SA.

Analyse : `llm-e3c01d2af58848bf99bc61869fbe3a9d`. Les **10 appels ont reçu
HTTP401** d'OpenAI. Aucun résultat d'analyse ni choix humain n'a été publié,
11/12 et les comptes secondaires n'ont pas été lancés. Ce n'est pas un rejet
directionnel des titres ; c'est un refus d'authentification.

La source `OPENAI_API_KEY` du processus et celle de l'environnement utilisateur
Windows sont identiques. Aucun autre exemplaire de cette clé n'est présent
dans `scripts/windows/forward_pit.env` ou `.env`. Les valeurs ne sont pas
consignées : seule la comparaison de longueur/empreinte a été effectuée.
Action nécessaire : remplacer la clé refusée dans l'environnement utilisé par
l'application, puis lancer une nouvelle analyse avec un nouvel identifiant.
Ne pas réutiliser ce run LLM échoué ni contourner la validation humaine.

Vérification finale broker : **0 ordre ouvert et 0 position** sur chacun des
trois comptes. Reçu :
`artifacts/operations/us_pipeline_gpt_replay_20261120/final-status.json`.

## Nouvelle clé et seconde analyse — 20 novembre

Après mise à jour par l'utilisateur, la clé a été relue directement depuis
l'environnement utilisateur Windows et transmise uniquement à l'environnement
du nouveau lanceur. Contrôle GET du modèle configuré : **HTTP200**, sans
appel d'analyse payant pour cette vérification. Les trois comptes étaient
toujours sans ordre ouvert ni position, et aucun verrou concurrent n'était actif.

- Nouveau batch : `us_pipeline-20261120073803-55994d74`.
- Nouvelle sélection : `q051-2a33ff771fe14e1992b5cae6056e8637`.
- Workflow : `20261120_083804_5b6893b5`.
- Étape10 : `20261120_083804_3d231437`.
- Même modèle B, séance19, fournisseur GPT, Web et attente humaine.

L'ancien lien de reprise est conservé dans `replay-failed-401.json` ; le lien
actif reste `replay.json`. Le journal du nouveau lanceur est
`artifacts/operations/us_pipeline_gpt_replay_20261120/launcher-retry2.log`.
Ne pas interpréter le `final-status.json` du premier essai comme le statut
de cette seconde analyse.

### Résultat de la seconde analyse

Les **10 réponses GPT sont reçues et valides techniquement**, sans refus401.
Analyse : `llm-d15e1538e26b400d87b025faa44528af`. Le protocole v10 et les
archives ont été revalidés avant publication du tableau. L'étape10 est
`COMPLETED` ; le workflow reste `running`, **1/3 étapes**, en attente de la
validation humaine. Aucun dossier de risque/exécution ni validation humaine
n'est publié pour cette nouvelle sélection.

Les dix estimations sont accompagnées de preuves `PARTIAL`. **0 titre est
éligible** : le minimum de deux sources Web récentes qualifiées n'est atteint
pour aucun titre (zéro ou une selon le cas). Certains dossiers comportent en
plus des citations Web/locales non traçables. Les cours locaux restent des
faits de contexte, sans promotion en preuve directionnelle suffisante.
Les probabilités estimées vont de 8 à 30 %, sans calibration empirique.

Le tableau et les fenêtres de détail sont consultables dans l'étape10 de
Pipeline. Aucun choix n'est effectué par l'assistant ; valider une sélection
vide permet de terminer ce passage sans achat. Les étapes11/12 n'ont pas été
démarrées au moment de ce constat. Reçu du second passage :
`artifacts/operations/us_pipeline_gpt_replay_20261120/retry2-status.json`.

## Relance GPT seule en français — 20 novembre, 11:49 UTC

À la demande explicite de l'utilisateur, le contrôleur de l'ancien passage a
été arrêté uniquement après vérification qu'il attendait une validation, sans
processus enfant, sans sélection humaine ni tentative de risque/exécution.
Ses scores et ses réponses v10 sont conservés. Le statut du workflow est
`stopped` ; le batch porte le motif `STOPPED_BY_USER_FOR_GPT_ONLY_REFRESH`.
Preuve : `artifacts/operations/us_pipeline_gpt_replay_20261120/gpt-only-stop.json`.

- Nouveau batch : `us_pipeline-20261120114920-02ed784c`.
- Nouvelle sélection : `q051-c345d1e2f94a4edf842bdf12a496d3cb`.
- Workflow : `20261120_124921_7cafe54c`.
- Étape10 : `20261120_124921_daf6a9f2`.
- Contrôleur ponctuel : `scripts/operations/refresh_q051_gpt_20261120.py`.

Cette opération réutilise exactement les dix candidats LONG antérieurs,
leurs scores Oracle et per-symbol ainsi que les preuves de couverture.
Elle rafraîchit les dossiers d'analyse locaux puis appelle GPT avec recherche
Web, protocole v11, analyses en français et contrat court terme H10/SL5,
sortie open11. Aucun nouvel entraînement ni calcul de score Oracle/LONG.
Le nouveau rapport scellé conserve l'identifiant et les empreintes de la
sélection source ; les étapes11/12 natives restent soumises au choix humain.

L'ancien pointeur est conservé dans `replay-v10-wait.json` ; `replay.json`
désigne désormais cette relance. Journal du lanceur :
`artifacts/operations/us_pipeline_gpt_replay_20261120/launcher-fr-refresh.log`.
### Résultat de la relance française

L'analyse `llm-25fb0015a2144500ba1f03f177803675` est **COMPLETED** :
**10 réponses sur 10 valides**, protocole v11/fr, puis publication de la
sélection et notification Telegram de l'étape10. Revalidation en lecture seule
effectuée à 12:01 UTC : les dix candidats et toutes les colonnes de scores
Oracle/LONG sont strictement identiques à la source. Rapports, empreintes,
protocole, preuves et liaison LLM revalidés dans le profil B exact.

Les probabilités subjectives vont de **8 à 34 %**. **0 titre est éligible** :
les dix dossiers restent `PARTIAL`. Neuf titres ont moins de deux sources Web
fraîches qualifiées ; AGNT en a deux, mais conserve des preuves partielles.
Certains dossiers comportent également des citations exclues faute de
traçabilité. Aucun seuil de qualification n'a été assoupli.

Le workflow reste `running`, 1/3 étapes, en attente du choix humain ;
aucune validation humaine ni tentative de risque/exécution n'existe pour
cette nouvelle sélection. La proposition expire le **21 novembre à
11:59:33 UTC**. Aucune sélection n'a été approuvée par l'assistant.

Preuve : `artifacts/operations/us_pipeline_gpt_replay_20261120/fr-refresh-status.json`.
Contrôle reproductible sans nouvel appel fournisseur :
`artifacts/operations/us_pipeline_gpt_replay_20261120/verify_fr_refresh.py`.
Tests ciblés du protocole v11 : **9 réussis** (`--no-cov`, la couverture globale
du projet ne s'applique pas à cette sélection de tests). Le contrôleur ponctuel
a également passé la compilation Python.

## Relance des trois probabilités — v12, 20 novembre, 12:21 UTC

Demande explicite : conserver la conjointe hausse/sans SL et ajouter la touche
du SL ainsi que la hausse finale hypothétique indépendamment du stop. Le
passage v11 a été arrêté au même point d'attente, sans enfant actif, validation
ni risque/exécution. Les archives sont conservées ; reçu `gpt-v12-stop.json`,
ancien pointeur `replay-v11-wait.json`.

- Batch : `us_pipeline-20261120122100-371972c5`.
- Sélection : `q051-b43c2635d2594ad6b805fefc50b1da05`.
- Workflow : `20261120_132100_284c7a15`.
- Étape10 : `20261120_132100_bf9c3498`.
- Contrôleur ponctuel : `scripts/operations/refresh_q051_gpt_breakdown_20261120.py`.
- Journal du lanceur : `launcher-v12.log` dans le dossier d'audit opérationnel.

Même séance19, même modèle B, mêmes dix candidats et scores scellés ;
nouveau dossier local et recherche Web, français, H10/SL5, sortie open11.
Les deux nouvelles estimations sont demandées dans chaque appel, sans
tripler le nombre d'appels. Aucun entraînement ni nouveau calcul Oracle/LONG.
L'analyse ne reprend 11/12 qu'après validation humaine explicite.

Contrôles v12 : **82 tests** schéma/parsing/SQL/UI/compatibilité, plus
**271 tests** catalogue, preuves, DeepSeek Search, scores et modes antérieurs.
Reçu principal : `artifacts/operations/llm_probability_20261120/tests-v12.xml`.
Au lancement : dossiers en préparation, aucune sélection humaine publiée.

### Résultat v12

Analyse `llm-59d9329993724e30b6d6ec5acda825fb` : **COMPLETED**, dix réponses
sur dix `VALID`, chacune avec les trois probabilités numériques. Notification
Telegram de l'étape10 envoyée. La nouvelle sélection est publiée et scellée.
Contrôle indépendant à **12:33 UTC** : mêmes dix candidats, mêmes scores
Oracle/LONG, empreintes source exactes, réponses SQL revalidées, cohérence
mathématique des probabilités et égalité des valeurs SQL/parquet vérifiées.

| Titre | Hausse sans SL | Touche SL | Hausse finale hypothétique |
| --- | --- | --- | --- |
| GLW | 29 % | 55 % | 47 % |
| ASX | 29 % | 61 % | 48 % |
| FLEX | 22 % | 64 % | 49 % |
| FUTU | 22 % | 56 % | 48 % |
| STX | 20 % | 72 % | 52 % |
| ZS | 20 % | 63 % | 50 % |
| IONS | 17 % | 61 % | 43 % |
| AGNT | 14 % | 66 % | 34 % |
| SA | 13 % | 72 % | 40 % |
| CTVA | 12 % | 78 % | 42 % |

Estimations subjectives non calibrées, et non fréquences mesurées. **Aucun
titre éligible**, les dix dossiers conservant des preuves `PARTIAL` : FUTU
a quatre sources Web qualifiées et IONS deux, mais leur qualité globale reste
partielle ; les autres titres ont zéro ou une source qualifiée. Aucun contrôle
de preuve n'a été assoupli.

Le workflow attend toujours la validation humaine (1/3 étapes), sans fichier
de validation ni dossier de risque/exécution. Expiration de la proposition :
**21 novembre, 12:32:01 UTC**. Aucun choix humain n'a été simulé.

Preuve complète : `artifacts/operations/us_pipeline_gpt_replay_20261120/v12-status.json`.
Audit reproductible en lecture seule, sans appel fournisseur :
`artifacts/operations/us_pipeline_gpt_replay_20261120/verify_v12_refresh.py`.

## Qualification des preuves facultative pour le choix humain

À la demande explicite de l'utilisateur, le paramètre
`us_pipeline.gpt_require_qualified_evidence_for_manual_selection` vaut `false`.
Les anciens résultats et leurs verdicts `PARTIAL` restent inchangés ; la
validation humaine peut désormais retenir les estimations valides malgré ces
réserves. Les blocages d'identité, d'estimation absente/invalide, d'expiration
et de traçabilité technique ne sont pas désactivés. Les validations nouvelles
archivent la politique et les réserves acceptées ; le choix reste manuel.

L'ancien contrôleur v12 a été arrêté avant toute validation/risque ; reçu
`gpt-manual-policy-stop.json`. Le contrôleur a été repris avec le nouveau code,
sur **la même proposition**, sans appel GPT ni nouvelle prédiction :

- Batch de reprise : `us_pipeline-20261120130551-12b25538`.
- Workflow du compte principal : `20261120_140610_465887f0`.
- Sélection conservée : `q051-b43c2635d2594ad6b805fefc50b1da05`.
- Analyse conservée : `llm-59d9329993724e30b6d6ec5acda825fb`.
- Contrôleur : `scripts/operations/resume_q051_human_policy_20261120.py`.
- Pointeur opérationnel : `manual-policy-resume.json` ; journal `launcher-manual-policy.log`.

La reprise attend le choix humain avant les étapes11/12 natives du compte
default, puis de test1 et test2. Vérification réelle en lecture seule :
**ASX, FLEX, STX et ZS sont autorisés au choix**, dix candidats sont
sélectionnables ; aucun fichier de validation ni dossier de risque n'a été
créé par ce contrôle. Aucun choix n'a été effectué à la place de l'utilisateur.
