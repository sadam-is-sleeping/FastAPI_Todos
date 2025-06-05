from fastapi import FastAPI, HTTPException. Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
from pathlib import Path
import logging
import time
from multiprocessing import Queue
from os import getenv
from prometheus_fastapi_instrumentator import Instrumentator
from logging_loki import LokiQueueHandler

app = FastAPI()

# Prometheus 메트릭스 엔드포인트 (/metrics)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

loki_logs_handler = LokiQueueHandler(
    Queue(-1),
    url=getenv("LOKI_ENDPOINT"),
    tags={"application": "fastapi"},
    version="1",
)

# Custom access logger (ignore Uvicorn's default logging)
custom_logger = logging.getLogger("custom.access")
custom_logger.setLevel(logging.INFO)

# Add Loki handler (assuming `loki_logs_handler` is correctly configured)
custom_logger.addHandler(loki_logs_handler)

async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time  # Compute response time

    log_message = (
        f'{request.client.host} - "{request.method} {request.url.path} HTTP/1.1" {response.status_code} {duration:.3f}s'
    )

    # **Only log if duration exists**
    if duration:
        custom_logger.info(log_message)

    return response

is_influxdb_installed = False
try:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS

    is_influxdb_installed = True
except ImportError:
    print("influxdb-client not installed!")

if is_influxdb_installed:
    # token = os.environ.get("INFLUXDB_TOKEN")
    url = "http://influxdb2:8086"
    token = "token"
    org = "sogang"
    bucket = "home"
    write_client = InfluxDBClient(
        # Service name: influxdb2
        url=url,
        token=token,
        org=org,
    )
    write_api = write_client.write_api(write_options=SYNCHRONOUS)

    for value in range(5):
        point = (
            Point("test_measurement")
            .tag("tagname1", "tagvalue1")
            .field("field1", value)
        )
        write_api.write(
            bucket=bucket,
            org=org,
            record=point,
        )


# To-Do Item model
class TodoItem(BaseModel):
    id: int
    title: str
    description: str
    due_to: int
    completed: bool

# set paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / 'templates'
TODO_FILE = BASE_DIR / 'todo.json'
HTML_FILE = TEMPLATE_DIR / 'index.html'

# Load To-Do from JSON file
def load_todos() -> dict:
    if TODO_FILE.is_file():
        with open(TODO_FILE, mode = 'rt', encoding = 'utf-8') as f:
            try:
                if is_influxdb_installed:
                    write_api.write(
                        bucket=bucket,
                        org=org,
                        record=(Point("test_log").field("log", "load")),
                    )
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
    if str(todo_id) in todos:
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
    with open(HTML_FILE, mode = 'rt') as f:
        content = f.read()
    return HTMLResponse(content = content)

# Reorder whole todos
@app.put('/reorder', response_model = dict)
def reorder_todos(ordered_ids: list[int]):
    todos = load_todos()
    ordered_todos = {}
    for todo_id in ordered_ids:
        todo_id_str = str(todo_id)
        if todo_id_str in todos:
            ordered_todos[todo_id_str] = todos[todo_id_str]
    save_todos(ordered_todos)
    return {
        'message': 'To-Do items reordered',
        'data': ordered_ids,
        }
