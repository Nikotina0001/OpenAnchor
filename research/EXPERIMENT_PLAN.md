# Initial calibration and experiment plan

No physical measurements have been collected. Filament pair names are candidates, not validated recipes. Check filament manufacturer processing limits and anchor creep at the chosen bed/chamber temperature before a print trial.

Use `examples/calibration-bar.stl` (60 × 20 × 10 mm, already bed positioned). Print five repetitions for each condition with the same orientation, plate preparation, dry filament, enclosure, cooling and process parameters:

1. No-brim control: `control-no-brim.3mf`.
2. Conventional brim: import the calibration bar and `control-conventional-brim.stl` as aligned parts, both main filament.
3. Different-material non-interlocking brim: import the bar and `control-second-material-no-interlock.stl` aligned, assigning the ring to the second filament. Keep contact geometry identical to condition 2.
4. OpenAnchor: `openanchor-demo.3mf`, main+flange slot 1; anchor+cap slot 2. Start with Hf=0.8 mm, Wf=5 mm, Wa=10 mm, L=2 mm, Tc=0.4 mm, G=0.1 mm and the actual resolved layer plan.

First compare PP with a documented candidate anchor filament. PLA at an 80°C bed triggers an estimated softening risk and is a comparison condition, not a recommended validated pair. Repeat with PA66 and a manufacturer-documented higher-temperature candidate. Keep each material pairing's process fixed within its four-condition comparison.

For each print record run ID, condition, lot/grade, moisture preparation, bed/nozzle/chamber temperature, layer schedule, material slot mapping, first-layer image, time of first lift, maximum corner lift after cooling (mm), pass/failure criterion, anchor detachment, flange removal force (N with calibrated fixture), dimensional error (mm), material consumption and visible damage. Photograph failed cases too.

If capture deposition fails, check whether the flange warped before the cap completed, the small gap created a poor overhang, or anchor stiffness/bed adhesion failed. Stop a run using the printer's normal controls when unsafe; software geometry checks cannot certify the physical process.

After the baseline comparison, test Hf=0.4/0.8/1.2 mm and L=1/2/3 mm with replication. Predefine success thresholds, randomize run order and examine statistical assumptions before selecting analysis. Record raw data in `results-template.csv`; never fill missing observations with invented values.
