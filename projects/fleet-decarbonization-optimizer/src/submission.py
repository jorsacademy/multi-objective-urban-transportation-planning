from __future__ import annotations

from collections import defaultdict

import pandas as pd
import pulp

from data_loader import FleetData
from model import ModelArtifacts


OUTPUT_COLUMNS = [
    "Year",
    "ID",
    "Num_Vehicles",
    "Type",
    "Fuel",
    "Distance_bucket",
    "Distance_per_vehicle(km)",
]


def _value(variable: pulp.LpVariable) -> float:
    value = variable.varValue
    return 0.0 if value is None else float(value)


def build_submission(data: FleetData, model: ModelArtifacts, tolerance: float = 1e-6) -> pd.DataFrame:
    rows: list[dict] = []

    vehicle_fuel_default = (
        data.vehicle_fuels.groupby("ID")["Fuel"].first().to_dict()
    )
    vehicle_distance_bucket = data.vehicles.set_index("ID")["Distance"].to_dict()

    # Buy rows.
    for (vid, year), var in model.buy.items():
        quantity = int(round(_value(var)))
        if quantity <= 0:
            continue
        rows.append(
            {
                "Year": int(year),
                "ID": str(vid),
                "Num_Vehicles": quantity,
                "Type": "Buy",
                "Fuel": str(vehicle_fuel_default[vid]),
                "Distance_bucket": str(vehicle_distance_bucket[vid]),
                "Distance_per_vehicle(km)": 0.0,
            }
        )

    # Use rows. The model stores total distance for a group of used vehicles.
    for key, used_var in model.used.items():
        vid, year, bucket, fuel = key
        quantity = int(round(_value(used_var)))
        total_distance = _value(model.distance[key])

        if quantity <= 0 or total_distance <= tolerance:
            continue

        per_vehicle_distance = total_distance / quantity

        rows.append(
            {
                "Year": int(year),
                "ID": str(vid),
                "Num_Vehicles": quantity,
                "Type": "Use",
                "Fuel": str(fuel),
                "Distance_bucket": str(bucket),
                "Distance_per_vehicle(km)": float(per_vehicle_distance),
            }
        )

    # Sell rows.
    for (vid, year), var in model.sell.items():
        quantity = int(round(_value(var)))
        if quantity <= 0:
            continue
        rows.append(
            {
                "Year": int(year),
                "ID": str(vid),
                "Num_Vehicles": quantity,
                "Type": "Sell",
                "Fuel": str(vehicle_fuel_default[vid]),
                "Distance_bucket": str(vehicle_distance_bucket[vid]),
                "Distance_per_vehicle(km)": 0.0,
            }
        )

    output = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)

    if output.empty:
        raise ValueError("The solved model produced an empty submission.")

    output["Year"] = output["Year"].astype(int)
    output["ID"] = output["ID"].astype(str)
    output["Num_Vehicles"] = output["Num_Vehicles"].astype(int)
    output["Type"] = output["Type"].astype(str)
    output["Fuel"] = output["Fuel"].astype(str)
    output["Distance_bucket"] = output["Distance_bucket"].astype(str)
    output["Distance_per_vehicle(km)"] = output["Distance_per_vehicle(km)"].astype(float)

    type_rank = {"Buy": 0, "Use": 1, "Sell": 2}
    output["_type_rank"] = output["Type"].map(type_rank)
    output = output.sort_values(
        ["Year", "_type_rank", "ID", "Distance_bucket", "Fuel"],
        kind="stable",
    ).drop(columns="_type_rank")

    return output.reset_index(drop=True)
