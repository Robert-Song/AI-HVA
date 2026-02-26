import json
import os

from ocrCorrector import GenAIStudioAPI
from documentProcessor import DocumentProcessor

class CombinedOCRProcessor:
    def __init__(self):
        self.ocrCorrector = GenAIStudioAPI()
        self.documentProcessor = DocumentProcessor()

    def process_document(self, document: str):
        result = self.documentProcessor.process_document(document)
        response = self.ocrCorrector.send_request(result)
        return response


if __name__ == "__main__":
    ocrCorrector = GenAIStudioAPI()
    documentProcessor = DocumentProcessor()
    documentNames = [
        'scyt129g',
        'FDN537N-D',
        'sip32431',
    ]
    os.makedirs("initialOCR", exist_ok=True)
    os.makedirs("correctedOCR", exist_ok=True)
    for documentName in documentNames:
        initial_path = f"initialOCR/{documentName}.txt"
        if not os.path.exists(initial_path):
            ocrResult = documentProcessor.process_document(f"{documentName}.pdf")
            with open(initial_path, "w", encoding="utf-8") as file:
                file.write(ocrResult)
        else:
            with open(initial_path, "r", encoding="utf-8") as file:
                ocrResult = file.read()
        correctedOCR = ""
        if not os.path.exists(f"correctedOCR/{documentName}.txt"):
            for i in range(10):
                chunk = ocrResult[i*int(len(ocrResult) / 10):(i+1)*int(len(ocrResult) / 10)]
                try:
                    correctedOCR += json.loads(ocrCorrector.send_request(chunk))["choices"][0]["message"]["content"]
                except:
                    print(f"Error with: {documentName}")
                    break
            with open(f"correctedOCR/{documentName}.txt", "w", encoding="utf-8") as file:
                file.write(correctedOCR)
        print(f"Processed {documentName}")