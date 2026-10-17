# Vérifications — 17 octobre 2026

25 contrôles réussis, hors navigateur : validation statique et simulations isolées des API Chrome / du DOM. Aucune session Amazon réelle consultée, aucun message réel envoyé et aucune commande système exécutée.

- OK — Syntaxe core.js
- OK — Syntaxe extract.js
- OK — Syntaxe background.js
- OK — Syntaxe popup.js
- OK — Manifest V3 et permissions
- OK — Installation sans alarme
- OK — Validation des URL
- OK — Planification aléatoire : 28 cas de bord
- OK — Activation avec alarme ponctuelle sans lecture immédiate
- OK — Référence initiale sans alerte
- OK — Nouvel ASIN : alerte et historique
- OK — Aucun doublon
- OK — Lecture vide conserve référence
- OK — Protection : désactivation et alarme effacée
- OK — Configuration et secret exclu de la réponse
- OK — Erreur réseau Telegram lisible sans secret
- OK — Échec Telegram conserve historique et erreur
- OK — Désactivation interdit les lectures
- OK — Réinitialisation
- OK — Extraction : ASIN valide, dédoublonnage et carte masquée
- OK — Extraction : ASIN invalide arrête la lecture
- OK — Extraction : CAPTCHA arrête la lecture
- OK — Extraction : grille absente conserve état et arrête
- OK — Extraction : grille vide sans remise à zéro
- OK — Fenêtre : identifiants uniques, éléments requis et absence de script inline

Les API ont été vérifiées dans la documentation officielle Chrome et Telegram (liens dans LISEZ-MOI.md). Les simulations ne prouvent pas la compatibilité avec le DOM Amazon actuel, le chargement effectif dans Chrome ou la réception des notifications Windows / Telegram. Ces trois points nécessitent la validation manuelle décrite dans le guide.

Contrôle du ZIP : CRC et contenu de chaque entrée comparés aux fichiers sources, manifeste et icône présents.

## Mise à jour 1.0.1 — tranches de dix minutes
Syntaxe des quatre fichiers JavaScript revalidée. Planification de 600 000 ms vérifiée sur 28 combinaisons de limites de tranche et de tirages aléatoires. Migration : ancienne alarme annulée et indices de planification réinitialisés, sans effacement des ASIN ni de Telegram. Aucune vérification en session réelle effectuée.

## Version 1.0.2 — photos Telegram
12 contrôles supplémentaires réussis, sur API et DOM simulés :
- OK — Syntaxe core.js
- OK — Syntaxe extract.js
- OK — Syntaxe background.js
- OK — Syntaxe popup.js
- OK — Première référence : aucun envoi Telegram
- OK — Liste inchangée : aucun envoi Telegram
- OK — Nouvelle carte : sendPhoto, image et titre dans la légende
- OK — Article déjà notifié : aucun renvoi
- OK — Photo absente : titre et lien envoyés en texte
- OK — Erreur de lecture : aucun message Telegram de statut
- OK — Extraction de l’URL photo Amazon
- OK — Rejet des images hors CDN Amazon ou non HTTPS (4 cas)
Aucun envoi réel effectué. La récupération des images dans votre page et leur accessibilité depuis Telegram restent à valider après installation.

## Version 1.0.3 — horaires quotidiens
16 contrôles supplémentaires réussis, dont 216 combinaisons de planification :
- OK — Syntaxe core.js
- OK — Syntaxe extract.js
- OK — Syntaxe background.js
- OK — Syntaxe popup.js
- OK — Bornes de jour : début inclus et fin exclue
- OK — Plage passant minuit
- OK — Plage désactivée : journée complète
- OK — Rejet horaires invalides
- OK — 216 plans vérifiés : jour, nuit et plage d’une minute
- OK — Activation hors plage programme une heure autorisée
- OK — Hors plage : aucun rechargement
- OK — Dans la plage : contrôle autorisé
- OK — Chargement terminé après fermeture : aucune lecture ni alerte
- OK — Paramètres invalides ne remplacent pas la plage
- OK — Modification conserve Telegram et les ASIN
- OK — Champs et bouton horaires présents, identifiants uniques
Contrôles effectués sur API simulées ; aucune session réelle Amazon / Telegram utilisée.

