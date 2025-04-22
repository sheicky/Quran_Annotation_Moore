import gradio as gr
import pandas as pd
import requests
import os
from data_manager import DataManager

# Initialisation du gestionnaire de données
data_manager = DataManager()

def load_quran_verses():
    try:
        # Charger le fichier Excel en sautant la première ligne d'en-tête
        df = pd.read_excel("moore_rwwad_v1.0.1-excel.1.xlsx", skiprows=1)
        
        # Définir les noms de colonnes
        df.columns = ['id', 'sura', 'aya', 'translation', 'footnotes']
        
        # Nettoyer et convertir les types de données
        df['id'] = df['id'].astype(int).astype(str)  # Convertir en int puis en str pour éviter les .0
        df['sura'] = df['sura'].astype(int)
        df['aya'] = df['aya'].astype(int)
        
        # Trier par sourate et verset
        df = df.sort_values(by=['sura', 'aya'])
        print(f"Fichier des versets chargé avec succès. {len(df)} versets trouvés.")
        
        # Afficher les premiers versets pour vérification
        print("Premiers versets chargés:")
        print(df[['sura', 'aya', 'translation']].head())
        
        return df
    except Exception as e:
        print(f"Erreur lors du chargement des versets: {str(e)}")
        return None

# Charger les données des versets
verses_df = load_quran_verses()

def verify_hf_username(username):
    """Vérifie si le nom d'utilisateur HuggingFace existe."""
    try:
        response = requests.get(f"https://huggingface.co/{username}")
        return response.status_code == 200
    except:
        return False

def has_user_recorded_verse(user_id, verse_id, metadata):
    return any(r["user_id"] == user_id and r["verse_id"] == verse_id for r in metadata["recordings"])

def get_verse_recording_count(verse_id, metadata):
    return sum(1 for r in metadata["recordings"] if r["verse_id"] == verse_id and r["status"] == "approved")

def get_available_verse(user_id, metadata, verses_df):
    if verses_df is None:
        print("Erreur: Le fichier des versets n'a pas pu être chargé")
        return None, None

    try:
        # Obtenir les versets déjà enregistrés par l'utilisateur
        user_recordings = [r for r in metadata["recordings"] if r["user_id"] == user_id]
        recorded_verses = set(r["verse_id"] for r in user_recordings)
        
        # Compter les enregistrements approuvés par verset
        verse_counts = {}
        for recording in metadata["recordings"]:
            if recording["status"] == "approved":
                verse_counts[recording["verse_id"]] = verse_counts.get(recording["verse_id"], 0) + 1
        
        max_recordings = data_manager.get_max_recordings()
        
        # Parcourir les versets dans l'ordre du fichier
        for _, verse in verses_df.iterrows():
            verse_id = verse['id']  # Déjà converti en str lors du chargement
            
            # Vérifier si l'utilisateur a déjà enregistré ce verset
            if verse_id in recorded_verses:
                print(f"Verset {verse_id} déjà enregistré par l'utilisateur {user_id}")
                continue
            
            # Vérifier le nombre d'enregistrements pour ce verset
            current_count = verse_counts.get(verse_id, 0)
            if current_count >= max_recordings:
                print(f"Verset {verse_id} a déjà atteint le maximum d'enregistrements ({current_count}/{max_recordings})")
                continue
            
            # Si le verset est disponible, le retourner
            print(f"Attribution du verset {verse_id} à l'utilisateur {user_id}")
            verse_info = {
                'id': verse_id,
                'sura': verse['sura'],
                'aya': verse['aya'],
                'text': verse['translation']
            }
            return verse_id, verse_info
            
        print(f"Aucun verset disponible pour l'utilisateur {user_id}")
        return None, None
        
    except Exception as e:
        print(f"Erreur lors de la recherche d'un verset disponible: {str(e)}")
        return None, None

