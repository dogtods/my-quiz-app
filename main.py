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
import re
import time
import urllib.parse
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

# Gemini AI: SDKの代わりにrequestsで直接REST APIを呼ぶ（ライブラリ依存なし）
import requests as _requests
GEMINI_AVAILABLE = True  # requestsは常に使えるのでTrue固定
GEMINI_ERROR = None

TARGET_SHEET_NAME = "{ここにシート名を記入}"

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
    min-height: 64px !important;
    font-size: 1.15rem !important;
    margin-bottom: 0px !important;
}
/* ボタン全体の上下マージンを少し詰める（スマホ用） */
.stButton {
    margin-bottom: -0.5rem;
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

                # 7列目があれば「メモ/参考URL」として扱う
                if len(row) >= 7 and row[6].strip():
                    item["notes"] = row[6].strip()
                
                # 8列目があれば「非表示」フラグとして扱う (TRUE, true, 1, などの場合は非表示)
                if len(row) >= 8 and row[7].strip().lower() in ("true", "1", "hidden", "非表示"):
                    item["hidden"] = True
                else:
                    item["hidden"] = False

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
        # 終了時にフラッシュ
        flush_history_to_sheets()
        
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
            
    # 非表示ボタン
    if st.button("🗑️ この問題を非表示にする", key="fc_hide", use_container_width=True, help="この問題をスプレッドシート上で非表示に設定し、出題対象から除外します"):
        if save_hidden_to_sheet(item["front"]):
            st.success("問題を非表示にしました")
            time.sleep(1)
            st.rerun()
            
             
    st.caption(f"進捗: {st.session_state.fc_index + 1} / {len(data)}")

    # 中断して保存ボタン
    st.divider()
    if st.button("💾 中断して保存 (Save & Quit)", use_container_width=True):
        flush_history_to_sheets()
        # 状態リセットしてトップ(ようなもの)へ戻る、あるいはrerun
        st.session_state.fc_index = 0
        st.session_state.fc_flipped = False
        st.session_state.fc_order = []
        st.success("学習内容を保存しました。最初の画面に戻ります。")
        time.sleep(1)
        st.rerun()


# ===================================================================
# LocalStorage ヘルパー
# ===================================================================
LS_KEY = "quiz_app_history"


def load_history_from_sheets() -> list[dict]:
    """スプレッドシートの 'History' シートから履歴を読み込む。"""
    try:
        url = st.session_state.get("current_deck_url") or st.secrets.get("spreadsheet_url")
        if not url:
            return []
            
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(url)
        worksheet = sh.worksheet("History")
        rows = worksheet.get_all_values()
        
        if not rows or len(rows) < 2:
            return []
            
        # ヘッダー除去
        data_rows = rows[1:]
        history = []
        for r in data_rows:
            if len(r) >= 3:
                history.append({
                    "timestamp": r[0],
                    "word": r[1],
                    "correct": (r[2] == "Correct")
                })
        return history
    except Exception:
        return []

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
    """履歴レコードを追加して保存（LocalStorage + Google Sheets）。"""
    jst = timezone(timedelta(hours=9))
    timestamp = datetime.now(jst).isoformat()
    record = {
        "word": word,
        "correct": correct,
        "timestamp": timestamp,
    }
    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append(record)
    
    # LocalStorage保存
    save_history_to_ls(st.session_state.history)
    
    # Google Sheets保存 (バッチ処理に変更: 10件ごとに flush)
    if "pending_history" not in st.session_state:
        st.session_state.pending_history = []
    
    st.session_state.pending_history.append(record)
    
    if len(st.session_state.pending_history) >= 10:
        flush_history_to_sheets()

def flush_history_to_sheets():
    """保留中の履歴をスプレッドシートに一括保存する。"""
    try:
        pending = st.session_state.get("pending_history", [])
        if not pending:
            return

        url = st.session_state.get("current_deck_url") or st.secrets.get("spreadsheet_url")
        if not url:
            return
            
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        sh = client.open_by_url(url)
        
        # Historyシートの取得または作成
        try:
            worksheet = sh.worksheet("History")
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="History", rows=1000, cols=3)
            worksheet.append_row(["Timestamp", "Word", "Correct"])
            
        # 一括追記
        rows_to_add = []
        for r in pending:
            rows_to_add.append([
                r["timestamp"],
                r["word"],
                "Correct" if r["correct"] else "Wrong"
            ])
        
        if rows_to_add:
            worksheet.append_rows(rows_to_add)
            
        # クリア
        st.session_state.pending_history = []
        st.toast("学習履歴を保存しました！", icon="✅")
        
    except Exception as e:
        st.error(f"スプレッドシートへの保存に失敗しました: {e}")


