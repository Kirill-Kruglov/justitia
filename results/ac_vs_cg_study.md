# Anti-Concentration vs Consequence Governance

Final verdict: **D. Only their combination is robust.**

## Validation Checks

| check | result |
|---|---:|
| feeder_observation_excludes_strategy_parameters | `True` |
| derived_exploitative_label_not_in_policy | `True` |
| fixed_hidden_types_absent | `True` |
| mutation_and_selection_occur | `True` |
| feature_proxy_fails_W1 | `True` |
| monoculture_fails_W5 | `True` |
| exploitative_strategies_rise_under_no_control | `True` |
| part_a_does_not_use_delayed_consequence | `True` |
| part_b_does_not_use_fixed_caps | `True` |
| at_least_one_core_cell_run_per_family | `True` |

## Part A First: Static Anti-Concentration

| world | best policy | permanence | perm lo | collapse hi | capture | exploit mass | welfare |
|---|---|---:|---:|---:|---:|---:|---:|
| W2_pure_capture | max_zone_share_cap | 0.000 | 0.000 | 1.000 | 0.650 | 0.632 | 0.017 |
| W4_scavenger_catastrophe | max_zone_share_cap | 0.000 | 0.000 | 1.000 | 0.703 | 0.672 | 0.131 |
| W6_mutation_corridor | max_zone_share_cap | 0.000 | 0.000 | 1.000 | 0.638 | 0.601 | 0.020 |
| W5_monoculture_shock | max_zone_share_cap | 0.000 | 0.000 | 0.267 | 0.384 | 0.000 | 0.470 |
| W3_catastrophe_ambiguity | max_zone_share_cap | 0.000 | 0.000 | 1.000 | 0.598 | 0.527 | 0.116 |

## Critical Publication Questions

1. Is the robust kernel actually blind consequence governance, or mostly anti-concentration? See world classifications below; Type AC means caps alone are sufficient.
2. Consequence feedback value beyond caps is measured by Part C and Part B rows versus Part A rows in `raw/summary.csv`.
3. Anti-concentration failure in catastrophe/scavenger worlds is visible in the Part A table above.
4. Consequence governance failure in pure capture is visible where Part B core rows fail seed-robust thresholds.
5. Unique necessity is classified by Type AC / Type CG / Type AC+CG per world.
6. Boundary conditions are represented by sweeps over pressure, mass, mutation, delay, severity, concentration, strength, and cost.

## World Classification

| world | classification | robustness | best family | best policy | permanence | perm lo | collapse hi | capture | welfare |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| W2_pure_capture | Type None | seed artifact | C | full_containment_kernel | 0.120 | 0.070 | 0.037 | 0.547 | 0.948 |
| W4_scavenger_catastrophe | Type AC+CG | robust | C | anti_concentration_plus_delayed_harm_throttle | 0.670 | 0.573 | 0.037 | 0.492 | 0.970 |
| W6_mutation_corridor | Type AC+CG | robust | C | anti_concentration_plus_delayed_harm_throttle | 1.000 | 0.963 | 0.037 | 0.406 | 0.958 |
| W5_monoculture_shock | Type None | seed artifact | C | anti_concentration_plus_delayed_harm_throttle | 0.000 | 0.000 | 0.037 | 0.320 | 0.804 |
| W3_catastrophe_ambiguity | Type AC+CG | robust | C | anti_concentration_plus_delayed_harm_throttle | 0.850 | 0.767 | 0.037 | 0.453 | 0.946 |

## Best Core Cells

