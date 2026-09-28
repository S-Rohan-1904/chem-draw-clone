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
# stderr noise that is not about the name: the CLI usage banner, and the JVM
# echoing JAVA_TOOL_OPTIONS (set in the Dockerfile) every time it starts.
_NOISE = ("Run the jar using", "Picked up JAVA_TOOL_OPTIONS", "Picked up _JAVA_OPTIONS")
# Seconds to wait for one name. Generous because the first name after a
# restart also pays for JVM start up on a slow CPU.
TIMEOUT_S = float(os.environ.get("CHEM_OPSIN_TIMEOUT", "30"))
_EOF = None  # put on the stdout queue when the process exits


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
        self._lines: queue.Queue[str | None] = queue.Queue()

    def _start(self) -> None:
        self._kill()
        self._proc = subprocess.Popen(
            self._args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        # Fresh queues, so a reader left over from a killed process cannot
        # feed lines into the new one.
        self._errors = queue.Queue()
        self._lines = queue.Queue()
        threading.Thread(target=self._pump_stderr, args=(self._proc, self._errors), daemon=True).start()
        threading.Thread(target=self._pump_stdout, args=(self._proc, self._lines), daemon=True).start()

    @staticmethod
    def _pump_stderr(proc: subprocess.Popen[str], errors: queue.Queue[str]) -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.strip()
            if line and not line.startswith(_NOISE):
                errors.put(line)

    @staticmethod
    def _pump_stdout(proc: subprocess.Popen[str], lines: queue.Queue[str | None]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(_EOF)

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _kill(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.kill()
            self._proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self._proc = None

    def _ask(self, name: str) -> str | None:
        """One output line for ``name``; None if the process is gone. Raises
        TimeoutError (after killing the process) if OPSIN does not answer."""
        assert self._proc and self._proc.stdin
        try:
            self._proc.stdin.write(name + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return None
        try:
            return self._lines.get(timeout=TIMEOUT_S)
        except queue.Empty:
            self._kill()
            raise TimeoutError from None

    def convert(self, name: str) -> tuple[str, str]:
        """Return (smiles, error_text). smiles is '' when OPSIN cannot parse."""
        name = name.replace("\n", " ").replace("\r", " ").strip()
        if not name:
            return "", "Input is empty."
        with self._lock:
            if not self._alive():
                self._start()
            # Drop stale stderr from earlier calls.
            while not self._errors.empty():
                self._errors.get_nowait()
            try:
                line = self._ask(name)
                if line is None:  # process died; restart once and retry
                    self._start()
                    line = self._ask(name)
            except TimeoutError:
                return "", f"OPSIN did not answer within {TIMEOUT_S:g} seconds."
            if line is None:
                return "", "OPSIN is not running."
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
            self._kill()


strict = OpsinProcess()
lenient_stereo = OpsinProcess(("-s",))
