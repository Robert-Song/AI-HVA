import sys
import os
import threading
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
from tkinter import *
from tkinter import filedialog, ttk
import shutil
from pathlib import Path
from info_compress import InfoCompressor
import logging
from netlist_parser import full_process_netlist
from map_connections import map_connections
from isolate_hardware import extract_components_from_netlist, extract_components_from_netlist_with_whitelist
from manual_folder import ManualFolder
from combinedOCRProcessor import CombinedOCRProcessor
import json
import subprocess
from llm_reason import check_reasoning, infer_components_and_relations
from netlist_filter import filter_netlist_full

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
normalimg = PhotoImage(file="uploadnormal.png")
hoverimg = PhotoImage(file="uploadhover.png")

selected_size = StringVar(value='L')

# Tracks which file is currently being shown on screen 2
file_index = 0
essential_components = []
comp_num = 0
checkbox_states = []  # BooleanVars for the current screen's checkboxes
# Expected file headers for each supported KiCad format
FILE_HEADERS = {
    ".kicad_sch": "(kicad_sch",
    ".net": "(export",
}
filelbl = None
errorlbl = None
contbtn = None

def show_screen1():
    # Persistent screen 1 status labels (created once, updated on each import attempt)
    global errorlbl
    global filelbl
    global contbtn
    errorlbl = Label(root, text="", fg="red")
    errorlbl.grid(row=2, column=0)
    filelbl = Label(root, text="")
    filelbl.grid(row=2, column=0)
    contbtn = Button(root, text="Continue", command=show_pre_screen2)

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
        # Copy each valid file to the project root directory
        for fp in valid:
            shutil.copy2(fp, "..")
        if allvalid:
            errorlbl.destroy()
            filelbl = Label(root, text="Uploaded files: " + names)
            filelbl.grid(row=2, column=0)
            contbtn = Button(root, text="Continue", command=show_pre_screen2)
            contbtn.grid(row=3, column=0, pady=(0, 35))
        else:
            contbtn.destroy()

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
            # Removed due to issues with reselection
            #worked, content = ic.check_duplicate_file(fp, content)
            return True
    except (OSError, UnicodeDecodeError):
        return False

def store_list(index=0, complist=[]):
    checked = [comp[0] for comp, state in zip(complist, checkbox_states) if state.get()]
    needdatasheets = [(comp[0], comp[2]) for comp, state in zip(complist, checkbox_states) if state.get()]
    essential_components.append([checked, file_paths[index]])
    if index + 1 < len(file_paths):
        show_screen2(index+1)
    else:
        for ec in essential_components:
            stem = Path(ec[1]).stem
            suffix = Path(ec[1]).suffix
            if suffix == ".kicad_sch":
                prsd = "prsd.kicad_sch"
                ic.convert_whitelist_kicad(ec[1], ec[0], prsd)
                prsdfix = "prsd.net"
                mcresult = map_connections(prsdfix)
                with open("connections-prsd.net", "w", encoding="utf-8") as f:
                    json.dump(mcresult, f, indent=2)
                icresult = extract_components_from_netlist(prsdfix)
                with open("isolate-prsd.net", "w", encoding="utf-8") as f:
                    json.dump(icresult, f, indent=2)
                full_process_netlist(prsdfix, stem + "-final.json")
                filter_netlist_full("result.net", ec[0], "filtered.net")
                cole = []
                for ds in needdatasheets:
                    result, error = mf.test_find_datasheet(ds[0], ds[1])
                    if error == None:
                        os.makedirs("../result", exist_ok=True)
                        filename = "../result/" + ds[0] + ".pdf"
                        with open(filename, "wb") as f:
                            f.write(result)
                        cole.append(filename)
        show_screen_debug()

