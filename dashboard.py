import os
import glob
import pandas as pd
import streamlit as st
from PIL import Image

st.set_page_config(page_title="NBA Team Dashboard", layout="wide")

st.title("🏀 NBA Team Dashboard")
st.write("Lux sports data experience: Player Points, Assists, Rebounds, 3PM, Quick Bet Trends & 100%ers")

# Find exported stats files
excel_files = glob.glob("*_stats.xlsx")

if not excel_files:
    st.error("No Excel files found. Run your NBA stats script (NBA.py) first.")
else:
    # Pretty label for dropdown, e.g. "Los Angeles Lakers (2024-25)"
    def parse_team_and_season(filename: str):
        base = filename.replace("_stats.xlsx", "")
        parts = base.split("_")
        if "-" in parts[-1]:
            season = parts[-1]
            team = " ".join(parts[:-1])
        else:
            season = "Unknown"
            team = " ".join(parts)
        return team, season

    def pretty_label(filename):
        team, season = parse_team_and_season(filename)
        return f"{team} ({season})"

    label_to_file = {pretty_label(f): f for f in excel_files}
    selected_label = st.selectbox("Choose a team & season:", sorted(label_to_file.keys()))
    selected_file = label_to_file[selected_label]
    st.success(f"Loaded: {selected_label}")

    # Extract team name from selected label (for the per-team tabs)
    team_name_part = selected_label.split(" (")[0]

    # Try to show team logo for selected team
    logo_path = f"logos/{team_name_part.replace(' ', '_')}.png"
    if os.path.exists(logo_path):
        st.image(Image.open(logo_path), width=120)

    # Load sheets for the selected team (for Points / Assists / Rebounds / 3PM / Quick Bets views)
    points_df = pd.read_excel(selected_file, sheet_name="Points")
    assists_df = pd.read_excel(selected_file, sheet_name="Assists")

    # New sheets (defensive load in case old files don't have them yet)
    try:
        rebounds_df = pd.read_excel(selected_file, sheet_name="Rebounds")
    except Exception:
        rebounds_df = pd.DataFrame(columns=["Game Time (PST)", "Opponent"])

    try:
        threes_df = pd.read_excel(selected_file, sheet_name="3PM")
    except Exception:
        threes_df = pd.DataFrame(columns=["Game Time (PST)", "Opponent"])

    avg_points_df = pd.read_excel(selected_file, sheet_name="Avg Points")
    avg_assists_df = pd.read_excel(selected_file, sheet_name="Avg Assists")

    # New avg sheets
    try:
        avg_rebounds_df = pd.read_excel(selected_file, sheet_name="Avg Rebounds")
    except Exception:
        avg_rebounds_df = pd.DataFrame(columns=["Player", "Avg Rebounds"])

    try:
        avg_3pm_df = pd.read_excel(selected_file, sheet_name="Avg 3PM")
    except Exception:
        avg_3pm_df = pd.DataFrame(columns=["Player", "Avg 3PM"])

    # ---- Helper: compute streak trends for Quick Bets ----
    def compute_trends(df: pd.DataFrame, thresholds, stat_label: str) -> pd.DataFrame:
        """
        thresholds: list of ints (e.g. [10, 15, 20,...])
        stat_label: "Points", "Assists", "Rebounds", "3PM"
        """
        if df.empty:
            return pd.DataFrame(columns=["Player", "Prop", "Threshold", "Total Games Hit",
                                         "Longest Streak", "Total Games", "Hit %"])

        df_sorted = df.sort_values("Game Time (PST)")
        players = [c for c in df.columns if c not in ["Game Time (PST)", "Opponent"]]
        records = []

        for player in players:
            series = df_sorted[player].fillna(0).astype(float)
            total_games = len(series)
            if total_games == 0:
                continue

            for t in thresholds:
                total_hits = int((series >= t).sum())
                current_streak = 0
                longest_streak = 0

                for val in series:
                    if val >= t:
                        current_streak += 1
                        longest_streak = max(longest_streak, current_streak)
                    else:
                        current_streak = 0

                if longest_streak >= 3:  # only show meaningful trends
                    hit_pct = (total_hits / total_games) * 100
                    records.append(
                        {
                            "Player": player,
                            "Prop": f"{t}+ {stat_label}",
                            "Threshold": t,
                            "Total Games Hit": total_hits,
                            "Longest Streak": longest_streak,
                            "Total Games": total_games,
                            "Hit %": hit_pct,
                        }
                    )

        if not records:
            return pd.DataFrame(columns=["Player", "Prop", "Threshold", "Total Games Hit",
                                         "Longest Streak", "Total Games", "Hit %"])

        return pd.DataFrame(records).sort_values(
            ["Hit %", "Longest Streak", "Total Games Hit"], ascending=False
        )

    # ---- Helper: compute 100% hit rate props (no streak requirement) ----
    def compute_perfects(df: pd.DataFrame, thresholds, stat_label: str, team_name: str) -> pd.DataFrame:
        """
        Find props where player hit EVERY game they played for that team/season.
        thresholds: list of ints
        stat_label: "Points", "Assists", "Rebounds", "3PM"
        """
        if df.empty:
            return pd.DataFrame(columns=["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"])

        df_sorted = df.sort_values("Game Time (PST)")
        players = [c for c in df.columns if c not in ["Game Time (PST)", "Opponent"]]
        records = []

        for player in players:
            series = df_sorted[player].dropna().astype(float)
            total_games = len(series)
            if total_games == 0:
                continue

            for t in thresholds:
                total_hits = int((series >= t).sum())
                if total_hits == total_games and total_games > 0:
                    hit_pct = (total_hits / total_games) * 100  # should be 100
                    records.append(
                        {
                            "Player": player,
                            "Team": team_name,
                            "Prop": f"{t}+ {stat_label}",
                            "Threshold": t,
                            "Total Games": total_games,
                            "Hit %": hit_pct,
                        }
                    )

        if not records:
            return pd.DataFrame(columns=["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"])

        return pd.DataFrame(records).sort_values(
            ["Total Games", "Threshold"], ascending=[False, True]
        )

    # Main view choice (now with Rebounds & 3PM)
    view_choice = st.radio(
        "Select View:",
        [
            "Player Points",
            "Player Assists",
            "Player Rebounds",
            "Player 3PM",
            "Quick Bets",
            "100%ers",
        ]
    )

    # Common player-view code (to keep structure same)
    def render_player_view(df, stat_type, avg_df, highlight_bg, highlight_text, threshold, legend_text):
        # All players selected by default
        all_players = [c for c in df.columns if c not in ["Game Time (PST)", "Opponent"]]
        selected_players = st.multiselect(
            f"Select players to display ({stat_type}):",
            options=all_players,
            default=all_players
        )

        display_df = df[["Game Time (PST)", "Opponent"] + selected_players] if selected_players else df[["Game Time (PST)", "Opponent"]]

        st.markdown(f"**Legend:**  {legend_text}")

        def highlight_values(val):
            if isinstance(val, (int, float)) and val >= threshold:
                return (
                    f"background-color: {highlight_bg}; "
                    f"color: {highlight_text}; "
                    f"font-weight: 600;"
                )
            return ""

        styled = display_df.style.applymap(highlight_values, subset=selected_players)
        st.dataframe(styled, use_container_width=True)

        st.subheader(f"📈 {stat_type} Over Time")
        if selected_players:
            chart_df = df.set_index("Game Time (PST)")[selected_players]
            st.line_chart(chart_df)
        else:
            st.info("Pick at least one player above to see the chart.")

        # Quick averages
        st.markdown(f"### ⚡ Quick Averages ({stat_type})")
        if not avg_df.empty:
            stat_col = avg_df.columns[-1]
            st.dataframe(
                avg_df.style.format({stat_col: "{:.2f}"}),
                use_container_width=True
            )
        else:
            st.info("No average data available.")

    # ========== PLAYER VIEWS ==========
    if view_choice == "Player Points":
        render_player_view(
            points_df,
            "Points",
            avg_points_df,
            "#FFF4D2",
            "#4A3B1C",
            10,
            "🥇 Gold highlight = Player scored more than 10 points",
        )

    elif view_choice == "Player Assists":
        render_player_view(
            assists_df,
            "Assists",
            avg_assists_df,
            "#E6E0FF",
            "#2F2545",
            3,
            "👑 Royal highlight = Player recorded 3 or more assists",
        )

    elif view_choice == "Player Rebounds":
        # Lux green-ish palette
        render_player_view(
            rebounds_df,
            "Rebounds",
            avg_rebounds_df,
            "#E0FFE6",
            "#1F3A2E",
            5,
            "🟢 Highlight = Player grabbed 5+ rebounds",
        )

    elif view_choice == "Player 3PM":
        # Lux blue-grey palette
        render_player_view(
            threes_df,
            "3PM",
            avg_3pm_df,
            "#E0F2FF",
            "#123047",
            2,
            "🎯 Highlight = Player made 2+ 3-pointers",
        )

    # ========== QUICK BETS VIEW (per selected team) ==========
    elif view_choice == "Quick Bets":
        st.subheader("⚡ Quick Bets – Trend Finder")
        st.write(
            "Showing only players who have hit key prop lines in **at least 3 games in a row** "
            "for the selected team & season."
        )

        # Define thresholds
        points_thresholds = [10, 15, 20, 25, 30, 35]
        assists_thresholds = [3, 5, 7, 10]
        rebounds_thresholds = [5, 8, 10, 12, 15]
        threes_thresholds = [1, 2, 3, 4, 5]

        # Compute trends for selected team
        points_trends = compute_trends(points_df, points_thresholds, "Points")
        assists_trends = compute_trends(assists_df, assists_thresholds, "Assists")
        rebounds_trends = compute_trends(rebounds_df, rebounds_thresholds, "Rebounds")
        threes_trends = compute_trends(threes_df, threes_thresholds, "3PM")

        # Rich, high-contrast color palettes for thresholds
        points_palette = {
            10: {"bg": "#F7C948", "text": "#1F1300"},
            15: {"bg": "#F4A300", "text": "#1F1300"},
            20: {"bg": "#E66F00", "text": "#FFFFFF"},
            25: {"bg": "#C83C00", "text": "#FFFFFF"},
            30: {"bg": "#B91C1C", "text": "#FFFFFF"},
            35: {"bg": "#7F1D1D", "text": "#FFFFFF"},
        }

        assists_palette = {
            3: {"bg": "#3B82F6", "text": "#FFFFFF"},
            5: {"bg": "#2563EB", "text": "#FFFFFF"},
            7: {"bg": "#7C3AED", "text": "#FFFFFF"},
            10: {"bg": "#6D28D9", "text": "#FFFFFF"},
        }

        rebounds_palette = {
            5: {"bg": "#34D399", "text": "#044E35"},
            8: {"bg": "#10B981", "text": "#FFFFFF"},
            10: {"bg": "#059669", "text": "#FFFFFF"},
            12: {"bg": "#047857", "text": "#FFFFFF"},
            15: {"bg": "#065F46", "text": "#FFFFFF"},
        }

        threes_palette = {
            1: {"bg": "#BFDBFE", "text": "#0F172A"},
            2: {"bg": "#93C5FD", "text": "#0F172A"},
            3: {"bg": "#60A5FA", "text": "#FFFFFF"},
            4: {"bg": "#3B82F6", "text": "#FFFFFF"},
            5: {"bg": "#1D4ED8", "text": "#FFFFFF"},
        }

        percentage_color = "#065F46"

        # Helper to render trend section
        def render_trend_section(title, trends_df, palette):
            st.markdown(title)
            if trends_df.empty:
                st.info("No strong trends (3+ game streaks) found for this team/season.")
            else:
                for _, row in trends_df.iterrows():
                    t = int(row["Threshold"])
                    pal = palette.get(t, {"bg": "#F7C948", "text": "#1F1300"})
                    pct = float(row["Hit %"])
                    total_games = int(row["Total Games"])
                    total_hits = int(row["Total Games Hit"])
                    longest_streak = int(row["Longest Streak"])

                    chip = (
                        f'<span style="background-color:{pal["bg"]}; color:{pal["text"]}; '
                        f'padding:3px 8px; border-radius:999px; font-weight:600;">'
                        f'{row["Player"]} {row["Prop"]}'
                        f"</span>"
                    )
                    pct_text = (
                        f'<span style="color:{percentage_color}; font-weight:700; margin-left:6px;">'
                        f'{pct:.1f}% hit rate'
                        f"</span>"
                    )
                    meta_text = (
                        f"<span style='color:#444;'>"
                        f" ({total_hits}/{total_games} games, longest streak {longest_streak})"
                        f"</span>"
                    )

                    st.markdown(chip + " " + pct_text + " " + meta_text, unsafe_allow_html=True)

        render_trend_section("### 🥇 Points Props Trends (Selected Team)", points_trends, points_palette)
        render_trend_section("### 👑 Assists Props Trends (Selected Team)", assists_trends, assists_palette)
        render_trend_section("### 🟢 Rebounds Props Trends (Selected Team)", rebounds_trends, rebounds_palette)
        render_trend_section("### 🎯 3PM Props Trends (Selected Team)", threes_trends, threes_palette)

    # ========== 100%ers VIEW (ACROSS ALL TEAMS) ==========
    else:
        st.subheader("💯 100%ers – League-Wide Perfect Hit Rates")
        st.write(
            "Players across **all teams & seasons** (based on your Excel files) who have a "
            "**100% hit rate** on any tracked prop."
        )

        # Define thresholds
        points_thresholds = [10, 15, 20, 25, 30, 35]
        assists_thresholds = [3, 5, 7, 10]
        rebounds_thresholds = [5, 8, 10, 12, 15]
        threes_thresholds = [1, 2, 3, 4, 5]

        # Aggregate perfect props from ALL teams/files
        all_perfect_points = []
        all_perfect_assists = []
        all_perfect_rebounds = []
        all_perfect_threes = []

        for f in excel_files:
            team_name, season = parse_team_and_season(f)
            try:
                p_df = pd.read_excel(f, sheet_name="Points")
                a_df = pd.read_excel(f, sheet_name="Assists")
            except Exception as e:
                st.warning(f"Skipping file {f} due to error reading sheets: {e}")
                continue

            # New sheets defensive read
            try:
                r_df = pd.read_excel(f, sheet_name="Rebounds")
            except Exception:
                r_df = pd.DataFrame(columns=["Game Time (PST)", "Opponent"])

            try:
                t_df = pd.read_excel(f, sheet_name="3PM")
            except Exception:
                t_df = pd.DataFrame(columns=["Game Time (PST)", "Opponent"])

            p_perf = compute_perfects(p_df, points_thresholds, "Points", team_name)
            a_perf = compute_perfects(a_df, assists_thresholds, "Assists", team_name)
            r_perf = compute_perfects(r_df, rebounds_thresholds, "Rebounds", team_name)
            t_perf = compute_perfects(t_df, threes_thresholds, "3PM", team_name)

            if not p_perf.empty:
                all_perfect_points.append(p_perf)
            if not a_perf.empty:
                all_perfect_assists.append(a_perf)
            if not r_perf.empty:
                all_perfect_rebounds.append(r_perf)
            if not t_perf.empty:
                all_perfect_threes.append(t_perf)

        def concat_or_empty(dfs, cols):
            if dfs:
                return pd.concat(dfs, ignore_index=True)
            return pd.DataFrame(columns=cols)

        perfect_points = concat_or_empty(
            all_perfect_points,
            ["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"],
        )
        perfect_assists = concat_or_empty(
            all_perfect_assists,
            ["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"],
        )
        perfect_rebounds = concat_or_empty(
            all_perfect_rebounds,
            ["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"],
        )
        perfect_threes = concat_or_empty(
            all_perfect_threes,
            ["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"],
        )

        # Sort for neat presentation
        def sort_df(df):
            if not df.empty:
                return df.sort_values(
                    ["Total Games", "Threshold", "Team", "Player"],
                    ascending=[False, True, True, True],
                )
            return df

        perfect_points = sort_df(perfect_points)
        perfect_assists = sort_df(perfect_assists)
        perfect_rebounds = sort_df(perfect_rebounds)
        perfect_threes = sort_df(perfect_threes)

        # Palettes
        points_palette = {
            10: {"bg": "#F7C948", "text": "#1F1300"},
            15: {"bg": "#F4A300", "text": "#1F1300"},
            20: {"bg": "#E66F00", "text": "#FFFFFF"},
            25: {"bg": "#C83C00", "text": "#FFFFFF"},
            30: {"bg": "#B91C1C", "text": "#FFFFFF"},
            35: {"bg": "#7F1D1D", "text": "#FFFFFF"},
        }

        assists_palette = {
            3: {"bg": "#3B82F6", "text": "#FFFFFF"},
            5: {"bg": "#2563EB", "text": "#FFFFFF"},
            7: {"bg": "#7C3AED", "text": "#FFFFFF"},
            10: {"bg": "#6D28D9", "text": "#FFFFFF"},
        }

        rebounds_palette = {
            5: {"bg": "#34D399", "text": "#044E35"},
            8: {"bg": "#10B981", "text": "#FFFFFF"},
            10: {"bg": "#059669", "text": "#FFFFFF"},
            12: {"bg": "#047857", "text": "#FFFFFF"},
            15: {"bg": "#065F46", "text": "#FFFFFF"},
        }

        threes_palette = {
            1: {"bg": "#BFDBFE", "text": "#0F172A"},
            2: {"bg": "#93C5FD", "text": "#0F172A"},
            3: {"bg": "#60A5FA", "text": "#FFFFFF"},
            4: {"bg": "#3B82F6", "text": "#FFFFFF"},
            5: {"bg": "#1D4ED8", "text": "#FFFFFF"},
        }

        percentage_color = "#065F46"

        def render_perfect_section(title, df, palette, icon=""):
            st.markdown(title)
            if df.empty:
                st.info("No players with a 100% hit rate on tracked props across your data.")
            else:
                for _, row in df.iterrows():
                    t = int(row["Threshold"])
                    pal = palette.get(t, {"bg": "#F7C948", "text": "#1F1300"})
                    total_games = int(row["Total Games"])
                    pct = float(row["Hit %"])  # should be 100

                    chip = (
                        f'<span style="background-color:{pal["bg"]}; color:{pal["text"]}; '
                        f'padding:3px 8px; border-radius:999px; font-weight:600;">'
                        f'({row["Team"]}) {row["Player"]} {row["Prop"]}'
                        f"</span>"
                    )
                    pct_text = (
                        f'<span style="color:{percentage_color}; font-weight:800; margin-left:6px;">'
                        f'{pct:.0f}% hit rate'
                        f"</span>"
                    )
                    meta_text = (
                        f"<span style='color:#444;'>"
                        f" ({total_games}/{total_games} games)"
                        f"</span>"
                    )

                    st.markdown(chip + " " + pct_text + " " + meta_text, unsafe_allow_html=True)

        render_perfect_section("### 🥇 100% Points Props (All Teams)", perfect_points, points_palette)
        render_perfect_section("### 👑 100% Assists Props (All Teams)", perfect_assists, assists_palette)
        render_perfect_section("### 🟢 100% Rebounds Props (All Teams)", perfect_rebounds, rebounds_palette)
        render_perfect_section("### 🎯 100% 3PM Props (All Teams)", perfect_threes, threes_palette)
