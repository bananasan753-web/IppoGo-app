import streamlit as st
from datetime import datetime, date
import zoneinfo
import random
import base64
import os
import time
import calendar as cal_module
import json
from supabase import create_client, Client

# 日本標準時（JST）の定義
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


def get_now_jst():
    """アプリ内時間を常に日本時間に統一するヘルパー関数"""
    return datetime.now(JST)


# --- メニュー選択ボタンなどの文字を大きくするCSS ---
st.markdown("""
    <style>
    div[data-testid="stColumn"] button p {
        font-size: 24px !important;
        font-weight: bold !important;
    }
    /* お菓子の見た目を可愛くホバーできるようにするCSS */
    .candy-item {
        display: inline-block;
        font-size: 28px;
        margin: 4px;
        cursor: pointer;
    }
    </style>
    """, unsafe_allow_html=True)


# =====================================================
# 🌐 Supabase 接続設定
# =====================================================
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


try:
    supabase = init_supabase()
except Exception as e:
    st.error("Supabaseへの接続に失敗しました。Secretsの設定を確認してください。")
    st.stop()

# =====================================================
# 🔊 効果音まわりの設定
# =====================================================
SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "決定ボタンを押す23.mp3")
ACHIEVE_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "クイズ正解1.mp3")
JAR_FULL_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "歓声と拍手.mp3")

JAR_SIZE_LABELS = {30: "S", 50: "M", 100: "L"}


def jar_size_label(capacity: int) -> str:
    return JAR_SIZE_LABELS.get(capacity, "?")


# =====================================================
# 💾 セーブデータ（Supabaseクラウド連携）
# =====================================================
PERSISTENT_KEYS = [
    "target_list",
    "jar_capacity",
    "jar_candies",
    "all_candy_log",
    "jar_complete_log",
    "last_jar_capacity",
    "course_km",
    "course_complete_sound_played",
    "course_complete_companion_message",
    "course_run_log",
    "course_complete_log",
    "companion",
    "goal_complete_log",
    "calendar_stickers",
    "calendar_notes",
    "sticker_type",
    "sticker_color",
    "daily_schedule",  # 一日のスケジュール（予定／記録）
]

PERSISTENT_DEFAULTS = {
    "target_list": [],
    "jar_capacity": 30,
    "jar_candies": [],
    "all_candy_log": [],
    "jar_complete_log": [],
    "last_jar_capacity": 30,
    "course_km": {},
    "course_complete_sound_played": {},
    "course_complete_companion_message": {},
    "course_run_log": [],
    "course_complete_log": [],
    "companion": None,
    "goal_complete_log": [],
    "calendar_stickers": {},
    "calendar_notes": {},
    "sticker_type": "circle",
    "sticker_color": "赤",
    "daily_schedule": {},
}


def check_user_exists(uid: str) -> bool:
    """Supabaseに指定ユーザーのデータが存在するか確認する"""
    try:
        response = supabase.table("user_data").select("id").eq("id", uid).execute()
        return bool(response.data and len(response.data) > 0)
    except Exception:
        return False


def load_progress(uid) -> bool:
    """
    Supabaseから指定ユーザーのデータを読み込む。
    成功したらTrue、データが見つからなかった／通信に失敗した場合はFalseを返す。
    ★重要：失敗時に黙って進捗をリセットしない（誤ってセーブデータを上書きする事故を防ぐため）。
    """
    try:
        response = supabase.table("user_data").select("*").eq("id", uid).execute()
        if response.data and len(response.data) > 0:
            saved_data = response.data[0].get("data", {})
            for key in PERSISTENT_KEYS:
                if key in saved_data:
                    st.session_state[key] = saved_data[key]
                else:
                    default_val = PERSISTENT_DEFAULTS[key]
                    st.session_state[key] = type(default_val)(default_val) if isinstance(default_val,
                                                                                         (list, dict)) else default_val
            return True
        return False
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return False


def save_progress():
    """現在の進捗を Supabase に保存する"""
    uid = st.session_state.get("current_user")
    if not uid:
        return
    data_to_save = {
        key: st.session_state[key]
        for key in PERSISTENT_KEYS
        if key in st.session_state
    }
    try:
        response = supabase.table("user_data").select("*").eq("id", uid).execute()
        if response.data and len(response.data) > 0:
            supabase.table("user_data").update({"data": data_to_save}).eq("id", uid).execute()
        else:
            supabase.table("user_data").insert({"id": uid, "data": data_to_save}).execute()
    except Exception as e:
        pass


def reset_progress_in_memory():
    """メモリ上の進捗を初期値に戻す"""
    for key, default_value in PERSISTENT_DEFAULTS.items():
        if isinstance(default_value, (list, dict)):
            st.session_state[key] = type(default_value)(default_value)
        else:
            st.session_state[key] = default_value


def reset_progress():
    """進捗を初期化しSupabaseからも削除する"""
    uid = st.session_state.get("current_user")
    reset_progress_in_memory()
    if uid:
        try:
            supabase.table("user_data").delete().eq("id", uid).execute()
        except Exception:
            pass


# =====================================================
# 🏃 ランニングコース共通設定 & SVG処理
# =====================================================
RUNNING_COURSES = {
    "village": {"name": "一歩村一周コース", "distance": 30, "tier": "🟢 初級", "bonus": None, "ready": True},
    "town": {"name": "その調子！二歩町巡り", "distance": 40, "tier": "🟢 初級", "bonus": None, "ready": True},
    "downtown": {"name": "進め三歩市街道", "distance": 50, "tier": "🟢 初級", "bonus": None, "ready": False},
    "prefecture": {"name": "信じて進む四歩県道", "distance": 70, "tier": "🟡 中級", "bonus": "skip", "ready": False},
    "nation": {"name": "君ならできる五歩国道", "distance": 90, "tier": "🟡 中級", "bonus": "skip", "ready": False},
    "continent": {"name": "焦らず行こう六歩大陸路", "distance": 120, "tier": "🟡 中級", "bonus": "skip", "ready": False},
    "world": {"name": "よくがんばった七歩世界道", "distance": 150, "tier": "🔴 上級", "bonus": "extra_run",
              "ready": False},
    "space": {"name": "誇っていい八歩宇宙路", "distance": 200, "tier": "🔴 上級", "bonus": "extra_run", "ready": False},
    "galaxy": {"name": "どこまでも行ける九歩銀河道", "distance": 300, "tier": "🔴 上級", "bonus": "extra_run",
               "ready": False},
}
RUNNING_TIER_ORDER = ["🟢 初級", "🟡 中級", "🔴 上級"]

COURSE_PRAISE_WORDS = [
    "いいペース！このまま行こう！🏃‍♂️", "足取り軽やか！絶好調だね！✨", "その調子！ゴールがだんだん近づいてきたよ🏘️",
    "ナイスラン！着実に進んでる！👏", "素晴らしい！景色も変わってきたね🌳", "すごい集中力！止まらないその勢い！🔥",
    "順調そのもの！自分を信じて！💪", "いいね！今日も一歩前進だ！🌟", "力強い一歩！道は繋がってるよ🛤️",
    "グッドラン！次のポイントまであと少し！🚀",
]
COURSE_LATE_PRAISE_WORDS = [
    "頑張れ！ラストスパートだ！🔥", "休憩も大事！さすがだね！☕", "ゴールが見えてきたよ！あと少し！🏁",
    "ここが踏ん張りどころ！いけるよ！💪", "疲れたら深呼吸してこう！焦らなくて大丈夫🍃",
]
COURSE_BONUS_MESSAGES = {
    "skip": "🚀 ショートカット発見！さらに+{km}km進んだ！",
    "extra_run": "💨 絶好調ラン！さらに+{km}km走れた！",
}
BONUS_CHANCE = 0.20
BONUS_KM_RANGE = (2, 5)


def maybe_apply_bonus(course_key: str):
    course = RUNNING_COURSES.get(course_key, {})
    bonus_type = course.get("bonus")
    if not bonus_type or random.random() >= BONUS_CHANCE:
        return 0, None
    bonus_km = random.randint(*BONUS_KM_RANGE)
    message = COURSE_BONUS_MESSAGES.get(bonus_type, "").format(km=bonus_km)
    return bonus_km, message


