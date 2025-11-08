import streamlit as st
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials,auth, firestore
import requests
import json

# ---------------------------
# Firebase initialization
# ---------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase_admin"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------------------------
# LLM Server
OLLAMA_URL = "http://127.0.0.1:11434"  # local Ollama 

def call_llm_server(payload):
    api_url = f"{OLLAMA_URL.rstrip('/')}/api/generate"

    # Nếu payload chứa start/end → LLM tạo lịch trình
    if "start_datetime" in payload and "end_datetime" in payload:
        from datetime import datetime, timedelta

        start_date = datetime.strptime(payload["start_datetime"], "%d-%m-%Y")
        end_date = datetime.strptime(payload["end_datetime"], "%d-%m-%Y")
        delta_days = (end_date - start_date).days + 1
        full_output = ""

        with st.status("🤖 LLM đang chạy...", expanded=True):
            for i in range(delta_days):
                current_date = (start_date + timedelta(days=i)).strftime("%d-%m-%Y")

                prompt = (
                    f"Tạo lịch trình du lịch chi tiết ngày {current_date} tại "
                    f"{payload['origin']} → {payload['destination']}, "
                    f"sở thích: {', '.join(payload.get('interests', []))}, tốc độ: {payload.get('pace')}.\n\n"
                    "Viết theo định dạng:\n\n"
                    "Sáng (HH:MM →  HH:MM): ...\n"
                    "Trưa (HH:MM →  HH:MM): ...\n"
                    "Tối (HH:MM →  HH:MM): ...\n\n"
                )

                response = requests.post(
                    api_url,
                    json={"model": "llama3.2:1b", "prompt": prompt, "max_tokens": 2000},
                    stream=True,
                    timeout=300
                )

                day_output = ""
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                day_output += data["response"]
                        except:
                            continue

                full_output += f"\n{day_output.strip()}\n" if day_output else f"\n❌ Không nhận được phản hồi cho ngày {current_date}.\n"

        return full_output.strip()

    # Nếu payload chứa prompt → Chatbot
    elif "prompt" in payload:
        prompt = payload["prompt"]
        # with st.status("💬 Chatbot đang chạy...", expanded=True):
        response = requests.post(
            api_url,
            json={"model": "llama3.2:1b", "prompt": prompt, "max_tokens": 2000},
            stream=True,
            timeout=300
        )

        output = ""
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if "response" in data:
                        output += data["response"]
                except:
                    continue
        return output.strip()

    else:
        return "❌ Payload không hợp lệ."



