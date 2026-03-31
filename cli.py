#!/usr/bin/env python3
"""
cli.py (Story 51-54)

Usage:
    python cli.py
    python cli.py --help

Author: Alex Kolyaskin 3-30-26
"""

import argparse
import os
import sys
import json
import shutil
import platform
import subprocess
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


# ---------------------------------------------------------------------------
# KiCad CLI path resolution
# ---------------------------------------------------------------------------

# Default paths per platform. Users can override via KICAD_CLI_PATH env var
# or by setting it in config.env (KICAD_CLI_PATH=...).
_KICAD_CLI_DEFAULTS = {
    "Windows": r"C:\Users\{username}\AppData\Local\Programs\KiCad\9.0\bin\kicad-cli.exe",
    "Darwin":  "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    "Linux":   "kicad-cli",
}


def get_kicad_cli_path() -> str:
    """
    Resolve the kicad-cli executable path.

    Priority:
      1. KICAD_CLI_PATH environment variable (set in .env / config.env or shell)
      2. Platform default (Windows AppData path, macOS app bundle, Linux PATH)
    """
    # Check env var first (set in config.env or shell)
    env_path = os.environ.get("KICAD_CLI_PATH", "").strip()
    if env_path:
        return env_path

    system = platform.system()
    default = _KICAD_CLI_DEFAULTS.get(system, "kicad-cli")

    # On Windows, expand the {username} placeholder
    if system == "Windows":
        default = default.format(username=os.environ.get("USERNAME", "user"))

    return default


def check_kicad_cli() -> tuple[bool, str]:
    """Check whether kicad-cli is available and return (available, path)."""
    path = get_kicad_cli_path()
    # For absolute paths, check file existence; for bare commands check PATH
    if os.path.isabs(path):
        available = os.path.isfile(path)
    else:
        available = shutil.which(path) is not None
    return available, path


# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------
SUPPORTED_INPUT_EXTENSIONS = {".kicad_sch", ".net"}
SUPPORTED_OUTPUT_EXTENSIONS = {".json"}  # STPA JSON output


