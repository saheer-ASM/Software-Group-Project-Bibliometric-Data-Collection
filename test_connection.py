import requests

try:
    r = requests.get("https://huggingface.co")
    print(r.status_code)
except Exception as e:
    print(e)