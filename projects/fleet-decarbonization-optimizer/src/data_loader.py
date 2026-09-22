from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class FleetData:
    demand: pd.DataFrame
    vehicles: pd.DataFrame
    vehicle_fuels: pd.DataFrame
    fuels: pd.DataFrame
    carbon: pd.DataFrame
    cost_profiles: pd.DataFrame
    sample_submission: pd.DataFrame | None = None


REQUIRED_COLUMNS = {
    "demand": {"Year", "Size", "Distance", "Demand (km)"},
    "vehicles": {"ID", "Vehicle", "Size", "Year", "Cost ($)", "Yearly range (km)", "Distance"},
    "vehicle_fuels": {"ID", "Fuel", "Consumption (unit_fuel/km)"},
    "fuels": {"Fuel", "Year", "Emissions (CO2/unit_fuel)", "Cost ($/unit_fuel)", "Cost Uncertainty (±%)"},
    "carbon": {"Year", "Carbon emission CO2/kg"},
    "cost_profiles": {"End of Year", "Resale Value %", "Insurance Cost %", "Maintenance Cost %"},
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    return pd.read_csv(path)


def _validate_columns(name: str, frame: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS[name] - set(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing required columns: {sorted(missing)}")


def load_data(data_dir: str | Path) -> FleetData:
    data_dir = Path(data_dir)

    demand = _read_csv(data_dir / "demand.csv")
    vehicles = _read_csv(data_dir / "vehicles.csv")
    vehicle_fuels = _read_csv(data_dir / "vehicles_fuels.csv")
    fuels = _read_csv(data_dir / "fuels.csv")
    carbon = _read_csv(data_dir / "carbon_emissions.csv")
    cost_profiles = _read_csv(data_dir / "cost_profiles.csv")

    for name, frame in {
        "demand": demand,
        "vehicles": vehicles,
        "vehicle_fuels": vehicle_fuels,
        "fuels": fuels,
        "carbon": carbon,
        "cost_profiles": cost_profiles,
    }.items():
        _validate_columns(name, frame)

    sample_path = data_dir / "sample_submission.csv"
    sample_submission = pd.read_csv(sample_path) if sample_path.exists() else None

    demand = demand.copy()
    vehicles = vehicles.copy()
    vehicle_fuels = vehicle_fuels.copy()
    fuels = fuels.copy()
    carbon = carbon.copy()
    cost_profiles = cost_profiles.copy()

    demand["Year"] = demand["Year"].astype(int)
    demand["Demand (km)"] = demand["Demand (km)"].astype(float)

    vehicles["Year"] = vehicles["Year"].astype(int)
    vehicles["Cost ($)"] = vehicles["Cost ($)"].astype(float)
    vehicles["Yearly range (km)"] = vehicles["Yearly range (km)"].astype(float)

    vehicle_fuels["Consumption (unit_fuel/km)"] = vehicle_fuels["Consumption (unit_fuel/km)"].astype(float)

    fuels["Year"] = fuels["Year"].astype(int)
    fuels["Emissions (CO2/unit_fuel)"] = fuels["Emissions (CO2/unit_fuel)"].astype(float)
    fuels["Cost ($/unit_fuel)"] = fuels["Cost ($/unit_fuel)"].astype(float)

    carbon["Year"] = carbon["Year"].astype(int)
    carbon["Carbon emission CO2/kg"] = carbon["Carbon emission CO2/kg"].astype(float)

    cost_profiles["End of Year"] = cost_profiles["End of Year"].astype(int)
    for column in ["Resale Value %", "Insurance Cost %", "Maintenance Cost %"]:
        cost_profiles[column] = cost_profiles[column].astype(float)

    if vehicles["ID"].duplicated().any():
        duplicates = vehicles.loc[vehicles["ID"].duplicated(), "ID"].tolist()
        raise ValueError(f"vehicles.csv contains duplicate vehicle IDs: {duplicates[:10]}")

    if fuels.duplicated(["Fuel", "Year"]).any():
        raise ValueError("fuels.csv contains duplicate Fuel/Year rows.")

    if carbon["Year"].duplicated().any():
        raise ValueError("carbon_emissions.csv contains duplicate Year rows.")

    return FleetData(
        demand=demand,
        vehicles=vehicles,
        vehicle_fuels=vehicle_fuels,
        fuels=fuels,
        carbon=carbon,
        cost_profiles=cost_profiles,
        sample_submission=sample_submission,
    )
