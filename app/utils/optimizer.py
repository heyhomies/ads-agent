import pandas as pd
import numpy as np
from typing import Dict, List, Any


def apply_optimization_rules(df_campaign, df_search_terms, client_config):
    """
    Apply optimization rules to the campaign data (simplified version without LLM)
    
    Args:
        df_campaign (pd.DataFrame): Campaign data
        df_search_terms (pd.DataFrame): Search terms data
        client_config (dict): Client configuration settings
        
    Returns:
        dict: Optimization results including changes and metrics
    """
    
    # Initialize results structure
    keyword_changes = []
    bid_changes = []
    summary = {
        'total_keywords_analyzed': 0,
        'keywords_to_pause': 0,
        'bids_to_increase': 0,
        'bids_to_decrease': 0,
        'avg_bid_increase': 0,
        'avg_bid_decrease': 0
    }
    
    # Simple keyword analysis for summary stats
    if df_search_terms is not None and not df_search_terms.empty:
        # Count total keywords
        summary['total_keywords_analyzed'] = len(df_search_terms)
        
        # Analyze keywords based on configuration
        target_acos = client_config.get('keyword_acos', 20.0) / 100  # Convert to decimal
        max_clicks = client_config.get('max_keyword_clicks', 50)
        
        # Count keywords to pause (high ACOS or too many clicks without conversions)
        if 'acos' in df_search_terms.columns and 'clicks' in df_search_terms.columns:
            # Handle both percentage and decimal ACOS values
            acos_col = df_search_terms['acos'].fillna(0)
            # Convert percentage to decimal if needed
            acos_col = acos_col.apply(lambda x: x/100 if x > 1 else x)
            
            clicks_col = df_search_terms['clicks'].fillna(0)
            orders_col = df_search_terms.get('orders', pd.Series([0] * len(df_search_terms))).fillna(0)
            
            # Count keywords to pause
            high_acos_mask = acos_col > target_acos
            high_clicks_no_orders_mask = (clicks_col >= max_clicks) & (orders_col == 0)
            
            summary['keywords_to_pause'] = int((high_acos_mask | high_clicks_no_orders_mask).sum())
            
            # Simple bid change estimates (for summary only)
            if 'cpc' in df_search_terms.columns:
                current_cpc = df_search_terms['cpc'].fillna(0)
                
                # Estimate bid increases (low ACOS, good performance)
                low_acos_mask = (acos_col > 0) & (acos_col < target_acos * 0.8) & (orders_col > 0)
                summary['bids_to_increase'] = int(low_acos_mask.sum())
                
                # Estimate bid decreases (high ACOS but not pausing)
                moderate_acos_mask = (acos_col > target_acos) & (acos_col < target_acos * 1.5)
                summary['bids_to_decrease'] = int(moderate_acos_mask.sum())
                
                # Average changes (simplified estimates)
                if summary['bids_to_increase'] > 0:
                    summary['avg_bid_increase'] = 15.0  # Estimated 15% increase
                if summary['bids_to_decrease'] > 0:
                    summary['avg_bid_decrease'] = 20.0  # Estimated 20% decrease
    
    return {
        "keyword_changes": keyword_changes,
        "bid_changes": bid_changes, 
        "summary": summary,
        "debug_info": ["Simplified optimizer - no LLM required"],
        "df_search_terms_with_hypothetical": df_search_terms,
        "df_campaign_with_hypothetical": df_campaign
    }
