# Sprint 17-F — Qualification des protections et des courses d'exécution

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Conclusion du 9 octobre 2026

**Qualification documentaire et tests synthétiques livrés ; parité de protection
courtier bloquée.** Aucun ordre DEMO/réel envoyé, aucune lecture de clé, aucun
appel API, aucune écriture SQL, aucun batch ou routeur modifié dans ce lot.

Le client DEMO en lecture reste disponible. Cela ne qualifie ni les sorties
automatiques ni le comportement effectif des ordres de protection.

## Capacités documentées et preuves manquantes

Source primaire consultée le 9 octobre :
[OpenAPI Trading212](https://docs.trading212.com/_bundle/api.json?download=).

| Fonction | Contrat documenté / conclusion |
| --- | --- |
| Stop | Déclenchement sur dernier prix traité, puis ordre au marché ; prix final non garanti |
| TP simple | Vente limite, au prix limite ou mieux si exécutée ; aucun lien OCO démontré |
| Stop-limit | Déclenche une limite ; l'exécution peut rester en attente |
| Annulation | Réponse positive = demande acceptée, pas garantie d'absence de fill |
| Soumission | Non idempotente ; pas de renvoi aveugle après timeout |
| OCO natif / bracket lié | Aucun endpoint explicite trouvé dans la description consultée ; capacité NON QUALIFIÉE |
| Remplacement atomique | Pas de garantie qualifiée permettant de supposer continuité et unicité de protection |
| Reduce-only / réservation partagée des sorties | NON QUALIFIÉS pour ce raccordement |

L'absence d'endpoint identifié n'est pas une preuve d'impossibilité générale
du produit ou de l'interface manuelle. Le constat concerne le contrat API
disponible pour notre moteur. Les comportements de réservation des titres,
rejets et exécutions partielles n'ont pas été testés sur le compte externe.

## Code livré

`service/fr/trading212_protection_17f.py` est un **auditeur pur de scénarios
synthétiques**, pas un contrôleur qui place des protections.

- `ExitLeg` décrit une sortie et son cumul rempli.
- `audit_protection` contrôle position restante, cumuls, quantité encore
  potentiellement exécutable, couverture stop et états incertains.
- `replacement_preflight` bloque avant annulation confirmée, puis calcule
  uniquement la quantité résiduelle cohérente pour un scénario factice.
- `readiness` conserve `BLOCKED_BROKER_PROTECTION_PARITY`, droits d'ordre faux.

Les entrées représentent **un seul épisode de position**, sans stock initial
ni opération étrangère. Les quantités sont Decimal finies positives ou nulles.
Les identifiants doivent être uniques ; un même cumul ne doit pas être compté
deux fois. Les flags de réconciliation sont des préconditions synthétiques,
pas une preuve de fraîcheur du compte. Le module ne vérifie pas les seuils de
prix, tick sizes, distances minimales ou leur acceptation par le courtier.

## Scénarios et résultats

| Scénario | Résultat de sécurité |
| --- | --- |
| Position 10, stop 10 et TP 10 indépendants | Exposition potentielle 20 ; pas de qualification OCO |
| Stop 5 + TP 5 pour une position 10 | Couverture stop incomplète et sorties non atomiques |
| TP remplit 4, position 6, stop 10 non annulé | Sur-exposition potentielle détectée, même si annulation demandée |
| Stop et TP remplissent tous les deux 10 | Survente synthétique détectée ; pas d'hypothèse de short autorisé |
| Stop remplit 3 avant annulation confirmée | Position restante 7 conservée, aucune remise à zéro du fill |
| Remplacement demandé avant annulation confirmée | Bloqué |
| Annulation confirmée avec position réconciliée 7 | Quantité candidate 7, **trou de protection explicite**, aucun ordre autorisé |
| TP encore actif, entrée encore remplissable ou position non réconciliée | Remplacement bloqué |
| Position fermée avec stop toujours actif | Ordre résiduel dangereux signalé |
| État UNKNOWN, chaîne REPLACING/REPLACED ou statut incohérent | Revue obligatoire ; aucune continuité supposée |

Un résultat `CONSISTENT_SYNTHETIC_ONLY` signifie que les quantités du scénario
sont cohérentes, **pas** que le titre est effectivement protégé chez Trading212.
Un stop au marché peut glisser en gap ; un stop-limit peut ne pas remplir.
Le module n'annonce donc jamais un prix de sortie garanti.

## Tests et preuves

**124 tests ciblés passent**, dont **27 nouveaux** cas de protection.
Rapport : `artifacts/fr/research/trading212_protection_17f/tests-20261009-v1/junit.xml`.
Les suites de reprise persistante, réconciliation, mapping, lecture DEMO,
contrat FR, routeur, doubles et coûts restent vertes.

```powershell
python -m pytest tests/test_fr_trading212_protection_17f.py tests/test_fr_trading212_durable_17e.py tests/test_fr_trading212_reconciliation_17d.py tests/test_fr_trading212_mapping_17c.py tests/test_fr_trading212_demo_17b.py tests/test_fr_broker_contract_17a.py tests/test_execution_broker_router_18a.py tests/test_execution_broker_doubles_18d.py tests/test_fr_execution_costs.py --no-cov -q
```

Les courses sont représentées par états/fills adverses synthétiques. Ce n'est
pas une mesure de latence réelle ni une validation du moteur de matching du
courtier. L'auditeur n'est pas raccordé au journal 17-E pour piloter des sorties.

## Décision et suite bornée

La [vérification publique 17-G](sprint_17g_decision_capacites_trading212.md)
et les questions de support sont préparées. La mention ancienne OCO limité
aux CFD ne suffit pas à qualifier les capacités API Invest en 2026.

Ne pas brancher `submit_oco_protection` ou `replace_stop_order` du moteur FR
sur des appels indépendants supposés atomiques. Ne pas reprendre les garanties
de l'adaptateur Alpaca US pour Trading212. Aucun changement de stratégie
(TP supprimé, stop seul, watcher local) n'est autorisé implicitement par cet audit.

Deux voies à décider avant un adaptateur d'exécution :

1. Obtenir une confirmation technique du courtier sur OCO/bracket, réservation
   des quantités et remplacement, puis un protocole de test DEMO autorisé.
2. Choisir explicitement un contrat de protection différent et en tester la
   parité avec le risque/backtest ; cela modifie la politique et demande un GO.

Sans preuve suffisante, conserver le shadow sans ordre plutôt que présenter
une émulation locale comme une protection native. Les réserves de données
Sprint 16 et du MIC d'exécution restent ouvertes. **Sprint 17 partiel ; pas de
GO PAPER autonome ou LIVE.**
