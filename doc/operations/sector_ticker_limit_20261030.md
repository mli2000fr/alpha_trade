# Interrupteur du nombre de titres par secteur

Évolution suivante : [poids sectoriel et concentration du facteur marché](risk_weight_market_switches_20261030.md).
Les résultats et limites conservées ci-dessous décrivent le passage précédent.

Dans `config.yaml` :

```yaml
risk_management:
  sector_ticker_limit_enabled: false
```

`false` ignore uniquement la borne en **nombre de titres** par secteur à
l'admission, à la revalidation du portefeuille et dans le risque natif Winner.
`true` réactive cette borne, y compris celle fournie par le régime courant
(`max_tickers_per_sector=4` lors de l'opération).

Le maximum stocké dans un snapshot reste visible mais n'est pas appliqué
lorsque l'interrupteur est faux. Les limites de poids sectoriel, exposition,
facteurs, corrélation, capital, nombre total de positions et drawdown restent
actives. En mode hybride, le nombre maximal est ignoré mais les contrôles
d'exposition et de corrélation continuent à s'appliquer dès le troisième titre.

Le champ est strictement booléen. Le dataclass conserve `true` comme valeur
de compatibilité pour les anciens snapshots sans champ ; le défaut
opérationnel demandé dans le YAML est `false`. Les anciennes expériences et
liaisons scellées ne sont pas réécrites.

## Relances PAPER et confirmations

Étapes 11/12 relancées sur `default` et `test1`, séance signal du 29/10/2026.
Les nouveaux résumés confirment `sector_ticker_limit_enabled=false` malgré le
maximum historique du régime encore enregistré à 4.

| Compte | Achats ouverts après l'opération | Autres décisions |
| --- | --- | --- |
| default | BAND 6, limite 53,16 $ ; COHU 3, limite 53,45 $ | SIMO refusé par poids sectoriel ; UCTT réduit à 2 au risque puis à zéro avant envoi par le même plafond de poids |
| test1 | BAND 107, limite 53,16 $, ordre précédent conservé | COHU/UCTT refusés par concentration du facteur marché ; SIMO par poids sectoriel |

Aucun de ces achats n'était rempli à la dernière vérification. Le plan BAND
de default, déjà autorisé mais bloqué par le nombre de titres sectoriels, a
été repris par le watcher après rechargement du nouvel interrupteur. Son
budget et sa quantité gelés ont été conservés. Aucun doublon n'a été soumis.

Le service default a nécessité une reprise après une fin de processus
transitoire pendant son rechargement ; son ancien PID a été confirmé absent
avant libération du bail. Les trois services sont vérifiés sains. Test2 n'a
pas fait l'objet d'une relance 11/12 ; seul son watcher a été rechargé pour
appliquer la configuration globale.

Le score affiché `60.0%>60%` pour test1 est arrondi : le contrôle compare la
valeur complète. Il ne s'agit pas du contrôle de nombre de titres supprimé.
Le message générique `CAMPAIGN_RISK_OR_CAPACITY_EXHAUSTED` pour UCTT/default
est précisé par le journal natif : `max_sector_weight atteint`.

## Validation et preuves

83 tests ciblés réussis : activation/désactivation, revalidation finale,
mode hybride, maintien des autres plafonds, booléens, configuration et risque
Winner. Aucune modification des seuils de poids ou de facteurs.

- Premier passage/test1 :
  `artifacts/operations/options_accounts_blackout_disabled/20261030T080455Z-06f60d65/`.
- Reprise default et vérification finale des deux comptes :
  `artifacts/operations/options_accounts_blackout_disabled/20261030T080725Z-4e67297b/sector_limit_final_verification.json`.
- Risque default `393aad593c8b4f7d`, exécution `5d9c48e00cb9432a`.
- Risque test1 `ca1334bfa1024f61` : aucune nouvelle cible, étape 12 terminée
  sans nouvel achat ; BAND existant conservé.

Les erreurs de certificat de notification SMTP restent distinctes ; elles
n'ont pas annulé les décisions ni les ordres broker.
