"""
Streamlit 学習用Webアプリ
- Google Sheetsからデータ読み込み
- 4択クイズモード
- マッチングゲーム（神経衰弱）
- 学習履歴のLocalStorage永続化
- Googleカレンダー連携
"""

import streamlit as st
import random
import json
import time
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Google Sheets / Calendar imports (graceful fallback for local dev)
# ---------------------------------------------------------------------------
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    from googleapiclient.discovery import build as build_google_service
    GCAL_AVAILABLE = True
except ImportError:
    GCAL_AVAILABLE = False

try:
    from streamlit_js_eval import streamlit_js_eval
    JS_EVAL_AVAILABLE = True
except ImportError:
    JS_EVAL_AVAILABLE = False

# ---------------------------------------------------------------------------
# ページ設定
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="学習アプリ",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# カスタムCSS（スマホ最適化）
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ---------- 全体 ---------- */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;600;700&display=swap');

html, body, [class*="st-"] {
    font-family: 'Noto Sans JP', sans-serif;
}

section[data-testid="stSidebar"] {
    background-color: #f8f9fa;
    border-right: 1px solid #ddd;
}
section[data-testid="stSidebar"] * {
    color: #333333 !important;
}
section[data-testid="stSidebar"] input, 
section[data-testid="stSidebar"] select, 
section[data-testid="stSidebar"] div[data-baseweb="select"] span {
    color: #333333 !important;
}

/* サイドバー開閉ボタンにテキストを追加 */
button[kind="header"]::after {
    content: "設定表示";
    color: #ffffff;
    font-size: 0.8rem;
    font-weight: bold;
    margin-left: 8px;
    vertical-align: middle;
}

/* ---------- ボタン共通 ---------- */
div.stButton > button {
    width: 100%;
    min-height: 56px;
    font-size: 1.1rem;
    font-weight: 600;
    border-radius: 14px;
    border: none;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(0,0,0,0.10);
}
div.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.18);
}
div.stButton > button:active {
    transform: translateY(0);
}

/* ---------- クイズ選択肢ボタン ---------- */
.quiz-option button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    min-height: 64px !important;
    font-size: 1.15rem !important;
    margin-bottom: 8px;
}
.quiz-option button:hover {
    background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
}

/* ---------- 正解/不正解 ---------- */
.correct-answer {
    background: #e3f2fd; /* 薄い青 */
    color: #333333;
    padding: 20px;
    border-radius: 16px;
    text-align: center;
    font-size: 1.3rem;
    font-weight: 700;
    margin: 16px 0;
    box-shadow: 0 4px 12px rgba(0,200,81,0.3);
    animation: popIn 0.3s ease;
}
.wrong-answer {
    background: #ffebee; /* 薄い赤 */
    color: #333333;
    padding: 20px;
    border-radius: 16px;
    text-align: center;
    font-size: 1.3rem;
    font-weight: 700;
    margin: 16px 0;
    box-shadow: 0 4px 12px rgba(255,68,68,0.3);
    animation: popIn 0.3s ease;
}

@keyframes popIn {
    0% { transform: scale(0.8); opacity: 0; }
    100% { transform: scale(1); opacity: 1; }
}

/* ---------- マッチングゲームカード ---------- */
.match-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    max-width: 400px;
    margin: 0 auto;
    padding: 8px;
}
.match-card {
    aspect-ratio: 1;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    padding: 6px;
    text-align: center;
    word-break: break-all;
    line-height: 1.2;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    min-height: 72px;
}
.match-card-hidden {
    background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); /* 薄い青紫グラデーション */
    color: #333333;
}
.match-card-hidden:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 16px rgba(102,126,234,0.4);
}
.match-card-revealed {
    background: linear-gradient(135deg, #fdfbf7 0%, #fff1eb 100%); /* ほぼ白に近い肌色 */
    color: #333333;
    border: 2px solid #f093fb;
}
.match-card-matched {
    background: #e0e0e0; /* シンプルなグレー */
    color: #777;
    opacity: 0.7;
    pointer-events: none;
}
.match-card-invisible {
    visibility: hidden;
}

/* ---------- 学習履歴の色分け ---------- */
.history-correct {
    background-color: #e3f2fd !important;
    border-left: 4px solid #2196F3;
    padding: 8px 12px;
    border-radius: 8px;
    margin: 4px 0;
}
.history-wrong {
    background-color: #ffebee !important;
    border-left: 4px solid #f44336;
    padding: 8px 12px;
    border-radius: 8px;
    margin: 4px 0;
}

/* ---------- スコアカード ---------- */
.score-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 24px;
    border-radius: 20px;
    text-align: center;
    margin: 16px 0;
    box-shadow: 0 8px 24px rgba(102,126,234,0.3);
}
.score-card h2 {
    margin: 0;
    font-size: 2.5rem;
}
    margin: 4px 0 0;
    font-size: 1.1rem;
    font-weight: 600;
    opacity: 1;
}

