import pyaudio
import numpy as np

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK
)

print("🎤 Testing microphone - Stay SILENT for 10 seconds...")
print("Watch the volume numbers below:")
print("-" * 40)

for i in range(0, int(RATE / CHUNK * 10)):
    data = stream.read(CHUNK, exception_on_overflow=False)
    audio_data = np.frombuffer(data, dtype=np.int16)
    volume = np.abs(audio_data).mean()
    
    if volume < 100:
        status = "✅ SILENT"
    elif volume < 500:
        status = "⚠️ SOME NOISE"
    else:
        status = "🚨 LOUD"
    
    print(f"Volume: {volume:.1f}  →  {status}")

stream.stop_stream()
stream.close()
p.terminate()
print("-" * 40)
print("Test complete!")