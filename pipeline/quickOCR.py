import pdfplumber
import os

# Define directories
source_dir = "pdf_datasheets/"
output_dir = "datasheets/"

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Process each file
for filename in os.listdir(source_dir):
    if filename.endswith(".pdf"):
        pdf_path = os.path.join(source_dir, filename)
        # Change extension for the output file
        txt_filename = os.path.splitext(filename)[0] + ".txt"
        txt_path = os.path.join(output_dir, txt_filename)
        
        print(f"Processing: {filename}...")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = []
                for page in pdf.pages:
                    # extract_text() returns the text found on the page
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                
                # Join all pages and save to file
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(full_text))
                    
            print(f"Successfully saved to: {txt_path}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

print("Done!")