/* ---------- ヘッダー ---------- */
.app-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 20px;
    text-align: center;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px rgba(102,126,234,0.25);
}
.app-header h1 {
    margin: 0;
    font-size: 1.6rem;
}
.app-header p {
    margin: 4px 0 0;
    opacity: 1;
    font-size: 1rem;
    font-weight: 600;
}

/* ---------- タイマー ---------- */
.timer-display {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    color: #00f5d4;
    font-size: 2rem;
    font-weight: 700;
    text-align: center;
    padding: 16px;
    border-radius: 16px;
    font-family: 'Courier New', monospace;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    margin: 12px 0;
}

/* ---------- レスポンシブ ---------- */
@media (max-width: 480px) {
    .match-card {
        font-size: 0.72rem;
        min-height: 64px;
        padding: 4px;
    }
    .match-grid {
        gap: 6px;
    }
}
</style>
""", unsafe_allow_html=True)


# ===================================================================
# データ読み込み
# ===================================================================

# 新しい読み込み関数（URL指定版）
@st.cache_data(ttl=300)
def load_data_by_url(url: str) -> list[dict]:
    """指定されたURLのGoogle Sheetsからデータを読み込む。"""
    if not GSPREAD_AVAILABLE or not url:
        return []
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)

        sh = gc.open_by_url(url)
        worksheet = sh.sheet1
        rows = worksheet.get_all_values()

        data = []
        for row in rows:
            if len(row) >= 2 and row[0].strip() and row[1].strip():
                item = {"front": row[0].strip(), "back": row[1].strip()}
                
                # 3～5列目は「誤答の選択肢」として扱う
                wrong_choices = [c.strip() for c in row[2:5] if len(row) > 2 and c.strip()]
                if wrong_choices:
                    item["wrong_choices"] = wrong_choices
                
                # 6列目があれば「解説」として扱う
                if len(row) >= 6 and row[5].strip():
                    item["explanation"] = row[5].strip()

                data.append(item)

        if data and data[0]["front"].lower() in ("表", "front", "おもて", "question"):
            data = data[1:]

        return data
    except Exception as e:
        st.error(f"データ読み込みエラー ({url}): {e}")
        return []

@st.cache_data(ttl=300)
def load_data_from_sheets() -> list[dict]:
    """(旧互換) secrets.spreadsheet_url から読み込む"""
    url = st.secrets.get("spreadsheet_url", "")
    return load_data_by_url(url)


def get_sample_data() -> list[dict]:
    """ローカル開発用サンプルデータ。"""
    return [
        {"front": "Apple", "back": "りんご"},
        {"front": "Dog", "back": "犬"},
        {"front": "Cat", "back": "猫"},
        {"front": "Book", "back": "本"},
        {"front": "Water", "back": "水"},
        {"front": "Fire", "back": "火"},
        {"front": "Mountain", "back": "山"},
        {"front": "River", "back": "川"},
        {"front": "Sky", "back": "空"},
        {"front": "Earth", "back": "地球"},
        {"front": "Sun", "back": "太陽"},
        {"front": "Moon", "back": "月"},
        {"front": "Star", "back": "星"},
        {"front": "Tree", "back": "木"},
        {"front": "Flower", "back": "花"},
        {"front": "Bird", "back": "鳥"},
    ]


def load_data(url: str = "") -> list[dict]:
    if url:
        return load_data_by_url(url)
    
    # URL指定がない場合は古い方式（spreadsheet_url）を試す
    data = load_data_from_sheets()
    if data:
        return data
    return get_sample_data()

# --- フラッシュカードモード ---
def flashcard_mode(data: list[dict]):
    st.markdown("### ⚡ フラッシュカード")
    
    if "fc_order" not in st.session_state or len(st.session_state.fc_order) != len(data):
        st.session_state.fc_index = 0
        st.session_state.fc_flipped = False
        # ランダム順にするためにインデックスリストを作成
        indices = list(range(len(data)))
        random.shuffle(indices)
        st.session_state.fc_order = indices

    # 全問終了チェック
    if st.session_state.fc_index >= len(data):
        st.markdown(
            '<div style="text-align:center; padding:40px 0;">'
            '<h2>🎉 一通り学習しました！</h2>'
            '</div>', 
            unsafe_allow_html=True
        )
        if st.button("🔄 最初からやり直す", use_container_width=True):
            st.session_state.fc_index = 0
            st.session_state.fc_flipped = False
            random.shuffle(st.session_state.fc_order)
            st.rerun()
        return

    current_data_idx = st.session_state.fc_order[st.session_state.fc_index]
    item = data[current_data_idx]
    
    # カード表示
    card_content = item["back"] if st.session_state.fc_flipped else item["front"]
    bg_color = "#e8f0fe" if st.session_state.fc_flipped else "#ffffff"
    text_color = "#1a73e8" if st.session_state.fc_flipped else "#000000"
    label = "答えを見る (Flip)" if not st.session_state.fc_flipped else "問題に戻る"

    # カード UI
    st.markdown(
        f"""
        <div style="
            border: 2px solid #ddd;
            border-radius: 12px;
            padding: 60px 20px;
            text-align: center;
            margin-bottom: 20px;
            background-color: {bg_color};
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
            <div style="color: {text_color}; margin: 0; font-size: clamp(1.5rem, 5vw, 2.5rem); font-weight: bold;">{card_content}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 操作ボタン
    col1, col2 = st.columns(2)
    with col1:
        if st.button("arrows_rotate", help="カードを裏返す", key="flip_btn", use_container_width=True):
            st.session_state.fc_flipped = not st.session_state.fc_flipped
            st.rerun()
    
    # レイアウト調整：反転ボタンを大きく
    if st.button(label, use_container_width=True, type="primary"):
        st.session_state.fc_flipped = not st.session_state.fc_flipped
        st.rerun()

    st.write("") # Spacer

    # 進行ボタン
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ まだ (Next)", use_container_width=True):
            st.session_state.fc_index += 1
            st.session_state.fc_flipped = False
            st.rerun()
    with c2:
        if st.button("⭕ 覚えた！ (Next)", use_container_width=True):
            add_history_record(item["front"], True)
            st.session_state.fc_index += 1
            st.session_state.fc_flipped = False
            st.session_state._ls_counter += 1
            st.rerun()
            
    st.caption(f"進捗: {st.session_state.fc_index + 1} / {len(data)}")


