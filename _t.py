import os, time
os.environ["DISCORD_WEBHOOK_URL"] = "https://discord.com/api/webhooks/1505078764793495653/0sDW3rfq_ri-NUQeGnk7XKpBx9H96_qoeRMkrSIBlxDqVULkFLC5QBaygx2K_D64laJZ"
import main
t0 = prev = time.time()
for chunk in main.app.stream(main.initial_state(), stream_mode="updates"):
    now = time.time()
    for node in chunk:
        print(f"{node:14} {now-prev:6.1f}s   누적 {now-t0:6.1f}s", flush=True)
    prev = now
print(f"{'합계':14} {time.time()-t0:6.1f}s")
