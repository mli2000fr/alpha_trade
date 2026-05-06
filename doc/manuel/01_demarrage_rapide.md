# 1. Démarrage rapide — installer et lancer l'IHM

> Objectif : à la fin de ce manuel vous voyez la page d'accueil de l'IHM
> dans votre navigateur. Temps estimé : **30 min**.

## 1.1 Prérequis matériels

| Élément | Minimum | Recommandé |
|---|---|---|
| OS | Windows 10 64 bits | Windows 11 |
| RAM | 8 Go | 16 Go |
| Disque libre | 10 Go | 30 Go (cache historique) |
| Connexion Internet | requise | fibre |

## 1.2 Logiciels à installer

### a) Python 3.12

1. Allez sur <https://www.python.org/downloads/windows/>.
2. Téléchargez **Python 3.12.x** (64-bit installer).
3. Lancez l'installeur. **⚠️ Cochez impérativement** :
   - ☑ « Add python.exe to PATH »
   - ☑ « Install for all users »
4. Cliquez sur « Install Now » et attendez la fin.
5. Vérifiez dans **PowerShell** (touche Windows → tapez « PowerShell » → Entrée) :

   ```powershell
   python --version
   # doit afficher : Python 3.12.x
   ```

### b) MySQL 8 (base de données)

1. Téléchargez **MySQL Community Server 8.x** : <https://dev.mysql.com/downloads/mysql/>.
2. Installez-le. À la fin, notez bien le **mot de passe root** que vous saisissez.
3. Créez la base de données :
   - Ouvrez « MySQL Command Line Client » (menu démarrer).
   - Saisissez le mot de passe root.
   - Tapez :
     ```sql
     CREATE DATABASE alpha_trade CHARACTER SET utf8mb4;
     CREATE USER 'alpha'@'localhost' IDENTIFIED BY 'choisissez_un_mdp';
     GRANT ALL PRIVILEGES ON alpha_trade.* TO 'alpha'@'localhost';
     FLUSH PRIVILEGES;
     EXIT;
     ```
4. Notez le couple **(login=alpha, password=choisissez_un_mdp)**.

### c) Git (optionnel)

Si vous avez reçu le projet sous forme de dossier ZIP, sautez cette étape.
Sinon : <https://git-scm.com/download/win>.

## 1.3 Récupération du projet

- **Avec ZIP** : décompressez dans `C:\projets\` ou `F:\projets\` (le chemin
  ne doit pas contenir d'espaces ni d'accents).
- **Avec Git** :
  ```powershell
  cd F:\
  git clone <url-du-depot> projets
  ```

## 1.4 Installation des dépendances Python

Ouvrez **PowerShell** dans le dossier du projet :

```powershell
cd F:\projets
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> ⏱️ Compter **5 à 15 minutes** la première fois (téléchargement de
> PyTorch, pandas, etc.).

> 💡 Si PowerShell refuse d'activer le venv (« exécution de scripts désactivée »),
> tapez : `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` puis « O ».

## 1.5 Variables d'environnement (clés et accès)

Créez un fichier `.env` à la racine `F:\projets\.env` :

```env
# Base de données
LOGIN_DB=alpha
PASSWORD_DB=choisissez_un_mdp

# Alpaca (broker US, gratuit en paper trading)
ALPACA_API_KEY=xxxxxxxxxxxxxxxx
ALPACA_API_SECRET=yyyyyyyyyyyyyyyyyyyyyyyy
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# EODHD (données fondamentales — abonnement nécessaire pour l'usage complet)
EODHD_API_TOKEN=zzzzzzzzzzzzzzzzzzzzzz
```

### Comment obtenir les clés Alpaca

1. Inscription gratuite : <https://alpaca.markets>.
2. Onglet **Paper Trading** → **API Keys** → **Generate**.
3. Copiez la clé et le secret dans le `.env`.

> ✅ **Paper Trading** = simulation gratuite avec de fausses positions et un
> faux portefeuille. **C'est ce que vous utiliserez pendant des semaines avant
> tout passage en argent réel.**

### Comment obtenir le token EODHD (optionnel au début)

- <https://eodhistoricaldata.com/> — l'application peut tourner en mode dégradé
  sans EODHD (les fundamentals seront vides).

## 1.6 Premier lancement

Toujours dans PowerShell, dans le venv activé :

```powershell
cd F:\projets
python run.py
```

Une fenêtre devrait s'ouvrir dans votre navigateur sur :

```
http://localhost:8501
```

Vous voyez la page **🏠 Vue d'ensemble** ✨

> Si rien ne s'ouvre, copiez l'URL ci-dessus dans Chrome / Edge / Firefox.

## 1.7 Initialisation de la base de données (1 fois)

Dans une **autre** fenêtre PowerShell (laissez l'IHM tourner) :

```powershell
cd F:\projets
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Cela crée toutes les tables nécessaires.

## 1.8 Vous êtes prêt

- Continuez avec [02_premiers_pas_ihm.md](02_premiers_pas_ihm.md).
- Pour arrêter l'IHM : revenez dans la fenêtre PowerShell où elle tourne et
  tapez `Ctrl + C`.

## 1.9 Que faire en cas de problème

Voir [51_depannage.md](51_depannage.md) — section « Démarrage ».

