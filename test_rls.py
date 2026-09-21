import pytest
import pytest_asyncio
import urllib.request
import json
import jwt
from datetime import datetime, timedelta, timezone
from mcp.client.sse import sse_client
from mcp import ClientSession

SERVER_URL = "http://127.0.0.1:8000"
SECRET_KEY = "super-secret-key"  # Same as in server.py

async def fetch_token(username: str) -> str:
    req = urllib.request.Request(
        f"{SERVER_URL}/login",
        data=json.dumps({"username": username}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())["token"]

async def execute_search(query: str, token: str) -> str:
    async with sse_client(f"{SERVER_URL}/mcp/sse") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            
            result = await session.call_tool(
                "search_documents", 
                {"query": query, "token": token}
            )
            return result.content[0].text

@pytest.mark.asyncio
async def test_hr_user_can_see_hr_docs():
    """Positive Case: Alice (HR) searches for 'salary' and sees the HR document."""
    token = await fetch_token("alice_hr")
    output = await execute_search("salary", token)
    
    assert "Engineering Salary Bands" in output
    assert "No documents found" not in output

@pytest.mark.asyncio
async def test_finance_user_cannot_see_hr_docs():
    """Negative Case: Charlie (Finance) searches for 'lunch' and is blocked by RLS from seeing the complaint log."""
    token = await fetch_token("charlie_fin")
    output = await execute_search("lunch", token)
    
    assert "HR Complaint Log" not in output

@pytest.mark.asyncio
async def test_abac_intern_clearance_blocked():
    """Negative Case: David (HR Intern) has clearance 1, so he CANNOT see 'Executive HR Strategy' (sensitivity 3)."""
    token = await fetch_token("david_hr")
    output = await execute_search("lay off", token)
    
    assert "Executive HR Strategy" not in output

@pytest.mark.asyncio
async def test_abac_explicit_share_override():
    """Positive Case: Charlie (Finance) is EXPLICITLY shared the 'Engineering Salary Bands' doc despite being in Finance."""
    token = await fetch_token("charlie_fin")
    output = await execute_search("salary", token)
    
    assert "Engineering Salary Bands" in output

@pytest.mark.asyncio
async def test_public_docs_visible_to_all():
    """Positive Case: Charlie (Finance) searches for 'Handbook' and CAN see it because it's Public."""
    token = await fetch_token("charlie_fin")
    output = await execute_search("Handbook", token)
    
    assert "Company Handbook" in output

@pytest.mark.asyncio
async def test_invalid_jwt_rejected():
    """Negative Case: A forged/invalid JWT should be rejected immediately."""
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
    
    output = await execute_search("salary", fake_token)
    assert "Error processing tool: Invalid token" in output or "Error" in output

@pytest.mark.asyncio
async def test_expired_jwt_rejected():
    """Negative Case: An expired JWT should be rejected."""
    # Create an artificially expired token
    expired_payload = {
        "sub": "alice_hr",
        "dept_id": 1,
        "exp": datetime.now(timezone.utc) - timedelta(hours=1)
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm="HS256")
    
    output = await execute_search("salary", expired_token)
    assert "Error processing tool: Token has expired" in output or "Error" in output
