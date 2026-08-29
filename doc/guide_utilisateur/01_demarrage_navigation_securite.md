# Démarrage, navigation et sécurité opérateur

## Avant d’ouvrir l’application

L’application repose sur plusieurs états externes : base de données, fichiers
d’artefacts ML, configuration, fournisseur de marché et éventuellement broker.
Une interface qui s’affiche ne garantit donc pas que la chaîne métier est prête.
Au premier démarrage, contrôler au minimum :

1. l’environnement affiché dans la Vue d’ensemble ;
2. la connectivité base et la fraîcheur des données ;
3. le compte broker et le mode paper/live ciblés ;
4. l’absence d’un run actif ou d’un verrou résiduel ;
5. la disponibilité des artefacts nécessaires au ML ;
6. l’état du kill switch avant toute exécution.

Les secrets ne doivent pas être recopiés dans un rapport, une capture ou un
ticket. La page Paramètres permet d’éprouver certaines connexions et de faire
tourner des secrets, mais la documentation ne fixe aucune valeur de secret.

## Comprendre la sidebar

La navigation est regroupée en six sections : Accueil, Workflow &
Orchestration, Trading, Analyse & Recherche, Configuration, puis Conformité &
Admin. Le flux quotidien n’est pas simplement l’ordre visuel de toutes les
pages. Son chemin logique est :

```text
Vue d’ensemble
  → Pipeline
  → Screening / ML
  → Risk
  → Execution
  → rapprochement broker et supervision
```

Les pages de recherche, d’administration et de conformité interviennent en
support ou à une fréquence différente.

## Vue d’ensemble : contrôle d’ouverture

La page d’accueil agrège notamment les positions ouvertes et leur PnL, l’état
de la base, le quota EODHD, la santé du pipeline, l’état de calibration du
screener et une sélection des meilleurs candidats. Elle sert à repérer une
anomalie, pas à reconstruire tout son diagnostic.

Lecture recommandée :

- une fraîcheur anormale doit être investiguée dans Pipeline et Supervision ;
- un quota faible doit faire réévaluer la profondeur ou l’étendue d’une collecte ;
- une calibration absente ou périmée doit être vérifiée avant d’interpréter les
  scores comme comparables ;
- un PnL broker ne doit pas être confondu avec le PnL d’un backtest ou d’une
  cible de portefeuille.

## Environnements et comptes

L’application supporte plusieurs comptes Alpaca et plusieurs contextes. Le
compte actif doit être relu sur les pages qui mutent ou rapprochent l’état
broker. Ne jamais déduire le compte ciblé d’un ancien onglet ou d’un nom de run.
La page Comptes Alpaca permet la consultation ; la page Exécution réaffiche son
propre contexte au moment des actions sensibles.

Le dry-run signifie que la chaîne simule ou prépare l’action sans envoyer les
ordres attendus au broker. Il ne signifie pas nécessairement que toutes les
écritures locales sont neutralisées : il faut lire le récapitulatif de l’action
concernée.

## Confirmations et opérations destructrices

Plusieurs écrans exigent une phrase, une case ou un motif avant une opération à
risque : gros téléchargement, kill switch, nettoyage d’artefacts, purge DB,
reset ML/backtests, action live. Cette friction est volontaire.

Avant confirmation :

- vérifier la portée exacte (run, batch, compte, dates, symboles) ;
- télécharger ou sauvegarder les éléments nécessaires ;
- s’assurer qu’aucun processus actif n’écrit dans la même ressource ;
- préférer une action ciblée à un reset global ;
- noter l’identifiant de run et le motif opérateur.

## Verrous et concurrence

Le pipeline et le backtesting utilisent un verrou inter-processus partagé pour
éviter deux travaux incompatibles. Un bouton désactivé peut donc être le
comportement normal. Ne pas supprimer un verrou uniquement parce qu’un écran
semble inactif : la Supervision et le registre de processus doivent d’abord
confirmer que le propriétaire n’existe plus. Les processus récupérés après un
redémarrage de l’IHM peuvent rester suivis par leur PID et leur artefact de run.

## Vocabulaire minimal

| Terme | Sens opérationnel |
|---|---|
| run | exécution identifiée d’un workflow ou d’une commande |
| batch ML | campagne cohérente de modèles/prédictions |
| artefact | fichier persistant contenant modèle, métadonnées ou résultat |
| PIT | information disponible à la date simulée, sans regard vers le futur |
| champion | modèle gouverné comme référence ; à distinguer du modèle réellement servi |
| gate | règle qui autorise, réduit, bloque ou dégrade un traitement |
| target | position souhaitée après risque, pas encore un fill |
| reconciliation | rapprochement entre état attendu, base et broker |

Pour le vocabulaire métier complet, utiliser également la page Glossaire et les
le [glossaire unifié](../20_glossaire.md).
