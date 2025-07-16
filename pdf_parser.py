import pandas as pd
import pdfplumber
import re
from datetime import datetime
import os
import tempfile
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import io

logger = logging.getLogger(__name__)

class PDFTransactionParser:
    def __init__(self):
        self.supported_banks = {
            'maybank': self._parse_maybank,
            'cimb': self._parse_cimb,
            'alliance': self._parse_alliance,
            'credit_card': self._parse_credit_card
        }
        
    def detect_bank_type(self, pdf_text: str) -> str:
        """Detect bank type from PDF text content"""
        text_lower = pdf_text.lower()
        
        # Check for bank-specific keywords first (more reliable)
        if 'maybank' in text_lower or 'malayan banking' in text_lower or 'maybank islamic' in text_lower:
            # Check if it's specifically a credit card statement
            if 'credit card statement' in text_lower or 'card statement' in text_lower:
                return 'credit_card'
            return 'maybank'
        elif 'cimb' in text_lower or 'commerce international' in text_lower:
            if 'credit card statement' in text_lower or 'card statement' in text_lower:
                return 'credit_card'
            return 'cimb'
        elif 'alliance' in text_lower or 'alliance bank' in text_lower:
            if 'credit card statement' in text_lower or 'card statement' in text_lower:
                return 'credit_card'
            return 'alliance'
        
        # Only check for generic credit card indicators if no bank is identified
        if ('credit card' in text_lower and 'statement' in text_lower) or \
           ('mastercard' in text_lower and 'statement' in text_lower) or \
           ('visa' in text_lower and 'statement' in text_lower):
            return 'credit_card'
        
        # Default fallback
        return 'maybank'
    
    def process_pdf(self, pdf_path: str, processing_id: str, bank_type: str = None) -> Dict[str, Any]:
        """Main method to process PDF and extract transactions"""
        start_time = datetime.now()
        
        try:
            logger.info(f"Opening PDF file: {pdf_path}")
            
            # Extract text from PDF
            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"PDF opened successfully, pages: {len(pdf.pages)}")
                all_text = ""
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    logger.info(f"Page {i+1} text length: {len(page_text) if page_text else 0}")
                    if page_text:
                        all_text += page_text + "\n"
                
                logger.info(f"Total extracted text length: {len(all_text)}")
                logger.info(f"First 500 characters: {all_text[:500]}")
            
            # Use provided bank type or detect from content
            if bank_type:
                logger.info(f"Using provided bank type: {bank_type}")
                detected_bank_type = bank_type
            else:
                detected_bank_type = self.detect_bank_type(all_text)
                logger.info(f"Auto-detected bank type: {detected_bank_type}")
            
            # Parse based on bank type
            parser_func = self.supported_banks.get(detected_bank_type)
            if not parser_func:
                raise ValueError(f"Unsupported bank type: {detected_bank_type}")
            
            # Parse transactions
            logger.info(f"Starting transaction parsing with {detected_bank_type} parser")
            transactions = parser_func(pdf_path)
            logger.info(f"Parsed {len(transactions)} transactions")
            
            if transactions:
                logger.info(f"Sample transaction: {transactions[0]}")
            else:
                logger.warning("No transactions found during parsing")
            
            # Generate CSV content
            csv_content = self._generate_csv(transactions, detected_bank_type)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Generate summary
            summary = self._generate_summary(transactions)
            
            return {
                'success': True,
                'bank_type': detected_bank_type,
                'transactions': transactions,
                'csv_content': csv_content,
                'processing_time': processing_time,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'bank_type': None,
                'transactions': [],
                'csv_content': None,
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
    
    def _parse_maybank(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Parse Maybank PDF statement"""
        transactions = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                in_transaction_section = False
                continuation_line = ""
                
                for line in lines:
                    line = line.strip()
                    
                    # Check if we're in transaction section
                    if "URUSNIAGA AKAUN" in line or "ACCOUNT TRANSACTIONS" in line:
                        in_transaction_section = True
                        continue
                    
                    # Check if we've reached the end
                    if "ENDING BALANCE" in line or "BAKI AKHIR" in line:
                        in_transaction_section = False
                        continue
                    
                    if not in_transaction_section:
                        continue
                    
                    # Handle continuation lines
                    if continuation_line:
                        line = continuation_line + " " + line
                        continuation_line = ""
                    
                    # Maybank transaction pattern: Date Amount Balance Description
                    date_pattern = r'(\d{2}/\d{2}/\d{4})'
                    amount_pattern = r'([\d,]+\.\d{2})'
                    
                    match = re.search(f'{date_pattern}.*?{amount_pattern}.*?{amount_pattern}(.+)', line)
                    
                    if match:
                        date_str = match.group(1)
                        amount_str = match.group(2)
                        balance_str = match.group(3)
                        description = match.group(4).strip()
                        
                        # Parse date
                        try:
                            transaction_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                        except ValueError:
                            continue
                        
                        # Parse amount
                        try:
                            amount = float(amount_str.replace(',', ''))
                            balance = float(balance_str.replace(',', ''))
                        except ValueError:
                            continue
                        
                        # Determine transaction type based on balance change
                        transaction_type = 'debit' if amount > 0 else 'credit'
                        
                        transactions.append({
                            'date': transaction_date.isoformat(),
                            'description': description,
                            'amount': amount,
                            'balance': balance,
                            'transaction_type': transaction_type,
                            'bank': 'maybank'
                        })
                    else:
                        # Check if this might be a continuation line
                        if line and not re.search(r'\d{2}/\d{2}/\d{4}', line):
                            continuation_line = line
        
        return transactions
    
    def _parse_cimb(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Parse CIMB Bank PDF statement using reference format"""
        transactions = []
        in_transaction_table = False
        current_transaction = None
        
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"CIMB parser processing PDF with {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                lines = text.split('\n')
                
                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    
                    logger.debug(f"Line {line_num + 1}: {line}")
                    
                    # Detect start of transaction table for CIMB Bank
                    if 'Date Description Cheque / Ref No Withdrawal Deposits Tax Balance' in line:
                        logger.info("Found CIMB Bank transaction table header")
                        in_transaction_table = True
                        continue
                    
                    # Skip bilingual header line
                    if 'Tarikh Diskripsi No Cek / Rujukan Pengeluaran Deposit Cukai Baki' in line:
                        logger.info("Skipping bilingual header")
                        continue
                    
                    # Skip amount header line
                    if line == '(RM) (RM) (RM) (RM)':
                        logger.info("Skipping amount header")
                        continue
                    
                    # Check for OPENING BALANCE
                    if 'OPENING BALANCE' in line:
                        logger.info("Found OPENING BALANCE")
                        continue
                    
                    # Check for CLOSING BALANCE to stop processing
                    if 'CLOSING BALANCE' in line or 'BAKI PENUTUP' in line:
                        logger.info("Found CLOSING BALANCE - stopping transaction processing")
                        if current_transaction:
                            transactions.append(current_transaction)
                            current_transaction = None
                        break
                    
                    if not in_transaction_table:
                        continue
                    
                    # CIMB Bank transaction pattern: DD/MM/YYYY at start of line
                    date_pattern = r'^(\d{2}/\d{2}/\d{4})\s+(.+)$'
                    date_match = re.search(date_pattern, line)
                    
                    if date_match:
                        # If we have a previous transaction, finalize it
                        if current_transaction:
                            transactions.append(current_transaction)
                        
                        logger.info("Found CIMB Bank transaction start")
                        
                        date_str = date_match.group(1)  # DD/MM/YYYY format
                        rest_of_line = date_match.group(2).strip()
                        
                        # Convert date format
                        try:
                            transaction_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                            
                            # Initialize transaction
                            current_transaction = {
                                'date': transaction_date.isoformat(),
                                'description': '',
                                'cheque_no': '',
                                'amount': 0.0,
                                'balance': 0.0,
                                'transaction_type': 'debit',
                                'bank': 'cimb',
                                'is_parsing': True
                            }
                            
                            # Parse the rest of the line to extract description and amounts
                            self._parse_cimb_transaction_line(current_transaction, rest_of_line)
                            
                            logger.info(f"Started transaction: {current_transaction['description']} - {current_transaction['amount']}")
                            
                        except ValueError as e:
                            logger.warning(f"Error parsing date {date_str}: {e}")
                            continue
                    else:
                        # This might be a continuation line for the current transaction
                        if current_transaction and current_transaction.get('is_parsing', False):
                            logger.debug("Processing continuation line for current transaction")
                            self._parse_cimb_continuation_line(current_transaction, line)
                        elif current_transaction:
                            # Transaction is complete, but this might be additional info
                            logger.debug("Processing additional info for complete transaction")
                            self._parse_cimb_continuation_line(current_transaction, line)
                
                # Add any remaining transaction
                if current_transaction:
                    transactions.append(current_transaction)
                    current_transaction = None
        
        # Clean up transactions
        self._finalize_cimb_transactions(transactions)
        
        logger.info(f"CIMB parser found {len(transactions)} transactions")
        return transactions
    
    def _parse_cimb_transaction_line(self, transaction, line):
        """Parse a CIMB transaction line to extract description, reference, and amounts"""
        # Look for amounts at the end of the line (two consecutive amounts typically)
        amount_pattern = r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$'
        amount_match = re.search(amount_pattern, line)
        
        if amount_match:
            # Found amounts - extract them
            transaction['amount'] = float(amount_match.group(1).replace(',', ''))
            transaction['balance'] = float(amount_match.group(2).replace(',', ''))
            
            # The part before amounts could be description + optional cheque number
            description_part = line[:amount_match.start()].strip()
            
            # Check if there's a reference number at the end of the description part
            ref_pattern = r'^(.+?)\s+([A-Z0-9]{8,})\s*$'
            ref_match = re.search(ref_pattern, description_part)
            
            if ref_match:
                # Found description + reference number on same line
                transaction['description'] = ref_match.group(1).strip()
                transaction['cheque_no'] = ref_match.group(2).strip()
            else:
                # Just description, no reference number on same line
                transaction['description'] = description_part
            
            transaction['is_parsing'] = False  # Complete transaction
        else:
            # No amounts found, this is just the description start
            transaction['description'] = line.strip()
            # Keep parsing for continuation lines
    
    def _parse_cimb_continuation_line(self, transaction, line):
        """Parse a continuation line for a CIMB transaction"""
        # Check if this line contains amounts (end of transaction)
        amount_pattern = r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$'
        amount_match = re.search(amount_pattern, line)
        
        if amount_match:
            # Found amounts - this completes the transaction
            if transaction['amount'] == 0.0:  # Only set if not already set
                transaction['amount'] = float(amount_match.group(1).replace(',', ''))
            transaction['balance'] = float(amount_match.group(2).replace(',', ''))
            
            # The rest might be additional description before the amounts
            description_part = line[:amount_match.start()].strip()
            if description_part:
                if transaction['description']:
                    transaction['description'] += f" {description_part}"
                else:
                    transaction['description'] = description_part
            
            transaction['is_parsing'] = False  # Complete transaction
        else:
            # Check if this is a numeric continuation of cheque number (like "1509")
            numeric_pattern = r'^\d{1,4}$'
            if re.match(numeric_pattern, line.strip()) and transaction['cheque_no']:
                # This is likely a continuation of the cheque number
                transaction['cheque_no'] += line.strip()
                logger.debug(f"Extended cheque number to: {transaction['cheque_no']}")
            else:
                # This is additional description
                # Skip obvious non-description lines
                skip_patterns = [
                    r'^\s*$',  # Empty lines
                    r'PRIVATE TRANSACTION',
                    r'^\s*[\d,]+\.\d{2}\s*$',  # Just amounts
                ]
                
                should_skip = False
                for pattern in skip_patterns:
                    if re.match(pattern, line, re.IGNORECASE):
                        should_skip = True
                        break
                
                if not should_skip and line.strip():
                    if transaction['description']:
                        transaction['description'] += f" {line.strip()}"
                    else:
                        transaction['description'] = line.strip()
                    logger.debug(f"Added to description: {line.strip()}")
    
    def _finalize_cimb_transactions(self, transactions):
        """Finalize CIMB transactions by cleaning up and determining debit/credit"""
        # Remove incomplete transactions
        transactions[:] = [t for t in transactions if not t.get('is_parsing', False)]
        
        # Clean up transaction objects
        for transaction in transactions:
            transaction.pop('is_parsing', None)
            
            # Clean up description and reference
            transaction['description'] = transaction['description'].strip()
            if 'cheque_no' in transaction:
                transaction['cheque_no'] = transaction['cheque_no'].strip()
        
        # Determine debit/credit based on balance changes
        for i, transaction in enumerate(transactions):
            if i == 0:
                # First transaction - assume it's based on amount sign
                if transaction['balance'] > (transaction['balance'] - transaction['amount']):
                    transaction['transaction_type'] = 'credit'
                else:
                    transaction['transaction_type'] = 'debit'
                    transaction['amount'] = -abs(transaction['amount'])
            else:
                # Compare with previous transaction balance
                prev_balance = transactions[i-1]['balance']
                if transaction['balance'] > prev_balance:
                    transaction['transaction_type'] = 'credit'
                    transaction['amount'] = abs(transaction['amount'])
                else:
                    transaction['transaction_type'] = 'debit'
                    transaction['amount'] = -abs(transaction['amount'])
            
            logger.debug(f"Processed transaction {i+1}: Amount = {transaction['amount']}")
    
    def _parse_alliance(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Parse Alliance Bank PDF statement"""
        transactions = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                in_transaction_section = False
                continuation_line = ""
                
                for line in lines:
                    line = line.strip()
                    
                    # Check for transaction section
                    if "Date" in line and "Description" in line:
                        in_transaction_section = True
                        continue
                    
                    # Check if we've reached the end
                    if "ENDING BALANCE" in line:
                        in_transaction_section = False
                        continue
                    
                    if not in_transaction_section:
                        continue
                    
                    # Handle continuation lines
                    if continuation_line:
                        line = continuation_line + " " + line
                        continuation_line = ""
                    
                    # Alliance date pattern (DDMMYY format)
                    date_pattern = r'(\d{6})'
                    amount_pattern = r'([\d,]+\.\d{2})'
                    
                    match = re.search(f'{date_pattern}(.+?){amount_pattern}', line)
                    
                    if match:
                        date_str = match.group(1)
                        description = match.group(2).strip()
                        amount_str = match.group(3)
                        
                        # Parse date (DDMMYY format)
                        try:
                            # Convert DDMMYY to DDMMYYYY
                            day = date_str[:2]
                            month = date_str[2:4]
                            year = "20" + date_str[4:6]  # Assuming 20xx
                            full_date = f"{day}/{month}/{year}"
                            transaction_date = datetime.strptime(full_date, '%d/%m/%Y').date()
                        except ValueError:
                            continue
                        
                        # Parse amount
                        try:
                            amount = float(amount_str.replace(',', ''))
                        except ValueError:
                            continue
                        
                        # Check for CR indicator
                        transaction_type = 'credit' if 'CR' in line else 'debit'
                        
                        transactions.append({
                            'date': transaction_date.isoformat(),
                            'description': description,
                            'amount': amount,
                            'balance': None,  # Alliance may not always show balance
                            'transaction_type': transaction_type,
                            'bank': 'alliance'
                        })
                    else:
                        # Check if this might be a continuation line
                        if line and not re.search(r'\d{6}', line):
                            continuation_line = line
        
        return transactions
    
    def _parse_credit_card(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Parse credit card PDF statement"""
        transactions = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    
                    # Credit card transaction pattern
                    date_pattern = r'(\d{2}/\d{2}/\d{4})'
                    amount_pattern = r'([\d,]+\.\d{2})'
                    
                    # Look for lines with posting date, transaction date, and amount
                    match = re.search(f'{date_pattern}\\s+{date_pattern}(.+?){amount_pattern}', line)
                    
                    if match:
                        posting_date_str = match.group(1)
                        transaction_date_str = match.group(2)
                        description = match.group(3).strip()
                        amount_str = match.group(4)
                        
                        # Parse dates
                        try:
                            posting_date = datetime.strptime(posting_date_str, '%d/%m/%Y').date()
                            transaction_date = datetime.strptime(transaction_date_str, '%d/%m/%Y').date()
                        except ValueError:
                            continue
                        
                        # Parse amount
                        try:
                            amount = float(amount_str.replace(',', ''))
                        except ValueError:
                            continue
                        
                        # Determine transaction type
                        transaction_type = 'credit' if amount < 0 else 'debit'
                        
                        transactions.append({
                            'date': transaction_date.isoformat(),
                            'posting_date': posting_date.isoformat(),
                            'description': description,
                            'amount': abs(amount),
                            'transaction_type': transaction_type,
                            'bank': 'credit_card'
                        })
        
        return transactions
    
    def _generate_csv(self, transactions: List[Dict[str, Any]], bank_type: str) -> str:
        """Generate CSV content from transactions"""
        if not transactions:
            return ""
        
        # Create DataFrame
        df = pd.DataFrame(transactions)
        
        # Standardize columns based on bank type
        if bank_type == 'credit_card':
            columns = ['posting_date', 'date', 'description', 'amount', 'transaction_type']
        else:
            columns = ['date', 'description', 'amount', 'balance', 'transaction_type']
        
        # Filter to only include available columns
        available_columns = [col for col in columns if col in df.columns]
        df = df[available_columns]
        
        # Generate CSV string
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue()
    
    def _generate_summary(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from transactions"""
        if not transactions:
            return {}
        
        df = pd.DataFrame(transactions)
        
        # Calculate summary statistics
        total_transactions = len(transactions)
        credit_transactions = df[df['transaction_type'] == 'credit']
        debit_transactions = df[df['transaction_type'] == 'debit']
        
        total_credits = credit_transactions['amount'].sum() if not credit_transactions.empty else 0
        total_debits = debit_transactions['amount'].sum() if not debit_transactions.empty else 0
        
        # Date range
        dates = pd.to_datetime(df['date'])
        date_range = {
            'start_date': dates.min().isoformat() if not dates.empty else None,
            'end_date': dates.max().isoformat() if not dates.empty else None
        }
        
        return {
            'total_transactions': total_transactions,
            'credit_count': len(credit_transactions),
            'debit_count': len(debit_transactions),
            'total_credits': round(total_credits, 2),
            'total_debits': round(total_debits, 2),
            'net_amount': round(total_credits - total_debits, 2),
            'date_range': date_range
        }