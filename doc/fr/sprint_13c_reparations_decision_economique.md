# Sprint 13-C — Réparations et décision économique France

Date : 4 octobre 2026. **Branche exploratoire complète ; validation stricte bloquée.**

## 1. Résultat et décision

Les 24 cellules fournisseur-assumées aboutissent désormais : trois politiques,
deux folds, nominal/stress et inconnus fiscaux taxés/non taxés. Aucun candidat
n’a été supprimé pour sa trajectoire future, ses données incomplètes ou ses
résultats. Les scores, modèles, rangs et paramètres de sélection restent gelés.

Décision : **NO-GO shadow/live pour la politique LONG H5 testée**. Ce n’est pas
un rejet de l’Oracle d’amplitude, ni une preuve qu’aucune stratégie FR ne peut
fonctionner. La direction n’est pas démontrée ; le premier fold est perdant et
les gains du second dépendent fortement d’un événement unique.

Le Sprint 13 strict n’est **pas** déclaré terminé. Les preuves indépendantes,
la disponibilité historique PIT, la fiscalité complète et un benchmark
total-return qualifié restent des dépendances du Sprint 12/13-A. Aucun de ces
flags n’est promu à partir de cette expérience fournisseur.

## 2. Réparations effectuées sans modifier les archives originales

### Prix du 30 juillet 2024

Une nouvelle requête EODHD bornée au 29–31 juillet confirme l’absence de la
journée du 30 pour ERA, GLE, MEDCL et VCT. Yahoo contient cette journée pour
les quatre titres. Sur les deux séances voisines, les quatre champs OHLC et
les volumes concordent avec EODHD (tolérance des prix 0,0001 EUR).

Un overlay local apporte **uniquement les quatre barres absentes**. Le code
refuse de remplacer silencieusement une barre existante. Ni les archives
EODHD, ni les barres canoniques SQL, ni les features des modèles ne sont
réécrites. La source Yahoo reste une source secondaire, pas une preuve
officielle d’exécution ou de disponibilité historique.

### Dates de paiement des dividendes

Le montant, la devise et l’ex-date fournisseur ne changent pas. L’overlay
ajoute uniquement une date de paiement documentée ; montant/devise incohérents,
date antérieure au détachement et revue ambiguë sont refusés.

| Titre / ex-date | Montant EUR | Paiement utilisé | Niveau de preuve et réserve |
|---|---:|---|---|
| SESG / 15-04-2025 | 0,25 | 17-04-2025 | Émetteur : paiement rapporté pour A-share ; rapprochement classe/FDR et retenue étrangère restent présumés |
| OPM / 29-04-2025 | 0,36 | 02-05-2025 | Compte rendu d’AG : solde approuvé et mis en paiement, pas le total annuel de 0,60 EUR |
| LSS / 30-04-2025 | 0,40 | 05-05-2025 | Émetteur : montant approuvé, paiement annoncé ; pas confirmation de versement individuel |
| IPS / 01-07-2025 | 1,85 | 03-07-2025 | Rapport semestriel : paiement rapporté, page 22/section 6.4.6 |
| ALSTI / 29-05-2025 | 0,59 | 02-06-2025 | Historique fournisseur secondaire concordant avec termes proposés ; **pas preuve du vote final de l’AG** |
| VIRP / 24-06-2025 | 1,45 | 26-06-2025 | Historique actionnaires de l’émetteur et approbation AG 19 juin 2025 |

