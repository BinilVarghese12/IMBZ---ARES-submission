"""
A.R.E.S. — Ambulance Resource Estimation System
Starter allocation engine for synthetic Greater Manchester data.

IMPORTANT:
- The included data is entirely fictional and is for a datathon prototype only.
- This is a transparent heuristic allocation engine, not a clinically validated
  dispatch system or a trained machine-learning model.
- It recommends depot-level staffing, not real-time emergency dispatch.
- Replace the sample CSV with validated data before drawing operational conclusions.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import math
import pandas as pd

REQUIRED_COLUMNS = {
    "town_or_district",
    "depot_name",
    "latitude",
    "longitude",
    "predicted_calls_per_hour",
    "current_ambulances",
    "minimum_ambulances_required",
    "priority_weight",
}


def load_and_validate(path: str | Path) -> pd.DataFrame:
    """Load input CSV and check required columns and numeric values."""
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

    numeric_cols = [
        "latitude", "longitude", "predicted_calls_per_hour",
        "current_ambulances", "minimum_ambulances_required", "priority_weight",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="raise")

    if df["depot_name"].duplicated().any():
        duplicates = df.loc[df["depot_name"].duplicated(), "depot_name"].tolist()
        raise ValueError(f"Each depot_name must be unique. Duplicates: {duplicates}")
    if (df["predicted_calls_per_hour"] < 0).any():
        raise ValueError("predicted_calls_per_hour cannot be negative.")
    if (df["current_ambulances"] < 0).any() or (df["minimum_ambulances_required"] < 0).any():
        raise ValueError("Ambulance counts cannot be negative.")
    if (df["priority_weight"] <= 0).any():
        raise ValueError("priority_weight must be greater than zero.")
    if not df["latitude"].between(-90, 90).all():
        raise ValueError("Latitude must be between -90 and 90.")
    if not df["longitude"].between(-180, 180).all():
        raise ValueError("Longitude must be between -180 and 180.")

    # These fields are counts, so fractional values are not valid.
    for col in ["current_ambulances", "minimum_ambulances_required"]:
        if not (df[col] % 1 == 0).all():
            raise ValueError(f"{col} must contain whole numbers.")
        df[col] = df[col].astype(int)

    return df


def marginal_benefit(row: pd.Series, assigned: int) -> float:
    """
    Heuristic score for placing one more ambulance at a depot.

    Prioritises:
    1) unmet minimum requirement,
    2) forecast demand per currently assigned ambulance,
    3) user-provided priority weight.

    The unmet-requirement bonus is intentionally large so the engine fills
    known shortages first where possible. This is a planning heuristic, not
    a calibrated estimate of lives saved or response-time improvement.
    """
    demand = float(row["predicted_calls_per_hour"])
    required = int(row["minimum_ambulances_required"])
    weight = float(row["priority_weight"])

    shortage_bonus = 100.0 if assigned < required else 0.0
    demand_per_ambulance = demand / max(assigned, 1)
    diminishing_return = demand / (assigned + 1)
    return weight * (shortage_bonus + 2.0 * demand_per_ambulance + diminishing_return)


def allocate_ambulances(df: pd.DataFrame, total_fleet: int | None = None) -> pd.DataFrame:
    """
    Allocate a fixed fleet across depots using a greedy marginal-benefit rule.

    By default, total_fleet is the sum of current_ambulances. If a different
    fleet size is supplied, the output uses exactly that number of vehicles.
    """
    result = df.copy()
    if total_fleet is None:
        total_fleet = int(result["current_ambulances"].sum())
    if total_fleet < 0:
        raise ValueError("total_fleet cannot be negative.")
    if total_fleet < 0:
        raise ValueError("total_fleet cannot be negative.")

    assigned = [0] * len(result)
    rows = [row for _, row in result.iterrows()]

    # Assign each vehicle to the depot with the highest current marginal score.
    for _ in range(total_fleet):
        scores = [marginal_benefit(row, assigned[i]) for i, row in enumerate(rows)]
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        assigned[best_idx] += 1

    result["recommended_ambulances"] = assigned
    result["change_vs_current"] = (
        result["recommended_ambulances"] - result["current_ambulances"]
    )
    result["unmet_minimum_after_allocation"] = (
        result["minimum_ambulances_required"] - result["recommended_ambulances"]
    ).clip(lower=0)
    result["above_minimum_after_allocation"] = (
        result["recommended_ambulances"] - result["minimum_ambulances_required"]
    ).clip(lower=0)

    return result.sort_values(
        ["unmet_minimum_after_allocation", "predicted_calls_per_hour"],
        ascending=[False, False],
    ).reset_index(drop=True)


def recommend_depot_for_specific_ambulance(
    allocation: pd.DataFrame,
    ambulance_id: str,
    from_depot: str | None = None,
) -> dict:
    """
    Recommend a target depot for a specific ambulance.

    The recommendation is based on the allocation engine's recommended counts.
    If from_depot is supplied, the function checks whether moving one vehicle
    from that depot would leave it below its recommended allocation.
    """
    if from_depot is not None:
        source_rows = allocation[allocation["depot_name"] == from_depot]
        if source_rows.empty:
            raise ValueError(f"Unknown source depot: {from_depot}")
        source = source_rows.iloc[0]
        if int(source["current_ambulances"]) <= 0:
            raise ValueError(f"No current ambulance is recorded at {from_depot}.")
        if int(source["current_ambulances"]) - 1 < int(source["recommended_ambulances"]):
            note = (
                f"Moving an ambulance from {from_depot} may leave that depot "
                "below its recommended allocation. Confirm operational cover first."
            )
        else:
            note = f"{from_depot} has at least one ambulance above its recommended allocation."
    else:
        note = "No source depot supplied; this is a suggested station for a newly available vehicle."

    candidates = allocation.copy()
    if from_depot is not None:
        candidates = candidates[candidates["depot_name"] != from_depot]
    if candidates.empty:
        raise ValueError("No eligible destination depot.")

    # Prefer depots with an unmet requirement; then use forecast demand and
    # shortage size as tie-breakers.
    candidates = candidates.assign(
        shortage=(
            candidates["minimum_ambulances_required"]
            - candidates["recommended_ambulances"]
        ).clip(lower=0)
    )
    candidates = candidates.sort_values(
        ["shortage", "predicted_calls_per_hour", "priority_weight"],
        ascending=[False, False, False],
    )
    best = candidates.iloc[0]
    return {
        "ambulance_id": ambulance_id,
        "recommended_depot": best["depot_name"],
        "town_or_district": best["town_or_district"],
        "predicted_calls_per_hour": float(best["predicted_calls_per_hour"]),
        "recommended_ambulances_at_depot": int(best["recommended_ambulances"]),
        "minimum_ambulances_required": int(best["minimum_ambulances_required"]),
        "reason": (
            f"Selected using forecast demand and depot requirement. "
            f"Forecast demand: {best['predicted_calls_per_hour']:.1f} calls/hour; "
            f"recommended allocation: {int(best['recommended_ambulances'])}; "
            f"stated minimum: {int(best['minimum_ambulances_required'])}."
        ),
        "operational_note": note,
    }


def save_map(allocation: pd.DataFrame, output_html: str = "ares_allocation_map.html") -> bool:
    """Save an optional Folium map. Returns False if Folium is not installed."""
    try:
        import folium
        from folium.plugins import BeautifyIcon
    except ImportError:
        print("Folium is not installed; skipping map. Install with: pip install folium")
        return False

    centre = [
        float(allocation["latitude"].mean()),
        float(allocation["longitude"].mean()),
    ]
    m = folium.Map(
    	location=[53.48, -2.24],
    	zoom_start=9,
    	tiles="OpenStreetMap"
    )
    max_change = max(1, int(allocation["change_vs_current"].abs().max()))
    for _, row in allocation.iterrows():
        change = int(row["change_vs_current"])
        if change > 0:
            colour = "red"
            movement = f"+{change} ambulance(s)"
        elif change < 0:
            colour = "blue"
            movement = f"{change} ambulance(s)"
        else:
            colour = "green"
            movement = "No change"

        popup = folium.Popup(
            f"<b>{row['depot_name']}</b><br>"
            f"District: {row['town_or_district']}<br>"
            f"Forecast calls/hour: {row['predicted_calls_per_hour']:.1f}<br>"
            f"Current ambulances: {int(row['current_ambulances'])}<br>"
            f"Recommended ambulances: {int(row['recommended_ambulances'])}<br>"
            f"Change: {movement}<br>"
            f"Minimum required: {int(row['minimum_ambulances_required'])}<br>"
            f"Unmet minimum: {int(row['unmet_minimum_after_allocation'])}",
            max_width=300,
        )
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            tooltip=f"{row['depot_name']}: {int(row['recommended_ambulances'])} recommended",
            popup=popup,
            icon=folium.Icon(color=colour, icon="plus-sign", prefix="glyphicon"),
        ).add_to(m)

    legend = """
    <div style="position: fixed; bottom: 25px; left: 25px; z-index: 9999;
                background: white; padding: 10px 12px; border: 1px solid #aaa;
                border-radius: 6px; font-size: 13px;">
      <b>A.R.E.S. allocation</b><br>
      <span style="color:red">●</span> More ambulances recommended<br>
      <span style="color:blue">●</span> Fewer ambulances recommended<br>
      <span style="color:green">●</span> No change
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    m.save(output_html)
    return True


