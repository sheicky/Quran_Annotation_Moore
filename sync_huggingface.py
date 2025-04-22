from huggingface_hub import HfApi
from datasets import Dataset, Audio
import json
import os
from dotenv import load_dotenv
import pandas as pd

# Charger les variables d'environnement
load_dotenv()

# Configuration
AUDIO_DIR = "audio_recordings"
METADATA_FILE = "metadata.json"
HUGGINGFACE_REPO = os.getenv("HUGGINGFACE_REPO", "votre-nom/quran-audio-moore")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"recordings": [], "users": {}}

def create_dataset():
    metadata = load_metadata()
    
    # Préparer les données pour le dataset
    data = {
        "audio": [],
        "verse_id": [],
        "sura": [],
        "aya": [],
        "user_id": [],
        "gender": [],
        "username": []
    }
    
    # Charger les versets pour avoir accès au texte
    verses_df = pd.read_excel("moore_rwwad_v1.0.1-excel.1.xlsx")
    verses_df.columns = ['id', 'sura', 'aya', 'translation', 'footnotes'] if len(verses_df.columns) >= 5 else verses_df.columns
    
    for recording in metadata["recordings"]:
        if os.path.exists(recording["audio_path"]):
            data["audio"].append(recording["audio_path"])
            data["verse_id"].append(recording["verse_id"])
            data["sura"].append(recording["sura"])
            data["aya"].append(recording["aya"])
            data["user_id"].append(recording["user_id"])
            data["gender"].append(recording["gender"])
            data["username"].append(metadata["users"][recording["user_id"]]["username"])
    
    # Créer le dataset
    dataset = Dataset.from_dict(data)
    
    # Convertir la colonne audio en caractéristiques audio
    dataset = dataset.cast_column("audio", Audio())
    
    return dataset

def push_to_huggingface():
    if not HUGGINGFACE_TOKEN:
        raise ValueError("Token HuggingFace non trouvé. Définissez HUGGINGFACE_TOKEN dans le fichier .env")
    
    # Créer le dataset
    dataset = create_dataset()
    
    # Push vers HuggingFace
    dataset.push_to_hub(
        HUGGINGFACE_REPO,
        token=HUGGINGFACE_TOKEN,
        private=False
    )
    
    print(f"Dataset mis à jour avec succès sur {HUGGINGFACE_REPO}")

if __name__ == "__main__":
    push_to_huggingface() 