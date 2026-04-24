from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from models import RegionSnapshot, ScenarioPreset
from presets import load_presets
from simulation import PopulationSimulation

try:
    from report import export_simulation_report

    REPORT_EXPORT_AVAILABLE = True
    REPORT_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover - optional dependency fallback
    export_simulation_report = None
    REPORT_EXPORT_AVAILABLE = False
    REPORT_IMPORT_ERROR = exc

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    MATPLOTLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency fallback
    FigureCanvasTkAgg = None
    Figure = None
    MATPLOTLIB_AVAILABLE = False


class PopulationApp(ttk.Frame):
    """Tkinter GUI for the simplified population dynamics model."""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.pack(fill="both", expand=True)

        self.presets = load_presets()
        self.preset_by_name = {preset.name: preset for preset in self.presets}
        self.region_by_id = {
            region.identifier: region
            for preset in self.presets
            for region in preset.regions
        }

        self.selected_scenario = tk.StringVar(value=self.presets[0].name)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_text_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Paused")
        self.note_var = tk.StringVar()

        self.metric_vars = {
            "scenario": tk.StringVar(),
            "category": tk.StringVar(),
            "mode": tk.StringVar(),
            "tick": tk.StringVar(),
            "current_year": tk.StringVar(),
            "start_year": tk.StringVar(),
            "end_year": tk.StringVar(),
            "years_per_tick": tk.StringVar(),
            "auto_stop": tk.StringVar(),
            "population": tk.StringVar(),
            "adults": tk.StringVar(),
            "groups": tk.StringVar(),
            "mean_group_size": tk.StringVar(),
            "births": tk.StringVar(),
            "deaths": tk.StringVar(),
            "migrants": tk.StringVar(),
            "matings": tk.StringVar(),
            "average_age": tk.StringVar(),
            "heterozygosity": tk.StringVar(),
            "mean_f": tk.StringVar(),
            "close_kin_pct": tk.StringVar(),
            "extreme_pct": tk.StringVar(),
            "capacity": tk.StringVar(),
            "regional_pressure": tk.StringVar(),
            "active_event": tk.StringVar(),
        }

        self.kin_avoidance_var = tk.DoubleVar()
        self.dispersal_var = tk.DoubleVar()
        self.mate_radius_var = tk.DoubleVar()
        self.isolation_var = tk.DoubleVar()
        self.mode_var = tk.StringVar()
        self.start_year_var = tk.IntVar()
        self.end_year_var = tk.IntVar()
        self.years_per_tick_var = tk.IntVar()
        self.show_pair_lines_var = tk.BooleanVar(value=True)
        self.auto_export_on_pause_var = tk.BooleanVar(value=False)
        self.auto_export_on_limit_var = tk.BooleanVar(value=False)
        self.tick_limit_var = tk.IntVar(value=0)

        self.control_text_vars = {
            "kin_avoidance": tk.StringVar(),
            "dispersal": tk.StringVar(),
            "mate_radius": tk.StringVar(),
            "isolation": tk.StringVar(),
        }

        self._after_id: str | None = None
        self._running = False
        self._suspend_control_update = False
        self.simulation = PopulationSimulation(self.current_preset)

        self._chart_canvas = None
        self._chart_axes = []
        self._chart_lines: dict[str, object] = {}
        self._build_layout()
        self._load_controls_from_simulation()
        self._refresh_view()
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

    @property
    def current_preset(self) -> ScenarioPreset:
        return self.preset_by_name[self.selected_scenario.get()]

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._configure_style()

        top_controls = ttk.Frame(self)
        top_controls.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        top_controls.columnconfigure(9, weight=1)

        ttk.Button(top_controls, text="Play", command=self.play).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(top_controls, text="Pause", command=self.pause).grid(
            row=0, column=1, padx=6
        )
        ttk.Button(top_controls, text="Step", command=self.step_once).grid(
            row=0, column=2, padx=6
        )
        ttk.Button(top_controls, text="Reset", command=self.reset).grid(
            row=0, column=3, padx=(6, 14)
        )
        self.export_button = ttk.Button(
            top_controls,
            text="Export PDF Report",
            command=self.export_pdf_report,
        )
        self.export_button.grid(row=0, column=4, padx=(0, 14))
        if not REPORT_EXPORT_AVAILABLE:
            self.export_button.state(["disabled"])

        ttk.Label(top_controls, text="Speed").grid(row=0, column=5, padx=(0, 6))
        ttk.Scale(
            top_controls,
            from_=0.5,
            to=5.0,
            variable=self.speed_var,
            orient="horizontal",
            length=180,
        ).grid(row=0, column=6, sticky="ew", padx=6)
        ttk.Label(top_controls, textvariable=self.speed_text_var, width=6).grid(
            row=0, column=7, padx=(6, 12)
        )

        ttk.Label(top_controls, text="Scenario").grid(
            row=0,
            column=8,
            sticky="e",
            padx=(0, 6),
        )
        scenario_box = ttk.Combobox(
            top_controls,
            textvariable=self.selected_scenario,
            values=[preset.name for preset in self.presets],
            state="readonly",
            width=34,
        )
        scenario_box.grid(row=0, column=9, sticky="ew")
        scenario_box.bind("<<ComboboxSelected>>", self._on_scenario_selected)

        ttk.Label(
            top_controls,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).grid(row=0, column=10, padx=(12, 0))

        main_pane = ttk.Panedwindow(self, orient="horizontal")
        main_pane.grid(row=1, column=0, sticky="nsew")

        left_pane = ttk.Panedwindow(main_pane, orient="vertical")
        right_panel = ttk.Frame(main_pane, padding=(12, 0, 0, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(5, weight=1)

        map_frame = ttk.LabelFrame(left_pane, text="Regional Map", padding=10)
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            map_frame,
            background="#d7e7f0",
            highlightthickness=1,
            highlightbackground="#90aab8",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self._draw_map())

        chart_frame = ttk.LabelFrame(left_pane, text="Time-Series Charts", padding=8)
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(0, weight=1)
        self._build_charts(chart_frame)

        left_pane.add(map_frame, weight=3)
        left_pane.add(chart_frame, weight=2)

        metrics_frame = ttk.LabelFrame(right_panel, text="Live Metrics", padding=12)
        metrics_frame.grid(row=0, column=0, sticky="ew")
        metrics_frame.columnconfigure(1, weight=1)

        fields = [
            ("Scenario", "scenario"),
            ("Category", "category"),
            ("Mode", "mode"),
            ("Tick", "tick"),
            ("Current year", "current_year"),
            ("Start year", "start_year"),
            ("End year", "end_year"),
            ("Years / tick", "years_per_tick"),
            ("Auto-stop", "auto_stop"),
            ("Population", "population"),
            ("Adults", "adults"),
            ("Groups", "groups"),
            ("Mean group size", "mean_group_size"),
            ("Births / step", "births"),
            ("Deaths / step", "deaths"),
            ("Migrants / step", "migrants"),
            ("Mating events", "matings"),
            ("Average age", "average_age"),
            ("Heterozygosity", "heterozygosity"),
            ("Mean F", "mean_f"),
            ("Close-kin matings", "close_kin_pct"),
            ("Extreme matings", "extreme_pct"),
            ("Capacity use", "capacity"),
            ("Peak region pressure", "regional_pressure"),
            ("Active event", "active_event"),
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(metrics_frame, text=label).grid(
                row=row,
                column=0,
                sticky="w",
                pady=2,
            )
            ttk.Label(metrics_frame, textvariable=self.metric_vars[key]).grid(
                row=row,
                column=1,
                sticky="e",
                pady=2,
            )

        time_frame = ttk.LabelFrame(right_panel, text="Time & Mode", padding=12)
        time_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        time_frame.columnconfigure(1, weight=1)

        ttk.Label(time_frame, text="Simulation mode").grid(row=0, column=0, sticky="w", pady=2)
        mode_box = ttk.Combobox(
            time_frame,
            textvariable=self.mode_var,
            values=["Historical scenario mode", "Sandbox mode"],
            state="readonly",
            width=22,
        )
        mode_box.grid(row=0, column=1, sticky="ew", padx=8, pady=2)
        mode_box.bind("<<ComboboxSelected>>", self._on_control_changed)

        ttk.Label(time_frame, text="Start year (BP)").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(
            time_frame,
            from_=0,
            to=300000,
            increment=1000,
            textvariable=self.start_year_var,
            width=10,
            command=self._on_control_changed,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=2)

        ttk.Label(time_frame, text="End year (BP)").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Spinbox(
            time_frame,
            from_=0,
            to=300000,
            increment=1000,
            textvariable=self.end_year_var,
            width=10,
            command=self._on_control_changed,
        ).grid(row=2, column=1, sticky="w", padx=8, pady=2)

        ttk.Label(time_frame, text="Years per tick").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Spinbox(
            time_frame,
            from_=1,
            to=5000,
            increment=50,
            textvariable=self.years_per_tick_var,
            width=10,
            command=self._on_control_changed,
        ).grid(row=3, column=1, sticky="w", padx=8, pady=2)

        ttk.Label(
            time_frame,
            text="Historical mode stops at the configured end year. Sandbox mode keeps running past it.",
            style="Secondary.TLabel",
            wraplength=320,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        experimental_frame = ttk.LabelFrame(
            right_panel,
            text="Experimental Controls",
            padding=12,
        )
        experimental_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        experimental_frame.columnconfigure(1, weight=1)

        self._add_control_row(
            experimental_frame,
            row=0,
            label="Kin avoidance",
            variable=self.kin_avoidance_var,
            from_=0.0,
            to=1.0,
            text_var=self.control_text_vars["kin_avoidance"],
        )
        self._add_control_row(
            experimental_frame,
            row=1,
            label="Dispersal rate",
            variable=self.dispersal_var,
            from_=0.0,
            to=0.12,
            text_var=self.control_text_vars["dispersal"],
        )
        self._add_control_row(
            experimental_frame,
            row=2,
            label="Mate radius",
            variable=self.mate_radius_var,
            from_=0.04,
            to=0.30,
            text_var=self.control_text_vars["mate_radius"],
        )
        self._add_control_row(
            experimental_frame,
            row=3,
            label="Group isolation",
            variable=self.isolation_var,
            from_=0.0,
            to=1.0,
            text_var=self.control_text_vars["isolation"],
        )

        ttk.Checkbutton(
            experimental_frame,
            text="Show mating pair lines on map",
            variable=self.show_pair_lines_var,
            command=self._draw_map,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

        report_frame = ttk.LabelFrame(right_panel, text="Report Export", padding=12)
        report_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        report_frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            report_frame,
            text="Auto export when manually paused",
            variable=self.auto_export_on_pause_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(
            report_frame,
            text="Auto export at tick limit",
            variable=self.auto_export_on_limit_var,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(report_frame, text="Tick limit").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(
            report_frame,
            from_=0,
            to=10000,
            increment=10,
            textvariable=self.tick_limit_var,
            width=10,
        ).grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Label(
            report_frame,
            text="0 disables automatic stop/export at a limit.",
            style="Secondary.TLabel",
        ).grid(row=2, column=2, sticky="w", padx=(8, 0), pady=(8, 0))
        if not REPORT_EXPORT_AVAILABLE:
            ttk.Label(
                report_frame,
                text=f"PDF export unavailable: {REPORT_IMPORT_ERROR}",
                wraplength=310,
                style="Warning.TLabel",
                justify="left",
            ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        region_frame = ttk.LabelFrame(right_panel, text="Regional Pressure", padding=8)
        region_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        region_frame.columnconfigure(0, weight=1)
        region_frame.rowconfigure(0, weight=1)

        self.region_tree = ttk.Treeview(
            region_frame,
            columns=("region", "population", "capacity", "pressure", "shock"),
            show="headings",
            height=4,
        )
        self.region_tree.heading("region", text="Region")
        self.region_tree.heading("population", text="Pop")
        self.region_tree.heading("capacity", text="Cap")
        self.region_tree.heading("pressure", text="Pressure")
        self.region_tree.heading("shock", text="Shock")
        self.region_tree.column("region", width=118, anchor="w")
        self.region_tree.column("population", width=54, anchor="e")
        self.region_tree.column("capacity", width=54, anchor="e")
        self.region_tree.column("pressure", width=76, anchor="e")
        self.region_tree.column("shock", width=58, anchor="e")
        self.region_tree.grid(row=0, column=0, sticky="ew")

        notes_frame = ttk.LabelFrame(right_panel, text="Kinship & Scenario Notes", padding=12)
        notes_frame.grid(row=5, column=0, sticky="nsew", pady=(12, 0))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)
        ttk.Label(
            notes_frame,
            textvariable=self.note_var,
            wraplength=330,
            justify="left",
            anchor="nw",
        ).grid(row=0, column=0, sticky="nsew")

        main_pane.add(left_pane, weight=4)
        main_pane.add(right_panel, weight=2)

        self.speed_var.trace_add("write", lambda *_args: self._update_speed_text())
        self._bind_control_traces()
        self._update_speed_text()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.configure("Status.TLabel", padding=(10, 4))
        style.configure("Secondary.TLabel", foreground="#5c6770")
        style.configure("Warning.TLabel", foreground="#8b3a14")

    def _add_control_row(
        self,
        parent: ttk.LabelFrame,
        *,
        row: int,
        label: str,
        variable: tk.DoubleVar,
        from_: float,
        to: float,
        text_var: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Scale(
            parent,
            from_=from_,
            to=to,
            variable=variable,
            orient="horizontal",
            length=180,
        ).grid(row=row, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(parent, textvariable=text_var, width=7).grid(
            row=row,
            column=2,
            sticky="e",
            pady=2,
        )

    def _bind_control_traces(self) -> None:
        self.kin_avoidance_var.trace_add("write", lambda *_args: self._on_control_changed())
        self.dispersal_var.trace_add("write", lambda *_args: self._on_control_changed())
        self.mate_radius_var.trace_add("write", lambda *_args: self._on_control_changed())
        self.isolation_var.trace_add("write", lambda *_args: self._on_control_changed())
        self.start_year_var.trace_add("write", lambda *_args: self._on_control_changed())
        self.end_year_var.trace_add("write", lambda *_args: self._on_control_changed())
        self.years_per_tick_var.trace_add("write", lambda *_args: self._on_control_changed())

    def _build_charts(self, parent: ttk.LabelFrame) -> None:
        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(
                parent,
                text="Matplotlib is not installed. The simulator remains usable, but charts are disabled.",
                wraplength=480,
                justify="left",
            ).grid(row=0, column=0, sticky="nw")
            return

        figure = Figure(figsize=(7.5, 4.2), dpi=100, constrained_layout=True)
        axes = figure.subplots(
            3,
            1,
            sharex=True,
            gridspec_kw={"height_ratios": [1.25, 1.0, 1.05]},
        )
        self._chart_axes = list(axes)

        population_line = axes[0].plot([], [], color="#365c7f", linewidth=2.2, label="Population")[0]
        capacity_line = axes[0].plot([], [], color="#d17b0f", linewidth=1.8, linestyle="--", label="Capacity")[0]
        axes[0].set_ylabel("Population")
        axes[0].legend(loc="upper left", fontsize=8, frameon=False)

        births_line = axes[1].plot([], [], color="#2a9d8f", linewidth=1.8, label="Births")[0]
        deaths_line = axes[1].plot([], [], color="#c75146", linewidth=1.8, label="Deaths")[0]
        migrants_line = axes[1].plot([], [], color="#6c5ce7", linewidth=1.8, label="Migrants")[0]
        axes[1].set_ylabel("Step flux")
        axes[1].legend(loc="upper left", fontsize=8, frameon=False, ncol=3)

        heterozygosity_line = axes[2].plot([], [], color="#1d3557", linewidth=1.8, label="Heterozygosity")[0]
        mean_f_line = axes[2].plot([], [], color="#b5179e", linewidth=1.8, label="Mean F")[0]
        close_kin_line = axes[2].plot([], [], color="#d94841", linewidth=1.8, label="Close-kin share")[0]
        axes[2].set_ylabel("Kinship / diversity")
        axes[2].set_xlabel("Tick")
        axes[2].legend(loc="upper left", fontsize=8, frameon=False, ncol=3)

        for axis in axes:
            axis.grid(True, alpha=0.18)
            axis.set_facecolor("#fbfbf8")
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)

        canvas = FigureCanvasTkAgg(figure, master=parent)
        widget = canvas.get_tk_widget()
        widget.grid(row=0, column=0, sticky="nsew")

        self._chart_canvas = canvas
        self._chart_lines = {
            "population": population_line,
            "capacity": capacity_line,
            "births": births_line,
            "deaths": deaths_line,
            "migrants": migrants_line,
            "heterozygosity": heterozygosity_line,
            "mean_f": mean_f_line,
            "close_kin": close_kin_line,
        }

    def _load_controls_from_simulation(self) -> None:
        controls = self.simulation.controls
        self._suspend_control_update = True
        self.kin_avoidance_var.set(controls.kin_avoidance_strength)
        self.dispersal_var.set(controls.dispersal_rate)
        self.mate_radius_var.set(controls.mate_radius)
        self.isolation_var.set(controls.group_isolation_strength)
        self.mode_var.set(self._mode_value_for_ui(controls.simulation_mode))
        self.start_year_var.set(controls.start_year_bp)
        self.end_year_var.set(controls.end_year_bp)
        self.years_per_tick_var.set(controls.years_per_tick)
        self._refresh_control_text()
        self._suspend_control_update = False

    def _refresh_control_text(self) -> None:
        self.control_text_vars["kin_avoidance"].set(f"{self.kin_avoidance_var.get():.2f}")
        self.control_text_vars["dispersal"].set(f"{self.dispersal_var.get():.3f}")
        self.control_text_vars["mate_radius"].set(f"{self.mate_radius_var.get():.2f}")
        self.control_text_vars["isolation"].set(f"{self.isolation_var.get():.2f}")

    def _on_control_changed(self, _event=None) -> None:
        self._refresh_control_text()
        if self._suspend_control_update:
            return
        try:
            start_year_bp = int(self.start_year_var.get())
            end_year_bp = int(self.end_year_var.get())
            years_per_tick = int(self.years_per_tick_var.get())
        except (tk.TclError, ValueError):
            self.status_var.set("Invalid time controls")
            return
        self.simulation.set_controls(
            kin_avoidance_strength=self.kin_avoidance_var.get(),
            dispersal_rate=self.dispersal_var.get(),
            mate_radius=self.mate_radius_var.get(),
            group_isolation_strength=self.isolation_var.get(),
            simulation_mode=self._mode_value_for_simulation(self.mode_var.get()),
            start_year_bp=start_year_bp,
            end_year_bp=end_year_bp,
            years_per_tick=years_per_tick,
        )
        self._load_controls_from_simulation()
        self.status_var.set("Controls updated")
        self._refresh_view()

    def _mode_value_for_ui(self, mode: str) -> str:
        return "Sandbox mode" if mode == "sandbox" else "Historical scenario mode"

    def _mode_value_for_simulation(self, value: str) -> str:
        return "sandbox" if value == "Sandbox mode" else "historical"

    def _format_year_bp(self, year_bp: int) -> str:
        if year_bp >= 0:
            return f"{year_bp:,} BP"
        return f"{abs(year_bp):,} years after present"

    def play(self) -> None:
        if self.simulation.is_finished:
            self.status_var.set(self.simulation.end_reason or "Run already ended")
            return
        if self._running:
            return
        self._running = True
        self.status_var.set("Running")
        self._schedule_next_step()

    def pause(
        self,
        reason: str = "manual",
        allow_auto_export: bool = True,
    ) -> None:
        was_running = self._running or self._after_id is not None
        self._running = False
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        if reason == "tick_limit":
            self.status_var.set("Reached tick limit")
        elif reason == "manual":
            self.status_var.set("Paused")
        else:
            self.status_var.set("Paused")

        if not allow_auto_export or not REPORT_EXPORT_AVAILABLE:
            return
        if reason == "manual" and was_running and self.auto_export_on_pause_var.get():
            self._run_report_export(status_prefix="Paused and exported")
        elif reason == "tick_limit" and self.auto_export_on_limit_var.get():
            self._run_report_export(status_prefix="Tick limit reached; exported")

    def step_once(self) -> None:
        if self.simulation.is_finished:
            self.status_var.set(self.simulation.end_reason or "Run already ended")
            return
        if not self._running:
            self.status_var.set("Stepped")
        self.simulation.step()
        self._refresh_view()
        if self._apply_simulation_stop():
            return
        self._apply_tick_limit()

    def reset(self) -> None:
        self.pause(reason="reset", allow_auto_export=False)
        self.simulation.reset()
        self.status_var.set("Reset")
        self._refresh_view()

    def export_pdf_report(self) -> None:
        self._run_report_export(status_prefix="Report saved")

    def _schedule_next_step(self) -> None:
        if not self._running:
            return
        self._after_id = self.after(self._step_delay_ms(), self._run_loop)

    def _run_loop(self) -> None:
        self.simulation.step()
        self._refresh_view()
        if self._apply_simulation_stop():
            return
        if not self._apply_tick_limit():
            self._schedule_next_step()

    def _refresh_view(self) -> None:
        metrics = self.simulation.state.metrics
        if metrics is None:
            return

        self.metric_vars["scenario"].set(metrics.scenario_name)
        self.metric_vars["category"].set(metrics.scenario_category)
        self.metric_vars["mode"].set(metrics.mode_label)
        self.metric_vars["tick"].set(str(metrics.tick))
        self.metric_vars["current_year"].set(self._format_year_bp(metrics.current_year_bp))
        self.metric_vars["start_year"].set(self._format_year_bp(metrics.start_year_bp))
        self.metric_vars["end_year"].set(self._format_year_bp(metrics.end_year_bp))
        self.metric_vars["years_per_tick"].set(f"{metrics.years_per_tick:,}")
        self.metric_vars["auto_stop"].set(metrics.auto_stop_status)
        self.metric_vars["population"].set(str(metrics.population))
        self.metric_vars["adults"].set(str(metrics.adults))
        self.metric_vars["groups"].set(str(metrics.groups))
        self.metric_vars["mean_group_size"].set(f"{metrics.mean_group_size:.1f}")
        self.metric_vars["births"].set(str(metrics.births_last_step))
        self.metric_vars["deaths"].set(str(metrics.deaths_last_step))
        self.metric_vars["migrants"].set(str(metrics.migrants_last_step))
        self.metric_vars["matings"].set(str(metrics.mating_count_last_step))
        self.metric_vars["average_age"].set(f"{metrics.average_age:.1f} years")
        self.metric_vars["heterozygosity"].set(f"{metrics.heterozygosity:.3f}")
        self.metric_vars["mean_f"].set(f"{metrics.mean_inbreeding_coefficient:.3f}")
        self.metric_vars["close_kin_pct"].set(
            f"{metrics.close_kin_mating_share * 100:.1f}%"
        )
        self.metric_vars["extreme_pct"].set(
            f"{metrics.extreme_inbreeding_share * 100:.1f}%"
        )
        self.metric_vars["capacity"].set(
            f"{metrics.population}/{metrics.carrying_capacity} ({metrics.capacity_use:.2f})"
        )
        self.metric_vars["regional_pressure"].set(f"{metrics.peak_regional_pressure:.2f}")
        self.metric_vars["active_event"].set(metrics.active_event)

        self.note_var.set(self._build_note_text())
        self._update_region_table(self.simulation.state.regions)
        self._draw_map()
        self._update_charts()

    def _build_note_text(self) -> str:
        metrics = self.simulation.state.metrics
        if metrics is None:
            return ""

        distribution = metrics.relatedness_distribution
        distribution_lines = [
            f"{label}: {distribution.get(label, 0.0) * 100:.1f}%"
            for label in (
                "unrelated",
                "distant relatives",
                "first cousins",
                "half-siblings",
                "siblings",
                "parent-child",
            )
            if distribution.get(label, 0.0) > 0.0 or metrics.mating_count_last_step > 0
        ]
        if not distribution_lines:
            distribution_lines = ["No mating events this step."]

        active_region_notes = [
            f"{snapshot.label}: {', '.join(snapshot.active_events)}"
            for snapshot in self.simulation.state.regions
            if snapshot.active_events
        ]

        lines = [
            f"{self.current_preset.category_label}: {self.current_preset.description}",
            self.current_preset.disclaimer,
            "",
            "Scenario notes:",
            *[f"- {note}" for note in self.current_preset.scenario_notes],
            "",
            "Run timing:",
            f"{metrics.mode_label}. Current year {self._format_year_bp(metrics.current_year_bp)} with {metrics.years_per_tick:,} years per tick.",
            f"Configured span: {self._format_year_bp(metrics.start_year_bp)} to {self._format_year_bp(metrics.end_year_bp)}.",
            f"Auto-stop status: {metrics.auto_stop_status}.",
            f"Pedigree depth tracked: {self.simulation.PEDIGREE_DEPTH} generations.",
            "Offspring F is approximated as half the pedigree-based coefficient of relatedness between parents.",
            "",
            "Current relatedness mix among mating pairs:",
            *distribution_lines,
            "",
            "Controls:",
            f"Kin avoidance {self.kin_avoidance_var.get():.2f}, dispersal {self.dispersal_var.get():.3f}, mate radius {self.mate_radius_var.get():.2f}, isolation {self.isolation_var.get():.2f}.",
        ]
        if active_region_notes:
            lines.extend(["", "Active regional stress:", *active_region_notes])
        elif metrics.active_event != "None":
            lines.extend(["", f"Active event window: {metrics.active_event}."])
        if metrics.ended_reason:
            lines.extend(["", f"Run ended because: {metrics.ended_reason}."])
        return "\n".join(lines)

    def _update_region_table(self, regions: list[RegionSnapshot]) -> None:
        for item_id in self.region_tree.get_children():
            self.region_tree.delete(item_id)

        for snapshot in regions:
            self.region_tree.insert(
                "",
                "end",
                iid=snapshot.region_id,
                values=(
                    snapshot.label,
                    snapshot.population,
                    snapshot.carrying_capacity,
                    f"{snapshot.pressure:.2f}",
                    f"{snapshot.shock_level:.2f}",
                ),
            )

    def _draw_map(self) -> None:
        width = max(self.canvas.winfo_width(), 460)
        height = max(self.canvas.winfo_height(), 360)
        self.canvas.delete("all")

        self._draw_map_background(width, height)
        self._draw_region_connections(width, height)

        snapshots = {
            snapshot.region_id: snapshot for snapshot in self.simulation.state.regions
        }
        for region in self.current_preset.regions:
            snapshot = snapshots.get(region.identifier)
            pressure = 0.0 if snapshot is None else snapshot.pressure
            shock = 0.0 if snapshot is None else snapshot.shock_level
            fill_color = self._region_fill(region.color, pressure, shock)
            shadow_points = self._offset_points(region.polygon, 0.008, 0.010)

            self.canvas.create_polygon(
                self._scale_points(width, height, shadow_points),
                fill="#9db3be",
                outline="",
            )
            self.canvas.create_polygon(
                self._scale_points(width, height, list(region.polygon)),
                fill=fill_color,
                outline="#576b6f",
                width=2.0 + min(2.5, shock * 3.0),
            )

            label_lines = [region.label]
            if snapshot is not None:
                label_lines.append(
                    f"{snapshot.population}/{snapshot.carrying_capacity}  p={snapshot.pressure:.2f}"
                )
            self.canvas.create_text(
                region.center_x * width,
                max(16, (region.center_y - region.spread_y - 0.06) * height),
                text="\n".join(label_lines),
                fill="#223c43",
                font=("TkDefaultFont", 10, "bold"),
                justify="center",
            )

        self._draw_migration_flows(width, height)
        if self.show_pair_lines_var.get():
            self._draw_recent_matings(width, height)

        for marker in sorted(self.simulation.state.markers, key=lambda item: item.size):
            x = marker.x * width
            y = marker.y * height
            radius = marker.size / 2
            outline = self._mix_colors("#ffffff", "#b6402c", min(0.6, marker.pressure * 0.4))
            self.canvas.create_oval(
                x - radius - 1.2,
                y - radius - 1.2,
                x + radius + 1.2,
                y + radius + 1.2,
                fill="",
                outline="#fdfdfd",
                width=1.4,
            )
            self.canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=marker.color,
                outline=outline,
                width=1.8,
            )
            if marker.group_size >= self.current_preset.group_target_size:
                self.canvas.create_text(
                    x,
                    y,
                    text=str(marker.group_size),
                    fill="#102024",
                    font=("TkDefaultFont", 8, "bold"),
                )

        self.canvas.create_text(
            12,
            10,
            text="Regional map: pressure darkens regions, shocks warm outlines, migration arrows show movement, pair lines show recent matings",
            anchor="nw",
            fill="#2e4a52",
            font=("TkDefaultFont", 10, "bold"),
        )
        self._draw_legend(width, height)

    def _draw_map_background(self, width: int, height: int) -> None:
        stripes = ["#e6f0f5", "#ddeaf1", "#d4e3ec", "#ccdde8", "#c5d8e4"]
        stripe_height = height / len(stripes)
        for index, color in enumerate(stripes):
            self.canvas.create_rectangle(
                0,
                index * stripe_height,
                width,
                (index + 1) * stripe_height,
                fill=color,
                outline="",
            )

        self.canvas.create_oval(
            width * 0.72,
            height * 0.72,
            width * 1.05,
            height * 1.05,
            fill="#d9e8ef",
            outline="",
        )
        self.canvas.create_rectangle(
            width * 0.02,
            height * 0.07,
            width * 0.98,
            height * 0.95,
            outline="#90aab8",
        )

    def _draw_region_connections(self, width: int, height: int) -> None:
        for region in self.current_preset.regions:
            for neighbor_id in region.neighbors:
                neighbor = self.region_by_id[neighbor_id]
                if region.identifier > neighbor_id:
                    continue
                self.canvas.create_line(
                    region.center_x * width,
                    region.center_y * height,
                    neighbor.center_x * width,
                    neighbor.center_y * height,
                    fill="#89a0aa",
                    dash=(5, 4),
                    width=1.4,
                )

    def _draw_migration_flows(self, width: int, height: int) -> None:
        for flow in self.simulation.state.migration_flows:
            source = self.region_by_id[flow.source_region_id]
            target = self.region_by_id[flow.target_region_id]
            width_px = min(6.0, 1.2 + flow.count * 0.55)
            color = self._mix_colors("#df6d2d", "#a52a2a", min(0.7, flow.count / 8))
            self.canvas.create_line(
                source.center_x * width,
                source.center_y * height,
                target.center_x * width,
                target.center_y * height,
                arrow="last",
                arrowshape=(12, 14, 5),
                smooth=True,
                fill=color,
                width=width_px,
            )

    def _draw_recent_matings(self, width: int, height: int) -> None:
        for event in self.simulation.state.recent_matings:
            color = "#4f6d7a"
            if event.extreme:
                color = "#8d0801"
            elif event.close_kin:
                color = "#d62828"
            elif event.relatedness_coefficient >= 0.0625:
                color = "#f4a261"

            width_px = 1.0 + min(4.5, event.relatedness_coefficient * 8.0)
            dash = () if event.close_kin else (4, 3)
            self.canvas.create_line(
                event.female_x * width,
                event.female_y * height,
                event.male_x * width,
                event.male_y * height,
                fill=color,
                width=width_px,
                dash=dash,
            )
            if event.close_kin:
                for x, y in (
                    (event.female_x * width, event.female_y * height),
                    (event.male_x * width, event.male_y * height),
                ):
                    self.canvas.create_oval(
                        x - 3,
                        y - 3,
                        x + 3,
                        y + 3,
                        fill="#fff1f0",
                        outline=color,
                        width=1.2,
                    )

    def _draw_legend(self, width: int, height: int) -> None:
        left = width * 0.03
        top = height * 0.80
        self.canvas.create_rectangle(
            left,
            top,
            left + 280,
            top + 92,
            fill="#f7fafc",
            outline="#9db1bb",
        )
        self.canvas.create_text(
            left + 10,
            top + 10,
            text="Legend",
            anchor="nw",
            fill="#24404a",
            font=("TkDefaultFont", 9, "bold"),
        )
        self.canvas.create_rectangle(
            left + 12,
            top + 30,
            left + 28,
            top + 44,
            fill="#93b35c",
            outline="",
        )
        self.canvas.create_text(
            left + 36,
            top + 37,
            text="Region fill darkens with pressure",
            anchor="w",
            fill="#24404a",
        )
        self.canvas.create_line(
            left + 14,
            top + 58,
            left + 34,
            top + 58,
            fill="#b44d35",
            width=3,
            arrow="last",
        )
        self.canvas.create_text(
            left + 36,
            top + 58,
            text="Recent inter-region migration",
            anchor="w",
            fill="#24404a",
        )
        self.canvas.create_line(
            left + 14,
            top + 78,
            left + 34,
            top + 78,
            fill="#d62828",
            width=2.4,
        )
        self.canvas.create_text(
            left + 36,
            top + 78,
            text="Close-kin mating event",
            anchor="w",
            fill="#24404a",
        )

    def _update_charts(self) -> None:
        if not MATPLOTLIB_AVAILABLE or self._chart_canvas is None:
            return

        history = self.simulation.state.history
        if not history:
            return

        ticks = [sample.tick for sample in history]
        population = [sample.population for sample in history]
        capacity = [sample.carrying_capacity for sample in history]
        births = [sample.births for sample in history]
        deaths = [sample.deaths for sample in history]
        migrants = [sample.migrants for sample in history]
        heterozygosity = [sample.heterozygosity for sample in history]
        mean_f = [sample.mean_inbreeding_coefficient for sample in history]
        close_kin = [sample.close_kin_mating_share for sample in history]

        self._chart_lines["population"].set_data(ticks, population)
        self._chart_lines["capacity"].set_data(ticks, capacity)
        self._chart_lines["births"].set_data(ticks, births)
        self._chart_lines["deaths"].set_data(ticks, deaths)
        self._chart_lines["migrants"].set_data(ticks, migrants)
        self._chart_lines["heterozygosity"].set_data(ticks, heterozygosity)
        self._chart_lines["mean_f"].set_data(ticks, mean_f)
        self._chart_lines["close_kin"].set_data(ticks, close_kin)

        x_min = ticks[0]
        x_max = max(ticks[-1], x_min + 1)
        for axis in self._chart_axes:
            axis.relim()
            axis.autoscale_view()
            axis.set_xlim(x_min, x_max)
            axis.set_ylim(bottom=0)

        self._chart_axes[2].set_ylim(
            bottom=0,
            top=max(
                1.0,
                max(
                    max(heterozygosity, default=0.0),
                    max(mean_f, default=0.0),
                    max(close_kin, default=0.0),
                )
                * 1.15,
            ),
        )
        self._chart_canvas.draw_idle()

    def _scale_points(
        self,
        width: int,
        height: int,
        points: list[tuple[float, float]],
    ) -> list[float]:
        scaled = []
        for x, y in points:
            scaled.extend([x * width, y * height])
        return scaled

    def _offset_points(
        self,
        points: tuple[tuple[float, float], ...],
        delta_x: float,
        delta_y: float,
    ) -> list[tuple[float, float]]:
        return [(x + delta_x, y + delta_y) for x, y in points]

    def _region_fill(self, base_color: str, pressure: float, shock: float) -> str:
        pressure_mix = min(0.55, max(0.0, pressure - 0.60) * 0.60)
        shock_mix = min(0.55, shock * 0.55)
        pressured = self._mix_colors(base_color, "#526b4c", pressure_mix)
        return self._mix_colors(pressured, "#c65d32", shock_mix)

    def _mix_colors(self, color_a: str, color_b: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        red_a, green_a, blue_a = self._hex_to_rgb(color_a)
        red_b, green_b, blue_b = self._hex_to_rgb(color_b)
        red = int(red_a + (red_b - red_a) * ratio)
        green = int(green_a + (green_b - green_a) * ratio)
        blue = int(blue_a + (blue_b - blue_a) * ratio)
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _hex_to_rgb(self, value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    def _step_delay_ms(self) -> int:
        speed = max(0.5, float(self.speed_var.get()))
        return int(1000 / speed)

    def _update_speed_text(self) -> None:
        self.speed_text_var.set(f"{self.speed_var.get():.1f}x")

    def _apply_simulation_stop(self) -> bool:
        if not self.simulation.is_finished:
            return False
        self.pause(reason="simulation_end", allow_auto_export=False)
        self.status_var.set(self.simulation.end_reason or "Simulation ended")
        return True

    def _apply_tick_limit(self) -> bool:
        try:
            limit = max(0, int(self.tick_limit_var.get()))
        except (tk.TclError, ValueError):
            self.status_var.set("Invalid tick limit")
            return False
        metrics = self.simulation.state.metrics
        if limit <= 0 or metrics is None or metrics.tick < limit:
            return False
        if self._running or self._after_id is not None:
            self.pause(reason="tick_limit", allow_auto_export=True)
        else:
            self.status_var.set("Reached tick limit")
            if REPORT_EXPORT_AVAILABLE and self.auto_export_on_limit_var.get():
                self._run_report_export(status_prefix="Tick limit reached; exported")
        return True

    def _run_report_export(self, status_prefix: str) -> None:
        if not REPORT_EXPORT_AVAILABLE or export_simulation_report is None:
            message = "PDF export unavailable"
            if REPORT_IMPORT_ERROR is not None:
                message = f"{message}: {REPORT_IMPORT_ERROR}"
            self.status_var.set(message)
            return
        try:
            path = export_simulation_report(self.simulation)
        except Exception as exc:
            self.status_var.set(f"PDF export failed: {exc}")
            return
        self.status_var.set(f"{status_prefix}: {path.name}")

    def _on_scenario_selected(self, _event=None) -> None:
        self.pause(reason="scenario_change", allow_auto_export=False)
        self.simulation.reset(self.current_preset)
        self._load_controls_from_simulation()
        self.status_var.set("Scenario loaded")
        self._refresh_view()

    def _on_close(self) -> None:
        self.pause(reason="close", allow_auto_export=False)
        self.master.destroy()
