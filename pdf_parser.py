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
        
        # Check for bank-specific keywords
        if 'maybank' in text_lower or 'malayan banking' in text_lower:
            if 'credit card' in text_lower or 'mastercard' in text_lower or 'visa' in text_lower:
                return 'credit_card'
            return 'maybank'
        elif 'cimb' in text_lower or 'commerce international' in text_lower:
            return 'cimb'
        elif 'alliance' in text_lower or 'alliance bank' in text_lower:
            return 'alliance'
        
        # Default fallback
        return 'maybank'
    
    def process_pdf(self, pdf_path: str, processing_id: str) -> Dict[str, Any]:
        """Main method to process PDF and extract transactions"""
        start_time = datetime.now()
        
        try:
            # Extract text from PDF
            with pdfplumber.open(pdf_path) as pdf:
                all_text = ""
                for page in pdf.pages:
                    all_text += page.extract_text() + "\n"
            
            # Detect bank type
            bank_type = self.detect_bank_type(all_text)
            logger.info(f"Detected bank type: {bank_type}")
            
            # Parse based on bank type
            parser_func = self.supported_banks.get(bank_type)
            if not parser_func:
                raise ValueError(f"Unsupported bank type: {bank_type}")
            
            # Parse transactions
            transactions = parser_func(pdf_path)
            
            # Generate CSV content
            csv_content = self._generate_csv(transactions, bank_type)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Generate summary
            summary = self._generate_summary(transactions)
            
            return {
                'success': True,
                'bank_type': bank_type,
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
        """Parse CIMB Bank PDF statement"""
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
                    
                    # Check for transaction section headers
                    if "Date" in line and "Description" in line and "Amount" in line:
                        in_transaction_section = True
                        continue
                    
                    # Check if we've reached the end
                    if "ENDING BALANCE" in line or "Total" in line:
                        in_transaction_section = False
                        continue
                    
                    if not in_transaction_section:
                        continue
                    
                    # Handle continuation lines
                    if continuation_line:
                        line = continuation_line + " " + line
                        continuation_line = ""
                    
                    # CIMB transaction pattern: Date Description ChequeNo Amount Balance
                    date_pattern = r'(\d{2}/\d{2}/\d{4})'
                    amount_pattern = r'([\d,]+\.\d{2})'
                    
                    match = re.search(f'{date_pattern}(.+?){amount_pattern}.*?{amount_pattern}', line)
                    
                    if match:
                        date_str = match.group(1)
                        description = match.group(2).strip()
                        amount_str = match.group(3)
                        balance_str = match.group(4)
                        
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
                        
                        # Determine transaction type
                        transaction_type = 'debit' if amount > 0 else 'credit'
                        
                        transactions.append({
                            'date': transaction_date.isoformat(),
                            'description': description,
                            'amount': amount,
                            'balance': balance,
                            'transaction_type': transaction_type,
                            'bank': 'cimb'
                        })
                    else:
                        # Check if this might be a continuation line
                        if line and not re.search(r'\d{2}/\d{2}/\d{4}', line):
                            continuation_line = line
        
        return transactions
    
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