## Version 1.0.4 — journal du test Telegram
23 contrôles réussis sur cette version :
- OK — Syntaxe core.js
- OK — Syntaxe extract.js
- OK — Syntaxe telegram.js
- OK — Syntaxe background.js
- OK — Syntaxe popup.js
- OK — Test réussi : getMe puis sendMessage et confirmation persistée
- OK — Diagnostic Telegram 401
- OK — Diagnostic Telegram 403
- OK — Diagnostic Telegram 400
- OK — Diagnostic Telegram 429
- OK — Délai dépassé : erreur lisible sans secret
- OK — Erreur réseau : diagnostic de connexion
- OK — Réponse non JSON : HTTP conservé dans le journal
- OK — Description distante : jeton, chat ID et URL masqués
- OK — Jeton absent : journal et aucune requête réseau
- OK — Chat ID absent : erreur locale explicite
- OK — Effacement du journal sans effacer Telegram
- OK — État et logs accessibles pendant la requête réseau
- OK — Journal affiché et boutons présents
- OK — Cadence et horaires conservés
- OK — Aucune nouvelle permission
- OK — Fenêtre : progression visible sans réactiver les boutons pendant le test
- OK — Fenêtre : erreur conservée après actualisation et boutons libérés
Les réponses Telegram sont simulées. Aucun jeton réel utilisé et aucun message réel envoyé ; le défaut de configuration de votre bot ne peut donc pas être déterminé ici. Le journal permet de l’identifier après mise à jour et nouveau test.

## Version 1.0.5 — cadence configurable
15 contrôles de cadence réussis (dont 288 plans), et 23 contrôles Telegram / fenêtre réexécutés avec succès :
- OK — Syntaxe core.js
- OK — Syntaxe extract.js
- OK — Syntaxe telegram.js
- OK — Syntaxe background.js
- OK — Syntaxe popup.js
- OK — Migration : ancienne alarme annulée, indices réinitialisés et nouvelle alarme
- OK — Valeurs entières de 1 à 1 440 ; défaut 10 minutes
- OK — 288 plans valides : durées 1–1 440 min, horaires normaux/nocturnes et fenêtre d’une minute
- OK — Enregistrement : nouvelle unité et alarme ponctuelle
- OK — Même durée : alarme existante conservée
- OK — Valeurs invalides refusées sans remplacer la cadence
- OK — Nouvelle durée respecte les horaires et conserve Telegram / ASIN
- OK — Après une alarme : prochain indice calculé avec la durée choisie
- OK — Surveillance désactivée : sauvegarde sans nouvelle alarme
- OK — Contrôle de saisie et bouton présents
Toujours sans session réelle Amazon ni envoi Telegram réel. Sources des tests : tests-interval.mjs et tests-telegram.mjs.

## Version 1.0.6 — lien direct Vine
23 contrôles Telegram et 15 contrôles de cadence réexécutés avec succès. Deux cas de légende vérifiés (photo présente / absente) : URL Vine et lien produit présents, longueur inférieure à 1 000 caractères sur le cas testé. Aucun envoi réel.

## Version 1.0.7 — tranches dynamiques, première minute
20 contrôles de planification et 23 contrôles Telegram / fenêtre réussis en simulation.
- OK — Syntaxe core.js
- OK — Syntaxe extract.js
- OK — Syntaxe telegram.js
- OK — Syntaxe background.js
- OK — Syntaxe popup.js
- OK — Migration vers les tranches dynamiques sans effacer Telegram / ASIN
- OK — Base 5 : durées 4, 5 et 6 ; base 1 : durées 1 et 2
- OK — 216 plans : durée autorisée, première minute, minimum 30 s et horaires respectés
- OK — Les trois durées possibles sont effectivement tirées
- OK — Chaînage : prochaine tranche commence à la fin de la précédente
- OK — Première minute expirée : nouveau départ sans rattrapage
- OK — Alarme dans la première minute : une seule lecture et prochaine tranche programmée
- OK — Ancienne alarme dupliquée ignorée
- OK — Alarme retardée après la première minute : aucune lecture
- OK — Réveil du worker : plan futur conservé sans nouveau tirage
- OK — Nouvelle base sauvegardée, durée dans 6/7/8 et historique conservé
- OK — Valeurs de base invalides refusées
- OK — Hors plage : prochaine première minute dans les heures autorisées
- OK — Désactivation : réglage sauvegardé sans alarme
- OK — Lien Vine toujours présent dans les alertes
Aucune session réelle utilisée.

