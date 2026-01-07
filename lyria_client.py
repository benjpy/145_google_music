import asyncio
import base64
import collections
import datetime
import threading
import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

def log_debug(msg):
    with open("lyria.log", "a") as f:
        f.write(f"[{datetime.datetime.now()}] {msg}\n")

class LyriaClient:
    def __init__(self, api_key: str):
        log_debug("Initializing LyriaClient (Threaded)")
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
        self.session = None
        self._session_manager = None
        self.is_playing = False
        self.is_connected = False
        self._playback_stream = None
        self._playback_buffer = collections.deque()
        self.sample_rate = 48000
        self.channels = 2
        self._current_prompts = []
        self.audio_enabled = False
        self._all_audio_bytes = bytearray()
        
        # Threading/Async management
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def connect(self):
        """Synchronous wrapper to connect in the background loop."""
        future = asyncio.run_coroutine_threadsafe(self._connect_async(), self._loop)
        return future.result(timeout=10)

    async def _connect_async(self):
        """ESTABLISHES connection to the Lyria RealTime model."""
        log_debug("Connecting to Lyria (Async)...")
        try:
            self._session_manager = self.client.aio.live.music.connect(model='models/lyria-realtime-exp')
            self.session = await self._session_manager.__aenter__()
            self.is_connected = True
            log_debug("Connected successfully")
            
            # Start receive loop after a tiny delay
            await asyncio.sleep(0.5)
            self._receive_task = self._loop.create_task(self._receive_audio())
        except Exception as e:
            log_debug(f"Connection failed: {e}")
            self.is_connected = False
            raise

        # Initialize output stream
        log_debug("Initializing sounddevice OutputStream")
        try:
            self._playback_stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='int16',
                callback=self._audio_callback
            )
            self._playback_stream.start()
            self.audio_enabled = True
            log_debug("OutputStream started")
        except Exception as e:
            log_debug(f"Warning: Could not start audio output device. Headless mode? Error: {e}")
            self.audio_enabled = False
            self._playback_stream = None

    def _audio_callback(self, outdata, frames, time, status):
        """Callback for the sounddevice output stream."""
        if status:
            print(f"Audio status: {status}")
        
        bytes_needed = frames * self.channels * 2 # 16-bit = 2 bytes
        current_data = b""
        
        while len(current_data) < bytes_needed and self._playback_buffer:
            chunk = self._playback_buffer.popleft()
            current_data += chunk
            
        if len(current_data) < bytes_needed:
            # Padding if buffer is empty
            current_data += b"\x00" * (bytes_needed - len(current_data))
        elif len(current_data) > bytes_needed:
            # Put remaining back in buffer
            self._playback_buffer.appendleft(current_data[bytes_needed:])
            current_data = current_data[:bytes_needed]
            
        outdata[:] = np.frombuffer(current_data, dtype='int16').reshape(-1, self.channels)

    async def _receive_audio(self):
        """Background task to receive audio chunks from the server."""
        log_debug("Starting receive_audio task")
        try:
            while self.is_connected:
                async for message in self.session.receive():
                    if not self.is_connected:
                        log_debug("is_connected is False, breaking receive loop")
                        break
                    if message.server_content and message.server_content.audio_chunks:
                        for chunk in message.server_content.audio_chunks:
                            # Only log every 20th chunk to keep log readable
                            if not hasattr(self, '_chunk_count'): self._chunk_count = 0
                            self._chunk_count += 1
                            if self._chunk_count % 20 == 0:
                                log_debug(f"Audio buffer: {len(self._playback_buffer)} chunks. Received: {len(chunk.data)} bytes")
                            
                            self._playback_buffer.append(chunk.data)
                            self._all_audio_bytes.extend(chunk.data)
                await asyncio.sleep(0.01)
        except Exception as e:
            log_debug(f"CRITICAL Error receiving audio: {e}")
        finally:
            log_debug("Closing receive_audio task")
            self.is_playing = False
            self.is_connected = False

    def set_prompts(self, prompts: list[dict]):
        asyncio.run_coroutine_threadsafe(self._set_prompts_async(prompts), self._loop)

    async def _set_prompts_async(self, prompts: list[dict]):
        if self.session and self.is_connected:
            try:
                self._current_prompts = prompts
                weighted_prompts = [
                    types.WeightedPrompt(text=p['text'], weight=p['weight'])
                    for p in prompts
                ]
                await self.session.set_weighted_prompts(prompts=weighted_prompts)
            except Exception as e:
                log_debug(f"Failed to set prompts: {e}")
                self.is_connected = False

    def set_config(self, config_dict: dict):
        asyncio.run_coroutine_threadsafe(self._set_config_async(config_dict), self._loop)

    def update_config_with_reset(self, config_dict: dict):
        """Sequential update and reset to avoid race conditions."""
        asyncio.run_coroutine_threadsafe(self._update_config_and_reset_async(config_dict), self._loop)

    async def _update_config_and_reset_async(self, config_dict: dict):
        log_debug("Atomic update started...")
        await self._set_config_async(config_dict)
        await asyncio.sleep(0.3)
        await self._reset_async()
        
        # Re-send prompts to ensure they are active in the new context
        if self._current_prompts:
            log_debug("Re-sending prompts after reset...")
            await self._set_prompts_async(self._current_prompts)
            
        log_debug("Atomic update finished.")

    async def _set_config_async(self, config_dict: dict):
        if self.session and self.is_connected:
            try:
                log_debug(f"Applying music generation config: {config_dict}")
                config = types.LiveMusicGenerationConfig(**config_dict)
                await self.session.set_music_generation_config(config=config)
                log_debug("Config applied successfully")
            except Exception as e:
                log_debug(f"Failed to set config: {e}")
                self.is_connected = False

    def play(self):
        asyncio.run_coroutine_threadsafe(self._play_async(), self._loop)

    async def _play_async(self):
        if self.session and self.is_connected:
            try:
                await self.session.play()
                self.is_playing = True
            except Exception as e:
                log_debug(f"Failed to play: {e}")
                self.is_connected = False

    def stop(self):
        asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)

    async def _stop_async(self):
        if self.session and self.is_connected:
            try:
                await self.session.stop()
            except Exception:
                pass
            self.is_playing = False

    def reset(self):
        asyncio.run_coroutine_threadsafe(self._reset_async(), self._loop)

    async def _reset_async(self):
        log_debug(f"Called _reset_async (connected={self.is_connected})")
        if self.session and self.is_connected:
            try:
                # Clear local buffers
                cleared_count = len(self._playback_buffer)
                self._playback_buffer.clear()
                self._all_audio_bytes.clear() # Clear accumulated for the new song
                log_debug(f"-> Cleared {cleared_count} buffered chunks and all_audio_bytes")
                
                log_debug("-> Invoking session.reset_context()...")
                await self.session.reset_context()
                log_debug("-> reset_context() returned successfully")
                
                # Tiny pause to let the stream transition
                await asyncio.sleep(0.1)
            except Exception as e:
                log_debug(f"!! reset_context() FAILED: {e}")
        else:
            log_debug(f"!! reset_context() SKIPPED: connected={self.is_connected}, session={self.session is not None}")

    def get_audio_bytes(self):
        """Returns all accumulated audio bytes for browser playback."""
        return bytes(self._all_audio_bytes)

    @staticmethod
    def create_wav_header(pcm_length, sample_rate=48000, channels=2):
        """Creates a WAV header for raw PCM data."""
        import struct
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        
        header = b'RIFF'
        header += struct.pack('<I', 36 + pcm_length)
        header += b'WAVEfmt '
        header += struct.pack('<I', 16)
        header += struct.pack('<H', 1)
        header += struct.pack('<H', channels)
        header += struct.pack('<I', sample_rate)
        header += struct.pack('<I', byte_rate)
        header += struct.pack('<H', block_align)
        header += struct.pack('<H', bits_per_sample)
        header += b'data'
        header += struct.pack('<I', pcm_length)
        return header

    def test_audio(self, duration=2.0):
        # Already synchronous
        self._playback_buffer.append(self._generate_test_tone(duration))

    def _generate_test_tone(self, duration):
        frequency = 440
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        tone = np.sin(frequency * t * 2 * np.pi) * 0.3 * 32767
        stereo_tone = np.zeros(len(tone) * 2, dtype=np.int16)
        stereo_tone[0::2] = tone.astype(np.int16)
        stereo_tone[1::2] = tone.astype(np.int16)
        return stereo_tone.tobytes()

    def close(self):
        log_debug("Closing LyriaClient (Threaded)")
        self.is_connected = False
        self.is_playing = False
        
        # Stop playback ASAP
        if self._playback_stream:
            try:
                self._playback_stream.stop()
                self._playback_stream.close()
            except Exception: pass

        # Close session in loop
        asyncio.run_coroutine_threadsafe(self._close_async(), self._loop).result(timeout=5)
        
        # Stop the loop
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)

    async def _close_async(self):
        if self.session and self._session_manager:
            try:
                await self._session_manager.__aexit__(None, None, None)
                log_debug("Session manager closed")
            except Exception as e:
                log_debug(f"Error closing session manager: {e}")
            self.session = None
            self._session_manager = None