# ===================================================================
# LocalStorage ヘルパー
# ===================================================================
LS_KEY = "quiz_app_history"


def load_history_from_ls() -> list[dict]:
    """LocalStorage から学習履歴を読み込む。"""
    if not JS_EVAL_AVAILABLE:
        return None  # JSが使えない場合はNoneを返す（ロード未完了扱い）
    try:
        raw = streamlit_js_eval(
            js_expressions=f"localStorage.getItem('{LS_KEY}')",
            key=f"ls_load_{st.session_state.get('_ls_counter', 0)}",
        )
        if raw and isinstance(raw, str):
            return json.loads(raw)
        if raw is None:
             return None # まだロードできていない
    except Exception:
        pass
    return []


def save_history_to_ls(history: list[dict]):
    """LocalStorage へ学習履歴を保存する。"""
    if not JS_EVAL_AVAILABLE:
        return
    try:
        data_json = json.dumps(history, ensure_ascii=False)
        # エスケープ処理
        escaped = data_json.replace("\\", "\\\\").replace("'", "\\'")
        streamlit_js_eval(
            js_expressions=f"localStorage.setItem('{LS_KEY}', '{escaped}')",
            key=f"ls_save_{st.session_state.get('_ls_counter', 0)}",
        )
    except Exception:
        pass


def add_history_record(word: str, correct: bool):
    """履歴レコードを追加して保存。"""
    jst = timezone(timedelta(hours=9))
    record = {
        "word": word,
        "correct": correct,
        "timestamp": datetime.now(jst).isoformat(),
    }
    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append(record)
    save_history_to_ls(st.session_state.history)


def get_word_status(word: str) -> str | None:
    """直近の学習結果を返す ('correct' / 'wrong' / None)。"""
    history = st.session_state.get("history", [])
    for rec in reversed(history):
        if rec["word"] == word:
            return "correct" if rec["correct"] else "wrong"
    return None


# ===================================================================
# Googleカレンダー連携
# ===================================================================
def register_to_calendar(summary: str, description: str = ""):
    """学習完了をGoogleカレンダーに登録する。"""
    if not GCAL_AVAILABLE:
        st.warning("Google Calendar APIライブラリがインストールされていません。")
        return False

    try:
        scopes = ["https://www.googleapis.com/auth/calendar.events"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build_google_service("calendar", "v3", credentials=creds)

        calendar_id = st.secrets.get("calendar_id", "primary")
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": now.isoformat(),
                "timeZone": "Asia/Tokyo",
            },
            "end": {
                "dateTime": (now + timedelta(minutes=30)).isoformat(),
                "timeZone": "Asia/Tokyo",
            },
        }

        service.events().insert(calendarId=calendar_id, body=event).execute()
        return True
    except Exception as e:
        st.error(f"カレンダー登録に失敗しました: {e}")
        return False


