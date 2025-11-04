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

# Force Qt to use offscreen platform to avoid GUI requirement
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure repo root is on sys.path
ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Monkeypatch QApplication.exec_ to avoid blocking
try:
    from PyQt5 import QtWidgets
    _orig_exec = getattr(QtWidgets.QApplication, 'exec_', None)
    def _fake_exec(self, *args, **kwargs):
        # keep the app alive briefly, then return
        return 0
    QtWidgets.QApplication.exec_ = _fake_exec  # type: ignore[attr-defined]
except Exception:
    pass

out_file = os.path.join(ROOT, 'run_output.txt')
err_file = os.path.join(ROOT, 'run_exception.txt')

with open(out_file, 'w', encoding='utf-8') as outf, open(err_file, 'w', encoding='utf-8') as errf:
    try:
        # Redirect stdout/stderr to file while running
        _old_stdout, _old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = outf, outf
        try:
            import core.main as m
            print('Imported core.main OK')
            try:
                # call main() which will create app and windows but won't block
                m.main()
                print('m.main() returned normally')
            except SystemExit as se:
                print('m.main() raised SystemExit:', se)
            except Exception as e:
                print('m.main() raised exception:', type(e), e)
                raise
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout, sys.stderr = _old_stdout, _old_stderr
    except Exception:
        traceback.print_exc(file=errf)
        # also print a short message to console
        print('Exception captured and written to', err_file)
    else:
        print('Run completed without exception; see', out_file)
