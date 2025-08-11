#!/usr/bin/env python3
"""
Test Hypothetical ACOS for Products with No Sales
"""

import pandas as pd
import sys
import warnings
import os
warnings.filterwarnings("ignore")
sys.path.append('.')

from app.utils.campaign_pauser import CampaignPauser
from app.utils.hypothetical_acos import HypotheticalACOSCalculator
from postgres_data_retriever import PostgreSQLRetriever

def test_hypothetical_acos_products():
    """Test hypothetical ACOS calculation for products with no sales"""
    print("🔍 Testing Hypothetical ACOS for Products with No Sales")
    print("=" * 70)
    
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    try:
        # First, check database pricing data
        print("📊 Loading database pricing data...")
        retriever = PostgreSQLRetriever()
        if not retriever.connect():
            print("❌ Database connection failed")
            return
        
        pricing_data = retriever.get_table_data('pricing', limit=1000)
        retriever.disconnect()
        
        if pricing_data.empty:
            print("❌ No pricing data found")
            return
        
        print(f"✅ Loaded {len(pricing_data)} pricing records")
        print(f"📋 Available pricing columns: {list(pricing_data.columns)}")
        
        # Show sample pricing data
        print(f"\n💰 Sample pricing data:")
        sample_pricing = pricing_data.head(10)
        if 'seller-sku' in pricing_data.columns and 'price' in pricing_data.columns:
            for _, row in sample_pricing.iterrows():
                sku = row.get('seller-sku', 'N/A')
                price = row.get('price', 'N/A')
                print(f"   {sku}: €{price}")
        
        # Read the campaign sheet
        df_campaign = pd.read_excel(excel_file, sheet_name='Sponsored Products-Kampagnen')
        print(f"\n✅ Loaded campaign sheet with {len(df_campaign)} rows")
        
        # Filter for products (Produktanzeige) with no sales but spending
        products_df = df_campaign[df_campaign['Entität'].str.lower() == 'produktanzeige'].copy()
        print(f"📦 Found {len(products_df)} total products")
        
        # Find products with spending but no sales
        no_sales_products = products_df[
            (products_df['Verkäufe'].fillna(0) == 0) & 
            (products_df['Ausgaben'].fillna(0) > 0)
        ].copy()
        
        print(f"🔍 Products with spending but no sales: {len(no_sales_products)}")
        
        if no_sales_products.empty:
            print("ℹ️ No products found with spending but no sales")
            return
        
        # Check SKU column and matches
        sku_col = 'SKU'
        if sku_col in no_sales_products.columns:
            product_skus = set(no_sales_products[sku_col].dropna().astype(str))
            db_skus = set(pricing_data['seller-sku'].dropna().astype(str))
            
            matches = product_skus.intersection(db_skus)
            print(f"🎯 SKU matches found: {len(matches)} out of {len(product_skus)} products")
            
            if matches:
                print(f"✅ Matching SKUs (first 10): {list(matches)[:10]}")
                
                # Test hypothetical ACOS calculation
                print(f"\n🧮 Testing Hypothetical ACOS Calculation:")
                calculator = HypotheticalACOSCalculator()
                
                if calculator.load_pricing_data():
                    # Test with first few matching products
                    test_products = no_sales_products[
                        no_sales_products[sku_col].isin(list(matches)[:5])
                    ]
                    
                    for idx, row in test_products.iterrows():
                        sku = row[sku_col]
                        spend = row['Ausgaben']
                        sales = row['Verkäufe']
                        
                        print(f"\n📦 Product: {sku}")
                        print(f"   💰 Spend: €{spend}")
                        print(f"   💸 Sales: €{sales}")
                        
                        # Calculate hypothetical ACOS
                        result = calculator.calculate_hypothetical_acos(spend, sku, 20.0)
                        
                        if result['has_data']:
                            print(f"   ✅ Hypothetical ACOS: {result['hypothetical_acos_pct']:.1f}%")
                            print(f"   📊 Gross price from DB: €{result['gross_price']:.2f}")
                            print(f"   💰 Net price (gross/1.19): €{result['net_price']:.2f}")
                            print(f"   📈 Calculation: €{spend} / €{result['net_price']:.2f} = {result['hypothetical_acos']:.4f} ({result['hypothetical_acos_pct']:.1f}%)")
                        else:
                            print(f"   ❌ {result['error']}")
                    
                    # Test the enrichment function
                    print(f"\n🔄 Testing DataFrame Enrichment:")
                    enriched_df = calculator.enrich_dataframe_with_hypothetical_acos(
                        test_products, 20.0
                    )
                    
                    # Check if hypothetical ACOS was added
                    if 'hypothetical_acos_note' in enriched_df.columns:
                        notes_with_hyp = enriched_df['hypothetical_acos_note'].str.contains(
                            'Hypothetischer ACOS', na=False
                        ).sum()
                        print(f"   ✅ {notes_with_hyp} products enriched with hypothetical ACOS")
                        
                        # Show enriched data
                        if notes_with_hyp > 0:
                            hyp_products = enriched_df[
                                enriched_df['hypothetical_acos_note'].str.contains('Hypothetischer ACOS', na=False)
                            ]
                            
                            print(f"\n📋 Enriched Products with Hypothetical ACOS:")
                            for idx, row in hyp_products.iterrows():
                                sku = row[sku_col]
                                note = row['hypothetical_acos_note']
                                original_acos = row.get('ACOS', 'N/A')
                                hyp_acos = row.get('hypothetical_acos_pct', 'N/A')
                                print(f"   {sku}: Original ACOS={original_acos}, New={hyp_acos}%, Note: {note}")
                    else:
                        print(f"   ❌ No hypothetical ACOS notes found in enriched data")
                
                else:
                    print("❌ Failed to load pricing data for calculator")
            else:
                print(f"❌ No SKU matches found")
                print(f"Sample product SKUs: {list(product_skus)[:10]}")
                print(f"Sample DB SKUs: {list(db_skus)[:10]}")
        else:
            print(f"❌ SKU column '{sku_col}' not found in products data")
            print(f"Available columns: {list(no_sales_products.columns)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_hypothetical_acos_products() 