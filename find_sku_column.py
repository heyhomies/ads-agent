#!/usr/bin/env python3
"""
Find the actual SKU column in Excel data
"""

import pandas as pd
import sys
import os
sys.path.append('.')

from app.utils.excel_processor import process_amazon_report

def find_sku_column():
    """Find the actual SKU column in the Excel data"""
    print("🔍 Finding SKU Column in Excel Data")
    print("=" * 50)
    
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    # Process Excel file
    result = process_amazon_report(excel_file)
    if result[0] is None:
        print("❌ Failed to process Excel file")
        return
    
    df_campaign, df_search_terms, _, _, _, _, _ = result
    
    print("🔍 Analyzing Campaign Data:")
    print(f"Columns: {list(df_campaign.columns)}")
    
    # Check unique values in potential SKU columns
    potential_sku_cols = ['produkt', 'keyword', 'customer_search_term']
    
    for col in potential_sku_cols:
        if col in df_campaign.columns:
            unique_vals = df_campaign[col].unique()
            print(f"\n📊 Column '{col}':")
            print(f"   Unique values: {len(unique_vals)}")
            print(f"   Sample values: {unique_vals[:10]}")
            
            # Check if values look like SKUs (not too generic)
            if len(unique_vals) > 1 and 'Sponsored Products' not in str(unique_vals[0]):
                print(f"   ✅ Potential SKU column!")
    
    # Also check search terms data
    if df_search_terms is not None:
        print(f"\n🔍 Analyzing Search Terms Data:")
        print(f"Columns: {list(df_search_terms.columns)}")
        
        for col in potential_sku_cols:
            if col in df_search_terms.columns:
                unique_vals = df_search_terms[col].unique()
                print(f"\n📊 Column '{col}':")
                print(f"   Unique values: {len(unique_vals)}")
                print(f"   Sample values: {unique_vals[:10]}")
                
                if len(unique_vals) > 1 and 'Sponsored Products' not in str(unique_vals[0]):
                    print(f"   ✅ Potential SKU column!")
    
    # Check if we need to look at raw Excel data
    print(f"\n📝 Checking raw Excel sheets...")
    try:
        # Read all sheets to see if there's a different structure
        xl_file = pd.ExcelFile(excel_file)
        print(f"Available sheets: {xl_file.sheet_names}")
        
        for sheet_name in xl_file.sheet_names:
            if 'campaign' in sheet_name.lower() or 'produkt' in sheet_name.lower():
                print(f"\n📋 Checking sheet: {sheet_name}")
                df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=5)
                print(f"Raw columns: {list(df_raw.columns)}")
                
                # Look for columns that might contain SKUs
                for col in df_raw.columns:
                    if any(term in col.lower() for term in ['sku', 'produkt', 'asin', 'product']):
                        print(f"   📦 Potential SKU column: {col}")
                        sample_vals = df_raw[col].dropna().unique()[:5]
                        print(f"   Sample values: {sample_vals}")
    
    except Exception as e:
        print(f"Error reading raw Excel: {e}")

if __name__ == "__main__":
    find_sku_column() 