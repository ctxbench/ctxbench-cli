from __future__ import annotations

import argparse
import sys

from copa.commands.eval import eval_command
from copa.commands.experiment import expand_experiment, validate_experiment
from copa.commands.run import run_command
from copa.util.logging import PhaseLogger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="copa", description="COPA benchmark CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    experiment_parser = subparsers.add_parser("experiment", help="Experiment commands")
    experiment_subparsers = experiment_parser.add_subparsers(dest="experiment_command", required=True)

    validate_parser = experiment_subparsers.add_parser(
        "validate", help="Validate an experiment file"
    )
    validate_parser.add_argument("path", help="Path to the experiment JSON file")
    validate_parser.set_defaults(func=lambda args: validate_experiment(args.path))

    expand_parser = experiment_subparsers.add_parser(
        "expand", help="Expand an experiment into runspec files"
    )
    expand_parser.add_argument("path", help="Path to the experiment JSON file")
    expand_parser.add_argument("--out", help="Directory to write runspec JSON files")
    expand_parser.add_argument("--jsonl", help="Optional JSONL file for all runspecs")
    expand_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    expand_parser.add_argument("--progress", action="store_true", help="Show batch progress")
    expand_parser.set_defaults(
        func=lambda args: expand_experiment(
            args.path,
            out_dir=args.out,
            jsonl_path=args.jsonl,
            verbose=args.verbose,
            progress=args.progress,
        )
    )

    run_parser = subparsers.add_parser("run", help="Run one or many runspecs")
    run_parser.add_argument("path", help="RunSpec JSON file, directory, or JSONL file")
    run_parser.add_argument("--out", help="Directory to write result JSON files")
    run_parser.add_argument("--jsonl", help="Optional JSONL file for run results")
    run_parser.add_argument("--force", action="store_true", help="Re-execute runs even when result artifacts already exist")
    run_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    run_parser.add_argument("--progress", action="store_true", help="Show batch progress")
    run_parser.set_defaults(
        func=lambda args: run_command(
            args.path,
            out_dir=args.out,
            jsonl_path=args.jsonl,
            force=args.force,
            verbose=args.verbose,
            progress=args.progress,
        )
    )

    eval_parser = subparsers.add_parser("eval", help="Evaluate one or many run results")
    eval_inputs = eval_parser.add_mutually_exclusive_group(required=True)
    eval_inputs.add_argument("--run-results-dir", help="Directory containing run result JSON files")
    eval_inputs.add_argument("--run-results-json", help="Run result JSON or JSONL file")
    eval_parser.add_argument("--experiment", required=True, help="Experiment JSON file")
    eval_parser.add_argument("--output-dir", help="Directory to write evaluation JSON files")
    eval_parser.add_argument("--output-jsonl", help="Optional JSONL file for flattened evaluation rows")
    eval_parser.add_argument("--output-csv", help="Optional CSV file for flattened evaluation rows")
    eval_parser.add_argument("--only", help="Evaluate only one question id")
    eval_parser.add_argument(
        "--mode",
        choices=["heuristic", "judge"],
        help="Evaluate only one evaluation mode",
    )
    eval_parser.add_argument("--continue-on-error", action="store_true", help="Keep evaluating after an item error")
    eval_parser.add_argument("--fail-on-missing-gold", action="store_true", help="Fail when exact-mode gold data is missing")
    eval_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    eval_parser.add_argument("--progress", action="store_true", help="Show batch progress")
    eval_parser.set_defaults(
        func=lambda args: eval_command(
            run_results_dir=args.run_results_dir,
            run_results_json=args.run_results_json,
            experiment_path=args.experiment,
            output_dir=args.output_dir,
            output_jsonl=args.output_jsonl,
            output_csv=args.output_csv,
            only=args.only,
            mode=args.mode,
            continue_on_error=args.continue_on_error,
            fail_on_missing_gold=args.fail_on_missing_gold,
            verbose=args.verbose,
            progress=args.progress,
        )
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        PhaseLogger(stream=sys.stderr).error(str(exc), code=1)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
