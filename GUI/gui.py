import sys
import os
import threading
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tkinter import *
from tkinter import filedialog, ttk
import shutil
from pathlib import Path
from info_compress import InfoCompressor
import logging
from combinedOCRProcessor import CombinedOCRProcessor
from netlist_parser import full_process_netlist
from map_connections import map_connections
from isolate_hardware import extract_components_from_netlist
from manual_folder import ManualFolder
from combinedOCRProcessor import CombinedOCRProcessor
import json
import subprocess
from llm_reason import check_reasoning, infer_components_and_relations

logging.basicConfig(format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

ic = InfoCompressor()
cop = CombinedOCRProcessor()
mf = ManualFolder()

# Initializes root window
root = Tk()

# Position window at center of screen
root.update_idletasks()
x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
y = (root.winfo_screenheight() - root.winfo_reqheight()) // 2
root.geometry(f"+{x}+{y}")

# Brings the window into focus
root.lift()
root.focus_force()

# Sets window title
root.title("AI-HVA")

# Make column 0 expand to fill the window width, keeping widgets centered
root.columnconfigure(0, weight=1)

canvas = Canvas(root)
#canvas.pack(side=LEFT, fill=BOTH, expand=True)

scrollbar = Scrollbar(root, orient=VERTICAL, command=canvas.yview)
#scrollbar.pack(side=RIGHT, fill=Y)

canvas.configure(yscrollcommand=scrollbar.set)
scrollable_frame = Frame(canvas)

# Screen 1: label prompting the user to upload a file
uploadlbl = Label(root, text="Upload a KiCad schematic or netlist file.")
uploadlbl.grid(row=0, column=0, pady=(25, 0), padx=100)

# Load normal and hover state images for the upload button
normalimg = PhotoImage(file="GUI/uploadnormal.png")
hoverimg = PhotoImage(file="GUI/uploadhover.png")

# Tracks which file is currently being shown on screen 2
file_index = 0
essential_components = []
comp_num = 0
checkbox_states = []  # BooleanVars for the current screen's checkboxes

def store_list(index=0, complist=[]):
    checked = [comp[0] for comp, state in zip(complist, checkbox_states) if state.get()]
    needdatasheets = [(comp[0], comp[2]) for comp, state in zip(complist, checkbox_states) if state.get()]
    unchecked = [comp[0] for comp, state in zip(complist, checkbox_states) if not state.get()]
    essential_components.append([checked, file_paths[index]])
    #essential_components.append([unchecked, file_paths[index]])
    if index + 1 < len(file_paths):
        show_screen2(index+1)
    else:
        print(essential_components)
        for ec in essential_components:
            print(ec[1])
            sp = ec[1].split("/")
            if Path(ec[1]).suffix == ".kicad_sch":
                prsd = "prsd.kicad_sch"
                ic.convert_whitelist_kicad(ec[1], ec[0], prsd)
                prsdfix = "prsd.net"
                mcresult = map_connections(prsdfix)
                with open("connections-prsd.net", "w", encoding="utf-8") as f:
                    json.dump(mcresult, f, indent=2)
                icresult = extract_components_from_netlist(prsdfix)
                with open("isolate-prsd.net", "w", encoding="utf-8") as f:
                    json.dump(icresult, f, indent=2)
                full_process_netlist(prsdfix, sp[len(sp) - 1].split(".")[0] + "-final.json")
                cole = []
                for ds in needdatasheets:
                    result, error = mf.test_find_datasheet(ds[0], ds[1])
                    if error == None:
                        filename = "result/" + ds[0] + ".pdf"
                        with open(filename, "wb") as f:
                            f.write(result)
                        cole.append(filename)
        show_screen_debug()

# Screen 2: shows components for one file at a time, advancing on each continue click
def show_screen2(index=0):

    global file_index, essential_components, comp_num, checkbox_states
    file_index = index

    fp = file_paths[index]
    for widget in root.winfo_children():
        widget.destroy()

    if Path(fp).suffix == ".kicad_sch":
        complist = ic.essential_list_kicad(fp)
    elif Path(fp).suffix == ".net":
        complist = ic.essential_list_netlist(fp)
    comp_num = len(complist)

    # Each checkbox gets its own BooleanVar so they toggle independently
    checkbox_states = [BooleanVar() for _ in complist]
    for i, (comp, state) in enumerate(zip(complist, checkbox_states)):
        checkbox = Checkbutton(root, text=f"{comp[0]}: {comp[1]}", variable=state)
        checkbox.grid(column=0, row=i)

    # Select/deselect all toggle
    def toggle_all():
        all_selected = all(s.get() for s in checkbox_states)
        for s in checkbox_states:
            s.set(not all_selected)

    toggle_btn = Button(root, text="Select All / Deselect All", command=toggle_all)
    toggle_btn.grid(column=0, row=comp_num, pady=(10, 0))

    # If there are more files, continue loads the next one; otherwise advance to screen 3

    contbtn = Button(root, text="Continue", command=lambda: store_list(index, complist))
    contbtn.grid(row=len(complist) + 2, column=0, pady=(0, 35))


_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

def _load_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_config(data):
    cfg = _load_config()
    cfg.update(data)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(cfg, f)

debug_enabled = BooleanVar()
debug_enabled.set(_load_config().get("debug_enabled", False))


class DebugWindow(logging.Handler):
    def __init__(self):
        super().__init__()
        self.win = Toplevel(root)
        self.win.title("Debug Output")
        self.win.geometry("600x400")

        self.text = Text(self.win, state="disabled", bg="black", fg="lime",
                         font=("Courier", 11), wrap="word")
        scrollbar = Scrollbar(self.win, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=RIGHT, fill=Y)
        self.text.pack(fill=BOTH, expand=True)
        self.win.lift()

    def emit(self, record):
        msg = self.format(record) + "\n"
        self.text.configure(state="normal")
        self.text.insert(END, msg)
        self.text.configure(state="disabled")
        self.text.see(END)


def _apply_debug():
    if debug_enabled.get():
        handler = DebugWindow()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)


