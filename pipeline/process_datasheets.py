import os
import requests
import pdfplumber
from src.ingestion.netlist_loader import load_netlist

def process_datasheets():
    netlist = load_netlist('netlist/rffe.net')
    components = netlist.get('components', {})

    pdf_dir = 'pdf_datasheets'
    txt_dir = 'datasheets'
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(txt_dir, exist_ok=True)

    failed_components = []
    success_count = 0

    print("Starting datasheet processing (Download + OCR)...")

    for cid, comp in components.items():
        url = comp.get('datasheet_url')
        if not url or url == '~' or not url.strip():
            continue

        txt_path = os.path.join(txt_dir, f"{cid}.txt")
        if os.path.exists(txt_path):
            print(f"Skipping {cid}, text already extracted.")
            continue

        pdf_path = os.path.join(pdf_dir, f"{cid}.pdf")
        
        # Step 1: Download if not already downloaded
        if not os.path.exists(pdf_path):
            print(f"Downloading {cid}...")
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)
            except Exception as e:
                print(f"  -> Failed to download {cid}: {e}")
                failed_components.append((cid, url, "Download failed"))
                continue

        # Step 2: Validate PDF header
        try:
            with open(pdf_path, 'rb') as f:
                header = f.read(5)
                if not header.startswith(b'%PDF-'):
                    print(f"  -> {cid}.pdf is not a valid PDF (likely HTML). Deleting...")
                    os.remove(pdf_path)
                    failed_components.append((cid, url, "Downloaded file was not a valid PDF"))
                    continue
        except Exception as e:
            print(f"  -> Failed to validate {cid}.pdf: {e}")
            failed_components.append((cid, url, "File access error"))
            continue

        # Step 3: Run OCR / Text Extraction
        print(f"Extracting text from {cid}...")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(full_text))
            success_count += 1
            print(f"  -> Successfully saved {cid}.txt")
        except Exception as e:
            print(f"  -> Error extracting text from {cid}: {e}")
            failed_components.append((cid, url, f"OCR Error: {str(e)}"))

    # Output manual download list
    if failed_components:
        with open('manual_download_required.txt', 'w', encoding='utf-8') as f:
            f.write("The following components need their datasheets downloaded manually.\n")
            f.write("Place the valid PDFs into the 'pdf_datasheets' folder, then re-run this script.\n")
            f.write("=" * 80 + "\n\n")
            for cid, url, reason in failed_components:
                f.write(f"Component: {cid}\nReason: {reason}\nURL: {url}\n\n")
        
        print(f"\nFinished. Successfully processed: {success_count}.")
        print(f"Failed to process {len(failed_components)} components.")
        print("Please check 'manual_download_required.txt' for instructions.")
    else:
        print(f"\nFinished! All datasheets successfully downloaded and extracted.")

if __name__ == '__main__':
    process_datasheets()