def save_notes_to_sheet(front: str, notes: str):
    """7列目（メモ/参考URL）をスプレッドシートに保存する。"""
    try:
        url = st.session_state.get("current_deck_url") or st.secrets.get("spreadsheet_url")
        if not url:
            return False
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(url)
        worksheet = sh.sheet1
        # 対象行を検索
        cell = worksheet.find(front, in_column=1)
        if cell:
            worksheet.update_cell(cell.row, 7, notes)
            # キャッシュクリア（シートデータキャッシュとセッションデータキャッシュの両方）
            st.cache_data.clear()
            # st.session_state.pop(key, None) # 停止：クイズ状態維持のため
            return True
        return False
    except Exception as e:
        if "403" in str(e):
            client_email = st.secrets.get("gcp_service_account", {}).get("client_email", "不明")
            st.error(f"⚠️ スプレッドシートの権限エラー (403)\n\nこの機能を使うには、スプレッドシートの画面右上の「共有」ボタンから、以下のメールアドレスを「編集者」として追加してください：\n\n`{client_email}`")
        else:
            st.error(f"メモの保存に失敗しました: {e}")
        return False


def save_explanation_to_sheet(front: str, explanation: str):
    """6列目（解説）をスプレッドシートに追記する。"""
    try:
        url = st.session_state.get("current_deck_url") or st.secrets.get("spreadsheet_url")
        if not url:
            return False
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(url)
        worksheet = sh.sheet1
        cell = worksheet.find(front, in_column=1)
        if cell:
            existing = worksheet.cell(cell.row, 6).value or ""
            new_val = (existing + "\n" + explanation).strip() if existing else explanation
            worksheet.update_cell(cell.row, 6, new_val)
            # キャッシュクリア（シートデータキャッシュとセッションデータキャッシュの両方）
            st.cache_data.clear()
            # st.session_state.pop(key, None) # 停止：クイズ状態維持のため
            return True
        return False
    except Exception as e:
        if "403" in str(e):
            client_email = st.secrets.get("gcp_service_account", {}).get("client_email", "不明")
            st.error(f"⚠️ スプレッドシートの権限エラー (403)\n\nこの機能を使うには、スプレッドシートの画面右上の「共有」ボタンから、以下のメールアドレスを「編集者」として追加してください：\n\n`{client_email}`")
        else:
            st.error(f"解説の保存に失敗しました: {e}")
        return False


def save_hidden_to_sheet(front: str):
    """8列目（非表示フラグ）をスプレッドシートに保存する。"""
    try:
        url = st.session_state.get("current_deck_url") or st.secrets.get("spreadsheet_url")
        if not url:
            return False
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(url)
        worksheet = sh.sheet1
        # 対象行を検索
        cell = worksheet.find(front, in_column=1)
        if cell:
            worksheet.update_cell(cell.row, 8, "TRUE")
            # キャッシュクリア（データの再読み込みを強制）
            st.cache_data.clear()
            if "session_cache_key" in st.session_state:
                del st.session_state.session_cache_key
            return True
        return False
    except Exception as e:
        st.error(f"非表示設定の保存に失敗しました: {e}")
        return False


def _call_gemini(prompt: str, api_key: str) -> str:
    """Gemini REST APIを共通呼び出し関数（検索連携あり・リトライ処理付き）。"""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-flash-lite-latest:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}]
    }
    
    max_retries = 3
    for i in range(max_retries):
        try:
            resp = _requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except _requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            if status_code in [429, 500, 503, 504] and i < max_retries - 1:
                # 指数バックオフ (2, 4, 8秒)
                wait_time = (2 ** (i + 1))
                time.sleep(wait_time)
                continue
            
            # エラーメッセージの日本語化
            if status_code == 429:
                raise Exception("AIの利用制限に達しました。少し時間を置いてから再度お試しください。")
            elif status_code == 503:
                raise Exception("AIサーバーが一時的に混み合っています。数分後に再度お試しください。")
            elif status_code in [500, 504]:
                raise Exception("AIサーバーでエラーが発生しました。時間を置いて再度お試しください。")
            else:
                raise Exception(f"通信エラーが発生しました (Status: {status_code})")
        except _requests.exceptions.RequestException as e:
            if i < max_retries - 1:
                time.sleep(2)
                continue
            raise Exception(f"ネットワーク接続エラーが発生しました: {e}")
    
    raise Exception("AIからの応答が得られませんでした。")


def render_mermaid(code: str):
    """Mermaidコードをmermaid.ink経由で画像として表示する。"""
    import base64
    encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii")
    img_url = f"https://mermaid.ink/img/{encoded}"
    st.image(img_url, use_container_width=True)


