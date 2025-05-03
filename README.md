# ETL as a Service

This project sets up an ETL (Extract, Transform, Load) system using a custom Flask web server, Apache Airflow, MySQL, and MinIO. All services are containerized using Docker.

## Prerequisites

- Docker
- Docker Compose

## Setup Instructions

### 1. Clone the repositories

Clone the web server project:

```bash
git clone https://github.com/nth-Tung/etl_as_a_service
cd etl_as_a_service
```

Clone the Airflow project:

```bash
git clone https://github.com/nth-Tung/airflow_docker_postgres
```

### 2. Start MySQL container

Run the following command to start a MySQL container:

```bash
docker run --name mysql -e MYSQL_ROOT_PASSWORD=root -d -v mysql-data:/var/lib/mysql --restart=always mysql:8.0
```

### 3. Start MinIO container

Run the following command to start a MinIO container:

```bash
docker run \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -v minio-data:/data \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  --restart=always \
  quay.io/minio/minio server /data --console-address ":9001"
```

### 4. Build and run the web server

Build the Docker image for the web server:

```bash
docker build -t web_server .
```

Run the web server container:

```bash
docker run --name web-server --restart=always -p 5000:5000 -d web_server
```

### 5. Build and run the Airflow service

Navigate to the Airflow project directory and build the Docker image:

```bash
docker build -t extending_airflow .
```

Run Airflow services using Docker Compose:

```bash
docker-compose up -d
```

### 6. Connect all containers to the same Docker network

Connect MySQL, MinIO, and the web server containers to the Airflow network:

```bash
docker network connect airflow_docker_postgres_network minio
docker network connect airflow_docker_postgres_network mysql
docker network connect airflow_docker_postgres_network web_server
```

### 7. Access the services

- **Web Server**: [http://0.0.0.0:5000](http://0.0.0.0:5000)
- **Airflow**: [http://0.0.0.0:8080](http://0.0.0.0:8080)
- **MinIO Console**: [http://0.0.0.0:9001](http://0.0.0.0:9001)

## Notes

- Make sure Docker and Docker Compose are installed and running before starting.
- Ensure that the Docker network `airflow_docker_postgres_network` is created by Airflow's `docker-compose.yml` before connecting other containers.
- Default credentials:
  - **MinIO**: `minioadmin / minioadmin`
  - **MySQL**: `root / root`
