import streamlit as st
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from PIL import Image
from io import BytesIO
import textwrap
import os
from dotenv import load_dotenv

# ─── PAGE CONFIG (MUST BE FIRST) ──────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Summarizer (Groq+LLaMA)", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── ENVIRONMENT VARIABLES ────────────────────────────────────────────────────
load_dotenv()  # Load environment variables from .env
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLAMA_MODEL = "llama3-8b-8192"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── CUSTOM STYLING ───────────────────────────────────────────────────────────
st.markdown("""
    <style>
    .main { padding: 2rem; }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #FF4B4B;
        color: white;
        border: none;
        font-weight: bold;
    }
    .stButton>button:hover { background-color: #FF2B2B; }
    .stTextInput>div>div>input, .stTextArea>div>textarea {
        border-radius: 10px;
    }
    div.row-widget.stRadio > div {
        flex-direction: row;
        justify-content: center;
    }
    div.row-widget.stRadio > div > label {
        margin: 0 1rem;
        padding: 0.5rem 1rem;
        border: 1px solid #FF4B4B;
        border-radius: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        return parsed.path.lstrip("/")
    if parsed.path == "/watch":
        return parse_qs(parsed.query).get("v", [None])[0]
    return None

def get_thumbnail(video_id: str) -> Image.Image | None:
    try:
        thumb_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        resp = requests.get(thumb_url)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    except:
        return None

def fetch_transcript(video_id: str) -> str:
    try:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi'])
    except:
        try:
            entries = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        except Exception as e:
            st.error(f"Failed to fetch transcript: {e}")
            return ""
    return " ".join(e["text"] for e in entries)

def generate_with_groq(prompt: str, model: str = LLAMA_MODEL, timeout: float = 60.0) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    wrapper = textwrap.TextWrapper(width=max_chars, break_long_words=False, replace_whitespace=False)
    return wrapper.wrap(text)

def summarize_in_chunks(transcript: str) -> str:
    chunks = chunk_text(transcript, max_chars=1500)
    summaries = []
    progress = st.progress(0)
    for i, chunk in enumerate(chunks):
        prompt = (
            "Summarize this excerpt of a YouTube transcript in Hindi. "
            "Provide the summary in Hindi in about 150–200 words:\n\n" + chunk
        )
        try:
            summaries.append(generate_with_groq(prompt))
        except Exception as e:
            summaries.append(f"[Error summarizing chunk {i+1}: {e}]")
        progress.progress((i + 1) / len(chunks))

    final_prompt = (
        "Combine these Hindi partial summaries into one coherent, detailed "
        "500‑word description in Hindi:\n\n" + "\n\n".join(summaries)
    )
    return generate_with_groq(final_prompt)

def answer_question(transcript: str, question: str) -> str:
    prompt = (
        "You are an assistant who answers questions in Hindi based only on the provided YouTube transcript.\n\n"
        f"Transcript:\n{transcript}\n\n"
        f"Question (in Hindi): {question}\n\n"
        "Answer in Hindi:"
    )
    return generate_with_groq(prompt)

# ─── MAIN APP UI ───────────────────────────────────────────────────────────────
# Header section with logo and title
col1, col2 = st.columns([1, 4])
with col1:
    st.image("https://img.icons8.com/color/96/000000/youtube-play.png", width=80)
with col2:
    st.title("F")
    st.markdown("##### Transform YouTube content into detailed notes and interactive Q&A")

st.markdown("---")

st.markdown("""
    <div style='background-color: #939597; padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
        <h4>How it works:</h4>
        <ol>
            <li>Paste a YouTube video URL</li>
            <li>Select your preferred language</li>
            <li>Generate transcript, summary, or ask questions!</li>
        </ol>
    </div>
""", unsafe_allow_html=True)

# Language and URL input
language = st.radio("Select Video Language:", ('Hindi', 'English'), index=0)
url = st.text_input("🔗 Enter YouTube Video URL:", placeholder="https://www.youtube.com/watch?v=...")

if url:
    video_id = extract_video_id(url)
    if not video_id:
        st.error("❌ Invalid YouTube URL. Please check the URL and try again.")
    else:
        # Video preview
        st.markdown("### 📺 Video Preview")
        thumb = get_thumbnail(video_id)
        if thumb:
            st.image(thumb, use_container_width=True)

        # Tabs: Transcript / Summary / Q&A
        tab1, tab2, tab3 = st.tabs(["📜 Transcript", "🧾 Summary", "❓ Q&A"])

        with tab1:
            if st.button("Generate Transcript", key="transcript_btn"):
                with st.spinner("📝 Fetching transcript..."):
                    try:
                        st.session_state.transcript = fetch_transcript(video_id)
                        st.success("✅ Transcript generated successfully!")
                        st.markdown("### 📄 Transcript Content")
                        st.text_area("", st.session_state.transcript, height=300)
                    except Exception as e:
                        st.error(f"❌ Failed to fetch transcript: {e}")

        with tab2:
            if st.button("Generate Summary", key="summary_btn"):
                if not st.session_state.get("transcript"):
                    st.warning("⚠️ Please generate the transcript first!")
                else:
                    with st.spinner("🔄 Generating summary..."):
                        try:
                            if language == 'Hindi':
                                st.session_state.description = summarize_in_chunks(st.session_state.transcript)
                            else:
                                prompt = "Summarize this YouTube transcript in about 500 words:\n\n" + st.session_state.transcript
                                st.session_state.description = generate_with_groq(prompt)
                            st.markdown("### 📋 Summary")
                            st.text_area("", st.session_state.description, height=300)
                        except Exception as e:
                            st.error(f"❌ Failed to generate summary: {e}")

        with tab3:
            st.markdown("### Ask a Question")
            user_question = st.text_input("💭 What would you like to know about the video?", placeholder="Type your question here...")
            if st.button("Get Answer", key="qa_btn"):
                if not st.session_state.get("transcript"):
                    st.warning("⚠️ Please generate the transcript first!")
                elif not user_question.strip():
                    st.warning("⚠️ Please enter a question!")
                else:
                    with st.spinner("🤔 Analyzing your question..."):
                        try:
                            if language == 'Hindi':
                                st.session_state.qa = answer_question(st.session_state.transcript, user_question)
                            else:
                                prompt = f"Answer this question based on the transcript:\n\nTranscript:\n{st.session_state.transcript}\n\nQuestion: {user_question}\n\nAnswer:"
                                st.session_state.qa = generate_with_groq(prompt)
                            st.markdown("### 💡 Answer")
                            st.text_area("", st.session_state.qa, height=200)
                        except Exception as e:
                            st.error(f"❌ Failed to generate answer: {e}")

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>Powered by Groq + LLaMA | Made with ❤️ using Streamlit</p>
    </div>
""", unsafe_allow_html=True)