def ai_generate_notes(front: str, back: str, custom_prompt: str = "") -> str:
    """[Button 1] 正解の理由と記憶のコツを簡潔に解説。またはユーザーのカスタムプロンプトを実行。"""
    api_key = st.secrets.get("gemini_api_key", "")
    if not api_key:
        return ""
    try:
        if custom_prompt.strip():
            prompt = (
                f"以下のクイズの設問と正解について、次の指示または質問に答えてください：\n"
                f"指示・質問：{custom_prompt}\n\n"
                f"設問: {front}\n"
                f"正解: {back}\n"
            )
        else:
            prompt = (
                f"以下のクイズの設問と正解を見て、日本語で解説を準備してください。3行程度で簡潔に、初心者でもわかるようにかみ砕いて：\n"
                f"「なぜこの回答なのか」「認識のポイント」「記憶のコツ」を含めてください。\n\n"
                f"設問: {front}\n"
                f"正解: {back}\n"
            )
        return _call_gemini(prompt, api_key)
    except Exception as e:
        st.error(f"AI解説の取得に失敗しました: {e}")
        return ""


def ai_explain_options(front: str, back: str, options: list[str]) -> str:
    """[Button 2] 全選択肢（正解・誤選択肢両方）の意味を解説。"""
    api_key = st.secrets.get("gemini_api_key", "")
    if not api_key:
        return ""
    try:
        options_text = "\n".join([f"-  {opt}" for opt in options])
        prompt = (
            f"以下のクイズの全選択肢を見て、各選択肢の意味、正解との違いを日本語で解説してください。\n"
            f"各選択肢に2行程度で説明してください。\n\n"
            f"設問: {front}\n"
            f"正解: {back}\n"
            f"選択肢:\n{options_text}\n"
        )
        return _call_gemini(prompt, api_key)
    except Exception as e:
        st.error(f"他の回答解説の取得に失敗しました: {e}")
        return ""


def ai_generate_diagram(front: str, back: str) -> str:
    """[Button 3] 設問の概念をテキストベース（ASCII/記号）の図解として生成。"""
    api_key = st.secrets.get("gemini_api_key", "")
    if not api_key:
        return ""
    try:
        prompt = (
            f"以下のクイズの設問と正解から、概念の関係性やプロセスを「テキストベースの図解」として作成してください。\n"
            f"特殊記号（→, ↴, ┝, ┃, ━, ┌, ┐, └, ┘）やASCII文字を使って、シンプルに文字だけで構造を表現してください。\n"
            f"画像やコード（Mermaid等）は不要です。文字だけで視覚的にわかる図にしてください。\n\n"
            f"設問: {front}\n"
            f"正解: {back}\n"
        )
        return _call_gemini(prompt, api_key)
    except Exception as e:
        st.error(f"図解の生成に失敗しました: {e}")
        return ""


def get_current_sheet_title() -> str:
    """現在のスプレッドシートのタイトル（ファイル名）を取得する"""
    if "current_sheet_title" in st.session_state:
        return st.session_state.current_sheet_title
    
    try:
        url = st.session_state.get("current_deck_url") or st.secrets.get("spreadsheet_url")
        if not url:
            return "専門分野"
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(url)
        st.session_state.current_sheet_title = sh.title
        return sh.title
    except Exception:
        return "専門分野"

def ai_generate_new_quiz(mode: str, question_item: dict, target_sheet_name: str) -> dict | None:
    api_key = st.secrets.get("gemini_api_key", "")
    if not api_key:
        return None
        
    term = question_item["front"]
    definition = question_item["back"]

    # --- モード別の切り口（1行で本質を伝える） ---
    mode_instructions = {
        "feynman": "切り口：実務で通じるビジネス比喩を用いて概念の本質を問え。幼稚な例えは禁止。",
        "client": "切り口：顧客の「なぜ必要？どう使う？」に答える形、または適用不可の例外を問え。",
        "objection": "切り口：顧客が『他社でも同じことを言われた』と反論した場面。この概念で関心を奪い返す最も鋭い問い返しを選ばせよ。",
        "context_switch": "切り口：担当者には定義通りに説明し納得を得た。次にROI重視のCFOへ伝える際、強調の優先順位をどう組み替えるかを問え。",
        "pre_mortem": "切り口：この概念を盲信して提案し大失注した。見落とした『制約条件』は何かを問え。",
    }

    prompt = (
        f"『{target_sheet_name}』の専門トレーナーとして、実戦的な4択クイズを作成せよ。\n"
        f"用語: {term}\n定義: {definition}\n\n"
        f"【重要】この用語と定義を核としつつ、必要に応じて一般的なビジネス知識や実例を用いて、現実味のある問い（コンテキスト）に補完すること。\n"
        f"ただし、出題の意図が元の定義から逸脱しないように注意せよ。\n\n"
        f"{mode_instructions.get(mode, mode_instructions['client'])}\n\n"
        f"条件:\n"
        f"- 誤答3つは専門家も一瞬迷う実務的な罠にせよ\n"
        f"- hint: 用語の核心メリットを20字以内で\n"
        f"- explanation: 正解が信頼を勝ち取る理由を心理学的根拠や実例と共に記載\n\n"
        f"JSON以外出力禁止。```不要。\n"
        '{"question":"","correct":"","wrong1":"","wrong2":"","wrong3":"","hint":"","explanation":""}'
    )

    try:
        resp = _call_gemini(prompt, api_key)
        # Markdownのコードブロックや余計な会話文を取り除き、最初の'{'から最後の'}'までを抽出
        match = re.search(r'\{.*\}', resp, re.DOTALL)
        if match:
            clean_resp = match.group(0)
            return json.loads(clean_resp)
        else:
            st.error("AIの生成結果からJSONを抽出できませんでした。")
            return None
    except json.JSONDecodeError as e:
        st.error(f"AIの生成データの形式(JSON)に誤りがありました: {e}")
        return None
    except Exception as e:
        st.error(f"問題生成に失敗しました: {e}")
        return None