def register_user(username, gender):
    try:
        if not username or not gender:
            return "Veuillez remplir tous les champs", None, None, gr.update(visible=False)
        
        # Simple vérification HuggingFace
        if not verify_hf_username(username):
            return "Ce nom d'utilisateur HuggingFace n'existe pas", None, None, gr.update(visible=False)
        
        metadata = data_manager._load_full_metadata()
        
        # Vérifier si l'utilisateur existe déjà
        if username in metadata["users"]:
            print(f"L'utilisateur {username} existe déjà")
        else:
            metadata["users"][username] = {
                "username": username,
                "gender": gender
            }
            data_manager.save_metadata(metadata)
            print(f"Nouvel utilisateur {username} enregistré")
        
        # Obtenir le premier verset disponible
        verse_id, verse_info = get_available_verse(username, metadata, verses_df)
        if verse_id and verse_info:
            verse_text = f"""Sourate {verse_info['sura']}, Verset {verse_info['aya']} (ID: {verse_info['id']})

{verse_info['text']}"""
            print(f"Verset attribué à {username}: Sourate {verse_info['sura']}, Verset {verse_info['aya']}")
        else:
            verse_text = "Aucun verset disponible pour le moment"
            print(f"Aucun verset disponible pour {username}")
            
        return f"Inscription réussie! Bienvenue {username}", username, verse_text, gr.update(visible=True)
        
    except Exception as e:
        print(f"Erreur lors de l'inscription: {str(e)}")
        return "Une erreur est survenue lors de l'inscription. Veuillez réessayer.", None, None, gr.update(visible=False)

def get_contributors_stats():
    """Obtenir les statistiques détaillées des contributeurs."""
    metadata = data_manager._load_full_metadata()
    contributors = []
    
    for username, user_info in metadata["users"].items():
        # Filtrer les enregistrements de l'utilisateur
        user_recordings = [r for r in metadata["recordings"] if r["user_id"] == username]
        
        if user_recordings:
            # Trier les enregistrements par date pour avoir la dernière contribution
            sorted_recordings = sorted(user_recordings, key=lambda x: x["timestamp"], reverse=True)
            last_contribution = sorted_recordings[0]["timestamp"]
            
            # Compter les différents types d'enregistrements
            total_recordings = len(user_recordings)
            approved_recordings = sum(1 for r in user_recordings if r["status"] == "approved")
            pending_recordings = sum(1 for r in user_recordings if r["status"] == "pending")
            
            # Calculer le rang (basé sur le nombre d'enregistrements approuvés)
            rank = "🥇 Expert" if approved_recordings >= 50 else \
                   "🥈 Avancé" if approved_recordings >= 20 else \
                   "🥉 Intermédiaire" if approved_recordings >= 5 else \
                   "🌟 Débutant"
            
            contributors.append({
                "username": username,
                "gender": user_info["gender"],
                "rank": rank,
                "total_recordings": total_recordings,
                "approved_recordings": approved_recordings,
                "pending_recordings": pending_recordings,
                "last_contribution": last_contribution
            })
    
    # Trier les contributeurs par nombre d'enregistrements approuvés
    contributors.sort(key=lambda x: x["approved_recordings"], reverse=True)
    return contributors

def format_contributors_table(contributors):
    """Formater les statistiques des contributeurs en tableau Markdown."""
    if not contributors:
        return "Aucun contributeur pour le moment."
    
    # Créer l'en-tête du tableau
    table = """| Rang | Contributeur | Genre | Enregistrements approuvés | En attente | Dernière contribution |
|------|--------------|--------|----------------------|------------|---------------------|
"""
    
    # Ajouter chaque contributeur
    for contrib in contributors:
        # Formater la date
        date_str = pd.to_datetime(contrib["last_contribution"]).strftime("%d/%m/%Y %H:%M")
        
        # Ajouter la ligne au tableau
        table += f"| {contrib['rank']} | {contrib['username']} | {contrib['gender']} | {contrib['approved_recordings']} | {contrib['pending_recordings']} | {date_str} |\n"
    
    return table

def get_next_verse(username):
    """Obtenir le prochain verset disponible pour l'utilisateur."""
    try:
        metadata = data_manager._load_full_metadata()
        verse_id, verse_info = get_available_verse(username, metadata, verses_df)
        
        if verse_id and verse_info:
            verse_text = f"""Sourate {verse_info['sura']}, Verset {verse_info['aya']} (ID: {verse_info['id']})

{verse_info['text']}"""
            return verse_text
        else:
            return "Aucun verset disponible pour le moment"
            
    except Exception as e:
        print(f"Erreur lors de la recherche du prochain verset: {str(e)}")
        return "Une erreur est survenue. Veuillez réessayer."

