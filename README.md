# Application d'Annotation Audio du Coran en Moore

Cette application permet d'enregistrer des versets du Coran en langue Moore. Elle est conçue pour créer un jeu de données de haute qualité avec plusieurs lecteurs par verset.

## Fonctionnalités

- Enregistrement audio des versets
- Système d'approbation par l'administrateur
- Possibilité de réenregistrement en cas de rejet
- Statistiques détaillées par utilisateur
- Interface d'administration
- Synchronisation automatique avec HuggingFace Datasets

## Configuration

1. Créez un Space sur HuggingFace :

   - Type : Gradio
   - Framework : Python
   - Hardware : CPU (suffisant pour cette application)

2. Variables d'environnement requises :

   ```
   HUGGINGFACE_TOKEN=votre_token_huggingface
   HUGGINGFACE_REPO=votre-nom/quran-audio-moore
   ```

3. Fichiers requis :
   - app.py (Interface utilisateur Gradio)
   - data_manager.py (Gestion des données)
   - sync_huggingface.py (Synchronisation avec HuggingFace)
   - requirements.txt (Dépendances)
   - moore_rwwad_v1.0.1-excel.1.xlsx (Données des versets)
   - .env (Variables d'environnement)

## Structure des données

Les enregistrements sont stockés localement dans le dossier `audio_recordings/` et les métadonnées dans `metadata.json`. Le script `sync_huggingface.py` synchronise ces données avec votre dataset HuggingFace.

## Déploiement

1. Créez votre Space sur HuggingFace
2. Ajoutez tous les fichiers requis
3. Configurez les variables d'environnement dans les paramètres du Space
4. L'application se déploiera automatiquement

## Synchronisation des données

La synchronisation avec HuggingFace se fait de deux manières :

1. Automatiquement lorsque l'administrateur approuve un enregistrement
2. Manuellement en exécutant `python sync_huggingface.py`

## Structure du projet

```
.
├── app.py                              # Interface Gradio
├── data_manager.py                     # Gestion des données
├── sync_huggingface.py                 # Synchronisation HF
├── requirements.txt                    # Dépendances
├── moore_rwwad_v1.0.1-excel.1.xlsx    # Données des versets
├── .env                               # Configuration
├── audio_recordings/                   # Dossier des enregistrements
└── metadata.json                      # Métadonnées
```
