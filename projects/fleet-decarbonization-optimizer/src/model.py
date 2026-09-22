from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import pulp

from data_loader import FleetData


DISTANCE_RANK = {"D1": 1, "D2": 2, "D3": 3, "D4": 4}
MAX_LIFE_YEARS = 10


@dataclass
class ModelArtifacts:
    problem: pulp.LpProblem
    buy: Dict[Tuple[str, int], pulp.LpVariable]
    sell: Dict[Tuple[str, int], pulp.LpVariable]
    fleet: Dict[Tuple[str, int], pulp.LpVariable]
    used: Dict[Tuple[str, int, str, str], pulp.LpVariable]
    distance: Dict[Tuple[str, int, str, str], pulp.LpVariable]
    years: list[int]


def _pct(value: float) -> float:
    """Convert either 15 or 0.15 style percentages to a 0-1 fraction."""
    return value / 100.0 if value > 1 else value


def build_model(data: FleetData) -> ModelArtifacts:
    demand = data.demand
    vehicles = data.vehicles
    vehicle_fuels = data.vehicle_fuels
    fuels = data.fuels
    carbon = data.carbon
    cost_profiles = data.cost_profiles

    years = sorted(demand["Year"].unique().tolist())
    vehicle_ids = vehicles["ID"].tolist()

    vehicle = vehicles.set_index("ID").to_dict("index")
    compatible_fuels = vehicle_fuels.groupby("ID")["Fuel"].apply(list).to_dict()

    consumption = {
        (row["ID"], row["Fuel"]): float(row["Consumption (unit_fuel/km)"])
        for _, row in vehicle_fuels.iterrows()
    }
    fuel_cost = {
        (row["Fuel"], int(row["Year"])): float(row["Cost ($/unit_fuel)"])
        for _, row in fuels.iterrows()
    }
    fuel_emissions = {
        (row["Fuel"], int(row["Year"])): float(row["Emissions (CO2/unit_fuel)"])
        for _, row in fuels.iterrows()
    }
    carbon_limit = {
        int(row["Year"]): float(row["Carbon emission CO2/kg"])
        for _, row in carbon.iterrows()
    }
    cost_profile = {
        int(row["End of Year"]): {
            "resale": _pct(float(row["Resale Value %"])),
            "insurance": _pct(float(row["Insurance Cost %"])),
            "maintenance": _pct(float(row["Maintenance Cost %"])),
        }
        for _, row in cost_profiles.iterrows()
    }

    problem = pulp.LpProblem("Fleet_Decarbonization_Optimization", pulp.LpMinimize)

    buy: Dict[Tuple[str, int], pulp.LpVariable] = {}
    sell: Dict[Tuple[str, int], pulp.LpVariable] = {}
    fleet: Dict[Tuple[str, int], pulp.LpVariable] = {}
    used: Dict[Tuple[str, int, str, str], pulp.LpVariable] = {}
    distance: Dict[Tuple[str, int, str, str], pulp.LpVariable] = {}

    for vid in vehicle_ids:
        model_year = int(vehicle[vid]["Year"])
        for year in years:
            buy[(vid, year)] = pulp.LpVariable(
                f"Buy__{vid}__{year}", lowBound=0, cat=pulp.LpInteger
            )
            sell[(vid, year)] = pulp.LpVariable(
                f"Sell__{vid}__{year}", lowBound=0, cat=pulp.LpInteger
            )
            fleet[(vid, year)] = pulp.LpVariable(
                f"Fleet__{vid}__{year}", lowBound=0, cat=pulp.LpInteger
            )

            if year != model_year:
                problem += buy[(vid, year)] == 0, f"PurchaseYear__{vid}__{year}"

    # Fleet balance. Purchases occur at the beginning of the year; sales occur at year end.
    for vid in vehicle_ids:
        for i, year in enumerate(years):
            if i == 0:
                problem += fleet[(vid, year)] == buy[(vid, year)], f"FleetBalanceStart__{vid}__{year}"
            else:
                prev = years[i - 1]
                problem += (
                    fleet[(vid, year)]
                    == fleet[(vid, prev)] - sell[(vid, prev)] + buy[(vid, year)]
                ), f"FleetBalance__{vid}__{year}"

            problem += sell[(vid, year)] <= fleet[(vid, year)], f"SellAvailable__{vid}__{year}"

    # A vehicle bought in model year y may operate for 10 calendar years, through y+9.
    # It must be sold at the end of that tenth year.
    for vid in vehicle_ids:
        model_year = int(vehicle[vid]["Year"])
        retirement_year = model_year + MAX_LIFE_YEARS - 1

        for year in years:
            if year > retirement_year:
                problem += fleet[(vid, year)] == 0, f"LifeFleetZero__{vid}__{year}"
                problem += sell[(vid, year)] == 0, f"LifeSellZero__{vid}__{year}"

        if retirement_year in years:
            problem += (
                sell[(vid, retirement_year)] == fleet[(vid, retirement_year)]
            ), f"MandatoryRetirement__{vid}__{retirement_year}"

    # Optional sales are capped at 20% of the existing fleet.
    # Mandatory tenth-year retirements are excluded from the optional-sale cap.
    for year in years:
        optional_sell_terms = []
        eligible_fleet_terms = []

        for vid in vehicle_ids:
            model_year = int(vehicle[vid]["Year"])
            retirement_year = model_year + MAX_LIFE_YEARS - 1
            if year != retirement_year:
                optional_sell_terms.append(sell[(vid, year)])
                eligible_fleet_terms.append(fleet[(vid, year)])

        if eligible_fleet_terms:
            problem += (
                pulp.lpSum(optional_sell_terms) <= 0.20 * pulp.lpSum(eligible_fleet_terms)
            ), f"MaxOptionalSales__{year}"

    # Assignment variables are created only for technically feasible combinations.
    for _, row in demand.iterrows():
        year = int(row["Year"])
        size = str(row["Size"])
        bucket = str(row["Distance"])
        demand_km = float(row["Demand (km)"])

        if bucket not in DISTANCE_RANK:
            raise ValueError(f"Unknown demand distance bucket: {bucket}")

        feasible_distance_vars = []

        for vid in vehicle_ids:
            if str(vehicle[vid]["Size"]) != size:
                continue

            vehicle_bucket = str(vehicle[vid]["Distance"])
            if vehicle_bucket not in DISTANCE_RANK:
                raise ValueError(f"Unknown vehicle distance bucket: {vehicle_bucket}")

            # A D4 vehicle can serve D1-D4; a D3 vehicle can serve D1-D3, etc.
            if DISTANCE_RANK[vehicle_bucket] < DISTANCE_RANK[bucket]:
                continue

            model_year = int(vehicle[vid]["Year"])
            if year < model_year or year > model_year + MAX_LIFE_YEARS - 1:
                continue

            for fuel in compatible_fuels.get(vid, []):
                if (fuel, year) not in fuel_cost or (fuel, year) not in fuel_emissions:
                    continue

                key = (vid, year, bucket, fuel)
                used[key] = pulp.LpVariable(
                    f"Used__{vid}__{year}__{bucket}__{fuel}",
                    lowBound=0,
                    cat=pulp.LpInteger,
                )
                distance[key] = pulp.LpVariable(
                    f"Distance__{vid}__{year}__{bucket}__{fuel}",
                    lowBound=0,
                    cat=pulp.LpContinuous,
                )

                yearly_range = float(vehicle[vid]["Yearly range (km)"])
                problem += (
                    distance[key] <= yearly_range * used[key]
                ), f"Range__{vid}__{year}__{bucket}__{fuel}"

                feasible_distance_vars.append(distance[key])

        if not feasible_distance_vars:
            raise ValueError(
                "No feasible vehicle/fuel combination for demand row: "
                f"year={year}, size={size}, bucket={bucket}"
            )

        problem += (
            pulp.lpSum(feasible_distance_vars) >= demand_km
        ), f"Demand__{year}__{size}__{bucket}"

    # A physical vehicle can only be counted once across all demand/fuel allocations in a year.
    for vid in vehicle_ids:
        for year in years:
            matching_used = [
                var for (v, y, _, _), var in used.items() if v == vid and y == year
            ]
            if matching_used:
                problem += (
                    pulp.lpSum(matching_used) <= fleet[(vid, year)]
                ), f"UseFleetLimit__{vid}__{year}"

    # Annual carbon budget: distance x consumption x fuel carbon intensity.
    for year in years:
        if year not in carbon_limit:
            raise ValueError(f"Missing carbon-emission limit for year {year}")

        emissions_terms = []
        for (vid, y, _, fuel), dist_var in distance.items():
            if y != year:
                continue
            emissions_terms.append(
                dist_var * consumption[(vid, fuel)] * fuel_emissions[(fuel, year)]
            )

        problem += (
            pulp.lpSum(emissions_terms) <= carbon_limit[year]
        ), f"CarbonBudget__{year}"

    # Objective: purchase + insurance + maintenance + fuel - resale proceeds.
    objective_terms = []

    for vid in vehicle_ids:
        purchase_cost = float(vehicle[vid]["Cost ($)"])
        model_year = int(vehicle[vid]["Year"])

        for year in years:
            objective_terms.append(purchase_cost * buy[(vid, year)])

            age = year - model_year + 1
            if 1 <= age <= MAX_LIFE_YEARS and age in cost_profile:
                objective_terms.append(
                    purchase_cost
                    * (cost_profile[age]["insurance"] + cost_profile[age]["maintenance"])
                    * fleet[(vid, year)]
                )
                objective_terms.append(
                    -purchase_cost * cost_profile[age]["resale"] * sell[(vid, year)]
                )

    for (vid, year, _, fuel), dist_var in distance.items():
        objective_terms.append(
            dist_var * consumption[(vid, fuel)] * fuel_cost[(fuel, year)]
        )

    problem += pulp.lpSum(objective_terms)

    return ModelArtifacts(
        problem=problem,
        buy=buy,
        sell=sell,
        fleet=fleet,
        used=used,
        distance=distance,
        years=years,
    )