def show_pre_screen2(index=0):

    global file_index, essential_components, comp_num, checkbox_states, selected_size
    file_index = index

    fp = file_paths[index]
    for widget in root.winfo_children():
        widget.destroy()


    sizes = (('Low-Level (all parts)', 'L'),
            ('Mid-Level (basic components removed)', 'M'),
            ('High-Level (only components with datasheets used)', 'H'))

    # label
    label = ttk.Label(text="Choose an abstraction level")
    label.grid(row=0, column=0, pady=(25, 0), padx=100)

    selected_size.set('L')

    # radio buttons
    i = 1
    for size in sizes:
        r = ttk.Radiobutton(
            root,
            text=size[0],
            value=size[1],
            variable=selected_size
        )
        r.grid(column=0, row=i)
        i += 1
        #r.pack(fill='x', padx=5, pady=5)

    # If there are more files, continue loads the next one; otherwise advance to screen 3

    contbtn = Button(root, text="Continue", command=lambda: show_screen2())
    contbtn.grid(row=5, column=0, pady=(0, 35))

# Screen 2: shows components for one file at a time, advancing on each continue click
def show_screen2(index=0):

    global file_index, essential_components, comp_num, checkbox_states, selected_size
    file_index = index

    fp = file_paths[index]
    for widget in root.winfo_children():
        widget.destroy()

    if Path(fp).suffix == ".kicad_sch":
        complist = ic.essential_list_kicad(fp, selected_size.get())
    elif Path(fp).suffix == ".net":
        complist = ic.essential_list_netlist(fp, selected_size.get())
    comp_num = len(complist)

    # Each checkbox gets its own BooleanVar so they toggle independently
    checkbox_states = [BooleanVar() for _ in complist]
    for i, (comp, state) in enumerate(zip(complist, checkbox_states)):
        checkbox = Checkbutton(root, text=f"{comp[0]}: {comp[1]}", variable=state)
        checkbox.grid(column=0, row=i, sticky="w")
        btn = Button(root, text="Details", command=lambda c=comp: show_component_details(c))
        btn.grid(column=1, row=i, padx=(4, 0))

    #sizes = (('Low-Level (all parts)', 'L'),
    #        ('Mid-Level (basic components removed)', 'M'),
    #        ('High-Level (only components with datasheets used)', 'H'))

    # label
    #label = ttk.Label(text="Choose an abstraction level")
    #label.grid(row=0, column=0, pady=(25, 0), padx=100)

    # radio buttons
    #i = 1
    #for size in sizes:
    #    r = ttk.Radiobutton(
    #        root,
    #        text=size[0],
    #        value=size[1],
    #        variable=selected_size
    #    )
    #    r.grid(column=0, row=i)
    #    i += 1
    #    #r.pack(fill='x', padx=5, pady=5)
        

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
    #infer_components_and_relations()
    #print(essential_components)
    complist = ic.essential_list_netlist("prsd.net")
    checked = [comp[0] for comp, state in zip(complist, checkbox_states) if state.get()]
    #print(checked)
    #filter_netlist_full("result.net", checked, "filtered.net")
    #nf = extract_components_from_netlist_with_whitelist("prsd.net", checked)
    #with open("prsd.json", "w") as f:
    #    json.dump(nf, f)
    os.chdir("pipeline")
    subprocess.run("python -m src.main -n ../filtered.net -s \"Run\" -p", shell=True, check=True)


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



def sort_treeview(tree, col, reverse):
    items = [(tree.set(k, col), k) for k in tree.get_children("")]
    try:
        items.sort(key=lambda t: int(t[0]), reverse=reverse)
    except ValueError:
        items.sort(key=lambda t: t[0].lower(), reverse=reverse)
    for i, (_, k) in enumerate(items):
        tree.move(k, "", i)
    tree.heading(col, command=lambda: sort_treeview(tree, col, not reverse))


