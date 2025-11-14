"""
College Basketball (NCAAB) version of your NBA tracker.

Requirements:
    pip install pandas openpyxl sportsipy

This script:
  • Asks for season (e.g. 2024-25 or 2025 or 25)
  • Lets you pick ONE team or ALL teams
  • For each team, creates an Excel file with sheets:
        - Points   (game-by-game, players as columns)
        - Assists
        - Rebounds
        - 3PM
        - Avg Points
        - Avg Assists
        - Avg Rebounds
        - Avg 3PM
        - Team Points (team score, opponent score, total)
"""

import time
import re
from datetime import datetime
import difflib

import pandas as pd
from sportsipy.ncaab.teams import Teams
from sportsipy.ncaab.schedule import Schedule  # noqa: F401  (used via team.schedule)


def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "").replace(".", "")


def parse_season_input(user_input: str):
    """
    Parse user season input for college hoops.

    Returns:
        season_label: 'YYYY-YY' style string, e.g. '2024-25'
        year_end:     'YYYY' string for sportsipy (season ends in this year)
    """
    user_input = (user_input or "").strip().lower()
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # Default: guess current NCAAB season based on date
    if not user_input:
        # If we're in Jul–Dec, assume upcoming season ending next year
        # If we're in Jan–Jun, assume current season ending this year
        year_end = current_year + 1 if current_month >= 7 else current_year
        year_start = year_end - 1
        return f"{year_start}-{str(year_end)[2:]}", str(year_end)

    user_input = re.sub(r"(season|the|\s)", "", user_input)
    match = re.match(r"(\d{2,4})(?:-|to)?(\d{2,4})?", user_input)
    if match:
        first = match.group(1)
        second = match.group(2)

        def to_year(val: str) -> int:
            v = int(val)
            if len(val) == 4:
                return v
            return 2000 + v if v < 50 else 1900 + v

        if second:
            # Range like 2024-25 or 2017-2018
            year_end_full = to_year(second)
        else:
            # Single year like 2025 or 25 -> treat as year the season ENDS
            year_end_full = to_year(first)

        year_start_full = year_end_full - 1
        season_label = f"{year_start_full}-{str(year_end_full)[2:]}"
        return season_label, str(year_end_full)

    # Fallback if parsing failed
    year_end = current_year + 1 if current_month >= 7 else current_year
    year_start = year_end - 1
    return f"{year_start}-{str(year_end)[2:]}", str(year_end)


def find_team(user_input: str, teams_list):
    """Find a college team by flexible input (full name or abbreviation)."""
    target = normalize_name(user_input)
    for t in teams_list:
        name_norm = normalize_name(getattr(t, "name", ""))
        abbr_norm = normalize_name(getattr(t, "abbreviation", ""))
        if target == abbr_norm or target == name_norm or target in name_norm:
            return t
    return None


def suggest_teams(user_input: str, teams_list, n=10):
    """Return a list of close team-name matches for user input."""
    labels = [getattr(t, "name", "") for t in teams_list]
    suggestions = difflib.get_close_matches(user_input, labels, n=n, cutoff=0.4)
    return suggestions


def build_team_dataframes(team, season_label: str):
    """
    For a given Team instance, build:
      - long_df : per-player, per-game stats (Points, Assists, Rebounds, 3PM)
      - team_points_df : team vs opponent points per game
    """
    print(f"\n✅ Team: {team.name} | Season: {season_label}")
    print("Fetching schedule and boxscores... this might take a bit ⏳")

    long_records = []
    team_points_records = []

    # Team schedule for that season
    schedule = team.schedule

    for game in schedule:
        # Basic game info
        dt_obj = getattr(game, "datetime", None)
        if isinstance(dt_obj, datetime):
            game_date_str = dt_obj.strftime("%Y-%m-%d")
        else:
            date_str = getattr(game, "date", None)
            if isinstance(date_str, str):
                # Example format: "Fri, Nov 10, 2017"
                try:
                    parsed = datetime.strptime(date_str, "%a, %b %d, %Y")
                    game_date_str = parsed.strftime("%Y-%m-%d")
                except ValueError:
                    game_date_str = date_str
            else:
                game_date_str = ""

        opponent_name = getattr(game, "opponent_name", None) or getattr(
            game, "opponent_abbr", ""
        )
        points_for = getattr(game, "points_for", 0) or 0
        points_against = getattr(game, "points_against", 0) or 0

        # Team level record
        team_points_records.append(
            {
                "Game Date": game_date_str,
                "Opponent": opponent_name,
                "Team Points": points_for,
                "Opponent Points": points_against,
                "Game Total Points": points_for + points_against,
            }
        )

        # Boxscore – player level stats
        try:
            boxscore = game.boxscore
        except Exception as e:
            print(f"   ⚠️  Skipping boxscore for {game.date} due to error: {e}")
            continue

        # Be nice to sports-reference servers
        time.sleep(0.6)

        team_abbr = team.abbreviation.upper()
        home_abbr = getattr(boxscore, "home_abbreviation", "").upper()
        away_abbr = getattr(boxscore, "away_abbreviation", "").upper()

        if home_abbr == team_abbr:
            players_list = getattr(boxscore, "home_players", []) or []
        elif away_abbr == team_abbr:
            players_list = getattr(boxscore, "away_players", []) or []
        else:
            # Fallback if we somehow can't match, skip player stats for this game
            players_list = []

        for p in players_list:
            name = getattr(p, "name", "Unknown Player")
            pts = getattr(p, "points", 0) or 0
            ast = getattr(p, "assists", 0) or 0
            reb = getattr(p, "total_rebounds", 0) or 0
            three = getattr(p, "three_pointers", 0) or 0

            long_records.append(
                {
                    "Game Date": game_date_str,
                    "Opponent": opponent_name,
                    "Player": name,
                    "Points": pts,
                    "Assists": ast,
                    "Rebounds": reb,
                    "3PM": three,
                }
            )

    long_df = pd.DataFrame(long_records)
    team_points_df = pd.DataFrame(team_points_records).sort_values("Game Date")

    return long_df, team_points_df


