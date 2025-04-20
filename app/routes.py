from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, File
import logging
from app.config import Config
from app.utils.minio_client import list_user_files, generate_download_url
from app.utils.airflow_client import get_dag_status, upload_to_airflow, extract_dag_id
import os

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
        data_file = request.files.get('data_file')
        py_file = request.files.get('py_file')

        if not data_file and not py_file:
            flash('At least one file is required')
            return redirect(url_for('main.upload'))

        airflow_api_url = Config.AIRFLOW_API_URL
        records = []

        # Handle DAG file (py_file)
        if py_file:
            if not py_file.filename.endswith('.py'):
                flash('DAG file must be a .py file')
                return redirect(url_for('main.upload'))

            # Extract dag_id from file
            dag_id = extract_dag_id(py_file)
            if not dag_id:
                flash('Could not extract dag_id from DAG file')
                return redirect(url_for('main.upload'))

            # Reset file pointer after reading
            py_file.seek(0)

            # Upload to Airflow
            if not upload_to_airflow(data_file, py_file, airflow_api_url, dag_id):
                return redirect(url_for('main.upload'))

            # Create database record for py_file
            py_record = File(
                user_id=current_user.id,
                filename=py_file.filename,
                file_type='py',
                status='processing',
                dag_id=dag_id
            )
            records.append(py_record)
        elif data_file:
            # Handle data file only (no py_file)
            # Optionally upload to Airflow without triggering a DAG
            if not upload_to_airflow(data_file, None, airflow_api_url, None):
                return redirect(url_for('main.upload'))

        # Handle data file (if provided)
        if data_file:
            _, file_ext = os.path.splitext(data_file.filename)
            file_type = file_ext.lstrip('.').lower() or 'unknown'
            data_record = File(
                user_id=current_user.id,
                filename=data_file.filename,
                file_type=file_type,
                status='uploaded',
                dag_id=None
            )
            records.append(data_record)

        # Save all records to the database
        for record in records:
            db.session.add(record)
        db.session.commit()

        flash('Files uploaded successfully')
        return redirect(url_for('main.dashboard'))

    return render_template('upload.html')

@bp.route('/results')
@login_required
def results():
    files = File.query.filter_by(user_id=current_user.id).all()
    for file in files:
        if file.dag_id and file.status == 'processing':
            status = get_dag_status(file.dag_id)
            file.status = status.lower() if status else 'waiting'
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
    # if not filename.startswith(f"{current_user.id}/"):
    #     flash('Unauthorized access to file')
    #     return redirect(url_for('main.files'))
    try:
        download_url = generate_download_url(filename)
        return redirect(download_url)
    except Exception as e:
        logger.error(f"Failed to generate download URL for {filename}: {e}")
        flash('Error downloading file')
        return redirect(url_for('main.files'))