def append_quiz_to_sheet(quiz_data: dict) -> bool:
    try:
        url = st.session_state.get("current_deck_url") or st.secrets.get("spreadsheet_url")
        if not url:
            return False
            
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(url)
        worksheet = sh.sheet1
        
        # A, B, C, D, E列に追記
        row_data = [
            quiz_data["question"],
            quiz_data["correct"],
            quiz_data["wrong1"],
            quiz_data["wrong2"],
            quiz_data["wrong3"],
            quiz_data.get("explanation", ""),
            quiz_data.get("hint", "")
        ]
        worksheet.append_row(row_data)
        
        # Google Sheetsへの追記後にキャッシュをクリアする
        st.cache_data.clear()
        return True
    except Exception as e:
        if "403" in str(e):
            client_email = st.secrets.get("gcp_service_account", {}).get("client_email", "不明")
            st.error(f"⚠️ スプレッドシートの権限エラー (403)\\n\\nこの機能を使うには、スプレッドシートの画面右上の「共有」ボタンから、以下のメールアドレスを「編集者」として追加してください：\\n\\n`{client_email}`")
        else:
            st.error(f"スプレッドシートへの追記に失敗しました: {e}")
        return False


def ai_generate_keywords(front: str) -> list[str]:
    """Geminiを用いて設問から重要なキーワードを抽出する。"""
    api_key = st.secrets.get("gemini_api_key", "")
    if not api_key:
        return []
    try:
        prompt = (
            f"以下のクイズの設問から、Google検索に役立つ重要なキーワード（専門用語、固有名詞など）を3〜5個抽出してください。"
            f"結果はカンマ区切りのみの形式で出力してください。\n\n"
            f"設問: {front}"
        )
        resp = _call_gemini(prompt, api_key)
        # カンマやスペース、改行で分割してリスト化
        keywords = [k.strip() for k in resp.replace("\n", ",").split(",") if k.strip()]
        return keywords
    except Exception:
        return []


def extract_keywords(text: str, n: int = 2) -> list[str]:
    """設問テキストからキーとなる語を最大n件抽出する（AIなし・コストゼロ）。"""
    # 句読点・かっこ・助詞パターンで分割
    parts = re.split(r'[。、,，.．\s　「」『』（）()【】〔〕・…ー\-\+\?？！!：:；;]', text)
    tokens = [p.strip() for p in parts if len(p.strip()) >= 2]
    # 「の/は/が/を/に/で/と/も/か/や/へ/から/まで/より/だ/です/ます」等のひらがなのみトークンを除外
    stop_hiragana = re.compile(r'^[ぁ-ん]{1,3}$')
    tokens = [t for t in tokens if not stop_hiragana.match(t)]
    # 重複削除・長さ降順ソートで上位n件
    seen = set()
    unique = []
    for t in sorted(tokens, key=len, reverse=True):
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:n]


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
# ===================================================================
# Googleカレンダー連携 (Webリンク生成)
# ===================================================================
def create_calendar_link(summary: str, description: str = "") -> str:
    """Googleカレンダーへの登録リンクを生成する。"""
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    start_time = now.strftime("%Y%m%dT%H%M%S")
    end_time = (now + timedelta(minutes=30)).strftime("%Y%m%dT%H%M%S")
    
    base_url = "https://www.google.com/calendar/render"
    params = {
        "action": "TEMPLATE",
        "text": summary,
        "details": description,
        "dates": f"{start_time}/{end_time}",
        "ctz": "Asia/Tokyo",
    }
    query = urllib.parse.urlencode(params)
    return f"{base_url}?{query}"


