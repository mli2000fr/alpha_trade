# Reprise Qwen local — 8 novembre 2026

Demande utilisateur : « tu peux reprenadre ». La campagne source reste
`artifacts/research/us_local_llm_winner_ab/20261107-v7`.

## Incident et remise en service

Le journal LM Studio du7 novembre à23 h33 montre `CUDA error: out of memory`,
puis l'arrêt du moteur llama.cpp ; le client avait enregistré HTTP400.
Après redémarrage par l'utilisateur, le serveur répondait, mais le modèle
Qwen3.5-9b Q8_0 était chargé avec4 096 tokens de contexte, incompatible avec
les requêtes figées. Il a été rechargé à34 186 tokens, même contexte qu'au
lancement précédent, et **une seule génération simultanée** au lieu de quatre
pour réduire la pression GPU. La limite de sortie reste16 384, timeout600s,
température0, modèle et prompt inchangés. Aucun appel GPT.

## Reprise et conservation

Programme : `scripts/research/us_local_llm_winner_resume.py`.
Avant reprise :99 dossiers qualifiés (61 réponses LLM et38 sans news),
57 invalides dont une erreur de transport sans reçu,48 dossiers non traités.

Le dossier `resume-attempts/<horodatage>/` conserve une sauvegarde SQLite de
l'ancien cache, les anciens bilans, l'autorisation et la configuration du modèle.
L'erreur de transport FLR18/08/2025 est retentée **une fois**. Le nouveau résultat
est ajouté au cache avec la même clé de requête ; l'ancienne tentative n'est
pas effacée. Une erreur technique persistante ou une sortie tronquée arrête
la reprise sans répétition automatique.

Ensuite, seules les48 requêtes non encore traitées sont lancées. Les autres
réponses déjà reçues, y compris celles aux citations invalides, ne sont pas
redemandées. Les sources, textes, requêtes et validations du protocole sont
vérifiés avant reprise. Une nouvelle erreur serveur arrête les appels suivants.
Deux tests vérifient que la reprise cible uniquement une erreur de transport
sans reçu et refuse une reprise générale ambiguë de plusieurs erreurs.

## Suivi et limites

Suivi courant : `campaign/progress.json`, recopié dans le dossier de reprise.
Pendant l'analyse : compteurs, titre/date en cours et PID enfant. Le log de
reprise et le reçu du rattrapage transport se trouvent dans `resume-attempts`.
Les anciens journaux de campagne restent intacts.

Le script reprend la collecte d'avis, sans changer les règles de validation ni
autoriser les réponses invalides dans le replay. Aucun backtest économique
Qwen n'est lancé automatiquement tant que des réponses restent invalides.
La règle d'exclusion technique demandée pour le test GPT est une expérience
distincte. Aucun changement de batch, modèle financier ou compte broker.
