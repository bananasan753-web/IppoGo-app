import streamlit as st
from datetime import datetime, date
import random
import base64
import os
import time
import calendar as cal_module
import json

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
# 🔊 効果音まわりの設定
# =====================================================
# ↓↓↓ このスクリプト(IPPOapp.py)と同じ階層に "sounds" フォルダを作り、
#     その中に効果音ファイルを置いてください。
#     例）IPPOapp.py と同じ場所に sounds/決定ボタンを押す23.mp3 を配置
#
# 元のコードにあった "C:\\Users\\banan\\Downloads\\..." のような絶対パスは
# あなたのPC専用の場所を指しているため、フォルダを移動したり
# 別のPCで動かしたり、将来Web公開したりすると動かなくなります。
# プロジェクト内の相対パスにしておくと、どこに持って行っても動きます。
SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "決定ボタンを押す23.mp3")
ACHIEVE_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "クイズ正解1.mp3")
JAR_FULL_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "歓声と拍手.mp3")

# 瓶の容量(個数) → サイズ表記(S/M/L)への変換
JAR_SIZE_LABELS = {30: "S", 50: "M", 100: "L"}


def jar_size_label(capacity: int) -> str:
    """瓶の容量からS/M/Lのサイズ表記を返す"""
    return JAR_SIZE_LABELS.get(capacity, "?")


# =====================================================
# 💾 セーブデータ（進捗の引き継ぎ）まわりの設定
# =====================================================
# IPPOapp.py と同じ場所に save_data.json というファイルを作り、
# そこに進捗を保存します。「つづきから」を選ぶとこのファイルから読み込みます。
SAVE_FILE_PATH = os.path.join(os.path.dirname(__file__), "save_data.json")

# 保存する（＝セーブデータに含める）項目一覧
# ここに入れているキーだけが save_data.json に書き出されます。
# ボタンの開閉状態など、一時的なUI表示のオン/オフはあえて含めていません。
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
]

# 「はじめから」で戻す初期値
PERSISTENT_DEFAULTS = {
    "target_list": [],
    "jar_capacity": 30,
    "jar_candies": [],
    "all_candy_log": [],
    "jar_complete_log": [],
    "last_jar_capacity": 30,
    "course_km": {},                    # { "village": 12, "town": 5, ... } コースごとの現在の走行距離
    "course_complete_sound_played": {},  # { "village": True, ... } コースごとの完走演出済みフラグ
    "course_complete_companion_message": {},  # { "village": "…やるじゃない。", ... } コースごとの完走セリフ
    "course_run_log": [],               # 全コース共通の「走った記録」ログ（カレンダー表示用）
    "course_complete_log": [],          # 全コース共通の「完走した記録」ログ（カレンダー表示用）
    "companion": None,
    "goal_complete_log": [],
    "calendar_stickers": {},
    "calendar_notes": {},
    "sticker_type": "circle",
    "sticker_color": "赤",
}


