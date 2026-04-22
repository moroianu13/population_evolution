from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

from models import (
    MatingEvent,
    MetricSample,
    MigrationFlow,
    PopulationMarker,
    RegionSnapshot,
    RunSummary,
    ScenarioPreset,
    SimulationControls,
    SimulationMetrics,
)

if TYPE_CHECKING:
    from simulation import PopulationSimulation


EDUCATIONAL_NOTE = (
    "This simulation is an educational and exploratory model, not a literal "
    "reconstruction of real prehistoric demography."
)

PAGE_BACKGROUND = "#f4f1ec"
PANEL_BACKGROUND = "#ffffff"
PANEL_BORDER = "#d6dde5"
HEADER_BACKGROUND = "#1f4259"
HEADER_RULE = "#dce4ea"
TEXT_PRIMARY = "#1d2f3c"
TEXT_SECONDARY = "#596f7c"
TEXT_MUTED = "#748896"
TEXT_WARNING = "#8b4a24"
TABLE_HEADER = "#e8eff4"
TABLE_ROW_ODD = "#fbfcfd"
TABLE_ROW_EVEN = "#f3f6f8"
GRID_COLOR = "#d6dde5"
FONT_FAMILY = "DejaVu Sans"
PAGE_SIZE = (8.27, 11.69)


@dataclass(frozen=True)
class ReportData:
    """Compact snapshot passed into the PDF renderer."""

    generated_at: datetime
    scenario: ScenarioPreset
    controls: SimulationControls
    metrics: SimulationMetrics
    run_summary: RunSummary
    history: list[MetricSample]
    regions: list[RegionSnapshot]
    markers: list[PopulationMarker]
    migration_flows: list[MigrationFlow]
    recent_matings: list[MatingEvent]


