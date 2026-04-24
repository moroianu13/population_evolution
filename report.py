from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from matplotlib.figure import Figure
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Polygon, Rectangle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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

PAGE_BACKGROUND = colors.HexColor("#ffffff")
TEXT_PRIMARY = colors.HexColor("#1f2f3d")
TEXT_SECONDARY = colors.HexColor("#5e7280")
TEXT_MUTED = colors.HexColor("#7f8f98")
TEXT_WARNING = colors.HexColor("#8a4a1e")
ACCENT = colors.HexColor("#1f4259")
TABLE_HEADER = colors.HexColor("#e9eff4")
TABLE_BORDER = colors.HexColor("#d5dde4")
TABLE_ROW_ODD = colors.HexColor("#fbfcfd")
TABLE_ROW_EVEN = colors.HexColor("#f4f7f9")
CARD_BACKGROUND = colors.HexColor("#f7fafc")
CARD_VALUE = colors.HexColor("#163042")
CARD_LABEL = colors.HexColor("#6d7f8a")


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

    styles = _build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=0.72 * inch,
        rightMargin=0.72 * inch,
        topMargin=0.72 * inch,
        bottomMargin=0.72 * inch,
        title=f"Population Evolution Report - {data.scenario.name}",
        author="Population Evolution Simulator",
        subject="Agent-based population simulation summary",
    )

    story = []
    story.extend(_build_page_one_story(data, styles, doc.width))
    story.append(PageBreak())
    story.extend(_build_page_two_story(data, styles, doc.width))
    story.append(PageBreak())
    story.extend(_build_page_three_story(data, styles, doc.width))

    doc.build(story)
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
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", scenario_name).strip("_").lower() or "scenario"
    return output_dir / f"{timestamp}_{slug}_report.pdf"


