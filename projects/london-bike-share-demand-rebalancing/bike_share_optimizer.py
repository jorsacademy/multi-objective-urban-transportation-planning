#!/usr/bin/env python3
"""London bike-sharing demand prediction and fleet rebalancing demo.

The project intentionally uses synthetic demand and station data so it can run
without external APIs. It is an educational example, not a production forecast.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

WEATHER = ("sunny", "cloudy", "rainy")
SEVERITY_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


@dataclass
class Station:
    id: int
    name: str
    latitude: float
    longitude: float
    capacity: int
    current_bikes: int
    demand_factor: float
    last_updated: datetime

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if not 0 <= self.current_bikes <= self.capacity:
            raise ValueError("current_bikes must be between 0 and capacity")
        if self.demand_factor < 0:
            raise ValueError("demand_factor must be non-negative")

    @property
    def utilization_rate(self) -> float:
        return self.current_bikes / self.capacity

    @property
    def availability_score(self) -> float:
        """Bike availability score capped at 1.0, with 80% fill treated as full service."""
        return min(1.0, self.current_bikes / (0.8 * self.capacity))


class DemandPredictor:
    feature_names = [
        "hour",
        "day_of_week",
        "month",
        "temperature",
        "is_weekend",
        "weather_sunny",
        "weather_cloudy",
        "weather_rainy",
    ]

    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.model = RandomForestRegressor(
            n_estimators=120,
            min_samples_leaf=2,
            random_state=random_state,
            n_jobs=-1,
        )
        self.is_trained = False
        self.metrics: Dict[str, float] = {}

    @staticmethod
    def _base_demand(hour: int, day_of_week: int, month: int) -> float:
        hourly = [5, 3, 2, 2, 3, 8, 20, 40, 60, 45, 35, 40, 45, 50, 55, 65, 75, 85, 70, 50, 35, 25, 15, 8]
        base = float(hourly[hour])
        if day_of_week >= 5:
            base *= 1.3 if 10 <= hour <= 16 else 0.7
        seasonal = [0.8, 0.8, 0.9, 1.0, 1.1, 1.2, 1.2, 1.1, 1.0, 0.9, 0.8, 0.8]
        return base * seasonal[month - 1]

    def generate_synthetic_data(self, n_samples: int = 10_000) -> pd.DataFrame:
        if n_samples < 100:
            raise ValueError("n_samples must be at least 100")
        rng = np.random.default_rng(self.random_state)
        base_date = datetime(2024, 1, 1)
        rows = []
        for _ in range(n_samples):
            date = base_date + timedelta(days=int(rng.integers(0, 366)), hours=int(rng.integers(0, 24)))
            hour = date.hour
            dow = date.weekday()
            month = date.month
            temperature = float(rng.normal(15, 8))
            weather = str(rng.choice(WEATHER, p=[0.4, 0.4, 0.2]))
            weather_mult = {"sunny": 1.2, "cloudy": 1.0, "rainy": 0.6}[weather]
            temp_mult = 0.7 if temperature < 5 else 1.1 if temperature > 25 else 1.15 if 15 <= temperature <= 20 else 1.0
            demand = max(0.0, self._base_demand(hour, dow, month) * weather_mult * temp_mult + rng.normal(0, 5))
            row = {
                "hour": hour,
                "day_of_week": dow,
                "month": month,
                "temperature": temperature,
                "is_weekend": int(dow >= 5),
                "demand": round(demand),
            }
            row.update({f"weather_{w}": int(weather == w) for w in WEATHER})
            rows.append(row)
        return pd.DataFrame(rows)

    def train(self, n_samples: int = 10_000) -> Dict[str, object]:
        df = self.generate_synthetic_data(n_samples)
        X = df[self.feature_names]
        y = df["demand"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=self.random_state
        )
        self.model.fit(X_train, y_train)
        pred = self.model.predict(X_test)
        self.is_trained = True
        self.metrics = {
            "mae": float(mean_absolute_error(y_test, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
            "r2": float(r2_score(y_test, pred)),
        }
        return {
            **self.metrics,
            "feature_importance": dict(zip(self.feature_names, self.model.feature_importances_)),
        }

    def predict(self, hour: int, day_of_week: int, month: int, temperature: float, weather: str) -> float:
        if not self.is_trained:
            raise RuntimeError("model must be trained before prediction")
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= day_of_week <= 6:
            raise ValueError("day_of_week must be between 0 and 6")
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        if weather not in WEATHER:
            raise ValueError(f"weather must be one of {WEATHER}")
        row = pd.DataFrame(
            [[hour, day_of_week, month, temperature, int(day_of_week >= 5), *(int(weather == w) for w in WEATHER)]],
            columns=self.feature_names,
        )
        return max(0.0, float(self.model.predict(row)[0]))


class FleetOptimizer:
    """Capacity-constrained integer allocation heuristics that conserve the fleet."""

    def __init__(self, stations: List[Station]) -> None:
        if not stations:
            raise ValueError("at least one station is required")
        self.stations = stations
        self.total_bikes = sum(s.current_bikes for s in stations)
        self.total_capacity = sum(s.capacity for s in stations)
        if self.total_bikes > self.total_capacity:
            raise ValueError("fleet exceeds total station capacity")

    def _allocate(self, weights: np.ndarray) -> List[int]:
        capacities = np.array([s.capacity for s in self.stations], dtype=int)
        weights = np.asarray(weights, dtype=float)
        if np.any(weights < 0) or not np.any(weights > 0):
            raise ValueError("allocation weights must contain a positive value and no negatives")

        ideal = self.total_bikes * weights / weights.sum()
        allocation = np.minimum(np.floor(ideal).astype(int), capacities)
        remaining = self.total_bikes - int(allocation.sum())

        # Fill remaining bikes by fractional priority while respecting capacities.
        fractional = ideal - np.floor(ideal)
        while remaining > 0:
            feasible = allocation < capacities
            if not np.any(feasible):
                raise RuntimeError("unable to place all bikes within capacities")
            score = np.where(feasible, fractional + weights / weights.max(), -np.inf)
            idx = int(np.argmax(score))
            allocation[idx] += 1
            remaining -= 1
            fractional[idx] = 0.0

        assert int(allocation.sum()) == self.total_bikes
        assert np.all(allocation <= capacities)
        return allocation.tolist()

    def optimize_distribution(self, objective: str = "balance") -> Dict[str, object]:
        capacities = np.array([s.capacity for s in self.stations], dtype=float)
        demand = np.array([s.demand_factor for s in self.stations], dtype=float)
        if objective == "balance":
            weights = capacities
        elif objective == "demand":
            weights = capacities * np.maximum(demand, 1e-9)
        elif objective == "availability":
            # Blend capacity and demand so high-demand stations are favored without starving others.
            normalized_demand = demand / demand.max() if demand.max() else np.ones_like(demand)
            weights = capacities * (0.5 + 0.5 * normalized_demand)
        else:
            raise ValueError("objective must be 'balance', 'demand', or 'availability'")

        current = [s.current_bikes for s in self.stations]
        optimized = self._allocate(weights)
        return {
            "objective": objective,
            "current_distribution": current,
            "optimized_distribution": optimized,
            "metrics": self._metrics(current, optimized),
            "rebalancing_moves": self._pair_moves(current, optimized),
        }

    def _metrics(self, current: List[int], optimized: List[int]) -> Dict[str, float]:
        capacities = np.array([s.capacity for s in self.stations], dtype=float)
        curr_util = np.array(current) / capacities
        opt_util = np.array(optimized) / capacities
        curr_std = float(np.std(curr_util))
        opt_std = float(np.std(opt_util))
        reduction = 100 * (curr_std - opt_std) / curr_std if curr_std > 0 else 0.0
        return {
            "current_utilization_std": curr_std,
            "optimized_utilization_std": opt_std,
            "utilization_dispersion_reduction_pct": reduction,
            "bikes_moved": float(sum(max(0, o - c) for c, o in zip(current, optimized))),
        }

    def _pair_moves(self, current: List[int], optimized: List[int]) -> List[Dict[str, object]]:
        sources = [[i, c - o] for i, (c, o) in enumerate(zip(current, optimized)) if c > o]
        sinks = [[i, o - c] for i, (c, o) in enumerate(zip(current, optimized)) if o > c]
        moves = []
        si = ti = 0
        while si < len(sources) and ti < len(sinks):
            src_idx, surplus = sources[si]
            dst_idx, deficit = sinks[ti]
            qty = min(surplus, deficit)
            moves.append({
                "from_station_id": self.stations[src_idx].id,
                "from_station": self.stations[src_idx].name,
                "to_station_id": self.stations[dst_idx].id,
                "to_station": self.stations[dst_idx].name,
                "bikes": int(qty),
            })
            sources[si][1] -= qty
            sinks[ti][1] -= qty
            if sources[si][1] == 0:
                si += 1
            if sinks[ti][1] == 0:
                ti += 1
        if sum(m["bikes"] for m in moves) != sum(max(0, o - c) for c, o in zip(current, optimized)):
            raise RuntimeError("rebalancing plan is inconsistent")
        return moves


class BikeShareSystem:
    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.rng = np.random.default_rng(random_state)
        self.stations: List[Station] = []
        self.demand_predictor = DemandPredictor(random_state=random_state)
        self.fleet_optimizer: FleetOptimizer | None = None
        self.training_results: Dict[str, object] = {}

    def initialize_system(self) -> None:
        self._create_sample_stations()
        self.training_results = self.demand_predictor.train()
        self.fleet_optimizer = FleetOptimizer(self.stations)

    def _create_sample_stations(self) -> None:
        raw = [
            ("King's Cross", 51.5308, -0.1238, 25), ("London Bridge", 51.5045, -0.0865, 30),
            ("Canary Wharf", 51.5054, -0.0235, 35), ("Westminster", 51.4994, -0.1245, 40),
            ("Tower Bridge", 51.5055, -0.0754, 20), ("Oxford Circus", 51.5154, -0.1419, 25),
            ("Covent Garden", 51.5118, -0.1226, 20), ("Bank", 51.5133, -0.0886, 30),
            ("Liverpool Street", 51.5178, -0.0823, 25), ("Paddington", 51.5154, -0.1755, 35),
            ("Victoria", 51.4952, -0.1441, 30), ("Waterloo", 51.5036, -0.1106, 40),
            ("Hyde Park Corner", 51.5028, -0.1527, 15), ("Shoreditch", 51.5246, -0.0773, 20),
            ("Greenwich", 51.4825, -0.0077, 25),
        ]
        self.stations = [
            Station(i, name, lat, lon, cap, int(self.rng.integers(3, cap)), float(self.rng.uniform(0.3, 0.9)), datetime.now())
            for i, (name, lat, lon, cap) in enumerate(raw, 1)
        ]

    def predict_demand(self, hour: int, weather: str = "sunny", temperature: float = 15.0, when: datetime | None = None) -> Dict[str, object]:
        when = when or datetime.now()
        hourly = [self.demand_predictor.predict(h, when.weekday(), when.month, temperature, weather) for h in range(24)]
        return {
            "hour": hour,
            "predicted_demand": hourly[hour],
            "hourly_predictions": hourly,
            "peak_hour": int(np.argmax(hourly)),
            "peak_demand": float(max(hourly)),
            "total_daily_demand": float(sum(hourly)),
        }

    def optimize_fleet(self, objective: str = "balance") -> Dict[str, object]:
        if self.fleet_optimizer is None:
            raise RuntimeError("system must be initialized first")
        return self.fleet_optimizer.optimize_distribution(objective)

    def apply_rebalancing(self, result: Dict[str, object]) -> None:
        optimized = result["optimized_distribution"]
        if len(optimized) != len(self.stations):
            raise ValueError("optimized distribution length mismatch")
        if sum(optimized) != sum(s.current_bikes for s in self.stations):
            raise ValueError("rebalancing must conserve total bike count")
        for station, bikes in zip(self.stations, optimized):
            if not 0 <= bikes <= station.capacity:
                raise ValueError("invalid station allocation")
            station.current_bikes = int(bikes)
            station.last_updated = datetime.now()
        self.fleet_optimizer = FleetOptimizer(self.stations)

    def status(self) -> Dict[str, object]:
        return {
            "total_bikes": sum(s.current_bikes for s in self.stations),
            "total_capacity": sum(s.capacity for s in self.stations),
            "mean_utilization": float(np.mean([s.utilization_rate for s in self.stations])),
            "mean_availability": float(np.mean([s.availability_score for s in self.stations])),
        }


class RealtimeMonitor:
    def __init__(self, system: BikeShareSystem) -> None:
        self.system = system

    def generate_alerts(self) -> List[Dict[str, object]]:
        alerts = []
        for s in self.system.stations:
            if s.current_bikes <= 3:
                alerts.append({"severity": "HIGH" if s.current_bikes == 0 else "MEDIUM", "type": "LOW_BIKES", "station": s.name, "value": s.current_bikes})
            if s.utilization_rate >= 0.9:
                alerts.append({"severity": "MEDIUM", "type": "HIGH_UTILIZATION", "station": s.name, "value": s.utilization_rate})
            if s.availability_score <= 0.2:
                alerts.append({"severity": "HIGH", "type": "LOW_AVAILABILITY", "station": s.name, "value": s.availability_score})
        return sorted(alerts, key=lambda a: SEVERITY_RANK[a["severity"]], reverse=True)


def cost_benefit_analysis(result: Dict[str, object], cost_per_bike_moved: float = 5.0, revenue_per_enabled_trip: float = 2.5) -> Dict[str, float | None]:
    bikes_moved = float(result["metrics"]["bikes_moved"])
    # Illustrative assumption only: each moved bike enables 0.5 additional paid trips that day.
    cost = bikes_moved * cost_per_bike_moved
    benefit = bikes_moved * 0.5 * revenue_per_enabled_trip
    net = benefit - cost
    return {
        "daily_cost": cost,
        "daily_benefit": benefit,
        "daily_net_benefit": net,
        "payback_days": (cost / max(benefit - cost, 1e-12)) if net > 0 else None,
    }


def create_visualizations(system: BikeShareSystem, output_path: str = "bike_share_dashboard.png") -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    names = [s.name for s in system.stations]
    bikes = [s.current_bikes for s in system.stations]
    caps = [s.capacity for s in system.stations]
    x = np.arange(len(names))
    axes[0, 0].bar(x, caps, alpha=0.35, label="Capacity")
    axes[0, 0].bar(x, bikes, alpha=0.85, label="Bikes")
    axes[0, 0].set_xticks(x, [n[:10] for n in names], rotation=45, ha="right")
    axes[0, 0].set_title("Station inventory")
    axes[0, 0].legend()

    hours = range(24)
    for weather in WEATHER:
        now = datetime.now()
        y = [system.demand_predictor.predict(h, now.weekday(), now.month, 15, weather) for h in hours]
        axes[0, 1].plot(hours, y, label=weather)
    axes[0, 1].set_title("Predicted demand by weather")
    axes[0, 1].set_xlabel("Hour")
    axes[0, 1].legend()

    axes[1, 0].scatter([s.demand_factor for s in system.stations], [s.utilization_rate for s in system.stations])
    axes[1, 0].set_xlabel("Demand factor")
    axes[1, 0].set_ylabel("Utilization")
    axes[1, 0].set_title("Demand vs utilization")

    objs = ["balance", "demand", "availability"]
    moved = [system.optimize_fleet(o)["metrics"]["bikes_moved"] for o in objs]
    axes[1, 1].bar(objs, moved)
    axes[1, 1].set_ylabel("Bikes moved")
    axes[1, 1].set_title("Rebalancing effort")

    fig.suptitle("London Bike-Sharing Analytics")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    system = BikeShareSystem(random_state=42)
    system.initialize_system()
    m = system.training_results
    print(f"Model metrics: R²={m['r2']:.3f}, MAE={m['mae']:.2f}, RMSE={m['rmse']:.2f}")
    print("Initial status:", system.status())

    result = system.optimize_fleet("demand")
    print(f"Demand-based plan moves {int(result['metrics']['bikes_moved'])} bikes in {len(result['rebalancing_moves'])} transfers")
    economics = cost_benefit_analysis(result)
    payback = "N/A" if economics["payback_days"] is None else f"{economics['payback_days']:.0f} days"
    print(f"Illustrative payback: {payback}")

    monitor = RealtimeMonitor(system)
    print(f"Active alerts: {len(monitor.generate_alerts())}")
    create_visualizations(system)
    print("Dashboard written to bike_share_dashboard.png")


if __name__ == "__main__":
    main()
