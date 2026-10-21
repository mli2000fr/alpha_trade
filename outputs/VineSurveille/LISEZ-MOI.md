# Vine Surveille — version 1.0.11
Extension Chrome Manifest V3 pour Windows 11. Chrome 120 ou plus récent.

## Installer ou mettre à jour
Extraire entièrement le ZIP. Pour une première installation : ouvrir chrome://extensions, activer le mode développeur, cliquer « Charger l’extension non empaquetée » et sélectionner le dossier VineSurveille contenant manifest.json.
Pour mettre à jour : remplacer les fichiers dans le dossier déjà chargé, puis cliquer « Recharger » sur la fiche de l’extension. Ne pas la désinstaller : les réglages et les ASIN sont conservés.
La migration annule l’ancien programme et recalcule la prochaine tranche. Aucun achat ni demande automatique de produit.

## Préparer la page
Ouvrir https://www.amazon.fr/vine/vine-items?queue=potluck dans le même profil Chrome, se connecter manuellement et conserver cet onglet sur la première page sans recherche. L’extension retrouve l’onglet même en arrière-plan ; si plusieurs correspondent, elle utilise le premier.
Si aucun onglet correspondant n’existe lors d’un contrôle programmé, l’extension ouvre Vine automatiquement en première position (index 0), dans la dernière fenêtre Chrome normale utilisée, sans prendre le premier plan. Les onglets épinglés restent prioritaires dans Chrome : le nouvel onglet ordinaire est placé en tête des onglets non épinglés. Le bouton « Ouvrir Vine » ouvre aussi un nouvel onglet en tête si nécessaire, et l’active.
Réserver cet onglet à la surveillance : il est rechargé à chaque contrôle.

## Tranches dynamiques : durée de base et première minute
Dans « Fréquence de surveillance », saisir une durée de base entière de 1 à 1 440 minutes puis cliquer « Enregistrer la durée ». Le défaut reste 10.
Pour une base N, chaque nouvelle tranche dure N−1, N ou N+1 minutes, avec un minimum d’une minute. Le tirage est indépendant à chaque tranche. Pour une base 1, les choix distincts sont 1 ou 2 minutes ; pour une base 1 440, les choix sont 1 439, 1 440 ou 1 441 minutes.
Chaque tranche comporte UNE vérification, dont le lancement est tiré au sort uniquement dans les 60 premières secondes de cette tranche. Aucun autre contrôle n’est lancé dans le reste de la tranche.
Exemple pour une base 5, à partir d’un début de tranche à 09:00 :
- tranche de 4 min : 09:00–09:04 ; contrôle possible à 09:00:37 ;
- tranche suivante de 6 min : 09:04–09:10 ; contrôle possible à 09:04:12 ;
- tranche suivante de 5 min : 09:10–09:15 ; contrôle possible à 09:10:48.
Les tranches s’enchaînent depuis la fin de la précédente ; elles ne sont plus des blocs fixes alignés sur l’horloge.
À l’activation ou après un changement de réglage, le premier début de tranche est programmé au moins 30 secondes plus tard. Ce délai tient compte de la limite des alarmes Chrome ; la première vérification est donc généralement prévue entre 30 et 90 secondes après l’activation.
Pour les tranches suivantes, la programmation respecte aussi un délai minimal de 30 secondes. Si nécessaire, seule la partie restante de la première minute est utilisée.
La fenêtre indique la durée de base, la durée et le début de la prochaine tranche, ainsi que l’heure de son contrôle.
Changer la base annule l’ancienne alarme et crée un nouveau départ. Enregistrer la même valeur conserve le tirage déjà prévu.
Chrome peut retarder une alarme. Si sa première minute est dépassée, le contrôle est ignoré, sans rattrapage tardif ni rafale. Si nécessaire, une nouvelle chaîne démarre. Le chargement et les alertes d’un contrôle lancé à temps peuvent se terminer après sa première minute.
Chrome fermé ou PC en veille : la cadence n’est pas garantie et le PC n’est pas réveillé. La prochaine alarme future est conservée lors du réveil du worker si elle reste exploitable.
Le caractère aléatoire ne garantit pas l’absence de détection par Amazon et ne constitue pas une autorisation d’automatisation.

