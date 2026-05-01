import os
import requests
from src.ingestion.netlist_loader import load_netlist

def download_datasheets():
    netlist = load_netlist('netlist/rffe.net')
    components = netlist.get('components', {})

    output_dir = 'pdf_datasheets'
    os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    fail_count = 0

    for cid, comp in components.items():
        url = comp.get('datasheet_url')
        if url and url != '~' and url.strip():
            filepath = os.path.join(output_dir, f"{cid}.pdf")
            if os.path.exists(filepath):
                print(f"Skipping {cid}, already downloaded.")
                continue

            print(f"Downloading {cid} from {url}...")
            try:
                # Add a generic User-Agent header to prevent 403 blocks
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                success_count += 1
            except Exception as e:
                print(f"Failed to download {cid} from {url}: {e}")
                fail_count += 1

    print(f"\nFinished downloading.")
    print(f"Successfully downloaded: {success_count}")
    print(f"Failed to download: {fail_count}")

if __name__ == '__main__':
    download_datasheets()
