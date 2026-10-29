# Diversification factorielle selon le capital du compte

Règle demandée le 29 octobre 2026, seuil initial de 25 000 $ ensuite porté à
100 000 $ à la demande de l'utilisateur. Configuration dans `config.yaml`, section
`risk_management` :

```yaml
factor_diversification_check_enabled: false
min_factor_diversification: 2
factor_diversification_small_account_threshold: 100000.0
factor_diversification_small_account_min: 1
```

Depuis la demande suivante du 29 octobre, `factor_diversification_check_enabled`
est `false` dans la configuration opérationnelle. Seul le minimum de facteurs
significatifs est alors ignoré, avant/après sizing et lors de la revalidation
Winner. La décomposition et les données qualifiées restent requises ; les
limites de bêta, concentration factorielle, secteur, corrélation et capital
restent actives. Ce réglage global concerne tous les comptes qui chargent
cette configuration. Il faut redémarrer un watcher existant pour charger le
nouveau code. Les anciens snapshots sans cet interrupteur gardent `true`.
Le tableau ci-dessous s'applique lorsque le contrôle est réactivé (`true`).

| Equity courante du compte, USD | Facteurs significatifs requis |
| --- | ---: |
| Strictement inférieure à 100 000 $ | 1 |
| Égale ou supérieure à 100 000 $ | 2 |

Un facteur significatif conserve sa définition : contribution supérieure à
10 % du risque total estimé. La règle réduit le nombre requis ; elle ne change
ni les facteurs ni leur calcul. Les plafonds de bêta, de concentration factorielle,
de secteur et de corrélation restent indépendants.

Le seuil porte sur l'equity effective utilisée par `RiskConfig`, issue du compte
broker pour le risque opérationnel et la revalidation Winner. Le buying power,
le compte nommé `default/test1/test2` et le preset d'univers archivé avec le
filtre ne remplacent pas ce capital. Le preset `capital_2001_5000` d'une sélection
partagée ne détermine donc pas le minimum applicable : c'est son capital réel
comparé au seuil configuré qui le détermine.

Le contrôle utilise `effective_min_factor_diversification` avant et après le
sizing dans `PortfolioBuilder`, ainsi que dans le contexte factoriel du watcher.
Le minimum normal reste conservé dans `min_factor_diversification`. Une mise à
jour de l'equity dans un replay recalcule la règle, y compris lors du franchissement
du seuil. La configuration figée et son fingerprint contiennent les paramètres.
Les anciens snapshots sans seuil continuent d'exiger leur minimum historique.
Cette règle ne fournit pas les historiques factoriels qualifiés qui manqueraient
à un replay ; elle ne lève aucun autre blocage de données.

Mettre `factor_diversification_small_account_threshold: null` désactive cette
adaptation. Le seuil doit être positif fini et les minima des entiers >= 1.
Le résumé de l'étape 11 expose `factor_diversification_policy` : capital retenu,
minimum normal, minimum effectif et paramètres du petit compte. L'approbation
du watcher expose `factor_min_diversification`.

Lorsque le contrôle est actif, aux capitaux observés, `default` (~2 000 $), `test1` (~59 500 $)
et `test2` (~62 000 $) exigent désormais un facteur. Aucun ordre, ancien
résultat ou paramètre figé d'une campagne n'est réécrit par cette livraison.
Les services watcher doivent être redémarrés pour charger la version modifiée.
