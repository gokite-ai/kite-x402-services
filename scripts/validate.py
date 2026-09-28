#!/usr/bin/env python3
"""
Validate every services/<name>/service.yaml against schema/service.schema.json
plus cross-field rules. Shipped with the python-fastapi template: run with

    just validate

Exit code 0 = all valid, 1 = problems found.
"""

import sys
import json
import yaml
from pathlib import Path
from jsonschema import validate, ValidationError
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "service.schema.json"
SERVICES_DIR = ROOT / "services"


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text())
    cls = validator_for(schema)
    cls.check_schema(schema)

    problems: list[str] = []
    seen_pay_to: dict[str, str] = {}

    if not SERVICES_DIR.is_dir():
        print("No services/ directory — skipping service-manifest validation", file=sys.stderr)
        return 0

    for child in sorted(SERVICES_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        yaml_path = child / "service.yaml"
        where = f"services/{child.name}/service.yaml"

        if not yaml_path.is_file():
            problems.append(f"{where}: missing manifest")
            continue

        try:
            doc = yaml.safe_load(yaml_path.read_text())
        except yaml.YAMLError as exc:
            problems.append(f"{where}: YAML error: {exc}")
            continue

        try:
            validate(instance=doc, schema=schema, cls=cls)
        except ValidationError as exc:
            problems.append(f"{where}: {exc.message}")
            continue

        # Cross-field checks
        if doc["name"] != child.name:
            problems.append(f'{where}: name "{doc["name"]}" must equal directory name "{child.name}"')

        readme = child / "README.md"
        if not readme.is_file():
            problems.append(f"{where}: services/{child.name}/README.md required")

        paths_seen: set[str] = set()
        for ep in doc["endpoints"]:
            key = f'{ep["method"]} {ep["path"]}'
            if key in paths_seen:
                problems.append(f"{where}: duplicate endpoint {key}")
            paths_seen.add(key)

            if doc.get("status", "draft") != "draft" and "example_request" not in ep:
                problems.append(f"{where}: {key} requires example_request when deployed")

        pay_to = doc.get("pay_to", "")
        prev = seen_pay_to.get(pay_to.lower())
        if prev and prev != child.name:
            print(f"note: {where} shares pay_to with services/{prev}", file=sys.stderr)
        seen_pay_to[pay_to.lower()] = child.name

    if problems:
        for p in problems:
            print(f"✗ {p}", file=sys.stderr)
        return 1

    print("✓ all service manifest(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
