# Fleet Decarbonization Optimizer

A mixed-integer linear programming (MILP) framework for multi-year fleet transition planning under demand, vehicle lifetime, resale, fuel, and carbon constraints.

## Scope

This repository is intentionally generic. It does not depend on any private company name, brand name, or competition-specific identity. The model is designed for educational, research, and other non-commercial uses involving fleet transition and decarbonization planning.

## Model overview

The optimizer jointly decides:

- how many vehicles to buy in each year,
- how many vehicles of each model remain in the active fleet,
- how many vehicles are used for each demand bucket,
- how much distance is allocated to each vehicle/fuel/demand combination,
- when vehicles are sold,
- how yearly emissions remain within the carbon budget,
- how to minimize total ownership and operating cost.

The implementation enforces these core rules:

1. A vehicle can only be purchased in its model year.
2. A vehicle can remain in service for at most 10 years.
3. Purchases occur at year start and sales at year end.
4. At most 20% of the eligible existing fleet may be sold in a year; mandatory end-of-life retirement is handled separately.
5. Vehicles may only serve demand of the same size class.
6. A vehicle with distance capability Dk can serve demand buckets D1 through Dk.
7. Demand is enforced in distance units rather than vehicle-count units.
8. Vehicle use cannot exceed available fleet inventory.
9. Distance assigned to a vehicle cannot exceed its yearly range.
10. Fuel must be compatible with the selected vehicle.
11. Fuel consumption, fuel price, and carbon intensity are evaluated by year.
12. Total annual operational emissions must remain within the annual carbon budget.
13. Purchase, insurance, maintenance, fuel, and resale value are incorporated into the objective.

## Expected input files

The default loader expects CSV files with these names:

- `demand.csv`
- `vehicles.csv`
- `vehicles_fuels.csv`
- `fuels.csv`
- `carbon_emissions.csv`
- `cost_profiles.csv`

A `sample_submission.csv` file may also be supplied for output-column validation.

The expected source column names are documented in `docs/data_schema.md`.

## Installation

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Place the CSV files in a local `data/` directory and run:

```bash
python src/optimize.py --data-dir data --output optimized_submission.csv
```

Optional solver parameters:

```bash
python src/optimize.py \
  --data-dir data \
  --output optimized_submission.csv \
  --time-limit 1800 \
  --mip-gap 0.005
```

## Output

The generated file contains:

- `Year`
- `ID`
- `Num_Vehicles`
- `Type`
- `Fuel`
- `Distance_bucket`
- `Distance_per_vehicle(km)`

The writer emits separate `Buy`, `Use`, and `Sell` records and validates data types before saving.

## Repository layout

```text
fleet-decarbonization-optimizer/
├── README.md
├── LICENSE.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── data_loader.py
│   ├── model.py
│   ├── validation.py
│   ├── submission.py
│   └── optimize.py
└── docs/
    ├── data_schema.md
    └── mathematical_model.md
```

## Important modelling note

The output format stores a single `Distance_per_vehicle(km)` value for each `Use` row. Internally, however, the optimization model works with total distance allocation. The submission builder converts that allocation into a per-vehicle distance while preserving an integer vehicle count.

## License

This project is source-available for educational, research, and non-commercial use only. Commercial use is not permitted without prior written permission. See `LICENSE.md`.
