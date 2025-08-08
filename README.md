# Centre d'Appel IA LiveKit pour Voitures (Exemple)

## Instructions de Configuration et d'Exécution du Projet

Ce projet se compose d'un frontend React et d'un backend Python Flask.

### Prérequis

*   Node.js et npm (ou yarn) pour le frontend.
*   Python 3.x et pip pour le backend.
*   Un compte LiveKit et des identifiants (Clé API, Secret API, URL du Serveur).

### 1. Configuration du Backend

1.  **Naviguez vers le répertoire backend :**
    ```bash
    cd backend
    ```

2.  **Créez un environnement virtuel Python (recommandé) :**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sous Windows, utilisez `venv\Scripts\activate`
    ```

3.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurez les variables d'environnement :**
    *   Créez un fichier nommé `.env` dans le répertoire `backend`.
    *   Ajoutez vos identifiants LiveKit à ce fichier :
        ```
        LIVEKIT_API_KEY=votre_clé_api_ici
        LIVEKIT_API_SECRET=votre_secret_api_ici
        LIVEKIT_URL=votre_url_livekit_ici
        ```
        Remplacez les espaces réservés par votre clé API LiveKit, votre secret et l'URL de votre serveur (par exemple, `https://votre-projet-abcdef.livekit.cloud`).

5.  **Lancez le serveur backend :**
    ```bash
    python server.py
    ```
    Le backend devrait maintenant être en cours d'exécution sur `http://localhost:5001`.

### 2. Configuration du Frontend

1.  **Naviguez vers le répertoire frontend (depuis la racine du projet) :**
    ```bash
    cd frontend
    ```

2.  **Installez les dépendances :**
    ```bash
    npm install
    # ou
    # yarn install
    ```

3.  **Configurez les variables d'environnement :**
    *   Créez un fichier nommé `.env` dans le répertoire `frontend`.
    *   Ajoutez l'URL de votre serveur LiveKit et l'URL du backend à ce fichier :
        ```
        VITE_LIVEKIT_URL=wss://votre-domaine-livekit.com
        VITE_BACKEND_URL=http://localhost:5001
        ```
        Remplacez `wss://votre-domaine-livekit.com` par votre URL WebSocket LiveKit réelle (c'est souvent la même que votre `LIVEKIT_URL` mais préfixée par `wss://` et sans le `/` à la fin si `LIVEKIT_URL` l'a, ou cela peut être un point de terminaison WebSocket spécifique comme `wss://votre-projet-abcdef.livekit.cloud`).
        `VITE_BACKEND_URL` doit pointer vers votre serveur backend en cours d'exécution.