# ---------------------------
# Streamlit UI setup
# ---------------------------
st.set_page_config(page_title="TripPlanner", page_icon="🧭", layout="wide")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stApp {
    background: url('https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1950&q=80') no-repeat center center fixed;
    background-size: cover;
    backdrop-filter: blur(8px);
    background-color: rgba(0, 0, 0, 0.4);
    background-blend-mode: darken;
}
</style>
""", unsafe_allow_html=True)

st.title("🧭 TripPlanner + Ollama")
st.subheader("Đăng ký / Đăng nhập")

# ---------------------------
# Khởi tạo session_state
# ---------------------------
if "user" not in st.session_state:
    st.session_state["user"] = None
if "history" not in st.session_state:
    st.session_state["history"] = []
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []


# Chuẩn hóa các item trong history để tránh KeyError
for item in st.session_state.get("history", []):
    if "type" not in item:
        item["type"] = "llm"  # mặc định LLM
    if "request" not in item:
        item["request"] = {}
    if "response" not in item:
        item["response"] = ""



# ---------------------------
# Firebase Login
# ---------------------------
FIREBASE_API_KEY = st.secrets["firebase_login"]["apiKey"]

def firebase_sign_in(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resp = requests.post(url, json=payload)
    return resp.json()

def load_history(user_email):
    history_ref = db.collection("users").document(user_email).collection("history").order_by("timestamp")
    history_docs = history_ref.stream()
    history_list = []
    for doc in history_docs:
        data = doc.to_dict()
        data["timestamp"] = data["timestamp"].strftime("%d-%m-%Y %H:%M:%S")
        history_list.append(data)
    return history_list[-5:]

def load_history(user_email):
    history_ref = db.collection("users").document(user_email).collection("history").order_by("timestamp")
    history_docs = history_ref.stream()
    history_list = []
    for doc in history_docs:
        data = doc.to_dict()
        data["timestamp"] = data["timestamp"].strftime("%d-%m-%Y %H:%M:%S")
        history_list.append(data)
    return history_list[-5:]


def load_chat_history(user_email):
    history_ref = db.collection("users").document(user_email).collection("history").order_by("timestamp")
    docs = history_ref.stream()
    chat_history = []
    for doc in docs:
        data = doc.to_dict()
        if data.get("type") == "chat":
            chat_history.append({
                "role": "user",
                "content": data.get("request", {}).get("prompt", ""),
                "timestamp": data.get("timestamp").strftime("%d-%m-%Y %H:%M:%S")
            })
            chat_history.append({
                "role": "assistant",
                "content": data.get("response", ""),
                "timestamp": data.get("timestamp").strftime("%d-%m-%Y %H:%M:%S")
            })
    return chat_history

# ---------------------------
# Form đăng nhập/đăng ký
# ---------------------------
email = st.text_input("Email")
password = st.text_input("Mật khẩu", type="password")

col_login, col_register, col_logout = st.columns(3)

with col_login:
    if st.button("🔓 Đăng nhập"):
        result = firebase_sign_in(email, password)
        if "error" in result:
            message = result["error"]["message"]
            if message == "EMAIL_NOT_FOUND":
                st.error("❌ Email chưa đăng ký. Hãy đăng ký trước.")
            elif message == "INVALID_PASSWORD":
                st.error("❌ Sai mật khẩu. Vui lòng thử lại.")
            else:
                st.error(f"Lỗi đăng nhập: {message}")
        else:
            st.session_state["user"] = email
            st.session_state["history"] = load_history(email)
            st.session_state["chat_history"] = load_chat_history(email)
            st.success(f"Đăng nhập thành công: {email}")

with col_register:
    if st.button("📝 Đăng ký"):
        try:
            user = auth.create_user(email=email, password=password)
            st.success("✅ Đăng ký thành công! Giờ bạn có thể đăng nhập.")
        except Exception as e:
            st.error(f"Lỗi đăng ký: {e}")

with col_logout:
    if st.session_state["user"] and st.button("🚪 Đăng xuất"):
        st.session_state["user"] = None
        st.session_state["history"] = []
        st.success("✅ Bạn đã đăng xuất.")



# ---------------------------
# Nhập thông tin chuyến đi & tạo lịch trình & chat bot
# ---------------------------

st.divider()
st.subheader("Chọn chế độ sử dụng TripPlanner")
col1, col2 = st.columns(2)
with col1:
    llm_button = st.button("🧭 LLM Hướng dẫn du lịch", key="llm_btn")
with col2:
    chat_button = st.button("💬 Chatbot", key="chat_btn")

# Xác định chế độ đang chọn
if llm_button:
    st.session_state["mode"] = "llm"
elif chat_button:
    st.session_state["mode"] = "chat"

mode = st.session_state.get("mode")

# --- LLM ---
if mode == "llm":

    origin = st.text_input("🏙️ Thành phố khởi hành")
    destination = st.text_input("📍 Thành phố điểm đến")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Ngày bắt đầu", datetime.now())
    with col2:
        end_date = st.date_input("📅 Ngày kết thúc", datetime.now())
    
    interests = st.multiselect("🎯 Sở thích", ["Ẩm thực", "Viện bảo tàng", "Thiên nhiên", "Cuộc sống đêm"])
    pace = st.selectbox("🚶‍♂️ Tốc độ", ["Thư giãn", "Bình thường", "Nhanh"])
    
    if st.button("✨ Tạo lịch trình chi tiết"):
        payload = {
            "origin": origin,
            "destination": destination,
            "start_datetime": start_date.strftime("%d-%m-%Y"),
            "end_datetime": end_date.strftime("%d-%m-%Y"),
            "interests": interests,
            "pace": pace,
        }

        # Gọi LLM tạo lịch trình
        itinerary = call_llm_server(payload)
        st.markdown(itinerary)

        st.session_state["history"].append({
            "type": "llm",
            "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "request": payload,
            "response": itinerary
        })

# --- Chatbot ---
elif mode == "chat":
    st.subheader("💬 Trò chuyện cùng TripPlanner")

    chat_container = st.container()

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Hiển thị lịch sử chat hiện tại trong session
    with chat_container:
        for item in st.session_state["chat_history"]:
            role = item.get("role")
            content = item.get("content")
            with st.chat_message(role):
                st.markdown(content)


    user_message = st.chat_input("Nhập tin nhắn của bạn...")

    if user_message:
    
        st.session_state["chat_history"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        })

        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_message)

        prompt_text = "\n".join([f"{item['role']}: {item['content']}" 
                                 for item in st.session_state["chat_history"]])
        bot_reply = call_llm_server({"prompt": prompt_text})

        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": bot_reply,
            "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        })
        with chat_container:
            with st.chat_message("assistant"):
                st.markdown(bot_reply)

        if st.session_state.get("user"):
            db.collection("users").document(st.session_state["user"]).collection("history").add({
                "type": "chat",
                "timestamp": datetime.now(),
                "request": {"prompt": user_message},
                "response": bot_reply
            })



# --- Hiển thị lịch sử theo chế độ ---
st.divider()
if st.session_state.get("history"):
    if mode == "llm":
        st.subheader("📜 Lịch sử chuyến đi")
        for item in reversed(st.session_state["history"]):
            if item.get("type") != "llm":
                continue
            origin = item.get("request", {}).get("origin", "N/A")
            destination = item.get("request", {}).get("destination", "N/A")
            timestamp = item.get("timestamp", "N/A")
            
            st.markdown(f"**🕒 {timestamp} | {origin} → {destination}**")
            st.json(item.get("request", {}))
            st.markdown(item.get("response", ""))
            st.write("---")

  


