from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
from pathlib import Path

app = FastAPI()

# To-Do Item model
class TodoItem(BaseModel):
    id: int
    title: str
    description: str
    completed: bool

# set json path
TODO_FILE = Path('todo.json')

# Load To-Do from JSON file
def load_todos() -> dict:
    if TODO_FILE.is_file():
        with open(TODO_FILE, mode = 'rt', encoding = 'utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Save To-Do to JSON file
def save_todos(todos: dict):
    with open(TODO_FILE, mode = 'wt', encoding = 'utf-8') as f:
        json.dump(todos, f, ensure_ascii = False, indent = 4)

# Get To-Do list
@app.get('/todos', response_model = dict[str, TodoItem])
def get_todos():
    return load_todos()

# Add new To-Do item
@app.post('/todos', response_model = TodoItem)
def create_todo(todo: TodoItem):
    todos = load_todos()
    todos.update({
        str(todo.id): todo.dict()})
    save_todos(todos)
    return todo

# Edit To-Do item
@app.put('/todos/{todo_id}', response_model = TodoItem)
def update_todo(todo_id: int, updated_todo: TodoItem):
    todos = load_todos()
    todos[str(todo_id)].update(updated_todo.dict())
    save_todos(todos)
    return updated_todo
    raise HTTPException(status_code = 404, detail = 'To-Do item not found')

# Delete To-Do item
@app.delete('/todos/{todo_id}', response_model = dict)
def delete_todo(todo_id: int):
    todos = load_todos()
    todos.pop(str(todo_id), None)
    save_todos(todos)
    return {'message': 'To-Do item deleted'}

# Serve HTML file
@app.get('/', response_class = HTMLResponse)
def root():
    with open('templates/index.html', mode = 'rt') as f:
        content = f.read()
    return HTMLResponse(content = content)
