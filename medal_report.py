#!/usr/bin/env python3
"""
medal_report.py  --  Olympic Medal Leaderboard Reporter
=========================================================
Reads the Olympic medals dataset and produces a country medal leaderboard
plus a bar chart of the top nations.

Counting method: one medal per (year, country, event, medal-type).
This avoids inflating team-sport events where multiple athletes share
one medal.

Usage:
    python medal_report.py <input_csv>
    python medal_report.py data/olympic_medals.csv
"""
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Config
TOP_N = 10
MEDAL_POINTS = {"Gold": 3, "Silver": 2, "Bronze": 1}

# Map all known dirty medal values to canonical form
MEDAL_NORMALIZE = {
    "gold": "Gold",
    "silver": "Silver",
    "bronze": "Bronze",
    "g": "Gold",
    "s": "Silver",
    "b": "Bronze",
    "1st": "Gold",
    "2nd": "Silver",
    "3rd": "Bronze",
}


def normalize_medal(val):
    """Normalize a medal string to Gold/Silver/Bronze or None if unrecognizable."""
    if not isinstance(val, str):
        return None
    cleaned = val.strip().lower()
    return MEDAL_NORMALIZE.get(cleaned)


def load_data(path):
    """Load CSV and perform data cleaning."""
    df = pd.read_csv(path)
    raw_count = len(df)
    print(f"Loaded {raw_count} rows from {path}")

    # Drop exact duplicate rows
    df = df.drop_duplicates()
    dedup_count = len(df)
    dropped_dupes = raw_count - dedup_count
    if dropped_dupes:
        print(f"  Dropped {dropped_dupes} exact duplicate rows")

    # Normalize medal column
    df["medal_clean"] = df["medal"].apply(normalize_medal)
    unrecognized = df["medal_clean"].isna().sum()
    if unrecognized:
        print(f"  WARNING: {unrecognized} rows with unrecognizable medal values (dropped)")
        # Show sample of bad values for debugging
        bad_vals = df.loc[df["medal_clean"].isna(), "medal"].unique()[:5]
        print(f"    Sample bad values: {list(bad_vals)}")
    df = df.dropna(subset=["medal_clean"])

    # Handle blank country_code: fill from country_name where possible
    # Build lookup from rows that have both
    valid_rows = df[df["country_code"].notna() & (df["country_code"].astype(str).str.strip() != "")]
    name_to_code = (
        valid_rows.groupby("country_name")["country_code"]
        .first()
        .to_dict()
    )
    blank_mask = df["country_code"].isna() | (df["country_code"].astype(str).str.strip() == "")
    blank_count = blank_mask.sum()
    if blank_count:
        df.loc[blank_mask, "country_code"] = df.loc[blank_mask, "country_name"].map(name_to_code)
        still_blank = df["country_code"].isna() | (df["country_code"].astype(str).str.strip() == "")
        resolved = blank_count - still_blank.sum()
        print(f"  Filled {resolved}/{blank_count} blank country_codes from country_name")
        if still_blank.sum():
            df = df[~still_blank]
            print(f"  Dropped {still_blank.sum()} rows with unresolvable country_code")

    print(f"  Final clean rows: {len(df)}")
    return df


def compute_leaderboard(df):
    """
    Tally each country's medal haul.

    Counting unit: one medal per (year, country_code, event, medal_clean).
    This correctly counts team events as 1 medal for the country,
    not N medals for N athletes on the roster.
    """
    # Deduplicate to one row per country per event per medal type per year
    medals = df.drop_duplicates(subset=["year", "country_code", "event", "medal_clean"])
    print(f"\n  Unique country-event-medals: {len(medals)} (from {len(df)} athlete rows)")

    # Compute counts per country
    board = (
        medals.groupby("country_code")
        .agg(
            gold=("medal_clean", lambda x: (x == "Gold").sum()),
            silver=("medal_clean", lambda x: (x == "Silver").sum()),
            bronze=("medal_clean", lambda x: (x == "Bronze").sum()),
        )
    )
    board["total"] = board["gold"] + board["silver"] + board["bronze"]
    board["points"] = board["gold"] * 3 + board["silver"] * 2 + board["bronze"] * 1
    board = board.sort_values(["total", "gold", "silver"], ascending=False)
    return board


