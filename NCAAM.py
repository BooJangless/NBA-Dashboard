"""
NCAAM version of your NBA tracker using CollegeBasketballData.com (CBBD).

BEFORE RUNNING:
    pip install cbbd pandas openpyxl

What this script does:
  • Asks for season (e.g. 2025-26 or 2025 or 25)
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
import difflib
from datetime import datetime

import pandas as pd
import cbbd


# <<<--- YOUR API KEY --->>>
API_KEY = "ibFY+KKStwXjrU9hb9z1nBJBAeFu3s6Rmnekyps/MdAoiSXZu7YA5nTHOuO2o0UK"


# ----------------- Helpers ----------------- #

def normalize_name(name: str) -> str:
    return (name or "").lower().replace(" ", "").replace(".", "")


def parse_season_input(user_input: str):
    """
    Parse user season input for CBB.

    Examples:
      '25'      -> season_int = 2025, label = '2025-26'
      '2025'    -> season_int = 2025, label = '2025-26'
      '2024-25' -> season_int = 2024, label = '2024-25'
      ''        -> current season based on today's date
    """
    user_input = (user_input or "").strip().lower()
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # Default: guess current CBB season based on date
    if not user_input:
        if current_month >= 7:
            start_full = current_year
        else:
            start_full = current_year - 1
        end_full = start_full + 1
        return start_full, f"{start_full}-{str(end_full)[2:]}"

    user_input = re.sub(r"(season|the|\s)", "", user_input)
    match = re.match(r"(\d{2,4})(?:-|to)?(\d{2,4})?", user_input)
    if match:
        first = match.group(1)
        second = match.group(2)

        def to_year_start(val: str) -> int:
            v = int(val)
            if len(val) == 4:
                return v
            # 2-digit years -> 2000s for modern seasons
            return 2000 + v if v < 50 else 1900 + v

        start_full = to_year_start(first)

        if second:
            v = int(second)
            if len(second) == 4:
                end_full = v
            else:
                end_full = 2000 + v if v < 50 else 1900 + v
        else:
            end_full = start_full + 1

        return start_full, f"{start_full}-{str(end_full)[2:]}"

    # Fallback: same as default logic
    if current_month >= 7:
        start_full = current_year
    else:
        start_full = current_year - 1
    end_full = start_full + 1
    return start_full, f"{start_full}-{str(end_full)[2:]}"


def team_display_name(team_obj):
    return (
        getattr(team_obj, "team", None)
        or getattr(team_obj, "name", None)
        or getattr(team_obj, "school", None)
        or ""
    )


def team_abbreviation(team_obj):
    return getattr(team_obj, "abbreviation", None) or ""


def find_team(user_input: str, teams_list):
    """Find a college team by flexible input (full name, part of name, or abbreviation)."""
    target = normalize_name(user_input)
    for t in teams_list:
        name = team_display_name(t)
        abbr = team_abbreviation(t)
        name_norm = normalize_name(name)
        abbr_norm = normalize_name(abbr)
        if target == abbr_norm or target == name_norm or target in name_norm:
            return t
    return None


def suggest_teams(user_input: str, teams_list, n=10):
    """Return a list of close team-name matches for user input."""
    labels = [team_display_name(t) for t in teams_list]
    suggestions = difflib.get_close_matches(user_input, labels, n=n, cutoff=0.4)
    return suggestions


# ----------------- Core data fetch ----------------- #

def fetch_player_games_for_team(api_client, team_name: str, season_int: int):
    """
    Use GamesApi.get_game_players to pull player box scores for a team & season.
    Returns a long-format list of dicts:
      {Game Time (PST), Opponent, Player, Points, Assists, Rebounds, 3PM}
    """
    games_api = cbbd.GamesApi(api_client)

    print(f"\nFetching player box scores for {team_name} in {season_int}...")
    try:
        boxes = games_api.get_game_players(season=season_int, team=team_name)
    except Exception as e:
        print(f"   ⚠️ Error from get_game_players: {e}")
        return []

    records = []

    for gb in boxes or []:
        # Game date
        dt = getattr(gb, "game_start_date", None) or getattr(gb, "start_date", None)
        if isinstance(dt, datetime):
            game_date_str = dt.date().isoformat()
        else:
            game_date_str = str(dt) if dt is not None else ""

        home_team = getattr(gb, "home_team", "")
        away_team = getattr(gb, "away_team", "")

        if home_team == team_name:
            opponent = away_team
        elif away_team == team_name:
            opponent = home_team
        else:
            opponent = getattr(gb, "opponent", "") or ""

        players_list = getattr(gb, "players", []) or []

        for p in players_list:
            name = getattr(p, "name", None) or getattr(p, "player", None) or "Unknown Player"

            # Points
            pts = getattr(p, "points", None)
            if pts is None:
                pts = getattr(p, "pts", 0)
            pts = pts or 0

            # Assists
            ast = getattr(p, "assists", None)
            if ast is None:
                ast = getattr(p, "ast", 0)
            ast = ast or 0

            # Rebounds – may sometimes be an object, so we try to pull a numeric field
            reb = getattr(p, "total_rebounds", None)
            if reb is None:
                reb = getattr(p, "rebounds", None)
            # If it's still not a plain number, try to pull ".total", otherwise 0
            if not isinstance(reb, (int, float)):
                maybe_total = getattr(reb, "total", None)
                reb = maybe_total if isinstance(maybe_total, (int, float)) else 0
            reb = reb or 0

            # 3PM – may also occasionally be an object; treat similarly
            three = getattr(p, "three_pointers_made", None)
            if three is None:
                three = getattr(p, "three_pointers", None)
            if not isinstance(three, (int, float)):
                maybe_total = getattr(three, "total", None)
                three = maybe_total if isinstance(maybe_total, (int, float)) else 0
            three = three or 0

            records.append(
                {
                    "Game Time (PST)": game_date_str,
                    "Opponent": opponent,
                    "Player": name,
                    "Points": pts,
                    "Assists": ast,
                    "Rebounds": reb,
                    "3PM": three,
                }
            )

    return records


def fetch_team_points_for_team(api_client, team_name: str, season_int: int):
    """
    Use GamesApi.get_games to get team points, opponent points, and game total
    for each game this team plays in the given season.
    """
    games_api = cbbd.GamesApi(api_client)

    print(f"Fetching team game results for {team_name} in {season_int}...")
    try:
        games = games_api.get_games(season=season_int, team=team_name)
    except Exception as e:
        print(f"   ⚠️ Error from get_games: {e}")
        return pd.DataFrame(columns=["Game Time (PST)", "Opponent", "Team Points", "Opponent Points", "Game Total Points"])

    rows = []

    for g in games or []:
        dt = getattr(g, "game_start_date", None) or getattr(g, "start_date", None)
        if isinstance(dt, datetime):
            date_str = dt.date().isoformat()
        else:
            date_str = str(dt) if dt is not None else ""

        home_team = getattr(g, "home_team", "")
        away_team = getattr(g, "away_team", "")

        home_score = getattr(g, "home_score", None)
        if home_score is None:
            home_score = getattr(g, "home_points", 0)
        home_score = home_score or 0

        away_score = getattr(g, "away_score", None)
        if away_score is None:
            away_score = getattr(g, "away_points", 0)
        away_score = away_score or 0

        if home_team == team_name:
            team_points = home_score
            opp_points = away_score
            opponent = away_team
        elif away_team == team_name:
            team_points = away_score
            opp_points = home_score
            opponent = home_team
        else:
            continue

        rows.append(
            {
                "Game Time (PST)": date_str,
                "Opponent": opponent,
                "Team Points": team_points,
                "Opponent Points": opp_points,
                "Game Total Points": team_points + opp_points,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["Game Time (PST)", "Opponent", "Team Points", "Opponent Points", "Game Total Points"])

    df = pd.DataFrame(rows).sort_values("Game Time (PST)")
    return df


# ----------------- Export logic ----------------- #

def export_team(api_client, team_name: str, season_int: int, season_label: str):
    """Fetch everything for one team and export to Excel."""
    print(f"\n✅ Team: {team_name} | Season: {season_label}")

    # Player game logs
    long_records = fetch_player_games_for_team(api_client, team_name, season_int)
    if not long_records:
        print(f"   ⚠️ No player game data found for {team_name} in {season_label}. Skipping file.")
        return

    long_df = pd.DataFrame(long_records)

    # Make sure all stat columns are numeric (fixes the Rebounds object error)
    for col in ["Points", "Assists", "Rebounds", "3PM"]:
        long_df[col] = pd.to_numeric(long_df[col], errors="coerce").fillna(0)

    # Pivot to wide format: rows = games, columns = players
    def make_pivot(stat: str):
        pivot = (
            long_df.pivot_table(
                index=["Game Time (PST)", "Opponent"],
                columns="Player",
                values=stat,
                aggfunc="sum",
            )
            .reset_index()
            .sort_values("Game Time (PST)")
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

    # Team game results
    team_points_df = fetch_team_points_for_team(api_client, team_name, season_int)

    file_name = f"{team_name.replace(' ', '_')}_{season_label}_ncaam_stats.xlsx"

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


# ----------------- Main ----------------- #

def main():
    print("🏀 NCAAM Tracker – Points, Assists, Rebounds, 3PM, Team & Game Totals")

    # Mode: one or all
    while True:
        mode = input("Download data for one team or all teams? (one/all): ").strip().lower()
        if mode in {"one", "all"}:
            break
        print("Please type 'one' or 'all'.")

    raw_season = input("Which season? (e.g., 2025-26 or 2025 or 25): ")
    season_int, season_label = parse_season_input(raw_season)
    print(f"\nUsing season: {season_label} (CBBD season param: {season_int})")

    # Configure CBBD
    configuration = cbbd.Configuration(access_token=API_KEY)

    with cbbd.ApiClient(configuration) as api_client:
        teams_api = cbbd.TeamsApi(api_client)

        # Load teams for that season
        try:
            teams_list = teams_api.get_teams(season=season_int)
        except Exception as e:
            print(f"❌ Could not load NCAAM teams for season {season_int}: {e}")
            return

        if not teams_list:
            print(f"❌ No NCAAM teams were found for season {season_int}.")
            return

        print(f"\nLoaded {len(teams_list)} teams for that season.")
        print("Example team names you can type (name / abbreviation):")
        for example in teams_list[:10]:
            print(f"   • {team_display_name(example)}  ({team_abbreviation(example)})")

        if mode == "all":
            print(f"\nDownloading stats for all {len(teams_list)} NCAAM teams...")
            for t in teams_list:
                name = team_display_name(t)
                if not name:
                    continue
                try:
                    export_team(api_client, name, season_int, season_label)
                except Exception as e:
                    print(f"  ⚠️  Skipping {name} because of an error: {e}")
                    time.sleep(0.5)
        else:
            # ONE TEAM – interactive, with suggestions and retries
            while True:
                user_team = input(
                    "\nWhich college team do you want?\n"
                    "(e.g., Duke, Dayton, Gonzaga)\n"
                    "Type team name or abbreviation (or 'list' to see more examples): "
                ).strip()

                if not user_team:
                    print("Please enter a team name or abbreviation.")
                    continue

                if user_team.lower() == "list":
                    print("\nSome more example teams:")
                    for example in teams_list[:30]:
                        print(f"   • {team_display_name(example)}  ({team_abbreviation(example)})")
                    continue

                t = find_team(user_team, teams_list)
                if t:
                    name = team_display_name(t)
                    export_team(api_client, name, season_int, season_label)
                    break

                print("\n❌ Couldn't find that team for this season.")
                suggestions = suggest_teams(user_team, teams_list)
                if suggestions:
                    print("   Did you mean:")
                    for s in suggestions:
                        print(f"     • {s}")
                else:
                    print("   No close matches found. Try using the exact school name or abbreviation shown above.")

                retry = input("Try another team name? (y/n): ").strip().lower()
                if retry != "y":
                    break

    print("\n🏁 Done! All requested team data processed.")


if __name__ == "__main__":
    main()
