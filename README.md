# Population Evolution Simulator

Python/Tkinter application for a scientifically inspired, simplified agent-based model of early human population dynamics.

This project stays intentionally cautious:

- It is inspired by population-genetic, demographic, and spatial ideas.
- It does not claim historical accuracy.
- Several presets are explicitly marked as hypotheses or stress tests.
- Geography, demography, and genomes are all simplified abstractions.

## Files

- `main.py`: starts the Tkinter application window.
- `ui.py`: Tkinter layout, map, charts, live metrics, and experimental controls.
- `simulation.py`: simplified agent-based simulation core.
- `models.py`: shared dataclasses for agents, regions, events, mating overlays, metrics, and chart history.
- `presets.py`: illustrative and hypothesis-labeled scenario presets.
- `report.py`: PDF report export for summary tables, charts, map snapshots, and interpretation notes.

## Current Model Features

- Individuals with:
  - unique id
  - sex
  - age
  - parent ids
  - position
  - region
  - group membership
  - a toy diploid genome
  - an offspring inbreeding coefficient `F`
- Local mating:
  - mate choice is probabilistic rather than deterministic
  - partner weights combine distance, age compatibility, local density, group isolation, exogamy tendency, toy-genome dissimilarity, and kin avoidance
- Migration:
  - young adults can move between local groups or neighboring regions
  - destination choice is weighted by regional pressure, habitat quality, distance, shocks, and isolation
- Carrying capacity pressure by region:
  - each region has its own capacity
  - fertility, mortality, and migration pressure respond to local overcrowding
- Environmental shocks:
  - scenarios can apply historically inspired regional or global stress windows
  - shocks are tied to BP date ranges rather than arbitrary tick numbers
  - shocks can alter mortality, fertility, migration, and carrying capacity
- Group structure:
  - people live in small residential bands
  - oversized groups split
- Finite historical runs:
  - each preset includes a start year, end year, and years-per-tick step size
  - each tick advances explicit simulated time in years before present (`BP`)
  - historical mode stops automatically at the configured end year
  - runs also stop if the population goes extinct or if no reproductive adults remain
  - sandbox mode keeps the historical clock running without the end-year stop
- Pedigree tracking:
  - ancestry is tracked through recorded parents for 5 generations
  - the model estimates a pedigree-based relatedness coefficient between potential partners
  - partner relationships are categorized as:
    - parent-child
    - siblings
    - half-siblings
    - first cousins
    - distant relatives
- Inbreeding modeling:
  - offspring receive `F` derived from parental relatedness in this lightweight pedigree model
  - higher `F` increases mortality risk, especially at young ages
  - population mean `F` is tracked over time
- Live kinship metrics:
  - mean inbreeding coefficient
  - share of close-kin matings
  - share of extreme matings (`parent-child` or `siblings`)
  - distribution of relatedness among recent mating pairs
- Visualization:
  - regional pressure map
  - recent migration arrows
  - optional mating-pair lines
  - close-kin mating events highlighted in red
  - charts for population/capacity, births/deaths/migration, heterozygosity, mean `F`, and close-kin mating share
- PDF reporting:
  - manual export from the GUI with `Export PDF Report`
  - optional automatic export on manual pause
  - optional automatic export when a user-defined tick limit is reached
  - multi-page PDF with summary tables, time-series charts, a map snapshot, and heuristic interpretation text

## Experimental Controls

The GUI exposes runtime sliders for:

- `kin_avoidance_strength`
- `dispersal_rate`
- `mate_radius`
- `group_isolation_strength`

These controls are applied on top of the selected preset so you can explore when inbreeding becomes difficult to avoid.

The GUI also exposes historical run controls for:

- simulation mode (`Historical scenario mode` or `Sandbox mode`)
- `start_year_bp`
- `end_year_bp`
- `years_per_tick`
- live display of the current simulated year and auto-stop status

The GUI also exposes report-export controls for:

- automatic export when the simulation is manually paused
- automatic export when a tick limit is reached
- a tick limit stop condition (`0` disables it)

## Presets

- `Baseline / Out of Africa`
  - Illustrative baseline with most founders in an Africa-like core and gradual outward spread.
  - Not a reconstruction of real prehistory.
- `Deep bottleneck hypothesis`
  - Explicitly marked as a hypothesis.
  - Uses a small founder pool and a prolonged low-capacity phase.
- `Toba-style environmental stress hypothesis`
  - Explicitly marked as a hypothesis.
  - Adds a temporary environmental shock with lower capacity, lower fertility, higher mortality, and stronger displacement.
- `Structured ancestry`
  - Illustrative structured-population setup with lower inter-region gene flow.
  - Not presented as a single correct ancestral history.
- `Low exogamy stress test`
  - Exploratory model stress test, not a historical claim.
  - Reduces inter-group mate exchange and weakens kin avoidance.
- `Inbreeding stress test`
  - Very small founder population with low dispersal, low exogamy, high isolation, and no kin avoidance.
  - Designed specifically to study when inbreeding becomes hard to avoid.

Each preset also includes:

- a finite BP time span
- a years-per-tick step size
- a historically inspired event timeline
- scenario notes that frame the timing as model assumptions rather than certain facts

## Visualization Notes

- The map is schematic rather than geographic.
- Region fill darkens with rising pressure.
- Region outlines warm under active shock.
- Arrows show recent inter-region migration during the latest step.
- Pair lines show recent mating events when enabled.
- The chart history is capped so the GUI stays responsive.
- Active events are shown according to the current simulated year.

## Limitations

- Time advances in simplified fixed steps defined by `years_per_tick`.
- The genome uses a small set of binary diploid loci.
- The relatedness and `F` calculations are lightweight pedigree approximations rather than a full genetic simulation.
- Event dates are scenario assumptions or historically inspired windows, not asserted facts.
- No language, culture, subsistence, archaeology, or explicit disease ecology is modeled.
- Kinship is only as complete as the recorded parent links inside the simulation.
- This should be treated as an educational sandbox, not a historical inference engine.

## Run

Use Python 3.10+ and run:

```bash
.venv/bin/python main.py
```

Tkinter is part of the Python standard library on most desktop Python installations.

Charts use Matplotlib when available. If Matplotlib is missing, the simulator still runs with the map and metrics panels, but without embedded charts.

PDF reports are generated with ReportLab Platypus and use Matplotlib-rendered chart/map images, so PDF export requires both `reportlab` and `matplotlib`.

## PDF Export

- Click `Export PDF Report` in the top toolbar to save a report for the current simulation state.
- Reports are written to the `exports/` folder in the project root.
- Filenames include a timestamp and a sanitized scenario name.
- Automatic export can be enabled from the `Report Export` panel in the GUI.

Each report includes:

- title, timestamp, selected scenario, and scenario disclaimer
- important input parameters, scenario time span, years per tick, and cumulative run summary
- population by region, historical event timeline, auto-stop status, and run end reason
- charts for population, births/deaths/migration, heterozygosity, regional pressure, and mean `F`
- a current map snapshot with migration flows and recent mating overlays
- an auto-generated interpretation section
- the note:
  - `This simulation is an educational and exploratory model, not a literal reconstruction of real prehistoric demography.`