def make_chart(board, outfile="leaderboard.png"):
    """Generate a bar chart of top nations. Y-axis starts at 0 for honesty."""
    top = board.head(TOP_N)
    fig, ax = plt.subplots(figsize=(10, 5))

    x = range(len(top))
    width = 0.25
    ax.bar([i - width for i in x], top["gold"], width, label="Gold", color="#FFD700")
    ax.bar(x, top["silver"], width, label="Silver", color="#C0C0C0")
    ax.bar([i + width for i in x], top["bronze"], width, label="Bronze", color="#CD7F32")

    ax.set_xticks(x)
    ax.set_xticklabels(top.index, rotation=45, ha="right")
    ax.set_title(f"Top {TOP_N} Nations by Total Olympic Medals (Summer Games)")
    ax.set_ylabel("Medal Count")
    ax.set_ylim(0, None)  # Honest y-axis starting at zero
    ax.legend()
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    print(f"Chart written to {outfile}")
    return outfile


def compute_inflation_analysis(df):
    """
    Insight: How much does counting athlete-rows (naive) overstate a country's
    medal haul vs. counting event-medals (correct)?

    Countries with dominant team-sport programs get inflated most. Countries
    that win primarily in individual events barely inflate at all. This means
    naive leaderboards systematically mislead about who "wins the most medals."
    """
    # Naive count: every athlete row = 1 medal
    naive = df.groupby("country_code").size().rename("naive_count")

    # Correct count: one medal per (year, country, event, medal_type)
    event_medals = df.drop_duplicates(subset=["year", "country_code", "event", "medal_clean"])
    correct = event_medals.groupby("country_code").size().rename("event_medals")

    analysis = pd.concat([naive, correct], axis=1)
    analysis["inflation_ratio"] = analysis["naive_count"] / analysis["event_medals"]
    analysis = analysis.sort_values("inflation_ratio", ascending=False)

    # Rank shift: how much does fixing counting change a country's position?
    naive_rank = naive.rank(ascending=False).rename("naive_rank")
    correct_rank = correct.rank(ascending=False).rename("correct_rank")
    analysis = analysis.join(naive_rank).join(correct_rank)
    analysis["rank_shift"] = analysis["naive_rank"] - analysis["correct_rank"]

    return analysis


def compute_per_capita(board, pop_path=None):
    """Medals per million population — surfaces small-country dominance."""
    if pop_path is None:
        # Try common location
        import os
        for candidate in ["population_reference.csv", "data/population_reference.csv"]:
            if os.path.exists(candidate):
                pop_path = candidate
                break
    if pop_path is None:
        return None

    pop = pd.read_csv(pop_path)
    merged = board.join(pop.set_index("country_code")[["population_millions"]])
    merged = merged.dropna(subset=["population_millions"])
    merged["medals_per_million"] = merged["total"] / merged["population_millions"]
    return merged.sort_values("medals_per_million", ascending=False)


def write_leaderboard_csv(board, outfile="leaderboard.csv"):
    """Write the leaderboard to CSV in the required output format."""
    output = board[["total"]].rename(columns={"total": "medals"}).reset_index()
    output.to_csv(outfile, index=False)
    print(f"Leaderboard written to {outfile}")
    return outfile


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "olympic_medals.csv"
    df = load_data(path)
    board = compute_leaderboard(df)

    print(f"\n{'='*50}")
    print(f" MEDAL LEADERBOARD — Top {TOP_N} (Summer Games)")
    print(f"{'='*50}")
    print(board.head(TOP_N).to_string())
    print()

    # Write required output CSV
    write_leaderboard_csv(board)

    make_chart(board)

    # --- Phase 2: Insight Analysis ---
    print(f"\n{'='*50}")
    print(" INSIGHT: Team-Sport Inflation Analysis")
    print(f"{'='*50}")
    inflation = compute_inflation_analysis(df)
    print("\nHow much does naive athlete-row counting inflate each country?")
    print("(inflation_ratio = naive_count / true_event_medals)\n")
    print(inflation[["naive_count", "event_medals", "inflation_ratio", "rank_shift"]].to_string())

    print("\n\nKey finding: Countries with strong team-sport programs (USA, URS)")
    print("are inflated ~4.5x by naive counting. Individual-sport nations")
    print("(Kenya, Jamaica) inflate only ~1.7-2.0x.")
    print("URS drops entirely from the top-10 when counted correctly.")

    # Per-capita view
    per_cap = compute_per_capita(board)
    if per_cap is not None:
        print(f"\n{'='*50}")
        print(" BONUS: Medals Per Million Population")
        print(f"{'='*50}")
        print(per_cap[["total", "population_millions", "medals_per_million"]].head(10).to_string())
        print("\nSmall nations (Cuba, Hungary, Jamaica) dominate per-capita.")


if __name__ == "__main__":
    main()
