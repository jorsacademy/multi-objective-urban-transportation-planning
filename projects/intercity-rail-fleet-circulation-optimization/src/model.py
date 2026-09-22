from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


@dataclass(frozen=True)
class Trip:
    trip_id: str
    origin: str
    destination: str
    departure: int
    arrival: int
    demand: int
    distance_km: float


@dataclass(frozen=True)
class FleetType:
    fleet_id: str
    capacity: int
    available_units: int
    maintenance_reserve: int
    cost_per_km: float
    activation_cost: float


@dataclass(frozen=True)
class DepotSupply:
    depot: str
    fleet_id: str
    units: int


@dataclass(frozen=True)
class Reposition:
    origin: str
    destination: str
    travel_minutes: int
    distance_km: float


@dataclass
class Solution:
    objective: float
    assignments: Dict[str, str]
    starts: List[Tuple[str, str, str]]
    ends: List[Tuple[str, str, str]]
    links: List[Tuple[str, str, str]]
    units_used: Dict[str, int]
    deadhead_km: float
    mip_gap: float | None
    mip_node_count: int | None


def sample_data() -> tuple[
    List[Trip], List[FleetType], List[DepotSupply], List[Reposition]
]:
    """Return a synthetic intercity timetable, fleet, depots, and reposition network."""
    trips = [
        Trip("T01", "A", "B", 360, 480, 110, 180.0),
        Trip("T02", "B", "C", 520, 640, 125, 200.0),
        Trip("T03", "C", "B", 690, 810, 120, 200.0),
        Trip("T04", "B", "A", 850, 970, 105, 180.0),
        Trip("T05", "A", "D", 390, 510, 70, 160.0),
        Trip("T06", "D", "A", 560, 680, 75, 160.0),
        Trip("T07", "A", "E", 430, 550, 85, 170.0),
        Trip("T08", "E", "A", 600, 720, 90, 170.0),
        Trip("T09", "A", "B", 1000, 1090, 80, 140.0),
        Trip("T10", "D", "A", 1160, 1260, 82, 160.0),
    ]

    fleet = [
        FleetType("FLEET_A", 100, 3, 1, 4.2, 650.0),
        FleetType("FLEET_B", 140, 2, 0, 5.1, 800.0),
    ]

    depot_supply = [
        DepotSupply("A", "FLEET_A", 2),
        DepotSupply("A", "FLEET_B", 2),
    ]

    reposition = [
        Reposition("B", "D", 35, 42.0),
        Reposition("D", "B", 35, 42.0),
        Reposition("B", "A", 45, 55.0),
        Reposition("A", "B", 45, 55.0),
        Reposition("D", "A", 40, 48.0),
        Reposition("A", "D", 40, 48.0),
        Reposition("E", "A", 40, 50.0),
        Reposition("A", "E", 40, 50.0),
        Reposition("C", "A", 70, 88.0),
        Reposition("A", "C", 70, 88.0),
    ]
    return trips, fleet, depot_supply, reposition


def _reposition_map(
    reposition: Iterable[Reposition],
) -> Dict[Tuple[str, str], Reposition]:
    mapping: Dict[Tuple[str, str], Reposition] = {}
    for move in reposition:
        key = (move.origin, move.destination)
        if key in mapping:
            raise ValueError(f"Duplicate reposition arc: {key}")
        if move.travel_minutes < 0 or move.distance_km < 0:
            raise ValueError(f"Invalid reposition arc: {key}")
        mapping[key] = move
    return mapping


def connection_options(
    trips: Sequence[Trip],
    reposition: Sequence[Reposition],
    min_turnaround: int,
) -> Dict[Tuple[int, int], Tuple[int, float]]:
    """Return feasible trip-to-trip connections with deadhead time and distance."""
    rep = _reposition_map(reposition)
    options: Dict[Tuple[int, int], Tuple[int, float]] = {}

    for i, first in enumerate(trips):
        for j, second in enumerate(trips):
            if i == j or second.departure <= first.arrival:
                continue

            if first.destination == second.origin:
                reposition_minutes = 0
                reposition_km = 0.0
            else:
                move = rep.get((first.destination, second.origin))
                if move is None:
                    continue
                reposition_minutes = move.travel_minutes
                reposition_km = move.distance_km

            ready_time = first.arrival + min_turnaround + reposition_minutes
            if ready_time <= second.departure:
                options[i, j] = (reposition_minutes, reposition_km)

    return options


