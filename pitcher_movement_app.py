"""
Pitcher Pitch Movement Viewer
pybaseball + matplotlib + Streamlit
"""

import warnings
warnings.filterwarnings("ignore")

import datetime
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import streamlit as st
from pybaseball import statcast_pitcher, playerid_lookup

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="MLB Pitcher Movement Viewer",
    page_icon="⚾",
    layout="wide",
)

st.title("⚾ MLB Pitcher Pitch Movement Viewer")
st.caption("Statcast データをもとに投手の球種別変化量を可視化します")

# ============================================================
# 定数
# ============================================================
PITCH_LABEL = {
    "FF": "Four-Seam (FF)",
    "SI": "Sinker (SI)",
    "SL": "Slider (SL)",
    "ST": "Sweeper (ST)",
    "CU": "Curveball (CU)",
    "KC": "Knuckle-Curve (KC)",
    "CH": "Changeup (CH)",
    "FS": "Split-Finger (FS)",
    "FC": "Cutter (FC)",
    "EP": "Eephus (EP)",
    "KN": "Knuckleball (KN)",
    "FO": "Forkball (FO)",
    "SC": "Screwball (SC)",
    "CS": "Slow Curve (CS)",
    "PO": "Pitchout (PO)",
}

COLORS = [
    "#E63946", "#457B9D", "#2A9D8F", "#E9C46A",
    "#F4A261", "#264653", "#A8DADC", "#6D6875",
    "#B5838D", "#FFAFCC", "#BDE0FE", "#CDB4DB",
]

# シーズンの開幕・閉幕日（概算）
# 進行中のシーズンは閉幕日を None にすると今日の日付を使用
_today = datetime.date.today().strftime("%Y-%m-%d")
SEASON_DATES = {
    2017: ("2017-04-02", "2017-10-01"),
    2018: ("2018-03-29", "2018-10-01"),
    2019: ("2019-03-28", "2019-09-29"),
    2020: ("2020-07-23", "2020-09-27"),  # COVID短縮
    2021: ("2021-04-01", "2021-10-03"),
    2022: ("2022-04-07", "2022-10-05"),
    2023: ("2023-03-30", "2023-10-01"),
    2024: ("2024-03-20", "2024-09-29"),
    2025: ("2025-03-27", "2025-09-28"),
    2026: ("2026-03-26", _today),        # 進行中：今日まで取得
}

# ============================================================
# キャッシュ付き関数
# ============================================================
@st.cache_data(show_spinner="選手情報を検索中...")
def lookup_player(last_name: str, first_name: str):
    return playerid_lookup(last_name.strip(), first_name.strip() or None)

@st.cache_data(show_spinner="Statcast データを取得中（しばらくお待ちください）...")
def fetch_statcast(player_id: int, start: str, end: str) -> pd.DataFrame:
    df = statcast_pitcher(start, end, player_id=player_id)
    return df

# ============================================================
# サイドバー：検索フォーム
# ============================================================
with st.sidebar:
    st.header("🔍 選手検索")

    last_name  = st.text_input("苗字（Last Name）", placeholder="例: ohtani / kershaw")
    first_name = st.text_input("名前（First Name）", placeholder="例: shohei（省略可）")

    season = st.selectbox(
        "シーズン",
        options=list(reversed(SEASON_DATES.keys())),
        index=0,
    )

    min_pitches = st.slider("集計に含める最低投球数", 5, 50, 10)

    search_btn = st.button("検索する", type="primary", use_container_width=True)

    st.divider()
    st.caption("データソース: Baseball Savant (Statcast) via pybaseball")

# ============================================================
# メイン処理
# ============================================================
ss = st.session_state  # 短縮エイリアス

# session_state に保存済みデータがあるか確認
has_cached = ss.get("ss_raw_df") is not None

# データなし & ボタン未押下 → 初期画面
if not search_btn and not has_cached:
    st.info("← サイドバーに選手名を入力して「検索する」を押してください。")
    st.stop()

# ボタン押下時のみ検索を実行（セレクトボックス操作では再検索しない）
base_key = f"{last_name.lower()}|{first_name.lower()}|{season}"
need_lookup = search_btn and (ss.get("ss_base_key") != base_key or not has_cached)

if need_lookup:
    if not last_name:
        st.error("苗字（Last Name）は必須です。")
        st.stop()

    lookup_df = lookup_player(last_name, first_name)

    if lookup_df.empty:
        st.error(f"「{last_name} {first_name}」に一致する選手が見つかりませんでした。スペルを確認してください。")
        st.stop()

    ss.ss_lookup_df  = lookup_df
    ss.ss_base_key   = base_key
    ss.ss_raw_df     = None   # 前のデータを破棄
    ss.ss_full_key   = ""

# lookup_df を session_state から復元
lookup_df = ss.get("ss_lookup_df")
if lookup_df is None or lookup_df.empty:
    st.info("← サイドバーに選手名を入力して「検索する」を押してください。")
    st.stop()