def load_progress():
    """save_data.json があれば読み込んで、session_stateに反映する（「つづきから」用）"""
    if not os.path.exists(SAVE_FILE_PATH):
        return
    try:
        with open(SAVE_FILE_PATH, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        for key, value in saved_data.items():
            st.session_state[key] = value
    except (json.JSONDecodeError, OSError):
        # 壊れたセーブファイルなどがあってもアプリが止まらないようにする
        pass


def save_progress():
    """現在の進捗を save_data.json に書き出す（ゲーム開始後、毎回の操作のたびに呼ばれる）"""
    data_to_save = {
        key: st.session_state[key]
        for key in PERSISTENT_KEYS
        if key in st.session_state
    }
    try:
        with open(SAVE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def reset_progress():
    """進捗をすべて初期値に戻し、save_data.jsonも削除する（「はじめから」「セーブデータを削除」用）"""
    for key, default_value in PERSISTENT_DEFAULTS.items():
        if isinstance(default_value, (list, dict)):
            st.session_state[key] = type(default_value)(default_value)  # 使い回さないよう複製
        else:
            st.session_state[key] = default_value
    if os.path.exists(SAVE_FILE_PATH):
        try:
            os.remove(SAVE_FILE_PATH)
        except OSError:
            pass


# =====================================================
# 🏃 ランニングコースの共通設定
# =====================================================
# 新しいコースを増やしたい時は、ここに1行足すだけでOK。
# bonus: None（ボーナスなし） / "skip"（ショートカット系、中級用） / "extra_run"（絶好調ラン系、上級用）
# ready: True で実際に遊べる。False の間は「準備中」表示になる。
RUNNING_COURSES = {
    "village":    {"name": "一歩村一周コース",         "distance": 30,  "tier": "🟢 初級", "bonus": None,        "ready": True},
    "town":       {"name": "その調子！二歩町巡り",       "distance": 40,  "tier": "🟢 初級", "bonus": None,        "ready": True},
    "downtown":   {"name": "進め三歩市街道",            "distance": 50,  "tier": "🟢 初級", "bonus": None,        "ready": False},
    "prefecture": {"name": "信じて進む四歩県道",         "distance": 70,  "tier": "🟡 中級", "bonus": "skip",      "ready": False},
    "nation":     {"name": "君ならできる五歩国道",       "distance": 90,  "tier": "🟡 中級", "bonus": "skip",      "ready": False},
    "continent":  {"name": "焦らず行こう六歩大陸路",     "distance": 120, "tier": "🟡 中級", "bonus": "skip",      "ready": False},
    "world":      {"name": "よくがんばった七歩世界道",   "distance": 150, "tier": "🔴 上級", "bonus": "extra_run", "ready": False},
    "space":      {"name": "誇っていい八歩宇宙路",       "distance": 200, "tier": "🔴 上級", "bonus": "extra_run", "ready": False},
    "galaxy":     {"name": "どこまでも行ける九歩銀河道", "distance": 300, "tier": "🔴 上級", "bonus": "extra_run", "ready": False},
}
RUNNING_TIER_ORDER = ["🟢 初級", "🟡 中級", "🔴 上級"]

# 達成のたびに出る、通常の励まし文言（10種類）
COURSE_PRAISE_WORDS = [
    "いいペース！このまま行こう！🏃‍♂️",
    "足取り軽やか！絶好調だね！✨",
    "その調子！ゴールがだんだん近づいてきたよ🏘️",
    "ナイスラン！着実に進んでる！👏",
    "素晴らしい！景色も変わってきたね🌳",
    "すごい集中力！止まらないその勢い！🔥",
    "順調そのもの！自分を信じて！💪",
    "いいね！今日も一歩前進だ！🌟",
    "力強い一歩！道は繋がってるよ🛤️",
    "グッドラン！次のポイントまであと少し！🚀",
]

# 終盤（残り1/3くらい）専用の励まし文言
COURSE_LATE_PRAISE_WORDS = [
    "頑張れ！ラストスパートだ！🔥",
    "休憩も大事！さすがだね！☕",
    "ゴールが見えてきたよ！あと少し！🏁",
    "ここが踏ん張りどころ！いけるよ！💪",
    "疲れたら深呼吸してこう！焦らなくて大丈夫🍃",
]

# ボーナス発動時のメッセージ
COURSE_BONUS_MESSAGES = {
    "skip": "🚀 ショートカット発見！さらに+{km}km進んだ！",
    "extra_run": "💨 絶好調ラン！さらに+{km}km走れた！",
}

BONUS_CHANCE = 0.20  # ボーナスが発動する確率（20%）
BONUS_KM_RANGE = (2, 5)  # ボーナスで進む距離の範囲


def maybe_apply_bonus(course_key: str):
    """
    コース設定にボーナスが設定されていれば、20%の確率でボーナス距離とメッセージを返す。
    ボーナスが無い/発動しなかった場合は (0, None) を返す。
    """
    course = RUNNING_COURSES.get(course_key, {})
    bonus_type = course.get("bonus")
    if not bonus_type:
        return 0, None
    if random.random() >= BONUS_CHANCE:
        return 0, None
    bonus_km = random.randint(*BONUS_KM_RANGE)
    message = COURSE_BONUS_MESSAGES.get(bonus_type, "").format(km=bonus_km)
    return bonus_km, message


def render_candy_jar_svg(candies: list, capacity: int) -> str:
    """
    お菓子の瓶を、実際に選んだお菓子の絵文字（🍬🍭🍫🍩🍪など）で表現したSVGを生成する。
    グラスの丸みがある底の部分にはみ出さないよう、縦の壁がまっすぐな範囲内だけに配置する。
    """
    count = len(candies)
    width, height = 260, 300
    margin = 24
    left_x, right_x = margin, width - margin
    top_y = 16
    bottom_r = (right_x - left_x) / 2
    straight_bottom_y = height - bottom_r - 16

    # グラスの輪郭（縦の壁＋丸底）
    glass_path = (
        f"M {left_x},{top_y} "
        f"L {left_x},{straight_bottom_y} "
        f"A {bottom_r},{bottom_r} 0 0 0 {right_x},{straight_bottom_y} "
        f"L {right_x},{top_y}"
    )

    columns = 8
    rows_total = max(1, -(-capacity // columns))  # 切り上げ割り算

    # 丸底の曲線にお菓子がはみ出さないよう、まっすぐな壁の範囲内（top_y 〜 straight_bottom_y）だけを使う
    inner_margin_x = 10  # 左右の壁からの余白
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
        rnd = random.Random(i * 97 + 13)  # 見た目がガタガタしすぎないよう、インデックス固定で疑似ランダム
        jitter_x = rnd.uniform(-spacing_x * 0.12, spacing_x * 0.12)
        jitter_y = rnd.uniform(-spacing_y * 0.12, spacing_y * 0.12)
        cx = interior_left + spacing_x * col + spacing_x / 2 + jitter_x
        cy = interior_bottom - spacing_y * row - spacing_y / 2 + jitter_y
        # 満杯に近づいて行が積み上がりすぎた場合は、グラス上部を超えないようにクリップ
        cy = max(cy, interior_top)
        emoji = candy.get("emoji", "🍬")
        tooltip_text = f"入れた日：{candy.get('date', '')}"
        tooltip_text = tooltip_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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
@st.cache_data
def load_sound_base64(path: str):
    """
    音声ファイルを読み込んでbase64文字列に変換する。
    st.cache_data を付けることで、毎回ディスクから読み直さず高速化。
    """
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


_sound_b64 = load_sound_base64(SOUND_PATH)
_achieve_sound_b64 = load_sound_base64(ACHIEVE_SOUND_PATH)
_jar_full_sound_b64 = load_sound_base64(JAR_FULL_SOUND_PATH)


def play_click_sound(delay: float = 1.2):
    """
    クリック効果音をブラウザ側(HTML)で再生する。

    ポイント：
    - StreamlitのPython側の状態(session_state)とは切り離して、
      ブラウザに直接 <audio autoplay> タグを送り込んで鳴らしている。
    - この直後に st.rerun() を呼ぶと画面が即座に作り直されて
      音が切れてしまうため、ごく短い time.sleep() を挟んで
      「鳴り始める→ある程度再生される」時間を確保している。
    - delay は効果音の長さに応じて調整してください。
      今回の効果音は1〜2秒程度なので、デフォルトを1.2秒にしている。
      まだ途切れる場合は 1.5〜2.0 まで増やしてOK。
      逆にボタンの反応が遅く感じる場合は少し短くしてもよい。
    """
    if _sound_b64 is None:
        # 音声ファイルが見つからない場合は何もしない（アプリを止めない）
        return
    sound_html = f"""
        <audio autoplay="true" style="display:none;">
            <source src="data:audio/mp3;base64,{_sound_b64}" type="audio/mp3">
        </audio>
    """
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_achieve_sound(delay: float = 0):
    """
    「この1歩を達成した！」ボタン専用の効果音（クイズ正解1.mp3、1秒ほど）。
    このボタンの直後は st.rerun() を呼んでいないので、
    基本的に delay=0（待機なし）でも音は最後まで鳴る。
    """
    if _achieve_sound_b64 is None:
        return
    sound_html = f"""
        <audio autoplay="true" style="display:none;">
            <source src="data:audio/mp3;base64,{_achieve_sound_b64}" type="audio/mp3">
        </audio>
    """
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


def play_jar_full_sound(delay: float = 0):
    """
    瓶が満杯になった瞬間専用の効果音（歓声と拍手.mp3、5秒ほど）。
    この後 st.rerun() を呼ばない画面なので、delay=0のままで
    5秒間しっかり最後まで鳴る。
    """
    if _jar_full_sound_b64 is None:
        return
    sound_html = f"""
        <audio autoplay="true" style="display:none;">
            <source src="data:audio/mp3;base64,{_jar_full_sound_b64}" type="audio/mp3">
        </audio>
    """
    st.components.v1.html(sound_html, height=0)
    if delay:
        time.sleep(delay)


# =====================================================
# 1. 記憶の部屋（セッション状態）の準備
# =====================================================

if "page" not in st.session_state:
    st.session_state.page = "title"

# タイトル画面で「はじめから」または「つづきから」を選んだかどうか
# これがTrueになるまでは自動セーブを行わない（空の状態で上書き保存してしまうのを防ぐため）
if "game_started" not in st.session_state:
    st.session_state.game_started = False

# 複数の目標とその中のLv.1~5を保存するリスト
if "target_list" not in st.session_state:
    st.session_state.target_list = []

# 目標削除の確認ステップ用（削除しようとしている目標のインデックス）
if "confirm_delete_target_index" not in st.session_state:
    st.session_state.confirm_delete_target_index = None

# 📅 カレンダーの一言メモ（日付ごとの自由記述）
if "calendar_notes" not in st.session_state:
    st.session_state.calendar_notes = {}  # { "YYYY/MM/DD": "メモ内容" }

# AIボタン用フラグ
if "ai_filled" not in st.session_state:
    st.session_state.ai_filled = False

# 選んだ瓶の容量（30個、50個、100個）
if "jar_capacity" not in st.session_state:
    st.session_state.jar_capacity = 30

# 瓶の中に入ったお菓子たちのデータリスト（現在進行中の瓶だけ。瓶が完成するとリセットされる）
if "jar_candies" not in st.session_state:
    st.session_state.jar_candies = []

# カレンダー表示用：全期間のお菓子ログ（瓶が完成してもリセットされない）
if "all_candy_log" not in st.session_state:
    st.session_state.all_candy_log = []

# 「今までの瓶」を表示中かどうか
if "show_past_jars" not in st.session_state:
    st.session_state.show_past_jars = False

# --- 状態管理用の変数 ---
if "praise_message" not in st.session_state:
    st.session_state.praise_message = ""

if "show_candy_buttons" not in st.session_state:
    st.session_state.show_candy_buttons = False

if "temp_candy_count" not in st.session_state:
    st.session_state.temp_candy_count = 0

if "last_completed_task" not in st.session_state:
    st.session_state.last_completed_task = ""

# 瓶が満杯になった時の効果音を「一度だけ」鳴らすためのフラグ
if "jar_full_sound_played" not in st.session_state:
    st.session_state.jar_full_sound_played = False

# 瓶のサイズが変わったら満杯フラグをリセットするために、前回選んだ容量を覚えておく
if "last_jar_capacity" not in st.session_state:
    st.session_state.last_jar_capacity = st.session_state.jar_capacity

# 🍯 瓶コンプリート（瓶が満杯になった日）のログ
if "jar_complete_log" not in st.session_state:
    st.session_state.jar_complete_log = []

# 🏃 ランニングコース共通の状態（どのコースでも使い回す）
if "course_km" not in st.session_state:
    st.session_state.course_km = {}  # { "village": 12, "town": 5, ... }
if "course_praise_message" not in st.session_state:
    st.session_state.course_praise_message = {}  # { "village": "いいペース！...", ... }（一時的な表示用、セーブ対象外）
if "course_complete_sound_played" not in st.session_state:
    st.session_state.course_complete_sound_played = {}
if "course_complete_companion_message" not in st.session_state:
    st.session_state.course_complete_companion_message = {}  # { "village": "…やるじゃない。", ... }
if "course_run_log" not in st.session_state:
    st.session_state.course_run_log = []  # カレンダー用：走った記録(日付・コース名・km・内容)
if "course_complete_log" not in st.session_state:
    st.session_state.course_complete_log = []  # カレンダー用：完走した記録
if "active_course_key" not in st.session_state:
    st.session_state.active_course_key = "village"  # 現在プレイ中のコース

# 🐾 相棒（ランニングの一緒に走る仲間）
COMPANIONS = {
    "cat": {"emoji": "🐱", "name": "ねこ"},
    "dog": {"emoji": "🐶", "name": "いぬ"},
    "bird": {"emoji": "🐦", "name": "とり"},
}

# 相棒ごとの性格つき応援セリフ（達成した時に、通常の励まし文言に加えて表示される）
COMPANION_MESSAGES = {
    "cat": [  # クールで素直じゃないけど、実はちゃんと見てくれてるタイプ
        "ふーん、やるじゃない。…べつに、感心してないけど。",
        "まあまあね。無理しない程度に頑張りなさいよ。",
        "ふぁ…（あくび）褒めてほしいなら、褒めてあげる。えらいわよ。",
        "悪くないじゃない。次も、まあ期待しててあげる。",
        "…気が向いたから、隣を歩いてあげてるだけだから。",
        "頑張るあんたを見てると、まあ悪くないなって思うのよね。",
        "誰のためでもなく、あんたのためなんだからね。",
    ],
    "dog": [  # 全力で褒めてくれる、超ポジティブな応援団長タイプ
        "うおおおすごいすごい！！やったねやったね！！🐾",
        "きみのこと、ずっと信じてたよ！！最高だ！！",
        "もっと行こう！！ぼく、どこまでもついていくよ！！",
        "しっぽ振るのが止まらないよ！！すごいすごい！！",
        "きみが頑張る姿、ぼくの元気の源だよ！ありがとう！",
        "できたね！！えらいえらい！！なでてあげたい気分！！",
        "よーし、次のご褒美探しに行こう！！ぼくも一緒だよ！",
    ],
    "bird": [  # ふわっと優しい、詩的な言葉で寄り添うタイプ
        "風が気持ちいいね〜。きみの一歩、ちゃんと空まで届いてるよ🕊️",
        "高いところから見てたよ。ちゃんと前に進んでる、大丈夫。",
        "さえずるくらい嬉しいことがあったみたいだね♪",
        "羽を休める時間も大事。無理せずゆっくりね。",
        "その調子。景色がどんどん変わっていくの、見えてる？",
        "小さな一歩も、飛び立つ前の助走みたいなものだよ。",
        "今日の空、きみの頑張りにちょうどいい色してるよ。",
    ],
}

# 相棒ごとの「ゴール達成（完走）」専用セリフ（各5種類）
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
    st.session_state.companion = None  # 未選択の場合はNone
if "show_companion_picker" not in st.session_state:
    st.session_state.show_companion_picker = False

# 🏆 最終目標達成の記念日ログ（カレンダー表示用）
if "goal_complete_log" not in st.session_state:
    st.session_state.goal_complete_log = []

# 🎨 カレンダーのシール機能
# 選べるシールの種類（丸は色を選べる／それ以外は固定デザイン）
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

GRID_STICKERS_SHOWN = 2  # カレンダー全体（月グリッド）で表示するシール個数

if "calendar_stickers" not in st.session_state:
    st.session_state.calendar_stickers = {}  # { "YYYY/MM/DD": 3 }  ← その日にシールを貼った回数

# 🎨 シールの見た目設定（目標達成時に自動で貼られるシールのデザイン）
if "sticker_type" not in st.session_state:
    st.session_state.sticker_type = "circle"  # デフォルトは丸
if "sticker_color" not in st.session_state:
    st.session_state.sticker_color = "赤"  # 丸のデフォルト色


def get_current_sticker_emoji() -> str:
    """設定に基づいて、現在貼られるシールの絵文字を返す"""
    if st.session_state.sticker_type == "circle":
        return STICKER_CIRCLE_COLORS.get(st.session_state.sticker_color, "🔴")
    return STICKER_FIXED_TYPES.get(st.session_state.sticker_type, {}).get("emoji", "🔴")


def add_sticker_for_date(date_str: str):
    """指定した日付のシール回数を1つ増やす（絵文字自体は保存せず、回数だけ記録する）"""
    st.session_state.calendar_stickers[date_str] = st.session_state.calendar_stickers.get(date_str, 0) + 1


def should_prompt_deadline_today(target_data: dict) -> bool:
    """
    このチャレンジ期限について、「今日」結果を聞くべきかどうかを判定する。
    - 期限が設定されていない／リマインド停止済み → 聞かない
    - reminder_mode="once"（その日だけ聞く） → 今日がちょうど期限日で、まだ未回答の時だけ聞く
    - reminder_mode="daily"（答えた後も毎日聞く） → 期限日以降、今日まだ回答していなければ毎日聞く
    """
    deadline = target_data.get("deadline")
    if not deadline or target_data.get("deadline_reminder_stopped"):
        return False
    today_str = datetime.now().strftime("%Y/%m/%d")
    if target_data.get("reminder_mode") == "daily":
        if today_str < deadline:
            return False
        answered_dates = {entry["date"] for entry in target_data.get("deadline_daily_log", [])}
        return today_str not in answered_dates
    # "once" モード
    if target_data.get("deadline_answered"):
        return False
    return today_str == deadline


def record_deadline_answer(target_data: dict, result_label: str):
    """
    チャレンジ期限の回答を記録する。
    - daily モード：毎日ごとの回答をログに追加していく（同じ日には1回だけ）
    - once モード：1回だけの回答として記録する
    """
    today_str = datetime.now().strftime("%Y/%m/%d")
    if target_data.get("reminder_mode") == "daily":
        target_data.setdefault("deadline_daily_log", []).append({
            "date": today_str,
            "result": result_label,
        })
    else:
        target_data["deadline_answered"] = True
        target_data["deadline_result"] = result_label
    # 結果を報告してくれたお礼に、ボーナスでシールを1回分カウント
    add_sticker_for_date(today_str)


def get_sticker_preview(date_str: str, limit: int = MAX_STICKERS_SHOWN, show_remainder: bool = True) -> str:
    """
    指定した日付のシールを、現在の設定の絵文字で表示用文字列に変換する。
    limit 個まで並べ、show_remainder=True かつそれ以上ある場合は「+N」を付け足す。
    ・カレンダー全体（月グリッド）：limit=GRID_STICKERS_SHOWN, show_remainder=False（アイコンのみ、＋N無し）
    ・日付詳細画面：limit=MAX_STICKERS_SHOWN, show_remainder=True（＋Nを表示）
    """
    count = st.session_state.calendar_stickers.get(date_str, 0)
    if count <= 0:
        return ""
    emoji = get_current_sticker_emoji()
    preview = emoji * min(count, limit)
    if show_remainder and count > limit:
        preview += f"+{count - limit}"
    return preview


# 📅 カレンダー画面：表示中の年月と、選択中の日付
if "calendar_view_year" not in st.session_state:
    st.session_state.calendar_view_year = datetime.now().year
if "calendar_view_month" not in st.session_state:
    st.session_state.calendar_view_month = datetime.now().month
if "selected_calendar_date" not in st.session_state:
    st.session_state.selected_calendar_date = datetime.now().strftime("%Y/%m/%d")

# 2. 【タイトル画面】
if st.session_state.page == "title":
    st.title("🏃‍♂️ IPPO(仮)")
    st.subheader("〜完璧主義をハックする、最初の一歩アプリ〜")
    st.write("")

    save_exists = os.path.exists(SAVE_FILE_PATH)

    col_new, col_continue = st.columns(2)
    with col_new:
        if st.button("🆕 はじめから", use_container_width=True):
            play_click_sound()
            reset_progress()
            st.session_state.game_started = True
            st.session_state.page = "menu_select"
            st.rerun()
    with col_continue:
        if st.button("▶️ つづきから", type="primary", use_container_width=True, disabled=not save_exists):
            play_click_sound()
            load_progress()
            st.session_state.game_started = True
            st.session_state.page = "menu_select"
            st.rerun()

    if not save_exists:
        st.caption("※ セーブデータがまだありません。「はじめから」で始めてね。")

    st.write("")
    st.write("")

    # 👉 右下にセーブデータ削除の設定を配置
    spacer_col, settings_col = st.columns([3, 1])
    with settings_col:
        with st.expander("⚙️ 設定"):
            st.caption("これまでの進捗（目標・お菓子・ランニング記録など）を完全に削除します。")
            if st.session_state.get("confirm_delete_save"):
                st.warning("本当に削除しますか？この操作は取り消せません。")
                confirm_col, cancel_col = st.columns(2)
                with confirm_col:
                    if st.button("🗑️ 削除する", key="confirm_delete_yes"):
                        play_click_sound(delay=0)
                        reset_progress()
                        st.session_state.confirm_delete_save = False
                        st.success("セーブデータを削除しました。")
                        st.rerun()
                with cancel_col:
                    if st.button("やめる", key="confirm_delete_no"):
                        play_click_sound(delay=0)
                        st.session_state.confirm_delete_save = False
                        st.rerun()
            else:
                if st.button("🗑️ セーブデータを削除", key="open_delete_confirm", disabled=not save_exists):
                    play_click_sound(delay=0)
                    st.session_state.confirm_delete_save = True
                    st.rerun()


# 3. 【2ページ目：メニュー画面】
elif st.session_state.page == "menu_select":
    st.title("🗺️ メニューセレクト")
    st.markdown("## 🎯 挑戦する項目を選んでください：")
    st.write("")

    col1, col2, col3 = st.columns(3)
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


# 4. 【3ページ目以降：各個別画面】
elif st.session_state.page in [
    "target_page", "calendar_page", "stage_page",
    "candy_page", "running_page", "running_course_page"
]:

    # 👈 左側のサイドバーメニュー
    with st.sidebar:
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
        st.write("---")
        if st.button("↩️ メニューセレクトに戻る"):
            play_click_sound()
            st.session_state.page = "menu_select"
            st.rerun()
        if st.button("🏠 タイトルに戻る"):
            play_click_sound()
            st.session_state.page = "title"
            st.rerun()

    # 👉 右側のメインコンテンツ
    # ─── 【目標登録画面（セットボタンなし・シンプルスッキリ版！）】 ───
    if st.session_state.page == "target_page":
        st.title("🎯 目標登録画面")
        st.write("まずは達成したい「大きな目標」を入力してください。")

        main_target_input = st.text_input("最終目標（例：テストで70点とる、など）", key="main_input")

        if main_target_input:
            st.write("---")
            st.markdown(f"### 📝 『{main_target_input}』のレベル1〜5を入力してください")

            if st.button("💡 思いつかないときは…？ (AIがヒントを入力)"):
                play_click_sound(delay=0)  # この後すぐrerunしないので待機不要
                st.session_state.ai_filled = True

            default_lv1 = "教科書を机の上に置く 📖" if st.session_state.ai_filled else ""
            default_lv2 = "教科書を1ページだけ開く 🔍" if st.session_state.ai_filled else ""
            default_lv3 = "問題を1問だけ解いてみる ✏️" if st.session_state.ai_filled else ""
            default_lv4 = "タイマーをかけて10分間だけ集中する ⏱️" if st.session_state.ai_filled else ""
            default_lv5 = "ワークの指定ページを1枚終わらせる 🏆" if st.session_state.ai_filled else ""

            lv1 = st.text_input("Lv.1 (例:教科書を開いた！)", value=default_lv1)
            lv2 = st.text_input("Lv.2 (例:10分出来た！)", value=default_lv2)
            lv3 = st.text_input("Lv.3 (例:1ページ出来た！)", value=default_lv3)
            lv4 = st.text_input("Lv.4 (例:60分できた！)", value=default_lv4)
            lv5 = st.text_input("Lv.5 (例:範囲内の勉強が一周出来た！)", value=default_lv5)

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
                    st.session_state.ai_filled = False
                    st.rerun()
                else:
                    st.error("⚠️ 全レベルを入力してください。")

        if st.session_state.target_list:
            st.write("---")
            st.markdown("## 🛡️ 登録済みのクエスト一覧")
            for i, target_data in enumerate(st.session_state.target_list):
                with st.expander(f"🎯 {target_data['title']}", expanded=True):
                    for lv, task in target_data["tasks"].items():
                        st.info(f"**{lv}**: {task}")

                    st.write("")
                    if target_data.get("completed", False):
                        st.success("🎉 この目標は達成済みです！おめでとう！")
                        if st.button("🔄 もう一度挑戦する", key=f"retry_target_{i}"):
                            play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
                            target_data["completed"] = False
                            st.rerun()
                    else:
                        if st.button(
                            "🏆 最終目標を達成した！",
                            type="primary",
                            key=f"complete_target_{i}",
                        ):
                            play_jar_full_sound()  # 大きな達成なので歓声と拍手.mp3
                            target_data["completed"] = True
                            now_datetime_str = datetime.now().strftime("%Y/%m/%d %H:%M")
                            today_date_str = datetime.now().strftime("%Y/%m/%d")
                            st.session_state.goal_complete_log.append({
                                "date": now_datetime_str,
                                "title": target_data["title"],
                            })
                            # 達成した日のカレンダーに、シールを1回分カウント
                            add_sticker_for_date(today_date_str)
                            st.rerun()

                    st.write("")
                    st.write("---")
                    # 🎯 チャレンジ期限の設定（この日までにどれくらい進んだか、後で聞かれる）
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
                                f"🎯 チャレンジ期限：{deadline_display}〜（{reminder_mode_label}／これまでの回答数：{len(daily_log)}回）"
                            )
                        elif target_data.get("deadline_answered"):
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display}"
                                f"（結果：{target_data.get('deadline_result', '?')} 報告済み）"
                            )
                        else:
                            st.caption(
                                f"🎯 チャレンジ期限：{deadline_display} まで"
                                f"（{reminder_mode_label}／この日になったら結果を聞くよ）"
                            )
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
                            new_deadline = st.date_input(
                                "いつまでに頑張る？",
                                value=datetime.today(),
                                key=f"deadline_input_{i}",
                            )
                            new_reminder_mode = st.radio(
                                "結果はいつ聞く？",
                                options=["once", "daily"],
                                format_func=lambda m: "その日だけ聞く" if m == "once" else "答えた後も毎日聞く（繰り返しチェックイン）",
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
                    # 🗑️ 目標の削除（誤操作防止のため確認ステップつき）
                    # 削除してもカレンダー側の記録（お菓子・ランニング・記念日ログなど）は
                    # すでに文章として保存済みなので消えない
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
                        if st.button("🗑️ この目標を削除", key=f"delete_target_{i}"):
                            play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
                            st.session_state.confirm_delete_target_index = i
                            st.rerun()

    # ─── 【📅 カレンダー画面（飴ちゃん履歴リンク実装版！！！）】 ───
    elif st.session_state.page == "calendar_page":
        st.title("📅 カレンダー画面")
        st.write("これまであなたが「一歩」を達成した記録がここに残っていきます！")

        # ───────────────────────────────
        # 🎯 今日聞くべきチャレンジ結果があれば、目立つ場所で表示する
        # ───────────────────────────────
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
                            play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
                            record_deadline_answer(t, result_label)
                            st.rerun()
                st.caption("正直に選んでね。0%でもチャレンジしたこと自体がすごいことだよ🌱")
                if st.button("🔕 このリマインドをやめる", key=f"banner_stop_reminder_{idx}"):
                    play_click_sound(delay=0)
                    t["deadline_reminder_stopped"] = True
                    st.rerun()
            st.write("")

        # 月を移動するボタン
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
                f"<h3 style='text-align:center;'>{st.session_state.calendar_view_year}年"
                f"{st.session_state.calendar_view_month}月</h3>",
                unsafe_allow_html=True,
            )
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

        # 曜日ヘッダー（月曜始まり）
        weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]
        header_cols = st.columns(7)
        for header_col, label in zip(header_cols, weekday_labels):
            header_col.markdown(
                f"<div style='text-align:center; font-weight:bold;'>{label}</div>",
                unsafe_allow_html=True,
            )

        # 月の週ごとの日付一覧を取得（月外の日は0）
        cal_obj = cal_module.Calendar(firstweekday=0)
        week_rows = cal_obj.monthdayscalendar(
            st.session_state.calendar_view_year, st.session_state.calendar_view_month
        )
        today_str = datetime.now().strftime("%Y/%m/%d")

        for week in week_rows:
            week_cols = st.columns(7)
            for day_col, day_num in zip(week_cols, week):
                with day_col:
                    if day_num == 0:
                        st.write("")  # 月外の空白マス
                    else:
                        cell_date_str = (
                            f"{st.session_state.calendar_view_year}/"
                            f"{st.session_state.calendar_view_month:02d}/{day_num:02d}"
                        )
                        cell_sticker_preview = get_sticker_preview(
                            cell_date_str, limit=GRID_STICKERS_SHOWN, show_remainder=False
                        )

                        day_label = f"{day_num}"
                        if cell_date_str == today_str:
                            day_label = f"🔹{day_num}"

                        # このセルにチャレンジ期限やメモがあれば、目印を追加
                        has_deadline = any(
                            t.get("deadline") == cell_date_str
                            or any(entry["date"] == cell_date_str for entry in t.get("deadline_daily_log", []))
                            for t in st.session_state.target_list
                        )
                        has_note = bool(st.session_state.calendar_notes.get(cell_date_str))
                        markers = ""
                        if has_deadline:
                            markers += "🎯"
                        if has_note:
                            markers += "📝"

                        label_line2 = " ".join(part for part in [cell_sticker_preview, markers] if part)
                        cell_label = f"{day_label} {label_line2}" if label_line2 else day_label

                        is_selected = (cell_date_str == st.session_state.selected_calendar_date)
                        if st.button(
                            cell_label,
                            key=f"cal_day_{cell_date_str}",
                            use_container_width=True,
                            type="primary" if is_selected else "secondary",
                        ):
                            play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
                            st.session_state.selected_calendar_date = cell_date_str

        st.write("---")

        # ここから下は選択中の日付の詳細表示
        selected_date_str = st.session_state.selected_calendar_date
        selected_date_display = datetime.strptime(selected_date_str, "%Y/%m/%d").strftime("%Y年%m月%d日")
        st.markdown(f"### 🔍 {selected_date_display} の記録")

        # ───────────────────────────────
        # 📝 一言メモ（この日の予定やメモを自由に書ける）
        # ───────────────────────────────
        existing_note = st.session_state.calendar_notes.get(selected_date_str, "")
        note_input = st.text_area(
            "📝 この日の一言メモ・予定",
            value=existing_note,
            key=f"note_input_{selected_date_str}",
            height=80,
            placeholder="例：友達とカフェに行く予定、明日は早起きする、など",
        )
        if st.button("💾 メモを保存", key=f"save_note_{selected_date_str}"):
            play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
            if note_input.strip():
                st.session_state.calendar_notes[selected_date_str] = note_input.strip()
            else:
                st.session_state.calendar_notes.pop(selected_date_str, None)
            st.rerun()

        st.write("---")

        # ───────────────────────────────
        # 🎯 チャレンジ期限（最終目標に設定した「この日までチャレンジ！」）
        # 実際の回答はページ上部のバナーで行う。ここではこの日の状態だけ表示する。
        # ───────────────────────────────
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

        # 毎日チェックイン形式で、この日にすでに回答している分があれば表示する
        daily_checkin_entries_today = []
        for idx, t in enumerate(st.session_state.target_list):
            for entry in t.get("deadline_daily_log", []):
                if entry["date"] == selected_date_str:
                    daily_checkin_entries_today.append((t, entry))
        for t, entry in daily_checkin_entries_today:
            st.info(f"🎯 『{t['title']}』この日のチェックイン結果：**{entry['result']}**")

        if deadline_start_targets or daily_checkin_entries_today:
            st.write("---")

        # 瓶のデータ（jar_candies）から、選んだ日付に一致するデータを引っこ抜く！
        daily_candies = [
            c for c in st.session_state.all_candy_log
            if c["date"].startswith(selected_date_str)
        ]

        # 瓶コンプリートのログから、選んだ日付に一致するデータを引っこ抜く！
        daily_jar_completions = [
            j for j in st.session_state.jar_complete_log
            if j["date"].startswith(selected_date_str)
        ]

        # ランニングの記録から、選んだ日付に一致するデータを引っこ抜く！
        daily_runs = [
            r for r in st.session_state.course_run_log
            if r["date"].startswith(selected_date_str)
        ]

        # 完走した記録から、選んだ日付に一致するデータを引っこ抜く！
        daily_course_completions = [
            v for v in st.session_state.course_complete_log
            if v["date"].startswith(selected_date_str)
        ]

        # 最終目標達成の記念日ログから、選んだ日付に一致するデータを引っこ抜く！
        daily_goal_completions = [
            g for g in st.session_state.goal_complete_log
            if g["date"].startswith(selected_date_str)
        ]

        # ───────────────────────────────
        # 🎨 シール表示エリア（この日に貼ったシール）
        # レベルを問わず「この1歩を達成した！」を押すたびに、設定中のデザインのシールが自動で貼られます
        # ───────────────────────────────
        sticker_line = get_sticker_preview(selected_date_str, limit=MAX_STICKERS_SHOWN, show_remainder=True)
        st.markdown(f"#### 🎨 この日のシール：{sticker_line if sticker_line else '（まだ貼られていません）'}")

        with st.expander(f"⚙️ シールの見た目を設定（現在：{get_current_sticker_emoji()}）"):
            st.caption("「この1歩を達成した！」を押すたびに、ここで設定したシールが自動で貼られます。")

            sticker_type_labels = {"circle": "丸", **{k: v["label"] for k, v in STICKER_FIXED_TYPES.items()}}
            sticker_type_keys = list(sticker_type_labels.keys())
            chosen_type = st.radio(
                "シールの種類",
                options=sticker_type_keys,
                format_func=lambda k: sticker_type_labels[k],
                index=sticker_type_keys.index(st.session_state.sticker_type),
                horizontal=True,
                key="sticker_type_radio",
            )
            if chosen_type != st.session_state.sticker_type:
                st.session_state.sticker_type = chosen_type
                st.rerun()

            if st.session_state.sticker_type == "circle":
                color_keys = list(STICKER_CIRCLE_COLORS.keys())
                chosen_color = st.radio(
                    "丸の色",
                    options=color_keys,
                    format_func=lambda c: f"{STICKER_CIRCLE_COLORS[c]} {c}",
                    index=color_keys.index(st.session_state.sticker_color),
                    horizontal=True,
                    key="sticker_color_radio",
                )
                if chosen_color != st.session_state.sticker_color:
                    st.session_state.sticker_color = chosen_color
                    st.rerun()

        st.write("---")

        if daily_goal_completions:
            for g in daily_goal_completions:
                g_time_part = g["date"].split(" ")[1]
                st.success(f"🏆✨ 『{g['title']}』の目標達成記念日！（{g_time_part}）")

        if daily_jar_completions:
            for jar in daily_jar_completions:
                jar_time_part = jar["date"].split(" ")[1]
                size_label = jar.get("size_label", JAR_SIZE_LABELS.get(jar["capacity"], "?"))
                st.success(f"🍯✨ お菓子のビン({size_label})完成✨（{jar_time_part}）")

        if daily_course_completions:
            for v in daily_course_completions:
                v_time_part = v["date"].split(" ")[1]
                course_name = v.get("course", "コース")
                st.success(f"🏁✨ 『{course_name}』完走達成✨（{v_time_part}）")

        if daily_candies:
            st.success(f"🎉 この日は **{len(daily_candies)}個** のお菓子をゲットしました！！")

            # リストで可愛く表示
            for item in daily_candies:
                # 時間の部分だけ抽出（例: "22:15"）
                time_part = item["date"].split(" ")[1]
                with st.container(border=True):
                    st.markdown(f"#### {item['emoji']} 放り込んだお菓子（{time_part}）")
                    st.write(f"**クリアしたクエスト：** {item['task']}")

        if daily_runs:
            total_daily_km = sum(r["km"] for r in daily_runs)
            st.success(f"🏃 この日は合計 **{total_daily_km}km** 走りました！！")

            # リストで可愛く表示
            for run in daily_runs:
                run_time_part = run["date"].split(" ")[1]
                companion_name = run.get("companion")
                course_name = run.get("course", "ランニング")
                with st.container(border=True):
                    st.markdown(f"#### 🏃 {course_name}：{run['km']}km 進んだ（{run_time_part}）")
                    st.write(f"**クリアしたクエスト：** {run['task']}")
                    if companion_name:
                        st.write(f"**一緒に走った相棒：** 🐾 {companion_name}")

        if not (daily_candies or daily_jar_completions or daily_runs or daily_course_completions or daily_goal_completions):
            st.info("この日の記録はありません")

    # 【ステージセレクト】
    elif st.session_state.page == "stage_page":
        st.title("⚔️ ステージセレクト")
        st.markdown("### 🎮 挑戦するステージを選んでください：")
        st.write("")
        scol1, scol3 = st.columns(2)
        with scol1:
            if st.button("🍬\n\nお菓子集め", use_container_width=True, key="stage_candy"):
                play_click_sound()
                st.session_state.page = "candy_page"
                st.rerun()
        with scol3:
            if st.button("🏃‍♂️\n\nランニング", use_container_width=True, key="stage_running"):
                play_click_sound()
                st.session_state.page = "running_page"
                st.rerun()

    # ─── 【🍬 お菓子集めステージ（その場セレクト＆こだわり10種褒め言葉版！！！）】 ───
    elif st.session_state.page == "candy_page":
        st.title("🍬 魔法のお菓子瓶ステージ")

        # 瓶のサイズ選択
        st.markdown("### 🏺 まずは貯めるお菓子瓶のサイズを決めよう！")
        jar_option = st.selectbox(
            "どの瓶に貯める？",
            [30, 50, 100],
            format_func=lambda x: f"小さめの瓶（{x}個入り）" if x == 30 else (
                f"普通の瓶（{x}個入り）" if x == 50 else f"特大の瓶（{x}個入り）")
        )
        st.session_state.jar_capacity = jar_option

        # 瓶のサイズを変えたら「満杯演出」をもう一度見られるようにリセット
        if jar_option != st.session_state.last_jar_capacity:
            st.session_state.jar_full_sound_played = False
            st.session_state.last_jar_capacity = jar_option

        st.write("---")

        # 【完全継承！】こだわりの誉め言葉10種リスト！
        praise_words = [
            "おめでとう！！°˖✧◝(⁰▿⁰)◜✧˖° 本当に素晴らしい一歩だよ！",
            "凄い！よく頑張ったね！！(∩´狂｀)∩",
            "もしや君は天才…？✨",
            "グッジョブ！！頑張った自分を褒めてあげてね！💪",
            "最高！！その調子、その調子！♬٩(*^∀^*)۶♬",
            "素晴らしい！今日も未来が変わったね！🌟",
            "やったね！ハードルを乗り越えた君に拍手！👏👏",
            "最高！100点満点！！👑",
            "ナイス！！流石だね！！🔥",
            "凄ーい！山を乗り越えたあなたはもっと強くなるよ🗻！"
        ]

        # 左右にメイン処理と飴セレクトボタンを分けるレイアウト
        main_col, side_candy_col = st.columns([3, 1])

        with main_col:
            st.subheader("🏆 達成した目標を選ぼう！")

            # 登録された目標の一覧からその場で選ばせるギミック！
            if not st.session_state.target_list:
                st.warning("⚠️ まだ目標が登録されていません！「目標登録画面」で目標を作ってきてね！")
                selected_target_title = None
            else:
                target_titles = [t["title"] for t in st.session_state.target_list]
                selected_target_title = st.selectbox("🎯 どの目標を達成した？", target_titles)

                selected_target_data = next(
                    t for t in st.session_state.target_list if t["title"] == selected_target_title)

                level_options = []
                for lv, task in selected_target_data["tasks"].items():
                    lv_num = lv.split(".")[1]
                    level_options.append(f"{lv}: {task} (🍬×{lv_num}個パワー)")

                selected_level_str = st.selectbox("⭐ どのレベルをクリアした？", level_options)

                chosen_lv_key = selected_level_str.split(":")[0]  # "Lv.1"
                chosen_candy_power = int(chosen_lv_key.split(".")[1])  # 1
                chosen_task_text = selected_target_data["tasks"][chosen_lv_key]  # タスク内容

            st.write("")

            # 達成ボタン！
            if st.button("➕ この1歩を達成した！", type="primary"):
                if selected_target_title:
                    play_achieve_sound()  # クイズ正解1.mp3（このボタンではrerunしないので待機不要）
                    # 10種類のお気に入りフレーズからランダム抽出！
                    st.session_state.praise_message = random.choice(praise_words)
                    # 右側の飴ボタンを解放！
                    st.session_state.show_candy_buttons = True
                    st.session_state.temp_candy_count = chosen_candy_power
                    # ホバー時の記憶用テキストを作成
                    st.session_state.last_completed_task = f"【{selected_target_title} - {chosen_lv_key}】 {chosen_task_text}"
                    # レベルに関係なく、達成したら今日のカレンダーにシールを1回分カウント
                    today_date_str = datetime.now().strftime("%Y/%m/%d")
                    add_sticker_for_date(today_date_str)
                else:
                    st.error("⚠️ 達成する目標を上のメニューから選んでください！")

            # 褒め言葉の表示エリア
            if st.session_state.praise_message:
                st.success(st.session_state.praise_message)

            # 瓶のビジュアル表示
            st.write("")
            current_count = len(st.session_state.jar_candies)
            capacity = st.session_state.jar_capacity

            st.markdown(f"### 🏺 現在の瓶の中身 （{current_count} / {capacity} 個）")

            with st.container(border=True):
                if current_count == 0:
                    st.write("瓶はまだ空っぽです。お菓子を選んで入れてね！")
                else:
                    st.markdown(
                        render_candy_jar_svg(st.session_state.jar_candies, capacity),
                        unsafe_allow_html=True,
                    )

            # 満杯判定
            if current_count >= capacity:
                st.markdown("## 🎉 おめでとう！！°˖✧◝(⁰▿⁰)◜✧˖°")
                st.balloons()
                st.success(f"素晴らしい！！！{capacity}個のお菓子瓶が完全に満杯になりました！！！")
                # 満杯演出はページを開くたびに何度も鳴らさず、初めて満杯になった時だけ鳴らす
                if not st.session_state.jar_full_sound_played:
                    play_jar_full_sound()  # 歓声と拍手.mp3
                    st.session_state.jar_full_sound_played = True
                    # カレンダーに表示するための「瓶完成」ログを1件追加（中身のスナップショットも保存）
                    st.session_state.jar_complete_log.append({
                        "date": datetime.now().strftime("%Y/%m/%d %H:%M"),
                        "capacity": capacity,
                        "size_label": JAR_SIZE_LABELS.get(capacity, "?"),
                        "candies": st.session_state.jar_candies.copy(),  # 「今までの瓶」表示用のスナップショット
                    })
                    # 新しい瓶をゼロから始められるようにリセット
                    st.session_state.jar_candies = []
                    # 次にまた満杯になった時に演出が出せるよう、フラグも戻しておく
                    st.session_state.jar_full_sound_played = False

            st.progress(min(current_count / capacity, 1.0))

            st.write("")
            if st.button("🗄️ 今までの瓶", key="toggle_past_jars"):
                play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
                st.session_state.show_past_jars = not st.session_state.show_past_jars

            if st.session_state.show_past_jars:
                if not st.session_state.jar_complete_log:
                    st.info("まだ完成した瓶はありません。最初の1本を完成させよう！")
                else:
                    st.markdown("#### 🏺 完成した瓶たち")
                    # 新しいものから順に表示
                    for jar_record in reversed(st.session_state.jar_complete_log):
                        jar_size_text = jar_record.get(
                            "size_label", JAR_SIZE_LABELS.get(jar_record.get("capacity"), "?")
                        )
                        jar_date_text = jar_record.get("date", "")
                        past_candies = jar_record.get("candies", [])
                        with st.expander(f"🍯 {jar_date_text}　お菓子のビン({jar_size_text})完成✨", expanded=False):
                            if past_candies:
                                st.markdown(
                                    render_candy_jar_svg(past_candies, jar_record.get("capacity", 30)),
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.caption("（この瓶の中身データは記録されていません）")

        # 👉 右側に飴ボタンを配置！
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
                        play_click_sound()  # ここで音を鳴らしてから少し待ってrerun
                        current_time_str = datetime.now().strftime("%Y/%m/%d %H:%M")

                        if len(st.session_state.jar_candies) < st.session_state.jar_capacity:
                            new_candy = {
                                "emoji": candy["emoji"],
                                "date": current_time_str,
                                "task": st.session_state.last_completed_task
                            }
                            st.session_state.jar_candies.append(new_candy)
                            # カレンダーの日別ログ用に、瓶が完成してリセットされても消えない全期間ログにも記録
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

    # 【ランニングページ】
    elif st.session_state.page == "running_page":
        st.title("🏃‍♂️ ランニングステージ")

        # 現在選んでいる相棒を表示
        if st.session_state.companion:
            comp = COMPANIONS[st.session_state.companion]
            st.markdown(f"#### 🐾 現在の相棒：{comp['emoji']} {comp['name']}")
        else:
            st.caption("🐾 まだ相棒が選ばれていません（右下の「相棒選択」から選べます）")

        st.write("走りたいステージを選んでください：")
        st.write("")

        # RUNNING_COURSES の設定から、tier（初級/中級/上級）ごとにグループ分けする
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
                        if st.button(
                            f"🏃\n\n{course['name']}",
                            use_container_width=True,
                            key=f"run_{course_key}",
                        ):
                            if course["ready"]:
                                play_click_sound()
                                st.session_state.active_course_key = course_key
                                st.session_state.page = "running_course_page"
                                st.rerun()
                            else:
                                play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
                                st.info(f"🚧 {tier} {course['name']} は現在準備中です！お楽しみに！")

        # 👉 右下に「相棒選択」ボタンを配置
        st.write("---")
        spacer_col, button_col = st.columns([3, 1])
        with button_col:
            if st.button("🐾 相棒選択", use_container_width=True, key="open_companion_picker"):
                play_click_sound(delay=0)  # このボタンではrerunしないので待機不要
                st.session_state.show_companion_picker = not st.session_state.show_companion_picker

        # 相棒選択UI（ボタンを押すと開閉する）
        if st.session_state.show_companion_picker:
            st.markdown("### 🐾 一緒に走る相棒を選んでね！")
            comp_cols = st.columns(3)
            for col, (comp_key, comp_data) in zip(comp_cols, COMPANIONS.items()):
                with col:
                    st.markdown(
                        f"<div style='text-align:center; font-size:64px;'>{comp_data['emoji']}</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        comp_data["name"],
                        use_container_width=True,
                        key=f"pick_companion_{comp_key}",
                    ):
                        play_click_sound()
                        st.session_state.companion = comp_key
                        st.session_state.show_companion_picker = False
                        st.rerun()

    # ─── 【🏃 一歩村一周コース（ランニング初級ステージ1）】 ───
    elif st.session_state.page == "running_course_page":
        course_key = st.session_state.active_course_key
        course = RUNNING_COURSES[course_key]
        distance_goal = course["distance"]

        st.title(f"🏃‍♂️ {course['name']}")
        st.write(f"全長 **{distance_goal}km** ！目標を達成してゴールを目指そう！")

        # 選んでいる相棒を表示（一緒に走ってくれるイメージ）
        if st.session_state.companion:
            comp = COMPANIONS[st.session_state.companion]
            st.markdown(
                f"<div style='font-size:20px;'>{comp['emoji']} <b>{comp['name']}</b> が一緒に走っています！</div>",
                unsafe_allow_html=True,
            )
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
            selected_course_target_title = st.selectbox(
                "🎯 どの目標を達成した？", course_target_titles, key=f"course_target_select_{course_key}"
            )

            selected_course_target_data = next(
                t for t in st.session_state.target_list if t["title"] == selected_course_target_title
            )

            course_level_options = []
            for lv, task in selected_course_target_data["tasks"].items():
                lv_num = lv.split(".")[1]
                course_level_options.append(f"{lv}: {task} (🏃×{lv_num}km進む)")

            selected_course_level_str = st.selectbox(
                "⭐ どのレベルをクリアした？", course_level_options, key=f"course_level_select_{course_key}"
            )

            course_chosen_lv_key = selected_course_level_str.split(":")[0]  # "Lv.1"
            course_chosen_km = int(course_chosen_lv_key.split(".")[1])  # 1〜5

        st.write("")

        # 達成ボタン！
        if st.button("➕ この1歩を達成した！", type="primary", key=f"course_achieve_button_{course_key}"):
            if selected_course_target_title:
                play_achieve_sound()  # クイズ正解1.mp3

                current_km = st.session_state.course_km.get(course_key, 0)

                # 進む距離を加算（ゴールを超えないようにする）
                new_total_km = min(current_km + course_chosen_km, distance_goal)
                st.session_state.course_km[course_key] = new_total_km

                # メッセージの決定：
                # Lv.5だけは特別な「追い風」メッセージ、
                # 残り1/3くらいならラストスパート系、それ以外は通常の励まし文言からランダム
                if course_chosen_km == 5:
                    message = "🌬️ 絶好調！追い風が来た！一気に5km進んだよ！"
                elif new_total_km >= distance_goal * (2 / 3):
                    message = random.choice(COURSE_LATE_PRAISE_WORDS)
                else:
                    message = random.choice(COURSE_PRAISE_WORDS)

                # コース設定にボーナスがあれば、20%の確率で追加の距離が発生する
                bonus_km, bonus_message = maybe_apply_bonus(course_key)
                total_km_for_log = course_chosen_km
                if bonus_km:
                    boosted_km = min(st.session_state.course_km[course_key] + bonus_km, distance_goal)
                    st.session_state.course_km[course_key] = boosted_km
                    message = f"{message}\n\n{bonus_message}"
                    total_km_for_log += bonus_km

                # 相棒が選ばれていれば、その子の性格に合ったセリフを追加
                if st.session_state.companion:
                    comp_info = COMPANIONS[st.session_state.companion]
                    comp_line = random.choice(COMPANION_MESSAGES[st.session_state.companion])
                    message = f"{message}\n\n{comp_info['emoji']} {comp_info['name']}「{comp_line}」"

                st.session_state.course_praise_message[course_key] = message

                # カレンダー画面用：走った記録を保存（一緒に走った相棒の名前も記録）
                course_task_text = selected_course_target_data["tasks"][course_chosen_lv_key]
                companion_name = COMPANIONS[st.session_state.companion]["name"] if st.session_state.companion else None
                st.session_state.course_run_log.append({
                    "date": datetime.now().strftime("%Y/%m/%d %H:%M"),
                    "course": course["name"],
                    "km": total_km_for_log,
                    "task": f"【{selected_course_target_title} - {course_chosen_lv_key}】 {course_task_text}",
                    "companion": companion_name,
                })

                # レベルに関係なく、達成したら今日のカレンダーにシールを1回分カウント
                today_date_str = datetime.now().strftime("%Y/%m/%d")
                add_sticker_for_date(today_date_str)
            else:
                st.error("⚠️ 達成する目標を上のメニューから選んでください！")

        # 励ましメッセージの表示
        if st.session_state.course_praise_message.get(course_key):
            st.success(st.session_state.course_praise_message[course_key])

        # 進捗表示
        current_km = st.session_state.course_km.get(course_key, 0)
        st.write("")
        st.markdown(f"### 🗺️ 現在の走行距離：{current_km} / {distance_goal} km")
        st.progress(min(current_km / distance_goal, 1.0))

        # ゴール達成判定
        if current_km >= distance_goal:
            st.markdown("## 🎉 ゴール達成！おめでとう！！")
            st.balloons()
            st.success(f"素晴らしい！！！『{course['name']}』を走りきりました！！！")
            if not st.session_state.course_complete_sound_played.get(course_key, False):
                play_jar_full_sound()  # 歓声と拍手.mp3
                st.session_state.course_complete_sound_played[course_key] = True
                # カレンダー画面用：完走の記録を保存（初めて達成した時だけ）
                st.session_state.course_complete_log.append({
                    "date": datetime.now().strftime("%Y/%m/%d %H:%M"),
                    "course": course["name"],
                })
                # 相棒が選ばれていれば、完走専用のお祝いセリフを1つ選んで固定保存
                if st.session_state.companion:
                    complete_line = random.choice(COMPANION_COMPLETE_MESSAGES[st.session_state.companion])
                    st.session_state.course_complete_companion_message[course_key] = complete_line

            # 相棒のお祝いセリフを表示（完走のたびに変わらないよう、保存された内容を表示）
            if st.session_state.companion and course_key in st.session_state.course_complete_companion_message:
                comp_info = COMPANIONS[st.session_state.companion]
                comp_line = st.session_state.course_complete_companion_message[course_key]
                st.info(f"{comp_info['emoji']} {comp_info['name']}「{comp_line}」")

# =====================================================
# 💾 自動セーブ
# =====================================================
# タイトル画面で「はじめから／つづきから」を選んだ後（game_started=True）だけ、
# 画面が更新されるたびに進捗を save_data.json へ書き出す。
# これにより、ブラウザを閉じたりStreamlitを再起動しても「つづきから」で再開できる。
if st.session_state.get("game_started"):
    save_progress()