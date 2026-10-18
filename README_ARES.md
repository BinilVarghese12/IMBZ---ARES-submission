# A.R.E.S. starter allocation engine

This starter project contains fictional Greater Manchester depot data and a Python allocation engine.

## Files
- `ares_greater_manchester_fake_data.csv` — fictional data for the ten Greater Manchester boroughs.
- `ares_allocation_engine.py` — validates the input, allocates a fixed fleet, saves recommendations, and optionally creates a Folium map.

## Run on LinuxONE

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas folium
python ares_allocation_engine.py
```

If Folium cannot be installed in your environment, the CSV recommendations still work; the map step is skipped.

## Useful commands

Use the default fleet (sum of `current_ambulances`):

```bash
python ares_allocation_engine.py
```

Try a smaller hypothetical fleet of 40:

```bash
python ares_allocation_engine.py --fleet 40
```

Recommend a depot for a newly available ambulance:

```bash
python ares_allocation_engine.py --ambulance-id AMB-TEST-01
```

Recommend a destination when considering moving an ambulance from a source depot:

```bash
python ares_allocation_engine.py --ambulance-id AMB-TEST-01 --from-depot "Trafford Depot"
```

The engine writes:
- `ares_allocation_recommendations.csv`
- `ares_allocation_map.html` (if Folium is available)

## Input CSV columns

- `town_or_district`
- `depot_name` (must be unique)
- `latitude`, `longitude`
- `predicted_calls_per_hour`
- `current_ambulances`
- `minimum_ambulances_required`
- `priority_weight` (relative importance multiplier; default should generally be 1.0)

Replace the synthetic values with your own validated data. Coordinates are approximate town-centre examples, not verified operational depot addresses.

## Important limitations

This is a transparent greedy heuristic, not a trained ML model or a clinically validated deployment tool. It allocates a fixed number of ambulances to depot-level counts based on a shortage bonus, predicted demand, and priority weights. The single-ambulance helper is a simple recommendation based on the allocation output and is not a full route/coverage optimisation model. For a stronger version, add road-network travel times, call severity, ambulance turnaround/occupancy, shift constraints, and an OR-Tools optimisation model. Do not use this synthetic prototype to make real emergency-service decisions.