# ===================================================================
# セッションステート初期化
# ===================================================================
def init_session_state():
    if "history_loaded" not in st.session_state:
        st.session_state.history_loaded = False
        st.session_state.history = []

    if not st.session_state.history_loaded:
        loaded_data = load_history_from_ls()
        if loaded_data is not None:
            # ロード成功（空リスト含む）
            st.session_state.history = loaded_data
            st.session_state.history_loaded = True
            st.rerun() # リロードして反映
        else:
            # ロード中...（次回rerunを待つ）
            st.stop()
        
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state._ls_counter = 0

        # クイズ用
        st.session_state.quiz_question = None
        st.session_state.quiz_options = []
        st.session_state.quiz_answered = False
        st.session_state.quiz_correct = False
        st.session_state.quiz_score = 0
        st.session_state.quiz_total = 0
        st.session_state.quiz_pool = None
        st.session_state.quiz_finished = False
        # マッチング用
        st.session_state.match_cards = []
        st.session_state.match_revealed = []
        st.session_state.match_matched = set()
        st.session_state.match_first = None
        st.session_state.match_start_time = None
        st.session_state.match_finished = False
        st.session_state.match_elapsed = 0
        st.session_state.match_attempts = 0


init_session_state()


def filter_and_slice_data(data: list[dict], limit_str: str, filter_mastered: bool) -> list[dict]:
    """設定に基づいてデータをフィルタリングおよびスライスする。"""
    if not data:
        return []

    # 1. 習熟度フィルター
    filtered = list(data)
    if filter_mastered:
        # 正解履歴があるものを除外（get_word_statusが 'correct' のもの）
        filtered = [d for d in filtered if get_word_status(d["front"]) != "correct"]
    
    # 2. ランダムシャッフル & スライス
    # セッション内で一貫性を保つため、session_state にキャッシュする
    
    # 現在の設定状況を表すキー
    current_key = f"{st.session_state.get('current_deck_url')}_{limit_str}_{filter_mastered}_length{len(data)}"
    
    # キャッシュがない、またはキーが変わった場合は再生成
    if "session_data_cache" not in st.session_state or st.session_state.get("session_cache_key") != current_key:
        # シャッフル
        random.shuffle(filtered)
        
        # スライス
        if limit_str != "すべて":
            try:
                limit = int(limit_str.replace("問", ""))
                filtered = filtered[:limit]
            except ValueError:
                pass
        
        st.session_state.session_data_cache = filtered
        st.session_state.session_cache_key = current_key
        
        # クイズ・フラッシュカードの状態もリセット（データが変わったため）
        st.session_state.quiz_pool = None
        st.session_state.quiz_question = None
        st.session_state.quiz_finished = False
        st.session_state.quiz_total = 0
        st.session_state.quiz_score = 0
        
        st.session_state.fc_index = 0
        st.session_state.fc_flipped = False
        st.session_state.fc_order = []
        
        st.session_state.match_finished = False
        st.session_state.match_cards = []

    return st.session_state.session_data_cache


# ===================================================================
# 4択クイズモード
# ===================================================================
def generate_quiz(data: list[dict]):
    """新しいクイズ問題を生成する。"""
    if len(data) < 4:
        st.error("データが4件以上必要です。")
        return

    # プールがNoneなら補充（初回のみ、またはリセット後）
    if st.session_state.quiz_pool is None and not st.session_state.quiz_finished:
        st.session_state.quiz_pool = list(data)
        random.shuffle(st.session_state.quiz_pool)

    # 次の問題を取り出す
    if st.session_state.quiz_pool:
        question_item = st.session_state.quiz_pool.pop(0)
    else:
        # 全ての問題を解き終わった
        st.session_state.quiz_finished = True
        st.session_state.quiz_question = None
        return

    # スプレッドシートに固定の誤答が設定されているか確認
    fixed_wrongs = question_item.get("wrong_choices", [])
    
    if len(fixed_wrongs) >= 3:
        # 固定の誤答をそのまま使用
        wrong_items_text = fixed_wrongs[:3]
    else:
        # 足りない分、または全てを従来通りランダムに生成
        wrong_pool = [d for d in data if d["front"] != question_item["front"]]
        # 既に固定値がある場合はそれを除外対象にする（重複防止）
        wrong_pool = [d for d in wrong_pool if d["back"] not in fixed_wrongs]
        
        needed = 3 - len(fixed_wrongs)
        sampled = random.sample(wrong_pool, min(needed, len(wrong_pool)))
        wrong_items_text = fixed_wrongs + [w["back"] for w in sampled]

    options = [question_item["back"]] + wrong_items_text
    random.shuffle(options)

    st.session_state.quiz_question = question_item
    st.session_state.quiz_options = options
    st.session_state.quiz_answered = False
    st.session_state.quiz_correct = False


