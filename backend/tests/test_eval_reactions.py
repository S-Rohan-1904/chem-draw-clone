import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("eval_reactions", HERE.parent / "scripts" / "eval_reactions.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def _names(entry, smiles):
    return {r["smiles"]: r["name"] for r in ev._single([{"name": entry, "set": "teaching", "smiles": smiles}])}


def test_entry_names_follow_structures_not_sorted_order():
    # molecules.tsv keeps the sorted SMILES, not the order the entry names them in.
    assert _names(
        "1-chloropropane 2-chloropropane 2-bromopropane 2-bromo-2-methylpropane",
        "CC(C)(C)Br.CC(C)Br.CC(C)Cl.CCCCl",
    ) == {
        "CC(C)(C)Br": "2-bromo-2-methylpropane",
        "CC(C)Br": "2-bromopropane",
        "CC(C)Cl": "2-chloropropane",
        "CCCCl": "1-chloropropane",
    }


def test_names_with_spaces_and_unnamed_parts():
    assert _names("acetic acid formic acid", "CC(=O)O.O=CO") == {"CC(=O)O": "acetic acid", "O=CO": "formic acid"}
    # "sodium" is the metal, not the ion, so the ion keeps a numbered entry name.
    assert _names("sodium acetate", "CC(=O)[O-].[Na+]") == {"CC(=O)[O-]": "acetate", "[Na+]": "sodium acetate (2)"}
