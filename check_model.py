import requests

url = "https://mohameddshaheer-field-classification-api.hf.space/predict"

payload = {
    "text": "Hospital and Healthcare."
}

response = requests.post(url, json=payload)

print(response.status_code)
print(response.json())