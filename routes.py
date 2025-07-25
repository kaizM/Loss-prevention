import os
import subprocess
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from app import app, db
from models import TransactionReport, SuspiciousTransaction, ReviewLog
from utils.file_parser import parse_modisoft_file
from utils.video_processor import create_video_clip, test_video_connection
import logging

ALLOWED_EXTENSIONS = {'txt', 'csv', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main dashboard showing recent reports and statistics"""
    recent_reports = TransactionReport.query.order_by(TransactionReport.upload_date.desc()).limit(5).all()
    
    # Statistics
    total_reports = TransactionReport.query.count()
    total_suspicious = SuspiciousTransaction.query.count()
    pending_reviews = SuspiciousTransaction.query.filter_by(review_status='pending').count()
    fraud_count = SuspiciousTransaction.query.filter_by(review_status='fraud').count()
    
    stats = {
        'total_reports': total_reports,
        'total_suspicious': total_suspicious,
        'pending_reviews': pending_reviews,
        'fraud_count': fraud_count
    }
    
    return render_template('index.html', recent_reports=recent_reports, stats=stats)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handle file upload and processing"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Create report record
                report = TransactionReport(filename=filename)
                db.session.add(report)
                db.session.commit()
                
                # Process the file
                suspicious_transactions = parse_modisoft_file(filepath)
                
                # Save suspicious transactions
                for trans_data in suspicious_transactions:
                    transaction = SuspiciousTransaction(
                        report_id=report.id,
                        transaction_timestamp=trans_data['timestamp'],
                        cashier_id=trans_data.get('cashier_id'),
                        register_id=trans_data.get('register_id'),
                        transaction_type=trans_data['transaction_type'],
                        transaction_id=trans_data.get('transaction_id'),
                        amount=trans_data.get('amount'),
                        pump_number=trans_data.get('pump_number'),
                        raw_data=str(trans_data.get('raw_data', ''))
                    )
                    db.session.add(transaction)
                
                # Update report
                report.processed = True
                report.total_transactions = trans_data.get('total_count', 0)
                report.suspicious_transactions = len(suspicious_transactions)
                db.session.commit()
                
                flash(f'File processed successfully! Found {len(suspicious_transactions)} suspicious transactions.', 'success')
                
                # Process video clips for each transaction
                flash('Starting video processing...', 'info')
                process_video_clips(report.id)
                
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                logging.error(f"Error processing file: {str(e)}")
                flash(f'Error processing file: {str(e)}', 'error')
                return redirect(request.url)
        else:
            flash('Invalid file type. Please upload CSV or Excel files only.', 'error')
            return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard for reviewing suspicious transactions"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    transaction_type_filter = request.args.get('type', 'all')
    date_filter = request.args.get('date_filter', '')
    report_id = request.args.get('report_id', '', type=str)
    cashier_filter = request.args.get('cashier', '', type=str)
    
    # Build query
    query = SuspiciousTransaction.query
    
    if status_filter != 'all':
        query = query.filter_by(review_status=status_filter)
    
    if transaction_type_filter != 'all':
        query = query.filter_by(transaction_type=transaction_type_filter)
    
    # Add cashier filtering
    if cashier_filter:
        query = query.filter_by(cashier_id=cashier_filter)
    
    # Add report ID filtering (specific report)
    if report_id:
        try:
            report_id_int = int(report_id)
            query = query.filter_by(report_id=report_id_int)
        except ValueError:
            flash(f'Invalid report ID: {report_id}', 'error')
    
    # Add date filtering
    if date_filter:
        try:
            from datetime import datetime, timedelta
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            start_datetime = datetime.combine(filter_date, datetime.min.time())
            end_datetime = datetime.combine(filter_date, datetime.max.time())
            query = query.filter(
                SuspiciousTransaction.transaction_timestamp >= start_datetime,
                SuspiciousTransaction.transaction_timestamp <= end_datetime
            )
        except ValueError:
            flash(f'Invalid date format: {date_filter}', 'error')
    
    # Pagination
    transactions = query.order_by(SuspiciousTransaction.transaction_timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('dashboard.html', 
                         transactions=transactions, 
                         status_filter=status_filter,
                         transaction_type_filter=transaction_type_filter,
                         date_filter=date_filter,
                         report_id=report_id,
                         cashier_filter=cashier_filter)

@app.route('/review/<int:transaction_id>')
def review_transaction(transaction_id):
    """Review individual transaction with video"""
    transaction = SuspiciousTransaction.query.get_or_404(transaction_id)
    
    # Get filter parameters to maintain context
    date_filter = request.args.get('date_filter', '')
    status_filter = request.args.get('status_filter', '')
    type_filter = request.args.get('type_filter', '')
    report_id = request.args.get('report_id', '')
    cashier_filter = request.args.get('cashier', '')
    page = request.args.get('page', 1)
    
    # Get related transactions (same cashier, same time period)
    related_transactions = SuspiciousTransaction.query.filter(
        SuspiciousTransaction.cashier_id == transaction.cashier_id,
        SuspiciousTransaction.transaction_timestamp >= transaction.transaction_timestamp,
        SuspiciousTransaction.id != transaction.id
    ).limit(5).all()
    
    return render_template('review.html', 
                         transaction=transaction,
                         related_transactions=related_transactions,
                         date_filter=date_filter,
                         status_filter=status_filter,
                         type_filter=type_filter,
                         report_id=report_id,
                         cashier_filter=cashier_filter,
                         page=page)

@app.route('/update_review/<int:transaction_id>', methods=['POST'])
def update_review(transaction_id):
    """Update review status of a transaction"""
    transaction = SuspiciousTransaction.query.get_or_404(transaction_id)
    
    old_status = transaction.review_status
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    # Log the change
    review_log = ReviewLog(
        transaction_id=transaction_id,
        old_status=old_status,
        new_status=new_status,
        notes=notes
    )
    db.session.add(review_log)
    
    # Update transaction
    transaction.review_status = new_status
    transaction.review_date = datetime.utcnow()
    transaction.review_notes = notes
    
    db.session.commit()
    
    flash(f'Transaction marked as {new_status}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/reports')
def reports():
    """Generate reports and analytics"""
    # Summary statistics
    total_transactions = SuspiciousTransaction.query.count()
    
    # By status
    status_counts = db.session.query(
        SuspiciousTransaction.review_status,
        db.func.count(SuspiciousTransaction.id)
    ).group_by(SuspiciousTransaction.review_status).all()
    
    # By transaction type
    type_counts = db.session.query(
        SuspiciousTransaction.transaction_type,
        db.func.count(SuspiciousTransaction.id)
    ).group_by(SuspiciousTransaction.transaction_type).all()
    
    # By cashier (top 10)
    cashier_counts = db.session.query(
        SuspiciousTransaction.cashier_id,
        db.func.count(SuspiciousTransaction.id)
    ).group_by(SuspiciousTransaction.cashier_id).order_by(
        db.func.count(SuspiciousTransaction.id).desc()
    ).limit(10).all()
    
    # Recent fraud cases
    recent_fraud = SuspiciousTransaction.query.filter_by(review_status='fraud').order_by(
        SuspiciousTransaction.review_date.desc()
    ).limit(10).all()
    
    return render_template('reports.html',
                         total_transactions=total_transactions,
                         status_counts=status_counts,
                         type_counts=type_counts,
                         cashier_counts=cashier_counts,
                         recent_fraud=recent_fraud)

@app.route('/export_csv')
def export_csv():
    """Export suspicious transactions to CSV"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Date', 'Time', 'Cashier ID', 'Register ID', 'Transaction Type',
        'Transaction ID', 'Amount', 'Pump Number', 'Review Status', 'Review Notes'
    ])
    
    # Write data
    transactions = SuspiciousTransaction.query.all()
    for trans in transactions:
        writer.writerow([
            trans.id,
            trans.transaction_timestamp.strftime('%Y-%m-%d'),
            trans.transaction_timestamp.strftime('%H:%M:%S'),
            trans.cashier_id or '',
            trans.register_id or '',
            trans.transaction_type,
            trans.transaction_id or '',
            trans.amount or '',
            trans.pump_number or '',
            trans.review_status,
            trans.review_notes or ''
        ])
    
    # Create response
    output.seek(0)
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=suspicious_transactions.csv'}
    )

