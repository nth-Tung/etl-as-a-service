import requests
from app.config import Config
import base64
from flask import flash
from flask_login import current_user
import ast

def trigger_dag(dag_id, conf):
    url = f"{Config.AIRFLOW_API_URL}/dags/{dag_id}/dagRuns"
    auth = base64.b64encode(f"admin:admin".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json'
    }
    data = {'conf': conf}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

def get_dag_status(dag_id):
    url = f"{Config.AIRFLOW_API_URL}/dags/{dag_id}/dagRuns"
    auth = base64.b64encode(f"admin:admin".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        response.raise_for_status()
        dag_runs = response.json().get('dag_runs', [])
        return dag_runs[0]['state'] if dag_runs else None
    return None

def upload_to_airflow(data_file, dag_file, airflow_api_url, dag_id):
    try:
        # Prepare files to send
        files = {}
        if dag_file:
            files['dag_file'] = (dag_file.filename, dag_file, 'text/x-python')
        if data_file:
            files['data_file'] = (data_file.filename, data_file, 'application/octet-stream')

        if not files:
            flash('No files to upload')
            return False

        auth = base64.b64encode(f"admin:admin".encode()).decode()
        headers = {
            'Authorization': f'Basic {auth}',
        }

        # Send files to /upload_dag endpoint
        response = requests.post(f"{airflow_api_url}/upload_dag", files=files, headers=headers)
        if response.status_code != 200:
            error_msg = response.json().get('error', 'Unknown error')
            flash(f'Error uploading files to Airflow: {error_msg}')
            return False

        # Trigger DAG only if dag_id is provided
        if dag_id:
            trigger_response = requests.post(
                f"{airflow_api_url}/dags/{dag_id}/dagRuns",
                json={"conf": {"uploaded_by": current_user.username}},
                headers={
                    'Authorization': f'Basic {auth}',
                    'Content-Type': 'application/json'
                }
            )
            if trigger_response.status_code != 200:
                flash('Uploaded files, but failed to trigger DAG')

        return True
    except Exception as e:
        flash(f'Error communicating with Airflow: {str(e)}')
        return False



def extract_dag_id(py_file):
    py_file.seek(0)
    content = py_file.read().decode('utf-8')
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'DAG':
                for kw in node.keywords:
                    if kw.arg == 'dag_id':
                        return kw.value.s
        return None
    except (SyntaxError, AttributeError):
        return None