import pytest

from src.model import connection_options, sample_data, solve_fleet_circulation


def test_sample_solution_is_complete_and_capacity_feasible():
    trips, fleet, depots, reposition = sample_data()
    solution = solve_fleet_circulation(trips, fleet, depots, reposition)

    trip_by_id = {t.trip_id: t for t in trips}
    fleet_by_id = {f.fleet_id: f for f in fleet}

    assert set(solution.assignments) == {t.trip_id for t in trips}
    for trip_id, fleet_id in solution.assignments.items():
        assert fleet_by_id[fleet_id].capacity >= trip_by_id[trip_id].demand


def test_maintenance_reserve_and_depot_supply_are_respected():
    trips, fleet, depots, reposition = sample_data()
    solution = solve_fleet_circulation(trips, fleet, depots, reposition)

    depot_supply = {(d.depot, d.fleet_id): d.units for d in depots}
    start_counts = {}
    for depot, _, fleet_id in solution.starts:
        start_counts[depot, fleet_id] = start_counts.get((depot, fleet_id), 0) + 1

    for key, count in start_counts.items():
        assert count <= depot_supply[key]

    fleet_by_id = {f.fleet_id: f for f in fleet}
    for fleet_id, count in solution.units_used.items():
        vehicle = fleet_by_id[fleet_id]
        assert count <= vehicle.available_units - vehicle.maintenance_reserve


def test_links_respect_turnaround_and_reposition_time():
    trips, fleet, depots, reposition = sample_data()
    solution = solve_fleet_circulation(trips, fleet, depots, reposition)
    options = connection_options(trips, reposition, min_turnaround=30)

    index = {t.trip_id: i for i, t in enumerate(trips)}
    for first_id, second_id, fleet_id in solution.links:
        i, j = index[first_id], index[second_id]
        assert (i, j) in options
        reposition_minutes, _ = options[i, j]
        assert trips[i].arrival + 30 + reposition_minutes <= trips[j].departure
        assert solution.assignments[first_id] == fleet_id
        assert solution.assignments[second_id] == fleet_id


def test_depot_balance_is_preserved():
    trips, fleet, depots, reposition = sample_data()
    solution = solve_fleet_circulation(trips, fleet, depots, reposition)

    dispatched = {}
    returned = {}
    for depot, _, fleet_id in solution.starts:
        dispatched[depot, fleet_id] = dispatched.get((depot, fleet_id), 0) + 1
    for _, depot, fleet_id in solution.ends:
        returned[depot, fleet_id] = returned.get((depot, fleet_id), 0) + 1

    assert dispatched == returned


def test_sample_regression_and_deadhead():
    trips, fleet, depots, reposition = sample_data()
    solution = solve_fleet_circulation(trips, fleet, depots, reposition)

    assert solution.objective == pytest.approx(10316.54, abs=1e-6)
    assert solution.deadhead_km == pytest.approx(42.0, abs=1e-6)
    assert solution.units_used == {"FLEET_A": 2, "FLEET_B": 1}
    assert solution.mip_gap is None or solution.mip_gap <= 1e-7


def test_invalid_maintenance_reserve_is_rejected():
    trips, fleet, depots, reposition = sample_data()
    bad_fleet = [
        type(fleet[0])(
            fleet[0].fleet_id,
            fleet[0].capacity,
            1,
            2,
            fleet[0].cost_per_km,
            fleet[0].activation_cost,
        ),
        fleet[1],
    ]
    with pytest.raises(ValueError, match="Maintenance reserve exceeds"):
        solve_fleet_circulation(trips, bad_fleet, depots, reposition)