# ---------------------------------------------------------------------------
# ANSI colour helpers (no external deps)
# ---------------------------------------------------------------------------
def _c(text, code):
    """Wrap text in an ANSI colour code if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

def green(t):  return _c(t, "32")
def yellow(t): return _c(t, "33")
def red(t):    return _c(t, "31")
def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "36")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
class Session:
    """Holds all mutable state for the current REPL session."""

    def __init__(self):
        self.input_path: str | None = None          # path to loaded file
        self.net_path: str | None = None            # path to .net (after conversion)
        self.output_dir: str | None = None          # output directory
        self.components: list[dict] = []            # parsed component list
        self.excluded: set[str] = set()             # refs excluded by user
        self.stpa_data: dict | None = None          # STPA JSON built so far
        self.new_hardware: list[str] = []           # newly detected hardware refs
        self.ocr_ran: bool = False                  # whether runocr was called
        self.force_overwrite: bool = False          # -f / --force flag

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
        lines.append(bold("──────────────────────────────────────────"))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_help(args: list[str], session: Session) -> None:
    """Display help for all commands or a specific command."""
    commands = {
        "load": (
            "load <file>",
            "Load a .kicad_sch or .net file. Parses components, runs netlist_parser,\n"
            "    and checks for new hardware automatically."
        ),
        "components": (
            "components",
            "List all parsed components. Shows ref, value, and description.\n"
            "    Components marked [EXCLUDED] will be skipped during run."
        ),
        "exclude": (
            "exclude <ref> [ref ...]",
            "Exclude one or more components by reference designator (e.g. U307 R306).\n"
            "    Excluded components are skipped in pipeline output."
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
            "Show current session state: loaded file, output dir, component counts, etc."
        ),
        "runocr": (
            "runocr",
            "Run OCR on datasheets for newly detected hardware components.\n"
            "    WARNING: This is slow. Requires new hardware to have been detected on load."
        ),
        "run": (
            "run",
            "Run the full pipeline: generate filtered .net + STPA JSON.\n"
            "    RAG/LLM analysis is not yet integrated (Sprint 3)."
        ),
        "newhardware": (
            "newhardware",
            "Show components detected as new hardware since last load."
        ),
        "clear": (
            "clear",
            "Reset the session (clears loaded file, components, exclusions, etc.)."
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
        cmd = args[0].lower()
        if cmd in commands:
            usage, desc = commands[cmd]
            print(f"\n  {bold(usage)}")
            print(f"    {desc}\n")
        else:
            print(red(f"  Unknown command: '{cmd}'. Type 'help' for a list."))
        return

    print(f"\n{bold('ai-hva — Hardware Vulnerability Analysis CLI')}")
    print(f"  Pipeline: load → [exclude] → runocr → run\n")
    print(bold("  Commands:"))
    for name, (usage, desc) in commands.items():
        short_desc = desc.split("\n")[0]
        print(f"    {cyan(usage):<32}  {short_desc}")
    print()


def cmd_load(args: list[str], session: Session) -> None:
    """Load a .kicad_sch or .net file and run through sprint-1 pipeline."""
    if not args:
        print(red("  Usage: load <file_path>"))
        return

    # Join args in case of spaces in path
    raw_path = " ".join(args)

    # Expand ~ and normalize path
    filepath = Path(raw_path).expanduser().resolve()

    # --- Validate file exists ---
    if not filepath.is_file():
        print(red(f"  Error: File not found: '{filepath}'"))
        return

    # --- Validate extension ---
    ext = filepath.suffix.lower()
    if ext not in SUPPORTED_INPUT_EXTENSIONS:
        print(red(f"  Error: Unsupported file type '{ext}'. "
                  f"Supported: {', '.join(SUPPORTED_INPUT_EXTENSIONS)}"))
        return

    print(f"  Loading {cyan(str(filepath))} ...")

    # --- If .kicad_sch, convert to .net via kicad-cli ---
    if ext == ".kicad_sch":
        kicad_ok, kicad_path = check_kicad_cli()
        if not kicad_ok:
            print(red(f"  Error: kicad-cli not found at '{kicad_path}'."))
            print(yellow("  Set KICAD_CLI_PATH in your environment or config.env, e.g.:"))
            print(yellow(r"    Windows: KICAD_CLI_PATH=C:\Users\YOU\AppData\Local\Programs\KiCad\9.0\bin\kicad-cli.exe"))
            print(yellow("    macOS:   KICAD_CLI_PATH=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))
            print(yellow("    Linux:   KICAD_CLI_PATH=kicad-cli"))
            print(yellow("  Tip: You can also load a pre-exported .net file directly."))
            return

        net_path = "result.net"
        try:
            result = subprocess.run(
                [kicad_path, "sch", "export", "netlist", str(filepath)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(yellow(f"  Warning: kicad-cli exited with code {result.returncode}."))
                if result.stderr:
                    print(yellow(f"  {result.stderr.strip()}"))
                net_path = None
            elif os.path.isfile(net_path):
                print(green(f"  Converted to netlist: {net_path}"))
            else:
                print(yellow("  Warning: kicad-cli ran but no .net file was produced."))
                net_path = None
        except Exception as e:
            print(yellow(f"  Warning: kicad-cli conversion failed ({e})."))
            print(yellow("  Tip: Try loading a pre-exported .net file directly."))
            net_path = None

        session.net_path = net_path
    else:
        session.net_path = str(filepath)

    session.input_path = str(filepath)

    # --- Parse components ---
    if session.net_path and HAS_INFO_COMPRESS:
        try:
            ic = InfoCompressor()
            raw_comps = ic.essential_list_netlist(session.net_path)
            # raw_comps is list of (name, desc) tuples from kinparse libparts
            # We also want full component data; use netlist_parser for that
            session.components = []
        except Exception as e:
            print(yellow(f"  Warning: Could not parse essential component list ({e})"))
            raw_comps = []

    # Use netlist_parser for richer component data
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
            print(green(f"  Parsed {len(session.components)} components."))
        except Exception as e:
            print(red(f"  Error parsing netlist: {e}"))
            return
    elif session.net_path is None:
        print(yellow("  Could not parse components — no valid .net file available."))
        return

    # --- Detect new hardware ---
    if HAS_DETECT_HW and session.net_path:
        db_path = "component_db.json"
        try:
            report = detect_new_hardware(session.net_path, db_path)
            session.new_hardware = report.get("new_components", [])
            if session.new_hardware:
                print(yellow(f"  ⚠  New hardware detected: "
                             f"{', '.join(session.new_hardware)}"))
                print(yellow(f"     Run 'runocr' to process their datasheets, "
                             f"or 'newhardware' to review."))
            else:
                print(green("  No new hardware detected."))
        except Exception as e:
            print(yellow(f"  Warning: Hardware detection failed ({e})"))

    print(green(f"\n  ✓ Load complete. Type 'components' to review, "
                f"'exclude' to filter, then 'run'."))


def cmd_components(args: list[str], session: Session) -> None:
    """List all parsed components."""
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
    """Exclude components by reference designator."""
    if not args:
        print(red("  Usage: exclude <ref> [ref ...]"))
        return
    if not session.components:
        print(yellow("  No components loaded. Use 'load <file>' first."))
        return

    valid_refs = {c["ref"] for c in session.components}
    added = []
    not_found = []

    for ref in args:
        ref = ref.upper().strip(",")
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
    """Re-include previously excluded components."""
    if not args:
        print(red("  Usage: include <ref> [ref ...]"))
        return

    removed = []
    not_excluded = []

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
    """Set the output directory."""
    if not args:
        print(red("  Usage: setoutput <directory>"))
        return

    dirpath = args[0]

    if os.path.isfile(dirpath):
        print(red(f"  Error: '{dirpath}' is a file, not a directory. "
                  "Please specify a directory path."))
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
    """Show current session state."""
    print()
    print(session.summary())


def cmd_newhardware(args: list[str], session: Session) -> None:
    """Show newly detected hardware components."""
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
    """Run OCR on datasheets for new hardware components."""
    if not session.input_path:
        print(yellow("  No file loaded. Use 'load <file>' first."))
        return

    if not session.new_hardware:
        print(yellow("  No new hardware to process. "
                     "OCR is most useful when new hardware is detected."))
        confirm = input("  Run OCR anyway on all components? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted.")
            return

    if not HAS_OCR:
        print(red("  Error: OCR module (combinedOCRProcessor) not available."))
        print(red("  Ensure Florence-2 model and dependencies are installed."))
        return

    print(yellow("  ⚠  OCR is slow and may take several minutes per document."))
    confirm = input("  Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("  Aborted.")
        return

    targets = session.new_hardware if session.new_hardware else [
        c["ref"] for c in session.included_components
    ]

    print(f"\n  Running OCR on {len(targets)} component(s)...\n")
    processor = CombinedOCRProcessor()

    for ref in targets:
        comp = next((c for c in session.components if c["ref"] == ref), {})
        desc = comp.get("desc", "")
        print(f"  Processing {cyan(ref)} ({desc}) ...")
        # In a full integration, we'd retrieve the PDF URL and pass it here.
        # For now we signal what would happen.
        print(yellow(f"    → PDF retrieval + OCR for '{ref}' not yet fully wired. "
                     "Stub complete."))

    session.ocr_ran = True
    print(green("\n  ✓ OCR step complete (stub). Results would feed into RAG pipeline."))


def cmd_run(args: list[str], session: Session) -> None:
    """Run the pipeline and save output."""
    if not session.input_path:
        print(yellow("  No file loaded. Use 'load <file>' first."))
        return

    if not session.output_dir:
        print(yellow("  No output directory set. Use 'setoutput <directory>' first."))
        return

    if not session.stpa_data:
        print(yellow("  No parsed data available. Try reloading with 'load <file>'."))
        return

    # --- Apply exclusions to STPA data ---
    stpa = dict(session.stpa_data)
    if session.excluded:
        stpa["components"] = {
            k: v for k, v in stpa.get("components", {}).items()
            if k not in session.excluded
        }
        # Also filter connection pairs that involve excluded components
        stpa["connection_pairs"] = {
            k: v for k, v in stpa.get("connection_pairs", {}).items()
            if not any(ep in session.excluded for ep in v.get("endpoints", []))
        }
        stpa["connection_details"] = {
            k: v for k, v in stpa.get("connection_details", {}).items()
            if k in stpa["connection_pairs"]
        }
        print(f"  Applied exclusions: {', '.join(session.excluded)}")

    # --- Determine output path ---
    input_stem = Path(session.input_path).stem
    output_filename = f"{input_stem}_stpa.json"
    output_path = os.path.join(session.output_dir, output_filename)

    # --- Handle overwrite ---
    if os.path.exists(output_path) and not session.force_overwrite:
        confirm = input(f"  '{output_path}' already exists. Overwrite? [y/N] ").strip().lower()
        if confirm != "y":
            print("  Aborted. Use 'setoutput' to choose a different directory.")
            return

    # --- Write STPA JSON ---
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stpa, f, indent=2)
        print(green(f"  ✓ STPA JSON saved to: {output_path}"))
    except OSError as e:
        print(red(f"  Error writing output: {e}"))
        return

    # --- RAG/LLM step (not yet integrated) ---
    print()
    print(yellow("  ── RAG / LLM Analysis ─────────────────────────"))
    print(yellow("  ⚠  RAG analysis not yet integrated (Sprint 3)."))
    print(yellow("     When complete, this step will:"))
    print(yellow("       5. Encode OCR text via embedding model"))
    print(yellow("       6. Query vector DB (RAG) for each component"))
    print(yellow("       7. Use LLM to populate remaining STPA fields"))
    print(yellow("  ────────────────────────────────────────────────"))
    print()
    print(green("  ✓ Run complete. Pipeline output saved."))


def cmd_clear(args: list[str], session: Session) -> None:
    """Reset the session."""
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
    """Start the interactive REPL."""
    print(BANNER)

    while True:
        try:
            raw = input(f"{cyan('ai-hva')}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print(green("  Goodbye!"))
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit"):
            print(green("  Goodbye!"))
            break

        if cmd in COMMANDS:
            try:
                COMMANDS[cmd](args, session)
            except Exception as e:
                print(red(f"  Unexpected error in '{cmd}': {e}"))
                print(red("  If this persists, please file a bug report."))
        else:
            print(red(f"  Unknown command: '{cmd}'"))
            cmd_help([], session)


# ---------------------------------------------------------------------------
# Entry point (also supports --help for quick non-interactive usage)
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-hva",
        description="AI-Pipeline for Hardware Vulnerability Analysis (CS407 Team 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py                        Start the interactive REPL
  python cli.py --load example.net     Start REPL with file pre-loaded
  python cli.py --load example.net \\
      --output ./results --force       Pre-load, set output, force overwrite
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
    return parser


def main() -> None:
    parser = build_arg_parser()
    cli_args = parser.parse_args()

    session = Session()
    session.force_overwrite = cli_args.force

    # --- Apply any pre-load args ---
    if cli_args.output:
        cmd_setoutput([cli_args.output], session)

    if cli_args.exclude:
        # Components aren't loaded yet; store refs and apply after load
        session.excluded = {r.upper() for r in cli_args.exclude}

    if cli_args.load:
        cmd_load([cli_args.load], session)

    # --- Non-interactive mode: --detect-hardware ---
    if cli_args.detect_hardware:
        if not session.input_path:
            print(red("  Error: --detect-hardware requires --load <file>"))
            sys.exit(1)
        cmd_newhardware([], session)
        sys.exit(0)

    # --- Start REPL ---
    run_repl(session)


if __name__ == "__main__":
    main()