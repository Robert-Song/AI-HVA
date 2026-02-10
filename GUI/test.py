from tkinter import *
from PIL import Image, ImageTk

root = Tk()
root.title("AI-HVA")
#root.geometry('350x200')
lbl = Label(root, text = "Upload a KiCad schematic file.")
lbl.grid(row = 0, column = 0, pady=(25, 0), padx=100)
image = Image.open("uploadnormal.png")
resized = image.resize((150, 150))
normalimg = ImageTk.PhotoImage(resized)
image = Image.open("uploadhover.png")



def clicked() :
    lbl.configure(text = "I just got clicked")

NORMAL_BG = "#9b9b9b"
HOVER_BG  = "#6c6c6c"

btn = Label(
    root,
    image=normalimg,
    padx=70,
    pady=70,
    cursor="hand2"
)

btn.image = normalimg
btn.grid(row=1, column=0, pady=50)

btn.bind("<Enter>", lambda e: btn.config(image=hoverimg))
btn.bind("<Leave>", lambda e: btn.config(image=normalimg))




root.mainloop()