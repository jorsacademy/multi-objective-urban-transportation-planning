from src.model import sample_data, solve_fleet_circulation


def main() -> None:
    trips, fleet, depots, reposition = sample_data()
    solution = solve_fleet_circulation(trips, fleet, depots, reposition)

    print("Intercity Rail Fleet Circulation Optimization")
    print("=" * 46)
    print(f"Objective: {solution.objective:,.2f}")
    print(f"Deadhead distance: {solution.deadhead_km:,.1f} km")
    print(f"MIP gap: {solution.mip_gap}")
    print(f"MIP node count: {solution.mip_node_count}")

    print("\nFleet usage:")
    for fleet_id, count in solution.units_used.items():
        print(f"  {fleet_id}: {count}")

    print("\nCirculation starts:")
    for depot, trip_id, fleet_id in solution.starts:
        print(f"  {fleet_id}: depot {depot} -> {trip_id}")

    print("\nTrip-to-trip links:")
    for first, second, fleet_id in solution.links:
        print(f"  {fleet_id}: {first} -> {second}")

    print("\nCirculation ends:")
    for trip_id, depot, fleet_id in solution.ends:
        print(f"  {fleet_id}: {trip_id} -> depot {depot}")


if __name__ == "__main__":
    main()
