import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster, playergamelog
import time
import re
from datetime import datetime
import pytz  # still imported in case you want to adjust later

def normalize_name(name: str):
    return name.lower().replace(" ", "").replace(".", "")

def find_team(user_input: str):
    """Find an NBA team by flexible user input (city, nickname, abbrev, etc.)."""
    all_teams = teams.get_teams()
    user_input = normalize_name(user_input)
    for t in all_teams:
        full = normalize_name(t["full_name"])
        nick = normalize_name(t["nickname"])
        city_nick = normalize_name(t["city"] + t["nickname"])
        abbr = normalize_name(t["abbreviation"])
        if (
            user_input in full
            or user_input in nick
            or user_input in city_nick
            or user_input == abbr
        ):
            return t["id"], t["full_name"]
    return None, None

def parse_season_input(user_input: str) -> str:
    """Let user type 25 / 2025 / 2024-25 and normalize to 'YYYY-YY'."""
    user_input = user_input.strip().lower()
    current_year = datetime.now().year

    if not user_input:
        year_start = current_year if datetime.now().month >= 8 else current_year - 1
        year_end = str(year_start + 1)[2:]
        return f"{year_start}-{year_end}"

    user_input = re.sub(r"(season|the|\s)", "", user_input)
    match = re.match(r"(\d{2,4})(?:-|to)?(\d{2,4})?", user_input)
    if match:
        start = match.group(1)
        end = match.group(2)
        start = int(start[-2:]) if len(start) == 4 else int(start)
        start_full = 2000 + start if start < 50 else 1900 + start
        if end:
            end = int(end[-2:]) if len(end) == 4 else int(end)
        else:
            end = (start + 1) % 100
        return f"{start_full}-{end:02d}"

    year_start = current_year if datetime.now().month >= 8 else current_year - 1
    year_end = str(year_start + 1)[2:]
    return f"{year_start}-{year_end}"

def fetch_players(team_id):
    """Get roster for a team ID."""
    roster = commonteamroster.CommonTeamRoster(team_id=team_id)
    time.sleep(0.6)  # tiny delay to avoid hammering the API
    df = roster.get_data_frames()[0]
    return df[["PLAYER_ID", "PLAYER"]]

def fetch_game_stats(player_id, season: str):
    """Get a player's game log (points + assists + opponent + game date)."""
    try:
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star="Regular Season",
        )
        time.sleep(0.6)
        df = gamelog.get_data_frames()[0]
    except Exception as e:
        # If we hit a timeout or some other error for this player, just skip them
        print(f"     ⚠️  Skipping this player's games due to error: {e}")
        return pd.DataFrame(columns=["Game Time (PST)", "Opponent", "Points", "Assists"])

    expected_cols = [c for c in ["GAME_DATE", "MATCHUP", "PTS", "AST"] if c in df.columns]
    if not expected_cols or "PTS" not in df.columns:
        return pd.DataFrame(columns=["Game Time (PST)", "Opponent", "Points", "Assists"])

    df = df[expected_cols].rename(columns={"GAME_DATE": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # NOTE: PlayerGameLog only gives dates, not real tip-off times.
    # We format the date into a single "Game Time (PST)" column for consistency.
    df["Game Time (PST)"] = df["Date"].dt.strftime("%Y-%m-%d")

    df["Opponent"] = df["MATCHUP"].apply(lambda x: x.split(" ")[-1] if isinstance(x, str) else "")
    df = df.rename(columns={"PTS": "Points", "AST": "Assists"})

    return df[["Game Time (PST)", "Opponent", "Points", "Assists"]].sort_values("Game Time (PST)")

def export_team_from_object(team_obj: dict, season: str):
    """Export one team's points/assists stats to an Excel file."""
    team_id = team_obj["id"]
    team_name = team_obj["full_name"]
    print(f"\n✅ Team: {team_name} | Season: {season}")
    print("Fetching player stats... this might take a minute ⏳")

    try:
        players_df = fetch_players(team_id)
    except Exception as e:
        print(f"  ⚠️  Could not fetch roster for {team_name}: {e}")
        return

    combined_points = None
    combined_assists = None
    avg_points = []
    avg_assists = []

    for _, row in players_df.iterrows():
        pid = row["PLAYER_ID"]
        pname = row["PLAYER"]
        print(f"  → Fetching {pname}...")
        games = fetch_game_stats(pid, season)
        if games.empty:
            continue

        # Points
        p_df = games[["Game Time (PST)", "Opponent", "Points"]].rename(columns={"Points": pname})
        if combined_points is None:
            combined_points = p_df
        else:
            combined_points = pd.merge(
                combined_points,
                p_df,
                on=["Game Time (PST)", "Opponent"],
                how="outer",
            )

        # Assists
        a_df = games[["Game Time (PST)", "Opponent", "Assists"]].rename(columns={"Assists": pname})
        if combined_assists is None:
            combined_assists = a_df
        else:
            combined_assists = pd.merge(
                combined_assists,
                a_df,
                on=["Game Time (PST)", "Opponent"],
                how="outer",
            )

        avg_points.append({"Player": pname, "Avg Points": games["Points"].mean()})
        avg_assists.append({"Player": pname, "Avg Assists": games["Assists"].mean()})

    if combined_points is None or combined_points.empty:
        print(f"  ⚠️  No game data found for {team_name} in season {season}. Skipping file.")
        return

    combined_points = combined_points.sort_values("Game Time (PST)").fillna(0)
    combined_assists = combined_assists.sort_values("Game Time (PST)").fillna(0)

    avg_points_df = pd.DataFrame(avg_points).sort_values("Avg Points", ascending=False)
    avg_assists_df = pd.DataFrame(avg_assists).sort_values("Avg Assists", ascending=False)

    file_name = f"{team_name.replace(' ', '_')}_{season}_stats.xlsx"
    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        combined_points.to_excel(writer, sheet_name="Points", index=False)
        combined_assists.to_excel(writer, sheet_name="Assists", index=False)
        avg_points_df.to_excel(writer, sheet_name="Avg Points", index=False)
        avg_assists_df.to_excel(writer, sheet_name="Avg Assists", index=False)

    print(f"  💾 Saved '{file_name}'")

def main():
    print("🏀 NBA Tracker – Points, Assists, Opponents & Game Time")
    mode = input("Download data for one team or all teams? (one/all): ").strip().lower()
    raw_season = input("Which season? (e.g., 2024-25 or 2025 or 25): ")
    season = parse_season_input(raw_season)

    if mode == "all":
        all_teams = teams.get_teams()
        print(f"\nDownloading stats for all {len(all_teams)} NBA teams...")
        for team in all_teams:
            try:
                export_team_from_object(team, season)
            except Exception as e:
                print(f"  ⚠️  Skipping {team['full_name']} because of an error: {e}")
    else:
        user_team = input("Which team do you want? (e.g., Lakers, LAL, Los Angeles Lakers): ").strip()
        team_id, team_name = find_team(user_team)
        if not team_id:
            print("❌ Couldn't find that team. Try again with a different name or abbreviation.")
            return
        export_team_from_object({"id": team_id, "full_name": team_name}, season)

    print("\n🏁 Done! All requested team data processed.")

if __name__ == "__main__":
    main()
