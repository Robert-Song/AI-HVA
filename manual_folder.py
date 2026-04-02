import os
from dotenv import load_dotenv, set_key
import requests

class ManualFolder:
    def __init__(self):
        load_dotenv("config.env")

    def set_manual_folder_path(self, directorypath):
        error = None
        if not os.path.exists(directorypath):
            error = f"Error updating manual folder: {directorypath} doesn't exist"
            return error
        if not os.path.isdir(directorypath):
            error = f"Error updating manual folder: {directorypath} isn't a directory"
            return error
        if not os.access(directorypath, os.R_OK):
            error = f"Error updating manual folder: {directorypath} is not readable"
            return error
        os.environ["AIHVA_MAN"] = directorypath
        set_key("config.env", "AIHVA_MAN", directorypath)
        return error
    
    def get_manual_folder_path(self):
        return os.environ.get("AIHVA_MAN")
    
    def get_fallback(self, partname):
        filename = os.path.join(self.get_manual_folder_path(), partname) + ".pdf"
        result = None
        error = None
        if not os.path.exists(filename):
            error = f"Fallback file not found in {filename}"
            return result, error
        with open(filename, "rb") as file:
            result = file.read()
        return result, error
    
    def test_find_datasheets(self, partnames, urls):
        '''
        74AHC1G04: Single NOT Gate, Low-Voltage CMOS (http://www.ti.com/lit/sg/scyt129e/scyt129e.pdf)
        74LVC1G332: Single OR 3-Input Gate, Low-Voltage CMOS (http://www.ti.com/lit/sg/scyt129e/scyt129e.pdf)
        SiP32431DR3: 10 pA, Ultra Low Leakage and Quiescent Current, Load Switch with Reverse Blocking, High Enable, SC-70-6 (http://www.vishay.com.hk/docs/66597/sip32431.pdf)
        FDN537N: 6.5A Id, 30V Vds,  Single N-Channel Power Trench MOSFET , 23mOhm Ron, -55 to 150 Â°C (https://www.onsemi.com/pub/Collateral/FDN537N-D.pdf) 
        '''
        for i in range(min(len(partnames), len(urls))):
            result, error = self.test_find_datasheet(partnames[i], urls[i])
            if error:
                print(f"Error: {error}")
            else:
                print(result[:100])

    def test_find_datasheet(self, partname, url):
        result = None
        error = None
        response = None
        try:
            response = requests.get(url)
        except:
            pass
        if response is None or response.status_code != 200:
            if response:
                print(f"URL request failed for {partname} at {url}: {response.status_code} {response.reason}")
            else:
                print(f"URL request failed for {partname} at {url} for unknown reasons")
            fresult, ferror = self.get_fallback(partname)
            if ferror:
                print(ferror)
                error = f"URL and fallback failed"
                return result, error
            else:
                print("Fallback file successful")
                return fresult, error
        result = response.content
        return result, error


#Test case for US#14
'''
mf = ManualFolder()
print("Valid folder set:")
error = mf.set_manual_folder_path("test/manual_folder")
if error:
    print(error)
print(f"Current manual folder: {mf.get_manual_folder_path()}")
print("Invalid folder set:")
error = mf.set_manual_folder_path("test/manual_folder/dne.exe")
if error:
    print(error)
print(f"Current manual folder: {mf.get_manual_folder_path()}")
'''

#Test case for US#15
'''
mf = ManualFolder()
error = mf.set_manual_folder_path("test/manual_folder")
if error:
    print(error)
mf.test_find_datasheets(["74AHC1G04", "74LVC1G332", "SiP32431DR3", "FDN537N"],
                        ["http://www.ti.com/lit/sg/scyt129e/scyt129e.pdf", "http://www.ti.com/lit/sg/scyt129e/scyt129e.pdf", "http://www.vishay.com.hk/docs/66597/sip32431.pdf", "https://www.onsemi.com/pub/Collateral/FDN537N-D.pdf"])
'''