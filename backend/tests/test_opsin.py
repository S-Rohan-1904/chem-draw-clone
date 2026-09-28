from app import opsin


def test_hung_process_times_out_and_restarts(monkeypatch):
    p = opsin.OpsinProcess()
    p._args = ["sleep", "60"]  # reads nothing, answers nothing
    monkeypatch.setattr(opsin, "TIMEOUT_S", 0.5)
    smiles, error = p.convert("ethanol")
    assert smiles == "" and "did not answer" in error
    assert p._proc is None  # killed; the next call starts a fresh one


def test_jvm_option_echo_is_not_an_error(monkeypatch):
    # The JVM prints "Picked up JAVA_TOOL_OPTIONS" on start (the Dockerfile
    # sets it); that line used to be glued onto the first failed name's error.
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "-Xss1m")
    p = opsin.OpsinProcess()
    try:
        smiles, error = p.convert("ethnaol")
    finally:
        p.stop()
    assert smiles == "" and "Picked up" not in error and "ethnaol" in error
