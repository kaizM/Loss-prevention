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
        # Determine file type and read accordingly with better error handling
        if filepath.lower().endswith('.csv'):
            # Try different encodings for CSV
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    df = pd.read_csv(filepath, encoding=encoding)
                    break
                except:
                    continue
            else:
                raise ValueError("Could not read CSV file with any encoding")
        elif filepath.lower().endswith(('.xls', '.xlsx')):
            # Try reading Excel with different parameters
            try:
                # First try normal read
                df = pd.read_excel(filepath)
            except Exception as e1:
                try:
                    # Try with different engines
                    df = pd.read_excel(filepath, engine='openpyxl')
                except Exception as e2:
                    try:
                        # Try reading with xlrd for .xls files
                        df = pd.read_excel(filepath, engine='xlrd')
                    except Exception as e3:
                        try:
                            # Try skipping problematic rows
                            df = pd.read_excel(filepath, skiprows=1)
                        except Exception as e4:
                            logging.error(f"All Excel reading attempts failed: {e1}, {e2}, {e3}, {e4}")
                            raise ValueError("Could not read Excel file with any method")
        else:
            raise ValueError("Unsupported file format")
        
        logging.info(f"Loaded file with {len(df)} total transactions")
        logging.info(f"Columns: {df.columns.tolist()}")
        
        # Clean up the dataframe - remove header rows and empty columns
        # Check if first few rows contain headers/titles
        for skip_rows in range(min(5, len(df))):
            if df.iloc[skip_rows].astype(str).str.contains('Date|Time|Tran|Transaction', case=False, na=False).any():
                # Found header row, use it as column names
                new_columns = df.iloc[skip_rows].tolist()
                df = df.iloc[skip_rows+1:].reset_index(drop=True)
                df.columns = new_columns
                break
        
        # Drop completely empty columns and rows
        df = df.dropna(axis=1, how='all').dropna(axis=0, how='all')
        
        logging.info(f"After cleanup: {len(df)} transactions with columns: {df.columns.tolist()}")
        
        # Define suspicious transaction types
        suspicious_types = ['VOID', 'NO SALE', 'REFUND', 'DISCOUNT REMOVED', 'NO_SALE', 'VOID_TRANSACTION']
        
        # Try to identify columns (flexible column mapping)
        column_mapping = identify_columns(df.columns.tolist())
        
        # If standard mapping fails, search for data patterns
        if not column_mapping:
            logging.info("Standard column mapping failed, searching for data patterns...")
            
            # Look for transaction type data in any column
            for col in df.columns:
                try:
                    col_values = df[col].astype(str).str.upper()
                    if any(sus_type in ' '.join(col_values.values) for sus_type in suspicious_types):
                        column_mapping['transaction_type'] = col
                        logging.info(f"Found transaction types in column: {col}")
                        break
                except:
                    continue
            
            # Look for date/time columns
            for col in df.columns:
                try:
                    if 'date' in str(col).lower() or 'time' in str(col).lower():
                        column_mapping['timestamp'] = col
                        break
                except:
                    continue
        
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
