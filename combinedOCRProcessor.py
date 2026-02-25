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
        #'scyt129g',
        'FDN537N-D',
        'sip32431',
    ]
    os.makedirs("initialOCR", exist_ok=True)
    os.makedirs("correctedOCR", exist_ok=True)
    for documentName in documentNames:
        ocrResult = ocrCorrector.send_request(documentProcessor.process_document(f"{documentName}.pdf"))
        with open(f"initialOCR/{documentName}.txt", "w", encoding="utf-8") as file:
            file.write(ocrResult)
        correctedOCR = ocrCorrector.send_request(ocrResult)
        with open(f"correctedOCR/{documentName}.txt", "w", encoding="utf-8") as file:
            file.write(correctedOCR)
        print(f"Processed {documentName}")