# --- 1. 複数候補の選択 ---
if len(lookup_df) > 1:
    options = {
        f"{row['name_first'].title()} {row['name_last'].title()} "
        f"(MLB: {int(row['mlb_played_first']) if pd.notna(row['mlb_played_first']) else '?'}"
        f"–{int(row['mlb_played_last']) if pd.notna(row['mlb_played_last']) else '?'})": idx
        for idx, row in lookup_df.iterrows()
    }
    saved_label  = ss.get("ss_chosen_label", list(options.keys())[0])
    default_idx  = list(options.keys()).index(saved_label) if saved_label in options else 0
    chosen_label = st.selectbox("複数の候補が見つかりました。選手を選んでください:",
                                list(options.keys()), index=default_idx)
    chosen_row   = lookup_df.loc[options[chosen_label]]
else:
    chosen_label = None
    chosen_row   = lookup_df.iloc[0]

player_id   = int(chosen_row["key_mlbam"])
player_name = f"{chosen_row['name_first'].title()} {chosen_row['name_last'].title()}"
full_key    = f"{base_key}|{player_id}"

# --- 2. Statcast 取得（選手または季節が変わった場合のみ）---
if ss.get("ss_full_key") != full_key or ss.get("ss_raw_df") is None:
    start_date, end_date = SEASON_DATES[season]
    raw_df = fetch_statcast(player_id, start_date, end_date)
    ss.ss_raw_df        = raw_df
    ss.ss_player_name   = player_name
    ss.ss_player_id     = player_id
    ss.ss_full_key      = full_key
    ss.ss_chosen_label  = chosen_label
    ss.ss_season        = season
else:
    raw_df      = ss.ss_raw_df
    player_name = ss.ss_player_name
    season      = ss.ss_season

raw_df = ss.ss_raw_df

st.subheader(f"{player_name}  —  {ss.ss_season} シーズン")
st.caption(f"MLBAM ID: {player_id}")

if raw_df is None or raw_df.empty:
    st.warning(
        f"{player_name} の {ss.ss_season} シーズンの投手データが見つかりませんでした。\n\n"
        "考えられる原因:\n"
        "- その年は投手として登板していない（例: DH 専念・故障）\n"
        "- Statcast 収録対象外のシーズン（2014 以前）\n"
        "- 名前のスペルが異なる"
    )
    st.stop()

# --- 3. データ取得列の定義 ---
COLS = ["pitch_type", "pfx_x", "pfx_z", "release_speed", "plate_x", "plate_z",
        "sz_top", "sz_bot", "release_spin_rate", "type", "description",
        "estimated_woba_using_speedangle", "launch_speed", "launch_angle",
        "game_date", "game_pk", "home_team", "away_team", "inning",
        # 新規追加
        "arm_angle",
        "release_pos_x", "release_pos_y", "release_pos_z",
        "release_extension",
        "spin_axis"]
available = [c for c in COLS if c in raw_df.columns]
df_all = raw_df[available].dropna(subset=["pitch_type", "pfx_x", "pfx_z",
                                           "release_speed", "plate_x", "plate_z"]).copy()
df_all["pfx_x_in"] = df_all["pfx_x"] * 12
df_all["pfx_z_in"] = df_all["pfx_z"] * 12
if "game_date" in df_all.columns:
    df_all["game_date"] = pd.to_datetime(df_all["game_date"]).dt.date

# ============================================================
# 3-A. 試合ログ & 試合フィルタ
# ============================================================
if "game_date" in df_all.columns and "home_team" in df_all.columns:

    # 試合ごとの集計
    game_log = (
        df_all.groupby(["game_date", "game_pk", "home_team", "away_team"])
        .agg(
            pitches=("pitch_type", "size"),
            avg_velo=("release_speed", "mean"),
            innings=("inning", "max") if "inning" in df_all.columns else ("pitch_type", "size"),
        )
        .reset_index()
        .sort_values("game_date")
    )
    game_log["対戦"] = game_log["away_team"] + "  @  " + game_log["home_team"]
    game_log["試合日"] = game_log["game_date"].astype(str)

    # 表示用テーブル
    with st.expander(f"📅 試合ログ（全 {len(game_log)} 登板）", expanded=False):
        log_disp = game_log[["試合日", "対戦", "pitches", "avg_velo", "innings"]].copy()
        log_disp.columns = ["試合日", "対戦カード", "投球数", "平均球速 (mph)", "最終イニング"]
        log_disp["平均球速 (mph)"] = log_disp["平均球速 (mph)"].round(1)
        st.dataframe(log_disp.set_index("試合日"), use_container_width=True)

    # 試合フィルタ セレクトボックス
    game_options = ["全試合（シーズン合算）"] + [
        f"{row['試合日']}  {row['対戦']}  ({int(row['pitches'])} 球)"
        for _, row in game_log.iterrows()
    ]
    selected_game = st.selectbox("🎮 表示する試合を選択", game_options)

    if selected_game == "全試合（シーズン合算）":
        df = df_all.copy()
        game_label = f"{ss.ss_season} シーズン合算"
    else:
        # 選択した game_pk で絞り込む
        idx = game_options.index(selected_game) - 1
        gk  = game_log.iloc[idx]["game_pk"]
        df  = df_all[df_all["game_pk"] == gk].copy()
        gd  = game_log.iloc[idx]["試合日"]
        opp = game_log.iloc[idx]["対戦"]
        game_label = f"{gd}  {opp}"
else:
    df = df_all.copy()
    game_label = f"{ss.ss_season} シーズン合算"

