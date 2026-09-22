# Multi-Modal Distribution Network Genetic Algorithm

A compact research-style implementation of a genetic algorithm for capacitated distribution-center location, customer allocation, and transportation-mode selection.

## Problem

The model chooses:

- which candidate distribution centers (DCs) to open,
- the capacity level of each open DC,
- which DC serves each customer zone,
- which transportation mode (truck, rail, or air) serves each customer.

The objective minimizes fixed facility costs, operating costs, and transportation costs while enforcing capacity, reserve-capacity, minimum-utilization, and mode-availability requirements.

## Important modeling correction

The original formulation used terms such as `z_ij * x_ik` and `z_ij * y_ijm`, which make the objective nonlinear. This implementation uses a **single-sourcing GA representation** instead:

- `C[i] = 0,1,2,3` determines whether DC `i` is closed or its capacity level.
- `A[j]` assigns customer `j` to one open DC.
- `T[j]` selects one available transport mode for customer `j`.
- The shipment quantity is therefore `d[j]` for the selected DC-mode pair and zero otherwise.

This makes demand satisfaction automatic in the chromosome representation.

## Feasibility note

The rule requiring every open DC to serve at least 15% of total demand implies that at most

`floor(1 / 0.15) = 6`

DCs can be open in any feasible solution, even though the stated upper bound is 8. The code keeps `MAX_DCS = 8` but derives an effective feasible upper bound of 6.

## Improvements over the old implementation

- removes redundant location and capacity genes,
- eliminates the DEAP dependency and duplicate `creator.create(...)` issues,
- pairs customer assignment and transportation mode during crossover,
- uses elitism,
- repairs aggregate reserve capacity,
- greedily repairs assignments for DC capacity and minimum utilization,
- uses normalized penalties instead of unrelated hard-coded penalty constants,
- removes unused pandas dependency,
- vectorizes distance construction with NumPy,
- separates cost breakdown, analysis, and convergence plotting.

## Run

```bash
pip install -r requirements.txt
python multimodal_distribution_ga.py
```

## Requirements

- Python 3.10+
- NumPy
- Matplotlib

## Mathematical interpretation

For each customer `j`, the GA chooses exactly one open DC `i=A[j]` and one available mode `m=T[j]`. The full customer demand `d_j` is assigned to that pair. Accordingly, the objective evaluated by the GA is:

\[
\min \sum_i f_{i,C_i}
+ \sum_j c_{A_j,C_{A_j}} d_j
+ \sum_j t_{A_j,j,T_j} d_j
\]

subject to facility capacity, aggregate reserve capacity, minimum utilization, facility-count, and transportation-mode availability constraints.
