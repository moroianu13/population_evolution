from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Sex = Literal["F", "M"]
Genome = tuple[tuple[int, int], ...]


@dataclass
class Individual:
    """A single person in the simplified agent-based model."""

    identifier: int
    sex: Sex
    age: int
    mother_id: int | None
    father_id: int | None
    x: float
    y: float
    region_id: str
    group_id: int
    genome: Genome
    birth_tick: int
    inbreeding_coefficient: float = 0.0
    alive: bool = True
    last_birth_tick: int = -999


@dataclass
class Group:
    """A local residential band used for mating and migration."""

    identifier: int
    region_id: str
    x: float
    y: float


@dataclass(frozen=True)
class RegionDefinition:
    """A coarse map region with local ecological capacity and migration pull."""

    identifier: str
    label: str
    center_x: float
    center_y: float
    spread_x: float
    spread_y: float
    carrying_capacity: int
    habitat_quality: float
    allele_bias: float
    color: str
    polygon: tuple[tuple[float, float], ...]
    neighbors: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvironmentalEvent:
    """Time-bounded modifier used for stress windows and local shocks."""

    label: str
    description: str
    start_tick: int
    end_tick: int
    mortality_multiplier: float = 1.0
    fertility_multiplier: float = 1.0
    migration_multiplier: float = 1.0
    capacity_multiplier: float = 1.0
    region_capacity_multipliers: dict[str, float] = field(default_factory=dict)
    region_mortality_multipliers: dict[str, float] = field(default_factory=dict)
    region_fertility_multipliers: dict[str, float] = field(default_factory=dict)
    region_migration_push: dict[str, float] = field(default_factory=dict)
    map_color: str = "#d76f2c"


@dataclass(frozen=True)
class ScenarioPreset:
    """Configuration for one illustrative or hypothesis-driven scenario."""

    name: str
    category_label: str
    description: str
    disclaimer: str
    seed: int
    initial_population: int
    genome_loci: int
    group_target_size: int
    adult_age: int
    menopause_age: int
    max_age: int
    birth_interval: int
    annual_birth_probability: float
    migration_rate: float
    long_distance_migration_rate: float
    exogamy_rate: float
    kin_avoidance: float
    mortality_multiplier: float
    fertility_multiplier: float
    mate_search_radius: float
    mate_genetic_diversity_weight: float
    group_isolation_strength: float
    group_fission_threshold: int
    regions: tuple[RegionDefinition, ...]
    initial_region_weights: dict[str, float]
    events: tuple[EnvironmentalEvent, ...] = ()


@dataclass
class SimulationControls:
    """User-adjustable experimental controls applied on top of a preset."""

    kin_avoidance_strength: float
    dispersal_rate: float
    mate_radius: float
    group_isolation_strength: float


@dataclass
class PopulationMarker:
    """Visual summary of one group on the map canvas."""

    identifier: int
    x: float
    y: float
    size: float
    region_id: str
    group_size: int
    color: str
    pressure: float


@dataclass
class RegionSnapshot:
    """Live region-level demographics for the GUI."""

    region_id: str
    label: str
    population: int
    carrying_capacity: int
    pressure: float
    shock_level: float
    active_events: tuple[str, ...]
    color: str


@dataclass
class MigrationFlow:
    """Aggregated flows between regions during the latest step."""

    source_region_id: str
    target_region_id: str
    count: int


@dataclass
class MatingEvent:
    """Recent successful mating visualized on the map."""

    female_id: int
    male_id: int
    female_x: float
    female_y: float
    male_x: float
    male_y: float
    relationship_label: str
    relatedness_coefficient: float
    offspring_inbreeding_coefficient: float
    close_kin: bool
    extreme: bool


@dataclass
class MetricSample:
    """One compact history sample used by the chart layer."""

    tick: int
    population: int
    carrying_capacity: int
    births: int
    deaths: int
    migrants: int
    mating_count: int
    heterozygosity: float
    mean_inbreeding_coefficient: float
    related_mating_share: float
    close_kin_mating_share: float
    extreme_inbreeding_share: float
    capacity_use: float
    peak_regional_pressure: float


@dataclass
class SimulationMetrics:
    """Live metrics surfaced to the GUI."""

    scenario_name: str
    scenario_category: str
    tick: int
    population: int
    adults: int
    groups: int
    mean_group_size: float
    births_last_step: int
    deaths_last_step: int
    migrants_last_step: int
    mating_count_last_step: int
    average_age: float
    heterozygosity: float
    mean_inbreeding_coefficient: float
    related_mating_share: float
    close_kin_mating_share: float
    extreme_inbreeding_share: float
    carrying_capacity: int
    capacity_use: float
    peak_regional_pressure: float
    active_event: str
    relatedness_distribution: dict[str, float] = field(default_factory=dict)


@dataclass
class EventHistoryEntry:
    """One event interval included in the run summary."""

    label: str
    description: str
    start_tick: int
    end_tick: int


@dataclass
class RunSummary:
    """Cumulative run totals used by the report layer."""

    initial_population: int
    total_ticks: int
    births_total: int
    deaths_total: int
    migrants_total: int
    mating_total: int
    related_mating_total: int
    close_kin_mating_total: int
    extreme_mating_total: int
    peak_region_pressure_over_run: float
    event_history: list[EventHistoryEntry] = field(default_factory=list)


@dataclass
class SimulationState:
    """Current simulation state consumed by the UI."""

    markers: list[PopulationMarker] = field(default_factory=list)
    metrics: SimulationMetrics | None = None
    regions: list[RegionSnapshot] = field(default_factory=list)
    migration_flows: list[MigrationFlow] = field(default_factory=list)
    recent_matings: list[MatingEvent] = field(default_factory=list)
    history: list[MetricSample] = field(default_factory=list)
    controls: SimulationControls | None = None
    run_summary: RunSummary | None = None
