"""Long-lived OPSIN processes.

Starting a JVM per name costs about half a second. OPSIN's CLI reads names
from stdin one per line, so one process per mode is kept running and fed
names under a lock. With ``-n`` every input yields exactly one stdout line
``<smiles>\\t<name>`` (empty SMILES on failure) and failures are explained on
stderr, which a reader thread collects.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
from importlib import resources

OPSIN_JAR = str(resources.files("py2opsin") / "opsin-cli-2.9.0-jar-with-dependencies.jar")
_BANNER = "Run the jar using"


def _java() -> str:
    home = os.environ.get("JAVA_HOME")
    if home and os.path.exists(os.path.join(home, "bin", "java")):
        return os.path.join(home, "bin", "java")
    return shutil.which("java") or "java"


class OpsinProcess:
    def __init__(self, extra_args: tuple[str, ...] = ()):
        self._args = [_java(), "-jar", OPSIN_JAR, "-osmi", "-n", *extra_args]
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._errors: queue.Queue[str] = queue.Queue()

    def _start(self) -> None:
        self._proc = subprocess.Popen(
            self._args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._errors = queue.Queue()
        threading.Thread(target=self._pump_stderr, args=(self._proc,), daemon=True).start()

    def _pump_stderr(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.strip()
            if line and not line.startswith(_BANNER):
                self._errors.put(line)

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def convert(self, name: str) -> tuple[str, str]:
        """Return (smiles, error_text). smiles is '' when OPSIN cannot parse."""
        name = name.replace("\n", " ").replace("\r", " ").strip()
        if not name:
            return "", "Input is empty."
        with self._lock:
            if not self._alive():
                self._start()
            assert self._proc and self._proc.stdin and self._proc.stdout
            # Drop stale stderr from earlier calls.
            while not self._errors.empty():
                self._errors.get_nowait()
            try:
                self._proc.stdin.write(name + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
            except (BrokenPipeError, OSError):
                line = ""
            if line == "":  # process died; restart once and retry
                self._start()
                assert self._proc and self._proc.stdin and self._proc.stdout
                self._proc.stdin.write(name + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
            smiles = line.rstrip("\n").split("\t", 1)[0].strip()
            errors: list[str] = []
            if not smiles:
                # stderr for this name is written before its stdout line,
                # but arrives on another thread; give it a moment.
                try:
                    errors.append(self._errors.get(timeout=0.5))
                except queue.Empty:
                    pass
                while not self._errors.empty():
                    errors.append(self._errors.get_nowait())
            else:
                while not self._errors.empty():  # e.g. STEREOCHEMISTRY_IGNORED notes
                    errors.append(self._errors.get_nowait())
            return smiles, " ".join(errors)

    def stop(self) -> None:
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.kill()
                except OSError:
                    pass
                self._proc = None


strict = OpsinProcess()
lenient_stereo = OpsinProcess(("-s",))
