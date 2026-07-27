import torch
import time

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    print("❌ No CUDA GPU found!")
    exit(1)

print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB")

# ── Warmup ───────────────────────────────────────────────────────────────────
print("\n🔥 Warming up...")
x = torch.randn(4096, 4096, device='cuda')
y = torch.randn(4096, 4096, device='cuda')
for _ in range(10):
    z = torch.matmul(x, y)
torch.cuda.synchronize()

# ── Benchmark: Matrix Multiplication ─────────────────────────────────────────
print("\n🚀 Running benchmark (matrix multiplication 4096x4096)...")
iterations = 500
start = time.time()
for i in range(iterations):
    z = torch.matmul(x, y)
    if i % 100 == 0:
        mem = torch.cuda.memory_allocated() / 1024**3
        print(f"   iter {i}/{iterations} | GPU mem: {mem:.2f} GB")
torch.cuda.synchronize()
elapsed = time.time() - start

print(f"\n✅ Done: {iterations} iterations in {elapsed:.2f}s")
print(f"   Avg: {elapsed/iterations*1000:.2f} ms per matmul")
print(f"   ~{(iterations / elapsed):.0f} matmuls/sec")

# ── Keep GPU busy for monitoring observation ─────────────────────────────────
print("\n⏳ Keeping GPU busy for 30s (for monitoring observation)...")
start = time.time()
while time.time() - start < 30:
    z = torch.matmul(x, y)
    mem = torch.cuda.memory_allocated() / 1024**3
    util = torch.cuda.utilization() if hasattr(torch.cuda, 'utilization') else 'N/A'
    print(f"   GPU util: {util} | mem: {mem:.2f} GB", end='\r')
torch.cuda.synchronize()
print("\n✅ Benchmark complete.")