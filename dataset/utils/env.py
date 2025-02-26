# importing os module for environment variables
import os
# importing necessary functions from dotenv library
from dotenv import load_dotenv 
# loading variables from .env file
load_dotenv() 

# mistral api key
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")