def _build_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}
    styles["report_title"] = ParagraphStyle(
        "ReportTitle",
        parent=sample["Title"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=25,
        textColor=TEXT_PRIMARY,
        spaceAfter=4,
    )
    styles["scenario_title"] = ParagraphStyle(
        "ScenarioTitle",
        parent=sample["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=ACCENT,
        spaceAfter=6,
    )
    styles["section_title"] = ParagraphStyle(
        "SectionTitle",
        parent=sample["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=TEXT_PRIMARY,
        spaceAfter=6,
    )
    styles["body"] = ParagraphStyle(
        "Body",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=13,
        textColor=TEXT_PRIMARY,
        spaceAfter=6,
    )
    styles["meta"] = ParagraphStyle(
        "Meta",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=9.0,
        leading=12,
        textColor=TEXT_SECONDARY,
        spaceAfter=4,
    )
    styles["note"] = ParagraphStyle(
        "Note",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=11.5,
        textColor=TEXT_WARNING,
        spaceAfter=6,
    )
    styles["small"] = ParagraphStyle(
        "Small",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.2,
        textColor=TEXT_MUTED,
    )
    styles["table_header"] = ParagraphStyle(
        "TableHeader",
        parent=sample["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.4,
        leading=10.2,
        textColor=TEXT_PRIMARY,
    )
    styles["table_cell"] = ParagraphStyle(
        "TableCell",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=8.1,
        leading=10.2,
        textColor=TEXT_PRIMARY,
    )
    styles["table_cell_small"] = ParagraphStyle(
        "TableCellSmall",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=9.5,
        textColor=TEXT_PRIMARY,
    )
    styles["card_label"] = ParagraphStyle(
        "CardLabel",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=9.8,
        textColor=CARD_LABEL,
        alignment=1,
    )
    styles["card_value"] = ParagraphStyle(
        "CardValue",
        parent=sample["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=CARD_VALUE,
        alignment=1,
    )
    return styles


def _build_page_one_story(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    content_width: float,
) -> list:
    story = []
    story.extend(_build_title_block(data, styles))
    story.append(Spacer(1, 10))
    story.append(_build_summary_cards(data, styles, content_width))
    story.append(Spacer(1, 12))
    panel_width = (content_width - 12) / 2.0
    story.append(
        _two_column_layout(
            left_flowables=[
                Paragraph("Run Summary", styles["section_title"]),
                _build_key_value_table(
                    _summary_rows(data),
                    styles,
                    (panel_width * 0.51, panel_width * 0.49),
                ),
            ],
            right_flowables=[
                Paragraph("Important Inputs", styles["section_title"]),
                _build_key_value_table(
                    _input_rows(data),
                    styles,
                    (panel_width * 0.52, panel_width * 0.48),
                ),
            ],
            total_width=content_width,
            left_width=panel_width,
            right_width=panel_width,
        )
    )
    story.append(Spacer(1, 12))
    story.append(Paragraph("Population By Region", styles["section_title"]))
    story.append(_build_region_table(data, styles, content_width))
    return story


def _build_page_two_story(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    content_width: float,
) -> list:
    del styles
    chart_width = (content_width - 12) / 2.0
    chart_height = chart_width * 0.62
    images = [
        _rl_image(
            _render_population_chart(data),
            chart_width,
            chart_height,
        ),
        _rl_image(
            _render_flux_chart(data),
            chart_width,
            chart_height,
        ),
        _rl_image(
            _render_diversity_chart(data),
            chart_width,
            chart_height,
        ),
        _rl_image(
            _render_pressure_chart(data),
            chart_width,
            chart_height,
        ),
    ]

    image_grid = Table(
        [[images[0], images[1]], [images[2], images[3]]],
        colWidths=[chart_width, chart_width],
    )
    image_grid.hAlign = "CENTER"
    image_grid.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return [Spacer(1, 2), image_grid]


def _build_page_three_story(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    content_width: float,
) -> list:
    map_width = content_width
    map_height = map_width * 0.35
    map_image = _rl_image(_render_map_snapshot(data), map_width, map_height)
    map_image.hAlign = "CENTER"

    interpretation = Paragraph(
        _bulleted_html(_interpretation_lines(data)),
        styles["body"],
    )
    notes = Paragraph(
        _notes_html(data),
        styles["meta"],
    )

    return [
        Paragraph("Map Snapshot", styles["section_title"]),
        map_image,
        Spacer(1, 14),
        Paragraph("Interpretation", styles["section_title"]),
        interpretation,
        Spacer(1, 12),
        Paragraph("Notes", styles["section_title"]),
        notes,
    ]


def _build_title_block(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
) -> list:
    generated = data.generated_at.strftime("%Y-%m-%d %H:%M:%S %Z")
    meta = (
        f"<b>Category:</b> {escape(data.scenario.category_label)} &nbsp;&nbsp;&nbsp; "
        f"<b>Mode:</b> {escape(data.run_summary.mode_label)} &nbsp;&nbsp;&nbsp; "
        f"<b>Generated:</b> {escape(generated)}"
    )
    timing = (
        f"<b>Scenario span:</b> {_format_year_bp(data.run_summary.start_year_bp)} "
        f"to {_format_year_bp(data.run_summary.end_year_bp)} &nbsp;&nbsp;&nbsp; "
        f"<b>Years per tick:</b> {data.run_summary.years_per_tick:,}"
    )
    return [
        Paragraph("Population Evolution Simulation Report", styles["report_title"]),
        Paragraph(escape(data.scenario.name), styles["scenario_title"]),
        Paragraph(meta, styles["meta"]),
        Paragraph(timing, styles["meta"]),
        Paragraph(escape(data.scenario.description), styles["body"]),
        Paragraph(escape(data.scenario.disclaimer), styles["note"]),
    ]


def _build_summary_cards(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    content_width: float,
) -> Table:
    cards = [
        ("Final Population", str(data.metrics.population)),
        ("Births Total", str(data.run_summary.births_total)),
        ("Heterozygosity", f"{data.metrics.heterozygosity:.3f}"),
        ("Mean Inbreeding F", f"{data.metrics.mean_inbreeding_coefficient:.3f}"),
    ]
    cells = []
    for label, value in cards:
        cells.append(
            [
                Paragraph(escape(label), styles["card_label"]),
                Spacer(1, 4),
                Paragraph(escape(value), styles["card_value"]),
            ]
        )
    table = Table([cells], colWidths=[content_width / 4.0] * 4)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CARD_BACKGROUND),
                ("BOX", (0, 0), (-1, -1), 1, TABLE_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 1, TABLE_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _build_key_value_table(
    rows: list[tuple[str, str]],
    styles: dict[str, ParagraphStyle],
    col_widths: tuple[float, float],
) -> Table:
    data_rows = [
        [
            Paragraph("<b>Field</b>", styles["table_header"]),
            Paragraph("<b>Value</b>", styles["table_header"]),
        ]
    ]
    for label, value in rows:
        data_rows.append(
            [
                Paragraph(escape(label), styles["table_cell"]),
                Paragraph(escape(value), styles["table_cell"]),
            ]
        )

    table = Table(data_rows, colWidths=list(col_widths), repeatRows=1)
    table.setStyle(_base_table_style(len(data_rows)))
    return table


def _build_region_table(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    total_width: float,
) -> Table:
    rows = [
        [
            Paragraph("<b>Region</b>", styles["table_header"]),
            Paragraph("<b>Pop</b>", styles["table_header"]),
            Paragraph("<b>Cap</b>", styles["table_header"]),
            Paragraph("<b>Pressure</b>", styles["table_header"]),
        ]
    ]
    col_widths = [
        total_width * 0.44,
        total_width * 0.16,
        total_width * 0.16,
        total_width * 0.20,
    ]
    for snapshot in data.regions:
        rows.append(
            [
                Paragraph(escape(snapshot.label), styles["table_cell"]),
                Paragraph(str(snapshot.population), styles["table_cell"]),
                Paragraph(str(snapshot.carrying_capacity), styles["table_cell"]),
                Paragraph(f"{snapshot.pressure:.2f}", styles["table_cell"]),
            ]
        )
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_base_table_style(len(rows), right_align_columns=(1, 2, 3)))
    return table


def _two_column_layout(
    *,
    left_flowables: list,
    right_flowables: list,
    total_width: float,
    left_width: float,
    right_width: float,
) -> Table:
    gap = max(8.0, total_width - left_width - right_width)
    layout = Table(
        [[left_flowables, right_flowables]],
        colWidths=[left_width, right_width],
    )
    layout.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), gap),
                ("LEFTPADDING", (1, 0), (1, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return layout


def _base_table_style(
    row_count: int,
    right_align_columns: tuple[int, ...] = (),
) -> TableStyle:
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
        ("BOX", (0, 0), (-1, -1), 1, TABLE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.75, TABLE_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for row_index in range(1, max(1, row_count)):
        background = TABLE_ROW_ODD if row_index % 2 else TABLE_ROW_EVEN
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), background))
    for column_index in right_align_columns:
        commands.append(("ALIGN", (column_index, 1), (column_index, -1), "RIGHT"))
    return TableStyle(commands)


def _summary_rows(data: ReportData) -> list[tuple[str, str]]:
    return [
        ("Current simulated year", _format_year_bp(data.run_summary.current_year_bp)),
        ("Total ticks", str(data.run_summary.total_ticks)),
        ("Initial population", str(data.run_summary.initial_population)),
        ("Final population", str(data.metrics.population)),
        ("Average age", f"{data.metrics.average_age:.1f}"),
        (
            "Births / deaths / migrants",
            (
                f"{data.run_summary.births_total} / {data.run_summary.deaths_total} / "
                f"{data.run_summary.migrants_total}"
            ),
        ),
        ("Heterozygosity (final)", f"{data.metrics.heterozygosity:.3f}"),
        ("Mean inbreeding F", f"{data.metrics.mean_inbreeding_coefficient:.3f}"),
        (
            "Related matings",
            _count_rate(data.run_summary.related_mating_total, data.run_summary.mating_total),
        ),
        (
            "Close-kin matings",
            _count_rate(data.run_summary.close_kin_mating_total, data.run_summary.mating_total),
        ),
        ("Peak region pressure", f"{data.run_summary.peak_region_pressure_over_run:.2f}"),
        ("Run ended", data.run_summary.ended_reason or "Still running"),
    ]


def _input_rows(data: ReportData) -> list[tuple[str, str]]:
    return [
        ("Genome loci", str(data.scenario.genome_loci)),
        ("Group target", str(data.scenario.group_target_size)),
        ("Adult age", str(data.scenario.adult_age)),
        ("Birth interval", f"{data.scenario.birth_interval} years"),
        ("Birth prob / year", f"{data.scenario.annual_birth_probability:.3f}"),
        (
            "Migration / long-distance",
            f"{data.scenario.migration_rate:.3f} / {data.scenario.long_distance_migration_rate:.3f}",
        ),
        (
            "Exogamy / kin avoidance",
            f"{data.scenario.exogamy_rate:.3f} / {data.controls.kin_avoidance_strength:.2f}",
        ),
        (
            "Dispersal / mate radius",
            f"{data.controls.dispersal_rate:.3f} / {data.controls.mate_radius:.2f}",
        ),
        ("Isolation strength", f"{data.controls.group_isolation_strength:.2f}"),
    ]


def _history_for_report(data: ReportData) -> list[MetricSample]:
    if data.history:
        return data.history
    return [
        MetricSample(
            tick=data.metrics.tick,
            year_bp=data.metrics.current_year_bp,
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


def _render_population_chart(data: ReportData) -> BytesIO:
    history = _history_for_report(data)
    x_values = [sample.year_bp for sample in history]
    return _render_line_chart(
        title="Population Over Time",
        subtitle="Population and total carrying capacity",
        x_values=x_values,
        series=[
            ("Population", [sample.population for sample in history], "#365c7f"),
            ("Capacity", [sample.carrying_capacity for sample in history], "#d17b0f"),
        ],
        y_label="Count",
    )


def _render_flux_chart(data: ReportData) -> BytesIO:
    history = _history_for_report(data)
    x_values = [sample.year_bp for sample in history]
    return _render_line_chart(
        title="Births / Deaths / Migrants",
        subtitle="Per-tick demographic and movement fluxes",
        x_values=x_values,
        series=[
            ("Births", [sample.births for sample in history], "#2a9d8f"),
            ("Deaths", [sample.deaths for sample in history], "#c75146"),
            ("Migrants", [sample.migrants for sample in history], "#6c5ce7"),
        ],
        y_label="Per tick",
    )


def _render_diversity_chart(data: ReportData) -> BytesIO:
    history = _history_for_report(data)
    x_values = [sample.year_bp for sample in history]
    return _render_line_chart(
        title="Diversity And Inbreeding",
        subtitle="Heterozygosity, mean F, and close-kin share",
        x_values=x_values,
        series=[
            ("Heterozygosity", [sample.heterozygosity for sample in history], "#1d3557"),
            (
                "Mean F",
                [sample.mean_inbreeding_coefficient for sample in history],
                "#b5179e",
            ),
            (
                "Close-kin share",
                [sample.close_kin_mating_share for sample in history],
                "#d94841",
            ),
        ],
        y_label="Value / share",
        y_floor=0.0,
    )


def _render_pressure_chart(data: ReportData) -> BytesIO:
    history = _history_for_report(data)
    x_values = [sample.year_bp for sample in history]
    return _render_line_chart(
        title="Pressure And Related Mating",
        subtitle="Peak regional pressure and related mating share",
        x_values=x_values,
        series=[
            (
                "Peak pressure",
                [sample.peak_regional_pressure for sample in history],
                "#8d6e63",
            ),
            (
                "Related share",
                [sample.related_mating_share for sample in history],
                "#f4a261",
            ),
        ],
        y_label="Value / share",
        y_floor=0.0,
    )


def _render_line_chart(
    *,
    title: str,
    subtitle: str,
    x_values: list[int],
    series: list[tuple[str, list[float], str]],
    y_label: str,
    y_floor: float | None = None,
) -> BytesIO:
    figure = Figure(figsize=(6.1, 3.5), dpi=170)
    axis = figure.add_subplot(111)
    axis.set_facecolor("white")
    for spine in axis.spines.values():
        spine.set_color("#d5dde4")
        spine.set_linewidth(0.9)
    axis.grid(True, color="#dbe3e8", alpha=0.35)
    axis.tick_params(axis="both", labelsize=8, colors="#5e7280")
    axis.set_title(title, loc="left", fontsize=11.5, fontweight="bold", color="#1f2f3d", pad=16)
    axis.text(
        0.0,
        1.02,
        subtitle,
        transform=axis.transAxes,
        fontsize=8.3,
        color="#7f8f98",
        va="bottom",
    )

    for label, values, color in series:
        axis.plot(x_values, values, color=color, linewidth=2.0, label=label)

    axis.set_xlabel("Simulated year (BP)", fontsize=8.5, color="#5e7280")
    axis.set_ylabel(y_label, fontsize=8.5, color="#5e7280")
    if x_values:
        oldest = max(x_values)
        youngest = min(x_values)
        if oldest == youngest:
            oldest += 1
            youngest -= 1
        axis.set_xlim(oldest, youngest)
    if y_floor is not None:
        axis.set_ylim(bottom=y_floor)
    if len(series) > 1:
        axis.legend(loc="upper left", frameon=False, fontsize=7.4, ncol=min(3, len(series)))

    buffer = BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=170, facecolor="white", bbox_inches="tight")
    buffer.seek(0)
    return buffer


def _render_map_snapshot(data: ReportData) -> BytesIO:
    figure = Figure(figsize=(7.6, 4.25), dpi=170)
    axis = figure.add_subplot(111)
    axis.set_xlim(0.0, 1.0)
    axis.set_ylim(1.0, 0.0)
    axis.set_aspect("equal")
    axis.axis("off")
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")

    stripes = ["#e6f0f5", "#ddeaf1", "#d4e3ec", "#ccdde8", "#c5d8e4"]
    stripe_height = 1.0 / len(stripes)
    for index, color in enumerate(stripes):
        axis.axhspan(
            index * stripe_height,
            (index + 1) * stripe_height,
            facecolor=color,
            edgecolor="none",
            zorder=0,
        )

    axis.add_patch(
        Ellipse(
            (0.86, 0.84),
            width=0.32,
            height=0.24,
            facecolor="#d9e8ef",
            edgecolor="none",
            zorder=0.1,
        )
    )
    axis.add_patch(
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
            axis.plot(
                [region.center_x, neighbor.center_x],
                [region.center_y, neighbor.center_y],
                color="#89a0aa",
                linewidth=1.15,
                linestyle=(0, (4, 3)),
                zorder=0.3,
            )

    for region in data.scenario.regions:
        snapshot = snapshot_by_id.get(region.identifier)
        pressure = 0.0 if snapshot is None else snapshot.pressure
        shock = 0.0 if snapshot is None else snapshot.shock_level
        fill_color = _region_fill(region.color, pressure, shock)
        shadow = [(x + 0.008, y + 0.010) for x, y in region.polygon]
        axis.add_patch(
            Polygon(
                shadow,
                closed=True,
                facecolor="#9db3be",
                edgecolor="none",
                zorder=0.5,
            )
        )
        axis.add_patch(
            Polygon(
                region.polygon,
                closed=True,
                facecolor=fill_color,
                edgecolor="#576b6f",
                linewidth=1.6 + min(1.6, shock * 2.6),
                zorder=0.6,
            )
        )
        label = region.label
        if snapshot is not None:
            label = f"{label}\n{snapshot.population}/{snapshot.carrying_capacity}  p={snapshot.pressure:.2f}"
        axis.text(
            region.center_x,
            max(0.05, region.center_y - region.spread_y - 0.07),
            label,
            ha="center",
            va="center",
            fontsize=8.6,
            fontweight="bold",
            color="#223c43",
            zorder=0.8,
        )

    for flow in data.migration_flows:
        source = region_by_id[flow.source_region_id]
        target = region_by_id[flow.target_region_id]
        color = _mix_colors("#df6d2d", "#a52a2a", min(0.7, flow.count / 8.0))
        axis.add_patch(
            FancyArrowPatch(
                (source.center_x, source.center_y),
                (target.center_x, target.center_y),
                arrowstyle="-|>",
                mutation_scale=12 + flow.count * 1.5,
                linewidth=min(4.0, 1.0 + flow.count * 0.35),
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
        axis.plot(
            [event.female_x, event.male_x],
            [event.female_y, event.male_y],
            color=color,
            linewidth=1.0 + min(3.2, event.relatedness_coefficient * 8.0),
            linestyle="-" if event.close_kin else (0, (4, 3)),
            alpha=0.88,
            zorder=1.0,
        )
        if event.close_kin:
            for x, y in ((event.female_x, event.female_y), (event.male_x, event.male_y)):
                axis.add_patch(
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
        axis.add_patch(
            Circle(
                (marker.x, marker.y),
                radius=radius + 0.0023,
                facecolor="none",
                edgecolor="#fdfdfd",
                linewidth=1.0,
                zorder=1.1,
            )
        )
        axis.add_patch(
            Circle(
                (marker.x, marker.y),
                radius=radius,
                facecolor=marker.color,
                edgecolor=outline,
                linewidth=1.2,
                zorder=1.15,
            )
        )
        if marker.group_size >= data.scenario.group_target_size:
            axis.text(
                marker.x,
                marker.y,
                str(marker.group_size),
                ha="center",
                va="center",
                fontsize=7.2,
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
    axis.text(
        0.03,
        0.96,
        legend,
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color="#24404a",
        bbox={"facecolor": "#f7fafc", "edgecolor": "#9db1bb", "boxstyle": "round,pad=0.5"},
        zorder=2.0,
    )

    buffer = BytesIO()
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=170, facecolor="white", bbox_inches="tight")
    buffer.seek(0)
    return buffer


def _rl_image(buffer: BytesIO, width: float, height: float) -> RLImage:
    image = RLImage(buffer, width=width, height=height)
    image.hAlign = "CENTER"
    return image


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
            "Migration appears to have partially reduced isolation in this run because "
            "related mating rates fell as movement accumulated."
        )
    elif migrants_per_tick < 0.45:
        migration_line = (
            "Migration remained weak relative to run length, so local isolation likely "
            "persisted across groups and regions."
        )
    else:
        migration_line = (
            "Migration was present, but its effect on reducing isolation was mixed in this run."
        )

    if data.run_summary.peak_region_pressure_over_run >= 1.10:
        pressure_line = (
            "Regional pressure reached bottleneck-like levels at least once, which suggests "
            "crowding or stress windows compressed parts of the population."
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
            "simplified model, consistent with isolation increasing inbreeding risk."
        )
    elif data.controls.dispersal_rate <= 0.03:
        low_dispersal_line = (
            "Dispersal was deliberately low, but close-kin matings did not dominate this run."
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
            "mating events. These interpretations are heuristic and scenario-dependent, "
            "not historical claims."
        ),
    ]


def _notes_html(data: ReportData) -> str:
    note_lines = [
        f"<b>Scenario context:</b> {escape(data.scenario.description)}",
    ]
    if data.scenario.scenario_notes:
        note_lines.append("<b>Scenario notes:</b>")
        note_lines.extend(f"&#8226; {escape(note)}" for note in data.scenario.scenario_notes[:2])
    event_lines = _event_timeline_lines(data)
    if event_lines:
        note_lines.append("<b>Event timeline:</b>")
        note_lines.extend(f"&#8226; {escape(line)}" for line in event_lines)
    note_lines.append("<b>Report notes:</b>")
    note_lines.extend(
        [
            f"&#8226; Latest tick: {data.metrics.tick}",
            f"&#8226; Current simulated year: {_format_year_bp(data.metrics.current_year_bp)}",
            f"&#8226; Ended reason: {escape(data.run_summary.ended_reason or 'Still running')}",
            f"&#8226; Recent mating events shown on map: {len(data.recent_matings)}",
            f"&#8226; Recent inter-region flows shown on map: {len(data.migration_flows)}",
            escape(EDUCATIONAL_NOTE),
        ]
    )
    return "<br/>".join(note_lines)


def _event_timeline_lines(data: ReportData) -> list[str]:
    if not data.run_summary.event_history:
        return []

    region_labels = {region.identifier: region.label for region in data.scenario.regions}
    lines: list[str] = []
    for entry in data.run_summary.event_history:
        regions = (
            ", ".join(region_labels.get(region_id, region_id) for region_id in entry.affected_regions)
            if entry.affected_regions
            else "All regions"
        )
        lines.append(
            (
                f"{entry.name}: {_format_year_bp(entry.start_year_bp)} to "
                f"{_format_year_bp(entry.end_year_bp)}; {regions}; status: {entry.status}."
            )
        )
    return lines


def _bulleted_html(lines: list[str]) -> str:
    return "<br/><br/>".join(f"&#8226; {escape(line)}" for line in lines)


def _count_rate(count: int, total: int) -> str:
    rate = _safe_rate(count, total)
    return f"{count} ({rate * 100:.1f}%)"


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _format_year_bp(year_bp: int) -> str:
    if year_bp >= 0:
        return f"{year_bp:,} BP"
    return f"{abs(year_bp):,} years after present"


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
