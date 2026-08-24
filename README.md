# Multi-Objective Urban Transportation Planning

This repository contains a small educational Operations Research example implemented with Python and Gurobi. The model allocates integer transportation units across routes and time periods while considering three objectives: total travel time, environmental impact, and operating cost.

## Model type

The formulation is a multi-objective integer linear programming model. Gurobi's hierarchical multi-objective mechanism is used:

- Travel time has priority 2.
- Environmental impact has priority 1.
- Operating cost has priority 1.

Therefore, the solver first protects the higher-priority travel-time objective. The two lower-priority objectives are then optimized at the same priority level with equal weights.

## Decision variable

`x[route, period]` is the integer number of transportation units assigned to a route in a time period.

## Parameters

For each route and time period, the example defines:

- travel time per transportation unit,
- environmental impact per transportation unit,
- operating cost per transportation unit,
- minimum transportation demand.

The model also includes a total budget and a maximum permitted environmental-impact level.

## Constraints

The model imposes the following requirements:

1. Total operating cost cannot exceed the budget.
2. Total environmental impact cannot exceed the specified limit.
3. The allocation for each route and time period must satisfy at least the specified demand.
4. Allocations are non-negative integers.

## Important modeling note

This repository is intentionally small and designed for teaching. All three objective coefficients are positive and each decision variable is bounded below by demand. As a result, increasing an allocation above its demand increases all three objective values. For the supplied sample data, the optimal allocation therefore occurs at the demand lower bounds.

This behavior is mathematically consistent with the formulation, but it also means that the sample model does not generate substantial trade-offs among competing transportation policies. A more realistic urban transportation model could add service-capacity relations, congestion effects, route-choice variables, fleet limits, fixed investment decisions, equity requirements, or alternative technologies.

## Requirements

- Python 3
- `gurobipy`
- A valid Gurobi license

Install the Python dependency with:

```bash
pip install -r requirements.txt
```

## Run

```bash
python urban_transportation_planning.py
```

With the sample data, the allocation is:

- Route1, Morning: 2
- Route1, Evening: 3
- Route2, Morning: 3
- Route2, Evening: 4
- Route3, Morning: 4
- Route3, Evening: 5

The corresponding totals are:

- Travel time: 247
- Environmental impact: 142
- Cost: 2470

## Educational scope

The repository is intended as a compact example for Operations Research courses, especially topics related to integer programming and multi-objective optimization with Gurobi.

## License

This project is distributed under a custom non-commercial license. Commercial use requires prior written permission from the copyright holder. See `LICENSE` for the complete terms.
