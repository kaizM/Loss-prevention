from datetime import datetime
from app import db

class TransactionReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    processed = db.Column(db.Boolean, default=False)
    total_transactions = db.Column(db.Integer, default=0)
    suspicious_transactions = db.Column(db.Integer, default=0)

class SuspiciousTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('transaction_report.id'), nullable=False)
    transaction_timestamp = db.Column(db.DateTime, nullable=False)
    cashier_id = db.Column(db.String(50))
    register_id = db.Column(db.String(50))
    transaction_type = db.Column(db.String(50), nullable=False)  # VOID, REFUND, NO_SALE, DISCOUNT_REMOVED
    transaction_id = db.Column(db.String(100))
    amount = db.Column(db.Float)
    pump_number = db.Column(db.String(10))
    raw_data = db.Column(db.Text)  # Store original row data
    
    # Video clip info
    video_clip_path = db.Column(db.String(500))
    video_processed = db.Column(db.Boolean, default=False)
    video_error = db.Column(db.Text)
    
    # Review info
    review_status = db.Column(db.String(20), default='pending')  # pending, ok, review, fraud
    review_date = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)
    
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    report = db.relationship('TransactionReport', backref=db.backref('suspicious_transactions_list', lazy=True))

class ReviewLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('suspicious_transaction.id'), nullable=False)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    notes = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    transaction = db.relationship('SuspiciousTransaction', backref='review_logs')
