#!/usr/bin/env python3
"""
Test Hypothetical ACOS Integration in Campaign Pauser
"""

import pandas as pd
import sys
import warnings
import os
warnings.filterwarnings("ignore")
sys.path.append('.')

from app.utils.campaign_pauser import CampaignPauser

def test_hypothetical_acos_integration():
    """Test if hypothetical ACOS is being calculated in campaign pausing"""
    print("🔍 Testing Hypothetical ACOS Integration in Campaign Pauser")
    print("=" * 70)
    
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    try:
        # Read the campaign sheet
        df_campaign = pd.read_excel(excel_file, sheet_name='Sponsored Products-Kampagnen')
        print(f"✅ Loaded campaign sheet with {len(df_campaign)} rows")
        
        # Filter for products (Produktanzeige)
        products_df = df_campaign[df_campaign['Entität'].str.lower() == 'produktanzeige'].copy()
        print(f"📦 Found {len(products_df)} total products")
        
        # Check products by sales status
        products_with_sales = products_df[products_df['Verkäufe'].fillna(0) > 0]
        products_no_sales = products_df[products_df['Verkäufe'].fillna(0) == 0]
        products_no_sales_with_spend = products_no_sales[products_no_sales['Ausgaben'].fillna(0) > 0]
        
        print(f"📊 Product Analysis:")
        print(f"   Products with sales: {len(products_with_sales)}")
        print(f"   Products with no sales: {len(products_no_sales)}")
        print(f"   Products with no sales but spending: {len(products_no_sales_with_spend)}")
        
        if not products_no_sales_with_spend.empty:
            print(f"\n🔍 Sample products with no sales but spending:")
            sample_products = products_no_sales_with_spend.head(5)
            for idx, row in sample_products.iterrows():
                sku = row.get('SKU', 'N/A')
                spend = row.get('Ausgaben', 0)
                sales = row.get('Verkäufe', 0)
                acos = row.get('ACOS', 0)
                print(f"   {sku}: Spend=€{spend}, Sales=€{sales}, ACOS={acos}")
        
        # Test configuration that should trigger hypothetical ACOS calculation
        test_config = {
            'max_keyword_acos': 15.0,
            'max_hypothetical_product_acos': 50.0,  # Set high so we can see calculations
            'max_keyword_clicks_no_conversion': 30,
            'target_acos': 20.0
        }
        
        print(f"\n🎯 Test Configuration:")
        print(f"   Max Product ACOS: {test_config['max_hypothetical_product_acos']}%")
        print(f"   Target ACOS: {test_config['target_acos']}%")
        
        # Initialize pauser and test processing
        print(f"\n🔄 Testing Campaign Pauser Processing...")
        pauser = CampaignPauser()
        
        # Test with a smaller subset to see detailed output
        test_subset = products_no_sales_with_spend.head(10).copy()
        print(f"📋 Testing with {len(test_subset)} products with no sales but spending")
        
        # Create a minimal campaign DataFrame for testing
        test_df = df_campaign[df_campaign.index.isin(test_subset.index)].copy()
        
        print(f"\n🧮 Processing test subset...")
        try:
            updated_df, summary = pauser.process_campaign_sheet(test_df, test_config)
            
            print(f"✅ Processing completed:")
            print(f"   Keywords paused: {summary.get('keywords_paused', 0)}")
            print(f"   Products paused: {summary.get('products_paused', 0)}")
            
            # Check if any hypothetical ACOS calculations were made
            if hasattr(pauser.hypothetical_calculator, 'pricing_data') and pauser.hypothetical_calculator.pricing_data is not None:
                print(f"✅ Hypothetical calculator has pricing data loaded")
            else:
                print(f"❌ Hypothetical calculator has no pricing data")
            
        except Exception as e:
            print(f"❌ Error during processing: {e}")
            import traceback
            traceback.print_exc()
        
        # Test if we can at least check the calculation logic manually
        print(f"\n🔧 Manual Test of Hypothetical ACOS Logic:")
        
        # Check if we can load the hypothetical calculator
        from app.utils.hypothetical_acos import HypotheticalACOSCalculator
        calc = HypotheticalACOSCalculator()
        
        if calc.load_pricing_data():
            print(f"✅ Hypothetical calculator loaded pricing data successfully")
            
            # Test with a sample product
            if not test_subset.empty:
                sample_row = test_subset.iloc[0]
                sku = sample_row.get('SKU', '')
                spend = sample_row.get('Ausgaben', 0)
                
                if sku and spend > 0:
                    print(f"\n📦 Testing calculation for SKU: {sku}, Spend: €{spend}")
                    result = calc.calculate_hypothetical_acos(spend, sku, 20.0)
                    
                    if result['has_data']:
                        print(f"   ✅ Hypothetical ACOS calculated: {result['hypothetical_acos_pct']:.1f}%")
                        print(f"   📊 Used price from DB: €{result['gross_price']:.2f}")
                    else:
                        print(f"   ❌ Could not calculate: {result['error']}")
                else:
                    print(f"   ⚠️ Sample product has no SKU or spend")
        else:
            print(f"❌ Could not load pricing data - likely database connection issue")
            print(f"ℹ️ This means hypothetical ACOS calculation will not work in the campaign pauser")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hypothetical_acos_integration() 