def export_team(team, season_label: str):
    """Build all dataframes for a team and export them to an Excel file."""
    long_df, team_points_df = build_team_dataframes(team, season_label)

    if long_df.empty:
        print(f"   ⚠️  No player game data found for {team.name} in {season_label}. Skipping file.")
        return

    # Pivot to wide format: rows = games, columns = players
    def make_pivot(stat: str):
        pivot = (
            long_df.pivot_table(
                index=["Game Date", "Opponent"],
                columns="Player",
                values=stat,
                aggfunc="sum",
            )
            .reset_index()
            .sort_values("Game Date")
            .fillna(0)
        )
        pivot.columns.name = None
        return pivot

    combined_points = make_pivot("Points")
    combined_assists = make_pivot("Assists")
    combined_rebounds = make_pivot("Rebounds")
    combined_3pm = make_pivot("3PM")

    # Per-player season averages
    avg_points_df = (
        long_df.groupby("Player", as_index=False)["Points"]
        .mean()
        .rename(columns={"Points": "Avg Points"})
        .sort_values("Avg Points", ascending=False)
    )
    avg_assists_df = (
        long_df.groupby("Player", as_index=False)["Assists"]
        .mean()
        .rename(columns={"Assists": "Avg Assists"})
        .sort_values("Avg Assists", ascending=False)
    )
    avg_rebounds_df = (
        long_df.groupby("Player", as_index=False)["Rebounds"]
        .mean()
        .rename(columns={"Rebounds": "Avg Rebounds"})
        .sort_values("Avg Rebounds", ascending=False)
    )
    avg_3pm_df = (
        long_df.groupby("Player", as_index=False)["3PM"]
        .mean()
        .rename(columns={"3PM": "Avg 3PM"})
        .sort_values("Avg 3PM", ascending=False)
    )

    file_name = f"{team.name.replace(' ', '_')}_{season_label}_ncaab_stats.xlsx"

    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        combined_points.to_excel(writer, sheet_name="Points", index=False)
        combined_assists.to_excel(writer, sheet_name="Assists", index=False)
        combined_rebounds.to_excel(writer, sheet_name="Rebounds", index=False)
        combined_3pm.to_excel(writer, sheet_name="3PM", index=False)
        avg_points_df.to_excel(writer, sheet_name="Avg Points", index=False)
        avg_assists_df.to_excel(writer, sheet_name="Avg Assists", index=False)
        avg_rebounds_df.to_excel(writer, sheet_name="Avg Rebounds", index=False)
        avg_3pm_df.to_excel(writer, sheet_name="Avg 3PM", index=False)

        if not team_points_df.empty:
            team_points_df.to_excel(writer, sheet_name="Team Points", index=False)

    print(f"   💾 Saved '{file_name}'")


def main():
    print("🏀 NCAAB Tracker – Points, Assists, Rebounds, 3PM, Team & Game Totals")
    mode = input("Download data for one team or all teams? (one/all): ").strip().lower()
    raw_season = input("Which season? (e.g., 2024-25 or 2025 or 25): ")

    season_label, year_end = parse_season_input(raw_season)
    print(f"\nUsing season: {season_label} (sportsipy year: {year_end})")

    try:
        all_teams = list(Teams(year=year_end))
    except Exception as e:
        print(f"❌ Could not load NCAAB teams for year {year_end}: {e}")
        print("   This usually means that season data is not available yet on sports-reference.")
        return

    if not all_teams:
        print(f"❌ No NCAAB teams were found for year {year_end}.")
        print("   The season might not be available yet on sports-reference. Try an earlier season (e.g. 2024, 2023).")
        return

    print(f"\nLoaded {len(all_teams)} teams for that season.")
    print("Example team names you can type:")
    for example in all_teams[:10]:
        print(f"   • {example.name}  ({example.abbreviation})")

    if mode == "all":
        print(f"\nDownloading stats for all {len(all_teams)} NCAAB teams...")
        for team in all_teams:
            try:
                export_team(team, season_label)
            except Exception as e:
                print(f"  ⚠️  Skipping {team.name} because of an error: {e}")
    else:
        user_team = input(
            "Which college team do you want? (e.g., Duke, PURDUE, Gonzaga Bulldogs): "
        ).strip()
        team = find_team(user_team, all_teams)
        if not team:
            print("❌ Couldn't find that team for this season.")
            suggestions = suggest_teams(user_team, all_teams)
            if suggestions:
                print("   Did you mean:")
                for s in suggestions:
                    print(f"     • {s}")
            else:
                print("   No close matches found. Try using the exact school name from the examples above.")
            return

        export_team(team, season_label)

    print("\n🏁 Done! All requested team data processed.")


if __name__ == "__main__":
    main()