## Horaires quotidiens
Cocher « Limiter à une plage horaire quotidienne », choisir le début et la fin puis cliquer « Enregistrer les horaires ».
Heure locale de Windows, tous les jours ; début inclus, fin exclue. 22:00–06:00 passe minuit. Deux heures identiques sont refusées ; décocher la limitation pour toute la journée.
Par défaut, la limitation est décochée ; les champs proposent 08:00–22:00.
Les contrôles sont choisis dans la partie autorisée de la première minute. Si aucune partie n’est autorisée, la prochaine tranche démarre à la prochaine ouverture possible.
Aucun rechargement n’est lancé hors plage. Si le chargement finit après la fermeture, sa lecture est ignorée. Les envois automatiques Telegram sont vérifiés avant chaque article ; une requête déjà envoyée peut être reçue après la fermeture.
« Désactiver » suspend aussi les reprises du lendemain. Après changement de fuseau ou réglage important de l’horloge Windows, réenregistrer les horaires pour recalculer le plan.
La référence reste conservée pendant la pause : un article apparu pendant la nuit mais encore présent à la reprise peut être signalé.

## Configurer Telegram
Utiliser un bot dédié, sans autre programme ni webhook.
1. Dans Telegram, ouvrir le compte officiel @BotFather : https://t.me/BotFather.
2. Envoyer /newbot et suivre les indications. Garder le jeton secret.
3. Ouvrir la conversation avec votre nouveau bot, appuyer sur « Démarrer » et envoyer « Bonjour ».
4. Dans l’extension, coller le jeton, laisser la case Telegram décochée et cliquer « Enregistrer ».
5. Cliquer « Détecter mon chat ID ». Cette action lit ponctuellement les mises à jour du bot et retient une seule discussion privée. Si plusieurs sont trouvées, utiliser un bot dédié ou saisir votre chat ID connu.
6. Cliquer « Enregistrer », puis « Tester Telegram » et vérifier la réception dans VOTRE conversation.
7. Cocher « Envoyer les nouveautés sur Telegram » puis « Enregistrer » pour les alertes automatiques.
Le chat ID est celui de votre conversation, pas l’identifiant du bot. Le jeton laissé vide conserve le jeton enregistré.
Si aucune discussion n’est trouvée, envoyer un nouveau message au bot puis réessayer. Telegram conserve les mises à jour au maximum 24 heures.
« Effacer Telegram » supprime les identifiants et désactive les envois. L’extension n’envoie ni email ni SMS.

## Notifications et photos
Cliquer « Activer » pour lancer la surveillance. La première lecture réussie établit la référence sans alerte.
Les notifications automatiques sont réservées aux ASIN jamais vus. Aucun message Telegram automatique de démarrage ou de contrôle inchangé. Une protection Amazon explicitement reconnue peut déclencher l’alerte d’arrêt décrite ci-dessous.
Chaque nouvel article a sa photo, son titre, son lien produit et le lien direct https://www.amazon.fr/vine/vine-items?queue=potluck.
La photo est lue sur la carte sans ouvrir la fiche produit. Seules les URL HTTPS des CDN Amazon reconnus sont transmises ; Telegram télécharge la photo depuis Amazon. Si elle manque, le titre et les liens sont envoyés avec la mention « Photo indisponible sur la carte ».
Les envois successifs sont espacés d’au moins 1,1 seconde. Un échec arrête l’envoi du reste du lot et apparaît dans l’extension. Aucun renvoi automatique : l’historique reste consultable.
Une coupure entre mémorisation et envoi peut faire manquer une alerte. Une requête interrompue peut avoir été livrée sans confirmation : livraison exactement une fois non garantie.
La notification Chrome cite jusqu’à trois titres ; cliquer dessus affiche Vine.
Windows : Paramètres > Système > Notifications > Google Chrome ; vérifier aussi « Ne pas déranger ».