def render_candy_jar_svg(candies: list, capacity: int) -> str:
    count = len(candies)
    width, height = 260, 300
    margin = 24
    left_x, right_x = margin, width - margin
    top_y = 16
    bottom_r = (right_x - left_x) / 2
    straight_bottom_y = height - bottom_r - 16

    glass_path = (
        f"M {left_x},{top_y} "
        f"L {left_x},{straight_bottom_y} "
        f"A {bottom_r},{bottom_r} 0 0 0 {right_x},{straight_bottom_y} "
        f"L {right_x},{top_y}"
    )

    columns = 8
    rows_total = max(1, -(-capacity // columns))
    inner_margin_x = 10
    interior_left = left_x + inner_margin_x
    interior_right = right_x - inner_margin_x
    interior_top = top_y + 8
    interior_bottom = straight_bottom_y - 4

    interior_height = max(interior_bottom - interior_top, 10)
    interior_width = interior_right - interior_left
    spacing_y = interior_height / rows_total
    spacing_x = interior_width / columns
    font_size = max(8, min(spacing_x, spacing_y) * 0.9)

    shapes_svg = ""
    for i, candy in enumerate(candies):
        row = i // columns
        col = i % columns
        rnd = random.Random(i * 97 + 13)
        jitter_x = rnd.uniform(-spacing_x * 0.12, spacing_x * 0.12)
        jitter_y = rnd.uniform(-spacing_y * 0.12, spacing_y * 0.12)
        cx = interior_left + spacing_x * col + spacing_x / 2 + jitter_x
        cy = interior_bottom - spacing_y * row - spacing_y / 2 + jitter_y
        cy = max(cy, interior_top)
        emoji = candy.get("emoji", "🍬")
        tooltip_text = f"入れた日：{candy.get('date', '')}".replace("&", "&amp;").replace("<", "&lt;").replace(">",
                                                                                                              "&gt;")
        shapes_svg += (
            f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{font_size:.1f}" '
            f'text-anchor="middle" dominant-baseline="central">{emoji}'
            f'<title>{tooltip_text}</title>'
            f'</text>'
        )

    return f"""
    <svg viewBox="0 0 {width} {height}" width="100%" style="max-width:280px; display:block; margin:0 auto;">
        <path d="{glass_path}" fill="none" stroke="#2b3a67" stroke-width="2" />
        {shapes_svg}
    </svg>
    """


# =====================================================
# 📊 一日のスケジュール（予定／記録の帯グラフ）まわりの処理
# =====================================================
SCHEDULE_COLORS = {
    "🔴 赤": "#F44336",
    "🟠 オレンジ": "#FF9800",
    "🟡 黄": "#FFC107",
    "🟢 緑": "#4CAF50",
    "🔵 青": "#2196F3",
    "🟣 紫": "#9C27B0",
    "🩷 ピンク": "#E91E63",
    "🩵 水色": "#00BCD4",
    "🟤 茶": "#795548",
    "⚫ 黒": "#333333",
}


def time_to_minutes(hhmm) -> int:
    """'HH:MM' 文字列 または datetime.time を、0時からの経過分数に変換する"""
    if hasattr(hhmm, "hour"):
        return hhmm.hour * 60 + hhmm.minute
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def minutes_to_hhmm(total_minutes: int) -> str:
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


def render_day_bar_svg(entries: list, bar_width: int = 150, height: int = 720) -> str:
    """
    24時間分の縦長の帯グラフ（0時始まり）をSVGで描画する。
    30分ごとに小目盛り、1時間ごとに大目盛り＋時刻ラベルを表示する。
    entries: [{"start": "HH:MM", "end": "HH:MM", "label": str, "color": "#rrggbb"}, ...]
    """
    label_area = 62
    total_width = bar_width + label_area
    svg_parts = [
        f'<rect x="{label_area}" y="0" width="{bar_width}" height="{height}" fill="#fafafa" stroke="#333" stroke-width="1.8" />'
    ]

    # 30分ごとの小目盛り、1時間ごとの大目盛り
    for half_hour in range(0, 49):
        minutes = half_hour * 30
        y = height * minutes / (24 * 60)
        is_major = (minutes % 60 == 0)
        stroke = "#b8b8b8" if is_major else "#e6e6e6"
        stroke_width = "1.4" if is_major else "0.8"
        svg_parts.append(
            f'<line x1="{label_area}" y1="{y:.1f}" x2="{label_area + bar_width}" y2="{y:.1f}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}" />'
        )
        if is_major:
            hour = minutes // 60
            svg_parts.append(
                f'<line x1="{label_area - 8}" y1="{y:.1f}" x2="{label_area}" y2="{y:.1f}" '
                f'stroke="#555" stroke-width="1.4" />'
            )
            svg_parts.append(
                f'<text x="{label_area - 12}" y="{y + 4:.1f}" font-size="13" font-weight="bold" '
                f'text-anchor="end">{hour:02d}:00</text>'
            )

    for e in entries:
        start_min = time_to_minutes(e["start"])
        end_min = time_to_minutes(e["end"])
        y1 = height * start_min / (24 * 60)
        y2 = height * end_min / (24 * 60)
        seg_height = max(y2 - y1, 4)
        color = e.get("color", "#4CAF50")
        label = e.get("label", "")
        safe_label = str(label).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        tooltip = f"{e['start']}〜{e['end']} {safe_label}"
        svg_parts.append(
            f'<rect x="{label_area + 3}" y="{y1:.1f}" width="{bar_width - 6}" height="{seg_height:.1f}" '
            f'fill="{color}" stroke="#ffffff" stroke-width="1" opacity="0.92" rx="3">'
            f'<title>{tooltip}</title></rect>'
        )
        # グラフ上にも予定名を表示（短時間の予定でも読めるよう中央配置）
        text_y = y1 + max(seg_height / 2 + 4, 14)
        display_label = str(label)
        max_chars = max(4, int((bar_width - 18) / 11))
        if len(display_label) > max_chars:
            display_label = display_label[:max_chars - 1] + "…"
        safe_display = display_label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        # 背景色に左右されにくいよう、白文字＋黒い半透明の縁取り
        svg_parts.append(
            f'<text x="{label_area + bar_width / 2:.1f}" y="{text_y:.1f}" text-anchor="middle" '
            f'font-size="13" font-weight="bold" fill="#ffffff" stroke="#333333" stroke-width="3" paint-order="stroke" '
            f'stroke-opacity="0.45">{safe_display}</text>'
        )

    return (f'<svg viewBox="0 0 {total_width} {height}" width="100%" height="{height}" '
            f'style="display:block; max-width:100%;">' + "".join(svg_parts) + "</svg>")



def find_schedule_matches(planned: list, actual: list) -> list:
    """予定と記録で、開始・終了時刻が完全に一致する組み合わせを探す"""
    matches = []
    for p in planned:
        for a in actual:
            if p["start"] == a["start"] and p["end"] == a["end"]:
                matches.append((p, a))
    return matches


def get_ippo_events_for_date(date_str: str) -> list:
    """その日のIPPO内イベント（お菓子・ランニング・目標達成など）を時刻順にまとめて返す"""
    events = []
    for c in st.session_state.get("all_candy_log", []):
        if c["date"].startswith(date_str):
            events.append((c["date"].split(" ")[1], f"{c.get('emoji', '🍬')} お菓子ゲット：{c.get('task', '')}"))
    for r in st.session_state.get("course_run_log", []):
        if r["date"].startswith(date_str):
            events.append(
                (r["date"].split(" ")[1], f"🏃 {r.get('course', 'ランニング')}：{r.get('km', 0)}km（{r.get('task', '')}）"))
    for j in st.session_state.get("jar_complete_log", []):
        if j["date"].startswith(date_str):
            size_label_text = j.get("size_label", JAR_SIZE_LABELS.get(j.get("capacity"), "?"))
            events.append((j["date"].split(" ")[1], f"🍯 お菓子のビン({size_label_text})完成"))
    for v in st.session_state.get("course_complete_log", []):
        if v["date"].startswith(date_str):
            events.append((v["date"].split(" ")[1], f"🏁 『{v.get('course', 'コース')}』完走達成"))
    for g in st.session_state.get("goal_complete_log", []):
        if g["date"].startswith(date_str):
            events.append((g["date"].split(" ")[1], f"🏆 『{g.get('title', '')}』目標達成"))
    events.sort(key=lambda ev: ev[0])
    return events


def render_schedule_and_events(date_str: str, editable: bool):
    """
    指定した日の「予定／記録」帯グラフと、隣にIPPOイベントログを表示する。
    editable=True の場合は、予定・記録の追加に加えて既存項目の編集・削除ができる。
    """
    day_schedule = st.session_state.daily_schedule.setdefault(date_str, {"planned": [], "actual": []})

    if editable:
        col_plan_btn, col_record_btn = st.columns(2)
        with col_plan_btn:
            if st.button("📅 予定を立てる", use_container_width=True, key=f"open_plan_form_{date_str}"):
                play_click_sound(delay=0)
                st.session_state.schedule_form_open = "planned" if st.session_state.get("schedule_form_open") != "planned" else None
                st.session_state.schedule_edit_target = None
                st.rerun()
        with col_record_btn:
            if st.button("✅ 記録する", use_container_width=True, key=f"open_record_form_{date_str}"):
                play_click_sound(delay=0)
                st.session_state.schedule_form_open = "actual" if st.session_state.get("schedule_form_open") != "actual" else None
                st.session_state.schedule_edit_target = None
                st.rerun()

        # 既存項目を押したときの編集・削除フォーム
        edit_target = st.session_state.get("schedule_edit_target")
        if edit_target and edit_target.get("date") == date_str:
            edit_kind = edit_target["kind"]
            edit_index = edit_target["index"]
            entries = day_schedule.get(edit_kind, [])
            if 0 <= edit_index < len(entries):
                entry = entries[edit_index]
                kind_label = "予定" if edit_kind == "planned" else "記録"
                st.session_state.schedule_form_open = None
                with st.container(border=True):
                    st.markdown(f"#### ✏️ {kind_label}を編集")
                    edit_col_start, edit_col_end = st.columns(2)
                    with edit_col_start:
                        edit_start = st.time_input(
                            "開始時刻", value=datetime.strptime(entry["start"], "%H:%M").time(),
                            key=f"edit_sched_start_{date_str}_{edit_kind}_{edit_index}")
                    with edit_col_end:
                        edit_end = st.time_input(
                            "終了時刻", value=datetime.strptime(entry["end"], "%H:%M").time(),
                            key=f"edit_sched_end_{date_str}_{edit_kind}_{edit_index}")
                    edit_label = st.text_input(
                        "内容（なんでもOK）", value=entry.get("label", ""),
                        key=f"edit_sched_label_{date_str}_{edit_kind}_{edit_index}")
                    current_color = entry.get("color", "#4CAF50" if edit_kind == "planned" else "#2196F3")
                    color_options = list(SCHEDULE_COLORS.keys())
                    current_color_name = next(
                        (name for name, hex_color in SCHEDULE_COLORS.items() if hex_color.lower() == str(current_color).lower()),
                        color_options[3 if edit_kind == "planned" else 4]
                    )
                    edit_color_name = st.selectbox(
                        "色（10色から選択）",
                        options=color_options,
                        index=color_options.index(current_color_name),
                        key=f"edit_sched_color_{date_str}_{edit_kind}_{edit_index}")
                    edit_color = SCHEDULE_COLORS[edit_color_name]

                    save_col, delete_col, cancel_col = st.columns(3)
                    with save_col:
                        if st.button("💾 変更を保存", type="primary", use_container_width=True,
                                     key=f"save_sched_edit_{date_str}_{edit_kind}_{edit_index}"):
                            if not edit_label.strip():
                                st.error("⚠️ 内容を入力してください。")
                            elif time_to_minutes(edit_start) >= time_to_minutes(edit_end):
                                st.error("⚠️ 終了時刻は開始時刻より後にしてください。")
                            else:
                                play_click_sound(delay=0)
                                entry.update({
                                    "start": edit_start.strftime("%H:%M"),
                                    "end": edit_end.strftime("%H:%M"),
                                    "label": edit_label.strip(),
                                    "color": edit_color,
                                })
                                st.session_state.schedule_edit_target = None
                                st.rerun()
                    with delete_col:
                        if st.button("🗑️ 削除", use_container_width=True,
                                     key=f"delete_sched_{date_str}_{edit_kind}_{edit_index}"):
                            play_click_sound(delay=0)
                            st.session_state.schedule_delete_target = {
                                "date": date_str, "kind": edit_kind, "index": edit_index
                            }
                            st.rerun()
                    with cancel_col:
                        if st.button("キャンセル", use_container_width=True,
                                     key=f"cancel_sched_edit_{date_str}_{edit_kind}_{edit_index}"):
                            st.session_state.schedule_edit_target = None
                            st.rerun()

        # 削除確認
        delete_target = st.session_state.get("schedule_delete_target")
        if delete_target and delete_target.get("date") == date_str:
            delete_kind = delete_target["kind"]
            delete_index = delete_target["index"]
            entries = day_schedule.get(delete_kind, [])
            if 0 <= delete_index < len(entries):
                target_entry = entries[delete_index]
                with st.container(border=True):
                    st.warning(f"「{target_entry.get('label', '')}（{target_entry['start']}〜{target_entry['end']}）」を削除しますか？")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button("🗑️ 削除する", type="primary", use_container_width=True,
                                     key=f"confirm_sched_delete_{date_str}_{delete_kind}_{delete_index}"):
                            play_click_sound(delay=0)
                            entries.pop(delete_index)
                            st.session_state.schedule_delete_target = None
                            st.session_state.schedule_edit_target = None
                            st.rerun()
                    with cancel_col:
                        if st.button("やめる", use_container_width=True,
                                     key=f"cancel_sched_delete_{date_str}_{delete_kind}_{delete_index}"):
                            st.session_state.schedule_delete_target = None
                            st.rerun()

        form_kind = st.session_state.get("schedule_form_open")
        if form_kind in ("planned", "actual"):
            form_title = "📅 予定を追加" if form_kind == "planned" else "✅ 記録を追加"
            with st.container(border=True):
                st.markdown(f"#### {form_title}")
                col_start, col_end = st.columns(2)
                with col_start:
                    start_time = st.time_input("開始時刻", key=f"sched_start_{date_str}_{form_kind}")
                with col_end:
                    end_time = st.time_input("終了時刻", key=f"sched_end_{date_str}_{form_kind}")
                label_text = st.text_input("内容（なんでもOK）", key=f"sched_label_{date_str}_{form_kind}",
                                           placeholder="例：数学の宿題、読書、休憩 など")
                color_options = list(SCHEDULE_COLORS.keys())
                default_color_index = 3 if form_kind == "planned" else 4
                color_pick_name = st.selectbox(
                    "色（10色から選択）",
                    options=color_options,
                    index=default_color_index,
                    key=f"sched_color_{date_str}_{form_kind}")
                color_pick = SCHEDULE_COLORS[color_pick_name]
                if st.button("➕ 追加する", type="primary", key=f"sched_add_{date_str}_{form_kind}"):
                    if not label_text.strip():
                        st.error("⚠️ 内容を入力してください。")
                    elif time_to_minutes(start_time) >= time_to_minutes(end_time):
                        st.error("⚠️ 終了時刻は開始時刻より後にしてください。")
                    else:
                        play_click_sound(delay=0)
                        new_entry = {
                            "start": start_time.strftime("%H:%M"),
                            "end": end_time.strftime("%H:%M"),
                            "label": label_text.strip(),
                            "color": color_pick,
                        }
                        day_schedule[form_kind].append(new_entry)
                        st.session_state.schedule_form_open = None
                        st.rerun()

    chart_col1, chart_col2, event_col = st.columns([1, 1, 1.35])
    for chart_col, kind, title, icon in [
        (chart_col1, "planned", "📅 予定", "📅"),
        (chart_col2, "actual", "✅ 記録", "✅"),
    ]:
        with chart_col:
            st.markdown(f"**{title}**")
            st.markdown(render_day_bar_svg(day_schedule[kind], bar_width=150, height=720), unsafe_allow_html=True)
            if day_schedule[kind]:
                if editable:
                    st.markdown("##### 🖱️ 項目を押して編集・削除")
                for i, entry in enumerate(day_schedule[kind]):
                    color = entry.get("color", "#4CAF50" if kind == "planned" else "#2196F3")
                    button_label = f"{icon} {entry['start']}〜{entry['end']}　{entry.get('label', '')}"
                    if editable:
                        if st.button(button_label, use_container_width=True, key=f"schedule_entry_button_{date_str}_{kind}_{i}"):
                            play_click_sound(delay=0)
                            st.session_state.schedule_edit_target = {"date": date_str, "kind": kind, "index": i}
                            st.session_state.schedule_delete_target = None
                            st.rerun()
                        # ボタンの左に色を表示する代わりに、直下に色チップを表示
                        st.markdown(
                            f'<div style="height:5px;background:{color};border-radius:4px;margin:-8px 0 6px 0;"></div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div style="border-left:8px solid {color};padding:6px 8px;margin:4px 0;">'
                            f'<b>{entry["start"]}〜{entry["end"]}</b>　{entry.get("label", "")}</div>',
                            unsafe_allow_html=True)
            else:
                st.caption("まだ登録されていません。")

    with event_col:
        st.markdown("**🎮 IPPO内のイベント記録**")
        events_today = get_ippo_events_for_date(date_str)
        if events_today:
            for event_time, event_label in events_today:
                st.write(f"⏰ {event_time}　{event_label}")
        else:
            st.caption("この日はまだイベントの記録がありません。")



# =====================================================
# 🔊 音声読み込み
# =====================================================
@st.cache_data
def load_sound_base64(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


_sound_b64 = load_sound_base64(SOUND_PATH)
_achieve_sound_b64 = load_sound_base64(ACHIEVE_SOUND_PATH)
_jar_full_sound_b64 = load_sound_base64(JAR_FULL_SOUND_PATH)


def play_click_sound(delay: float = 1.2):
    if _sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{_sound_b64}" type="audio/mp3"></audio>'
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_achieve_sound(delay: float = 0):
    if _achieve_sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{_achieve_sound_b64}" type="audio/mp3"></audio>'
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_jar_full_sound(delay: float = 0):
    if _jar_full_sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{_jar_full_sound_b64}" type="audio/mp3"></audio>'
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


# =====================================================
# 1. 記憶の部屋（セッション状態）の初期化
# =====================================================
now_jst = get_now_jst()

if "page" not in st.session_state:
    st.session_state.page = "title"
if "login_step" not in st.session_state:
    st.session_state.login_step = "title"  # 'title', 'login_input', 'confirm'
if "temp_user_id" not in st.session_state:
    st.session_state.temp_user_id = ""
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "game_started" not in st.session_state:
    st.session_state.game_started = False
if "target_list" not in st.session_state:
    st.session_state.target_list = []
if "confirm_delete_target_index" not in st.session_state:
    st.session_state.confirm_delete_target_index = None
if "editing_target_index" not in st.session_state:
    st.session_state.editing_target_index = None
if "calendar_notes" not in st.session_state:
    st.session_state.calendar_notes = {}
if "jar_capacity" not in st.session_state:
    st.session_state.jar_capacity = 30
if "jar_candies" not in st.session_state:
    st.session_state.jar_candies = []
if "all_candy_log" not in st.session_state:
    st.session_state.all_candy_log = []
if "show_past_jars" not in st.session_state:
    st.session_state.show_past_jars = False
if "praise_message" not in st.session_state:
    st.session_state.praise_message = ""
if "show_candy_buttons" not in st.session_state:
    st.session_state.show_candy_buttons = False
if "temp_candy_count" not in st.session_state:
    st.session_state.temp_candy_count = 0
if "last_completed_task" not in st.session_state:
    st.session_state.last_completed_task = ""
if "jar_full_sound_played" not in st.session_state:
    st.session_state.jar_full_sound_played = False
if "last_jar_capacity" not in st.session_state:
    st.session_state.last_jar_capacity = st.session_state.jar_capacity
if "jar_complete_log" not in st.session_state:
    st.session_state.jar_complete_log = []
if "course_km" not in st.session_state:
    st.session_state.course_km = {}
if "course_praise_message" not in st.session_state:
    st.session_state.course_praise_message = {}
if "course_complete_sound_played" not in st.session_state:
    st.session_state.course_complete_sound_played = {}
if "course_complete_companion_message" not in st.session_state:
    st.session_state.course_complete_companion_message = {}
if "course_run_log" not in st.session_state:
    st.session_state.course_run_log = []
if "course_complete_log" not in st.session_state:
    st.session_state.course_complete_log = []
if "active_course_key" not in st.session_state:
    st.session_state.active_course_key = "village"

# 📊 一日のスケジュール（予定／記録）
if "daily_schedule" not in st.session_state:
    st.session_state.daily_schedule = {}
if "schedule_form_open" not in st.session_state:
    st.session_state.schedule_form_open = None
if "schedule_edit_target" not in st.session_state:
    st.session_state.schedule_edit_target = None
if "schedule_delete_target" not in st.session_state:
    st.session_state.schedule_delete_target = None

COMPANIONS = {
    "cat": {"emoji": "🐱", "name": "ねこ"},
    "dog": {"emoji": "🐶", "name": "いぬ"},
    "bird": {"emoji": "🐦", "name": "とり"},
}

COMPANION_MESSAGES = {
    "cat": [
        "ふーん、やるじゃない。…べつに、感心してないけど。",
        "まあまあね。無理しない程度に頑張りなさいよ。",
        "ふぁ…（あくび）褒めてほしいなら、褒めてあげる。えらいわよ。",
        "悪くないじゃない。次も、まあ期待しててあげる。",
        "…気が向いたから、隣を歩いてあげてるだけだから。",
        "頑張るあんたを見てると、まあ悪くないなって思うのよね。",
        "誰のためでもなく、あんたのためなんだからね。",
    ],
    "dog": [
        "うおおおすごいすごい！！やったねやったね！！🐾",
        "きみのこと、ずっと信じてたよ！！最高だ！！",
        "もっと行こう！！ぼく、どこまでもついていくよ！！",
        "しっぽ振るのが止まらないよ！！すごいすごい！！",
        "きみが頑張る姿、ぼくの元気の源だよ！ありがとう！",
        "できたね！！えらいえらい！！なでてあげたい気分！！",
        "よーし、次のご褒美探しに行こう！！ぼくも一緒だよ！",
    ],
    "bird": [
        "風が気持ちいいね〜。きみの一歩、ちゃんと空まで届いてるよ🕊️",
        "高いところから見てたよ。ちゃんと前に進んでる、大丈夫。",
        "さえずるくらい嬉しいことがあったみたいだね♪",
        "羽を休める時間も大事。無理せずゆっくりね。",
        "その調子。景色がどんどん変わっていくの、見えてる？",
        "小さな一歩も、飛び立つ前の助走みたいなものだよ。",
        "今日の空、きみの頑張りにちょうどいい色してるよ。",
    ],
}

COMPANION_COMPLETE_MESSAGES = {
    "cat": [
        "…やるじゃない。最初から出来ると思ってたけどね。",
        "はぁ…お疲れさま。よくやったわね、本当に。",
        "べ、別に感動なんてしてないんだから！…ちょっとだけよ。",
        "やっと着いたわね。…隣にいられて、悪くなかったわ。",
        "次はどこ行くの？…付き合ってあげてもいいけど。",
    ],
    "dog": [
        "やったーーー！！！ゴールだ！！最高だよ！！🎉",
        "きみ、本当にすごいよ！！誇らしいよ！！",
        "ずっと一緒に走れて幸せだった！！ありがとう！！",
        "抱きつきたいくらい嬉しい！！よく頑張ったね！！",
        "次のコースも一緒に行こうね！！絶対だよ！！",
    ],
    "bird": [
        "ここまで飛んできたね。振り返ってごらん、素敵な道のりだったよ🕊️",
        "空の色が変わった気がする。きみが変わったからかな。",
        "ゴールは終わりじゃなくて、次の風の始まりだよ。",
        "静かに、でも確かに。ここまで来たこと、誇っていいよ。",
        "また新しい空へ、一緒に飛んでいこうね。",
    ],
}

if "companion" not in st.session_state:
    st.session_state.companion = None
if "show_companion_picker" not in st.session_state:
    st.session_state.show_companion_picker = False
if "goal_complete_log" not in st.session_state:
    st.session_state.goal_complete_log = []

STICKER_CIRCLE_COLORS = {
    "赤": "🔴", "橙": "🟠", "黄": "🟡", "緑": "🟢",
    "青": "🔵", "紫": "🟣", "黒": "⚫", "白": "⚪",
}
STICKER_FIXED_TYPES = {
    "star": {"emoji": "⭐", "label": "星"},
    "petal": {"emoji": "🌸", "label": "花びら"},
    "hanamaru": {"emoji": "💮", "label": "花丸"},
    "smile": {"emoji": "😊", "label": "スマイル"},
}
MAX_STICKERS_SHOWN = 5
GRID_STICKERS_SHOWN = 2

if "calendar_stickers" not in st.session_state:
    st.session_state.calendar_stickers = {}
if "sticker_type" not in st.session_state:
    st.session_state.sticker_type = "circle"
if "sticker_color" not in st.session_state:
    st.session_state.sticker_color = "赤"


def get_current_sticker_emoji() -> str:
    if st.session_state.sticker_type == "circle":
        return STICKER_CIRCLE_COLORS.get(st.session_state.sticker_color, "🔴")
    return STICKER_FIXED_TYPES.get(st.session_state.sticker_type, {}).get("emoji", "🔴")


def add_sticker_for_date(date_str: str):
    st.session_state.calendar_stickers[date_str] = st.session_state.calendar_stickers.get(date_str, 0) + 1


def should_prompt_deadline_today(target_data: dict) -> bool:
    deadline = target_data.get("deadline")
    if not deadline or target_data.get("deadline_reminder_stopped"):
        return False
    today_str = get_now_jst().strftime("%Y/%m/%d")
    if target_data.get("reminder_mode") == "daily":
        if today_str < deadline:
            return False
        answered_dates = {entry["date"] for entry in target_data.get("deadline_daily_log", [])}
        return today_str not in answered_dates
    if target_data.get("deadline_answered"):
        return False
    return today_str == deadline


def record_deadline_answer(target_data: dict, result_label: str):
    today_str = get_now_jst().strftime("%Y/%m/%d")
    if target_data.get("reminder_mode") == "daily":
        target_data.setdefault("deadline_daily_log", []).append({
            "date": today_str,
            "result": result_label,
        })
    else:
        target_data["deadline_answered"] = True
        target_data["deadline_result"] = result_label
    add_sticker_for_date(today_str)


def get_sticker_preview(date_str: str, limit: int = MAX_STICKERS_SHOWN, show_remainder: bool = True) -> str:
    count = st.session_state.calendar_stickers.get(date_str, 0)
    if count <= 0:
        return ""
    emoji = get_current_sticker_emoji()
    preview = emoji * min(count, limit)
    if show_remainder and count > limit:
        preview += f"+{count - limit}"
    return preview


if "calendar_view_year" not in st.session_state:
    st.session_state.calendar_view_year = now_jst.year
if "calendar_view_month" not in st.session_state:
    st.session_state.calendar_view_month = now_jst.month
if "selected_calendar_date" not in st.session_state:
    st.session_state.selected_calendar_date = now_jst.strftime("%Y/%m/%d")

# =====================================================
# 2. 【タイトル画面】
# =====================================================
if st.session_state.page == "title":
    st.title("🏃‍♂️ IPPO(仮)")
    st.subheader("〜完璧主義をハックする、最初の一歩アプリ〜")
    st.write("")

    # ステップ1：はじめから / つづきから 選択画面
    if st.session_state.login_step == "title":
        col_new, col_continue = st.columns(2)
        with col_new:
            if st.button("🆕 はじめから", use_container_width=True, type="primary"):
                play_click_sound(delay=0)
                st.session_state.login_mode = "new"
                st.session_state.login_step = "login_input"
                st.rerun()

        with col_continue:
            if st.button("▶️ つづきから", use_container_width=True, type="secondary"):
                play_click_sound(delay=0)
                st.session_state.login_mode = "continue"
                st.session_state.login_step = "login_input"
                st.rerun()

    # ステップ2：ユーザーID入力画面
    elif st.session_state.login_step == "login_input":
        if st.session_state.get("login_mode") == "new":
            st.markdown("### 🆕 新しく始めるユーザー名を入力してください")
            input_name = st.text_input("ユーザー名（またはID）", key="input_user_name_new")

            # ★修正①：すでに同じ名前のセーブデータがある場合は警告する
            name_already_exists = bool(input_name.strip()) and check_user_exists(input_name.strip())
            if name_already_exists:
                st.warning("⚠️ その名前のセーブデータはすでにあります。このまま進むと上書きされて消えてしまいます。")

            col_ok, col_back = st.columns(2)
            with col_ok:
                button_label = "⚠️ 上書きして始める" if name_already_exists else "決定してスタート"
                if st.button(button_label, type="primary", use_container_width=True):
                    play_click_sound(delay=0)
                    if input_name.strip():
                        st.session_state.current_user = input_name.strip()
                        reset_progress_in_memory()
                        if name_already_exists:
                            # 上書きする場合は、Supabase側の古いレコードも削除してから真っさらにする
                            try:
                                supabase.table("user_data").delete().eq("id", st.session_state.current_user).execute()
                            except Exception:
                                pass
                        st.session_state.game_started = True
                        st.session_state.page = "menu_select"
                        st.session_state.login_step = "title"
                        st.rerun()
                    else:
                        st.warning("ユーザー名を入力してください。")
            with col_back:
                if st.button("戻る", use_container_width=True):
                    play_click_sound(delay=0)
                    st.session_state.login_step = "title"
                    st.rerun()

        else:  # continue モード
            st.markdown("### ▶️ 前ログインしたときの名前（ID）を入力してください")
            input_name = st.text_input("ユーザー名（またはID）", key="input_user_name_continue")

            col_search, col_back = st.columns(2)
            with col_search:
                if st.button("検索する", type="primary", use_container_width=True):
                    play_click_sound(delay=0)
                    if input_name.strip():
                        uid = input_name.strip()
                        if check_user_exists(uid):
                            st.session_state.temp_user_id = uid
                            st.session_state.login_step = "confirm"
                            st.rerun()
                        else:
                            st.error(f"「{uid}」のセーブデータが見つかりませんでした。名前を確認してください。")
                    else:
                        st.warning("ユーザー名を入力してください。")
            with col_back:
                if st.button("戻る", use_container_width=True):
                    play_click_sound(delay=0)
                    st.session_state.login_step = "title"
                    st.rerun()

    # ステップ3：データの確認画面（はい／いいえ）
    elif st.session_state.login_step == "confirm":
        st.success(f"🎉 **{st.session_state.temp_user_id}** さんのセーブデータが見つかりました！")
        st.markdown("### このデータで続けますか？")
        st.write("")

        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("はい", type="primary", use_container_width=True):
                play_click_sound(delay=0)
                # ★修正②：読み込みに失敗した場合は、進めずにその場でエラーを見せる
                load_ok = load_progress(st.session_state.temp_user_id)
                if load_ok:
                    st.session_state.current_user = st.session_state.temp_user_id
                    st.session_state.game_started = True
                    st.session_state.page = "menu_select"
                    st.session_state.login_step = "title"
                    st.rerun()
                else:
                    st.error(
                        "⚠️ データの読み込みに失敗しました。進捗を上書きしないよう、ここで止めています。"
                        "少し時間をおいてから、もう一度お試しください。"
                    )

        with col_no:
            if st.button("いいえ", use_container_width=True):
                play_click_sound(delay=0)
                st.session_state.login_step = "title"
                st.session_state.temp_user_id = ""
                st.rerun()

    st.write("")
    st.write("")

    # タイトル画面設定エリア
    if st.session_state.get("current_user"):
        spacer_col, settings_col = st.columns([3, 1])
        with settings_col:
            with st.expander("⚙️ 設定"):
                st.caption(f"現在のユーザー: **{st.session_state.current_user}** のデータを削除します。")
                if st.session_state.get("confirm_delete_save"):
                    st.warning("本当に削除しますか？この操作は取り消せません。")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button("🗑️ 削除する", key="confirm_delete_yes"):
                            play_click_sound(delay=0)
                            reset_progress()
                            st.session_state.confirm_delete_save = False
                            st.success("データを削除しました。")
                            st.rerun()
                    with cancel_col:
                        if st.button("やめる", key="confirm_delete_no"):
                            play_click_sound(delay=0)
                            st.session_state.confirm_delete_save = False
                            st.rerun()
                else:
                    if st.button("🗑️ データを削除", key="open_delete_confirm"):
                        play_click_sound(delay=0)
                        st.session_state.confirm_delete_save = True
                        st.rerun()

# =====================================================
# 3. 【2ページ目：メニュー画面】
# =====================================================
elif st.session_state.page == "menu_select":
    st.sidebar.title("👤 ユーザー情報")
    st.sidebar.info(f"ログイン中: **{st.session_state.current_user}**")

    st.title("🗺️ メニューセレクト")
    st.markdown("## 🎯 挑戦する項目を選んでください：")
    st.write("")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🎯\n\n目標登録", use_container_width=True, key="menu_target"):
            play_click_sound()
            st.session_state.page = "target_page"
            st.rerun()
    with col2:
        if st.button("📅\n\nカレンダー", use_container_width=True, key="menu_calendar"):
            play_click_sound()
            st.session_state.page = "calendar_page"
            st.rerun()
    with col3:
        if st.button("⚔️\n\nステージ", use_container_width=True, key="menu_stage"):
            play_click_sound()
            st.session_state.page = "stage_page"
            st.rerun()
    with col4:
        if st.button("📊\n\n一日のスケジュール", use_container_width=True, key="menu_schedule"):
            play_click_sound()
            st.session_state.page = "schedule_page"
            st.rerun()

# =====================================================
# 4. 【個別画面】
# =====================================================
elif st.session_state.page in [
    "target_page", "calendar_page", "stage_page",
    "candy_page", "running_page", "running_course_page", "schedule_page"
]:

    # サイドバーメニュー
    with st.sidebar:
        st.title("👤 ユーザー情報")
        st.info(f"ログイン中: **{st.session_state.current_user}**")
        st.write("---")
        st.title("⚙️ クイックメニュー")
        if st.button("🎯 目標登録画面へ"):
            play_click_sound()
            st.session_state.page = "target_page"
            st.rerun()
        if st.button("📅 カレンダー画面へ"):
            play_click_sound()
            st.session_state.page = "calendar_page"
            st.rerun()
        if st.button("⚔️ ステージ画面へ"):
            play_click_sound()
            st.session_state.page = "stage_page"
            st.rerun()
        if st.button("📊 一日のスケジュールへ"):
            play_click_sound()
            st.session_state.page = "schedule_page"
            st.rerun()
        st.write("---")
        if st.button("↩️ メニューセレクトに戻る"):
            play_click_sound()
            st.session_state.page = "menu_select"
            st.rerun()
        if st.button("🏠 タイトルに戻る"):
            play_click_sound()
            st.session_state.page = "title"
            st.session_state.login_step = "title"
            st.rerun()

    # --- 目標登録画面 ---
    if st.session_state.page == "target_page":
        st.title("🎯 目標登録画面")
        st.write("まずは達成したい「大きな目標」を入力してください。")

        main_target_input = st.text_input("最終目標（例：テストで70点とる、など）", key="main_input")

        if main_target_input:
            st.write("---")
            st.markdown(f"### 📝 『{main_target_input}』のレベル1〜5を入力してください")

            lv1 = st.text_input("Lv.1 (例:教科書を開いた！)")
            lv2 = st.text_input("Lv.2 (例:10分出来た！)")
            lv3 = st.text_input("Lv.3 (例:1ページ出来た！)")
            lv4 = st.text_input("Lv.4 (例:60分できた！)")
            lv5 = st.text_input("Lv.5 (例:範囲内の勉強が一周出来た！)")

            if st.button("✨ この目標セットを登録する", type="primary"):
                if lv1 and lv2 and lv3 and lv4 and lv5:
                    new_target = {
                        "title": main_target_input,
                        "tasks": {"Lv.1": lv1, "Lv.2": lv2, "Lv.3": lv3, "Lv.4": lv4, "Lv.5": lv5},
                        "completed": False,
                    }
                    st.session_state.target_list.append(new_target)
                    play_click_sound()
                    st.success(f"📌 目標『{main_target_input}』を登録しました！お菓子画面で選べるようになったよ！")
                    st.rerun()
                else:
                    st.error("⚠️ 全レベルを入力してください。")

        if st.session_state.target_list:
            st.write("---")
            st.markdown("## 🛡️ 登録済みのクエスト一覧")
            for i, target_data in enumerate(st.session_state.target_list):
                with st.expander(f"🎯 {target_data['title']}", expanded=True):

                    # --- 編集モードと通常モードの切り替え ---
                    if st.session_state.get("editing_target_index") == i:
                        st.markdown("### ✏️ 目標の編集")
                        edit_title = st.text_input("最終目標タイトル", value=target_data["title"],
                                                   key=f"edit_title_{i}")
                        edit_lv1 = st.text_input("Lv.1", value=target_data["tasks"].get("Lv.1", ""),
                                                 key=f"edit_lv1_{i}")
                        edit_lv2 = st.text_input("Lv.2", value=target_data["tasks"].get("Lv.2", ""),
                                                 key=f"edit_lv2_{i}")
                        edit_lv3 = st.text_input("Lv.3", value=target_data["tasks"].get("Lv.3", ""),
                                                 key=f"edit_lv3_{i}")
                        edit_lv4 = st.text_input("Lv.4", value=target_data["tasks"].get("Lv.4", ""),
                                                 key=f"edit_lv4_{i}")
                        edit_lv5 = st.text_input("Lv.5", value=target_data["tasks"].get("Lv.5", ""),
                                                 key=f"edit_lv5_{i}")

                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.button("💾 変更を保存", key=f"save_edit_{i}", type="primary",
                                         use_container_width=True):
                                if edit_title and edit_lv1 and edit_lv2 and edit_lv3 and edit_lv4 and edit_lv5:
                                    play_click_sound(delay=0)
                                    target_data["title"] = edit_title.strip()
                                    target_data["tasks"] = {
                                        "Lv.1": edit_lv1, "Lv.2": edit_lv2, "Lv.3": edit_lv3,
                                        "Lv.4": edit_lv4, "Lv.5": edit_lv5
                                    }
                                    st.session_state.editing_target_index = None
                                    st.success("目標を更新しました！")
                                    st.rerun()
                                else:
                                    st.error("⚠️ すべての項目を入力してください。")
                        with cancel_col:
                            if st.button("キャンセル", key=f"cancel_edit_{i}", use_container_width=True):
                                play_click_sound(delay=0)
                                st.session_state.editing_target_index = None
                                st.rerun()

                    else:
                        for lv, task in target_data["tasks"].items():
                            st.info(f"**{lv}**: {task}")

                        st.write("")
                        if target_data.get("completed", False):
                            st.success("🎉 この目標は達成済みです！おめでとう！")
                            if st.button("🔄 もう一度挑戦する", key=f"retry_target_{i}"):
                                play_click_sound(delay=0)
                                target_data["completed"] = False
                                st.rerun()
                        else:
                            if st.button("🏆 最終目標を達成した！", type="primary", key=f"complete_target_{i}"):
                                play_jar_full_sound()
                                target_data["completed"] = True
                                now = get_now_jst()
                                now_datetime_str = now.strftime("%Y/%m/%d %H:%M")
                                today_date_str = now.strftime("%Y/%m/%d")
                                st.session_state.goal_complete_log.append({
                                    "date": now_datetime_str,
                                    "title": target_data["title"],
                                })
                                add_sticker_for_date(today_date_str)
                                st.rerun()

                    st.write("")
                    st.write("---")
                    current_deadline = target_data.get("deadline")
                    if current_deadline:
                        deadline_display = datetime.strptime(current_deadline, "%Y/%m/%d").strftime("%Y年%m月%d日")
                        is_daily_mode = target_data.get("reminder_mode") == "daily"
                        reminder_mode_label = "答えた後も毎日聞く" if is_daily_mode else "その日だけ聞く"

                        if target_data.get("deadline_reminder_stopped"):
                            st.caption(f"🎯 チャレンジ期限：{deadline_display}（リマインドは停止中）")
                        elif is_daily_mode:
                            daily_log = target_data.get("deadline_daily_log", [])
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display}〜（{reminder_mode_label}／これまでの回答数：{len(daily_log)}回）")
                        elif target_data.get("deadline_answered"):
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display}（結果：{target_data.get('deadline_result', '?')} 報告済み）")
                        else:
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display} まで（{reminder_mode_label}／この日になったら結果を聞くよ）")

                        if st.button("期限を解除する", key=f"clear_deadline_{i}"):
                            play_click_sound(delay=0)
                            target_data["deadline"] = None
                            target_data["deadline_answered"] = False
                            target_data["deadline_result"] = None
                            target_data["reminder_mode"] = "once"
                            target_data["deadline_reminder_stopped"] = False
                            target_data["deadline_daily_log"] = []
                            st.rerun()
                    else:
                        with st.expander("🎯 この日までチャレンジ！を設定する"):
                            new_deadline = st.date_input("いつまでに頑張る？", value=get_now_jst().date(),
                                                         key=f"deadline_input_{i}")
                            new_reminder_mode = st.radio(
                                "結果はいつ聞く？",
                                options=["once", "daily"],
                                format_func=lambda
                                    m: "その日だけ聞く" if m == "once" else "答えた後も毎日聞く（繰り返しチェックイン）",
                                key=f"deadline_mode_{i}",
                            )
                            if st.button("この日を設定する", key=f"set_deadline_{i}"):
                                play_click_sound(delay=0)
                                target_data["deadline"] = new_deadline.strftime("%Y/%m/%d")
                                target_data["deadline_answered"] = False
                                target_data["deadline_result"] = None
                                target_data["reminder_mode"] = new_reminder_mode
                                target_data["deadline_reminder_stopped"] = False
                                target_data["deadline_daily_log"] = []
                                st.rerun()

                    st.write("---")
                    # 操作ボタンエリア（編集・複製・削除）
                    if st.session_state.get("confirm_delete_target_index") == i:
                        st.warning(f"『{target_data['title']}』を削除しますか？この操作は取り消せません。")
                        del_confirm_col, del_cancel_col = st.columns(2)
                        with del_confirm_col:
                            if st.button("🗑️ 削除する", key=f"confirm_delete_target_yes_{i}"):
                                play_click_sound(delay=0)
                                st.session_state.target_list.pop(i)
                                st.session_state.confirm_delete_target_index = None
                                st.rerun()
                        with del_cancel_col:
                            if st.button("やめる", key=f"confirm_delete_target_no_{i}"):
                                play_click_sound(delay=0)
                                st.session_state.confirm_delete_target_index = None
                                st.rerun()
                    else:
                        col_edit, col_copy, col_del = st.columns(3)
                        with col_edit:
                            if st.button("✏️ 編集", key=f"edit_target_{i}", use_container_width=True):
                                play_click_sound(delay=0)
                                st.session_state.editing_target_index = i
                                st.rerun()
                        with col_copy:
                            if st.button("📋 複製", key=f"copy_target_{i}", use_container_width=True):
                                play_click_sound(delay=0)
                                copied_target = {
                                    "title": f"{target_data['title']} (コピー)",
                                    "tasks": target_data["tasks"].copy(),
                                    "completed": False
                                }
                                st.session_state.target_list.insert(i + 1, copied_target)
                                st.success("目標を複製しました！")
                                st.rerun()
                        with col_del:
                            if st.button("🗑️ 削除", key=f"delete_target_{i}", use_container_width=True):
                                play_click_sound(delay=0)
                                st.session_state.confirm_delete_target_index = i
                                st.rerun()

    # --- カレンダー画面 ---
    elif st.session_state.page == "calendar_page":
        st.title("📅 カレンダー画面")
        st.write("これまであなたが「一歩」を達成した記録がここに残っていきます！")

        due_targets = [
            (idx, t) for idx, t in enumerate(st.session_state.target_list)
            if should_prompt_deadline_today(t)
        ]
        for idx, t in due_targets:
            with st.container(border=True):
                st.markdown(f"#### 🎯 『{t['title']}』結果はどうだったかな？")
                result_options = ["0%", "20%", "35%", "50%", "60%〜"]
                result_cols = st.columns(len(result_options))
                for rcol, result_label in zip(result_cols, result_options):
                    with rcol:
                        if st.button(result_label, key=f"banner_deadline_result_{idx}_{result_label}"):
                            play_click_sound(delay=0)
                            record_deadline_answer(t, result_label)
                            st.rerun()
                st.caption("正直に選んでね。0%でもチャレンジしたこと自体がすごいことだよ🌱")
                if st.button("🔕 このリマインドをやめる", key=f"banner_stop_reminder_{idx}"):
                    play_click_sound(delay=0)
                    t["deadline_reminder_stopped"] = True
                    st.rerun()
            st.write("")

        nav_prev, nav_title, nav_next = st.columns([1, 3, 1])
        with nav_prev:
            if st.button("◀ 前月", use_container_width=True, key="cal_prev_month"):
                play_click_sound()
                new_month = st.session_state.calendar_view_month - 1
                new_year = st.session_state.calendar_view_year
                if new_month < 1:
                    new_month = 12
                    new_year -= 1
                st.session_state.calendar_view_month = new_month
                st.session_state.calendar_view_year = new_year
                st.rerun()
        with nav_title:
            st.markdown(
                f"<h3 style='text-align:center;'>{st.session_state.calendar_view_year}年{st.session_state.calendar_view_month}月</h3>",
                unsafe_allow_html=True)
        with nav_next:
            if st.button("次月 ▶", use_container_width=True, key="cal_next_month"):
                play_click_sound()
                new_month = st.session_state.calendar_view_month + 1
                new_year = st.session_state.calendar_view_year
                if new_month > 12:
                    new_month = 1
                    new_year += 1
                st.session_state.calendar_view_month = new_month
                st.session_state.calendar_view_year = new_year
                st.rerun()

        st.write("")
        weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]
        header_cols = st.columns(7)
        for header_col, label in zip(header_cols, weekday_labels):
            header_col.markdown(f"<div style='text-align:center; font-weight:bold;'>{label}</div>",
                                unsafe_allow_html=True)

        cal_obj = cal_module.Calendar(firstweekday=0)
        week_rows = cal_obj.monthdayscalendar(st.session_state.calendar_view_year, st.session_state.calendar_view_month)
        today_str = get_now_jst().strftime("%Y/%m/%d")

        for week in week_rows:
            week_cols = st.columns(7)
            for day_col, day_num in zip(week_cols, week):
                with day_col:
                    if day_num == 0:
                        st.write("")
                    else:
                        cell_date_str = f"{st.session_state.calendar_view_year}/{st.session_state.calendar_view_month:02d}/{day_num:02d}"
                        cell_sticker_preview = get_sticker_preview(cell_date_str, limit=GRID_STICKERS_SHOWN,
                                                                   show_remainder=False)
                        day_label = f"🔹{day_num}" if cell_date_str == today_str else f"{day_num}"

                        has_deadline = any(
                            t.get("deadline") == cell_date_str or any(
                                entry["date"] == cell_date_str for entry in t.get("deadline_daily_log", []))
                            for t in st.session_state.target_list
                        )
                        has_note = bool(st.session_state.calendar_notes.get(cell_date_str))
                        markers = ("🎯" if has_deadline else "") + ("📝" if has_note else "")

                        label_line2 = " ".join(part for part in [cell_sticker_preview, markers] if part)
                        cell_label = f"{day_label} {label_line2}" if label_line2 else day_label

                        is_selected = (cell_date_str == st.session_state.selected_calendar_date)
                        if st.button(cell_label, key=f"cal_day_{cell_date_str}", use_container_width=True,
                                     type="primary" if is_selected else "secondary"):
                            play_click_sound(delay=0)
                            st.session_state.selected_calendar_date = cell_date_str

        st.write("---")
        selected_date_str = st.session_state.selected_calendar_date
        selected_date_display = datetime.strptime(selected_date_str, "%Y/%m/%d").strftime("%Y年%m月%d日")
        st.markdown(f"### 🔍 {selected_date_display} の記録")

        existing_note = st.session_state.calendar_notes.get(selected_date_str, "")
        note_input = st.text_area("📝 この日の一言メモ・予定", value=existing_note,
                                  key=f"note_input_{selected_date_str}", height=80,
                                  placeholder="例：友達とカフェに行く予定など")
        if st.button("💾 メモを保存", key=f"save_note_{selected_date_str}"):
            play_click_sound(delay=0)
            if note_input.strip():
                st.session_state.calendar_notes[selected_date_str] = note_input.strip()
            else:
                st.session_state.calendar_notes.pop(selected_date_str, None)
            st.rerun()

        st.write("---")

        deadline_start_targets = [
            (idx, t) for idx, t in enumerate(st.session_state.target_list)
            if t.get("deadline") == selected_date_str
        ]
        for idx, t in deadline_start_targets:
            is_daily_mode = t.get("reminder_mode") == "daily"
            if t.get("deadline_reminder_stopped"):
                st.caption(f"🎯 『{t['title']}』この日がチャレンジ期限でした（リマインドは停止済み）")
            elif is_daily_mode:
                st.caption(f"🎯 『{t['title']}』この日からチャレンジ開始！（毎日チェックイン形式）")
            elif t.get("deadline_answered"):
                st.info(f"🎯 『{t['title']}』チャレンジ結果：**{t.get('deadline_result', '?')}** 達成")
            elif should_prompt_deadline_today(t):
                st.info(f"🎯 『{t['title']}』の結果はまだ聞けていません。ページ上部で回答できます👆")
            else:
                st.caption(f"🎯 『{t['title']}』この日までチャレンジ！（この日になったら結果を聞くよ）")

        daily_checkin_entries_today = []
        for idx, t in enumerate(st.session_state.target_list):
            for entry in t.get("deadline_daily_log", []):
                if entry["date"] == selected_date_str:
                    daily_checkin_entries_today.append((t, entry))
        for t, entry in daily_checkin_entries_today:
            st.info(f"🎯 『{t['title']}』この日のチェックイン結果：**{entry['result']}**")

        if deadline_start_targets or daily_checkin_entries_today:
            st.write("---")

        daily_candies = [c for c in st.session_state.all_candy_log if c["date"].startswith(selected_date_str)]
        daily_jar_completions = [j for j in st.session_state.jar_complete_log if
                                 j["date"].startswith(selected_date_str)]
        daily_runs = [r for r in st.session_state.course_run_log if r["date"].startswith(selected_date_str)]
        daily_course_completions = [v for v in st.session_state.course_complete_log if
                                    v["date"].startswith(selected_date_str)]
        daily_goal_completions = [g for g in st.session_state.goal_complete_log if
                                  g["date"].startswith(selected_date_str)]

        sticker_line = get_sticker_preview(selected_date_str, limit=MAX_STICKERS_SHOWN, show_remainder=True)
        st.markdown(f"#### 🎨 この日のシール：{sticker_line if sticker_line else '（まだ貼られていません）'}")

        with st.expander(f"⚙️ シールの見た目を設定（現在：{get_current_sticker_emoji()}）"):
            sticker_type_labels = {"circle": "丸", **{k: v["label"] for k, v in STICKER_FIXED_TYPES.items()}}
            sticker_type_keys = list(sticker_type_labels.keys())
            chosen_type = st.radio("シールの種類", options=sticker_type_keys,
                                   format_func=lambda k: sticker_type_labels[k],
                                   index=sticker_type_keys.index(st.session_state.sticker_type), horizontal=True,
                                   key="sticker_type_radio")
            if chosen_type != st.session_state.sticker_type:
                st.session_state.sticker_type = chosen_type
                st.rerun()

            if st.session_state.sticker_type == "circle":
                color_keys = list(STICKER_CIRCLE_COLORS.keys())
                chosen_color = st.radio("丸の色", options=color_keys,
                                        format_func=lambda c: f"{STICKER_CIRCLE_COLORS[c]} {c}",
                                        index=color_keys.index(st.session_state.sticker_color), horizontal=True,
                                        key="sticker_color_radio")
                if chosen_color != st.session_state.sticker_color:
                    st.session_state.sticker_color = chosen_color
                    st.rerun()

        st.write("---")

        # 📊 その日のスケジュール（予定／記録の帯グラフ）を閲覧のみで表示
        st.markdown("### 📊 その日のスケジュール")
        render_schedule_and_events(selected_date_str, editable=False)

        st.write("---")

        if daily_goal_completions:
            for g in daily_goal_completions:
                st.success(f"🏆✨ 『{g['title']}』の目標達成記念日！（{g['date'].split(' ')[1]}）")

        if daily_jar_completions:
            for jar in daily_jar_completions:
                size_label = jar.get("size_label", JAR_SIZE_LABELS.get(jar["capacity"], "?"))
                st.success(f"🍯✨ お菓子のビン({size_label})完成✨（{jar['date'].split(' ')[1]}）")

        if daily_course_completions:
            for v in daily_course_completions:
                st.success(f"🏁✨ 『{v.get('course', 'コース')}』完走達成✨（{v['date'].split(' ')[1]}）")

        if daily_candies:
            st.success(f"🎉 この日は **{len(daily_candies)}個** のお菓子をゲットしました！！")
            for item in daily_candies:
                with st.container(border=True):
                    st.markdown(f"#### {item['emoji']} 放り込んだお菓子（{item['date'].split(' ')[1]}）")
                    st.write(f"**クリアしたクエスト：** {item['task']}")

        if daily_runs:
            st.success(f"🎉 この日は合計 **{sum(r['km'] for r in daily_runs)}km** 走りました！！")
            for run in daily_runs:
                with st.container(border=True):
                    st.markdown(
                        f"#### 🏃 {run.get('course', 'ランニング')}：{run['km']}km 進んだ（{run['date'].split(' ')[1]}）")
                    st.write(f"**クリアしたクエスト：** {run['task']}")
                    if run.get("companion"):
                        st.write(f"**一緒に走った相棒：** 🐾 {run['companion']}")

        if not (
                daily_candies or daily_jar_completions or daily_runs or daily_course_completions or daily_goal_completions):
            st.info("この日の記録はありません")

    # --- ステージ画面 ---
    elif st.session_state.page == "stage_page":
        st.title("⚔️ ステージセレクト")
        st.markdown("### 🎮 挑戦するステージを選んでください：")
        st.write("")
        scol1, scol2, scol3 = st.columns(3)
        with scol1:
            if st.button("🍬\n\nお菓子集め", use_container_width=True, key="stage_candy"):
                play_click_sound()
                st.session_state.page = "candy_page"
                st.rerun()
        with scol2:
            if st.button("🏃‍♂️\n\nランニング", use_container_width=True, key="stage_running"):
                play_click_sound()
                st.session_state.page = "running_page"
                st.rerun()
        with scol3:
            if st.button("📊\n\n一日のスケジュール", use_container_width=True, key="stage_schedule"):
                play_click_sound()
                st.session_state.page = "schedule_page"
                st.rerun()

    # --- 一日のスケジュール画面 ---
    elif st.session_state.page == "schedule_page":
        st.title("📊 一日のスケジュール")
        st.write("今日の「予定」と「記録」を、縦の帯グラフで見比べられます。0時からスタートの24時間表示です。")

        today_str_jst = get_now_jst().strftime("%Y/%m/%d")
        st.caption(f"📅 対象日：{datetime.strptime(today_str_jst, '%Y/%m/%d').strftime('%Y年%m月%d日')}（今日）")

        render_schedule_and_events(today_str_jst, editable=True)

    # --- お菓子集めステージ ---
    elif st.session_state.page == "candy_page":
        st.title("🍬 魔法のお菓子瓶ステージ")

        st.markdown("### 🏺 まずは貯めるお菓子瓶のサイズを決めよう！")
        jar_option = st.selectbox("どの瓶に貯める？", [30, 50, 100],
                                  format_func=lambda x: f"小さめの瓶（{x}個入り）" if x == 30 else (
                                      f"普通の瓶（{x}個入り）" if x == 50 else f"特大の瓶（{x}個入り）"))
        st.session_state.jar_capacity = jar_option

        if jar_option != st.session_state.last_jar_capacity:
            st.session_state.jar_full_sound_played = False
            st.session_state.last_jar_capacity = jar_option

        st.write("---")

        praise_words = [
            "おめでとう！！°˖✧◝(⁰▿⁰)◜✧˖° 本当に素晴らしい一歩だよ！",
            "凄い！よく頑張ったね！！(∩´狂｀)∩", "もしや君は天才…？✨",
            "グッジョブ！！頑張った自分を褒めてあげてね！💪", "最高！！その調子、その調子！♬٩(*^∀^*)۶♬",
            "素晴らしい！今日も未来が変わったね！🌟", "やったね！ハードルを乗り越えた君に拍手！👏👏",
            "最高！100点満点！！👑", "ナイス！！流石だね！！🔥", "凄ーい！山を乗り越えたあなたはもっと強くなるよ🗻！"
        ]

        main_col, side_candy_col = st.columns([3, 1])

        with main_col:
            st.subheader("🏆 達成した目標を選ぼう！")

            if not st.session_state.target_list:
                st.warning("⚠️ まだ目標が登録されていません！「目標登録画面」で目標を作ってきてね！")
                selected_target_title = None
            else:
                target_titles = [t["title"] for t in st.session_state.target_list]
                selected_target_title = st.selectbox("🎯 どの目標を達成した？", target_titles)
                selected_target_data = next(
                    t for t in st.session_state.target_list if t["title"] == selected_target_title)

                level_options = [f"{lv}: {task} (🍬×{lv.split('.')[1]}個パワー)" for lv, task in
                                 selected_target_data["tasks"].items()]
                selected_level_str = st.selectbox("⭐ どのレベルをクリアした？", level_options)

                chosen_lv_key = selected_level_str.split(":")[0]
                chosen_candy_power = int(chosen_lv_key.split(".")[1])
                chosen_task_text = selected_target_data["tasks"][chosen_lv_key]

            st.write("")

            if st.button("➕ この1歩を達成した！", type="primary"):
                if selected_target_title:
                    play_achieve_sound()
                    st.session_state.praise_message = random.choice(praise_words)
                    st.session_state.show_candy_buttons = True
                    st.session_state.temp_candy_count = chosen_candy_power
                    st.session_state.last_completed_task = f"【{selected_target_title} - {chosen_lv_key}】 {chosen_task_text}"
                    add_sticker_for_date(get_now_jst().strftime("%Y/%m/%d"))
                else:
                    st.error("⚠️ 達成する目標を上のメニューから選んでください！")

            if st.session_state.praise_message:
                st.success(st.session_state.praise_message)

            st.write("")
            current_count = len(st.session_state.jar_candies)
            capacity = st.session_state.jar_capacity

            st.markdown(f"### 🏺 現在の瓶の中身 （{current_count} / {capacity} 個）")

            with st.container(border=True):
                if current_count == 0:
                    st.write("瓶はまだ空っぽです。お菓子を選んで入れてね！")
                else:
                    st.markdown(render_candy_jar_svg(st.session_state.jar_candies, capacity), unsafe_allow_html=True)

            if current_count >= capacity:
                st.markdown("## 🎉 おめでとう！！°˖✧◝(⁰▿⁰)◜✧˖°")
                st.balloons()
                st.success(f"素晴らしい！！！{capacity}個のお菓子瓶が完全に満杯になりました！！！")
                if not st.session_state.jar_full_sound_played:
                    play_jar_full_sound()
                    st.session_state.jar_full_sound_played = True
                    st.session_state.jar_complete_log.append({
                        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
                        "capacity": capacity,
                        "size_label": JAR_SIZE_LABELS.get(capacity, "?"),
                        "candies": st.session_state.jar_candies.copy(),
                    })
                    st.session_state.jar_candies = []
                    st.session_state.jar_full_sound_played = False

            st.progress(min(current_count / capacity, 1.0))

            st.write("")
            if st.button("🗄️ 今までの瓶", key="toggle_past_jars"):
                play_click_sound(delay=0)
                st.session_state.show_past_jars = not st.session_state.show_past_jars

            if st.session_state.show_past_jars:
                if not st.session_state.jar_complete_log:
                    st.info("まだ完成した瓶はありません。最初の1本を完成させよう！")
                else:
                    st.markdown("#### 🏺 完成した瓶たち")
                    for jar_record in reversed(st.session_state.jar_complete_log):
                        jar_size_text = jar_record.get("size_label",
                                                       JAR_SIZE_LABELS.get(jar_record.get("capacity"), "?"))
                        with st.expander(f"🍯 {jar_record.get('date', '')} お菓子のビン({jar_size_text})完成✨",
                                         expanded=False):
                            if jar_record.get("candies"):
                                st.markdown(render_candy_jar_svg(jar_record["candies"], jar_record.get("capacity", 30)),
                                            unsafe_allow_html=True)

        with side_candy_col:
            st.markdown("### 🍬 飴を選ぶ")
            if st.session_state.show_candy_buttons:
                st.write(f"あと **{st.session_state.temp_candy_count}** 個 入れてね！")
                candies_spec = [
                    {"emoji": "🍬", "label": "定番キャンディ"},
                    {"emoji": "🍭", "label": "渦巻きロリポップ"},
                    {"emoji": "🍫", "label": "濃厚チョコブロック"},
                    {"emoji": "🍩", "label": "サクサクドーナツ"},
                    {"emoji": "🍪", "label": "チョコチップクッキー"}
                ]
                for candy in candies_spec:
                    if st.button(f"{candy['emoji']}\n\n{candy['label']}", use_container_width=True,
                                 key=f"btn_{candy['emoji']}"):
                        play_click_sound()
                        current_time_str = get_now_jst().strftime("%Y/%m/%d %H:%M")

                        if len(st.session_state.jar_candies) < st.session_state.jar_capacity:
                            new_candy = {
                                "emoji": candy["emoji"],
                                "date": current_time_str,
                                "task": st.session_state.last_completed_task
                            }
                            st.session_state.jar_candies.append(new_candy)
                            st.session_state.all_candy_log.append(new_candy)

                        st.balloons()
                        st.toast(f"{candy['emoji']} を瓶に入れたよ！やったね！")
                        st.session_state.temp_candy_count -= 1

                        if st.session_state.temp_candy_count <= 0:
                            st.session_state.show_candy_buttons = False
                            st.session_state.praise_message = ""
                        st.rerun()
            else:
                st.caption("クエストを達成すると、ここに飴ボタンが出現するよ！")

    # --- ランニングページ ---
    elif st.session_state.page == "running_page":
        st.title("🏃‍♂️ ランニングステージ")

        if st.session_state.companion:
            comp = COMPANIONS[st.session_state.companion]
            st.markdown(f"#### 🐾 現在の相棒：{comp['emoji']} {comp['name']}")
        else:
            st.caption("🐾 まだ相棒が選ばれていません（右下の「相棒選択」から選べます）")

        st.write("走りたいステージを選んでください：")
        st.write("")

        courses_by_tier = {tier: [] for tier in RUNNING_TIER_ORDER}
        for course_key, course in RUNNING_COURSES.items():
            courses_by_tier[course["tier"]].append((course_key, course))

        level_tabs = st.tabs(RUNNING_TIER_ORDER)

        for tab, tier in zip(level_tabs, RUNNING_TIER_ORDER):
            with tab:
                st.markdown(f"### {tier}")
                stage_cols = st.columns(3)
                for col, (course_key, course) in zip(stage_cols, courses_by_tier[tier]):
                    with col:
                        if st.button(f"🏃\n\n{course['name']}", use_container_width=True, key=f"run_{course_key}"):
                            if course["ready"]:
                                play_click_sound()
                                st.session_state.active_course_key = course_key
                                st.session_state.page = "running_course_page"
                                st.rerun()
                            else:
                                play_click_sound(delay=0)
                                st.info(f"🚧 {tier} {course['name']} は現在準備中です！お楽しみに！")

        st.write("---")
        spacer_col, button_col = st.columns([3, 1])
        with button_col:
            if st.button("🐾 相棒選択", use_container_width=True, key="open_companion_picker"):
                play_click_sound(delay=0)
                st.session_state.show_companion_picker = not st.session_state.show_companion_picker

        if st.session_state.show_companion_picker:
            st.markdown("### 🐾 一緒に走る相棒を選んでね！")
            comp_cols = st.columns(3)
            for col, (comp_key, comp_data) in zip(comp_cols, COMPANIONS.items()):
                with col:
                    st.markdown(f"<div style='text-align:center; font-size:64px;'>{comp_data['emoji']}</div>",
                                unsafe_allow_html=True)
                    if st.button(comp_data["name"], use_container_width=True, key=f"pick_companion_{comp_key}"):
                        play_click_sound()
                        st.session_state.companion = comp_key
                        st.session_state.show_companion_picker = False
                        st.rerun()

    # --- 一歩村一周コース等 ---
    elif st.session_state.page == "running_course_page":
        course_key = st.session_state.active_course_key
        course = RUNNING_COURSES[course_key]
        distance_goal = course["distance"]

        st.title(f"🏃‍♂️ {course['name']}")
        st.write(f"全長 **{distance_goal}km** ！目標を達成してゴールを目指そう！")

        if st.session_state.companion:
            comp = COMPANIONS[st.session_state.companion]
            st.markdown(
                f"<div style='font-size:20px;'>{comp['emoji']} <b>{comp['name']}</b> が一緒に走っています！</div>",
                unsafe_allow_html=True)
        else:
            st.caption("🐾 相棒が未選択です。ステージ選択画面の「相棒選択」から選べます。")

        if st.button("← ステージ選択に戻る"):
            play_click_sound()
            st.session_state.page = "running_page"
            st.rerun()

        st.write("---")
        st.subheader("🏆 達成した目標を選ぼう！")

        if not st.session_state.target_list:
            st.warning("⚠️ まだ目標が登録されていません！「目標登録画面」で目標を作ってきてね！")
            selected_course_target_title = None
        else:
            course_target_titles = [t["title"] for t in st.session_state.target_list]
            selected_course_target_title = st.selectbox("🎯 どの目標を達成した？", course_target_titles,
                                                        key=f"course_target_select_{course_key}")
            selected_course_target_data = next(
                t for t in st.session_state.target_list if t["title"] == selected_course_target_title)

            course_level_options = [f"{lv}: {task} (🏃×{lv.split('.')[1]}km進む)" for lv, task in
                                    selected_course_target_data["tasks"].items()]
            selected_course_level_str = st.selectbox("⭐ どのレベルをクリアした？", course_level_options,
                                                     key=f"course_level_select_{course_key}")

            course_chosen_lv_key = selected_course_level_str.split(":")[0]
            course_chosen_km = int(course_chosen_lv_key.split(".")[1])

        st.write("")

        if st.button("➕ この1歩を達成した！", type="primary", key=f"course_achieve_button_{course_key}"):
            if selected_course_target_title:
                play_achieve_sound()
                current_km = st.session_state.course_km.get(course_key, 0)
                new_total_km = min(current_km + course_chosen_km, distance_goal)
                st.session_state.course_km[course_key] = new_total_km

                if course_chosen_km == 5:
                    message = "🌬️ 絶好調！追い風が来た！一気に5km進んだよ！"
                elif new_total_km >= distance_goal * (2 / 3):
                    message = random.choice(COURSE_LATE_PRAISE_WORDS)
                else:
                    message = random.choice(COURSE_PRAISE_WORDS)

                bonus_km, bonus_message = maybe_apply_bonus(course_key)
                total_km_for_log = course_chosen_km
                if bonus_km:
                    boosted_km = min(st.session_state.course_km[course_key] + bonus_km, distance_goal)
                    st.session_state.course_km[course_key] = boosted_km
                    message = f"{message}\n\n{bonus_message}"
                    total_km_for_log += bonus_km

                if st.session_state.companion:
                    comp_info = COMPANIONS[st.session_state.companion]
                    comp_line = random.choice(COMPANION_MESSAGES[st.session_state.companion])
                    message = f"{message}\n\n{comp_info['emoji']} {comp_info['name']}「{comp_line}」"

                st.session_state.course_praise_message[course_key] = message

                course_task_text = selected_course_target_data["tasks"][course_chosen_lv_key]
                companion_name = COMPANIONS[st.session_state.companion]["name"] if st.session_state.companion else None
                st.session_state.course_run_log.append({
                    "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
                    "course": course["name"],
                    "km": total_km_for_log,
                    "task": f"【{selected_course_target_title} - {course_chosen_lv_key}】 {course_task_text}",
                    "companion": companion_name,
                })
                add_sticker_for_date(get_now_jst().strftime("%Y/%m/%d"))
            else:
                st.error("⚠️ 達成する目標を上のメニューから選んでください！")

        if st.session_state.course_praise_message.get(course_key):
            st.success(st.session_state.course_praise_message[course_key])

        current_km = st.session_state.course_km.get(course_key, 0)
        st.write("")
        st.markdown(f"### 🗺️ 現在の走行距離：{current_km} / {distance_goal} km")
        st.progress(min(current_km / distance_goal, 1.0))

        if current_km >= distance_goal:
            st.markdown("## 🎉 ゴール達成！おめでとう！！")
            st.balloons()
            st.success(f"素晴らしい！！！『{course['name']}』を走りきりました！！！")
            if not st.session_state.course_complete_sound_played.get(course_key, False):
                play_jar_full_sound()
                st.session_state.course_complete_sound_played[course_key] = True
                st.session_state.course_complete_log.append({
                    "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
                    "course": course["name"],
                })
                if st.session_state.companion:
                    complete_line = random.choice(COMPANION_COMPLETE_MESSAGES[st.session_state.companion])
                    st.session_state.course_complete_companion_message[course_key] = complete_line

            if st.session_state.companion and course_key in st.session_state.course_complete_companion_message:
                comp_info = COMPANIONS[st.session_state.companion]
                comp_line = st.session_state.course_complete_companion_message[course_key]
                st.info(f"{comp_info['emoji']} {comp_info['name']}「{comp_line}」")

# =====================================================
# 💾 Supabase への自動セーブ
# =====================================================
if st.session_state.get("game_started"):
    save_progress()
