import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Configuration variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
LNBITS_ADMIN_KEY = os.getenv('LNBITS_ADMIN_KEY')
LNBITS_DOMAIN = os.getenv('LNBITS_DOMAIN')