def submit_recording(username, audio, verse_text):
    """Soumettre manuellement un enregistrement."""
    if audio is None:
        return "Veuillez d'abord enregistrer un verset.", verse_text
        
    try:
        # Extraire les informations du verset depuis le texte affiché
        import re
        match = re.match(r"Sourate (\d+), Verset (\d+) \(ID: (\d+)\)", verse_text)
        if not match:
            return "Erreur: impossible de récupérer les informations du verset", verse_text
            
        sura, aya, verse_id = map(int, match.groups())
        
        # Récupérer le texte du verset
        verse_row = verses_df[verses_df['id'] == verse_id]
        if verse_row.empty:
            return "Erreur: verset non trouvé dans la base de données", verse_text
            
        verse_info = {
            'id': str(verse_id),
            'sura': sura,
            'aya': aya,
            'text': verse_row.iloc[0]['translation']
        }
        
        success = data_manager.save_recording(audio, username, verse_info)
        if success:
            # Obtenir automatiquement le prochain verset
            metadata = data_manager._load_full_metadata()
            next_verse_id, next_verse_info = get_available_verse(username, metadata, verses_df)
            if next_verse_id and next_verse_info:
                next_verse_text = f"""Sourate {next_verse_info['sura']}, Verset {next_verse_info['aya']} (ID: {next_verse_info['id']})

{next_verse_info['text']}"""
                return "Enregistrement soumis avec succès!", next_verse_text
            else:
                return "Enregistrement soumis avec succès! Aucun autre verset disponible.", verse_text
        else:
            return "Erreur lors de la soumission de l'enregistrement.", verse_text
    except Exception as e:
        print(f"Erreur lors de la soumission: {str(e)}")
        return f"Une erreur est survenue lors de la soumission: {str(e)}", verse_text

