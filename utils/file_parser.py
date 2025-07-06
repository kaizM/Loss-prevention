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
        
        # Clean up the dataframe for Modisoft format
        # Look for the actual header row with transaction data
        header_row_index = None
        for i in range(min(10, len(df))):
            row_data = df.iloc[i].astype(str)
            row_str = ' '.join(row_data.values).upper()
            if any(keyword in row_str for keyword in ['TRAN DATE', 'TRAN TYPE', 'TENDER', 'GROSS']):
                header_row_index = i
                logging.info(f"Found header row at index {i}: {df.iloc[i].tolist()}")
                break
        
        if header_row_index is not None:
            # Use the found row as column headers
            df.columns = df.iloc[header_row_index].astype(str)
            df = df.iloc[header_row_index + 1:].reset_index(drop=True)
        
        # Clean column names and remove empty columns
        df.columns = [str(col).strip() if pd.notna(col) else f"Col_{i}" for i, col in enumerate(df.columns)]
        df = df.dropna(axis=1, how='all').dropna(axis=0, how='all')
        
        logging.info(f"After cleanup: {len(df)} transactions with columns: {df.columns.tolist()}")
        
        # Define suspicious transaction types (Modisoft specific)
        # Based on your data, we're looking for non-"normal" transaction types
        suspicious_types = ['VOID', 'NO SALE', 'REFUND', 'DISCOUNT REMOVED', 'NO_SALE', 'VOID_TRANSACTION', 'CANCEL', 'COMP', 'RETURN', 'ADJUSTMENT']
        # Note: "normal" transactions are regular sales, everything else is potentially suspicious
        
        # Try to identify columns with improved mapping
        column_mapping = identify_columns(df.columns.tolist())
        
        # Enhanced pattern search for Modisoft data
        if not column_mapping:
            logging.info("Standard column mapping failed, searching for Modisoft patterns...")
            column_mapping = {}
            
            # Search all data for transaction types
            for col in df.columns:
                try:
                    col_name = str(col).upper()
                    sample_data = df[col].astype(str).str.upper().head(20)
                    
                    # Check if this column contains transaction types
                    if any(sus_type in ' '.join(sample_data.values) for sus_type in suspicious_types):
                        column_mapping['transaction_type'] = col
                        logging.info(f"Found transaction types in column: {col}")
                    
                    # Check for date/time columns
                    if any(keyword in col_name for keyword in ['DATE', 'TIME', 'TIMESTAMP']):
                        column_mapping['timestamp'] = col
                        logging.info(f"Found timestamp column: {col}")
                    
                    # Check for amount columns
                    if any(keyword in col_name for keyword in ['AMOUNT', 'TOTAL', 'PRICE', '$']):
                        column_mapping['amount'] = col
                    
                    # Check for cashier columns
                    if any(keyword in col_name for keyword in ['CASHIER', 'CLERK', 'EMPLOYEE']):
                        column_mapping['cashier_id'] = col
                        
                    # Check for register columns
                    if any(keyword in col_name for keyword in ['REGISTER', 'REG', 'TERMINAL']):
                        column_mapping['register_id'] = col
                        
                except Exception as e:
                    logging.warning(f"Error analyzing column {col}: {e}")
                    continue
        
        logging.info(f"Final column mapping: {column_mapping}")
        
        if not column_mapping or 'transaction_type' not in column_mapping:
            # Last resort - show user what we found for manual mapping
            logging.error("Could not automatically identify columns")
            sample_data = df.head(10).to_string()
            logging.info(f"Sample data:\n{sample_data}")
            raise ValueError("Could not identify required columns. Please check the Modisoft export format.")
        
        # Filter for suspicious transactions
        for index, row in df.iterrows():
            try:
                # Get transaction type
                transaction_type = str(row.get(column_mapping.get('transaction_type', ''), '')).upper()
                
                # For Modisoft: flag specific suspicious transaction types
                # Based on your data: "No Sale", "void", etc.
                is_suspicious = (transaction_type.upper() in ['NO SALE', 'VOID', 'REFUND', 'RETURN', 'CANCEL', 'ADJUSTMENT']) or \
                               any(sus_type in transaction_type.upper() for sus_type in suspicious_types)
                
                if is_suspicious:
                    # Parse timestamp
                    timestamp = parse_timestamp(row, column_mapping)
                    
                    if timestamp:
                        # Get cashier name, fallback to register or N/A
                        cashier_name = str(row.get(column_mapping.get('cashier_id', ''), '')).strip()
                        if not cashier_name or cashier_name.lower() in ['nan', 'none', '']:
                            cashier_name = "N/A"
                        
                        # Get register ID and transaction ID
                        register_id = str(row.get(column_mapping.get('register_id', ''), '')).strip()
                        trans_id = str(row.get(column_mapping.get('transaction_id', ''), '')).strip()
                        
                        # Handle missing register/transaction data
                        if not register_id or register_id.lower() in ['nan', 'none', '']:
                            if trans_id and trans_id.isdigit() and trans_id.lower() != 'nan':
                                # Use pattern from transaction ID 
                                register_id = f"REG-{(int(trans_id) % 3) + 1}"  # 3 registers
                            elif cashier_name and cashier_name != "N/A":
                                # Assign register based on cashier
                                register_id = "REG-1"  # Main register for named cashiers
                            else:
                                register_id = "REG-2"  # Default for unnamed transactions
                        
                        # Clean up transaction ID
                        if not trans_id or trans_id.lower() in ['nan', 'none', '']:
                            trans_id = f"TXN-{timestamp.strftime('%H%M%S')}"  # Generate from timestamp
                        
                        # Get amount, ensure it's properly parsed
                        amount_value = row.get(column_mapping.get('amount', ''), 0)
                        amount = parse_amount(amount_value) if amount_value else 0.0
                        
                        suspicious_transaction = {
                            'timestamp': timestamp,
                            'cashier_id': cashier_name,
                            'register_id': register_id,
                            'transaction_type': transaction_type,
                            'transaction_id': trans_id,
                            'amount': amount,
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
        'timestamp': ['tran date', 'date', 'time', 'datetime', 'timestamp', 'trans_date', 'trans_time'],
        'transaction_type': ['tran type', 'type', 'trans_type', 'transaction_type', 'description', 'desc'],
        'amount': ['gross', 'amount', 'total', 'value', 'sum', 'price', 'net'],
        'tender': ['tender', 'payment', 'method', 'payment_type'],
        'discount': ['discount', 'disc', 'reduction'],
        'tax': ['tax', 'taxes'],
        'net_amount': ['net', 'net amount', 'final'],
        'cashier_id': ['cashier name', 'cashier', 'cashier_id', 'employee', 'emp_id', 'clerk', 'operator'],
        'register_id': ['register', 'reg_id', 'terminal', 'pos_id', 'station'],
        'transaction_id': ['tran id', 'trans_id', 'transaction_id', 'receipt', 'receipt_id', 'id'],
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
