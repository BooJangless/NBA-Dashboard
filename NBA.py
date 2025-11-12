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
    """Get a player's game log (points, assists, rebounds, 3PM, opponent, game date)."""
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
        return pd.DataFrame(columns=["Game Time (PST)", "Opponent", "Points", "Assists", "Rebounds", "3PM"])

    needed = {"GAME_DATE", "MATCHUP", "PTS", "AST", "REB", "FG3M"}
    present = needed.intersection(df.columns)
    # Require at least PTS to consider this valid; fill missing others with 0
    if "PTS" not in present or "GAME_DATE" not in present or "MATCHUP" not in present:
        return pd.DataFrame(columns=["Game Time (PST)", "Opponent", "Points", "Assists", "Rebounds", "3PM"])

    # Keep only the columns we can map; fill missing metric cols with 0
    out = df[list(present)].rename(columns={"GAME_DATE": "Date"})
    # Add missing stat columns with zeros if not present (defensive coding)
    for col_src, col_dst in [("AST", "Assists"), ("REB", "Rebounds"), ("FG3M", "3PM"), ("PTS", "Points")]:
        if col_src not in out.columns:
            out[col_src] = 0

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["Game Time (PST)"] = out["Date"].dt.strftime("%Y-%m-%d")
    out["Opponent"] = out["MATCHUP"].apply(lambda x: x.split(" ")[-1] if isinstance(x, str) else "")

    out = out.rename(columns={"PTS": "Points", "AST": "Assists", "REB": "Rebounds", "FG3M": "3PM"})
    return out[["Game Time (PST)", "Opponent", "Points", "Assists", "Rebounds", "3PM"]].sort_values("Game Time (PST)")

def export_team_from_object(team_obj: dict, season: str):
    """Export one team's points/assists/rebounds/3PM stats to an Excel file."""
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
    combined_rebounds = None
    combined_3pm = None
    avg_points = []
    avg_assists = []
    avg_rebounds = []
    avg_3pm = []

    for _, row in players_df.iterrows():
        pid = row["PLAYER_ID"]
        pname = row["PLAYER"]
        print(f"  → Fetching {pname}...")
        games = fetch_game_stats(pid, season)
        if games.empty:
            continue

        # Points
        p_df = games[["Game Time (PST)", "Opponent", "Points"]].rename(columns={"Points": pname})
        combined_points = p_df if combined_points is None else pd.merge(
            combined_points, p_df, on=["Game Time (PST)", "Opponent"], how="outer"
        )

        # Assists
        a_df = games[["Game Time (PST)", "Opponent", "Assists"]].rename(columns={"Assists": pname})
        combined_assists = a_df if combined_assists is None else pd.merge(
            combined_assists, a_df, on=["Game Time (PST)", "Opponent"], how="outer"
        )

        # Rebounds
        r_df = games[["Game Time (PST)", "Opponent", "Rebounds"]].rename(columns={"Rebounds": pname})
        combined_rebounds = r_df if combined_rebounds is None else pd.merge(
            combined_rebounds, r_df, on=["Game Time (PST)", "Opponent"], how="outer"
        )

        # 3PM
        t_df = games[["Game Time (PST)", "Opponent", "3PM"]].rename(columns={"3PM": pname})
        combined_3pm = t_df if combined_3pm is None else pd.merge(
            combined_3pm, t_df, on=["Game Time (PST)", "Opponent"], how="outer"
        )

        avg_points.append({"Player": pname, "Avg Points": games["Points"].mean()})
        avg_assists.append({"Player": pname, "Avg Assists": games["Assists"].mean()})
        avg_rebounds.append({"Player": pname, "Avg Rebounds": games["Rebounds"].mean()})
        avg_3pm.append({"Player": pname, "Avg 3PM": games["3PM"].mean()})

    if combined_points is None or combined_points.empty:
        print(f"  ⚠️  No game data found for {team_name} in season {season}. Skipping file.")
        return

    def _sort_fill(df):
        return df.sort_values("Game Time (PST)").fillna(0)

    combined_points = _sort_fill(combined_points)
    combined_assists = _sort_fill(combined_assists)
    combined_rebounds = _sort_fill(combined_rebounds)
    combined_3pm = _sort_fill(combined_3pm)

    avg_points_df = pd.DataFrame(avg_points).sort_values("Avg Points", ascending=False)
    avg_assists_df = pd.DataFrame(avg_assists).sort_values("Avg Assists", ascending=False)
    avg_rebounds_df = pd.DataFrame(avg_rebounds).sort_values("Avg Rebounds", ascending=False)
    avg_3pm_df = pd.DataFrame(avg_3pm).sort_values("Avg 3PM", ascending=False)

    file_name = f"{team_name.replace(' ', '_')}_{season}_stats.xlsx"
    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        combined_points.to_excel(writer, sheet_name="Points", index=False)
        combined_assists.to_excel(writer, sheet_name="Assists", index=False)
        combined_rebounds.to_excel(writer, sheet_name="Rebounds", index=False)
        combined_3pm.to_excel(writer, sheet_name="3PM", index=False)
        avg_points_df.to_excel(writer, sheet_name="Avg Points", index=False)
        avg_assists_df.to_excel(writer, sheet_name="Avg Assists", index=False)
        avg_rebounds_df.to_excel(writer, sheet_name="Avg Rebounds", index=False)
        avg_3pm_df.to_excel(writer, sheet_name="Avg 3PM", index=False)

    print(f"  💾 Saved '{file_name}'")

def main():
    print("🏀 NBA Tracker – Points, Assists, Rebounds, 3PM, Opponents & Game Time")
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
