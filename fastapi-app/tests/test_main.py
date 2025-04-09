import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from main import app, save_todos, load_todos, TodoItem

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # 테스트 전 초기화
    save_todos({})
    yield
    # 테스트 후 정리
    save_todos({})

def test_get_todos_empty():
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == {}

def test_get_todos_with_items():
    todo = TodoItem(
        id = 1,
        title = "Test",
        description = "Test description",
        due_to = 0,
        completed = False)
    save_todos({"1": todo.dict()})
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()["1"]["title"] == "Test"

def test_create_todo():
    todo = {
        "1": {
            "id": 1,
            "title": "Test",
            "description": "Test description",
            "due_to": 0,
            "completed": False
            }
        }
    response = client.post("/todos", json=todo)
    assert response.status_code == 200
    assert response.json()["1"]["title"] == "Test"

def test_create_todo_invalid():
    todo = {"1": {"id": 1, "title": "Test"}}
    response = client.post("/todos", json=todo)
    assert response.status_code == 422

def test_update_todo():
    todo = TodoItem(
        id = 1,
        title = "Test",
        description = "Test description",
        due_to = 0,
        completed = False)
    save_todos({"1": todo.dict()})
    updated_todo = {
        "1": {
            "id": 1,
            "title": "Updated",
            "description": "Updated description",
            "due_to": 0,
            "completed": True}}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 200
    assert response.json()["1"]["title"] == "Updated"

def test_update_todo_not_found():
    updated_todo = {
        "1": {
            "id": 1,
            "title": "Updated",
            "description": "Updated description",
            "due_to": 0,
            "completed": True
            }
        }
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 404

def test_delete_todo():
    todo = TodoItem(
        id = 1,
        title = "Test",
        description = "Test description",
        due_to = 0,
        completed = False)
    save_todos({"1": todo.dict()})
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["message"] == "To-Do item deleted"
    
def test_delete_todo_not_found():
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["message"] == "To-Do item deleted"