Sources consultées : [SES](https://www.ses.com/press-release/ses-q1-2025-results),
[OPmobility, compte rendu de l’AG](https://www.opmobility.com/wp-content/uploads/2025/05/opmobility-ag2025-compte-rendu-fr.pdf),
[Lectra](https://www.lectra.com/fr/investisseurs/information-actionnaires/dividende),
[Ipsos, rapport semestriel](https://ml-eu.globenewswire.com/Resource/Download/95074133-74a4-4290-b4da-9b2f33b86559),
[historique STIF secondaire](https://fr.investing.com/equities/stif-france-dividends),
[Virbac](https://fr.virbac.com/fr/sites/virbac-corporate/home/investors/shareholders-area.html).

Les requêtes HTTP locales SES/STIF ont répondu 403 ; cela n’est pas contourné.
Les faits visibles par la recherche web sont conservés comme **revue structurée
manuelle**, avec URL et emplacement, pas comme archive brute prétendument
téléchargée. Les pièces accessibles OPmobility/Lectra/Ipsos sont hashées.
Les notes ne sont pas antidatées comme features PIT. Aucun taux de prélèvement
personnel ou étranger non qualifié n’est présenté comme coût fiscal complet.

Cette réparation couvre les événements effectivement rencontrés par les
portefeuilles figés. D’autres événements incomplets restent dans les tapes et
bloquent s’ils sont rencontrés : ce n’est pas une certification de couverture
sur les 118 titres ou tous les chemins futurs.

## 3. Comparaison complète

Folds indépendants : 4 000 EUR initiaux chacun, huit positions, 168 trades clos
par cellule. Les intervalles de décisions restent ceux du protocole :
fold 6 du 29-07-2024 au 23-01-2025 ; fold 7 du 24-01-2025 au 23-07-2025.
Sortie à J+5 séances. La tape peut se prolonger pour les paiements de créances,
sans nouvelle intention. Les Sharpe/expositions incluent cette queue commune
aux politiques : ne pas comparer les folds comme deux périodes de durée égale.

| Fold | Politique | Net nominal, inconnus non taxés | Net nominal, inconnus taxés | Net stress, inconnus non taxés | Net stress, inconnus taxés |
|---|---|---:|---:|---:|---:|
| 6 | ATR TOP20 LONG | −35,22 % | −38,17 % | −44,14 % | −46,70 % |
| 6 | Oracle TOP20 LONG | −23,89 % | −27,82 % | −33,80 % | −37,49 % |
| 6 | Contrôle uniforme LONG | −13,23 % | −14,90 % | −24,01 % | −25,49 % |
| 7 | ATR TOP20 LONG | +52,42 % | +43,18 % | +34,15 % | +25,48 % |
| 7 | Oracle TOP20 LONG | +63,81 % | +54,52 % | +43,81 % | +34,95 % |
| 7 | Contrôle uniforme LONG | −10,42 % | −12,31 % | −20,72 % | −22,32 % |

Les rendements sont nets des quatre coûts modélisés : commission, spread,
slippage et TTF simulée. Ils ne sont pas nets d’une fiscalité personnelle ou
de toute retenue étrangère possible. Stress : coûts d’exécution ×2, pas le
taux de TTF. Les scénarios ne constituent pas des bornes mathématiques : le
cash, les quantités et les achats suivants peuvent changer avec les frais.

Oracle bat ATR d’environ 11,33 et 11,39 points dans les deux folds sous le
nominal/inconnus non taxés. Mais il fait moins bien que le contrôle au fold 6
(−10,66 points) et mieux au fold 7 (+74,23 points). L’avantage sur un contrôle
simple n’est donc pas stable sur ces deux seules fenêtres.

Oracle nominal/inconnus non taxés : Sharpe −1,68 puis +1,07 ; drawdown maximal
27,90 % puis 25,25 % ; win rate 42,26 % puis 44,64 %. Un win rate inférieur à
50 % n’invalide pas mécaniquement une stratégie ; ici, la concentration des
gains et l’instabilité temporelle importent davantage.

## 4. Audit de concentration et attribution

Au fold 7 Oracle nominal/inconnus non taxés :

- gain net total : **2 552,46 EUR** ;
- meilleur trade : ABVX, achat 16 juillet, vente 23 juillet : **2 674,89 EUR** ;
- contribution cumulée de tous les trades ABVX : **2 619,40 EUR** ;
- total moins contribution du meilleur trade : **−122,43 EUR** ;
- total moins contribution du symbole ABVX : **−66,94 EUR**.

Ces soustractions sont une **attribution comptable**, pas un backtest « sans
Abivax » : on ne réalloue pas le capital et on ne recalcule pas les achats
suivants. Aucun titre n’est retiré et aucun seuil n’est optimisé après les pertes.
Les exports donnent la concentration et les principales contributions pour
les 24 cellules, pas uniquement le scénario le plus favorable.

Le mouvement exceptionnel ne doit pas être écarté arbitrairement comme une
erreur : EODHD indique 8,10 EUR à l’ouverture du 16 juillet et 54,30 EUR à la
clôture du 23 juillet. Une vérification Yahoo distincte compare cette fenêtre.
L’émetteur a annoncé des résultats cliniques positifs le 22 juillet 2025 à
22h05, **après l’entrée**, ce qui donne une explication rétrospective plausible,
pas un signal disponible le 16 juillet ni une preuve de direction anticipée.
[Communiqué Abivax](https://abivax.gcs-web.com/news-releases/news-release-details/abivax-announces-positive-phase-3-results-both-abtect-8-week).

## 5. Livrables, scripts et reproductibilité

- Refresh EODHD et Yahoo : `artifacts/fr/research/provider_exploratory_13b/repair-20261004-v1`.
- Pièces nouvelles : `public-repair-20261004-v1` dans le même répertoire.
- Overlay final : `payment-repair-20261004-v2/overlay.json`.
- Configuration finale : `config/research_fr/provider_exploratory_13b_v4.yaml`.
- Revues : `config/research_fr/public_payment_review_13c_v2.json`.
- Rejeu complet : `artifacts/fr/research/provider_exploratory_13b/exploratory-20261004-v8`.
- Décision/attributions : `artifacts/fr/research/provider_exploratory_13b/decision-20261004-v1/report.json`.
- Contrôle prix ABVX : `artifacts/fr/research/provider_exploratory_13b/abvx-check-20261004-v1/report.json`.

Les dossiers v4/v5/v6/v7 restent des jalons archivés, pas des expériences
indépendantes à additionner. Les intentions sont identiques ; seuls des champs
de comptabilisation documentés sont ajoutés à l’expérience séparée. Les hashes
des archives de qualification strictes restent inchangés.

```powershell
python -m modelFactory.fr_provider_exploratory_13b --config config/research_fr/provider_exploratory_13b_v4.yaml --output artifacts/fr/research/provider_exploratory_13b/rejeu-nouveau-dossier
python -m service.fr.economic_decision_13c --source artifacts/fr/research/provider_exploratory_13b/rejeu-nouveau-dossier --output artifacts/fr/research/provider_exploratory_13b/decision-nouveau-dossier
```

Tests : **52 tests ciblés passent** (réparations, non-mutation, contradictions,
dates, ambiguïtés, attribution sans fausse simulation, plus comptabilité,
reporting et gates stricts). Ce n’est pas une validation de toute l’application.

## 6. Ce qui empêche encore une clôture stricte du Sprint 13

Mise à jour : les sensibilités de retard d'entrée et de plafond sont désormais
exécutées séparément dans [13-D](sprint_13d_robustesse_economique.md). Leur
statut « non exécutées » ci-dessous décrit la clôture de 13-C. Les sensibilités
secteur/taille/segment PIT restent non exécutées ; aucun GO strict n'est acquis.

| Exigence | État après ce travail |
|---|---|
| Comparaison fournisseur nominal/stress, mêmes intentions | Terminée : 24/24 |
| Attribution par symbole/semestre, concentration et frais | Terminée pour l’expérience fournisseur |
| Preuves indépendantes prix/statuts/CA/PIT/fiscalité complètes | Toujours bloquée ; Yahoo et notes de revue ne les remplacent pas |
| Benchmark FR total-return qualifié | Non qualifié ; aucun alpha calculé contre un benchmark inadéquat |
| Direction/abstention validée | Pas de politique validée à ajouter aux trois contrôles |
| Sensibilités secteur/taille/segment PIT, retards d’entrée | Non exécutées ; pas de réglage post hoc à partir des pertes |
| Confirmation réservée 2026 | Non consultée, aucun candidat robuste promu |
| Décision shadow/live | NO-GO pour cette politique ; aucune activation |

On s’arrête donc avec une **conclusion exploratoire documentée**, pas avec un
« Sprint 13 strict terminé » fictif. L’exigence de couverture indépendante
ne peut pas être levée par un simple correctif de code ou par deux fournisseurs
concordants. Cela ne signifie pas que toutes les sources gratuites possibles
ont été épuisées ni qu’un abonnement payant garantit automatiquement la
qualification. Aucun achat n’est engagé.

Pour reprendre strictement : acquérir et faire qualifier les preuves restantes
du [TODO Sprint 12](TODO_sprint_12_reste_a_faire.md), compléter le benchmark,
puis reprendre les tapes strictes et la revue de décision. Il ne faut pas
consulter 2026 pour trouver une variante qui rendrait rentable le développement.
