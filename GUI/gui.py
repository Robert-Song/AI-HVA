from tkinter import *
from tkinter import filedialog
import shutil
from pathlib import Path
from info_compress import InfoCompressor
from netlist_parser import full_process_netlist
from map_connections import map_connections
from isolate_hardware import extract_components_from_netlist
from manual_folder import ManualFolder
from combinedOCRProcessor import CombinedOCRProcessor
import json
import os

# Initializes root window
root = Tk()

# Position window at center of screen
root.update_idletasks()
x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
y = (root.winfo_screenheight() - root.winfo_reqheight()) // 2
root.geometry(f"+{x}+{y}")

ic = InfoCompressor()
cop = CombinedOCRProcessor()
mf = ManualFolder()

# Brings the window into focus
root.lift()
root.focus_force()

# Sets window title
root.title("AI-HVA")

# Make column 0 expand to fill the window width, keeping widgets centered
root.columnconfigure(0, weight=1)

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
                prsd = sp[len(sp) - 1].split(".")[0] + "-prsd.kicad_sch"
                ic.convert_whitelist_kicad(ec[1], ec[0], prsd)
                prsdfix = sp[len(sp) - 1].split(".")[0] + "-prsd.net"
                mcresult = map_connections(prsdfix)
                with open(sp[len(sp) - 1].split(".")[0] + "-connections-prsd.net", "w", encoding="utf-8") as f:
                    json.dump(mcresult, f, indent=2)
                icresult = extract_components_from_netlist(prsdfix)
                with open(sp[len(sp) - 1].split(".")[0] + "-isolate-prsd.net", "w", encoding="utf-8") as f:
                    json.dump(icresult, f, indent=2)
                full_process_netlist(prsdfix, sp[len(sp) - 1].split(".")[0] + "-final.json")
                cole = []
                for ds in needdatasheets:
                    result, error = mf.test_find_datasheet(ds[0], ds[1])
                    if error == None:
                        os.makedirs("result", exist_ok=True)
                        filename = "result/" + ds[0] + ".pdf"
                        with open(filename, "wb") as f:
                            f.write(result)
                        cole.append(filename)
                dp = CombinedOCRProcessor()
                for co in cole:
                    print(dp.process_document(co))
                        
                        

        show_screen3()


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


def show_screen4():
    for widget in root.winfo_children():
        widget.destroy()
    uploadlbl = Label(root, text="Upload a PDF file.")
    uploadlbl.grid(row=0, column=0, pady=(25, 0), padx=100)

    # Load normal and hover state images for the upload button
    normalimg = PhotoImage(file="GUI/uploadnormal.png")
    hoverimg = PhotoImage(file="GUI/uploadhover.png")
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
    filebtn.bind("<Button-1>", lambda e: import_pdf())

def import_pdf():
    file_path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[("PDF Files", ["*.pdf"])]
    )
    # Keep root window in focus after dialog closes
    root.lift()
    root.focus_force()
    contbtn = Button(root, text="Begin OCR", command=lambda: cop.process_document(file_path))
    contbtn.grid(row=3, column=0, pady=(0, 35))

def show_screen3():
    global dirbtn, dirlbl
    # Remove all screen 1 widgets
    for widget in root.winfo_children():
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
        exportbtn = Button(root, text="Continue", command=show_screen4)
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
        errorlbl.destroy()
        # Warn about any corrupted or unrecognized files
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