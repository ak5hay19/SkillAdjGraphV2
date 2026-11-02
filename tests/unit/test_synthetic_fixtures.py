import json

import yaml


def test_synthetic_fixtures_are_marked_and_fictional(synthetic_dir):
    data = json.loads((synthetic_dir / "qualifications.json").read_text(encoding="utf-8"))
    links = yaml.safe_load((synthetic_dir / "example.yaml").read_text(encoding="utf-8"))
    assert data["synthetic"] is True and links["synthetic"] is True
    codes = [q["code"] for q in data["qualifications"]] + [o["code"] for o in data["occupations"]]
    assert codes and all(c.startswith("TEST/") for c in codes)
