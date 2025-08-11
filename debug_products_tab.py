#!/usr/bin/env python3
"""
Debug script for the products tab
"""

import pandas as pd
import sys
import warnings
warnings.filterwarnings("ignore")
sys.path.append('.')

def debug_products_tab():
    """Debug the products tab logic"""
    print("🔍 Debugging Products Tab")
    print("=" * 50)
    
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    try:
        # Read campaign sheet
        df_campaign = pd.read_excel(excel_file, sheet_name='Sponsored Products-Kampagnen')
        print(f"✅ Loaded campaign data: {df_campaign.shape}")
        print(f"📋 Columns: {list(df_campaign.columns)}")
        
        # Check for Entität column
        if 'Entität' in df_campaign.columns:
            print(f"✅ Found 'Entität' column")
            entity_counts = df_campaign['Entität'].value_counts()
            print(f"📊 Entity counts:")
            for entity, count in entity_counts.items():
                print(f"   {entity}: {count}")
            
            # Filter for products
            products_mask = df_campaign['Entität'].astype(str).str.lower() == 'produktanzeige'
            df_products = df_campaign[products_mask].copy()
            print(f"✅ Found {len(df_products)} products")
            
        else:
            print(f"❌ No 'Entität' column found")
            df_products = df_campaign.copy()
        
        # Check for campaign ID
        campaign_id_cols = ['Kampagnen-ID', 'kampagnen-id', 'campaign_id', 'Campaign ID']
        campaign_id_col = None
        for col in campaign_id_cols:
            if col in df_products.columns:
                campaign_id_col = col
                print(f"✅ Found campaign ID column: {col}")
                break
        
        if campaign_id_col is None:
            print(f"❌ No campaign ID column found")
        else:
            unique_campaigns = df_products[campaign_id_col].nunique()
            print(f"📊 Number of unique campaigns: {unique_campaigns}")
        
        # Check for spend/sales columns
        spend_cols = ['Ausgaben', 'ausgaben', 'spend', 'Spend']
        sales_cols = ['Verkäufe', 'verkäufe', 'sales', 'Sales']
        
        spend_col = None
        for col in spend_cols:
            if col in df_products.columns:
                spend_col = col
                print(f"✅ Found spend column: {col}")
                break
        
        sales_col = None
        for col in sales_cols:
            if col in df_products.columns:
                sales_col = col
                print(f"✅ Found sales column: {col}")
                break
        
        if spend_col:
            total_spend = df_products[spend_col].sum()
            print(f"💰 Total spend: €{total_spend:.2f}")
        
        if sales_col:
            total_sales = df_products[sales_col].sum()
            print(f"💰 Total sales: €{total_sales:.2f}")
        
        print(f"✅ Products tab debug completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_products_tab() 