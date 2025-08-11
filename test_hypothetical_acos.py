#!/usr/bin/env python3
"""
Test hypothetical ACOS calculation with specific file
"""

import pandas as pd
import sys
import os
sys.path.append('.')

from app.utils.excel_processor import process_amazon_report
from app.utils.hypothetical_acos import HypotheticalACOSCalculator
from postgres_data_retriever import PostgreSQLRetriever

def test_with_file_102():
    """Test hypothetical ACOS with the file ending in 102"""
    print("🔍 Testing Hypothetical ACOS with file ending in 102")
    print("=" * 60)
    
    # Find the specific file
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    if not os.path.exists(excel_file):
        print(f"❌ File not found: {excel_file}")
        return
    
    print(f"📊 Processing: {excel_file}")
    
    # Process the Excel file
    try:
        result = process_amazon_report(excel_file)
        if result[0] is None:
            print("❌ Failed to process Excel file")
            return
        
        df_campaign, df_search_terms, _, _, _, _, _ = result
        
        print(f"\n📈 Campaign data: {len(df_campaign)} rows")
        print(f"🔍 Search terms data: {len(df_search_terms) if df_search_terms is not None else 0} rows")
        
        # Choose the data to analyze
        df_to_analyze = df_search_terms if df_search_terms is not None else df_campaign
        
        if df_to_analyze is not None:
            print(f"\n📋 Columns: {list(df_to_analyze.columns)}")
            
            # Check for ASIN columns
            asin_cols = [col for col in df_to_analyze.columns if 'asin' in col.lower()]
            print(f"🏷️ ASIN columns: {asin_cols}")
            
            # Check for 0 sales products with spending
            if 'spend' in df_to_analyze.columns and 'sales' in df_to_analyze.columns:
                zero_sales_with_spend = df_to_analyze[
                    (df_to_analyze['sales'] == 0) & (df_to_analyze['spend'] > 0)
                ]
                print(f"📊 Products with spend > 0 but sales = 0: {len(zero_sales_with_spend)}")
                
                if len(zero_sales_with_spend) > 0:
                    print("\n📝 Sample data (first 5 rows):")
                    display_cols = ['spend', 'sales']
                    if asin_cols:
                        display_cols.extend(asin_cols)
                    if 'customer_search_term' in zero_sales_with_spend.columns:
                        display_cols.append('customer_search_term')
                    
                    available_cols = [col for col in display_cols if col in zero_sales_with_spend.columns]
                    print(zero_sales_with_spend[available_cols].head().to_string(index=False))
                    
                    # Test hypothetical ACOS calculation
                    print(f"\n🧮 Testing hypothetical ACOS calculation...")
                    calculator = HypotheticalACOSCalculator()
                    
                    if calculator.load_pricing_data():
                        print(f"✅ Database connected, {len(calculator.pricing_data)} pricing records loaded")
                        
                        # Test with first row that has spending
                        test_row = zero_sales_with_spend.iloc[0]
                        spend = test_row['spend']
                        
                        # Try to find ASIN
                        asin = None
                        for asin_col in asin_cols:
                            if asin_col in test_row and pd.notna(test_row[asin_col]):
                                asin = str(test_row[asin_col])
                                break
                        
                        if asin:
                            print(f"\n🎯 Testing calculation:")
                            print(f"   ASIN: {asin}")
                            print(f"   Spend: €{spend}")
                            
                            result = calculator.calculate_hypothetical_acos(spend, asin, 20.0)
                            print(f"   Result: {result}")
                            
                            if result['has_data']:
                                print(f"   ✅ Hypothetical ACOS: {result['hypothetical_acos_pct']:.1f}%")
                                print(f"   📊 Gross price: €{result['gross_price']:.2f}")
                                print(f"   💰 Net price: €{result['net_price']:.2f}")
                            else:
                                print(f"   ❌ {result['error']}")
                        else:
                            print(f"   ❌ No valid ASIN found in test row")
                    else:
                        print("❌ Database connection failed")
                else:
                    print("ℹ️ No products found with spend > 0 and sales = 0")
            else:
                print("❌ Missing 'spend' or 'sales' columns")
        else:
            print("❌ No data to analyze")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_with_file_102() 