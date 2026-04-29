from __future__ import annotations

import argparse
import sys

from copa.commands.eval import eval_command
from copa.commands.experiment import expand_experiment, validate_experiment
from copa.commands.run import run_command
from copa.benchmark.selectors import RunSelector
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
    _add_selector_arguments(run_parser, include_status=False)
    run_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    run_parser.add_argument("--progress", action="store_true", help="Show batch progress")
    run_parser.set_defaults(
        func=lambda args: run_command(
            args.path,
            out_dir=args.out,
            jsonl_path=args.jsonl,
            force=args.force,
            selector=_selector_from_args(args),
            verbose=args.verbose,
            progress=args.progress,
        )
    )

    eval_parser = subparsers.add_parser("eval", help="Evaluate one or many run results")
    eval_inputs = eval_parser.add_mutually_exclusive_group(required=True)
    eval_inputs.add_argument("--run-dir", help="Directory containing run result JSON files")
    eval_inputs.add_argument("--run-jsonl", help="Run result JSON or JSONL file")
    eval_parser.add_argument("--output-dir", help="Directory to write evaluation JSON files")
    eval_parser.add_argument("--output-jsonl", help="Optional JSONL file for flattened evaluation rows")
    eval_parser.add_argument("--output-csv", help="Optional CSV file for flattened evaluation rows")
    eval_parser.add_argument("--force", action="store_true", help="Re-evaluate runs even when evaluation artifacts already exist")
    eval_parser.add_argument("--only", help="Evaluate only one question id")
    _add_selector_arguments(eval_parser, include_status=True)
    eval_parser.add_argument(
        "--mode",
        choices=["judge"],
        help="Evaluate only one evaluation mode",
    )
    eval_parser.add_argument("--continue-on-error", action="store_true", help="Keep evaluating after an item error")
    eval_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    eval_parser.add_argument("--progress", action="store_true", help="Show batch progress")
    eval_parser.set_defaults(
        func=lambda args: eval_command(
            run_dir=args.run_dir,
            run_jsonl=args.run_jsonl,
            output_dir=args.output_dir,
            output_jsonl=args.output_jsonl,
            output_csv=args.output_csv,
            force=args.force,
            only=args.only,
            mode=args.mode,
            selector=_selector_from_args(args),
            continue_on_error=args.continue_on_error,
            verbose=args.verbose,
            progress=args.progress,
        )
    )

    return parser


def _add_selector_arguments(parser: argparse.ArgumentParser, *, include_status: bool) -> None:
    parser.add_argument("--provider", help="Filter by provider")
    parser.add_argument("--model", help="Filter by model id or model name")
    parser.add_argument("--instance", help="Filter by instance id")
    parser.add_argument("--question", help="Filter by question id")
    parser.add_argument("--strategy", help="Filter by strategy")
    parser.add_argument("--format", help="Filter by context format")
    parser.add_argument("--repeat", type=int, help="Filter by repeat index")
    parser.add_argument("--exclude-provider", action="append", default=[], help="Exclude by provider")
    parser.add_argument("--exclude-model", action="append", default=[], help="Exclude by model id or model name")
    parser.add_argument("--exclude-instance", action="append", default=[], help="Exclude by instance id")
    parser.add_argument("--exclude-question", action="append", default=[], help="Exclude by question id")
    parser.add_argument("--exclude-strategy", action="append", default=[], help="Exclude by strategy")
    parser.add_argument("--exclude-format", action="append", default=[], help="Exclude by context format")
    parser.add_argument("--exclude-repeat", action="append", type=int, default=[], help="Exclude by repeat index")
    if include_status:
        parser.add_argument("--status", help="Filter by run status")
        parser.add_argument("--exclude-status", action="append", default=[], help="Exclude by run status")


def _selector_from_args(args: argparse.Namespace) -> RunSelector:
    return RunSelector(
        provider=getattr(args, "provider", None),
        model=getattr(args, "model", None),
        instance=getattr(args, "instance", None),
        question=getattr(args, "question", None),
        strategy=getattr(args, "strategy", None),
        format=getattr(args, "format", None),
        repeat=getattr(args, "repeat", None),
        status=getattr(args, "status", None),
        exclude_provider=tuple(getattr(args, "exclude_provider", []) or ()),
        exclude_model=tuple(getattr(args, "exclude_model", []) or ()),
        exclude_instance=tuple(getattr(args, "exclude_instance", []) or ()),
        exclude_question=tuple(getattr(args, "exclude_question", []) or ()),
        exclude_strategy=tuple(getattr(args, "exclude_strategy", []) or ()),
        exclude_format=tuple(getattr(args, "exclude_format", []) or ()),
        exclude_repeat=tuple(getattr(args, "exclude_repeat", []) or ()),
        exclude_status=tuple(getattr(args, "exclude_status", []) or ()),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        PhaseLogger(stream=sys.stderr).error("Execution interrupted", code=130)
        return 130
    except Exception as exc:
        PhaseLogger(stream=sys.stderr).error(str(exc), code=1)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
