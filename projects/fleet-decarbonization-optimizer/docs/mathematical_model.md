# Mathematical Model

## Sets

Let:

- `Y` be the planning years.
- `V` be vehicle model IDs.
- `B = {D1, D2, D3, D4}` be demand distance buckets.
- `F(v)` be fuels compatible with vehicle model `v`.
- `S(v)` be the size class of vehicle model `v`.
- `R(v)` be the maximum distance-bucket rank of vehicle model `v`.

Each vehicle ID is treated as a purchase cohort because an ID is tied to one model year.

## Decision variables

For vehicle `v` and year `y`:

- `Buy[v,y]`: integer number of vehicles purchased at the start of year `y`.
- `Fleet[v,y]`: integer number of vehicles available during year `y`.
- `Sell[v,y]`: integer number of vehicles sold at the end of year `y`.

For feasible vehicle/year/demand-bucket/fuel combinations:

- `Used[v,y,b,f]`: integer number of vehicles assigned to demand bucket `b` using fuel `f`.
- `Distance[v,y,b,f]`: total annual kilometres assigned to that group.

## Purchase-year constraint

A model may only be purchased in its designated model year:

```text
Buy[v,y] = 0                       for y != ModelYear[v]
```

## Fleet balance

Purchases are available immediately at the beginning of the purchase year. Sales leave the fleet only after that year's operation:

```text
Fleet[v,y0] = Buy[v,y0]

Fleet[v,y] = Fleet[v,y-1] - Sell[v,y-1] + Buy[v,y]
```

Sales cannot exceed available fleet inventory:

```text
Sell[v,y] <= Fleet[v,y]
```

## Vehicle lifetime

A vehicle has a maximum service life of ten calendar years. A vehicle bought in year `p` may operate from `p` through `p+9` and must be sold at the end of `p+9`.

```text
Sell[v,p+9] = Fleet[v,p+9]
Fleet[v,y] = 0                     for y > p+9
```

## Annual sale limit

Optional sales are limited to 20% of the eligible existing fleet in each year. Mandatory tenth-year retirement is modelled separately and excluded from the optional-sale cap.

```text
sum(OptionalSell[v,y]) <= 0.20 * sum(EligibleFleet[v,y])
```

## Demand compatibility

A vehicle can only serve demand of the same size class.

A vehicle capable of `Dk` can serve any demand bucket with rank no greater than `k`. Therefore:

```text
D4 -> D1, D2, D3, D4
D3 -> D1, D2, D3
D2 -> D1, D2
D1 -> D1
```

This ordering is implemented numerically rather than by lexicographic string comparison.

## Demand satisfaction

Demand is expressed in kilometres, so the model satisfies demand with distance variables rather than vehicle-count variables.

For each year, size, and demand bucket:

```text
sum(Distance[v,y,b,f]) >= Demand[y,size,b]
```

where only technically compatible vehicles and fuels are included in the sum.

## Vehicle range

For every feasible assignment:

```text
Distance[v,y,b,f] <= YearlyRange[v] * Used[v,y,b,f]
```

## Fleet-use limit

The same physical vehicle cannot be counted in more than one simultaneous demand/fuel assignment within a year:

```text
sum(Used[v,y,b,f]) <= Fleet[v,y]
```

## Carbon budget

Operational carbon emissions are calculated from distance, vehicle fuel consumption, and the year-specific carbon intensity of the selected fuel:

```text
Emissions[y]
  = sum(
        Distance[v,y,b,f]
        * Consumption[v,f]
        * CarbonIntensity[f,y]
    )

Emissions[y] <= CarbonBudget[y]
```

## Objective function

The objective minimizes total fleet ownership and operating cost:

```text
Minimize
    PurchaseCost
  + InsuranceCost
  + MaintenanceCost
  + FuelCost
  - ResaleProceeds
```

Purchase cost:

```text
sum(PurchasePrice[v] * Buy[v,y])
```

Ownership cost is age-dependent:

```text
sum(
    PurchasePrice[v]
    * (InsuranceRate[age] + MaintenanceRate[age])
    * Fleet[v,y]
)
```

Fuel cost:

```text
sum(
    Distance[v,y,b,f]
    * Consumption[v,f]
    * FuelPrice[f,y]
)
```

Resale proceeds:

```text
sum(
    PurchasePrice[v]
    * ResaleRate[age]
    * Sell[v,y]
)
```

and resale proceeds are subtracted from total cost.

## Output conversion

The optimizer tracks total distance assigned to a vehicle group. The CSV output format instead requires `Distance_per_vehicle(km)`. For each nonzero use assignment:

```text
Distance_per_vehicle = TotalDistance / Num_Vehicles
```

This preserves the original distance allocation while producing a valid integer vehicle count and a floating-point per-vehicle distance.