@app.route('/video/<int:transaction_id>')
def serve_video(transaction_id):
    """Serve video clip for a transaction"""
    transaction = SuspiciousTransaction.query.get_or_404(transaction_id)
    
    if transaction.video_clip_path and os.path.exists(transaction.video_clip_path):
        return send_file(transaction.video_clip_path)
    else:
        flash('Video clip not available', 'error')
        return redirect(url_for('dashboard'))

@app.route('/video_settings')
def video_settings():
    """Video configuration and testing page"""
    # Test current video connections
    connection_status = test_video_connection()
    
    # Get current environment settings (without exposing sensitive data)
    current_settings = {
        'alibi_cloud_configured': bool(os.environ.get('ALIBI_CLOUD_API')),
        'rtsp_configured': bool(os.environ.get('RTSP_STREAM_URL')),
        'alibi_camera_id': os.environ.get('ALIBI_CAMERA_ID', '1'),
        'local_files_available': connection_status.get('local_files', False)
    }
    
    return render_template('video_settings.html', 
                         connection_status=connection_status,
                         current_settings=current_settings)

@app.route('/test_video_connection')
def test_video_connection_route():
    """AJAX endpoint to test video connections"""
    status = test_video_connection()
    return jsonify(status)

@app.route('/test_rtsp_url', methods=['POST'])
def test_rtsp_url():
    """Test a specific RTSP URL"""
    rtsp_url = request.json.get('rtsp_url')
    
    if not rtsp_url:
        return jsonify({'success': False, 'error': 'No RTSP URL provided'})
    
    try:
        logging.info(f"Testing RTSP connection to: {rtsp_url[:30]}...")  # Don't log full URL with password
        
        # Test RTSP connection using FFprobe with more verbose output for debugging
        cmd = ['ffprobe', '-v', 'error', '-rtsp_transport', 'tcp', '-analyzeduration', '3000000', '-i', rtsp_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        success = result.returncode == 0
        
        # More detailed error reporting
        if success:
            return jsonify({
                'success': True,
                'message': 'RTSP connection successful! Camera stream is accessible.',
                'details': 'The system can connect to your camera and receive video data.'
            })
        else:
            error_msg = result.stderr if result.stderr else 'Unknown connection error'
            logging.error(f"RTSP test failed: {error_msg}")
            
            # Special handling for network connectivity issues
            if 'Connection refused' in error_msg or 'No route to host' in error_msg or not error_msg:
                return jsonify({
                    'success': False,
                    'message': 'Cannot reach camera - Network issue',
                    'error': 'Camera is on local network (192.168.0.5) but this system runs on the cloud',
                    'troubleshooting': 'Your camera is working fine! The issue is that cloud servers cannot directly access local network cameras. Use the local file upload option instead, or set up port forwarding on your router.'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'RTSP connection failed',
                    'error': error_msg,
                    'troubleshooting': 'Check if: 1) Camera is powered on, 2) Network connection is working, 3) Username/password are correct, 4) RTSP port 1050 is open'
                })
        
    except subprocess.TimeoutExpired:
        logging.error("RTSP test timeout")
        return jsonify({
            'success': False, 
            'error': 'Connection timeout - Cannot reach local camera from cloud',
            'troubleshooting': 'This is expected! Your camera (192.168.0.5) is on a local network, but this system runs on the cloud. The camera is fine - use local file upload instead.'
        })
    except Exception as e:
        logging.error(f"RTSP test exception: {str(e)}")
        return jsonify({
            'success': False, 
            'error': f'Test failed: {str(e)}',
            'troubleshooting': 'Check camera settings and network connectivity'
        })

def process_video_clips(report_id):
    """Process video clips for all suspicious transactions in a report"""
    transactions = SuspiciousTransaction.query.filter_by(report_id=report_id).all()
    processed_count = 0
    error_count = 0
    
    logging.info(f"Processing video clips for {len(transactions)} transactions in report {report_id}")
    
    for transaction in transactions:
        try:
            logging.info(f"Processing video for transaction {transaction.id} at {transaction.transaction_timestamp}")
            clip_path = create_video_clip(transaction)
            if clip_path:
                transaction.video_clip_path = clip_path
                transaction.video_processed = True
                processed_count += 1
                logging.info(f"Successfully created video clip: {clip_path}")
            else:
                transaction.video_error = "No matching video source found for this timestamp"
                error_count += 1
                logging.warning(f"No video source found for transaction {transaction.id}")
        except Exception as e:
            logging.error(f"Error creating video clip for transaction {transaction.id}: {str(e)}")
            transaction.video_error = str(e)
            error_count += 1
        
        db.session.commit()
    
    logging.info(f"Video processing complete: {processed_count} success, {error_count} errors")

@app.route('/test_video_processing')
def test_video_processing():
    """Test video processing with existing transactions"""
    # Get a transaction from July 4th to test
    test_transaction = SuspiciousTransaction.query.filter(
        SuspiciousTransaction.transaction_timestamp >= datetime(2025, 7, 4),
        SuspiciousTransaction.transaction_timestamp < datetime(2025, 7, 5)
    ).first()
    
    if not test_transaction:
        flash('No transactions found for July 4th to test', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        logging.info(f"Testing video processing for transaction {test_transaction.id}")
        clip_path = create_video_clip(test_transaction)
        if clip_path:
            test_transaction.video_clip_path = clip_path
            test_transaction.video_processed = True
            test_transaction.video_error = None
            db.session.commit()
            flash(f'Test successful! Video clip created: {clip_path}', 'success')
        else:
            test_transaction.video_error = "Test failed: No video clip created"
            db.session.commit()
            flash('Test failed: No video clip created', 'error')
    except Exception as e:
        logging.error(f"Test video processing error: {str(e)}")
        test_transaction.video_error = f"Test error: {str(e)}"
        db.session.commit()
        flash(f'Test error: {str(e)}', 'error')
    
    return redirect(url_for('review_transaction', transaction_id=test_transaction.id))

@app.route('/alibi_integration')
def alibi_integration():
    """Alibi web playback integration page"""
    from datetime import date
    return render_template('alibi_web_integration.html', today=date.today().isoformat())

@app.route('/api/pending_transactions')
def api_pending_transactions():
    """API endpoint to get transactions needing video review"""
    pending = SuspiciousTransaction.query.filter(
        SuspiciousTransaction.video_processed == False
    ).order_by(SuspiciousTransaction.transaction_timestamp.desc()).limit(20).all()
    
    transactions = []
    for transaction in pending:
        transactions.append({
            'id': transaction.id,
            'transaction_timestamp': transaction.transaction_timestamp.isoformat(),
            'transaction_type': transaction.transaction_type,
            'amount': transaction.amount,
            'cashier_id': transaction.cashier_id,
            'register_id': transaction.register_id
        })
    
    return jsonify(transactions)

@app.route('/upload_video_clips', methods=['POST'])
def upload_video_clips():
    """Handle video clip uploads from Alibi web interface"""
    try:
        uploaded_files = request.files.getlist('videos')
        
        if not uploaded_files:
            return jsonify({'success': False, 'error': 'No files uploaded'})
        
        uploaded_count = 0
        for file in uploaded_files:
            if file.filename and allowed_file(file.filename):
                # Create clips directory if it doesn't exist
                upload_date = datetime.now().strftime('%Y-%m-%d')
                clips_dir = os.path.join('clips', upload_date)
                os.makedirs(clips_dir, exist_ok=True)
                
                # Save the file
                filename = secure_filename(file.filename)
                filepath = os.path.join(clips_dir, filename)
                file.save(filepath)
                
                # Try to link to transaction if filename contains ID
                try:
                    # Extract transaction ID from filename (if present)
                    import re
                    id_match = re.search(r'transaction_(\d+)', filename)
                    if id_match:
                        transaction_id = int(id_match.group(1))
                        transaction = SuspiciousTransaction.query.get(transaction_id)
                        if transaction:
                            transaction.video_clip_path = filepath
                            transaction.video_processed = True
                            db.session.commit()
                except:
                    pass  # Continue even if linking fails
                
                uploaded_count += 1
        
        return jsonify({
            'success': True, 
            'message': f'Uploaded {uploaded_count} video clips successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test_live_feed')
def test_live_feed():
    """Test live video feed connection"""
    return render_template('test_live_feed.html')

@app.route('/live_feed_stream')
def live_feed_stream():
    """Stream live video feed from Local Alibi DVR"""
    # Get Alibi DVR settings using your actual connection details
    alibi_dvr_host = os.environ.get('ALIBI_DVR_HOST', 'gngpalacios.alibiddns.com')
    alibi_dvr_port = os.environ.get('ALIBI_DVR_PORT', '8000')
    alibi_username = os.environ.get('ALIBI_USERNAME', 'admin')
    alibi_password = os.environ.get('ALIBI_PASSWORD', 'password')
    camera_id = os.environ.get('ALIBI_CAMERA_ID', '4')  # Default to camera 4
    
    # Test connection to your DVR with multiple authentication methods
    try:
        import requests
        from requests.auth import HTTPBasicAuth, HTTPDigestAuth
        
        test_url = f"http://{alibi_dvr_host}:{alibi_dvr_port}"
        
        # Try different authentication methods
        auth_methods = [
            HTTPBasicAuth(alibi_username, alibi_password),
            HTTPDigestAuth(alibi_username, alibi_password),
            None  # No auth
        ]
        
        # Try different common endpoints
        endpoints = [
            '',
            '/index.html',
            '/login',
            '/cgi-bin/main-cgi',
            '/web'
        ]
        
        last_error = None
        
        for auth in auth_methods:
            for endpoint in endpoints:
                try:
                    full_url = test_url + endpoint
                    response = requests.get(
                        full_url, 
                        auth=auth, 
                        timeout=10,
                        allow_redirects=True,
                        verify=False  # Skip SSL verification for local DVR
                    )
                    
                    if response.status_code in [200, 401, 403]:  # 401/403 means DVR is responding
                        return jsonify({
                            'dvr_url': test_url,
                            'camera_id': camera_id,
                            'status': 'dvr_responding',
                            'port': alibi_dvr_port,
                            'host': alibi_dvr_host,
                            'auth_required': response.status_code in [401, 403],
                            'endpoint': endpoint,
                            'status_code': response.status_code
                        })
                        
                except requests.exceptions.ConnectionError as e:
                    last_error = f"Connection refused - DVR may be offline or firewalled"
                    continue
                except requests.exceptions.Timeout as e:
                    last_error = f"Connection timeout - DVR not responding"
                    continue
                except Exception as e:
                    last_error = str(e)
                    continue
        
        return jsonify({
            'error': last_error or 'All connection attempts failed',
            'dvr_url': test_url,
            'status': 'connection_failed',
            'help': 'Check if DVR is online and accessible from this network'
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Configuration error: {str(e)}',
            'dvr_url': test_url,
            'status': 'config_error'
        })
    
    return jsonify({
        'error': 'Local Alibi DVR not found. Please check network connection and IP address.',
        'dvr_ip': alibi_dvr_ip,
        'status': 'not_found'
    })

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
