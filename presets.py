from __future__ import annotations

from models import HistoricalEvent, RegionDefinition, ScenarioPreset


def _regions(
    africa_bias: float,
    corridor_bias: float,
    eurasia_bias: float,
) -> tuple[RegionDefinition, ...]:
    return (
        RegionDefinition(
            identifier="africa_core",
            label="Africa Core",
            center_x=0.19,
            center_y=0.44,
            spread_x=0.12,
            spread_y=0.16,
            carrying_capacity=185,
            habitat_quality=1.08,
            allele_bias=africa_bias,
            color="#7a9e3a",
            polygon=(
                (0.06, 0.20),
                (0.18, 0.13),
                (0.28, 0.19),
                (0.31, 0.35),
                (0.23, 0.61),
                (0.14, 0.74),
                (0.07, 0.54),
            ),
            neighbors=("corridor",),
        ),
        RegionDefinition(
            identifier="corridor",
            label="Northeast Corridor",
            center_x=0.48,
            center_y=0.33,
            spread_x=0.11,
            spread_y=0.10,
            carrying_capacity=90,
            habitat_quality=0.88,
            allele_bias=corridor_bias,
            color="#b0b96c",
            polygon=(
                (0.30, 0.24),
                (0.45, 0.18),
                (0.61, 0.20),
                (0.66, 0.31),
                (0.58, 0.45),
                (0.37, 0.42),
            ),
            neighbors=("africa_core", "eurasia"),
        ),
        RegionDefinition(
            identifier="eurasia",
            label="Eurasia",
            center_x=0.79,
            center_y=0.34,
            spread_x=0.15,
            spread_y=0.16,
            carrying_capacity=155,
            habitat_quality=1.0,
            allele_bias=eurasia_bias,
            color="#d5c88a",
            polygon=(
                (0.61, 0.18),
                (0.78, 0.10),
                (0.94, 0.16),
                (0.97, 0.31),
                (0.90, 0.50),
                (0.75, 0.58),
                (0.61, 0.43),
            ),
            neighbors=("corridor",),
        ),
    )


