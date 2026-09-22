from __future__ import annotations

from collections import defaultdict

import pandas as pd

from data_loader import FleetData
from model import DISTANCE_RANK, MAX_LIFE_YEARS
from submission import OUTPUT_COLUMNS


ALLOWED_TYPES = {"Buy", "Use", "Sell"}
ALLOWED_FUELS = {"Electricity", "LNG", "BioLNG", "HVO", "B20"}
ALLOWED_DISTANCE_BUCKETS = set(DISTANCE_RANK)


def validate_submission(data: FleetData, submission: pd.DataFrame, tolerance: float = 1e-6) -> list[str]:
    errors: list[str] = []

    if list(submission.columns) != OUTPUT_COLUMNS:
        errors.append(
            f"Output columns must exactly equal {OUTPUT_COLUMNS}; got {list(submission.columns)}"
        )
        return errors

    vehicles = data.vehicles.set_index("ID").to_dict("index")
    compatible_fuels = (
        data.vehicle_fuels.groupby("ID")["Fuel"].apply(set).to_dict()
    )
    consumption = {
        (row["ID"], row["Fuel"]): float(row["Consumption (unit_fuel/km)"])
        for _, row in data.vehicle_fuels.iterrows()
    }
    fuel_emissions = {
        (row["Fuel"], int(row["Year"])): float(row["Emissions (CO2/unit_fuel)"])
        for _, row in data.fuels.iterrows()
    }
    carbon_limit = {
        int(row["Year"]): float(row["Carbon emission CO2/kg"])
        for _, row in data.carbon.iterrows()
    }

    years = sorted(data.demand["Year"].astype(int).unique().tolist())
    expected_years = set(years)

    for idx, row in submission.iterrows():
        prefix = f"row {idx}"
        try:
            year = int(row["Year"])
        except Exception:
            errors.append(f"{prefix}: Year must be an integer")
            continue

        vid = str(row["ID"])
        type_ = str(row["Type"])
        fuel = str(row["Fuel"])
        bucket = str(row["Distance_bucket"])

        try:
            quantity = int(row["Num_Vehicles"])
        except Exception:
            errors.append(f"{prefix}: Num_Vehicles must be an integer")
            continue

        try:
            distance = float(row["Distance_per_vehicle(km)"])
        except Exception:
            errors.append(f"{prefix}: Distance_per_vehicle(km) must be numeric")
            continue

        if year not in expected_years:
            errors.append(f"{prefix}: Year {year} is outside the planning horizon")
        if vid not in vehicles:
            errors.append(f"{prefix}: unknown vehicle ID {vid}")
            continue
        if quantity <= 0:
            errors.append(f"{prefix}: Num_Vehicles must be > 0")
        if type_ not in ALLOWED_TYPES:
            errors.append(f"{prefix}: invalid Type {type_}")
        if fuel not in ALLOWED_FUELS:
            errors.append(f"{prefix}: invalid Fuel {fuel}")
        if bucket not in ALLOWED_DISTANCE_BUCKETS:
            errors.append(f"{prefix}: invalid Distance_bucket {bucket}")
        if fuel not in compatible_fuels.get(vid, set()):
            errors.append(f"{prefix}: fuel {fuel} is incompatible with vehicle {vid}")

        model_year = int(vehicles[vid]["Year"])
        if type_ == "Buy" and year != model_year:
            errors.append(
                f"{prefix}: vehicle {vid} can only be bought in its model year {model_year}"
            )

        if type_ == "Use":
            if year < model_year or year > model_year + MAX_LIFE_YEARS - 1:
                errors.append(
                    f"{prefix}: vehicle {vid} is used outside its 10-year service life"
                )
            if DISTANCE_RANK[bucket] > DISTANCE_RANK[str(vehicles[vid]["Distance"])]:
                errors.append(
                    f"{prefix}: vehicle {vid} cannot serve distance bucket {bucket}"
                )
            if distance < -tolerance:
                errors.append(f"{prefix}: distance cannot be negative")
            if distance > float(vehicles[vid]["Yearly range (km)"]) + tolerance:
                errors.append(
                    f"{prefix}: per-vehicle distance exceeds yearly range for {vid}"
                )
        else:
            if abs(distance) > tolerance:
                errors.append(f"{prefix}: Buy/Sell rows must have zero distance")

    if errors:
        return errors

    # Reconstruct fleet inventory and verify use/sale limits.
    buy_by = defaultdict(int)
    sell_by = defaultdict(int)
    use_by = defaultdict(int)

    for _, row in submission.iterrows():
        key = (str(row["ID"]), int(row["Year"]))
        if row["Type"] == "Buy":
            buy_by[key] += int(row["Num_Vehicles"])
        elif row["Type"] == "Sell":
            sell_by[key] += int(row["Num_Vehicles"])
        elif row["Type"] == "Use":
            use_by[key] += int(row["Num_Vehicles"])

    fleet = defaultdict(int)
    for year in years:
        for vid, meta in vehicles.items():
            if year == years[0]:
                start = buy_by[(vid, year)]
            else:
                start = fleet[(vid, year - 1)] - sell_by[(vid, year - 1)] + buy_by[(vid, year)]
            fleet[(vid, year)] = start

            if start < 0:
                errors.append(f"negative fleet inventory for {vid} in {year}")
            if use_by[(vid, year)] > start:
                errors.append(
                    f"used {use_by[(vid, year)]} of {vid} in {year}, but only {start} are in fleet"
                )
            if sell_by[(vid, year)] > start:
                errors.append(
                    f"sold {sell_by[(vid, year)]} of {vid} in {year}, but only {start} are in fleet"
                )

            retirement_year = int(meta["Year"]) + MAX_LIFE_YEARS - 1
            if year == retirement_year and sell_by[(vid, year)] != start:
                errors.append(
                    f"vehicle cohort {vid} must be fully sold at end of {retirement_year}"
                )
            if year > retirement_year and start != 0:
                errors.append(f"vehicle {vid} remains in fleet after its 10-year lifetime")

    # Optional annual sale cap, matching the model formulation.
    for year in years:
        optional_sold = 0
        eligible_fleet = 0
        for vid, meta in vehicles.items():
            retirement_year = int(meta["Year"]) + MAX_LIFE_YEARS - 1
            if year != retirement_year:
                optional_sold += sell_by[(vid, year)]
                eligible_fleet += fleet[(vid, year)]
        if optional_sold > 0.20 * eligible_fleet + tolerance:
            errors.append(
                f"optional sales exceed 20% of eligible fleet in {year}: {optional_sold} > {0.20 * eligible_fleet:.3f}"
            )

    # Demand coverage by exact size and demand bucket.
    use_rows = submission[submission["Type"] == "Use"].copy()
    for _, demand_row in data.demand.iterrows():
        year = int(demand_row["Year"])
        size = str(demand_row["Size"])
        bucket = str(demand_row["Distance"])
        required = float(demand_row["Demand (km)"])

        supplied = 0.0
        for _, row in use_rows[use_rows["Year"] == year].iterrows():
            vid = str(row["ID"])
            if str(vehicles[vid]["Size"]) != size:
                continue
            # The submission distance bucket identifies the demand bucket being served.
            if str(row["Distance_bucket"]) != bucket:
                continue
            supplied += float(row["Num_Vehicles"]) * float(row["Distance_per_vehicle(km)"])

        if supplied + tolerance < required:
            errors.append(
                f"demand not met for {year} {size}_{bucket}: supplied {supplied:.3f}, required {required:.3f}"
            )

    # Carbon budget.
    for year in years:
        emitted = 0.0
        for _, row in use_rows[use_rows["Year"] == year].iterrows():
            vid = str(row["ID"])
            fuel = str(row["Fuel"])
            total_distance = float(row["Num_Vehicles"]) * float(row["Distance_per_vehicle(km)"])
            if (fuel, year) not in fuel_emissions:
                errors.append(f"missing fuel emissions data for {fuel} in {year}")
                continue
            emitted += total_distance * consumption[(vid, fuel)] * fuel_emissions[(fuel, year)]

        if year not in carbon_limit:
            errors.append(f"missing carbon budget for {year}")
        elif emitted > carbon_limit[year] + tolerance:
            errors.append(
                f"carbon budget exceeded in {year}: {emitted:.3f} > {carbon_limit[year]:.3f}"
            )

    return errors


def assert_valid_submission(data: FleetData, submission: pd.DataFrame) -> None:
    errors = validate_submission(data, submission)
    if errors:
        preview = "\n".join(f"- {error}" for error in errors[:50])
        suffix = "" if len(errors) <= 50 else f"\n... and {len(errors) - 50} more errors"
        raise ValueError(f"Submission validation failed:\n{preview}{suffix}")
