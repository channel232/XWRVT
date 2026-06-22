import os, random, subprocess, threading, time
from pathlib import Path
import gdown

TMP               = Path("/tmp/mjx9render")
XKQT7             = "1sXwstU6lFL2G6msCSYife8GFt_YEmwN4"
RVNM2             = "1KJRX_fSFyyRHhW_Lh846o9POxcrGgqL4"
WDPL9             = "1n-tXny5mhhYmeWEnZl_xi2aXWHnSAqGw"
DURATION          = random.randint(18000, 28800)
AUDIO_BITRATE_K   = 128
FPS               = 1
MIN_SIZE_BYTES    = int(1.0 * 1024 * 1024 * 1024)
MAX_SIZE_BYTES    = int(1.95 * 1024 * 1024 * 1024)
TARGET_IMAGE_NAME = os.environ.get("TARGET_IMAGE_NAME")
if not TARGET_IMAGE_NAME:
    raise SystemExit("TARGET_IMAGE_NAME env var not set.")

TMP.mkdir(exist_ok=True)
(TMP / "xkqt7").mkdir(exist_ok=True)
(TMP / "rvnm2").mkdir(exist_ok=True)
(TMP / "wdpl9").mkdir(exist_ok=True)

xkqt7_dir  = TMP / "xkqt7"
rvnm2_dir  = TMP / "rvnm2"
wdpl9_path = TMP / "wdpl9" / "wdpl9.mp4"

def download_with_timeout(fn, timeout_sec=1800, label="download"):
    result = [None]; error = [None]
    def worker():
        try: result[0] = fn()
        except Exception as e: error[0] = e
    t = threading.Thread(target=worker, daemon=True)
    t.start(); t.join(timeout_sec)
    if t.is_alive(): raise TimeoutError(f"{label} timed out after {timeout_sec}s")
    if error[0]: raise error[0]
    return result[0]

stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free space: {free_gb:.1f} GB")
if free_gb < 4.0:
    raise SystemExit(f"[DISK] Not enough free space ({free_gb:.1f} GB).")

print("Fetching xkqt7...")
try:
    download_with_timeout(
        lambda: gdown.download_folder(id=XKQT7, output=str(xkqt7_dir), quiet=False, use_cookies=False),
        timeout_sec=900, label="xkqt7"
    )
except Exception as e:
    raise SystemExit(f"xkqt7 failed: {e}")

print("Fetching rvnm2...")
try:
    download_with_timeout(
        lambda: gdown.download_folder(id=RVNM2, output=str(rvnm2_dir), quiet=False, use_cookies=False),
        timeout_sec=900, label="rvnm2"
    )
except Exception as e:
    raise SystemExit(f"rvnm2 failed: {e}")

if not wdpl9_path.exists():
    print("Fetching wdpl9...")
    try:
        download_with_timeout(
            lambda: gdown.download(id=WDPL9, output=str(wdpl9_path), quiet=False),
            timeout_sec=300, label="wdpl9"
        )
    except Exception as e:
        raise SystemExit(f"wdpl9 failed: {e}")
else:
    print("wdpl9 already present, skipping.")

matches = list(xkqt7_dir.rglob(TARGET_IMAGE_NAME))
if not matches:
    raise SystemExit(f"Target {TARGET_IMAGE_NAME} not found.")
image_path = matches[0]
print(f"\n>>> FILE   : {image_path.name}")
print(f">>> DURATION: {DURATION}s ({DURATION//60}m {DURATION%60}s)\n")

rvnm2_files = list(rvnm2_dir.glob("*.mp3"))
if not rvnm2_files:
    raise SystemExit("No rvnm2 files found.")
random.shuffle(rvnm2_files)
print("Playback order:")
for i, s in enumerate(rvnm2_files):
    print(f"  {i+1}. {s.name}")