# ===================================================================
# セッションステート初期化
# ===================================================================
def init_session_state():
    if "history_loaded" not in st.session_state:
        st.session_state.history_loaded = False
        st.session_state.history = []

    # JSが反応しない場合のタイムアウト処理
    if not st.session_state.history_loaded:
        # リトライ回数管理
        if "history_retry_count" not in st.session_state:
            st.session_state.history_retry_count = 0
        
        st.session_state.history_retry_count += 1
        
        loaded_data = load_history_from_ls()
        if loaded_data is not None:
            # ロード成功
            st.session_state.history = loaded_data
            st.session_state.history_loaded = True
            st.rerun()
        else:
            # ロード失敗/待機中
            if st.session_state.history_retry_count > 2:
                # 2回リトライしてもダメなら諦めて空で進める（無限ループ防止）
                st.warning("履歴データの読み込みに失敗しました。新規セッションとして開始します。")
                st.session_state.history = []
                st.session_state.history_loaded = True
                # st.rerun() # ここでrerunすると無限ループの恐れがあるのでそのまま進める
            else:
                # 少し待ってからリロード（stopして再度実行されるのを期待）
                with st.spinner("学習履歴を読み込んでいます..."):
                     time.sleep(1.0)
                st.rerun()

    # Google Sheetsからの履歴読み込み（バックアップとして結合、または初期ロード）
    if st.session_state.history_loaded and not st.session_state.get("sheets_history_loaded", False):
        try:
            sheets_history = load_history_from_sheets()
            if sheets_history:
                # 既存の履歴を (timestamp, word) のセットにして重複チェック
                existing_keys = set()
                for r in st.session_state.history:
                     # timestampが無い古いデータへの考慮
                     ts = r.get("timestamp", "")
                     wd = r.get("word", "")
                     existing_keys.add((ts, wd))
                
                for rec in sheets_history:
                    # 重複していなければ追加
                    ts = rec.get("timestamp", "")
                    wd = rec.get("word", "")
                    if (ts, wd) not in existing_keys:
                        st.session_state.history.append(rec)
                        existing_keys.add((ts, wd))
                
                # 並び替え（古い順->新しい順）
                st.session_state.history.sort(key=lambda x: x.get("timestamp", ""))
                
            st.session_state.sheets_history_loaded = True
            if sheets_history:
                st.toast(f"シートから {len(sheets_history)} 件の履歴を統合しました", icon="📊")
        except Exception as e:
            # st.error(f"DEBUG: Sheets Load Error: {e}") # 本番用は非表示
            pass

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

    if "pending_history" not in st.session_state:
        st.session_state.pending_history = []


init_session_state()


