# London Bike-Share Demand & Rebalancing Optimizer

A reproducible educational demo that combines synthetic bike-share demand prediction with capacity-constrained fleet rebalancing.

## What it does

- trains a Random Forest demand model on synthetic hourly demand data;
- evaluates the model with R², MAE and RMSE instead of a hard-coded accuracy claim;
- creates capacity-constrained integer station allocations for balance, demand and availability objectives;
- guarantees that rebalancing conserves the total number of bikes;
- produces source-to-destination transfer instructions;
- generates severity-ordered operational alerts;
- writes a four-panel analytics dashboard to `bike_share_dashboard.png`.

## Important scope note

The station and demand data are synthetic. The optimization logic is a deterministic allocation heuristic, not a production-grade vehicle-routing or dispatch optimizer. Economic outputs are illustrative assumptions, not business forecasts.

## Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python bike_share_optimizer.py
```

## Tests

```bash
pip install pytest
pytest -q
```

## Improvements over the legacy script

The legacy version could crash while formatting a missing payback period, could produce inconsistent fleet allocations after rounding, re-trained the model unnecessarily during analytics, sorted alert severities lexicographically, and displayed a random "efficiency" KPI. This version removes those failure modes and makes the random synthetic setup reproducible.
