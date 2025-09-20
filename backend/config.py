import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    SEMANTIC_API_KEY = os.getenv("SEMANTIC_API_KEY")
    IEEE_API_KEY = os.getenv("IEEE_API_KEY")
    DOWNLOAD_DIR = "./downloads"