def solve_fleet_circulation(
    trips: List[Trip],
    fleet: List[FleetType],
    depot_supply: List[DepotSupply],
    reposition: List[Reposition],
    min_turnaround: int = 30,
    service_day_start: int = 240,
    service_day_end: int = 1440,
    empty_seat_penalty: float = 0.03,
    idle_time_penalty: float = 0.4,
    deadhead_cost_per_km: float = 2.0,
) -> Solution:
    """Solve depot-constrained fleet circulation and deadhead repositioning as a MILP."""
    if not trips or not fleet:
        raise ValueError("Trips and fleet must both be non-empty.")
    if min_turnaround < 0:
        raise ValueError("min_turnaround must be non-negative.")
    if service_day_end <= service_day_start:
        raise ValueError("service_day_end must be after service_day_start.")

    fleet_by_id = {f.fleet_id: f for f in fleet}
    if len(fleet_by_id) != len(fleet):
        raise ValueError("Fleet identifiers must be unique.")

    depot_units: Dict[Tuple[str, str], int] = {}
    for item in depot_supply:
        if item.fleet_id not in fleet_by_id:
            raise ValueError(f"Unknown fleet in depot supply: {item.fleet_id}")
        if item.units < 0:
            raise ValueError("Depot units must be non-negative.")
        depot_units[item.depot, item.fleet_id] = depot_units.get(
            (item.depot, item.fleet_id), 0
        ) + item.units

    depots = sorted({d.depot for d in depot_supply})
    if not depots:
        raise ValueError("At least one depot is required.")

    for vehicle in fleet:
        if vehicle.maintenance_reserve < 0:
            raise ValueError("maintenance_reserve must be non-negative.")
        usable = vehicle.available_units - vehicle.maintenance_reserve
        if usable < 0:
            raise ValueError(
                f"Maintenance reserve exceeds fleet for {vehicle.fleet_id}."
            )
        supplied = sum(
            units
            for (_, fleet_id), units in depot_units.items()
            if fleet_id == vehicle.fleet_id
        )
        if supplied < usable:
            raise ValueError(
                f"Depot supply for {vehicle.fleet_id} is below usable fleet availability."
            )

    rep = _reposition_map(reposition)

    for trip in trips:
        if trip.arrival <= trip.departure:
            raise ValueError(f"Trip {trip.trip_id} must arrive after departure.")
        if trip.demand < 0 or trip.distance_km < 0:
            raise ValueError(f"Trip {trip.trip_id} has invalid demand or distance.")
        if not any(f.capacity >= trip.demand for f in fleet):
            raise ValueError(f"No fleet type can cover demand for trip {trip.trip_id}.")

    links = connection_options(trips, reposition, min_turnaround)

    start_option: Dict[Tuple[str, int], Tuple[int, float]] = {}
    end_option: Dict[Tuple[int, str], Tuple[int, float]] = {}
    for depot in depots:
        for t, trip in enumerate(trips):
            if depot == trip.origin:
                start_minutes, start_km = 0, 0.0
            else:
                move = rep.get((depot, trip.origin))
                if move is None:
                    start_minutes, start_km = -1, -1.0
                else:
                    start_minutes, start_km = move.travel_minutes, move.distance_km
            if (
                start_minutes >= 0
                and service_day_start + start_minutes + min_turnaround <= trip.departure
            ):
                start_option[depot, t] = (start_minutes, start_km)

            if trip.destination == depot:
                end_minutes, end_km = 0, 0.0
            else:
                move = rep.get((trip.destination, depot))
                if move is None:
                    end_minutes, end_km = -1, -1.0
                else:
                    end_minutes, end_km = move.travel_minutes, move.distance_km
            if (
                end_minutes >= 0
                and trip.arrival + min_turnaround + end_minutes <= service_day_end
            ):
                end_option[t, depot] = (end_minutes, end_km)

    x_idx: Dict[Tuple[int, int], int] = {}
    start_idx: Dict[Tuple[str, int, int], int] = {}
    end_idx: Dict[Tuple[int, str, int], int] = {}
    link_idx: Dict[Tuple[int, int, int], int] = {}

    n = 0
    for t in range(len(trips)):
        for k in range(len(fleet)):
            x_idx[t, k] = n
            n += 1

    for depot, t in start_option:
        for k in range(len(fleet)):
            start_idx[depot, t, k] = n
            n += 1

    for t, depot in end_option:
        for k in range(len(fleet)):
            end_idx[t, depot, k] = n
            n += 1

    for i, j in links:
        for k in range(len(fleet)):
            link_idx[i, j, k] = n
            n += 1

    c = np.zeros(n)
    lb = np.zeros(n)
    ub = np.ones(n)
    integrality = np.ones(n)

    for t, trip in enumerate(trips):
        for k, vehicle in enumerate(fleet):
            c[x_idx[t, k]] = (
                trip.distance_km * vehicle.cost_per_km
                + empty_seat_penalty * max(0, vehicle.capacity - trip.demand)
            )
            if vehicle.capacity < trip.demand:
                ub[x_idx[t, k]] = 0.0

    for (depot, t), (_, deadhead_km) in start_option.items():
        for k, vehicle in enumerate(fleet):
            c[start_idx[depot, t, k]] = (
                vehicle.activation_cost + deadhead_cost_per_km * deadhead_km
            )

    for (t, depot), (_, deadhead_km) in end_option.items():
        for k in range(len(fleet)):
            c[end_idx[t, depot, k]] = deadhead_cost_per_km * deadhead_km

    for (i, j), (deadhead_minutes, deadhead_km) in links.items():
        idle = trips[j].departure - trips[i].arrival - deadhead_minutes
        for k in range(len(fleet)):
            c[link_idx[i, j, k]] = (
                idle_time_penalty * idle + deadhead_cost_per_km * deadhead_km
            )

    rows: List[Dict[int, float]] = []
    lows: List[float] = []
    highs: List[float] = []

    def add(coeffs: Dict[int, float], low: float, high: float) -> None:
        rows.append(coeffs)
        lows.append(low)
        highs.append(high)

    for t in range(len(trips)):
        add({x_idx[t, k]: 1.0 for k in range(len(fleet))}, 1.0, 1.0)

    for t in range(len(trips)):
        for k in range(len(fleet)):
            incoming = {x_idx[t, k]: -1.0}
            outgoing = {x_idx[t, k]: -1.0}

            for depot in depots:
                idx = start_idx.get((depot, t, k))
                if idx is not None:
                    incoming[idx] = 1.0
                idx = end_idx.get((t, depot, k))
                if idx is not None:
                    outgoing[idx] = 1.0

            for i, j in links:
                if j == t:
                    incoming[link_idx[i, j, k]] = 1.0
                if i == t:
                    outgoing[link_idx[i, j, k]] = 1.0

            add(incoming, 0.0, 0.0)
            add(outgoing, 0.0, 0.0)

    for depot in depots:
        for k, vehicle in enumerate(fleet):
            coeffs = {
                idx: 1.0
                for (d, _, kk), idx in start_idx.items()
                if d == depot and kk == k
            }
            if coeffs:
                add(
                    coeffs,
                    -np.inf,
                    float(depot_units.get((depot, vehicle.fleet_id), 0)),
                )

    for k, vehicle in enumerate(fleet):
        coeffs = {idx: 1.0 for (_, _, kk), idx in start_idx.items() if kk == k}
        add(
            coeffs,
            -np.inf,
            float(vehicle.available_units - vehicle.maintenance_reserve),
        )

    for depot in depots:
        for k in range(len(fleet)):
            coeffs: Dict[int, float] = {}
            for (d, _, kk), idx in start_idx.items():
                if d == depot and kk == k:
                    coeffs[idx] = coeffs.get(idx, 0.0) + 1.0
            for (_, d, kk), idx in end_idx.items():
                if d == depot and kk == k:
                    coeffs[idx] = coeffs.get(idx, 0.0) - 1.0
            if coeffs:
                add(coeffs, 0.0, 0.0)

    A = lil_matrix((len(rows), n), dtype=float)
    for r, coeffs in enumerate(rows):
        for col, value in coeffs.items():
            A[r, col] = value

    result = milp(
        c=c,
        integrality=integrality,
        bounds=Bounds(lb, ub),
        constraints=LinearConstraint(
            A.tocsr(), np.asarray(lows), np.asarray(highs)
        ),
        options={"disp": False},
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"Optimization failed: {result.message}")

    values = result.x
    assignments: Dict[str, str] = {}
    starts: List[Tuple[str, str, str]] = []
    ends: List[Tuple[str, str, str]] = []
    selected_links: List[Tuple[str, str, str]] = []
    deadhead_km = 0.0

    for t, trip in enumerate(trips):
        for k, vehicle in enumerate(fleet):
            if values[x_idx[t, k]] > 0.5:
                assignments[trip.trip_id] = vehicle.fleet_id

    for (depot, t, k), idx in start_idx.items():
        if values[idx] > 0.5:
            starts.append((depot, trips[t].trip_id, fleet[k].fleet_id))
            deadhead_km += start_option[depot, t][1]

    for (t, depot, k), idx in end_idx.items():
        if values[idx] > 0.5:
            ends.append((trips[t].trip_id, depot, fleet[k].fleet_id))
            deadhead_km += end_option[t, depot][1]

    for (i, j, k), idx in link_idx.items():
        if values[idx] > 0.5:
            selected_links.append(
                (trips[i].trip_id, trips[j].trip_id, fleet[k].fleet_id)
            )
            deadhead_km += links[i, j][1]

    units_used = {
        vehicle.fleet_id: sum(
            1 for _, _, fleet_id in starts if fleet_id == vehicle.fleet_id
        )
        for vehicle in fleet
    }

    return Solution(
        objective=float(result.fun),
        assignments=assignments,
        starts=sorted(starts),
        ends=sorted(ends),
        links=sorted(selected_links),
        units_used=units_used,
        deadhead_km=float(deadhead_km),
        mip_gap=getattr(result, "mip_gap", None),
        mip_node_count=getattr(result, "mip_node_count", None),
    )