## Journal du test Telegram
Le bouton « Tester Telegram » est un envoi manuel et fonctionne même hors horaires ou avec surveillance désactivée. Il utilise les paramètres ENREGISTRÉS.
« Journal du test Telegram » affiche les formats, la validation du bot par getMe, les réponses HTTP, l’envoi sendMessage, puis la confirmation ou l’erreur. Chaque requête a un délai maximal de 12 secondes.
Les étapes apparaissent pendant le test et restent si la fenêtre est rouverte. Chaque test remplace le journal précédent ; au maximum 80 lignes. Boutons « Copier le journal » et « Effacer le journal ».
Le jeton, les URL d’API contenant le jeton et le chat ID sont masqués. Les réponses complètes ne sont pas stockées. Les journaux ne sont pas envoyés à un autre service.
- 401 / 404 : vérifier le jeton auprès de BotFather, puis l’enregistrer.
- 400 / chat not found : envoyer un message au bot, puis vérifier ou détecter le chat ID.
- 403 : lire la description ; un chat ID de bot ne peut pas remplacer votre conversation personnelle. Vérifier aussi que le bot n’est pas bloqué.
- 429 : attendre le délai indiqué.
- Réseau / délai : vérifier connexion, VPN, pare-feu et autorisation api.telegram.org.
Une confirmation signifie que Telegram a créé le message dans la discussion configurée ; elle ne prouve ni sa lecture ni l’affichage d’une notification sur le téléphone.
Si aucune étape ne démarre, le worker peut traiter une opération en cours ; attendre ou recharger l’extension.

## Détection, limites et sécurité
Seules les cartes rendues dans la grille de la page ciblée sont lues. Les cartes masquées sont exclues ; les cartes situées sous le bas de l’écran mais rendues dans la page sont incluses. Aucun défilement automatique ni parcours des pages suivantes.
Un ASIN déjà connu ne déclenche pas de nouvelle alerte s’il revient ou si son titre change. Un article apparu puis disparu entre deux contrôles peut être manqué.
Maximum : 20 000 identifiants et 50 nouveautés mémorisées (trois affichées). Au plafond, arrêt de la surveillance. « Réinitialiser la référence » efface cette mémoire et l’historique après confirmation ; la prochaine lecture est silencieuse.
Une liste vide ou illisible ne remplace pas la référence. Une protection reconnue, une connexion requise ou une grille absente arrête la surveillance : résoudre manuellement puis réactiver.
Un chargement bloqué expire après deux minutes et est récupéré lors d’un contrôle ultérieur. Les sélecteurs Amazon peuvent évoluer.
Aucun achat, réservation, clic de demande de produit, résolution de CAPTCHA ou contournement de protection.
Le jeton est stocké dans chrome.storage.local, sans chiffrement dédié. Ne pas partager le profil ; révoquer le jeton via BotFather s’il est exposé. Les données Amazon transmises à Telegram se limitent aux titres, ASIN, liens et URL des photos ; aucun cookie ni mot de passe Amazon.

## Permissions
alarms : programmation ; storage : réglages et état local ; scripting : lecture des cartes ; notifications : alertes Chrome.
https://www.amazon.fr/* : retrouver l’onglet et lire le document principal après validation de la page ciblée.
https://api.telegram.org/* : alertes, test et détection de discussion sur demande.
Pas de permissions cookies, debugger ou webRequest, pas de code distant ni serveur tiers autre que Telegram. La désinstallation supprime le stockage local.

## Validation et documentation
Voir VERIFICATIONS.md. Les tests sont isolés, avec API Chrome, DOM et réponses réseau simulés : aucune connexion au compte Amazon ni envoi Telegram réel effectué.
Après installation : tester Chrome et Telegram, activer, vérifier l’heure de la prochaine tranche puis la dernière lecture réussie. La première lecture doit rester sans alerte.
Sources des tests : tests-interval.mjs et tests-telegram.mjs.
Documentation officielle :
- https://developer.chrome.com/docs/extensions/reference/api/alarms
- https://developer.chrome.com/docs/extensions/reference/api/storage
- https://developer.chrome.com/docs/extensions/reference/api/scripting
- https://developer.chrome.com/docs/extensions/reference/api/tabs
- https://developer.chrome.com/docs/extensions/reference/api/notifications
- https://core.telegram.org/bots/api
- https://core.telegram.org/bots/tutorial

