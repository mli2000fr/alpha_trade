# Étape 11 LLM — snapshot courant et sélection vide

## Incident et chronologie

Le déverrouillage ciblé du 18 octobre à 00:23 Paris avait bien permis à
`llm-fa604bed142d41a7be61012432c1fc6e` de démarrer le risque. La tentative IHM
`20261018_002339_f0e1f317` a ensuite échoué, avant résumé risque, avec :

```text
ValueError: Oracle operational snapshot must match decision date
```

Le signal concernait la séance du 16 octobre. Le snapshot du compte PAPER était
capturé à son heure réelle, après J. Le builder imposait pourtant une égalité
des dates calendaires, convention correcte pour les replays mais incompatible
avec un risque courant exécuté après clôture ou pendant le week-end.

Un second défaut apparaissait dans le log du modèle factoriel :
`UnboundLocalError: ... 'pd' ...`. L'import local de pandas, situé après le
retour anticipé pour liste vide, masquait l'import global de `db_io.py`.
Ce défaut était journalisé comme warning ; le contrôle du snapshot était
l'erreur terminale. La relance de 08:53 était ensuite bloquée par la réservation
laissée par cette nouvelle tentative échouée, pas par un échec du déverrouillage.

## Correction bornée

- Suppression de l'import local pandas redondant : la demande de facteurs pour
  zéro symbole renvoie bien un DataFrame vide sans accès SQL.
- Pour les seules politiques `oracle_web_llm_long` / `oracle_web_llm_directional`
  avec source **`broker:paper:llm`**, le snapshot courant du compte principal
  `default` peut financer un signal de la séance précédente.
- Sa capture garde **son timestamp réel** : aucun `replace`, aucune date J
  fabriquée, aucune réécriture des archives.
- Horodatages timezone-aware ; capture non future et datant d'au plus **5 minutes**
  au moment du sizing. Capture et sizing doivent appartenir à l'intervalle
  **[clôture J, ouverture de la séance suivante[**, calculé par le calendrier US
  strict, y compris jours fériés, week-end et changements d'heure.
- Le contrôle d'âge de l'analyse LLM (24 h dans ce run), les empreintes,
  compte/preset, univers tradable, prix/ATR/ADV, capital, SHORT/borrow et règles
  de protections restent indépendants et obligatoires.
- Les autres sources et stratégies, notamment les snapshots historiques des
  backtests, conservent leur exigence d'égalité avec la date de décision. Aucune
  exception générale de date n'est ajoutée aux replays.

Le log d'admission indique désormais le nombre de titres retenus par le LLM,
le nombre admissible après l'univers tradable et les symboles exclus. Une
sélection vide est testée dans le vrai builder : zéro nouvelle entrée, pas
d'invention de titre ou de contournement de filtre. Le cas FMC reste soumis
à l'univers tradable ; son avis SHORT ne constitue pas une autorisation.

## Validation et exploitation

**358 tests réussis**, sans API, SQL de production, appel LLM ni ordre : contrôles
snapshot, overnight/week-end/férié/DST, refus avant clôture/après ouverture,
captures périmées/futures/naïves, autres comptes/sources, builder avec et sans
candidat, anciennes règles de replay, facteurs vides, SHORT, SIP, archives,
reprise des boutons indépendants et CLI risque.

La première passe sous environnement restreint a eu un échec de droits sur le
dispositif de certificats Windows, pas une erreur de logique ; la passe complète
avec accès aux certificats réussit. HTTPS n'a pas été désactivé.

Les verrous risque/exécution ne sont **jamais libérés automatiquement sur
exception** : un processus peut avoir écrit des résultats avant de tomber.
Une reprise de cette analyse demande de vérifier les processus, l'état SQL,
l'absence de résumé/cibles et la fraîcheur, puis de libérer uniquement sa
réservation avec une mise à jour conditionnelle et une sauvegarde locale.
Le correctif ne lance ni étape 11 ni étape 12 à lui seul.

### Réarmement ciblé après les correctifs

Le 18 octobre à **09:10:41 Paris**, la réservation de cette même analyse a été
libérée après contrôle des archives, fraîcheur, tentatives IHM terminales,
absence de processus actif et de `risk_summary.json`. Aucun `risk_run_id` ni
`execution_started_at` n'était renseigné ; zéro décision/cible trouvée autour
de la tentative de 00:23. L'UPDATE conditionnel n'a modifié que
`risk_started_at` (ancienne valeur UTC `2026-10-17 22:23:40`), et le résultat
a été relu après commit. Tous les autres champs sont inchangés.

Audit et sauvegarde avant modification :
`artifacts/operations/llm_risk_rearm/20261018T071041266399Z-llm-fa604bed142d41a7be61012432c1fc6e/`.
Ni le risque ni l'exécution n'ont été lancés. Cette analyse reste soumise à son
expiration d'origine : **18 octobre 2026 à 20:36:11 Paris**. Une relance manuelle
de 11 peut donc utiliser le même identifiant avant cette borne. Un éventuel
nouvel échec ne sera pas automatiquement réarmé.
