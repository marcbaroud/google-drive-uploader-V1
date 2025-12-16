import os
import threading
import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
SCOPES = ["https://www.googleapis.com/auth/drive"]
BACKUP_ROOT_NAME = "BackupFolder2025"

class DriveUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Drive Dropper")
        self.root.geometry("500x350")
        self.root.config(bg="#f0f0f0")

        # UI Elements
        self.label = tk.Label(
            root, 
            text="Drag & Drop a File OR Folder Here", 
            bg="#ffffff", 
            fg="#333333",
            font=("Arial", 14, "bold"),
            relief="groove",
            borderwidth=2
        )
        self.label.pack(expand=True, fill="both", padx=20, pady=20)
        
        self.status_label = tk.Label(root, text="Ready", bg="#f0f0f0", fg="blue")
        self.status_label.pack(side="bottom", pady=10)

        # Register the Drag and Drop functionality
        self.label.drop_target_register(DND_FILES)
        self.label.dnd_bind('<<Drop>>', self.drop_handler)

    def get_google_service(self):
        """Handles authentication and returns the drive service."""
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        return build("drive", "v3", credentials=creds)

    def drop_handler(self, event):
        """Triggered when a file/folder is dropped."""
        path = event.data
        # Clean up path (tkinterdnd sometimes adds {} around paths with spaces)
        if path.startswith('{') and path.endswith('}'):
            path = path[1:-1]
        
        # We accept BOTH files and folders now
        if os.path.exists(path):
            self.status_label.config(text=f"Preparing: {os.path.basename(path)}...")
            threading.Thread(target=self.process_upload, args=(path,), daemon=True).start()
        else:
            self.status_label.config(text="Error: Invalid path dropped.")

    def process_upload(self, local_path):
        """Decides if it's a file or folder and uploads accordingly."""
        try:
            service = self.get_google_service()
            item_name = os.path.basename(local_path)

            # 1. Get/Create the Main Root Folder (BackupFolder2025)
            query = f"name='{BACKUP_ROOT_NAME}' and mimeType='application/vnd.google-apps.folder'"
            response = service.files().list(q=query, spaces='drive').execute()
            
            if not response['files']:
                file_metadata = {
                    "name": BACKUP_ROOT_NAME,
                    "mimeType": "application/vnd.google-apps.folder"
                }
                root_folder = service.files().create(body=file_metadata, fields="id").execute()
                root_id = root_folder.get('id')
            else:
                root_id = response['files'][0]['id']

            # --- BRANCH 1: IT IS A SINGLE FILE ---
            if os.path.isfile(local_path):
                self.update_status(f"Uploading file: {item_name}...")
                
                file_metadata = {"name": item_name, "parents": [root_id]}
                media = MediaFileUpload(local_path)
                
                service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id"
                ).execute()

            # --- BRANCH 2: IT IS A FOLDER ---
            elif os.path.isdir(local_path):
                self.update_status(f"Creating folder '{item_name}' on Drive...")
                
                # Create the sub-folder inside BackupFolder2025
                sub_folder_meta = {
                    "name": item_name,
                    "parents": [root_id],
                    "mimeType": "application/vnd.google-apps.folder"
                }
                sub_folder = service.files().create(body=sub_folder_meta, fields="id").execute()
                sub_folder_id = sub_folder.get('id')

                # Loop through files in that folder
                files = os.listdir(local_path)
                total_files = len(files)
                
                for index, file_name in enumerate(files):
                    full_path = os.path.join(local_path, file_name)
                    
                    if os.path.isfile(full_path):
                        self.update_status(f"Uploading {index + 1}/{total_files}: {file_name}")
                        
                        file_metadata = {"name": file_name, "parents": [sub_folder_id]}
                        media = MediaFileUpload(full_path)
                        
                        service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields="id"
                        ).execute()

            self.update_status("Upload Complete!")

        except Exception as e:
            print(e)
            self.update_status(f"Error: {str(e)}")

    def update_status(self, message):
        """Helper to safely update GUI from a thread."""
        self.root.after(0, lambda: self.status_label.config(text=message))

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = DriveUploaderApp(root)
    root.mainloop()