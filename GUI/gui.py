from tkinter import *
from PIL import Image, ImageTk
from tkinter import filedialog
import shutil
# Initializes root window
root = Tk()

# Brings the window into focus
root.lift()
root.focus_force()

# Sets window title
root.title("AI-HVA")

# Create and place a label for upload info
lbl = Label(root, text = "Upload a KiCad schematic file.")
lbl.grid(row = 0, column = 0, pady=(25, 0), padx=100)

# Import both images for button (hover and normal)
normalimg = PhotoImage(file="uploadnormal.png")
hoverimg = PhotoImage(file="uploadhover.png")

# Define import file logic
def import_file():
    # Opens file window and ensures root window remains in focus on file dialog close
    file_path = filedialog.askopenfilename(title="Select a file", filetypes=[("KiCad Netlists/Schematics", ["*.net", ".kicad_sch"])])
    root.lift()
    root.focus_force()
    # Prints file path for now
    if file_path:
        # Process the selected file (you can replace this with your own logic)
        print("Selected file:", file_path)

# Create file import button
filebtn = Label(
    root,
    image=normalimg,
    padx=70,
    pady=70,
    cursor="hand2",
)

filebtn.image = normalimg
filebtn.grid(row=1, column=0, pady=25)

filebtn.bind("<Enter>", lambda e: filebtn.config(image=hoverimg))
filebtn.bind("<Leave>", lambda e: filebtn.config(image=normalimg))
filebtn.bind("<Button-1>", lambda e: import_file())

root.mainloop()