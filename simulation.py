from __future__ import annotations

import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass, replace

from models import (
    EventHistoryEntry,
    Genome,
    Group,
    Individual,
    MatingEvent,
    MetricSample,
    MigrationFlow,
    PopulationMarker,
    RegionDefinition,
    RegionSnapshot,
    RunSummary,
    ScenarioPreset,
    SimulationControls,
    SimulationMetrics,
    SimulationState,
)


@dataclass(frozen=True)
class RelationshipSummary:
    """Pedigree-based relationship summary for one pair."""

    label: str
    relatedness_coefficient: float
    offspring_inbreeding_coefficient: float
    is_related: bool
    close_kin: bool
    extreme: bool


class PopulationSimulation:
    """Scientifically inspired, simplified agent-based model for the GUI."""

    HISTORY_LIMIT = 240
    PEDIGREE_DEPTH = 5
    RELATEDNESS_BUCKETS = (
        "unrelated",
        "distant relatives",
        "first cousins",
        "half-siblings",
        "siblings",
        "parent-child",
    )

    def __init__(self, scenario: ScenarioPreset) -> None:
        self._scenario = scenario
        self.controls = self._default_controls(scenario)
        self._random = random.Random()
        self.state = SimulationState()
        self.tick = 0
        self.individuals: dict[int, Individual] = {}
        self.groups: dict[int, Group] = {}
        self._region_lookup: dict[str, RegionDefinition] = {}
        self._next_individual_id = 1
        self._next_group_id = 1
        self._pedigree_weight_cache: dict[int, dict[int, float]] = {}
        self._relationship_cache: dict[tuple[int, int], RelationshipSummary] = {}
        self._history: list[MetricSample] = []
        self._recent_matings: list[MatingEvent] = []
        self._births_total = 0
        self._deaths_total = 0
        self._migrants_total = 0
        self._matings_total = 0
        self._related_matings_total = 0
        self._close_kin_matings_total = 0
        self._extreme_matings_total = 0
        self._peak_region_pressure_over_run = 0.0
        self.reset(scenario)

    @property
    def scenario(self) -> ScenarioPreset:
        return self._scenario

    def set_controls(
        self,
        *,
        kin_avoidance_strength: float | None = None,
        dispersal_rate: float | None = None,
        mate_radius: float | None = None,
        group_isolation_strength: float | None = None,
    ) -> None:
        """Update runtime controls from the UI."""

        updates = {}
        if kin_avoidance_strength is not None:
            updates["kin_avoidance_strength"] = self._clamp(
                kin_avoidance_strength,
                0.0,
                1.0,
            )
        if dispersal_rate is not None:
            updates["dispersal_rate"] = self._clamp(dispersal_rate, 0.0, 0.20)
        if mate_radius is not None:
            updates["mate_radius"] = self._clamp(mate_radius, 0.04, 0.30)
        if group_isolation_strength is not None:
            updates["group_isolation_strength"] = self._clamp(
                group_isolation_strength,
                0.0,
                1.0,
            )
        if updates:
            self.controls = replace(self.controls, **updates)
            metrics = self.state.metrics
            if metrics is not None:
                conditions = self._current_conditions()
                self._rebuild_state(
                    conditions=conditions,
                    births=metrics.births_last_step,
                    deaths=metrics.deaths_last_step,
                    migrants=metrics.migrants_last_step,
                    mating_count=metrics.mating_count_last_step,
                    close_kin_matings=int(
                        round(metrics.close_kin_mating_share * metrics.mating_count_last_step)
                    ),
                    extreme_matings=int(
                        round(metrics.extreme_inbreeding_share * metrics.mating_count_last_step)
                    ),
                    relationship_counts=self._distribution_counts_from_shares(
                        metrics.relatedness_distribution,
                        metrics.mating_count_last_step,
                    ),
                    flow_counts={
                        (flow.source_region_id, flow.target_region_id): flow.count
                        for flow in self.state.migration_flows
                    },
                    append_history=False,
                )

    def reset(self, scenario: ScenarioPreset | None = None) -> SimulationState:
        if scenario is not None:
            self._scenario = scenario
            self.controls = self._default_controls(scenario)

        self._random = random.Random(self._scenario.seed)
        self.tick = 0
        self.individuals = {}
        self.groups = {}
        self._region_lookup = {
            region.identifier: region for region in self._scenario.regions
        }
        self._next_individual_id = 1
        self._next_group_id = 1
        self._pedigree_weight_cache = {}
        self._relationship_cache = {}
        self._history = []
        self._recent_matings = []
        self._births_total = 0
        self._deaths_total = 0
        self._migrants_total = 0
        self._matings_total = 0
        self._related_matings_total = 0
        self._close_kin_matings_total = 0
        self._extreme_matings_total = 0
        self._peak_region_pressure_over_run = 0.0

        regional_counts = self._allocate_initial_population()
        for region_id, count in regional_counts.items():
            if count <= 0:
                continue
            group_count = max(1, round(count / self._scenario.group_target_size))
            for _ in range(group_count):
                self._spawn_group(region_id)

        group_sizes = defaultdict(int)
        for region_id, count in regional_counts.items():
            groups = self._groups_in_region(region_id)
            if not groups:
                groups = [self._spawn_group(region_id)]
            for _ in range(count):
                group = min(groups, key=lambda candidate: group_sizes[candidate.identifier])
                founder = self._create_founder(region_id, group)
                self.individuals[founder.identifier] = founder
                group_sizes[group.identifier] += 1

        self._refresh_positions()
        conditions = self._current_conditions()
        self._rebuild_state(
            conditions=conditions,
            births=0,
            deaths=0,
            migrants=0,
            mating_count=0,
            close_kin_matings=0,
            extreme_matings=0,
            relationship_counts=self._empty_distribution_counts(),
            flow_counts={},
            append_history=True,
        )
        return self.state

    def step(self) -> SimulationState:
        self.tick += 1
        conditions = self._current_conditions()

        for person in self._alive_people():
            person.age += 1

        deaths = self._apply_mortality(conditions)
        migrants, flow_counts = self._apply_migration(conditions)
        (
            births,
            mating_count,
            related_matings,
            close_kin_matings,
            extreme_matings,
            relationship_counts,
        ) = self._apply_reproduction(conditions)

        self._births_total += births
        self._deaths_total += deaths
        self._migrants_total += migrants
        self._matings_total += mating_count
        self._related_matings_total += related_matings
        self._close_kin_matings_total += close_kin_matings
        self._extreme_matings_total += extreme_matings

        self._split_oversized_groups()
        self._remove_empty_groups()
        self._refresh_positions()
        self._rebuild_state(
            conditions=conditions,
            births=births,
            deaths=deaths,
            migrants=migrants,
            mating_count=mating_count,
            close_kin_matings=close_kin_matings,
            extreme_matings=extreme_matings,
            relationship_counts=relationship_counts,
            flow_counts=flow_counts,
            append_history=True,
        )
        return self.state

    def _default_controls(self, scenario: ScenarioPreset) -> SimulationControls:
        return SimulationControls(
            kin_avoidance_strength=scenario.kin_avoidance,
            dispersal_rate=scenario.migration_rate,
            mate_radius=scenario.mate_search_radius,
            group_isolation_strength=scenario.group_isolation_strength,
        )

    def _allocate_initial_population(self) -> dict[str, int]:
        total_weight = sum(self._scenario.initial_region_weights.values()) or 1.0
        raw_counts = {
            region.identifier: (
                self._scenario.initial_population
                * self._scenario.initial_region_weights.get(region.identifier, 0.0)
                / total_weight
            )
            for region in self._scenario.regions
        }
        counts = {
            region_id: int(raw_count) for region_id, raw_count in raw_counts.items()
        }
        remainder = self._scenario.initial_population - sum(counts.values())
        ranked = sorted(
            raw_counts,
            key=lambda region_id: raw_counts[region_id] - counts[region_id],
            reverse=True,
        )
        for region_id in ranked[:remainder]:
            counts[region_id] += 1
        return counts

    def _create_founder(self, region_id: str, group: Group) -> Individual:
        age = self._sample_founder_age()
        sex = self._random.choice(("F", "M"))
        return Individual(
            identifier=self._new_individual_id(),
            sex=sex,
            age=age,
            mother_id=None,
            father_id=None,
            x=group.x,
            y=group.y,
            region_id=region_id,
            group_id=group.identifier,
            genome=self._founder_genome(self._region_lookup[region_id]),
            birth_tick=0,
            inbreeding_coefficient=0.0,
            last_birth_tick=-self._random.randint(0, self._scenario.birth_interval),
        )

    def _sample_founder_age(self) -> int:
        draw = self._random.random()
        if draw < 0.20:
            return self._random.randint(0, 14)
        if draw < 0.76:
            return self._random.randint(15, 35)
        if draw < 0.95:
            return self._random.randint(36, 50)
        return self._random.randint(51, 65)

    def _founder_genome(self, region: RegionDefinition) -> Genome:
        genome = []
        for locus_index in range(self._scenario.genome_loci):
            locus_shift = ((locus_index % 6) - 2.5) * 0.025
            probability = self._clamp(
                region.allele_bias + locus_shift + self._random.uniform(-0.03, 0.03),
                0.05,
                0.95,
            )
            genome.append((self._draw_allele(probability), self._draw_allele(probability)))
        return tuple(genome)

    def _draw_allele(self, probability: float) -> int:
        return 1 if self._random.random() < probability else 0

    def _apply_mortality(self, conditions: dict[str, object]) -> int:
        people = self._alive_people()
        group_members = self._group_members(people)
        region_counts = self._region_counts(people)
        deaths = 0

        for person in people:
            if not person.alive:
                continue

            region_capacity = max(8, self._region_capacity(person.region_id, conditions))
            region_pressure = region_counts[person.region_id] / region_capacity
            group_pressure = (
                len(group_members[person.group_id]) / self._scenario.group_target_size
                if self._scenario.group_target_size
                else 1.0
            )
            shock_level = self._region_shock_level(person.region_id, conditions)

            death_probability = self._base_mortality(person.age)
            death_probability *= self._scenario.mortality_multiplier
            death_probability *= float(conditions["mortality"])
            death_probability *= self._region_factor(
                person.region_id,
                conditions,
                "region_mortality_factors",
            )
            death_probability *= self._inbreeding_mortality_multiplier(person)
            death_probability *= 1.0 + max(0.0, region_pressure - 0.82) * 0.55
            death_probability *= 1.0 + max(0.0, region_pressure - 1.00) * 1.10
            death_probability *= 1.0 + max(0.0, group_pressure - 1.0) * 0.20
            death_probability *= 1.0 + shock_level * 0.18

            if person.age > self._scenario.max_age:
                death_probability = 1.0

            if self._random.random() < min(0.98, death_probability):
                person.alive = False
                deaths += 1
                region_counts[person.region_id] -= 1

        return deaths

    def _base_mortality(self, age: int) -> float:
        if age <= 2:
            return 0.055
        if age <= 14:
            return 0.008
        if age <= 29:
            return 0.010
        if age <= 39:
            return 0.014
        if age <= 49:
            return 0.022
        if age <= 59:
            return 0.045
        if age <= 69:
            return 0.090
        return 0.180

    def _inbreeding_mortality_multiplier(self, person: Individual) -> float:
        coefficient = person.inbreeding_coefficient
        if coefficient <= 0.0:
            return 1.0

        if person.age <= 5:
            multiplier = 1.0 + coefficient * 4.2
        elif person.age <= 14:
            multiplier = 1.0 + coefficient * 2.2
        else:
            multiplier = 1.0 + coefficient * 0.8

        if coefficient >= 0.125:
            multiplier += 0.10
        if coefficient >= 0.25:
            multiplier += 0.22
        return multiplier

    def _apply_migration(
        self,
        conditions: dict[str, object],
    ) -> tuple[int, dict[tuple[str, str], int]]:
        people = self._alive_people()
        self._random.shuffle(people)
        group_members = self._group_members(people)
        region_counts = self._region_counts(people)
        flow_counts: dict[tuple[str, str], int] = defaultdict(int)
        migrants = 0

        for person in people:
            if person.age < self._scenario.adult_age or person.age > 38:
                continue

            current_capacity = max(8, self._region_capacity(person.region_id, conditions))
            current_pressure = region_counts[person.region_id] / current_capacity
            local_group_pressure = (
                len(group_members[person.group_id]) / self._scenario.group_target_size
            )
            shock_push = self._region_migration_push(person.region_id, conditions)

            move_probability = self.controls.dispersal_rate
            move_probability *= float(conditions["migration"])
            move_probability *= max(
                0.18,
                1.0 - self.controls.group_isolation_strength * 0.45,
            )
            move_probability *= 0.65 + max(0.0, current_pressure - 0.70) * 1.35
            move_probability *= 1.0 + max(0.0, local_group_pressure - 1.0) * 0.35
            move_probability *= 1.0 + shock_push * 0.90

            if self._random.random() >= min(0.75, move_probability):
                continue

            target_group = self._choose_migration_target(
                person=person,
                region_counts=region_counts,
                conditions=conditions,
                group_members=group_members,
            )
            if target_group is None or target_group.identifier == person.group_id:
                continue

            old_group_id = person.group_id
            old_region_id = person.region_id

            person.group_id = target_group.identifier
            person.region_id = target_group.region_id
            person.x = target_group.x
            person.y = target_group.y

            migrants += 1
            group_members[old_group_id] = [
                member
                for member in group_members[old_group_id]
                if member.identifier != person.identifier
            ]
            group_members[target_group.identifier].append(person)
            region_counts[old_region_id] -= 1
            region_counts[person.region_id] += 1

            if old_region_id != person.region_id:
                flow_counts[(old_region_id, person.region_id)] += 1

        return migrants, dict(flow_counts)

    def _choose_migration_target(
        self,
        person: Individual,
        region_counts: dict[str, int],
        conditions: dict[str, object],
        group_members: dict[int, list[Individual]],
    ) -> Group | None:
        current_region = self._region_lookup[person.region_id]
        current_capacity = max(8, self._region_capacity(person.region_id, conditions))
        current_pressure = region_counts[person.region_id] / current_capacity
        current_shock = self._region_shock_level(person.region_id, conditions)

        search_depth = 1
        if current_pressure > 0.95 or current_shock > 0.18:
            search_depth = 2
        if self._random.random() < self._effective_long_distance_rate() * float(
            conditions["migration"]
        ):
            search_depth = 3

        candidate_groups = []
        weights = []

        for region_id in self._reachable_regions(person.region_id, search_depth):
            region = self._region_lookup[region_id]
            region_capacity = max(8, self._region_capacity(region_id, conditions))
            region_pressure = region_counts[region_id] / region_capacity
            region_shock = self._region_shock_level(region_id, conditions)
            center_distance = self._distance(
                current_region.center_x,
                current_region.center_y,
                region.center_x,
                region.center_y,
            )

            attractiveness = 0.30 + region.habitat_quality * 0.45
            attractiveness += max(0.0, 1.18 - region_pressure) * 0.75
            attractiveness += max(0.0, current_pressure - region_pressure) * 0.35
            attractiveness *= max(0.10, 1.05 - region_shock * 0.55)
            attractiveness /= 1.0 + center_distance * 2.80

            if region_id == person.region_id:
                attractiveness *= 0.78
            elif region_id in current_region.neighbors:
                attractiveness *= max(
                    0.30,
                    1.10 - self.controls.group_isolation_strength * 0.35,
                )
            else:
                attractiveness *= max(
                    0.10,
                    1.0 - self.controls.group_isolation_strength * 0.60,
                )

            groups = self._groups_in_region(region_id)
            if not groups and region_pressure < 1.10:
                new_group = self._spawn_group(region_id)
                group_members[new_group.identifier] = []
                groups = [new_group]

            for group in groups:
                if group.identifier == person.group_id:
                    continue

                local_size = len(group_members[group.identifier])
                local_distance = self._distance(person.x, person.y, group.x, group.y)
                group_weight = attractiveness
                group_weight *= max(
                    0.15,
                    1.30 - (local_size / max(1, self._scenario.group_target_size)),
                )
                group_weight /= 1.0 + local_distance * 5.0

                if group_weight > 0:
                    candidate_groups.append(group)
                    weights.append(group_weight)

        if not candidate_groups:
            return None

        return self._random.choices(candidate_groups, weights=weights, k=1)[0]

    def _effective_long_distance_rate(self) -> float:
        base_rate = max(0.001, self._scenario.migration_rate)
        ratio = self.controls.dispersal_rate / base_rate
        return min(0.25, self._scenario.long_distance_migration_rate * ratio)

    def _apply_reproduction(
        self,
        conditions: dict[str, object],
    ) -> tuple[int, int, int, int, int, dict[str, int]]:
        people = self._alive_people()
        group_members = self._group_members(people)
        region_counts = self._region_counts(people)
        births = 0
        mating_count = 0
        related_matings = 0
        close_kin_matings = 0
        extreme_matings = 0
        relationship_counts = self._empty_distribution_counts()
        recent_matings: list[MatingEvent] = []

        eligible_females = [
            person
            for person in people
            if person.sex == "F"
            and self._scenario.adult_age <= person.age <= self._scenario.menopause_age
            and (self.tick - person.last_birth_tick) >= self._scenario.birth_interval
        ]
        self._random.shuffle(eligible_females)

        for female in eligible_females:
            if not female.alive:
                continue

            region_capacity = max(8, self._region_capacity(female.region_id, conditions))
            region_pressure = region_counts[female.region_id] / region_capacity
            group_pressure = (
                len(group_members[female.group_id]) / self._scenario.group_target_size
            )

            fertility = self._scenario.annual_birth_probability
            fertility *= self._scenario.fertility_multiplier
            fertility *= float(conditions["fertility"])
            fertility *= self._region_factor(
                female.region_id,
                conditions,
                "region_fertility_factors",
            )
            fertility *= self._fertility_age_modifier(female.age)
            fertility *= max(0.15, 1.16 - region_pressure * 0.45)
            fertility *= max(0.35, 1.06 - max(0.0, group_pressure - 1.0) * 0.20)

            if self._random.random() >= min(0.65, fertility):
                continue

            mate, relationship = self._choose_mate(
                female=female,
                group_members=group_members,
                conditions=conditions,
            )
            if mate is None or relationship is None:
                continue

            child = self._create_child(female, mate, relationship)
            self.individuals[child.identifier] = child
            group_members[child.group_id].append(child)
            region_counts[child.region_id] += 1

            births += 1
            mating_count += 1
            relationship_counts[relationship.label] += 1
            if relationship.is_related:
                related_matings += 1
            if relationship.close_kin:
                close_kin_matings += 1
            if relationship.extreme:
                extreme_matings += 1

            recent_matings.append(
                MatingEvent(
                    female_id=female.identifier,
                    male_id=mate.identifier,
                    female_x=female.x,
                    female_y=female.y,
                    male_x=mate.x,
                    male_y=mate.y,
                    relationship_label=relationship.label,
                    relatedness_coefficient=relationship.relatedness_coefficient,
                    offspring_inbreeding_coefficient=relationship.offspring_inbreeding_coefficient,
                    close_kin=relationship.close_kin,
                    extreme=relationship.extreme,
                )
            )

        recent_matings.sort(
            key=lambda event: (event.close_kin, event.relatedness_coefficient),
            reverse=True,
        )
        self._recent_matings = recent_matings[:24]
        return (
            births,
            mating_count,
            related_matings,
            close_kin_matings,
            extreme_matings,
            relationship_counts,
        )

    def _fertility_age_modifier(self, age: int) -> float:
        if age <= 18:
            return 0.70
        if age <= 30:
            return 1.00
        if age <= 35:
            return 0.88
        return 0.62

    def _choose_mate(
        self,
        female: Individual,
        group_members: dict[int, list[Individual]],
        conditions: dict[str, object],
    ) -> tuple[Individual | None, RelationshipSummary | None]:
        current_group = self.groups[female.group_id]
        search_radius = self.controls.mate_radius
        nearby_groups = [
            group
            for group in self.groups.values()
            if group.identifier != current_group.identifier
            and self._distance(current_group.x, current_group.y, group.x, group.y)
            <= search_radius
        ]
        same_region_groups = [
            group
            for group in self.groups.values()
            if group.region_id == female.region_id
            and group.identifier != current_group.identifier
        ]

        prefer_exogamy = self._random.random() < self._scenario.exogamy_rate
        candidate_groups = [current_group]
        if nearby_groups:
            candidate_groups.extend(nearby_groups)
        elif same_region_groups:
            candidate_groups.extend(same_region_groups)
        elif self.controls.group_isolation_strength < 0.75 or prefer_exogamy:
            for neighbor_id in self._region_lookup[female.region_id].neighbors:
                candidate_groups.extend(self._groups_in_region(neighbor_id))

        seen_groups = set()
        candidate_males = []
        for group in candidate_groups:
            if group.identifier in seen_groups:
                continue
            seen_groups.add(group.identifier)
            for male in group_members.get(group.identifier, []):
                if (
                    male.alive
                    and male.sex == "M"
                    and self._scenario.adult_age <= male.age <= 60
                ):
                    candidate_males.append(male)

        if not candidate_males:
            return None, None

        viable_candidates = []
        relationships = []
        weights = []

        for male in candidate_males:
            relationship = self._relationship_summary(female.identifier, male.identifier)
            distance = self._distance(female.x, female.y, male.x, male.y)
            distance_scale = max(0.04, search_radius * 0.75)
            distance_factor = math.exp(-distance / distance_scale)

            age_gap = abs(female.age - male.age)
            age_factor = max(0.03, 1.0 - age_gap / 26.0) ** 2

            local_density = len(group_members[male.group_id]) / max(
                1,
                self._scenario.group_target_size,
            )
            density_factor = 0.72 + min(0.58, local_density * 0.24)

            isolation_factor = 1.0
            if male.group_id != female.group_id:
                isolation_factor *= max(
                    0.05,
                    1.0 - self.controls.group_isolation_strength * 0.78,
                )
            else:
                isolation_factor *= 1.0 + self.controls.group_isolation_strength * 0.16
            if male.region_id != female.region_id:
                isolation_factor *= max(
                    0.05,
                    1.0 - self.controls.group_isolation_strength * 0.86,
                )

            if prefer_exogamy and male.group_id != female.group_id:
                isolation_factor *= 1.18
            elif prefer_exogamy:
                isolation_factor *= 0.88

            diversity_factor = 1.0 + (
                (1.0 - self._genetic_similarity(female, male))
                * self._scenario.mate_genetic_diversity_weight
            )

            kin_penalty = 1.0 - self.controls.kin_avoidance_strength * min(
                0.98,
                relationship.relatedness_coefficient * 1.75
                + (0.18 if relationship.close_kin else 0.0),
            )
            weight = (
                distance_factor
                * age_factor
                * density_factor
                * isolation_factor
                * diversity_factor
                * max(0.02, kin_penalty)
            )
            weight *= max(
                0.78,
                1.0 - self._region_shock_level(male.region_id, conditions) * 0.18,
            )

            if weight <= 0:
                continue

            viable_candidates.append(male)
            relationships.append(relationship)
            weights.append(weight)

        if not viable_candidates:
            return None, None

        index = self._random.choices(
            range(len(viable_candidates)),
            weights=weights,
            k=1,
        )[0]
        return viable_candidates[index], relationships[index]

    def _genetic_similarity(self, first: Individual, second: Individual) -> float:
        similarity = 0.0
        for locus_a, locus_b in zip(first.genome, second.genome):
            dosage_a = locus_a[0] + locus_a[1]
            dosage_b = locus_b[0] + locus_b[1]
            similarity += 1.0 - abs(dosage_a - dosage_b) / 2.0
        return similarity / max(1, self._scenario.genome_loci)

    def _create_child(
        self,
        mother: Individual,
        father: Individual,
        relationship: RelationshipSummary,
    ) -> Individual:
        group = self.groups[mother.group_id]
        genome = tuple(
            (
                self._random.choice(mother_locus),
                self._random.choice(father_locus),
            )
            for mother_locus, father_locus in zip(mother.genome, father.genome)
        )
        child = Individual(
            identifier=self._new_individual_id(),
            sex=self._random.choice(("F", "M")),
            age=0,
            mother_id=mother.identifier,
            father_id=father.identifier,
            x=group.x,
            y=group.y,
            region_id=group.region_id,
            group_id=group.identifier,
            genome=genome,
            birth_tick=self.tick,
            inbreeding_coefficient=relationship.offspring_inbreeding_coefficient,
        )
        mother.last_birth_tick = self.tick
        return child

    def _relationship_summary(
        self,
        first_id: int,
        second_id: int,
    ) -> RelationshipSummary:
        cache_key = tuple(sorted((first_id, second_id)))
        cached = self._relationship_cache.get(cache_key)
        if cached is not None:
            return cached

        first = self.individuals[first_id]
        second = self.individuals[second_id]
        relatedness = self._relatedness_coefficient(first_id, second_id)

        label = "unrelated"
        close_kin = False
        extreme = False

        if self._is_parent_child(first, second):
            label = "parent-child"
            relatedness = max(relatedness, 0.5)
            close_kin = True
            extreme = True
        elif self._is_full_siblings(first, second):
            label = "siblings"
            relatedness = max(relatedness, 0.5)
            close_kin = True
            extreme = True
        elif self._is_half_siblings(first, second):
            label = "half-siblings"
            relatedness = max(relatedness, 0.25)
            close_kin = True
        elif self._is_first_cousins(first, second):
            label = "first cousins"
            relatedness = max(relatedness, 0.125)
            close_kin = True
        elif relatedness >= 0.03125:
            label = "distant relatives"
            close_kin = relatedness >= 0.125

        result = RelationshipSummary(
            label=label,
            relatedness_coefficient=min(1.0, relatedness),
            offspring_inbreeding_coefficient=min(0.5, relatedness / 2.0),
            is_related=relatedness >= 0.03125,
            close_kin=close_kin,
            extreme=extreme,
        )
        self._relationship_cache[cache_key] = result
        return result

    def _relatedness_coefficient(self, first_id: int, second_id: int) -> float:
        first_weights = self._pedigree_weights(first_id)
        second_weights = self._pedigree_weights(second_id)
        shared_ancestors = set(first_weights) & set(second_weights)
        coefficient = 0.0

        for ancestor_id in shared_ancestors:
            ancestor = self.individuals.get(ancestor_id)
            ancestor_factor = 1.0
            if ancestor is not None:
                ancestor_factor += ancestor.inbreeding_coefficient
            coefficient += (
                first_weights[ancestor_id]
                * second_weights[ancestor_id]
                * ancestor_factor
            )

        return min(1.0, coefficient)

    def _pedigree_weights(self, individual_id: int) -> dict[int, float]:
        cached = self._pedigree_weight_cache.get(individual_id)
        if cached is not None:
            return cached

        weights = {individual_id: 1.0}
        frontier = [(individual_id, 1.0, 0)]

        while frontier:
            current_id, current_weight, depth = frontier.pop()
            if depth >= self.PEDIGREE_DEPTH:
                continue

            current = self.individuals.get(current_id)
            if current is None:
                continue

            for parent_id in (current.mother_id, current.father_id):
                if parent_id is None:
                    continue
                parent_weight = current_weight * 0.5
                weights[parent_id] = weights.get(parent_id, 0.0) + parent_weight
                frontier.append((parent_id, parent_weight, depth + 1))

        self._pedigree_weight_cache[individual_id] = weights
        return weights

    def _is_parent_child(self, first: Individual, second: Individual) -> bool:
        return (
            first.identifier in {second.mother_id, second.father_id}
            or second.identifier in {first.mother_id, first.father_id}
        )

    def _is_full_siblings(self, first: Individual, second: Individual) -> bool:
        return (
            first.mother_id is not None
            and first.father_id is not None
            and first.mother_id == second.mother_id
            and first.father_id == second.father_id
        )

    def _is_half_siblings(self, first: Individual, second: Individual) -> bool:
        shared_parents = {
            parent_id
            for parent_id in (first.mother_id, first.father_id)
            if parent_id is not None
        } & {
            parent_id
            for parent_id in (second.mother_id, second.father_id)
            if parent_id is not None
        }
        return len(shared_parents) == 1

    def _is_first_cousins(self, first: Individual, second: Individual) -> bool:
        for first_parent_id in (first.mother_id, first.father_id):
            if first_parent_id is None:
                continue
            first_parent = self.individuals.get(first_parent_id)
            if first_parent is None:
                continue
            for second_parent_id in (second.mother_id, second.father_id):
                if second_parent_id is None:
                    continue
                second_parent = self.individuals.get(second_parent_id)
                if second_parent is None:
                    continue
                if self._is_full_siblings(first_parent, second_parent) or self._is_half_siblings(
                    first_parent,
                    second_parent,
                ):
                    return True
        return False

    def _split_oversized_groups(self) -> None:
        people = self._alive_people()
        group_members = self._group_members(people)

        for group_id, members in list(group_members.items()):
            if len(members) <= self._scenario.group_fission_threshold:
                continue

            source_group = self.groups[group_id]
            new_group = self._spawn_group(source_group.region_id, anchor=source_group)
            movers = self._random.sample(members, k=len(members) // 2)

            for person in movers:
                person.group_id = new_group.identifier
                person.region_id = new_group.region_id
                person.x = new_group.x
                person.y = new_group.y

    def _remove_empty_groups(self) -> None:
        occupied_group_ids = {person.group_id for person in self._alive_people()}
        for group_id in list(self.groups):
            if group_id not in occupied_group_ids:
                del self.groups[group_id]

    def _refresh_positions(self) -> None:
        for group in self.groups.values():
            region = self._region_lookup[group.region_id]
            group.x = self._clamp(
                group.x + self._random.uniform(-0.010, 0.010),
                region.center_x - region.spread_x,
                region.center_x + region.spread_x,
            )
            group.y = self._clamp(
                group.y + self._random.uniform(-0.010, 0.010),
                region.center_y - region.spread_y,
                region.center_y + region.spread_y,
            )

        for person in self._alive_people():
            group = self.groups.get(person.group_id)
            if group is None:
                continue
            region = self._region_lookup[group.region_id]
            person.region_id = group.region_id
            person.x = self._clamp(
                group.x + self._random.uniform(-0.030, 0.030),
                region.center_x - region.spread_x,
                region.center_x + region.spread_x,
            )
            person.y = self._clamp(
                group.y + self._random.uniform(-0.030, 0.030),
                region.center_y - region.spread_y,
                region.center_y + region.spread_y,
            )

    def _rebuild_state(
        self,
        conditions: dict[str, object],
        births: int,
        deaths: int,
        migrants: int,
        mating_count: int,
        close_kin_matings: int,
        extreme_matings: int,
        relationship_counts: dict[str, int],
        flow_counts: dict[tuple[str, str], int],
        append_history: bool,
    ) -> None:
        people = self._alive_people()
        group_members = self._group_members(people)
        region_counts = self._region_counts(people)
        total_capacity = max(1, self._total_capacity(conditions))
        average_age = (
            sum(person.age for person in people) / len(people) if people else 0.0
        )
        adults = sum(1 for person in people if person.age >= self._scenario.adult_age)
        mean_inbreeding = (
            sum(person.inbreeding_coefficient for person in people) / len(people)
            if people
            else 0.0
        )

        region_snapshots = []
        peak_regional_pressure = 0.0
        for region in self._scenario.regions:
            capacity = self._region_capacity(region.identifier, conditions)
            pressure = region_counts[region.identifier] / max(1, capacity)
            peak_regional_pressure = max(peak_regional_pressure, pressure)
            region_snapshots.append(
                RegionSnapshot(
                    region_id=region.identifier,
                    label=region.label,
                    population=region_counts[region.identifier],
                    carrying_capacity=capacity,
                    pressure=pressure,
                    shock_level=self._region_shock_level(region.identifier, conditions),
                    active_events=tuple(
                        dict(conditions["region_event_labels"]).get(region.identifier, ())
                    ),
                    color=region.color,
                )
            )

        markers = []
        for group_id, members in sorted(group_members.items()):
            group = self.groups.get(group_id)
            if group is None or not members:
                continue
            region_capacity = self._region_capacity(group.region_id, conditions)
            pressure = region_counts[group.region_id] / max(1, region_capacity)
            region = self._region_lookup[group.region_id]
            markers.append(
                PopulationMarker(
                    identifier=group_id,
                    x=group.x,
                    y=group.y,
                    size=max(8.0, min(28.0, 7.0 + len(members) * 0.60)),
                    region_id=region.identifier,
                    group_size=len(members),
                    color=region.color,
                    pressure=pressure,
                )
            )

        migration_flows = [
            MigrationFlow(
                source_region_id=source_id,
                target_region_id=target_id,
                count=count,
            )
            for (source_id, target_id), count in sorted(
                flow_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:6]
        ]

        mean_group_size = (
            sum(len(members) for members in group_members.values()) / len(group_members)
            if group_members
            else 0.0
        )
        relatedness_distribution = self._distribution_shares(
            relationship_counts,
            mating_count,
        )
        related_share = (
            sum(
                count
                for label, count in relationship_counts.items()
                if label != "unrelated"
            )
            / mating_count
            if mating_count
            else 0.0
        )
        close_kin_share = close_kin_matings / mating_count if mating_count else 0.0
        extreme_share = extreme_matings / mating_count if mating_count else 0.0

        metrics = SimulationMetrics(
            scenario_name=self._scenario.name,
            scenario_category=self._scenario.category_label,
            tick=self.tick,
            population=len(people),
            adults=adults,
            groups=len(group_members),
            mean_group_size=mean_group_size,
            births_last_step=births,
            deaths_last_step=deaths,
            migrants_last_step=migrants,
            mating_count_last_step=mating_count,
            average_age=average_age,
            heterozygosity=self._observed_heterozygosity(people),
            mean_inbreeding_coefficient=mean_inbreeding,
            related_mating_share=related_share,
            close_kin_mating_share=close_kin_share,
            extreme_inbreeding_share=extreme_share,
            carrying_capacity=total_capacity,
            capacity_use=len(people) / total_capacity,
            peak_regional_pressure=peak_regional_pressure,
            active_event=str(conditions["label"]),
            relatedness_distribution=relatedness_distribution,
        )

        if append_history:
            self._history.append(
                MetricSample(
                    tick=self.tick,
                    population=metrics.population,
                    carrying_capacity=metrics.carrying_capacity,
                    births=births,
                    deaths=deaths,
                    migrants=migrants,
                    mating_count=mating_count,
                    heterozygosity=metrics.heterozygosity,
                    mean_inbreeding_coefficient=metrics.mean_inbreeding_coefficient,
                    related_mating_share=metrics.related_mating_share,
                    close_kin_mating_share=close_kin_share,
                    extreme_inbreeding_share=extreme_share,
                    capacity_use=metrics.capacity_use,
                    peak_regional_pressure=peak_regional_pressure,
                )
            )
            self._history = self._history[-self.HISTORY_LIMIT :]

        self._peak_region_pressure_over_run = max(
            self._peak_region_pressure_over_run,
            peak_regional_pressure,
        )
        run_summary = RunSummary(
            initial_population=self._scenario.initial_population,
            total_ticks=self.tick,
            births_total=self._births_total,
            deaths_total=self._deaths_total,
            migrants_total=self._migrants_total,
            mating_total=self._matings_total,
            related_mating_total=self._related_matings_total,
            close_kin_mating_total=self._close_kin_matings_total,
            extreme_mating_total=self._extreme_matings_total,
            peak_region_pressure_over_run=self._peak_region_pressure_over_run,
            event_history=self._event_history_entries(),
        )

        self.state = SimulationState(
            markers=markers,
            metrics=metrics,
            regions=region_snapshots,
            migration_flows=migration_flows,
            recent_matings=list(self._recent_matings),
            history=list(self._history),
            controls=replace(self.controls),
            run_summary=run_summary,
        )

    def _distribution_shares(
        self,
        counts: dict[str, int],
        total: int,
    ) -> dict[str, float]:
        if total <= 0:
            return {bucket: 0.0 for bucket in self.RELATEDNESS_BUCKETS}
        return {
            bucket: counts.get(bucket, 0) / total
            for bucket in self.RELATEDNESS_BUCKETS
        }

    def _distribution_counts_from_shares(
        self,
        shares: dict[str, float],
        total: int,
    ) -> dict[str, int]:
        counts = {bucket: 0 for bucket in self.RELATEDNESS_BUCKETS}
        if total <= 0:
            return counts
        for bucket in self.RELATEDNESS_BUCKETS:
            counts[bucket] = int(round(shares.get(bucket, 0.0) * total))
        return counts

    def _empty_distribution_counts(self) -> dict[str, int]:
        return {bucket: 0 for bucket in self.RELATEDNESS_BUCKETS}

    def _event_history_entries(self) -> list[EventHistoryEntry]:
        entries = []
        for event in self._scenario.events:
            if event.start_tick > self.tick:
                continue
            entries.append(
                EventHistoryEntry(
                    label=event.label,
                    description=event.description,
                    start_tick=event.start_tick,
                    end_tick=min(self.tick, event.end_tick),
                )
            )
        return entries

    def _current_conditions(self) -> dict[str, object]:
        mortality = 1.0
        fertility = 1.0
        migration = 1.0
        capacity = 1.0
        region_capacity_factors: dict[str, float] = defaultdict(lambda: 1.0)
        region_mortality_factors: dict[str, float] = defaultdict(lambda: 1.0)
        region_fertility_factors: dict[str, float] = defaultdict(lambda: 1.0)
        region_migration_push: dict[str, float] = defaultdict(float)
        region_event_labels: dict[str, list[str]] = defaultdict(list)
        active_labels = []
        active_descriptions = []

        for event in self._scenario.events:
            if event.start_tick <= self.tick <= event.end_tick:
                active_labels.append(event.label)
                active_descriptions.append(event.description)
                mortality *= event.mortality_multiplier
                fertility *= event.fertility_multiplier
                migration *= event.migration_multiplier
                capacity *= event.capacity_multiplier

                for region_id, factor in event.region_capacity_multipliers.items():
                    region_capacity_factors[region_id] *= factor
                for region_id, factor in event.region_mortality_multipliers.items():
                    region_mortality_factors[region_id] *= factor
                for region_id, factor in event.region_fertility_multipliers.items():
                    region_fertility_factors[region_id] *= factor
                for region_id, push in event.region_migration_push.items():
                    region_migration_push[region_id] += push

                for region_id in event.region_capacity_multipliers:
                    region_event_labels[region_id].append(event.label)
                for region_id in event.region_mortality_multipliers:
                    region_event_labels[region_id].append(event.label)
                for region_id in event.region_fertility_multipliers:
                    region_event_labels[region_id].append(event.label)
                for region_id in event.region_migration_push:
                    region_event_labels[region_id].append(event.label)

        region_shock_levels: dict[str, float] = {}
        for region in self._scenario.regions:
            region_id = region.identifier
            capacity_factor = capacity * region_capacity_factors[region_id]
            mortality_factor = mortality * region_mortality_factors[region_id]
            fertility_factor = fertility * region_fertility_factors[region_id]
            shock_level = max(
                0.0,
                (1.0 - capacity_factor) * 1.05,
                (mortality_factor - 1.0) * 0.80,
                (1.0 - fertility_factor) * 0.70,
                region_migration_push[region_id] * 0.90,
            )
            region_shock_levels[region_id] = min(1.40, shock_level)

        return {
            "mortality": mortality,
            "fertility": fertility,
            "migration": migration,
            "capacity": capacity,
            "region_capacity_factors": dict(region_capacity_factors),
            "region_mortality_factors": dict(region_mortality_factors),
            "region_fertility_factors": dict(region_fertility_factors),
            "region_migration_push": dict(region_migration_push),
            "region_shock_levels": region_shock_levels,
            "region_event_labels": {
                region_id: tuple(sorted(set(labels)))
                for region_id, labels in region_event_labels.items()
            },
            "label": "None" if not active_labels else "; ".join(active_labels),
            "descriptions": tuple(active_descriptions),
        }

    def _region_factor(
        self,
        region_id: str,
        conditions: dict[str, object],
        field_name: str,
    ) -> float:
        return dict(conditions[field_name]).get(region_id, 1.0)

    def _region_capacity(self, region_id: str, conditions: dict[str, object]) -> int:
        region = self._region_lookup[region_id]
        region_factor = self._region_factor(
            region_id,
            conditions,
            "region_capacity_factors",
        )
        capacity = region.carrying_capacity
        capacity *= float(conditions["capacity"])
        capacity *= region_factor
        return max(8, int(round(capacity)))

    def _total_capacity(self, conditions: dict[str, object]) -> int:
        return sum(
            self._region_capacity(region.identifier, conditions)
            for region in self._scenario.regions
        )

    def _region_shock_level(
        self,
        region_id: str,
        conditions: dict[str, object],
    ) -> float:
        return dict(conditions["region_shock_levels"]).get(region_id, 0.0)

    def _region_migration_push(
        self,
        region_id: str,
        conditions: dict[str, object],
    ) -> float:
        return dict(conditions["region_migration_push"]).get(region_id, 0.0)

    def _observed_heterozygosity(self, people: list[Individual]) -> float:
        if not people:
            return 0.0

        heterozygous_loci = 0
        total_loci = len(people) * self._scenario.genome_loci
        for person in people:
            heterozygous_loci += sum(
                1 for allele_a, allele_b in person.genome if allele_a != allele_b
            )
        return heterozygous_loci / max(1, total_loci)

    def _alive_people(self) -> list[Individual]:
        return [person for person in self.individuals.values() if person.alive]

    def _group_members(self, people: list[Individual]) -> dict[int, list[Individual]]:
        members: dict[int, list[Individual]] = defaultdict(list)
        for person in people:
            members[person.group_id].append(person)
        return members

    def _region_counts(self, people: list[Individual]) -> dict[str, int]:
        counts = {region.identifier: 0 for region in self._scenario.regions}
        for person in people:
            counts[person.region_id] += 1
        return counts

    def _groups_in_region(self, region_id: str) -> list[Group]:
        return [group for group in self.groups.values() if group.region_id == region_id]

    def _reachable_regions(self, start_region_id: str, max_depth: int) -> list[str]:
        visited = {start_region_id}
        order = [start_region_id]
        frontier: deque[tuple[str, int]] = deque([(start_region_id, 0)])

        while frontier:
            region_id, depth = frontier.popleft()
            if depth >= max_depth:
                continue
            for neighbor_id in self._region_lookup[region_id].neighbors:
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                order.append(neighbor_id)
                frontier.append((neighbor_id, depth + 1))

        return order

    def _spawn_group(self, region_id: str, anchor: Group | None = None) -> Group:
        region = self._region_lookup[region_id]
        base_x = region.center_x if anchor is None else anchor.x
        base_y = region.center_y if anchor is None else anchor.y
        spread_x = region.spread_x if anchor is None else min(region.spread_x, 0.06)
        spread_y = region.spread_y if anchor is None else min(region.spread_y, 0.06)

        group = Group(
            identifier=self._new_group_id(),
            region_id=region_id,
            x=self._clamp(
                base_x + self._random.uniform(-spread_x, spread_x),
                region.center_x - region.spread_x,
                region.center_x + region.spread_x,
            ),
            y=self._clamp(
                base_y + self._random.uniform(-spread_y, spread_y),
                region.center_y - region.spread_y,
                region.center_y + region.spread_y,
            ),
        )
        self.groups[group.identifier] = group
        return group

    def _new_individual_id(self) -> int:
        identifier = self._next_individual_id
        self._next_individual_id += 1
        return identifier

    def _new_group_id(self) -> int:
        identifier = self._next_group_id
        self._next_group_id += 1
        return identifier

    @staticmethod
    def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
        return math.hypot(x2 - x1, y2 - y1)

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))
