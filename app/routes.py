from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, File
import logging
from werkzeug.security import generate_password_hash
from app.utils.minio_client import upload_to_minio, list_user_files, generate_download_url
from app.utils.airflow_client import trigger_dag, get_dag_status
import os
from datetime import datetime
import uuid

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return redirect(url_for('main.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('main.login'))
    return render_template('register.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    files = File.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', files=files)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        csv_file = request.files.get('csv_file')
        py_file = request.files.get('py_file')
        dag_id = request.form.get('dag_id')
        if not csv_file and not py_file:
            flash('No File')
            return redirect(url_for('main.upload'))

        csv_filename = f"{current_user.id}/{dag_id}_{csv_file.filename}"
        py_filename = f"dags/{dag_id}_{py_file.filename}"

        # # Upload to MinIO
        # logger.debug(f"Uploading to MinIO: {csv_filename}, {py_filename}")
        # upload_to_minio(csv_file, csv_filename)
        # upload_to_minio(py_file, py_filename)

        # Ensure app/dags directory exists
        dag_dir = os.path.join('app', 'dags')
        logger.debug(f"Creating directory if not exists: {dag_dir}")
        os.makedirs(dag_dir, exist_ok=True)

        # Save Python DAG file to ./app/dags for Airflow
        dag_file_path = os.path.join(dag_dir, f"{dag_id}.py")
        logger.debug(f"Saving DAG file to: {dag_file_path}")
        py_file.seek(0)
        py_file.save(dag_file_path)

        # Verify file was saved
        if not os.path.exists(dag_file_path):
            logger.error(f"Failed to save DAG file: {dag_file_path}")
            flash('Error saving DAG file')
            return redirect(url_for('main.upload'))

        # Save to database
        logger.debug(f"Saving file records to database: {dag_id}")
        csv_record = File(user_id=current_user.id, filename=csv_filename, file_type='csv', status='uploaded', dag_id=dag_id)
        py_record = File(user_id=current_user.id, filename=py_filename, file_type='py', status='uploaded', dag_id=dag_id)
        db.session.add(csv_record)
        db.session.add(py_record)
        db.session.commit()

        # Trigger Airflow DAG
        logger.debug(f"Triggering DAG: {dag_id}")
        trigger_dag(dag_id, {'csv_filename': csv_filename, 'py_filename': py_filename})
        csv_record.status = 'processing'
        py_record.status = 'processing'
        db.session.commit()

        flash('Files uploaded and DAG triggered')
        return redirect(url_for('main.dashboard'))

    return render_template('upload.html')


@bp.route('/results')
@login_required
def results():
    files = File.query.filter_by(user_id=current_user.id).all()
    for file in files:
        if file.dag_id and file.status == 'processing':
            status = get_dag_status(file.dag_id)
            file.status = status.lower() if status else 'error'
            db.session.commit()
    return render_template('results.html', files=files)


@bp.route('/files')
@login_required
def files():
    try:
        user_files = list_user_files(current_user.id)
        return render_template('files.html', files=user_files)
    except Exception as e:
        logger.error(f"Failed to list user files: {e}")
        flash('Error loading files from MinIO')
        return redirect(url_for('main.dashboard'))



@bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    # Chỉ cho phép tải file thuộc về user
    if not filename.startswith(f"{current_user.id}/"):
        flash('Unauthorized access to file')
        return redirect(url_for('main.files'))
    try:
        download_url = generate_download_url(filename)
        return redirect(download_url)
    except Exception as e:
        logger.error(f"Failed to generate download URL for {filename}: {e}")
        flash('Error downloading file')
        return redirect(url_for('main.files'))