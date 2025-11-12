import os
import glob
import pandas as pd
import streamlit as st
from PIL import Image

st.set_page_config(page_title="NBA Team Dashboard", layout="wide")

st.title("🏀 NBA Team Dashboard")
st.write("Lux sports data experience: Player Points, Assists, Quick Bet Trends & 100%ers")

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

    # Load sheets for the selected team (for Points / Assists / Quick Bets views)
    points_df = pd.read_excel(selected_file, sheet_name="Points")
    assists_df = pd.read_excel(selected_file, sheet_name="Assists")
    avg_points_df = pd.read_excel(selected_file, sheet_name="Avg Points")
    avg_assists_df = pd.read_excel(selected_file, sheet_name="Avg Assists")

    # ---- Helper: compute streak trends for Quick Bets ----
    def compute_trends(df: pd.DataFrame, thresholds, stat_label: str) -> pd.DataFrame:
        """
        thresholds: list of ints (e.g. [10, 15, 20,...])
        stat_label: "Points" or "Assists"
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
        thresholds: list of ints (e.g. [10, 15, 20,...])
        stat_label: "Points" or "Assists"
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

    # Main view choice (added "100%ers")
    view_choice = st.radio(
        "Select View:",
        ["Player Points", "Player Assists", "Quick Bets", "100%ers"]
    )

    # ========== PLAYER POINTS / ASSISTS VIEWS ==========
    if view_choice in ["Player Points", "Player Assists"]:
        if view_choice == "Player Points":
            df = points_df
            stat_type = "Points"
            avg_df = avg_points_df

            # Lux gold palette for regular points view
            highlight_bg = "#FFF4D2"   # soft gold
            highlight_text = "#4A3B1C" # rich brown
            threshold = 10
            legend_text = "🥇 Gold highlight = Player scored more than 10 points"
        else:
            df = assists_df
            stat_type = "Assists"
            avg_df = avg_assists_df

            # Lux royal palette for regular assists view
            highlight_bg = "#E6E0FF"   # soft royal violet
            highlight_text = "#2F2545" # deep plum
            threshold = 3
            legend_text = "👑 Royal highlight = Player recorded 3 or more assists"

        # All players selected by default
        all_players = [c for c in df.columns if c not in ["Game Time (PST)", "Opponent"]]
        selected_players = st.multiselect(
            f"Select players to display ({stat_type}):",
            options=all_players,
            default=all_players
        )

        display_df = df[["Game Time (PST)", "Opponent"] + selected_players]

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
            avg_col = avg_df.columns[-1]  # "Avg Points" or "Avg Assists"
            st.dataframe(
                avg_df.style.format({avg_col: "{:.2f}"}),
                use_container_width=True
            )
        else:
            st.info("No average data available.")

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

        # Compute trends for selected team
        points_trends = compute_trends(points_df, points_thresholds, "Points")
        assists_trends = compute_trends(assists_df, assists_thresholds, "Assists")

        # Rich, high-contrast color palettes for thresholds
        points_palette = {
            10: {"bg": "#F7C948", "text": "#1F1300"},  # Bold golden yellow
            15: {"bg": "#F4A300", "text": "#1F1300"},  # Deep gold-orange
            20: {"bg": "#E66F00", "text": "#FFFFFF"},  # Fiery amber
            25: {"bg": "#C83C00", "text": "#FFFFFF"},  # Burnt red-orange
            30: {"bg": "#B91C1C", "text": "#FFFFFF"},  # Rich crimson red
            35: {"bg": "#7F1D1D", "text": "#FFFFFF"},  # Dark royal red
        }

        assists_palette = {
            3: {"bg": "#3B82F6", "text": "#FFFFFF"},   # Bright royal blue
            5: {"bg": "#2563EB", "text": "#FFFFFF"},   # Deep blue
            7: {"bg": "#7C3AED", "text": "#FFFFFF"},   # Lux violet
            10: {"bg": "#6D28D9", "text": "#FFFFFF"},  # Electric purple
        }

        percentage_color = "#065F46"  # Deep rich teal for % text

        # POINTS TRENDS
        st.markdown("### 🥇 Points Props Trends (Selected Team)")
        if points_trends.empty:
            st.info("No strong points trends (3+ game streaks) found for this team/season.")
        else:
            for _, row in points_trends.iterrows():
                t = int(row["Threshold"])
                pal = points_palette.get(t, {"bg": "#F7C948", "text": "#1F1300"})
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

        # ASSISTS TRENDS
        st.markdown("### 👑 Assists Props Trends (Selected Team)")
        if assists_trends.empty:
            st.info("No strong assists trends (3+ game streaks) found for this team/season.")
        else:
            for _, row in assists_trends.iterrows():
                t = int(row["Threshold"])
                pal = assists_palette.get(t, {"bg": "#3B82F6", "text": "#FFFFFF"})
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

        # Aggregate perfect props from ALL teams/files
        all_perfect_points = []
        all_perfect_assists = []

        for f in excel_files:
            team_name, season = parse_team_and_season(f)
            try:
                p_df = pd.read_excel(f, sheet_name="Points")
                a_df = pd.read_excel(f, sheet_name="Assists")
            except Exception as e:
                st.warning(f"Skipping file {f} due to error reading sheets: {e}")
                continue

            p_perf = compute_perfects(p_df, points_thresholds, "Points", team_name)
            a_perf = compute_perfects(a_df, assists_thresholds, "Assists", team_name)

            if not p_perf.empty:
                all_perfect_points.append(p_perf)
            if not a_perf.empty:
                all_perfect_assists.append(a_perf)

        if all_perfect_points:
            perfect_points = pd.concat(all_perfect_points, ignore_index=True)
        else:
            perfect_points = pd.DataFrame(columns=["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"])

        if all_perfect_assists:
            perfect_assists = pd.concat(all_perfect_assists, ignore_index=True)
        else:
            perfect_assists = pd.DataFrame(columns=["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"])

        # Sort for neat presentation
        if not perfect_points.empty:
            perfect_points = perfect_points.sort_values(
                ["Total Games", "Threshold", "Team", "Player"],
                ascending=[False, True, True, True]
            )
        if not perfect_assists.empty:
            perfect_assists = perfect_assists.sort_values(
                ["Total Games", "Threshold", "Team", "Player"],
                ascending=[False, True, True, True]
            )

        # Same rich palettes as Quick Bets
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

        percentage_color = "#065F46"  # Deep rich teal for 100% text

        # 100% Points Props (league-wide)
        st.markdown("### 🥇 100% Points Props (All Teams)")
        if perfect_points.empty:
            st.info("No players with a 100% hit rate on tracked points props across your data.")
        else:
            for _, row in perfect_points.iterrows():
                t = int(row["Threshold"])
                pal = points_palette.get(t, {"bg": "#F7C948", "text": "#1F1300"})
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

        # 100% Assists Props (league-wide)
        st.markdown("### 👑 100% Assists Props (All Teams)")
        if perfect_assists.empty:
            st.info("No players with a 100% hit rate on tracked assists props across your data.")
        else:
            for _, row in perfect_assists.iterrows():
                t = int(row["Threshold"])
                pal = assists_palette.get(t, {"bg": "#3B82F6", "text": "#FFFFFF"})
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