# スイング・空振り判定
SWING_DESC = {"swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
              "hit_into_play", "hit_into_play_no_out", "hit_into_play_score"}
WHIFF_DESC = {"swinging_strike", "swinging_strike_blocked"}
CSW_DESC   = {"swinging_strike", "swinging_strike_blocked", "called_strike"}

# ============================================================
# 4. 球種別集計
# ============================================================
def pitch_summary_stats(group):
    total = len(group)
    swings = group["description"].isin(SWING_DESC).sum() if "description" in group else 0
    whiffs = group["description"].isin(WHIFF_DESC).sum() if "description" in group else 0
    csw    = group["description"].isin(CSW_DESC).sum()   if "description" in group else 0
    strikes = (group["type"] == "S").sum() + (group["type"] == "X").sum() \
              if "type" in group else 0

    stats = {
        "count":      total,
        "avg_speed":  group["release_speed"].mean(),
        "avg_pfx_x":  group["pfx_x_in"].mean(),
        "avg_pfx_z":  group["pfx_z_in"].mean(),
        "strike_pct": strikes / total * 100 if total else 0,
        "whiff_pct":  whiffs  / swings * 100 if swings else 0,
        "csw_pct":    csw     / total  * 100 if total else 0,
    }
    if "release_spin_rate" in group:
        stats["avg_spin"] = group["release_spin_rate"].mean()
    if "estimated_woba_using_speedangle" in group:
        in_play = group["estimated_woba_using_speedangle"].dropna()
        stats["xwoba"] = in_play.mean() if len(in_play) else float("nan")
    return pd.Series(stats)

summary = (
    df.groupby("pitch_type")
    .apply(pitch_summary_stats, include_groups=False)
    .reset_index()
)
summary = summary[summary["count"] >= min_pitches].copy()

if summary.empty:
    st.warning(f"最低投球数 {min_pitches} 球以上の球種データがありません。スライダーの値を下げてみてください。")
    st.stop()

total_pitches = summary["count"].sum()
summary["usage_pct"] = summary["count"] / total_pitches * 100
summary["label"]     = summary["pitch_type"].map(lambda c: PITCH_LABEL.get(c, c))
summary = summary.sort_values("count", ascending=False).reset_index(drop=True)

pitch_colors = {
    row["pitch_type"]: COLORS[i % len(COLORS)]
    for i, row in summary.iterrows()
}

# ============================================================
# 5. Pitch Summary テーブル
# ============================================================
st.subheader("📊 Pitch Summary")

tbl = summary[["label", "count", "usage_pct", "avg_speed", "avg_pfx_x",
               "avg_pfx_z", "strike_pct", "whiff_pct", "csw_pct"]].copy()

# オプション列
if "avg_spin" in summary.columns:
    tbl["avg_spin"] = summary["avg_spin"]
if "xwoba" in summary.columns:
    tbl["xwoba"] = summary["xwoba"]

col_rename = {
    "label":      "球種",
    "count":      "投球数",
    "usage_pct":  "使用率 %",
    "avg_speed":  "平均球速 (mph)",
    "avg_pfx_x":  "横変化 (in)",
    "avg_pfx_z":  "縦変化 (in)",
    "strike_pct": "ストライク %",
    "whiff_pct":  "空振り %",
    "csw_pct":    "CSW %",
    "avg_spin":   "回転数 (rpm)",
    "xwoba":      "xwOBA",
}
tbl = tbl.rename(columns=col_rename).set_index("球種")

# 数値フォーマット
fmt = {
    "投球数":          "{:.0f}",
    "使用率 %":        "{:.1f}",
    "平均球速 (mph)":  "{:.1f}",
    "横変化 (in)":     "{:.1f}",
    "縦変化 (in)":     "{:.1f}",
    "ストライク %":    "{:.1f}",
    "空振り %":        "{:.1f}",
    "CSW %":          "{:.1f}",
    "回転数 (rpm)":    "{:.0f}",
    "xwOBA":          "{:.3f}",
}
styled = tbl.style.format({k: v for k, v in fmt.items() if k in tbl.columns})

# 空振り % と CSW % を高いほど緑でハイライト
for col in ["空振り %", "CSW %"]:
    if col in tbl.columns:
        styled = styled.background_gradient(cmap="RdYlGn", subset=[col], vmin=0, vmax=40)
# xwOBA は低いほど緑
if "xwOBA" in tbl.columns:
    styled = styled.background_gradient(cmap="RdYlGn_r", subset=["xwOBA"], vmin=0.2, vmax=0.5)

st.dataframe(styled, use_container_width=True)

with st.expander("📌 指標の説明"):
    st.markdown("""
| 指標 | 説明 |
|------|------|
| 使用率 % | 全投球に占めるその球種の割合 |
| ストライク % | ストライク（見逃し・空振り・ファウル・インプレー）の割合 |
| 空振り % | スイングのうち空振りになった割合（Whiff Rate） |
| CSW % | Called Strike + Whiff の合計割合（投手の支配力の指標） |
| 回転数 | リリース時の平均スピン（rpm） |
| xwOBA | インプレー時の推定加重出塁率（低いほど投手有利） |
""")

# --- 5. 描画 ---
BG         = "#161b22"
GRID_COLOR = "#30363d"
TEXT_COLOR = "white"