4.  **Lancez le serveur de développement frontend :**
    ```bash
    npm run dev
    # ou
    # yarn dev
    ```
    Le frontend devrait maintenant être accessible dans votre navigateur, généralement à `http://localhost:5173` (Vite affichera l'URL exacte).

### 3. Utilisation de l'Application

*   Assurez-vous que les serveurs backend et frontend sont tous deux en cours d'exécution.
*   Ouvrez l'URL du frontend dans votre navigateur (`http://localhost:5174` ou similaire).
*   L'interface principale vous permet de démarrer un appel avec l'agent vocal.
*   Une navigation simple en haut de la page permet d'accéder à l'interface d'appel (`/`) ou au tableau de bord (`/dashboard`).

### 4. Tableau de Bord de Supervision de l'Agent

Ce projet inclut un tableau de bord de supervision pour analyser les performances et les activités de l'agent IA. Le backend collecte des données détaillées et expose des APIs pour alimenter ce tableau de bord. Le frontend fournit une interface utilisateur pour visualiser ces données.

**Accès au Tableau de Bord:**

*   Une fois le frontend et le backend démarrés, accédez au tableau de bord en naviguant vers l'URL `/dashboard` dans votre navigateur (par exemple, `http://localhost:5174/dashboard`).

**Fonctionnalités du Tableau de Bord:**

Le tableau de bord offre plusieurs sections pour une analyse complète :

*   **Aperçu (KPIs) :**
    *   Indicateurs clés de performance agrégés : Nombre total d'appels, durée moyenne, nombre d'erreurs critiques, taux de confirmation d'identité, etc.
    *   Visualisation de l'utilisation des outils principaux par l'agent.
*   **Historique des Appels :**
    *   Liste paginée et filtrable de tous les appels enregistrés (par date, ID adhérent, numéro appelant).
    *   Informations de base pour chaque appel et accès aux détails.
*   **Vue Détaillée d'un Appel (Modale) :**
    *   Accessible depuis l'historique des appels.
    *   **Informations Générales:** Métadonnées de l'appel (ID, timestamps, durée, appelant, adhérent identifié).
    *   **Résumé de l'Appel:** Description narrative de l'appel (si généré par l'agent).
    *   **Évaluation de Performance:** Notes sur l'adhérence aux instructions et la résolution de l'appel (basées sur des heuristiques backend).
    *   **Chronologie des Actions de l'Agent:** Liste détaillée des outils appelés (avec paramètres et résultats) et des messages importants envoyés par l'agent.
    *   **Résumé des Actions sur la Base de Données:** Liste à puces des interactions clés avec la base de données (consultations, modifications) liées à l'appel.
    *   **Tableau des Interactions BD Détaillées:** Vue tabulaire complète de toutes les interactions avec la base de données pendant l'appel.
    *   **Erreurs Pendant l'Appel:** Liste des erreurs système survenues spécifiquement durant cet appel.
*   **Journal des Erreurs Système :**
    *   Liste paginée et filtrable de toutes les erreurs critiques survenues dans le backend, avec détails (source, message, trace, contexte).
*   **Journal des Interactions Base de Données :**
    *   Liste paginée et filtrable de toutes les opérations de base de données initiées par le système, avec détails (type, table, description).

**Collecte de Données Backend:**

*   Les données sont stockées dans une base de données MySQL. Les tables suivantes ont été ajoutées pour le tableau de bord :
    *   `journal_appels`: Métadonnées des appels, résumés, évaluations.
    *   `actions_agent`: Actions spécifiques de l'agent (appels d'outils, messages).
    *   `interactions_bd`: Opérations sur la base de données.
    *   `erreurs_systeme`: Erreurs système.
*   La journalisation est intégrée dans les modules backend (`agent.py`, `tools.py`, `db_driver.py`).
*   Une logique d'évaluation de performance post-appel (`performance_eval.py`) enrichit les données de `journal_appels`.
*   Les APIs pour le tableau de bord sont définies dans `dashboard_api.py`.

### 5. Considérations de Sécurité (Important)

*   **Protection des APIs du Tableau de Bord :** Les points de terminaison de l'API du tableau de bord (`/api/dashboard/*`) sont actuellement **non protégés**. Dans un environnement de production ou partagé, il est **essentiel** de mettre en place une authentification et une autorisation robustes pour contrôler l'accès à ces données potentiellement sensibles.
*   **Principe du Moindre Privilège (Base de Données) :** Le compte utilisateur de la base de données utilisé par l'application backend doit avoir uniquement les permissions minimales nécessaires sur les tables (par exemple, `SELECT` sur les tables de données principales, `INSERT/UPDATE/SELECT` sur les tables de journalisation).
*   **Journalisation de Données Sensibles :** Bien que l'objectif soit de journaliser les actions et non les données brutes sensibles, une attention particulière doit être portée aux paramètres des outils (`actions_agent.parametres_outil`) et aux descriptions d'actions BD (`interactions_bd.description_action`) pour éviter la journalisation involontaire d'informations confidentielles non nécessaires à l'audit. Un masquage ou une omission sélective pourrait être requis.
*   **HTTPS :** Pour tout déploiement, assurez-vous que toutes les communications entre le client, le serveur frontend et le serveur backend sont chiffrées via HTTPS.

### 6. Robustesse et Améliorations Futures

*   **Gestion des Erreurs :** Le système intègre une journalisation des erreurs. Une surveillance active de ces journaux est recommandée.
*   **Scalabilité de la Journalisation :** Pour des environnements à très haute charge, la journalisation directe en base de données pourrait devenir un goulot d'étranglement. Des mécanismes de journalisation asynchrone ou des services de journalisation dédiés pourraient être envisagés.
*   **Tests :** Un plan de test conceptuel a été défini. L'exécution rigoureuse de tests unitaires, d'intégration et de bout en bout est cruciale avant toute utilisation en production.
*   **Évaluation de Performance de l'Agent :** La logique actuelle est basée sur des heuristiques. Elle peut être significativement améliorée et affinée avec des analyses plus poussées ou même des évaluations assistées par LLM.
