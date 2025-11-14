import os
import glob
import base64
import pandas as pd
import streamlit as st
from PIL import Image

# Folder where your logos live
LOGO_DIR = "Team_logos"

st.set_page_config(page_title="NBA Team Dashboard", layout="wide")

st.title("🏀 NBA Team Dashboard")
st.write(
    "Lux sports data experience: Player Points, Assists, Rebounds, 3PM, "
    "Team Totals, Quick Bet Trends & 100%ers"
)

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
    selected_label = st.selectbox(
        "Choose a team & season:", sorted(label_to_file.keys())
    )
    selected_file = label_to_file[selected_label]
    st.success(f"Loaded: {selected_label}")

    # Extract team name from selected label (for the per-team tabs)
    team_name_part = selected_label.split(" (")[0]

    # ---- Logo helpers ----
    def get_logo_path(team_name: str) -> str:
        """Map 'Indiana Pacers' -> Team_logos/indiana_pacers.png"""
        fname = team_name.replace(" ", "_").lower() + ".png"
        return os.path.join(LOGO_DIR, fname)

    def load_logo_data_uri(team_name: str) -> str:
        logo_file = get_logo_path(team_name)
        if not os.path.exists(logo_file):
            return ""
        with open(logo_file, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{data}"

    logo_cache = {}

    def get_logo_html_for_team(team_name: str, size: int = 20) -> str:
        if team_name not in logo_cache:
            logo_cache[team_name] = load_logo_data_uri(team_name)
        uri = logo_cache[team_name]
        if not uri:
            return ""
        return (
            f'<img src="{uri}" '
            f'style="height:{size}px; width:{size}px; object-fit:contain; '
            f'vertical-align:middle; margin-right:6px; border-radius:50%;">'
        )

    # Preload selected team logo for Quick Bets
    selected_team_logo_uri = load_logo_data_uri(team_name_part)
    if selected_team_logo_uri:
        logo_cache[team_name_part] = selected_team_logo_uri
        quickbets_logo_html = get_logo_html_for_team(team_name_part, size=22)
    else:
        quickbets_logo_html = ""

    # Show big header logo if present
    big_logo_path = get_logo_path(team_name_part)
    if os.path.exists(big_logo_path):
        st.image(Image.open(big_logo_path), width=120)

    # ---- Load sheets for the selected team ----
    points_df = pd.read_excel(selected_file, sheet_name="Points")
    assists_df = pd.read_excel(selected_file, sheet_name="Assists")

    try:
        rebounds_df = pd.read_excel(selected_file, sheet_name="Rebounds")
    except Exception:
        rebounds_df = pd.DataFrame(columns=["Game Time (PST)", "Opponent"])

    try:
        threes_df = pd.read_excel(selected_file, sheet_name="3PM")
    except Exception:
        threes_df = pd.DataFrame(columns=["Game Time (PST)", "Opponent"])

    # Team total scores sheet (Team Points)
    try:
        team_totals_df = pd.read_excel(selected_file, sheet_name="Team Points")
    except Exception:
        team_totals_df = pd.DataFrame(
            columns=[
                "Game Time (PST)",
                "Opponent",
                "Team Points",
                "Opponent Points",
                "Game Total Points",
            ]
        )

    avg_points_df = pd.read_excel(selected_file, sheet_name="Avg Points")
    avg_assists_df = pd.read_excel(selected_file, sheet_name="Avg Assists")

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
            return pd.DataFrame(
                columns=[
                    "Player",
                    "Prop",
                    "Threshold",
                    "Total Games Hit",
                    "Longest Streak",
                    "Total Games",
                    "Hit %",
                ]
            )

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
            return pd.DataFrame(
                columns=[
                    "Player",
                    "Prop",
                    "Threshold",
                    "Total Games Hit",
                    "Longest Streak",
                    "Total Games",
                    "Hit %",
                ]
            )

        return pd.DataFrame(records).sort_values(
            ["Hit %", "Longest Streak", "Total Games Hit"], ascending=False
        )

    # ---- Helper: compute 100% hit rate props (no streak requirement) ----
    def compute_perfects(
        df: pd.DataFrame, thresholds, stat_label: str, team_name: str
    ) -> pd.DataFrame:
        """
        Find props where player hit EVERY game they played for that team/season.
        thresholds: list of ints
        stat_label: "Points", "Assists", "Rebounds", "3PM"
        """
        if df.empty:
            return pd.DataFrame(
                columns=["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"]
            )

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
            return pd.DataFrame(
                columns=["Player", "Team", "Prop", "Threshold", "Total Games", "Hit %"]
            )

        return pd.DataFrame(records).sort_values(
            ["Total Games", "Threshold"], ascending=[False, True]
        )

    # ---- Main view choice (added Team Totals) ----
    view_choice = st.radio(
        "Select View:",
        [
            "Player Points",
            "Player Assists",
            "Player Rebounds",
            "Player 3PM",
            "Team Totals",
            "Quick Bets",
            "100%ers",
        ],
    )

    # ---- Common player-view code ----
    def render_player_view(
        df, stat_type, avg_df, highlight_bg, highlight_text, threshold, legend_text
    ):
        all_players = [c for c in df.columns if c not in ["Game Time (PST)", "Opponent"]]
        selected_players = st.multiselect(
            f"Select players to display ({stat_type}):",
            options=all_players,
            default=all_players,
        )

        display_df = (
            df[["Game Time (PST)", "Opponent"] + selected_players]
            if selected_players
            else df[["Game Time (PST)", "Opponent"]]
        )

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

        st.markdown(f"### ⚡ Quick Averages ({stat_type})")
        if not avg_df.empty:
            stat_col = avg_df.columns[-1]
            st.dataframe(
                avg_df.style.format({stat_col: "{:.2f}"}), use_container_width=True
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
        render_player_view(
            threes_df,
            "3PM",
            avg_3pm_df,
            "#E0F2FF",
            "#123047",
            2,
            "🎯 Highlight = Player made 2+ 3-pointers",
        )

    # ========== TEAM TOTALS VIEW ==========
    elif view_choice == "Team Totals":
        st.subheader("📊 Team Scores & Game Totals")

        if team_totals_df.empty:
            st.info("No team total data found in this file (expected sheet: 'Team Points').")
        else:
            df = team_totals_df.copy()

            # Ensure numeric
            for col in ["Team Points", "Opponent Points", "Game Total Points"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Clean/sort dates
            if "Game Time (PST)" in df.columns:
                df["Game Time (PST)"] = pd.to_datetime(
                    df["Game Time (PST)"], errors="coerce"
                )
                df = df.sort_values("Game Time (PST)")

            df_chart = df.copy()
            df_display = df.copy()
            df_display["Game Time (PST)"] = df_display["Game Time (PST)"].dt.strftime(
                "%Y-%m-%d"
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("🟦 Our points (avg)", f"{df['Team Points'].mean():.1f}")
            col2.metric("🟥 Their points (avg)", f"{df['Opponent Points'].mean():.1f}")
            col3.metric(
                "🌟 Total points (avg)", f"{df['Game Total Points'].mean():.1f}"
            )

            if df["Game Total Points"].notna().any():
                max_row = df.loc[df["Game Total Points"].idxmax()]
                st.markdown(
                    f"**Biggest firework game:** "
                    f"{max_row['Game Time (PST)'].strftime('%Y-%m-%d')} vs {max_row['Opponent']} "
                    f"with **{int(max_row['Game Total Points'])}** total points 🎆"
                )

            st.markdown("---")

            st.markdown("### 📅 Every Game – Nice & Simple")

            display_df = df_display.rename(
                columns={
                    "Game Time (PST)": "Date",
                    "Opponent": "Opponent",
                    "Team Points": "Our Points",
                    "Opponent Points": "Their Points",
                    "Game Total Points": "Total Points",
                }
            )

            def color_result(row):
                if row["Our Points"] > row["Their Points"]:
                    style = "background-color: #DCFCE7; color: #14532D; font-weight: 600;"
                elif row["Our Points"] < row["Their Points"]:
                    style = "background-color: #FEE2E2; color: #991B1B; font-weight: 600;"
                else:
                    style = "background-color: #E5E7EB; color: #111827; font-weight: 600;"
                return [style] * len(row)

            styled_table = display_df.style.apply(color_result, axis=1)
            st.dataframe(styled_table, use_container_width=True)

            st.markdown(
                "> 🟢 Green rows = your team scored more. 🔴 Red rows = the other team scored more."
            )

            st.markdown("---")

            st.markdown("### 📈 Points Story Over the Season")
            df_chart = df_chart.set_index("Game Time (PST)")[
                ["Team Points", "Opponent Points", "Game Total Points"]
            ]
            st.line_chart(df_chart)

    # ========== QUICK BETS VIEW ==========
    elif view_choice == "Quick Bets":
        st.subheader("⚡ Quick Bets – Trend Finder")
        st.write(
            "See which players are **on fire** for this team & season. "
            "Only props with at least a **3-game hit streak** are shown."
        )

        points_thresholds = [10, 15, 20, 25, 30, 35]
        assists_thresholds = [3, 5, 7, 10]
        rebounds_thresholds = [5, 8, 10, 12, 15]
        threes_thresholds = [1, 2, 3, 4, 5]

        points_trends = compute_trends(points_df, points_thresholds, "Points")
        assists_trends = compute_trends(assists_df, assists_thresholds, "Assists")
        rebounds_trends = compute_trends(rebounds_df, rebounds_thresholds, "Rebounds")
        threes_trends = compute_trends(threes_df, threes_thresholds, "3PM")

        points_palette = {
            10: {"bg": "#F7C948", "text": "#111827"},
            15: {"bg": "#F4A300", "text": "#111827"},
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
            5: {"bg": "#34D399", "text": "#064E3B"},
            8: {"bg": "#10B981", "text": "#FFFFFF"},
            10: {"bg": "#059669", "text": "#FFFFFF"},
            12: {"bg": "#047857", "text": "#FFFFFF"},
            15: {"bg": "#065F46", "text": "#FFFFFF"},
        }

        threes_palette = {
            1: {"bg": "#BFDBFE", "text": "#111827"},
            2: {"bg": "#93C5FD", "text": "#111827"},
            3: {"bg": "#60A5FA", "text": "#FFFFFF"},
            4: {"bg": "#3B82F6", "text": "#FFFFFF"},
            5: {"bg": "#1D4ED8", "text": "#FFFFFF"},
        }

        percentage_color = "#10B981"

        def render_trend_grouped(trends_df, palette, stat_label, logo_html_prefix="", max_items=20):
            if trends_df.empty:
                st.info("No strong trends (3+ game streaks) found for this stat.")
                return

            top_n = st.slider(
                f"How many hot {stat_label.lower()} props to show?",
                min_value=5,
                max_value=min(max_items, len(trends_df)),
                value=min(10, len(trends_df)),
                key=f"slider_{stat_label}",
            )

            show_df = trends_df.head(top_n)

            for threshold, group in show_df.groupby("Threshold", sort=True):
                pal_header = palette.get(int(threshold), {"bg": "#F9A826", "text": "#FACC15"})
                header_color = pal_header["bg"]

                header = f"{int(threshold)}+ {stat_label}"
                st.markdown(
                    f"<div style='margin-top:0.85rem; margin-bottom:0.25rem; "
                    f"font-weight:700; font-size:1.05rem; letter-spacing:0.04em; "
                    f"text-transform:uppercase; color:{header_color};'>"
                    f"{header}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                for _, row in group.iterrows():
                    t = int(row["Threshold"])
                    pal = palette.get(t, {"bg": "#F7C948", "text": "#111827"})
                    pct = float(row["Hit %"])
                    total_games = int(row["Total Games"])
                    total_hits = int(row["Total Games Hit"])
                    longest_streak = int(row["Longest Streak"])

                    chip = (
                        f'{logo_html_prefix}'
                        f'<span style="background-color:{pal["bg"]}; color:{pal["text"]}; '
                        f'padding:4px 10px; border-radius:999px; font-weight:600; font-size:1.0rem;">'
                        f'{row["Player"]} {row["Prop"]}'
                        f"</span>"
                    )
                    pct_text = (
                        f'<span style="color:{percentage_color}; font-weight:700; '
                        f'margin-left:6px; font-size:0.9rem;">'
                        f"{pct:.1f}% hit rate"
                        f"</span>"
                    )
                    meta_text = (
                        f"<span style='color:#D1D5DB; font-size:0.85rem;'>"
                        f" ({total_hits}/{total_games} games, best streak {longest_streak})"
                        f"</span>"
                    )

                    st.markdown(
                        chip + " " + pct_text + " " + meta_text,
                        unsafe_allow_html=True,
                    )

        tab_points, tab_assists, tab_reb, tab_3pm = st.tabs(
            ["🥇 Points", "👑 Assists", "🟢 Rebounds", "🎯 3PM"]
        )

        with tab_points:
            st.markdown("#### Hottest Points Props")
            render_trend_grouped(points_trends, points_palette, "Points", quickbets_logo_html)

        with tab_assists:
            st.markdown("#### Hottest Assists Props")
            render_trend_grouped(assists_trends, assists_palette, "Assists", quickbets_logo_html)

        with tab_reb:
            st.markdown("#### Hottest Rebounds Props")
            render_trend_grouped(rebounds_trends, rebounds_palette, "Rebounds", quickbets_logo_html)

        with tab_3pm:
            st.markdown("#### Hottest 3PM Props")
            render_trend_grouped(threes_trends, threes_palette, "3PM", quickbets_logo_html)

    # ========== 100%ers VIEW ==========
    elif view_choice == "100%ers":
        st.subheader("💯 100%ers – League-Wide Perfect Hit Rates")
        st.write(
            "Players across **all teams & seasons** (based on your Excel files) who have a "
            "**100% hit rate** on any tracked prop."
        )

        points_thresholds = [10, 15, 20, 25, 30, 35]
        assists_thresholds = [3, 5, 7, 10]
        rebounds_thresholds = [5, 8, 10, 12, 15]
        threes_thresholds = [1, 2, 3, 4, 5]

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

        points_palette = {
            10: {"bg": "#F7C948", "text": "#111827"},
            15: {"bg": "#F4A300", "text": "#111827"},
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
            5: {"bg": "#34D399", "text": "#064E3B"},
            8: {"bg": "#10B981", "text": "#FFFFFF"},
            10: {"bg": "#059669", "text": "#FFFFFF"},
            12: {"bg": "#047857", "text": "#FFFFFF"},
            15: {"bg": "#065F46", "text": "#FFFFFF"},
        }

        threes_palette = {
            1: {"bg": "#BFDBFE", "text": "#111827"},
            2: {"bg": "#93C5FD", "text": "#111827"},
            3: {"bg": "#60A5FA", "text": "#FFFFFF"},
            4: {"bg": "#3B82F6", "text": "#FFFFFF"},
            5: {"bg": "#1D4ED8", "text": "#FFFFFF"},
        }

        percentage_color = "#10B981"

        def render_perfect_grouped(df, palette, stat_label, max_items=40):
            if df.empty:
                st.info(
                    "No players with a 100% hit rate on tracked props in your current data."
                )
                return

            top_n = st.slider(
                f"How many perfect {stat_label.lower()} props to show?",
                min_value=5,
                max_value=min(max_items, len(df)),
                value=min(15, len(df)),
                key=f"slider_perfect_{stat_label}",
            )

            show_df = df.head(top_n)

            for threshold, group in show_df.groupby("Threshold", sort=True):
                pal_header = palette.get(int(threshold), {"bg": "#F9A826", "text": "#FACC15"})
                header_color = pal_header["bg"]

                header = f"{int(threshold)}+ {stat_label}"
                st.markdown(
                    f"<div style='margin-top:0.85rem; margin-bottom:0.25rem; "
                    f"font-weight:700; font-size:1.05rem; letter-spacing:0.04em; "
                    f"text-transform:uppercase; color:{header_color};'>"
                    f"{header}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                for _, row in group.iterrows():
                    t = int(row["Threshold"])
                    pal = palette.get(t, {"bg": "#F7C948", "text": "#111827"})
                    total_games = int(row["Total Games"])
                    pct = float(row["Hit %"])
                    team = row["Team"]
                    logo_html = get_logo_html_for_team(team, size=22)

                    chip = (
                        f'{logo_html}'
                        f'<span style="background-color:{pal["bg"]}; color:{pal["text"]}; '
                        f'padding:4px 10px; border-radius:999px; font-weight:600; font-size:1.0rem;">'
                        f'({team}) {row["Player"]} {row["Prop"]}'
                        f"</span>"
                    )
                    pct_text = (
                        f'<span style="color:{percentage_color}; font-weight:800; '
                        f'margin-left:6px; font-size:0.9rem;">'
                        f"{pct:.0f}% hit rate"
                        f"</span>"
                    )
                    meta_text = (
                        f"<span style='color:#D1D5DB; font-size:0.85rem;'>"
                        f" ({total_games}/{total_games} games)"
                        f"</span>"
                    )

                    st.markdown(
                        chip + " " + pct_text + " " + meta_text,
                        unsafe_allow_html=True,
                    )

        tab_p, tab_a, tab_r, tab_t = st.tabs(
            ["🥇 Points 100%ers", "👑 Assists 100%ers", "🟢 Rebounds 100%ers", "🎯 3PM 100%ers"]
        )

        with tab_p:
            st.markdown("#### Perfect Points Props")
            render_perfect_grouped(perfect_points, points_palette, "Points")

        with tab_a:
            st.markdown("#### Perfect Assists Props")
            render_perfect_grouped(perfect_assists, assists_palette, "Assists")

        with tab_r:
            st.markdown("#### Perfect Rebounds Props")
            render_perfect_grouped(perfect_rebounds, rebounds_palette, "Rebounds")

        with tab_t:
            st.markdown("#### Perfect 3PM Props")
            render_perfect_grouped(perfect_threes, threes_palette, "3PM")
