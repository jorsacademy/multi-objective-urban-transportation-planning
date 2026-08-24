from gurobipy import GRB, Model, quicksum


def build_model():
    """Build and return a small multi-objective urban transportation model."""
    model = Model("UrbanTransportationPlanning")

    routes = ["Route1", "Route2", "Route3"]
    time_periods = ["Morning", "Evening"]

    # Sample parameters indexed by route and time period.
    travel_time = {
        (route, period): 10 + i + j
        for i, route in enumerate(routes)
        for j, period in enumerate(time_periods)
    }
    environmental_impact = {
        (route, period): 5 + i + j
        for i, route in enumerate(routes)
        for j, period in enumerate(time_periods)
    }
    operating_cost = {
        (route, period): 100 + 10 * i + 10 * j
        for i, route in enumerate(routes)
        for j, period in enumerate(time_periods)
    }
    demand = {
        (route, period): 2 + i + j
        for i, route in enumerate(routes)
        for j, period in enumerate(time_periods)
    }

    budget = 10_000
    max_environmental_impact = 300

    # Integer decision variables. Non-negativity is implicit because lb=0 by default.
    units = model.addVars(
        routes,
        time_periods,
        vtype=GRB.INTEGER,
        lb=0,
        name="x",
    )

    total_travel_time = quicksum(
        travel_time[route, period] * units[route, period]
        for route in routes
        for period in time_periods
    )
    total_environmental_impact = quicksum(
        environmental_impact[route, period] * units[route, period]
        for route in routes
        for period in time_periods
    )
    total_cost = quicksum(
        operating_cost[route, period] * units[route, period]
        for route in routes
        for period in time_periods
    )

    # Hierarchical multi-objective optimization:
    # 1) minimize travel time first;
    # 2) among solutions that preserve the best higher-priority objective,
    #    minimize environmental impact and cost at the same lower priority.
    model.ModelSense = GRB.MINIMIZE
    model.setObjectiveN(
        total_travel_time,
        index=0,
        priority=2,
        weight=1.0,
        name="MinimizeTravelTime",
    )
    model.setObjectiveN(
        total_environmental_impact,
        index=1,
        priority=1,
        weight=1.0,
        name="MinimizeEnvironmentalImpact",
    )
    model.setObjectiveN(
        total_cost,
        index=2,
        priority=1,
        weight=1.0,
        name="MinimizeCost",
    )

    model.addConstr(total_cost <= budget, name="BudgetConstraint")
    model.addConstr(
        total_environmental_impact <= max_environmental_impact,
        name="EnvironmentalImpactConstraint",
    )

    for route in routes:
        for period in time_periods:
            model.addConstr(
                units[route, period] >= demand[route, period],
                name=f"Demand_{route}_{period}",
            )

    return {
        "model": model,
        "routes": routes,
        "time_periods": time_periods,
        "units": units,
        "total_travel_time": total_travel_time,
        "total_environmental_impact": total_environmental_impact,
        "total_cost": total_cost,
    }


def main():
    data = build_model()
    model = data["model"]
    model.optimize()

    if model.Status == GRB.OPTIMAL:
        print("Optimal solution found:")
        for route in data["routes"]:
            for period in data["time_periods"]:
                value = data["units"][route, period].X
                print(f" - Units allocated to {route} during {period}: {value:g}")

        print(
            "Objective values: "
            f"Travel Time = {data['total_travel_time'].getValue():g}, "
            f"Environmental Impact = {data['total_environmental_impact'].getValue():g}, "
            f"Cost = {data['total_cost'].getValue():g}"
        )
    else:
        print(f"Optimization ended with Gurobi status code {model.Status}.")


if __name__ == "__main__":
    main()