def show_screen_debug():
    for widget in root.winfo_children():
        widget.destroy()
    Label(root, text="Debug Options").grid(row=0, column=0, pady=(25, 0), padx=100)
    Checkbutton(root, text="Enable debug output", variable=debug_enabled).grid(row=1, column=0, pady=(10, 0))
    Button(root, text="Continue", command=lambda: [
        _save_config({"debug_enabled": debug_enabled.get()}),
        _apply_debug(),
        show_screen3()
    ]).grid(row=2, column=0, pady=(10, 35))


def show_screen4():
    for widget in root.winfo_children():
        if not isinstance(widget, Toplevel):
            widget.destroy()
    uploadlbl = Label(root, text="Upload a PDF file.")
    uploadlbl.grid(row=0, column=0, pady=(25, 0), padx=100)

    filebtn = Label(
        root,
        image=normalimg,
        padx=70,
        pady=70,
        cursor="hand2",
    )

    # Keep a reference to prevent garbage collection
    filebtn.image = normalimg
    filebtn.grid(row=1, column=0, pady=25)

    # Swap image on hover and trigger import on click
    filebtn.bind("<Enter>", lambda e: filebtn.config(image=hoverimg))
    filebtn.bind("<Leave>", lambda e: filebtn.config(image=normalimg))
    
    #filebtn.bind("<Button-1>", lambda e: import_pdf())


_ocr_stopped = False
_progress_bar = None


def set_progress(value):
    """Update the progress bar on screen 5. value should be 0-100.
    Can be called from other modules: import GUI.gui as gui; gui.set_progress(50)
    """
    if _progress_bar is not None:
        _progress_bar['value'] = value


def import_pdf():
    file_path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[("PDF Files", ["*.pdf"])]
    )
    # Keep root window in focus after dialog closes
    root.lift()
    root.focus_force()
    contbtn = Button(root, text="Begin OCR", command=lambda: start_ocr(file_path))
    contbtn.grid(row=3, column=0, pady=(0, 35))


def start_ocr(file_path):
    global _ocr_stopped
    _ocr_stopped = False
    show_screen5()

    def run():
        result = cop.process_document(file_path)
        if not _ocr_stopped:
            root.after(0, lambda: on_ocr_complete(result))

    threading.Thread(target=run, daemon=True).start()


def on_ocr_complete(result):
    # TODO: handle OCR result and advance to next screen
    pass


def stop_ocr():
    global _ocr_stopped
    _ocr_stopped = True
    show_screen4()


def show_screen5():
    global _progress_bar
    for widget in root.winfo_children():
        if not isinstance(widget, Toplevel):
            widget.destroy()
    Label(root, text="Processing...").grid(row=0, column=0, pady=(25, 0), padx=100)
    _progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate", maximum=100)
    _progress_bar.grid(row=1, column=0, pady=(10, 0), padx=40)
    Button(root, text="Stop Processing", fg="red", command=stop_ocr).grid(row=2, column=0, pady=(10, 35))

def show_screen6():
    global _progress_bar
    for widget in root.winfo_children():
        if not isinstance(widget, Toplevel):
            widget.destroy()
    Label(root, text="Processing...").grid(row=0, column=0, pady=(25, 0), padx=100)
    _progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate", maximum=100)
    _progress_bar.grid(row=1, column=0, pady=(10, 0), padx=40)
    Button(root, text="Stop Processing", fg="red", command=stop_ocr).grid(row=2, column=0, pady=(10, 35))
    infer_components_and_relations()
    os.chdir("pipeline")
    subprocess.run("python -m src.main -n ../prsd.net -s \"Run\" -p", shell=True, check=True)