def quiz_mode(data: list[dict]):
    """4択クイズの表示・ロジック。"""
    # 全問終了時の画面
    if st.session_state.get("quiz_finished"):
        st.balloons()
        st.markdown(
            '<div style="text-align:center; padding:40px 20px;">'
            '<h1 style="font-size:3rem;">🎉</h1>'
            '<h2>お疲れ様でした！全問終了です</h2>'
            '<p style="font-size:1.2rem; color:#333; font-weight:600; margin-bottom:30px;">スプレッドシートにある全ての問題を学習しました。</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        
        # 最終スコア
        total = st.session_state.quiz_total
        score = st.session_state.quiz_score
        if total > 0:
            rate = int(score / total * 100)
            st.markdown(
                f'<div class="score-card" style="margin-bottom:40px;">'
                f'<h2>最終結果: {score} / {total}</h2>'
                f'<p>正答率 {rate}%</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if st.button("🔄 最初から挑戦する", use_container_width=True):
            st.session_state.quiz_finished = False
            st.session_state.quiz_total = 0
            st.session_state.quiz_score = 0
            st.session_state.quiz_pool = None
            st.session_state.quiz_question = None
            st.rerun()
        return

    st.markdown("### 🎯 4択クイズ")
    st.caption("表示された言葉の意味を4つの選択肢から選んでください。")

    # 問題がなければ生成
    if st.session_state.quiz_question is None:
        generate_quiz(data)

    q = st.session_state.quiz_question
    if q is None:
        return

    # 問題文の色分け
    word_status = get_word_status(q["front"])
    status_class = ""
    if word_status == "correct":
        status_class = "history-correct"
    elif word_status == "wrong":
        status_class = "history-wrong"

    # スコア計算 (表示は回答後のみ)
    total = st.session_state.quiz_total
    score = st.session_state.quiz_score

    # 未回答時のみ、上部に問題を表示（スコアは表示しない）
    if not st.session_state.quiz_answered:

        st.markdown(
            f'<div class="{status_class}" style="text-align:center; padding:24px; '
            f'border-radius:16px; margin:16px 0;">'
            f'<span style="font-size: clamp(1.2rem, 4vw, 2rem); font-weight:700;">{q["front"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # 回答済みなら結果表示
    if st.session_state.quiz_answered:
        # 画面トップへスクロール
        if JS_EVAL_AVAILABLE:
            streamlit_js_eval(
                js_expressions="parent.window.scrollTo(0, 0)",
                key=f"scroll_top_{st.session_state.get('_ls_counter', 0)}"
            )

        # 1. 正解/不正解
        if st.session_state.quiz_correct:
            st.markdown(
                f'<div class="correct-answer">⭕ 正解！ — {q["back"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="wrong-answer">❌ 不正解… 正解は「{q["back"]}」</div>',
                unsafe_allow_html=True,
            )

        # 2. 解説があれば表示
        if "explanation" in q and q["explanation"]:
            st.info(f"💡 解説: {q['explanation']}")

        # 3. 次へボタン
        if st.button("▶️ 次の問題", key="next_q", use_container_width=True):
            generate_quiz(data)
            st.rerun()

        # 4. 問題文 (再掲)
        st.markdown(
            f'<div class="{status_class}" style="text-align:center; padding:24px; '
            f'border-radius:16px; margin:16px 0;">'
            f'<span style="font-size: clamp(1.2rem, 4vw, 2rem); font-weight:700;">{q["front"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 5. スコア (再掲)
        if total > 0:
            rate = int(score / total * 100)
            st.markdown(
                f'<div class="score-card">'
                f'<h2>{score} / {total}</h2>'
                f'<p>正答率 {rate}%</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
        return

    # 選択肢ボタン
    for i, option in enumerate(st.session_state.quiz_options):
        col_class = "quiz-option"
        st.markdown(f'<div class="{col_class}">', unsafe_allow_html=True)
        if st.button(option, key=f"opt_{i}", use_container_width=True):
            correct = option == q["back"]
            st.session_state.quiz_answered = True
            st.session_state.quiz_correct = correct
            st.session_state.quiz_total += 1
            if correct:
                st.session_state.quiz_score += 1
            add_history_record(q["front"], correct)
            st.session_state._ls_counter += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ===================================================================
# マッチングゲーム（神経衰弱）
# ===================================================================
def init_matching_game(data: list[dict], num_pairs: int = 8):
    """マッチングゲームを初期化する。"""
    st.session_state.match_cleared_pairs = st.session_state.get("match_cleared_pairs", set())
    
    # 候補データの抽出（習熟度フィルタ済みデータから、さらにクリア済みを除外）
    available_data = [d for d in data if d['front'] not in st.session_state.match_cleared_pairs]
    
    if len(available_data) < num_pairs:
        # 足りない場合
        if len(data) >= num_pairs:
            # 元データなら足りる -> リセット提案
            st.warning(f"未クリアのペアが足りません（残り{len(available_data)}ペア）。リセットしてください。")
            return
        else:
            # 元データ自体が足りない
            st.error(f"マッチングゲームには{num_pairs}件以上のデータが必要です。")
            return

    pairs = random.sample(available_data, num_pairs)
    cards = []
    for p in pairs:
        cards.append({"id": f"f_{p['front']}", "text": p["front"], "pair_key": p["front"], "side": "front"})
        cards.append({"id": f"b_{p['front']}", "text": p["back"], "pair_key": p["front"], "side": "back"})

    random.shuffle(cards)

    st.session_state.match_cards = cards
    st.session_state.match_revealed = [False] * (num_pairs * 2)
    st.session_state.match_matched = set()
    st.session_state.match_first = None
    st.session_state.match_start_time = time.time()
    st.session_state.match_finished = False
    st.session_state.match_elapsed = 0
    st.session_state.match_attempts = 0


def matching_game(data: list[dict], num_pairs: int = 8):
    """マッチングゲーム（神経衰弱）の表示・ロジック。"""
    st.markdown("### 🧩 マッチングゲーム")
    total_cards = num_pairs * 2
    st.caption(f"表と裏のペアを見つけてください。{num_pairs}組{total_cards}枚のカードをめくります。")

    # 初期化ボタンエリア
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 新しいゲーム", key="new_match", use_container_width=True):
            init_matching_game(data, num_pairs)
            st.rerun()
    with col_b:
        # 重複リセットボタン
        cleared_count = len(st.session_state.get("match_cleared_pairs", set()))
        if st.button(f"🗑️ 重複履歴リセット ({cleared_count})", key="reset_match_history", use_container_width=True, help="このセッションでクリアしたペアの除外を解除します"):
            st.session_state.match_cleared_pairs = set()
            st.success("重複防止履歴をリセットしました")
            time.sleep(0.5)
            st.rerun()

    # カード枚数が変わった場合などの再初期化チェック
    if not st.session_state.match_cards or len(st.session_state.match_cards) != total_cards:
        init_matching_game(data, num_pairs)
        st.rerun()

    cards = st.session_state.match_cards
    revealed = st.session_state.match_revealed
    matched = st.session_state.match_matched

    # ゲーム完了チェック
    if len(matched) == total_cards and not st.session_state.match_finished:
        st.session_state.match_finished = True
        st.session_state.match_elapsed = time.time() - st.session_state.match_start_time

    # タイマー表示
    if st.session_state.match_finished:
        elapsed = st.session_state.match_elapsed
        st.markdown(
            f'<div class="timer-display">🎉 クリア！ {elapsed:.1f}秒 '
            f'（{st.session_state.match_attempts}回）</div>',
            unsafe_allow_html=True,
        )
        if st.button("📅 カレンダーに記録", key="cal_match", use_container_width=True):
            ok = register_to_calendar(
                summary="📚 学習完了（マッチングゲーム）",
                description=f"クリアタイム: {elapsed:.1f}秒 / 試行回数: {st.session_state.match_attempts}回",
            )
            if ok:
                st.success("カレンダーに登録しました！")
        
        # 完了メッセージと次へボタン
        st.markdown(
            f"""
            <div style="
                background-color: #e3f2fd; 
                color: #333; 
                padding: 1rem; 
                border-radius: 10px; 
                text-align: center; 
                margin-bottom: 1rem; 
                border: 2px solid #2196F3;
            ">
                <h3 style="margin:0; color:#1565C0;">🎉 クリア！おめでとうございます！</h3>
                <p style="margin:0.5rem 0 0 0; font-weight:bold;">タイム: {elapsed:.1f}秒 / 試行: {st.session_state.match_attempts}回</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # 次へボタン
        if st.button("➡️ 次のゲームへ", key="next_match_btn", type="primary", use_container_width=True):
            # 今回クリアしたペアを記録
            current_pairs = {card['pair_key'] for card in st.session_state.match_cards}
            st.session_state.match_cleared_pairs = st.session_state.get("match_cleared_pairs", set()) | current_pairs
            
            # 再初期化
            init_matching_game(data, num_pairs)
            st.rerun()

    else:
        if st.session_state.match_start_time:
            elapsed = time.time() - st.session_state.match_start_time
            with col_b:
                st.markdown(
                    f'<div class="timer-display">⏱️ {elapsed:.0f}秒</div>',
                    unsafe_allow_html=True,
                )

    # グリッド描画 (レスポンシブな列数計算)
    # 6枚(3ペア) -> 3列x2行
    # 8枚(4ペア) -> 4列x2行
    # 12枚(6ペア) -> 4列x3行 (or 3x4)
    # 16枚(8ペア) -> 4列x4行
    
    if num_pairs == 3:
        cols_count = 3
    elif num_pairs == 4:
        cols_count = 4 # 2行
    elif num_pairs == 6:
        cols_count = 3 # 4行 (スマホだと3列が良い)
    else: # 8ペア
        cols_count = 4

    rows_count = (total_cards + cols_count - 1) // cols_count
    
    for row in range(rows_count):
        cols = st.columns(cols_count, gap="small")
        for col_idx in range(cols_count):
            idx = row * cols_count + col_idx
            if idx >= len(cards):
                break
                
            card = cards[idx]
            with cols[col_idx]:
                if idx in matched:
                    # マッチ済み: テキスト表示（色反転などで分かりやすく）
                    st.button(f"⭕ {card['text']}", key=f"m_{idx}", disabled=True, use_container_width=True)
                elif revealed[idx]:
                    # 表向き: 色付きボタン
                    word_status = get_word_status(card["pair_key"])
                    label = card["text"]
                    st.button(label, key=f"m_{idx}", disabled=True, use_container_width=True)
                else:
                    # 裏向き
                    if st.button("❓", key=f"m_{idx}", use_container_width=True):
                        handle_card_click(idx)
                        st.rerun()


def handle_card_click(idx: int):
    """カードクリック時のロジック。"""
    cards = st.session_state.match_cards
    revealed = st.session_state.match_revealed
    matched = st.session_state.match_matched

    if idx in matched or revealed[idx]:
        return

    if st.session_state.match_first is None:
        # 1枚目
        revealed[idx] = True
        st.session_state.match_first = idx
    else:
        # 2枚目
        first_idx = st.session_state.match_first
        revealed[idx] = True
        st.session_state.match_attempts += 1

        first_card = cards[first_idx]
        second_card = cards[idx]

        if (first_card["pair_key"] == second_card["pair_key"]
                and first_card["side"] != second_card["side"]):
            # ペア成立
            matched.add(first_idx)
            matched.add(idx)
            st.session_state.match_matched = matched
            add_history_record(first_card["pair_key"], True)
        else:
            # ペア不成立 → 両方裏に戻す
            revealed[first_idx] = False
            revealed[idx] = False
            if first_card["pair_key"] != second_card["pair_key"]:
                add_history_record(first_card["pair_key"], False)
                add_history_record(second_card["pair_key"], False)

        st.session_state.match_first = None
        st.session_state.match_revealed = revealed
        st.session_state._ls_counter += 1


# ===================================================================
# 学習履歴パネル
# ===================================================================
def history_panel():
    """学習履歴を表示する。"""
    st.markdown("### 📊 学習履歴")

    history = st.session_state.get("history", [])
    if not history:
        st.info("まだ学習履歴がありません。クイズやマッチングゲームで学習を始めましょう！")
        return

    # 統計
    total = len(history)
    correct = sum(1 for h in history if h["correct"])
    wrong = total - correct
    rate = int(correct / total * 100) if total > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("合計", f"{total}問")
    c2.metric("正解", f"{correct}問", delta=f"{rate}%")
    c3.metric("不正解", f"{wrong}問")

    st.divider()

    # 直近の履歴（最新20件）
    recent = list(reversed(history[-20:]))
    for rec in recent:
        css_class = "history-correct" if rec["correct"] else "history-wrong"
        icon = "✅" if rec["correct"] else "❌"
        ts = rec.get("timestamp", "")
        # 日時を短縮表示
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                ts = dt.strftime("%m/%d %H:%M")
            except Exception:
                pass
        st.markdown(
            f'<div class="{css_class}">'
            f'{icon} <b>{rec["word"]}</b>'
            f'<span style="float:right; opacity:1; font-weight:600; color:#333; font-size:0.9rem;">{ts}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # カレンダー登録
    if st.button("📅 学習セッションをカレンダーに記録", key="cal_hist", use_container_width=True):
        ok = register_to_calendar(
            summary="📚 学習完了",
            description=f"合計{total}問 / 正解{correct}問 / 正答率{rate}%",
        )
        if ok:
            st.success("カレンダーに登録しました！")

    # 履歴クリア
    if st.button("🗑️ 履歴をクリア", key="clear_hist", use_container_width=True):
        st.session_state.history = []
        save_history_to_ls([])
        st.session_state._ls_counter += 1
        st.rerun()


# ===================================================================
# メイン
# ===================================================================
def main():
    # サイドバーで機能切り替え
    with st.sidebar:
        st.title("メニュー")
        
        # デッキ選択
        deck_options = {}
        # 1. 既存の設定があれば「メイン」として追加
        default_url = st.secrets.get("spreadsheet_url", "")
        if default_url:
            deck_options["メイン"] = default_url

        # 2. [decks] セクションがあれば追加
        if "decks" in st.secrets:
            for name, info in st.secrets["decks"].items():
                # 辞書ライクならOK（isinstance(dict)だとAttrDictで弾かれる可能性があるため）
                if "url" in info:
                    deck_options[name] = info["url"]
        
        # 3. URL直接入力オプションを追加
        # 選択肢のリストを作成（順序保証のため）
        options_keys = list(deck_options.keys())
        options_keys.append("🔗 URL直接入力")
        deck_options["🔗 URL直接入力"] = "DIRECT_INPUT"

        # デッキ選択メニュー
        selected_deck_name = st.selectbox("問題集 (デッキ)", options_keys, key="deck_selector")
        
        if selected_deck_name == "🔗 URL直接入力":
            selected_deck_url = st.text_input("スプレッドシートのURLを入力してください")
        else:
            selected_deck_url = deck_options[selected_deck_name]
        
        
        # DEBUG: デッキ読み込み状況を確認 (不要になったためコメントアウト)
        # with st.expander("Debug Info (Deck Config)"):
        #     st.write("options_keys", options_keys)
        #     st.write("deck_options", deck_options)
        #     st.write("secrets.decks", st.secrets.get("decks", "Not Found"))

        mode = st.radio("学習モード", ["4択クイズ", "フラッシュカード", "マッチングゲーム", "学習履歴"])
        
        st.divider()
        st.caption("セッション設定")
        
        # 出題数の制限
        limit_options = ["すべて", "10問", "20問", "30問"]
        selected_limit = st.radio("1回の出題数", limit_options, index=1, horizontal=True)
        
        # 習熟度フィルター
        filter_mastered = st.checkbox("覚えた（正解した）問題を除外", value=False)
        
        # マッチングゲーム設定（モードがマッチングの時のみ表示、または常時表示）
        # ここではシンプルに常時表示し、モード切り替え時に適用されるようにする
        match_pairs = 8
        if mode == "マッチングゲーム":
            st.caption("マッチングゲーム設定")
            match_pairs = st.select_slider(
                "カードの枚数（ペア数）",
                options=[3, 4, 6, 8],
                value=8,
                format_func=lambda x: f"{x * 2}枚 ({x}ペア)"
            )
        
        st.divider()
        st.caption("設定")
        if st.button("学習履歴をリセット"):
            if JS_EVAL_AVAILABLE:
                st.session_state.history = []
                # LocalStorageもクリア
                streamlit_js_eval(
                    js_expressions=f"localStorage.removeItem('{LS_KEY}')",
                    key=f"ls_clear_{st.session_state.get('_ls_counter', 0)}"
                )
                st.session_state._ls_counter += 1
                st.success("履歴を削除しました")

    # デッキ変更または設定変更検知
    current_settings = f"{selected_deck_url}_{selected_limit}_{filter_mastered}_{match_pairs}"
    if st.session_state.get("current_settings") != current_settings:
        st.session_state.current_settings = current_settings
        st.session_state.quiz_pool = None
        st.session_state.quiz_question = None
        st.session_state.quiz_finished = False
        st.session_state.quiz_total = 0
        st.session_state.quiz_score = 0
        
        st.session_state.fc_index = 0
        st.session_state.fc_flipped = False
        st.session_state.fc_order = []
        
        st.session_state.match_finished = False
        st.session_state.match_cards = []
        # session_data_cache もリセット（filter_and_slice_data内で再生成される）
        if "session_cache_key" in st.session_state:
            del st.session_state.session_cache_key

    # データ読み込み
    data = load_data(selected_deck_url)
    if not data:
        st.error("データを読み込めませんでした。")
        return

    # データをフィルタリング & スライス
    filtered_data = filter_and_slice_data(data, selected_limit, filter_mastered)

    if not filtered_data:
        st.warning("条件に一致する問題がありません（全て正解済み、またはデータ自体が空です）。")
        if filter_mastered:
            st.info("「覚えた問題を除外」のチェックを外すと、復習ができます。")
        return

    # モード分岐
    if mode == "4択クイズ":
        quiz_mode(filtered_data)
    elif mode == "フラッシュカード":
        flashcard_mode(filtered_data)
    elif mode == "マッチングゲーム":
        # マッチングは全データからランダムの方がゲームとして成立しやすいが、
        # 要望に合わせてフィルタ済みデータを使う（数が少なすぎる場合は警告などが必要かも）
        # -> 指定ペア数以上のデータが必要
        if len(filtered_data) < match_pairs:
             st.warning(f"マッチングゲーム（{match_pairs}ペア）には少なくとも{match_pairs}件のデータが必要です。フィルタ条件を緩和してください。")
        else:
             matching_game(filtered_data, match_pairs)
    elif mode == "学習履歴":
        history_panel()

if __name__ == "__main__":
    main()
