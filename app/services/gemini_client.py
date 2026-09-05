import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

key = os.getenv("GEMINI_API_KEY", "").strip() 
if not key:
    raise RuntimeError("GEMINI_API_KEY is missing.")

client = genai.Client(api_key=key)
LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
PROJECT_NAME = os.getenv("GEMINI_PROJECT_NAME", "projects/267960008987")
PROJECT_NUMBER = os.getenv("GEMINI_PROJECT_NUMBER", "267960008987")
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")

