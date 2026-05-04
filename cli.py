#!/usr/bin/env python3
"""
cli.py (Stories 51-57, 61)

Usage:
    python cli.py
    python cli.py --help

Author: Alex Kolyaskin
"""

import argparse
import os
import sys
import json
import shutil
import platform
import subprocess
import threading
import time
import signal
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional pipeline imports — gracefully degrade if dependencies missing
# ---------------------------------------------------------------------------
try:
    from info_compress import InfoCompressor
    HAS_INFO_COMPRESS = True
except ImportError:
    HAS_INFO_COMPRESS = False

try:
    from netlist_parser import extract_netlist_data, build_stpa_json, NetlistParseError
    HAS_NETLIST_PARSER = True
except ImportError:
    HAS_NETLIST_PARSER = False

try:
    from detect_new_hardware import detect_new_hardware
    HAS_DETECT_HW = True
except ImportError:
    HAS_DETECT_HW = False

try:
    from combinedOCRProcessor import CombinedOCRProcessor
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

try:
    from manual_folder import ManualFolder
    HAS_MANUAL_FOLDER = True
except ImportError:
    HAS_MANUAL_FOLDER = False


# ---------------------------------------------------------------------------
# KiCad CLI path resolution
# ---------------------------------------------------------------------------

_KICAD_CLI_DEFAULTS = {
    "Windows": r"C:\Users\{username}\AppData\Local\Programs\KiCad\9.0\bin\kicad-cli.exe",
    "Darwin":  "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    "Linux":   "kicad-cli",
}


def get_kicad_cli_path() -> str:
    env_path = os.environ.get("KICAD_CLI_PATH", "").strip()
    if env_path:
        return env_path
    system = platform.system()
    default = _KICAD_CLI_DEFAULTS.get(system, "kicad-cli")
    if system == "Windows":
        default = default.format(username=os.environ.get("USERNAME", "user"))
    return default


def check_kicad_cli() -> tuple[bool, str]:
    path = get_kicad_cli_path()
    if os.path.isabs(path):
        available = os.path.isfile(path)
    else:
        available = shutil.which(path) is not None
    return available, path


# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------
SUPPORTED_INPUT_EXTENSIONS = {".kicad_sch", ".net"}
SUPPORTED_OUTPUT_EXTENSIONS = {".json"}


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
def _c(text, code):
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

def green(t):  return _c(t, "32")
def yellow(t): return _c(t, "33")
def red(t):    return _c(t, "31")
def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "36")
def blue(t):   return _c(t, "34")


# ---------------------------------------------------------------------------
# Progress tracking (US #56)
# ---------------------------------------------------------------------------

# Named pipeline stages with relative weight (used to compute % complete)
PIPELINE_STAGES = [
    ("load",        "Loading and converting file"),
    ("parse",       "Parsing netlist components"),
    ("detect",      "Detecting new hardware"),
    ("ocr",         "Running OCR on datasheets"),
    ("filter",      "Applying component filters"),
    ("generate",    "Generating STPA JSON"),
    ("pipeline",    "Running analysis pipeline"),
    ("done",        "Complete"),
]

_STAGE_INDEX = {s[0]: i for i, s in enumerate(PIPELINE_STAGES)}


