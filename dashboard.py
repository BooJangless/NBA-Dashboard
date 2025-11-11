import os
import glob
import pandas as pd
import streamlit as st
from PIL import Image

st.set_page_config(page_title="NBA Team Dashboard", layout="wide")

st.title("🏀 NBA Team Dashboard")
st.write("Lux sports data experience: Player Points & Assists with Opponents & Game Times (PST)")

excel_files = glob.glob("*_stats.xlsx")

if not excel_files:
    st.error("No Excel files found. Run your NBA stats script first.")
else:
    def pretty_label(filename):
        base = filename.replace("_stats.xlsx", "")
        parts = base.split("_")
        if "-" in parts[-1]:
            season = parts[-1]
            team = " ".join(parts[:-1])
        else:
            season = "Unknown"
            team = " ".join(parts)
        return f"{team} ({season})"

    label_to_file = {pretty_label(f): f for f in excel_files}
    selected_label = st.selectbox("Choose a team & season:", sorted(label_to_file.keys()))
    selected_file = label_to_file[selected_label]
    st.success(f"Loaded: {selected_label}")

    # Logo
    team_name_part = selected_label.split(" (")[0]
    logo_path = f"logos/{team_name_part.replace(' ', '_')}.png"
    if os.path.exists(logo_path):
        st.image(Image.open(logo_path), width=120)

    # Load all sheets
    points_df = pd.read_excel(selected_file, sheet_name="Points")
    assists_df = pd.read_excel(selected_file, sheet_name="Assists")
    avg_points_df = pd.read_excel(selected_file, sheet_name="Avg Points")
    avg_assists_df = pd.read_excel(selected_file, sheet_name="Avg Assists")

    # Helper: compute trends for Quick Bets
    def compute_trends(df: pd.DataFrame, thresholds, stat_label: str) -> pd.DataFrame:
        df_sorted = df.sort_values("Game Time (PST)")
        players = [c for c in df.columns if c not in ["Game Time (PST)", "Opponent"]]
        records = []

        for player in players:
            series = df_sorted[player].fillna(0).astype(float)
            for t in thresholds:
                total_hits = int((series >= t).sum())
                current_streak = 0
                longest_streak = 0
                for val in series:
                    if val >= t:
                        current_streak += 1
                        if current_streak > longest_streak:
                            longest_streak = current_streak
                    else:
                        current_streak = 0
                if longest_streak >= 3:  # only keep meaningful trends
                    records.append(
                        {
                            "Player": player,
                            "Prop": f"{t}+ {stat_label}",
                            "Total Games Hit": total_hits,
                            "Longest Streak": longest_streak,
                        }
                    )
        if not records:
            return pd.DataFrame(columns=["Player", "Prop", "Total Games Hit", "Longest Streak"])
        return pd.DataFrame(records).sort_values(
            ["Longest Streak", "Total Games Hit"], ascending=False
        )

    # Main mode selector
    view_choice = st.radio("Select View:", ["Player Points", "Player Assists", "Quick Bets"])

    # ========== PLAYER POINTS / ASSISTS VIEWS ==========
    if view_choice in ["Player Points", "Player Assists"]:
        if view_choice == "Player Points":
            df = points_df
            stat_type = "Points"
            avg_df = avg_points_df

            # Lux gold palette
            highlight_bg = "#FFF4D2"   # soft gold / champagne
            highlight_text = "#4A3B1C" # rich brown
            threshold = 10
            legend_text = "🥇 Gold highlight = Player scored more than 10 points"
        else:
            df = assists_df
            stat_type = "Assists"
            avg_df = avg_assists_df

            # Lux royal palette
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

        # Quick averages (TikTok mode)
        st.markdown(f"### ⚡ Quick Averages ({stat_type})")
        if not avg_df.empty:
            avg_col = avg_df.columns[-1]
            st.dataframe(
                avg_df.style.format({avg_col: "{:.2f}"}),
                use_container_width=True
            )
        else:
            st.info("No average data available.")

    # ========== QUICK BETS VIEW ==========
    else:
        st.subheader("⚡ Quick Bets – Trend Finder")
        st.write(
            "Showing only players who have hit key prop lines in **at least 3 games in a row**."
        )

        # Points trends: 10+, 15+, 20+, 25+, 30+, 35+
        points_trends = compute_trends(points_df, [10, 15, 20, 25, 30, 35], "Points")
        # Assists trends: 3+, 5+, 7+, 10+
        assists_trends = compute_trends(assists_df, [3, 5, 7, 10], "Assists")

        # Points section
        st.markdown("### 🥇 Points Props Trends")
        if points_trends.empty:
            st.info("No strong points trends (3+ game streaks) found for this team/season.")
        else:
            # Bullet-style list like the NFL example
            for _, row in points_trends.iterrows():
                line = (
                    f"- **{row['Player']} {row['Prop']}** "
                    f"({int(row['Total Games Hit'])} games, "
                    f"longest streak {int(row['Longest Streak'])})"
                )
                st.markdown(line)

        # Assists section
        st.markdown("### 👑 Assists Props Trends")
        if assists_trends.empty:
            st.info("No strong assists trends (3+ game streaks) found for this team/season.")
        else:
            for _, row in assists_trends.iterrows():
                line = (
                    f"- **{row['Player']} {row['Prop']}** "
                    f"({int(row['Total Games Hit'])} games, "
                    f"longest streak {int(row['Longest Streak'])})"
                )
                st.markdown(line)
