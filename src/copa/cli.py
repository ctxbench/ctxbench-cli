import argparse
import itertools
import json
from pathlib import Path


SCHEMAS = {
    "plan": "plan.schema.json",
    "runspec": "runspec.schema.json",
}


def _schemas_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_schema(kind: str) -> dict:
    if kind not in SCHEMAS:
        raise ValueError(f"Unknown schema kind: {kind}")
    schema_path = _schemas_dir() / SCHEMAS[kind]
    return _load_json(schema_path)


def _validator(schema: dict):
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError(
            "jsonschema is required for validation; add it to your environment."
        ) from exc
    return jsonschema.Draft202012Validator(schema)


def _validate_json(doc: dict, schema: dict, label: str) -> int:
    validator = _validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda err: err.path)
    if errors:
        print(f"{label}: invalid")
        for err in errors:
            path = ".".join(str(part) for part in err.path)
            location = f" at {path}" if path else ""
            print(f"  -{location}: {err.message}")
        return 1
    print(f"{label}: valid")
    return 0


def _list_schemas(_: argparse.Namespace) -> int:
    schemas_dir = _schemas_dir()
    print("Available schemas:")
    for kind, filename in SCHEMAS.items():
        print(f"  - {kind}: {schemas_dir / filename}")
    return 0


def _sanitize_strategy(level: dict) -> dict:
    allowed = {"type", "representation", "config"}
    return {key: value for key, value in level.items() if key in allowed}


def _sanitize_model(level: dict, defaults: dict | None) -> dict:
    allowed = {"provider", "model"}
    model = {key: value for key, value in level.items() if key in allowed}
    if defaults:
        model["params"] = defaults
    return model


def _plan_to_runspecs(plan: dict) -> list[dict]:
    factors = plan.get("factors", {})
    if "models" not in factors or "strategies" not in factors:
        raise ValueError("Plan must define factors.models and factors.strategies.")

    selection = plan.get("selection", {})
    task_ids = selection.get("taskIds") or []
    instance_ids = selection.get("instanceIds") or []
    if not task_ids or not instance_ids:
        raise ValueError(
            "Plan selection must include taskIds and instanceIds to build runspecs."
        )

    defaults = plan.get("defaults", {})
    model_defaults = defaults.get("modelParams")
    budgets = defaults.get("budgets", {})
    tool_provider = defaults.get("toolProvider")
    retrieval = defaults.get("retrieval")

    factor_names = list(factors.keys())
    factor_levels = [factors[name]["levels"] for name in factor_names]

    suite = plan["suite"]
    repeats = int(plan.get("repeats", 1))
    plan_id = plan["planId"]
    schema_version = plan["schemaVersion"]

    runspecs: list[dict] = []
    counter = 1
    for task_id, instance_id in itertools.product(task_ids, instance_ids):
        for levels in itertools.product(*factor_levels):
            for repeat_index in range(1, repeats + 1):
                factor_level_map = {
                    name: level for name, level in zip(factor_names, levels)
                }
                model_level = factor_level_map["models"]
                strategy_level = factor_level_map["strategies"]

                runspec = {
                    "kind": "copa.runspec",
                    "schemaVersion": schema_version,
                    "runspecId": f"{plan_id}-{counter:05d}",
                    "suite": {"id": suite["id"], "version": suite["version"]},
                    "task": {"id": task_id},
                    "instance": {
                        "id": instance_id,
                        "inputs": {
                            "question": {"id": instance_id, "text": instance_id},
                            "artifacts": [],
                        },
                    },
                    "strategy": _sanitize_strategy(strategy_level),
                    "model": _sanitize_model(model_level, model_defaults),
                    "budgets": budgets,
                    "factorLevels": factor_level_map,
                    "provenance": {"createdFromPlanId": plan_id},
                }
                if tool_provider:
                    runspec["toolProvider"] = tool_provider
                if retrieval:
                    runspec["retrieval"] = retrieval
                if repeats > 1:
                    runspec["repeat"] = {"index": repeat_index}
                runspecs.append(runspec)
                counter += 1
    return runspecs


def _handle_validate(args: argparse.Namespace) -> int:
    schema = _load_schema(args.kind)
    doc = _load_json(Path(args.path))
    return _validate_json(doc, schema, args.path)


def _handle_plan(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    plan = _load_json(plan_path)

    try:
        if _validate_json(plan, _load_schema("plan"), str(plan_path)) != 0:
            return 1
    except RuntimeError as exc:
        print(str(exc))
        return 2

    try:
        runspecs = _plan_to_runspecs(plan)
    except ValueError as exc:
        print(f"Plan error: {exc}")
        return 1

    output_dir = Path(args.out_dir or plan.get("recording", {}).get("outputDir", ""))
    if not output_dir:
        print(
            "Plan output directory not provided and plan.recording.outputDir missing."
        )
        return 1
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, runspec in enumerate(runspecs, start=1):
        filename = output_dir / f"runspec-{index:05d}.json"
        with filename.open("w", encoding="utf-8") as handle:
            json.dump(runspec, handle, indent=2, sort_keys=True)
            handle.write("\n")

    print(f"Wrote {len(runspecs)} runspec(s) to {output_dir}")
    return 0


def _handle_run(args: argparse.Namespace) -> int:
    schema = _load_schema("runspec")
    exit_code = 0
    for path in args.runspecs:
        doc = _load_json(Path(path))
        try:
            exit_code |= _validate_json(doc, schema, path)
        except RuntimeError as exc:
            print(str(exc))
            return 2
    if exit_code == 0:
        print(f"Validated {len(args.runspecs)} runspec(s). Execution not implemented.")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="copa",
        description=("COPA Bench CLI. Validate, expand plans and run benchmark specs."),
        epilog=(
            "Examples:\n"
            "  copa list\n"
            "  copa validate plan path/to/plan.json\n"
            "  copa plan --plan path/to/plan.json --out-dir runspecs/\n"
            "  copa run path/to/runspec.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available schemas.")
    list_parser.set_defaults(func=_list_schemas)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a JSON document against a schema."
    )
    validate_parser.add_argument(
        "kind", choices=sorted(SCHEMAS.keys()), help="Schema kind to validate against."
    )
    validate_parser.add_argument("path", help="Path to the JSON file.")
    validate_parser.set_defaults(func=_handle_validate)

    plan_parser = subparsers.add_parser("plan", help="Generate runspecs from a plan.")
    plan_parser.add_argument("--plan", required=True, help="Path to the plan JSON.")
    plan_parser.add_argument(
        "--out-dir",
        help="Output directory for runspec files. Defaults to plan.recording.outputDir.",
    )
    plan_parser.set_defaults(func=_handle_plan)

    run_parser = subparsers.add_parser(
        "run", help="Validate runspecs and execute them (not implemented)."
    )
    run_parser.add_argument("runspecs", nargs="+", help="Runspec JSON files to run.")
    run_parser.set_defaults(func=_handle_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
