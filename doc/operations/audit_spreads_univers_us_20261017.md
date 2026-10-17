# Audit des spreads de l’univers tradable US — 17 octobre 2026

## Conclusion

Le calcul arithmétique n’est pas en cause. La sélection utilise des quotes
historiques **IEX**, et non un bid/ask consolidé SIP. Sur le petit échantillon
contrôlé, ce choix exclut des titres dont le spread consolidé est inférieur au
seuil. Ne pas relever arbitrairement ce seuil pour compenser le flux.

Audit en lecture seule : aucune cotation, publication d’univers, configuration,
réservation de risque, sélection LLM ou ordre n’a été modifié. Les seuls ajouts
sont le script de recherche, ses tests, ce document et les résultats locaux.

## Périmètre et résultats en base

Publication canonique `universe-1e6cf5f693b24be3881eb38186d77572`, séance
du **16 octobre 2026**, preset `capital_2001_5000`, 1 790 titres :

| Premier motif bloquant | Titres |
| --- | ---: |
| Spread supérieur au maximum | 1 233 |
| Liquidité insuffisante | 94 |
| Prix inférieur au minimum | 69 |
| Quote indisponible | 41 |
| Historique insuffisant | 40 |
| Blackout résultats | 16 |
| Autorisés | 297 |

Ces motifs sont ordonnés : un titre peut échouer aussi à un contrôle ultérieur.
Une correction du spread ne signifie pas automatiquement qu’il devient tradable.

Reproduction du choix du publieur : dernière `quote_date` avec spread non nul
entre J−5 jours calendaires et J, pour chaque symbole.

- 1 650 quotes disponibles ; 140 absentes. Parmi ces absences, 99 titres sont
  déjà exclus par un motif antérieur et 41 par `quote_unavailable`.
- **0 erreur de formule** sur les 1 650 quotes :
  `(ask − bid) / ((ask + bid) / 2) × 10 000` donne bien les bps stockés.
- **0 divergence** entre les spreads copiés dans cette publication et ceux
  actuellement sélectionnés en base.
- Aucun bid/ask invalide selon les contrôles fini, positif et ask ≥ bid ; aucune
  taille manquante ou non positive parmi ces quotes.
- 1 649 quotes datent de J ; ACVA utilise le 15 octobre, autorisé par la fenêtre
  J−5/J actuelle. Ce n’est pas une quote hors séance de sa propre journée.
- 1 629 quotes se situent dans les 60 dernières secondes de la séance J.
  La médiane est à une seconde de la clôture. Pas d’indice d’un décalage général
  Paris/New York : les horodatages sont interprétés en UTC et comparés à la
  séance NYSE (13:30–20:00 UTC ce jour-là).
- Spread médian des 1 233 titres exclus pour ce motif : **11,2445 %**.

## Comparaison fournisseur bornée

22 requêtes HTTP GET, compte `default`, **11 symboles uniques**, deux flux par
symbole, toutes HTTP 200. Aucun appel aux API d’ordres. Fenêtre identique à la
collecte : séance entière, dernière quote (`sort=desc`, `limit=1`).

Échantillonnage déterministe, sans rendement futur : sept positions réparties
dans le classement des spreads exclus, FMC, et trois témoins autorisés. KE est
aussi le maximum de cette liste ; sa déduplication explique les 11 et non 12
symboles. Il ne s’agit pas d’un sondage aléatoire représentatif.

| Symbole | Spread stocké / IEX (%) | SIP (%) | Observation |
| --- | ---: | ---: | --- |
| IONS | 0,6056 | 0,0931 | Sous le seuil en SIP |
| EMBJ | 8,5072 | 0,0277 | Sous le seuil en SIP |
| PAG | 10,0427 | 0,1224 | Sous le seuil en SIP |
| SCI | 11,2445 | 0,0369 | Sous le seuil en SIP |
| TECK | 26,6305 | 0,0464 | Sous le seuil en SIP |
| NXRT | 28,4624 | 0,0545 | Sous le seuil en SIP |
| KE | 30,9728 | 0,2706 | Sous le seuil en SIP |
| FMC | 12,9821 | 0,1768 | Reste exclu par le prix de 5,66 $ |
| AB | 0,3160 | 0,0287 | Témoin autorisé |
| JD | 0,0370 | 0,0370 | Témoin autorisé |
| ZTO | 0,0496 | 0,0496 | Témoin autorisé |

Le seuil courant du preset est **60 bps = 0,60 %**. Il est vérifié dans le code
et la configuration présents ; cette mesure n’est pas une reconstruction
indépendante de toutes les configurations historiques.

