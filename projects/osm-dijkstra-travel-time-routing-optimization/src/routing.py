"""Travel-time weighted Dijkstra routing on OpenStreetMap road networks.

The implementation targets OSMnx 2.x. Edge weights are free-flow travel times in
seconds, derived from OSM edge lengths and speed estimates. The shortest-path
solver delegates to OSMnx's routing.shortest_path, which uses Dijkstra's
algorithm for a single origin/destination pair with a non-negative weight.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
from shapely.geometry import box


@dataclass(frozen=True)
class RouteResult:
    route: list[int]
    distance_m: float
    travel_time_s: float

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000

    @property
    def travel_time_min(self) -> float:
        return self.travel_time_s / 60


DEFAULT_HIGHWAY_SPEEDS: dict[str, float] = {
    "motorway": 100,
    "motorway_link": 70,
    "trunk": 90,
    "trunk_link": 60,
    "primary": 70,
    "primary_link": 50,
    "secondary": 60,
    "secondary_link": 45,
    "tertiary": 50,
    "tertiary_link": 40,
    "residential": 35,
    "living_street": 20,
    "service": 25,
    "unclassified": 35,
}


def build_drive_graph(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    *,
    padding_deg: float = 0.08,
) -> nx.MultiDiGraph:
    """Download a drive network covering the origin/destination bounding box.

    ``padding_deg`` is deliberately explicit because this graph-construction
    strategy is suitable for regional examples but not for global routing.
    """

    west = min(origin_lon, destination_lon) - padding_deg
    east = max(origin_lon, destination_lon) + padding_deg
    south = min(origin_lat, destination_lat) - padding_deg
    north = max(origin_lat, destination_lat) + padding_deg
    polygon = box(west, south, east, north)

    return ox.graph.graph_from_polygon(
        polygon,
        network_type="drive",
        simplify=True,
        retain_all=False,
    )


def add_free_flow_travel_times(
    graph: nx.MultiDiGraph,
    *,
    highway_speeds: Mapping[str, float] | None = None,
    fallback_speed_kph: float = 40.0,
) -> nx.MultiDiGraph:
    """Add ``speed_kph`` and ``travel_time`` edge attributes.

    OSMnx first uses tagged ``maxspeed`` values where available, then imputes
    missing values by highway class. Travel time is subsequently computed from
    edge ``length`` and ``speed_kph``.
    """

    speeds = dict(DEFAULT_HIGHWAY_SPEEDS)
    if highway_speeds:
        speeds.update(highway_speeds)

    graph = ox.routing.add_edge_speeds(
        graph,
        hwy_speeds=speeds,
        fallback=fallback_speed_kph,
    )
    graph = ox.routing.add_edge_travel_times(graph)
    return graph


def dijkstra_fastest_route(
    graph: nx.MultiDiGraph,
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
) -> RouteResult:
    """Compute the minimum-travel-time route between two coordinates."""

    origin_node = ox.distance.nearest_nodes(graph, X=origin_lon, Y=origin_lat)
    destination_node = ox.distance.nearest_nodes(
        graph,
        X=destination_lon,
        Y=destination_lat,
    )

    route = ox.routing.shortest_path(
        graph,
        origin_node,
        destination_node,
        weight="travel_time",
    )
    if route is None:
        raise nx.NetworkXNoPath("No drivable path exists between the selected points.")

    route_edges = ox.routing.route_to_gdf(graph, route, weight="travel_time")

    return RouteResult(
        route=route,
        distance_m=float(route_edges["length"].sum()),
        travel_time_s=float(route_edges["travel_time"].sum()),
    )


def _road_style(highway: object) -> tuple[str, float, float]:
    """Return cartographic color, linewidth and alpha for one OSM edge."""

    if isinstance(highway, list):
        highway = highway[0] if highway else ""
    hwy = str(highway)

    if hwy in {"motorway", "motorway_link", "trunk", "trunk_link"}:
        return "#38577A", 0.85, 0.80
    if hwy in {"primary", "primary_link", "secondary", "secondary_link"}:
        return "#284867", 0.55, 0.65
    return "#17324D", 0.30, 0.48


def plot_route(
    graph: nx.MultiDiGraph,
    result: RouteResult,
    *,
    output: str | Path | None = None,
    title: str = "Dijkstra's algorithm weighted by travel time in OSM networks",
) -> tuple[plt.Figure, plt.Axes]:
    """Render a navy cartographic network with a high-contrast amber route."""

    graph_projected = ox.projection.project_graph(graph)
    route_edges = ox.routing.route_to_gdf(
        graph_projected,
        result.route,
        weight="travel_time",
    )
    edges = ox.convert.graph_to_gdfs(graph_projected, nodes=False)

    edge_colors: list[str] = []
    edge_widths: list[float] = []
    edge_alphas: list[float] = []
    for highway in edges["highway"]:
        color, width, alpha = _road_style(highway)
        edge_colors.append(color)
        edge_widths.append(width)
        edge_alphas.append(alpha)

    background = "#07111F"
    route_color = "#F3A52B"

    fig, ax = plt.subplots(figsize=(14, 8), dpi=170)
    fig.patch.set_facecolor(background)
    ax.set_facecolor(background)

    # Plot per-class road hierarchy to avoid the flat, bright network look.
    for geometry, color, linewidth, alpha in zip(
        edges.geometry,
        edge_colors,
        edge_widths,
        edge_alphas,
    ):
        if geometry is None:
            continue
        x, y = geometry.xy
        ax.plot(
            x,
            y,
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            solid_capstyle="round",
            zorder=1,
        )

    # Subtle dark halo beneath the route improves legibility on dense networks.
    route_edges.plot(
        ax=ax,
        color="#020810",
        linewidth=5.0,
        alpha=0.70,
        zorder=4,
    )
    route_edges.plot(
        ax=ax,
        color=route_color,
        linewidth=2.6,
        alpha=0.98,
        zorder=5,
    )

    nodes = ox.convert.graph_to_gdfs(graph_projected, edges=False)
    start = nodes.loc[result.route[0]].geometry
    end = nodes.loc[result.route[-1]].geometry
    ax.scatter(
        [start.x, end.x],
        [start.y, end.y],
        s=[28, 28],
        c=[route_color, route_color],
        edgecolors="#FFE4A3",
        linewidths=0.8,
        zorder=6,
    )

    ax.set_title(title, color="#D9E5F2", fontsize=14, pad=14)
    ax.text(
        0.015,
        0.025,
        f"{result.distance_km:.1f} km  •  {result.travel_time_min:.0f} min",
        transform=ax.transAxes,
        color="#91A9C1",
        fontsize=9,
        ha="left",
        va="bottom",
    )
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.tight_layout(pad=0.4)

    if output is not None:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            output,
            dpi=300,
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
        )

    return fig, ax