def _build_summary(data, system_name):
    components = data.get("components", {})
    nets = data.get("nets", {})

    prefix_labels = {
        "R": "Resistors", "C": "Capacitors", "L": "Inductors",
        "U": "ICs / Modules", "Q": "Transistors", "D": "Diodes",
        "J": "Connectors", "SW": "Switches", "F": "Fuses",
        "Y": "Crystals / Oscillators", "TP": "Test Points",
    }
    prefix_counts = {}
    for ref in components:
        prefix = "".join(c for c in ref if c.isalpha())
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

    conn_count = {}
    for nodes in nets.values():
        for node in nodes:
            ref = node.get("ref", "")
            conn_count[ref] = conn_count.get(ref, 0) + 1

    top_hubs = sorted(conn_count.items(), key=lambda x: x[1], reverse=True)[:5]
    power_nets = [n for n in nets if any(p in n.upper() for p in ("VCC", "VDD", "GND", "PWR", "3V3", "5V", "12V", "24V"))]

    lines = [
        f"System: {system_name}",
        "",
        "Overview",
        "--------",
        f"Total components:  {len(components)}",
        f"Total nets:        {len(nets)}",
        "",
    ]

    if prefix_counts:
        lines.append("Component breakdown:")
        for prefix, count in sorted(prefix_counts.items(), key=lambda x: -x[1]):
            label = prefix_labels.get(prefix, f"{prefix} components")
            lines.append(f"  {label}: {count}")
        lines.append("")

    if top_hubs:
        lines.append("Most connected components:")
        for ref, count in top_hubs:
            val = components.get(ref, {}).get("value", "")
            desc = components.get(ref, {}).get("raw_desc", "")
            detail = f" — {desc}" if desc else (f" ({val})" if val else "")
            lines.append(f"  {ref}{detail}: {count} pins")
        lines.append("")

    if power_nets:
        lines.append("Power rails detected:")
        for net in sorted(power_nets):
            node_refs = sorted(set(n.get("ref", "") for n in nets[net]))
            lines.append(f"  {net}: {', '.join(node_refs)}")

    return "\n".join(lines)


class SchematicDetailWindow:
    def __init__(self, parent, data, system_name):
        self.win = Toplevel(parent)
        self.win.title(f"Schematic Details — {system_name}")
        self.win.geometry("900x620")
        self.win.attributes("-topmost", True)
        self.win.lift()
        self.win.focus_force()

        notebook = ttk.Notebook(self.win)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # --- Details tab ---
        details_frame = Frame(notebook)
        notebook.add(details_frame, text="Details")

        meta = data.get("metadata", {})
        comp_count = len(data.get("components", {}))
        net_count = len(data.get("nets", {}))
        meta_text = f"System: {system_name}   |   Components: {comp_count}   |   Nets: {net_count}"
        if meta.get("date"):
            meta_text += f"   |   Date: {meta['date']}"
        Label(details_frame, text=meta_text, anchor="w").pack(fill=X, padx=8, pady=(8, 4))

        # BOM table
        Label(details_frame, text="Bill of Materials", font=("TkDefaultFont", 10, "bold"), anchor="w").pack(fill=X, padx=8)
        bom_frame = Frame(details_frame)
        bom_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 6))

        bom_cols = ("Ref", "Value", "Description", "Pins")
        bom_tree = ttk.Treeview(bom_frame, columns=bom_cols, show="headings", height=8)
        bom_vsb = Scrollbar(bom_frame, orient=VERTICAL, command=bom_tree.yview)
        bom_tree.configure(yscrollcommand=bom_vsb.set)
        bom_vsb.pack(side=RIGHT, fill=Y)
        bom_tree.pack(fill=BOTH, expand=True)

        col_widths = {"Ref": 80, "Value": 130, "Description": 380, "Pins": 60}
        for col in bom_cols:
            bom_tree.heading(col, text=col, command=lambda c=col: sort_treeview(bom_tree, c, False))
            bom_tree.column(col, width=col_widths[col])

        conn_count = {}
        for nodes in data.get("nets", {}).values():
            for node in nodes:
                ref = node.get("ref", "")
                conn_count[ref] = conn_count.get(ref, 0) + 1

        for ref, details in sorted(data.get("components", {}).items()):
            bom_tree.insert("", END, values=(
                ref,
                details.get("value", ""),
                details.get("raw_desc", ""),
                conn_count.get(ref, 0),
            ))

        # Net table
        Label(details_frame, text="Net List", font=("TkDefaultFont", 10, "bold"), anchor="w").pack(fill=X, padx=8)
        net_frame = Frame(details_frame)
        net_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 6))

        net_cols = ("Net Name", "Components", "Pin Count")
        net_tree = ttk.Treeview(net_frame, columns=net_cols, show="headings", height=8)
        net_vsb = Scrollbar(net_frame, orient=VERTICAL, command=net_tree.yview)
        net_tree.configure(yscrollcommand=net_vsb.set)
        net_vsb.pack(side=RIGHT, fill=Y)
        net_tree.pack(fill=BOTH, expand=True)

        net_tree.column("Net Name", width=200)
        net_tree.column("Components", width=500)
        net_tree.column("Pin Count", width=80)
        for col in net_cols:
            net_tree.heading(col, text=col, command=lambda c=col: sort_treeview(net_tree, c, False))

        for net_name, nodes in sorted(data.get("nets", {}).items()):
            refs = sorted(set(n.get("ref", "") for n in nodes))
            net_tree.insert("", END, values=(net_name, ", ".join(refs), len(nodes)))

        # --- Summary tab ---
        summary_frame = Frame(notebook)
        notebook.add(summary_frame, text="Summary")

        summary_text = Text(summary_frame, wrap="word", state="disabled",
                            font=("TkDefaultFont", 11), padx=10, pady=10)
        summary_vsb = Scrollbar(summary_frame, command=summary_text.yview)
        summary_text.configure(yscrollcommand=summary_vsb.set)
        summary_vsb.pack(side=RIGHT, fill=Y)
        summary_text.pack(fill=BOTH, expand=True)

        summary = _build_summary(data, system_name)
        summary_text.configure(state="normal")
        summary_text.insert(END, summary)
        summary_text.configure(state="disabled")


