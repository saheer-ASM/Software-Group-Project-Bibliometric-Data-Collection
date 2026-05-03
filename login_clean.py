token = input("Enter your token: ").strip() 
from huggingface_hub import login 
print("Logging in...") 
login(token=token) 
print("Login successful!") 
