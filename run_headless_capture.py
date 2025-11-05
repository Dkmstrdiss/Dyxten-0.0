"""Run the application initialization in headless mode and capture any exception.
This script sets QT_QPA_PLATFORM=offscreen and monkeypatches QApplication.exec_ to
prevent entering the GUI event loop so we can run initialisation code and record
tracebacks without opening UI windows.

Usage:
  .\.venv\Scripts\python.exe run_headless_capture.py

Output:
  - run_exception.txt : contains the full traceback if an exception occurred
  - run_output.txt : stdout/stderr captured during the run
"""
from __future__ import annotations
import os
import sys
import traceback

"""Run the application initialization in headless mode and capture output.

This script launches a child Python process to run the actual import and
initialisation. Running as a subprocess ensures OS-level stdout/stderr (for
example messages emitted by Qt's C++ layer) are captured into files instead
of leaking to the console where Python-level redirection doesn't catch them.

Usage:
  .\.venv\Scripts\python.exe run_headless_capture.py

Outputs:
  - run_output.txt : combined stdout+stderr from the child run
  - run_exception.txt : contains the traceback (or full output) if the child
    process exited with an error code
"""

# Force Qt to use offscreen platform to avoid GUI requirement for the child
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure repo root is on sys.path for child runs
ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

out_file = os.path.join(ROOT, "run_output.txt")
err_file = os.path.join(ROOT, "run_exception.txt")


def _run_child_mode() -> int:
    """Run the initialisation in-process (child mode).

    This mode is intended to be executed by a parent process which captures
    the child's stdout/stderr at the OS level.
    """
    # Monkeypatch QApplication.exec_ to avoid blocking the event loop
    try:
        from PyQt5 import QtWidgets

        def _fake_exec(self, *args, **kwargs):
            return 0

        QtWidgets.QApplication.exec_ = _fake_exec  # type: ignore[attr-defined]
    except Exception:
        # If PyQt5 isn't available the import below will fail and we'll report it
        pass

    try:
        import core.main as m  # type: ignore

        print("Imported core.main OK")
        try:
            rc = m.main()
            print("m.main() returned", rc)
            return int(rc) if isinstance(rc, int) else 0
        except SystemExit as se:
            print("m.main() raised SystemExit:", se)
            # propagate exit code
            try:
                code = int(se.code)  # type: ignore[arg-type]
            except Exception:
                code = 0
            return code
        except Exception:
            traceback.print_exc()
            return 2
    except Exception:
        traceback.print_exc()
        return 3


def _run_parent_mode() -> None:
    """Launch a child Python process and capture its combined output.

    The child is invoked with RUN_AS_CHILD=1 to select the in-process
    initialisation path. The parent's job is to write the child's output to
    `run_output.txt` and, if the child failed, to write details to
    `run_exception.txt`.
    """
    import subprocess

    env = dict(os.environ)
    env["RUN_AS_CHILD"] = "1"
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    proc = subprocess.run([sys.executable, __file__], env=env, capture_output=True, text=True)

    # Always write combined stdout+stderr to run_output.txt for inspection
    combined = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    with open(out_file, "w", encoding="utf-8") as outf:
        outf.write(combined)

    if proc.returncode != 0:
        # Child failed; write the full output into run_exception.txt as well
        with open(err_file, "w", encoding="utf-8") as errf:
            errf.write(combined)
        print("Child process failed; see", err_file)
    else:
        print("Run completed without exception; see", out_file)


if __name__ == "__main__":
    if os.environ.get("RUN_AS_CHILD") == "1":
        rc = _run_child_mode()
        sys.exit(rc)
    else:
        _run_parent_mode()
