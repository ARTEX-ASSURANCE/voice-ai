# Projet de Centre d'Appel IA (Architecture Refactorisée)

Ce projet est une implémentation d'un agent vocal IA pour un centre d'appel d'assurance. Il a été refactorisé pour suivre une architecture moderne, modulaire et orientée services, conçue pour la scalabilité, la maintenabilité et la robustesse.

## Vue d'ensemble de l'Architecture

Le projet est maintenant divisé en plusieurs services distincts qui communiquent entre eux :

*   **Application Layer (`src/application`)**: Un service API basé sur **FastAPI** qui sert de point d'entrée principal. Il gère les requêtes HTTP, comme la création de tokens d'accès pour les appels.
*   **Execution Layer (`src/execution`)**: Le cœur de l'agent IA. C'est un worker basé sur **LiveKit Agents** qui gère la logique de conversation, l'interaction avec le LLM, et l'utilisation des outils.
*   **Data Access Layer (`src/data_access`)**: Une couche de pilote de base de données dédiée qui gère toutes les interactions avec la base de données MySQL.
*   **Dashboard (`dashboard`)**: Un tableau de bord de supervision basé sur **Streamlit** pour analyser les performances et les activités de l'agent. (Note: L'intégration complète du tableau de bord avec la nouvelle architecture est en cours).

La gestion de l'état de la session est assurée par **Redis**, ce qui permet une meilleure scalabilité et une gestion de la mémoire plus robuste.

## Pile Technologique

*   **Backend**: Python, FastAPI, LiveKit Agents
*   **IA & Voix**: Google Gemini, Google TTS, Deepgram STT, Silero VAD
*   **Base de Données**: MySQL
*   **Gestion de l'État**: Redis
*   **Tableau de Bord**: Streamlit
*   **Déploiement**: Docker & Docker Compose

---

## Instructions de Configuration et d'Exécution

La méthode recommandée pour lancer ce projet est d'utiliser Docker, car il orchestre tous les services nécessaires (application, worker, redis).

### Prérequis

*   **Docker** et **Docker Compose** (v2) installés sur votre machine.
*   Un compte **LiveKit** et des identifiants (Clé API, Secret API, URL du Serveur).
*   Des identifiants de base de données **MySQL**.

### 1. Configuration de l'Environnement

1.  **Créez un fichier `.env`** à la racine du projet. Vous pouvez renommer le fichier `backend/.env.example` s'il existe ou en créer un nouveau.
2.  **Remplissez le fichier `.env`** avec vos identifiants :

    ```dotenv
    # Identifiants LiveKit
    LIVEKIT_API_KEY=votre_cle_api_livekit
    LIVEKIT_API_SECRET=votre_secret_api_livekit
    LIVEKIT_URL=votre_url_livekit

    # Identifiants Base de Données
    DB_HOST=nom_hote_db
    DB_USER=utilisateur_db
    DB_PASSWORD=mot_de_passe_db
    DB_NAME=nom_base_de_donnees
    DB_PORT=3306

    # Identifiants SendGrid (pour l'envoi d'e-mails)
    SENDGRID_API_KEY=votre_cle_api_sendgrid
    SENDER_EMAIL=votre_email_expediteur

    # Hôte Redis (utilisé par le worker)
    REDIS_HOST=redis
    REDIS_PORT=6379
    ```
    **Note :** `REDIS_HOST` est défini sur `redis`, qui est le nom du service dans le fichier `docker-compose.yml`. Ne changez pas cette valeur si vous utilisez Docker Compose.

### 2. Lancement des Services

1.  **Ouvrez un terminal** à la racine du projet.
2.  **Lancez tous les services** avec Docker Compose :
    ```bash
    docker compose up --build
    ```
    Cette commande va construire les images Docker pour les services `application` et `execution`, et démarrer un conteneur `redis`.

### 3. Utilisation de l'Application

*   **Point d'entrée API**: Le service `application` est maintenant accessible sur `http://localhost:8000`. C'est ce point de terminaison que votre frontend (non inclus dans ce dépôt) devrait utiliser pour obtenir un token LiveKit.
*   **Agent IA**: Le service `execution` se connectera automatiquement à votre instance LiveKit et attendra les appels.
*   **Tableau de Bord**: Le tableau de bord Streamlit n'est pas encore intégré au `docker-compose.yml`. Pour le lancer localement, vous pouvez naviguer vers le répertoire `dashboard` et suivre les instructions de son propre `README.md` (si disponible).

---

## Structure du Code

*   `src/`: Contient tout le code source de l'application.
    *   `application/`: Le service API FastAPI.
    *   `data_access/`: Le pilote de base de données.
    *   `execution/`: Le worker de l'agent LiveKit, y compris les outils (`tools.py`).
    *   `shared/`: Code partagé entre les services, comme le `MemoryManager` et les `prompts`.
*   `infra/`: Contient les fichiers de configuration de l'infrastructure, comme les `Dockerfile`s.
*   `dashboard/`: L'application du tableau de bord Streamlit.
*   `docker-compose.yml`: Le fichier d'orchestration pour lancer tous les services.
*   `.env`: Fichier (à créer) pour les secrets et les configurations.
*   `backend/`: **(Obsolète)** Contient les fichiers restants de l'ancienne architecture, comme les `knowledge_documents`.
