# Reprise bornée — sélection mensuelle TOP20, 24 octobre 2026

Le premier replay a échoué avant de produire un compte terminé. L'adaptateur
mensuel transmettait toutes les campagnes actives au runtime, même lorsque
le moteur demandait uniquement les sorties à échéance avant ouverture. Ce
passage ne fournit volontairement pas de bougies ; ZS et NTNX, non échus,
provoquaient donc `KeyError: 'bars'`. Ce n'est pas une lacune de prix qualifiée.

Le correctif versionné conserve exactement le sous-ensemble demandé. Un plan
non tenté réarmé peut uniquement remplacer sa propre identité dans ce
sous-ensemble. Aucun autre titre n'est ajouté. Les positions financées gardent
leur politique, les sorties restent contrôlées, aucune donnée n'est inventée.

L'ancien script, protocole, tests, documents et logs restent scellés inchangés.
Le nouvel adaptateur est `scripts.research.us_winner_monthly_scope_repair_20261024`.
L'amendement est dans le dossier du run, sous `scope-repair-20261024-v1` : erreur
initiale, empreintes des sources/archives, reçus de chaque compte terminé,
puis résolution seulement après les dix comptes audités.

Les 334 snapshots préparés (333 titres et SPY) sont réutilisés après contrôle
des empreintes. La reprise n'ouvre aucune connexion SQL, n'appelle aucun
fournisseur et ne modifie aucun autre run ni la production. Le compte interrompu
doit recommencer son calcul ; les comptes terminés sont conservés s'il en existe.

Tests : reproduction de l'élargissement fautif, sous-ensemble préouverture,
appel vide, plusieurs positions avec échéances distinctes, réarmement mensuel
et immutabilité des positions financées. Les audits cash/frais/prix/sorties du
protocole initial sont conservés, ainsi que ses limites exploratoires et PIT.
Validation : **55 tests ciblés passent**, dont sept tests du correctif. Aucun
compte n'était terminé au moment de l'échec ; les 334 snapshots sont présents.

Reprise : `python -u -m scripts.research.us_winner_monthly_scope_repair_20261024`.
Suivi : `artifacts/research/us_winner_monthly_selector/20261024-v1/progress.json`.
Les nouveaux logs portent le suffixe `scope-repair-v1`, sans écraser les anciens.
