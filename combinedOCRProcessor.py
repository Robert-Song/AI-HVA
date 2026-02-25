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