| family | world | policy | permanence | perm lo | collapse hi | capture | exploit mass | welfare | response div | cost | MI |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | W6_mutation_corridor | anti_concentration_plus_delayed_harm_throttle | 1.000 | 0.963 | 0.037 | 0.406 | 0.150 | 0.958 | 0.964 | 0.008 | 0.013 |
| C | W6_mutation_corridor | full_containment_kernel | 1.000 | 0.963 | 0.037 | 0.418 | 0.173 | 0.957 | 0.965 | 0.008 | 0.013 |
| C | W3_catastrophe_ambiguity | anti_concentration_plus_delayed_harm_throttle | 0.850 | 0.767 | 0.037 | 0.453 | 0.117 | 0.946 | 0.931 | 0.013 | 0.013 |
| C | W3_catastrophe_ambiguity | full_containment_kernel | 0.810 | 0.722 | 0.037 | 0.453 | 0.115 | 0.947 | 0.924 | 0.013 | 0.010 |
| C | W4_scavenger_catastrophe | anti_concentration_plus_delayed_harm_throttle | 0.670 | 0.573 | 0.037 | 0.492 | 0.248 | 0.970 | 0.978 | 0.009 | 0.006 |
| C | W4_scavenger_catastrophe | full_containment_kernel | 0.320 | 0.237 | 0.037 | 0.513 | 0.277 | 0.969 | 0.979 | 0.009 | 0.007 |
| B | W3_catastrophe_ambiguity | delayed_harm_throttle | 0.170 | 0.109 | 0.037 | 0.540 | 0.201 | 0.933 | 0.908 | 0.014 | 0.013 |
| C | W2_pure_capture | full_containment_kernel | 0.120 | 0.070 | 0.037 | 0.547 | 0.351 | 0.948 | 0.907 | 0.014 | 0.008 |
| C | W2_pure_capture | anti_concentration_plus_delayed_harm_throttle | 0.100 | 0.055 | 0.037 | 0.557 | 0.372 | 0.931 | 0.909 | 0.014 | 0.008 |
| B | W3_catastrophe_ambiguity | consequence_weighted_migration_friction | 0.060 | 0.028 | 0.037 | 0.558 | 0.230 | 0.937 | 0.903 | 0.015 | 0.015 |
| B | W4_scavenger_catastrophe | delayed_harm_throttle | 0.020 | 0.006 | 0.037 | 0.570 | 0.377 | 0.934 | 0.981 | 0.011 | 0.009 |
| C | W5_monoculture_shock | anti_concentration_plus_delayed_harm_throttle | 0.000 | 0.000 | 0.037 | 0.320 | 0.000 | 0.804 | 0.501 | 0.036 | 0.000 |
| B | W5_monoculture_shock | consequence_weighted_migration_friction | 0.000 | 0.000 | 0.037 | 0.325 | 0.000 | 0.955 | 0.623 | 0.022 | 0.000 |
| C | W5_monoculture_shock | full_containment_kernel | 0.000 | 0.000 | 0.070 | 0.333 | 0.000 | 0.904 | 0.483 | 0.038 | 0.000 |
| B | W5_monoculture_shock | delayed_harm_throttle | 0.000 | 0.000 | 0.037 | 0.333 | 0.000 | 0.940 | 0.621 | 0.023 | 0.000 |
| A | W5_monoculture_shock | max_zone_share_cap | 0.000 | 0.000 | 0.267 | 0.384 | 0.000 | 0.470 | 0.992 | 0.000 | 0.000 |
| A | W5_monoculture_shock | random_allocation_plus_cap | 0.000 | 0.000 | 0.278 | 0.384 | 0.000 | 0.445 | 0.993 | 0.000 | 0.000 |
| B | W5_monoculture_shock | consequence_weighted_resource_flow | 0.000 | 0.000 | 0.311 | 0.384 | 0.000 | 0.432 | 0.992 | 0.000 | 0.000 |
| A | W5_monoculture_shock | uniform_resource_cap | 0.000 | 0.000 | 0.255 | 0.384 | 0.000 | 0.469 | 0.992 | 0.000 | 0.000 |
| B | W5_monoculture_shock | neighbor_consequence_allocator | 0.000 | 0.000 | 0.300 | 0.385 | 0.000 | 0.433 | 0.993 | 0.000 | 0.000 |
