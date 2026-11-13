import streamlit as st
from datetime import datetime, date, timedelta
import zoneinfo
import random
import html
import base64
import os
import time
import calendar as cal_module
import json
import copy
from supabase import create_client, Client

# 日本標準時（JST）の定義
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


def stage_tab_selector(labels, key):
    """st.tabs の代わりに使うタブ切り替え。
    st.tabs は、ボタンを押して画面が更新されるたびに先頭のタブへ戻ってしまう。
    そこで選んだタブを session_state に覚えておき、アクションの後もそのタブにとどまるようにする。
    選ばれているタブの名前（labels のどれか）を返す。使う側は `if 選択中 == "ラベル":` で中身を出す。"""
    if st.session_state.get(key) not in labels:
        st.session_state[key] = labels[0]
    return st.radio("タブ", labels, key=key, horizontal=True, label_visibility="collapsed")


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
    .aqua-growth-message { text-align:center; font-size:30px; font-weight:800; margin:14px 0; animation:aqua-pop .55s ease-out; }
    .aqua-milestone { position:relative; overflow:hidden; text-align:center; padding:18px 8px 8px; border-radius:18px; background:linear-gradient(180deg, rgba(225,247,255,.9), rgba(255,255,255,.7)); margin:12px 0; }
    .aqua-milestone-title { position:relative; z-index:2; font-size:30px; font-weight:900; margin:4px 0 12px; animation:aqua-pop .6s ease-out; }
    .aqua-fish-burst { position:relative; height:150px; overflow:hidden; }
    .aqua-fish-burst span { position:absolute; bottom:-60px; font-size:30px; animation:aqua-rise 2.2s ease-out forwards; animation-delay:var(--delay); left:var(--left); }
    @keyframes aqua-rise { 0% { transform:translateY(0) rotate(0deg); opacity:0; } 12% { opacity:1; } 100% { transform:translateY(-220px) rotate(var(--rotate)); opacity:0; } }
    @keyframes aqua-pop { 0% { transform:scale(.7); opacity:0; } 70% { transform:scale(1.08); opacity:1; } 100% { transform:scale(1); opacity:1; } }
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
AQUA_POINT_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "パパッ.mp3")
AQUA_GACHA_LOW_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "ペタッ.mp3")
AQUA_GACHA_THREE_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "きらーん1.mp3")
AQUA_FEED_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "コルク栓を抜く.mp3")
CANDY_CRAFT_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "決定ボタンを押す21.mp3")  # スイーツを作るとき

JAR_SIZE_LABELS = {5: "XS", 10: "S", 20: "M", 30: "L"}  # 5(XS)は過去の瓶の履歴表示用。選べるのは10/20/30


def jar_size_label(capacity: int) -> str:
    return JAR_SIZE_LABELS.get(capacity, "?")


# =====================================================
# 🐠 水族館ステージ
# =====================================================
# =====================================================
# 🐠 魚データ（data/fish.jsonから読み込み）
# =====================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FISH_DATA_PATH = os.path.join(BASE_DIR, "data", "fish.json")

try:
    with open(FISH_DATA_PATH, "r", encoding="utf-8") as f:
        ALL_FISH = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    st.error(f"魚データ（data/fish.json）の読み込みに失敗しました: {e}")
    st.stop()

AQUA_GACHA_FISH = [
    fish for fish in ALL_FISH
    if fish.get("gacha", False)
]

AQUA_SHOP_FISH = [
    fish for fish in ALL_FISH
    if fish.get("shop", False)
]

# 1cmからさらに1cm育つたびに獲得する豪華度
# 2.0cm、3.0cm、4.0cm…に到達するたび、その魚の☆数ぶん豪華度を加算。
# 初期1.0cmには成長による豪華度ボーナスはない。
AQUA_GROWTH_BONUS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

AQUA_DECORATIONS = [
    {"id": "seaweed", "name": "ゆらゆら海藻", "emoji": "🌿", "price": 3, "score": 2},
    {"id": "coral", "name": "カラフルサンゴ", "emoji": "🪸", "price": 5, "score": 3},
    {"id": "pot", "name": "沈んだ壺", "emoji": "🏺", "price": 6, "score": 4},
    {"id": "castle", "name": "海底のお城", "emoji": "🏰", "price": 10, "score": 7},
    {"id": "treasure", "name": "宝箱", "emoji": "💎", "price": 12, "score": 8},
]

# =====================================================
# 🪸 飾りガチャ（data/goods.jsonから読み込み）
# =====================================================
# goods.json の形式（リスト）:
#   {"id": "jellyfish_lamp", "name": "クラゲランプ", "emoji": "🪼", "stars": 3, "weight": 10}
#   stars  : 1〜5（そのまま豪華度になる）
#   weight : 出やすさ（大きいほど出やすい。省略時は1）
#   gacha  : false にするとガチャから外せる（省略時はtrue）
# ※ idはショップの飾り（seaweed等）や他のグッズと重ならないようにしてください。
AQUA_DECOR_GACHA_PRICE = 5  # 飾りガチャ1回に必要なIPPOポイント
GOODS_DATA_PATH = os.path.join(BASE_DIR, "data", "goods.json")


