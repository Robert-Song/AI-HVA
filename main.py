from ocrCorrector import GenAIStudioAPI
from documentProcessor import DocumentProcessor

def main():
    # full test
    documentProcessor = DocumentProcessor()
    result = documentProcessor.process_document("scyt129g.pdf")
    print(result)
    ocrCorrector = GenAIStudioAPI()
    response = ocrCorrector.send_request(result)
    with open("corrected_document.txt", "w", encoding="utf-8") as file:
        file.write(response)


if __name__ == "__main__":
    main()
