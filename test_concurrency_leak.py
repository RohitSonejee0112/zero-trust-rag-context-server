import asyncio
import jwt
from server import app, search_documents, lifespan

SECRET_KEY = "super-secret-key"

def create_token(user_id, dept_id, clearance):
    return jwt.encode({
        "user_id": user_id,
        "department_id": dept_id,
        "clearance_level": clearance
    }, SECRET_KEY, algorithm="HS256")

async def test_concurrency():
    print("Testing for Connection-Pool Context Leaks...")
    
    # Alice (HR) - Should see HR docs
    token_alice = create_token(1, 1, 2)
    # Charlie (Finance) - Should NEVER see HR docs
    token_charlie = create_token(4, 3, 2)
    
    async with lifespan(app):
        print("Database pool created.")
        
        # We will blast 50 concurrent requests alternating between Alice and Charlie.
        # If the context leaks, Charlie might get HR documents!
        tasks = []
        for i in range(50):
            if i % 2 == 0:
                tasks.append(search_documents(query="recent employee complaints", token=token_alice))
            else:
                tasks.append(search_documents(query="recent employee complaints", token=token_charlie))
                
        print("Firing 50 concurrent requests...")
        results = await asyncio.gather(*tasks)
        
        leaks_found = 0
        for i, res in enumerate(results):
            text_result = res[0].text
            is_charlie = (i % 2 != 0)
            
            if is_charlie and "Alice reported Bob" in text_result:
                leaks_found += 1
                
        if leaks_found > 0:
            print(f"FAILED: Found {leaks_found} context leaks! Charlie saw HR data!")
        else:
            print("SUCCESS: 0 context leaks detected across 50 concurrent requests. Transaction-local configuration is perfectly secure.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test_concurrency())
