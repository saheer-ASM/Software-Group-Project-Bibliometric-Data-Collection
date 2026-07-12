import requests

url = "https://mohameddshaheer-field-classification-api.hf.space/predict"

paper_text = """
Title: Intrusion Detection in Software Defined Networks Using Machine Learning

Abstract: Software Defined Networking (SDN) has emerged as a flexible network architecture.
However, SDN controllers are vulnerable to various cyberattacks. This paper proposes a machine
learning-based intrusion detection framework that analyzes network traffic features and classifies
malicious activities using Random Forest and XGBoost models.
"""

response = requests.post(
    url,
    json={"text": paper_text}
)

print(response.status_code)
print(response.json())