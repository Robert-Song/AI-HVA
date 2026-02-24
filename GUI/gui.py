from tkinter import *
from PIL import Image, ImageTk
from tkinter import filedialog
import shutil
from pathlib import Path

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

# Screen 1: label prompting the user to upload a file
uploadlbl = Label(root, text="Upload a KiCad schematic or netlist file.")
uploadlbl.grid(row=0, column=0, pady=(25, 0), padx=100)

# Load normal and hover state images for the upload button
normalimg = PhotoImage(file="uploadnormal.png")
hoverimg = PhotoImage(file="uploadhover.png")



# Screen 2: clears all widgets and shows the export directory selection UI
def show_screen2():
    global dirbtn, dirlbl
    # Remove all screen 1 widgets
    for widget in root.winfo_children():
        widget.destroy()
    # Prompt label
    exportlabel = Label(root, text="Choose a destination folder to export the output.")
    exportlabel.grid(row=0, column=0, pady=(25, 0), padx=100)
    # Button to open directory picker
    dirbtn = Button(root, text="Choose Directory", command=directory_select)
    dirbtn.grid(row=1, column=0, pady=25)
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
        dirbtn.grid(row=3, column=0)
        # Export button to confirm and proceed
        exportbtn = Button(root, text="Export")
        exportbtn.grid(row=4, column=0)


# Expected file headers for each supported KiCad format
FILE_HEADERS = {
    ".kicad_sch": "(kicad_sch",
    ".net": "(export",
}

# Returns True if the file is non-empty and starts with the expected header
def validate_file(fp):
    suffix = Path(fp).suffix.lower()
    expected = FILE_HEADERS.get(suffix)
    if not expected:
        return False
    try:
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read(len(expected))
        return content == expected
    except (OSError, UnicodeDecodeError):
        return False


# Opens a file picker for KiCad netlists/schematics and copies them to the project root
def import_file():
    file_paths = filedialog.askopenfilenames(
        title="Select a file",
        filetypes=[("KiCad Netlists/Schematics", ["*.net", "*.kicad_sch"])]
    )
    # Keep root window in focus after dialog closes
    root.lift()
    root.focus_force()
    if file_paths:
        # Split files into valid and invalid
        valid = [fp for fp in file_paths if validate_file(fp)]
        invalid = [fp for fp in file_paths if not validate_file(fp)]
        # Warn about any corrupted or unrecognized files
        if invalid:
            invalid_names = ", ".join(Path(fp).name for fp in invalid)
            errorlbl = Label(root, text="Invalid or corrupted files: " + invalid_names, fg="red")
            errorlbl.grid(row=2, column=0)
        if not valid:
            return
        # Display the names of all valid selected files
        names = ", ".join(Path(fp).name for fp in valid)
        filelbl = Label(root, text="Uploaded files: " + names)
        filelbl.grid(row=2, column=0)
        # Copy each valid file to the project root directory
        for fp in valid:
            shutil.copy2(fp, "..")
        # Show continue button to advance to screen 2
        contbtn = Button(root, text="Continue", command=show_screen2)
        contbtn.grid(row=3, column=0, pady=(0, 35))

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