fig = plt.figure(figsize=(18, 14), facecolor="#0d1117")
fig.suptitle(
    f"{player_name}  —  Pitch Movement Summary  ({game_label})",
    color="white", fontsize=18, fontweight="bold", y=0.98,
)

gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.35,
                      left=0.07, right=0.97, top=0.93, bottom=0.07)

ax_scatter = fig.add_subplot(gs[0, :2])
ax_legend  = fig.add_subplot(gs[0, 2])
ax_speed   = fig.add_subplot(gs[1, 0])
ax_pfx_x   = fig.add_subplot(gs[1, 1])
ax_pfx_z   = fig.add_subplot(gs[1, 2])

for ax in [ax_scatter, ax_speed, ax_pfx_x, ax_pfx_z]:
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT_COLOR)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")

# 変化量散布図
ax_scatter.axhline(0, color="#556270", linewidth=1)
ax_scatter.axvline(0, color="#556270", linewidth=1)

for _, row in summary.iterrows():
    c    = pitch_colors[row["pitch_type"]]
    mask = df["pitch_type"] == row["pitch_type"]
    ax_scatter.scatter(df.loc[mask, "pfx_x_in"], df.loc[mask, "pfx_z_in"],
                       color=c, alpha=0.15, s=6, zorder=2)
    ax_scatter.scatter(row["avg_pfx_x"], row["avg_pfx_z"],
                       color=c, s=140, zorder=5, edgecolors="white", linewidths=0.8)
    ax_scatter.annotate(row["pitch_type"],
                        (row["avg_pfx_x"], row["avg_pfx_z"]),
                        textcoords="offset points", xytext=(6, 4),
                        fontsize=9, color=c, fontweight="bold")

ax_scatter.set_xlabel("Horizontal Break (in)  ←  Glove Side  |  Arm Side  →", fontsize=10, color=TEXT_COLOR)
ax_scatter.set_ylabel("Vertical Break (in)  ↑ Rise  |  Drop ↓", fontsize=10, color=TEXT_COLOR)
ax_scatter.set_title("Pitch Movement Map (pfx_x vs pfx_z)", fontsize=12, fontweight="bold", color=TEXT_COLOR)

# 凡例
ax_legend.set_facecolor(BG)
ax_legend.axis("off")
patches = [
    mpatches.Patch(color=pitch_colors[row["pitch_type"]],
                   label=f"{row['label']}  n={row['count']:,}")
    for _, row in summary.iterrows()
]
ax_legend.legend(handles=patches, loc="center", frameon=False,
                 labelcolor=TEXT_COLOR, fontsize=9.5)
ax_legend.set_title("Pitch Types", color=TEXT_COLOR, fontsize=11, fontweight="bold")

# 平均球速
colors_bar = [pitch_colors[p] for p in summary["pitch_type"]]
bars = ax_speed.barh(summary["label"], summary["avg_speed"], color=colors_bar, height=0.6)
ax_speed.set_xlabel("Avg Velocity (mph)", fontsize=9, color=TEXT_COLOR)
ax_speed.set_title("Average Velocity", fontsize=11, fontweight="bold", color=TEXT_COLOR)
ax_speed.invert_yaxis()
ax_speed.tick_params(colors=TEXT_COLOR)
for bar, val in zip(bars, summary["avg_speed"]):
    ax_speed.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                  f"{val:.1f}", va="center", color=TEXT_COLOR, fontsize=8)

# 横変化
bars2 = ax_pfx_x.barh(summary["label"], summary["avg_pfx_x"], color=colors_bar, height=0.6)
ax_pfx_x.axvline(0, color="white", linewidth=0.8)
ax_pfx_x.set_xlabel("Avg Horizontal Break (in)", fontsize=9, color=TEXT_COLOR)
ax_pfx_x.set_title("Horizontal Break (pfx_x)", fontsize=11, fontweight="bold", color=TEXT_COLOR)
ax_pfx_x.invert_yaxis()
ax_pfx_x.tick_params(colors=TEXT_COLOR)
for bar, val in zip(bars2, summary["avg_pfx_x"]):
    xpos = bar.get_width() + (0.2 if val >= 0 else -0.2)
    ha   = "left" if val >= 0 else "right"
    ax_pfx_x.text(xpos, bar.get_y() + bar.get_height() / 2,
                  f"{val:.1f}", va="center", ha=ha, color=TEXT_COLOR, fontsize=8)

# 縦変化
bars3 = ax_pfx_z.barh(summary["label"], summary["avg_pfx_z"], color=colors_bar, height=0.6)
ax_pfx_z.axvline(0, color="white", linewidth=0.8)
ax_pfx_z.set_xlabel("Avg Vertical Break (in)", fontsize=9, color=TEXT_COLOR)
ax_pfx_z.set_title("Vertical Break (pfx_z)", fontsize=11, fontweight="bold", color=TEXT_COLOR)
ax_pfx_z.invert_yaxis()
ax_pfx_z.tick_params(colors=TEXT_COLOR)
for bar, val in zip(bars3, summary["avg_pfx_z"]):
    xpos = bar.get_width() + (0.2 if val >= 0 else -0.2)
    ha   = "left" if val >= 0 else "right"
    ax_pfx_z.text(xpos, bar.get_y() + bar.get_height() / 2,
                  f"{val:.1f}", va="center", ha=ha, color=TEXT_COLOR, fontsize=8)