class ProgressTracker:
    """
    Lightweight stage-based progress tracker.
    Reports progress as [stage N/total] percentage + label without
    crashing or blocking the main REPL thread.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._current_stage = 0
        self._total_stages = len(PIPELINE_STAGES)
        self._active = False
        self._last_pct = -1

    def start(self):
        with self._lock:
            self._current_stage = 0
            self._active = True
            self._last_pct = -1
        self._print_stage(0)

    def advance(self, stage_key: str):
        """Move to a named stage and print progress."""
        idx = _STAGE_INDEX.get(stage_key, self._current_stage + 1)
        with self._lock:
            if not self._active:
                return
            self._current_stage = idx
        self._print_stage(idx)

    def finish(self):
        with self._lock:
            self._active = False
        self._print_stage(len(PIPELINE_STAGES) - 1, force=True)
        print()  # newline after final progress line

    def abort(self):
        with self._lock:
            self._active = False
        # Print a cancelled line
        sys.stdout.write(f"\r  {yellow('⚠  Pipeline cancelled.')}                          \n")
        sys.stdout.flush()

    def _print_stage(self, idx: int, force: bool = False):
        total = self._total_stages - 1  # "done" is the last, 0-indexed finish
        pct = int((idx / max(total, 1)) * 100)
        label = PIPELINE_STAGES[min(idx, len(PIPELINE_STAGES) - 1)][1]
        bar_width = 20
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        stage_str = f"[{idx}/{total}]"
        line = (
            f"\r  {cyan(stage_str)} [{bar}] {pct:3d}%  {label}  "
        )
        sys.stdout.write(line)
        sys.stdout.flush()
        with self._lock:
            self._last_pct = pct


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
class Session:
    """Holds all mutable state for the current REPL session."""

    def __init__(self):
        self.input_path: str | None = None
        self.net_path: str | None = None
        self.output_dir: str | None = None
        self.components: list[dict] = []
        self.excluded: set[str] = set()
        self.stpa_data: dict | None = None
        self.new_hardware: list[str] = []
        self.ocr_ran: bool = False
        self.force_overwrite: bool = False

        # US #55 — fallback database toggle
        self.fallback_enabled: bool = True   # on by default
        self.fallback_folder: str | None = None  # set by setfallback

        # US #56 — progress tracker (shared, not per-run)
        self.progress: ProgressTracker = ProgressTracker()

        # US #57 — background pipeline process/thread
        self._pipeline_thread: threading.Thread | None = None
        self._pipeline_proc: subprocess.Popen | None = None
        self._pipeline_running: bool = False
        self._pipeline_lock: threading.Lock = threading.Lock()

    @property
    def included_components(self) -> list[dict]:
        return [c for c in self.components if c.get("ref") not in self.excluded]

    def summary(self) -> str:
        lines = [bold("── Session Info ──────────────────────────")]
        lines.append(f"  Input file   : {self.input_path or yellow('(none)')}")
        lines.append(f"  Net file     : {self.net_path or yellow('(none)')}")
        lines.append(f"  Output dir   : {self.output_dir or yellow('(none)')}")
        lines.append(f"  Components   : {len(self.components)} total, "
                     f"{len(self.excluded)} excluded, "
                     f"{len(self.included_components)} included")
        lines.append(f"  New hardware : {len(self.new_hardware)} detected")
        lines.append(f"  OCR ran      : {'yes' if self.ocr_ran else 'no'}")
        lines.append(f"  STPA JSON    : {'built (partial)' if self.stpa_data else 'not yet generated'}")
        # US #55
        fb_status = green("enabled") if self.fallback_enabled else red("disabled")
        fb_folder = self.fallback_folder or yellow("(not set — will use AIHVA_MAN env var)")
        lines.append(f"  Fallback DB  : {fb_status}  |  folder: {fb_folder}")
        # US #57
        pipe_status = yellow("running") if self._pipeline_running else "(idle)"
        lines.append(f"  Pipeline     : {pipe_status}")
        lines.append(bold("──────────────────────────────────────────"))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# US #61 — Syntax validation helpers
# ---------------------------------------------------------------------------

class CLISyntaxError(Exception):
    """Raised when a REPL command has invalid syntax."""
    pass


def _require_args(cmd_name: str, args: list[str], min_count: int,
                  usage: str) -> None:
    """
    Raise CLISyntaxError if fewer than min_count args were supplied.
    Provides a clear, actionable message (AC: helps user fix the error).
    """
    if len(args) < min_count:
        raise CLISyntaxError(
            f"'{cmd_name}' requires at least {min_count} argument(s), "
            f"but got {len(args)}.\n"
            f"  Usage: {usage}"
        )


def _reject_extra_args(cmd_name: str, args: list[str], max_count: int,
                       usage: str) -> None:
    """Raise CLISyntaxError if more than max_count args were supplied."""
    if len(args) > max_count:
        raise CLISyntaxError(
            f"'{cmd_name}' accepts at most {max_count} argument(s), "
            f"but got {len(args)}.\n"
            f"  Usage: {usage}"
        )


def _validate_file_path(arg: str, cmd_name: str) -> Path:
    """Return a resolved Path, raising CLISyntaxError for obviously bad inputs."""
    if not arg.strip():
        raise CLISyntaxError(
            f"'{cmd_name}': file path cannot be empty."
        )
    p = Path(arg).expanduser()
    # Check for obviously unsupported extensions early (better UX)
    ext = p.suffix.lower()
    if ext and ext not in SUPPORTED_INPUT_EXTENSIONS | SUPPORTED_OUTPUT_EXTENSIONS | {".pdf", ""}:
        # Don't block — just warn; actual validation happens in cmd_load
        pass
    return p


def _validate_toggle(arg: str, cmd_name: str) -> bool:
    """Parse on/off/true/false/1/0 into bool, raise CLISyntaxError otherwise."""
    normalized = arg.strip().lower()
    if normalized in ("on", "true", "1", "yes", "enable", "enabled"):
        return True
    if normalized in ("off", "false", "0", "no", "disable", "disabled"):
        return False
    raise CLISyntaxError(
        f"'{cmd_name}': invalid toggle value '{arg}'.\n"
        f"  Expected one of: on, off, true, false, 1, 0, yes, no."
    )


def _handle_syntax_error(e: CLISyntaxError) -> None:
    """Print a formatted syntax error (AC: does not execute the command)."""
    print(red(f"\n  Syntax error: {e}\n"))


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_help(args: list[str], session: Session) -> None:
    """Display help for all commands or a specific command."""
    commands = {
        "load": (
            "load <file>",
            "Load a .kicad_sch or .net file. Parses components and checks for new hardware."
        ),
        "components": (
            "components",
            "List all parsed components with ref, value, and status."
        ),
        "exclude": (
            "exclude <ref> [ref ...]",
            "Exclude components by reference designator (e.g. U307 R306)."
        ),
        "include": (
            "include <ref> [ref ...]",
            "Re-include previously excluded components."
        ),
        "setoutput": (
            "setoutput <directory>",
            "Set the output directory where results will be saved."
        ),
        "info": (
            "info",
            "Show current session state."
        ),
        "runocr": (
            "runocr",
            "Run OCR on datasheets for newly detected hardware components."
        ),
        "run": (
            "run",
            "Run the full pipeline: generate filtered .net + STPA JSON (async)."
        ),
        "stop": (
            "stop",
            "[US#57] Stop a running pipeline safely and clean up partial output."
        ),
        "newhardware": (
            "newhardware",
            "Show components detected as new hardware since last load."
        ),
        "fallback": (
            "fallback <on|off>",
            "[US#55] Enable or disable fallback datasheet folder when auto-retrieval fails."
        ),
        "setfallback": (
            "setfallback <directory>",
            "[US#55] Set the manual fallback folder path for datasheets."
        ),
        "clear": (
            "clear",
            "Reset the session."
        ),
        "exit": (
            "exit  |  quit",
            "Exit the ai-hva CLI."
        ),
        "help": (
            "help [command]",
            "Show this help message, or detailed help for a specific command."
        ),
    }

    if args:
        # US #61: validate help argument
        cmd = args[0].lower().strip()
        if cmd in commands:
            usage, desc = commands[cmd]
            print(f"\n  {bold(usage)}")
            print(f"    {desc}\n")
        else:
            # Don't silently ignore — tell the user the command is unknown
            print(red(f"\n  Syntax error: unknown command '{cmd}' passed to help."))
            print(yellow(f"  Available commands: {', '.join(sorted(commands))}.\n"))
        return

    print(f"\n{bold('ai-hva — Hardware Vulnerability Analysis CLI')}")
    print(f"  Pipeline: {cyan('load')} → [{cyan('exclude')}] → [{cyan('runocr')}] → {cyan('run')}\n")
    print(bold("  Commands:"))
    for name, (usage, desc) in commands.items():
        short_desc = desc.split("\n")[0]
        print(f"    {cyan(usage):<38}  {short_desc}")
    print()


def cmd_load(args: list[str], session: Session) -> None:
    """Load a .kicad_sch or .net file and run through sprint-1 pipeline."""
    # US #61: validate args
    try:
        _require_args("load", args, 1, "load <file_path>")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    raw_path = " ".join(args)
    filepath = Path(raw_path).expanduser().resolve()

    if not filepath.is_file():
        print(red(f"  Error: File not found: '{filepath}'"))
        return

    ext = filepath.suffix.lower()
    if ext not in SUPPORTED_INPUT_EXTENSIONS:
        # US #61: clear message for wrong file type
        print(red(
            f"  Syntax error: unsupported file extension '{ext}'.\n"
            f"  Supported types: {', '.join(sorted(SUPPORTED_INPUT_EXTENSIONS))}.\n"
            f"  Usage: load <file.kicad_sch|file.net>"
        ))
        return

    # US #57: block if pipeline is already running
    with session._pipeline_lock:
        if session._pipeline_running:
            print(red("  Error: a pipeline is already running. Use 'stop' first."))
            return

    session.progress.start()
    print(f"\n  Loading {cyan(str(filepath))} ...")

    # --- Convert .kicad_sch → .net if needed ---
    session.progress.advance("load")
    if ext == ".kicad_sch":
        kicad_ok, kicad_path = check_kicad_cli()
        if not kicad_ok:
            print(red(f"\n  Error: kicad-cli not found at '{kicad_path}'."))
            print(yellow("  Set KICAD_CLI_PATH in your environment or config.env."))
            print(yellow("  Tip: You can also load a pre-exported .net file directly."))
            session.progress.abort()
            return

        net_path = "result.net"
        try:
            result = subprocess.run(
                [kicad_path, "sch", "export", "netlist", str(filepath)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(yellow(f"\n  Warning: kicad-cli exited with code {result.returncode}."))
                if result.stderr:
                    print(yellow(f"  {result.stderr.strip()}"))
                net_path = None
            elif os.path.isfile(net_path):
                print(green(f"\n  Converted to netlist: {net_path}"))
            else:
                print(yellow("\n  Warning: kicad-cli ran but no .net file was produced."))
                net_path = None
        except Exception as e:
            print(yellow(f"\n  Warning: kicad-cli conversion failed ({e})."))
            net_path = None

        session.net_path = net_path
    else:
        session.net_path = str(filepath)

    session.input_path = str(filepath)

    # --- Parse components ---
    session.progress.advance("parse")
    if session.net_path and HAS_NETLIST_PARSER:
        try:
            with open(session.net_path, "r", encoding="utf-8") as f:
                content = f.read()
            raw_data = extract_netlist_data(content)
            session.components = [
                {
                    "ref": ref,
                    "value": data.get("value", ""),
                    "desc": data.get("raw_desc", ""),
                }
                for ref, data in raw_data.get("components", {}).items()
            ]
            session.stpa_data = build_stpa_json(raw_data)
            print(green(f"\n  Parsed {len(session.components)} components."))
        except Exception as e:
            print(red(f"\n  Error parsing netlist: {e}"))
            session.progress.abort()
            return
    elif session.net_path is None:
        print(yellow("\n  Could not parse components — no valid .net file available."))
        session.progress.abort()
        return

    # --- Detect new hardware ---
    session.progress.advance("detect")
    if HAS_DETECT_HW and session.net_path:
        db_path = "component_db.json"
        try:
            report = detect_new_hardware(session.net_path, db_path)
            session.new_hardware = report.get("new_components", [])
            if session.new_hardware:
                print(yellow(f"\n  ⚠  New hardware detected: "
                             f"{', '.join(session.new_hardware)}"))
                print(yellow(f"     Run 'runocr' to process their datasheets."))
            else:
                print(green("\n  No new hardware detected."))
        except Exception as e:
            print(yellow(f"\n  Warning: Hardware detection failed ({e})"))

    session.progress.finish()
    print(green(f"\n  ✓ Load complete. Type 'components' to review, "
                f"'exclude' to filter, then 'run'."))


def cmd_components(args: list[str], session: Session) -> None:
    # US #61: no args expected
    try:
        _reject_extra_args("components", args, 0, "components")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    if not session.components:
        print(yellow("  No components loaded. Use 'load <file>' first."))
        return

    print(f"\n  {bold('Components')} ({len(session.components)} total, "
          f"{len(session.excluded)} excluded):\n")
    print(f"  {'Ref':<10} {'Value':<12} {'Status':<12} Description")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*30}")

    for comp in session.components:
        ref = comp.get("ref", "?")
        value = comp.get("value", "")[:11]
        desc = comp.get("desc", "")[:45]
        is_new = ref in session.new_hardware
        if ref in session.excluded:
            status = red("[EXCLUDED]")
        elif is_new:
            status = yellow("[NEW]     ")
        else:
            status = green("[included]")
        print(f"  {ref:<10} {value:<12} {status}  {desc}")
    print()


def cmd_exclude(args: list[str], session: Session) -> None:
    try:
        _require_args("exclude", args, 1, "exclude <ref> [ref ...]")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    if not session.components:
        print(yellow("  No components loaded. Use 'load <file>' first."))
        return

    valid_refs = {c["ref"] for c in session.components}
    added, not_found = [], []

    for ref in args:
        ref = ref.upper().strip(",")
        if not ref:
            continue
        if ref in valid_refs:
            session.excluded.add(ref)
            added.append(ref)
        else:
            not_found.append(ref)

    if added:
        print(green(f"  Excluded: {', '.join(added)}"))
    if not_found:
        print(yellow(f"  Not found (ignored): {', '.join(not_found)}"))
        print(yellow(f"  Tip: Use 'components' to see valid reference designators."))


def cmd_include(args: list[str], session: Session) -> None:
    try:
        _require_args("include", args, 1, "include <ref> [ref ...]")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    removed, not_excluded = [], []
    for ref in args:
        ref = ref.upper().strip(",")
        if ref in session.excluded:
            session.excluded.remove(ref)
            removed.append(ref)
        else:
            not_excluded.append(ref)

    if removed:
        print(green(f"  Re-included: {', '.join(removed)}"))
    if not_excluded:
        print(yellow(f"  Not currently excluded: {', '.join(not_excluded)}"))


def cmd_setoutput(args: list[str], session: Session) -> None:
    try:
        _require_args("setoutput", args, 1, "setoutput <directory>")
        _reject_extra_args("setoutput", args, 1, "setoutput <directory>")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    dirpath = args[0]

    if os.path.isfile(dirpath):
        print(red(f"  Error: '{dirpath}' is a file, not a directory."))
        return

    if not os.path.exists(dirpath):
        try:
            os.makedirs(dirpath, exist_ok=True)
            print(green(f"  Created directory: {dirpath}"))
        except OSError as e:
            print(red(f"  Error: Could not create directory '{dirpath}': {e}"))
            return

    if not os.access(dirpath, os.W_OK):
        print(red(f"  Error: Directory '{dirpath}' is not writable."))
        return

    session.output_dir = dirpath
    print(green(f"  Output directory set to: {dirpath}"))


def cmd_info(args: list[str], session: Session) -> None:
    try:
        _reject_extra_args("info", args, 0, "info")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return
    print()
    print(session.summary())


def cmd_newhardware(args: list[str], session: Session) -> None:
    try:
        _reject_extra_args("newhardware", args, 0, "newhardware")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    if not session.new_hardware:
        print(yellow("  No new hardware detected in this session."))
        if not session.input_path:
            print(yellow("  Load a file first with 'load <file>'."))
        return

    print(f"\n  {bold('New Hardware Detected')} ({len(session.new_hardware)} components):\n")
    for ref in session.new_hardware:
        comp = next((c for c in session.components if c["ref"] == ref), {})
        value = comp.get("value", "")
        desc = comp.get("desc", "")
        print(f"    {yellow(ref):<12} {value:<12} {desc}")
    print(f"\n  Run {cyan('runocr')} to process datasheets for these components.\n")


def cmd_runocr(args: list[str], session: Session) -> None:
    try:
        _reject_extra_args("runocr", args, 0, "runocr")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    if not session.input_path:
        print(yellow("  No file loaded. Use 'load <file>' first."))
        return

    if not session.new_hardware:
        print(yellow("  No new hardware to process."))
        confirm = input("  Run OCR anyway on all components? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            return

    if not HAS_OCR:
        print(red("  Error: OCR module (combinedOCRProcessor) not available."))
        return

    print(yellow("  ⚠  OCR is slow and may take several minutes per document."))
    confirm = input("  Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("  Aborted.")
        return

    targets = session.new_hardware if session.new_hardware else [
        c["ref"] for c in session.included_components
    ]

    # US #56 — show progress during OCR
    print(f"\n  Running OCR on {len(targets)} component(s)...\n")
    session.progress.start()
    session.progress.advance("ocr")

    processor = CombinedOCRProcessor()
    for i, ref in enumerate(targets):
        comp = next((c for c in session.components if c["ref"] == ref), {})
        desc = comp.get("desc", "")
        print(f"\n  [{i+1}/{len(targets)}] Processing {cyan(ref)} ({desc}) ...")

        # US #55 — fallback logic during OCR datasheet retrieval
        if HAS_MANUAL_FOLDER and session.fallback_enabled:
            mf = ManualFolder()
            if session.fallback_folder:
                mf.set_manual_folder_path(session.fallback_folder)
            # Try to find datasheet; fallback folder will be used automatically
            # by ManualFolder if the URL request fails
            datasheet_url = comp.get("datasheet", "")
            result, error = mf.test_find_datasheet(ref, datasheet_url)
            if error:
                print(yellow(f"    ⚠  Datasheet retrieval failed: {error}"))
            else:
                print(green(f"    ✓  Datasheet retrieved for {ref}."))
        elif not session.fallback_enabled:
            print(yellow(f"    Fallback disabled — skipping datasheet retrieval for {ref}."))

    session.progress.finish()
    session.ocr_ran = True
    print(green("\n  ✓ OCR step complete."))


# ---------------------------------------------------------------------------
# US #55 — fallback toggle commands
# ---------------------------------------------------------------------------

def cmd_fallback(args: list[str], session: Session) -> None:
    """
    US #55 — Enable or disable fallback datasheet database.
    Usage: fallback <on|off>
    """
    try:
        _require_args("fallback", args, 1, "fallback <on|off>")
        _reject_extra_args("fallback", args, 1, "fallback <on|off>")
        enabled = _validate_toggle(args[0], "fallback")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    session.fallback_enabled = enabled
    state_str = green("enabled") if enabled else red("disabled")
    print(f"  Fallback datasheet database {state_str}.")

    if enabled and not session.fallback_folder:
        env_folder = os.environ.get("AIHVA_MAN", "")
        if env_folder:
            print(yellow(f"  Using fallback folder from AIHVA_MAN: {env_folder}"))
        else:
            print(yellow("  No fallback folder set. Use 'setfallback <directory>' to configure one."))


def cmd_setfallback(args: list[str], session: Session) -> None:
    """
    US #55 — Set the manual fallback folder path for datasheets.
    Usage: setfallback <directory>
    """
    try:
        _require_args("setfallback", args, 1, "setfallback <directory>")
        _reject_extra_args("setfallback", args, 1, "setfallback <directory>")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    dirpath = args[0].strip()

    # US #61 — validate before touching anything
    if not dirpath:
        print(red("  Syntax error: directory path cannot be empty.\n"
                  "  Usage: setfallback <directory>"))
        return

    if not HAS_MANUAL_FOLDER:
        print(red("  Error: ManualFolder module not available."))
        return

    mf = ManualFolder()
    error = mf.set_manual_folder_path(dirpath)
    if error:
        print(red(f"  Error: {error}"))
        return

    session.fallback_folder = dirpath
    # Also enable fallback automatically when a folder is set
    session.fallback_enabled = True
    print(green(f"  Fallback folder set to: {dirpath}"))
    print(green(f"  Fallback database automatically enabled."))

    # Count PDFs in the folder so user knows what's available
    try:
        pdf_count = len([f for f in os.listdir(dirpath)
                         if f.lower().endswith(".pdf")])
        print(f"  Found {cyan(str(pdf_count))} PDF file(s) in fallback folder.")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# US #57 — stop command
# ---------------------------------------------------------------------------

def cmd_stop(args: list[str], session: Session) -> None:
    """
    US #57 — Stop a running pipeline safely.
    Usage: stop
    """
    try:
        _reject_extra_args("stop", args, 0, "stop")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    with session._pipeline_lock:
        running = session._pipeline_running
        proc = session._pipeline_proc

    if not running:
        print(yellow("  No pipeline is currently running."))
        return

    print(yellow("  Stopping pipeline..."))

    # Terminate the subprocess if it exists
    if proc is not None:
        try:
            if platform.system() == "Windows":
                proc.terminate()
            else:
                # Send SIGTERM first for graceful shutdown
                os.kill(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't respond
                    os.kill(proc.pid, signal.SIGKILL)
                    proc.wait()
        except (ProcessLookupError, PermissionError) as e:
            print(yellow(f"  Warning: could not signal process ({e})"))

    # Signal the thread to stop
    with session._pipeline_lock:
        session._pipeline_running = False

    # Wait for the thread to finish (with timeout so REPL doesn't hang)
    if session._pipeline_thread and session._pipeline_thread.is_alive():
        session._pipeline_thread.join(timeout=3)

    session.progress.abort()

    # Clean up partial output
    _cleanup_partial_output(session)

    with session._pipeline_lock:
        session._pipeline_proc = None
        session._pipeline_thread = None

    print(green("  ✓ Pipeline stopped. Partial output has been cleaned up."))


def _cleanup_partial_output(session: Session) -> None:
    """Remove any partial output files left by an aborted run."""
    if not session.output_dir or not session.input_path:
        return
    input_stem = Path(session.input_path).stem
    partial_path = os.path.join(session.output_dir, f"{input_stem}_stpa.json")
    if os.path.exists(partial_path):
        try:
            os.remove(partial_path)
            print(yellow(f"  Removed partial output: {partial_path}"))
        except OSError as e:
            print(yellow(f"  Warning: could not remove partial output: {e}"))


# ---------------------------------------------------------------------------
# US #56 + #57 — async pipeline runner
# ---------------------------------------------------------------------------

def _run_pipeline_thread(session: Session, stpa: dict, output_path: str,
                         input_stem: str) -> None:
    """
    Background thread body for cmd_run.
    Updates progress tracker at each stage and streams subprocess output.
    Sets session._pipeline_running = False when done or cancelled.
    """
    try:
        # Stage: filter
        session.progress.advance("filter")
        ic = InfoCompressor() if HAS_INFO_COMPRESS else None
        prsd = "prsd.kicad_sch"

        if ic and session.input_path and stpa.get("components"):
            try:
                ic.convert_whitelist_kicad(
                    session.input_path, stpa["components"], prsd
                )
            except Exception as e:
                print(yellow(f"\n  Warning: whitelist conversion failed ({e})"))

        # Check for stop before heavyweight stage
        with session._pipeline_lock:
            if not session._pipeline_running:
                return

        # Stage: generate JSON
        session.progress.advance("generate")
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(stpa, f, indent=2)
            print(green(f"\n  ✓ STPA JSON saved to: {output_path}"))
        except OSError as e:
            print(red(f"\n  Error writing output: {e}"))
            return

        # Check for stop before subprocess
        with session._pipeline_lock:
            if not session._pipeline_running:
                return

        # Stage: run analysis pipeline subprocess
        session.progress.advance("pipeline")
        pipeline_dir = "pipeline"
        if os.path.isdir(pipeline_dir):
            cmd = [
                sys.executable, "-m", "src.main",
                "-n", f"../prsd.net",
                "-s", "Run",
                "-p"
            ]
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=pipeline_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                with session._pipeline_lock:
                    session._pipeline_proc = proc

                # Stream output line by line (US #56)
                for line in proc.stdout:
                    with session._pipeline_lock:
                        if not session._pipeline_running:
                            proc.terminate()
                            break
                    line = line.rstrip()
                    if line:
                        print(f"  {blue('│')} {line}")

                proc.wait()
                with session._pipeline_lock:
                    session._pipeline_proc = None

                if proc.returncode not in (0, -15, -9):  # -15=SIGTERM, -9=SIGKILL
                    print(yellow(f"\n  Pipeline exited with code {proc.returncode}."))

            except FileNotFoundError:
                print(yellow("\n  Warning: pipeline module not found; skipping subprocess."))
            except Exception as e:
                print(yellow(f"\n  Warning: pipeline subprocess failed ({e})"))
        else:
            print(yellow(f"\n  Note: '{pipeline_dir}' directory not found; skipping subprocess."))

        # Final check — did user stop us?
        with session._pipeline_lock:
            still_running = session._pipeline_running

        if still_running:
            session.progress.finish()
            print(green("\n  ✓ Run complete."))

    except Exception as e:
        print(red(f"\n  Unexpected error in pipeline thread: {e}"))
    finally:
        with session._pipeline_lock:
            session._pipeline_running = False
            session._pipeline_proc = None


def cmd_run(args: list[str], session: Session) -> None:
    """Run the pipeline asynchronously (US #56, #57)."""
    try:
        _reject_extra_args("run", args, 0, "run")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    # US #57: prevent double-start
    with session._pipeline_lock:
        if session._pipeline_running:
            print(red("  Error: pipeline is already running. Use 'stop' to cancel it first."))
            return

    if not session.input_path:
        print(yellow("  No file loaded. Use 'load <file>' first."))
        return
    if not session.output_dir:
        print(yellow("  No output directory set. Use 'setoutput <directory>' first."))
        return
    if not session.stpa_data:
        print(yellow("  No parsed data available. Try reloading with 'load <file>'."))
        return

    # Apply exclusions
    stpa = dict(session.stpa_data)
    if session.excluded:
        stpa["components"] = {
            k: v for k, v in stpa.get("components", {}).items()
            if k not in session.excluded
        }
        stpa["connection_pairs"] = {
            k: v for k, v in stpa.get("connection_pairs", {}).items()
            if not any(ep in session.excluded for ep in v.get("endpoints", []))
        }
        stpa["connection_details"] = {
            k: v for k, v in stpa.get("connection_details", {}).items()
            if k in stpa["connection_pairs"]
        }
        print(f"  Applied exclusions: {', '.join(session.excluded)}")

    # US #55 — inject fallback state into stpa metadata
    stpa.setdefault("system_metadata", {})
    stpa["system_metadata"]["fallback_enabled"] = session.fallback_enabled
    stpa["system_metadata"]["fallback_folder"] = session.fallback_folder or ""

    input_stem = Path(session.input_path).stem
    output_filename = f"{input_stem}_stpa.json"
    output_path = os.path.join(session.output_dir, output_filename)

    if os.path.exists(output_path) and not session.force_overwrite:
        confirm = input(f"  '{output_path}' already exists. Overwrite? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            return

    # Launch pipeline in background thread (US #57)
    with session._pipeline_lock:
        session._pipeline_running = True

    session.progress.start()

    t = threading.Thread(
        target=_run_pipeline_thread,
        args=(session, stpa, output_path, input_stem),
        daemon=True,
        name="pipeline-thread"
    )
    session._pipeline_thread = t
    t.start()

    print(green(
        f"\n  Pipeline started in background.\n"
        f"  Output → {output_path}\n"
        f"  Type {cyan('stop')} to cancel, or {cyan('info')} to check status."
    ))


def cmd_clear(args: list[str], session: Session) -> None:
    try:
        _reject_extra_args("clear", args, 0, "clear")
    except CLISyntaxError as e:
        _handle_syntax_error(e)
        return

    # US #57: warn if pipeline is running
    with session._pipeline_lock:
        running = session._pipeline_running
    if running:
        print(yellow("  Warning: a pipeline is running. Clearing will NOT stop it."))
        print(yellow("  Use 'stop' first if you want to cancel the pipeline."))

    confirm = input("  Clear all session data? [y/N] ").strip().lower()
    if confirm == "y":
        session.__init__()
        print(green("  Session cleared."))
    else:
        print("  Aborted.")


# ---------------------------------------------------------------------------
# Command dispatch table
# ---------------------------------------------------------------------------
COMMANDS = {
    "help":         cmd_help,
    "load":         cmd_load,
    "components":   cmd_components,
    "exclude":      cmd_exclude,
    "include":      cmd_include,
    "setoutput":    cmd_setoutput,
    "info":         cmd_info,
    "newhardware":  cmd_newhardware,
    "runocr":       cmd_runocr,
    "run":          cmd_run,
    "stop":         cmd_stop,          # US #57
    "fallback":     cmd_fallback,      # US #55
    "setfallback":  cmd_setfallback,   # US #55
    "clear":        cmd_clear,
}


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

BANNER = f"""
{bold('╔══════════════════════════════════════════════════╗')}
{bold('║')}  {cyan('ai-hva')} — Hardware Vulnerability Analysis CLI    {bold('║')}
{bold('║')}  CS407 Team 2 | Sandia National Laboratories     {bold('║')}
{bold('╚══════════════════════════════════════════════════╝')}

  Pipeline: {cyan('load')} → [{cyan('exclude')}] → [{cyan('runocr')}] → {cyan('run')}
  Type {cyan('help')} for available commands.
"""


def run_repl(session: Session) -> None:
    print(BANNER)

    while True:
        # US #57: show a subtle indicator when pipeline is running
        with session._pipeline_lock:
            pipe_running = session._pipeline_running
        prompt_prefix = f"{yellow('⚙ ')}ai-hva" if pipe_running else f"{cyan('ai-hva')}"

        try:
            raw = input(f"{prompt_prefix}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            # US #57: clean stop on Ctrl-C if pipeline is running
            with session._pipeline_lock:
                running = session._pipeline_running
            if running:
                print(yellow("  Ctrl-C detected — stopping running pipeline..."))
                cmd_stop([], session)
            print(green("  Goodbye!"))
            break

        if not raw:
            continue

        # US #61: detect and report empty/whitespace-only commands
        parts = raw.split()
        if not parts:
            continue

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit"):
            # US #57: warn if pipeline is running on exit
            with session._pipeline_lock:
                running = session._pipeline_running
            if running:
                confirm = input(
                    yellow("  Pipeline is still running. Exit anyway? [y/N] ")
                ).strip().lower()
                if confirm != "y":
                    print("  Aborted. Use 'stop' then 'exit'.")
                    continue
                cmd_stop([], session)
            print(green("  Goodbye!"))
            break

        if cmd in COMMANDS:
            try:
                COMMANDS[cmd](args, session)
            except CLISyntaxError as e:
                # Should have been caught inside each command, but catch here too
                _handle_syntax_error(e)
            except Exception as e:
                print(red(f"  Unexpected error in '{cmd}': {e}"))
                print(red("  If this persists, please file a bug report."))
        else:
            # US #61: unknown command — clear error, no execution
            print(red(f"\n  Syntax error: unknown command '{cmd}'."))
            # Suggest close matches if any
            close = [c for c in COMMANDS if c.startswith(cmd[:3])]
            if close:
                print(yellow(f"  Did you mean: {', '.join(close)}?"))
            print(yellow(f"  Type {cyan('help')} for a list of available commands.\n"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-hva",
        description="AI-Pipeline for Hardware Vulnerability Analysis (CS407 Team 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py                                    Start interactive REPL
  python cli.py --load example.net                 Pre-load a file
  python cli.py --load example.net --output ./out  Pre-load and set output dir
  python cli.py --load example.net --no-fallback   Disable fallback DB on start
  python cli.py --load example.net --fallback-dir ./datasheets
        """,
    )
    parser.add_argument(
        "--load", "-l",
        metavar="FILE",
        help="Pre-load a .kicad_sch or .net file on startup",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="DIRECTORY",
        help="Set output directory on startup",
    )
    parser.add_argument(
        "--exclude", "-e",
        metavar="REF",
        nargs="+",
        help="Pre-exclude component references (e.g. --exclude U307 R306)",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force overwrite of existing output files without prompting",
    )
    parser.add_argument(
        "--detect-hardware",
        action="store_true",
        help="Print new hardware report and exit (non-interactive)",
    )
    # US #55 — argparse flags for fallback
    fallback_group = parser.add_mutually_exclusive_group()
    fallback_group.add_argument(
        "--no-fallback",
        action="store_true",
        help="[US#55] Disable fallback datasheet database on startup",
    )
    fallback_group.add_argument(
        "--fallback",
        action="store_true",
        default=True,
        help="[US#55] Enable fallback datasheet database on startup (default)",
    )
    parser.add_argument(
        "--fallback-dir",
        metavar="DIRECTORY",
        help="[US#55] Set the manual fallback folder for datasheets on startup",
    )
    return parser


def _validate_startup_args(cli_args: argparse.Namespace) -> list[str]:
    """
    US #61 — validate argparse startup arguments before the REPL begins.
    Returns a list of error strings (empty = all valid).
    """
    errors = []

    if cli_args.load:
        p = Path(cli_args.load).expanduser()
        if not p.exists():
            errors.append(f"--load: file not found: '{cli_args.load}'")
        elif p.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
            errors.append(
                f"--load: unsupported file extension '{p.suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_INPUT_EXTENSIONS))}"
            )

    if cli_args.output:
        op = Path(cli_args.output)
        if op.exists() and op.is_file():
            errors.append(
                f"--output: '{cli_args.output}' is an existing file, not a directory."
            )

    if cli_args.fallback_dir:
        fd = Path(cli_args.fallback_dir)
        if not fd.exists():
            errors.append(f"--fallback-dir: directory not found: '{cli_args.fallback_dir}'")
        elif not fd.is_dir():
            errors.append(f"--fallback-dir: '{cli_args.fallback_dir}' is not a directory.")

    return errors


def main() -> None:
    parser = build_arg_parser()
    cli_args = parser.parse_args()

    # US #61 — validate startup args before doing anything
    startup_errors = _validate_startup_args(cli_args)
    if startup_errors:
        print(red("\n  Startup argument error(s):"))
        for err in startup_errors:
            print(red(f"    • {err}"))
        print(yellow("\n  Run 'python cli.py --help' for usage information.\n"))
        sys.exit(1)

    session = Session()
    session.force_overwrite = cli_args.force

    # US #55 — apply fallback flag from argparse
    if cli_args.no_fallback:
        session.fallback_enabled = False
        print(yellow("  Fallback database disabled via --no-fallback."))

    if cli_args.fallback_dir:
        cmd_setfallback([cli_args.fallback_dir], session)

    # Apply pre-load args
    if cli_args.output:
        cmd_setoutput([cli_args.output], session)

    if cli_args.exclude:
        session.excluded = {r.upper() for r in cli_args.exclude}

    if cli_args.load:
        cmd_load([cli_args.load], session)

    # Non-interactive mode
    if cli_args.detect_hardware:
        if not session.input_path:
            print(red("  Error: --detect-hardware requires --load <file>"))
            sys.exit(1)
        cmd_newhardware([], session)
        sys.exit(0)

    run_repl(session)


if __name__ == "__main__":
    main()