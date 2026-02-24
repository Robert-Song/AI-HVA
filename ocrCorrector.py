import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

class GenAIStudioAPI:
    url = None
    headers = None
    prompt = None
    def __init__(self):
        self.url = "https://genai.rcac.purdue.edu/api/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {os.getenv('GENAI_STUDIO_API_KEY')}",
            "Content-Type": "application/json"
        }
        self.prompt = "You are a helpful assistant that corrects OCR errors in a document.\
        You will be given a document and you will need to correct the OCR errors in the document.\
             You will need to return the corrected document."
    def send_request(self, message: str):
        body = {
            "model": "llama4:latest",
            "messages": [
            {
                "role": "user",
                "content": self.prompt + "\n" + message
            }
            ],
            "stream": False
        }
        response = requests.post(self.url, headers=self.headers, json=body)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Error: {response.status_code}, {response.text}")
            return None


if __name__ == "__main__":
    ocr_corrector = GenAIStudioAPI()
    default_prompt = "The quick brown fox jumps over the lazy dog."
    response = ocr_corrector.send_request(default_prompt)
    if response is not None:
        with open("corrected_document.txt", "w", encoding="utf-8") as file:
                file.write(response)
        responseDict = json.loads(response)
        print(responseDict["choices"][0]["message"]["content"])