# --- 6. Movement chart を Streamlit に表示 ---
st.pyplot(fig, use_container_width=True)
plt.close(fig)

# ============================================================
# 7. Pitch Locations
# ============================================================
st.divider()
st.subheader("📍 Pitch Locations")

# ストライクゾーン寸法（平均値 or デフォルト）
sz_top = df["sz_top"].mean() if "sz_top" in df.columns and df["sz_top"].notna().any() else 3.5
sz_bot = df["sz_bot"].mean() if "sz_bot" in df.columns and df["sz_bot"].notna().any() else 1.5
PLATE_HALF = 17 / 24  # ホームプレートの半幅 (ft)

pitch_types = summary["pitch_type"].tolist()
n = len(pitch_types)

# グリッド列数（最大 4列）
MAX_COLS = 4
n_cols = min(n, MAX_COLS)
n_rows = (n + n_cols - 1) // n_cols

fig2, axes = plt.subplots(
    n_rows, n_cols,
    figsize=(4.5 * n_cols, 5 * n_rows),
    facecolor="#0d1117",
)
fig2.suptitle(
    f"{player_name}  —  Pitch Locations  ({game_label})\n"
    f"Catcher's perspective  (Left = 1B side)",
    color="white", fontsize=14, fontweight="bold", y=1.01,
)

# axes を常に 1D リストに統一
if n == 1:
    axes = [axes]
elif n_rows == 1:
    axes = list(axes)
else:
    axes = [ax for row in axes for ax in row]

def draw_zone(ax, sz_t, sz_b, plate_h):
    """ストライクゾーンとホームプレートを描画"""
    # ストライクゾーン
    zone = plt.Rectangle(
        (-plate_h, sz_b), plate_h * 2, sz_t - sz_b,
        linewidth=1.5, edgecolor="white", facecolor="none", zorder=3,
    )
    ax.add_patch(zone)
    # 9分割グリッド線
    for x in [-plate_h / 3, plate_h / 3]:
        ax.axvline(x, color="#555", linewidth=0.6, zorder=2,
                   ymin=(sz_b - 1.0) / (sz_t + 1.0 - 1.0 + 0.5),
                   ymax=(sz_t - 1.0) / (sz_t + 1.0 - 1.0 + 0.5))
    for z in [sz_b + (sz_t - sz_b) / 3, sz_b + 2 * (sz_t - sz_b) / 3]:
        ax.axhline(z, color="#555", linewidth=0.6, zorder=2,
                   xmin=((-plate_h) + 1.5) / 3.0,
                   xmax=(plate_h + 1.5) / 3.0)
    # ホームプレート（五角形）
    plate_x = [-plate_h, plate_h, plate_h, 0, -plate_h]
    plate_z = [sz_b - 0.35, sz_b - 0.35, sz_b - 0.15, sz_b - 0.05, sz_b - 0.15]
    ax.fill(plate_x, plate_z, color="#888", zorder=2)

for i, ptype in enumerate(pitch_types):
    ax = axes[i]
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=7)

    mask = df["pitch_type"] == ptype
    px = df.loc[mask, "plate_x"]
    pz = df.loc[mask, "plate_z"]
    c  = pitch_colors[ptype]
    row_s = summary[summary["pitch_type"] == ptype].iloc[0]

    # ヒートマップ的に密度を kde で表現（散布点）
    ax.scatter(px, pz, color=c, alpha=0.25, s=8, zorder=4)

    draw_zone(ax, sz_top, sz_bot, PLATE_HALF)

    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(0.5, 5.5)
    ax.set_aspect("equal")
    ax.set_title(
        f"{row_s['label']}\n"
        f"n={row_s['count']:,}  {row_s['avg_speed']:.1f} mph",
        color=c, fontsize=9, fontweight="bold",
    )
    ax.set_xlabel("plate_x (ft)", fontsize=7, color=TEXT_COLOR)
    ax.set_ylabel("plate_z (ft)", fontsize=7, color=TEXT_COLOR)

    # 打者方向ラベル
    ax.text(-2.3, 5.2, "←1B", color="#aaa", fontsize=6.5)
    ax.text( 1.7, 5.2, "3B→", color="#aaa", fontsize=6.5)

# 余った軸を非表示
for j in range(i + 1, len(axes)):
    axes[j].set_visible(False)

plt.tight_layout()
st.pyplot(fig2, use_container_width=True)
plt.close(fig2)

# ============================================================
# 8. Arm Angle & Release Point
# ============================================================
st.divider()
st.subheader("💪 Arm Angle & Release Point")

has_arm    = "arm_angle"     in df.columns and df["arm_angle"].notna().any()
has_relpos = "release_pos_x" in df.columns and df["release_pos_x"].notna().any()
has_ext    = "release_extension" in df.columns and df["release_extension"].notna().any()

if not has_arm and not has_relpos:
    st.info("このシーズンには Arm Angle / Release Point データがありません（2020年以降で利用可能）。")
