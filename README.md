# Olympic Medal Leaderboard Reporter

Python submission for the **Repo Execution Agent** — Claude Olympics Ignition Round.

---

## Repository Structure

```
├── agent_config.json     # Required — type, entry, run_command, runtime_version
├── olympics.json         # Required — tool contract (challenge_id, entrypoint, outputs)
├── medal_report.py       # Tool entry point
├── requirements.txt      # Python dependencies
├── env_vars.json         # Non-sensitive config
├── olympic_medals.csv    # Practice dataset
└── population_reference.csv  # Population data for per-capita analysis
```

---

## Output Contract

The script produces a `leaderboard.csv` file:

```
country_code,medals
USA,549
CHN,476
...
```

---

## Testing Locally

```bash
pip install -r requirements.txt
python medal_report.py olympic_medals.csv
cat leaderboard.csv
```

---

## What It Does

1. Loads and cleans the Olympic medals dataset (deduplication, medal normalization, country code resolution)
2. Computes a medal leaderboard counting one medal per (year, country, event, medal-type) — avoids inflating team sports
3. Writes `leaderboard.csv` in the required output format
4. Generates a bar chart (`leaderboard.png`) of the top 10 nations
5. Performs team-sport inflation analysis
6. Computes per-capita medal rankings
