import os
from huggingface_hub import login
token = os.environ.get("HF_TOKEN")
if token:
    login(token=token)