# Sprint 16-F — Confirmation verrouillée sur une ouverture réelle

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

État au 7 octobre 2026 : **confirmation exécutée à 14 h 57, coupure maintenue
à 9 h Paris ; 242 features sur 330, zéro candidat, shadow bloqué**.
La [remédiation prospective](sprint_16f_remediation.md) est implémentée ;
rattrapage et confirmation du 8 octobre restent à qualifier. L'inventaire du
6 octobre ci-dessous est conservé comme historique.
Ce travail poursuit [16-E](sprint_16e_preuves_et_decision_reelle.md).

## 1. Hypothèse et contrat figés

Vérifier que les collectes prospectives fournissent, avant une décision, les
barres, réponses actions et versions d'identité requises par les formules
gelées du modèle Oracle FR H5. Ce n'est pas un test de gain économique ni
une démonstration de direction D1/D10.

Protocole : `config/research_fr/opening_confirmation_16f.json`.

- Marché `FR_EQ`, calendrier `XPAR`, aucun fallback US/CN.
- Ouverture cible : **7 octobre 2026, 9 h Europe/Paris = 7 h UTC**.
- Dernière séance attendue pour les features : **6 octobre 2026**.
- Univers : les 330 identités du manifeste candidat, pas un nouvel univers.
- Bootstrap et pièces émetteurs : dossiers 16-C/16-E explicitement figés.
- Aucune reconstruction d'un prix manquant par carry-forward.
- Aucune utilisation d'une version reçue après l'ouverture cible.
- Aucune modification des modèles, de SQL ou des tâches planifiées.
- Aucun serving, shadow ou ordre autorisé, même si des contrôles passent.

Le protocole est copié dans le rapport et son SHA-256 est enregistré.
Changer le protocole constitue une nouvelle version d'expérience, pas une
correction silencieuse du rapport existant.

## 2. Deux phases distinctes

Service : `service/fr/opening_confirmation_16f.py`.

### Préparer

`--phase prepare` inspecte les archives normales connues **maintenant** :
présence de la dernière barre attendue, couverture des réponses div/splits,
référentiel et réserves, erreurs d'intégrité. La présence d'une réponse vide
sur la fenêtre est une couverture fournisseur, pas une preuve indépendante
d'absence d'événement. Ce contrôle ne calcule pas les 21 séances de features
et ne qualifie pas une décision future.

Rapport réel :
`artifacts/fr/research/opening_confirmation_16f/preparation-20261006-v1/report.json`.

- Statut : `WAIT_ACTUAL_OPENING`.
- Barres du 6 octobre observées dans les collectes quotidiennes au moment
  du contrôle : **0**.
- Réponses div/splits couvrant le 6 octobre observées : **0 / 0**.
- Référentiel courant observé : couverture jusqu'au **5 octobre**.
- Les archives de warmup du bootstrap restent utilisables à leur heure réelle
  mais ne contiennent pas la nouvelle séance du 6 octobre.

Les trois zéros ne prouvent pas un échec : le contrôle a lieu avant les
horaires configurés de 22 h pour les barres et 23 h pour les événements.
Seul le contrôle après les passages permettra de distinguer attente, absence,
échec et réception trop tardive. Les erreurs d'archives sont affichées à part.

### Confirmer

`--phase confirm` refuse de démarrer avant l'ouverture réelle. Après celle-ci,
il réutilise le contrôle intégré 16-E avec la coupure fixée à **l'ouverture**,
pas à l'heure plus tardive de lancement du script. Une collecte reçue après
9 h est exclue même si l'audit est lancé à 15 h.

L'assemblage complet réévalue les 21 séances et le manifeste. Le diagnostic
du référentiel reste distinct du contrôle strict ; les pièces émetteurs doivent
être reçues **et revues** avant la coupure pour être connues dans cette décision.
Elles ne deviennent jamais automatiquement des ajustements qualifiés.

## 3. Commande à exécuter après le 7 octobre à 9 h Paris

```powershell
python -u -m service.fr.opening_confirmation_16f --phase confirm --output-dir artifacts/fr/research/opening_confirmation_16f/opening-20261007-v1
```

Le dossier doit être nouveau. Pour répéter le même audit, utiliser `v2`.
Ne pas changer `decision_date` pour contourner une absence de données.
Pour une autre ouverture, créer et documenter une nouvelle version du protocole.

Ce script ne déclenche pas de collecte et n'attend pas en arrière-plan.
Aucune automatisation de suivi ni tâche Windows supplémentaire n'a été créée.
Les collectes existantes doivent réellement tourner pour alimenter le contrôle.

## 4. Réserve structurelle du référentiel

À la décision initiale, le batch `fr_security_master_sync` était configuré à **20 h Paris** et recherchait
les publications jusqu'à **J−1**. Son passage du 6 octobre couvre donc au mieux
le 5 octobre. À l'ouverture du 7 octobre, les features attendent le 6 octobre :
une séance de retard peut subsister **même si le batch a réussi**.

Cela doit rester séparé d'un échec réseau, d'un fragment ESMA absent et d'une
archive corrompue. Le diagnostic 16-D peut décrire une dernière référence
connue avec une séance de retard ; l'assemblage strict 16-B ne la transforme
pas en preuve d'identité/négociabilité sur la séance manquante.

Il faudra ensuite décider, sur les preuves du rapport :

1. Si une collecte supplémentaire peut réellement obtenir les publications
   requises avant décision, sans inventer une disponibilité fournisseur.
2. Sinon, si un protocole limité à référence retardée est acceptable ; cela
   nécessitera un GO explicite et conservera le risque de changement non observé.
3. Ou conserver le shadow bloqué. Ne pas assouplir le contrôle juste pour
   produire des candidats.

## 5. Lecture du rapport de confirmation

| Section | Ce qu'elle mesure | Ce qu'elle ne démontre pas |
| --- | --- | --- |
| `daily_assembly` | Features calculables, candidats, raisons par titre, intégrité et preflight | Rentabilité ou droit de servir |
| `reference` | Version connue, fin de couverture, retard en séances XPAR et âge | Absence de changement pendant la séance non observée |
| `evidence` | Pièces intégrales hashées, correspondance de revue et disponibilité avant ouverture | Paiement réalisé, ajustement validé ou intervalle historique de devise |
| `next_gates` | Conditions de libération encore requises | Autorisation de les ignorer |

Les 233 passages locaux du soir du 6 octobre ne constituent pas un objectif
à atteindre à tout prix le lendemain. La fenêtre change, de nouvelles données
sont nécessaires et les réserves peuvent changer.

## 6. Validation et état de clôture

Tests supplémentaires : refus de confirmation avant ouverture sans appeler
l'audit ; transmission de la date et des dossiers gelés ; protocole incapable
d'activer le serving ; préparation qui n'est pas une décision réalisée.
Campagne ciblée complète : **81 tests passants** après adaptation du test de
chemin pour Windows. Aucun défaut applicatif n'a été masqué.

La confirmation du 7 octobre a été lue : `DECISION_AUDITED_SHADOW_BLOCKED`.
La remédiation ne change pas ce résultat passé. Le prochain protocole cible
le 8 octobre à 9 h Paris ; aucune confirmation de cette ouverture future
ni clôture du Sprint 16 complet n'est déclarée.
