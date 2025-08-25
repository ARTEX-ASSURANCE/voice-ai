# Projet de Centre d'Appel IA (Architecture Refactorisée)

Ce projet est une implémentation d'un agent vocal IA pour un centre d'appel d'assurance. Il a été refactorisé pour suivre une architecture moderne, modulaire et orientée services, conçue pour la scalabilité, la maintenabilité et la robustesse.

## Vue d'ensemble de l'Architecture

Le projet est maintenant divisé en plusieurs services distincts qui doivent être exécutés localement :

*   **Application Layer (`src/application`)**: Un service API basé sur **FastAPI** qui sert de point d'entrée principal. Il gère les requêtes HTTP, comme la création de tokens d'accès pour les appels.
*   **Execution Layer (`src/execution`)**: Le cœur de l'agent IA. C'est un worker basé sur **LiveKit Agents** qui gère la logique de conversation, l'interaction avec le LLM, et l'utilisation des outils.
*   **Data Access Layer (`src/data_access`)**: Une couche de pilote de base de données dédiée qui gère toutes les interactions avec la base de données MySQL.
*   **Dashboard (`dashboard`)**: Un tableau de bord de supervision basé sur **Streamlit**.

La gestion de l'état de la session est assurée par **Redis**.

## Pile Technologique

*   **Backend**: Python, FastAPI, LiveKit Agents
*   **IA & Voix**: Google Gemini, Google TTS, Deepgram STT, Silero VAD
*   **Base de Données**: MySQL
*   **Gestion de l'État**: Redis
*   **Tableau de Bord**: Streamlit

---

## Instructions de Configuration et d'Exécution Locale

Cette section décrit comment configurer et lancer le projet sur votre machine locale sans utiliser Docker.

### Prérequis

*   **Python 3.11** ou supérieur.
*   Un serveur **Redis** installé et en cours d'exécution sur votre machine locale.
*   Un serveur **MySQL** installé et en cours d'exécution sur votre machine locale.
*   Un compte **LiveKit** et des identifiants (Clé API, Secret API, URL du Serveur).
*   Les dépendances de build pour `mysqlclient` (ex: `default-libmysqlclient-dev` sur Debian/Ubuntu).

### 1. Configuration de l'Environnement

1.  **Créez un environnement virtuel Python** à la racine du projet (recommandé) :
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sous Windows, utilisez `venv\Scripts\activate`
    ```

2.  **Installez toutes les dépendances** depuis le fichier `requirements.txt` consolidé :
    ```bash
    pip install -r requirements.txt
    ```

3.  **Créez un fichier `.env`** à la racine du projet.
4.  **Remplissez le fichier `.env`** avec vos identifiants. **Important :** Pour une exécution locale, `DB_HOST` et `REDIS_HOST` doivent pointer vers `localhost`.

    ```dotenv
    # Identifiants LiveKit
    LIVEKIT_API_KEY=votre_cle_api_livekit
    LIVEKIT_API_SECRET=votre_secret_api_livekit
    LIVEKIT_URL=votre_url_livekit

    # Identifiants Base de Données (configuration locale)
    DB_HOST=localhost
    DB_USER=utilisateur_db
    DB_PASSWORD=mot_de_passe_db
    DB_NAME=nom_base_de_donnees
    DB_PORT=3306

    # Identifiants SendGrid
    SENDGRID_API_KEY=votre_cle_api_sendgrid
    SENDER_EMAIL=votre_email_expediteur

    # Hôte Redis (configuration locale)
    REDIS_HOST=localhost
    REDIS_PORT=6379
    ```

### 2. Lancement des Services

Pour que le système fonctionne, vous devez lancer les deux services principaux (Application et Execution) dans des terminaux séparés. Assurez-vous que votre environnement virtuel est activé dans chaque terminal.

1.  **Lancez le Service Application (API FastAPI)** :
    *   Ouvrez un premier terminal.
    *   Exécutez la commande suivante :
        ```bash
        python -m src.application.main
        ```
    *   Le service API devrait maintenant être en cours d'exécution sur `http://localhost:8000`.

2.  **Lancez le Service Execution (Agent IA)** :
    *   Ouvrez un second terminal.
    *   Exécutez la commande suivante pour démarrer le worker :
        ```bash
        python -m src.execution.worker start
        ```
    *   Le worker se connectera à LiveKit et sera prêt à recevoir des appels.

### 3. Utilisation de l'Application

*   Votre frontend (non inclus dans ce dépôt) doit maintenant être configuré pour envoyer des requêtes au point de terminaison `http://localhost:8000` pour obtenir les tokens LiveKit.
*   Une fois qu'un client se connecte à une room LiveKit, le service d'exécution prendra en charge l'appel.

---

## Structure du Code

*   `src/`: Contient tout le code source de l'application.
    *   `application/`: Le service API FastAPI.
    *   `data_access/`: Le pilote de base de données.
    *   `execution/`: Le worker de l'agent LiveKit, y compris les outils (`tools.py`).
    *   `shared/`: Code partagé entre les services, comme le `MemoryManager` et les `prompts`.
*   `dashboard/`: L'application du tableau de bord Streamlit.
*   `requirements.txt`: La liste consolidée de toutes les dépendances Python.
*   `.env`: Fichier (à créer) pour les secrets et les configurations.
*   `backend/`: **(Obsolète)** Contient les fichiers restants de l'ancienne architecture, comme les `knowledge_documents`.
