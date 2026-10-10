# Sprint 11-C — disponibilité, revue de guidance et ablation événementielle

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

**Suite documentaire11-E :** [complément gratuit et seconde revue](sprint_11e_completion_gratuite_guidance.md).
Les résultats AMF/DILA ci-dessous restent figés, aucun modèle refait. La suite
propose15 paires documentaires11-D/11-E (9 UP/6 DOWN), sans gain D1/D10 testé :
faible intersection Oracle et seconde lecture humaine encore requise.

Exécution du 4 octobre 2026, sans abonnement supplémentaire. Le résultat est
un **pilote prédictif exploratoire**, pas un backtest économique, ni une preuve
PIT stricte, ni une clôture de toutes les branches du Sprint 11.

## 1. Livrables exécutés

- Profil pré-enregistré : `config/research_fr/event_direction_11c_v1.yaml`.
- Revue documentaire : `config/research_fr/guidance_review_11c_v1.yaml`.
- Service : `service/fr/event_direction_11c.py`.
- CLI : `modelFactory/fr_event_direction_11c.py`.
- Résultats : `artifacts/fr/research/event_direction_11c/pilot-20261004-v1/report.json`.
- Protocole écrit avant ajustement : `protocol.json` dans le même dossier.
- Paires et exclusions sourcées/hashées : `guidance_validated.json`.
- Probabilités et scores OOS : `oos_predictions.parquet`.
- Panels de features de recherche et métriques quotidiennes, séparés par délai,
  fold et variante. Aucun artefact n'est ajouté au serving.

Les fichiers sources AMF/DILA, le référentiel et le pool Oracle sont vérifiés
par SHA avant calcul. Une sortie existante est refusée, aucune archive antérieure
n'est écrasée. Ni SQL, ni batch, ni portefeuille de production ne sont touchés.

## 2. Disponibilité : ce qui est établi et ce qui reste une hypothèse

### AMF

La date de publication du fichier est distincte de la date de position. Les
features ne sont calculées qu'à partir de la première, retardée d'un jour
calendaire dans le pilote principal, et de deux jours dans la sensibilité.
Une publication le vendredi devient admissible au plus tôt le samedi selon
cette convention, et n'entre dans le pool que lorsqu'une séance existe.
Ce n'est pas un décalage d'une/deux séances de bourse.

Le ratio n'est jamais porté comme total de short interest. Les variations
sont celles de deux publications consécutives du même détenteur/ISIN avec
ratios tous deux au-dessus du seuil public de 0,5 %. Le passage sous le seuil
est un événement séparé, pas une observation permanente du ratio réel.
L'absence de publication reste non observée.

Les mises à jour distinctes du même jour sont exclues et interrompent la
continuité des variations : aucun ordre de ligne ne choisit la « dernière ».
261 groupes sont ambigus dans tout l'historique traité jusqu'à 2025, contre
38 dans le sous-ensemble 2018–2025 des 330 ISIN inventorié en 11-B. Ces deux
chiffres n'ont pas le même périmètre. Les 15 lignes incohérentes du lecteur
11-B restent mises en quarantaine.

**Réserve non levée :** l'export est une reconstruction actuelle, pas un
historique de vintages quotidiens. Une date de publication n'établit pas que
la valeur aujourd'hui reconstruite était identique dans le fichier ancien.
Le pilote ne prétend donc pas valider un signal PIT de production.

### DILA

Les annonces sont dédupliquées par ISIN et identifiant `uin_idt_uin`.
La plus tardive des transmissions avec fuseau explicite donne le jour local
Europe/Paris. Des doublons présentant des jours contradictoires auraient été
exclus ; aucun groupe de cette sorte n'est apparu dans les archives lues.
23 845 documents distincts sont conservés sur tout le corpus jusqu'à 2025.

L'heure de transmission ne prouve pas l'heure de publication Web. Le même
délai d'un/deux jours est une **hypothèse conservatrice de recherche**, pas
une preuve que tout délai réel de diffusion lui est inférieur.

La collecte ne couvre que les archives des 120 émetteurs du POC, dont 48 ISIN
du référentiel FR. Un indicateur `dila_archive_collected` distingue les titres
non collectés. Le contrôle prix possède lui aussi cet indicateur afin de ne
pas attribuer son effet de sélection à l'ajout des annonces.

Les features DILA du pilote sont des **compteurs d'annonces**, sans direction
inférée du titre. Un test des révisions de guidance ou de surprises de résultats
serait une autre expérience ; le NO-GO ci-dessous ne les condamne pas.

## 3. Revue sémantique des documents

Les pages pertinentes des sept PDF archivés ont été rendues et examinées
visuellement, avec contrôle du texte, des périodes et des notes. La revue est
effectuée par le même agent ; elle n'est pas une double revue indépendante.