else:
    n_arm_cols = sum([has_arm, has_relpos, has_ext])
    fig3, arm_axes = plt.subplots(1, n_arm_cols,
                                  figsize=(6 * n_arm_cols, 5),
                                  facecolor="#0d1117")
    if n_arm_cols == 1:
        arm_axes = [arm_axes]

    ax_idx = 0

    # --- Arm Angle ---
    if has_arm:
        arm_summary = (
            df.groupby("pitch_type")["arm_angle"]
            .mean()
            .reindex(summary["pitch_type"])
            .dropna()
        )
        ax = arm_axes[ax_idx]; ax_idx += 1
        ax.set_facecolor(BG)
        for sp in ax.spines.values(): sp.set_edgecolor(GRID_COLOR)
        ax.tick_params(colors=TEXT_COLOR)
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--", axis="x")

        labels = [summary.loc[summary["pitch_type"] == p, "label"].values[0]
                  for p in arm_summary.index]
        colors_arm = [pitch_colors[p] for p in arm_summary.index]
        bars_arm = ax.barh(labels, arm_summary.values, color=colors_arm, height=0.6)
        ax.invert_yaxis()
        ax.axvline(0, color="white", linewidth=0.8)
        for bar, val in zip(bars_arm, arm_summary.values):
            ax.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f}°", va="center", color=TEXT_COLOR, fontsize=8)
        ax.set_xlabel("Arm Angle (degrees)", fontsize=9, color=TEXT_COLOR)
        ax.set_title("Arm Angle by Pitch Type\n(+ = above horizontal, − = below)",
                     fontsize=10, fontweight="bold", color=TEXT_COLOR)
        ax.xaxis.label.set_color(TEXT_COLOR)

    # --- Release Point (catcher's view: x vs z) ---
    if has_relpos:
        ax = arm_axes[ax_idx]; ax_idx += 1
        ax.set_facecolor(BG)
        for sp in ax.spines.values(): sp.set_edgecolor(GRID_COLOR)
        ax.tick_params(colors=TEXT_COLOR)
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")

        for _, row in summary.iterrows():
            c    = pitch_colors[row["pitch_type"]]
            mask = df["pitch_type"] == row["pitch_type"]
            sub  = df.loc[mask]
            ax.scatter(sub["release_pos_x"], sub["release_pos_z"],
                       color=c, alpha=0.15, s=6, zorder=2)
            mx = sub["release_pos_x"].mean()
            mz = sub["release_pos_z"].mean()
            ax.scatter(mx, mz, color=c, s=120, zorder=5,
                       edgecolors="white", linewidths=0.8)
            ax.annotate(row["pitch_type"], (mx, mz),
                        textcoords="offset points", xytext=(5, 3),
                        fontsize=8, color=c, fontweight="bold")

        ax.set_xlabel("release_pos_x  (ft,  ← 3B side | 1B side →)",
                      fontsize=9, color=TEXT_COLOR)
        ax.set_ylabel("release_pos_z  (ft,  height)", fontsize=9, color=TEXT_COLOR)
        ax.set_title("Release Point\n(Catcher's View)", fontsize=10,
                     fontweight="bold", color=TEXT_COLOR)
        ax.xaxis.label.set_color(TEXT_COLOR)
        ax.yaxis.label.set_color(TEXT_COLOR)

    # --- Extension ---
    if has_ext:
        ext_summary = (
            df.groupby("pitch_type")["release_extension"]
            .mean()
            .reindex(summary["pitch_type"])
            .dropna()
        )
        ax = arm_axes[ax_idx]; ax_idx += 1
        ax.set_facecolor(BG)
        for sp in ax.spines.values(): sp.set_edgecolor(GRID_COLOR)
        ax.tick_params(colors=TEXT_COLOR)
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--", axis="x")

        labels_ext = [summary.loc[summary["pitch_type"] == p, "label"].values[0]
                      for p in ext_summary.index]
        colors_ext = [pitch_colors[p] for p in ext_summary.index]
        bars_ext = ax.barh(labels_ext, ext_summary.values, color=colors_ext, height=0.6)
        ax.invert_yaxis()
        for bar, val in zip(bars_ext, ext_summary.values):
            ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                    f"{val:.2f} ft", va="center", color=TEXT_COLOR, fontsize=8)
        ax.set_xlabel("Extension (ft)", fontsize=9, color=TEXT_COLOR)
        ax.set_title("Release Extension\n(distance past rubber)", fontsize=10,
                     fontweight="bold", color=TEXT_COLOR)
        ax.xaxis.label.set_color(TEXT_COLOR)

    plt.tight_layout()
    st.pyplot(fig3, use_container_width=True)
    plt.close(fig3)

# ============================================================
# 9. Active Spin  (Spin Rate + Spin Axis)
# ============================================================
st.divider()
st.subheader("🔄 Active Spin")

has_spin = "release_spin_rate" in df.columns and df["release_spin_rate"].notna().any()
has_axis = "spin_axis"         in df.columns and df["spin_axis"].notna().any()

if not has_spin:
    st.info("このシーズンにはスピンデータがありません。")
