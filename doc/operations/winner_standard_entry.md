# Winner — entrée standard sans confirmation

Implémentation du 26 octobre 2026. Modification de contrat, **pas une preuve
de rentabilité**, ni une activation/qualification du compte courtier.

## Configuration

Dans le bloc existant `winner_pyramiding` de `config.yaml` :

```yaml
winner_pyramiding:
  enabled: true
  confirmation_bars: 0
```

Conserver les autres champs du bloc. Ne pas créer un second bloc YAML portant
le même nom. Ce document ne change pas les valeurs opérationnelles.

- **0** : après approbation de l'étape 11, l'étape 12 crée une campagne durable
  et tente de transmettre un ordre standard sans cassure ni attente de bougies.
  Type `market` / `limit`, buffer de limite, fenêtre de soumission et limite de
  gap sont figés depuis la configuration d'exécution de cette étape.
- **1–12** : comportement précédent inchangé : le watcher attend une cassure
  fraîche du plus haut régulier précédent, confirmée par N clôtures 5 minutes,
  puis revalide le risque avant l'ordre limite IOC.
- `initial_position_fraction` accepte actuellement **0.5 ou 1.0 seulement**.
  Une valeur telle que 0.75 est une erreur de configuration, pas un arrondi.

Le mode 0 utilise un ordre **DAY**, sans `extended_hours`. Un envoi hors séance
ne signifie pas un achat immédiat : le courtier peut mettre l'ordre en attente
pour la prochaine séance régulière. Un ordre limite peut ne jamais être exécuté ;
un ordre marché peut subir un gap. Aucun prix d'ouverture n'est garanti.
Les fenêtres `post_close`, `pre_open`, `both` sont conservées pour la soumission
hors séance ; une entrée encore autorisée peut être tentée en séance régulière.

## Risque et protections

Le mode 0 ne contourne pas les contrôles : watcher local sain et compatible,
compte/marché exacts, données daily qualifiées, cotation SIP temps réel récente,
spread, capital disponible, quantité entière, budget approuvé, corrélations,
secteur, régime, drawdown et événements sur titres restent requis.

**SIP refusé ou trop ancien = nouvelle entrée bloquée**, y compris hors séance.
L'absence de confirmation ne permet pas de substituer un cours retardé ou IEX.
Une revalidation valide au moment de l'envoi n'est pas une garantie sur le gap
du prochain open. Un ordre marché déjà en attente peut bloquer les admissions
suivantes si sa réservation de capital ne peut pas être qualifiée.

Une campagne n'est pas un ordre exécuté. Le watcher réconcilie l'ordre exact
par son identifiant durable et protège chaque quantité réellement achetée :

- SL et TP calculés depuis le **prix de fill réel**, selon le profil Winner figé ;
  `take_profit_pct: null` = pas de TP de prix ;
- trailing Winner après observation de barres régulières terminées, sans
  desserrer le SL ; pas le trailing/TP standard du parcours historique ;
- horizon calculé au **premier fill effectif** : avec 20, entrée incluse,
  sortie prévue à l'ouverture de la 21e séance officielle ; les fractions
  exécutées ensuite et les renforcements ne remettent pas ce compteur à zéro ;
- un renforcement reste optionnel et gagnant : avec confirmation 0 il exige
  **au moins une clôture 5m terminée après l'entrée** au-delà du seuil configuré.
  Aucun renforcement sur une simple absence de bougies.

Le watcher doit continuer à tourner pour poser/réconcilier les protections après
fill, ajuster le trailing et effectuer les sorties temporelles. Les stops/TP
déjà confirmés chez le courtier ne dépendent pas de sa présence, mais leur pose
initiale et leur suivi local ne sont pas garantis si le PC est arrêté.

Le profil, les conditions de l'ordre et le budget sont figés dans
`execution_winner_campaigns.state_json`. Une modification YAML ne remplace pas les
campagnes existantes. Une réponse de soumission perdue n'autorise **aucun second
achat** : réconciliation préalable, même si une recherche retourne 404.
Les fills partiels reçoivent leurs protections sans doubler la quantité.
Un ordre DAY expiré/annulé n'est pas automatiquement remplacé.
Si le watcher observe la désactivation des entrées ou l'expiration du plan,
il demande l'annulation du reliquat d'entrée déjà transmis et conserve/protège
les quantités éventuellement achetées pendant la course d'annulation.

Après mise à jour des sources, **redémarrer le watcher local avant l'étape 12** :
le contrôle de santé refuse un processus antérieur à cette implémentation.

## Replay et vérification

Le replay intraday partage le coordinateur, les niveaux Winner et la
revalidation native du risque. Pour le mode 0, il utilise les opens 5m observés
de la séance régulière ; les limites DAY en attente réservent du capital et
expirent au close. Il n'invente pas un fill intrabar à partir d'un low futur.
Cette approximation peut manquer des fills limites réels. Pas de cotation
préouverture historique qualifiée : pas de parité complète annoncée avec live.
Ces limites sont enregistrées dans `standard_entry_assumptions` du rapport.

Tests hors ligne : `test_winner_standard_entry.py`, suites Winner existantes,
`test_winner_intraday.py` et branche d'orchestration de `test_executor.py`.
Ils n'émettent aucun ordre et n'appellent aucun fournisseur. Les fixtures
isolent le profil Winner du YAML opérationnel modifiable par l'utilisateur.
