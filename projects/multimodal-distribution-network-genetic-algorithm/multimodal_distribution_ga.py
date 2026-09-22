from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import copy
import math
import random

import matplotlib.pyplot as plt
import numpy as np


NUM_LOCATIONS = 15
NUM_CUSTOMERS = 25
NUM_CAPACITY_LEVELS = 3
NUM_TRANSPORT_MODES = 3

MAX_DCS = 8
MIN_UTILIZATION_SHARE = 0.15
CAPACITY_BUFFER = 1.20

# Because every open DC must serve at least 15% of total demand,
# at most floor(1 / 0.15) = 6 DCs can be simultaneously feasible.
EFFECTIVE_MAX_DCS = min(MAX_DCS, math.floor(1.0 / MIN_UTILIZATION_SHARE))

MODE_NAMES = ("Truck", "Rail", "Air")
CAPACITY_NAMES = ("Small", "Medium", "Large")


@dataclass
class Individual:
    """Chromosome: (C, A, T).

    C[i] in {0,1,2,3}: 0=closed, 1..3=capacity level.
    A[j] in {0,...,14}: DC assigned to customer j.
    T[j] in {0,1,2}: transport mode used for customer j.
    """
    capacities: List[int]
    assignments: List[int]
    transport_modes: List[int]
    fitness: float = math.inf

    def clone(self) -> "Individual":
        return copy.deepcopy(self)