def load_aqua_decor_gacha() -> list:
    try:
        with open(GOODS_DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    items = []
    for item in raw if isinstance(raw, list) else []:
        if not item.get("gacha", True):
            continue
        if not all(item.get(k) for k in ("id", "name", "emoji")):
            continue
        stars = max(1, min(5, int(item.get("stars", 1))))
        weight = float(item.get("weight", 1))
        if weight <= 0:
            continue
        items.append({"id": item["id"], "name": item["name"], "emoji": item["emoji"],
                      "stars": stars, "weight": weight})
    return items


AQUA_GACHA_DECORATIONS = load_aqua_decor_gacha()

AQUA_TANK_LEVELS = [
    {"level": 1, "required": 0, "name": "小さな水槽", "size": "60cm水槽"},
    {"level": 2, "required": 35, "name": "にぎやかな水槽", "size": "90cm水槽"},
    {"level": 3, "required": 90, "name": "大きな水槽", "size": "120cm水槽"},
    {"level": 4, "required": 180, "name": "豪華な水族館", "size": "大型パノラマ水槽"},
    {"level": 5, "required": 320, "name": "夢の大水族館", "size": "巨大パノラマ水槽"},
]

AQUA_FOOD = {
    "normal": {"name": "通常餌", "emoji": "🫧", "price": 2, "feed_points": 1, "pack": 3},
    "premium": {"name": "高級餌", "emoji": "✨", "price": 5, "feed_points": 3, "pack": 3},
    "bundle": {"name": "みんなの餌の塊", "emoji": "🍙", "price": 8, "feed_points": 3, "pack": 1},
    "grand_bundle": {"name": "全体の餌の塊", "emoji": "🎁", "price": 35, "feed_points": 3, "pack": 1},
}


def get_fish_stars(fish: dict) -> int:
    """旧データのN/R/SRも星に移行し、既存の魚を失わない。"""
    if "stars" in fish:
        return max(1, min(5, int(fish["stars"])))
    match = next((f for f in AQUA_GACHA_FISH + AQUA_SHOP_FISH
                  if f["id"] == fish.get("id")), None)
    if match:
        return match["stars"]
    return {"N": 1, "R": 3, "SR": 4}.get(fish.get("rarity"), 1)


def fish_display_name(fish: dict) -> str:
    return fish.get("custom_name") or fish.get("default_name") or fish.get("name", "魚")


def normalize_aqua_fish():
    """既存データも魚種別A/B/Cの表示名と展示設定に移行。"""
    counts = {}
    for fish in st.session_state.get("aqua_fish", []):
        species = fish.get("id", fish.get("name", "unknown"))
        counts[species] = counts.get(species, 0) + 1
        ordinal = counts[species]
        # 既存のデフォルト名は保存済みのカスタム名を上書きしない
        fish.setdefault("default_name", f"{fish.get('name', '魚')}{fish_letter(ordinal)}")
        fish.setdefault("custom_name", "")
        fish.setdefault("display", True)


def normalize_aqua_decorations():
    """既存の飾りデータにも展示設定（display）を付ける。旧データは展示中として扱う。"""
    for decor in st.session_state.get("aqua_decorations", []):
        decor.setdefault("display", True)


def toggle_decoration_display(index: int):
    """飾りの「展示する」チェックが変わったときに呼ばれる。"""
    decorations = st.session_state.get("aqua_decorations", [])
    if 0 <= index < len(decorations):
        decorations[index]["display"] = bool(st.session_state.get(f"aqua_decor_show_{index}", True))
        save_progress()


def fish_letter(number: int) -> str:
    result = ""
    while number:
        number, digit = divmod(number - 1, 26)
        result = chr(65 + digit) + result
    return result


def obtain_aqua_fish(species: dict) -> tuple[bool, int]:
    """同種5匹まで。超過時は星数ぶん豪華度に変換。"""
    owned = sum(f.get("id") == species["id"] for f in st.session_state.aqua_fish)
    if owned >= 5:
        bonus = species["stars"]
        st.session_state.aqua_duplicate_bonus = st.session_state.get("aqua_duplicate_bonus", 0) + bonus
        return False, bonus
    used_names = {f.get("default_name") for f in st.session_state.aqua_fish if f.get("id") == species["id"]}
    ordinal = 1
    while f"{species['name']}{fish_letter(ordinal)}" in used_names:
        ordinal += 1
    st.session_state.aqua_fish.append({
        "id": species["id"], "name": species["name"], "emoji": species["emoji"],
        "stars": species["stars"], "feed_points": 0, "size_mm": 10.0,
        "default_name": f"{species['name']}{fish_letter(ordinal)}",
        "custom_name": "", "display": True,
    })
    return True, 0


def give_fish_food(fish_index: int, food_key: str, count: int = 1, play_sound: bool = True):
    """餌の成長ポイントを加算し、5ポイントごとに0.1cm成長させる。"""
    fish = st.session_state.aqua_fish[fish_index]
    old_size_mm = float(fish.get("size_mm", 10.0))
    points = AQUA_FOOD[food_key]["feed_points"] * count
    fish["feed_points"] = fish.get("feed_points", 0) + points

    # 5成長ポイント = 0.1cm。
    # 初期値は1.0cmなので、最初の5ポイントで1.1cmになる。
    growth_steps = fish["feed_points"] // 5
    fish["size_mm"] = round(10.0 + growth_steps * 1.0, 1)
    queue_aqua_growth_notification(fish, old_size_mm, fish["size_mm"])

    st.session_state.aqua_feed_log.append({
        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
        "fish": fish_display_name(fish), "food": AQUA_FOOD[food_key]["name"],
        "count": count, "points": points,
    })
    if play_sound:
        play_aqua_feed_sound(delay=0)


def queue_aqua_growth_notification(fish: dict, old_size_mm: float, new_size_mm: float):
    """魚の成長演出をキューに入れる。1cm刻みの到達時は特別演出も付ける。"""
    old_cm = old_size_mm / 10.0
    new_cm = new_size_mm / 10.0
    if new_cm <= old_cm:
        return
    queue = st.session_state.setdefault("aqua_growth_notifications", [])
    name = fish_display_name(fish)
    queue.append({"type":"growth", "name":name, "cm":new_cm})
    first_milestone = max(2, int(old_cm) + 1)
    last_milestone = int(new_cm)
    for cm in range(first_milestone, last_milestone + 1):
        if old_cm < cm <= new_cm:
            queue.append({"type":"milestone", "name":name, "cm":cm, "emoji":fish.get("emoji","🐟")})

def render_aqua_growth_notifications():
    """餌やり欄に魚の成長メッセージを表示し、成長に応じた効果音を鳴らす。"""
    queue = st.session_state.get("aqua_growth_notifications", [])
    if not queue:
        return

    # 0.1cm成長ごとに正解音、整数cm到達時には歓声と拍手を鳴らす。
    # 1cm到達時は「0.1cm成長」の通知も同時に存在するため、両方を順番に再生する。
    has_small_growth = any(notice.get("type") == "growth" for notice in queue)
    has_milestone = any(notice.get("type") == "milestone" for notice in queue)

    if has_small_growth:
        play_achieve_sound(delay=0)
    if has_milestone:
        play_jar_full_sound(delay=0)

    for notice in queue:
        if notice.get("type") == "growth":
            st.markdown(
                f'<div class="aqua-growth-message">🐠 {html.escape(notice["name"])}が成長したよ！</div>',
                unsafe_allow_html=True,
            )
        elif notice.get("type") == "milestone":
            emoji = html.escape(notice.get("emoji", "🐟"))
            burst = "".join(
                f'<span style="--left:{(i*17+3)%97}%; --delay:{(i%9)*0.08:.2f}s; --rotate:{(-18+(i*13)%37)}deg">{emoji}</span>'
                for i in range(28)
            )
            message = (
                f'<div class="aqua-milestone">'
                f'<div class="aqua-milestone-title">🎉 {html.escape(notice["name"])}が {notice["cm"]}cm にまで成長した！！おめでとう！！ 🎉</div>'
                f'<div class="aqua-fish-burst">{burst}</div></div>'
            )
            st.markdown(message, unsafe_allow_html=True)

    # 表示・効果音ともに一度だけ。
    st.session_state.aqua_growth_notifications = []


def get_aqua_tank_score() -> int:
    fish_score = len(st.session_state.get("aqua_fish", [])) * 5
    decor_score = sum(d.get("score", 1) for d in st.session_state.get("aqua_decorations", []))

    # 初期1.0cmは成長ボーナス0。
    # 2.0cmに到達すると1回、3.0cmに到達するとさらに1回…というように、
    # 「整数cmに到達した回数」×「その魚の☆数」を加算する。
    growth_score = 0
    for fish in st.session_state.get("aqua_fish", []):
        size_mm = max(10, int(round(float(fish.get("size_mm", 10.0)))))
        reached_cm = max(0, size_mm // 10 - 1)  # 1cm→0、2cm→1、3cm→2…
        stars = get_fish_stars(fish)
        growth_score += reached_cm * AQUA_GROWTH_BONUS.get(stars, stars)

    return fish_score + decor_score + growth_score + st.session_state.get("aqua_duplicate_bonus", 0)


def get_aqua_tank_level() -> dict:
    score = get_aqua_tank_score()
    current = AQUA_TANK_LEVELS[0]
    for level_data in AQUA_TANK_LEVELS:
        if score >= level_data["required"]:
            current = level_data
    return current


def sync_aqua_tank_history():
    """達成した水槽レベルを一度だけ記録する。過去の到達日は推測しない。"""
    history = st.session_state.get("aqua_tank_history")
    score = get_aqua_tank_score()
    if history is None:
        # 旧データ移行時、既に到達済みのLvは日付不明として保持する。
        history = {str(entry["level"]): None for entry in AQUA_TANK_LEVELS
                   if score >= entry["required"]}
        if not st.session_state.get("aqua_fish") and not st.session_state.get("aqua_decorations"):
            history["1"] = get_now_jst().strftime("%Y/%m/%d")
        st.session_state.aqua_tank_history = history
        save_progress()
    else:
        changed = False
        for entry in AQUA_TANK_LEVELS:
            key = str(entry["level"])
            if score >= entry["required"] and key not in history:
                history[key] = get_now_jst().strftime("%Y/%m/%d")
                changed = True
        if changed:
            save_progress()
    return history


def add_aqua_reward(level: int, source: str):
    """旧バージョン互換：目標Lv.達成を交換券として記録する。"""
    st.session_state.aqua_reward_queue.append({
        "level": level,
        "source": source,
        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
    })


def render_aquarium_tank() -> str:
    level_data = get_aqua_tank_level()
    fish = [f for f in st.session_state.get("aqua_fish", []) if f.get("display", True)]
    decorations = [d for d in st.session_state.get("aqua_decorations", []) if d.get("display", True)]
    fish_html = "".join(
        f'<span title="{html.escape(fish_display_name(f), quote=True)} {f.get("size_mm", 10.0):.1f}mm" '
        f'style="font-size:{max(28, min(70, 30 + f.get("size_mm", 10.0) * 0.7)):.0f}px; margin:8px;">'
        f'{f.get("emoji", "🐟")}</span>' for f in fish
    )
    decor_html = "".join(
        f'<span title="{d.get("name", "置物")}" style="font-size:38px; margin:5px;">{d.get("emoji", "🪸")}</span>'
        for d in decorations
    )
    if not fish_html and not decor_html:
        fish_html = '<span style="font-size:48px; opacity:.6;">🌊</span>'
    tank_height = 280 + (level_data["level"] - 1) * 55
    return f"""
    <div style="border:4px solid #78c7e8; border-radius:24px; padding:18px; min-height:{tank_height}px;
                background:linear-gradient(#c9f3ff 0%, #8dd8ef 48%, #3fa8c5 49%, #176b8a 100%);
                box-shadow:inset 0 0 25px rgba(255,255,255,.65); text-align:center;">
        <div style="font-weight:bold; color:#07506a; background:rgba(255,255,255,.72); border-radius:12px; padding:6px; display:inline-block;">
            Lv.{level_data['level']} {level_data['name']} ／ {level_data['size']}
        </div>
        <div style="margin-top:80px;">{decor_html}{fish_html}</div>
        <div style="margin-top:30px; color:white; font-weight:bold;">🐚 水槽の中を育てよう！ 🐚</div>
    </div>
    """


def feed_selected_fish(fish_index: int, food_key: str) -> bool:
    inventory = st.session_state.aqua_food_inventory
    inventory.setdefault("grand_bundle", 0)
    food = AQUA_FOOD[food_key]
    if inventory.get(food_key, 0) <= 0 or not (0 <= fish_index < len(st.session_state.aqua_fish)):
        return False
    inventory[food_key] -= 1
    give_fish_food(fish_index, food_key)
    return True


# =====================================================
# 🦖 恐竜レース（すごろく）
# =====================================================
# ・お菓子屋さん・水族館・恐竜レースは、すべてIPPOポイントを共有します。
# ・新しい恐竜を増やすときは DINO_SPECIES に1つ書き足してください。
DINO_DICE_COST = 3          # サイコロ1回に必要なIPPOポイント
DINO_MAX_LEVEL = 10
DINO_BATTLE_WIN_EXP = 6
DINO_BATTLE_LOSE_EXP = 2
DINO_SPECIAL_USES = 2
DINO_BATTLE_PRACTICE_EXP = 0  # 模型との練習では経験値・報酬なし

DINO_BERRIES = {
    "hp": {"name": "いのちの木の実", "emoji": "❤️", "stat": "hp", "label": "最大HP"},
    "hp_plus": {"name": "大きないのちの木の実", "emoji": "💖", "stat": "hp", "label": "最大HP"},
    "attack": {"name": "ちからの木の実", "emoji": "⚔️", "stat": "attack", "label": "攻撃力"},
    "attack_plus": {"name": "大きなちからの木の実", "emoji": "💥", "stat": "attack", "label": "攻撃力"},
    "speed": {"name": "はやさの木の実", "emoji": "💨", "stat": "speed", "label": "素早さ"},
    "speed_plus": {"name": "大きなはやさの木の実", "emoji": "🌪️", "stat": "speed", "label": "素早さ"},
}        # 固有技は1回の力試しで使える回数

DINO_DATA_PATH = os.path.join(BASE_DIR, "data", "dino.json")
DINO_SHOP_DATA_PATH = os.path.join(BASE_DIR, "data", "dino_shop.json")
with open(DINO_DATA_PATH, "r", encoding="utf-8") as f:
    DINO_SPECIES = json.load(f)
with open(DINO_SHOP_DATA_PATH, "r", encoding="utf-8") as f:
    DINO_SHOP_DATA = json.load(f)


DINO_GACHA_COST_POINTS = 5              # 恐竜ガチャ1回に必要なIPPOポイント
DINO_GACHA_RATES = {1: 40, 2: 30, 3: 18, 4: 9, 5: 3}   # ★ごとの出やすさ
DINO_GACHA_DUP_EXP_PER_STAR = 10       # すでに仲間の恐竜が出たとき、★1つにつきもらえる経験値

# ---------- 固有技（バトル）の種類。dino.json の "special" で指定する ----------
# （書いていない恐竜は、下の初期設定を使う。新しい種類を増やすときは dino_special_effect に1つ足す）
#   multi_hit  : 連続攻撃。hits_min〜hits_max 回、1回ごとに hit_min〜hit_max ダメージ
#   recoil_hit : 反動つき攻撃。min〜max の大ダメージ＋自分も recoil_min〜recoil_max ダメージ
#   heal_hit   : 回復つき攻撃。min〜max ダメージ＋自分のHPを heal 回復
#   stun_hit   : 麻痺つき攻撃。min〜max ダメージ＋chance（初期30%）で相手を1ターン行動不能に
#   counter    : カウンター。相手の攻撃を受けて、受けたダメージを multiplier倍（初期2倍）にして返す。
#                相手がぼうぎょしていたら不発
#   random     : 完全ランダム。他の恐竜の固有技を1つランダムで選んで発動する
DINO_SPECIAL_DEFAULTS = {
    "velociraptor": {"type": "multi_hit", "hits_min": 2, "hits_max": 5, "hit_min": 1, "hit_max": 3},
    "stegosaurus": {"type": "heal_hit", "min": 3, "max": 6, "heal": 2},
    "triceratops": {"type": "recoil_hit", "min": 7, "max": 12, "recoil_min": 2, "recoil_max": 4},
}

# ---------- 固有能力（レース）の種類。dino.json の "passive" で指定する ----------
# 3つの系統があり、どれもサイコロを振るたびに判定される（発動確率はレベルで上がる。chance_scale で調整できる）。
#   type "pickup"（🎒 拾う系）：item に拾うものを1種類だけ指定する
#       item "berry"        : 木の実を1個（berries で種類ごとの出やすさを指定できる）
#       item "special_dice" : スペシャルダイスを1個
#       item "drink"        : 能力アップドリンク（dino_shop.json の stat_items）を1本（drinks で種類を絞れる）
#       item "ippo_points"  : IPPOポイントを min〜max 個
#   type "move"（👣 進む系）：effect に効果を指定する
#       effect "extra_steps": 出た目に steps マス追加で進む
#       effect "double_dice": 出た目の2倍進む
#       effect "dice_map"   : 出た目が when のとき、必ず steps マス進む（確率なし）
#   type "ambush"（⚔️ バトル系）：バトルマス以外でもいきなり野良恐竜とのバトルになる（挑むかは自由）。
#       勝つと経験値が exp_multiplier 倍。負けると、出た目のぶんだけ後戻りする
DINO_PASSIVE_DEFAULTS = {
    "velociraptor": {"type": "pickup", "item": "ippo_points", "min": 1, "max": 3,
                     "message": "🦖 ヴェロキラプトルが仲間を呼んだ！ 仲間たちから {n} IPPOポイントもらった！"},
    "stegosaurus": {"type": "move", "effect": "dice_map", "when": [1, 2, 3], "steps": 6, "use_chance": True},
    "triceratops": {"type": "move", "effect": "extra_steps", "steps": 1},
}
DINO_PASSIVE_KIND_LABELS = {"pickup": "🎒 拾う系", "move": "👣 進む系", "ambush": "⚔️ バトル系"}
DINO_BERRY_PICKUP_DEFAULT = {"hp": 3, "attack": 3, "speed": 3, "hp_plus": 1, "attack_plus": 1, "speed_plus": 1}

DINO_FOOD = {
    "meat": {"name": "こんがり肉", "emoji": "🍖", "price": 2, "exp": 3},
    "feast": {"name": "ごちそう肉", "emoji": "🍗", "price": 5, "exp": 8},
}

# 野良恐竜（力試しの相手）
WILD_DINOS = [
    {"name": "コンプソグナトゥス", "emoji": "🦎"},
    {"name": "アンキロサウルス", "emoji": "🐢"},
    {"name": "パラサウロロフス", "emoji": "🦕"},
    {"name": "ディロフォサウルス", "emoji": "🐊"},
    {"name": "ティラノサウルス", "emoji": "🦖"},
]

# コース。1マス＝100m。ready=Falseのコースは「準備中」表示になります。
DINO_COURSES = {
    "beginner": {"name": "はじめての恐竜レース", "tier": "🟢 初級", "distance_km": 5, "ready": True},
    "intermediate": {"name": "恐竜ロードレース", "tier": "🟡 中級", "distance_km": 10, "ready": False},
    "advanced": {"name": "恐竜サバイバルレース", "tier": "🔴 上級", "distance_km": 20, "ready": False},
    "survival": DINO_SHOP_DATA["courses"]["survival"],
    "relax": DINO_SHOP_DATA["courses"]["relax"],
}

DINO_BOOST_MESSAGES = ["💨 追い風が来た！", "🌟 近道を見つけた！", "🌋 地面がゆれて背中を押された！"]
DINO_SOUND_PRIORITY = {"click": 0, "feed": 1, "points": 1, "achieve": 2, "finish": 3}


def dino_exp_for_level(level: int) -> int:
    """そのレベルに必要な累計経験値。Lv2=10、Lv3=30、Lv4=60…"""
    return 10 * level * (level - 1) // 2


def dino_level_from_exp(exp: int) -> int:
    level = 1
    while level < DINO_MAX_LEVEL and exp >= dino_exp_for_level(level + 1):
        level += 1
    return level


def dino_level(dino: dict) -> int:
    return dino_level_from_exp(dino.get("exp", 0))


def dino_display_name(dino: dict) -> str:
    return dino.get("custom_name") or DINO_SPECIES[dino["species"]]["name"]


def dino_max_hp(dino: dict) -> int:
    return DINO_SPECIES[dino["species"]]["base_hp"] + (dino_level(dino) - 1) * 3 + int(dino.get("hp_bonus", 0))


def dino_attack(dino: dict) -> int:
    return dino_power_bonus(dino_level(dino)) + int(dino.get("attack_bonus", 0))

def dino_speed(dino: dict) -> int:
    return dino_level(dino) + int(dino.get("speed_bonus", 0))

def dino_base_dodge_rate(speed: int) -> int:
    """素早さに応じた基本回避率（%）。"""
    if speed < 10:
        return 1
    if speed < 20:
        return 10
    if speed < 30:
        return 20
    if speed < 40:
        return 30
    if speed < 50:
        return 40
    return 50

def dino_dodge_rate(defender_speed: int, attacker_speed: int, special: bool = False) -> int:
    """相手との素早さ差と攻撃種別を反映した回避率（%）。"""
    rate = dino_base_dodge_rate(defender_speed) + defender_speed - attacker_speed
    if special:
        rate -= 20
    return max(0, min(30 if special else 50, rate))

def dino_power_bonus(level: int) -> int:
    """Lv4でダメージ+1、Lv7で+2、Lv10で+3。"""
    return (level - 1) // 3


def dino_passive_chance(level: int) -> float:
    """固有能力が発動する確率。Lv1で20%、Lv10で47%。"""
    return min(0.5, 0.20 + 0.03 * (level - 1))


def dino_passive(species_key: str):
    """その恐竜の固有能力の設定（なければNone）。"""
    return DINO_SPECIES[species_key].get("passive") or DINO_PASSIVE_DEFAULTS.get(species_key)


def dino_passive_effective_chance(species_key: str, level: int):
    """固有能力の発動確率（0〜1）。出た目で必ず発動するタイプは None。"""
    passive = dino_passive(species_key)
    if not passive or (passive.get("effect") == "dice_map" and not passive.get("use_chance")):
        return None
    return min(1.0, dino_passive_chance(level) * float(passive.get("chance_scale", 1.0)))


def dino_passive_caption(species_key: str, level: int) -> str:
    """固有能力の説明（系統・名前・内容・発動確率）。"""
    info = DINO_SPECIES[species_key]
    passive = dino_passive(species_key)
    label = DINO_PASSIVE_KIND_LABELS.get(passive["type"], "✨") if passive else "✨"
    text = f"{label}『{info['passive_name']}』：{info['passive_text']}"
    chance = dino_passive_effective_chance(species_key, level)
    if chance is not None:
        text += f"（発動確率 {int(round(chance * 100))}%）"
    return text


def dino_passive_move(passive: dict, dice: int, chance: float, who: str, info: dict):
    """進む系。(進むマス数, 表示メッセージ or None) を返す。"""
    name = info["passive_name"]
    effect = passive.get("effect")
    if effect == "dice_map":
        when = passive.get("when", 1)
        when_list = when if isinstance(when, list) else [when]      # 1つでも、[1, 2, 3] のような複数でもOK
        if dice in [int(w) for w in when_list]:
            if passive.get("use_chance") and random.random() >= chance:
                return dice, None                                      # 確率に外れたら、出た目のまま
            steps = int(passive["steps"])
            return steps, f"✨ {who}の『{name}』！ 出た目は{dice}だけど、{steps}マス進める！"
        return dice, None
    if random.random() >= chance:
        return dice, None
    if effect == "double_dice":
        return dice * 2, f"🌪️ {who}の『{name}』！ 出た目の2倍、{dice * 2}マス進む！"
    if effect == "extra_steps":
        extra = int(passive.get("steps", 1))
        return dice + extra, f"💨 {who}の『{name}』！ さらに +{extra}マス進む！（合計 {dice + extra}マス）"
    return dice, None
def dino_passive_pickup(passive: dict, who: str, info: dict):
    """拾う系。決まった種類のものを1つだけ拾ってくる。"""
    name = info["passive_name"]
    item = passive.get("item")
    if item == "ippo_points":
        n = random.randint(int(passive["min"]), int(passive["max"]))
        st.session_state.ippo_points += n
        template = passive.get("message", "🎒 {who}の『{pn}』！ IPPOポイントを {n} 個拾ってきた！")
        add_dino_message(template.format(who=who, pn=name, n=n))
    elif item == "special_dice":
        st.session_state.dino_special_dice = int(st.session_state.get("dino_special_dice", 0)) + 1
        add_dino_message(f"🎒 {who}の『{name}』！ 🌟 スペシャルダイスを1個拾ってきた！")
    elif item == "berry":
        weights = {k: w for k, w in (passive.get("berries") or DINO_BERRY_PICKUP_DEFAULT).items() if k in DINO_BERRIES}
        if not weights:
            return
        berry_key = random.choices(list(weights), weights=list(weights.values()), k=1)[0]
        inventory = st.session_state.setdefault("dino_berries", {})
        inventory[berry_key] = inventory.get(berry_key, 0) + 1
        berry = DINO_BERRIES[berry_key]
        add_dino_message(f"🎒 {who}の『{name}』！ {berry['emoji']} {berry['name']}を拾ってきた！")
    elif item == "drink":
        weights = passive.get("drinks") or {}
        pool = [i for i in DINO_SHOP_DATA.get("stat_items", []) if not weights or i["id"] in weights]
        if not pool:
            return
        pick = random.choices(pool, weights=[float(weights.get(i["id"], 1)) for i in pool], k=1)[0]
        inventory = st.session_state.setdefault("dino_stat_items", {})
        inventory[pick["id"]] = inventory.get(pick["id"], 0) + 1
        add_dino_message(f"🎒 {who}の『{name}』！ {pick['emoji']} {pick['name']}を拾ってきた！")
    else:
        return
    queue_dino_sound("points")


def dino_passive_try_ambush(passive: dict, course_key: str, partner: dict, dice: int, chance: float, who: str, info: dict) -> bool:
    """バトル系。バトルマス以外でも、一定確率でいきなりバトルのお誘いが来る（挑むかは自由）。"""
    race = get_dino_race(course_key)
    if race["finished"] or race["pending_battle"] or random.random() >= chance:
        return False
    enemy = make_wild_dino(partner)
    multiplier = float(passive.get("exp_multiplier", 2))
    enemy["ambush"] = {"exp_multiplier": multiplier, "back_steps": int(dice)}
    race["pending_battle"] = enemy
    add_dino_message(f"⚡ {who}の『{info['passive_name']}』！ いきなり野良の {enemy['emoji']} {enemy['name']} が飛び出してきた！ "
                     f"勝てば経験値{multiplier:g}倍、負けると{dice}マス戻るよ。挑むかは自由！")
    return True


def dino_course_goal(course_key: str) -> int:
    return DINO_COURSES[course_key]["distance_km"] * 10


def queue_dino_sound(kind: str):
    current = st.session_state.get("dino_sound")
    if current is None or DINO_SOUND_PRIORITY[kind] > DINO_SOUND_PRIORITY[current]:
        st.session_state.dino_sound = kind


def add_dino_message(text: str):
    st.session_state.setdefault("dino_messages", []).append(text)


def log_dino_event(text: str):
    st.session_state.dino_event_log.append({
        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"), "text": text,
    })


def get_dino_partner():
    partner_id = st.session_state.get("dino_partner")
    return next((d for d in st.session_state.get("dino_owned", []) if d.get("id") == partner_id), None)


def ensure_dino_data():
    """初期恐竜3種を配る。足りない項目も補う。"""
    if not st.session_state.dino_owned:
        st.session_state.dino_owned = [
            {"id": f"{key}_1", "species": key, "exp": 0, "custom_name": ""}
            for key, info in DINO_SPECIES.items() if not info.get("stars")   # ★付き＝ガチャ限定は配らない
        ]
    for d in st.session_state.dino_owned:
        d.setdefault("custom_name", "")
        d.setdefault("exp", 0)
        d.setdefault("hp_bonus", 0)
        d.setdefault("attack_bonus", 0)
        d.setdefault("speed_bonus", 0)
        d.setdefault("growth_log", [])
    for key in DINO_FOOD:
        st.session_state.dino_food.setdefault(key, 0)
    st.session_state.setdefault("dino_berries", {key: 0 for key in DINO_BERRIES})
    for key in DINO_BERRIES:
        st.session_state.dino_berries.setdefault(key, 0)
    st.session_state.setdefault("dino_stat_items", {})
    if st.session_state.dino_partner and get_dino_partner() is None:
        st.session_state.dino_partner = None


def get_dino_race(course_key: str) -> dict:
    race = st.session_state.dino_race.setdefault(course_key, {})
    race.setdefault("pos", 0)
    race.setdefault("free_rolls", 0)
    race.setdefault("pending_battle", None)
    race.setdefault("finished", False)
    race.setdefault("laps", 0)
    return race


DINO_GROWTH_STATS = {
    "hp": {"emoji": "❤️", "label": "HP", "field": "hp_bonus"},
    "attack": {"emoji": "⚔️", "label": "攻撃力", "field": "attack_bonus"},
    "speed": {"emoji": "💨", "label": "素早さ", "field": "speed_bonus"},
}
DINO_GROWTH_LOG_MAX = 200


def record_dino_growth(dino: dict, text: str):
    """成長履歴に1行追加する（最新200件まで保存）。"""
    log = dino.setdefault("growth_log", [])
    log.append({"date": get_now_jst().strftime("%Y/%m/%d %H:%M"), "text": text})
    if len(log) > DINO_GROWTH_LOG_MAX:
        del log[:len(log) - DINO_GROWTH_LOG_MAX]


def add_dino_exp(dino: dict, amount: int):
    if amount <= 0:
        return
    old_level = dino_level(dino)
    dino["exp"] = dino.get("exp", 0) + amount
    new_level = dino_level(dino)
    if new_level <= old_level:
        return
    name = dino_display_name(dino)
    # 1レベル上がるごとに、HP・攻撃力・素早さのどれか1つがランダムで+1
    for reached in range(old_level + 1, new_level + 1):
        stat_key = random.choice(list(DINO_GROWTH_STATS))
        info = DINO_GROWTH_STATS[stat_key]
        dino[info["field"]] = int(dino.get(info["field"], 0)) + 1
        record_dino_growth(dino, f"⭐ Lv.{reached} にレベルアップ！ {info['emoji']} {info['label']} +1")
        add_dino_message(f"🎉 {name}が Lv.{reached} にレベルアップ！ {info['emoji']} {info['label']}が +1 上がった！")
        log_dino_event(f"🦖 {name}が Lv.{reached} にレベルアップ！（{info['label']}+1）")
    queue_dino_sound("achieve")


def build_dino_board(course_key: str) -> dict:
    """特別マスの配置。コースごとに固定（毎回同じ盤面）。戻るマスはありません。"""
    goal = dino_course_goal(course_key)
    rnd = random.Random(f"dino-board-{course_key}")
    mode = DINO_COURSES[course_key].get("mode", "")

    # ゆるレースはゴール以外の全マスがイベントマス。
    if mode == "relax":
        return {position: "event" for position in range(1, goal)}

    # 初級5kmコースは全50マスのうち、ゴールを除く20マスを特別マスにする。
    if course_key == "beginner" and goal == 50:
        positions = sorted(rnd.sample(range(1, goal), 20))
        kinds = ["boost", "again", "food", "battle"] * 5
        rnd.shuffle(kinds)
        return dict(zip(positions, kinds))

    count = max(8, goal // (2 if mode == "survival" else 4))
    positions = sorted(rnd.sample(range(3, goal), min(count, max(0, goal - 3))))
    pattern = ["boost", "again", "food", "battle"]
    if mode == "survival":
        kinds = [rnd.choice(["battle", "battle", "battle", "food", "boost", "again"]) for _ in positions]
    else:
        kinds = [pattern[i % len(pattern)] for i in range(len(positions))]
    rnd.shuffle(kinds)
    return dict(zip(positions, kinds))


def render_dino_board(course_key: str, pos: int, token: str) -> str:
    goal = dino_course_goal(course_key)
    board = build_dino_board(course_key)
    icons = {"boost": "💨", "again": "🎲", "food": "🍖", "battle": "⚔️", "event": "🌸"}
    colors = {"boost": "#d6f0ff", "again": "#fff2b8", "food": "#ffe0c2", "battle": "#ffd0d0", "event": "#fce4ec"}
    per_row = 10
    cells = []
    for start in range(1, goal + 1, per_row):
        nums = list(range(start, min(start + per_row, goal + 1)))
        if ((start - 1) // per_row) % 2 == 1:   # すごろく風に1行ごと折り返す
            nums.reverse()
        for n in nums:
            if n == goal:
                icon, bg = "🏁", "#d9f7be"
            else:
                icon, bg = icons.get(board.get(n), ""), colors.get(board.get(n), "#f4f4f4")
            here = (n == pos)
            if here:
                icon = token
            border = "3px solid #ff9800" if here else "1px solid #cccccc"
            opacity = "0.45" if n < pos else "1"
            cells.append(
                f'<div style="background:{bg}; border:{border}; border-radius:8px; opacity:{opacity}; color:#333; '
                f'aspect-ratio:1; display:flex; flex-direction:column; align-items:center; justify-content:center;">'
                f'<div style="font-size:clamp(7px,1.6vw,11px); line-height:1;">{n}</div>'
                f'<div style="font-size:clamp(12px,3vw,22px); line-height:1.1;">{icon}</div></div>'
            )
    start_line = f'🚩 スタート {token if pos == 0 else ""}'
    return (
        f'<div style="margin-bottom:6px; font-weight:bold;">{start_line}</div>'
        f'<div style="display:grid; grid-template-columns:repeat({per_row}, 1fr); gap:3px;">{"".join(cells)}</div>'
    )


def finish_dino_race(course_key: str):
    race = get_dino_race(course_key)
    if race["finished"]:
        return
    race["finished"] = True
    race["laps"] += 1
    st.session_state.course_complete_log.append({
        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
        "course": DINO_COURSES[course_key]["name"],
    })
    add_dino_message(f"🏁 ゴール！！ 『{DINO_COURSES[course_key]['name']}』を完走しました！おめでとう！")
    queue_dino_sound("finish")


def advance_dino(course_key: str, steps: int, partner: dict) -> int:
    """前にだけ進む（戻るマスはありません）。進んだ分だけ経験値が入る。"""
    race = get_dino_race(course_key)
    new_pos = min(dino_course_goal(course_key), race["pos"] + max(0, steps))
    gained = new_pos - race["pos"]
    race["pos"] = new_pos
    add_dino_exp(partner, gained)
    return gained


DINO_ENEMY_DIFFICULTIES = ["やさしめ", "ふつう", "つよい"]


def dino_enemy_stats_by_difficulty(partner: dict, difficulty: str):
    """模型恐竜・野良恐竜で共通の強さ設定。(難しさ, レベル, HP, 素早さ, 攻撃力) を返す。
    やさしめ：Lv.1 ／ ふつう：自分と同じ強さ ／ つよい：自分より強い"""
    partner_level = dino_level(partner)
    partner_hp = dino_max_hp(partner)
    partner_speed = dino_speed(partner)
    partner_attack = dino_attack(partner)

    if difficulty == "やさしめ":
        return difficulty, 1, 17, 1, 0
    if difficulty == "つよい":
        # レベル上限でも、HP・攻撃力・素早さは自分の恐竜より高くする。
        level = min(DINO_MAX_LEVEL, partner_level + 2)
        return (difficulty, level,
                max(14 + 3 * level, partner_hp + 6),
                max(level, partner_speed + 2),
                max(dino_power_bonus(level), partner_attack + 1))
    # ふつう
    return "ふつう", partner_level, max(12, partner_hp), max(1, partner_speed), partner_attack


def make_wild_dino(partner: dict) -> dict:
    """野良恐竜を作る。強さは模型恐竜と同じ3段階（やさしめ／ふつう／つよい）からランダムに決まる。
    画面にはレベルだけを表示する（やさしめ等の文字は出さない）。"""
    base = random.choice(WILD_DINOS)
    difficulty = random.choice(DINO_ENEMY_DIFFICULTIES)
    _, level, hp, speed, attack = dino_enemy_stats_by_difficulty(partner, difficulty)
    return {"name": base["name"], "emoji": base["emoji"], "level": level, "max_hp": hp,
            "speed": speed, "attack": attack}


def apply_dino_square(course_key: str, partner: dict):
    race = get_dino_race(course_key)
    goal = dino_course_goal(course_key)
    kind = build_dino_board(course_key).get(race["pos"])
    if kind == "boost":
        extra = min(random.randint(2, 3), goal - race["pos"])
        add_dino_message(f"{random.choice(DINO_BOOST_MESSAGES)} さらに {extra}マス（{extra * 100}m）進む！")
        advance_dino(course_key, extra, partner)
        if race["pos"] >= goal:
            finish_dino_race(course_key)
    elif kind == "again":
        race["free_rolls"] += 1
        add_dino_message("🎲 もう一回サイコロが振れるよ！（ポイントはかからない！）")
    elif kind == "food":
        food_key = random.choices(["meat", "feast"], weights=[7, 3])[0]
        st.session_state.dino_food[food_key] = st.session_state.dino_food.get(food_key, 0) + 1
        food = DINO_FOOD[food_key]
        add_dino_message(f"{food['emoji']} {food['name']}を見つけた！ 持ち物に入れたよ！")
    elif kind == "event":
        event_text = random.choice(["小さな恐竜に花を渡した🌷。心がぽかぽか！", "木陰でひと休み🌳。いい風が吹いてきた！",
            "きれいな石を見つけた💎。記念に持って帰ろう！", "蝶々と追いかけっこ🦋。楽しい時間を過ごした！",
            "仲間とおやつを分けっこ🍪。友情が深まった！", "虹が出た🌈。なんだかいいことがありそう！",
            "ふかふかの草でお昼寝💤。元気いっぱい！", "小鳥の歌を聞いた🐦。ほっとするね！"])
        add_dino_message("🌸 ゆるイベント：" + event_text)
    elif kind == "battle":
        enemy = make_wild_dino(partner)
        race["pending_battle"] = enemy
        add_dino_message(f"⚔️ 野良の {enemy['emoji']} {enemy['name']} があらわれた！ 力試しに挑むかは自由だよ。")


def roll_dino_dice(course_key: str, special_dice_value=None):
    partner = get_dino_partner()
    race = get_dino_race(course_key)
    goal = dino_course_goal(course_key)
    if partner is None or race["finished"] or race["pending_battle"]:
        return
    if special_dice_value is not None:
        if st.session_state.get("dino_special_dice", 0) <= 0:
            add_dino_message("⚠️ スペシャルダイスを持っていません！ショップで購入しよう。")
            return
        if special_dice_value not in range(1, 7):
            return
        st.session_state.dino_special_dice -= 1
        dice = int(special_dice_value)
        add_dino_message(f"🌟 スペシャルダイス！ 好きな {dice} を選んだ！")
    elif race["free_rolls"] > 0:
        race["free_rolls"] -= 1
        dice = random.randint(1, 6)
    elif st.session_state.ippo_points >= DINO_DICE_COST:
        st.session_state.ippo_points -= DINO_DICE_COST
        dice = random.randint(1, 6)
    else:
        add_dino_message("⚠️ IPPOポイントが足りません！ 目標を達成してIPPOポイントを貯めよう。")
        return

    species_key = partner["species"]
    species_info = DINO_SPECIES[species_key]
    passive = dino_passive(species_key)
    chance = dino_passive_effective_chance(species_key, dino_level(partner)) or 0.0
    who = f"{species_info['emoji']} {dino_display_name(partner)}"
    steps = dice
    move_note = None
    if passive and passive["type"] == "move":          # 👣 進む系：進むマス数が変わる
        steps, move_note = dino_passive_move(passive, dice, chance, who, species_info)
    if move_note is None:
        add_dino_message(f"🎲 サイコロの目は {dice}！ {dice}マス進む！" if special_dice_value is None else f"🎲 {dice}マス進む！")
    else:
        add_dino_message(f"🎲 サイコロの目は {dice}！" if special_dice_value is None else f"🎲 {dice}が出た！")
        add_dino_message(move_note)
    if passive and passive["type"] == "pickup" and random.random() < chance:   # 🎒 拾う系
        dino_passive_pickup(passive, who, species_info)

    gained = advance_dino(course_key, steps, partner)
    add_dino_message(f"👣 {gained}マス（{gained * 100}m）進んだ！ 現在 {race['pos'] * 100}m 地点")
    queue_dino_sound("click")
    if race["pos"] >= goal:
        finish_dino_race(course_key)
    else:
        apply_dino_square(course_key, partner)
        if passive and passive["type"] == "ambush":      # ⚔️ バトル系：いきなりバトルのお誘い
            dino_passive_try_ambush(passive, course_key, partner, dice, chance, who, species_info)
    save_progress()


def restart_dino_race(course_key: str):
    race = get_dino_race(course_key)
    race.update({"pos": 0, "free_rolls": 0, "pending_battle": None, "finished": False})
    save_progress()


# ---------------- バトル（力試し） ----------------
def start_dino_battle(course_key: str, partner: dict):
    race = get_dino_race(course_key)
    enemy = race["pending_battle"]
    if not enemy:
        return
    race["pending_battle"] = None
    max_hp = dino_max_hp(partner)
    st.session_state.dino_battle = {
        "enemy": enemy, "enemy_hp": enemy["max_hp"],
        "player_max_hp": max_hp, "player_hp": max_hp,
        "special_left": DINO_SPECIAL_USES,
        "log": ["⚔️ 力試しスタート！ どう戦う？"], "over": False, "result": None, "practice": False,
        "course_key": course_key, "ambush": enemy.get("ambush"),
    }
    save_progress()


def start_dino_practice_battle(partner: dict, difficulty: str = "ふつう"):
    """強さを選べる模型との練習バトル。練習なので経験値・報酬はなし。"""
    partner_hp = dino_max_hp(partner)
    difficulty, level, enemy_hp, enemy_speed, enemy_attack = dino_enemy_stats_by_difficulty(partner, difficulty)

    enemy = {"name": "練習用の模型恐竜", "emoji": "🦖", "level": level,
             "max_hp": enemy_hp, "speed": enemy_speed, "attack": enemy_attack}
    max_hp = partner_hp
    st.session_state.dino_battle = {
        "enemy": enemy, "enemy_hp": enemy["max_hp"], "player_max_hp": max_hp, "player_hp": max_hp,
        "special_left": DINO_SPECIAL_USES,
        "log": [f"🧸 模型恐竜との練習開始！（{difficulty}）勝っても経験値・報酬はありません。"],
        "over": False, "result": None, "practice": True, "practice_difficulty": difficulty,
    }
    save_progress()


def eat_dino_berry(dino: dict, berry_key: str):
    berry = DINO_BERRIES[berry_key]
    inventory = st.session_state.dino_berries
    if inventory.get(berry_key, 0) <= 0:
        return
    inventory[berry_key] -= 1
    amount = 2 if berry_key.endswith("_plus") else 1
    field = {"hp": "hp_bonus", "attack": "attack_bonus", "speed": "speed_bonus"}[berry["stat"]]
    dino[field] = int(dino.get(field, 0)) + amount
    record_dino_growth(dino, f"{berry['emoji']} {berry['name']}を食べた！ {berry['label']} +{amount}")
    add_dino_message(f"{berry['emoji']} {dino_display_name(dino)}が{berry['name']}を食べた！ {berry['label']} +{amount}！")
    save_progress()


def use_dino_stat_item(target: dict, item: dict) -> str:
    """能力アップアイテムを1個使う。（お金や持ち物の増減は呼び出し側）結果の文章を返す。"""
    name = dino_display_name(target)
    stat = DINO_GROWTH_STATS[item["stat"]]
    old_level = dino_level(target)
    target[stat["field"]] = int(target.get(stat["field"], 0)) + item["amount"]
    record_dino_growth(target, f"{item['emoji']} {item['name']}を使った！ {stat['label']} +{item['amount']}")
    add_dino_exp(target, item["exp"])
    add_dino_message(f"{item['emoji']} {name}に{item['name']}を使った！ 経験値 +{item['exp']}、{stat['label']} +{item['amount']}！")
    text = f"{item['emoji']} {name}に{item['name']}を使った！ {stat['label']} +{item['amount']}、経験値 +{item['exp']}"
    if dino_level(target) > old_level:
        text += f"　🎉 Lv.{dino_level(target)} にレベルアップ！"
    return text


def dino_gacha_pool() -> list:
    """ガチャで出る恐竜（dino.json で stars が付いているもの）。[(キー, 情報), ...]"""
    return [(key, info) for key, info in DINO_SPECIES.items() if int(info.get("stars", 0)) > 0]


def dino_gacha_spin() -> bool:
    """恐竜ガチャを1回回す。IPPOポイントを使い、結果を dino_gacha_result に入れる。回せなければFalse。
    すでに仲間の恐竜が出たときは、★の数に応じた経験値がその恐竜に入る。"""
    pool = dino_gacha_pool()
    if not pool or st.session_state.ippo_points < DINO_GACHA_COST_POINTS:
        return False
    st.session_state.ippo_points -= DINO_GACHA_COST_POINTS
    star_list = sorted({int(info["stars"]) for _, info in pool})
    weights = [max(0.0, float(DINO_GACHA_RATES.get(s, 0))) for s in star_list]
    if sum(weights) <= 0:
        weights = [1.0] * len(star_list)
    stars = random.choices(star_list, weights=weights, k=1)[0]
    key, info = random.choice([(k, i) for k, i in pool if int(i["stars"]) == stars])

    owned = next((d for d in st.session_state.dino_owned if d["species"] == key), None)
    result = {"key": key, "stars": stars, "name": info["name"], "emoji": info["emoji"],
              "comment": info.get("gacha_comment", ""), "is_new": owned is None}
    if owned is None:
        st.session_state.dino_owned.append({"id": f"{key}_1", "species": key, "exp": 0,
                                            "custom_name": "", "hp_bonus": 0, "attack_bonus": 0,
                                            "speed_bonus": 0, "growth_log": []})
        log_dino_event(f"🎰 ガチャで {info['emoji']} {info['name']} が仲間になった！")
    else:
        result["dup_exp"] = stars * DINO_GACHA_DUP_EXP_PER_STAR
        before = dino_level(owned)
        add_dino_exp(owned, result["dup_exp"])
        result["level_up"] = dino_level(owned) if dino_level(owned) > before else None
    st.session_state.dino_gacha_result = result
    save_progress()
    return True


def skip_dino_battle(course_key: str):
    race = get_dino_race(course_key)
    enemy = race["pending_battle"]
    race["pending_battle"] = None
    if enemy:
        add_dino_message(f"👋 {enemy['emoji']} {enemy['name']}は見送った。さあ、先へ進もう！")
    save_progress()


def dino_special_spec(species_key: str) -> dict:
    """その恐竜の固有技の設定。dino.json の "special"、なければ初期設定。"""
    return (DINO_SPECIES[species_key].get("special")
            or DINO_SPECIAL_DEFAULTS.get(species_key)
            or DINO_SPECIAL_DEFAULTS["triceratops"])


def dino_special_effect(species_key: str, bonus: int, pname: str) -> dict:
    """固有技の結果。damage(敵へ) / recoil(自分へ) / heal(回復) / stun(相手を行動不能に) /
    counter(カウンター) / counter_mult(返す倍率) / texts(表示する文章のリスト) を返す。"""
    info = DINO_SPECIES[species_key]
    spec = dino_special_spec(species_key)
    prefix = f"🌟 {pname}の固有技『{info['special_name']}』！"
    effect = {"damage": 0, "recoil": 0, "heal": 0, "stun": False, "counter": False, "counter_mult": 2, "texts": []}
    kind = spec["type"]

    if kind == "random":   # 完全ランダム：ほかの恐竜の固有技を1つ選んで発動する
        others = [k for k in DINO_SPECIES if k != species_key and dino_special_spec(k)["type"] != "random"]
        if others:
            picked = random.choice(others)
            picked_info = DINO_SPECIES[picked]
            sub = dino_special_effect(picked, bonus, pname)
            sub["texts"] = [f"{prefix} 🎲 {picked_info['emoji']} {picked_info['name']}の『{picked_info['special_name']}』が飛び出した！"] + sub["texts"]
            return sub
        spec = DINO_SPECIAL_DEFAULTS["triceratops"]
        kind = spec["type"]

    if kind == "multi_hit":
        hits = [random.randint(int(spec["hit_min"]), int(spec["hit_max"]))
                for _ in range(random.randint(int(spec["hits_min"]), int(spec["hits_max"])))]
        effect["damage"] = sum(hits) + bonus
        effect["texts"].append(f"{prefix} {len(hits)}回連続（{'+'.join(map(str, hits))}）で合計 {effect['damage']}ダメージ！")
    elif kind == "heal_hit":
        effect["damage"] = random.randint(int(spec["min"]), int(spec["max"])) + bonus
        effect["heal"] = int(spec["heal"])
        effect["texts"].append(f"{prefix} {effect['damage']}ダメージ！ 自分のHPが{effect['heal']}回復！")
    elif kind == "stun_hit":
        effect["damage"] = random.randint(int(spec["min"]), int(spec["max"])) + bonus
        effect["texts"].append(f"{prefix} {effect['damage']}ダメージ！")
        if random.random() < float(spec.get("chance", 0.3)):
            effect["stun"] = True
            effect["texts"].append("💫 相手は目を回して、このターンは動けない！")
    elif kind == "counter":
        effect["counter"] = True
        effect["counter_mult"] = float(spec.get("multiplier", 2))
        effect["texts"].append(f"{prefix} どっしり身構えた…！ 受けたダメージを倍にして返すよ！")
    else:   # recoil_hit（反動つき攻撃）
        effect["damage"] = random.randint(int(spec["min"]), int(spec["max"])) + bonus
        effect["recoil"] = random.randint(int(spec["recoil_min"]), int(spec["recoil_max"]))
        effect["texts"].append(f"{prefix} {effect['damage']}ダメージ！ …でも自分も {effect['recoil']}ダメージ！")
    return effect


def resolve_dino_battle_turn(partner: dict, action: str):
    battle = st.session_state.dino_battle
    enemy = battle["enemy"]
    pname = f"{DINO_SPECIES[partner['species']]['emoji']} {dino_display_name(partner)}"
    ename = f"{enemy['emoji']} {enemy['name']}"
    bonus_p = dino_attack(partner)
    bonus_e = int(enemy.get("attack", (enemy["level"] - 1) // 3))

    if action == "special" and battle.get("special_left", 0) <= 0:
        battle["log"] = ["🌟 固有技はもう使えないよ！ ほかの行動を選ぼう。"]
        return
    if action == "flee":
        battle["over"], battle["result"] = True, "flee"
        battle["log"] = [f"🏃 {pname}は うまく逃げ出した！ 無理しなくて大丈夫！"]
        return

    enemy_action = random.choices(["attack", "defend", "special"], weights=[5, 2, 3])[0]
    enemy_label = {"attack": "こうげき", "defend": "ぼうぎょ", "special": "強打"}[enemy_action]
    log = [f"👀 {ename}は『{enemy_label}』を選んだ！"]
    to_enemy = to_player = heal = 0
    stun = counter = False      # 麻痺（相手の行動不能）・カウンター
    counter_mult = 2

    # --- 自分の行動 ---
    if action == "attack":
        if enemy_action == "defend":
            damage = random.randint(4, 8) + bonus_e
            to_player += damage
            log.append(f"🛡️ 守りを固めていた{ename}に反撃された！ {damage}ダメージ！")
        else:
            damage = random.randint(1, 5) + bonus_p
            to_enemy += damage
            log.append(f"⚔️ {pname}のこうげき！ {damage}ダメージ！")
    elif action == "defend":
        if enemy_action == "attack":
            damage = random.randint(4, 8) + bonus_p
            to_enemy += damage
            log.append(f"🛡️ {pname}は攻撃を受け止めてカウンター！ {damage}ダメージ！")
        elif enemy_action == "defend":
            log.append("🛡️ おたがい守りを固めて、にらみ合い…")
        else:
            log.append(f"🛡️ {pname}は身構えたが、強打は防ぎきれない！")
    else:  # special
        battle["special_left"] -= 1
        effect = dino_special_effect(partner["species"], bonus_p, pname)
        to_enemy += effect["damage"]
        to_player += effect["recoil"]
        heal = effect["heal"]
        stun, counter, counter_mult = effect["stun"], effect["counter"], effect["counter_mult"]
        log.extend(effect["texts"])

    # --- 相手の行動 ---
    # 自分の固有技の反動とは分けて、相手の攻撃だけを回避判定する。
    incoming_damage = 0
    incoming_special = enemy_action == "special"
    if stun:
        log.append(f"😵 {ename}は目を回して動けない！ このターンは何もできなかった！")
    elif enemy_action == "attack" and action != "defend":
        incoming_damage = random.randint(1, 5) + bonus_e
        log.append(f"💥 {ename}のこうげき！ {incoming_damage}ダメージ！")
    elif enemy_action == "special":
        incoming_damage = random.randint(4, 7) + bonus_e
        log.append(f"💥 {ename}の強打！ {incoming_damage}ダメージ！")

    # 素早さは回避率だけに影響する（攻撃力・先手判定などには使わない）。
    player_speed = dino_speed(partner)
    enemy_speed = int(enemy.get("speed", enemy["level"]))
    dodge_rate = dino_dodge_rate(player_speed, enemy_speed, special=incoming_special)
    if incoming_damage > 0 and random.random() < dodge_rate / 100:
        incoming_damage = 0
        log.append(f"💨 {dino_display_name(partner)}は回避した！")
    to_player += incoming_damage

    # カウンター：受けたダメージを倍にして返す。相手がぼうぎょしていたら不発。
    if counter:
        if enemy_action == "defend":
            log.append(f"🛡️ {ename}はぼうぎょしていた…！ カウンターは不発に終わった！")
        elif incoming_damage > 0:
            reflected = round(incoming_damage * counter_mult)
            to_enemy += reflected
            log.append(f"🔁 受けた {incoming_damage} ダメージを{counter_mult:g}倍にして返した！ {reflected}ダメージ！")
        elif not stun:
            log.append("💨 攻撃をかわしたので、今回は返すダメージがなかったよ。")

    # 相手側も同じルールで回避する。プレイヤーの固有技は必殺技扱い。
    enemy_dodge_rate = dino_dodge_rate(
        enemy_speed, player_speed, special=(action == "special")
    )
    if to_enemy > 0 and not counter and random.random() < enemy_dodge_rate / 100:
        to_enemy = 0
        log.append(f"💨 {enemy['name']}は回避した！")

    battle["enemy_hp"] = max(0, battle["enemy_hp"] - to_enemy)
    battle["player_hp"] = max(0, battle["player_hp"] - to_player)
    if heal and battle["player_hp"] > 0:
        battle["player_hp"] = min(battle["player_max_hp"], battle["player_hp"] + heal)

    if battle["enemy_hp"] <= 0:
        battle["over"], battle["result"] = True, "win"
        if battle.get("practice"):
            log.append("🎉 模型恐竜に勝利！ 練習おつかれさま！ 経験値・報酬はありません。")
        else:
            ambush = battle.get("ambush")
            win_exp = round(DINO_BATTLE_WIN_EXP * float(ambush["exp_multiplier"])) if ambush else DINO_BATTLE_WIN_EXP
            log.append(f"🎉 {ename}に勝利！ 経験値 +{win_exp}！" + ("（いきなりバトルボーナス！）" if ambush else ""))
            add_dino_exp(partner, win_exp)
            if random.random() < 0.5:
                berry_key = random.choice(list(DINO_BERRIES))
                st.session_state.dino_berries.setdefault(berry_key, 0)
                st.session_state.dino_berries[berry_key] += 1
                berry = DINO_BERRIES[berry_key]
                amount = 2 if berry_key.endswith("_plus") else 1
                log.append(f"{berry['emoji']} 戦利品：{berry['name']}！（食べると{berry['label']}+{amount}）")
            else:
                st.session_state.dino_special_dice = int(st.session_state.get("dino_special_dice", 0)) + 1
                log.append("🌟 戦利品：スペシャルダイスを1個手に入れた！")
            log_dino_event(f"⚔️ {pname}が野良の{ename}との力試しに勝利！")
        queue_dino_sound("achieve")
    elif battle["player_hp"] <= 0:
        battle["over"], battle["result"] = True, "lose"
        if battle.get("practice"):
            log.append(f"😵 模型恐竜に負けてしまった…。練習だから何度でも挑戦できるよ！")
        else:
            log.append(f"😵 {pname}はたおれてしまった… でも挑戦はすごいこと！ 経験値 +{DINO_BATTLE_LOSE_EXP}")
            add_dino_exp(partner, DINO_BATTLE_LOSE_EXP)
            if battle.get("ambush"):   # いきなりバトルに負けたら、出た目のぶん後戻り
                lose_race = get_dino_race(battle["course_key"])
                old_pos = lose_race["pos"]
                lose_race["pos"] = max(0, old_pos - int(battle["ambush"]["back_steps"]))
                log.append(f"⏪ いきなりバトルに負けて、{old_pos - lose_race['pos']}マス戻った…")
            log_dino_event(f"⚔️ {pname}が野良の{ename}に力試しで挑戦！")
    battle["log"] = log
    save_progress()



# =====================================================
# 💎 IPPOポイント（お菓子屋さん・水族館・恐竜レースで共通）
# =====================================================
SINGLE_TASK_POINTS = 1      # 単発・反復タスクの達成ポイント
CANDY_COST_POINTS = 1       # 最初から使える5種類のお菓子を1個入れるのに必要なIPPOポイント
CANDY_SHOP_EXTRA_COST_POINTS = 2   # ショップで買った追加のお菓子を1個入れるのに必要なIPPOポイント


# =====================================================
# 🍰 お菓子屋さん ① 設定値・定数（お菓子コインはお菓子屋さん内だけで使うゲーム内通貨）
# =====================================================

# お菓子コインはお菓子屋さん内だけで使うゲーム内通貨。
# IPPOポイントや水族館・恐竜レースの仕組みとは独立させる。
CANDY_SHOP_MATERIALS = {'whip': {'name': 'ホイップクリーム', 'emoji': '🍦', 'price': 20}, 'chocolate': {'name': 'チョコレート', 'emoji': '🍫', 'price': 20}, 'strawberry': {'name': 'イチゴ', 'emoji': '🍓', 'price': 20}, 'flour': {'name': '小麦粉', 'emoji': '🌾', 'price': 20}, 'cookie': {'name': 'クッキー', 'emoji': '🍪', 'price': 20}, 'milk': {'name': 'ミルク', 'emoji': '🥛', 'price': 20}, 'matcha': {'name': '抹茶', 'emoji': '🍵', 'price': 20}, 'banana': {'name': 'バナナ', 'emoji': '🍌', 'price': 20}, 'cheese': {'name': 'クリームチーズ', 'emoji': '🧀', 'price': 20}, 'caramel': {'name': 'キャラメル', 'emoji': '🍯', 'price': 20}}


# 最初から瓶に入れられる5種類（🍬🍭🍫🍩🍪）は、これまで通りIPPOポイントだけで入れられる。
# こちらはショップでお菓子コインを使って買い足せる「追加のお菓子」（最初の5種類とは別の種類）。
# 追加のお菓子は「買いきり」：一度買えば、以降は何個でも IPPOポイント（CANDY_SHOP_EXTRA_COST_POINTS）だけで瓶に入れられる。
CANDY_SHOP_JAR_CANDIES = {
    "cupcake": {"name": "カップケーキ", "emoji": "🧁", "price": 400},
    "dango": {"name": "おだんご", "emoji": "🍡", "price": 400},
    "pudding": {"name": "とろとろプリン", "emoji": "🍮", "price": 400},
    "shaved_ice": {"name": "ふわふわかき氷", "emoji": "🍧", "price": 400},
    "waffle": {"name": "サクサクワッフル", "emoji": "🧇", "price": 400},
}


# 最初から使える5種類
CANDY_DEFAULT_SPEC = [
    {"emoji": "🍬", "label": "定番キャンディ"},
    {"emoji": "🍭", "label": "渦巻きロリポップ"},
    {"emoji": "🍫", "label": "濃厚チョコブロック"},
    {"emoji": "🍩", "label": "サクサクドーナツ"},
    {"emoji": "🍪", "label": "チョコチップクッキー"},
]


# 瓶の大きさ（お客さんの注文の個数も、この3種類）
CANDY_JAR_SIZES = [10, 20, 30]


CANDY_JAR_NAMES = {10: "小さめの瓶", 20: "普通の瓶", 30: "大きめの瓶"}


CANDY_JAR_DEFAULT_NAME = "瓶詰めお菓子"   # 名前をつけなかったときの呼び名


CANDY_JAR_REWARD_DEFAULT = {10: (100, 300), 20: (200, 400), 30: (300, 500)}


CANDY_RECIPE_BOOK_PRICE = 50
CANDY_INVITE_TICKET_PRICE = 50   # 特別招待チケット1枚の値段（お菓子コイン）


CANDY_HINT_COST = 5
CANDY_GACHA_COST_COINS = 20   # お菓子ガチャ1回に必要なお菓子コイン
CANDY_GACHA_DEFAULT_RATES = {1: 40, 2: 30, 3: 18, 4: 9, 5: 3}   # ★ごとの出やすさ（JSONのgacha_ratesで調整できる）


CANDY_SHOP_FALLBACK = {
    "name": "ふしぎなお菓子", "emoji": "🍬", "rarity": 1, "sell_price": 20,
}


# =====================================================
# 🍰 お菓子屋さん ② JSONデータの読み込み（レシピ・瓶の注文ルール）
# =====================================================

# レシピと瓶注文ルールは、アプリ本体とは別のJSONファイルで管理する。
CANDY_RECIPE_DATA_PATH = os.path.join(BASE_DIR, "data", "candy_recipes.json")
# dataフォルダがない環境では、アプリ本体と同じ場所のレシピJSONも読み込める。
if not os.path.exists(CANDY_RECIPE_DATA_PATH):
    CANDY_RECIPE_DATA_PATH = os.path.join(BASE_DIR, "candy_recipes.json")


CANDY_JAR_ORDER_DATA_PATH = os.path.join(BASE_DIR, "data", "candy_jar_orders.json")


def load_candy_json(path: str, label: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("JSONの最上位はオブジェクトにしてください")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        st.error(f"{label}データを読み込めませんでした: {exc}")
        st.stop()


CANDY_RECIPE_DATA = load_candy_json(CANDY_RECIPE_DATA_PATH, "スイーツレシピ")


CANDY_JAR_ORDER_DATA = load_candy_json(CANDY_JAR_ORDER_DATA_PATH, "瓶注文")


CANDY_SHOP_RECIPES = {
    recipe["id"]: recipe for recipe in CANDY_RECIPE_DATA.get("recipes", [])
}


CANDY_SHOP_FALLBACKS = CANDY_RECIPE_DATA.get("fallback_sweets", [])


# =====================================================
# 🍰 お菓子屋さん ③ 共通のヘルパー（経験値・瓶の名前）
# =====================================================

def candy_shop_add_exp(amount: int):
    """販売・瓶注文の経験値を加算して店レベルを更新する。"""
    if amount <= 0:
        return
    st.session_state.candy_shop_exp = int(st.session_state.get("candy_shop_exp", 0)) + amount
    while st.session_state.candy_shop_level < 20:
        next_need = st.session_state.candy_shop_level * 100
        if st.session_state.candy_shop_exp < next_need:
            break
        st.session_state.candy_shop_exp -= next_need
        st.session_state.candy_shop_level += 1


def candy_jar_display_name() -> str:
    return (st.session_state.get("jar_name") or "").strip() or CANDY_JAR_DEFAULT_NAME


# =====================================================
# 🍓 お菓子屋さん ④ スイーツ作り（材料の購入・合成・完成セリフ）
# =====================================================

def candy_shop_buy_material(material_key: str, quantity: int = 1):
    item = CANDY_SHOP_MATERIALS[material_key]
    cost = item["price"] * quantity
    if st.session_state.candy_coins < cost:
        return False
    st.session_state.candy_coins -= cost
    st.session_state.candy_shop_materials[material_key] = (
        st.session_state.candy_shop_materials.get(material_key, 0) + quantity
    )
    save_progress()
    return True


def candy_shop_craft(material_keys: list):
    """材料1〜3個を消費。2材料は通常レシピ、3材料は秘伝のレシピ書が必要。"""
    if not 1 <= len(material_keys) <= 3:
        return False, None
    if len(material_keys) == 3 and not st.session_state.get("candy_shop_recipe_book_owned", False):
        return False, None
    needed = {}
    for key in material_keys:
        needed[key] = needed.get(key, 0) + 1
    for key, count in needed.items():
        if st.session_state.candy_shop_materials.get(key, 0) < count:
            return False, None

    for key, count in needed.items():
        st.session_state.candy_shop_materials[key] -= count

    wanted = tuple(sorted(material_keys))
    crafted = None
    for recipe_key, recipe in CANDY_SHOP_RECIPES.items():
        recipe_materials = tuple(sorted(recipe.get("materials", [])))
        if recipe_materials == wanted and (len(wanted) < 3 or st.session_state.get("candy_shop_recipe_book_owned", False)):
            crafted = {
                "id": recipe_key, "name": recipe["name"], "emoji": recipe["emoji"],
                "rarity": int(recipe["rarity"]), "sell_price": int(recipe["sell_price"]),
                "materials": list(recipe.get("materials", [])),
            }
            break
    if crafted is None:
        # レシピにない組み合わせは、3種類の星1スイーツからランダムに生成する。
        fallback = random.choice(CANDY_SHOP_FALLBACKS) if CANDY_SHOP_FALLBACKS else CANDY_SHOP_FALLBACK
        crafted = dict(fallback)

    st.session_state.candy_shop_products.append(crafted)
    if not any(item.get("id") == crafted.get("id") for item in st.session_state.candy_shop_discovered):
        st.session_state.candy_shop_discovered.append({
            "id": crafted["id"], "name": crafted["name"], "emoji": crafted["emoji"],
            "rarity": int(crafted.get("rarity", 1)),
            "materials": list(crafted.get("materials", [])),
        })
    save_progress()
    return True, crafted


def candy_shop_craft_message(product: dict) -> str:
    """スイーツ完成時のセリフ。JSONのcraft_messagesからランダムに選ぶ（{name}がスイーツ名に置き換わる）。"""
    messages = CANDY_RECIPE_DATA.get("craft_messages") or ["{name}完成！"]
    return random.choice(messages).replace("{name}", f"{product['emoji']}{product['name']}")


# =====================================================
# 🧁 お菓子屋さん ⑤ 商品棚とお客さん（棚から戻す・お店をひらく）
# =====================================================

def candy_shop_return_displayed(index: int):
    """棚に並べた商品を、持ち物（商品）に戻す。"""
    displayed = st.session_state.candy_shop_displayed
    if not 0 <= index < len(displayed):
        return False
    st.session_state.candy_shop_products.append(displayed.pop(index))
    save_progress()
    return True


def candy_shop_serve_customer(customer: dict) -> dict:
    """お客さん1人が棚を見て、気に入ったスイーツを買ってくれる。（必ず何か1つ買ってくれる）
    大好物（likes）があればそれを選び、ファンボーナス込みの金額を払う。
    なければ、その人の選び方（highest=いちばん豪華 / cheapest=お手頃 / random=気分）で選ぶ。
    ときどきチップをくれることもある。"""
    shelf = st.session_state.candy_shop_displayed
    lines = customer.get("lines", {})
    likes = set(customer.get("likes", []))

    def price_of(product):
        return int(product.get("sell_price", CANDY_SHOP_FALLBACK["sell_price"]))

    favorites = [i for i, p in enumerate(shelf) if p.get("emoji") in likes]
    loved = bool(favorites)
    if loved:
        chosen = random.choice(favorites)
    else:
        style = customer.get("style", "random")
        indexes = list(range(len(shelf)))
        if style == "highest":
            chosen = max(indexes, key=lambda i: price_of(shelf[i]))
        elif style == "cheapest":
            chosen = min(indexes, key=lambda i: price_of(shelf[i]))
        else:
            chosen = random.choice(indexes)

    product = shelf.pop(chosen)
    paid = price_of(product)
    if loved:
        paid = round(paid * float(customer.get("fan_bonus", 1.5)))
    tip = round(paid * 0.3) if (loved or random.random() < 0.05) else 0
    paid += tip

    notes = st.session_state.candy_shop_customer_notes
    note = notes.setdefault(customer["id"], {"visits": 0, "bought": 0, "loved": 0})
    note["visits"] = int(note.get("visits", 0)) + 1
    note["bought"] = int(note.get("bought", 0)) + 1
    if loved:
        note["loved"] = int(note.get("loved", 0)) + 1
    st.session_state.candy_coins += paid
    candy_shop_add_exp(max(5, int(product.get("rarity", 1)) * 5) + (5 if loved else 0))
    return {"id": customer["id"], "name": customer.get("name", "お客さん"),
            "emoji": customer.get("emoji", "🙂"), "loved": loved, "tip": tip, "paid": paid,
            "bought": {"emoji": product.get("emoji", ""), "name": product.get("name", "")},
            "line": lines.get("love" if loved else "buy", "ありがとう！")}


def candy_shop_open_for_business():
    """お店をひらく。来店人数は毎回ランダム（最低1人、棚の商品数以下、最大5人）。
    お客さんはランダムに来て、棚のスイーツを気に入って買ってくれる。"""
    customers = CANDY_RECIPE_DATA.get("customers", [])
    if not customers or not st.session_state.candy_shop_displayed:
        return None
    # 来店人数は毎回ランダム。最低1人、棚の商品数を超えず、最大5人。
    count = random.randint(1, min(5, len(st.session_state.candy_shop_displayed)))
    customer_by_id = {c["id"]: c for c in customers}

    # 🎫 特別招待チケットを使ったお客さんは、このお店ひらきで確定で1回来てくれる。
    invited_ids = [cid for cid in st.session_state.get("candy_shop_invited_customers", [])
                   if cid in customer_by_id]
    visits = []
    served_invited = []
    for cid in invited_ids:
        if not st.session_state.candy_shop_displayed:
            break  # 棚のスイーツが足りないときは、招待は次回に持ち越し（チケットはむだにならない）
        visit = candy_shop_serve_customer(customer_by_id[cid])
        visit["invited"] = True
        visits.append(visit)
        served_invited.append(cid)
    st.session_state.candy_shop_invited_customers = [
        cid for cid in st.session_state.get("candy_shop_invited_customers", []) if cid not in served_invited
    ]

    # 残りの枠は、いつも通りランダムなお客さんが来る（招待したお客さんは重ならない）。
    pool = [c for c in customers if c["id"] not in invited_ids]
    for _ in range(min(max(0, count - len(served_invited)), len(pool))):
        if not st.session_state.candy_shop_displayed:
            break  # 棚のスイーツが全部届いたら、今日はここまで
        weights = [max(1, int(c.get("weight", 1))) for c in pool]
        customer = random.choices(pool, weights=weights, k=1)[0]
        pool.remove(customer)
        visits.append(candy_shop_serve_customer(customer))
    save_progress()
    return {"visits": visits, "total": sum(v["paid"] for v in visits)}


# =====================================================
# 🫙 お菓子屋さん ⑥ 瓶の注文（注文づくり・お菓子を入れる・渡す・瓶の画面）
# =====================================================

def candy_rule_target(rule: dict, size: int) -> int:
    """注文ルールから、瓶の大きさ(個数)に合った目標値を返す。旧形式（targetだけ）にも対応。"""
    targets = rule.get("targets")
    if isinstance(targets, dict) and targets:
        if str(size) in targets:
            return int(targets[str(size)])
        nearest = min(targets, key=lambda k: abs(int(k) - int(size)))
        return int(targets[nearest])
    return int(rule.get("target", 50))


def candy_jar_reward_range(capacity: int):
    """瓶の大きさごとの報酬コインの(最低, 最高)。JSONのreward_rangesで調整できる。"""
    r = CANDY_JAR_ORDER_DATA.get("reward_ranges", {}).get(str(capacity))
    if isinstance(r, dict) and "min" in r and "max" in r:
        return int(r["min"]), int(r["max"])
    return CANDY_JAR_REWARD_DEFAULT.get(int(capacity), (100, 300))


def candy_shop_create_jar_order():
    """20種類の注文条件から、お客さんの注文を1件作る。（瓶の大きさは注文に含めず、自分で選ぶ）"""
    order = st.session_state.get("candy_shop_jar_order")
    order_rules = CANDY_JAR_ORDER_DATA.get("orders", [])
    if not order_rules:
        return
    if not order:
        rule = random.choice(order_rules)
        st.session_state.candy_shop_jar_order = {
            "condition_id": rule["id"],
            "message": rule["message"],
            "dimension": rule["dimension"],
        }
        save_progress()
    elif not order.get("condition_id"):
        # 旧バージョンの注文データを新しい注文形式へ移行する。
        rule = random.choice(order_rules)
        order.update({"condition_id": rule["id"], "message": rule["message"],
                      "dimension": rule["dimension"]})
        order.pop("reward", None)
        order.pop("exp", None)
        save_progress()
    if order and ("quantity" in order or "target" in order):
        # 旧形式の注文に残っている希望個数・目標値は使わない（瓶の大きさは自分で選ぶ）。
        order.pop("quantity", None)
        order.pop("target", None)
        save_progress()


def candy_extra_owned(shop_key: str) -> bool:
    """追加のお菓子を持っているか。（ショップで買いきり／ガチャで当てたお菓子。キーが gacha_ で始まるものはガチャのお菓子）
    以前の在庫方式で買った分や、瓶に入れたことがある分も持っている扱い。"""
    if shop_key.startswith("gacha_"):
        return candy_gacha_owned(shop_key[len("gacha_"):])
    if st.session_state.candy_shop_jar_candy_stock.get(shop_key, 0) > 0:
        return True
    item = CANDY_SHOP_JAR_CANDIES.get(shop_key)
    return bool(item) and any(c.get("emoji") == item["emoji"] for c in st.session_state.get("all_candy_log", []))


def candy_jar_put_candy(emoji: str, shop_key=None):
    """瓶にお菓子を1個入れる。評価用の数値は保存するが、画面には表示しない。"""
    if len(st.session_state.jar_candies) >= st.session_state.jar_capacity:
        return False
    cost = CANDY_SHOP_EXTRA_COST_POINTS if shop_key is not None else CANDY_COST_POINTS
    if st.session_state.ippo_points < cost:
        return False
    if shop_key is not None and not candy_extra_owned(shop_key):
        return False
    st.session_state.ippo_points -= cost
    stats = CANDY_JAR_ORDER_DATA.get("candy_stats", {}).get(
        emoji, {"sweetness": 50, "cuteness": 50, "seasonality": 50}
    )
    new_candy = {
        "emoji": emoji,
        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
        "task": f"{cost} IPPOポイントで入れたお菓子",
        "_stats": dict(stats),
    }
    st.session_state.jar_candies.append(new_candy)
    st.session_state.all_candy_log.append(new_candy)
    return True


def candy_jar_deliver():
    """瓶を渡し、注文サイズとの近さ・中身の傾向を内部評価して報酬を決める。"""
    capacity = st.session_state.jar_capacity
    candies = st.session_state.jar_candies
    if len(candies) < capacity:
        return None
    name = candy_jar_display_name()
    delivered_candies = candies[:capacity]
    st.session_state.jar_complete_log.append({
        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
        "capacity": capacity,
        "size_label": JAR_SIZE_LABELS.get(capacity, "?"),
        "candies": delivered_candies,
        "name": name,
    })
    st.session_state.jar_candies = candies[capacity:]
    st.session_state.jar_name = ""
    st.session_state.jar_full_sound_played = False

    order = st.session_state.get("candy_shop_jar_order")
    reward = 0
    exp = 0
    rewarded = False
    thanks = "ありがとう！大切にいただくね♪"
    if order:
        # 評価値は常にJSONの最新の値を使う（なければ入れた時点の値、それもなければ50）。
        totals = {"sweetness": 0.0, "cuteness": 0.0, "seasonality": 0.0}
        for candy in delivered_candies:
            stats = (CANDY_JAR_ORDER_DATA.get("candy_stats", {}).get(candy.get("emoji", ""))
                     or candy.get("_stats")
                     or {"sweetness": 50, "cuteness": 50, "seasonality": 50})
            for key in totals:
                totals[key] += float(stats.get(key, 50))
        averages = {key: value / max(1, len(delivered_candies)) for key, value in totals.items()}
        # 注文には瓶の大きさ(10/20/30個)ごとの目標値があり、実際に渡した瓶の大きさの判定を使う。
        rule = next((r for r in CANDY_JAR_ORDER_DATA.get("orders", [])
                     if r.get("id") == order.get("condition_id")), None)
        if rule:
            dimension = rule.get("dimension", "cuteness")
            target = float(candy_rule_target(rule, capacity))
        else:
            dimension = order.get("dimension", "cuteness")
            target = float(order.get("target", 50))
        fit_score = max(0, 100 - abs(averages.get(dimension, 50) - target))

        # 瓶の大きさごとの報酬レンジの中で、注文との近さ(0〜100)に応じて1コイン単位で決める。
        reward_min, reward_max = candy_jar_reward_range(capacity)
        reward = reward_min + round((reward_max - reward_min) * fit_score / 100)
        exp = max(20, round(reward / 10 + fit_score / 10))
        st.session_state.candy_coins += reward
        candy_shop_add_exp(exp)
        thanks = random.choice(CANDY_JAR_ORDER_DATA.get("thanks", [thanks]))
        st.session_state.candy_shop_jar_order_log.append({
            "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
            "quantity": capacity, "reward": reward, "name": name,
        })
        st.session_state.candy_shop_jar_order = None
        candy_shop_create_jar_order()
        rewarded = True

    save_progress()
    return {"name": name, "rewarded": rewarded, "reward": reward, "thanks": thanks}


def render_candy_jar_section():
    """瓶の注文タブの中に表示する、瓶にお菓子を入れる画面（挑戦中の瓶・名前・大きさ変更・お菓子選び・今までの瓶）。"""
    current_capacity = st.session_state.jar_capacity
    if current_capacity not in CANDY_JAR_NAMES:
        current_capacity = 30
        st.session_state.jar_capacity = current_capacity
        st.session_state.last_jar_capacity = current_capacity
    st.markdown(f"### 🏺 挑戦中：{CANDY_JAR_NAMES[current_capacity]}（{current_capacity}個入り）")

    # 瓶一つ一つの名前（瓶を渡すたびに新しい瓶の名前を付けられる）
    jar_serial = len(st.session_state.jar_complete_log)
    typed_name = st.text_input(
        "🏷️ この瓶の名前（空欄なら「瓶詰めお菓子」）",
        value=st.session_state.jar_name, max_chars=20,
        placeholder=CANDY_JAR_DEFAULT_NAME, key=f"jar_name_input_{jar_serial}",
    )
    if typed_name.strip() != st.session_state.jar_name:
        st.session_state.jar_name = typed_name.strip()
        save_progress()

    st.caption("選んだ瓶は完成して渡したあともそのまま！ 別の大きさにしたいときだけ変更できます。")

    if st.button("⚙️ 瓶の大きさを変更する", key="open_jar_size_change"):
        st.session_state.show_jar_size_change = not st.session_state.get("show_jar_size_change", False)
    if st.session_state.get("show_jar_size_change", False):
        with st.container(border=True):
            jar_option = st.selectbox(
                "変更後の瓶の大きさ", CANDY_JAR_SIZES,
                index=CANDY_JAR_SIZES.index(current_capacity),
                format_func=lambda x: f"{CANDY_JAR_NAMES[x]}（{x}個入り）",
                key="jar_size_change_choice",
            )
            st.info(f"今まで入れたお菓子 {len(st.session_state.jar_candies)} 個はそのまま引き継ぎます。"
                    "（瓶より多い分は、次の瓶に入ります）")
            change_col, cancel_col = st.columns(2)
            with change_col:
                if st.button("この大きさに変更", type="primary", key="confirm_jar_size_change"):
                    st.session_state.jar_capacity = jar_option
                    st.session_state.last_jar_capacity = jar_option
                    st.session_state.jar_full_sound_played = False
                    st.session_state.show_jar_size_change = False
                    save_progress()
                    st.rerun()
            with cancel_col:
                if st.button("キャンセル", key="cancel_jar_size_change"):
                    st.session_state.show_jar_size_change = False
                    st.rerun()

    st.write("---")

    capacity = st.session_state.jar_capacity
    current_count = len(st.session_state.jar_candies)
    is_full = current_count >= capacity
    jar_area, candy_area = st.columns([3, 1])

    with jar_area:
        st.markdown(f"### 🏺 現在の瓶の中身 （{min(current_count, capacity)} / {capacity} 個）")

        with st.container(border=True):
            if current_count == 0:
                st.write("瓶はまだ空っぽです。お菓子を選んで入れてね！")
            else:
                st.markdown(render_candy_jar_svg(st.session_state.jar_candies[:capacity], capacity),
                            unsafe_allow_html=True)

        st.progress(min(current_count / capacity, 1.0))

        if is_full:
            jar_name_text = candy_jar_display_name()
            st.markdown("## 🎉 おめでとう！！°˖✧◝(⁰▿⁰)◜✧˖°")
            if not st.session_state.jar_full_sound_played:
                st.balloons()
                play_jar_full_sound()
                st.session_state.jar_full_sound_played = True
            st.success(f"素晴らしい！！！{capacity}個の「{jar_name_text}」が完成しました！ お客さんに渡そう！")
            if st.button(f"🎁 「{jar_name_text}」を渡す", type="primary", key="candy_jar_deliver_button"):
                result = candy_jar_deliver()
                if result:
                    if result["rewarded"]:
                        st.session_state.candy_shop_delivery_message = {
                            "thanks": result["thanks"], "name": result["name"], "reward": result["reward"]
                        }
                    else:
                        st.session_state.candy_shop_delivery_message = {
                            "thanks": "受け取ってくれてありがとう！", "name": result["name"], "reward": 0
                        }
                    st.rerun()

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
                    record_name = f"「{jar_record['name']}」" if jar_record.get("name") else ""
                    with st.expander(f"🍯 {jar_record.get('date', '')} {record_name}お菓子のビン({jar_size_text})完成✨",
                                     expanded=False):
                        if jar_record.get("candies"):
                            st.markdown(render_candy_jar_svg(jar_record["candies"], jar_record.get("capacity", 30)),
                                        unsafe_allow_html=True)

    with candy_area:
        st.metric("💎 IPPOポイント", st.session_state.ippo_points)
        st.caption("お菓子屋さん・水族館・恐竜レースで共通のIPPOポイントです。")
        st.markdown("### 🍬 飴を選ぶ")
        st.caption(f"最初のお菓子は1個 ＝ {CANDY_COST_POINTS} IPPOポイント／"
                   f"ショップで買った・ガチャで当てた追加のお菓子は1個 ＝ {CANDY_SHOP_EXTRA_COST_POINTS} IPPOポイント")
        can_buy_candy = st.session_state.ippo_points >= CANDY_COST_POINTS
        if is_full:
            st.info("瓶が完成したよ！ 渡してから、次の瓶にお菓子を入れよう。")
        elif not can_buy_candy:
            st.warning("IPPOポイントが足りないよ！ 目標を達成してIPPOポイントをためよう。")

        # 最初から使える5種類 ＋ ショップで買った（買いきりの）追加のお菓子 ＋ ガチャで当てたお菓子
        picker = [{"emoji": c["emoji"], "label": c["label"], "shop_key": None, "stock": None}
                  for c in CANDY_DEFAULT_SPEC]
        for shop_key, item in CANDY_SHOP_JAR_CANDIES.items():
            if candy_extra_owned(shop_key):
                picker.append({"emoji": item["emoji"], "label": item["name"],
                               "shop_key": shop_key, "stock": None})
        for gacha_candy in candy_gacha_pool():
            if candy_gacha_owned(gacha_candy["id"]):
                picker.append({"emoji": gacha_candy["emoji"],
                               "label": f"{gacha_candy['name']} {'★' * int(gacha_candy['stars'])}",
                               "shop_key": f"gacha_{gacha_candy['id']}", "stock": None})
        for candy in picker:
            candy_cost = CANDY_COST_POINTS if candy["shop_key"] is None else CANDY_SHOP_EXTRA_COST_POINTS
            label = f"{candy['emoji']}\n\n{candy['label']}\n💎{candy_cost}"
            button_key = f"btn_{candy['emoji']}" if candy["shop_key"] is None else f"btn_shop_{candy['shop_key']}"
            if st.button(label, use_container_width=True, key=button_key,
                         disabled=(st.session_state.ippo_points < candy_cost or is_full)):
                play_click_sound()
                if candy_jar_put_candy(candy["emoji"], candy["shop_key"]):
                    st.toast(f"{candy['emoji']} を瓶に入れたよ！やったね！")
                st.session_state.praise_message = ""
                save_progress()
                st.rerun()
        st.caption("ショップで買ったお菓子や、ガチャで当てたお菓子もここに追加されます。")
        st.markdown("---")
        if st.button("📖 手に入れたお菓子一覧", use_container_width=True, key="open_candy_collection"):
            play_click_sound()
            st.session_state.page = "candy_collection_page"
            st.rerun()


# =====================================================
# 🎰 お菓子屋さん ⑦ お菓子ガチャ（瓶の注文で使えるお菓子が出る）
# =====================================================
def candy_gacha_pool() -> list:
    """ガチャで出るお菓子の一覧。candy_jar_orders.json の candy_catalog のうち、stars（★1〜5）があるもの。"""
    return [c for c in CANDY_JAR_ORDER_DATA.get("candy_catalog", [])
            if int(c.get("stars", 0)) > 0 and c.get("id")]


def candy_gacha_rates() -> dict:
    """★ごとの出やすさ。JSONのgacha_ratesがあればそれを使う。"""
    rates = dict(CANDY_GACHA_DEFAULT_RATES)
    for star, weight in CANDY_JAR_ORDER_DATA.get("gacha_rates", {}).items():
        try:
            rates[int(star)] = float(weight)
        except (TypeError, ValueError):
            pass
    return rates


def candy_gacha_owned(gacha_id: str) -> bool:
    """そのガチャのお菓子を手に入れたことがあるか。"""
    return int(st.session_state.candy_gacha_owned.get(gacha_id, 0)) > 0


def candy_gacha_give_materials(stars: int) -> dict:
    """同じお菓子が出たとき：今持っている材料の中から、★の数だけ（★1なら1個、★2なら2個…）ランダムでもらえる。
    材料を1つも持っていないときは、材料の種類の中から選ぶ。"""
    materials = st.session_state.candy_shop_materials
    gained = {}
    for _ in range(max(1, int(stars))):
        held = [k for k, v in materials.items() if v > 0 and k in CANDY_SHOP_MATERIALS]
        key = random.choice(held or list(CANDY_SHOP_MATERIALS))
        materials[key] = materials.get(key, 0) + 1
        gained[key] = gained.get(key, 0) + 1
    return gained


def candy_gacha_spin():
    """ガチャを1回回す。コインを使い、結果を candy_gacha_result に入れる。回せなければFalse。"""
    pool = candy_gacha_pool()
    if not pool or st.session_state.candy_coins < CANDY_GACHA_COST_COINS:
        return False
    st.session_state.candy_coins -= CANDY_GACHA_COST_COINS

    rates = candy_gacha_rates()
    star_list = sorted({int(c["stars"]) for c in pool})
    weights = [max(0.0, rates.get(s, 0)) for s in star_list]
    if sum(weights) <= 0:
        weights = [1.0] * len(star_list)
    stars = random.choices(star_list, weights=weights, k=1)[0]
    got = random.choice([c for c in pool if int(c["stars"]) == stars])

    owned = st.session_state.candy_gacha_owned
    is_new = int(owned.get(got["id"], 0)) <= 0
    owned[got["id"]] = int(owned.get(got["id"], 0)) + 1

    result = {"id": got["id"], "emoji": got.get("emoji", "🍬"), "name": got.get("name", ""),
              "stars": stars, "is_new": is_new, "win_comment": got.get("win_comment", ""),
              "stats": CANDY_JAR_ORDER_DATA.get("candy_stats", {}).get(got.get("emoji", ""), {})}
    if not is_new:
        result["materials"] = candy_gacha_give_materials(stars)
        comments = CANDY_JAR_ORDER_DATA.get("gacha_duplicate_comments") or ["同じお菓子が出たよ！ 材料をプレゼントするね🎁"]
        result["dup_comment"] = random.choice(comments)
    st.session_state.candy_gacha_result = result
    save_progress()
    return True


def render_candy_gacha_tab():
    """お菓子ガチャの画面。"""
    st.subheader("🎰 お菓子ガチャ")
    st.write(f"1回 **🪙{CANDY_GACHA_COST_COINS}**。瓶の注文で使えるお菓子が出るよ！")
    st.caption(f"当たったお菓子は「瓶の注文」の瓶に、1個につき {CANDY_SHOP_EXTRA_COST_POINTS} IPPOポイントで入れられます。"
               "すでに持っているお菓子が出たときは、持っている材料からプレゼントがもらえるよ🎁")
    st.metric("🪙 お菓子コイン", st.session_state.candy_coins)

    # 直前のガチャ結果は、画面更新後にここで表示・効果音を鳴らす（効果音は1回だけ）
    result = st.session_state.pop("candy_gacha_result", None)
    if result:
        play_candy_gacha_sound()
        with st.container(border=True):
            st.markdown(f"### {'★' * result['stars']}　{result['emoji']} {result['name']}")
            if result["is_new"]:
                st.success(f"🎉 {result['win_comment']}")
                if result["stars"] >= 4:
                    st.balloons()
                for key, label in (("sweetness", "🍯 甘さ"), ("cuteness", "🎀 可愛さ"), ("seasonality", "🍁 季節感")):
                    value = int(result["stats"].get(key, 0))
                    st.progress(max(0, min(100, value)) / 100, text=f"{label}：{value}")
            else:
                st.info(result["dup_comment"])
                gained_text = "　".join(
                    f"{CANDY_SHOP_MATERIALS[k]['emoji']}{CANDY_SHOP_MATERIALS[k]['name']} ×{n}"
                    for k, n in result["materials"].items() if k in CANDY_SHOP_MATERIALS
                )
                st.success(f"🎁 もらった材料：{gained_text}")

    pool = candy_gacha_pool()
    if not pool:
        st.info("🚧 ガチャのお菓子は準備中です！（candy_jar_orders.json の candy_catalog にガチャのお菓子を入れると遊べます）")
    elif st.button(f"🎰 ガチャを回す（🪙{CANDY_GACHA_COST_COINS}）", type="primary", use_container_width=True,
                   disabled=st.session_state.candy_coins < CANDY_GACHA_COST_COINS, key="candy_gacha_spin_button"):
        if candy_gacha_spin():
            st.rerun()
    if pool and st.session_state.candy_coins < CANDY_GACHA_COST_COINS:
        st.caption("コインがたまったら回せるよ🪙 スイーツを売ったり、瓶を渡したりして集めよう！")

    st.write("---")
    got_count = sum(1 for c in pool if candy_gacha_owned(c["id"]))
    st.markdown(f"#### 🍬 ガチャで出会ったお菓子（{got_count} / {len(pool)} 種類）")
    for c in sorted(pool, key=lambda x: (int(x["stars"]), int(x.get("no", 0)))):
        stars_text = "★" * int(c["stars"])
        if candy_gacha_owned(c["id"]):
            times = int(st.session_state.candy_gacha_owned.get(c["id"], 0))
            st.write(f"{c['emoji']} **{c['name']}**　{stars_text}　（出会った回数 {times}）")
        else:
            st.write(f"❓ ？？？　{stars_text}")


# =====================================================
# 📖 お菓子屋さん ⑧ 手に入れたお菓子一覧ページ
# =====================================================

def candy_is_obtained(emoji: str) -> bool:
    """そのお菓子を手に入れたことがあるか。最初の5種類は最初から所持、
    追加のお菓子はショップで買った（買いきり）か、瓶に入れたことがあれば所持扱い。
    ガチャのお菓子は、ガチャで当てたことがあれば所持扱い。"""
    if any(c["emoji"] == emoji for c in CANDY_DEFAULT_SPEC):
        return True
    if any(c.get("emoji") == emoji and candy_gacha_owned(c["id"]) for c in candy_gacha_pool()):
        return True
    for shop_key, item in CANDY_SHOP_JAR_CANDIES.items():
        if item["emoji"] == emoji and candy_extra_owned(shop_key):
            return True
    return False


def render_candy_collection_page():
    """手に入れたお菓子の一覧ページ（No.・名前・一言・パラメータをJSONから表示）。"""
    st.title("📖 手に入れたお菓子一覧")
    if st.button("↩️ お菓子の瓶に戻る", key="back_to_candy_page"):
        play_click_sound()
        st.session_state.page = "candy_page"
        st.rerun()

    catalog = CANDY_JAR_ORDER_DATA.get("candy_catalog", [])
    stats_all = CANDY_JAR_ORDER_DATA.get("candy_stats", {})
    if not catalog:
        st.warning("お菓子一覧のデータ（candy_catalog）がJSONに見つかりませんでした。")
        return

    obtained = [c for c in catalog if candy_is_obtained(c.get("emoji", ""))]
    st.caption(f"手に入れたお菓子：{len(obtained)} / {len(catalog)} 種類　"
               "（ショップやガチャで新しいお菓子が増えるよ✨）")

    used_counts = {}
    for c in st.session_state.get("all_candy_log", []):
        used_counts[c.get("emoji")] = used_counts.get(c.get("emoji"), 0) + 1

    stat_labels = [("sweetness", "🍯 甘さ"), ("cuteness", "🎀 可愛さ"), ("seasonality", "🍁 季節感")]
    for entry in catalog:
        emoji = entry.get("emoji", "")
        no_text = f"No.{entry.get('no', '?')}"
        if not candy_is_obtained(emoji):
            with st.container(border=True):
                st.markdown(f"### {no_text}　❓ ？？？{'　' + '★' * int(entry['stars']) if entry.get('stars') else ''}")
                st.caption("まだ手に入れていないお菓子です。ガチャで出会えるかも！" if entry.get("stars")
                           else "まだ手に入れていないお菓子です。ショップで探してみよう！")
            continue
        stats = stats_all.get(emoji, {})
        with st.container(border=True):
            star_text = f"　{'★' * int(entry['stars'])}" if entry.get("stars") else ""
            st.markdown(f"### {no_text}　{emoji} {entry.get('name', '')}{star_text}")
            if entry.get("comment"):
                st.write(entry["comment"])
            for key, label in stat_labels:
                value = int(stats.get(key, 0))
                st.progress(max(0, min(100, value)) / 100, text=f"{label}：{value}")
            st.caption(f"これまでに瓶へ入れた数：{used_counts.get(emoji, 0)} 個")


# =====================================================
# 🏪 お菓子屋さん ⑨ お菓子屋さんのメイン画面（タブ構成）
# =====================================================

def render_candy_shop():
    """お菓子屋さんステージ内に表示するショップ・制作・販売・瓶注文UI。"""
    candy_shop_create_jar_order()
    st.markdown("---")
    st.title("🍰 お菓子屋さん")
    st.metric("🪙 お菓子コイン", st.session_state.candy_coins)
    delivery_message = st.session_state.pop("candy_shop_delivery_message", None)
    if delivery_message:
        st.success(f"🙋「{delivery_message['thanks']}」")
        if delivery_message.get("reward", 0):
            st.info(f"🎁「{delivery_message['name']}」を渡したよ！ 🪙{delivery_message['reward']}コインを獲得！")
    level = st.session_state.candy_shop_level
    exp = st.session_state.candy_shop_exp
    need = level * 100 if level < 20 else 0
    st.markdown(f"**お店レベル：Lv.{level}**")
    if need:
        st.progress(min(exp / need, 1.0), text=f"次のレベルまで {exp} / {need}")
    else:
        st.success("最高レベルに到達しました！")

    _candy_tab = stage_tab_selector(["🍓 スイーツを作る", "🧁 商品棚", "🫙 瓶の注文", "🛍️ ショップ", "🎰 お菓子ガチャ", "📖 スイーツ図鑑"], "candy_shop_active_tab")

    if _candy_tab == "🍓 スイーツを作る":
        st.subheader("材料を組み合わせてスイーツを作ろう")
        craft_done = st.session_state.pop("candy_shop_craft_message", None)
        if craft_done:
            play_candy_craft_sound()   # 「この材料でスイーツを作る」を押した直後に1回だけ鳴らす
            st.success(f"{craft_done['text']}　レア度：{'★' * int(craft_done['rarity'])}")
            if int(craft_done["rarity"]) >= 4:
                st.balloons()
        material_names = {
            key: f"{item['emoji']} {item['name']}（所持 {st.session_state.candy_shop_materials.get(key, 0)}）"
            for key, item in CANDY_SHOP_MATERIALS.items()
        }
        available = [key for key in CANDY_SHOP_MATERIALS
                     if st.session_state.candy_shop_materials.get(key, 0) > 0]
        if not available:
            st.info("材料がありません。ショップで材料を購入しよう！")
        else:
            first = st.selectbox("材料1", ["選択しない"] + available,
                                 format_func=lambda k: "選択しない" if k == "選択しない" else material_names[k],
                                 key="candy_shop_material_1")
            second = st.selectbox("材料2（使わなくてもOK）", ["選択しない"] + available,
                                  format_func=lambda k: "選択しない" if k == "選択しない" else material_names[k],
                                  key="candy_shop_material_2")
            book_owned = bool(st.session_state.get("candy_shop_recipe_book_owned", False))
            third = st.selectbox("材料3（秘伝のレシピ書）", ["選択しない"] + available,
                                 format_func=lambda k: "選択しない" if k == "選択しない" else material_names[k],
                                 key="candy_shop_material_3", disabled=not book_owned)
            chosen = [key for key in (first, second, third) if key != "選択しない"]
            if chosen:
                labels = " ＋ ".join(
                    f"{CANDY_SHOP_MATERIALS[k]['emoji']}{CANDY_SHOP_MATERIALS[k]['name']}" for k in chosen
                )
                st.info(f"「{labels}」を使ってスイーツを作る？")
            needed = {}
            for key in chosen:
                needed[key] = needed.get(key, 0) + 1
            insufficient = any(st.session_state.candy_shop_materials.get(k, 0) < n for k, n in needed.items())
            if st.button("🍰 この材料でスイーツを作る", type="primary",
                         disabled=(not chosen or len(chosen) > 3 or insufficient or (len(chosen) == 3 and not book_owned)),
                         key="candy_shop_craft_button"):
                ok, product = candy_shop_craft(chosen)
                if ok:
                    st.session_state.candy_shop_craft_message = {
                        "text": candy_shop_craft_message(product), "rarity": int(product["rarity"]),
                    }
                    st.rerun()
                else:
                    st.error("材料が足りません。")
            if not book_owned:
                st.caption("材料を3つ選ぶには、ショップで『秘伝のレシピ書』を買ってね！")
        st.caption("材料2つのレシピは★2・★3、材料3つのレシピは★4・★5。レシピにない組み合わせは★1のスイーツになるよ。")

        with st.expander("🔎 まだ見つけていないスイーツのヒント（5 IPPOポイント）"):
            if st.session_state.get("candy_shop_last_hint"):
                st.info(st.session_state.candy_shop_last_hint)
            discovered_ids = {item.get("id") for item in st.session_state.candy_shop_discovered}
            undiscovered = [r for r in CANDY_RECIPE_DATA.get("recipes", []) if r.get("id") not in discovered_ids]
            if not undiscovered:
                st.success("すべてのレシピをスイーツ図鑑に登録したよ！")
            elif st.button("💡 ヒントをもらう（5ポイント）",
                           disabled=st.session_state.ippo_points < CANDY_HINT_COST,
                           key="candy_shop_get_hint"):
                hint_recipe = random.choice(undiscovered)
                st.session_state.ippo_points -= CANDY_HINT_COST
                st.session_state.candy_shop_last_hint = "💡 " + hint_recipe.get("hint", "材料をいろいろ組み合わせてみよう！")
                save_progress()
                st.rerun()

    if _candy_tab == "🧁 商品棚":
        st.subheader("商品棚")
        st.write(f"展示中：{len(st.session_state.candy_shop_displayed)} / {st.session_state.candy_shop_shelf_capacity} 個")
        if st.session_state.candy_shop_products:
            options = list(range(len(st.session_state.candy_shop_products)))
            selected_product = st.selectbox(
                "棚に展示する商品",
                options,
                format_func=lambda i: f"{st.session_state.candy_shop_products[i]['emoji']} {st.session_state.candy_shop_products[i]['name']}（★{st.session_state.candy_shop_products[i]['rarity']}）",
                key="candy_shop_product_to_display",
            )
            if st.button("🪧 商品を棚に並べる", disabled=(
                    len(st.session_state.candy_shop_displayed) >= st.session_state.candy_shop_shelf_capacity),
                    key="candy_shop_display_button"):
                st.session_state.candy_shop_displayed.append(
                    st.session_state.candy_shop_products.pop(selected_product)
                )
                save_progress()
                st.rerun()
        else:
            st.info("まだ商品がありません。材料を組み合わせて作ってみよう！")

        if st.session_state.candy_shop_displayed:
            st.markdown("#### 🪧 いまの棚")
            for idx, product in enumerate(list(st.session_state.candy_shop_displayed)):
                with st.container(border=True):
                    st.markdown(
                        f"### {product['emoji']} {product['name']}　{'★' * int(product.get('rarity', 1))}"
                    )
                    st.caption(f"お値段：🪙 {product.get('sell_price', 20)}")
                    if st.button("↩️ 棚からもどす", key=f"candy_shop_return_{idx}"):
                        candy_shop_return_displayed(idx)
                        st.rerun()
        else:
            st.info("棚は空です。商品を作って展示しよう！")

        st.write("---")
        st.markdown("#### 🚪 お店をひらく")
        st.caption("お客さんにはそれぞれ好みがあるよ。大好物を見つけると、特別なお礼をしてくれるかも💖")
        visit_result = st.session_state.pop("candy_shop_visit_result", None)
        if visit_result:
            for visit in visit_result["visits"]:
                with st.container(border=True):
                    st.markdown(f"**{visit['emoji']} {visit['name']}**" + ("　🎫 特別招待で来てくれたよ！" if visit.get("invited") else ""))
                    st.write(f"「{visit['line']}」")
                    if visit["bought"]:
                        bonus_text = "　💖大好物ボーナス！" if visit["loved"] else ""
                        tip_text = f"　✨チップ +{visit['tip']}" if visit.get("tip") else ""
                        st.success(f"{visit['bought']['emoji']} {visit['bought']['name']} を購入！ 🪙+{visit['paid']}{bonus_text}{tip_text}")
            if visit_result["total"]:
                st.info(f"🪙 今回の売り上げ：{visit_result['total']} コイン")
        if not CANDY_RECIPE_DATA.get("customers"):
            st.warning("お客さんのデータ（customers）が見つかりませんでした。")
        if not st.session_state.candy_shop_displayed:
            st.caption("棚にスイーツを並べると、お店をひらけるよ🍰")
        if st.button("🔔 お店をひらいてお客さんを迎える", type="primary",
                     disabled=(not st.session_state.candy_shop_displayed or not CANDY_RECIPE_DATA.get("customers")),
                     key="candy_shop_open_button"):
            st.session_state.candy_shop_visit_result = candy_shop_open_for_business()
            st.rerun()

        with st.expander("📒 常連さんノート", expanded=bool(st.session_state.pop("candy_notes_keep_open", False))):
            notes = st.session_state.candy_shop_customer_notes
            all_customers = CANDY_RECIPE_DATA.get("customers", [])
            met = sum(1 for c in all_customers if c["id"] in notes)
            st.caption(f"出会ったお客さん：{met} / {len(all_customers)} 人")
            ticket_count = int(st.session_state.get("candy_shop_invite_tickets", 0))
            invited_now = st.session_state.get("candy_shop_invited_customers", [])
            st.write(f"🎫 特別招待チケット：**{ticket_count}枚**")
            if ticket_count <= 0 and not invited_now:
                st.caption("チケットは「🛍️ ショップ」で買えるよ。使うと、次にお店をひらいたとき、そのお客さんが1回だけ必ず来てくれます。")
            for customer in all_customers:
                note = notes.get(customer["id"])
                with st.container(border=True):
                    if not note:
                        st.markdown("### ❓ ？？？")
                        st.caption("まだ会っていないお客さんです。")
                        continue
                    st.markdown(f"### {customer.get('emoji', '🙂')} {customer.get('name', '')}")
                    if int(note.get("loved", 0)) > 0:
                        st.write(f"💖 大好物：{' '.join(customer.get('likes', []))}")
                    else:
                        st.write(f"🔎 ヒント：{customer.get('hint', '')}")
                    st.caption(f"来店 {note.get('visits', 0)} 回／購入 {note.get('bought', 0)} 回／大好物 {note.get('loved', 0)} 回")
                    if customer["id"] in invited_now:
                        st.success("🎫 次にお店をひらいたとき、このお客さんが必ず来てくれるよ！")
                    elif ticket_count > 0:
                        if st.button("🎫 このお客さんにチケットを使う！", key=f"candy_shop_use_ticket_{customer['id']}",
                                     use_container_width=True):
                            st.session_state.candy_shop_invite_tickets = ticket_count - 1
                            st.session_state.candy_shop_invited_customers = list(invited_now) + [customer["id"]]
                            st.session_state.candy_notes_keep_open = True
                            save_progress()
                            st.rerun()

    if _candy_tab == "🫙 瓶の注文":
        st.subheader("🫙 瓶の注文")
        order = st.session_state.candy_shop_jar_order
        if order:
            message = order.get("message") or "お菓子をつめた瓶が欲しいな～！"
            with st.container(border=True):
                st.markdown("### 💬 お客さんの注文")
                st.info(f"🙋 「{message}」")
                st.caption("お客さんの要望に合うお菓子を選んで、瓶に詰めてあげよう！")

        st.write("---")
        render_candy_jar_section()

        st.write("---")
        st.markdown("#### 過去の瓶注文")
        for record in reversed(st.session_state.candy_shop_jar_order_log[-10:]):
            record_name = f"「{record['name']}」" if record.get("name") else ""
            st.write(f"🫙 {record['date']}：{record_name}{record['quantity']}個入り＋{record['reward']}コイン")

    if _candy_tab == "🛍️ ショップ":
        st.subheader("ショップ")
        st.markdown("#### 📕 秘伝のレシピ書")
        if st.session_state.get("candy_shop_recipe_book_owned", False):
            st.success("秘伝のレシピ書を持っているよ！材料を3つ選べるようになりました。")
        else:
            st.write("材料を3つ組み合わせる特別なスイーツ作りに挑戦できるよ！")
            if st.button(f"秘伝のレシピ書を買う：🪙 {CANDY_RECIPE_BOOK_PRICE}",
                         disabled=st.session_state.candy_coins < CANDY_RECIPE_BOOK_PRICE,
                         key="candy_shop_buy_recipe_book"):
                st.session_state.candy_coins -= CANDY_RECIPE_BOOK_PRICE
                st.session_state.candy_shop_recipe_book_owned = True
                save_progress()
                st.success("秘伝のレシピ書を手に入れたよ！")
                st.rerun()
        st.markdown("#### 🎫 特別招待チケット")
        st.write("使うと、次にお店をひらいたとき、選んだお客さんが **1回だけ必ず** 来てくれるよ！（1枚使いきり）")
        st.caption("使うときは「🧁 商品棚」タブの『📒 常連さんノート』で、会ったことのあるお客さんに使えます。")
        st.write(f"所持：{int(st.session_state.get('candy_shop_invite_tickets', 0))}枚")
        if st.button(f"チケットを1枚買う：🪙 {CANDY_INVITE_TICKET_PRICE}",
                     disabled=st.session_state.candy_coins < CANDY_INVITE_TICKET_PRICE,
                     key="candy_shop_buy_invite_ticket"):
            st.session_state.candy_coins -= CANDY_INVITE_TICKET_PRICE
            st.session_state.candy_shop_invite_tickets = int(st.session_state.get("candy_shop_invite_tickets", 0)) + 1
            save_progress()
            st.rerun()
        st.markdown("#### 🧁 材料")
        cols = st.columns(2)
        for idx, (material_key, item) in enumerate(CANDY_SHOP_MATERIALS.items()):
            with cols[idx % 2]:
                st.write(f"{item['emoji']} **{item['name']}**")
                st.caption(f"所持：{st.session_state.candy_shop_materials.get(material_key, 0)}")
                if st.button(f"1個購入：🪙 {item['price']}", key=f"candy_shop_buy_material_{material_key}",
                             disabled=st.session_state.candy_coins < item["price"]):
                    candy_shop_buy_material(material_key)
                    st.rerun()

        st.markdown("#### 🍬 追加のお菓子（瓶に入れる用）")
        st.caption(f"一度買えば、ずっと「瓶の注文」の瓶に入れられるようになります（入れるときは1個につき {CANDY_SHOP_EXTRA_COST_POINTS} IPPOポイント）。"
                   "最初の5種類（🍬🍭🍫🍩🍪）は買わなくても入れられます。")
        for candy_key, item in CANDY_SHOP_JAR_CANDIES.items():
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"{item['emoji']} **{item['name']}**")
                st.caption("✅ 購入済み" if candy_extra_owned(candy_key) else "まだ持っていません")
            with col_b:
                if candy_extra_owned(candy_key):
                    st.button("購入済み", key=f"candy_shop_buy_jar_candy_{candy_key}", disabled=True)
                elif st.button(f"買う 🪙{item['price']}", key=f"candy_shop_buy_jar_candy_{candy_key}",
                               disabled=st.session_state.candy_coins < item["price"]):
                    st.session_state.candy_coins -= item["price"]
                    # 買いきり：1以上なら「持っている」扱い（瓶に入れても減らない）
                    st.session_state.candy_shop_jar_candy_stock[candy_key] = 1
                    save_progress()
                    st.rerun()

        st.markdown("#### 🗄️ 棚")
        st.write(f"現在の展示数上限：{st.session_state.candy_shop_shelf_capacity}個")
        shelf_price = 100 * (st.session_state.candy_shop_shelf_capacity - 1)
        if st.button(f"棚を1つ増やす：🪙 {shelf_price}",
                     disabled=st.session_state.candy_coins < shelf_price or st.session_state.candy_shop_shelf_capacity >= 20,
                     key="candy_shop_buy_shelf"):
            st.session_state.candy_coins -= shelf_price
            st.session_state.candy_shop_shelf_capacity += 1
            save_progress()
            st.rerun()
        st.caption("棚を増やすと、一度に展示できる商品数が増えます。")

        st.markdown("#### 💎 IPPOポイント交換")
        st.caption("お菓子コイン500枚で、IPPOポイントを1ポイント交換できます。")
        st.write(f"現在のお菓子コイン：🪙 {st.session_state.candy_coins}枚")
        st.write(f"現在のIPPOポイント：💎 {st.session_state.ippo_points}ポイント")
        if st.button(
            "💎 500お菓子コインで1IPPOポイントと交換",
            disabled=st.session_state.candy_coins < 500,
            key="candy_shop_exchange_ippo_point",
        ):
            st.session_state.candy_coins -= 500
            st.session_state.ippo_points += 1
            save_progress()
            st.success("IPPOポイントを1ポイント受け取ったよ！")
            st.rerun()

    if _candy_tab == "🎰 お菓子ガチャ":
        render_candy_gacha_tab()

    if _candy_tab == "📖 スイーツ図鑑":
        st.subheader("📖 スイーツ図鑑")
        all_recipes = CANDY_RECIPE_DATA.get("recipes", [])
        all_recipe_ids = {recipe.get("id") for recipe in all_recipes}
        discovered_ids = {
            product.get("id") for product in st.session_state.candy_shop_discovered
            if product.get("id") in all_recipe_ids
        }
        discovered_count = len(discovered_ids)
        total_count = len(all_recipes)
        st.metric("発見したスイーツ / 全種類", f"{discovered_count} / {total_count}")
        st.progress(discovered_count / total_count if total_count else 0)

        if not st.session_state.candy_shop_discovered:
            st.info("まだスイーツが登録されていません。材料を組み合わせて発見しよう！")
        else:
            recipe_by_id = {recipe.get("id"): recipe for recipe in all_recipes}
            for product in st.session_state.candy_shop_discovered:
                recipe = recipe_by_id.get(product.get("id"), {})
                material_ids = product.get("materials") or recipe.get("materials", [])
                material_names = [
                    f"{CANDY_SHOP_MATERIALS.get(mid, {}).get('emoji', '🧺')} "
                    f"{CANDY_SHOP_MATERIALS.get(mid, {}).get('name', mid)}"
                    for mid in material_ids
                ]
                st.write(f"{product['emoji']} **{product['name']}**　{'★' * int(product.get('rarity', 1))}")
                if material_names:
                    st.caption("作り方：" + " ＋ ".join(material_names))
                else:
                    st.caption("作り方：材料の記録がありません（このスイーツは以前のバージョンで発見したものです）。")


def add_single_task(title: str) -> bool:
    title = title.strip()
    if not title:
        return False
    st.session_state.single_tasks.append({
        "id": get_now_jst().strftime("%Y%m%d%H%M%S%f"),
        "title": title, "completed": False, "completed_at": None,
        "repeat_enabled": False, "repeat_mode": "range", "repeat_start": None,
        "repeat_end": None, "repeat_weekday": 0, "completed_dates": [],
        "created_date": get_now_jst().strftime("%Y/%m/%d"),
    })
    return True


def refresh_single_task_status() -> bool:
    """
    期間つきの反復タスク（開始日〜終了日）を「完了したタスク」へ移す。
    ・期間のすべての日を達成した → 移動
    ・終了日を過ぎた（1回以上は達成している） → 移動
    ※毎週の反復（終了日なし）は期間が決まっていないので、自動では移動しない。
    変更があればTrueを返す。
    """
    today = get_now_jst().date()
    changed = False
    for task in st.session_state.get("single_tasks", []):
        if not task.get("repeat_enabled") or task.get("completed"):
            continue
        if task.get("repeat_mode") != "range" or not task.get("repeat_end"):
            continue
        done_dates = set(task.get("completed_dates", []))
        if not done_dates:
            continue
        try:
            start = datetime.strptime(task.get("repeat_start"), "%Y/%m/%d").date()
            end = datetime.strptime(task.get("repeat_end"), "%Y/%m/%d").date()
        except (ValueError, TypeError):
            continue
        total_days = (end - start).days + 1
        all_done = 0 < total_days <= 400 and all(
            (start + timedelta(days=i)).strftime("%Y/%m/%d") in done_dates for i in range(total_days)
        )
        if all_done or end < today:
            task["completed"] = True
            if not task.get("completed_at"):
                task["completed_at"] = get_now_jst().strftime("%Y/%m/%d %H:%M")
            changed = True
    return changed


def complete_single_task(task_id: str, completion_date: str = None) -> bool:
    """単発・反復タスクを達成し、指定日につき1ポイントを加算する。"""
    today = completion_date or get_now_jst().strftime("%Y/%m/%d")
    for task in st.session_state.single_tasks:
        if task.get("id") == task_id:
            completed_dates = task.setdefault("completed_dates", [])
            if today in completed_dates:
                return False
            if not task.get("repeat_enabled") and task.get("completed"):
                return False
            completed_dates.append(today)
            task["completed_at"] = get_now_jst().strftime("%Y/%m/%d %H:%M")
            if not task.get("repeat_enabled"):
                task["completed"] = True
            st.session_state.ippo_points += SINGLE_TASK_POINTS
            # リマインド達成をイベント記録に残す（反復タスクも日付ごとに記録）
            completion_log = st.session_state.setdefault("single_task_completion_log", [])
            completion_log.append({
                "task_id": task_id,
                "title": task.get("title", "タスク"),
                "date": f"{today} {get_now_jst().strftime('%H:%M')}",
                "points": SINGLE_TASK_POINTS,
            })
            add_sticker_for_date(today)
            refresh_single_task_status()
            return True
    return False


# =====================================================
# 💾 セーブデータ（Supabaseクラウド連携）
# =====================================================
PERSISTENT_KEYS = [
    "target_list",
    "jar_capacity",
    "jar_candies",
    "jar_name",
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
    "schedule_templates",  # 自分用スケジュールテンプレート（最大5件）
    "ippo_points",
    "aqua_reward_queue",
    "aqua_fish",
    "aqua_decorations",
    "aqua_food_inventory",
    "aqua_feed_log",
    "aqua_duplicate_bonus",
    "aqua_goal_log",
    "aqua_tank_history",
    "dino_owned",
    "dino_partner",
    "dino_food",
    "dino_berries",
    "dino_stat_items",
    "dino_special_dice",
    "dino_race",
    "dino_locked_course",
    "dino_event_log",
    "dino_unlocked_courses",
    "single_tasks",
    "single_task_completion_log",
    "candy_coins",
    "candy_shop_materials",
    "candy_shop_jar_candy_stock",
    "candy_shop_unlocked_recipes",
    "candy_shop_recipe_book_owned",
    "candy_shop_products",
    "candy_shop_displayed",
    "candy_shop_discovered",
    "candy_shop_shelf_capacity",
    "candy_shop_level",
    "candy_shop_exp",
    "candy_shop_jar_order",
    "candy_shop_jar_order_log",
    "candy_shop_customer_notes",
    "candy_shop_invite_tickets",
    "candy_shop_invited_customers",
    "candy_gacha_owned",
]

PERSISTENT_DEFAULTS = {
    "target_list": [],
    "jar_capacity": 30,
    "jar_candies": [],
    "jar_name": "",
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
    "schedule_templates": [],
    "ippo_points": 0,
    "aqua_reward_queue": [],
    "aqua_fish": [],
    "aqua_decorations": [],
    "aqua_food_inventory": {"normal": 0, "premium": 0, "bundle": 0, "grand_bundle": 0},
    "aqua_feed_log": [],
    "aqua_duplicate_bonus": 0,
    "aqua_goal_log": [],
    "aqua_tank_history": None,
    "dino_owned": [],
    "dino_partner": None,
    "dino_food": {"meat": 0, "feast": 0},
    "dino_berries": {key: 0 for key in DINO_BERRIES},
    "dino_stat_items": {},
    "dino_special_dice": 0,
    "dino_race": {},
    "dino_locked_course": None,
    "dino_event_log": [],
    "dino_unlocked_courses": [],
    "single_tasks": [],
    "single_task_completion_log": [],
    # お菓子屋さんは初期コイン100枚と少量の材料から開始（追加のお菓子はショップで購入）
    "candy_coins": 100,
    "candy_shop_materials": {"whip": 2, "chocolate": 2, "strawberry": 2, "flour": 2, "cookie": 2},
    "candy_shop_jar_candy_stock": {"cupcake": 0, "dango": 0, "pudding": 0, "shaved_ice": 0, "waffle": 0},
    "candy_shop_unlocked_recipes": [],
    "candy_shop_recipe_book_owned": False,
    "candy_shop_products": [],
    "candy_shop_displayed": [],
    "candy_shop_discovered": [],
    "candy_shop_shelf_capacity": 2,
    "candy_shop_level": 1,
    "candy_shop_exp": 0,
    "candy_shop_jar_order": None,
    "candy_shop_jar_order_log": [],
    "candy_shop_customer_notes": {},
    "candy_shop_invite_tickets": 0,
    "candy_shop_invited_customers": [],
    "candy_gacha_owned": {},
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

            # 旧データでは「アクアポイント」と「お菓子ポイント」が別管理だったため、
            # 初回移行時に両方を合算して共通のIPPOポイントへ引き継ぐ。
            if "ippo_points" in saved_data:
                st.session_state.ippo_points = int(saved_data.get("ippo_points", 0) or 0)
            else:
                old_aqua_points = int(saved_data.get("aqua_points", 0) or 0)
                old_candy_points = int(saved_data.get("candy_points", 0) or 0)
                st.session_state.ippo_points = old_aqua_points + old_candy_points
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


def schedule_time_options(step_minutes: int = 5) -> list:
    """分の候補（通常は5分刻み）。"""
    return list(range(0, 60, step_minutes))


def schedule_time_selectbox(label: str, value: str, key: str) -> str:
    """開始・終了時刻を「時」「分」の2つの選択欄で指定する。"""
    try:
        initial_hour, initial_minute = map(int, str(value).split(":")[:2])
        if not (0 <= initial_hour <= 23 and 0 <= initial_minute <= 59):
            raise ValueError("invalid time")
    except (ValueError, TypeError):
        initial_hour, initial_minute = 0, 0

    # 過去に1分単位で登録した時刻も、編集時に失わないようにする。
    minute_options = schedule_time_options(5)
    if initial_minute not in minute_options:
        minute_options = sorted(minute_options + [initial_minute])

    st.markdown(f"**{label}**")
    hour_col, minute_col = st.columns(2)
    with hour_col:
        selected_hour = st.selectbox(
            "時", options=list(range(24)), index=initial_hour,
            format_func=lambda hour: f"{hour:02d} 時", key=f"{key}_hour",
        )
    with minute_col:
        selected_minute = st.selectbox(
            "分", options=minute_options,
            index=minute_options.index(initial_minute),
            format_func=lambda minute: f"{minute:02d} 分", key=f"{key}_minute",
        )
    return f"{selected_hour:02d}:{selected_minute:02d}"


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
    # 水族館側で達成した目標も、お菓子屋さんと同じようにイベント記録へ表示する
    for ag in st.session_state.get("aqua_goal_log", []):
        if ag["date"].startswith(date_str):
            level = ag.get("level", "")
            points = ag.get("points", 0)
            if ag.get("source") == "dino":
                label = f"🦖 『{ag.get('target', '')}』{level}目標達成（💎{points} IPPOポイント）"
            elif ag.get("source") == "candy":
                label = f"🍬 『{ag.get('target', '')}』{level}目標達成（💎{points} IPPOポイント）"
            else:
                label = f"🐠 『{ag.get('target', '')}』{level}目標達成（💎{points} IPPOポイント）"
            events.append((ag["date"].split(" ")[1], label))
    # リマインド／単発タスクの達成（反復タスクも達成日ごとに表示）
    for completion in st.session_state.get("single_task_completion_log", []):
        completed_at = completion.get("date", "")
        if completed_at.startswith(date_str):
            event_time = completed_at.split(" ")[1] if " " in completed_at else "--:--"
            title = completion.get("title", "タスク")
            points = completion.get("points", SINGLE_TASK_POINTS)
            events.append((event_time, f"🎉 リマインド『{title}』達成！（💎{points} IPPOポイント）"))
    # 旧データ互換：達成ログがない旧形式の単発タスクだけ従来表示
    for st_task in st.session_state.get("single_tasks", []):
        completed_at = st_task.get("completed_at")
        already_logged = any(
            item.get("task_id") == st_task.get("id") and item.get("date", "").startswith(date_str)
            for item in st.session_state.get("single_task_completion_log", [])
        )
        if st_task.get("completed") and completed_at and completed_at.startswith(date_str) and not already_logged:
            events.append((completed_at.split(" ")[1], f"✅ 単発タスク『{st_task.get('title', '')}』完了（💎{SINGLE_TASK_POINTS} IPPOポイント）"))
    # 恐竜レースでの出来事（レベルアップ・力試しなど）
    for de in st.session_state.get("dino_event_log", []):
        if de["date"].startswith(date_str):
            events.append((de["date"].split(" ")[1], de["text"]))
    events.sort(key=lambda ev: ev[0])
    return events


def build_schedule_print_html(date_strings: list, include_planned: bool, include_actual: bool) -> str:
    """選択した最大7日分を、1枚のSVG画像としてまとめて印刷する。"""
    kinds = []
    if include_planned:
        kinds.append(("planned", "予定", "#4CAF50"))
    if include_actual:
        kinds.append(("actual", "記録", "#2196F3"))
    ordered_dates = sorted(set(date_strings), key=lambda v: datetime.strptime(v, "%Y/%m/%d"))[:7]
    if not ordered_dates or not kinds:
        return "<p>印刷する日付と種類を選択してください。</p>"

    left_margin, top_margin = 54, 52
    day_width = 190
    track_gap = 5
    track_width = (day_width - 16 - track_gap * (len(kinds) - 1)) / len(kinds)
    graph_top, graph_height = top_margin, 720
    graph_bottom = graph_top + graph_height
    total_width = left_margin + day_width * len(ordered_dates) + 8
    total_height = graph_bottom + 18
    parts = [f'<rect x="0" y="0" width="{total_width}" height="{total_height}" fill="#fff"/>']

    for half in range(49):
        mins = half * 30
        y = graph_top + graph_height * mins / 1440
        major = mins % 60 == 0
        parts.append(
            f'<line x1="{left_margin}" y1="{y:.1f}" x2="{total_width}" y2="{y:.1f}" '
            f'stroke="{"#999" if major else "#e5e5e5"}" stroke-width="{"1.2" if major else ".6"}"/>'
        )
        if major:
            parts.append(f'<text x="{left_margin - 7}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#222">{mins // 60:02d}:00</text>')

    for day_index, date_str in enumerate(ordered_dates):
        day_x = left_margin + day_index * day_width
        day = st.session_state.daily_schedule.get(date_str, {"planned": [], "actual": []})
        date_label = datetime.strptime(date_str, "%Y/%m/%d").strftime("%m/%d（%a）")
        parts.append(f'<text x="{day_x + day_width / 2:.1f}" y="28" text-anchor="middle" font-size="16" font-weight="bold" fill="#222">{html.escape(date_label)}</text>')
        for kind_index, (key, title, fallback_color) in enumerate(kinds):
            x = day_x + 8 + kind_index * (track_width + track_gap)
            parts.append(f'<text x="{x + track_width / 2:.1f}" y="46" text-anchor="middle" font-size="11" font-weight="bold" fill="#222">{title}</text>')
            parts.append(f'<rect x="{x:.1f}" y="{graph_top}" width="{track_width:.1f}" height="{graph_height}" fill="#fff" stroke="#777" stroke-width=".8"/>')
            for entry in sorted(day.get(key, []) or [], key=lambda item: item.get("start", "00:00")):
                try:
                    start_min = time_to_minutes(entry.get("start", "00:00"))
                    end_min = time_to_minutes(entry.get("end", "00:00"))
                    if not (0 <= start_min < end_min <= 1440):
                        continue
                except Exception:
                    continue
                y1 = graph_top + graph_height * start_min / 1440
                y2 = graph_top + graph_height * end_min / 1440
                color = str(entry.get("color", fallback_color))
                if not (len(color) == 7 and color.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in color[1:])):
                    color = fallback_color
                label = html.escape(str(entry.get("label", "")))
                parts.append(f'<rect x="{x + 2:.1f}" y="{y1:.1f}" width="{max(track_width - 4, 1):.1f}" height="{max(y2-y1, 3):.1f}" rx="2" fill="{color}" fill-opacity=".9" stroke="#333" stroke-width=".4"/>')
                if y2 - y1 >= 18:
                    parts.append(f'<text x="{x + track_width / 2:.1f}" y="{(y1 + y2) / 2 + 3:.1f}" text-anchor="middle" font-size="9" fill="#fff" stroke="#222" stroke-width=".5" paint-order="stroke">{label}</text>')
        parts.append(f'<line x1="{day_x + day_width}" y1="8" x2="{day_x + day_width}" y2="{graph_bottom}" stroke="#aaa" stroke-width="1"/>')

    combined_svg = f'<svg xmlns="http://www.w3.org/2000/svg" class="combined-schedule" viewBox="0 0 {total_width} {total_height}" role="img" aria-label="スケジュール帯グラフ">' + "".join(parts) + "</svg>"
    return f'''<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
*{{box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#222;margin:0;padding:14px;background:#f5f7fa}}
.toolbar{{display:flex;justify-content:space-between;align-items:center;max-width:1200px;margin:0 auto 12px}}
.toolbar h1{{font-size:22px;margin:0}}.print-button{{padding:10px 18px;background:#1769aa;color:white;border:0;border-radius:8px;font-weight:bold;font-size:16px;cursor:pointer}}
.image-sheet{{background:#fff;max-width:1200px;margin:0 auto;padding:10px;border:1px solid #aaa}}.combined-schedule{{display:block;width:100%;height:auto}}
@page{{size:A4 landscape;margin:7mm}}@media print{{body{{padding:0;background:#fff}}.toolbar{{display:none}}.image-sheet{{max-width:none;padding:0;border:0}}.combined-schedule{{width:100%;height:auto;max-height:190mm;print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
</style></head><body><div class="toolbar"><h1>IPPO スケジュール印刷</h1><button class="print-button" onclick="window.focus();window.print()">🖨️ 印刷する</button></div><div class="image-sheet">{combined_svg}</div></body></html>'''


def render_schedule_clipboard(date_str: str):
    """予定だけをコピーし、別の日へ貼り付ける（記録はコピーしない）。"""
    schedule = st.session_state.daily_schedule.setdefault(date_str, {"planned": [], "actual": []})
    clipboard = st.session_state.get("schedule_clipboard")
    with st.container(border=True):
        st.markdown("#### 📋 予定のコピー・貼り付け")
        col_copy, col_paste = st.columns(2)
        with col_copy:
            if st.button("📋 この日の予定をコピー", key=f"copy_schedule_{date_str}",
                         use_container_width=True, disabled=not schedule["planned"]):
                play_click_sound(delay=0)
                st.session_state.schedule_clipboard = {
                    "source_date": date_str,
                    "planned": copy.deepcopy(schedule["planned"]),
                }
                st.rerun()
        with col_paste:
            if st.button("📥 コピーした予定を貼り付け", key=f"paste_schedule_{date_str}",
                         use_container_width=True, disabled=not clipboard):
                play_click_sound(delay=0)
                st.session_state.schedule_paste_target = date_str
                st.rerun()
        if clipboard:
            st.caption(f"コピー中：{clipboard['source_date']} の予定 {len(clipboard['planned'])} 件（記録は対象外）")
        else:
            st.caption("コピー元の日付で「この日の予定をコピー」を押してください。")

        if st.session_state.get("schedule_paste_target") == date_str and clipboard:
            st.warning(f"{date_str} に {len(clipboard['planned'])} 件の予定を貼り付けます。")
            paste_mode = st.radio(
                "貼り付け方法", ["既存の予定に追加", "既存の予定を置き換え"],
                key=f"paste_mode_{date_str}",
            )
            if paste_mode == "既存の予定を置き換え" and schedule["planned"]:
                st.warning("この日の既存の予定は消えます。実際の記録は残ります。")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("貼り付けを確定", type="primary", use_container_width=True,
                             key=f"confirm_paste_{date_str}"):
                    copied = copy.deepcopy(clipboard["planned"])
                    if paste_mode == "既存の予定を置き換え":
                        schedule["planned"] = copied
                    else:
                        schedule["planned"].extend(copied)
                    st.session_state.schedule_paste_target = None
                    save_progress()
                    st.rerun()
            with cancel_col:
                if st.button("キャンセル", use_container_width=True,
                             key=f"cancel_paste_{date_str}"):
                    st.session_state.schedule_paste_target = None
                    st.rerun()


def render_schedule_templates(date_str: str):
    """最大5件のテンプレートを編集し、選択日の予定・記録へ独立して貼り付ける。"""
    templates = st.session_state.setdefault("schedule_templates", [])
    if templates is None:
        templates = []
        st.session_state.schedule_templates = templates
    day = st.session_state.daily_schedule.setdefault(date_str, {"planned": [], "actual": []})
    with st.expander("🗂️ 自分だけの一日テンプレート（最大5つ）", expanded=False):
        st.caption("いつもの一日の流れを保存して、好きな日の予定にも記録にも使えます。")
        if len(templates) < 5:
            with st.form(f"template_create_{date_str}"):
                new_name = st.text_input("新しいテンプレート名", placeholder="例：平日の勉強日", key=f"template_new_name_{date_str}")
                creation = st.radio("作り方", ["空のテンプレートを作る", "この日の予定から作る", "この日の記録から作る"], key=f"template_creation_{date_str}")
                if st.form_submit_button("➕ テンプレートを作成"):
                    if not new_name.strip():
                        st.error("テンプレート名を入力してください。")
                    elif len(templates) >= 5:
                        st.warning("テンプレートは5つまでです。")
                    else:
                        source = {"空のテンプレートを作る": None, "この日の予定から作る": "planned", "この日の記録から作る": "actual"}[creation]
                        entries = copy.deepcopy(day[source]) if source else []
                        templates.append({"id": get_now_jst().strftime("%Y%m%d%H%M%S%f"), "name": new_name.strip(), "entries": entries})
                        play_click_sound(delay=0)
                        save_progress()
                        st.rerun()
        else:
            st.info("5つ登録済みです。新しく作るには、不要なテンプレートを削除してください。")

        if not templates:
            st.caption("まだテンプレートはありません。")
            return

        names = [f"{i + 1}. {t['name']}（{len(t.get('entries', []))}件）" for i, t in enumerate(templates)]
        chosen = st.selectbox("編集・貼り付けするテンプレート", range(len(templates)), format_func=lambda i: names[i], key=f"template_choose_{date_str}")
        template = templates[chosen]
        template_id = template.get("id", str(chosen))
        entries = template.setdefault("entries", [])
        with st.form(f"template_rename_{date_str}_{template_id}"):
            renamed = st.text_input("テンプレート名を変更", value=template["name"])
            if st.form_submit_button("名前を保存"):
                if renamed.strip():
                    template["name"] = renamed.strip()
                    save_progress()
                    st.rerun()
                else:
                    st.error("名前を入力してください。")

        st.markdown("**🕒 テンプレートの内容**")
        if not entries:
            st.caption("まだ項目がありません。下のフォームから追加できます。")
        for i, entry in enumerate(entries):
            with st.expander(f"{entry['start']}〜{entry['end']}　{entry.get('label', '')}", expanded=False):
                with st.form(f"template_edit_{date_str}_{template_id}_{i}"):
                    label = st.text_input("内容", value=entry.get("label", ""))
                    start = schedule_time_selectbox("開始時刻", entry["start"],
                                                    key=f"template_edit_start_{date_str}_{template_id}_{i}")
                    end = schedule_time_selectbox("終了時刻", entry["end"],
                                                  key=f"template_edit_end_{date_str}_{template_id}_{i}")
                    color_options = list(SCHEDULE_COLORS)
                    current_color = entry.get("color", "#4CAF50")
                    current_idx = next((j for j, name in enumerate(color_options) if SCHEDULE_COLORS[name] == current_color), 3)
                    color_name = st.selectbox("色", color_options, index=current_idx)
                    save_item = st.form_submit_button("💾 この項目を保存")
                    delete_item = st.form_submit_button("🗑️ この項目を削除")
                    if delete_item:
                        entries.pop(i)
                        save_progress()
                        st.rerun()
                    if save_item:
                        if not label.strip() or not valid_template_time_range(start, end):
                            st.error("内容と正しい時刻を入力してください（開始は終了より前）。")
                        else:
                            entries[i] = {"label": label.strip(), "start": start, "end": end, "color": SCHEDULE_COLORS[color_name]}
                            entries.sort(key=lambda e: e["start"])
                            save_progress()
                            st.rerun()

        with st.form(f"template_add_{date_str}_{template_id}"):
            st.markdown("**➕ テンプレートに予定を追加**")
            label = st.text_input("内容", placeholder="例：薬理の問題演習")
            c1, c2 = st.columns(2)
            with c1:
                start = schedule_time_selectbox("開始時刻", "09:00",
                                                key=f"template_add_start_{date_str}_{template_id}")
            with c2:
                end = schedule_time_selectbox("終了時刻", "10:00",
                                              key=f"template_add_end_{date_str}_{template_id}")
            color_name = st.selectbox("色", list(SCHEDULE_COLORS), index=3)
            if st.form_submit_button("➕ 項目を追加"):
                if not label.strip() or not valid_template_time_range(start, end):
                    st.error("内容と正しい時刻を入力してください（開始は終了より前）。")
                else:
                    entries.append({"label": label.strip(), "start": start, "end": end, "color": SCHEDULE_COLORS[color_name]})
                    entries.sort(key=lambda e: e["start"])
                    save_progress()
                    st.rerun()

        st.divider()
        st.markdown(f"**📥 『{template['name']}』を貼り付け**")
        with st.container(border=True):
            destination = st.radio("貼り付け先", ["📅 予定", "✅ 記録"], horizontal=True,
                                   key=f"template_paste_dest_{date_str}_{template_id}")
            try:
                paste_default = datetime.strptime(date_str, "%Y/%m/%d").date()
            except ValueError:
                paste_default = get_now_jst().date()
            target_dates = schedule_date_range_picker(
                "貼り付ける日付（カレンダーで ○日〜○日 のようにまとめて選べます）",
                key=f"template_paste_dates_{date_str}_{template_id}",
                default_date=paste_default,
            )
            paste_mode = st.radio("貼り付け方法", ["既存の内容に追加", "既存の内容を置き換え"],
                                  key=f"template_paste_mode_{date_str}_{template_id}")
            st.caption("置き換えを選ぶと、選んだ貼り付け先の内容だけが置き換わります。もう一方は残ります。")
            if paste_mode == "既存の内容を置き換え" and len(target_dates) > 1:
                st.warning(f"選んだ{len(target_dates)}日分すべての「{destination[2:]}」が置き換わります。")
            if st.button("📋 テンプレートを貼り付け", type="primary", use_container_width=True,
                         disabled=(not entries or not target_dates),
                         key=f"template_paste_button_{date_str}_{template_id}"):
                key = "planned" if destination == "📅 予定" else "actual"
                apply_schedule_entries_to_dates(
                    entries, target_dates, key, replace=(paste_mode == "既存の内容を置き換え"))
                play_click_sound(delay=0)
                st.session_state.schedule_notice = (
                    f"✅ 『{template['name']}』を {target_dates[0]} 〜 {target_dates[-1]}"
                    f"（{len(target_dates)}日分）の{destination[2:]}に貼り付けました！"
                )
                save_progress()
                st.rerun()

        # 削除はフォーム送信にまとめず、通常のボタンで実行する。
        # フォーム内チェックボックスの状態や別フォームとの干渉で削除できないケースを避ける。
        delete_confirm_key = f"template_delete_confirm_{template_id}"
        delete_confirm = st.checkbox(
            f"『{template['name']}』を削除することを確認",
            key=delete_confirm_key,
        )
        if st.button(
            "🗑️ 選択中のテンプレートを削除",
            key=f"template_delete_button_{template_id}",
            disabled=not delete_confirm,
        ):
            # 選択中のIDを再確認してから削除する。
            current_templates = st.session_state.get("schedule_templates", [])
            delete_index = next(
                (i for i, item in enumerate(current_templates)
                 if str(item.get("id", i)) == str(template_id)),
                None,
            )
            if delete_index is not None:
                removed_name = current_templates.pop(delete_index).get("name", "テンプレート")
                st.session_state.schedule_templates = current_templates
                save_progress()
                st.success(f"『{removed_name}』を削除しました。")
                st.rerun()
            else:
                st.warning("削除するテンプレートが見つかりません。画面を更新してください。")


def valid_template_time_range(start: str, end: str) -> bool:
    """時刻がHH:MM形式かつ同一日内で開始＜終了か検証する。"""
    try:
        a = datetime.strptime(start, "%H:%M")
        b = datetime.strptime(end, "%H:%M")
        return a < b and len(start) == 5 and len(end) == 5
    except (ValueError, TypeError):
        return False


# =====================================================
# 🗓️ 複数日まとめて操作（カレンダー期間選択・一括追加・クイック追加ページ）
# =====================================================
SCHEDULE_MAX_RANGE_DAYS = 62  # 一度にまとめて選べる最大日数
WEEKDAY_LABELS = ["月", "火", "水", "木", "金", "土", "日"]


def schedule_date_range_picker(label: str, key: str, default_date) -> list:
    """
    カレンダーで「○日〜○日」の期間（1日だけでもOK）を選び、日付文字列（YYYY/MM/DD）のリストで返す。
    曜日で絞り込むこともできる（空なら全部の曜日）。
    """
    picked = st.date_input(
        label, value=(default_date, default_date), key=f"{key}_range",
        help="カレンダーで最初の日と最後の日をクリックすると期間を選べます。1日だけならその日を1回クリック。",
    )
    if isinstance(picked, (tuple, list)):
        if len(picked) == 0:
            return []
        start_d = picked[0]
        end_d = picked[1] if len(picked) >= 2 else picked[0]
    else:
        start_d = end_d = picked
    if end_d < start_d:
        start_d, end_d = end_d, start_d

    weekdays = st.multiselect(
        "曜日を絞る（選ばなければ全部の曜日）", WEEKDAY_LABELS, key=f"{key}_weekdays",
    )
    allowed = {WEEKDAY_LABELS.index(w) for w in weekdays}

    total_days = (end_d - start_d).days + 1
    if total_days > SCHEDULE_MAX_RANGE_DAYS:
        st.warning(f"⚠️ 一度に選べるのは最大{SCHEDULE_MAX_RANGE_DAYS}日です。最初の{SCHEDULE_MAX_RANGE_DAYS}日分だけが対象になります。")
        total_days = SCHEDULE_MAX_RANGE_DAYS

    date_strs = []
    for offset in range(total_days):
        d = start_d + timedelta(days=offset)
        if allowed and d.weekday() not in allowed:
            continue
        date_strs.append(d.strftime("%Y/%m/%d"))

    if not isinstance(picked, (tuple, list)) or len(picked) < 2:
        st.caption("📆 1日だけ選択中です（期間にしたいときは、最後の日もクリックしてね）")
    if date_strs:
        st.caption(f"📆 {date_strs[0]} 〜 {date_strs[-1]}（{len(date_strs)}日分が対象）")
    else:
        st.caption("📆 対象になる日がありません。日付か曜日を見直してください。")
    return date_strs


def apply_schedule_entries_to_dates(entries: list, date_strs: list, kind: str, replace: bool = False):
    """
    entries（予定／記録のリスト）を、指定した複数の日の「planned」または「actual」にコピーする。
    各日に独立したコピーを入れるので、あとから1日ずつ編集しても他の日に影響しない。
    """
    for ds in date_strs:
        day = st.session_state.daily_schedule.setdefault(ds, {"planned": [], "actual": []})
        day.setdefault("planned", [])
        day.setdefault("actual", [])
        copied = []
        for e in entries:
            c = copy.deepcopy(e)
            c.pop("schedule_reward_claimed", None)  # 貼り付け先では未達成の予定として扱う
            copied.append(c)
        if replace:
            day[kind] = copied
        else:
            day[kind].extend(copied)
        day[kind].sort(key=lambda e: e["start"])


def render_schedule_bulk_delete(date_str: str):
    """その日、または選んだ期間の予定／記録をまとめて削除する（削除前に必ず確認する）。"""
    pending = st.session_state.get("bulk_delete_pending")
    with st.expander("🗑️ 予定・記録をまとめて削除", expanded=bool(pending)):
        st.caption("その日だけ、または○日〜○日の期間の予定・記録を一括で削除できます。削除前に確認画面が出ます。")

        # ---- 確認画面（削除ボタンを押したあと） ----
        if pending:
            kind_text = {"planned": "予定", "actual": "記録", "both": "予定と記録の両方"}[pending["target"]]
            with st.container(border=True):
                st.error(
                    f"⚠️ 本当に削除しますか？\n\n"
                    f"📆 {pending['dates'][0]} 〜 {pending['dates'][-1]}（{len(pending['dates'])}日分）\n\n"
                    f"🗑️ 対象：{kind_text}（合計 {pending['count']} 件）\n\n"
                    f"削除したものは元に戻せません。"
                )
                confirm_col, cancel_col = st.columns(2)
                with confirm_col:
                    if st.button("🗑️ はい、削除します", type="primary", use_container_width=True,
                                 key=f"bulk_delete_confirm_{date_str}"):
                        kinds = ["planned", "actual"] if pending["target"] == "both" else [pending["target"]]
                        removed = 0
                        for ds in pending["dates"]:
                            day = st.session_state.daily_schedule.get(ds)
                            if not day:
                                continue
                            for k in kinds:
                                removed += len(day.get(k, []))
                                day[k] = []
                        st.session_state.bulk_delete_pending = None
                        st.session_state.schedule_edit_target = None
                        st.session_state.schedule_delete_target = None
                        st.session_state.schedule_form_open = None
                        play_click_sound(delay=0)
                        save_progress()
                        st.session_state.schedule_notice = (
                            f"🗑️ {pending['dates'][0]} 〜 {pending['dates'][-1]}の{kind_text}を {removed} 件削除しました。"
                        )
                        st.rerun()
                with cancel_col:
                    if st.button("やめる", use_container_width=True, key=f"bulk_delete_cancel_{date_str}"):
                        st.session_state.bulk_delete_pending = None
                        st.rerun()
            return

        # ---- 削除する範囲の選択 ----
        target_label = st.radio(
            "削除するもの", ["📅 予定", "✅ 記録", "📅✅ 予定と記録の両方"],
            key=f"bulk_delete_target_{date_str}",
        )
        target = {"📅 予定": "planned", "✅ 記録": "actual", "📅✅ 予定と記録の両方": "both"}[target_label]
        try:
            default_d = datetime.strptime(date_str, "%Y/%m/%d").date()
        except ValueError:
            default_d = get_now_jst().date()
        target_dates = schedule_date_range_picker(
            "削除する日付（その日だけ／カレンダーで期間を選べます）",
            key=f"bulk_delete_dates_{date_str}", default_date=default_d,
        )
        kinds = ["planned", "actual"] if target == "both" else [target]
        count = sum(
            len(st.session_state.daily_schedule.get(ds, {}).get(k, []))
            for ds in target_dates for k in kinds
        )
        if target_dates:
            if count:
                st.info(f"🗑️ 削除される項目：{count} 件（{len(target_dates)}日分の中）")
            else:
                st.caption("選んだ範囲には、削除できる予定・記録がありません。")
        if st.button("🗑️ 削除の確認へ進む", use_container_width=True,
                     disabled=(not target_dates or count == 0),
                     key=f"bulk_delete_request_{date_str}"):
            st.session_state.bulk_delete_pending = {
                "dates": target_dates, "target": target, "count": count,
            }
            st.rerun()


def render_quick_add_page():
    """⚡ クイック追加：日付（複数日OK）・時間・内容を決めて、予定／記録をまとめて追加するページ。"""
    st.title("⚡ クイック追加")
    st.caption("日付（○日〜○日のように複数日もOK）・時間・内容を決めて、予定や記録をまとめて追加できます。")

    today_dt = get_now_jst().date()
    default_date = st.session_state.get("quick_add_default_date") or today_dt

    # 追加後に内容欄を空にする（ウィジェット作成前にだけ消せる）
    if st.session_state.pop("quick_add_reset", False):
        st.session_state.pop("qa_label", None)
    notice = st.session_state.pop("quick_add_notice", None)
    if notice:
        st.success(notice)

    kind_label_pick = st.radio("追加するもの", ["📅 予定", "✅ 記録"], horizontal=True, key="qa_kind")
    kind = "planned" if kind_label_pick == "📅 予定" else "actual"
    kind_word = "予定" if kind == "planned" else "記録"

    with st.container(border=True):
        st.markdown("#### 1️⃣ 日付をえらぶ")
        date_strs = schedule_date_range_picker(
            "追加する日付（カレンダーで期間を選べます）",
            key=f"qa_dates_{default_date.strftime('%Y%m%d') if hasattr(default_date, 'strftime') else default_date}",
            default_date=default_date,
        )

    with st.container(border=True):
        st.markdown("#### 2️⃣ 時間をえらぶ")
        col_start, col_end = st.columns(2)
        with col_start:
            start_time = schedule_time_selectbox("開始時刻", "09:00", key="qa_start")
        with col_end:
            end_time = schedule_time_selectbox("終了時刻", "10:00", key="qa_end")

    with st.container(border=True):
        st.markdown(f"#### 3️⃣ {kind_word}の内容")
        label_text = st.text_input("内容（なんでもOK）", key="qa_label", placeholder="例：数学の宿題、読書、休憩 など")
        color_options = list(SCHEDULE_COLORS.keys())
        color_name = st.selectbox(
            "色（10色から選択）", options=color_options,
            index=3 if kind == "planned" else 4, key=f"qa_color_{kind}",
        )

    if date_strs and label_text.strip():
        st.info(f"{kind_label_pick}：{start_time}〜{end_time}『{label_text.strip()}』を {len(date_strs)}日分に追加します")

    if st.button("➕ まとめて追加する", type="primary", use_container_width=True,
                 key="qa_add_button", disabled=not date_strs):
        if not label_text.strip():
            st.error("⚠️ 内容を入力してください。")
        elif time_to_minutes(start_time) >= time_to_minutes(end_time):
            st.error("⚠️ 終了時刻は開始時刻より後にしてください。")
        else:
            play_click_sound(delay=0)
            new_entry = {
                "start": start_time,
                "end": end_time,
                "label": label_text.strip(),
                "color": SCHEDULE_COLORS[color_name],
            }
            apply_schedule_entries_to_dates([new_entry], date_strs, kind, replace=False)
            save_progress()
            st.session_state.quick_add_notice = (
                f"✅ {date_strs[0]} 〜 {date_strs[-1]}（{len(date_strs)}日分）の{kind_word}に"
                f"『{new_entry['label']}』{start_time}〜{end_time} を追加しました！"
            )
            st.session_state.quick_add_reset = True
            st.rerun()

    st.write("---")
    nav_a, nav_b = st.columns(2)
    with nav_a:
        if st.button("↩️ 一日のスケジュールへ", use_container_width=True, key="qa_back_schedule"):
            st.session_state.page = "schedule_page"
            st.rerun()
    with nav_b:
        if st.button("📅 カレンダーで確認する", use_container_width=True, key="qa_go_calendar",
                     disabled=not date_strs):
            st.session_state.selected_calendar_date = date_strs[0]
            st.session_state.page = "calendar_page"
            st.rerun()



def single_task_is_due(task: dict, date_str: str) -> bool:
    """指定日に反復タスクを表示するか判定する。"""
    if not task.get("repeat_enabled"):
        return False
    if date_str in task.get("completed_dates", []):
        return False
    try:
        target_date = datetime.strptime(date_str, "%Y/%m/%d").date()
        start = datetime.strptime(task.get("repeat_start", date_str), "%Y/%m/%d").date()
        if target_date < start:
            return False
        if task.get("repeat_mode") == "range":
            end_text = task.get("repeat_end")
            if end_text and target_date > datetime.strptime(end_text, "%Y/%m/%d").date():
                return False
            return True
        return target_date.weekday() == int(task.get("repeat_weekday", 0))
    except (ValueError, TypeError):
        return False


def render_single_task_reminders(date_str: str):
    """該当日の反復タスクを個別ボタンで表示する。達成後はその日だけ非表示。"""
    due = [task for task in st.session_state.get("single_tasks", [])
           if single_task_is_due(task, date_str)]
    if not due:
        return
    st.markdown("### 🔔 今日のリマインド")
    for task in due:
        with st.container(border=True):
            st.write(f"🌟 **{task.get('title', 'タスク')}の日です！**")
            if st.button("できたら押してね！（+1 IPPOポイント）",
                         key=f"repeat_task_done_{task.get('id')}_{date_str}",
                         use_container_width=True):
                if complete_single_task(task.get("id"), completion_date=date_str):
                    st.session_state.single_task_notice = (
                        f"🎉『{task.get('title', 'タスク')}』達成！1 IPPOポイントゲット！")
                    save_progress()
                    st.rerun()


def render_schedule_and_events(date_str: str, editable: bool, clipboard_at_bottom: bool = False):
    """
    指定した日の「予定／記録」帯グラフと、隣にIPPOイベントログを表示する。
    editable=True の場合は、予定・記録の追加に加えて既存項目の編集・削除ができる。
    """
    day_schedule = st.session_state.daily_schedule.setdefault(date_str, {"planned": [], "actual": []})

    render_single_task_reminders(date_str)

    if editable:
        if not clipboard_at_bottom:
            render_schedule_clipboard(date_str)
        schedule_notice = st.session_state.pop("schedule_notice", None)
        if schedule_notice:
            st.success(schedule_notice)
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
                        edit_start = schedule_time_selectbox(
                            "開始時刻", entry["start"],
                            key=f"edit_sched_start_{date_str}_{edit_kind}_{edit_index}")
                    with edit_col_end:
                        edit_end = schedule_time_selectbox(
                            "終了時刻", entry["end"],
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

                    # 予定の1コマを、そのまま「記録」にもコピーする
                    if edit_kind == "planned":
                        if st.button("✅ 予定通りに出来た（+1 IPPOポイント）", use_container_width=True,
                                     key=f"as_planned_{date_str}_{edit_index}"):
                            actual_entries = day_schedule.setdefault("actual", [])
                            copied_entry = {
                                "start": entry["start"], "end": entry["end"],
                                "label": entry.get("label", ""), "color": entry.get("color", "#4CAF50"),
                            }
                            already = any(
                                a.get("start") == copied_entry["start"] and a.get("end") == copied_entry["end"]
                                and a.get("label", "") == copied_entry["label"]
                                for a in actual_entries
                            )
                            if entry.get("schedule_reward_claimed", False):
                                st.session_state.schedule_notice = "ℹ️ この予定は達成済みです。"
                            else:
                                if not already:
                                    actual_entries.append(copied_entry)
                                    actual_entries.sort(key=lambda e: e["start"])
                                entry["schedule_reward_claimed"] = True
                                st.session_state.ippo_points = int(st.session_state.get("ippo_points", 0)) + 1
                                st.session_state.schedule_notice = (
                                    f"🎉 『{copied_entry['label']}』を達成！ 1 IPPOポイントを獲得しました！"
                                )
                            st.session_state.schedule_edit_target = None
                            save_progress()
                            st.rerun()
                        st.caption("予定はそのまま残り、実際の記録にも同じコマが入ります。")

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
                                    "start": edit_start,
                                    "end": edit_end,
                                    "label": edit_label.strip(),
                                    "color": edit_color,
                                })
                                st.session_state.schedule_edit_target = None
                                save_progress()
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
                            save_progress()
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
                    start_time = schedule_time_selectbox(
                        "開始時刻", "09:00",
                        key=f"sched_start_{date_str}_{form_kind}")
                with col_end:
                    end_time = schedule_time_selectbox(
                        "終了時刻", "10:00",
                        key=f"sched_end_{date_str}_{form_kind}")
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
                            "start": start_time,
                            "end": end_time,
                            "label": label_text.strip(),
                            "color": color_pick,
                        }
                        day_schedule[form_kind].append(new_entry)
                        st.session_state.schedule_form_open = None
                        save_progress()
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

    if editable and clipboard_at_bottom:
        st.write("---")
        render_schedule_clipboard(date_str)

    if editable:
        render_schedule_templates(date_str)
        render_schedule_bulk_delete(date_str)



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
_aqua_point_sound_b64 = load_sound_base64(AQUA_POINT_SOUND_PATH)
_aqua_gacha_low_sound_b64 = load_sound_base64(AQUA_GACHA_LOW_SOUND_PATH)
_aqua_gacha_three_sound_b64 = load_sound_base64(AQUA_GACHA_THREE_SOUND_PATH)
_aqua_feed_sound_b64 = load_sound_base64(AQUA_FEED_SOUND_PATH)
_candy_craft_sound_b64 = load_sound_base64(CANDY_CRAFT_SOUND_PATH)


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


def play_aqua_point_sound(delay: float = 0):
    """IPPOポイント獲得時の効果音。"""
    if _aqua_point_sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{_aqua_point_sound_b64}" type="audio/mp3"></audio>'
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_aqua_feed_sound(delay: float = 0):
    """魚に餌を渡したときの効果音。"""
    if _aqua_feed_sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{_aqua_feed_sound_b64}" type="audio/mp3"></audio>'
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_candy_craft_sound(delay: float = 0):
    """お菓子屋さんで「この材料でスイーツを作る」を押したときの効果音。"""
    if _candy_craft_sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{_candy_craft_sound_b64}" type="audio/mp3"></audio>'
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_candy_gacha_sound(delay: float = 0):
    """お菓子ガチャを回したときの効果音（ペタッ.mp3を1回だけ）。"""
    if _aqua_gacha_low_sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{_aqua_gacha_low_sound_b64}" type="audio/mp3"></audio>'
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_aqua_gacha_sound(stars: int, delay: float = 0):
    """ガチャの☆数に応じた効果音。☆1〜2=ペタッ、☆3=きらーん1。"""
    sound_b64 = _aqua_gacha_low_sound_b64 if stars <= 2 else _aqua_gacha_three_sound_b64
    if sound_b64 is None:
        return
    sound_html = f'<audio autoplay="true" style="display:none;"><source src="data:audio/mp3;base64,{sound_b64}" type="audio/mp3"></audio>'
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
if "jar_name" not in st.session_state:
    st.session_state.jar_name = ""
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
if "schedule_templates" not in st.session_state or st.session_state.schedule_templates is None:
    st.session_state.schedule_templates = []
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
if "ippo_points" not in st.session_state:
    st.session_state.ippo_points = 0
if "aqua_reward_queue" not in st.session_state:
    st.session_state.aqua_reward_queue = []
if "aqua_fish" not in st.session_state:
    st.session_state.aqua_fish = []
if "aqua_decorations" not in st.session_state:
    st.session_state.aqua_decorations = []
if "aqua_food_inventory" not in st.session_state:
    st.session_state.aqua_food_inventory = {"normal": 0, "premium": 0, "bundle": 0, "grand_bundle": 0}
if "aqua_feed_log" not in st.session_state:
    st.session_state.aqua_feed_log = []
if "aqua_goal_log" not in st.session_state:
    st.session_state.aqua_goal_log = []
if "aqua_tank_history" not in st.session_state:
    st.session_state.aqua_tank_history = None
if "dino_owned" not in st.session_state:
    st.session_state.dino_owned = []
if "dino_partner" not in st.session_state:
    st.session_state.dino_partner = None
if "dino_food" not in st.session_state:
    st.session_state.dino_food = {"meat": 0, "feast": 0}
if "dino_special_dice" not in st.session_state:
    st.session_state.dino_special_dice = 0
if "dino_race" not in st.session_state:
    st.session_state.dino_race = {}
if "dino_locked_course" not in st.session_state:
    st.session_state.dino_locked_course = None
if "dino_stat_items" not in st.session_state:
    st.session_state.dino_stat_items = {}
if "dino_event_log" not in st.session_state:
    st.session_state.dino_event_log = []
if "dino_unlocked_courses" not in st.session_state:
    st.session_state.dino_unlocked_courses = []
if "single_tasks" not in st.session_state:
    st.session_state.single_tasks = []
if "single_task_completion_log" not in st.session_state:
    st.session_state.single_task_completion_log = []

# お菓子屋さんの新規データ初期化（既存のお菓子瓶・他ステージのデータには触れない）
for _shop_key in (
    "candy_coins", "candy_shop_materials", "candy_shop_jar_candy_stock",
    "candy_shop_unlocked_recipes", "candy_shop_recipe_book_owned", "candy_shop_products", "candy_shop_displayed",
    "candy_shop_discovered", "candy_shop_shelf_capacity", "candy_shop_level",
    "candy_shop_exp", "candy_shop_jar_order", "candy_shop_jar_order_log", "candy_shop_customer_notes",
    "candy_shop_invite_tickets", "candy_shop_invited_customers",
    "candy_gacha_owned",
):
    if _shop_key not in st.session_state:
        _default = PERSISTENT_DEFAULTS[_shop_key]
        st.session_state[_shop_key] = copy.deepcopy(_default)

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
    "candy_page", "candy_collection_page", "aquarium_page", "dino_page", "schedule_page",
    "future_schedule_page", "schedule_print_page", "quick_add_page"
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

        # ===== 📝 単発のタスク（完了すると3ポイント） =====
        with st.container(border=True):
            st.markdown("### 📝 単発のタスク")
            st.caption(f"1回きりのタスクを登録できます。完了を押すと **{SINGLE_TASK_POINTS} IPPOポイント** もらえます。")
            single_notice = st.session_state.pop("single_task_notice", None)
            if single_notice:
                play_aqua_point_sound(delay=0)
                st.success(single_notice)

            with st.form("single_task_form", clear_on_submit=True):
                new_single_title = st.text_input("単発のタスク", placeholder="例：メールの返信、洗濯物をたたむ、薬局に行く")
                if st.form_submit_button("➕ タスクを追加"):
                    if add_single_task(new_single_title):
                        save_progress()
                        st.rerun()
                    else:
                        st.error("⚠️ タスクの内容を入力してください。")

            if refresh_single_task_status():
                save_progress()
            open_tasks = [t for t in st.session_state.single_tasks if not t.get("completed")]
            done_tasks = [t for t in st.session_state.single_tasks if t.get("completed")]
            if not open_tasks:
                st.caption("まだ未完了のタスクはありません。")
            for task in open_tasks:
                task_col, done_col, del_col = st.columns([5, 3, 1])
                with task_col:
                    st.write(f"📌 {task['title']}")

                    # ✏️ タスク名の編集
                    if st.session_state.get("editing_single_task_id") == task["id"]:
                        edited_title = st.text_input(
                            "タスク名を変更",
                            value=task["title"],
                            key=f"single_task_edit_input_{task['id']}"
                        )

                        edit_col1, edit_col2 = st.columns(2)

                        with edit_col1:
                            if st.button(
                                "💾 保存",
                                key=f"single_task_edit_save_{task['id']}",
                                use_container_width=True
                            ):
                                if edited_title.strip():
                                    task["title"] = edited_title.strip()
                                    st.session_state.editing_single_task_id = None
                                    save_progress()
                                    st.rerun()
                                else:
                                    st.error("タスク名を入力してください。")

                        with edit_col2:
                            if st.button(
                                "キャンセル",
                                key=f"single_task_edit_cancel_{task['id']}"
                            ):
                                st.session_state.editing_single_task_id = None
                                st.rerun()

                    else:
                        if st.button(
                            "✏️ 名前を編集",
                            key=f"single_task_edit_open_{task['id']}",
                            use_container_width=True
                        ):
                            st.session_state.editing_single_task_id = task["id"]
                            st.rerun()

                    with st.expander("🔁 このタスクを反復にする／設定する"):
                        mode = st.radio(
                            "繰り返し方",
                            options=["range", "weekly"],
                            format_func=lambda x: "開始日から終了日まで毎日" if x == "range" else "毎週、指定した曜日（7日ごと）",
                            index=0 if task.get("repeat_mode", "range") == "range" else 1,
                            key=f"single_repeat_mode_{task['id']}",
                        )
                        default_start = task.get("repeat_start")
                        try:
                            start_value = datetime.strptime(default_start, "%Y/%m/%d").date() if default_start else get_now_jst().date()
                        except ValueError:
                            start_value = get_now_jst().date()
                        repeat_start = st.date_input("開始日", value=start_value, key=f"single_repeat_start_{task['id']}")
                        repeat_end = None
                        repeat_weekday = task.get("repeat_weekday", 0)
                        if mode == "range":
                            try:
                                end_value = datetime.strptime(task.get("repeat_end"), "%Y/%m/%d").date() if task.get("repeat_end") else repeat_start
                            except ValueError:
                                end_value = repeat_start
                            repeat_end = st.date_input("終了日", value=max(repeat_start, end_value),
                                                       min_value=repeat_start, key=f"single_repeat_end_{task['id']}")
                        else:
                            weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
                            repeat_weekday = st.selectbox("毎週何曜日？", range(7),
                                index=int(task.get("repeat_weekday", 0)),
                                format_func=lambda x: weekdays[x], key=f"single_repeat_weekday_{task['id']}")
                        if st.button("🔁 反復設定を保存", key=f"single_repeat_save_{task['id']}",
                                     use_container_width=True):
                            if mode == "range" and repeat_end < repeat_start:
                                st.error("終了日は開始日以降にしてください。")
                            else:
                                task["repeat_enabled"] = True
                                task["repeat_mode"] = mode
                                task["repeat_start"] = repeat_start.strftime("%Y/%m/%d")
                                task["repeat_end"] = repeat_end.strftime("%Y/%m/%d") if repeat_end else None
                                task["repeat_weekday"] = int(repeat_weekday)
                                task["completed_dates"] = task.get("completed_dates", [])
                                save_progress()
                                st.rerun()
                        if task.get("repeat_enabled") and st.button("反復を解除する", key=f"single_repeat_off_{task['id']}"):
                            task["repeat_enabled"] = False
                            task["completed"] = False
                            save_progress()
                            st.rerun()
                with done_col:
                    if st.button(f"✅ 完了！ +{SINGLE_TASK_POINTS} IPPOポイント", key=f"single_done_{task['id']}", use_container_width=True):
                        if complete_single_task(task["id"]):
                            st.session_state.single_task_notice = f"🎉 『{task['title']}』を完了！ {SINGLE_TASK_POINTS} IPPOポイントゲット！"
                            save_progress()
                            st.rerun()
                with del_col:
                    if st.button("🗑️", key=f"single_del_{task['id']}", use_container_width=True):
                        st.session_state.single_tasks = [t for t in st.session_state.single_tasks if t["id"] != task["id"]]
                        save_progress()
                        st.rerun()
            if done_tasks and st.checkbox(f"完了したタスクを見る（{len(done_tasks)}件）", key="show_done_single_tasks"):
                for task in reversed(done_tasks[-30:]):
                    repeat_info = ""
                    if task.get("repeat_enabled"):
                        repeat_info = f"　🔁 {len(task.get('completed_dates', []))}回達成"
                    st.write(f"✅ {task['title']}　（{task.get('completed_at', '')}）{repeat_info}")

        st.write("---")
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
                                play_achieve_sound(delay=0)
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
                        # その日に有効な反復リマインドがあれば、カレンダーにベルを表示
                        reminder_tasks = [
                            task for task in st.session_state.get("single_tasks", [])
                            if single_task_is_due(task, cell_date_str)
                        ]
                        has_reminder = bool(reminder_tasks)
                        markers = ("🎯" if has_deadline else "") + ("📝" if has_note else "") + ("🔔" if has_reminder else "")

                        label_line2 = " ".join(part for part in [cell_sticker_preview, markers] if part)
                        cell_label = f"{day_label} {label_line2}" if label_line2 else day_label

                        is_selected = (cell_date_str == st.session_state.selected_calendar_date)
                        if st.button(cell_label, key=f"cal_day_{cell_date_str}", use_container_width=True,
                                     type="primary" if is_selected else "secondary"):
                            play_click_sound(delay=0)
                            st.session_state.selected_calendar_date = cell_date_str
                            st.session_state.schedule_form_open = None
                            st.session_state.schedule_edit_target = None
                            st.session_state.schedule_delete_target = None
                            st.session_state.schedule_paste_target = None

        st.write("---")
        selected_date_str = st.session_state.selected_calendar_date
        selected_date_display = datetime.strptime(selected_date_str, "%Y/%m/%d").strftime("%Y年%m月%d日")
        st.markdown(f"### 🔍 {selected_date_display} の記録")

        selected_reminders = [
            task for task in st.session_state.get("single_tasks", [])
            if single_task_is_due(task, selected_date_str)
        ]
        if selected_reminders:
            st.markdown("#### 🔔 この日のリマインド")
            for reminder_task in selected_reminders:
                st.caption(f"・{reminder_task.get('title', 'タスク')}")
        else:
            st.caption("🔔 この日に設定された未完了のリマインドはありません")

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

        # 📊 選択した日のスケジュールは過去の日付も編集可能
        st.markdown("### 📊 その日のスケジュール")
        render_schedule_and_events(selected_date_str, editable=True)

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
            if st.button("🍬\n\nお菓子屋さん", use_container_width=True, key="stage_candy"):
                play_click_sound()
                st.session_state.page = "candy_page"
                st.rerun()
        with scol2:
            if st.button("🐠\n\n水族館", use_container_width=True, key="stage_aquarium"):
                play_click_sound()
                st.session_state.page = "aquarium_page"
                st.rerun()
        with scol3:
            if st.button("🦖\n\n恐竜レース", use_container_width=True, key="stage_dino"):
                play_click_sound()
                st.session_state.page = "dino_page"
                st.rerun()

    # --- 一日のスケジュール画面 ---
    elif st.session_state.page == "schedule_page":
        st.title("📊 一日のスケジュール")
        today_dt = get_now_jst().date()
        today_str = today_dt.strftime("%Y/%m/%d")
        st.caption(f"📅 今日：{today_dt.strftime('%Y年%m月%d日')}")
        nav1, nav_quick, nav2 = st.columns(3)
        with nav1:
            if st.button("📅 未来の予定を立てる", type="primary", use_container_width=True, key="go_future_schedule"):
                st.session_state.page = "future_schedule_page"
                st.rerun()
        with nav_quick:
            if st.button("⚡ クイック追加", use_container_width=True, key="go_quick_add_from_daily"):
                play_click_sound(delay=0)
                st.session_state.quick_add_default_date = today_dt
                st.session_state.page = "quick_add_page"
                st.rerun()
        with nav2:
            if st.button("🖨️ 印刷", use_container_width=True, key="go_schedule_print_from_daily"):
                st.session_state.schedule_print_dates = [today_str]
                st.session_state.schedule_print_include_planned = True
                st.session_state.schedule_print_include_actual = True
                st.session_state.page = "schedule_print_page"
                st.rerun()
        st.markdown(f"### 📅 {today_dt.strftime('%Y年%m月%d日')} のスケジュール")
        render_schedule_and_events(today_str, editable=True, clipboard_at_bottom=True)

    # --- クイック追加ページ ---
    elif st.session_state.page == "quick_add_page":
        render_quick_add_page()

    # --- 未来の予定を立てる専用ページ ---
    elif st.session_state.page == "future_schedule_page":
        st.title("📅 未来の予定を立てる")
        today_dt = get_now_jst().date()
        if "schedule_future_date" not in st.session_state:
            st.session_state.schedule_future_date = today_dt
        if st.session_state.schedule_future_date < today_dt:
            st.session_state.schedule_future_date = today_dt
        selected = st.date_input("予定を立てる日付", min_value=today_dt, key="schedule_future_date")
        date_str = selected.strftime("%Y/%m/%d")
        st.caption(f"選択した日付：{selected.strftime('%Y年%m月%d日')}")
        nav1, nav2, nav3 = st.columns(3)
        with nav1:
            if st.button("↩️ 一日のスケジュールへ", use_container_width=True, key="future_back_daily"):
                st.session_state.page = "schedule_page"
                st.rerun()
        with nav2:
            if st.button("🖨️ 印刷", use_container_width=True, key="go_schedule_print_from_future"):
                st.session_state.schedule_print_dates = [date_str]
                st.session_state.schedule_print_include_planned = True
                st.session_state.schedule_print_include_actual = True
                st.session_state.page = "schedule_print_page"
                st.rerun()
        with nav3:
            if st.button("⚡ クイック追加", use_container_width=True, key="go_quick_add_from_future"):
                play_click_sound(delay=0)
                st.session_state.quick_add_default_date = selected
                st.session_state.page = "quick_add_page"
                st.rerun()
        st.caption("予定は当日になっても保存されています")
        render_schedule_and_events(date_str, editable=True, clipboard_at_bottom=True)

    # --- 印刷設定・プレビュー専用ページ ---
    elif st.session_state.page == "schedule_print_page":
        st.title("🖨️ スケジュール印刷")
        st.caption("日付を最大7日分選び、予定・記録の帯グラフを印刷できます。空の日も書き込み用の空白グラフとして印刷されます。")
        today_dt = get_now_jst().date()
        if "schedule_print_dates" not in st.session_state or not st.session_state.schedule_print_dates:
            st.session_state.schedule_print_dates = [today_dt.strftime("%Y/%m/%d")]
        if "schedule_print_date_picker" not in st.session_state:
            st.session_state.schedule_print_date_picker = today_dt
        pc1, pc2 = st.columns([3,1])
        with pc1:
            add_date = st.date_input("追加する日付", key="schedule_print_date_picker")
        with pc2:
            st.write("")
            if st.button("➕ 日付を追加", use_container_width=True, key="print_add_date_page"):
                value=add_date.strftime("%Y/%m/%d")
                if value in st.session_state.schedule_print_dates:
                    st.warning("その日付はすでに選択されています。")
                elif len(st.session_state.schedule_print_dates) >= 7:
                    st.warning("日付は最大7日分までです。")
                else:
                    st.session_state.schedule_print_dates.append(value)
                    st.rerun()
        st.markdown("**印刷する日付**")
        for value in list(st.session_state.schedule_print_dates):
            c1,c2=st.columns([5,1])
            with c1:
                st.write("📅 " + datetime.strptime(value,"%Y/%m/%d").strftime("%Y年%m月%d日"))
            with c2:
                if st.button("削除", key=f"print_remove_page_{value}"):
                    st.session_state.schedule_print_dates.remove(value)
                    st.rerun()
        c1,c2=st.columns(2)
        with c1:
            include_planned=st.checkbox("📅 予定", key="schedule_print_include_planned")
        with c2:
            include_actual=st.checkbox("✅ 記録", key="schedule_print_include_actual")
        if not (include_planned or include_actual):
            st.info("「予定」か「記録」、または両方にチェックしてください。")
        if st.button("🔄 印刷プレビューを更新", type="primary", use_container_width=True,
                     disabled=(not st.session_state.schedule_print_dates or not (include_planned or include_actual)),
                     key="refresh_schedule_print_page"):
            st.session_state.schedule_print_preview = True
        if st.session_state.get("schedule_print_preview", True) and st.session_state.schedule_print_dates and (include_planned or include_actual):
            print_html=build_schedule_print_html(st.session_state.schedule_print_dates,include_planned,include_actual)
            st.markdown("### 印刷プレビュー（帯グラフ）")
            st.components.v1.html(print_html,height=900,scrolling=True)
        if st.button("↩️ スケジュールに戻る", use_container_width=True, key="back_from_schedule_print"):
            st.session_state.page="schedule_page"
            st.rerun()

    # --- お菓子屋さんステージ ---
    elif st.session_state.page == "candy_page":
        st.title("🍬 魔法のお菓子瓶ステージ")

        praise_words = [
            "おめでとう！！°˖✧◝(⁰▿⁰)◜✧˖° 本当に素晴らしい一歩だよ！",
            "凄い！よく頑張ったね！！(∩´狂｀)∩", "もしや君は天才…？✨",
            "グッジョブ！！頑張った自分を褒めてあげてね！💪", "最高！！その調子、その調子！♬٩(*^∀^*)۶♬",
            "素晴らしい！今日も未来が変わったね！🌟", "やったね！ハードルを乗り越えた君に拍手！👏👏",
            "最高！100点満点！！👑", "ナイス！！流石だね！！🔥", "凄ーい！山を乗り越えたあなたはもっと強くなるよ🗻！"
        ]

        with st.container():
            st.subheader("🏆 達成した目標を選ぼう！")
            st.caption(f"目標を達成するとIPPOポイントがもらえます。そのポイントで、下の「瓶の注文」からお菓子を1個ずつ瓶に入れよう！（最初のお菓子は{CANDY_COST_POINTS} IPPOポイント、追加のお菓子は{CANDY_SHOP_EXTRA_COST_POINTS} IPPOポイント）")

            if not st.session_state.target_list:
                st.warning("⚠️ まだ目標が登録されていません！「目標登録画面」で目標を作ってきてね！")
                selected_target_title = None
            else:
                target_titles = [t["title"] for t in st.session_state.target_list]
                selected_target_title = st.selectbox("🎯 どの目標を達成した？", target_titles)
                selected_target_data = next(
                    t for t in st.session_state.target_list if t["title"] == selected_target_title)

                level_options = [f"{lv}: {task} (💎{lv.split('.')[1]} IPPOポイント)" for lv, task in
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
                    st.session_state.ippo_points += chosen_candy_power
                    st.session_state.aqua_goal_log.append({
                        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
                        "target": selected_target_title, "level": chosen_lv_key, "task": chosen_task_text,
                        "points": chosen_candy_power, "source": "candy",
                    })
                    st.session_state.last_completed_task = f"【{selected_target_title} - {chosen_lv_key}】 {chosen_task_text}"
                    add_sticker_for_date(get_now_jst().strftime("%Y/%m/%d"))
                    save_progress()
                    st.info(f"💎 {chosen_candy_power} IPPOポイントゲット！ 下の「瓶の注文」でお菓子を入れよう！")
                else:
                    st.error("⚠️ 達成する目標を上のメニューから選んでください！")

            if st.session_state.praise_message:
                st.success(st.session_state.praise_message)


        # 瓶にお菓子を入れる機能は「瓶の注文」タブに統合済み。
        render_candy_shop()

    # --- お菓子一覧ページ ---
    elif st.session_state.page == "candy_collection_page":
        render_candy_collection_page()

    # --- 水族館ページ ---
    elif st.session_state.page == "aquarium_page":
        st.title("🐠 あなただけの水族館")
        normalize_aqua_fish()
        normalize_aqua_decorations()
        tank = get_aqua_tank_level()
        tank_score = get_aqua_tank_score()
        tank_history = sync_aqua_tank_history()
        next_req = next((x["required"] for x in AQUA_TANK_LEVELS if x["level"] > tank["level"]), None)
        next_text = "MAX" if next_req is None else f"あと {next_req - tank_score}ポイント"
        st.markdown(f"### 🌊 水槽 Lv.{tank['level']}『{tank['name']}』")
        st.caption(f"豪華度 {tank_score} ／ 次の水槽Lvまで：{next_text}")
        st.caption("🌊 展示水槽（魚一覧で展示・非展示を切り替えられます）")
        st.markdown(render_aquarium_tank(), unsafe_allow_html=True)

        stat1, stat2, stat3 = st.columns(3)
        with stat1:
            st.metric("💎 IPPOポイント", st.session_state.ippo_points)
        with stat2:
            st.metric("🐟 飼っている魚", len(st.session_state.aqua_fish))
        with stat3:
            st.metric("🪸 飾り", len(st.session_state.aqua_decorations))

        # --- 今までに集めた魚やアイテム ---
        with st.expander("📦 持っている飾り・餌"):
            st.caption("🐟 魚は「📖 魚図鑑」で見られるよ！")
            owned_decors = st.session_state.aqua_decorations
            food_stock = st.session_state.aqua_food_inventory

            st.markdown("#### 🪸 飾り")
            if not owned_decors:
                st.caption("まだ飾りがありません。ショップで買ってみよう！")
            else:
                shown_decors = sum(1 for d in owned_decors if d.get("display", True))
                st.write(f"合計 **{len(owned_decors)}個**（展示中 {shown_decors}個 ／ 非展示 {len(owned_decors) - shown_decors}個）")
                st.caption("チェックを入れた飾りだけが展示水槽に飾られます。")
                decor_groups = {}
                for i, d in enumerate(owned_decors):
                    decor_groups.setdefault(d.get("id", d.get("name", "飾り")), []).append(i)
                for indices in decor_groups.values():
                    first = owned_decors[indices[0]]
                    st.write(f"{first.get('emoji', '🪸')} {first.get('name', '飾り')}　**{len(indices)}個**")
                    for n, i in enumerate(indices, 1):
                        st.checkbox(
                            f"{first.get('emoji', '🪸')} {first.get('name', '飾り')}{n} を展示する",
                            value=owned_decors[i].get("display", True),
                            key=f"aqua_decor_show_{i}",
                            on_change=toggle_decoration_display,
                            args=(i,),
                        )

            st.markdown("#### 🍚 餌")
            for food_key, food in AQUA_FOOD.items():
                unit = "個" if food_key in ("bundle", "grand_bundle") else "回"
                st.write(f"{food['emoji']} {food['name']}：**{food_stock.get(food_key, 0)}{unit}**")

        st.write("---")
        st.subheader("🏆 達成した目標を選ぼう！")
        st.caption("目標を達成してIPPOポイントをゲットしよう！")
        if not st.session_state.target_list:
            st.warning("⚠️ まだ目標が登録されていません！『目標登録』で目標を作ってね！")
        else:
            aqua_target_titles = [t["title"] for t in st.session_state.target_list]
            aqua_target_title = st.selectbox("🎯 どの目標を達成した？", aqua_target_titles, key="aqua_target_select")
            aqua_target_data = next(t for t in st.session_state.target_list if t["title"] == aqua_target_title)
            aqua_level_options = [f"{lv}: {task} (💎{int(lv.replace('Lv.', '').replace('Lv', ''))} IPPOポイント)" for lv, task in aqua_target_data["tasks"].items()]
            aqua_level_str = st.selectbox("⭐ どのレベルをクリアした？", aqua_level_options, key="aqua_level_select")
            aqua_lv_key = aqua_level_str.split(":")[0]
            aqua_task_text = aqua_target_data["tasks"][aqua_lv_key]
            if st.button("➕ この1歩を達成した！", type="primary", key="aqua_achieve_button"):
                earned_ap = int(aqua_lv_key.replace("Lv.", "").replace("Lv", ""))
                st.session_state.ippo_points += earned_ap
                play_aqua_point_sound(delay=0)
                st.session_state.aqua_goal_log.append({
                    "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
                    "target": aqua_target_title,
                    "level": aqua_lv_key,
                    "task": aqua_task_text,
                    "points": earned_ap,
                })
                add_sticker_for_date(get_now_jst().strftime("%Y/%m/%d"))
                save_progress()
                st.success(f"🎉 目標達成！ {earned_ap} IPPOポイントを獲得したよ！")

        # 旧バージョンで貯めた交換券は、既存ユーザーのポイントを失わないよう移行できる。
        if st.session_state.aqua_reward_queue:
            with st.expander("🎟️ 以前のバージョンで貯めた交換券"):
                st.write(f"未交換：{len(st.session_state.aqua_reward_queue)}枚（合計 {sum(int(ticket.get('level', 1)) for ticket in st.session_state.aqua_reward_queue)} IPPOポイント）")
                if st.button("以前の交換券をまとめて交換", key="aqua_legacy_exchange"):
                    st.session_state.ippo_points += sum(int(ticket.get("level", 1)) for ticket in st.session_state.aqua_reward_queue)
                    play_aqua_point_sound(delay=0)
                    st.session_state.aqua_reward_queue = []
                    save_progress()
                    st.rerun()

        st.write("---")
        _aqua_tab = stage_tab_selector(["🛍️ ショップ", "🎰 ガチャ", "🎣 釣り", "🌱 育成", "📖 魚図鑑"], "aqua_active_tab")

        # ===== 🛍️ ショップ（魚・餌・飾りを1つにまとめた）=====
        if _aqua_tab == "🛍️ ショップ":
            st.subheader("🛍️ ショップ")
            _aqua_shop_sub = stage_tab_selector(["🐟 魚", "🍚 餌", "🪸 飾り"], "aqua_shop_sub_tab")

            if _aqua_shop_sub == "🐟 魚":
                st.markdown("#### 🐟 ショップ限定の魚")
                shop_cols = st.columns(2)
                for idx, fish_data in enumerate(AQUA_SHOP_FISH):
                    with shop_cols[idx % 2]:
                        st.markdown(f"### {fish_data['emoji']} {fish_data['name']}　{'☆' * fish_data['stars']}")
                        st.write(f"💎 {fish_data['price']} IPPOポイント")
                        if st.button("購入する", key=f"buy_shop_fish_{fish_data['id']}", use_container_width=True):
                            if st.session_state.ippo_points >= fish_data["price"]:
                                st.session_state.ippo_points -= fish_data["price"]
                                obtained, bonus = obtain_aqua_fish(fish_data)
                                sync_aqua_tank_history()
                                save_progress()
                                if obtained:
                                    st.success(f"{fish_data['emoji']} {fish_data['name']}が仲間入り！")
                                else:
                                    st.success(f"同じ種類は5匹まで！ 豪華度 +{bonus} に変換しました。")
                                st.rerun()
                            else:
                                st.warning("IPPOポイントが足りません！")

            if _aqua_shop_sub == "🍚 餌":
                st.markdown("#### 🍚 魚を育てる餌")
                food_cols = st.columns(4)
                for idx, (food_key, food) in enumerate(AQUA_FOOD.items()):
                    with food_cols[idx]:
                        st.markdown(f"### {food['emoji']} {food['name']}")
                        if food_key == "bundle":
                            st.write(f"展示水槽の魚全員に1回ずつ ／ {food['price']} IPPOポイント")
                        elif food_key == "grand_bundle":
                            st.write(f"所持している魚全員（非展示も含む）に1回ずつ ／ {food['price']} IPPOポイント")
                            st.write(f"1匹につき **+{food['feed_points']}成長ポイント**（魚が多いほどお得！）")
                        else:
                            st.write(f"{food['pack']}回分 ／ {food['price']} IPPOポイント")
                            st.write(f"1回の餌やりで **+{food['feed_points']}成長ポイント**")
                        if st.button("購入する", key=f"buy_food_{food_key}", use_container_width=True):
                            if st.session_state.ippo_points >= food["price"]:
                                st.session_state.ippo_points -= food["price"]
                                st.session_state.aqua_food_inventory[food_key] = st.session_state.aqua_food_inventory.get(food_key, 0) + food["pack"]
                                save_progress()
                                st.success(f"{food['name']}を{food['pack']}回分購入しました！")
                                st.rerun()
                            else:
                                st.warning("IPPOポイントが足りません！")
                st.write(f"通常餌：{st.session_state.aqua_food_inventory.get('normal', 0)}回　／　高級餌：{st.session_state.aqua_food_inventory.get('premium', 0)}回　／　みんなの餌の塊：{st.session_state.aqua_food_inventory.get('bundle', 0)}個　／　全体の餌の塊：{st.session_state.aqua_food_inventory.get('grand_bundle', 0)}個")

            if _aqua_shop_sub == "🪸 飾り":
                st.markdown("#### 🪸 水槽の飾り")
                decor_cols = st.columns(2)
                for idx, decor in enumerate(AQUA_DECORATIONS):
                    with decor_cols[idx % 2]:
                        st.markdown(f"### {decor['emoji']} {decor['name']}")
                        st.write(f"{decor['price']} IPPOポイント ／ 豪華度 +{decor['score']}")
                        if st.button("飾る", key=f"buy_decor_{decor['id']}", use_container_width=True):
                            if st.session_state.ippo_points >= decor["price"]:
                                st.session_state.ippo_points -= decor["price"]
                                st.session_state.aqua_decorations.append({"id": decor["id"], "name": decor["name"], "emoji": decor["emoji"], "score": decor["score"], "display": True})
                                sync_aqua_tank_history()
                                save_progress()
                                st.success(f"{decor['emoji']} {decor['name']}を水槽に置きました！")
                                st.rerun()
                            else:
                                st.warning("IPPOポイントが足りません！")

        # ===== 🎰 ガチャ（魚ガチャ・飾りガチャは別のガチャ。同じページに並べる）=====
        if _aqua_tab == "🎰 ガチャ":
            st.subheader("🎰 ガチャ")
            st.markdown("#### 🎁 ガチャ限定の魚")
            st.write("1回 **5 IPPOポイント**。ショップにはいない魚が出ます！")
            if st.button("🎁 5 IPPOポイントでガチャを回す！", type="primary", use_container_width=True, key="aqua_gacha"):
                if st.session_state.ippo_points >= 5:
                    st.session_state.ippo_points -= 5
                    got = random.choices(AQUA_GACHA_FISH, weights=[f["weight"] for f in AQUA_GACHA_FISH], k=1)[0]
                    play_aqua_gacha_sound(get_fish_stars(got), delay=0)
                    obtained, bonus = obtain_aqua_fish(got)
                    sync_aqua_tank_history()
                    save_progress()
                    if obtained:
                        st.success(f"🎉 {'☆' * got['stars']}！ {got['emoji']} {got['name']}が出ました！")
                    else:
                        st.success(f"🎉 {got['name']}は5匹所持済み！ 豪華度 +{bonus} に変換しました。")
                    st.rerun()
                else:
                    st.warning("IPPOポイントが足りません！")
            st.caption("ガチャとショップでは魚の種類を分けています。")

            st.write("---")
            st.markdown("#### 🎰 ガチャ限定の飾り")
            st.write(f"1回 **{AQUA_DECOR_GACHA_PRICE} IPPOポイント**。水槽ショップにはない飾りが出ます！")
            st.caption("☆の数がそのまま豪華度になります（☆1なら+1、☆3なら+3、☆5なら+5）。")

            # 直前のガチャ結果は、画面更新後にここで表示・効果音を鳴らす
            decor_result = st.session_state.pop("aqua_decor_gacha_result", None)
            if decor_result:
                play_aqua_gacha_sound(decor_result["stars"], delay=0)
                st.success(f"🎉 {'☆' * decor_result['stars']}！ {decor_result['emoji']} {decor_result['name']}が出ました！（豪華度 +{decor_result['stars']}）")

            if not AQUA_GACHA_DECORATIONS:
                st.info("🚧 飾りガチャは準備中です！（data/goods.json にガチャの飾りを入れると遊べます）")
            else:
                if st.button(f"🎰 {AQUA_DECOR_GACHA_PRICE} IPPOポイントで飾りガチャを回す！", type="primary",
                             use_container_width=True, key="aqua_decor_gacha"):
                    if st.session_state.ippo_points >= AQUA_DECOR_GACHA_PRICE:
                        st.session_state.ippo_points -= AQUA_DECOR_GACHA_PRICE
                        got = random.choices(AQUA_GACHA_DECORATIONS,
                                             weights=[g["weight"] for g in AQUA_GACHA_DECORATIONS], k=1)[0]
                        st.session_state.aqua_decorations.append({
                            "id": got["id"], "name": got["name"], "emoji": got["emoji"],
                            "stars": got["stars"], "score": got["stars"], "display": True,
                        })
                        st.session_state.aqua_decor_gacha_result = got
                        sync_aqua_tank_history()
                        save_progress()
                        st.rerun()
                    else:
                        st.warning("IPPOポイントが足りません！")
            st.caption("ガチャで出た飾りは、そのまま水槽に飾られます。「📦 持っている飾り・餌」で展示のON/OFFができます。")

        # ===== 🎣 釣り（準備中）=====
        if _aqua_tab == "🎣 釣り":
            st.subheader("🎣 釣り")
            st.info("🚧 釣りは準備中です！もう少し待っててね🎣✨")

        # ===== 🌱 育成（餌やり）=====
        if _aqua_tab == "🌱 育成":
            st.subheader("🌱 育成")
            # 魚の成長通知はここ（育成ページ）に表示する。
            render_aqua_growth_notifications()
            fish_list = st.session_state.aqua_fish
            if not fish_list:
                st.info("まずはショップかガチャで魚を迎えよう！")
            else:
                st.caption("餌は「🛍️ ショップ」の「🍚 餌」で買えるよ。")
                st.markdown("#### 🍚 餌やり")
                st.info("💡 展示中の魚はここから直接餌をあげられます。展示していない魚は、下の「複数の魚にまとめて餌をあげる」から選んでください。")

                normal_stock = st.session_state.aqua_food_inventory.get("normal", 0)
                premium_stock = st.session_state.aqua_food_inventory.get("premium", 0)
                bundle_stock = st.session_state.aqua_food_inventory.get("bundle", 0)
                grand_bundle_stock = st.session_state.aqua_food_inventory.get("grand_bundle", 0)

                # 展示中の魚だけ、直接餌をあげられるように表示する。
                displayed_fish_indices = [
                    i for i, fish in enumerate(fish_list)
                    if fish.get("display", True)
                ]
                if displayed_fish_indices:
                    st.markdown("##### 🐠 展示中の魚に直接餌をあげる")
                    for i in displayed_fish_indices:
                        fish = fish_list[i]
                        stars = get_fish_stars(fish)
                        size_cm = fish.get("size_mm", 10.0) / 10
                        progress = fish.get("feed_points", 0) % 5
                        st.markdown(
                            f"**{fish_display_name(fish)}**　{'☆' * stars}　"
                            f"現在 **{size_cm:.1f}cm**　（次の0.1cmまで {progress}/5pt）"
                        )
                        feed_col1, feed_col2, feed_col3 = st.columns([2, 2, 2])
                        with feed_col1:
                            if st.button(
                                f"🫧 通常餌をあげる（残り {normal_stock}）",
                                disabled=normal_stock <= 0,
                                key=f"aqua_feed_one_normal_{i}",
                                use_container_width=True,
                            ):
                                st.session_state.aqua_food_inventory["normal"] -= 1
                                give_fish_food(i, "normal")
                                sync_aqua_tank_history()
                                save_progress()
                                st.rerun()
                        with feed_col2:
                            if st.button(
                                f"✨ 高級餌をあげる（残り {premium_stock}）",
                                disabled=premium_stock <= 0,
                                key=f"aqua_feed_one_premium_{i}",
                                use_container_width=True,
                            ):
                                st.session_state.aqua_food_inventory["premium"] -= 1
                                give_fish_food(i, "premium")
                                sync_aqua_tank_history()
                                save_progress()
                                st.rerun()
                        with feed_col3:
                            st.write(f"成長ポイント：**{fish.get('feed_points', 0) % 5}/5**")
                else:
                    st.caption("現在、展示中の魚はいません。下のまとめて餌やりから魚を選べます。")

                st.markdown("##### 👥 複数の魚にまとめて餌をあげる")
                st.caption("展示していない魚も、ここから選んで餌をあげられます。展示中の魚もまとめて選択できます。")
                fish_indices = st.multiselect(
                    "① 餌をあげる魚を選ぶ",
                    options=list(range(len(fish_list))),
                    format_func=lambda i: f"{fish_list[i]['emoji']} {fish_display_name(fish_list[i])}（{'☆' * get_fish_stars(fish_list[i])}・{fish_list[i].get('size_mm', 10.0) / 10:.1f}cm・{'展示中' if fish_list[i].get('display', True) else '非展示'}）",
                    key="aqua_feed_fish_choices",
                )
                st.caption("② 選んだ魚1匹あたりに、何個あげるか指定します。")
                col_n, col_p = st.columns(2)
                with col_n:
                    normal_count = st.number_input(
                        "🫧 通常餌（1匹あたり）",
                        min_value=0,
                        max_value=normal_stock,
                        value=0,
                        step=1,
                        key="aqua_feed_normal_count",
                    )
                with col_p:
                    premium_count = st.number_input(
                        "✨ 高級餌（1匹あたり）",
                        min_value=0,
                        max_value=premium_stock,
                        value=0,
                        step=1,
                        key="aqua_feed_premium_count",
                    )
                needed_normal = len(fish_indices) * normal_count
                needed_premium = len(fish_indices) * premium_count
                if fish_indices:
                    st.write(f"③ 必要な餌：通常 **{needed_normal}個** ／ 高級 **{needed_premium}個**")
                else:
                    st.caption("魚を選ぶと必要な餌の数が表示されます。")
                if st.button(
                    "🐟 選んだ魚にまとめて餌をあげる",
                    type="primary",
                    disabled=not fish_indices or (normal_count + premium_count == 0),
                    key="aqua_feed_selected",
                    use_container_width=True,
                ):
                    if needed_normal > normal_stock or needed_premium > premium_stock:
                        st.warning("選んだ魚の数に対して餌が足りません。数を調整してね！")
                    else:
                        st.session_state.aqua_food_inventory["normal"] -= needed_normal
                        st.session_state.aqua_food_inventory["premium"] -= needed_premium
                        for i in fish_indices:
                            if normal_count:
                                give_fish_food(i, "normal", normal_count, play_sound=False)
                            if premium_count:
                                give_fish_food(i, "premium", premium_count, play_sound=False)
                        play_aqua_feed_sound(delay=0)
                        sync_aqua_tank_history()
                        save_progress()
                        st.success(f"🐠 {len(fish_indices)}匹に餌をあげました！")
                        st.rerun()

                st.write("---")
                st.markdown("#### 🍙 みんなの餌の塊")
                displayed_indices = [i for i, fish in enumerate(fish_list) if fish.get("display", True)]
                st.caption("展示水槽にいる魚だけに、1匹あたり+3成長ポイント。")
                st.write(f"展示中：{len(displayed_indices)}匹 ／ 持っている餌の塊：**{bundle_stock}個**")
                if st.button("🍙 展示水槽の魚全員にあげる",
                             disabled=bundle_stock == 0 or not displayed_indices,
                             key="aqua_feed_bundle", use_container_width=True):
                    if st.session_state.aqua_food_inventory.get("bundle", 0) > 0 and displayed_indices:
                        st.session_state.aqua_food_inventory["bundle"] -= 1
                        for i in displayed_indices:
                            give_fish_food(i, "bundle", play_sound=False)
                        play_aqua_feed_sound(delay=0)
                        sync_aqua_tank_history()
                        save_progress()
                        st.success(f"🎉 展示中の{len(displayed_indices)}匹に餌をあげました！")
                        st.rerun()

                st.markdown("#### 🎁 全体の餌の塊")
                st.caption("非展示の魚も含め、所持しているすべての魚に1匹あたり+3成長ポイント。")
                st.write(f"持っている全体の餌の塊：**{grand_bundle_stock}個**")
                if st.button("🎁 所持している魚全員にあげる",
                             disabled=grand_bundle_stock == 0,
                             key="aqua_feed_grand_bundle", use_container_width=True):
                    if st.session_state.aqua_food_inventory.get("grand_bundle", 0) > 0:
                        st.session_state.aqua_food_inventory["grand_bundle"] -= 1
                        for i in range(len(fish_list)):
                            give_fish_food(i, "grand_bundle", play_sound=False)
                        play_aqua_feed_sound(delay=0)
                        sync_aqua_tank_history()
                        save_progress()
                        st.success(f"🎉 所持している{len(fish_list)}匹全員に餌をあげました！")
                        st.rerun()

        # ===== 📖 魚図鑑（今までにGETした魚。名前・展示の設定もここ）=====
        if _aqua_tab == "📖 魚図鑑":
            st.subheader("📖 魚図鑑")
            fish_list = st.session_state.aqua_fish
            species_groups = {}
            for i, fish in enumerate(fish_list):
                species_groups.setdefault(fish.get("id", fish.get("name", "魚")), []).append(i)
            known_ids = {sp["id"] for sp in ALL_FISH}
            met_count = sum(1 for sid in species_groups if sid in known_ids)
            shown_fish = sum(1 for f in fish_list if f.get("display", True))
            st.write(f"出会った魚：**{met_count} / {len(ALL_FISH)} 種類**　／　飼っている魚：**{len(fish_list)}匹**（展示中 {shown_fish}匹 ／ 非展示 {len(fish_list) - shown_fish}匹）")
            st.caption("魚の種類を開くと、1匹ずつ名前・展示設定を変更できます。まだ出会っていない魚は「？？？」で表示されます。")

            def _render_owned_species(indices):
                first = fish_list[indices[0]]
                with st.expander(f"{first.get('emoji', '🐟')} {first.get('name', '魚')}　{'☆' * get_fish_stars(first)}　（{len(indices)}/5匹）"):
                    for i in indices:
                        fish = fish_list[i]
                        st.markdown(f"**{fish_display_name(fish)}**　{fish.get('size_mm', 10.0) / 10:.2f}cm　成長 {fish.get('feed_points', 0) % 5}/5pt")
                        col_name, col_display = st.columns([3, 1])
                        with col_name:
                            new_name = st.text_input("名前（空欄ならデフォルト名）", value=fish.get("custom_name", ""),
                                                     key=f"aqua_fish_name_{i}", placeholder=fish.get("default_name", "魚"))
                        with col_display:
                            show = st.checkbox("展示する", value=fish.get("display", True), key=f"aqua_fish_show_{i}")
                        if new_name != fish.get("custom_name", "") or show != fish.get("display", True):
                            fish["custom_name"] = new_name.strip()
                            fish["display"] = show
                            save_progress()
                    st.caption("この種類は最大5匹まで所持できます。")

            for species in ALL_FISH:
                if species["id"] in species_groups:
                    _render_owned_species(species_groups[species["id"]])
                else:
                    st.caption(f"❓ ？？？　{'☆' * int(species.get('stars', 1))}　まだ出会っていません")
            # fish.json にない旧データの魚も、失わないようここに表示する
            for sid, indices in species_groups.items():
                if sid not in known_ids:
                    _render_owned_species(indices)

        st.write("---")
        st.markdown("### 📈 水槽レベルアップ条件")
        # 達成済みのレベルと、現在のレベルの一つ上だけ公開する。
        for level_data in AQUA_TANK_LEVELS:
            level = level_data["level"]
            if level <= tank["level"]:
                achieved = tank_history.get(str(level))
                date_text = f"達成日：{achieved}" if achieved else "達成日：記録なし（旧データ）"
                st.write(f"✅ **Lv.{level} {level_data['name']}**：豪華度 {level_data['required']} ／ {date_text}")
            elif level == tank["level"] + 1:
                remaining = max(0, level_data["required"] - tank_score)
                st.info(f"🔓 次の水槽 **Lv.{level} {level_data['name']}**：豪華度 {level_data['required']} 必要（あと {remaining}）")
        if tank["level"] == AQUA_TANK_LEVELS[-1]["level"]:
            st.success("🏆 最高レベルに到達！")

    # --- 恐竜レースページ ---
    elif st.session_state.page == "dino_page":
        st.title("🦖 恐竜レース")
        ensure_dino_data()
        partner = get_dino_partner()

        # 効果音・演出は、画面更新後に一度だけ
        dino_sound_kind = st.session_state.pop("dino_sound", None)
        if dino_sound_kind == "finish":
            play_jar_full_sound(delay=0)
            st.balloons()
        elif dino_sound_kind == "achieve":
            play_achieve_sound(delay=0)
        elif dino_sound_kind == "points":
            play_aqua_point_sound(delay=0)
        elif dino_sound_kind == "feed":
            play_aqua_feed_sound(delay=0)
        elif dino_sound_kind == "click":
            play_click_sound(delay=0)

        st.caption("サイコロで進むすごろくレース！ 1マス＝100m。戻るマスはないので、安心して進もう🦖")

        # ポイント・パートナー表示
        info1, info2, info3 = st.columns(3)
        with info1:
            st.metric("💎 IPPOポイント", st.session_state.ippo_points)
        with info2:
            if partner:
                st.metric("🤝 パートナー", f"{DINO_SPECIES[partner['species']]['emoji']} {dino_display_name(partner)}")
            else:
                st.metric("🤝 パートナー", "未選択")
        with info3:
            st.metric("🎲 サイコロ1回", f"{DINO_DICE_COST} IPPOポイント")

        # 目標を達成して共通のIPPOポイントをゲット
        with st.expander("🏆 目標を達成してIPPOポイントをゲット！"):
            st.caption("達成した目標のレベルぶんだけIPPOポイントがもらえます。")
            if not st.session_state.target_list:
                st.warning("⚠️ まだ目標が登録されていません！『目標登録』で目標を作ってね！")
            else:
                dino_target_titles = [t["title"] for t in st.session_state.target_list]
                dino_target_title = st.selectbox("🎯 どの目標を達成した？", dino_target_titles, key="dino_target_select")
                dino_target_data = next(t for t in st.session_state.target_list if t["title"] == dino_target_title)
                dino_level_options = [
                    f"{lv}: {task} (💎{int(lv.replace('Lv.', '').replace('Lv', ''))} IPPOポイント)"
                    for lv, task in dino_target_data["tasks"].items()
                ]
                dino_level_str = st.selectbox("⭐ どのレベルをクリアした？", dino_level_options, key="dino_level_select")
                dino_lv_key = dino_level_str.split(":")[0]
                dino_task_text = dino_target_data["tasks"][dino_lv_key]
                if st.button("➕ この1歩を達成した！", type="primary", key="dino_achieve_button"):
                    dino_earned = int(dino_lv_key.replace("Lv.", "").replace("Lv", ""))
                    st.session_state.ippo_points += dino_earned
                    st.session_state.aqua_goal_log.append({
                        "date": get_now_jst().strftime("%Y/%m/%d %H:%M"),
                        "target": dino_target_title, "level": dino_lv_key, "task": dino_task_text,
                        "points": dino_earned, "source": "dino",
                    })
                    add_sticker_for_date(get_now_jst().strftime("%Y/%m/%d"))
                    queue_dino_sound("points")
                    add_dino_message(f"🎉 目標達成！ {dino_earned} IPPOポイントをゲットしたよ！")
                    save_progress()
                    st.rerun()

        # 直前の出来事（サイコロの結果など）
        dino_messages = st.session_state.pop("dino_messages", [])
        if dino_messages:
            with st.container(border=True):
                for message_text in dino_messages:
                    st.write(message_text)

        _dino_main_tab = stage_tab_selector(["🏁 レース", "🦖 恐竜たち", "🌱 育成", "🍖 恐竜ショップ", "🎰 恐竜ガチャ"], "dino_active_tab")

        # ---------------- レース ----------------
        if _dino_main_tab == "🏁 レース":
            course_keys = ["beginner", "intermediate", "advanced"] + [
                k for k in ("survival", "relax")
                if k in st.session_state.get("dino_unlocked_courses", [])
            ]
            locked_course = st.session_state.get("dino_locked_course")
            if locked_course in course_keys:
                # ---- 決定済み：コースを固定して表示。変えるときは変更ボタン ----
                course_key = locked_course
                locked_info = DINO_COURSES[course_key]
                name_col, change_col = st.columns([3, 1])
                with name_col:
                    st.markdown(f"🗺️ **{locked_info['tier']} {locked_info['name']}（{locked_info['distance_km']}km）**")
                with change_col:
                    if st.button("🔄 変更", use_container_width=True, key="dino_course_change"):
                        st.session_state.dino_locked_course = None
                        save_progress()
                        st.rerun()
            else:
                # ---- 未決定：選んで「決める」を押すと固定される ----
                course_key = st.selectbox(
                    "🗺️ コースを選ぶ", course_keys,
                    format_func=lambda k: f"{DINO_COURSES[k]['tier']} {DINO_COURSES[k]['name']}（{DINO_COURSES[k]['distance_km']}km）",
                    key="dino_course_choice",
                )
                if st.button("✅ このコースに決める", type="primary", use_container_width=True, key="dino_course_lock"):
                    st.session_state.dino_locked_course = course_key
                    save_progress()
                    st.rerun()
            course = DINO_COURSES[course_key]
            if not course["ready"]:
                st.info(f"🚧 {course['tier']} {course['name']} は現在準備中です！お楽しみに！")
            elif partner is None:
                st.warning("🤝 まずは『恐竜たち』タブで、一緒に走るパートナーを選んでね！")
            else:
                race = get_dino_race(course_key)
                goal = dino_course_goal(course_key)
                partner_species = DINO_SPECIES[partner["species"]]
                partner_level = dino_level(partner)
                st.markdown(f"#### {partner_species['emoji']} {dino_display_name(partner)}（Lv.{partner_level}）と一緒に走ろう！")
                st.write(f"📍 現在地：**{race['pos'] * 100}m / {goal * 100}m**（{race['pos']}/{goal}マス）　🏁 完走 {race['laps']}回")
                st.progress(min(race["pos"] / goal, 1.0))
                st.markdown(render_dino_board(course_key, race["pos"], partner_species["emoji"]), unsafe_allow_html=True)
                st.caption("💨 追い風　🎲 もう一回　🍖 食べ物　⚔️ バトル（力試し・挑むかは自由）　🏁 ゴール")
                st.write("")

                # 模型恐竜との練習はレース進行に関係なくいつでも開始できる
                if st.session_state.get("dino_battle") is None:
                    practice_difficulty = st.selectbox(
                        "🧸 練習する模型恐竜の強さ",
                        ["やさしめ", "ふつう", "つよい"],
                        index=1,
                        key="dino_practice_difficulty",
                        help="やさしめ：Lv.1 ／ ふつう：自分と同じ強さ ／ つよい：自分より強い",
                    )
                    if st.button(
                        "🧸 模型の恐竜と練習バトル（いつでも挑戦・報酬なし）",
                        use_container_width=True, key="dino_practice_battle"):
                        start_dino_practice_battle(partner, practice_difficulty)
                        st.rerun()

                battle = st.session_state.get("dino_battle")
                if battle:
                    # ===== バトル中 =====
                    enemy = battle["enemy"]
                    st.markdown(f"### ⚔️ 力試し！ vs {enemy['emoji']} {enemy['name']}（Lv.{enemy['level']}）")
                    col_me, col_enemy = st.columns(2)
                    with col_me:
                        st.markdown(f"**{partner_species['emoji']} {dino_display_name(partner)}**")
                        st.caption(f"HP {battle['player_hp']} / {battle['player_max_hp']}")
                        st.progress(battle["player_hp"] / battle["player_max_hp"])
                    with col_enemy:
                        st.markdown(f"**{enemy['emoji']} {enemy['name']}**")
                        st.caption(f"HP {battle['enemy_hp']} / {enemy['max_hp']}")
                        st.progress(battle["enemy_hp"] / enemy["max_hp"])
                    with st.container(border=True):
                        for line in battle["log"]:
                            st.write(line)

                    if battle["over"]:
                        end_label = "🧸 練習を終える" if battle.get("practice") else "🏁 レースにもどる"
                        if st.button(end_label, type="primary", use_container_width=True, key="dino_battle_end"):
                            del st.session_state["dino_battle"]
                            st.rerun()
                    else:
                        special_left = battle.get("special_left", 0)
                        st.caption(f"🌟 固有技『{partner_species['special_name']}』：{partner_species['special_text']}（この力試しであと {special_left}回）")
                        battle_actions = [
                            ("attack", "⚔️ こうげき"), ("defend", "🛡️ ぼうぎょ"),
                            ("special", f"🌟 固有技({special_left})"), ("flee", "🏃 にげる"),
                        ]
                        for action_col, (action_key, action_label) in zip(st.columns(4), battle_actions):
                            with action_col:
                                if st.button(action_label, use_container_width=True, key=f"dino_battle_{action_key}",
                                             disabled=(action_key == "special" and special_left <= 0)):
                                    resolve_dino_battle_turn(partner, action_key)
                                    st.rerun()
                        with st.expander("📖 戦い方のルール"):
                            st.write("⚔️ **こうげき**：1〜5のダメージ。ただし相手がぼうぎょだと反撃される！")
                            st.write("🛡️ **ぼうぎょ**：相手がこうげきなら攻撃を止めて大きな反撃！ でも相手が固有技・強打のときは防げない。")
                            st.write(f"🌟 **固有技**：恐竜ごとの特別な技。ぼうぎょされても止められない。1回の力試しで{DINO_SPECIAL_USES}回まで。")
                            st.write("🏃 **にげる**：いつでも安全に逃げられる。")

                elif race["pending_battle"]:
                    # ===== バトルマスに到着（挑むかどうかは自由）=====
                    pending = race["pending_battle"]
                    if pending.get("ambush"):
                        st.warning(f"⚡ いきなり野良の {pending['emoji']} {pending['name']}（Lv.{pending['level']}）が飛び出してきた！ "
                                   f"勝つと経験値が{float(pending['ambush']['exp_multiplier']):g}倍！ 負けると{pending['ambush']['back_steps']}マス戻るよ。挑戦する？")
                    else:
                        st.warning(f"⚔️ 野良の {pending['emoji']} {pending['name']}（Lv.{pending['level']}）があらわれた！ 力試しに挑戦する？")
                    fight_col, skip_col = st.columns(2)
                    with fight_col:
                        if st.button("⚔️ 力試しに挑む！", type="primary", use_container_width=True, key="dino_battle_accept"):
                            start_dino_battle(course_key, partner)
                            st.rerun()
                    with skip_col:
                        if st.button("👋 見送る", use_container_width=True, key="dino_battle_skip"):
                            skip_dino_battle(course_key)
                            st.rerun()

                elif race["finished"]:
                    # ===== ゴール =====
                    st.success(f"🏁 『{course['name']}』を完走しました！ よくがんばったね！")
                    if st.button("🔄 もう一度走る", type="primary", use_container_width=True, key=f"dino_restart_{course_key}"):
                        restart_dino_race(course_key)
                        st.rerun()

                else:
                    # ===== サイコロ =====
                    free_rolls = race["free_rolls"]
                    can_roll = free_rolls > 0 or st.session_state.ippo_points >= DINO_DICE_COST
                    if free_rolls > 0:
                        dice_label = f"🎲 サイコロを振る！（無料・あと{free_rolls}回）"
                    else:
                        dice_label = f"🎲 サイコロを振る！（{DINO_DICE_COST} IPPOポイント）"
                    if st.button(dice_label, type="primary", use_container_width=True,
                                 disabled=not can_roll, key=f"dino_roll_{course_key}"):
                        roll_dino_dice(course_key)
                        st.rerun()
                    if not can_roll:
                        st.caption("IPPOポイントが足りません。上の『目標を達成してIPPOポイントをゲット！』でIPPOポイントを貯めよう！")
                    special_stock = int(st.session_state.get("dino_special_dice", 0))
                    if special_stock > 0:
                        special_value = st.selectbox("🌟 スペシャルダイスの目を選ぶ", [1, 2, 3, 4, 5, 6], key=f"dino_special_value_{course_key}")
                        if st.button(f"🌟 スペシャルダイスを使う（残り{special_stock}個）", use_container_width=True,
                                     disabled=bool(race["finished"] or race["pending_battle"]), key=f"dino_special_roll_{course_key}"):
                            roll_dino_dice(course_key, special_dice_value=int(special_value))
                            st.rerun()
                    else:
                        st.caption("🌟 スペシャルダイスはショップで購入できます（1個5 IPPOポイント）。")
                    st.caption(dino_passive_caption(partner["species"], partner_level))

        # ---------------- 恐竜たち ----------------
        if _dino_main_tab == "🦖 恐竜たち":
            st.markdown("#### 🦖 あなたの恐竜たち")
            st.caption("名前は自由につけられます。パートナーに選んだ恐竜が、レースとバトルに出ます。")
            for dino in st.session_state.dino_owned:
                species = DINO_SPECIES[dino["species"]]
                level = dino_level(dino)
                is_partner = dino["id"] == st.session_state.dino_partner
                title = f"{species['emoji']} {dino_display_name(dino)}　Lv.{level}" + ("　🤝パートナー" if is_partner else "")
                with st.expander(title, expanded=is_partner):
                    st.write(f"種類：**{species['name']}**　／　最大HP：**{dino_max_hp(dino)}**　／　攻撃補正：+{dino_attack(dino)}　／　素早さ：{dino_speed(dino)}")
                    st.caption(
                        f"📈 レベルアップ・アイテムのボーナス：❤️HP +{int(dino.get('hp_bonus', 0))}　"
                        f"⚔️攻撃力 +{int(dino.get('attack_bonus', 0))}　💨素早さ +{int(dino.get('speed_bonus', 0))}"
                    )
                    if st.checkbox("📜 成長履歴を見る", key=f"dino_growth_show_{dino['id']}"):
                        growth_log = dino.get("growth_log", [])
                        if not growth_log:
                            st.caption("まだ成長の記録がありません。レベルが上がるとここに残ります！")
                        for growth_entry in reversed(growth_log):   # 新しい順
                            st.write(f"🗓️ {growth_entry['date']}　{growth_entry['text']}")
                    if level >= DINO_MAX_LEVEL:
                        st.progress(1.0)
                        st.caption(f"経験値 {dino.get('exp', 0)}（最大レベル！）")
                    else:
                        base_exp = dino_exp_for_level(level)
                        next_exp = dino_exp_for_level(level + 1)
                        st.progress((dino.get("exp", 0) - base_exp) / (next_exp - base_exp))
                        st.caption(f"経験値 {dino.get('exp', 0)}（次のレベルまであと {next_exp - dino.get('exp', 0)}）")
                    st.write("✨ **固有能力** " + dino_passive_caption(dino["species"], level))
                    if dino_passive_effective_chance(dino["species"], level) is not None:
                        st.caption("　発動確率は、レベルが上がると高くなるよ。")
                    st.write(f"🌟 **固有技『{species['special_name']}』**：{species['special_text']}")
                    new_name = st.text_input("名前（空欄なら元の名前）", value=dino.get("custom_name", ""),
                                             key=f"dino_name_{dino['id']}", placeholder=species["name"])
                    if new_name.strip() != dino.get("custom_name", ""):
                        dino["custom_name"] = new_name.strip()
                        save_progress()
                    if st.button("🤝 パートナーにする", key=f"dino_partner_{dino['id']}",
                                 disabled=is_partner, use_container_width=True):
                        st.session_state.dino_partner = dino["id"]
                        save_progress()
                        st.rerun()

        # ---------------- 恐竜ショップ ----------------
        if _dino_main_tab == "🍖 恐竜ショップ":
            st.markdown("#### 🍖 恐竜のごはん")
            st.caption("餌をあげると経験値がたまって、恐竜のレベルが上がります。レースのマスに進んだり、力試しに勝ったりしても経験値がもらえるよ！")
            food_cols = st.columns(len(DINO_FOOD))
            for food_col, (food_key, food) in zip(food_cols, DINO_FOOD.items()):
                with food_col:
                    st.markdown(f"### {food['emoji']} {food['name']}")
                    st.write(f"{food['price']} IPPOポイント ／ 経験値 +{food['exp']}")
                    st.caption(f"持っている数：{st.session_state.dino_food.get(food_key, 0)}個")
                    if st.button("購入する", key=f"dino_buy_{food_key}", use_container_width=True):
                        if st.session_state.ippo_points >= food["price"]:
                            st.session_state.ippo_points -= food["price"]
                            st.session_state.dino_food[food_key] = st.session_state.dino_food.get(food_key, 0) + 1
                            save_progress()
                            st.success(f"{food['emoji']} {food['name']}を買いました！")
                            st.rerun()
                        else:
                            st.warning("IPPOポイントが足りません！")

            st.write("---")
            st.markdown("#### 🌟 スペシャルダイス")
            st.write("**スペシャルダイス** — 5 IPPOポイント ／ 1回だけ、1〜6から好きな目を選べます。")
            st.caption(f"所持数：{int(st.session_state.get('dino_special_dice', 0))}個")
            if st.button("🌟 スペシャルダイスを購入（5 IPPOポイント）", key="dino_buy_special_dice", use_container_width=True):
                if st.session_state.ippo_points >= 5:
                    st.session_state.ippo_points -= 5
                    st.session_state.dino_special_dice = int(st.session_state.get("dino_special_dice", 0)) + 1
                    save_progress()
                    st.success("スペシャルダイスを1個購入しました！レースで好きな目を選んで使えます。")
                    st.rerun()
                else:
                    st.warning("IPPOポイントが足りません！")

            st.write("---")
            st.markdown("#### 🏁 コースショップ")
            st.caption("IPPOポイントで新しいすごろくコースを解放できます。")
            for course_key in ("survival", "relax"):
                course_data = DINO_COURSES[course_key]
                owned_course = course_key in st.session_state.get("dino_unlocked_courses", [])
                st.markdown(f"**{('🏆' if course_key == 'survival' else '🌸')} {course_data['name']}** — {course_data['price']} IPPOポイント")
                st.caption("バトルマスがたくさん！手ごわいサバイバル。" if course_key == "survival" else "和むイベントマスがたくさんある、のんびりコース。")
                if owned_course:
                    st.success("購入済み")
                elif st.button(f"購入する（{course_data['price']} IPPOポイント）", key=f"dino_course_buy_{course_key}", use_container_width=True):
                    if st.session_state.ippo_points >= course_data["price"]:
                        st.session_state.ippo_points -= course_data["price"]
                        st.session_state.setdefault("dino_unlocked_courses", []).append(course_key)
                        save_progress()
                        st.success(f"{course_data['name']}を解放しました！")
                        st.rerun()
                    else:
                        st.warning("IPPOポイントが足りません！")

        # ---------------- 育成（ごはん・木の実・能力アップアイテム） ----------------
        if _dino_main_tab == "🌱 育成":
            st.markdown("#### 🌱 恐竜を育てよう")
            st.caption("① 育てる恐竜を選ぶ　→　② ごはん・木の実・アイテムで強くしよう！")
            grow_result = st.session_state.pop("dino_grow_result", None)
            if grow_result:
                st.success(grow_result)

            grow_dinos = st.session_state.dino_owned
            default_idx = next((i for i, d in enumerate(grow_dinos) if d["id"] == st.session_state.dino_partner), 0)
            grow_idx = st.selectbox(
                "① 育てる恐竜", list(range(len(grow_dinos))), index=default_idx,
                format_func=lambda i: f"{DINO_SPECIES[grow_dinos[i]['species']]['emoji']} {dino_display_name(grow_dinos[i])}（Lv.{dino_level(grow_dinos[i])}）",
                key="dino_grow_target",
            )
            grow_target = grow_dinos[grow_idx]
            grow_species = DINO_SPECIES[grow_target["species"]]
            grow_level = dino_level(grow_target)
            grow_name = dino_display_name(grow_target)

            # --- いまの様子 ---
            with st.container(border=True):
                st.markdown(f"### {grow_species['emoji']} {grow_name}　Lv.{grow_level}")
                if grow_level >= DINO_MAX_LEVEL:
                    st.progress(1.0)
                    st.caption(f"経験値 {grow_target.get('exp', 0)}（最大レベル！）")
                else:
                    base_exp = dino_exp_for_level(grow_level)
                    next_exp = dino_exp_for_level(grow_level + 1)
                    st.progress((grow_target.get("exp", 0) - base_exp) / (next_exp - base_exp))
                    st.caption(f"経験値 {grow_target.get('exp', 0)} ／ 次のレベルまであと {next_exp - grow_target.get('exp', 0)}")
                stat_col1, stat_col2, stat_col3 = st.columns(3)
                hp_bonus = int(grow_target.get("hp_bonus", 0))
                attack_bonus = int(grow_target.get("attack_bonus", 0))
                speed_bonus = int(grow_target.get("speed_bonus", 0))
                stat_col1.metric("❤️ 最大HP", dino_max_hp(grow_target), delta=f"+{hp_bonus}" if hp_bonus else None, delta_color="off")
                stat_col2.metric("⚔️ 攻撃力", f"+{dino_attack(grow_target)}", delta=f"+{attack_bonus}" if attack_bonus else None, delta_color="off")
                stat_col3.metric("💨 素早さ", dino_speed(grow_target), delta=f"+{speed_bonus}" if speed_bonus else None, delta_color="off")
                st.caption("小さな数字は、木の実・アイテム・レベルアップで増えた分だよ。")

            st.markdown("##### ② 育てかたを選ぶ")
            _dino_grow_tab = stage_tab_selector(["🍽️ ごはん", "🍇 木の実", "🧪 能力アップアイテム"], "dino_grow_active_tab")

            # --- ごはん ---
            if _dino_grow_tab == "🍽️ ごはん":
                st.caption("あげると経験値がたまって、レベルアップ！ ごはんは「🍖 恐竜ショップ」で買えるよ。レースの食べ物マスでも見つかるよ。")
                food_grow_cols = st.columns(len(DINO_FOOD))
                for food_col, (food_key, food) in zip(food_grow_cols, DINO_FOOD.items()):
                    with food_col:
                        with st.container(border=True):
                            stock = st.session_state.dino_food.get(food_key, 0)
                            st.markdown(f"### {food['emoji']} {food['name']}")
                            st.write(f"経験値 **+{food['exp']}**")
                            st.caption(f"持っている数：{stock}個")
                            if st.button("あげる", key=f"dino_grow_feed_{food_key}", disabled=stock <= 0, use_container_width=True):
                                old_level = dino_level(grow_target)
                                st.session_state.dino_food[food_key] -= 1
                                add_dino_message(f"{food['emoji']} {grow_name}は{food['name']}をもぐもぐ！ 経験値 +{food['exp']}")
                                queue_dino_sound("feed")
                                add_dino_exp(grow_target, food["exp"])
                                text = f"{food['emoji']} {grow_name}は{food['name']}をもぐもぐ！ 経験値 +{food['exp']}"
                                if dino_level(grow_target) > old_level:
                                    text += f"　🎉 Lv.{dino_level(grow_target)} にレベルアップ！"
                                st.session_state.dino_grow_result = text
                                save_progress()
                                st.rerun()

            # --- 木の実 ---
            if _dino_grow_tab == "🍇 木の実":
                st.caption("力試し（バトル）に勝つと、ときどきもらえるよ。食べると、その能力がずっと上がるよ！")
                berry_cols = st.columns(3)
                for berry_col, stat_key in zip(berry_cols, ("hp", "attack", "speed")):
                    stat_info = DINO_GROWTH_STATS[stat_key]
                    with berry_col:
                        with st.container(border=True):
                            st.markdown(f"**{stat_info['emoji']} {stat_info['label']}アップ**")
                            for berry_key, berry in DINO_BERRIES.items():
                                if berry["stat"] != stat_key:
                                    continue
                                stock = st.session_state.get("dino_berries", {}).get(berry_key, 0)
                                amount = 2 if berry_key.endswith("_plus") else 1
                                st.caption(f"{berry['name']}　残り {stock}個")
                                if st.button(f"{berry['emoji']} 食べる（+{amount}）", key=f"dino_grow_berry_{berry_key}",
                                             disabled=stock <= 0, use_container_width=True):
                                    eat_dino_berry(grow_target, berry_key)
                                    st.session_state.dino_grow_result = (
                                        f"{berry['emoji']} {grow_name}が{berry['name']}を食べた！ {berry['label']} +{amount}！")
                                    st.rerun()

            # --- 能力アップアイテム（ドリンクなど） ---
            if _dino_grow_tab == "🧪 能力アップアイテム":
                st.caption("拾ったアイテムは無料で使えるよ。IPPOポイントで買って、すぐ使うこともできるよ。"
                           f"　いまのIPPOポイント：{st.session_state.ippo_points}")
                for item in DINO_SHOP_DATA["stat_items"]:
                    owned_count = int(st.session_state.get("dino_stat_items", {}).get(item["id"], 0))
                    stat_label = DINO_GROWTH_STATS[item["stat"]]["label"]
                    with st.container(border=True):
                        item_left, item_right = st.columns([3, 2])
                        with item_left:
                            st.markdown(f"**{item['emoji']} {item['name']}**")
                            st.caption(f"{stat_label} +{item['amount']} ／ 経験値 +{item['exp']}")
                            st.caption(f"🎒 持っている数：{owned_count}個")
                        with item_right:
                            if st.button(f"使う（{owned_count}個）", key=f"dino_grow_item_use_{item['id']}",
                                         disabled=owned_count <= 0, use_container_width=True):
                                st.session_state.setdefault("dino_stat_items", {})[item["id"]] = owned_count - 1
                                st.session_state.dino_grow_result = use_dino_stat_item(grow_target, item)
                                save_progress()
                                st.rerun()
                            if st.button(f"買って使う（{item['price']} IPPO）", key=f"dino_grow_item_{item['id']}",
                                         disabled=st.session_state.ippo_points < item["price"], use_container_width=True):
                                st.session_state.ippo_points -= item["price"]
                                st.session_state.dino_grow_result = use_dino_stat_item(grow_target, item)
                                save_progress()
                                st.rerun()

        # ---------------- 恐竜ガチャ ----------------
        if _dino_main_tab == "🎰 恐竜ガチャ":
            st.markdown("#### 🎰 恐竜ガチャ")
            st.write(f"1回 **{DINO_GACHA_COST_POINTS} IPPOポイント**。新しい恐竜の仲間に会えるよ！")
            st.caption("出会った恐竜は「🦖 恐竜たち」タブに仲間入りして、パートナーにできるよ。"
                       "すでに仲間の恐竜が出たときは、その恐竜に経験値がもらえるよ🎁")
            st.metric("💎 IPPOポイント", st.session_state.ippo_points)

            gacha_result = st.session_state.pop("dino_gacha_result", None)
            if gacha_result:
                play_aqua_gacha_sound(gacha_result["stars"], delay=0)   # 効果音は1回だけ
                with st.container(border=True):
                    st.markdown(f"### {'★' * gacha_result['stars']}　{gacha_result['emoji']} {gacha_result['name']}")
                    if gacha_result["is_new"]:
                        st.success(f"🎉 {gacha_result['name']}が仲間になったよ！ {gacha_result['comment']}")
                        if gacha_result["stars"] >= 4:
                            st.balloons()
                    else:
                        text = f"すでに仲間の{gacha_result['name']}に会えたよ！ 仲良しボーナスで経験値 +{gacha_result['dup_exp']} 🎁"
                        if gacha_result.get("level_up"):
                            text += f"　🎉 Lv.{gacha_result['level_up']} にレベルアップ！"
                        st.info(text)

            gacha_pool = dino_gacha_pool()
            if not gacha_pool:
                st.info("🚧 ガチャの恐竜は準備中です！（dino.json に stars 付きの恐竜を入れると遊べます）")
            elif st.button(f"🎰 ガチャを回す（{DINO_GACHA_COST_POINTS} IPPOポイント）", type="primary", use_container_width=True,
                           disabled=st.session_state.ippo_points < DINO_GACHA_COST_POINTS, key="dino_gacha_spin_button"):
                if dino_gacha_spin():
                    st.rerun()
            if gacha_pool and st.session_state.ippo_points < DINO_GACHA_COST_POINTS:
                st.caption("IPPOポイントがたまったら回せるよ💎 目標を達成してためよう！")

            st.write("---")
            met = sum(1 for key, _ in gacha_pool if any(d["species"] == key for d in st.session_state.dino_owned))
            st.markdown(f"#### 🦕 ガチャで出会える恐竜（{met} / {len(gacha_pool)} 種類）")
            for key, info in sorted(gacha_pool, key=lambda x: (int(x[1]["stars"]), x[1]["name"])):
                stars_text = "★" * int(info["stars"])
                if any(d["species"] == key for d in st.session_state.dino_owned):
                    st.write(f"{info['emoji']} **{info['name']}**　{stars_text}　（仲間になったよ）")
                else:
                    st.write(f"❓ ？？？　{stars_text}")

# =====================================================
# 💾 Supabase への自動セーブ
# =====================================================
if st.session_state.get("game_started"):
    save_progress()

