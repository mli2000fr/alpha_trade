# Prévisions de résultats CN — qualification avant nouveau POC

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Date : 6 octobre 2026. Décision : conserver `cn_akshare_enrichment`
désactivé, sans endpoints. Aucun nouveau téléchargement de données métier,
aucune écriture SQL, aucun entraînement ni activation planifiée pendant cet audit.

## Famille retenue et continuité avec les travaux existants

Priorité aux prévisions de résultats publiées par les sociétés (`业绩预告`),
pas aux révisions d'analystes Eastmoney. Une annonce d'émetteur peut fournir
des bornes de bénéfice, revenu, croissance et une correction explicite.
Ce n'est pas un consensus de courtiers et aucune performance D1/D10 n'est démontrée.

Ne pas recommencer le [pilote 15-D1](./sprint_15d1_pilote_guidance_pit.md).
Il a déjà établi la faisabilité documentaire, la rareté des annonces fraîches
(5,13 % des observations Oracle TOP20 avec annonce datée de moins de 20 jours
dans son inventaire), les ambiguïtés d'horodatage et les difficultés d'extraction.
Ce pourcentage historique concerne des métadonnées d'archive Eastmoney : il
ne prouve ni couverture future, ni licence, ni disponibilité PIT des valeurs.

## Qualification documentaire des droits

Sources officielles consultées le 6 octobre 2026 :

- [CNINFO — page avec déclaration juridique](https://www.cninfo.com.cn/new/snapshot/companyDetailCn?code=002261).
  Le texte indique une possibilité de consultation et téléchargement à des
  fins non commerciales, sous réserve du droit applicable et de la déclaration.
  Il réserve une permission écrite pour les usages visant la vente profitable
  à autrui. Cette disposition ne constitue pas à elle seule une validation
  de nos appels automatisés, de l'archivage intégral ou des usages ML/live.
  Ne pas confondre un POC privé non commercial et toute exploitation future.
- [CNINFO — plateforme de données](https://webapi.cninfo.com.cn/).
  Le portail officiel propose des services de données ; accès, contrat,
  coûts et quotas correspondant à nos besoins non établis ici.
- [Eastmoney — déclaration juridique](https://about.eastmoney.com/home/disclaimer).
  Réserves sur la copie et la réutilisation sans permission préalable et sur
  les charges excessives. Aucun droit spécifique obtenu pour le projet.
  Ne pas relancer l'inventaire de masse Eastmoney utilisé par 15-D1.

Verdict : `PENDING_CNINFO_AUTOMATED_ACCESS_AND_USAGE_QUALIFICATION`.
Il s'agit d'une réserve documentaire, pas d'une déclaration d'illégalité,
ni d'une garantie juridique. Aucun endpoint AKShare n'est autorisé globalement
sur la base de la licence logicielle de la bibliothèque.

Contact publié par CNINFO : `szsi_clientservice@szse.cn`.
Demander une confirmation ou les conditions API applicables pour :

1. accès depuis la France, appels automatisés aux notices et PDF de prévisions ;
2. pilote privé non commercial de dix émetteurs et trente documents maximum ;
3. archivage local des notices, documents et corrections, durée de conservation ;
4. extraction numérique, calcul de révisions, entraînement et évaluation ML ;
5. distinction recherche privée, trading pour compte propre, usage professionnel
   et éventuelle redistribution ;
6. endpoints officiellement supportés, quotas, fréquence et gestion des retraits.

Ne pas envoyer de demande au nom de l'utilisateur sans son autorisation.
Ne pas contourner CAPTCHA, refus d'accès, restrictions géographiques ou quotas.

## POC suivant, uniquement après qualification des droits

Le futur batch proposé se nommerait `cn_issuer_forecast_snapshot`.
Ce nom est une proposition, pas un batch implémenté ou activé.
Utiliser un connecteur direct à la source autorisée ; AKShare n'est pas un
prérequis. Le POC reste en fichiers de recherche, sans tables canoniques.

Pré-enregistrer dix sociétés couvrant Shanghai/Shenzhen et plusieurs boards,
avec des annonces originales et corrigées quand disponibles, et au maximum
trente documents. Ne pas sélectionner les sociétés sur leurs rendements futurs.
Respecter le quota autorisé ; stopper au budget ou au premier refus d'accès.
Si aucun quota n'est communiqué, ne pas extrapoler une collecte de masse.

Archiver pour chaque document : source, paramètres de requête non secrets,
identifiant de notice, code et identité canonique, URL, titre, statut HTTP,
type MIME, hash SHA-256, fichier brut autorisé, première observation UTC,
horodatage de publication brut et précision, version de l'extracteur et
identifiant de correction/original. Conserver les versions, ne jamais remplacer
silencieusement l'annonce originale par sa correction.

Extraire séparément : exercice/période fiscale, métrique, unité et devise,
bornes basse/haute, signe du bénéfice ou de la perte, variation annoncée,
ancienne prévision, nouvelle prévision et résultat réalisé. Une valeur ambiguë
reste en quarantaine avec motif ; aucune conversion implicite de 万元 en CNY.

Disponibilité : pour une collecte prospective, ne jamais utiliser avant la
première observation locale et la publication qualifiée. Un document ancien
collecté aujourd'hui n'acquiert pas une disponibilité historique certifiée.
Un horodatage à minuit ou seulement une date doit porter un indicateur de
précision insuffisante ; toute règle historique J+1/J+2 reste un proxy déclaré,
pas une preuve retrouvée de disponibilité.

## Gates et suites

Avant collecte quotidienne : droits archivés, identités et pagination validées,
budget maîtrisé, deux passages sans doublons de document/version, récupération
des corrections, validation manuelle des champs numériques du POC et absence
de valeurs ambiguës promues automatiquement.

Avant ML : corpus suffisant d'événements valides, dates disponibles avant la
décision, protocole OOF événementiel pré-enregistré et comparaison appariée avec
baseline sans ces annonces. Abstention en absence d'événement ; ne pas propager
une annonce ancienne comme signal quotidien frais. Avant live : qualification
distincte des droits et de l'exploitation. Un succès technique du POC ne suffit
donc pas à activer le batch ni à promouvoir une feature.

Prochaine action requise : obtenir les conditions applicables CNINFO ou fournir
un corpus dont les droits de traitement sont établis. En attendant, le batch
générique reste désactivé et les modèles existants sont inchangés.
