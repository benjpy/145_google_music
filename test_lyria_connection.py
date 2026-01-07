import asyncio
import os
from lyria_client import LyriaClient

async def test_connection():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
        return

    print("Connecting to Lyria...")
    client = LyriaClient(api_key=api_key)
    try:
        await client.connect()
        print("Connected!")
        
        print("Setting prompts...")
        await client.set_prompts([{"text": "Minimal techno", "weight": 1.0}])
        
        print("Setting config...")
        await client.set_config({"bpm": 120, "density": 0.5})
        
        print("Playing...")
        await client.play()
        
        print("Waiting for audio chunks...")
        for _ in range(10):
            chunk = await client.audio_queue.get()
            print(f"Received chunk of size: {len(chunk)} bytes")
            
        print("Stopping...")
        await client.stop()
        await client.close()
        print("Test passed!")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