## Ouverture automatique — version 1.0.9
L’ouverture automatique a lieu uniquement au moment d’un contrôle autorisé, avec surveillance activée, dans les horaires et dans la première minute de la tranche. La création charge déjà la page ; aucun second rechargement n’est ajouté. Si Vine est déjà ouvert ailleurs dans le même profil, l’onglet est réutilisé. Les autres pages Amazon restent inchangées.
Fermer l’onglet pendant la surveillance entraîne sa réouverture au prochain contrôle autorisé. Pour empêcher cette réouverture, désactiver la surveillance. Sans fenêtre normale disponible, l’erreur est affichée et le prochain contrôle pourra réessayer. Connexion requise ou protection détectée : intervention manuelle, sans contournement.

## Alerte Telegram de protection Amazon — version 1.0.10
L’option « Alerter sur Telegram en cas de protection Amazon » est activée par défaut. Elle utilise le même jeton et le même chat ID enregistrés que les nouveautés, mais reste indépendante de la case « Envoyer les nouveautés sur Telegram ». Pour la désactiver, décocher son option puis cliquer « Enregistrer ».
Quand un CAPTCHA, Robot Check, une vérification de sécurité ou une redirection de protection explicitement reconnue est détecté pendant un contrôle, l’extension désactive la surveillance et annule l’alarme avant de tenter un message Telegram. Le message contient le lien Vine et les instructions de reprise. Une seule tentative par arrêt : aucun renvoi automatique, même en cas d’échec. Une réactivation manuelle suivie d’une nouvelle protection peut entraîner une nouvelle alerte.
Le texte envoyé indique : « Protection Amazon détectée », « La surveillance Vine a été arrêtée », puis demande d’ouvrir Vine, résoudre manuellement la vérification, et cliquer sur Activer dans l’extension lorsque les articles sont de nouveau accessibles.
Pour réactiver :
1. Ouvrir https://www.amazon.fr/vine/vine-items?queue=potluck.
2. Résoudre soi-même le CAPTCHA / la vérification ou se reconnecter à Amazon.
3. Vérifier que la liste des articles est accessible.
4. Ouvrir l’extension et cliquer « Activer ».
La reprise suit la prochaine tranche programmée et les horaires enregistrés. Aucun redémarrage automatique après protection.
Si Telegram n’est pas configuré ou si l’envoi échoue, la surveillance reste arrêtée et l’erreur d’alerte s’affiche dans l’extension. La réception d’une alerte ne peut pas être garantie en cas de réseau coupé ou d’arrêt de Chrome pendant l’envoi. Les simples erreurs de grille, listes vides, pannes de service et demandes de connexion ne sont pas étiquetées automatiquement comme protection ; elles gardent leur traitement local. Certaines protections non reconnues peuvent donc ne produire aucune alerte Telegram.

## Correction des contrôles sautés — version 1.0.11
Un défaut a été reproduit dans la reprise du service worker : quand Chrome avait déjà retiré une alarme ponctuelle arrivée à échéance, la restauration pouvait avancer à la tranche suivante avant que l’événement d’alarme ne traite le contrôle, qui était alors ignoré. Une alarme future à moins de trente secondes pouvait également être abandonnée lors d’une restauration.
La reprise traite maintenant la tranche due une seule fois si sa première minute reste valide, et restaure une alarme future sans changer de tranche. Un marquage persistant empêche le double traitement entre reprise et événement. Les tranches périmées restent ignorées selon la règle de première minute et sont journalisées.
Mise à jour : remplacer les fichiers du dossier chargé, cliquer Recharger dans chrome://extensions, puis désactiver et réactiver la surveillance une fois afin de recalculer l’ancien programme. Ne pas réinitialiser la référence : Telegram, horaires et ASIN restent conservés.
La fenêtre contient « Journal de surveillance » : ouvrir ce volet pour voir les prochaines tranches, restaurations, déclenchements et contrôles ignorés. Quarante entrées locales au maximum ; aucun jeton, chat ID ou contenu Amazon n’y est inscrit. La copie peut se faire en sélectionnant le texte.
Une base 5 conserve les durées 4/5/6 et les contrôles dans leur première minute. Chrome peut toujours retarder les alarmes, notamment pendant une veille. Le journal permet de distinguer ces retards des restaurations de programme.