| Émetteur | Pièce / page | Qualification | Valeurs et réserve |
| --- | --- | --- | --- |
| Lagardère | 20/12/2021, p.1 | Révision prospective haussière | Marge Publishing proche de 12 % vers environ 13,5 %, Workman exclu dans les deux chiffres ; estimations approximatives |
| Aubay | 22/07/2021, p.2 | Révision prospective haussière | CA annuel 2021 : 440–450 M EUR vers 456–465 M EUR ; périmètre comparable |
| Orange | 13/02/2025, p.4 | Révision prospective haussière | Objectif de cash-flow organique télécoms 2025 de 3,5 Md EUR vers au moins 3,6 Md EUR |
| Vallourec | 01/02/2024, p.1 | Résultats provisoires contre ancienne guidance | RBE exercice 2023 : ancienne fourchette 1 075–1 175 M EUR, estimation désormais >1 190 M EUR ; exercice déjà terminé, pas une nouvelle guidance prospective |
| Lectra | 27/07/2023, p.1 | Confirmation, pas nouvelle révision | Confirme les objectifs révisés le 27 avril ; résultats réalisés en baisse ne suffisent pas à créer une nouvelle baisse de prévision |
| Valneva | 29/12/2023, p.1 | Périmètres non comparables directement | Total incluant PRV/autres produits versus ventes de produits inchangées ; ne pas soustraire deux périmètres différents |
| Entech | 20/11/2024, p.1 | Nouveaux objectifs sans ancienne valeur comparable | Ambitions 2025/2026/2029, pas de paire old/new reconstruite dans cette passe |

**Correction Orange :** l'extraction brute affiche `3,58`. Le rendu montre
`3,5` suivi de l'appel de note en exposant `8`. La valeur ancienne est donc
3,5, pas 3,58. Les résultats réalisés 2024 (environ 3,4 Md EUR) ne sont pas
non plus l'ancienne prévision 2025. Ne pas convertir les notes en décimales.
La note8 précise que la guidance du Capital Market Day est **hors Espagne** ;
cette restriction de périmètre doit accompagner la valeur ancienne.

Le classement historique « quatre paires comparables » du POC demeure un
constat de comparabilité numérique. La revue distingue maintenant **trois
révisions prospectives** et **un résultat provisoire contre ancienne prévision**.

Les hash, URL, ISIN, pages, date du document, transmission et motifs sont
conservés dans le manifeste et la sortie. La mention `validated` désigne la
revue sémantique de ces documents, pas une admission de toute la disponibilité
PIT ni une généralisation du parseur.

## 4. Protocole prédictif figé avant exécution

- Marché FR, horizon H5, pool Oracle TOP20 OOF réparé du Sprint 10-C3.
- Folds directionnels 6 et 7, découpages/purges du protocole antérieur.
- Train : labels mûrs avant validation ; validation : mûrs avant test.
- Au moins 126 jours train et 100 exemples par classe ; évaluation au moins
  40 jours et 30 exemples par extrême. Les plans source gardent leur gate de
  couverture des séances. Aucun relâchement pour obtenir un résultat.
- Cible ternaire D1/intermédiaires/D10 ; les déciles inconnus ne sont pas
  arbitrairement attribués à une classe.
- Logistique fixe C=1, max_iter=500, graine17, deux threads. Aucun choix
  champion ni balayage d'hyperparamètres.
- Référence : les 14 features prix françaises + indicateur de collecte DILA.
- AMF : logarithmes de compteurs de publications, hausses, baisses et passages
  sous seuil, sur fenêtres rétrospectives de 7/30 jours calendaires.
- DILA : logarithmes de compteurs de documents, sur les mêmes fenêtres.
- Quatre variantes : contrôle, +AMF, +DILA, +AMF+DILA ; chaque ajout est
  comparé au même contrôle sur les mêmes événements.
- Classement LONG/SHORT des 20 % extrêmes du score au sein du pool Oracle.
  Il s'agit d'un diagnostic brut H5, pas d'un portefeuille exécutable.
- Délai1 jour principal ; délai2 sensibilité, pas substitué après lecture.
- Gates : deux folds ; AUC moyenne ≥0,53 ; delta moyen vs contrôle ≥0,01
  et positif dans chaque fold ; IC moyen ≥0,03 ; spread moyen ≥0,2 %.
- 2026 entièrement hors expérience. Pas de nouvelle confirmation « intacte »
  revendiquée sur 2024–2025 déjà étudié dans les expériences antérieures.

## 5. Résultats exécutés

### Délai principal : un jour calendaire

| Variante | AUC D1/D10 fold6 | AUC fold7 | AUC moyenne | Delta moyen vs contrôle | IC quotidien moyen | Spread brut moyen |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Contrôle prix + collecte | 0,5066 | 0,5148 | 0,5107 | — | 0,0143 | −0,8861 % |
| + AMF | 0,4450 | 0,5127 | 0,4788 | −0,0319 | −0,0123 | −1,8416 % |
| + DILA compteurs | 0,5078 | 0,5208 | 0,5143 | +0,0036 | 0,0190 | −0,7954 % |
| + AMF et DILA | 0,4465 | 0,5147 | 0,4806 | −0,0301 | −0,0106 | −1,6650 % |