Les 11 couples bid/ask IEX correspondent exactement aux valeurs stockées.
Les 11 timestamps correspondent après arrondi à la seconde, cohérent avec la
précision `DATETIME` sans fractions de seconde ; la comparaison par simple
troncature ne correspond que pour deux quotes. Les réponses fournisseur brutes
conservent leurs timestamps à haute précision.

Exemple KE : IEX 21,72 / 29,68 $, contre SIP 25,83 / 25,90 $. Le spread large
n’est donc ni une erreur de calcul ni une preuve que l’ensemble du marché
présentait réellement ce même écart.

Les sept titres dont le premier motif était le spread passent tous ce contrôle
avec SIP. **Ne pas extrapoler que les 1 233 titres deviendraient tous autorisés**
ni que ces cotations historiques garantissent un spread d’exécution futur.

## Chaîne de code et origine

- `dataIntegrityEngine/sync_latest_quotes.py` : mode historique lorsque les bornes
  sont fournies ; dernière quote de la séance, appel sans paramètre `feed`.
- `service/alpaca/clientAlpaca.py` : cet appel a `feed=DEFAULT_FEED`, actuellement
  `iex`. La configuration du fournisseur des quotes *latest* n’est pas une
  sélection du flux de ce chemin historique.
- Historique IHM : étape `sync_latest_quotes`, lancement le 17 octobre à
  00:15:24 Paris, période du 9 au 16 octobre, univers
  `config/univers_batch/univers_filtred_tradable.txt`. Fin à 00:39:08 ;
  1 650 lignes persistées, logs mentionnant IEX.
- `common/publish_tradable_universe.py` : copie le spread déjà calculé, sans
  contrôle du flux ni de l’heure précise au-delà de la fenêtre de dates.
- `stock_quote_snapshots` n’a **ni colonne provider/feed ni archive brute**.
  Le schéma à clé symbole/jour peut écraser une ancienne quote. La correspondance
  du code, des logs et du petit échantillon est probante ici, mais ne constitue
  pas une provenance exhaustive scellée de tout l’historique.

## Remédiation proposée, non exécutée

**Mise à jour** : le GO ultérieur a déclenché la mise en œuvre décrite dans
[Correctif quotes SIP](correctif_quotes_sip_20261017.md). La présente section
conserve les recommandations formulées au moment de l’audit, avant ce GO.

1. Rendre le flux historique explicite et configurable ; privilégier **SIP
   historique** pour mesurer un spread consolidé après clôture. Ne pas retomber
   silencieusement sur IEX en cas d’erreur de droits, quota ou réseau.
2. Conserver fournisseur, flux, timestamp précis et provenance/conditions de la
   quote. Qualifier validité bid/ask, tailles, séance et ancienneté.
3. Prévoir une reprise ciblée qui **requalifie les lignes existantes** : un simple
   relancement les ignore actuellement et ne corrigerait donc pas le problème.
   Préserver la traçabilité des anciennes publications.
4. Vérifier la couverture SIP du périmètre complet, puis republier explicitement
   pour la bonne date et le bon preset ; refaire les autres contrôles sans les
   contourner. Ne pas modifier des décisions/ordres historiques par rétroaction.
5. Conserver un contrôle de quote fraîche à l’entrée : une quote de clôture J
   n’atteste pas des conditions de marché à l’exécution J+1.

La documentation officielle distingue IEX (une place) du SIP consolidé et permet
les requêtes historiques SIP avec `end` vieux d’au moins 15 minutes sans
abonnement temps réel. L’accès a été effectivement vérifié sur ce compte pour
ces 22 requêtes, sans promettre une couverture universelle :
[FAQ Alpaca](https://docs.alpaca.markets/us/docs/market-data-faq),
[quotes historiques](https://docs.alpaca.markets/us/reference/stockquotesingle-1).

## Reproduction et pièces

```powershell
python -u -m scripts.research.us_tradable_quote_audit `
  --universe-run-id universe-1e6cf5f693b24be3881eb38186d77572 `
  --output artifacts/research/us_tradable_quote_audit/NOUVEAU_DOSSIER `
  --compare-feeds
```

Sans `--compare-feeds`, seule la base est lue. Le dossier doit être neuf.
Le script démarre une transaction SQL en lecture seule et ne contient aucun
appel de publication ou de persistance SQL.

Résultats : `artifacts/research/us_tradable_quote_audit/audit-20261017-v1/` :
`report.json`, `quote_inputs.csv` (1 790 lignes), `provider_comparison.json`
(paramètres sans secrets et réponses fournisseur). Aucun secret n’est archivé.

Tests : `tests/test_us_tradable_quote_audit.py`, **9 réussis**. Ils vérifient les
bps, les quotes invalides, les statistiques vides et l’échantillonnage borné et
déterministe, sans SQL, réseau ou ordre.