else:
    import math

    spin_summary = (
        df.groupby("pitch_type")
        .agg(
            avg_spin =("release_spin_rate", "mean"),
            avg_axis =("spin_axis",         "mean") if has_axis else ("release_spin_rate", "count"),
        )
        .reindex(summary["pitch_type"])
        .dropna(subset=["avg_spin"])
        .reset_index()
    )
    spin_summary["label"] = spin_summary["pitch_type"].map(
        lambda c: PITCH_LABEL.get(c, c))

    fig4, spin_axes = plt.subplots(
        1, 2 if has_axis else 1,
        figsize=(12 if has_axis else 6, 5),
        facecolor="#0d1117",
        subplot_kw={"polar": False},
    )
    if not has_axis:
        spin_axes = [spin_axes]

    # --- Spin Rate bar ---
    ax_sr = spin_axes[0]
    ax_sr.set_facecolor(BG)
    for sp in ax_sr.spines.values(): sp.set_edgecolor(GRID_COLOR)
    ax_sr.tick_params(colors=TEXT_COLOR)
    ax_sr.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--", axis="x")
    colors_spin = [pitch_colors[p] for p in spin_summary["pitch_type"]]
    bars_sr = ax_sr.barh(spin_summary["label"], spin_summary["avg_spin"],
                         color=colors_spin, height=0.6)
    ax_sr.invert_yaxis()
    for bar, val in zip(bars_sr, spin_summary["avg_spin"]):
        ax_sr.text(bar.get_width() + 20, bar.get_y() + bar.get_height() / 2,
                   f"{val:.0f}", va="center", color=TEXT_COLOR, fontsize=8)
    ax_sr.set_xlabel("Avg Spin Rate (rpm)", fontsize=9, color=TEXT_COLOR)
    ax_sr.set_title("Spin Rate by Pitch Type", fontsize=10,
                    fontweight="bold", color=TEXT_COLOR)
    ax_sr.xaxis.label.set_color(TEXT_COLOR)

    # --- Spin Axis clock chart (polar) ---
    if has_axis:
        ax_sa = fig4.add_subplot(1, 2, 2, polar=True)
        ax_sa.set_facecolor(BG)
        ax_sa.tick_params(colors=TEXT_COLOR, labelsize=7)
        ax_sa.set_theta_direction(-1)        # 時計回り
        ax_sa.set_theta_offset(math.pi / 2)  # 12時を上に

        # 時計の数字ラベル
        hour_labels = ["12", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
        ax_sa.set_xticks([math.radians(i * 30) for i in range(12)])
        ax_sa.set_xticklabels(hour_labels, color=TEXT_COLOR, fontsize=8)
        ax_sa.set_yticks([])
        ax_sa.set_ylim(0, 1)
        ax_sa.grid(color=GRID_COLOR, linewidth=0.5)
        ax_sa.set_facecolor(BG)
        for sp in ax_sa.spines.values(): sp.set_edgecolor(GRID_COLOR)

        for _, row in spin_summary.iterrows():
            if pd.isna(row["avg_axis"]):
                continue
            angle_deg = row["avg_axis"]          # Statcast: 0=12時(バックスピン)
            angle_rad = math.radians(angle_deg)
            c = pitch_colors[row["pitch_type"]]
            ax_sa.annotate(
                "", xy=(angle_rad, 0.82), xytext=(0, 0),
                arrowprops=dict(arrowstyle="->", color=c, lw=2.0),
            )
            ax_sa.text(angle_rad, 0.95, row["pitch_type"],
                       ha="center", va="center", color=c,
                       fontsize=8, fontweight="bold")

        ax_sa.set_title("Spin Axis (Clock Face)\n12=Backspin  6=Topspin",
                        color=TEXT_COLOR, fontsize=10, fontweight="bold", pad=15)

    plt.tight_layout()
    st.pyplot(fig4, use_container_width=True)
    plt.close(fig4)

# ============================================================
# 10. Movement Profile  (Velo × Break の詳細比較)
# ============================================================
st.divider()
st.subheader("📐 Movement Profile")

fig5, (ax_mp1, ax_mp2) = plt.subplots(1, 2, figsize=(14, 6), facecolor="#0d1117")

for ax in [ax_mp1, ax_mp2]:
    ax.set_facecolor(BG)
    for sp in ax.spines.values(): sp.set_edgecolor(GRID_COLOR)
    ax.tick_params(colors=TEXT_COLOR)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--")
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)

# --- Velo vs Total Break ---
for _, row in summary.iterrows():
    c           = pitch_colors[row["pitch_type"]]
    total_break = math.sqrt(row["avg_pfx_x"] ** 2 + row["avg_pfx_z"] ** 2)
    ax_mp1.scatter(row["avg_speed"], total_break,
                   color=c, s=200, zorder=5, edgecolors="white", linewidths=0.8)
    ax_mp1.annotate(
        f"{row['pitch_type']}\n{row['avg_speed']:.1f} mph",
        (row["avg_speed"], total_break),
        textcoords="offset points", xytext=(6, 4),
        fontsize=8, color=c, fontweight="bold",
    )
ax_mp1.set_xlabel("Avg Velocity (mph)", fontsize=10, color=TEXT_COLOR)
ax_mp1.set_ylabel("Total Break — √(pfx_x² + pfx_z²)  (in)", fontsize=10, color=TEXT_COLOR)
ax_mp1.set_title("Velocity vs Total Break", fontsize=12, fontweight="bold", color=TEXT_COLOR)

