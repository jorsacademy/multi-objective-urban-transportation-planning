from datetime import datetime

from bike_share_optimizer import BikeShareSystem, FleetOptimizer, RealtimeMonitor, Station, cost_benefit_analysis


def test_allocation_conserves_bikes_and_capacity():
    stations = [
        Station(1, "A", 0, 0, 10, 9, 0.2, datetime.now()),
        Station(2, "B", 0, 0, 10, 1, 0.9, datetime.now()),
        Station(3, "C", 0, 0, 5, 2, 0.5, datetime.now()),
    ]
    optimizer = FleetOptimizer(stations)
    for objective in ("balance", "demand", "availability"):
        result = optimizer.optimize_distribution(objective)
        optimized = result["optimized_distribution"]
        assert sum(optimized) == 12
        assert all(0 <= x <= s.capacity for x, s in zip(optimized, stations))
        assert sum(m["bikes"] for m in result["rebalancing_moves"]) == result["metrics"]["bikes_moved"]


def test_alerts_are_severity_sorted():
    stations = [
        Station(1, "Empty", 0, 0, 10, 0, 0.5, datetime.now()),
        Station(2, "Full", 0, 0, 10, 10, 0.5, datetime.now()),
    ]
    system = BikeShareSystem()
    system.stations = stations
    alerts = RealtimeMonitor(system).generate_alerts()
    severities = [a["severity"] for a in alerts]
    assert severities[0] == "HIGH"


def test_cost_benefit_handles_nonpositive_net_without_formatting_crash():
    result = {"metrics": {"bikes_moved": 10.0}}
    economics = cost_benefit_analysis(result)
    assert economics["payback_days"] is None
