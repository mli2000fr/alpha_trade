# Dépannage et questions fréquentes

## Pourquoi partial alors que missing_count vaut zéro ?

Dans oracle_atr_market_regime_daily, missing_returns_policy est le mode choisi,
pas le résultat. Lire movement_quality/statut, compteurs et couverture : une
séance peut être complète avec la politique partial. Les futures listes ne sont
pas des prédictions LONG/SHORT ; un rendement immature ne doit pas être mis à zéro.

## Pourquoi actif ne signifie pas collecte opérationnelle ?

enabled décrit la configuration ; vérifier installation, dernier run et source
amont. CN D10/17-C peuvent rester actifs tout en manquant D6/D9 bloqués. FR
daily bars publie en staging, pas automatiquement dans les tables canoniques.
Rouge/gras = échec opérationnel ; noir ⛔ ⚖️ = droits/prudence à ne pas contourner.
[Catalogue](../operations/catalogue_batchs_actuel.md).

## Pourquoi GPT coché dans l'IHM n'est pas lancé par us_pipeline ?

Le scheduler construit des options fraîches, pas celles de la session Streamlit.
Son llm_filter_enabled reste false. Le filtre activé explicitement dans Pipeline
est prospectif PAPER/default, après clôture J et avant ouverture suivante ; il
n'est pas compatible avec une recherche Web historique/shadow.

## Méthode générale

Toujours diagnostiquer du plus haut niveau vers l’objet fautif : workflow → run
→ étape → objet métier → dépendance externe. Conserver les identifiants et la
première erreur utile. Éviter reset, purge ou relance globale tant qu’une reprise
ciblée reste possible.

## Le bouton de lancement est désactivé

Causes fréquentes : run du même type actif, verrou pipeline/backtesting, batch ML
manquant, confirmation non saisie, dépendance non satisfaite, contexte DB ou
broker indisponible. Consulter le message adjacent et Supervision Ops. Ne pas
modifier directement l’état de session ou le fichier de verrou.

## Le run reste `running`

Vérifier PID, activité des logs, horodatage, processus récupéré et service
externe. Un calcul silencieux peut être valide. Si le PID n’existe plus et que
le registre ne se réconcilie pas, documenter l’état avant toute action sur le
verrou.

## Le pipeline termine mais les données manquent

Contrôler périmètre demandé, univers prévisualisé, date, compteurs par étape et
avertissements. `completed` décrit la commande, pas une garantie de couverture
universelle. Vérifier tables/artefacts aval et gates.

## Les scores ont changé par rapport à hier

Comparer univers, date, données disponibles, poids, calibration et version des
composants. Le rang peut changer sans variation forte du score brut si la
population change.

## Une prédiction est absente

Vérifier couverture de features, `available_at`, batch, artefact, mapping du
symbole, drift/gate et erreur d’écriture. Distinguer absence attendue/fallback et
échec.

## Champion et modèle servi divergent

Rechercher promotion incomplète, rollback, artefact invalide ou configuration
de serving. Ne pas recopier simplement le fichier champion : valider manifeste,
compatibilité et procédure de promotion.

## Le risque rejette un bon candidat

Le score ne prime pas sur les contraintes. Lire motif, exposition existante,
secteur, capital, régime et gates. Comparer taille avant/après et, si disponible,
shadow compare.

## Une cible n’apparaît pas au broker

Suivre cible → request → ordre → statut. Vérifier dry-run, compte, horaires,
fractionnement, buying power, rejet et kill switch. Une cible n’est pas un ordre.

## Position locale et broker divergent

Geler les nouvelles actions si la divergence est matérielle. Examiner fills,
ordres partiels, corporate actions, lots et réconciliation J+1. Le broker est la
réalité d’exécution ; la correction locale doit conserver l’audit.

## Protection absente

Vérifier parent, fill, ordre enfant, watcher et événements. Une annulation via
kill switch peut avoir supprimé la protection. Traiter comme prioritaire si une
position est ouverte.

## Backtest sans trades ou avec couverture faible

Contrôler univers PIT, `stock_scores_history`, prédictions, batch, plage, seuils,
gaps et filtres. Ne pas abaisser des seuils avant d’avoir identifié si l’entrée
est simplement absente.

## Backtest et live divergent

Utiliser la page Parité. Comparer données/date de disponibilité, univers,
batch/modèle, contrat d’exécution, portefeuille initial et configuration. Une
divergence de fill n’a pas la même cause qu’une divergence de décision risque.

## Quota fournisseur faible

Arrêter les collectes non essentielles, estimer la charge, réduire le périmètre
ou planifier. Ne pas mélanger silencieusement des fournisseurs sans cross-check.

## Quand utiliser reset ou purge ?

Seulement lorsqu’une reconstruction complète est nécessaire, sauvegardée et
comprise. Pour un artefact, run ou table isolé, préférer les opérations ciblées.

## Informations à joindre à un incident

- horodatage et environnement ;
- page et action ;
- compte (sans secret) ;
- workflow/run/batch ;
- symbole et date as-of ;
- statut, première erreur et extrait minimal de log ;
- effet observé et état attendu ;
- actions déjà tentées ;
- présence d’ordres/positions réels.

