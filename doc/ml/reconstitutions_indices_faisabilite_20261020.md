# Sorties d’indices et rebond — audit de faisabilité du 20 octobre 2026

## Décision

**Vérification des sources terminée. Piste bloquée pour le backtest historique
Russell, pas rejetée économiquement : aucune performance n’a été calculée.**

L’hypothèse proposée était un achat après la sortie effective d’un indice,
pour rechercher un rebond après une pression vendeuse temporaire. Le GO
portait d’abord sur la qualification gratuite des archives et de leur usage.
Le contrôle évite de monter un test sur une liste partielle ou dont les droits
de collecte ne sont pas qualifiés.

| Prérequis | Constat | Conséquence |
|---|---|---|
| Existence de documents Russell publics | Liste finale 2025 repérée ; page officielle avec liens juin 2026 | Accessibilité n’est pas autorisation d’automatiser |
| Droits LSEG pour notre collecte | Conditions du site, sections 9–10, restrictives ; pas d’autorisation spécifique fournie | Pas de téléchargement par script, extraction de listes ou import Alpha Trade |
| Archive historique complète 2024–2026 | Non qualifiée dans un cadre d’utilisation adapté | Pas de cohorte exhaustive, pas de dénominateur garanti |
| Annonces propres aux sociétés auprès de la SEC | Recherche techniquement accessible, mais mentions bruyantes et pages tronquées | Pas un substitut aux listes historiques complètes |
| Prix et comparaison économique | Non ouverts dans cette phase | Aucun PnL, taux gagnant ou conclusion d’efficacité |

## Pourquoi la source LSEG n’est pas intégrée

