import numpy as np
import pandas as pd
import pytest

from bike_share_optimizer import BikeShareOptimizer


@pytest.fixture
def existing_stations():
    return pd.DataFrame(
        {
            "station_id": ["S1", "S2"],
            "latitude": [40.7500, 40.7600],
            "longitude": [-73.9900, -73.9800],
            "capacity": [20, 25],
            "has_charger": [False, True],
        }
    )


@pytest.fixture
def potential_locations():
    return pd.DataFrame(
        {
            "location_id": ["L1", "L2", "L3"],
            "latitude": [40.7550, 40.7800, 40.7200],
            "longitude": [-73.9850, -73.9500, -74.0200],
            "poi_score": [8.0, 5.0, 3.0],
            "equity_score": [4.0, 9.0, 7.0],
        }
    )


@pytest.fixture
def trip_data():
    return pd.DataFrame(
        {
            "start_station": ["S1", "S1", "S1", "S2"],
            "end_station": ["S2", "S2", "S1", "S1"],
            "distance": [1.0, 2.0, 3.0, 4.0],
        }
    )


def test_haversine_distance_is_zero_for_same_point():
    distance = BikeShareOptimizer._haversine_distance(40.75, -73.99, 40.75, -73.99)
    assert distance == pytest.approx(0.0)


def test_haversine_distance_is_reasonable_for_one_degree_latitude():
    distance = BikeShareOptimizer._haversine_distance(0.0, 0.0, 1.0, 0.0)
    assert distance == pytest.approx(111.19, rel=0.01)


def test_build_demand_model_counts_starting_trips(
    existing_stations, potential_locations, trip_data
):
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)
    optimizer.load_data(trip_data=trip_data)

    demand = optimizer.build_demand_model().set_index("station_id")["demand"]

    assert demand["S1"] == 3
    assert demand["S2"] == 1


def test_predict_rider_flow_preserves_historical_counts(
    existing_stations, potential_locations, trip_data
):
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)
    optimizer.load_data(trip_data=trip_data)

    flow = optimizer.predict_rider_flow()

    assert flow.loc["S1", "S2"] == 2
    assert flow.loc["S1", "S1"] == 1
    assert flow.loc["S2", "S1"] == 1


def test_new_station_flow_is_positive_and_symmetric(
    existing_stations, potential_locations, trip_data
):
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)
    optimizer.load_data(trip_data=trip_data)
    optimizer.build_demand_model()
    new_station = pd.DataFrame(
        {"station_id": ["N1"], "latitude": [40.7700], "longitude": [-73.9700]}
    )

    flow = optimizer.predict_rider_flow(new_station)

    assert flow.loc["N1", "S1"] > 0
    assert flow.loc["N1", "S1"] == pytest.approx(flow.loc["S1", "N1"])


def test_optimize_new_stations_validates_inputs(existing_stations, potential_locations):
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)

    with pytest.raises(ValueError, match="num_stations"):
        optimizer.optimize_new_stations(num_stations=0)

    with pytest.raises(ValueError, match="equity_weight"):
        optimizer.optimize_new_stations(equity_weight=1.1)


def test_optimize_new_stations_returns_requested_count(existing_stations, potential_locations):
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)

    result = optimizer.optimize_new_stations(num_stations=2, equity_weight=0.5)

    assert len(result) == 2
    assert set(result.columns) == {
        "station_id",
        "latitude",
        "longitude",
        "poi_score",
        "equity_score",
        "combined_score",
    }
    assert np.isfinite(result["combined_score"]).all()


def test_optimize_fleet_mix_preserves_total(existing_stations, potential_locations, trip_data):
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)
    optimizer.load_data(trip_data=trip_data)

    mix = optimizer.optimize_fleet_mix(total_bikes=100, e_bike_cost_ratio=2.0)

    assert mix["regular_bikes"] + mix["e_bikes"] == 100
    assert 0 <= mix["e_bike_percentage"] <= 100


def test_recommend_station_capacity_has_minimum_ten(
    existing_stations, potential_locations, trip_data
):
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)
    optimizer.load_data(trip_data=trip_data)
    optimizer.predict_rider_flow()

    capacities = optimizer.recommend_station_capacity()

    assert (capacities["recommended_capacity"] >= 10).all()


def test_transit_integration_rewards_nearby_node(existing_stations, potential_locations):
    transit = pd.DataFrame(
        {
            "node_id": ["T1", "T2"],
            "latitude": [40.7501, 41.0],
            "longitude": [-73.9901, -74.5],
            "type": ["subway", "bus"],
            "ridership": [1000, 10000],
        }
    )
    optimizer = BikeShareOptimizer(existing_stations, potential_locations)
    optimizer.load_data(transit_nodes=transit)

    scores = optimizer.evaluate_transit_integration().set_index("station_id")

    assert scores.loc["S1", "transit_score"] > 0
