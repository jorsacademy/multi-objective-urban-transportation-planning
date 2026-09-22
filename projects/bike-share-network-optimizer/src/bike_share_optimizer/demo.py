"""Reproducible demonstration for the optimizer package."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .optimizer import BikeShareOptimizer


def build_demo_data(seed=42):
    rng = np.random.default_rng(seed)
    existing_stations = pd.DataFrame(
        {
            "station_id": [f"S{i}" for i in range(1, 51)],
            "latitude": rng.uniform(40.7, 40.8, 50),
            "longitude": rng.uniform(-74.0, -73.9, 50),
            "capacity": rng.integers(10, 30, 50),
            "has_charger": rng.choice([True, False], 50),
        }
    )
    potential_locations = pd.DataFrame(
        {
            "location_id": [f"L{i}" for i in range(1, 101)],
            "latitude": rng.uniform(40.7, 40.8, 100),
            "longitude": rng.uniform(-74.0, -73.9, 100),
            "poi_score": rng.uniform(0, 10, 100),
            "equity_score": rng.uniform(0, 10, 100),
        }
    )

    trip_rows = []
    for _ in range(10_000):
        trip_rows.append(
            {
                "start_station": rng.choice(existing_stations["station_id"]),
                "end_station": rng.choice(existing_stations["station_id"]),
                "bike_type": rng.choice(["regular", "e-bike"], p=[0.8, 0.2]),
                "distance": rng.uniform(0.5, 5.0),
            }
        )

    transit_nodes = pd.DataFrame(
        {
            "node_id": [f"T{i}" for i in range(1, 21)],
            "latitude": rng.uniform(40.7, 40.8, 20),
            "longitude": rng.uniform(-74.0, -73.9, 20),
            "type": rng.choice(["subway", "bus", "train"], 20),
            "ridership": rng.integers(1000, 10000, 20),
        }
    )
    return existing_stations, potential_locations, pd.DataFrame(trip_rows), transit_nodes


def main():
    existing, potential, trips, transit = build_demo_data()
    optimizer = BikeShareOptimizer(existing, potential)
    optimizer.load_data(trips, transit)
    optimizer.build_demand_model()
    optimizer.predict_rider_flow()

    print("Recommended new stations:")
    print(optimizer.optimize_new_stations(num_stations=5, equity_weight=0.6))
    print("\nFleet mix:")
    print(optimizer.optimize_fleet_mix(total_bikes=1000))
    print("\nCapacity recommendations:")
    print(optimizer.recommend_station_capacity().head())


if __name__ == "__main__":
    main()
