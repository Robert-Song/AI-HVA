import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from frontend.app_state import PipelineConfig
from frontend.component_selector import component_label, group_components
from frontend.datasheet_manager import attach_manual_pdf, process_component_datasheets
from frontend.kicad_export import resolve_input_netlist
from frontend.pipeline_runner import load_components, run_pipeline_from_config


class AIHVAApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI-HVA Pipeline")
        self.geometry("980x720")
        self.minsize(820, 560)

        self.config_state = PipelineConfig()
        self.components: dict = {}
        self.component_vars: dict[str, tk.BooleanVar] = {}
        self.group_vars: dict[str, tk.BooleanVar] = {}
        self.events: queue.Queue = queue.Queue()

        self._build_layout()
        self.after(100, self._drain_events)

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        self.input_frame = ttk.LabelFrame(root, text="Input")
        self.input_frame.pack(fill=tk.X, pady=(0, 8))
        self._build_input_frame()

        middle = ttk.Frame(root)
        middle.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.selector_frame = ttk.LabelFrame(middle, text="Components")
        self.selector_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._build_selector_frame()

        self.options_frame = ttk.LabelFrame(middle, text="Pipeline Options")
        self.options_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self._build_options_frame()

        self.log = tk.Text(root, height=9, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH)

    def _build_input_frame(self) -> None:
        self.kicad_var = tk.StringVar()
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.system_var = tk.StringVar(value="Run")

        self._path_row(self.input_frame, 0, "kicad-cli", self.kicad_var, self._browse_kicad)
        self._path_row(self.input_frame, 1, "Schematic/netlist", self.input_var, self._browse_input)
        self._path_row(self.input_frame, 2, "Output directory", self.output_var, self._browse_output)

        ttk.Label(self.input_frame, text="System name").grid(row=3, column=0, sticky=tk.W, padx=4, pady=3)
        ttk.Entry(self.input_frame, textvariable=self.system_var).grid(row=3, column=1, sticky=tk.EW, padx=4, pady=3)

        ttk.Button(self.input_frame, text="Parse Components", command=self.parse_components).grid(row=3, column=2, sticky=tk.EW, padx=4, pady=3)
        self.input_frame.columnconfigure(1, weight=1)

    def _path_row(self, parent, row: int, label: str, var: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=4, pady=3)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky=tk.EW, padx=4, pady=3)
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, sticky=tk.EW, padx=4, pady=3)

    def _build_selector_frame(self) -> None:
        toolbar = ttk.Frame(self.selector_frame)
        toolbar.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(toolbar, text="Select All", command=lambda: self._set_all(True)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Select None", command=lambda: self._set_all(False)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Fetch Datasheets", command=self.fetch_datasheets).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Attach PDF", command=self.attach_pdf).pack(side=tk.RIGHT, padx=(0, 6))

        self.canvas = tk.Canvas(self.selector_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.selector_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.component_container = ttk.Frame(self.canvas)
        self.component_container.bind(
            "<Configure>",
            lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.component_container, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_options_frame(self) -> None:
        self.subgroup_var = tk.BooleanVar(value=False)
        self.hops_var = tk.IntVar(value=0)

        ttk.Checkbutton(
            self.options_frame,
            text="Enable Functional Sub-grouping",
            variable=self.subgroup_var,
        ).pack(anchor=tk.W, padx=10, pady=(10, 8))

        ttk.Label(self.options_frame, text="Max Connection Hops").pack(anchor=tk.W, padx=10)
        ttk.Scale(
            self.options_frame,
            from_=0,
            to=10,
            orient=tk.HORIZONTAL,
            variable=self.hops_var,
            command=lambda value: self.hops_label.configure(text=str(int(float(value)))),
        ).pack(fill=tk.X, padx=10, pady=(2, 0))
        self.hops_label = ttk.Label(self.options_frame, text="0")
        self.hops_label.pack(anchor=tk.W, padx=10, pady=(0, 12))

        ttk.Button(self.options_frame, text="Start Pipeline", command=self.start_pipeline).pack(fill=tk.X, padx=10, pady=10)

    def _browse_kicad(self) -> None:
        path = filedialog.askopenfilename(title="Select kicad-cli executable")
        if path:
            self.kicad_var.set(path)

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select KiCad schematic or netlist",
            filetypes=[("KiCad files", "*.kicad_sch *.net"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self.output_var.set(path)

    def parse_components(self) -> None:
        try:
            input_path = Path(self.input_var.get()).expanduser()
            if not input_path.exists():
                raise FileNotFoundError("Select an existing .kicad_sch or .net file.")
            output_dir = Path(self.output_var.get()).expanduser() if self.output_var.get() else Path.cwd() / "pipeline" / "output"
            kicad_cli = Path(self.kicad_var.get()).expanduser() if self.kicad_var.get() else None
            netlist_path = resolve_input_netlist(input_path, kicad_cli, output_dir)
            netlist = load_components(netlist_path)
        except Exception as exc:
            messagebox.showerror("Parse failed", str(exc))
            return

        self.config_state.input_path = input_path
        self.config_state.kicad_cli_path = kicad_cli
        self.config_state.netlist_path = netlist_path
        self.config_state.output_dir = output_dir
        self.components = netlist.get("components", {})
        self._populate_components()
        self._log(f"Loaded {len(self.components)} components from {netlist_path}")

    def _populate_components(self) -> None:
        for child in self.component_container.winfo_children():
            child.destroy()
        self.component_vars.clear()
        self.group_vars.clear()

        grouped = group_components(self.components)
        for prefix, component_ids in grouped.items():
            group_var = tk.BooleanVar(value=True)
            self.group_vars[prefix] = group_var
            group_box = ttk.LabelFrame(self.component_container, text=f"{prefix} ({len(component_ids)})")
            group_box.pack(fill=tk.X, padx=6, pady=4)
            ttk.Checkbutton(
                group_box,
                text=f"Include all {prefix}",
                variable=group_var,
                command=lambda p=prefix: self._toggle_group(p),
            ).pack(anchor=tk.W, padx=6, pady=2)
            for component_id in component_ids:
                var = tk.BooleanVar(value=True)
                self.component_vars[component_id] = var
                ttk.Checkbutton(
                    group_box,
                    text=component_label(component_id, self.components[component_id]),
                    variable=var,
                    command=lambda p=prefix: self._sync_group(p),
                ).pack(anchor=tk.W, padx=20, pady=1)

    def _toggle_group(self, prefix: str) -> None:
        value = self.group_vars[prefix].get()
        for component_id in group_components(self.components).get(prefix, []):
            self.component_vars[component_id].set(value)

    def _sync_group(self, prefix: str) -> None:
        ids = group_components(self.components).get(prefix, [])
        self.group_vars[prefix].set(all(self.component_vars[cid].get() for cid in ids))

    def _set_all(self, value: bool) -> None:
        for var in self.group_vars.values():
            var.set(value)
        for var in self.component_vars.values():
            var.set(value)

    def _selected_ids(self) -> set[str]:
        return {cid for cid, var in self.component_vars.items() if var.get()}

    def _sync_config(self) -> None:
        selected = self._selected_ids()
        self.config_state.selected_components = selected
        self.config_state.ignored_parts = set(self.components) - selected
        self.config_state.output_dir = Path(self.output_var.get()).expanduser() if self.output_var.get() else self.config_state.output_dir
        self.config_state.system_name = self.system_var.get().strip() or "Run"
        self.config_state.enable_subgrouping = self.subgroup_var.get()
        self.config_state.max_connection_hops = int(self.hops_var.get())

    def fetch_datasheets(self) -> None:
        if not self.components:
            messagebox.showinfo("No components", "Parse a netlist first.")
            return
        self._sync_config()
        self._run_background(
            "datasheets",
            lambda: process_component_datasheets(
                self.components,
                self.config_state.selected_components,
                self.config_state.netlist_path,
                self.config_state.system_name,
                self.config_state.output_dir,
            ),
        )

    def attach_pdf(self) -> None:
        if not self.components:
            messagebox.showinfo("No components", "Parse a netlist first.")
            return
        component_id = self._prompt_component_id()
        if not component_id:
            return
        pdf_path = filedialog.askopenfilename(title="Select supplemental PDF", filetypes=[("PDF", "*.pdf")])
        if not pdf_path:
            return
        self._sync_config()
        result = attach_manual_pdf(
            component_id,
            Path(pdf_path),
            self.config_state.netlist_path,
            self.config_state.system_name,
            self.config_state.output_dir,
        )
        self._log(f"{result.component_id}: {result.status} - {result.message}")

    def _prompt_component_id(self) -> str | None:
        dialog = tk.Toplevel(self)
        dialog.title("Component ID")
        dialog.transient(self)
        dialog.grab_set()
        value = tk.StringVar()
        ttk.Label(dialog, text="Map PDF to component ID").pack(padx=12, pady=(12, 4))
        combo = ttk.Combobox(dialog, textvariable=value, values=sorted(self.components))
        combo.pack(padx=12, pady=4)
        selected = {"value": None}

        def accept() -> None:
            if value.get() in self.components:
                selected["value"] = value.get()
                dialog.destroy()
            else:
                messagebox.showerror("Invalid component", "Choose a component from the list.")

        ttk.Button(dialog, text="Attach", command=accept).pack(padx=12, pady=(4, 12))
        self.wait_window(dialog)
        return selected["value"]

    def start_pipeline(self) -> None:
        if not self.config_state.netlist_path:
            messagebox.showinfo("No netlist", "Parse components before starting the pipeline.")
            return
        self._sync_config()
        if not self.config_state.output_dir:
            messagebox.showerror("Missing output", "Choose an output directory.")
            return
        self._run_background("pipeline", lambda: run_pipeline_from_config(self.config_state))

    def _run_background(self, name: str, target) -> None:
        self._log(f"Starting {name}...")

        def worker() -> None:
            try:
                self.events.put((name, "ok", target()))
            except Exception as exc:
                self.events.put((name, "error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_events(self) -> None:
        while True:
            try:
                name, status, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if status == "error":
                self._log(f"{name} failed: {payload}")
                messagebox.showerror(f"{name} failed", str(payload))
            elif name == "datasheets":
                failures = [result for result in payload if result.status != "ok"]
                for result in payload:
                    self._log(f"{result.component_id}: {result.status} - {result.message}")
                if failures:
                    messagebox.showwarning("Datasheets", f"{len(failures)} component datasheets need manual PDFs.")
                else:
                    messagebox.showinfo("Datasheets", "All selected datasheets are available.")
            elif name == "pipeline":
                self._log("Pipeline complete.")
                messagebox.showinfo("Pipeline complete", "Final STPA JSON was written to the selected output directory.")
        self.after(100, self._drain_events)

    def _log(self, message: str) -> None:
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)


def main() -> None:
    app = AIHVAApp()
    app.mainloop()