class DistributionNetworkGA:
    """Genetic algorithm for a capacitated multi-modal distribution network.

    The implementation follows the single-sourcing interpretation:
    each customer is assigned to exactly one open DC and one available mode.
    Its full demand is shipped on that assignment, so demand satisfaction is automatic.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.py_rng = random.Random(seed)
        self.setup_problem_data()

    def setup_problem_data(self) -> None:
        base_fixed = self.rng.uniform(1.5, 3.0, (NUM_LOCATIONS, NUM_CAPACITY_LEVELS))
        base_fixed[:, 1] *= 2.5
        base_fixed[:, 2] *= 5.0
        self.fixed_costs = base_fixed

        self.operating_costs = self.rng.uniform(
            0.1, 0.5, (NUM_LOCATIONS, NUM_CAPACITY_LEVELS)
        )

        self.capacities = np.zeros((NUM_LOCATIONS, NUM_CAPACITY_LEVELS))
        self.capacities[:, 0] = self.rng.uniform(100, 200, NUM_LOCATIONS)
        self.capacities[:, 1] = self.rng.uniform(300, 500, NUM_LOCATIONS)
        self.capacities[:, 2] = self.rng.uniform(600, 1000, NUM_LOCATIONS)

        self.demands = self.rng.uniform(20, 80, NUM_CUSTOMERS)
        self.total_demand = float(self.demands.sum())

        self.location_coords = self.rng.uniform(0, 100, (NUM_LOCATIONS, 2))
        self.customer_coords = self.rng.uniform(0, 100, (NUM_CUSTOMERS, 2))
        delta = self.location_coords[:, None, :] - self.customer_coords[None, :, :]
        self.distances = np.linalg.norm(delta, axis=2)

        mode_multipliers = np.array([1.0, 0.7, 2.0])
        self.transport_costs = (
            self.distances[:, :, None] * mode_multipliers[None, None, :] * 0.01
        )

        self.mode_availability = self.rng.choice(
            [0, 1],
            size=(NUM_LOCATIONS, NUM_TRANSPORT_MODES),
            p=[0.2, 0.8],
        )
        for i in range(NUM_LOCATIONS):
            if self.mode_availability[i].sum() == 0:
                self.mode_availability[i, 0] = 1

    def _open_dcs(self, individual: Individual) -> List[int]:
        return [i for i, level in enumerate(individual.capacities) if level > 0]

    def create_individual(self) -> Individual:
        n_open = self.py_rng.randint(3, EFFECTIVE_MAX_DCS)
        open_dcs = self.py_rng.sample(range(NUM_LOCATIONS), n_open)

        capacity_levels = [0] * NUM_LOCATIONS
        for i in open_dcs:
            capacity_levels[i] = self.py_rng.randint(1, NUM_CAPACITY_LEVELS)

        assignments = [self.py_rng.choice(open_dcs) for _ in range(NUM_CUSTOMERS)]
        transport_modes = []
        for dc in assignments:
            available = np.flatnonzero(self.mode_availability[dc]).tolist()
            transport_modes.append(self.py_rng.choice(available))

        ind = Individual(capacity_levels, assignments, transport_modes)
        self.repair_individual(ind)
        return ind

    def repair_individual(self, individual: Individual) -> None:
        individual.capacities = [
            int(min(NUM_CAPACITY_LEVELS, max(0, level)))
            for level in individual.capacities
        ]

        open_dcs = self._open_dcs(individual)

        if not open_dcs:
            i = self.py_rng.randrange(NUM_LOCATIONS)
            individual.capacities[i] = self.py_rng.randint(1, NUM_CAPACITY_LEVELS)
            open_dcs = [i]

        if len(open_dcs) > EFFECTIVE_MAX_DCS:
            scored = []
            for i in open_dcs:
                level = individual.capacities[i] - 1
                score = self.fixed_costs[i, level] / max(self.capacities[i, level], 1e-9)
                scored.append((score, i))
            scored.sort(reverse=True)
            to_close = [i for _, i in scored[: len(open_dcs) - EFFECTIVE_MAX_DCS]]
            for i in to_close:
                individual.capacities[i] = 0
            open_dcs = self._open_dcs(individual)

        required_capacity = CAPACITY_BUFFER * self.total_demand
        for _ in range(NUM_LOCATIONS * NUM_CAPACITY_LEVELS):
            total_capacity = sum(
                self.capacities[i, individual.capacities[i] - 1] for i in open_dcs
            )
            if total_capacity >= required_capacity:
                break

            upgrade_candidates = [
                i for i in open_dcs if individual.capacities[i] < NUM_CAPACITY_LEVELS
            ]
            if upgrade_candidates:
                def upgrade_value(i: int) -> float:
                    old = individual.capacities[i] - 1
                    new = old + 1
                    dc = self.capacities[i, new] - self.capacities[i, old]
                    df = self.fixed_costs[i, new] - self.fixed_costs[i, old]
                    return dc / max(df, 1e-9)

                best = max(upgrade_candidates, key=upgrade_value)
                individual.capacities[best] += 1
                continue

            if len(open_dcs) < EFFECTIVE_MAX_DCS:
                closed = [i for i in range(NUM_LOCATIONS) if i not in open_dcs]
                if closed:
                    best = max(closed, key=lambda i: self.capacities[i, -1])
                    individual.capacities[best] = NUM_CAPACITY_LEVELS
                    open_dcs.append(best)
                    continue
            break

        open_dcs = self._open_dcs(individual)

        for j in range(NUM_CUSTOMERS):
            if individual.assignments[j] not in open_dcs:
                individual.assignments[j] = self.py_rng.choice(open_dcs)

        self._repair_assignments_by_load(individual)

        for j, dc in enumerate(individual.assignments):
            mode = int(individual.transport_modes[j]) % NUM_TRANSPORT_MODES
            if self.mode_availability[dc, mode] == 0:
                available = np.flatnonzero(self.mode_availability[dc]).tolist()
                mode = min(available, key=lambda m: self.transport_costs[dc, j, m])
            individual.transport_modes[j] = mode

        individual.fitness = math.inf

    def _repair_assignments_by_load(self, individual: Individual) -> None:
        open_dcs = self._open_dcs(individual)
        if not open_dcs:
            return

        max_caps = {
            i: self.capacities[i, individual.capacities[i] - 1] for i in open_dcs
        }
        min_load = MIN_UTILIZATION_SHARE * self.total_demand

        loads = {i: 0.0 for i in open_dcs}
        assignments = [-1] * NUM_CUSTOMERS

        customers = sorted(
            range(NUM_CUSTOMERS), key=lambda j: self.demands[j], reverse=True
        )
        unassigned = set(customers)

        for i in open_dcs:
            while loads[i] < min_load and unassigned:
                feasible = [
                    j for j in unassigned
                    if loads[i] + self.demands[j] <= max_caps[i] + 1e-9
                ]
                if not feasible:
                    break
                j = min(
                    feasible,
                    key=lambda jj: (
                        abs((loads[i] + self.demands[jj]) - min_load),
                        self.transport_costs[i, jj].min(),
                    ),
                )
                assignments[j] = i
                loads[i] += float(self.demands[j])
                unassigned.remove(j)

        for j in sorted(unassigned, key=lambda jj: self.demands[jj], reverse=True):
            feasible = [
                i for i in open_dcs
                if loads[i] + self.demands[j] <= max_caps[i] + 1e-9
            ]
            candidates = feasible if feasible else open_dcs
            dc = min(
                candidates,
                key=lambda i: (
                    self.operating_costs[i, individual.capacities[i] - 1]
                    + self.transport_costs[i, j].min()
                    + max(0.0, loads[i] + self.demands[j] - max_caps[i]) * 1000.0
                ),
            )
            assignments[j] = dc
            loads[dc] += float(self.demands[j])

        individual.assignments = assignments

    def evaluate(self, individual: Individual) -> float:
        open_dcs = self._open_dcs(individual)
        if not open_dcs:
            return math.inf

        fixed_cost = 0.0
        operating_cost = 0.0
        transport_cost = 0.0
        loads = np.zeros(NUM_LOCATIONS)

        for i in open_dcs:
            level = individual.capacities[i] - 1
            fixed_cost += self.fixed_costs[i, level]

        invalid_assignment = 0
        invalid_mode = 0

        for j in range(NUM_CUSTOMERS):
            dc = individual.assignments[j]
            mode = individual.transport_modes[j]

            if dc not in open_dcs:
                invalid_assignment += 1
                continue
            if not (0 <= mode < NUM_TRANSPORT_MODES) or self.mode_availability[dc, mode] == 0:
                invalid_mode += 1
                continue

            demand = float(self.demands[j])
            loads[dc] += demand
            level = individual.capacities[dc] - 1
            operating_cost += self.operating_costs[dc, level] * demand
            transport_cost += self.transport_costs[dc, j, mode] * demand

        capacity_violation = 0.0
        utilization_violation = 0.0
        total_capacity = 0.0

        min_load = MIN_UTILIZATION_SHARE * self.total_demand
        for i in open_dcs:
            level = individual.capacities[i] - 1
            cap = float(self.capacities[i, level])
            total_capacity += cap
            capacity_violation += max(0.0, loads[i] - cap) / max(cap, 1e-9)
            utilization_violation += max(0.0, min_load - loads[i]) / max(min_load, 1e-9)

        required_capacity = CAPACITY_BUFFER * self.total_demand
        reserve_violation = max(0.0, required_capacity - total_capacity) / required_capacity
        dc_count_violation = max(0, len(open_dcs) - MAX_DCS)

        base_cost = fixed_cost + operating_cost + transport_cost
        normalized_violation = (
            capacity_violation
            + utilization_violation
            + reserve_violation
            + invalid_assignment
            + invalid_mode
            + dc_count_violation
        )
        penalty = max(base_cost, 1.0) * 100.0 * normalized_violation

        individual.fitness = base_cost + penalty
        return individual.fitness

    def crossover(self, p1: Individual, p2: Individual) -> Tuple[Individual, Individual]:
        c1, c2 = p1.clone(), p2.clone()

        for i in range(NUM_LOCATIONS):
            if self.py_rng.random() < 0.5:
                c1.capacities[i], c2.capacities[i] = c2.capacities[i], c1.capacities[i]

        for j in range(NUM_CUSTOMERS):
            if self.py_rng.random() < 0.5:
                c1.assignments[j], c2.assignments[j] = c2.assignments[j], c1.assignments[j]
                c1.transport_modes[j], c2.transport_modes[j] = (
                    c2.transport_modes[j],
                    c1.transport_modes[j],
                )

        self.repair_individual(c1)
        self.repair_individual(c2)
        return c1, c2

    def mutate(self, individual: Individual, gene_prob: float = 0.08) -> None:
        for i in range(NUM_LOCATIONS):
            if self.py_rng.random() < gene_prob:
                individual.capacities[i] = self.py_rng.randint(0, NUM_CAPACITY_LEVELS)

        open_dcs = self._open_dcs(individual)
        if not open_dcs:
            i = self.py_rng.randrange(NUM_LOCATIONS)
            individual.capacities[i] = self.py_rng.randint(1, NUM_CAPACITY_LEVELS)
            open_dcs = [i]

        for j in range(NUM_CUSTOMERS):
            if self.py_rng.random() < gene_prob:
                individual.assignments[j] = self.py_rng.choice(open_dcs)
            if self.py_rng.random() < gene_prob:
                dc = individual.assignments[j]
                available = np.flatnonzero(self.mode_availability[dc]).tolist()
                individual.transport_modes[j] = self.py_rng.choice(available)

        self.repair_individual(individual)

    def tournament(self, population: List[Individual], k: int = 3) -> Individual:
        contestants = self.py_rng.sample(population, k)
        return min(contestants, key=lambda ind: ind.fitness)

    def run(
        self,
        pop_size: int = 150,
        generations: int = 300,
        crossover_prob: float = 0.80,
        mutation_prob: float = 0.20,
        elitism: int = 2,
        verbose: bool = True,
    ) -> Tuple[Individual, dict]:
        population = [self.create_individual() for _ in range(pop_size)]
        for ind in population:
            self.evaluate(ind)

        history = {"generation": [], "minimum": [], "average": []}

        for gen in range(generations + 1):
            fits = np.array([ind.fitness for ind in population], dtype=float)
            history["generation"].append(gen)
            history["minimum"].append(float(fits.min()))
            history["average"].append(float(fits.mean()))

            if verbose and (gen == 0 or gen % 20 == 0 or gen == generations):
                print(f"gen={gen:3d}  min={fits.min():.4f}  avg={fits.mean():.4f}")

            if gen == generations:
                break

            population.sort(key=lambda ind: ind.fitness)
            next_population = [
                population[i].clone() for i in range(min(elitism, pop_size))
            ]

            while len(next_population) < pop_size:
                p1 = self.tournament(population)
                p2 = self.tournament(population)

                if self.py_rng.random() < crossover_prob:
                    c1, c2 = self.crossover(p1, p2)
                else:
                    c1, c2 = p1.clone(), p2.clone()

                if self.py_rng.random() < mutation_prob:
                    self.mutate(c1)
                if self.py_rng.random() < mutation_prob:
                    self.mutate(c2)

                self.evaluate(c1)
                self.evaluate(c2)
                next_population.extend([c1, c2])

            population = next_population[:pop_size]

        best = min(population, key=lambda ind: ind.fitness).clone()
        return best, history

    def cost_breakdown(self, individual: Individual) -> Tuple[float, float, float]:
        fixed = operating = transport = 0.0
        for i in self._open_dcs(individual):
            level = individual.capacities[i] - 1
            fixed += self.fixed_costs[i, level]

        for j in range(NUM_CUSTOMERS):
            dc = individual.assignments[j]
            mode = individual.transport_modes[j]
            level = individual.capacities[dc] - 1
            demand = float(self.demands[j])
            operating += self.operating_costs[dc, level] * demand
            transport += self.transport_costs[dc, j, mode] * demand

        return fixed, operating, transport

    def analyze_solution(self, individual: Individual) -> None:
        open_dcs = self._open_dcs(individual)
        loads = np.zeros(NUM_LOCATIONS)
        for j, dc in enumerate(individual.assignments):
            loads[dc] += self.demands[j]

        fixed, operating, transport = self.cost_breakdown(individual)
        print("\n=== SOLUTION ANALYSIS ===")
        print(f"Objective value: {individual.fitness:,.4f}")
        print(f"Base cost:       {fixed + operating + transport:,.4f}")
        print(f"Open DCs:        {len(open_dcs)}")
        print(f"Total demand:    {self.total_demand:,.2f}")

        for i in open_dcs:
            level = individual.capacities[i] - 1
            cap = self.capacities[i, level]
            utilization = 100.0 * loads[i] / cap
            print(
                f"  DC {i:02d} | {CAPACITY_NAMES[level]:6s} | "
                f"load={loads[i]:7.2f} / cap={cap:7.2f} | util={utilization:6.2f}%"
            )

        counts = np.bincount(individual.transport_modes, minlength=NUM_TRANSPORT_MODES)
        print("\nMode usage:")
        for m, count in enumerate(counts):
            print(f"  {MODE_NAMES[m]}: {count} customers")

        print("\nCost breakdown:")
        print(f"  Fixed:         {fixed:,.4f}")
        print(f"  Operating:     {operating:,.4f}")
        print(f"  Transportation:{transport:,.4f}")

    def plot_history(self, history: dict, output_path: str | None = None) -> None:
        plt.figure(figsize=(9, 5))
        plt.plot(history["generation"], history["minimum"], label="Minimum")
        plt.plot(history["generation"], history["average"], label="Average")
        plt.xlabel("Generation")
        plt.ylabel("Objective value")
        plt.title("GA convergence")
        plt.legend()
        plt.grid(alpha=0.25)
        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=160)
            plt.close()
        else:
            plt.show()


def main() -> None:
    ga = DistributionNetworkGA(seed=42)
    best, history = ga.run(
        pop_size=150,
        generations=300,
        crossover_prob=0.80,
        mutation_prob=0.20,
        elitism=2,
        verbose=True,
    )
    ga.analyze_solution(best)
    ga.plot_history(history)


if __name__ == "__main__":
    main()
