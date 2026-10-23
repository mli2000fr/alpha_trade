# Winner seul contre exclusion du bas du classement — suivi

## État au lancement corrigé, nuit du 22 au 23 octobre 2026

**REJEU EN COURS — aucun avantage économique encore établi.** Ne pas confondre
le précédent gain descriptif d'aire du parcours avec le rendement de ces comptes.

[Protocole](winner_filtre_bas_classement_protocole_20261022.md).
Canonique : `artifacts/research/us_winner_bottom_rank_filter/20261022-v2/`.

Six comptes natifs, capital4000USD redémarré indépendamment par compte :

| Année | Bras |
|---|---|
| 2025 complète | Winner seul, retirer les3derniers, retirer les5derniers |
| 2026 au30septembre | mêmes trois bras |

Bas du classement **estimé** au jour Oracle, ratio volatilité20/60 décroissant
pour les exclus. Les titres conservés restent dans l'ordre Oracle original.
Pas les vrais perdants sélectionnés grâce au futur, ni un modèle entraîné.
La règle avait échoué en validation ancienne : test économique exploratoire
autorisé après observation des résultats récents, pas confirmation indépendante.

## Paramètres réellement gelés

- Winner actuel : SL7 %, trailing15 %, aucun TP, demi-position, renforcement off,
  confirmation de deux clôtures5m, attente20séances.
- Détention20séances depuis le fill réel puis sortie open21. Pas OracleJ20.
- Profil capital_2001_5000, equity explicitement4000, risque par trade1,25 %,
  huit positions maximum, seuil de drawdown15 % et gardes natives.
- Levier YAML autorisé2x mais plafond brut du risque **1x**, conservé partout.
  Ni exposition2x forcée ni double capital fictif. Capital réellement utilisé
  sera publié, car le filtre peut changer les opportunités et le cash libre.
- Coûts canoniques du moteur, financement6,5%/252 sur cash débiteur.
- Deux overlays factoriels sans tapes qualifiées non reproduits, explicitement
  désactivés dans les trois comptes de recherche ; aucune modification YAML.
  Pearson et autres gardes natives conservés. Pas parité broker/PIT complète.

## Périmètre et lectures réalisées

Ne pas reprendre les anciennes213campagnes : seuls112deleurs titres/date
appartenaient aux nouveaux TOP10 et20avaient le même rang. Ce ne sont donc pas
des témoins valides du filtre de cet audit. Aucune performance de ces anciennes
campagnes n'a été ajoutée aux nouvelles.

Nouveau snapshot MySQL READ ONLY de **4 262 675 bougies SIP5m existantes**, sur
131titres ayant figuré au TOP10 des périodes demandées. Index symbole/timestamp,
zéro appel Alpaca/EODHD/LLM. Les téléchargements existants n'ont pas été arrêtés.
Un comptage exploratoire trop large a été annulé : seule notre requête exacte
a été interrompue, puis remplacée par ces lectures ciblées.

| Année | Signaux TOP10 initiaux, seed précédent inclus | Cohorte commune | Fenêtre SIP insuffisante | Données J réservées |
|---|---:|---:|---:|---:|
| 2025 | 2 510 | 1 428 | 1 082 | 0 |
| 2026 | 1 880 | 1 027 | 841 | 12 |

Il s'agit d'observations titre/date, pas de trades déjà exécutés. Filtre auxiliaire
figé **avant** ces exclusions. Couverture maximale attente+détention vérifiée
sur tous les bras ; biais de conditionnement sur prix futurs explicite.
Les trois comptes voient les mêmes exclusions, sans remplacement TOP11.

Daily/benchmark : ancien cache split, pas des raw réétiquetés. Niveaux d'entrée
et fills : véritables raw SIP5m de l'archive ; secteurs actuels non PIT. Inventaire
OST existant non certifié exhaustif ; aucune absence de ligne ne prouve l'absence
de dividende ou autre événement. Cette réserve reste attachée aux performances.

## Correction de lecture du budget, pas optimisation

V1 a échoué dès l'admission2025 : la pré-garde du replay vérifiait une fraction
arithmétique de la quantité, pas sa conversion effective en actions entières.
Avec full=1, la demi-position vaut zéro action et le constructeur natif refuse
le plan. Les trois comptes2025 échouent avant mesure financière ; le premier
2026 était commencé. Ce processus V1 a été explicitement arrêté ; aucun résultat
partiel n'est utilisé comme résultat final, aucun batch utilisateur touché.

V2 conserve V1 et toutes les empreintes. Adaptateur de recherche séparé : appeler
le constructeur natif, refuser le seul motif `ZERO_WHOLE_INITIAL_SHARES`, puis
continuer les autres cibles. Aucun arrondi vers le haut, budget augmenté,
fraction d'action ou assouplissement de règle. Les autres erreurs continuent
de faire échouer le compte. Rejouer les six comptes, ne pas fusionner les versions.

Un cache en lecture seule évite les appels de calendrier officiel identiques ;
les listes retournées sont copiées et les mêmes sessions/dates sont testées.
Ce n'est pas un cache de prix ni un changement d'heure d'exécution.

## Suivre et interpréter à la fin

```powershell
Get-Content F:\projets\artifacts\research\us_winner_bottom_rank_filter\20261022-v2\progress.json
```

`completed_runs` compte les six comptes terminés ; `completed_sessions` concerne
le compte courant. `annual-summary.partial.csv` n'est pas un bilan final.
Ne pas lancer une seconde instance dans ce dossier. Les premiers comptes ne
sont pas encore une comparaison entre les deux années et les trois variantes.

À la fin : `report.json`, `annual-summary.csv`, puis chaque sous-dossier compte
avec trades, événements, courbes5m/daily et état de risque. Si un compte est en
échec ou incomplet, pas de verdict économique complet ni de PnL inventé.

Audit préparé, **pas encore exécuté tant que report.json n'existe pas** :

```powershell
python -u -m scripts.research.us_winner_bottom_rank_filter_audit_20261022
```

Il vérifie le sens du filtre, les entrées réellement retenues, la confirmation
5m, les cash-flows partagés, frais, absence de rachat d'une position détenue,
les PnL unitaires, capital/DD et les sorties open21 depuis le fill. Il enrichit
`annual-metrics-audited.csv` (rendements, DD, gagnants/perdants, moyennes, durées,
capital), puis produit `final-audit.json`. Même assistant, pas revue humaine.

**32 tests ciblés passent** : 13pour le filtre/cohorte, 14du moteur intraday,
3pour le refus entier/calendrier, 2pour l'audit cash. Les audits des performances
réelles restent à faire, et ces tests ne démontrent pas la rentabilité.

Prochaine action à la fin du calcul : lire les six comptes, passer l'auditeur,
comparer rendement/DD/capital par année et documenter un verdict borné. Aucune
automatisation de suivi, activation PAPER/live, nouvelle collecte ou nouvelle
expérience n'a été créée. L'absence d'entraînement ne rend pas ces années inédites.
