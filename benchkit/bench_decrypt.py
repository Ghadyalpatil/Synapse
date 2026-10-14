import sys, os, time, json
sys.argv = ["bench", "--node-id", "D", "--port", "9004"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.join(SCRIPT_DIR, "_run", "run_D"))
sys.path.insert(0, os.getcwd())

from backend.crypto.layered_encryption import layered_encryption

enc_path = os.path.join(SCRIPT_DIR, "enc_times.json")
with open(enc_path) as f:
    enc_data = json.load(f)

ciphertext = enc_data["sample_ciphertext"]
sender_pub = enc_data["sender_public_key"]

# Warm-up
for _ in range(10):
    layered_encryption.decrypt_for_hop(sender_pub, ciphertext)

N = 500
times = []
last_plain = None
for _ in range(N):
    t0 = time.perf_counter()
    plain = layered_encryption.decrypt_for_hop(sender_pub, ciphertext)
    t1 = time.perf_counter()
    times.append((t1 - t0) * 1000.0)
    last_plain = plain

out_path = os.path.join(SCRIPT_DIR, "dec_times.json")
with open(out_path, "w") as f:
    json.dump({"times_ms": times, "decrypted_matches_original": last_plain == enc_data["message"]}, f)

print("DEC_DONE", len(times), "MATCH:", last_plain == enc_data["message"], "->", out_path)
