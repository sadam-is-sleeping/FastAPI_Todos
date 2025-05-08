import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException # Required for some checks
from pathlib import Path
import json

# Assume 'app' is the FastAPI instance in main.py
try:
    from main import app, TODO_FILE, TodoItem
except ImportError:
    # Handle cases where main.py isn't directly importable
    print("Warning: Could not import 'app' from 'main'. Ensure correct path.")
    pytest.skip("Skipping tests: 'main' module not found.", allow_module_level=True)

# Initialize the test client
client = TestClient(app)

# Standard item for reuse in tests
SAMPLE_TODO = {
    "id": 1,
    "title": "Test Todo",
    "description": "Test description",
    "due_to": 1678886400, # Example timestamp (consider using dynamic dates)
    "completed": False
}

# Fixture to manage the todo.json file state for each test
@pytest.fixture(autouse=True)
def manage_todo_file():
    # Ensure clean state before test
    if TODO_FILE.exists():
        TODO_FILE.unlink()
    TODO_FILE.touch() # Create empty file
    save_todos({}) # Initialize with empty JSON object

    yield # Test runs here

    # Clean up after test
    if TODO_FILE.exists():
        TODO_FILE.unlink()

# Helper to save todos (mirrors the one in main.py)
def save_todos(todos: dict):
     with open(TODO_FILE, mode = 'wt', encoding = 'utf-8') as f:
        json.dump(todos, f, ensure_ascii = False, indent = 4)

# --- Basic Endpoint Tests ---

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<h1>To-Do List</h1>" in response.text

def test_create_todo():
    """Test POST /todos to create an item."""
    response = client.post("/todos", json=SAMPLE_TODO)
    assert response.status_code == 200
    data = response.json()
    # Verify response body matches input
    assert data["title"] == SAMPLE_TODO["title"]
    assert data["completed"] == False

    # Verify persistence
    response_get = client.get("/todos")
    assert str(SAMPLE_TODO["id"]) in response_get.json()

def test_get_todos_empty():
    """Test GET /todos when no items exist."""
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == {}

def test_get_todos_with_item():
    """Test GET /todos after creating an item."""
    client.post("/todos", json=SAMPLE_TODO) # Setup
    response = client.get("/todos")
    assert response.status_code == 200
    data = response.json()
    assert str(SAMPLE_TODO["id"]) in data
    assert data[str(SAMPLE_TODO["id"])]["title"] == SAMPLE_TODO["title"]

def test_update_todo():
    """Test PUT /todos/{todo_id} to modify an item."""
    client.post("/todos", json=SAMPLE_TODO) # Setup
    todo_id = SAMPLE_TODO["id"]

    updated_data = SAMPLE_TODO.copy()
    updated_data["title"] = "Updated Test Todo"
    updated_data["completed"] = True

    response = client.put(f"/todos/{todo_id}", json=updated_data)
    assert response.status_code == 200
    data = response.json()
    # Check response reflects updates
    assert data["title"] == "Updated Test Todo"
    assert data["completed"] == True

    # Verify persistence of the update
    response_get = client.get("/todos")
    assert response_get.json()[str(todo_id)]["title"] == "Updated Test Todo"

def test_update_nonexistent_todo():
    """Test PUT /todos/{todo_id} for an item that doesn't exist."""
    response = client.put("/todos/999", json=SAMPLE_TODO) # Use a non-existent ID
    assert response.status_code == 404 # Expect Not Found

def test_delete_todo():
    """Test DELETE /todos/{todo_id} to remove an item."""
    client.post("/todos", json=SAMPLE_TODO) # Setup
    todo_id = SAMPLE_TODO["id"]

    response_delete = client.delete(f"/todos/{todo_id}")
    assert response_delete.status_code == 200
    assert response_delete.json() == {"message": "To-Do item deleted"}

    # Verify item is actually removed
    response_get = client.get("/todos")
    assert str(todo_id) not in response_get.json()