def create_interface():
    global verses_df
    
    if verses_df is None:
        print("ERREUR: Impossible de charger le fichier des versets!")
        with gr.Blocks() as error_app:
            gr.Markdown("""
            # Erreur de chargement
            
            Impossible de charger le fichier des versets. Veuillez vérifier que le fichier Excel est présent et correctement formaté.
            """)
        return error_app
    
    print(f"Interface créée avec {len(verses_df)} versets chargés.")
    
    def record_verse(user_id, audio):
        if not user_id:
            return "ID utilisateur invalide", None
        if not audio:
            return "Aucun enregistrement détecté", None
        
        metadata = data_manager.load_metadata(user_id)
        
        # Vérifier d'abord s'il y a des versets à réenregistrer
        verses_to_rerecord = data_manager.get_verses_to_rerecord(user_id)
        if verses_to_rerecord:
            verse = verses_to_rerecord[0]
            verse_info = {
                'id': verse['verse_id'],
                'sura': verse['sura'],
                'aya': verse['aya'],
                'text': verses_df[verses_df['id'] == int(verse['verse_id'])]['translation'].iloc[0]
            }
            recording_id = data_manager.save_recording(audio, user_id, verse_info)
            data_manager.remove_verse_from_rerecord_list(user_id, verse['verse_id'])
            
            # Obtenir le prochain verset après le réenregistrement
            next_verse_id, next_verse_info = get_available_verse(user_id, metadata, verses_df)
            if next_verse_id and next_verse_info:
                next_verse_text = f"""Sourate {next_verse_info['sura']}, Verset {next_verse_info['aya']} (ID: {next_verse_info['id']})

{next_verse_info['text']}"""
            else:
                next_verse_text = "Aucun verset disponible pour le moment"
                
            return f"Réenregistrement sauvegardé avec succès pour la sourate {verse_info['sura']}, verset {verse_info['aya']}. En attente d'approbation.", next_verse_text
        
        if user_id not in metadata["users"]:
            return "ID utilisateur invalide", None
            
        verse_id, verse_info = get_available_verse(user_id, metadata, verses_df)
        if not verse_id:
            return "Aucun verset disponible pour l'enregistrement", None
        
        recording_id = data_manager.save_recording(audio, user_id, verse_info)
        
        # Obtenir automatiquement le prochain verset
        next_verse_id, next_verse_info = get_available_verse(user_id, metadata, verses_df)
        if next_verse_id and next_verse_info:
            next_verse_text = f"""Sourate {next_verse_info['sura']}, Verset {next_verse_info['aya']} (ID: {next_verse_info['id']})

{next_verse_info['text']}"""
        else:
            next_verse_text = "Aucun verset disponible pour le moment"
        
        return f"Enregistrement sauvegardé avec succès pour la sourate {verse_info['sura']}, verset {verse_info['aya']}. En attente d'approbation.", next_verse_text
    
    def display_user_stats(username):
        if not username:
            return "Veuillez entrer votre nom d'utilisateur"
            
        stats = data_manager.get_recording_stats(username)
        verses_to_rerecord = data_manager.get_verses_to_rerecord(username)
        
        rerecord_info = ""
        if verses_to_rerecord:
            rerecord_info = "\n\nVersets à réenregistrer :\n" + "\n".join(
                f"- Sourate {v['sura']}, Verset {v['aya']}"
                for v in verses_to_rerecord
            )
        
        return f"""Vos statistiques:
Total de vos enregistrements: {stats['total_recordings']}
Enregistrements en attente: {stats['pending_recordings']}
Enregistrements approuvés: {stats['approved_recordings']}{rerecord_info}"""

    def display_admin_stats(username):
        if not data_manager.is_admin(username):
            return "Accès non autorisé", None
            
        stats = data_manager.get_recording_stats(username)
        
        verse_stats = "\n".join([f"Verset {v}: {c} enregistrements" 
                               for v, c in stats['recordings_per_verse'].items()])
        
        user_stats = "\n".join([f"Utilisateur {u}: {c} enregistrements" 
                              for u, c in stats['recordings_per_user'].items()])
        
        stats_text = f"""Statistiques globales:
Total des enregistrements: {stats['total_recordings']}
Nombre d'utilisateurs: {stats['total_users']}
Enregistrements par genre:
- Homme: {stats['recordings_per_gender']['Homme']}
- Femme: {stats['recordings_per_gender']['Femme']}
Enregistrements en attente: {stats['pending_recordings']}
Enregistrements approuvés: {stats['approved_recordings']}

Statistiques par verset:
{verse_stats}

Statistiques par utilisateur:
{user_stats}"""

        # Créer un DataFrame pour l'affichage du dataset
        metadata = data_manager._load_full_metadata()
        verses_df = load_quran_verses()
        
        dataset_rows = []
        for recording in metadata["recordings"]:
            verse_row = verses_df[verses_df['id'] == int(recording["verse_id"])]
            translation = verse_row.iloc[0]['translation'] if not verse_row.empty else "Non disponible"
            
            dataset_rows.append({
                "ID Enregistrement": recording["id"],
                "Sourate": recording["sura"],
                "Verset": recording["aya"],
                "Texte": translation[:100] + "..." if len(translation) > 100 else translation,
                "Utilisateur": recording["user_id"],
                "Genre": recording["gender"],
                "Statut": recording["status"],
                "Date": recording["timestamp"],
                "Audio": recording["audio_path"] if os.path.exists(recording["audio_path"]) else "Fichier manquant"
            })
        
        dataset_df = pd.DataFrame(dataset_rows)
        return stats_text, dataset_df.to_csv(index=False)

    def sync_dataset(username):
        if not data_manager.is_admin(username):
            return "Accès non autorisé"
        
        success = data_manager.sync_to_huggingface()
        if success:
            return "Dataset synchronisé avec succès sur HuggingFace!"
        else:
            return "Erreur lors de la synchronisation. Vérifiez les logs pour plus de détails."

    def approve_recording(admin_username, recording_id):
        try:
            data_manager.approve_recording(recording_id, admin_username)
            return f"Enregistrement {recording_id} approuvé avec succès"
        except Exception as e:
            return str(e)

    def reject_recording(admin_username, recording_id):
        try:
            data_manager.reject_recording(recording_id, admin_username)
            return f"Enregistrement {recording_id} rejeté avec succès"
        except Exception as e:
            return str(e)

    def update_max_recordings(admin_username, new_max):
        try:
            data_manager.update_max_recordings(int(new_max), admin_username)
            return f"Nombre maximum d'enregistrements par verset mis à jour à {new_max}"
        except Exception as e:
            return str(e)

    with gr.Blocks() as app:
        gr.Markdown("""
        # 🎙️ Application d'enregistrement du Coran en Mooré
        
        ## Comment participer ?
        1. Inscrivez-vous avec votre nom d'utilisateur HuggingFace
        2. Sélectionnez votre genre
        3. Commencez à enregistrer les versets qui s'affichent !
        """)
        
        with gr.Tab("Inscription & Enregistrement"):
            with gr.Row():
                username = gr.Textbox(label="Nom d'utilisateur HuggingFace")
                gender = gr.Radio(choices=["Homme", "Femme"], label="Genre")
            register_btn = gr.Button("S'inscrire")
            registration_output = gr.Textbox(label="Statut de l'inscription")
            
            # Affichage du verset et contrôles d'enregistrement
            recording_section = gr.Column(visible=False)
            with recording_section:
                verse_display = gr.Textbox(label="Verset à enregistrer", lines=4)
                audio_recorder = gr.Audio(sources=["microphone"], type="filepath")
                with gr.Row():
                    submit_btn = gr.Button("📤 Soumettre l'enregistrement")
                    next_verse_btn = gr.Button("⏭️ Verset suivant")
                recording_status = gr.Textbox(label="Statut de l'enregistrement")

            # Événements
            register_btn.click(
                register_user,
                inputs=[username, gender],
                outputs=[registration_output, username, verse_display, recording_section]
            )
            
            submit_btn.click(
                submit_recording,
                inputs=[username, audio_recorder, verse_display],
                outputs=[recording_status, verse_display]
            )
            
            next_verse_btn.click(
                get_next_verse,
                inputs=[username],
                outputs=[verse_display]
            )

        with gr.Tab("Contributeurs"):
            gr.Markdown("""
            ## Liste des Contributeurs
            
            Classement des contributeurs basé sur le nombre d'enregistrements approuvés.
            
            ### Rangs :
            - 🥇 Expert : 50+ enregistrements approuvés
            - 🥈 Avancé : 20+ enregistrements approuvés
            - 🥉 Intermédiaire : 5+ enregistrements approuvés
            - 🌟 Débutant : Moins de 5 enregistrements approuvés
            """)
            
            contributors_display = gr.Markdown()
            refresh_btn = gr.Button("Rafraîchir la liste")
            
            def update_contributors():
                contributors = get_contributors_stats()
                return format_contributors_table(contributors)
            
            refresh_btn.click(
                update_contributors,
                outputs=contributors_display
            )
            
            # Afficher la liste initiale
            contributors_display.value = update_contributors()

        with gr.Tab("Mes statistiques"):
            user_stats_input = gr.Textbox(label="Votre nom d'utilisateur HuggingFace")
            show_stats_btn = gr.Button("Afficher mes statistiques")
            user_stats_output = gr.Textbox(label="Vos statistiques", lines=5)
            
            show_stats_btn.click(display_user_stats, inputs=[user_stats_input], outputs=user_stats_output)

        with gr.Tab("Administration"):
            admin_username = gr.Textbox(label="Nom d'utilisateur administrateur")
            
            with gr.Tab("Statistiques globales"):
                show_admin_stats_btn = gr.Button("Afficher les statistiques globales")
                admin_stats_output = gr.Textbox(label="Statistiques globales", lines=20)
                dataset_download = gr.File(label="Télécharger le dataset (CSV)")
                
                show_admin_stats_btn.click(
                    display_admin_stats,
                    inputs=[admin_username],
                    outputs=[admin_stats_output, dataset_download]
                )
            
            with gr.Tab("Dataset"):
                gr.Markdown("""
                ### Gestion du Dataset
                Le dataset est automatiquement synchronisé avec HuggingFace lorsque vous approuvez un enregistrement.
                Vous pouvez aussi forcer une synchronisation manuelle avec le bouton ci-dessous.
                """)
                sync_btn = gr.Button("Synchroniser avec HuggingFace", variant="primary")
                sync_output = gr.Textbox(label="Résultat de la synchronisation")
                
                # Lien vers le dataset
                gr.Markdown(f"""
                ### Accéder au Dataset
                Votre dataset est disponible sur HuggingFace à l'adresse suivante :
                [https://huggingface.co/datasets/{data_manager.HF_DATASET_REPO}](https://huggingface.co/datasets/{data_manager.HF_DATASET_REPO})
                """)
                
                sync_btn.click(
                    sync_dataset,
                    inputs=[admin_username],
                    outputs=sync_output
                )
            
            with gr.Tab("Gestion des enregistrements"):
                recording_id_input = gr.Textbox(label="ID de l'enregistrement")
                with gr.Row():
                    approve_btn = gr.Button("Approuver")
                    reject_btn = gr.Button("Rejeter")
                recording_action_output = gr.Textbox(label="Résultat")
                
                approve_btn.click(
                    approve_recording,
                    inputs=[admin_username, recording_id_input],
                    outputs=recording_action_output
                )
                reject_btn.click(
                    reject_recording,
                    inputs=[admin_username, recording_id_input],
                    outputs=recording_action_output
                )
            
            with gr.Tab("Paramètres"):
                max_recordings_input = gr.Number(label="Nombre maximum d'enregistrements par verset", value=data_manager.get_max_recordings())
                update_max_btn = gr.Button("Mettre à jour")
                update_max_output = gr.Textbox(label="Résultat")
                
                update_max_btn.click(
                    update_max_recordings,
                    inputs=[admin_username, max_recordings_input],
                    outputs=update_max_output
                )

    return app

if __name__ == "__main__":
    app = create_interface()
    app.launch(share=True) 