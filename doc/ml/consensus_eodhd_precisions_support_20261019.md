# Consensus EODHD — ce que la réponse du support débloque

**Variante revenus seuls exécutée après GO** : [pilote, motifs et maturités](consensus_revenus_observes_20261019.md).
Deux cas TOP10 documentés, aucun H10 encore mature ; pas de résultat d'efficacité
ni de promotion de la règle EPS ET revenus.

Source : [réponse transmise par l'utilisateur](sources/reponse_support_eodhd_trends_docn_fun_20261019.md).
Précisions reçues après la revue initiale, sans date/heure de courriel certifiée.
**Aucun appel API, achat, requête SQL, entraînement ou changement de production.**

## Bilan actualisé

| Question | Réponse | Conséquence pour la recherche |
|---|---|---|
| Unités | Valeurs complètes, pas milliers/millions | 306 723 910 représente 306 723 910 unités monétaires, pas 306 723 910 millions |
| Devise DOCN/FUN | USD confirmé pour ces deux sociétés | Réserve de devise levée par déclaration fournisseur sur ce périmètre, pas sur tout l'univers |
| Dates FUN | 30 juin = trimestre fini le 28 juin ; 30 septembre = troisième trimestre 2026 | Convention d'ancrage expliquée, pas une erreur de date démontrée |
| Horizons | `0q` : estimation courante pour la période ; `+1q` : dernier état conservé quand elle était encore « prochaine » | Ne pas mélanger les deux états ; préférer `0q` pour suivre le courant de la période |
| Dates des anciens états | Non conservées | `+1q` n'est ni J−7, ni J−30, ni une ancienne version précisément datée |
| EPS | Généralement non-GAAP, exceptions et base non identifiée par item | EPS par enregistrement reste **inconnu**, ni GAAP ni non-GAAP certifié ; basic/dilué également inconnus |
| Analystes | Identités absentes, agrégats seulement | Variation de moyenne ≠ révision prouvée des mêmes analystes |

L'identité FUN est confirmée comme l'émetteur Six Flags actuellement coté.
Cela ne certifie pas toutes les identités ou périmètres comptables historiques.
Le support confirme le trimestre de septembre, **pas son jour de clôture fiscal
exact**. Aucun jour précis n'est inventé.

La règle générale « premiers jours du mois → mois précédent » ne donne aucun
seuil numérique : ne pas coder arbitrairement « avant le 7 » ou « avant le 10 ».
Conserver l'ancrage fournisseur et le trimestre identifié, séparés d'une date
fiscale réelle lorsqu'elle est documentée.

## Conséquences sur nos exemples

Pour la période fournisseur 2026-09-30 :

- DOCN, observation du 18 octobre : `0q EPS=0,3186` est l'état courant de cette
  période ; `+1q EPS=0,2842` est une ancienne prévision conservée, sans date
  d'origine exploitable. Ce ne sont pas deux estimations concurrentes également
  courantes, ni nécessairement un doublon à supprimer.
- FUN : même logique pour `0q EPS=2,0811` et `+1q EPS=2,1470`.
- Les vraies collectes `0q` du 11 et du 18 octobre restent des observations
  distinctes et datées par nos reçus. Leur variation est un changement de
  l'agrégat fournisseur pendant cette fenêtre réellement observée.
- Les conventions comptables EPS restant inconnues, on ne déclare pas que
  la comparaison EPS est pleinement qualifiée par cette seule réponse.
- FMC reste réservé : la forte modification des nombres d'analystes n'est
  pas résolue par cette précision générale.

Attention : un item `0q` d'une ancienne fin de période ne devient pas le
trimestre actuellement à prévoir pour chaque date de décision. Il faut
identifier la période pertinente, son état de publication et sa disponibilité
avant l'entrée. La clarification ne rend pas tous les `0q` historiques courants.

## Ce qui peut être étudié sans inventer de données

**Piste distincte possible : variation du consensus de revenus entre deux
snapshots `0q` réellement collectés**, pour un même symbole et trimestre,
devise vérifiée, périmètre comparable, disponibilité antérieure à la décision.

Ce test évite l'ambiguïté GAAP/non-GAAP de l'EPS, mais pas les effets de
composition du consensus. Il doit être décrit comme « variation de consensus
agrégé de revenus », pas comme « les mêmes analystes ont relevé leurs prévisions ».
Conserver les nombres d'analystes et traiter séparément leurs changements ;
un nombre inchangé ne prouve toujours pas une population identique.

Ce serait une hypothèse **nouvelle, figée avant résultats**, pas un remplacement
silencieux de notre règle primaire EPS ET revenus, ni une promotion basée sur
les faibles variations DOCN/FUN déjà examinées. Aucun test de cette variante
n'a été lancé avec cette mise à jour documentaire.

Pour élargir à tout l'univers, établir la devise de publication par société
depuis une source adéquate. `currency_symbol` des Financials est la piste citée
par le support ; nous n'avons ni vérifié son accès sur le compte ni acheté
Fundamentals ici. **Ne pas supposer USD pour toute action cotée aux États-Unis.**

## Ce qui n'est pas débloqué

- Le backtest historique des consensus sur 2024–2025 : ni la date fiscale, ni
  `+1q`, ni les comparaisons glissantes reçues aujourd'hui ne créent une archive
  des états alors connus.
- Une comparaison de surprise `EPS réalisé` contre `EPS estimé` sur une base
  comptable certifiée : l'endpoint ne fournit pas cette certification.
- Une explication causale de la variation par les mêmes analystes.
- Une confirmation directionnelle avec huit dates de collecte seulement.
- La qualification rétroactive à l'ouverture du 19 octobre : cette précision
  est reçue après, sans heure d'e-mail permettant de prétendre le contraire.

## Décision

La réponse est utile et la question fournisseur **n'est plus en attente**.
Inutile de lui redemander la même base EPS que l'endpoint ne sait pas identifier.
Maintenir les collectes existantes, préserver les états séparés et ne pas
requalifier globalement les lignes en base. Pas de nouvel abonnement justifié
par ce retour seul.

La piste « publication financière réelle + réaction prix » reste indépendante
de ces limites du consensus ; son [bilan SEC](reconstitution_annonces_financieres_sec_20261019.md)
et son besoin d'une cohorte choisie sans information future ne changent pas.
