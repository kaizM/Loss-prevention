import pandas as pd
import os
import logging
from datetime import datetime

def parse_modisoft_file(filepath):
    """
    Parse Modisoft transaction file and extract suspicious transactions.
    
    Args:
        filepath (str): Path to the uploaded file
        
    Returns:
        list: List of suspicious transaction dictionaries
    """
    suspicious_transactions = []
    
    try:
        # Determine file type and read accordingly
        if filepath.lower().endswith('.csv'):
            df = pd.read_csv(filepath)
        elif filepath.lower().endswith(('.xls', '.xlsx')):
            df = pd.read_excel(filepath)
        else:
            raise ValueError("Unsupported file format")
        
        logging.info(f"Loaded file with {len(df)} total transactions")
        logging.info(f"Columns: {df.columns.tolist()}")
        
        # Define suspicious transaction types
        suspicious_types = ['VOID', 'NO SALE', 'REFUND', 'DISCOUNT REMOVED', 'NO_SALE', 'VOID_TRANSACTION']
        
        # Try to identify columns (flexible column mapping)
        column_mapping = identify_columns(df.columns.tolist())
        
        if not column_mapping:
            raise ValueError("Could not identify required columns in the file")
        
        # Filter for suspicious transactions
        for index, row in df.iterrows():
            try:
                # Get transaction type
                transaction_type = str(row.get(column_mapping.get('transaction_type', ''), '')).upper()
                
                # Check if transaction is suspicious
                is_suspicious = any(sus_type in transaction_type for sus_type in suspicious_types)
                
                if is_suspicious:
                    # Parse timestamp
                    timestamp = parse_timestamp(row, column_mapping)
                    
                    if timestamp:
                        suspicious_transaction = {
                            'timestamp': timestamp,
                            'cashier_id': str(row.get(column_mapping.get('cashier_id', ''), '')),
                            'register_id': str(row.get(column_mapping.get('register_id', ''), '')),
                            'transaction_type': transaction_type,
                            'transaction_id': str(row.get(column_mapping.get('transaction_id', ''), '')),
                            'amount': parse_amount(row.get(column_mapping.get('amount', ''), 0)),
                            'pump_number': str(row.get(column_mapping.get('pump_number', ''), '')),
                            'raw_data': row.to_dict(),
                            'total_count': len(df)
                        }
                        
                        suspicious_transactions.append(suspicious_transaction)
                        logging.debug(f"Found suspicious transaction: {transaction_type} at {timestamp}")
                    
            except Exception as e:
                logging.warning(f"Error processing row {index}: {str(e)}")
                continue
        
        logging.info(f"Found {len(suspicious_transactions)} suspicious transactions")
        return suspicious_transactions
        
    except Exception as e:
        logging.error(f"Error parsing file {filepath}: {str(e)}")
        raise

def identify_columns(columns):
    """
    Identify relevant columns from the file headers.
    
    Args:
        columns (list): List of column names
        
    Returns:
        dict: Mapping of standardized column names to actual column names
    """
    column_mapping = {}
    
    # Convert to lowercase for matching
    columns_lower = [col.lower() for col in columns]
    
    # Define possible column name variations
    column_patterns = {
        'timestamp': ['date', 'time', 'datetime', 'timestamp', 'trans_date', 'trans_time'],
        'cashier_id': ['cashier', 'cashier_id', 'employee', 'emp_id', 'clerk', 'operator'],
        'register_id': ['register', 'reg_id', 'terminal', 'pos_id', 'station'],
        'transaction_type': ['type', 'trans_type', 'transaction_type', 'description', 'desc'],
        'transaction_id': ['trans_id', 'transaction_id', 'receipt', 'receipt_id', 'id'],
        'amount': ['amount', 'total', 'value', 'sum', 'price'],
        'pump_number': ['pump', 'pump_no', 'pump_number', 'dispenser', 'fueling_point']
    }
    
    # Try to match columns
    for standard_name, patterns in column_patterns.items():
        for pattern in patterns:
            for i, col in enumerate(columns_lower):
                if pattern in col:
                    column_mapping[standard_name] = columns[i]
                    break
            if standard_name in column_mapping:
                break
    
    logging.info(f"Column mapping: {column_mapping}")
    return column_mapping

def parse_timestamp(row, column_mapping):
    """
    Parse timestamp from row data.
    
    Args:
        row: Pandas row
        column_mapping: Column mapping dictionary
        
    Returns:
        datetime: Parsed timestamp or None
    """
    try:
        # Try to get timestamp from mapped column
        if 'timestamp' in column_mapping:
            timestamp_str = str(row[column_mapping['timestamp']])
            
            # Try common timestamp formats
            timestamp_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%m/%d/%Y %H:%M:%S',
                '%m-%d-%Y %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%m/%d/%Y %H:%M',
                '%Y-%m-%d',
                '%m/%d/%Y'
            ]
            
            for fmt in timestamp_formats:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
            
            # Try pandas to_datetime as fallback
            return pd.to_datetime(timestamp_str)
            
    except Exception as e:
        logging.warning(f"Error parsing timestamp: {str(e)}")
        return None

def parse_amount(amount_str):
    """
    Parse monetary amount from string.
    
    Args:
        amount_str: String representation of amount
        
    Returns:
        float: Parsed amount or 0.0
    """
    try:
        # Remove currency symbols and spaces
        amount_str = str(amount_str).replace('$', '').replace(',', '').strip()
        return float(amount_str)
    except (ValueError, TypeError):
        return 0.0