def main():
    parser = argparse.ArgumentParser(description="A.R.E.S. depot allocation starter engine")
    parser.add_argument("--input", default="ares_greater_manchester_fake_data.csv")
    parser.add_argument("--fleet", type=int, default=None,
                        help="Total available fleet; defaults to current fleet total.")
    parser.add_argument("--output", default="ares_allocation_recommendations.csv")
    parser.add_argument("--map", default="ares_allocation_map.html",
                        help="Output HTML map; pass an empty string to skip.")
    parser.add_argument("--ambulance-id", default=None,
                        help="Optional example ID for a single-ambulance recommendation.")
    parser.add_argument("--from-depot", default=None,
                        help="Optional source depot if redeploying an existing ambulance.")
    args = parser.parse_args()

    df = load_and_validate(args.input)
    allocation = allocate_ambulances(df, args.fleet)
    allocation.to_csv(args.output, index=False)

    print("\nA.R.E.S. — Depot Allocation Recommendations")
    print("=" * 48)
    display_cols = [
        "town_or_district", "depot_name", "predicted_calls_per_hour",
        "current_ambulances", "recommended_ambulances", "change_vs_current",
        "unmet_minimum_after_allocation",
    ]
    print(allocation[display_cols].to_string(index=False))
    print(f"\nTotal fleet allocated: {int(allocation['recommended_ambulances'].sum())}")
    print(f"Recommendations saved to: {args.output}")

    if args.ambulance_id:
        recommendation = recommend_depot_for_specific_ambulance(
            allocation, args.ambulance_id, args.from_depot
        )
        print("\nSingle-ambulance recommendation")
        for key, value in recommendation.items():
            print(f"{key}: {value}")

    if args.map:
        if save_map(allocation, args.map):
            print(f"Map saved to: {args.map}")


if __name__ == "__main__":
    main()
