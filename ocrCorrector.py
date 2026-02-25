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
        You will need to return the corrected document. Do not include any other text in your response.\
        Do not alter the meaning of the document. Do not add any additional information to the document. Do not remove information from the document."
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

    default_prompt = """IMPORTANT NOTICE FOR TI DESIGN INFORMATION AND RESOURCES
Texas Instruments Incorporated (TTT) technical application or other design advice, services or information, including, but not limited to,
reference designs and materials relating to technical modules, collectively, "TI Resources) are intended to assist designers who are
developing applications and materials that incorporate TI Products. By downloading, accessing or using any particular TI Resource in any way, you are
individuality or, if you are acting on behalf of a company, your company, agree to use it solely for this purpose and subject to the terms of
this.
TI provision of TI Resources is not an offer or otherwise all other applicable warranty or warranty disclaimers in TI
enhancesments, improvements and other changes to TI Resources. It is applicable analysis, evaluation and judgment and make corrections.
You understand and agree that you have any other responsibility for TI Resources, such as ITI Resources. Ti Resources. Tii Resources. Teieves the right to make corrections,
(and of all of TI Products used for or or other failures, with all applicable regulations, and other applicable failures. You
anticipate dangerous consequences or failures. (2) monitor their compliance, and their consequences, and (3) listen to the likelihood of failures. If you
will thoroughly test that such applications and the functionality of Ti Products as used as a particular TII resource.
TII Products are not applicable to all applicable requirements, and that applicable requirements. If applicable requirements are applicable, you
testing other than that specific specifications described in the published documents, and if applicable to this resource, it is not required that you
The TI Products identified in such such applications, NOT OTHER LICENSE, EXPRESS or IMPPLIED, TO STOPPLED, or OFTHERSEVE TO
The TTI Products listed in such Resources, NOOTHER LICENSE. EXPRESS OR IMPPLIED, or OPSTOPPED, are not allowed to apply for any applications that include
the TI Products that have been issued as required. The TTI products are not authorized to use this resource. This indicates that they are not included in the
RIGHT OF TI OR ANY ANY THIRTY PARTY PARTY HEREIN, BUT NOT NOT HEREIN. But not only limited to any patent right, might work right, or
regarding or referencing third-party products or services does not require a license to a third license to use any patent or other product or services, or a warranty or
endorsement thereof. Use of TII Resources. This requires a license not to comply with the patent or any intellectual property of the
TI RESOURS OR PROVIDED IT IS AND WITH ALL FAULTS. TTI DISCUSSALES ALL OTHER WARRANTIES AND OTHER WARRANTY IS NOT LIMITED TO
ACCURACY OR COMPLETES, TITLE, TITLES, TITL, AND ALL FILLED FILLURE PURPOSE, AND NON-NON-INFROMPURPOSE. AND ANY AMPLIFIED WARRANTY OR ANY PARTY INTELLECTUAL.
PROPERTY RIGHTS.
I SHALL NOT BE LIABLE FOR SHALL NOT DEFINED IF INFINITY YOU AGAINST ANY ANY ANY INCLUING BUT NOT
THIS IS NOT ABILITY FOR THIS PARTY PURPOSE. IT IS NOT INFINITIBILITY FOR ANY ANYTHING BUT NOT INTENT
DESCRIBED IN IT RESOURIES OR OTHERWEARES, IN NO EVENT SHALL IT IS LIABLE OR ANY ACTUAL, DIRECT, SPECIAL, OR
ARISING OUT OF TII RESOUREES OR USE THESE OR THESE, IN EVENT SHALL TO BE LIEBLE FOR ANY ACTIVAL, DIRECT. SPECIAL,
POSSIBBILITY OF TTI RESOLVES, INCENT SHALL TO EXEMPLY OR EXPLORATION OF THE OR
PossibilityBILITY OF SUCH DAMAGES.
This Notice applies to TI Resoures, Additional representatives against any damages, costs, and/or LIABILITIES BEEN ADVISED out of your non-
Compliance with the terms and provisions of this Notice. This Notice:
This notice applies to Ti Resources, Additional applications apply to the use of the use and purchase of certain types of materials, TI products and services, TII products and Services.
modules, and samples (http://www.com/docs/documents/samples/tampls.htm)
Mailing Address: Texas Instruments, Post Office Box 65603, Dallas, Texas 75265
Copyright @ 2018, Texas Instruments incorporated"""
    response = ocr_corrector.send_request(default_prompt)
    if response is not None:
        with open("corrected_document.txt", "w", encoding="utf-8") as file:
                file.write(response)
        responseDict = json.loads(response)
        print(responseDict["choices"][0]["message"]["content"])