def show_screen3():
    global dirbtn, dirlbl
    for widget in root.winfo_children():
        if not isinstance(widget, Toplevel):
            widget.destroy()
    # Prompt label
    exportlabel = Label(root, text="Choose a destination folder to export the output.")
    exportlabel.grid(row=0, column=0, pady=(25, 0), padx=50)
    # Button to open directory picker
    dirbtn = Button(root, text="Choose Directory", command=directory_select)
    dirbtn.grid(row=1, column=0, pady=(0,35))
    # Placeholder label updated once a directory is chosen
    dirlbl = Label(root, text="")


# Opens a directory picker and displays the chosen path
def directory_select():
    global dirlbl, dirbtn
    directory = filedialog.askdirectory(title="Select a destination folder")
    # Keep root window in focus after dialog closes
    root.lift()
    root.focus_force()
    if directory:
        # Hide the choose directory button temporarily
        dirbtn.grid_remove()
        # Update and show the selected directory label
        dirlbl.config(text="Export folder: " + directory)
        dirlbl.grid(row=2, column=0, pady=(0, 35))
        # Re-show choose directory button below the label so user can reselect
        dirbtn.grid(row=3, column=0, pady=0)
        # Export button to confirm and proceed
        exportbtn = Button(root, text="Continue", command=show_screen6)
        exportbtn.grid(row=4, column=0, pady=(0,35))


# Expected file headers for each supported KiCad format
FILE_HEADERS = {
    ".kicad_sch": "(kicad_sch",
    ".net": "(export",
}
filelbl = None
errorlbl = None
contbtn = None
# Returns True if the file is non-empty and starts with the expected header
def validate_file(fp):
    suffix = Path(fp).suffix.lower()
    expected = FILE_HEADERS.get(suffix)
    if not expected:
        return False
    try:
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read(len(expected))
        if content != expected:
            return False
        else:
            worked, content = ic.check_duplicate_file(fp, content)
            return worked
    except (OSError, UnicodeDecodeError):
        return False


# Opens a file picker for KiCad netlists/schematics and copies them to the project root
def import_file():
    global file_paths
    global filelbl
    global errorlbl
    global contbtn
    global allvalid
    file_paths = filedialog.askopenfilenames(
        title="Select a file",
        filetypes=[("KiCad Netlists/Schematics", ["*.net", "*.kicad_sch"])]
    )
    # Keep root window in focus after dialog closes
    root.lift()
    root.focus_force()
    if file_paths:
        # Split files into valid and invalid
        valid = []
        invalid = []
        for fp in file_paths:
            if validate_file(fp):
                valid.append(fp)
            else:
                invalid.append(fp)
        allvalid = True
        errorlbl.destroy()        # Warn about any corrupted or unrecognized files
        if invalid:
            invalid_names = ", ".join(Path(fp).name for fp in invalid)
            errorlbl = Label(root, text="Invalid or corrupted files: " + invalid_names, fg="red")
            errorlbl.grid(row=2, column=0, pady=(0, 35))
            allvalid = False
        if not valid:
            filelbl.destroy()
            allvalid = False
            contbtn.destroy()
            return
        # Display the names of all valid selected files
        names = ", ".join(Path(fp).name for fp in valid)
        filelbl.destroy()
        if allvalid:
            errorlbl.destroy()
            filelbl = Label(root, text="Uploaded files: " + names)
            filelbl.grid(row=2, column=0)
        # Copy each valid file to the project root directory
        for fp in valid:
            shutil.copy2(fp, "..")
        # Show continue button to advance to screen 2
        if allvalid:
            contbtn = Button(root, text="Continue", command=show_screen2)
            contbtn.grid(row=3, column=0, pady=(0, 35))
        else:
            contbtn.destroy()


# Persistent screen 1 status labels (created once, updated on each import attempt)
errorlbl = Label(root, text="", fg="red")
errorlbl.grid(row=2, column=0)
filelbl = Label(root, text="")
filelbl.grid(row=2, column=0)
contbtn = Button(root, text="Continue", command=show_screen2)



# Screen 1: upload button using a label widget for custom image styling
filebtn = Label(
    root,
    image=normalimg,
    padx=70,
    pady=70,
    cursor="hand2",
)

# Keep a reference to prevent garbage collection
filebtn.image = normalimg
filebtn.grid(row=1, column=0, pady=25)

# Swap image on hover and trigger import on click
filebtn.bind("<Enter>", lambda e: filebtn.config(image=hoverimg))
filebtn.bind("<Leave>", lambda e: filebtn.config(image=normalimg))
filebtn.bind("<Button-1>", lambda e: import_file())

root.mainloop()