import asyncio
import asyncpg
import time
import statistics
from sentence_transformers import SentenceTransformer

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Generate a query vector to use for benchmarking
query = "What is the compensation for technical roles?"
query_vector = model.encode(query).tolist()
vector_str = "[" + ",".join(map(str, query_vector)) + "]"

ITERATIONS = 100

async def measure_query(conn, with_rls: bool):
    latencies = []
    
    # Warmup
    for _ in range(10):
        if with_rls:
            await conn.execute("SELECT set_config('app.current_department_id', '1', false)")
        await conn.fetch(
            "SELECT title, content, 1 - (embedding <=> $1::vector) AS similarity "
            "FROM documents ORDER BY embedding <=> $1::vector LIMIT 3",
            vector_str
        )
    
    # Benchmark
    for _ in range(ITERATIONS):
        start_time = time.perf_counter()
        
        if with_rls:
            await conn.execute("SELECT set_config('app.current_department_id', '1', false)")
        
        await conn.fetch(
            "SELECT title, content, 1 - (embedding <=> $1::vector) AS similarity "
            "FROM documents ORDER BY embedding <=> $1::vector LIMIT 3",
            vector_str
        )
        
        end_time = time.perf_counter()
        latencies.append((end_time - start_time) * 1000) # Convert to ms
        
    return latencies

async def main():
    print("==================================================")
    print(" RLS LATENCY BENCHMARK (100 ITERATIONS) ")
    print("==================================================\n")
    
    print(f"Query: '{query}'")
    print(f"Iterations per test: {ITERATIONS}\n")

    # 1. Connect as ADMIN (Bypasses RLS)
    print("Running baseline benchmark (RLS Disabled / Admin)...")
    admin_conn = await asyncpg.connect(
        user='admin', password='password123', database='mcp_auth_db', host='127.0.0.1', port=5433
    )
    admin_latencies = await measure_query(admin_conn, with_rls=False)
    await admin_conn.close()

    # 2. Connect as APP_USER (Enforces RLS)
    print("Running secure benchmark (RLS Enabled / app_user)...")
    app_conn = await asyncpg.connect(
        user='app_user', password='app_password', database='mcp_auth_db', host='127.0.0.1', port=5433
    )
    app_latencies = await measure_query(app_conn, with_rls=True)
    await app_conn.close()

    # Calculate stats
    admin_avg = statistics.mean(admin_latencies)
    admin_p50 = statistics.median(admin_latencies)
    admin_p90 = statistics.quantiles(admin_latencies, n=10)[8]

    app_avg = statistics.mean(app_latencies)
    app_p50 = statistics.median(app_latencies)
    app_p90 = statistics.quantiles(app_latencies, n=10)[8]

    overhead_p50 = app_p50 - admin_p50

    print("\n================== RESULTS ==================")
    print("WITHOUT RLS (Admin):")
    print(f"  Avg: {admin_avg:.2f} ms")
    print(f"  p50: {admin_p50:.2f} ms")
    print(f"  p90: {admin_p90:.2f} ms")
    
    print("\nWITH RLS (app_user + set_config):")
    print(f"  Avg: {app_avg:.2f} ms")
    print(f"  p50: {app_p50:.2f} ms")
    print(f"  p90: {app_p90:.2f} ms")
    
    print("=============================================")
    print(f"RLS OVERHEAD (p50): ~{overhead_p50:.2f} ms")
    print("=============================================")

if __name__ == '__main__':
    asyncio.run(main())
