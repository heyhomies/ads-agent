from typing import List, Dict
import pandas as pd
import numpy as np
import warnings
import streamlit as st


def compute_placement_adjustments(df_campaign: pd.DataFrame, target_acos: float = 0.20) -> List[Dict]:
    """
    SIMPLE placement adjustment computation using exact German Excel column names.
    
    Special Rule: Campaigns with Top-Platzierung <20 clicks get +100 percentage points
    """
    
    # Store full campaign data for Anzeigengruppe lookups
    df_full = df_campaign.copy()
    
    # Find the correct entity column name (could be processed to lowercase)
    entity_col = None
    if 'Entität' in df_campaign.columns:
        entity_col = 'Entität'
    elif 'entität' in df_campaign.columns:
        entity_col = 'entität'
    elif 'entity' in df_campaign.columns:
        entity_col = 'entity'
    
    if entity_col is None:
        st.error("❌ Keine Entity-Spalte gefunden!")
        return []
    
    # Filter for Gebotsanpassung entities only
    df_place = df_campaign[df_campaign[entity_col].astype(str).str.lower() == 'gebotsanpassung'].copy()
    if df_place.empty:
        return []

    # Find the correct placement column name
    placement_col = None
    if 'Platzierung' in df_campaign.columns:
        placement_col = 'Platzierung'
    elif 'platzierung' in df_campaign.columns:
        placement_col = 'platzierung'
    elif 'placement' in df_campaign.columns:
        placement_col = 'placement'
    
    if placement_col is None:
        st.error("❌ Keine Placement-Spalte gefunden!")
        return []
    
    # Add placement key for matching
    placement_map = {
        'platzierung produktseite': 'product_page',
        'platzierung rest der suche': 'rest_of_search', 
        'top-platzierung': 'top_of_search'
    }
    
    df_place['placement_key'] = df_place[placement_col].astype(str).str.lower().str.strip().map(placement_map)
    df_place = df_place[df_place['placement_key'].notna()]
    
    if df_place.empty:
        return []

    # Find column names for clicks, spend, sales, percentage
    clicks_col = 'clicks' if 'clicks' in df_campaign.columns else 'Klicks' if 'Klicks' in df_campaign.columns else 'klicks'
    spend_col = 'spend' if 'spend' in df_campaign.columns else 'Ausgaben' if 'Ausgaben' in df_campaign.columns else 'ausgaben'  
    sales_col = 'sales' if 'sales' in df_campaign.columns else 'Verkäufe' if 'Verkäufe' in df_campaign.columns else 'verkäufe'
    percentage_col = 'prozentsatz' if 'prozentsatz' in df_campaign.columns else 'Prozentsatz' if 'Prozentsatz' in df_campaign.columns else 'percentage'
    
    # Add sales_adjusted column for RPC calculation
    df_place['sales_adjusted'] = df_place[sales_col].apply(lambda x: max(x, 1.0) if x >= 0 else 1.0)
    df_place['rpc'] = df_place.apply(lambda r: (r['sales_adjusted'] / r[clicks_col]) if r[clicks_col] != 0 else float('inf'), axis=1)

    recommendations = []

    # Find campaign ID column name
    campaign_id_col = 'kampagnen-id' if 'kampagnen-id' in df_campaign.columns else 'Kampagnen-ID' if 'Kampagnen-ID' in df_campaign.columns else 'campaign_id'
    
    # Process each campaign
    for campaign_id, grp in df_place.groupby(campaign_id_col):
        
        # Check for special rule: Top-Platzierung <20 clicks
        top_placement = grp[grp['placement_key'] == 'top_of_search']
        
        if not top_placement.empty and top_placement[clicks_col].iloc[0] < 20:
            # *** SPECIAL RULE FOR LOW TRAFFIC CAMPAIGNS ***
            # Note: Display info is now handled in dashboard.py, not here
            
            # Get Base CPC from Anzeigengruppe - use dynamic column names
            anzeigengruppe = df_full[
                (df_full[campaign_id_col] == campaign_id) & 
                (df_full[entity_col].astype(str).str.lower() == 'anzeigengruppe')
            ]
            
            if not anzeigengruppe.empty:
                # Find Standardgebot column (processed version with underscores)
                standardgebot_col = None
                possible_std_cols = [
                    'standardgebot_für_die_anzeigengruppe',  # Most likely after processing
                    'Standardgebot für die Anzeigengruppe',   # Original
                    'standardgebot für die anzeigengruppe',   # Lowercase
                    'standard_bid_ad_group'                   # English fallback
                ]
                
                for col in possible_std_cols:
                    if col in anzeigengruppe.columns:
                        standardgebot_col = col
                        break
                
                if standardgebot_col:
                    standardgebot = anzeigengruppe[standardgebot_col].iloc[0]
                    try:
                        base_cpc = float(standardgebot)
                        # Debug info removed - display handled in dashboard
                    except:
                        base_cpc = 0.50
                        # Debug info removed - display handled in dashboard
                else:
                    # Debug info removed - display handled in dashboard
                    base_cpc = 0.50
            else:
                # Debug info removed - display handled in dashboard
                base_cpc = 0.50
            
            # Process each placement in this campaign
            for _, row in grp.iterrows():
                current_pct = row[percentage_col]
                
                if row['placement_key'] == 'top_of_search':
                    # Apply +100 percentage points to Top-Platzierung
                    target_pct = current_pct + 100
                    max_bid = base_cpc * (1 + target_pct / 100)
                    
                    # Cap at €1.50
                    if max_bid > 1.50:
                        # Scale down to hit €1.50 exactly
                        target_pct = ((1.50 / base_cpc) - 1) * 100
                        max_bid = 1.50
                        actual_increase = target_pct - current_pct
                        # Display info removed - handled in dashboard.py
                        # Display info removed - handled in dashboard.py
                    else:
                        actual_increase = 100
                        # Display info removed - handled in dashboard.py
                    
                    recommendations.append({
                        'campaign_id': campaign_id,
                        'placement': row[placement_col],
                        'current_adjust_pct': current_pct,
                        'recommended_adjust_pct': target_pct,
                        'cpc': base_cpc,
                        'base_cpc': base_cpc,
                        'clicks': row[clicks_col],
                        'spend': row[spend_col],
                        'sales': row[sales_col],
                        'current_acos': row.get('acos', row.get('ACOS', 0)),
                        'is_total': False,
                        'special_rule': 'low_top_clicks',
                        'new_max_bid': max_bid,
                        'bid_capped': max_bid == 1.50,
                        'actual_increase': actual_increase
                    })
                else:
                    # Other placements stay unchanged
                    recommendations.append({
                        'campaign_id': campaign_id,
                        'placement': row[placement_col],
                        'current_adjust_pct': current_pct,
                        'recommended_adjust_pct': current_pct,  # No change
                        'cpc': base_cpc,
                        'base_cpc': base_cpc,
                        'clicks': row[clicks_col],
                        'spend': row[spend_col],
                        'sales': row[sales_col],
                        'current_acos': row.get('acos', row.get('ACOS', 0)),
                        'is_total': False,
                        'special_rule': 'low_top_clicks'
                    })
            
            # Add campaign total
            total_acos = None
            if grp[sales_col].sum() > 0:
                total_acos = (grp[spend_col].sum() / grp[sales_col].sum()) * 100
            
            recommendations.append({
                'campaign_id': campaign_id,
                'placement': 'Gesamt',
                'clicks': grp[clicks_col].sum(),
                'spend': grp[spend_col].sum(),
                'sales': grp[sales_col].sum(),
                'current_acos': total_acos,
                'is_total': True,
                'special_rule': 'low_top_clicks',
                'base_cpc_total': base_cpc
            })
            
            continue  # Skip normal processing
        
        # *** NORMAL PROCESSING for campaigns with ≥20 clicks ***
        valid_rpc = grp['rpc'].replace([float('inf')], pd.NA).dropna()
        if valid_rpc.empty:
            continue
            
        min_rpc = valid_rpc.min()
        base_cpc = min_rpc * target_acos
        
        # Normal RPC-based recommendations...
        # (keeping existing logic for normal campaigns)
        for _, row in grp.iterrows():
            target_rpc = row['sales_adjusted'] / row[clicks_col] if row[clicks_col] > 0 else float('inf')
            if target_rpc == float('inf'):
                continue
                
            target_cpc = target_rpc * target_acos
            current_cpc = row[spend_col] / row[clicks_col] if row[clicks_col] > 0 else 0
            
            if current_cpc > 0:
                recommended_pct = ((target_cpc / base_cpc) - 1) * 100
                recommended_pct = max(0, min(900, recommended_pct))  # Cap at 0-900%
            else:
                recommended_pct = 0
            
            recommendations.append({
                'campaign_id': campaign_id,
                'placement': row[placement_col],
                'current_adjust_pct': row[percentage_col],
                'recommended_adjust_pct': round(recommended_pct),
                'cpc': current_cpc,
                'rpc': target_rpc,
                'min_rpc': min_rpc,
                'base_cpc': base_cpc,
                'clicks': row[clicks_col],
                'spend': row[spend_col],
                'sales': row[sales_col],
                'current_acos': row.get('acos', row.get('ACOS', 0)),
                'is_total': False
            })
        
        # Add normal campaign total
        total_acos = None
        if grp[sales_col].sum() > 0:
            total_acos = (grp[spend_col].sum() / grp[sales_col].sum()) * 100
            
        recommendations.append({
            'campaign_id': campaign_id,
            'placement': 'Gesamt',
            'clicks': grp[clicks_col].sum(),
            'spend': grp[spend_col].sum(),
            'sales': grp[sales_col].sum(),
            'current_acos': total_acos,
            'total_rpc': grp[sales_col].sum() / grp[clicks_col].sum() if grp[clicks_col].sum() > 0 else None,
            'target_cpc': min_rpc * target_acos if min_rpc else None,
            'base_cpc_total': base_cpc,
            'min_rpc_total': min_rpc,
            'is_total': True
        })

    return recommendations
