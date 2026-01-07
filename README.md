# Lyria Music Studio 🎵

A real-time generative music application powered by Google's Lyria model. This app allows you to steer music generation in real-time using text prompts and musical parameters like BPM, Density, and Scale.

## Features
- **Real-time Steering**: Change prompts and parameters on the fly.
- **Bi-directional Streaming**: Low-latency audio generation and playback.
- **Local Audio Output**: Plays directly to your computer's speakers using `sounddevice`.
- **Diagnostics**: Built-in logs and audio tests.

## Setup

### 1. Prerequisites
- Python 3.10+
- A Google Gemini API Key (with access to Lyria RealTime).

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
GOOGLE_API_KEY=your_api_key_here
```

### 4. Run the App
```bash
streamlit run app.py
```

## Deployment on Streamlit Cloud
1. Push this code to a GitHub repository.
2. In Streamlit Cloud, add your `GOOGLE_API_KEY` to **Secrets**:
   ```toml
   GOOGLE_API_KEY = "your_api_key_here"
   ```
3. **Important Note**: Audio playback currently uses `sounddevice`, which plays to the **server's** audio output. When deployed to Streamlit Cloud, you won't hear music in your browser. This application is optimized for local performance.
