from __future__ import annotations

import argparse
from pathlib import Path

import pulp

from data_loader import load_data
from model import build_model
from submission import build_submission
from validation import assert_valid_submission


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Solve the multi-year fleet decarbonization MILP and write a validated CSV submission."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing the required CSV input files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("optimized_submission.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=None,
        help="Optional CBC solver time limit in seconds.",
    )
    parser.add_argument(
        "--mip-gap",
        type=float,
        default=None,
        help="Optional relative MIP gap for CBC, for example 0.005.",
    )
    parser.add_argument(
        "--solver-log",
        action="store_true",
        help="Show CBC solver output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data = load_data(args.data_dir)
    artifacts = build_model(data)

    solver = pulp.PULP_CBC_CMD(
        msg=args.solver_log,
        timeLimit=args.time_limit,
        gapRel=args.mip_gap,
    )

    artifacts.problem.solve(solver)

    status = pulp.LpStatus[artifacts.problem.status]
    print(f"Solver status: {status}")

    if status not in {"Optimal", "Integer Feasible"}:
        raise RuntimeError(
            "The solver did not return a usable integer solution. "
            f"Status: {status}. Do not attempt to read variable values from an infeasible/undefined model."
        )

    objective_value = pulp.value(artifacts.problem.objective)
    if objective_value is not None:
        print(f"Objective value: {objective_value:,.2f}")

    submission = build_submission(data, artifacts)
    assert_valid_submission(data, submission)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(args.output, index=False)

    print(f"Validated submission written to: {args.output}")
    print(f"Rows: {len(submission)}")


if __name__ == "__main__":
    main()
