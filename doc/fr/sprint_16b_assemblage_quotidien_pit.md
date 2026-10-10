# Sprint 16-B — Assemblage quotidien FR à partir des observations archivées

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Bilan au 6 octobre 2026

**Adaptateur et diagnostic livrés ; données quotidiennes non libérées.**
L'assemblage est hors ligne, en fichiers de recherche. Aucune connexion SQL,
collecte supplémentaire, modification de batch, entraînement ou ordre.
Le modèle reste celui du [contrat 16-A](sprint_16a_contrat_prediction_et_preflight.md),
candidat Oracle amplitude H5, et non un nouveau modèle de direction.

Le diagnostic réel pour l'ouverture XPAR du **6 octobre 2026** est bloqué :
330 identités examinées, **0 jeu de features complet**, 0 ligne proposée.
Ce blocage ne doit pas être contourné en rebaptisant les données « qualifiées ».
Le Sprint 16 complet et le shadow prospectif ne sont pas terminés.

## 1. Fichiers et rôle

| Élément | Emplacement / fonction |
| --- | --- |
| Adaptateur | `service/fr/daily_feature_adapter_16b.py` |
| Tests | `tests/test_fr_daily_feature_adapter_16b.py` |
| Contrat et preflight | `service/fr/prediction_contract_16a.py` |
| Formules d'entraînement réutilisées | `modelFactory/fr_feature_panel.compute_symbol_features` |
| Observations de barres | `artifacts/fr/operations/eodhd_daily/observations/` |
| Payloads de barres | `artifacts/fr/operations/eodhd_daily/raw/` |
| Observations et payloads d'actions sur titres | `artifacts/fr/operations/fr_corporate_actions_sync/observations/` et `raw/` |
| Versions du référentiel | `artifacts/fr/operations/fr_security_master_sync/versions/` |
| Sorties uniquement | `artifacts/fr/research/daily_feature_adapter_16b/<version>/` |

Les fichiers `latest` et le checkpoint courant **ne sont pas utilisés comme
vérité historique** : ils peuvent intégrer des corrections après la décision.
Les anciens panels de recherche avec hypothèse J+1 ne servent pas à compléter
automatiquement les observations prospectives manquantes.

## 2. Date de décision et calendrier

L'utilisateur choisit une **date de séance**. Le service utilise son ouverture
XPAR comme `decision_at`, avec fuseau explicite en UTC. Il appelle le calendrier
FR existant, sans connexion de base et sans fallback lundi–vendredi US.
Un week-end ou jour férié non négocié est refusé.

Pour le 6 octobre : décision à **07:00 UTC / 09:00 Paris**, features de la
séance précédente, le **5 octobre**. Les 21 séances nécessaires vont du
**7 septembre au 5 octobre 2026**.

Les jours sont comptés en séances : le lundi utilise le vendredi précédent
lorsqu'il s'agit de la dernière séance, pas une soustraction de 24 heures.
Le calendrier bibliothèque permet la construction technique de la fenêtre ;
il ne remplace pas une qualification indépendante du calendrier pour release.

## 3. Reconstruction des barres réellement observées

```text
Date de décision → ouverture XPAR → séance précédente → 21 séances requises
                                     │
               observations disponibles avant la décision
                                     │
            contrôle des liens et SHA-256 des payloads bruts
                                     │
        dernière version observée avant la décision, pour chaque barre
                                     │
                 contrôle OHLCV et continuité en séances
                                     │
            mêmes 14 features brutes que l'entraînement
```

Pour chaque observation le service vérifie :

- horodatages `observed_at` et `available_at` explicites et cohérents ;
- disponibilité et observation au plus tard à la décision ;
- empreinte SHA-256 du payload et correspondance symbole/fenêtre/type ;
- absence de date dupliquée ou hors de la fenêtre fournisseur ;
- barre finale observée après la clôture de sa séance ;
- validité OHLCV et absence de volume nul pour le profil figé ;
- présence de toutes les 21 séances, sans pont au-dessus d'une lacune.

Une correction reçue après la décision n'écrase pas la version connue à cette
date. Deux valeurs différentes ayant exactement la même disponibilité sont
ambiguës et rejetées. Les archives futures valides sont ignorées, y compris
dans la liste des preuves utilisées. Une archive malformée ne devient pas
silencieusement une barre absente : l'erreur est conservée.

Les 14 features sont calculées par **la fonction d'entraînement existante**.
Il n'y a pas de seconde implémentation divergente des rendements, ATR ou SMA.
Le logarithme de `traded_value_mean20_eur` n'est pas appliqué ici ; il appartient
à l'entrée du modèle, conformément à 16-A. Les valeurs calculées non finies
sont rejetées.

## 4. Actions sur titres et identités

Pour dividendes et splits, l'adaptateur exige une fenêtre effectivement
interrogée et observée avant la décision couvrant toutes les séances requises.
Un fichier vide sans couverture suffisante n'est pas une preuve d'absence.
Les versions successives remplacent les événements dans leur propre fenêtre.
Un événement présent dans la fenêtre de features est réservé pour qualification :
pas d'ajustement automatique des prix ni d'intégration automatique d'un
dividende. Le profil d'entraînement exclut des historiques à splits ; une
absence de split dans ces 21 séances seule ne prouve donc pas l'éligibilité
complète du titre au profil. Cette preuve reste à compléter avant release.

Le référentiel est la dernière **version archivée observée** avant la décision,
pas le dernier fichier disponible aujourd'hui. Son nom doit correspondre au
SHA-256 de son contenu. Il faut FR_EQ, une date de couverture correspondant à
la séance de features, continuité historique et quotidienne déclarées, sans
anomalie. Par titre : ISIN unique, version non ambiguë à la date, MIC attendu,
EUR et pas de terminaison ou annulation réservée.

