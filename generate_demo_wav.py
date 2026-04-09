"""
Generate a 15-second demo WAV file for Vocal Vitals demo mode.
Run: python generate_demo_wav.py
"""
import struct
import math

SAMPLE_RATE = 22050
DURATION    = 15  # seconds
N_SAMPLES   = SAMPLE_RATE * DURATION

def write_wav(path, samples, sample_rate=22050):
    n_channels   = 1
    bit_depth    = 16
    byte_rate    = sample_rate * n_channels * bit_depth // 8
    block_align  = n_channels * bit_depth // 8
    data_size    = len(samples) * block_align
    header_size  = 44

    with open(path, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', data_size + header_size - 8))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))               # Subchunk1Size
        f.write(struct.pack('<H', 1))                # AudioFormat (PCM)
        f.write(struct.pack('<H', n_channels))
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', byte_rate))
        f.write(struct.pack('<H', block_align))
        f.write(struct.pack('<H', bit_depth))
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            f.write(struct.pack('<h', int(clamped * 32767)))

if __name__ == '__main__':
    samples = []
    for i in range(N_SAMPLES):
        t = i / SAMPLE_RATE
        # Simulate a speaking voice: mix of harmonics with slight tremor
        fund  = 0.3 * math.sin(2 * math.pi * 187 * t)           # fundamental ~187 Hz (pitch_mean)
        h2    = 0.15 * math.sin(2 * math.pi * 374 * t)          # 2nd harmonic
        h3    = 0.08 * math.sin(2 * math.pi * 561 * t)          # 3rd harmonic
        tremor = 1 + 0.02 * math.sin(2 * math.pi * 5.5 * t)     # slight tremor
        noise  = 0.02 * (2 * ((i * 1664525 + 1013904223) % (2**32)) / (2**32) - 1)  # tiny noise
        # Add pauses to simulate real speech (at t=4s and t=10s)
        envelope = 0.0 if (4.0 < t < 4.8 or 10.0 < t < 11.0) else 1.0
        sample = (fund + h2 + h3) * tremor * envelope + noise
        samples.append(sample)

    write_wav('frontend/public/demo.wav', samples)
    print(f"Generated demo.wav: {N_SAMPLES} samples @ {SAMPLE_RATE} Hz, {DURATION}s")
