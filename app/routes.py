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
import ast
from werkzeug.utils import secure_filename

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



def extract_dag_id_from_file(py_file_stream):
    """
    Đọc nội dung file và trích xuất giá trị của biến 'dag_id' (nếu có).
    Trả về chuỗi dag_id hoặc None nếu không tìm thấy.
    """
    try:
        file_content = py_file_stream.read().decode('utf-8')
        tree = ast.parse(file_content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'dag_id':
                        if isinstance(node.value, ast.Str):
                            return node.value.s
        return None
    except Exception as e:
        print(f"Error parsing DAG file: {e}")
        return None


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        data_file = request.files.get('data_file')
        py_file = request.files.get('py_file')
        dag_id = request.form.get('dag_id')

        # Kiểm tra ít nhất một file được upload
        if not data_file and not py_file:
            flash('At least one file is required')
            return redirect(url_for('main.upload'))

        # Đảm bảo dag_id được cung cấp khi upload file .py
        if py_file and not dag_id:
            flash('DAG ID is required for Python DAG files')
            return redirect(url_for('main.upload'))
        if py_file and dag_id:
            dag_id_from_file = extract_dag_id_from_file(py_file.stream)
            py_file.stream.seek(0)  # reset file pointer để không bị lỗi ở bước upload tiếp theo

            if not dag_id.isidentifier() or ' ' in dag_id:
                flash('DAG ID must be a valid Python identifier (no spaces or special characters)')
                return redirect(url_for('main.upload'))

            if dag_id_from_file and dag_id != dag_id_from_file:
                flash(
                    f'DAG ID must match the "dag_id" defined in the uploaded Python file (found "{dag_id_from_file}")')
                return redirect(url_for('main.upload'))


        # Tạo thư mục app/dags nếu chưa tồn tại
        dag_dir = os.path.join('app', 'dags')
        os.makedirs(dag_dir, exist_ok=True)

        if data_file:
            # Dùng tên gốc
            data_dag_filename = secure_filename(data_file.filename)
            data_dag_path = os.path.join(dag_dir, data_dag_filename)

            logger.debug(f"Saving data file to Airflow dags: {data_dag_path}")
            data_file.seek(0)
            data_file.save(data_dag_path)

            if not os.path.exists(data_dag_path):
                logger.error(f"Failed to save data file: {data_dag_path}")
                flash('Error saving data file')
                return redirect(url_for('main.upload'))

            # Xác định loại file qua đuôi
            _, file_ext = os.path.splitext(data_file.filename)
            file_type = file_ext.lstrip('.').lower() or 'unknown'

            data_record = File(
                user_id=current_user.id,
                filename=data_dag_filename,
                file_type=file_type,
                status='uploaded',
                dag_id=dag_id if dag_id else None
            )
            db.session.add(data_record)

        # Xử lý file Python DAG
        if py_file:
            py_uuid = uuid.uuid4()
            py_filename = f"dags/{py_uuid}_{py_file.filename}"
            py_dag_path = os.path.join(dag_dir, f"{dag_id}.py")

            logger.debug(f"Saving PY to Airflow dags: {py_dag_path}")
            py_file.seek(0)
            py_file.save(py_dag_path)

            if not os.path.exists(py_dag_path):
                logger.error(f"Failed to save PY file: {py_dag_path}")
                flash('Error saving PY file')
                return redirect(url_for('main.upload'))

            py_record = File(
                user_id=current_user.id,
                filename=py_filename,
                file_type='py',
                status='processing',  # Đặt trạng thái processing vì DAG sẽ chạy
                dag_id=dag_id
            )
            db.session.add(py_record)

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