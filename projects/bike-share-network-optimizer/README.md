# Bike Share Network Optimizer

A Python package for planning and evaluating bike-share networks. It supports station placement scoring, rider-flow estimation, transit integration analysis, fleet-mix recommendations, and dock-capacity recommendations.

## Features

- Demand estimation from historical trip counts
- Rider-flow matrix generation
- Gravity-model flow estimates for proposed stations
- Haversine geographic distance calculations
- Transit integration scoring within a 500 m radius
- Candidate station ranking using POI, equity, and distance factors
- E-bike vs. regular-bike fleet-mix recommendations
- Station capacity recommendations based on modeled inflow/outflow
- Reproducible synthetic demo data
- Automated tests and GitHub Actions CI

## Project structure

```text
bike-share-network-optimizer/
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── bike_share_optimizer/
│       ├── __init__.py
│       ├── __main__.py
│       ├── demo.py
│       └── optimizer.py
├── tests/
│   └── test_optimizer.py
├── .gitignore
├── LICENSE
├── README.md
├── bike_share_optimizer.py
├── pyproject.toml
├── requirements-dev.txt
└── requirements.txt
```

The root `bike_share_optimizer.py` file is retained as a compatibility entry point. The reusable implementation lives under `src/bike_share_optimizer/`.

## Requirements

- Python 3.9+
- NumPy
- pandas

## Installation

For normal use:

```bash
python -m pip install -e .
```

For development, testing, coverage, and linting:

```bash
python -m pip install -e ".[dev]"
```

You can also install the pinned minimum runtime dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Run the demo

Preferred package entry point:

```bash
python -m bike_share_optimizer
```

The compatibility script also remains available:

```bash
python bike_share_optimizer.py
```

The demo creates synthetic station, trip, and transit data, builds the demand and flow models, and prints recommended new stations, fleet mix, and station capacities.

## Basic usage

```python
from bike_share_optimizer import BikeShareOptimizer

optimizer = BikeShareOptimizer(existing_stations, potential_locations)
optimizer.load_data(trip_data=trip_data, transit_nodes=transit_nodes)
optimizer.build_demand_model()
optimizer.predict_rider_flow()

new_stations = optimizer.optimize_new_stations(num_stations=5, equity_weight=0.6)
fleet_mix = optimizer.optimize_fleet_mix(total_bikes=1000)
capacity = optimizer.recommend_station_capacity()
```

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=bike_share_optimizer --cov-report=term-missing
```

Run the linter:

```bash
ruff check src tests bike_share_optimizer.py
```

## Continuous integration

GitHub Actions runs on every push to `main` and on pull requests targeting `main`. The CI matrix tests Python 3.9, 3.10, 3.11, and 3.12 and performs:

1. Package installation with development dependencies
2. Ruff lint checks
3. Pytest unit tests with coverage
4. A package-entry-point smoke test

## Expected data columns

### Existing stations

- `station_id`
- `latitude`
- `longitude`
- `capacity`
- `has_charger`

### Potential locations

- `location_id`
- `latitude`
- `longitude`
- `poi_score`
- `equity_score`

### Trip data

- `start_station`
- `end_station`
- `distance` (optional for fleet-mix analysis)

### Transit nodes

- `node_id`
- `latitude`
- `longitude`
- `type`
- `ridership`

## Development status

This repository is a planning-model prototype. The built-in POI scoring method generates demonstration values when an external POI dataset is unavailable. Production use should replace synthetic/demo inputs with validated operational, demographic, transit, and POI datasets.

## License

This repository is licensed under the **JORS Academy Non-Commercial Source License 1.0**. Commercial use is prohibited without a separate prior written commercial license. See [`LICENSE`](LICENSE) for the complete terms.
