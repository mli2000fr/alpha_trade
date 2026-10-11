# Guidance — vérification SEC et instant de décision, 30 septembre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

Statut : **BLOCKED_FOR_ML_EVIDENCE_IMPROVED**. Suite bornée aux cinq candidats du pilote, sans nouvelles sociétés, sans rendements et sans entraînement. Le pilote original et son formulaire de revue indépendante sont préservés.

## Ce qui a été vérifié

Les cinq annonces ont désormais un lien vers un index SEC 8-K, son accession et son annexe EX-99.1. Les valeurs du pilote sont corroborées par lecture des annexes. Pour Autodesk, les anciennes valeurs sont également corroborées par les annexes de mai 2023 et juin 2024. Cette deuxième lecture par le même assistant n'est pas une adjudication indépendante.

| Candidat | Acceptation affichée par SEC | Révision nominale du milieu | Lecture à une décision le même jour à 16 h |
|---|---|---:|---|
| [COLM 01/08/2023](https://www.sec.gov/Archives/edgar/data/1050797/0001050797-23-000131-index.html) | 16:05:53 | −1,6575 % | Acceptation après le cutoff |
| [LOW 23/05/2023](https://www.sec.gov/Archives/edgar/data/60667/000006066723000079/0000060667-23-000079-index.html) | 08:45:30 | −1,1236 % | Avant le cutoff ; disponibilité effective non prouvée |
| [LOW 20/08/2024](https://www.sec.gov/Archives/edgar/data/60667/000006066724000137/0000060667-24-000137-index.htm) | 08:45:21 | −1,8343 % | Avant le cutoff ; disponibilité effective non prouvée |
| [ADSK 23/08/2023](https://www.sec.gov/Archives/edgar/data/769397/000076939723000157/0000769397-23-000157-index.htm) | 16:03:37 | +0,4625 % | Acceptation après le cutoff |
| [ADSK 29/08/2024](https://www.sec.gov/Archives/edgar/data/769397/000076939724000147/0000769397-24-000147-index.htm) | 16:04:36 | +1,0762 % | Acceptation après le cutoff |

Ces comparaisons sont des **scénarios sous convention America/New_York**, conservée explicitement dans les données et encore soumise à revue. Les pages d'index consultées affichent une horloge sans suffixe de fuseau. Aucune conversion UTC n'est promue en vérité validée. À 09 h 30 le même jour, les trois annonces d'après-clôture restent également trop tardives.

L'heure d'acceptation SEC n'est ni l'heure de réception par la stratégie, ni nécessairement la première publication publique. Une information diffusée auparavant par l'émetteur pourrait relever d'une autre chaîne de preuve ; elle n'est pas antidatée ici. Pour une chaîne fondée sur SEC, une acceptation après le cutoff exclut l'usage à cet instant. Une acceptation avant le cutoff ne suffit pas à certifier la diffusion et la réception à temps.

## Preuves des montants et limites économiques

- [COLM EX-99.1](https://www.sec.gov/Archives/edgar/data/1050797/000105079723000131/colmfy23q2exhibit991.htm) : FY2023, ventes nettes 3,57–3,67 → 3,53–3,59 Md USD. La prévision d'effet de change évolue de −20 à −30 points de base : ne pas interpréter tout le delta comme une variation à change constant.
- [LOW mai 2023 EX-99.1](https://www.sec.gov/Archives/edgar/data/60667/000006066723000079/exhibit991-05052023.htm) : FY2023, environ 88–90 → 87–89 Md USD. Les comparaisons au réalisé FY2022 à 53 semaines restent distinctes de cette paire de prévisions FY2023 à 52 semaines.
- [LOW août 2024 EX-99.1](https://www.sec.gov/Archives/edgar/data/60667/000006066724000137/exhibit991-08022024.htm) : FY2024, 84–85 → 82,7–83,2 Md USD, ancien/nouveau explicites.
- ADSK FY2024 : [mai 2023](https://www.sec.gov/Archives/edgar/data/769397/000076939723000106/q124pressrelease.htm), 5 355–5 455 M USD ; [août 2023](https://www.sec.gov/Archives/edgar/data/769397/000076939723000157/q224pressrelease.htm), 5 405–5 455. Les deux documents portent sur l'exercice finissant le 31 janvier 2024. Cela ne certifie pas l'absence d'une annonce intermédiaire.
- ADSK FY2025 : [juin 2024](https://www.sec.gov/Archives/edgar/data/769397/000076939724000095/q125pressrelease.htm), 5 990–6 090 M USD ; [août 2024](https://www.sec.gov/Archives/edgar/data/769397/000076939724000147/q225pressrelease.htm), 6 080–6 130. Même exercice finissant le 31 janvier 2025, avec réserve identique sur le prédécesseur immédiat.

Le [10-K Autodesk FY2024](https://www.sec.gov/Archives/edgar/data/769397/000076939724000090/adsk-20240131.htm), sections Global Reach et nouveau modèle de transaction, décrit le déplacement de certaines incitations commerciales : de réduction du revenu vers les charges opérationnelles. Cela peut relever la croissance du revenu affiché sans effet équivalent sur le résultat opérationnel ou le cash-flow. Ce contexte confirme la nécessité d'une distinction entre révision nominale et révision à base économique comparable. Il ne permet pas d'attribuer les 65 M USD de hausse du milieu en août 2024 à ce seul changement.

## Résultat de la lecture du code

`modelFactory/oracle/predictions_store.py:32` conserve `prediction_date` en DATE et `created_at` comme horodatage de création de ligne. Ni l'un ni l'autre ne prouve à lui seul le cutoff historique de la décision, notamment pour une prédiction recalculée.

`modelFactory/oracle/leakage.py:1` distingue la disponibilité future du label des features ; à la ligne 89 et suivantes, le contrôle des noms de features futures est structurel. Il ne remplace pas une jointure horodatée d'événements de guidance. Le résumé documentaire dans `oracle_extreme_reference.md` ne suffit donc pas à certifier ce nouveau flux.

Un contrat de recherche explicite existe dans `modelFactory/directional_data_research/closing_quote_microstructure.py:1` : décision à 16 h New York, entrée au plus tôt J+1. C'est le contrat de ce diagnostic, **pas une preuve que tous les batchs Oracle utilisent 16 h**. Aucun batch historique réel n'a été joint dans cet audit.

`service/forward_pit/batch.py:1212` écrit séparément `acceptance_datetime` et les horloges `observed_at/available_at`, ces dernières alimentées par l'observation du collecteur. Il serait incorrect de remplacer silencieusement une observation de 2026 par une acceptation de 2023. Un replay reconstruit doit avoir son propre contrat et ses preuves, distincts de l'historique effectivement reçu par la stratégie.

## Artefacts et contrôles exécutés

Dans `work/guidance_pit_followup_20260930/` : `evidence.json` conserve les transcriptions structurées, liens, accessions, horloges affichées et réserves ; `audit.py` vérifie leur cohérence avec les cinq candidats originaux ; `audit_results.json` expose chaque motif de blocage et les scénarios de cutoff. Les hashes portent sur les fichiers locaux, **pas sur les documents SEC bruts**.

Le test d'accès direct à SEC a d'abord échoué sur les permissions réseau ; la tentative autorisée a reçu HTTP 403. Aucune archive brute SEC n'a été obtenue. Les pages sont consultées via l'outil web ; les sources IR archivées dans le pilote restent disponibles, mais ne sont pas présentées comme des archives SEC.

Contrôles : cinq identifiants identiques au pilote ; dates cohérentes ; accession et CIK cohérents avec les chemins ; ordre ancien/nouveau Autodesk ; champs de revue laissés vides ; aucun événement ML-éligible ; trois cas de frontière temporelle vérifiés (après cutoff, avant cutoff et égalité). Ces contrôles passent sans valider l'exhaustivité documentaire ou le sens économique.

## Ce qui bloque encore une expérience D1/D10

1. Revue indépendante des valeurs, unités, périodes, rôles et comparabilité. Le formulaire existant reste vierge.
2. Archives historiques reproductibles, validation de fuseau, diffusion et règle de latence ; preuve du prédécesseur immédiat pour les deux paires Autodesk.
3. Identification d'un batch Oracle et de son cutoff exact, puis jointure des événements disponibles avant ce cutoff. Pour une décision après annonce, recalculer l'instant d'entrée et la cible correspondante ; ne pas garder implicitement une cible antérieure à l'annonce.

**Avancée : cinq chaînes index SEC → annexe identifiées, valeurs corroborées, trois incompatibilités avec un cutoff à 16 h mises en évidence. Limite : zéro ligne prête pour ML.** Une hausse de guidance reste une feature candidate et ne devient jamais automatiquement D10 ; une baisse ne devient jamais automatiquement D1.
