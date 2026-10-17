# Milestone 1: prove the API key and SDK work.
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

response = client.models.generate_content(model=model, contents="Say hello in one short sentence.")
print(response.text)
