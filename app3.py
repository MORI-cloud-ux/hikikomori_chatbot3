import streamlit as st
from openai import OpenAI
import json
import re
from datetime import date
from supabase import create_client, Client
from pathlib import Path

# --- ✅ アクセス制限パス設定（全体への入口） ---
ACCESS_PASS = "forest2025"

# --- APIキー（Secrets管理） ---
API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=API_KEY)

# --- Supabaseクライアント ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Streamlit UI設定 ---
st.set_page_config(
    page_title="🌿 不登校・ひきこもり相談AIエージェント",
    layout="wide",
)

# ============================================================
# 📚 0. 知識ベースJSONの読み込み（knowledge_base.json）
# ============================================================
@st.cache_data
def load_knowledge_base(path: str = "knowledge_base.json") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"知識ベースJSONが見つかりません: {p.resolve()}\n"
            "アプリ（この.py）と同じフォルダに 'knowledge_base.json' を置いてください。"
        )
    text = p.read_text(encoding="utf-8")
    return json.loads(text)

try:
    knowledge_base = load_knowledge_base("knowledge_base.json")
except Exception as e:
    st.error(f"知識ベースJSONの読み込みに失敗しました: {e}")
    st.stop()

SLOT_SCHEMA = knowledge_base.get("slot_schema", {}) or {}

def default_slots_from_schema(schema: dict) -> dict:
    slots = {}
    for k in schema.keys():
        slots[k] = "不明"
    return slots

# --- カスタムCSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic&display=swap');
body {
    font-family: 'Zen Maru Gothic', sans-serif;
    background: linear-gradient(180deg, #fff7ec 0%, #fff1de 50%, #ffeacf 100%);
    color: #333;
}
.stApp { padding: 2rem; }
h1 {
    color: #2e7d32;
    text-align: center;
    font-weight: 700;
    margin-bottom: 0.3rem;
    font-size: 2.5rem;
}
.stTextArea textarea {
    background-color: #d9f0d9;
    border-radius: 1.2rem;
    border: 1px solid #a8d5a2;
    color: #2e4d32;
    font-size: 1.05rem;
    padding: 0.8rem;
}
.user-bubble {
    background-color: #d0f0c0;
    color: #1b3d1b;
    border-radius: 1rem;
    padding: 0.8rem;
    margin: 0.4rem 0;
    box-shadow: 0px 2px 6px rgba(0,0,0,0.1);
}
.bot-bubble {
    background-color: #e6ffe6;
    color: #2e7d32;
    border-radius: 1rem;
    padding: 0.8rem;
    margin: 0.4rem 0;
    box-shadow: 0px 2px 6px rgba(0,0,0,0.1);
}
.stButton>button {
    background-color: #66bb6a;
    color: white;
    border-radius: 1.5rem;
    border: none;
    padding: 0.6rem 1.2rem;
    font-size: 1rem;
    transition: 0.2s;
}
.stButton>button:hover {
    background-color: #4caf50;
}
footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🔐 1. アクセス用パスワード認証（共通の入口）
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h1>🌿 不登校・ひきこもり相談AIエージェントへようこそ</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#2e7d32;'>アクセスにはパスワードが必要です</p>", unsafe_allow_html=True)
    password_input = st.text_input("🔑 アクセス用パスワードを入力してください", type="password", placeholder="パスワードを入力")
    if st.button("はじめる 🌱"):
        if password_input == ACCESS_PASS:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()

# ============================================================
# 🧑‍💻 2. Supabase ユーザー登録・ログイン
# ============================================================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown("<h1>👥 ログイン / 新規登録</h1>", unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["ログイン", "新規登録"])

    with tab_login:
        login_email = st.text_input("メールアドレス", key="login_email")
        login_password = st.text_input("パスワード", type="password", key="login_password")

        if st.button("ログイン"):
            if not login_email or not login_password:
                st.error("メールアドレスとパスワードを入力してください。")
            else:
                try:
                    res = supabase.auth.sign_in_with_password(
                        {"email": login_email, "password": login_password}
                    )
                    st.session_state.user = res.user
                    st.success("ログインしました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"ログインに失敗しました: {e}")

    with tab_signup:
        signup_email = st.text_input("新規登録用メールアドレス", key="signup_email")
        signup_password = st.text_input("新規登録用パスワード（6文字以上推奨）", type="password", key="signup_password")

        if st.button("アカウント作成"):
            if not signup_email or not signup_password:
                st.error("メールアドレスとパスワードを入力してください。")
            else:
                try:
                    supabase.auth.sign_up({"email": signup_email, "password": signup_password})
                    st.success("登録しました。確認メールが届いていれば、メール認証後にログインしてください。")
                except Exception as e:
                    st.error(f"登録に失敗しました: {e}")

    st.stop()

# ここに来たら Supabase ログイン済み
user = st.session_state.user
user_id = getattr(user, "id", None)
if user_id is None and isinstance(user, dict):
    user_id = user.get("id")

if not user_id:
    st.error("ユーザーIDが取得できませんでした。Supabaseの認証設定を確認してください。")
    st.stop()

today_str = date.today().isoformat()

# ============================================================
# 🌱 3. チャット用のセッション状態（slotsは内部用）
# ============================================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "current_phase" not in st.session_state:
    st.session_state.current_phase = None

# 内部制御用（画面表示しない）
if "slots" not in st.session_state:
    st.session_state.slots = default_slots_from_schema(SLOT_SCHEMA)

# ============================================================
# 📥 4. 今日の会話履歴を Supabase から読み込む（フェーズ復元）
# ============================================================
def load_today_history(user_id: str):
    try:
        res = supabase.table("user_chats").select("*") \
            .eq("user_id", user_id) \
            .eq("chat_date", today_str) \
            .order("message_time", desc=False) \
            .execute()
        data = res.data if hasattr(res, "data") else res.get("data", [])
    except Exception as e:
        st.error(f"会話履歴の読み込み中にエラーが発生しました: {e}")
        data = []

    history = []
    current_phase = None
    for row in data:
        history.append({"user": row.get("user_message", ""), "bot": row.get("bot_message", "")})
        if row.get("phase") and current_phase is None:
            current_phase = row.get("phase")

    st.session_state.chat_history = history
    st.session_state.current_phase = current_phase

load_today_history(user_id)

# ============================================================
# 🔧 ユーティリティ：JSONの安全パース
# ============================================================
def safe_json_load(s: str) -> dict:
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))

