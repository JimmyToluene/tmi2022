"""Audio timeline for BV1ZnpG6dE8g: loudness, onsets, beats, spectral shape per video frame.

Usage: python audio_metrics.py <audio_wav> <out_json>
"""
import json
import sys

import librosa
import numpy as np

FPS = 30.0


def main(wav, out):
    y, sr = librosa.load(wav, sr=22050, mono=True)
    hop = int(sr / FPS)  # one analysis hop per video frame
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=2048, hop_length=hop)[0]
    flat = librosa.feature.spectral_flatness(y=y, n_fft=2048, hop_length=hop)[0]
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=2048, hop_length=hop)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop, units="time")
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop, units="time")
    harm, perc = librosa.effects.hpss(y)
    h_rms = librosa.feature.rms(y=harm, hop_length=hop)[0]
    p_rms = librosa.feature.rms(y=perc, hop_length=hop)[0]
    # vocal-band energy share (300-3400 Hz) as a crude voice-presence cue
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = (freqs >= 300) & (freqs <= 3400)
    vshare = S[band].sum(0) / (S.sum(0) + 1e-9)
    chroma = librosa.feature.chroma_cqt(y=harm, sr=sr, hop_length=hop)
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    n = min(len(rms), 452)
    per_frame = []
    for i in range(n):
        per_frame.append({
            "frame": i + 1, "t": round(i / FPS, 4),
            "rms_db": round(float(librosa.amplitude_to_db(np.array([rms[i]]), ref=np.max(rms))[0]), 2),
            "centroid_hz": round(float(cent[i]), 1), "flatness": round(float(flat[i]), 4),
            "zcr": round(float(zcr[i]), 4), "onset_strength": round(float(onset_env[i]), 3),
            "harmonic_rms": round(float(h_rms[i]), 5), "percussive_rms": round(float(p_rms[i]), 5),
            "voiceband_share": round(float(vshare[i]), 3),
            "chroma_peak": keys[int(chroma[:, i].argmax())],
        })
    res = {
        "duration_s": round(len(y) / sr, 3),
        "tempo_bpm": float(np.atleast_1d(tempo)[0]),
        "beat_times_s": [round(float(b), 3) for b in beats],
        "beat_frames": [int(round(b * FPS)) + 1 for b in beats],
        "onset_times_s": [round(float(o), 3) for o in onsets],
        "onset_frames": [int(round(o * FPS)) + 1 for o in onsets],
        "global_chroma_profile": {k: round(float(v), 3) for k, v in zip(keys, chroma.mean(1))},
        "per_frame": per_frame,
    }
    json.dump(res, open(out, "w"), ensure_ascii=False)
    print("tempo", res["tempo_bpm"], "beats", len(beats), "onsets", len(onsets))
    print("beat frames", res["beat_frames"])
    print("onset frames", res["onset_frames"])
    # coarse 0.5 s summary
    for s in range(0, n, 15):
        seg = per_frame[s:s + 15]
        print(f"{seg[0]['t']:5.2f}s rms_db={np.mean([p['rms_db'] for p in seg]):6.1f} "
              f"cent={np.mean([p['centroid_hz'] for p in seg]):7.0f} flat={np.mean([p['flatness'] for p in seg]):.3f} "
              f"vband={np.mean([p['voiceband_share'] for p in seg]):.2f} perc/harm={np.mean([p['percussive_rms'] for p in seg])/max(1e-6,np.mean([p['harmonic_rms'] for p in seg])):.2f} "
              f"chroma={max(set(p['chroma_peak'] for p in seg), key=[p['chroma_peak'] for p in seg].count)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
