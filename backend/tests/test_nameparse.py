from app.chem import build
from app.nameparse import breakdown, tokenize


def kinds(name):
    return [(t["kind"], t["text"]) for t in tokenize(name) if t["kind"] != "sep"]


def test_tokens_basic():
    assert kinds("2-methylbut-2-ene") == [("locant", "2"), ("substituent", "methyl"), ("parent", "but"), ("locant", "2"), ("infix", "ene")]
    assert kinds("propanoic acid") == [("parent", "prop"), ("infix", "an"), ("suffix", "oic acid")]
    assert kinds("(2R)-butan-2-ol")[0] == ("stereo", "(2R)")
    assert ("multiplier", "tri") in kinds("2,2,4-trimethylpentane")
    assert kinds("hexane-2,4-dione")[-1] == ("suffix", "dione")
    assert ("locant", "N,N") in kinds("N,N-dimethylaniline")


def test_substituent_atoms_located():
    r = build("2,2,4-trimethylpentane")
    b = breakdown("2,2,4-trimethylpentane", r.smiles)
    methyl = next(t for t in b["tokens"] if t["kind"] == "substituent")
    parent = next(t for t in b["tokens"] if t["kind"] == "parent")
    assert len(methyl["atoms"]) == 3 and len(parent["atoms"]) == 5
    assert not set(methyl["atoms"]) & set(parent["atoms"])
    assert any(l["kind"] == "substituent" for l in b["legend"])


def test_unknown_tokens_marked_other():
    assert ("other", "xyzzy") in kinds("xyzzyethane")
