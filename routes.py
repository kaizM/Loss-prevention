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
                
                # Start video processing in background (simplified for demo)
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
    
    # Build query
    query = SuspiciousTransaction.query
    
    if status_filter != 'all':
        query = query.filter_by(review_status=status_filter)
    
    if transaction_type_filter != 'all':
        query = query.filter_by(transaction_type=transaction_type_filter)
    
    # Pagination
    transactions = query.order_by(SuspiciousTransaction.transaction_timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('dashboard.html', 
                         transactions=transactions, 
                         status_filter=status_filter,
                         transaction_type_filter=transaction_type_filter)

@app.route('/review/<int:transaction_id>')
def review_transaction(transaction_id):
    """Review individual transaction with video"""
    transaction = SuspiciousTransaction.query.get_or_404(transaction_id)
    
    # Get related transactions (same cashier, same time period)
    related_transactions = SuspiciousTransaction.query.filter(
        SuspiciousTransaction.cashier_id == transaction.cashier_id,
        SuspiciousTransaction.transaction_timestamp >= transaction.transaction_timestamp,
        SuspiciousTransaction.id != transaction.id
    ).limit(5).all()
    
    return render_template('review.html', 
                         transaction=transaction,
                         related_transactions=related_transactions)

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
        # Test RTSP connection using FFprobe
        cmd = ['ffprobe', '-v', 'quiet', '-rtsp_transport', 'tcp', '-i', rtsp_url, '-t', '2']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        success = result.returncode == 0
        
        return jsonify({
            'success': success,
            'message': 'RTSP connection successful' if success else 'RTSP connection failed',
            'error': result.stderr if not success else None
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Connection timeout'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def process_video_clips(report_id):
    """Process video clips for all suspicious transactions in a report"""
    transactions = SuspiciousTransaction.query.filter_by(report_id=report_id).all()
    
    for transaction in transactions:
        try:
            clip_path = create_video_clip(transaction)
            if clip_path:
                transaction.video_clip_path = clip_path
                transaction.video_processed = True
            else:
                transaction.video_error = "No matching video found"
        except Exception as e:
            logging.error(f"Error creating video clip for transaction {transaction.id}: {str(e)}")
            transaction.video_error = str(e)
        
        db.session.commit()

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
