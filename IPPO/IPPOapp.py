import streamlit as st
from datetime import datetime, date
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

JAR_SIZE_LABELS = {30: "S", 50: "M", 100: "L"}


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