def load_presets() -> list[ScenarioPreset]:
    """Return historically inspired but explicitly simplified scenarios."""

    return [
        ScenarioPreset(
            name="Baseline / Out of Africa",
            category_label="Illustrative baseline",
            description=(
                "Most founders begin in an Africa-like core, then spread gradually through a "
                "lower-capacity corridor toward Eurasia as local density rises."
            ),
            disclaimer="Not a reconstruction of real prehistory; only an illustrative baseline.",
            scenario_notes=(
                "Dates are scenario assumptions chosen to create a finite run with plausible-seeming structure.",
                "The dated windows are historically inspired and should not be read as a literal migration chronology.",
            ),
            seed=11,
            start_year_bp=120_000,
            end_year_bp=35_000,
            years_per_tick=250,
            default_mode="historical",
            initial_population=140,
            genome_loci=24,
            group_target_size=16,
            adult_age=16,
            menopause_age=40,
            max_age=72,
            birth_interval=3,
            annual_birth_probability=0.24,
            migration_rate=0.050,
            long_distance_migration_rate=0.020,
            exogamy_rate=0.30,
            kin_avoidance=0.92,
            mortality_multiplier=1.0,
            fertility_multiplier=1.0,
            mate_search_radius=0.15,
            mate_genetic_diversity_weight=0.11,
            group_isolation_strength=0.32,
            group_fission_threshold=28,
            regions=_regions(0.28, 0.46, 0.66),
            initial_region_weights={"africa_core": 0.84, "corridor": 0.10, "eurasia": 0.06},
            event_timeline=(
                HistoricalEvent(
                    name="Corridor aridity pulse",
                    description=(
                        "Historically inspired dry interval used here as a scenario assumption "
                        "to lower corridor capacity and encourage movement."
                    ),
                    start_year_bp=74_000,
                    end_year_bp=69_000,
                    affected_regions=("corridor",),
                    migration_modifier=1.12,
                    carrying_capacity_modifier=0.82,
                    map_color="#c97d3e",
                ),
            ),
        ),
        ScenarioPreset(
            name="Deep bottleneck hypothesis",
            category_label="Hypothesis",
            description=(
                "Begins with a very small founder pool and a prolonged low-capacity phase. "
                "This is included as a hypothesis test, not as settled history."
            ),
            disclaimer=(
                "The deep bottleneck framing is controversial and is shown here only as a "
                "simplified hypothesis."
            ),
            scenario_notes=(
                "The long low-capacity window is a thought experiment rather than a consensus demographic reconstruction.",
                "Historical dates are used only to anchor the scenario in a finite BP timeline.",
            ),
            seed=23,
            start_year_bp=150_000,
            end_year_bp=45_000,
            years_per_tick=300,
            default_mode="historical",
            initial_population=48,
            genome_loci=24,
            group_target_size=12,
            adult_age=16,
            menopause_age=40,
            max_age=72,
            birth_interval=3,
            annual_birth_probability=0.23,
            migration_rate=0.036,
            long_distance_migration_rate=0.012,
            exogamy_rate=0.18,
            kin_avoidance=0.88,
            mortality_multiplier=1.08,
            fertility_multiplier=0.96,
            mate_search_radius=0.13,
            mate_genetic_diversity_weight=0.08,
            group_isolation_strength=0.50,
            group_fission_threshold=24,
            regions=_regions(0.30, 0.45, 0.65),
            initial_region_weights={"africa_core": 0.88, "corridor": 0.10, "eurasia": 0.02},
            event_timeline=(
                HistoricalEvent(
                    name="Extended low-capacity window",
                    description=(
                        "Long depressed-resource phase used to model a severe bottleneck hypothesis."
                    ),
                    start_year_bp=135_000,
                    end_year_bp=105_000,
                    affected_regions=(),
                    fertility_multiplier=0.92,
                    mortality_multiplier=1.12,
                    carrying_capacity_modifier=0.78,
                    map_color="#bc6c25",
                ),
                HistoricalEvent(
                    name="Corridor contraction",
                    description=(
                        "Additional corridor stress to keep movement narrow during the bottleneck interval."
                    ),
                    start_year_bp=120_000,
                    end_year_bp=96_000,
                    affected_regions=("corridor",),
                    migration_modifier=1.08,
                    carrying_capacity_modifier=0.72,
                    map_color="#c08552",
                ),
            ),
        ),
        ScenarioPreset(
            name="Toba-style environmental stress hypothesis",
            category_label="Hypothesis",
            description=(
                "Applies a temporary, severe environmental shock with lower carrying capacity, "
                "lower fertility, higher mortality, and stronger displacement."
            ),
            disclaimer=(
                "This does not claim that any specific eruption produced a human near-extinction; "
                "it is an explicit stress hypothesis."
            ),
            scenario_notes=(
                "The dated shock window is historically inspired rather than asserted as a precise causal mechanism.",
                "Recovery timing is stylized so the model can compare acute stress with slower demographic rebound.",
            ),
            seed=37,
            start_year_bp=95_000,
            end_year_bp=40_000,
            years_per_tick=250,
            default_mode="historical",
            initial_population=135,
            genome_loci=24,
            group_target_size=16,
            adult_age=16,
            menopause_age=40,
            max_age=72,
            birth_interval=3,
            annual_birth_probability=0.24,
            migration_rate=0.058,
            long_distance_migration_rate=0.028,
            exogamy_rate=0.28,
            kin_avoidance=0.92,
            mortality_multiplier=1.0,
            fertility_multiplier=1.0,
            mate_search_radius=0.15,
            mate_genetic_diversity_weight=0.10,
            group_isolation_strength=0.36,
            group_fission_threshold=28,
            regions=_regions(0.28, 0.46, 0.66),
            initial_region_weights={"africa_core": 0.80, "corridor": 0.12, "eurasia": 0.08},
            event_timeline=(
                HistoricalEvent(
                    name="Acute environmental shock",
                    description=(
                        "Short severe stress window with broad mortality, fertility, and capacity effects."
                    ),
                    start_year_bp=76_000,
                    end_year_bp=72_000,
                    affected_regions=(),
                    fertility_multiplier=0.68,
                    mortality_multiplier=1.40,
                    migration_modifier=1.35,
                    carrying_capacity_modifier=0.74,
                    map_color="#cf5c36",
                ),
                HistoricalEvent(
                    name="Recovery lag",
                    description=(
                        "Stylized lingering recovery period in which corridor and Eurasia remain partly degraded."
                    ),
                    start_year_bp=72_000,
                    end_year_bp=64_000,
                    affected_regions=("corridor", "eurasia"),
                    fertility_multiplier=0.88,
                    migration_modifier=1.10,
                    carrying_capacity_modifier=0.82,
                    map_color="#e09f3e",
                ),
            ),
        ),
        ScenarioPreset(
            name="Structured ancestry",
            category_label="Illustrative structure",
            description=(
                "Maintains stronger regional structure and lower inter-region gene flow so "
                "that ancestry remains subdivided for longer."
            ),
            disclaimer=(
                "This is an illustrative structured-population setup, not a claim that one "
                "specific ancestral graph is correct."
            ),
            scenario_notes=(
                "The time span is deliberately broad so regional structure can persist over many simulated generations.",
                "Event windows here are mild and mostly serve to reinforce structure, not to narrate a specific history.",
            ),
            seed=41,
            start_year_bp=130_000,
            end_year_bp=45_000,
            years_per_tick=300,
            default_mode="historical",
            initial_population=165,
            genome_loci=24,
            group_target_size=17,
            adult_age=16,
            menopause_age=40,
            max_age=72,
            birth_interval=3,
            annual_birth_probability=0.24,
            migration_rate=0.034,
            long_distance_migration_rate=0.010,
            exogamy_rate=0.18,
            kin_avoidance=0.92,
            mortality_multiplier=1.0,
            fertility_multiplier=1.0,
            mate_search_radius=0.13,
            mate_genetic_diversity_weight=0.10,
            group_isolation_strength=0.56,
            group_fission_threshold=28,
            regions=_regions(0.24, 0.48, 0.72),
            initial_region_weights={"africa_core": 0.70, "corridor": 0.15, "eurasia": 0.15},
            event_timeline=(
                HistoricalEvent(
                    name="Persistent corridor friction",
                    description=(
                        "Mild corridor constraints used to keep ancestry structured for longer."
                    ),
                    start_year_bp=110_000,
                    end_year_bp=70_000,
                    affected_regions=("corridor",),
                    migration_modifier=1.05,
                    carrying_capacity_modifier=0.88,
                    map_color="#c69752",
                ),
            ),
        ),
        ScenarioPreset(
            name="Low exogamy stress test",
            category_label="Stress test",
            description=(
                "Reduces inter-group mate exchange and weakens kin avoidance to explore how "
                "rapidly local relatedness can accumulate under isolation."
            ),
            disclaimer=(
                "This is an exploratory stress test, not a historical claim about any real population."
            ),
            scenario_notes=(
                "The dated window only provides a finite historical frame for the stress test.",
                "The scientific purpose here is comparative behavior under low exogamy, not historical inference.",
            ),
            seed=53,
            start_year_bp=90_000,
            end_year_bp=35_000,
            years_per_tick=250,
            default_mode="historical",
            initial_population=105,
            genome_loci=24,
            group_target_size=14,
            adult_age=16,
            menopause_age=40,
            max_age=72,
            birth_interval=3,
            annual_birth_probability=0.23,
            migration_rate=0.020,
            long_distance_migration_rate=0.006,
            exogamy_rate=0.08,
            kin_avoidance=0.36,
            mortality_multiplier=1.02,
            fertility_multiplier=0.98,
            mate_search_radius=0.10,
            mate_genetic_diversity_weight=0.07,
            group_isolation_strength=0.72,
            group_fission_threshold=22,
            regions=_regions(0.28, 0.47, 0.66),
            initial_region_weights={"africa_core": 0.86, "corridor": 0.09, "eurasia": 0.05},
            event_timeline=(
                HistoricalEvent(
                    name="Low-connectivity interval",
                    description=(
                        "Scenario assumption that amplifies isolation by making the corridor harder to use."
                    ),
                    start_year_bp=72_000,
                    end_year_bp=54_000,
                    affected_regions=("corridor",),
                    migration_modifier=1.12,
                    carrying_capacity_modifier=0.80,
                    map_color="#b66a41",
                ),
            ),
        ),
        ScenarioPreset(
            name="Inbreeding stress test",
            category_label="Stress test",
            description=(
                "Very small founder population with low dispersal, low exogamy, strong isolation, "
                "and no kin avoidance."
            ),
            disclaimer=(
                "Designed to study when inbreeding becomes hard to avoid in a tiny isolated population; "
                "not a historical reconstruction."
            ),
            scenario_notes=(
                "This scenario is intentionally extreme so the model reaches unavoidable inbreeding regimes quickly.",
                "Its time window is only a finite frame for comparison and should not be read as a dated historical claim.",
            ),
            seed=67,
            start_year_bp=85_000,
            end_year_bp=60_000,
            years_per_tick=150,
            default_mode="historical",
            initial_population=68,
            genome_loci=24,
            group_target_size=10,
            adult_age=16,
            menopause_age=40,
            max_age=72,
            birth_interval=3,
            annual_birth_probability=0.22,
            migration_rate=0.010,
            long_distance_migration_rate=0.002,
            exogamy_rate=0.02,
            kin_avoidance=0.0,
            mortality_multiplier=1.04,
            fertility_multiplier=0.96,
            mate_search_radius=0.08,
            mate_genetic_diversity_weight=0.04,
            group_isolation_strength=0.85,
            group_fission_threshold=18,
            regions=_regions(0.29, 0.45, 0.64),
            initial_region_weights={"africa_core": 0.94, "corridor": 0.05, "eurasia": 0.01},
            event_timeline=(
                HistoricalEvent(
                    name="Persistent local scarcity",
                    description=(
                        "Moderate long-running local scarcity that keeps the small population clustered."
                    ),
                    start_year_bp=79_000,
                    end_year_bp=66_000,
                    affected_regions=("africa_core",),
                    migration_modifier=1.06,
                    carrying_capacity_modifier=0.84,
                    map_color="#9f5d36",
                ),
            ),
        ),
    ]