Les [conditions officielles](https://www.lseg.com/en/policies/website-terms-of-use)
réservent certains usages à la consultation personnelle non professionnelle et
restreignent l’accès automatisé, y compris à usage interne ou personnel.
Dans notre politique de prudence, aucune autorisation adaptée à la constitution
automatique d’un jeu de recherche Alpha Trade n’est établie.

La première consultation documentaire a identifié la page de reconstitution et
un PDF 2025 avant la découverte de cette restriction. Les lectures suivantes
du même groupe d’outils ont aussi exposé le lien/PDF 2026 pendant le contrôle
des conditions. **Aucun PDF LSEG n’a été téléchargé sur disque par nos scripts,
aucune liste n’a été convertie en table et aucun dataset LSEG n’a été importé.**
Après identification de la restriction, aucun nouvel accès à ces listes n’a
été lancé. Pas de miroir, changement de domaine, contournement de protection
ou reprise d’une liste recopiée par un tiers.

C’est une réserve d’autorisation pour ce projet, pas une affirmation juridique
universelle sur tout usage manuel des documents. Aucun avis juridique ni
garantie d’absence de risque n’est donné ici.

## Alternative SEC vérifiée séparément

La SEC peut héberger des déclarations rédigées par une société concernant son
propre titre. C’est une source distincte à examiner ; il ne s’agit pas de
réutiliser une liste FTSE Russell éventuellement annexée à un dépôt.

La vérification borne les requêtes et refuse tout domaine autre que les
services publics SEC autorisés dans le script. Les formulaires de recherche
sont 10-K, 10-Q, 8-K, 20-F et 6-K ; les produits structurés 424B2 sont hors de
ce filtre. La présence d’un terme dans un document ne signifie pas exclusion.

### Contrôle de la syntaxe de recherche

Le premier essai utilisait une expression avec `AND` et parenthèses. Le JSON
renvoyé par EFTS montre que **ces éléments ont été traités comme des phrases
obligatoires littérales**, et non comme la combinaison attendue. Les trois
zéros initiaux sont conservés, mais **ne prouvent pas zéro événement en
2024, 2025 ou 2026**. Les guides d’anciennes interfaces EDGAR ne suffisent pas
à présumer le comportement du service actuel.

Un contrôle séparé, sans modifier le premier dossier, utilise des termes
simples et vérifie le plan de requête renvoyé par la SEC :

| Requête | Année de dépôt | Documents correspondants renvoyés comme total | Page conservée | Portée |
|---|---:|---:|---:|---|
| `"Russell"`, contrôle positif | 2025 | 3 529 | 100 | Validation de l’accès/recherche, pas une cohorte |
| `"Russell" "removed"` | 2024 | 950 | 100 | Tronquée, aucun décompte d’exclusions |
| `"Russell" "removed"` | 2025 | 969 | 100 | Tronquée, aucun décompte d’exclusions |
| `"Russell" "removed"` | 2026 jusqu’au 30 septembre | 890 | 100 | Tronquée, aucun décompte d’exclusions |

Ces nombres sont des **documents/annexes trouvés**, pas autant d’événements,
de sociétés ou d’annonces de suppression. Les deux mots peuvent se trouver
dans des sections sans aucun rapport. Aucun total n’a été extrapolé.

Cinq originaux correspondant à un CIK unique du mapping courant tradable
ont été choisis par date/accession/URL, avant tout prix, sans remplacement :
**SU, PSO, MTX, RGR et PIPR**, tous issus de 2024 dans ce petit contrôle borné.
Les quatre premiers ne donnent pas de mention rapprochée répondant au motif
de découverte. PIPR comporte une annexe de rémunération comparant des sociétés
de banque d’investissement avec une référence Russell : **pas une annonce de
sa propre exclusion**, pas un historique de suppressions exploitable.
Cette annexe ne sert pas à reconstruire une liste de constituants.

Il n’y a donc **aucun événement admis par cette lecture limitée**, mais aucune
conclusion d’absence d’événements dans les années recherchées. Les premiers
100 résultats ne sont pas un tirage représentatif. L’échantillon de cinq,
issu uniquement de 2024, ne qualifie évidemment pas les annonces 2025–2026.
Élargir cette recherche pourrait découvrir des exemples, mais pas certifier
gratuitement la couverture d’une liste exhaustive ni supprimer le biais de
communication des sociétés.

Le mapping courant de **1 790 symboles** conserve par ailleurs le biais de
survivants. Les tickers/classes historiques, radiations et absences de prix
devraient rester qualifiés séparément. Une déclaration hypothétique « si nous
sortions de l’indice » et une mention tardive dans un rapport annuel ne
permettent pas de négocier rétroactivement après la sortie effective.

## Contrat à figer si une source adaptée est obtenue

C’est un projet de protocole, **pas un backtest lancé** :

1. Une famille d’indice précisément désignée ; d’abord Russell 3000, sans
   mélanger départ de Russell 2000 vers Russell 1000 et sortie de la famille.
2. Versions des annonces, date de publication et date d’effet distinctes.
   Une liste finale téléchargée aujourd’hui ne certifie pas sa disponibilité
   historique avant l’ouverture d’entrée. Une date seule impose une marge
   conservatrice ; ne pas inventer une heure.
3. Motif d’exclusion qualifié avec preuve disponible avant décision : taille,
   éligibilité, acquisition, faillite, radiation, changement de classe.
   Ne pas traiter automatiquement toute suppression comme une vente forcée
   temporaire ni écarter après coup les titres qui ont continué de baisser.
4. LONG à la première ouverture NYSE complète après l’effet **et** après
   disponibilité qualifiée de l’information. Horizon principal cinq séances,
   séance d’entrée comprise ; dix/vingt secondaires, sans choisir le meilleur
   après observation. Pas d’optimisation TP/SL dans ce premier test.
5. Population complète de la source, croisement avec le tradable actuel
   présenté séparément ; contrôle des absents et classes historiques.
6. Comparaison avec SPY et témoins choisis uniquement sur informations
   antérieures : taille et liquidité. La capitalisation actuelle ne peut pas
   servir de taille historique. Même dates, coûts et politique de manquants.
7. Coûts explicites et stress adaptés aux petites valeurs ; prix manquant
   reste inconnu, pas zéro, perte ou motif de remplacement. Aucun rendement
   de portefeuille sans contraintes réelles de capital/exécution.
8. Croisement Oracle TOP10/TOP20 % après construction de la cohorte, pas
   présélection par ses mouvements futurs. Ne pas affirmer un nouveau holdout
   vierge sur 2024–2026, années déjà examinées dans de nombreuses recherches.

Trois reconstitutions annuelles partagent chacune un contexte de marché :
cent titres d’une même session ne valent pas cent événements indépendants.
Les intervalles de confiance devront refléter les regroupements par date.

## Comment débloquer sans achat prématuré

Demander à LSEG une autorisation écrite/un accès API ou fichier adapté,
**ou** qualifier un fournisseur qui couvre explicitement le même usage :

- exclusions Russell 3000 de juin 2024, juin 2025 et juin 2026, versions finales
  et révisions historiques ; ajouts/migrations explicitement distingués ;
- identifiants stables, classe/ticker historique, date d’effet et, idéalement,
  première annonce/publication avec heure ou convention de disponibilité ;
- nature du motif, radiés conservés, garanties de complétude et corrections ;
- droits de téléchargement automatisé, stockage local, recherche quantitative
  interne/backtest, durée de conservation après résiliation et interdictions
  de redistribution ; statut des données dérivées ;
- échantillon de quelques événements vérifiables et devis **avant abonnement**.

### EODHD : attention au périmètre

La [documentation Fundamentals](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds)
décrit `HistoricalTickerComponents`, avec dates d’entrée/sortie, pour une
famille S&P limitée. Elle renvoie à un produit Marketplace pour une couverture
plus large. **Cela ne confirme ni la couverture Russell, ni l’accès avec le
Calendar & News existant, ni la date de première annonce.** Aucun appel payant,
test d’entitlement ou achat EODHD n’a été effectué dans cette phase.
Passer aux exclusions S&P serait une nouvelle cohorte à approuver, pas le
même test Russell renommé. Un historique de composition n’est pas, à lui seul,
un historique d’annonces disponible en temps réel.

## Archives et validation

Racine : `artifacts/research/us_index_deletion_feasibility/`.

- `20261020-v1/` : protocole, trois réponses SEC et leurs reçus/empreintes ;
  premier contrôle de syntaxe conservé, non interprété comme zéro événement.
- `source-control-20261020-v1/` : protocole correctif séparé, quatre recherches,
  cinq originaux, sélection antérieure à toute lecture de prix, rapport et audit.
- Scripts : `us_index_deletion_feasibility.py`,
  `us_index_deletion_source_check.py`, `us_index_deletion_source_audit.py`.

**12 requêtes SEC**, toutes HTTP 200, **5 535 118 octets lus**. TLS vérifié,
contact SEC réel déclaré sans impression de sa valeur, appels sériels espacés,
plafonds de requêtes/octets/durée ; aucune reprise de refus ou contournement.
**Quatre tests ciblés passent.** L’audit recoupe les empreintes, compteurs,
plans de recherche et cinq extractions ; même assistant, pas seconde revue
humaine indépendante.

Pas de jeu de listes LSEG enregistré, pas d’écriture SQL, de téléchargement
de prix, de modèle entraîné, d’appel LLM, d’ordre ou de batch modifié. Aucune
performance ni AUC calculée et aucun processus de recherche laissé en cours.

### Sources repérées lors de l’audit

- [Conditions LSEG](https://www.lseg.com/en/policies/website-terms-of-use),
  sections 9–10 ; réserve déterminante pour l’automatisation.
- [Page officielle Russell](https://www.lseg.com/en/ftse-russell/russell-reconstitution),
  existence du calendrier/liens, **pas autorisation de collecte**.
- [Portail SEC de recherche](https://www.sec.gov/search-filings),
  annonces propres des sociétés à vérifier, pas couverture garantie.
- [EODHD Fundamentals](https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds),
  alternative contractuelle à qualifier, sans présumer le produit Russell.
