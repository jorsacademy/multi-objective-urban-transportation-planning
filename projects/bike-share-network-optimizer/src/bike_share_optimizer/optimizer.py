"""Core bike-share network planning and optimization utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


class BikeShareOptimizer:
    """Optimize bike-share station placement, flows, fleet mix, and capacity."""

    def __init__(self, existing_stations=None, potential_locations=None):
        self.existing_stations = (
            existing_stations.copy() if existing_stations is not None else pd.DataFrame()
        )
        self.potential_locations = (
            potential_locations.copy() if potential_locations is not None else pd.DataFrame()
        )
        self.transit_nodes = pd.DataFrame()
        self.trip_data = pd.DataFrame()
        self.demand_model = None
        self.flow_model = None

    def load_data(self, trip_data=None, transit_nodes=None):
        if trip_data is not None:
            self.trip_data = trip_data.copy()
        if transit_nodes is not None:
            self.transit_nodes = transit_nodes.copy()

    def build_demand_model(self, features=None):
        if self.trip_data.empty:
            raise ValueError("Trip data must be loaded before building demand model")

        station_demand = self.trip_data.groupby("start_station").size().reset_index()
        station_demand.columns = ["station_id", "demand"]
        self.demand_model = station_demand
        return station_demand

    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """Return great-circle distance between two coordinates in kilometers."""
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        return 6371.0 * 2 * np.arcsin(np.sqrt(a))

    def predict_rider_flow(self, new_stations=None):
        if self.trip_data.empty:
            raise ValueError("Trip data must be loaded before predicting rider flow")

        station_ids = list(self.existing_stations["station_id"])
        if new_stations is not None:
            station_ids.extend(list(new_stations["station_id"]))

        flow_matrix = pd.DataFrame(0.0, index=station_ids, columns=station_ids)
        trip_counts = (
            self.trip_data.groupby(["start_station", "end_station"])
            .size()
            .reset_index(name="trips")
        )

        for row in trip_counts.itertuples(index=False):
            if row.start_station in flow_matrix.index and row.end_station in flow_matrix.columns:
                flow_matrix.loc[row.start_station, row.end_station] = float(row.trips)

        if new_stations is not None and not new_stations.empty:
            self._predict_new_station_flows(flow_matrix, new_stations)

        self.flow_model = flow_matrix
        return flow_matrix

    def _predict_new_station_flows(self, flow_matrix, new_stations):
        all_stations = pd.concat(
            [
                self.existing_stations[["station_id", "latitude", "longitude"]],
                new_stations[["station_id", "latitude", "longitude"]],
            ],
            ignore_index=True,
        )
        station_coords = all_stations.set_index("station_id")[["latitude", "longitude"]]

        station_demand = pd.DataFrame({"station_id": flow_matrix.index})
        if self.demand_model is not None:
            station_demand = station_demand.merge(self.demand_model, on="station_id", how="left")
        else:
            station_demand["demand"] = [flow_matrix.loc[s].mean() for s in flow_matrix.index]

        median_demand = station_demand["demand"].median()
        if pd.isna(median_demand) or median_demand <= 0:
            median_demand = 1.0
        station_demand["demand"] = station_demand["demand"].fillna(median_demand)
        demand = station_demand.set_index("station_id")["demand"]

        historical = flow_matrix.to_numpy(dtype=float)
        positive = historical[historical > 0]
        historical_mean = float(positive.mean()) if positive.size else 1.0

        raw_predictions = []
        for i in new_stations["station_id"]:
            for j in flow_matrix.index:
                if i == j or flow_matrix.loc[i, j] > 0 or flow_matrix.loc[j, i] > 0:
                    continue

                lat1, lon1 = station_coords.loc[i]
                lat2, lon2 = station_coords.loc[j]
                distance_km = max(self._haversine_distance(lat1, lon1, lat2, lon2), 0.05)
                raw_flow = float((demand.loc[i] * demand.loc[j]) / (distance_km**2))
                raw_predictions.append((i, j, raw_flow))

        if not raw_predictions:
            return

        raw_mean = float(np.mean([value for _, _, value in raw_predictions]))
        scale_factor = historical_mean / raw_mean if raw_mean > 0 else 1.0

        for i, j, raw_flow in raw_predictions:
            predicted = raw_flow * scale_factor
            flow_matrix.loc[i, j] = predicted
            flow_matrix.loc[j, i] = predicted

    def evaluate_transit_integration(self):
        if self.transit_nodes.empty:
            raise ValueError("Transit nodes must be loaded before evaluating integration")

        results = []
        for station in self.existing_stations.itertuples(index=False):
            score = 0.0
            for node in self.transit_nodes.itertuples(index=False):
                distance = self._haversine_distance(
                    station.latitude, station.longitude, node.latitude, node.longitude
                )
                if distance <= 0.5:
                    score += float(node.ridership) * (1 - distance / 0.5)
            results.append({"station_id": station.station_id, "transit_score": score})
        return pd.DataFrame(results)

    def assess_station_poi_proximity(self, random_state=42):
        """Generate demo POI scores when external POI data is unavailable."""
        rng = np.random.default_rng(random_state)
        return pd.DataFrame(
            {
                "station_id": self.existing_stations["station_id"].values,
                "poi_score": rng.uniform(0, 10, size=len(self.existing_stations)),
            }
        )

    @staticmethod
    def _safe_normalize(series):
        max_value = series.max()
        if pd.isna(max_value) or max_value <= 0:
            return pd.Series(0.0, index=series.index)
        return series / max_value

    def optimize_new_stations(self, num_stations=5, equity_weight=0.5):
        if self.potential_locations.empty:
            raise ValueError("Potential locations must be loaded before optimizing")
        if num_stations <= 0:
            raise ValueError("num_stations must be positive")
        if not 0 <= equity_weight <= 1:
            raise ValueError("equity_weight must be between 0 and 1")

        locations = self.potential_locations.copy()
        min_distances = []

        for candidate in locations.itertuples(index=False):
            if self.existing_stations.empty:
                min_distances.append(0.0)
                continue
            distances = [
                self._haversine_distance(
                    candidate.latitude,
                    candidate.longitude,
                    station.latitude,
                    station.longitude,
                )
                for station in self.existing_stations.itertuples(index=False)
            ]
            min_distances.append(min(distances))

        locations["min_distance_km"] = min_distances
        poi_norm = self._safe_normalize(locations["poi_score"])
        equity_norm = self._safe_normalize(locations["equity_score"])
        distance_norm = self._safe_normalize(locations["min_distance_km"])

        locations["combined_score"] = (
            (1 - equity_weight) * poi_norm
            + equity_weight * equity_norm
            + 0.5 * distance_norm
        )

        selected = locations.nlargest(num_stations, "combined_score")
        return selected[
            ["location_id", "latitude", "longitude", "poi_score", "equity_score", "combined_score"]
        ].rename(columns={"location_id": "station_id"})

    def optimize_fleet_mix(self, total_bikes=1000, e_bike_cost_ratio=2.5):
        if self.trip_data.empty:
            raise ValueError("Trip data must be loaded before optimizing fleet mix")
        if total_bikes <= 0:
            raise ValueError("total_bikes must be positive")
        if e_bike_cost_ratio <= 0:
            raise ValueError("e_bike_cost_ratio must be positive")

        distances = (
            self.trip_data["distance"]
            if "distance" in self.trip_data.columns
            else pd.Series(1.0, index=self.trip_data.index)
        )
        median_distance = distances.median()
        long_trip_share = float((distances > median_distance).mean())
        adjusted_share = min(max(long_trip_share / np.sqrt(e_bike_cost_ratio), 0.0), 1.0)

        e_bikes = int(total_bikes * adjusted_share)
        regular_bikes = total_bikes - e_bikes
        return {
            "regular_bikes": regular_bikes,
            "e_bikes": e_bikes,
            "total_bikes": total_bikes,
            "e_bike_percentage": round(e_bikes / total_bikes * 100, 1),
        }

    def recommend_station_capacity(self):
        if self.flow_model is None:
            raise ValueError("Flow model must be built before recommending capacity")

        inflow = self.flow_model.sum(axis=0)
        outflow = self.flow_model.sum(axis=1)
        peak = pd.DataFrame(
            {"station_id": inflow.index, "inflow": inflow.values, "outflow": outflow.values}
        )
        peak["max_flow"] = peak[["inflow", "outflow"]].max(axis=1)
        peak["recommended_capacity"] = (
            np.ceil(peak["max_flow"] * 0.2).astype(int).clip(lower=10)
        )
        return peak[["station_id", "recommended_capacity"]]