def show_component_details(comp):
    name = comp[0]
    desc = comp[1] if len(comp) > 1 else ""
    docs = comp[2] if len(comp) > 2 else ""
    lib  = comp[3] if len(comp) > 3 else ""
    pins = comp[4] if len(comp) > 4 else []
    footprint = comp[5] if len(comp) > 5 else ""

    win = Toplevel(root)
    win.title(f"Details — {name}")
    win.attributes("-topmost", True)
    win.lift()
    win.focus_force()

    pad = {"padx": 12, "pady": 3, "sticky": "w"}
    row = 0

    Label(win, text="Component", font=("TkDefaultFont", 10, "bold")).grid(
        row=row, column=0, columnspan=2, padx=12, pady=(12, 4), sticky="w")
    row += 1

    fields = [
        ("Name", name),
        ("Library", lib),
        ("Description", desc),
        ("Footprint", footprint),
        ("Datasheet", docs),
    ]
    for label, value in fields:
        if value:
            Label(win, text=label + ":").grid(row=row, column=0, **pad)
            Label(win, text=value, wraplength=360, justify="left").grid(row=row, column=1, **pad)
            row += 1

    if pins:
        Label(win, text="Pins", font=("TkDefaultFont", 10, "bold")).grid(
            row=row, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="w")
        row += 1

        pin_frame = Frame(win)
        pin_frame.grid(row=row, column=0, columnspan=2, padx=12, pady=(0, 4), sticky="ew")
        pin_cols = ("Pin", "Name", "Type")
        pin_tree = ttk.Treeview(pin_frame, columns=pin_cols, show="headings",
                                height=min(len(pins), 10))
        pin_vsb = Scrollbar(pin_frame, orient=VERTICAL, command=pin_tree.yview)
        pin_tree.configure(yscrollcommand=pin_vsb.set)
        pin_vsb.pack(side=RIGHT, fill=Y)
        pin_tree.pack(fill=BOTH, expand=True)
        pin_tree.column("Pin",  width=50,  anchor="center")
        pin_tree.column("Name", width=120)
        pin_tree.column("Type", width=120)
        for col in pin_cols:
            pin_tree.heading(col, text=col)
        for pin in pins:
            pin_tree.insert("", END, values=(pin[0], pin[1], pin[2] if len(pin) > 2 else ""))
        row += 1

    Button(win, text="Close", command=win.destroy).grid(
        row=row, column=0, columnspan=2, pady=(8, 12))


def open_detail_window(net_file, system_name):
    try:
        from netlist_parser import extract_netlist_data
        with open(net_file, "r", encoding="utf-8") as f:
            content = f.read()
        data = extract_netlist_data(content)
        SchematicDetailWindow(root, data, system_name)
    except Exception as e:
        logger.warning(f"Could not open detail window: {e}")


show_screen1()