#!/usr/bin/env python3
"""
Test SKU-based hypothetical ACOS calculation
"""

import pandas as pd
import sys
import os
sys.path.append('.')

from app.utils.excel_processor import process_amazon_report
from app.utils.hypothetical_acos import HypotheticalACOSCalculator
from postgres_data_retriever import PostgreSQLRetriever

def test_sku_hypothetical():
    """Test SKU-based hypothetical ACOS calculation"""
    print("🔍 Testing SKU-based Hypothetical ACOS")
    print("=" * 60)
    
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    # Get database SKUs
    print("📊 Loading database SKUs...")
    retriever = PostgreSQLRetriever()
    if not retriever.connect():
        print("❌ Database connection failed")
        return
    
    pricing_data = retriever.get_table_data('pricing', limit=1000)
    retriever.disconnect()
    
    if pricing_data.empty:
        print("❌ No pricing data found")
        return
    
    db_skus = set(pricing_data['seller-sku'].dropna())
    print(f"✅ Loaded {len(db_skus)} unique SKUs from database")
    print(f"Sample DB SKUs: {list(db_skus)[:10]}")
    
    # Get Excel data
    print(f"\n📊 Processing Excel data...")
    result = process_amazon_report(excel_file)
    if result[0] is None:
        print("❌ Failed to process Excel file")
        return
    
    df_campaign, df_search_terms, _, _, _, _, _ = result
    df_to_check = df_search_terms if df_search_terms is not None else df_campaign
    
    print(f"\n📋 Available columns: {list(df_to_check.columns)}")
    
    # Check for SKU column
    sku_col = None
    for col in ['sku', 'SKU', 'produkt', 'seller-sku']:
        if col in df_to_check.columns:
            sku_col = col
            print(f"✅ Found SKU column: {col}")
            break
    
    if sku_col is None:
        print("❌ No SKU column found")
        return
    
    # Get products with 0 sales and spending
    zero_sales_with_spend = df_to_check[
        (df_to_check['sales'] == 0) & (df_to_check['spend'] > 0)
    ]
    
    print(f"✅ Found {len(zero_sales_with_spend)} products with 0 sales but spending")
    
    # Check SKU matches
    excel_skus = set(zero_sales_with_spend[sku_col].dropna())
    matches = excel_skus.intersection(db_skus)
    
    print(f"\n🎯 SKU matches found: {len(matches)}")
    
    if matches:
        print(f"✅ Matching SKUs: {list(matches)[:10]}")
        
        # Test calculation with first match
        test_sku = list(matches)[0]
        test_row = zero_sales_with_spend[
            zero_sales_with_spend[sku_col] == test_sku
        ].iloc[0]
        
        print(f"\n🧮 Test calculation with SKU: {test_sku}")
        print(f"   Spend: €{test_row['spend']}")
        
        # Test with calculator
        calculator = HypotheticalACOSCalculator()
        if calculator.load_pricing_data():
            result = calculator.calculate_hypothetical_acos(test_row['spend'], test_sku, 20.0)
            
            if result['has_data']:
                print(f"   ✅ Hypothetical ACOS: {result['hypothetical_acos_pct']:.1f}%")
                print(f"   📊 Gross price: €{result['gross_price']:.2f}")
                print(f"   💰 Net price: €{result['net_price']:.2f}")
            else:
                print(f"   ❌ {result['error']}")
        
        # Test full enrichment
        print(f"\n🔄 Testing full dataframe enrichment...")
        calculator = HypotheticalACOSCalculator()
        df_enriched = calculator.enrich_dataframe_with_hypothetical_acos(
            zero_sales_with_spend.head(10), 20.0
        )
        
        hyp_count = df_enriched['hypothetical_acos_note'].str.contains('Hypothetischer ACOS', na=False).sum()
        print(f"✅ Successfully calculated hypothetical ACOS for {hyp_count} out of 10 test rows")
        
        if hyp_count > 0:
            print("\n📝 Sample enriched data:")
            display_cols = [sku_col, 'spend', 'hypothetical_acos_pct', 'hypothetical_acos_note']
            available_cols = [col for col in display_cols if col in df_enriched.columns]
            print(df_enriched[available_cols].head().to_string(index=False))
    else:
        print("❌ No SKU matches found")
        print(f"Sample Excel SKUs: {list(excel_skus)[:10]}")
        print(f"Sample DB SKUs: {list(db_skus)[:10]}")

if __name__ == "__main__":
    test_sku_hypothetical() 