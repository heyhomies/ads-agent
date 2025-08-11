#!/usr/bin/env python3
"""
Test Campaign Pausing Functionality
"""

import pandas as pd
import sys
import warnings
import os
warnings.filterwarnings("ignore")
sys.path.append('.')

from app.utils.campaign_pauser import CampaignPauser

def test_campaign_pausing():
    """Test the campaign pausing functionality"""
    print("🔍 Testing Campaign Pausing Functionality")
    print("=" * 60)
    
    excel_file = "temp_uploads/bulk-alodtl8t4nbm6-20250610-20250710-1752151829102.xlsx"
    
    try:
        # Read the campaign sheet directly
        df_campaign = pd.read_excel(excel_file, sheet_name='Sponsored Products-Kampagnen')
        print(f"✅ Loaded campaign sheet with {len(df_campaign)} rows")
        
        # Check entity distribution
        entity_counts = df_campaign['Entität'].value_counts()
        print(f"\n📊 Entity distribution:")
        for entity, count in entity_counts.items():
            print(f"   {entity}: {count}")
        
        # Test configuration
        test_config = {
            'max_keyword_acos': 15.0,  # 15% threshold for keywords
            'max_hypothetical_product_acos': 25.0,  # 25% threshold for products  
            'max_keyword_clicks_no_conversion': 30,  # 30 clicks without conversion
            'target_acos': 20.0
        }
        
        print(f"\n🎯 Test Configuration:")
        print(f"   Max Keyword ACOS: {test_config['max_keyword_acos']}%")
        print(f"   Max Product ACOS: {test_config['max_hypothetical_product_acos']}%")
        print(f"   Max Clicks without Conversion: {test_config['max_keyword_clicks_no_conversion']}")
        
        # Initialize pauser
        pauser = CampaignPauser()
        
        # Get preview first
        print(f"\n🔍 Getting pausing preview...")
        preview = pauser.get_pausing_preview(df_campaign, test_config)
        
        print(f"📋 Pausing Preview:")
        print(f"   Keywords to pause: {len(preview['keywords_to_pause'])}")
        print(f"   Products to pause: {len(preview['products_to_pause'])}")
        print(f"   Total to pause: {preview['total_count']}")
        
        if preview['keywords_to_pause']:
            print(f"\n🔍 Keywords to pause (first 5):")
            for i, kw in enumerate(preview['keywords_to_pause'][:5]):
                print(f"   {i+1}. {kw['keyword']} - {kw['reason']}")
        
        if preview['products_to_pause']:
            print(f"\n🔍 Products to pause (first 5):")
            for i, prod in enumerate(preview['products_to_pause'][:5]):
                print(f"   {i+1}. {prod['sku']} - {prod['reason']}")
        
        # Test actual processing (without database for now)
        print(f"\n🔄 Testing actual processing...")
        
        # Create a small test subset
        test_df = df_campaign.head(50).copy()
        
        # Check what we have in test data
        print(f"📊 Test data summary:")
        print(f"   Total rows: {len(test_df)}")
        test_entities = test_df['Entität'].value_counts()
        for entity, count in test_entities.items():
            print(f"   {entity}: {count}")
        
        # Check for ACOS values
        keywords_test = test_df[test_df['Entität'].str.lower() == 'keyword']
        products_test = test_df[test_df['Entität'].str.lower() == 'produktanzeige']
        
        print(f"\n📋 ACOS analysis in test data:")
        if not keywords_test.empty:
            kw_acos = keywords_test['ACOS'].dropna()
            if not kw_acos.empty:
                print(f"   Keywords ACOS range: {kw_acos.min():.4f} - {kw_acos.max():.4f}")
                # Convert to percentage if needed
                if kw_acos.max() > 1:
                    kw_acos_pct = kw_acos
                else:
                    kw_acos_pct = kw_acos * 100
                above_threshold = kw_acos_pct > test_config['max_keyword_acos']
                print(f"   Keywords above {test_config['max_keyword_acos']}% threshold: {above_threshold.sum()}")
        
        if not products_test.empty:
            prod_acos = products_test['ACOS'].dropna()
            if not prod_acos.empty:
                print(f"   Products ACOS range: {prod_acos.min():.4f} - {prod_acos.max():.4f}")
                # Convert to percentage if needed
                if prod_acos.max() > 1:
                    prod_acos_pct = prod_acos
                else:
                    prod_acos_pct = prod_acos * 100
                above_threshold = prod_acos_pct > test_config['max_hypothetical_product_acos']
                print(f"   Products above {test_config['max_hypothetical_product_acos']}% threshold: {above_threshold.sum()}")
        
        print(f"\n✅ Campaign pausing test completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_campaign_pausing() 