def test_delete_nonexistent_todo():
    """Test DELETE /todos/{todo_id} for an item that doesn't exist."""
    response_delete = client.delete("/todos/999")
    # Current app implementation returns 200 even if item wasn't there.
    assert response_delete.status_code == 200
    assert response_delete.json() == {"message": "To-Do item deleted"}
    # Verify list remains empty/unchanged
    response_get = client.get("/todos")
    assert response_get.json() == {}

# --- Advanced / Edge Case Tests ---

def test_create_todo_invalid_data_validation():
    """Test POST /todos with invalid input (validation errors)."""
    # Missing required field 'title'
    invalid_todo = {k: v for k, v in SAMPLE_TODO.items() if k != 'title'}
    response = client.post("/todos", json=invalid_todo)
    assert response.status_code == 422 # Unprocessable Entity

    # Incorrect data type
    invalid_todo_type = SAMPLE_TODO.copy()
    invalid_todo_type["completed"] = "maybe?"
    response = client.post("/todos", json=invalid_todo_type)
    assert response.status_code == 422

def test_update_todo_invalid_data_validation():
    """Test PUT /todos/{todo_id} with invalid input."""
    client.post("/todos", json=SAMPLE_TODO) # Setup
    todo_id = SAMPLE_TODO["id"]

    # Invalid update payload (missing required field)
    invalid_update_data = {"description": "only description"}
    response = client.put(f"/todos/{todo_id}", json=invalid_update_data)
    assert response.status_code == 422

def test_create_todo_overwrites_existing_id():
    """Test POST /todos uses update logic, overwriting existing IDs."""
    client.post("/todos", json=SAMPLE_TODO) # First item

    # Item with same ID but different content
    colliding_todo = SAMPLE_TODO.copy()
    colliding_todo["title"] = "Overwritten Title"
    response = client.post("/todos", json=colliding_todo)

    # App currently overwrites, so expect 200
    assert response.status_code == 200
    assert response.json()["title"] == "Overwritten Title"

    # Verify only the overwritten item exists
    response_get = client.get("/todos")
    todos = response_get.json()
    assert len(todos) == 1
    assert todos[str(SAMPLE_TODO["id"])]["title"] == "Overwritten Title"

def test_delete_todo_is_idempotent():
    """Test DELETE /todos/{todo_id} behaves idempotently."""
    client.post("/todos", json=SAMPLE_TODO) # Setup
    todo_id = SAMPLE_TODO["id"]

    # First delete
    response1 = client.delete(f"/todos/{todo_id}")
    assert response1.status_code == 200

    # Second delete (should not error)
    response2 = client.delete(f"/todos/{todo_id}")
    # App currently returns 200 even if item was already gone
    assert response2.status_code == 200
    assert response2.json() == {"message": "To-Do item deleted"}

    # Verify item remains deleted
    response_get = client.get("/todos")
    assert str(todo_id) not in response_get.json()

def test_api_handles_corrupted_json_file():
    """Test API gracefully handles loading a malformed todo.json."""
    # Manually corrupt the file
    with open(TODO_FILE, "w") as f:
        f.write("this is not valid json {")

    # GET should handle JSONDecodeError and return empty
    response_get = client.get("/todos")
    assert response_get.status_code == 200
    assert response_get.json() == {}

    # POST should also handle the load error, then save correctly
    response_post = client.post("/todos", json=SAMPLE_TODO)
    assert response_post.status_code == 200

    # Verify the file is now valid and contains the new item
    response_get_after = client.get("/todos")
    assert str(SAMPLE_TODO["id"]) in response_get_after.json()

def test_reorder():
    r1 = client.post("/todos", json=SAMPLE_TODO)
    SAMPLE_TODO2 = SAMPLE_TODO.copy()
    SAMPLE_TODO2.update(
        {
            "id": 2,
            "title": "Test Todo 2",
            "due_to": 1234567,
        }
    )
    r2 = client.post("/todos", json=SAMPLE_TODO2)
    r_reorder = client.post("/reorder", json=[2, 1])
    assert r_reorder.status_code == 200
    assert r_reorder.json().get("data") == [2, 1]
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json().keys() == [2, 1]
