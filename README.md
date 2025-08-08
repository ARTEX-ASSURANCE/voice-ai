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

3.  **Appliquez le schéma de la base de données :**
    *   Le projet a subi une refonte majeure de la base de données. Pour appliquer le nouveau schéma et migrer les anciennes données (si elles existent), vous devez exécuter le script de migration.
    *   Connectez-vous à votre serveur MySQL et exécutez le script `migration.sql` qui se trouve dans le répertoire `backend`.
    *   Exemple de commande :
        ```bash
        mysql -u root1 -p extranet < backend/migration.sql
        ```

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

2.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configurez les variables d'environnement :**
    *   Le fichier `.env.example` sert de modèle. Copiez-le vers un nouveau fichier nommé `.env` :
        ```bash
        cp .env.example .env
        ```
    *   Modifiez le fichier `.env` pour y ajouter vos propres clés API et autres secrets.

4.  **Lancez le serveur backend :**
    ```bash
    python server.py
    ```
    Le backend devrait maintenant être en cours d'exécution sur `http://localhost:5001`.

### 2. Configuration du Dashboard Streamlit

1.  **Naviguez vers le répertoire dashboard (depuis la racine du projet) :**
    ```bash
    cd dashboard
    ```

2.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configurez les secrets :**
    *   Le fichier `secrets.toml.example` sert de modèle. Copiez-le vers un nouveau fichier nommé `secrets.toml` dans le répertoire `.streamlit` :
        ```bash
        cp dashboard/.streamlit/secrets.toml.example dashboard/.streamlit/secrets.toml
        ```
    *   Modifiez le fichier `secrets.toml` pour y ajouter vos identifiants de base de données.


4.  **Lancez le dashboard :**
    ```bash
    streamlit run app.py
    ```
    Le dashboard devrait maintenant être accessible dans votre navigateur, généralement à `http://localhost:8501`.