# --- H-Break vs V-Break (矢印で原点から各球種へ) ---
ax_mp2.axhline(0, color="#556270", linewidth=1)
ax_mp2.axvline(0, color="#556270", linewidth=1)
for _, row in summary.iterrows():
    c = pitch_colors[row["pitch_type"]]
    ax_mp2.annotate(
        "",
        xy=(row["avg_pfx_x"], row["avg_pfx_z"]),
        xytext=(0, 0),
        arrowprops=dict(arrowstyle="->", color=c, lw=2.0),
    )
    ax_mp2.scatter(row["avg_pfx_x"], row["avg_pfx_z"],
                   color=c, s=120, zorder=5, edgecolors="white", linewidths=0.8)
    ax_mp2.annotate(
        f"{row['pitch_type']}",
        (row["avg_pfx_x"], row["avg_pfx_z"]),
        textcoords="offset points", xytext=(6, 4),
        fontsize=9, color=c, fontweight="bold",
    )
ax_mp2.set_xlabel("Horizontal Break (in)  ← Glove | Arm →", fontsize=10, color=TEXT_COLOR)
ax_mp2.set_ylabel("Vertical Break (in)  ↑ Rise | Drop ↓", fontsize=10, color=TEXT_COLOR)
ax_mp2.set_title("Movement Profile\n(Arrow = direction & magnitude from gravity baseline)",
                 fontsize=11, fontweight="bold", color=TEXT_COLOR)

plt.tight_layout()
st.pyplot(fig5, use_container_width=True)
plt.close(fig5)

# ============================================================
# 11. Pitch Frequency  (試合ごとの球種使用率推移)
# ============================================================
st.divider()
st.subheader("📈 Pitch Frequency")

if "game_date" not in df_all.columns:
    st.info("試合日データがないため Pitch Frequency を表示できません。")
else:
    # df_all を使用（試合フィルタに依存しない）
    freq_df = df_all[df_all["pitch_type"].isin(summary["pitch_type"])].copy()
    freq_df["game_date"] = pd.to_datetime(freq_df["game_date"])

    # 試合×球種ごとの投球数
    game_pitch_cnt = (
        freq_df.groupby(["game_date", "pitch_type"])
        .size()
        .reset_index(name="cnt")
    )
    game_total = freq_df.groupby("game_date").size().reset_index(name="total")
    game_pitch_cnt = game_pitch_cnt.merge(game_total, on="game_date")
    game_pitch_cnt["pct"] = game_pitch_cnt["cnt"] / game_pitch_cnt["total"] * 100

    # ピボット
    pivot = game_pitch_cnt.pivot(index="game_date", columns="pitch_type", values="pct").fillna(0)
    pivot = pivot[[p for p in summary["pitch_type"] if p in pivot.columns]]
    pitch_order = list(pivot.columns)

    fig6, (ax_f1, ax_f2) = plt.subplots(2, 1, figsize=(16, 10), facecolor="#0d1117")

    for ax in [ax_f1, ax_f2]:
        ax.set_facecolor(BG)
        for sp in ax.spines.values(): sp.set_edgecolor(GRID_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=8)
        ax.xaxis.label.set_color(TEXT_COLOR)
        ax.yaxis.label.set_color(TEXT_COLOR)
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, linestyle="--", axis="y")

    dates = pivot.index

    # --- 積み上げ面グラフ ---
    bottom = [0] * len(dates)
    for ptype in pitch_order:
        vals = pivot[ptype].values
        c    = pitch_colors[ptype]
        lbl  = PITCH_LABEL.get(ptype, ptype)
        ax_f1.fill_between(dates, bottom, [b + v for b, v in zip(bottom, vals)],
                           alpha=0.75, color=c, label=lbl)
        bottom = [b + v for b, v in zip(bottom, vals)]

    ax_f1.set_ylim(0, 100)
    ax_f1.set_ylabel("Usage %", fontsize=9, color=TEXT_COLOR)
    ax_f1.set_title("Pitch Usage % per Game (Stacked)", fontsize=11,
                    fontweight="bold", color=TEXT_COLOR)
    ax_f1.legend(loc="upper left", frameon=False, labelcolor=TEXT_COLOR,
                 fontsize=8, ncol=2)
    ax_f1.set_xlim(dates.min(), dates.max())

    # --- 折れ線グラフ（球種別推移） ---
    for ptype in pitch_order:
        c   = pitch_colors[ptype]
        lbl = PITCH_LABEL.get(ptype, ptype)
        ax_f2.plot(dates, pivot[ptype].values, color=c, linewidth=1.8,
                   marker="o", markersize=3, label=lbl)

    ax_f2.set_ylabel("Usage %", fontsize=9, color=TEXT_COLOR)
    ax_f2.set_xlabel("Game Date", fontsize=9, color=TEXT_COLOR)
    ax_f2.set_title("Pitch Usage % per Game (Line)", fontsize=11,
                    fontweight="bold", color=TEXT_COLOR)
    ax_f2.legend(loc="upper left", frameon=False, labelcolor=TEXT_COLOR,
                 fontsize=8, ncol=2)
    ax_f2.set_xlim(dates.min(), dates.max())

    plt.tight_layout()
    st.pyplot(fig6, use_container_width=True)
    plt.close(fig6)