Spread = rendement moyen du panier LONG plus rendement signé du panier SHORT,
moyenné par jour puis par fold. Il n'inclut ni commissions, ni spread de marché,
ni slippage, ni taxe, ni borrow. Ce n'est pas un rendement de portefeuille.

### LONG et SHORT séparés, délai principal

| Variante | LONG fold6 | SHORT fold6 | LONG fold7 | SHORT fold7 |
| --- | ---: | ---: | ---: | ---: |
| Contrôle | −0,7875 % | +0,7930 % | +1,9330 % | −3,7107 % |
| + AMF | −1,2418 % | +0,2242 % | +1,1893 % | −3,8549 % |
| + DILA | −0,7920 % | +0,9312 % | +2,0135 % | −3,7435 % |
| + AMF et DILA | −1,1933 % | +0,2031 % | +1,2819 % | −3,6219 % |

Le petit mieux LONG de DILA au fold7 ne s'accompagne pas d'une amélioration
LONG au fold6. Les SHORT restent fortement négatifs au fold7. Ne pas retenir
un seul côté/fold après lecture et le présenter comme une politique confirmée.

### Sensibilité : deux jours calendaires

| Ajout | AUC moyenne | Delta vs même contrôle | Spread brut moyen |
| --- | ---: | ---: | ---: |
| AMF | 0,4797 | −0,0310 | −1,2108 % |
| DILA | 0,5137 | +0,0030 | −0,8528 % |
| AMF + DILA | 0,4821 | −0,0286 | −1,0198 % |

Toutes les variantes ajoutées, sous les deux délais, concluent
`NO_GO_INCREMENTAL_PROXY_PILOT`. Ce verdict est limité aux compteurs/features,
au modèle et au périmètre effectivement testés. Ce n'est pas la preuve qu'aucune
information AMF ou annonce réglementée ne peut jamais apporter de direction.

## 6. Guidance : pourquoi aucun entraînement n'a été lancé

Trois paires prospectives, toutes haussières, aucun exemple baissier validé.
Deux sont en 2021, avant l'historique directionnel Oracle OOF utilisé ici.
L'échantillon de textes préfiltrés ne constitue pas un historique exhaustif de
surprises. Le nombre d'événements indépendants ne devient pas plus grand en
répétant la même annonce sur plusieurs jours/titres candidats.

Verdict : `BLOCKED_INSUFFICIENT_VALIDATED_GUIDANCE_AND_NO_INDEPENDENT_REVIEW`.
Pas de NO-GO statistique inventé, ni d'apprentissage sur trois annonces.
Une extension requiert collecte sur le véritable univers, événements haussiers
et baissiers comparables, contrôle hors échantillon et contrat de disponibilité.
Ces tâches ne sont pas déclarées impossibles gratuitement.

## 7. État du Sprint 11 après cette passe

| Branche | État |
| --- | --- |
| Publication AMF reconstruite et compteurs de changements | Pilote exploratoire terminé, NO-GO incrémental ; PIT strict non qualifié |
| Activité d'annonces DILA sur archives POC120 | Pilote exploratoire terminé, NO-GO incrémental ; collecte partielle et disponibilité Web non prouvée |
| Guidance sémantique | Revue corrigée ; étude prédictive bloquée par support/validation, pas par un abonnement obligatoire |
| INPI/RNE | Non testé dans cette passe |
| Consensus/borrow/enchères/options/quotes historiques | Suspendus faute de source qualifiée ; aucun abonnement commandé |

**Sprint 11 complet toujours ouvert.** Cette passe répond à la demande de
qualification et de test sur ce qui est disponible ; elle ne remplace pas une
collecte étendue/validation des événements sémantiques. Le Sprint12 reste
indépendant et ne rend pas ces métriques brutes économiquement exploitables.

## 8. Vérification et reproduction

Suite distincte du 4 octobre : [11-D — corpus guidance élargi](sprint_11d_corpus_guidance_elargi.md).
La revue 11-C ci-dessus reste celle de l'échantillon initial. 11-D apporte
quatre nouvelles annonces comparables (trois UP/une DOWN), sans relancer les
modèles AMF/DILA. Le cumul documentaire est de sept annonces, mais sans
validation indépendante ni GO PIT/entraînement. Sprint11 toujours ouvert.

24 tests ciblés ont passé avant le pilote, comprenant le lecteur11-B, les
nouvelles règles11-C et le modèle directionnel10-B. La vérification finale
cumulée avec les POC DILA et guidance donne **33 tests passants**. Ruff passe.
Pas de suite complète revendiquée.

```powershell
python -u -m modelFactory.fr_event_direction_11c --output artifacts/fr/research/event_direction_11c/nouvelle_sortie
```

Ne pas modifier ce profil pour chercher un meilleur résultat sur les folds
déjà lus. Une nouvelle hypothèse impose une nouvelle version et une validation
distincte. Aucun processus de ce pilote n'est encore en cours.
