import os
import json
from pathlib import Path
from datetime import datetime
import shutil
import pandas as pd
from huggingface_hub import HfApi, create_repo, upload_file
from datasets import Dataset, Audio
import requests

class DataManager:
    def __init__(self, base_dir="."):
        self.base_dir = Path(base_dir)
        self.audio_dir = self.base_dir / "audio_recordings"
        self.metadata_file = self.base_dir / "metadata.json"
        self.backup_dir = self.base_dir / "backups"
        self.config_file = self.base_dir / "config.json"
        self.ADMIN_USERNAME = "sheickydollar"
        self.HF_DATASET_REPO = f"{self.ADMIN_USERNAME}/quran-audio-moore"
        
        # Créer les dossiers nécessaires
        self.audio_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Initialiser ou charger la configuration
        self.init_config()

    def init_config(self):
        """Initialiser ou charger la configuration du système."""
        if not self.config_file.exists():
            default_config = {
                "admin_username": self.ADMIN_USERNAME,
                "max_recordings_per_verse": 5,
                "repository": self.HF_DATASET_REPO,
                "settings": {
                    "require_admin_approval": True,
                    "auto_sync_to_hub": True
                }
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

    def is_admin(self, username):
        """Vérifier si l'utilisateur est l'admin."""
        return username == self.ADMIN_USERNAME

    def get_max_recordings(self):
        """Obtenir le nombre maximum d'enregistrements par verset."""
        return self.config["max_recordings_per_verse"]

    def update_max_recordings(self, new_max, username):
        """Mettre à jour le nombre maximum d'enregistrements par verset."""
        if not self.is_admin(username):
            raise PermissionError("Seul l'administrateur peut modifier ce paramètre")
        
        self.config["max_recordings_per_verse"] = new_max
        self.save_config()

    def save_config(self):
        """Sauvegarder la configuration."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def load_metadata(self, username=None):
        """Charger les métadonnées depuis le fichier JSON."""
        if not self.is_admin(username) and username is not None:
            # Pour les utilisateurs non-admin, retourner seulement leurs propres données
            full_metadata = self._load_full_metadata()
            user_metadata = {
                "recordings": [r for r in full_metadata["recordings"] if r["user_id"] == username],
                "users": {username: full_metadata["users"].get(username, {})} if username in full_metadata["users"] else {}
            }
            return user_metadata
        
        return self._load_full_metadata()

    def _load_full_metadata(self):
        """Charger toutes les métadonnées (accès admin uniquement)."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"recordings": [], "users": {}}

    def save_recording(self, audio_data, user_id, verse_info):
        """Sauvegarder un nouvel enregistrement."""
        metadata = self._load_full_metadata()
        
        # Créer le nom du fichier audio
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_filename = f"{user_id}_sura{verse_info['sura']}_aya{verse_info['aya']}_{timestamp}.wav"
        audio_path = self.audio_dir / audio_filename

        # Sauvegarder l'audio
        audio_data.save(str(audio_path))

        # Créer l'ID unique de l'enregistrement
        recording_id = f"rec_{timestamp}_{user_id}"

        # Mettre à jour les métadonnées
        recording_info = {
            "id": recording_id,
            "user_id": user_id,
            "verse_id": str(verse_info['id']),
            "sura": verse_info['sura'],
            "aya": verse_info['aya'],
            "audio_path": str(audio_path),
            "gender": metadata["users"][user_id]["gender"],
            "timestamp": datetime.now().isoformat(),
            "status": "approved",  # Par défaut approuvé
            "approved_by": None,
            "approved_at": datetime.now().isoformat()
        }
        
        metadata["recordings"].append(recording_info)
        self.save_metadata(metadata)
        
        # Synchroniser immédiatement avec HuggingFace
        try:
            self.sync_to_huggingface()
        except Exception as e:
            print(f"Erreur lors de la synchronisation avec HuggingFace: {str(e)}")
        
        return recording_id

    def save_metadata(self, metadata):
        """Sauvegarder les métadonnées avec backup."""
        if self.metadata_file.exists():
            backup_path = self.backup_dir / f"metadata_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy(self.metadata_file, backup_path)

        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def get_recording_stats(self, username=None):
        """Obtenir les statistiques des enregistrements."""
        metadata = self.load_metadata(username)
        
        if not self.is_admin(username):
            # Pour les utilisateurs non-admin, montrer seulement leurs stats
            return {
                "total_recordings": len(metadata["recordings"]),
                "pending_recordings": sum(1 for r in metadata["recordings"] if r["status"] == "pending"),
                "approved_recordings": sum(1 for r in metadata["recordings"] if r["status"] == "approved")
            }
        
        # Stats complètes pour l'admin
        stats = {
            "total_recordings": len(metadata["recordings"]),
            "total_users": len(metadata["users"]),
            "recordings_per_verse": {},
            "recordings_per_user": {},
            "recordings_per_gender": {"Homme": 0, "Femme": 0},
            "pending_recordings": sum(1 for r in metadata["recordings"] if r["status"] == "pending"),
            "approved_recordings": sum(1 for r in metadata["recordings"] if r["status"] == "approved")
        }
        
        for recording in metadata["recordings"]:
            verse_id = recording["verse_id"]
            user_id = recording["user_id"]
            gender = recording["gender"]
            
            stats["recordings_per_verse"][verse_id] = stats["recordings_per_verse"].get(verse_id, 0) + 1
            stats["recordings_per_user"][user_id] = stats["recordings_per_user"].get(user_id, 0) + 1
            stats["recordings_per_gender"][gender] += 1
            
        return stats

    def approve_recording(self, recording_id, admin_username):
        """Approuver un enregistrement."""
        if not self.is_admin(admin_username):
            raise PermissionError("Seul l'administrateur peut approuver les enregistrements")
        
        metadata = self._load_full_metadata()
        for recording in metadata["recordings"]:
            if recording["id"] == recording_id:
                recording["status"] = "approved"
                recording["approved_by"] = admin_username
                recording["approved_at"] = datetime.now().isoformat()
                break
        self.save_metadata(metadata)
        
        if self.config["settings"]["auto_sync_to_hub"]:
            self.sync_to_huggingface()

    def reject_recording(self, recording_id, admin_username):
        """Rejeter un enregistrement et le renvoyer à l'utilisateur pour réenregistrement."""
        if not self.is_admin(admin_username):
            raise PermissionError("Seul l'administrateur peut rejeter les enregistrements")
        
        metadata = self._load_full_metadata()
        
        for recording in metadata["recordings"]:
            if recording["id"] == recording_id:
                # Marquer l'enregistrement comme rejeté
                recording["status"] = "rejected"
                recording["rejected_by"] = admin_username
                recording["rejected_at"] = datetime.now().isoformat()
                
                # Ajouter le verset à la liste des versets à réenregistrer pour l'utilisateur
                user_id = recording["user_id"]
                verse_info = {
                    "verse_id": recording["verse_id"],
                    "sura": recording["sura"],
                    "aya": recording["aya"]
                }
                
                if "verses_to_rerecord" not in metadata:
                    metadata["verses_to_rerecord"] = {}
                if user_id not in metadata["verses_to_rerecord"]:
                    metadata["verses_to_rerecord"][user_id] = []
                
                metadata["verses_to_rerecord"][user_id].append(verse_info)
                break
                
        self.save_metadata(metadata)
        
        # Synchroniser avec HuggingFace pour retirer l'enregistrement rejeté
        try:
            self.sync_to_huggingface()
        except Exception as e:
            print(f"Erreur lors de la synchronisation avec HuggingFace: {str(e)}")

    def get_verses_to_rerecord(self, user_id):
        """Obtenir la liste des versets à réenregistrer pour un utilisateur."""
        metadata = self._load_full_metadata()
        if "verses_to_rerecord" not in metadata:
            return []
        
        return metadata["verses_to_rerecord"].get(user_id, [])

    def remove_verse_from_rerecord_list(self, user_id, verse_id):
        """Retirer un verset de la liste des versets à réenregistrer."""
        metadata = self._load_full_metadata()
        if "verses_to_rerecord" in metadata and user_id in metadata["verses_to_rerecord"]:
            metadata["verses_to_rerecord"][user_id] = [
                verse for verse in metadata["verses_to_rerecord"][user_id]
                if verse["verse_id"] != verse_id
            ]
            self.save_metadata(metadata)

    def sync_to_huggingface(self):
        """Synchroniser les données avec HuggingFace."""
        if not self.is_admin(self.ADMIN_USERNAME):
            raise PermissionError("Seul l'administrateur peut synchroniser avec HuggingFace")
        
        try:
            # Créer le dataset avec tous les enregistrements non rejetés
            dataset = self.create_huggingface_dataset()
            
            # Push vers HuggingFace
            dataset.push_to_hub(
                self.HF_DATASET_REPO,
                private=False,
                commit_message=f"Update dataset - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            print(f"Dataset mis à jour avec succès sur {self.HF_DATASET_REPO}")
            return True
        except Exception as e:
            print(f"Erreur lors de la synchronisation avec HuggingFace: {str(e)}")
            return False

    def create_huggingface_dataset(self):
        """Créer un dataset pour HuggingFace avec tous les enregistrements non rejetés."""
        metadata = self._load_full_metadata()
        
        # Charger les versets pour avoir accès au texte
        s3_path = "s3://moore-collection/raw_data/quran/data.xlsx"
        storage_options = {
            "key": os.getenv("AWS_ACCESS_KEY_ID"),
            "secret": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "client_kwargs": {"endpoint_url": os.getenv("AWS_S3_ENDPOINT_URL")  }
        }
        verses_df = pd.read_excel(s3_path, storage_options=storage_options)
        verses_df.columns = ['id', 'sura', 'aya', 'translation', 'footnotes'] if len(verses_df.columns) >= 5 else verses_df.columns
        
        data = {
            "audio": [],           # Fichier audio
            "verse_id": [],        # ID du verset
            "sura": [],           # Numéro de la sourate
            "aya": [],            # Numéro du verset
            "translation": [],     # Texte du verset en moore
            "user_id": [],        # ID de l'utilisateur
            "gender": [],         # Genre de l'utilisateur
            "username": [],       # Nom d'utilisateur
            "recording_date": [], # Date d'enregistrement
            "status": []          # Statut de l'enregistrement
        }
        
        for recording in metadata["recordings"]:
            # Inclure tous les enregistrements sauf ceux qui sont rejetés
            if recording["status"] != "rejected" and os.path.exists(recording["audio_path"]):
                # Récupérer les informations du verset
                verse_row = verses_df[verses_df['id'] == int(recording["verse_id"])]
                if not verse_row.empty:
                    translation = verse_row.iloc[0]['translation']
                else:
                    translation = "Traduction non disponible"

                data["audio"].append(recording["audio_path"])
                data["verse_id"].append(recording["verse_id"])
                data["sura"].append(recording["sura"])
                data["aya"].append(recording["aya"])
                data["translation"].append(translation)
                data["user_id"].append(recording["user_id"])
                data["gender"].append(recording["gender"])
                data["username"].append(metadata["users"][recording["user_id"]]["username"])
                data["recording_date"].append(recording["timestamp"])
                data["status"].append(recording["status"])
        
        # Créer le dataset
        dataset = Dataset.from_dict(data)
        
        # Convertir la colonne audio en caractéristiques audio
        dataset = dataset.cast_column("audio", Audio())
        
        return dataset

    def backup_data(self):
        """Créer une sauvegarde complète des données."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)
        
        # Copier les métadonnées et la configuration
        shutil.copy(self.metadata_file, backup_path / "metadata.json")
        shutil.copy(self.config_file, backup_path / "config.json")
        
        # Copier les fichiers audio
        audio_backup_path = backup_path / "audio_recordings"
        shutil.copytree(self.audio_dir, audio_backup_path, dirs_exist_ok=True)
        
        return str(backup_path)

    def verify_data_integrity(self):
        """Vérifier l'intégrité des données."""
        metadata = self.load_metadata()
        issues = []
        
        for recording in metadata["recordings"]:
            if not os.path.exists(recording["audio_path"]):
                issues.append(f"Fichier audio manquant: {recording['audio_path']}")
            
            if recording["user_id"] not in metadata["users"]:
                issues.append(f"Utilisateur manquant: {recording['user_id']}")
            
            if recording.get("approved_by") and recording["approved_by"] not in self.config["admins"]:
                issues.append(f"Approbateur invalide: {recording['approved_by']}")
        
        return issues 
    

# Initialiser le gestionnaire de données
data_manager = DataManager()
print("Dossiers initialisés avec succès !") 
