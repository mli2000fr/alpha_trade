# E6-B0 — Faisabilité des options après Oracle

## Résultat

E6-A a démontré une forte concentration OOF de l’amplitude dans le TOP20 Oracle.
E6-B0 vérifie si les données permettent de transformer ce constat en test
économique d’un straddle, sans inventer une prime ou un spread.

Le verdict est **GO pour un pilote REST borné à 2022–2025**, mais **pas encore GO
pour une campagne complète par flat files**.

## Preuves d’accès du 6 septembre 2026

| Source | Résultat | Usage possible |
|---|---|---|
| contrats historiques avec `as_of` seul | HTTP 200 | reconstruire call/put, strike et expiration PIT |
| agrégats journaliers d’un contrat expiré | HTTP 200 | prix/volume de transaction historique |
| trades d’un contrat expiré | HTTP 200 | historique depuis le 2 juin 2014 |
| quotes NBBO d’un contrat expiré | HTTP 200 | bid/ask exact depuis le 7 mars 2022 |
| catalogue flat files options day/minute | annoncé `entitled=true` | transport potentiel en masse |
| `/flatfiles/list` | HTTP 502, archive temporairement indisponible | inventaire impossible au moment du test |
| URL signée `/flatfiles/url` | HTTP 200 | URL délivrée |
| lecture de l’objet signé | HTTP 401 | téléchargement effectivement bloqué |

La documentation Eroya confirme les profondeurs trades/quotes, les routes
historiques et les archives options par séance. Elle indique aussi que la
livraison dépend des droits fournisseur/OPRA. Un droit annoncé dans le catalogue
ne vaut donc pas preuve de téléchargement réussi.

Le probe a aussi établi une subtilité d’API importante : `as_of=2024-07-01`
retourne correctement les contrats alors actifs et `expired=true` retourne les
contrats aujourd’hui expirés, mais combiner les deux filtres retourne zéro ligne.
La reconstruction PIT doit utiliser **`as_of` sans `expired=true`**.

## Pourquoi les snapshots existants ne suffisent pas

La collecte locale contient seulement 44 contrats pour 12 symboles. Le
collecteur avait volontairement demandé deux lignes et deux pages par symbole :
les réponses sont triées depuis les premiers strikes et ne forment pas une chaîne
ATM complète. Elles représentent l’état courant de septembre 2026, pas les états
historiques des dates Oracle.

Un snapshot peut valider le schéma (`bid`, `ask`, IV, Greeks, open interest),
mais ne doit jamais être joint rétroactivement à 2018–2025.

## Contrat PIT préfixé pour E6-B1

```text
Oracle TOP20 OOF connu à la clôture J
        │
        ▼
Open action J+1 et contrôle du gap
        │
        ▼
Expiration 35–55 jours, même strike call/put le plus proche
        │
        ▼
Entrée ≥ 09:35 ET : achat call ask + put ask
        │
        ├── valorisation H3
        ├── valorisation H5
        ├── valorisation H10
        └── valorisation H20
                 vente call bid + put bid avant 15:55 ET
```

- expiration au moins cinq jours calendaires après la sortie ;
- aucune interpolation si un côté du NBBO manque ;
- aucun `last_trade` utilisé comme substitut du prix exécutable ;
- spread payé deux fois implicitement par le chemin ask → bid ;
- commissions ajoutées séparément ;
- paire call/put strictement au même strike et à la même expiration ;
- fenêtres de split, contrat ajusté ou changement de ticker isolées ;
- comparaison quotidienne appariée TOP20, NEXT20 et REST80.

## Campagne proposée

### E6-B1 — pilote REST

Période autorisée par la profondeur NBBO : 7 mars 2022 au 11 juillet 2025.
Utiliser un calendrier de dates préfixé et tous les candidats de ces dates. Il
ne faut pas choisir a posteriori les jours dont les options sont rentables.

Le pilote doit d’abord mesurer : taux de contrat trouvé, taux de paire ATM,
taux de NBBO complet à l’entrée et à chaque sortie, spread médian, volume et
concentration par symbole. Aucun résultat de PnL n’est interprétable si la
couverture dépend fortement de la liquidité future.

### E6-B2 — écran large

À lancer seulement lorsque les flat files sont effectivement téléchargeables.
Les fichiers day/minute couvrent les transactions de tout le marché mais pas le
NBBO avant mars 2022. La période 2018–2022 peut documenter l’amplitude des primes
et le volume ; elle ne constitue pas une confirmation exacte ask → bid.

### E6-B3 — confirmation

Après le pilote, figer une seule politique de DTE/strike/liquidité et réserver
une période 2022+ intacte. Mesurer rendement net moyen et médian, drawdown,
semestres positifs, concentration et avantage contre NEXT20/REST80.

## Limites économiques

La réussite d’E6-A ne garantit pas la réussite d’un long straddle. L’Oracle peut
simplement reconnaître les titres auxquels le marché des options facture déjà
une volatilité implicite très élevée. E6-B doit donc répondre à :

> Le mouvement réalisé après le signal Oracle excède-t-il la prime et le spread
> déjà exigés par les vendeurs d’options ?

Sans prix exécutable historique, la réponse reste inconnue.

## Implémentation

- `modelFactory/oracle_options_feasibility.py` : audit reproductible des snapshots
  et décision à partir des preuves d’accès ;
- `tests/test_oracle_options_feasibility.py` : paires call/put, accès REST,
  blocage flat files et contrat ask → bid ;
- artefact : `artifacts/models/shared_directional/oracle-options-feasibility-*/report.json`.

Références fournisseur : [documentation API Eroya](https://docs.eroya.co/llms.txt)
et [couverture de données Eroya](https://eroya.co/data).
