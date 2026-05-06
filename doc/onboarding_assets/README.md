# Assets vidéo onboarding

> Sprint S25.3 — Phase G.

Ce dossier contient les ressources binaires de la vidéo onboarding
opérateur (cf. `doc/onboarding_video_script.md`).

## Conventions

* Format vidéo : MP4 H.264 1080p 30 fps.
* Sous-titres : `.vtt` français.
* Nom de fichier : `onboarding_v<MAJOR.MINOR>.mp4`.
* Si fichier > 50 Mo : commit un pointer `onboarding_v1.mp4.url`
  contenant l'URL S3/Drive (ne pas commit le binaire).

## Fichiers attendus

| Fichier | Description | Statut |
|---|---|---|
| `onboarding_v1.mp4` | Vidéo principale (~150 Mo) | ⚠️ pointer URL |
| `onboarding_v1.vtt` | Sous-titres FR | ⚠️ à produire |
| `cover.png` | Vignette 1280x720 | ⚠️ à produire |

## Production

Voir `doc/onboarding_video_script.md` pour le découpage scènes,
captures à enregistrer, et checklist post-production.

