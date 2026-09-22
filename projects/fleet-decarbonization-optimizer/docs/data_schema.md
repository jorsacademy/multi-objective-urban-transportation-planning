# Data Schema

The loader expects the following CSV schemas.

## demand.csv

| Column | Meaning |
| --- | --- |
| `Year` | Planning year |
| `Size` | Vehicle size bucket such as S1-S4 |
| `Distance` | Demand distance bucket such as D1-D4 |
| `Demand (km)` | Annual distance demand in kilometres |

## vehicles.csv

| Column | Meaning |
| --- | --- |
| `ID` | Unique vehicle model identifier |
| `Vehicle` | Drivetrain or vehicle family |
| `Size` | Vehicle size bucket |
| `Year` | Purchase/model year |
| `Cost ($)` | Purchase cost per vehicle |
| `Yearly range (km)` | Maximum annual distance per vehicle |
| `Distance` | Maximum distance bucket the vehicle can serve |

## vehicles_fuels.csv

| Column | Meaning |
| --- | --- |
| `ID` | Vehicle model identifier |
| `Fuel` | Compatible fuel |
| `Consumption (unit_fuel/km)` | Fuel consumption per kilometre |

## fuels.csv

| Column | Meaning |
| --- | --- |
| `Fuel` | Fuel name |
| `Year` | Planning year |
| `Emissions (CO2/unit_fuel)` | Carbon emissions per unit fuel |
| `Cost ($/unit_fuel)` | Median fuel cost per unit |
| `Cost Uncertainty (±%)` | Fuel-cost uncertainty band |

## carbon_emissions.csv

| Column | Meaning |
| --- | --- |
| `Year` | Planning year |
| `Carbon emission CO2/kg` | Maximum annual carbon emissions |

## cost_profiles.csv

| Column | Meaning |
| --- | --- |
| `End of Year` | Vehicle age at the end of the year |
| `Resale Value %` | Resale value as a percentage of purchase cost |
| `Insurance Cost %` | Annual insurance cost as a percentage of purchase cost |
| `Maintenance Cost %` | Annual maintenance cost as a percentage of purchase cost |

## sample_submission.csv

The submission schema is:

- `Year`
- `ID`
- `Num_Vehicles`
- `Type`
- `Fuel`
- `Distance_bucket`
- `Distance_per_vehicle(km)`

The repository intentionally does not include the original input datasets.