def normalize_phase(p: str) -> str:
    if p in ["phase_1", "phase_2", "phase_3", "phase_4"]:
        return p
    return "phase_1"

def validate_slot_value(slot_key: str, value: str) -> str:
    meta = SLOT_SCHEMA.get(slot_key, {})
    allowed = meta.get("values", []) or []
    if value in allowed:
        return value
    return "不明"

# ============================================================
# 🧠 5. システムプロンプト生成（UIに表示しない情報も回答文に内包）
# ============================================================
def build_system_prompt(fixed_phase=None, is_first_today=False):
    prompt = ""
    prompt += "あなたは不登校・ひきこもり支援の専門家です。\n"
    prompt += "利用者に共感し、責めず、安全を優先し、現実的で具体的な一歩を提案してください。\n"
    prompt += "知識ベース（phases/compass_principles/key_scenes/slot_schema/action_cards）に基づいて応答してください。\n"
    prompt += "\n"
    prompt += "【重要ルール】\n"
    prompt += "- 出力は必ず「JSONのみ」。本文の外に説明や注釈、Markdown、コードブロックを書かない。\n"
    prompt += "- 推測でスロットを埋めない。根拠が弱い場合は「不明」のまま。\n"
    prompt += "- 回答の最後に、必ず1〜2個の具体的な確認質問を含める。\n"
    prompt += "- その質問は、次の支援分岐に直結する内容にする。\n"
    prompt += "- 質問は自然な会話文として response の中に書く（箇条書きにしない）。\n"
    prompt += "- action_cards は最大3枚まで選ぶ。\n"
    prompt += "- ただし、質問や支援カードの内容はUIに別表示しないため、必ず response の文章の中に自然に含める（質問がある場合は文中で尋ねる。支援策は具体策として文章中に書く）。\n"
    prompt += "- 緊急性が高い可能性があるときは、安全確保の確認を優先する。\n"
    prompt += "- 抽象的な理念だけで終わらせない。\n"
    prompt += "- 必ず具体的な声かけ例を最低2つ提示する。\n"
    prompt += "- 必ず段階的な小さな行動例（0か100かではない中間案）を2つ以上提示する。\n"
    prompt += "- 明日そのまま使える表現にする。\n"
    prompt += "- 命令口調や断定は避ける。\n"
    prompt += "- 実務性と安心感のバランスを取る。\n"
    prompt += "\n"

    if is_first_today:
        prompt += "今日はその日の最初の相談です。発言内容から phase_1〜phase_4 を一つだけ推定してください。\n"
    else:
        prompt += f"本日のフェーズは {fixed_phase} に固定です。再推定してはいけません。\n"

    prompt += "\n"
    prompt += "【あなたが返すJSON形式】\n"
    prompt += "{\n"
    prompt += '  "phase": "phase_1|phase_2|phase_3|phase_4",\n'
    prompt += '  "slots_update": { "SLOT_KEY": "VALUE", "...": "..." },\n'
    prompt += '  "questions": ["質問1","質問2"],\n'
    prompt += '  "selected_action_card_ids": ["AC_...","AC_..."],\n'
    prompt += '  "response": "相談者への回答（この文章の中に、必要な確認質問も、具体的支援も、次の一歩も全部含める）"\n'
    prompt += "}\n"
    prompt += "\n"

    prompt += "【現在のスロット（既知情報）】\n"
    prompt += json.dumps(st.session_state.slots, ensure_ascii=False, indent=2) + "\n\n"

    prompt += "【知識ベース】\n"
    prompt += json.dumps(knowledge_base, ensure_ascii=False, indent=2)

    return prompt

