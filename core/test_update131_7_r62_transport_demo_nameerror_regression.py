from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_production_reset_does_not_reference_demo_result_before_seed_runs():
    source = (ROOT / "core" / "system_data.py").read_text()
    reset_block = source[source.index("def reset_all_operational_data"):source.index("def _seed_transport_demo")]
    assert "**transport_demo" not in reset_block
