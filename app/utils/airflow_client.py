import requests
from config import Config
import base64

# def trigger_dag(dag_id, conf):
#     url = f"{Config.AIRFLOW_API_URL}/dags/{dag_id}/dagRuns"
#     headers = {'Authorization': f'Bearer {Config.AIRFLOW_API_TOKEN}'}
#     data = {'conf': conf}
#     response = requests.post(url, json=data, headers=headers)
#     response.raise_for_status()

def trigger_dag(dag_id, conf):
    url = f"{Config.AIRFLOW_API_URL}/dags/{dag_id}/dagRuns"
    # Use Basic Auth with admin username:password
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
    response.raise_for_status()
    dag_runs = response.json().get('dag_runs', [])
    return dag_runs[0]['state'] if dag_runs else None