concat_path = TMP / f"clist_{image_path.stem}.txt"
estimated_len = 200
repeats = max(1, (DURATION // (len(rvnm2_files) * estimated_len)) + 2)
with open(concat_path, "w") as f:
    for _ in range(repeats):
        batch = rvnm2_files[:]
        random.shuffle(batch)
        for s in batch:
            f.write(f"file '{s}'\n")

intervals_left = []
intervals_right = []
t = random.randint(360, 840)
while t < DURATION - 10:
    show_dur = random.randint(3, 4)
    end_t = t + show_dur
    if random.random() < 0.5:
        intervals_left.append((t, end_t))
    else:
        intervals_right.append((t, end_t))
    t += random.randint(360, 840)

def make_enable(intervals):
    if not intervals:
        return "0"
    return "+".join([f"between(t,{s},{e})" for s, e in intervals])

enable_left  = make_enable(intervals_left)
enable_right = make_enable(intervals_right)
print(f"Overlay: {len(intervals_left)} left, {len(intervals_right)} right appearances")

output_path = TMP / f"OUT_{image_path.stem}.mp4"

stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free after fetch: {free_gb:.1f} GB")
if free_gb < 2.0:
    raise SystemExit(f"[DISK] Not enough space ({free_gb:.1f} GB free).")

filter_complex = (
    f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p[bg];"
    f"[1:v]scale=220:-1,chromakey=0x00ff00:0.3:0.1[wdpl9_clean];"
    f"[wdpl9_clean]split[wl][wr];"
    f"[bg][wl]overlay=30:H-h-30:enable='{enable_left}'[mid];"
    f"[mid][wr]overlay=W-w-30:H-h-30:enable='{enable_right}'[outv]"
)

cmd = [
    "ffmpeg", "-y",
    "-loop", "1", "-framerate", str(FPS), "-i", str(image_path),
    "-stream_loop", "-1", "-i", str(wdpl9_path),
    "-f", "concat", "-safe", "0", "-i", str(concat_path),
    "-t", str(DURATION),
    "-filter_complex", filter_complex,
    "-map", "[outv]", "-map", "2:a",
    "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
    "-crf", "28", "-r", str(FPS), "-g", str(FPS * 2),
    "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_K}k", "-ar", "44100",
    "-movflags", "+faststart", str(output_path),
]

print("\nRunning FFmpeg...")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
stopped_by_watcher = False
under_minimum = False

def size_watcher():
    global stopped_by_watcher
    while proc.poll() is None:
        time.sleep(15)
        if output_path.exists():
            size = output_path.stat().st_size
            mb = size / (1024 * 1024)
            gb = size / (1024 * 1024 * 1024)
            print(f"[SIZE] {mb:.1f} MB ({gb:.3f} GB)", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] Cap reached — stopping.", flush=True)
                stopped_by_watcher = True
                proc.terminate()
                break

watcher = threading.Thread(target=size_watcher, daemon=True)
watcher.start()
for line in proc.stdout:
    print(line, end="", flush=True)
proc.wait()
watcher.join()

if not stopped_by_watcher and proc.returncode != 0:
    raise SystemExit(f"FFmpeg failed: {proc.returncode}")
if not output_path.exists() or output_path.stat().st_size == 0:
    raise SystemExit("No output produced.")

final_size    = output_path.stat().st_size
final_size_mb = final_size / (1024 * 1024)
final_size_gb = final_size / (1024 * 1024 * 1024)

if final_size < MIN_SIZE_BYTES:
    print(f"[SIZE] ⚠️ Under 1 GB ({final_size_gb:.3f} GB).")
    under_minimum = True

stop_reason = "cap reached" if stopped_by_watcher else "duration reached"
print(f"\nDONE — {output_path}")
print(f"Stop   : {stop_reason}")
print(f"Size   : {final_size_mb:.1f} MB ({final_size_gb:.3f} GB)")
print(f"1–2 GB : {'✅' if MIN_SIZE_BYTES <= final_size <= MAX_SIZE_BYTES else '❌'}")

github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"image_name={image_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"under_minimum={str(under_minimum).lower()}\n")
