import os 
from huggingface_hub import HfApi, login, create_repo, upload_folder 
 
print("="*50) 
print("UPLOADING SCIBERT MODEL TO HUGGING FACE") 
print("="*50) 
 
token = input("Paste your token: ").strip() 
login(token=token) 
 
username = input("Your Hugging Face username: ").strip() 
repo_name = input("Repository name (press Enter for 'scibert-finetuned'): ").strip() 
if not repo_name: 
    repo_name = "scibert-finetuned" 
 
print(f"\n?? Creating/verifying repository: {username}/{repo_name}") 
create_repo(repo_id=f"{username}/{repo_name}", repo_type="model", exist_ok=True) 
 
print("?? Uploading model files... (this will take 3-5 minutes)") 
print(f"   Files to upload: {os.listdir('D:/SoftwareProject/scibert_finetuned')}") 
 
try: 
    upload_folder( 
        folder_path="D:/SoftwareProject/scibert_finetuned", 
        repo_id=f"{username}/{repo_name}", 
        repo_type="model", 
        commit_message="Upload SciBERT fine-tuned multi-classification model" 
    ) 
    print("\n? SUCCESS! Model uploaded successfully!") 
    print(f"?? View your model at: https://huggingface.co/{username}/{repo_name}") 
except Exception as e: 
    print(f"\n? Upload failed: {e}") 
