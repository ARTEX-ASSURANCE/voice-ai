# Centre d'Appel IA LiveKit

## Instructions de Configuration et d'Exécution du Projet

Ce projet se compose d'un backend Python Flask et d'un tableau de bord de supervision Streamlit.

### Prérequis

*   Python 3.x et pip.
*   Un compte LiveKit et des identifiants (Clé API, Secret API, URL du Serveur).
*   MySQL d'installé et configuré.

### Configuration de la Base de Données

Ce projet nécessite une base de données MySQL pour fonctionner.

1.  **Créez la base de données :**
    ```sql
    CREATE DATABASE extranet;
    ```

2.  **Créez un utilisateur (optionnel mais recommandé) :**
    ```sql
    CREATE USER 'root1'@'localhost' IDENTIFIED BY 'ARTEX123';
    GRANT ALL PRIVILEGES ON extranet.* TO 'root1'@'localhost';
    FLUSH PRIVILEGES;
    ```
    *Note : Assurez-vous que les informations d'identification de l'utilisateur correspondent à celles que vous configurerez dans les fichiers `.env` et `secrets.toml`.*

### Configuration des Services Externes

#### Intégration Google Calendar (pour la planification de rappels)

L'outil `schedule_callback` nécessite une intégration avec Google Calendar.

1.  **Créez un Projet Google Cloud :**
    *   Allez sur la [console Google Cloud](https://console.cloud.google.com/) et créez un nouveau projet.

2.  **Activez l'API Google Calendar :**
    *   Dans votre projet, allez à la section "API et services" > "Bibliothèque".
    *   Recherchez "Google Calendar API" et activez-la.

3.  **Créez un Compte de Service :**
    *   Allez à "API et services" > "Identifiants".
    *   Cliquez sur "Créer des identifiants" et choisissez "Compte de service".
    *   Donnez un nom à votre compte de service (ex: `voicebot-calendar-manager`) et accordez-lui le rôle "Éditeur" (ou un rôle plus restreint si vous le souhaitez).
    *   Une fois le compte créé, cliquez dessus, allez dans l'onglet "Clés", cliquez sur "Ajouter une clé" > "Créer une nouvelle clé".
    *   Choisissez le format **JSON** et téléchargez le fichier.

4.  **Partagez votre Calendrier :**
    *   Ouvrez Google Calendar.
    *   Allez dans les paramètres du calendrier que vous souhaitez utiliser.
    *   Dans la section "Partager avec des personnes spécifiques", ajoutez l'adresse e-mail de votre compte de service (elle se trouve dans le fichier JSON que vous avez téléchargé, sous la clé `client_email`).
    *   Assurez-vous de lui donner les permissions "Apporter des modifications aux événements".

5.  **Configurez les Variables d'Environnement :**
    *   Placez le fichier JSON de la clé du compte de service dans le répertoire `backend`.
    *   Ouvrez votre fichier `backend/.env` et mettez à jour les variables suivantes :
        ```
        GOOGLE_CALENDAR_ID="votre_id_de_calendrier_ici"
        GOOGLE_SERVICE_ACCOUNT_FILE="chemin/vers/votre_fichier.json"
        ```
        *   L'ID du calendrier se trouve dans les paramètres de votre calendrier Google.
        *   Le chemin du fichier de service doit être relatif au répertoire `backend`.

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
    *   Le fichier `.env.example` sert de modèle. Copiez-le vers un nouveau fichier nommé `.env` :
        ```bash
        cp .env.example .env
        ```
    *   Modifiez le fichier `.env` pour y ajouter vos propres clés API et autres secrets.

5.  **Lancez le serveur backend :**
    ```bash
    python server.py
    ```
    Le backend devrait maintenant être en cours d'exécution sur `http://localhost:5001`.

### 2. Configuration du Dashboard Streamlit

1.  **Naviguez vers le répertoire dashboard (depuis la racine du projet) :**
    ```bash
    cd dashboard
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

4.  **Configurez les secrets :**
    *   Le fichier `secrets.toml.example` sert de modèle. Copiez-le vers un nouveau fichier nommé `secrets.toml` dans le répertoire `.streamlit` :
        ```bash
        cp dashboard/.streamlit/secrets.toml.example dashboard/.streamlit/secrets.toml
        ```
    *   Modifiez le fichier `secrets.toml` pour y ajouter vos identifiants de base de données.


5.  **Lancez le dashboard :**
    ```bash
    streamlit run app.py
    ```
    Le dashboard devrait maintenant être accessible dans votre navigateur, généralement à `http://localhost:8501`.

### 3. Utilisation de l'Application

*   Assurez-vous que le serveur backend et le dashboard sont tous deux en cours d'exécution.
*   L'agent vocal est accessible via des appels SIP, gérés par le backend.
*   Le dashboard de supervision est accessible via l'URL fournie par Streamlit.

### 4. Dashboard de Supervision de l'Agent

Ce projet inclut un tableau de bord de supervision pour analyser les performances et les activités de l'agent IA. Le backend collecte des données détaillées et expose des APIs pour alimenter ce tableau de bord. Le frontend fournit une interface utilisateur pour visualiser ces données.

**Accès au Tableau de Bord:**

*   Une fois le backend et le dashboard démarrés, accédez au tableau de bord en naviguant vers l'URL du dashboard (par exemple, `http://localhost:8501`).

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