## Version 1.0.8 — trois nouveautés affichées
Limite d’affichage passée de dix à trois dans la fenêtre ; syntaxe de popup.js vérifiée. Stockage et envois Telegram inchangés.

## Version 1.0.9 — ouverture automatique de Vine
8 contrôles spécifiques réussis, avec 20 contrôles de planification et 23 contrôles Telegram réexécutés :
- OK — Sans onglet Vine : création index 0, fenêtre normale, arrière-plan
- OK — Fin de chargement du nouvel onglet : lecture et référence silencieuse
- OK — Vine déjà au troisième onglet : réutilisation sans création
- OK — Autre page Amazon : création de Vine sans modifier l’autre page
- OK — Hors horaires : aucune ouverture
- OK — Surveillance désactivée : aucune ouverture
- OK — Première minute dépassée : aucune ouverture
- OK — Échec ouverture : erreur lisible et aucune attente bloquée
API Chrome et réseau simulés. API tabs.create et windows.getLastFocused vérifiées dans la documentation officielle ; aucune nouvelle permission. Aucun navigateur réel contrôlé.

## Version 1.0.10 — alerte de protection
15 contrôles de protection réussis ; 23 contrôles Telegram, 20 de planification et 8 d’onglets réexécutés avec succès.
- OK — Syntaxe core.js
- OK — Syntaxe extract.js
- OK — Syntaxe telegram.js
- OK — Syntaxe background.js
- OK — Syntaxe popup.js
- OK — Protection : surveillance arrêtée avant l’envoi, une alerte avec lien et instructions
- OK — Pas de doublon après arrêt
- OK — Nouvel arrêt après réactivation : nouvelle alerte autorisée
- OK — Option décochée : arrêt sans alerte
- OK — Configuration absente : arrêt et erreur locale sans requête
- OK — Échec Telegram : arrêt conservé, erreur masquée, sans répétition automatique
- OK — Autre erreur : aucun faux message de protection
- OK — CAPTCHA reconnu et signalé explicitement
- OK — Panne de service distinguée d’une protection
- OK — Option de protection présente
API et réponses réseau simulées, aucun envoi réel ni session Amazon utilisée. Source supplémentaire : tests-protection.mjs.

## Version 1.0.11 — reprise des alarmes
Régression reproduite sur le code 1.0.10 : zéro contrôle au réveil avec alarme ponctuelle retirée avant livraison, contre un attendu. Le même scénario passe sur le correctif.
- OK — Réveil du worker avec alarme due : un contrôle et une seule avance de tranche
- OK — Alarme encore présente au réveil : un seul traitement
- OK — Alarme absente à dix secondes de l’échéance : même tranche, aucun saut
- OK — Première minute expirée : un seul saut explicitement journalisé
- OK — Tranche déjà marquée avant interruption : aucun doublon
- OK — 60 réveils avec base 5 et horaires 06:00–22:00 : aucun contrôle sauté ni écart de dix minutes
Les autres suites ont été réexécutées : 23 contrôles Telegram / fenêtre, 20 de tranches, 8 d’onglets et 15 de protection, tous réussis. Les 60 réveils emploient un nouveau contexte worker à chaque contrôle avec la base 5 et la plage 06:00–22:00. Chrome, le temps et le réseau sont simulés ; le défaut observé chez vous n’a pas été inspecté dans votre navigateur réel.
Documentation relue : https://developer.chrome.com/docs/extensions/reference/api/alarms et https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