def filter_and_slice_data(data: list[dict], limit_str: str, filter_mastered: bool, mastered_rate: int = 20) -> list[dict]:
    """設定に基づいてデータをフィルタリングおよびスライスする。"""
    if not data:
        return []

    # 0. 非表示フィルター
    data = [d for d in data if not d.get("hidden", False)]
    if not data:
        return []

    # 1. 習熟度フィルター
    if filter_mastered:
        # 正解履歴がないもの（未習熟）
        unmastered = [d for d in data if get_word_status(d["front"]) != "correct"]
        # 正解履歴があるもの（既習）
        mastered = [d for d in data if get_word_status(d["front"]) == "correct"]
        
        # 既習問題から指定割合をランダムに混ぜる
        num_mastered_to_include = max(1, len(mastered) * mastered_rate // 100) if mastered and mastered_rate > 0 else 0
        sampled_mastered = random.sample(mastered, min(num_mastered_to_include, len(mastered)))
        
        filtered = unmastered + sampled_mastered
    else:
        filtered = list(data)
    
    # 2. ランダムシャッフル & スライス
    # セッション内で一貫性を保つため、session_state にキャッシュする
    
    # 現在の設定状況を表すキー
    current_key = f"{st.session_state.get('current_deck_url')}_{limit_str}_{filter_mastered}_{mastered_rate}_len{len(data)}"
    
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
        
        if "next_forced_quiz" in st.session_state:
            fq = st.session_state.pop("next_forced_quiz")
            st.session_state.quiz_question = {
                "front": fq["question"],
                "back": fq["correct"],
                "wrong_choices": [fq["wrong1"], fq["wrong2"], fq["wrong3"]],
                "explanation": fq.get("explanation", ""),
                "notes": fq.get("hint", "")
            }
            options = [fq["correct"], fq["wrong1"], fq["wrong2"], fq["wrong3"]]
            random.shuffle(options)
            st.session_state.quiz_options = options
            st.session_state.quiz_answered = False
            st.session_state.quiz_correct = False
            st.session_state.quiz_finished = False
            # 生成によるリロード時はスコアをリセットせず維持する
        else:
            st.session_state.quiz_question = None
            st.session_state.quiz_finished = False
            # 通常のリセット時のみスコアを0に戻す
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
        # 終了時にフラッシュ
        flush_history_to_sheets()
        
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
            f'border-radius:16px; margin:16px 0; background-color: #ffffff; border: 1px solid #eee;">'
            f'<span style="font-size: clamp(1.2rem, 4vw, 2rem); font-weight:700; color: black;">{q["front"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # ヒントの表示 (Notes/7列目にヒントが格納されている想定)
        hint_text = q.get("notes", "")
        if hint_text:
            st.info(f"💡 ヒント: {hint_text}")

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
        c_next, c_hide = st.columns([2, 1])
        with c_next:
            if st.button("▶️ 次の問題", key="next_q", use_container_width=True, type="primary"):
                generate_quiz(data)
                st.rerun()
        with c_hide:
            if st.button("🗑️ 非表示", key="quiz_hide", use_container_width=True, help="この問題を非表示にして除外します"):
                if save_hidden_to_sheet(q["front"]):
                    st.success("非表示にしました")
                    time.sleep(1)
                    generate_quiz(data)
                    st.rerun()

        # 4. 問題文 (再掲) - 黒文字に変更
        st.markdown(
            f'<div class="{status_class}" style="text-align:center; padding:24px; '
            f'border-radius:16px; margin:16px 0; background-color: #ffffff;">'
            f'<span style="font-size: clamp(1.2rem, 4vw, 2rem); font-weight:700; color: black;">{q["front"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        
        # 4.5 選択肢の再表示（復活）
        st.caption("選択肢:")
        for opt in st.session_state.quiz_options:
            if opt == q["back"]:
                st.info(f"⭕ {opt}")
            elif opt == st.session_state.get("quiz_selected_option"):
                st.error(f"❌ {opt}")
            else:
                st.text(f"・ {opt}")

        # --- AI機能（メモ欄より上に配置） ---
        gemini_api_key = st.secrets.get("gemini_api_key", "")
        if GEMINI_AVAILABLE and gemini_api_key:
            st.divider()
            
            # カスタムプロンプト入力欄
            custom_prompt_key = f"custom_prompt_{q['front']}"
            custom_prompt = st.text_input("🤖 AIへの追加の指示・質問（任意）", placeholder="例：〇〇との違いを教えて", key=custom_prompt_key)

            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("🤖 AI解説", key=f"ai_gen_{q['front']}", use_container_width=True):
                    with st.spinner("AIが解説を生成中..."):
                        ai_text = ai_generate_notes(q["front"], q["back"], custom_prompt)
                    if ai_text:
                        st.session_state[f"ai_result_{q['front']}"] = ai_text

            with col_btn2:
                if st.button("🔍 他も解説", key=f"ai_opts_{q['front']}", use_container_width=True):
                    with st.spinner("AIが選択肢を解説中..."):
                        opts_text = ai_explain_options(
                            q["front"], q["back"],
                            options=st.session_state.get("quiz_options", [])
                        )
                    if opts_text:
                        st.session_state[f"ai_opts_result_{q['front']}"] = opts_text

            with col_btn3:
                if st.button("📊 図解生成", key=f"ai_diag_{q['front']}", use_container_width=True):
                    with st.spinner("AIが図解を生成中..."):
                        diagram_code = ai_generate_diagram(q["front"], q["back"])
                    if diagram_code:
                        st.session_state[f"ai_diagram_{q['front']}"] = diagram_code

        # 6. メモ・参考URL入力欄
        st.divider()
        st.markdown("####  📝 メモ・参考URLメモ")
        st.caption("調べた内容やURLをメモしておくと次回から表示されます。")

        # メモのキャッシュキー
        notes_cache_key = f"notes_{q['front']}"
        ai_pending_key = f"ai_pending_{q['front']}"
        kw_pending_key = f"kw_pending_{q['front']}"
        notes_counter_key = f"notes_counter_{q['front']}"
        if notes_counter_key not in st.session_state:
            st.session_state[notes_counter_key] = 0

        # ペンディングの適用
        for pkey in [ai_pending_key, kw_pending_key]:
            if pkey in st.session_state:
                st.session_state[notes_cache_key] = st.session_state.pop(pkey)
                st.session_state[notes_counter_key] += 1

        if notes_cache_key not in st.session_state:
            st.session_state[notes_cache_key] = q.get("notes", "")

        notes_widget_key = f"notes_area_{q['front']}_{st.session_state[notes_counter_key]}"

        notes_input = st.text_area(
            "メモ入力欄",
            value=st.session_state[notes_cache_key],
            height=120,
            key=notes_widget_key,
            label_visibility="collapsed",
            placeholder="調べた内容、参考にしたURLなどを自由に記入してください...",
        )

        # --- キーワードボタン（順序：選択肢4つ → 抽出キーワード2つ） ---
        all_options = st.session_state.get("quiz_options", [])
        kw_from_q = extract_keywords(q["front"], n=2)
        kw_candidates = all_options + kw_from_q
        if kw_candidates:
            st.caption("🏷️ タップしてメモ欄に追加:")
            kw_cols = st.columns(3)
            for i, kw in enumerate(kw_candidates):
                with kw_cols[i % 3]:
                    if st.button(kw, key=f"kw_memo_btn_{i}_{q['front']}", use_container_width=True):
                        current = st.session_state.get(notes_widget_key, notes_input)
                        sep = "\n" if current.strip() else ""
                        st.session_state[kw_pending_key] = current + sep + kw
                        st.rerun()

        col_save, col_adopt = st.columns(2)
        with col_save:
            if st.button("💾 メモを保存", key=f"save_notes_{q['front']}", use_container_width=True):
                if save_notes_to_sheet(q["front"], notes_input):
                    st.session_state[notes_cache_key] = notes_input
                    st.success("メモを保存しました！")
                else:
                    # シートが見つからなかった場合はセッションのみ保存
                    st.session_state[notes_cache_key] = notes_input
                    st.warning("シートへの保存は失敗しましたが、セッション内に保持しています。")
        with col_adopt:
            if st.button("📝 解説として採用 (列６に追記)", key=f"adopt_expl_{q['front']}", use_container_width=True):
                if notes_input.strip():
                    if save_explanation_to_sheet(q["front"], notes_input):
                        st.success("解説として追記しました！")
                    else:
                        st.error("解説の保存に失敗しました。")
                else:
                    st.warning("メモの内容が空です。")



        # --- AI結果表示セクション ---
        if GEMINI_AVAILABLE and gemini_api_key:
            # 定義：各結果に対して保存ボタンを表示するヘルパー（関数内関数）
            def show_result_with_save_buttons(result_key, title, icon, color_type="info"):
                if result_key in st.session_state:
                    content = st.session_state[result_key]
                    if color_type == "info":
                        st.info(f"{icon} {title}:\n\n{content}")
                    elif color_type == "success":
                        st.success(f"{icon} {title}:\n\n{content}")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("💾 メモとして保存", key=f"save_n_{result_key}_{q['front']}", use_container_width=True):
                            if save_notes_to_sheet(q["front"], content):
                                st.session_state[notes_cache_key] = content
                                # 本体のメモ入力欄ウィジェットを更新するためにカウンターを上げる
                                st.session_state[notes_counter_key] += 1
                                del st.session_state[result_key]
                                st.toast("メモを保存しました！", icon="✅")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("シートへの保存に失敗しました。")
                    with c2:
                        if st.button("📝 解説欄(列6)に保存", key=f"save_e_{result_key}_{q['front']}", use_container_width=True):
                            if save_explanation_to_sheet(q["front"], content):
                                del st.session_state[result_key]
                                st.toast("解説欄に保存しました！", icon="📝")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("解説の保存に失敗しました。")

            # 1. AI解説の結果
            show_result_with_save_buttons(f"ai_result_{q['front']}", "AI解説", "🤖")

            # 2. 他の回答の解説の結果
            show_result_with_save_buttons(f"ai_opts_result_{q['front']}", "選択肢の解説", "🔍", "success")

            # 3. 図解の結果
            show_result_with_save_buttons(f"ai_diagram_{q['front']}", "テキスト図解", "📊")

            # --- AI自動生成セクション ---
            st.divider()
            st.markdown("#### 🪄 この問題からAIで新しく生成")
            st.caption(f"現在の「{q['front']}」について新しい問題を作り、スプレッドシートに自動追記して次へ進みます。")
            
            c_f, c_c = st.columns(2)
            with c_f:
                if st.button("👨‍🏫 ファインマン", help="説明を問う問題を作ります", use_container_width=True):
                    with st.spinner("生成中..."):
                        sheet_title = get_current_sheet_title()
                        quiz_data = ai_generate_new_quiz("feynman", q, sheet_title)
                        if quiz_data and append_quiz_to_sheet(quiz_data):
                            st.success("登録しました！")
                            st.session_state.next_forced_quiz = quiz_data
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()
            with c_c:
                if st.button("👔 クライアント", help="例外や必要性を問う問題を作ります", use_container_width=True):
                    with st.spinner("生成中..."):
                        sheet_title = get_current_sheet_title()
                        quiz_data = ai_generate_new_quiz("client", q, sheet_title)
                        if quiz_data and append_quiz_to_sheet(quiz_data):
                            st.success("登録しました！")
                            st.session_state.next_forced_quiz = quiz_data
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("⚔️ 反論処理", help="NOや疑念への切り返しを問う", use_container_width=True):
                    with st.spinner("生成中..."):
                        sheet_title = get_current_sheet_title()
                        quiz_data = ai_generate_new_quiz("objection", q, sheet_title)
                        if quiz_data and append_quiz_to_sheet(quiz_data):
                            st.success("登録しました！")
                            st.session_state.next_forced_quiz = quiz_data
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()
            with c2:
                if st.button("🔄 コンテキスト", help="相手に応じた使い分けを問う", use_container_width=True):
                    with st.spinner("生成中..."):
                        sheet_title = get_current_sheet_title()
                        quiz_data = ai_generate_new_quiz("context_switch", q, sheet_title)
                        if quiz_data and append_quiz_to_sheet(quiz_data):
                            st.success("登録しました！")
                            st.session_state.next_forced_quiz = quiz_data
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()
            with c3:
                if st.button("📉 失敗逆算", help="誤用や見落としのリスクを問う", use_container_width=True):
                    with st.spinner("生成中..."):
                        sheet_title = get_current_sheet_title()
                        quiz_data = ai_generate_new_quiz("pre_mortem", q, sheet_title)
                        if quiz_data and append_quiz_to_sheet(quiz_data):
                            st.success("登録しました！")
                            st.session_state.next_forced_quiz = quiz_data
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()

        # 6. AI機能の警告表示 (Gemini未設定時など)
        if not (GEMINI_AVAILABLE and gemini_api_key):
            if not GEMINI_AVAILABLE:
                err_msg = GEMINI_ERROR or "不明なエラー"
                st.caption(f"⚠️ AI機能: ライブラリ未ロード — {err_msg}")
            elif not gemini_api_key:
                st.caption("⚠️ AI機能: APIキー未設定 (secrets.toml に gemini_api_key が見つかりません)")

        # --- スコア表示 (解答済み画面の最下部) ---
        total = st.session_state.quiz_total
        score = st.session_state.quiz_score
        if total > 0:
            rate = int(score / total * 100)
            st.markdown(
                f'<div style="text-align:center; margin-top:24px; padding:12px; background:#f0f2f6; border-radius:12px;">'
                f'<h4 style="margin:0;">スコア: {score} / {total} (正答率 {rate}%)</h4>'
                f'</div>',
                unsafe_allow_html=True,
            )
        
        # 解答済み画面の最後で確実に return する
        return
    
    # --- 未解答時の選択肢ボタン表示 ---
    for i, option in enumerate(st.session_state.quiz_options):
        # 4択は gap を狭くする
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
    
    st.divider()
    # 中断して保存ボタン
    if st.button("💾 中断して保存 (Save & Quit)", key="quiz_save_quit", use_container_width=True):
        flush_history_to_sheets()
        st.session_state.quiz_finished = False
        st.session_state.quiz_total = 0
        st.session_state.quiz_score = 0
        st.session_state.quiz_pool = None
        st.session_state.quiz_question = None
        st.success("学習内容を保存しました。最初の画面に戻ります。")
        time.sleep(1)
        st.rerun()


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
            f'{icon} <b style="color:black;">{rec["word"]}</b>'
            f'<span style="float:right; opacity:1; font-weight:600; color:#333; font-size:0.9rem;">{ts}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # カレンダー登録 (リンクボタンに変更)
    summary = "📚 学習完了"
    description = f"合計{total}問 / 正解{correct}問 / 正答率{rate}%"
    link_url = create_calendar_link(summary, description)
    
    st.link_button("📅 カレンダーに登録 (Google Calendar)", link_url, use_container_width=True)

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
    # セッションと履歴の初期化
    init_session_state()

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
        
        # サービスアカウント情報の表示（デバッグ用・権限設定用）
        # try:
        #     sa_email = st.secrets["gcp_service_account"]["client_email"]
        #     with st.expander("🔑 サービスアカウント情報"):
        #         st.caption("スプレッドシートの「共有」に以下を追加してください:")
        #         st.code(sa_email, language=None)
        #         st.caption("※権限は「編集者」に設定")
        # except Exception:
        #     pass
        
        
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
        filter_mastered = st.checkbox("覚えた問題の頻度を下げて出題", value=True)
        mastered_rate = 20
        if filter_mastered:
            mastered_rate = st.slider("既習問題の出現率 (%)", 0, 100, 20, step=5, help="正解済みの問題がどの程度の割合で混ざるかを設定します。0%にすると完全に出なくなります。")
        
        # マッチングゲーム設定
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
                # キャッシュキーも削除して再生成を促す
                if "session_cache_key" in st.session_state:
                    del st.session_state.session_cache_key
                # LocalStorageもクリア
                streamlit_js_eval(
                    js_expressions=f"localStorage.removeItem('{LS_KEY}')",
                    key=f"ls_clear_{st.session_state.get('_ls_counter', 0)}"
                )
                st.session_state._ls_counter += 1
                st.success("履歴を削除しました")

    # デッキ変更または設定変更検知
    current_settings = f"{selected_deck_url}_{selected_limit}_{filter_mastered}_{mastered_rate}_{match_pairs}"
    if st.session_state.get("current_settings") != current_settings:
        st.session_state.current_settings = current_settings
        st.session_state.current_deck_url = selected_deck_url  # デッキURLを更新
        st.session_state.sheets_history_loaded = False         # 切り替え時に履歴を再読み込み
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
    filtered_data = filter_and_slice_data(data, selected_limit, filter_mastered, mastered_rate)

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
