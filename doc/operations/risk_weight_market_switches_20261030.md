# Interrupteurs poids sectoriel et concentration marché — 30/10/2026

Évolution suivante : [interrupteur de corrélation et relances](correlation_check_switch_20261030.md).
Les résultats et contrôles conservés ci-dessous décrivent le passage précédent.

Demande utilisateur : désactiver ces deux contrôles et relancer les étapes
11 et 12 sur default puis test1, en PAPER.

```yaml
risk_management:
  sector_ticker_limit_enabled: false
  sector_weight_limit_enabled: false
  market_factor_concentration_check_enabled: false
```

Les deux dernières clés constituent cette évolution :

- `sector_weight_limit_enabled` contrôle le plafond de poids sectoriel à
  l'entrée et à la revalidation finale, ainsi que les variantes d'exposition
  sectorielle `exposure` et `hybrid`. Les règles de corrélation du mode hybride
  restent distinctes.
- `market_factor_concentration_check_enabled` contrôle uniquement le plafond
  de contribution du facteur `market` à la variance du portefeuille. Le plafond
  bêta, les plafonds de contribution `size`/`momentum` et la qualification des
  entrées factorielles ne sont pas désactivés.

Les flags transitent dans le builder de portefeuille et le risque natif utilisé
par le watcher. Le régime peut encore fournir les valeurs des plafonds, mais
ne réactive pas les interrupteurs. Les résumés de risque les exposent dans
`risk_controls_effective`. Les valeurs sont strictement booléennes.

Le YAML opérationnel est à `false`. Les valeurs du dataclass restent `true`
pour lire les anciens snapshots sans modifier implicitement leurs règles.
Réactiver une clé à `true` réapplique son seuil configuré. Les autres limites
(cash, poids individuel, nombre total, corrélation, bêta, drawdown) restent
indépendantes.

## Résultat PAPER vérifié

Ordres d'achat ouverts, aucun rempli lors de la vérification :

| Compte | Titres et quantités | Évolution |
| --- | --- | --- |
| default | BAND 6, COHU 3, UCTT 2, SIMO 1 | UCTT repris par le watcher sur son plan existant ; nouvel ordre SIMO |
| test1 | BAND 107, SIMO 24 | BAND précédent conservé ; nouvel ordre SIMO ; UCTT bloqué par corrélation native |

COHU/test1 garde sa campagne antérieure, sans écrasement ni double soumission ;
le journal du watcher confirme aussi son refus par corrélation native.
Les quantités des ordres déjà ouverts n'ont pas été augmentées. Le risque a
retenu COHU 106, UCTT 104 et SIMO 24 sur test1 après réduction au poids maximal
par titre ; cela ne garantit pas leur autorisation finale d'exécution.

Les résumés finaux confirment les trois flags à `false`. Les services default
et test1 ont été rechargés avant les relances ; test2 a uniquement rechargé son
watcher, sans nouvelle relance 11/12. Les trois services sont vérifiés sains.
Les SL/TP Winner gelés ne sont pas modifiés par ces interrupteurs.

## Validation et archives

115 tests ciblés réussis : admission et revalidation sectorielles, paramètres
booléens, maintien du plafond bêta et des autres concentrations, propagation
au risque natif et tests du modèle factoriel.

Dossier de l'opération :
`artifacts/operations/options_accounts_blackout_disabled/20261030T092819Z-317d8337/`.
Le bilan et la confirmation broker sont dans `summary.json` et
`weight_market_controls_final_verification.json`, avec les journaux par compte.

- Sélection partagée : `opt-41ee41f934d34a5d8179641fc71c66e8`.
- Risque default : `137ad74ec8b64872` ; exécution `d874fb17d4ef41e5`.
- Risque test1 : `a29f43a946204210` ; exécution `47fbba4dea5c47f9`.

L'erreur de certificat SMTP de notification reste distincte et n'a pas annulé
les décisions ni les ordres acceptés par Alpaca.
