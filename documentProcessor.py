import pdf2image
from transformers import AutoProcessor, AutoModelForCausalLM, Qwen2VLForConditionalGeneration,  BlipForConditionalGeneration, BlipProcessor
from PIL import Image
import torch
from dotenv import load_dotenv
import os
import requests


import logging

logger = logging.getLogger(__name__)


class DocumentProcessor:
    device = None
    torch_dtype = None
    model = None
    prompt = None
    processor = None
    def __init__(self):
        self.initialize_OCR()
    
    def initialize_OCR(self):
        print("Initializing OCR")
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        #self.model = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-base", torch_dtype=self.torch_dtype, trust_remote_code=True, attn_implementation="eager").to(self.device)
        #self.processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base", trust_remote_code=True)
        
        self.model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            torch_dtype=self.torch_dtype,
            trust_remote_code=True
        ).to(self.device)

        self.processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            trust_remote_code=True
        )
        self.prompt = "<OCR>"
        print("OCR initialized")

    def __process_image(self, image: Image.Image):
        logger.info("Processing image")
        inputs = self.processor(text=self.prompt, images=image, return_tensors="pt").to(self.device, self.torch_dtype)
        logger.info("Inputs created")
        generated_ids = self.model.generate(
            #input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            #max_new_tokens=4096,
            max_new_tokens=1024,
            num_beams=3,
            #do_sample=False
        )
        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        #parsed_answer = self.processor.post_process_generation(generated_text, task="<OCR>", image_size=(image.width, image.height))

        #p_a = parsed_answer['<OCR>']
        p_a = generated_text
        logger.info("Parsed answer")
        return p_a
    
    def process_document(self, document: str):
        docImageList = pdf2image.convert_from_path(document)
        result = ""
        for image in docImageList:
            result += self.__process_image(image) + "\n"
            logger.info("Processed image")
        return result

if __name__ == "__main__":
    load_dotenv()
    documentProcessor = DocumentProcessor()
    result = documentProcessor.process_document("CS373_HW2_Spring2026.pdf")
    print(result)