def export_simulation_report(
    simulation: PopulationSimulation,
    output_dir: str | Path = "exports",
) -> Path:
    """Export the current simulation state into a multi-page PDF report."""

    data = _collect_report_data(simulation)
    output_path = _build_output_path(
        Path(output_dir),
        data.generated_at,
        data.scenario.name,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(output_path) as pdf:
        metadata = pdf.infodict()
        metadata["Title"] = f"Population Evolution Report - {data.scenario.name}"
        metadata["Author"] = "Population Evolution Simulator"
        metadata["Subject"] = "Agent-based population simulation summary"
        metadata["CreationDate"] = data.generated_at

        for figure in (
            _build_summary_page(data),
            _build_charts_page(data),
            _build_map_page(data),
        ):
            pdf.savefig(figure)
            figure.clear()

    return output_path


def _collect_report_data(simulation: PopulationSimulation) -> ReportData:
    state = simulation.state
    metrics = state.metrics
    controls = state.controls
    run_summary = state.run_summary
    if metrics is None or controls is None or run_summary is None:
        raise ValueError("Simulation state is incomplete; cannot export report.")

    return ReportData(
        generated_at=datetime.now().astimezone(),
        scenario=simulation.scenario,
        controls=controls,
        metrics=metrics,
        run_summary=run_summary,
        history=list(state.history),
        regions=list(state.regions),
        markers=list(state.markers),
        migration_flows=list(state.migration_flows),
        recent_matings=list(state.recent_matings),
    )


def _build_output_path(output_dir: Path, generated_at: datetime, scenario_name: str) -> Path:
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    slug = _slugify(scenario_name)
    return output_dir / f"{timestamp}_{slug}_report.pdf"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "scenario"


def _build_summary_page(data: ReportData) -> Figure:
    figure = _new_report_figure()
    _decorate_page(
        figure,
        data,
        page_number=1,
        page_title="Run Summary",
        page_blurb=(
            "A compact overview of the selected scenario, key inputs, cumulative outcomes, "
            "and region-level state at the end of the run."
        ),
    )
    grid = figure.add_gridspec(
        3,
        2,
        left=0.07,
        right=0.93,
        bottom=0.07,
        top=0.82,
        height_ratios=[0.28, 0.88, 0.72],
        width_ratios=[1.08, 0.92],
        hspace=0.18,
        wspace=0.10,
    )

    highlights_ax = figure.add_subplot(grid[0, :])
    summary_ax = figure.add_subplot(grid[1, 0])
    inputs_ax = figure.add_subplot(grid[1, 1])
    region_ax = figure.add_subplot(grid[2, 0])
    event_ax = figure.add_subplot(grid[2, 1])

    _draw_stat_cards(
        highlights_ax,
        cards=[
            ("Final Population", str(data.metrics.population)),
            ("Births Total", str(data.run_summary.births_total)),
            ("Heterozygosity", f"{data.metrics.heterozygosity:.3f}"),
            ("Mean Inbreeding F", f"{data.metrics.mean_inbreeding_coefficient:.3f}"),
        ],
        note=data.scenario.disclaimer,
    )

    summary_rows = [
        ("Total ticks", str(data.run_summary.total_ticks)),
        ("Initial population", str(data.run_summary.initial_population)),
        ("Final population", str(data.metrics.population)),
        ("Average age", f"{data.metrics.average_age:.1f}"),
        ("Births total", str(data.run_summary.births_total)),
        ("Deaths total", str(data.run_summary.deaths_total)),
        ("Migrants total", str(data.run_summary.migrants_total)),
        ("Heterozygosity (final)", f"{data.metrics.heterozygosity:.3f}"),
        ("Mean inbreeding F", f"{data.metrics.mean_inbreeding_coefficient:.3f}"),
        ("Related matings", _count_rate(data.run_summary.related_mating_total, data.run_summary.mating_total)),
        ("Close-kin matings", _count_rate(data.run_summary.close_kin_mating_total, data.run_summary.mating_total)),
        ("Extreme matings", _count_rate(data.run_summary.extreme_mating_total, data.run_summary.mating_total)),
        ("Peak region pressure", f"{data.run_summary.peak_region_pressure_over_run:.2f}"),
        ("Active event now", data.metrics.active_event),
    ]
    _draw_key_value_table(
        summary_ax,
        "Run Summary",
        summary_rows,
        subtitle="Cumulative outputs and end-state metrics for the current run.",
    )

    input_rows = [
        ("Initial pop", str(data.scenario.initial_population)),
        ("Genome loci", str(data.scenario.genome_loci)),
        ("Group target", str(data.scenario.group_target_size)),
        ("Adult age", str(data.scenario.adult_age)),
        ("Birth interval", str(data.scenario.birth_interval)),
        ("Birth prob / year", f"{data.scenario.annual_birth_probability:.3f}"),
        ("Preset migration", f"{data.scenario.migration_rate:.3f}"),
        ("Long-distance migration", f"{data.scenario.long_distance_migration_rate:.3f}"),
        ("Exogamy rate", f"{data.scenario.exogamy_rate:.3f}"),
        ("Preset kin avoidance", f"{data.scenario.kin_avoidance:.2f}"),
        ("Runtime kin avoidance", f"{data.controls.kin_avoidance_strength:.2f}"),
        ("Runtime dispersal", f"{data.controls.dispersal_rate:.3f}"),
        ("Runtime mate radius", f"{data.controls.mate_radius:.2f}"),
        ("Runtime isolation", f"{data.controls.group_isolation_strength:.2f}"),
        ("Mortality multiplier", f"{data.scenario.mortality_multiplier:.2f}"),
        ("Fertility multiplier", f"{data.scenario.fertility_multiplier:.2f}"),
    ]
    _draw_key_value_table(
        inputs_ax,
        "Important Inputs",
        input_rows,
        subtitle="Preset values and live runtime controls used for this export.",
    )

    region_rows = [
        (
            snapshot.label,
            str(snapshot.population),
            str(snapshot.carrying_capacity),
            f"{snapshot.pressure:.2f}",
        )
        for snapshot in data.regions
    ]
    _draw_matrix_table(
        region_ax,
        "Population By Region",
        columns=("Region", "Pop", "Cap", "Pressure"),
        rows=region_rows,
        font_size=8.8,
        subtitle="Regional population, carrying capacity, and end-state pressure.",
    )

    if data.run_summary.event_history:
        event_rows = [
            (
                entry.label,
                f"{entry.start_tick}-{entry.end_tick}",
                textwrap.fill(entry.description, width=35),
            )
            for entry in data.run_summary.event_history
        ]
        _draw_matrix_table(
            event_ax,
            "Event History",
            columns=("Event", "Ticks", "Description"),
            rows=event_rows,
            font_size=8.1,
            subtitle="Scenario-defined environmental windows active during this run.",
        )
    else:
        _draw_note_box(
            event_ax,
            title="Event History",
            body="No event windows are defined for this scenario.",
            subtitle="Scenario-defined environmental windows active during this run.",
        )

    return figure


def _build_charts_page(data: ReportData) -> Figure:
    figure = _new_report_figure()
    _decorate_page(
        figure,
        data,
        page_number=2,
        page_title="Time-Series Metrics",
        page_blurb=(
            "Core demographic, mobility, diversity, and kinship signals across the current "
            "simulation history window."
        ),
    )
    grid = figure.add_gridspec(
        3,
        2,
        left=0.08,
        right=0.92,
        bottom=0.07,
        top=0.81,
        hspace=0.28,
        wspace=0.18,
    )

    history = data.history or [
        MetricSample(
            tick=data.metrics.tick,
            population=data.metrics.population,
            carrying_capacity=data.metrics.carrying_capacity,
            births=data.metrics.births_last_step,
            deaths=data.metrics.deaths_last_step,
            migrants=data.metrics.migrants_last_step,
            mating_count=data.metrics.mating_count_last_step,
            heterozygosity=data.metrics.heterozygosity,
            mean_inbreeding_coefficient=data.metrics.mean_inbreeding_coefficient,
            related_mating_share=data.metrics.related_mating_share,
            close_kin_mating_share=data.metrics.close_kin_mating_share,
            extreme_inbreeding_share=data.metrics.extreme_inbreeding_share,
            capacity_use=data.metrics.capacity_use,
            peak_regional_pressure=data.metrics.peak_regional_pressure,
        )
    ]

    ticks = [sample.tick for sample in history]

    axes = [
        figure.add_subplot(grid[0, 0]),
        figure.add_subplot(grid[0, 1]),
        figure.add_subplot(grid[1, 0]),
        figure.add_subplot(grid[1, 1]),
        figure.add_subplot(grid[2, 0]),
        figure.add_subplot(grid[2, 1]),
    ]

    _plot_series_panel(
        axes[0],
        ticks,
        [
            ("Population", [sample.population for sample in history], "#365c7f"),
            ("Capacity", [sample.carrying_capacity for sample in history], "#d17b0f"),
        ],
        title="Population Over Time",
        subtitle="Population size compared with aggregate carrying capacity.",
        ylabel="Count",
    )
    _plot_series_panel(
        axes[1],
        ticks,
        [
            ("Births", [sample.births for sample in history], "#2a9d8f"),
            ("Deaths", [sample.deaths for sample in history], "#c75146"),
            ("Migrants", [sample.migrants for sample in history], "#6c5ce7"),
        ],
        title="Births / Deaths / Migrants",
        subtitle="Per-tick demographic and movement fluxes.",
        ylabel="Per tick",
    )
    _plot_series_panel(
        axes[2],
        ticks,
        [("Heterozygosity", [sample.heterozygosity for sample in history], "#1d3557")],
        title="Heterozygosity Over Time",
        subtitle="Observed toy-genome diversity across the living population.",
        ylabel="H",
        y_floor=0.0,
    )
    _plot_series_panel(
        axes[3],
        ticks,
        [
            (
                "Peak regional pressure",
                [sample.peak_regional_pressure for sample in history],
                "#8d6e63",
            )
        ],
        title="Peak Regional Pressure Over Time",
        subtitle="Highest region-level capacity pressure at each tick.",
        ylabel="Pressure",
        y_floor=0.0,
    )
    _plot_series_panel(
        axes[4],
        ticks,
        [
            (
                "Mean inbreeding F",
                [sample.mean_inbreeding_coefficient for sample in history],
                "#b5179e",
            )
        ],
        title="Mean Inbreeding Coefficient Over Time",
        subtitle="Population-average offspring inbreeding coefficient F.",
        ylabel="F",
        y_floor=0.0,
    )
    _plot_series_panel(
        axes[5],
        ticks,
        [
            (
                "Close-kin share",
                [sample.close_kin_mating_share for sample in history],
                "#d94841",
            ),
            (
                "Related share",
                [sample.related_mating_share for sample in history],
                "#f4a261",
            ),
        ],
        title="Related Mating Share Over Time",
        subtitle="Share of mating events involving related partners.",
        ylabel="Share",
        y_floor=0.0,
    )
    return figure


def _build_map_page(data: ReportData) -> Figure:
    figure = _new_report_figure()
    _decorate_page(
        figure,
        data,
        page_number=3,
        page_title="Map Snapshot And Interpretation",
        page_blurb=(
            "A schematic spatial view of the latest simulation state, paired with concise "
            "interpretation notes for the current run."
        ),
    )
    grid = figure.add_gridspec(
        2,
        2,
        left=0.07,
        right=0.93,
        bottom=0.07,
        top=0.81,
        height_ratios=[1.22, 0.78],
        width_ratios=[1.15, 0.95],
        hspace=0.18,
        wspace=0.12,
    )

    map_ax = figure.add_subplot(grid[0, :])
    interpretation_ax = figure.add_subplot(grid[1, 0])
    notes_ax = figure.add_subplot(grid[1, 1])

    _draw_map_snapshot(map_ax, data)
    _draw_note_box(
        interpretation_ax,
        title="Auto-Generated Interpretation",
        body="\n".join(_interpretation_lines(data)),
        font_size=9.8,
    )

    notes_lines = [
        data.scenario.description,
        "",
        EDUCATIONAL_NOTE,
        "",
        "Report notes:",
        f"- Latest tick: {data.metrics.tick}",
        f"- Recent mating events shown on map: {len(data.recent_matings)}",
        f"- Recent inter-region flows shown on map: {len(data.migration_flows)}",
    ]
    _draw_note_box(
        notes_ax,
        title="Notes",
        body="\n".join(notes_lines),
        subtitle="Context for reading this export and map view.",
        font_size=9.5,
    )
    return figure


def _new_report_figure() -> Figure:
    figure = Figure(figsize=PAGE_SIZE, dpi=150)
    figure.patch.set_facecolor(PAGE_BACKGROUND)
    return figure


def _decorate_page(
    figure: Figure,
    data: ReportData,
    *,
    page_number: int,
    page_title: str,
    page_blurb: str,
) -> None:
    generated = data.generated_at.strftime("%Y-%m-%d %H:%M %Z")
    figure.add_artist(
        Rectangle(
            (0.0, 0.94),
            1.0,
            0.06,
            transform=figure.transFigure,
            facecolor=HEADER_BACKGROUND,
            edgecolor="none",
            zorder=-20,
        )
    )
    figure.add_artist(
        Rectangle(
            (0.07, 0.852),
            0.86,
            0.0016,
            transform=figure.transFigure,
            facecolor=HEADER_RULE,
            edgecolor="none",
            zorder=-20,
        )
    )
    figure.add_artist(
        Rectangle(
            (0.07, 0.055),
            0.86,
            0.0012,
            transform=figure.transFigure,
            facecolor=HEADER_RULE,
            edgecolor="none",
            zorder=-20,
        )
    )

    figure.text(
        0.07,
        0.966,
        "Population Evolution Simulator",
        fontsize=12.5,
        fontweight="bold",
        color="white",
        fontfamily=FONT_FAMILY,
        va="center",
    )
    figure.text(
        0.07,
        0.912,
        page_title,
        fontsize=18,
        fontweight="bold",
        color=TEXT_PRIMARY,
        fontfamily=FONT_FAMILY,
        va="center",
    )
    figure.text(
        0.07,
        0.885,
        f"Scenario: {data.scenario.name}",
        fontsize=10.3,
        color=TEXT_SECONDARY,
        fontfamily=FONT_FAMILY,
        va="center",
    )
    figure.text(
        0.07,
        0.866,
        textwrap.fill(page_blurb, width=104),
        fontsize=9.2,
        color=TEXT_MUTED,
        fontfamily=FONT_FAMILY,
        va="top",
    )

    figure.text(
        0.93,
        0.966,
        f"Page {page_number}",
        fontsize=10.2,
        color="white",
        fontfamily=FONT_FAMILY,
        ha="right",
        va="center",
    )
    figure.text(
        0.93,
        0.885,
        generated,
        fontsize=9.5,
        color=TEXT_SECONDARY,
        fontfamily=FONT_FAMILY,
        ha="right",
        va="center",
    )
    figure.text(
        0.93,
        0.866,
        data.scenario.category_label,
        fontsize=9.2,
        color=TEXT_MUTED,
        fontfamily=FONT_FAMILY,
        ha="right",
        va="center",
    )
    figure.text(
        0.07,
        0.037,
        EDUCATIONAL_NOTE,
        fontsize=8.4,
        color=TEXT_MUTED,
        fontfamily=FONT_FAMILY,
        va="center",
    )
    figure.text(
        0.93,
        0.037,
        "Portfolio-style simulation report",
        fontsize=8.4,
        color=TEXT_MUTED,
        fontfamily=FONT_FAMILY,
        ha="right",
        va="center",
    )


def _draw_stat_cards(
    ax,
    cards: list[tuple[str, str]],
    *,
    note: str | None = None,
) -> None:
    ax.axis("off")
    card_width = 0.225
    gap = 0.02
    left = 0.0
    for label, value in cards:
        card = FancyBboxPatch(
            (left, 0.22 if note else 0.10),
            card_width,
            0.64 if note else 0.76,
            boxstyle="round,pad=0.012,rounding_size=0.03",
            transform=ax.transAxes,
            facecolor=PANEL_BACKGROUND,
            edgecolor=PANEL_BORDER,
            linewidth=1.0,
        )
        card.set_clip_on(False)
        ax.add_patch(card)
        ax.add_patch(
            Rectangle(
                (left, 0.78 if note else 0.82),
                card_width,
                0.04,
                transform=ax.transAxes,
                facecolor=TABLE_HEADER,
                edgecolor="none",
            )
        )
        ax.text(
            left + 0.03,
            0.70 if note else 0.74,
            label,
            fontsize=8.8,
            color=TEXT_MUTED,
            fontfamily=FONT_FAMILY,
            va="top",
        )
        ax.text(
            left + 0.03,
            0.45 if note else 0.50,
            value,
            fontsize=16,
            fontweight="bold",
            color=TEXT_PRIMARY,
            fontfamily=FONT_FAMILY,
            va="center",
        )
        left += card_width + gap

    if note:
        ax.text(
            0.0,
            0.03,
            textwrap.fill(note, width=118),
            fontsize=8.7,
            color=TEXT_WARNING,
            fontfamily=FONT_FAMILY,
            va="bottom",
        )


def _draw_key_value_table(
    ax,
    title: str,
    rows: list[tuple[str, str]],
    *,
    subtitle: str | None = None,
) -> None:
    _add_panel_shell(ax, title, subtitle)
    table = ax.table(
        cellText=rows,
        colLabels=["Field", "Value"],
        colColours=[TABLE_HEADER, TABLE_HEADER],
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        bbox=[0.04, 0.07, 0.92, 0.76],
        colWidths=[0.60, 0.32],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.6)
    table.scale(1.0, 1.18)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(PANEL_BORDER)
        cell.get_text().set_fontfamily(FONT_FAMILY)
        if row == 0:
            cell.set_text_props(fontweight="bold", color=TEXT_PRIMARY)
            cell.set_facecolor(TABLE_HEADER)
        else:
            cell.set_facecolor(TABLE_ROW_ODD if row % 2 else TABLE_ROW_EVEN)
            if col == 0:
                cell.set_text_props(fontweight="bold")
            if col == 1:
                cell.set_text_props(ha="right")


def _draw_matrix_table(
    ax,
    title: str,
    columns: tuple[str, ...],
    rows: list[tuple[str, ...]],
    font_size: float,
    *,
    subtitle: str | None = None,
) -> None:
    _add_panel_shell(ax, title, subtitle)
    right_aligned_headers = {"Pop", "Cap", "Pressure", "Shock", "Ticks"}
    table = ax.table(
        cellText=rows,
        colLabels=list(columns),
        colColours=[TABLE_HEADER] * len(columns),
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        bbox=[0.04, 0.07, 0.92, 0.76],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1.0, 1.12)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(PANEL_BORDER)
        cell.get_text().set_fontfamily(FONT_FAMILY)
        if row == 0:
            cell.set_text_props(fontweight="bold", color=TEXT_PRIMARY)
            cell.set_facecolor(TABLE_HEADER)
        else:
            cell.set_facecolor(TABLE_ROW_ODD if row % 2 else TABLE_ROW_EVEN)
            if columns[col] in right_aligned_headers:
                cell.set_text_props(ha="right")


def _draw_note_box(
    ax,
    title: str,
    body: str,
    *,
    subtitle: str | None = None,
    font_size: float = 10.0,
) -> None:
    _add_panel_shell(ax, title, subtitle)
    ax.text(
        0.05,
        0.80,
        _wrap_panel_text(body),
        va="top",
        ha="left",
        fontsize=font_size,
        color=TEXT_PRIMARY,
        fontfamily=FONT_FAMILY,
        transform=ax.transAxes,
    )


def _plot_series_panel(
    ax,
    ticks: list[int],
    series: list[tuple[str, list[float], str]],
    *,
    title: str,
    subtitle: str,
    ylabel: str,
    y_floor: float | None = None,
) -> None:
    _style_chart_axis(ax, title, subtitle)
    for label, values, color in series:
        ax.plot(ticks, values, linewidth=2.2, label=label, color=color)
    ax.set_xlabel("Tick")
    ax.set_ylabel(ylabel)
    ax.margins(x=0.05, y=0.12)
    if ticks:
        x_min = ticks[0]
        x_max = max(ticks[-1], x_min + 1)
        ax.set_xlim(x_min, x_max)
    if y_floor is not None:
        ax.set_ylim(bottom=y_floor)
    if len(series) > 1:
        ax.legend(
            loc="upper left",
            frameon=False,
            fontsize=7.9,
            ncol=min(3, len(series)),
        )


def _add_panel_shell(ax, title: str, subtitle: str | None = None) -> None:
    ax.axis("off")
    panel = FancyBboxPatch(
        (0.0, 0.0),
        1.0,
        1.0,
        boxstyle="round,pad=0.012,rounding_size=0.03",
        transform=ax.transAxes,
        facecolor=PANEL_BACKGROUND,
        edgecolor=PANEL_BORDER,
        linewidth=1.0,
        zorder=-10,
    )
    panel.set_clip_on(False)
    ax.add_patch(panel)
    ax.text(
        0.04,
        0.93,
        title,
        fontsize=11.6,
        fontweight="bold",
        color=TEXT_PRIMARY,
        fontfamily=FONT_FAMILY,
        va="top",
    )
    if subtitle:
        ax.text(
            0.04,
            0.86,
            textwrap.fill(subtitle, width=48),
            fontsize=8.5,
            color=TEXT_MUTED,
            fontfamily=FONT_FAMILY,
            va="top",
        )


def _style_chart_axis(ax, title: str, subtitle: str) -> None:
    ax.set_facecolor(PANEL_BACKGROUND)
    for spine in ax.spines.values():
        spine.set_color(PANEL_BORDER)
        spine.set_linewidth(0.9)
    ax.grid(True, alpha=0.18, color=GRID_COLOR)
    ax.tick_params(axis="both", labelsize=8.4, colors=TEXT_SECONDARY)
    ax.xaxis.label.set_fontfamily(FONT_FAMILY)
    ax.yaxis.label.set_fontfamily(FONT_FAMILY)
    ax.xaxis.label.set_color(TEXT_SECONDARY)
    ax.yaxis.label.set_color(TEXT_SECONDARY)
    ax.set_title(
        title,
        loc="left",
        fontsize=11.1,
        fontweight="bold",
        color=TEXT_PRIMARY,
        fontfamily=FONT_FAMILY,
        pad=18,
    )
    ax.text(
        0.0,
        1.01,
        textwrap.fill(subtitle, width=42),
        transform=ax.transAxes,
        fontsize=8.3,
        color=TEXT_MUTED,
        fontfamily=FONT_FAMILY,
        va="bottom",
    )


def _wrap_panel_text(body: str, width: int = 62) -> str:
    wrapped_lines: list[str] = []
    for paragraph in body.splitlines():
        stripped = paragraph.strip()
        if not stripped:
            wrapped_lines.append("")
            continue
        if stripped.startswith("- "):
            filled = textwrap.fill(stripped[2:], width=max(20, width - 2))
            wrapped = filled.splitlines()
            wrapped_lines.append(f"- {wrapped[0]}")
            for line in wrapped[1:]:
                wrapped_lines.append(f"  {line}")
            continue
        wrapped_lines.append(textwrap.fill(stripped, width=width))
    return "\n".join(wrapped_lines)


def _draw_map_snapshot(ax, data: ReportData) -> None:
    panel = FancyBboxPatch(
        (0.0, 0.0),
        1.0,
        1.0,
        boxstyle="round,pad=0.012,rounding_size=0.03",
        transform=ax.transAxes,
        facecolor=PANEL_BACKGROUND,
        edgecolor=PANEL_BORDER,
        linewidth=1.0,
        zorder=-30,
    )
    panel.set_clip_on(False)
    ax.add_patch(panel)
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(1.0, 0.0)
    ax.set_aspect("equal")
    ax.axis("off")

    stripes = ["#e6f0f5", "#ddeaf1", "#d4e3ec", "#ccdde8", "#c5d8e4"]
    stripe_height = 1.0 / len(stripes)
    for index, color in enumerate(stripes):
        ax.axhspan(
            index * stripe_height,
            (index + 1) * stripe_height,
            facecolor=color,
            edgecolor="none",
            zorder=0,
        )

    ax.add_patch(
        Ellipse(
            (0.86, 0.84),
            width=0.32,
            height=0.24,
            facecolor="#d9e8ef",
            edgecolor="none",
            zorder=0.1,
        )
    )
    ax.add_patch(
        Rectangle(
            (0.02, 0.07),
            0.96,
            0.88,
            fill=False,
            linewidth=1.0,
            edgecolor="#90aab8",
            zorder=0.2,
        )
    )

    region_by_id = {region.identifier: region for region in data.scenario.regions}
    snapshot_by_id = {snapshot.region_id: snapshot for snapshot in data.regions}

    for region in data.scenario.regions:
        for neighbor_id in region.neighbors:
            if region.identifier > neighbor_id:
                continue
            neighbor = region_by_id[neighbor_id]
            ax.plot(
                [region.center_x, neighbor.center_x],
                [region.center_y, neighbor.center_y],
                color="#89a0aa",
                linewidth=1.2,
                linestyle=(0, (4, 3)),
                zorder=0.3,
            )

    for region in data.scenario.regions:
        snapshot = snapshot_by_id.get(region.identifier)
        pressure = 0.0 if snapshot is None else snapshot.pressure
        shock = 0.0 if snapshot is None else snapshot.shock_level
        fill_color = _region_fill(region.color, pressure, shock)
        shadow = [(x + 0.008, y + 0.010) for x, y in region.polygon]

        ax.add_patch(
            Polygon(
                shadow,
                closed=True,
                facecolor="#9db3be",
                edgecolor="none",
                zorder=0.5,
            )
        )
        ax.add_patch(
            Polygon(
                region.polygon,
                closed=True,
                facecolor=fill_color,
                edgecolor="#576b6f",
                linewidth=1.6 + min(1.6, shock * 2.6),
                zorder=0.6,
            )
        )

        if snapshot is not None:
            label = f"{region.label}\n{snapshot.population}/{snapshot.carrying_capacity}  p={snapshot.pressure:.2f}"
        else:
            label = region.label
        ax.text(
            region.center_x,
            max(0.05, region.center_y - region.spread_y - 0.07),
            label,
            ha="center",
            va="center",
            fontsize=9.4,
            fontweight="bold",
            color="#223c43",
            zorder=0.8,
        )

    for flow in data.migration_flows:
        source = region_by_id[flow.source_region_id]
        target = region_by_id[flow.target_region_id]
        color = _mix_colors("#df6d2d", "#a52a2a", min(0.7, flow.count / 8.0))
        ax.add_patch(
            FancyArrowPatch(
                (source.center_x, source.center_y),
                (target.center_x, target.center_y),
                arrowstyle="-|>",
                mutation_scale=12 + flow.count * 1.5,
                linewidth=min(4.5, 1.0 + flow.count * 0.35),
                color=color,
                alpha=0.85,
                connectionstyle="arc3,rad=0.08",
                zorder=0.9,
            )
        )

    for event in data.recent_matings:
        color = "#4f6d7a"
        if event.extreme:
            color = "#8d0801"
        elif event.close_kin:
            color = "#d62828"
        elif event.relatedness_coefficient >= 0.0625:
            color = "#f4a261"

        ax.plot(
            [event.female_x, event.male_x],
            [event.female_y, event.male_y],
            color=color,
            linewidth=1.0 + min(3.5, event.relatedness_coefficient * 8.0),
            linestyle="-" if event.close_kin else (0, (4, 3)),
            alpha=0.88,
            zorder=1.0,
        )
        if event.close_kin:
            for x, y in ((event.female_x, event.female_y), (event.male_x, event.male_y)):
                ax.add_patch(
                    Circle(
                        (x, y),
                        radius=0.008,
                        facecolor="#fff1f0",
                        edgecolor=color,
                        linewidth=1.0,
                        zorder=1.05,
                    )
                )

    for marker in sorted(data.markers, key=lambda item: item.size):
        radius = 0.008 + marker.size * 0.00058
        outline = _mix_colors("#ffffff", "#b6402c", min(0.6, marker.pressure * 0.4))
        ax.add_patch(
            Circle(
                (marker.x, marker.y),
                radius=radius + 0.0025,
                facecolor="none",
                edgecolor="#fdfdfd",
                linewidth=1.1,
                zorder=1.1,
            )
        )
        ax.add_patch(
            Circle(
                (marker.x, marker.y),
                radius=radius,
                facecolor=marker.color,
                edgecolor=outline,
                linewidth=1.3,
                zorder=1.15,
            )
        )
        if marker.group_size >= data.scenario.group_target_size:
            ax.text(
                marker.x,
                marker.y,
                str(marker.group_size),
                ha="center",
                va="center",
                fontsize=7.6,
                fontweight="bold",
                color="#102024",
                zorder=1.2,
            )

    legend = (
        "Pressure darkens regions\n"
        "Warm borders indicate shocks\n"
        "Orange arrows show recent migration\n"
        "Red pair lines indicate close-kin matings"
    )
    ax.text(
        0.03,
        0.97,
        "Current Simulation Map Snapshot",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11.4,
        fontweight="bold",
        color=TEXT_PRIMARY,
        fontfamily=FONT_FAMILY,
        zorder=2.0,
    )
    ax.text(
        0.03,
        0.92,
        "A schematic spatial view of regions, group markers, migration flows, and recent mating events.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color=TEXT_MUTED,
        fontfamily=FONT_FAMILY,
        zorder=2.0,
    )
    ax.text(
        0.03,
        0.84,
        legend,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.0,
        color="#24404a",
        fontfamily=FONT_FAMILY,
        bbox={"facecolor": "#f7fafc", "edgecolor": "#9db1bb", "boxstyle": "round,pad=0.5"},
        zorder=2.0,
    )


def _interpretation_lines(data: ReportData) -> list[str]:
    related_rate = _safe_rate(
        data.run_summary.related_mating_total,
        data.run_summary.mating_total,
    )
    close_kin_rate = _safe_rate(
        data.run_summary.close_kin_mating_total,
        data.run_summary.mating_total,
    )
    extreme_rate = _safe_rate(
        data.run_summary.extreme_mating_total,
        data.run_summary.mating_total,
    )
    migrants_per_tick = _safe_rate(
        data.run_summary.migrants_total,
        max(1, data.run_summary.total_ticks),
    )

    related_history = [sample.related_mating_share for sample in data.history]
    window = max(3, len(related_history) // 4) if related_history else 0
    early_related = fmean(related_history[:window]) if window else 0.0
    late_related = fmean(related_history[-window:]) if window else 0.0

    risk_label = "low"
    if data.metrics.mean_inbreeding_coefficient >= 0.10 or close_kin_rate >= 0.18:
        risk_label = "high"
    elif data.metrics.mean_inbreeding_coefficient >= 0.04 or close_kin_rate >= 0.08:
        risk_label = "moderate"

    if migrants_per_tick >= 1.1 and late_related < early_related * 0.90:
        migration_line = (
            "Migration appears to have partially reduced isolation in this run: related "
            "mating rates fell as movement accumulated."
        )
    elif migrants_per_tick < 0.45:
        migration_line = (
            "Migration remained weak relative to run length, so local isolation likely "
            "persisted across groups and regions."
        )
    else:
        migration_line = (
            "Migration was present, but its effect on reducing isolation was mixed in this "
            "particular run."
        )

    if data.run_summary.peak_region_pressure_over_run >= 1.10:
        pressure_line = (
            "Regional pressure reached bottleneck-like levels at least once, which suggests "
            "crowding or shock windows were able to compress parts of the population."
        )
    elif data.run_summary.peak_region_pressure_over_run >= 0.95:
        pressure_line = (
            "Regional pressure came close to local carrying limits, but bottleneck pressure "
            "was moderate rather than extreme."
        )
    else:
        pressure_line = (
            "Regional carrying-capacity pressure stayed fairly contained, so severe spatial "
            "bottlenecks were limited in this run."
        )

    if data.controls.dispersal_rate <= 0.03 and close_kin_rate >= 0.10:
        low_dispersal_line = (
            "Under low dispersal, close-kin matings became noticeably more frequent in this "
            "simplified model, which is consistent with isolation increasing inbreeding risk."
        )
    elif data.controls.dispersal_rate <= 0.03:
        low_dispersal_line = (
            "Dispersal was deliberately low, but close-kin matings did not dominate this "
            "particular run."
        )
    else:
        low_dispersal_line = (
            "With the current dispersal setting, close-kin matings were present but did not "
            "overwhelm the mating pool."
        )

    return [
        (
            f"Inbreeding risk remained {risk_label} in this run "
            f"(final mean F = {data.metrics.mean_inbreeding_coefficient:.3f}, "
            f"close-kin mating share = {close_kin_rate * 100:.1f}%, "
            f"extreme share = {extreme_rate * 100:.1f}%)."
        ),
        migration_line,
        pressure_line,
        low_dispersal_line,
        (
            f"Overall related mating accounted for {related_rate * 100:.1f}% of recorded "
            f"mating events. These interpretations are heuristic and scenario-dependent, "
            "not historical claims."
        ),
    ]


def _count_rate(count: int, total: int) -> str:
    rate = _safe_rate(count, total)
    return f"{count} ({rate * 100:.1f}%)"


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _region_fill(base_color: str, pressure: float, shock: float) -> str:
    pressure_mix = min(0.55, max(0.0, pressure - 0.60) * 0.60)
    shock_mix = min(0.55, shock * 0.55)
    pressured = _mix_colors(base_color, "#526b4c", pressure_mix)
    return _mix_colors(pressured, "#c65d32", shock_mix)


def _mix_colors(color_a: str, color_b: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    red_a, green_a, blue_a = _hex_to_rgb(color_a)
    red_b, green_b, blue_b = _hex_to_rgb(color_b)
    red = int(red_a + (red_b - red_a) * ratio)
    green = int(green_a + (green_b - green_a) * ratio)
    blue = int(blue_a + (blue_b - blue_a) * ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
