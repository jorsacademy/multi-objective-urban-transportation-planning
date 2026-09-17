# Multi-Objective and Trade-Off Optimization Research Series

This file maps repositories where several competing objectives, priorities, or trade-offs are explicit parts of the decision problem. It is an index only: each repository remains independent because the objective structure and solution method differ.

## Mathematical multi-objective optimization

- `multi-objective-urban-transportation-planning` — hierarchical multi-objective integer optimization with travel time, environmental impact, and operating cost.
- `mean-variance-portfolio-cardinality-optimization` — risk-return trade-off with cardinality constraints; not a generic Pareto model, but an important structured trade-off problem.
- `fleet-decarbonization-optimizer` — long-horizon fleet decisions where economic and decarbonization considerations interact.

## Evolutionary multi-objective optimization

- `multi-objective-cvrp-nsga2-python` — routing solved with NSGA-II/Pareto search rather than hierarchical exact optimization.

## Learned multi-objective combinatorial optimization

- `multi-objective-neural-combinatorial-optimization` — learned solution policies for multi-objective combinatorial problems.

## Related design and process trade-offs

- `wind-farm-layout-optimization` — energy production, spacing, and wake effects combined in a mathematical-programming design model.
- `wind-farm-layout-optimizer` — heuristic alternative for related layout trade-offs.
- `adaptive-cooling-metal-fabrication-optimization` — process-performance trade-offs in an industrial setting.
- `constrained-bayesian-optimization-chemical-process-python` — expensive black-box process optimization where objectives interact with feasibility constraints.

## Why these repositories stay separate

Multi-objective research can mean very different things:

- lexicographic or hierarchical objectives;
- weighted scalarization;
- explicit Pareto-front approximation;
- evolutionary multi-objective search;
- risk-return trade-offs;
- learned policies conditioned on objective preferences.

Those distinctions materially affect the algorithms and evaluation metrics, so a shared multi-objective theme is useful for comparison but not a consolidation criterion.
