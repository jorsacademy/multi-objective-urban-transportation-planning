# Intercity Rail Fleet Circulation Optimization

A mixed-integer optimization project for assigning fleet types to scheduled passenger trips and constructing depot-feasible daily vehicle circulations.

The model is intentionally generic. All data are synthetic, and no real or fictional transport operator is referenced.

## Problem

A passenger transport network has a fixed timetable. Each scheduled trip has an origin, destination, departure time, arrival time, passenger demand, and route distance.

Several fleet types are available. Each fleet type has:

- passenger capacity,
- a physical fleet limit,
- a maintenance reserve,
- distance-based operating cost,
- a vehicle activation cost.

Vehicles begin and end the service day at depots. Consecutive trips may be linked directly when they meet at the same station, or through an empty repositioning movement when a feasible deadhead arc exists.

The optimization model decides:

- which fleet type operates each scheduled trip,
- which trips are chained into the same physical vehicle circulation,
- which depot dispatches each circulation,
- which depot receives each circulation at the end of the day,
- when an empty repositioning movement is economically and temporally feasible.

## Decision variables

The model uses binary variables for:

- `x[t,k]`: trip `t` is assigned to fleet type `k`,
- `y[i,j,k]`: a unit of fleet type `k` operates trip `j` immediately after trip `i`,
- `s[d,t,k]`: a circulation of fleet type `k` leaves depot `d` to begin with trip `t`,
- `e[t,d,k]`: a circulation of fleet type `k` ends after trip `t` and returns to depot `d`.

## Core constraints

1. Every scheduled trip is covered exactly once.
2. A fleet type can cover a trip only when passenger capacity is sufficient.
3. Trip-to-trip links must satisfy chronological order and minimum turnaround time.
4. Same-station links require no deadhead movement.
5. Different-station links require an explicitly defined repositioning arc with sufficient travel time.
6. Flow conservation gives each assigned trip exactly one predecessor and one successor in its circulation.
7. Depot dispatches cannot exceed depot-specific inventory.
8. Total active units cannot exceed physical fleet availability after the maintenance reserve is removed.
9. End-of-day depot balance requires each depot to recover, by fleet type, the number of units it dispatched.
10. Depot-to-first-trip and last-trip-to-depot movements must fit inside the service-day horizon.

## Objective

The objective minimizes:

- scheduled operating cost,
- vehicle activation cost,
- empty-seat penalty,
- idle-time penalty,
- deadhead/repositioning distance cost.

This creates a trade-off between using additional physical vehicles and extending existing circulations through feasible repositioning moves.

## Deadhead modeling

A repositioning arc contains:

```text
origin
destination
travel_minutes
distance_km
```

For a connection from trip `i` to trip `j`:

```text
arrival_i + minimum_turnaround + reposition_time <= departure_j
```

If the first trip ends at the origin of the second trip, reposition time and distance are zero.

## Maintenance reserve

The usable number of physical vehicles is:

```text
usable_fleet_k = available_units_k - maintenance_reserve_k
```

The number of circulation starts for fleet type `k` cannot exceed this value.

This is a strategic maintenance-availability representation rather than an individual rolling-stock maintenance scheduling model.

## Solver diagnostics

The example reports:

- optimal objective value,
- total deadhead distance,
- MIP gap,
- MIP node count,
- fleet units used,
- depot starts and returns,
- selected trip-to-trip circulation links.

## Verified synthetic result

The current synthetic instance contains ten scheduled trips, two fleet types, one active depot, and a repositioning network.

Verified output:

```text
Objective: 10,316.54
Deadhead distance: 42.0 km
MIP gap: 0.0
MIP node count: 1

Fleet usage:
FLEET_A: 2
FLEET_B: 1
```

The optimal solution contains a 42 km empty repositioning movement between two scheduled trips. Therefore the deadhead structure is active in the optimum rather than being unused example data.

## Installation

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m src.run
```

## Test

```bash
pytest -q
```

The test suite verifies:

- complete trip coverage,
- passenger-capacity feasibility,
- depot inventory limits,
- maintenance-reserve availability,
- chronological connection feasibility,
- deadhead travel-time feasibility,
- fleet consistency across linked trips,
- end-of-day depot balance,
- deterministic regression values,
- optimal MIP gap on the sample instance,
- rejection of invalid maintenance-reserve data.

## Scope and limitations

This repository is a compact OR prototype, not a production railway planning system.

A production deployment would typically require additional structures such as:

- individual vehicle identities and equipment compatibility,
- periodic maintenance events and shop capacity,
- multi-day circulation balance,
- consist coupling and splitting,
- platform and yard constraints,
- crew interactions,
- stochastic disruption recovery,
- rolling-horizon re-optimization,
- large-instance performance engineering.

The current model is designed to make the core fleet-circulation logic explicit, reproducible, and testable before those layers are introduced.

## Solver

The model uses `scipy.optimize.milp`, backed by HiGHS. No commercial optimization solver is required.

## Project structure

```text
.
├── LICENSE
├── README.md
├── requirements.txt
├── src
│   ├── __init__.py
│   ├── model.py
│   └── run.py
└── tests
    └── test_model.py
```

## License

Non-commercial use only. Commercial use, sale, sublicensing for commercial purposes, paid-service integration, or incorporation into a commercial product is prohibited without separate written permission. See `LICENSE` for the full terms.