# ============================================================
# 🤖 6. GPT応答生成 ＋ Supabase 保存（UI表示用の質問/カードは保持しない）
# ============================================================
def generate_response(user_input: str) -> str:
    is_first_today = (len(st.session_state.chat_history) == 0 or st.session_state.current_phase is None)
    fixed_phase = None if is_first_today else st.session_state.current_phase

    messages = [{"role": "system", "content": build_system_prompt(fixed_phase=fixed_phase, is_first_today=is_first_today)}]

    for chat in st.session_state.chat_history:
        messages.append({"role": "user", "content": f"相談者の発言: {chat['user']}"})
        messages.append({"role": "assistant", "content": chat["bot"]})

    messages.append({"role": "user", "content": f"相談者の発言: {user_input}"})

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
    )
    raw = resp.choices[0].message.content.strip()

    try:
        obj = safe_json_load(raw)
    except Exception as e:
        st.error(f"AIの出力JSONの解析に失敗しました（形式乱れの可能性）: {e}")
        response_text = raw
        phase_for_row = st.session_state.current_phase or "phase_1"
        try:
            supabase.table("user_chats").insert({
                "user_id": user_id,
                "chat_date": today_str,
                "user_message": user_input,
                "bot_message": response_text,
                "phase": phase_for_row
            }).execute()
        except Exception as e2:
            st.error(f"会話の保存中にエラーが発生しました: {e2}")
        return response_text

    phase_out = normalize_phase(obj.get("phase", "phase_1"))
    if is_first_today:
        st.session_state.current_phase = phase_out
    phase_for_row = st.session_state.current_phase or phase_out

    slots_update = obj.get("slots_update", {}) or {}
    for k in st.session_state.slots.keys():
        if k in slots_update:
            v = slots_update.get(k)
            if isinstance(v, str):
                v_norm = validate_slot_value(k, v)
                if v_norm != "不明":
                    st.session_state.slots[k] = v_norm

    response_text = obj.get("response", "").strip()
    if not response_text:
        response_text = "（すみません、うまく回答を生成できませんでした。もう一度、状況を短く教えてください。）"

    try:
        supabase.table("user_chats").insert({
            "user_id": user_id,
            "chat_date": today_str,
            "user_message": user_input,
            "bot_message": response_text,
            "phase": phase_for_row
        }).execute()
    except Exception as e:
        st.error(f"会話の保存中にエラーが発生しました: {e}")

    return response_text

