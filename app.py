import streamlit as st
import asyncio
import base64
import time
import os
from dotenv import load_dotenv
from lyria_client import LyriaClient
from google.genai import types

# Load environment variables
load_dotenv()

# Page Config
st.set_page_config(page_title="Lyria Music Studio", page_icon="🎵", layout="wide")

# Custom CSS for a premium look
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at top right, #1a1a2e, #16213e, #0f3460);
        color: #ffffff;
    }
    .main-header {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 3rem;
        background: -webkit-linear-gradient(#00d2ff, #3a7bd5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sidebar .sidebar-content {
        background-color: rgba(255, 255, 255, 0.05);
    }
    .prompt-card {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">Lyria Music Studio</h1>', unsafe_allow_html=True)
st.write("Real-time generative music powered by Google's Lyria model.")

# --- Session State ---
if 'client' not in st.session_state:
    st.session_state.client = None
if 'prompts' not in st.session_state:
    st.session_state.prompts = [{"text": "Chill Lo-Fi beats", "weight": 1.0}]
if 'is_running' not in st.session_state:
    st.session_state.is_running = False

# --- Sidebar ---
with st.sidebar:
    st.header("Settings")
    
    # API Key Management
    fixed_key = ""
    if "GOOGLE_API_KEY" in st.secrets:
        fixed_key = st.secrets["GOOGLE_API_KEY"]
        st.success("API Key: Configured from Secrets ✅")
    elif os.environ.get("GOOGLE_API_KEY"):
        fixed_key = os.environ.get("GOOGLE_API_KEY")
        st.success("API Key: Configured from .env ✅")
    
    # If key is already fixed, we don't need to show the input unless they want to override
    if fixed_key:
        api_key_input = st.text_input("Gemini API Key (Override)", 
                                     type="password", 
                                     help="Only enter if you want to override the pre-configured key.")
        api_key = api_key_input if api_key_input else fixed_key
    else:
        api_key = st.text_input("Gemini API Key", 
                                type="password",
                                help="Enter your key from Google AI Studio. For Streamlit Cloud, add it to App Secrets.")
    
    if not api_key:
        st.warning("⚠️ API Key is required to start.")
    
    st.divider()
    
    st.subheader("Music Parameters")
    bpm = st.slider("BPM", 60, 200, 120)
    density = st.slider("Density", 0.0, 1.0, 0.5)
    brightness = st.slider("Brightness", 0.0, 1.0, 0.5)
    guidance = st.slider("Guidance", 0.0, 6.0, 4.0)
    
    st.divider()
    
    mute_bass = st.checkbox("Mute Bass", False)
    mute_drums = st.checkbox("Mute Drums", False)
    only_bass_drums = st.checkbox("Only Bass & Drums", False)
    
    mode = st.selectbox("Generation Mode", 
                        options=["QUALITY", "DIVERSITY", "VOCALIZATION"],
                        index=0)
    
    st.subheader("Scale & Mode")
    scales = [s for s in dir(types.Scale) if not s.startswith("_")]
    scale_name = st.selectbox("Musical Scale", options=scales, index=scales.index("C_MAJOR_A_MINOR") if "C_MAJOR_A_MINOR" in scales else 0)
    
    st.divider()
    with st.expander("Diagnostics"):
        if st.button("🔔 Test Audio Output"):
            if st.session_state.client:
                st.session_state.client.test_audio()
                st.toast("Playing test tone...")
            else:
                st.warning("Client not initialized. Start session first.")
        
        if st.button("🧹 Clear Logs"):
            if os.path.exists("lyria.log"):
                os.remove("lyria.log")
                st.rerun()
        
        if os.path.exists("lyria.log"):
            with open("lyria.log", "r") as f:
                logs = f.readlines()
                st.text_area("Logs", "".join(logs[-10:]), height=150)

# --- Functions ---
def start_session():
    if not api_key:
        st.error("Please provide an API Key.")
        return
    
    try:
        # Cleanup existing if any
        if st.session_state.client:
            st.session_state.client.close()
            
        st.session_state.client = LyriaClient(api_key=api_key)
        st.session_state.client.connect()
        
        if not st.session_state.client.is_connected:
            st.error("Connection failed.")
            return
        
        # Initial Prompts
        st.session_state.client.set_prompts(st.session_state.prompts)
        
        # Initial Config
        config = {
            "bpm": bpm,
            "density": density,
            "brightness": brightness,
            "guidance": guidance,
            "mute_bass": mute_bass,
            "mute_drums": mute_drums,
            "only_bass_and_drums": only_bass_drums,
            "music_generation_mode": getattr(types.MusicGenerationMode, mode),
            "scale": getattr(types.Scale, scale_name)
        }
        st.session_state.client.set_config(config)
        
        st.session_state.client.play()
        st.session_state.is_running = True
        st.rerun()
    except Exception as e:
        st.error(f"Failed to start: {e}")

def stop_session():
    st.session_state.is_running = False
    if st.session_state.client:
        st.session_state.client.close()
        st.session_state.client = None
    st.rerun()

def reconnect_session():
    stop_session()
    start_session()

def update_params():
    if st.session_state.client and st.session_state.client.is_connected:
        try:
            config = {
                "bpm": bpm,
                "density": density,
                "brightness": brightness,
                "guidance": guidance,
                "mute_bass": mute_bass,
                "mute_drums": mute_drums,
                "only_bass_and_drums": only_bass_drums,
                "music_generation_mode": getattr(types.MusicGenerationMode, mode),
                "scale": getattr(types.Scale, scale_name)
            }
            st.session_state.client.update_config_with_reset(config)
            st.toast("Parameters & Context updated")
        except Exception as e:
            st.error(f"Update failed: {e}")

# --- Main UI ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Prompts")
    for i, p in enumerate(st.session_state.prompts):
        with st.container():
            c1, c2, c3 = st.columns([4, 2, 1])
            new_text = c1.text_input(f"Prompt {i+1}", value=p['text'], key=f"text_{i}")
            new_weight = c2.number_input("Weight", value=p['weight'], min_value=-5.0, max_value=5.0, step=0.1, key=f"weight_{i}")
            if c3.button("🗑️", key=f"del_{i}"):
                st.session_state.prompts.pop(i)
                st.rerun()
            
            st.session_state.prompts[i]["text"] = new_text
            st.session_state.prompts[i]["weight"] = new_weight

    if st.button("➕ Add Prompt"):
        st.session_state.prompts.append({"text": "", "weight": 1.0})
        st.rerun()

    if st.button("Apply Prompts"):
        if st.session_state.client and st.session_state.is_running:
            st.session_state.client.set_prompts(st.session_state.prompts)
            if st.session_state.client.is_connected:
                st.success("Prompts applied!")
            else:
                st.error("Connection lost.")

with col2:
    st.subheader("Controls")
    if not st.session_state.is_running:
        if st.button("▶️ Start Generation", use_container_width=True, type="primary"):
            start_session()
    else:
        if st.button("⏹️ Stop Generation", use_container_width=True):
            stop_session()
        
        if st.button("🔄 Reset Context", use_container_width=True):
            if st.session_state.client:
                st.session_state.client.reset()
                st.toast("Context reset")

    if st.button("Apply Parameters"):
        if st.session_state.client and st.session_state.is_running:
            update_params()
            if st.session_state.client and st.session_state.client.is_connected:
                st.success("Parameters applied!")
            else:
                st.error("Connection lost.")

    st.divider()
    
    if st.session_state.client:
        if st.session_state.client.is_connected:
            st.write("🟢 Connection Active")
        else:
            st.write("🔴 Connection Lost")
            if st.button("🔄 Reconnect Now", use_container_width=True):
                reconnect_session()

# --- Audio Playback ---
if st.session_state.is_running and st.session_state.client:
    if st.session_state.client.audio_enabled:
        st.success("Music is playing to your local speakers! 🔊")
    else:
        st.warning("☁️ Cloud Mode: Local speakers unavailable. Use the button below to listen.")
        
    st.info("Generating music... 🎶")
    
    with st.expander("🌐 Browser Playback (Fallback)", expanded=not st.session_state.client.audio_enabled):
        st.write(f"**Live Session Captured**: `{st.session_state.client.recording_duration:.1f}s` of music")
        
        col_gen, col_dl, col_clr = st.columns(3)
        
        pcm_data = st.session_state.client.get_audio_bytes()
        wav_data = None
        if pcm_data:
            wav_data = LyriaClient.create_wav_header(len(pcm_data)) + pcm_data
            
        if col_gen.button(f"🔄 Refresh Player", use_container_width=True):
            if wav_data:
                st.audio(wav_data, format="audio/wav")
            else:
                st.info("No audio generated yet.")
        
        if col_dl.download_button(
            label="💾 Download WAV",
            data=wav_data if wav_data else b"",
            file_name=f"lyria_session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav",
            mime="audio/wav",
            disabled=(wav_data is None),
            use_container_width=True
        ):
            st.toast("Download started!")

        if col_clr.button("🗑️ Clear Recording", use_container_width=True):
            st.session_state.client._all_audio_bytes.clear()
            st.rerun()

    if wav_data and not st.session_state.client.audio_enabled:
        st.audio(wav_data, format="audio/wav")

    st.write("Current Prompts:", st.session_state.prompts)
    
    if st.button("Refresh Status"):
        st.rerun()

    st.warning("Note: The audio is playing directly to your computer's speakers to avoid Streamlit's web-based audio limitations.")
