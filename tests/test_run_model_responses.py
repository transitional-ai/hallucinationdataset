from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# These tests exercise manifest and response parsing only. Avoid loading CUDA
# libraries during test collection; model execution imports real torch normally.
sys.modules["torch"] = types.ModuleType("torch")

import run_model_responses as runner  # noqa: E402


def test_pilot_manifest_loads_binary_options() -> None:
    manifest = runner.load_manifest(ROOT / "metadata_examples" / "evaluation_manifest.csv")
    assert len(manifest) == 807
    assert manifest["question_id"].nunique() == 807
    assert manifest["option_C"].eq("").all()
    assert manifest["option_D"].eq("").all()


def test_confidence_is_requested_only_when_required() -> None:
    assert runner.row_requires_confidence(pd.Series({"task": "vhd_ii_hce"}))
    assert not runner.row_requires_confidence(pd.Series({"task": "accuracy"}))
    assert not runner.row_requires_confidence(
        pd.Series({"task": "vhd_ii_hce", "requires_confidence": "no"})
    )


def test_response_parser_accepts_percent_confidence() -> None:
    choice, confidence, status = runner.parse_response(
        '{"choice":"B","confidence_percent":80}', ["A", "B"], True
    )
    assert choice == "B"
    assert confidence == 0.8
    assert status == "json"


def test_response_parser_accepts_choice_only_when_confidence_not_required() -> None:
    choice, confidence, status = runner.parse_response(
        '{"choice":"A"}', ["A", "B"], False
    )
    assert choice == "A"
    assert confidence is None
    assert status == "json"
