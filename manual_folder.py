import os
from dotenv import load_dotenv, set_key


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

mf = ManualFolder()
error = mf.set_manual_folder_path("Test")
if error:
    print(error)
print(f"Current manual folder: {mf.get_manual_folder_path()}")