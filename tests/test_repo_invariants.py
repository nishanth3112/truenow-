import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# sha256 of the kit files as shipped; the graders use their own copies, so ours must stay untouched.
KIT_SHA256 = {
    "eval/public_eval.jsonl": "b0b14acced7315c5dde48865dd345b1f012d29a6183a42f268d3f6b2220e8ed0",
    "harness/contract.py": "f84bab0b19edefed76112b532d2a39f0669f393f736c42785ec22ff609a3956c",
    "harness/run_eval.py": "09d385654c2fdedb2ec856fd8fd48683e2029cee9708957e99ec2917d1c8e59c",
    "harness/scoring.py": "682a40a23a26e306a61c1bc78643f4d120aa4fdd6f05b35c9fecb9edd72a99de",
    "harness/selftest/conflicts_gold.json": "c414e50b324e3e35be6f98ae72330646a2cb39c1628a3cd02462076ac8f16664",
    "harness/selftest/eval.jsonl": "005232dc0cd72f581a1700ecbc39eb9949a36cfd2b1042c2aa9ed20a90b3ff04",
    "harness/selftest/snapshots/01_2026-01-05_baseline/manifest.json": "cf2e62197406aaa77de6e05cbfc190a3e43380105fe3e5c1d534c399715e1e03",
    "harness/selftest/snapshots/01_2026-01-05_baseline/pages/certificates.md": "ca972b9aabd9c433b2d502b167452359b01bf8147a43f4e682c683fbb1443818",
    "harness/selftest/snapshots/01_2026-01-05_baseline/pages/fees.md": "e8773016587c40f442aec7b3714811375804fa68821a3fbd24ea4d532746d21b",
    "harness/selftest/snapshots/02_2026-03-01_update/manifest.json": "ff0a09f1e7a6e256073fd9c0a4a81a626b617a13c5257fb79bb7005dffd17365",
    "harness/selftest/snapshots/02_2026-03-01_update/pages/certificates.md": "59da5376b8ef4f7bedf500f8a8b919840bdf44840b85920cdcebb708c5730ba4",
    "harness/selftest/snapshots/02_2026-03-01_update/pages/promo.md": "cb542b0585f3c4fa9ec9a274a8cfee6e8543a549da7fb22d1f49e2c405f5ae3e",
}


def _tracked():
    return subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()


def test_kit_files_unchanged():
    files = sorted(
        p
        for d in ("harness", "eval")
        for p in (ROOT / d).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    got = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert got == KIT_SHA256


def test_no_data_tracked():
    bad = re.compile(r"^snapshots/0|^snapshots_zip/|\.zip$|\.pdf$")
    assert [f for f in _tracked() if bad.search(f)] == []


def test_no_pyproject_or_lock():
    assert [f for f in _tracked() if Path(f).name in ("pyproject.toml", "uv.lock")] == []
    assert not (ROOT / "pyproject.toml").exists() and not (ROOT / "uv.lock").exists()
