# Interrupteur de corrélation — 30/10/2026

Demande utilisateur : même principe que les interrupteurs sectoriels, désactivé
par défaut dans la configuration, puis relance PAPER de default et test1.

```yaml
risk_management:
  correlation_check_enabled: false
```

`false` désactive les veto de corrélation suivants :

- filtre Pearson signé entre candidats du builder, utilisé en live et replay ;
- variante de corrélation factorielle si `use_factor_correlation_filter=true` ;
- contrôle intra-sectoriel du mode hybride ;
- comparaison native entre le candidat Winner et les positions/achats en attente ;
- revalidation de corrélation factorielle du contexte live.

`true` réactive ces contrôles avec leurs seuils configurés. Il ne faut pas
modifier artificiellement ces seuils pour simuler la désactivation. Le champ
exige un vrai booléen. Le défaut opérationnel YAML est `false` ; le défaut du
dataclass reste `true` pour la compatibilité des anciennes configurations
figées sans ce champ.

Les budgets, quantités entières, capacité broker, poids individuel, plafond
bêta et données factorielles qualifiées restent contrôlés. Désactiver le veto
de corrélation n'efface pas les besoins d'historique des autres contrôles.
Les paramètres précédemment désactivés (nombre de titres sectoriels, poids
sectoriel, concentration du facteur marché) gardent leur état explicite.

## Résultat des relances

Ordres d'achat ouverts lors de la confirmation broker, aucun rempli :

| Compte | BAND | COHU | UCTT | SIMO |
| --- | ---: | ---: | ---: | ---: |
| default | 6 | 3 | 2 | 1 |
| test1 | 107 | 106 | 103 | 24 |

Default conserve ses quatre achats sans changement. Les plans COHU et UCTT
déjà autorisés sur test1 ont pu être soumis par le watcher après rechargement
du risque natif : COHU 106 à limite 53,45 $, UCTT 103 à 54,75 $. Les quantités
sont bornées par les anciennes admissions et les contraintes fraîches, sans
augmentation des ordres précédents. BAND et SIMO de test1 sont conservés.

Les phases risque/exécution ont ensuite terminé sans nouvelles cibles, les
achats étant déjà ouverts. Aucun claim n'a été supprimé ni ancienne décision
réécrite. Les trois watchers sont vérifiés sains. Test2 a uniquement rechargé
son service, sans nouveau workflow 11/12 ; ses trois achats ouverts restent
BAND 55, COHU 56, SIMO 14 à la vérification.

## Validation et preuves

70 tests ciblés réussis : builder de portefeuille, risque Winner, absence de
données de corrélation quand le seul veto est désactivé, mode hybride,
corrélation factorielle et maintien des autres refus (régime/bêta notamment).

Preuves :
`artifacts/operations/options_accounts_blackout_disabled/20261030T093703Z-2b4314bc/`
contient `summary.json`, `correlation_final_verification.json` et les
confirmations/services par compte.

- Sélection : `opt-f0135d19131f49598dac3adac3f40882`.
- Risque default : `fe24c91d070a4294`.
- Risque test1 : `d4d7e62059f34001`.

Les ordres sont en attente : une acceptation broker ne prouve pas leur
remplissage. Le défaut de certificat SMTP de notification reste distinct.