Ces vérifications ne constituent **pas** une nouvelle qualification indépendante
des archives ESMA de base et de toutes leurs versions. Le programme conserve
donc une réserve explicite `INDEPENDENT_MASTER_AND_ACTIONS_QUALIFICATION`.
Il n'assimile ni une assertion de checkpoint à une preuve suffisante, ni un
statut fournisseur courant à une négociabilité historique.

## 5. Sorties et protection contre la promotion involontaire

Trois fichiers sont produits :

- `manifest.json` : copie du candidat et des preuves de 16-A ;
- `dataset.json` : proposition de features brutes, si calculable et sans
  motif de réserve détecté par l'assemblage ;
- `report.json` : fenêtre, compteurs, motifs par titre, erreurs d'archive,
  empreintes des fichiers effectivement examinés et résultat du preflight.

Même pour une ligne calculable sur un jeu de test conforme :

```json
{
  "qualification": "OBSERVED_RESEARCH_NOT_INDEPENDENTLY_QUALIFIED",
  "identity_qualified_at_session": false,
  "tradable_at_session": false
}
```

Il est donc intentionnel que le preflight de 16-A **ne libère pas** cette
proposition. `candidate_rows_count` ne signifie pas « titres servables ».
Le statut final demeure `BLOCKED_NOT_RELEASED`, `serving_enabled: false`,
`orders_allowed: false`, `sql_writes: false`.
Une erreur d'intégrité d'archive retire toutes les lignes proposées : le
programme ne continue pas sur un sous-ensemble silencieusement amputé.

Les sorties sont créées dans un dossier nouveau ; aucun résultat existant
n'est écrasé. Deux exécutions vers deux dossiers n'ajoutent aucun doublon métier
en base, puisqu'il n'y a aucune écriture SQL. Ce n'est pas encore le mécanisme
d'upsert des prédictions du futur shadow.

## 6. Résultat sur les données actuelles

Diagnostic `decision-20261006-v2/report.json` :

| Réserve | Nombre d'identités concernées |
| --- | ---: |
| Continuité historique du master non qualifiée | 330 |
| Master observé à la décision ne couvrant pas la séance requise | 330 |
| Fenêtre de 21 séances incomplète dans les chemins inspectés jusqu'au bout | 300 |
| Couverture observée des dividendes insuffisante | 300 |
| Couverture observée des splits insuffisante | 300 |
| Barre à volume nul impropre au profil figé | 30 |
| Identité terminée ou réservée | 30 |
| Version d'identité ambiguë/absente à cette date | 15 |
| Devise/ISIN non conforme dans la version examinée | 6 |
| Dividende fournisseur dans la fenêtre | 5 |

Les motifs se chevauchent et ne s'additionnent pas en un total de titres.
Pour 30 titres, la validation des barres s'arrête sur volume nul avant d'évaluer
les contrôles suivants ; les compteurs 300 ne prouvent pas que les 30 autres
ont une fenêtre complète. **0 feature complète, 0 ligne proposée.**
Aucune erreur de hash/lecture d'archive n'a été relevée dans cette exécution.

La version master collectée le 6 octobre à 20h Paris couvre le 5 octobre,
mais elle était **inconnue à l'ouverture du 6 octobre** ; elle ne peut pas
réparer rétroactivement cette décision. Une collecte réussie après coup
ne supprime donc pas le motif PIT de cette ouverture.

## 7. Commande et contrôles

```powershell
python -m service.fr.daily_feature_adapter_16b --decision-date 2026-10-06 --output-dir artifacts/fr/research/daily_feature_adapter_16b/decision-20261006-v2
```

Cette commande a été exécutée. Pour rejouer, choisir un autre nom de dossier.
Pour une autre date, elle doit être une séance XPAR et il faut disposer des
observations antérieures correspondantes. Le statut `BLOCKED_NOT_RELEASED`
est un résultat de diagnostic enregistré ; ne pas assimiler le code de sortie
CLI normal à un GO serving.

Tests : corrections après décision, archives corrompues, horodatages, lacunes,
volume nul, doublons, couverture des actions, événements à réserver, versions
du master, identité terminée et parité des formules. Aucune activation automatique.

## 8. Comment avancer réellement

1. **Historique d'observations** : laisser s'accumuler 21 séances ou faire une
   collecte de démarrage autorisée couvrant la fenêtre. Une collecte nouvelle
   ne vaut qu'à partir de sa disponibilité réelle, jamais pour les ouvertures
   passées. Aucun téléchargement supplémentaire n'a été lancé en 16-B.
2. **Référentiel** : qualifier les lacunes de continuité héritées et les
   identités réservées. Faire parvenir les preuves requises avant la décision
   choisie, ou choisir une décision ultérieure explicitement compatible.
3. **Actions sur titres** : couvrir la fenêtre, valider les événements et
   l'absence de splits incompatible avec le profil historique.
4. **Release distincte** : revue du candidat, réserves Sprint 15, protocole
   prospectif et qualification indépendante des inputs. Ensuite seulement
   implémenter le scoring shadow, sa publication idempotente et son reporting.

Il n'y a pas besoin de payer un nouveau fournisseur pour constater ces
blocages. En revanche, attendre davantage de séances ne suffit pas à résoudre
les réserves d'identité et de qualification. Ne pas lancer automatiquement
un entraînement ni promettre que la collecte seule rendra le modèle profitable.
