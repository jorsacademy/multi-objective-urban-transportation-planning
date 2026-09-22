# OSM Dijkstra Travel-Time Routing Optimization

Travel-time weighted shortest-path routing on OpenStreetMap road networks with OSMnx and Dijkstra's algorithm.

The project downloads a drivable OSM network between two coordinates, derives free-flow edge travel times from road length and speed estimates, solves the minimum-travel-time route, and renders the result using a dark navy cartographic style with an amber/orange route.

## Method

For each road edge, OSMnx provides or derives a length in meters. Speed values are obtained from OSM `maxspeed` tags when available and otherwise imputed from highway-class defaults. Edge travel time is then calculated from length and speed. The route solver minimizes the non-negative `travel_time` edge attribute using OSMnx's single-pair shortest-path routine, which uses Dijkstra's algorithm.

This is free-flow routing, not live-traffic routing. Congestion, incidents, turn delays, traffic signals, road closures, and time-dependent speeds are not modeled unless separately added to the graph.

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run the example

From the repository root:

```bash
python -m examples.example_route
```

The example writes its map to:

```text
outputs/fastest_route.png
```

## Core usage

```python
from src.routing import (
    add_free_flow_travel_times,
    build_drive_graph,
    dijkstra_fastest_route,
    plot_route,
)

origin = (32.93210288339607, -5.6613932957355715)
destination = (34.23038027794419, -3.3500597061072726)

graph = build_drive_graph(*origin, *destination)
graph = add_free_flow_travel_times(graph)
result = dijkstra_fastest_route(graph, *origin, *destination)

print(result.distance_km)
print(result.travel_time_min)

plot_route(graph, result, output="outputs/fastest_route.png")
```

## Cartographic style

The visualization intentionally avoids the default bright OSMnx appearance. Minor streets are subdued, higher-order roads are slightly emphasized, the canvas is dark navy, and the selected route is drawn in amber with a subtle halo for legibility.

## Accuracy and limitations

- OSMnx 2.x is the supported API family.
- Travel times are estimates based on OSM speed metadata and fallback highway-class speeds.
- The downloaded graph uses a buffered bounding box around the two coordinates. This is suitable for regional examples, but a larger/custom study polygon may be required when an optimal route would reasonably leave that corridor.
- OpenStreetMap data quality varies by region.
- A valid route requires the selected points to belong to a connected drivable component.

## License

This repository is source-available for non-commercial use only. Commercial use is prohibited. See `LICENSE` for the full terms.

The custom license is intentionally not an OSI-approved open-source license because OSI-compliant licenses cannot prohibit commercial use.
