#!/usr/bin/env python3
"""
Check if customer_search_term values are ASINs that match database
"""

import pandas as pd
import sys
import os
sys.path.append('.')

from app.utils.excel_processor import process_amazon_report
from postgres_data_retriever import PostgreSQLRetriever

def check_asin_matches():
    """Check if customer_search_term values match database ASINs"""
    print("🔍 Checking ASIN matches between Excel and Database")
    print("=" * 60)
    
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    # Get database ASINs
    print("📊 Loading database ASINs...")
    retriever = PostgreSQLRetriever()
    if not retriever.connect():
        print("❌ Database connection failed")
        return
    
    pricing_data = retriever.get_table_data('pricing', limit=1000)
    retriever.disconnect()
    
    if pricing_data.empty:
        print("❌ No pricing data found")
        return
    
    db_asins = set(pricing_data['asin1'].dropna().str.upper())
    print(f"✅ Loaded {len(db_asins)} unique ASINs from database")
    print(f"Sample DB ASINs: {list(db_asins)[:5]}")
    
    # Get Excel data
    print(f"\n📊 Processing Excel data...")
    result = process_amazon_report(excel_file)
    if result[0] is None:
        print("❌ Failed to process Excel file")
        return
    
    df_campaign, df_search_terms, _, _, _, _, _ = result
    df_to_check = df_search_terms if df_search_terms is not None else df_campaign
    
    # Get products with 0 sales and spending
    zero_sales_with_spend = df_to_check[
        (df_to_check['sales'] == 0) & (df_to_check['spend'] > 0)
    ]
    
    print(f"✅ Found {len(zero_sales_with_spend)} products with 0 sales but spending")
    
    # Check customer_search_term values
    search_terms = zero_sales_with_spend['customer_search_term'].dropna().str.upper()
    unique_search_terms = set(search_terms)
    
    print(f"📝 Found {len(unique_search_terms)} unique search terms")
    print(f"Sample search terms: {list(unique_search_terms)[:10]}")
    
    # Check matches
    matches = unique_search_terms.intersection(db_asins)
    print(f"\n🎯 ASIN matches found: {len(matches)}")
    
    if matches:
        print(f"✅ Matching ASINs: {list(matches)[:10]}")
        
        # Test calculation with first match
        test_asin = list(matches)[0]
        test_row = zero_sales_with_spend[
            zero_sales_with_spend['customer_search_term'].str.upper() == test_asin
        ].iloc[0]
        
        print(f"\n🧮 Test calculation with ASIN: {test_asin}")
        print(f"   Spend: €{test_row['spend']}")
        
        # Get price from database
        price_row = pricing_data[pricing_data['asin1'].str.upper() == test_asin].iloc[0]
        gross_price = price_row['price']
        net_price = gross_price / 1.19
        hypothetical_acos = (test_row['spend'] / net_price) * 100
        
        print(f"   Gross price: €{gross_price:.2f}")
        print(f"   Net price: €{net_price:.2f}")
        print(f"   ✅ Hypothetical ACOS: {hypothetical_acos:.1f}%")
    else:
        print("❌ No matches found")
        print("Sample search terms vs DB ASINs:")
        print(f"Search terms: {list(unique_search_terms)[:5]}")
        print(f"DB ASINs: {list(db_asins)[:5]}")

if __name__ == "__main__":
    check_asin_matches() 