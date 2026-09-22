from pathlib import Path

from src.routing import (
    add_free_flow_travel_times,
    build_drive_graph,
    dijkstra_fastest_route,
    plot_route,
)


# Example coordinates in Morocco.
ORIGIN = (32.93210288339607, -5.6613932957355715)
DESTINATION = (34.23038027794419, -3.3500597061072726)


def main() -> None:
    graph = build_drive_graph(*ORIGIN, *DESTINATION)
    graph = add_free_flow_travel_times(graph)

    result = dijkstra_fastest_route(graph, *ORIGIN, *DESTINATION)

    print(f"Fastest route: {result.travel_time_min:.1f} min")
    print(f"Distance: {result.distance_km:.2f} km")

    plot_route(
        graph,
        result,
        output=Path("outputs/fastest_route.png"),
    )


if __name__ == "__main__":
    main()