# ============================================================
# 🧾 Sidebar（履歴はサイドバーへ / ログアウト）
# ============================================================
with st.sidebar:
    st.markdown(f"**ログイン中:** {getattr(user, 'email', '')}")
    st.markdown("---")
    st.markdown("### 🧭 今日の状態")
    st.markdown(f"- 日付: {today_str}")
    st.markdown(f"- Phase: `{st.session_state.current_phase or '未推定'}`")

    # 今日の履歴（簡易一覧）
    st.markdown("---")
    st.markdown("### 💬 今日の履歴（一覧）")
    if st.session_state.chat_history:
        for i, chat in enumerate(st.session_state.chat_history, start=1):
            preview = (chat.get("user", "") or "").replace("\n", " ")
            if len(preview) > 30:
                preview = preview[:30] + "…"
            st.markdown(f"{i}. {preview}")
    else:
        st.caption("まだ今日の履歴はありません。")

    # 過去の履歴（日付選択）
    st.markdown("---")
    st.markdown("### 📅 過去の相談をひらく")

    try:
        res_dates = supabase.table("user_chats").select("chat_date") \
            .eq("user_id", user_id) \
            .order("chat_date", desc=True) \
            .execute()
        data_dates = res_dates.data if hasattr(res_dates, "data") else res_dates.get("data", [])
        date_options = sorted({row["chat_date"] for row in data_dates}, reverse=True)
    except Exception as e:
        st.error(f"過去の相談日リスト取得中にエラーが発生しました: {e}")
        date_options = []

    if date_options:
        selected_date = st.selectbox(
            "日付を選択",
            options=date_options,
            format_func=lambda d: str(d),
            key="history_date_select_sidebar"
        )

        if selected_date:
            st.markdown(f"**{selected_date} の相談履歴**")
            try:
                res_hist = supabase.table("user_chats").select("*") \
                    .eq("user_id", user_id) \
                    .eq("chat_date", selected_date) \
                    .order("message_time", desc=False) \
                    .execute()
                hist = res_hist.data if hasattr(res_hist, "data") else res_hist.get("data", [])
            except Exception as e:
                st.error(f"過去の相談履歴取得中にエラーが発生しました: {e}")
                hist = []

            if not hist:
                st.caption("この日には記録された相談はありません。")
            else:
                # サイドバーは縦が狭いので直近のみプレビュー
                for row in hist[-20:]:
                    um = (row.get("user_message", "") or "").replace("\n", " ")
                    bm = (row.get("bot_message", "") or "").replace("\n", " ")
                    st.markdown(f"- **あなた**: {um[:40]}{'…' if len(um)>40 else ''}")
                    st.markdown(f"  **AI**: {bm[:40]}{'…' if len(bm)>40 else ''}")
    else:
        st.caption("まだ過去の相談はありません。")

    st.markdown("---")
    if st.button("ログアウト"):
        st.session_state.user = None
        st.session_state.chat_history = []
        st.session_state.current_phase = None
        st.session_state.slots = default_slots_from_schema(SLOT_SCHEMA)
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.rerun()

# ============================================================
# 🏷 7. タイトル・フェーズ表示
# ============================================================
st.markdown("<h1>AIエージェントへ相談する</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#2e7d32;'>温かく寄り添い、少しずつ一歩を。</p>", unsafe_allow_html=True)

st.markdown("### 現在の気持ちの推定フェーズ")

phase_display = [
    ("phase_1", "Phase 1：閉塞期（閉じこもり・虚無感を感じる時期）"),
    ("phase_2", "Phase 2：揺らぎ期（関係を求めたい気持ちと不安がある時期）"),
    ("phase_3", "Phase 3：希求・模索期（関わりや意味の模索している時期）"),
    ("phase_4", "Phase 4：転回期（価値観の転換と再出発に向けた時期）"),
]

if st.session_state.current_phase is None:
    st.markdown("まだフェーズは推定されていません。最初の相談内容を送信すると推定されます。")

for key, label in phase_display:
    mark = "●" if st.session_state.current_phase == key else "○"
    st.markdown(f"[{mark}] {label}")

st.markdown("---")

# ============================================================
# 💬 8. 今日の会話（ChatGPT風：上に積み上げ）
# ============================================================
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["user"])
    with st.chat_message("assistant"):
        st.markdown(chat["bot"])

# ============================================================
# ⌨️ 9. 入力欄（下に固定）
# ============================================================
user_text = st.chat_input("どんなことでも大丈夫です。ここに入力してください。")

if user_text:
    user_text = user_text.strip()
    if user_text:
        with st.spinner("AIエージェントは考えています…"):
            try:
                generate_response(user_text)
            except Exception as e:
                st.error(f"エラー: {e}")
        st.rerun()
