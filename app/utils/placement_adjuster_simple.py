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
    
    # Filter for Gebotsanpassung entities only
    df_place = df_campaign[df_campaign['Entität'] == 'Gebotsanpassung'].copy()
    if df_place.empty:
        return []

    # Add placement key for matching
    placement_map = {
        'Platzierung Produktseite': 'product_page',
        'Platzierung Rest der Suche': 'rest_of_search', 
        'Top-Platzierung': 'top_of_search'
    }
    
    df_place['placement_key'] = df_place['Platzierung'].map(placement_map)
    df_place = df_place[df_place['placement_key'].notna()]
    
    if df_place.empty:
        return []

    # Add sales_adjusted column for RPC calculation
    df_place['sales_adjusted'] = df_place['Verkäufe'].apply(lambda x: max(x, 1.0) if x >= 0 else 1.0)
    df_place['rpc'] = df_place.apply(lambda r: (r['sales_adjusted'] / r['Klicks']) if r['Klicks'] != 0 else float('inf'), axis=1)

    recommendations = []

    # Process each campaign
    for campaign_id, grp in df_place.groupby('Kampagnen-ID'):
        
        # Check for special rule: Top-Platzierung <20 clicks
        top_placement = grp[grp['placement_key'] == 'top_of_search']
        
        if not top_placement.empty and top_placement['Klicks'].iloc[0] < 20:
            # *** SPECIAL RULE FOR LOW TRAFFIC CAMPAIGNS ***
            st.info(f"🎯 **SPEZIALREGEL für Campaign {campaign_id}**: Top-Platzierung <20 Klicks")
            
            # Get Base CPC from Anzeigengruppe
            anzeigengruppe = df_full[
                (df_full['Kampagnen-ID'] == campaign_id) & 
                (df_full['Entität'] == 'Anzeigengruppe')
            ]
            
            if not anzeigengruppe.empty:
                standardgebot = anzeigengruppe['Standardgebot für die Anzeigengruppe'].iloc[0]
                try:
                    base_cpc = float(standardgebot)
                    st.success(f"   💰 **Base CPC**: €{base_cpc:.2f} aus Anzeigengruppe")
                except:
                    base_cpc = 0.50
                    st.warning(f"   ⚠️ Standardgebot '{standardgebot}' nicht numerisch - Default: €{base_cpc:.2f}")
            else:
                # Show available campaigns for debugging  
                available_campaigns = df_full[df_full['Entität'] == 'Anzeigengruppe']['Kampagnen-ID'].unique()
                base_cpc = 0.50
                st.warning(f"   📋 Campaign {campaign_id} hat keine Anzeigengruppe - Default: €{base_cpc:.2f}")
                st.info(f"   ℹ️ Verfügbare: {sorted(available_campaigns)[:3]}...")
            
            # Process each placement in this campaign
            for _, row in grp.iterrows():
                current_pct = row['Prozentsatz']
                
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
                        st.warning(f"   ⚠️ +100PP → €{base_cpc * (1 + (current_pct + 100) / 100):.2f} - skaliert auf +{actual_increase:.0f}PP für €1.50")
                        st.success(f"   📊 Top-Platzierung: {current_pct}% → {target_pct:.0f}% (+{actual_increase:.0f}PP) | €{max_bid:.2f}")
                    else:
                        actual_increase = 100
                        st.success(f"   📊 Top-Platzierung: {current_pct}% → {target_pct:.0f}% (+100PP) | €{max_bid:.2f}")
                    
                    recommendations.append({
                        'campaign_id': campaign_id,
                        'placement': row['Platzierung'],
                        'current_adjust_pct': current_pct,
                        'recommended_adjust_pct': target_pct,
                        'cpc': base_cpc,
                        'base_cpc': base_cpc,
                        'clicks': row['Klicks'],
                        'spend': row['Ausgaben'],
                        'sales': row['Verkäufe'],
                        'current_acos': row.get('ACOS', 0) * 100 if row.get('ACOS', 0) < 1 else row.get('ACOS', 0),
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
                        'placement': row['Platzierung'],
                        'current_adjust_pct': current_pct,
                        'recommended_adjust_pct': current_pct,  # No change
                        'cpc': base_cpc,
                        'base_cpc': base_cpc,
                        'clicks': row['Klicks'],
                        'spend': row['Ausgaben'],
                        'sales': row['Verkäufe'],
                        'current_acos': row.get('ACOS', 0) * 100 if row.get('ACOS', 0) < 1 else row.get('ACOS', 0),
                        'is_total': False,
                        'special_rule': 'low_top_clicks'
                    })
            
            # Add campaign total
            total_acos = None
            if grp['Verkäufe'].sum() > 0:
                total_acos = (grp['Ausgaben'].sum() / grp['Verkäufe'].sum()) * 100
            
            recommendations.append({
                'campaign_id': campaign_id,
                'placement': 'Gesamt',
                'clicks': grp['Klicks'].sum(),
                'spend': grp['Ausgaben'].sum(),
                'sales': grp['Verkäufe'].sum(),
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
            target_rpc = row['sales_adjusted'] / row['Klicks'] if row['Klicks'] > 0 else float('inf')
            if target_rpc == float('inf'):
                continue
                
            target_cpc = target_rpc * target_acos
            current_cpc = row['Ausgaben'] / row['Klicks'] if row['Klicks'] > 0 else 0
            
            if current_cpc > 0:
                recommended_pct = ((target_cpc / base_cpc) - 1) * 100
                recommended_pct = max(0, min(900, recommended_pct))  # Cap at 0-900%
            else:
                recommended_pct = 0
            
            recommendations.append({
                'campaign_id': campaign_id,
                'placement': row['Platzierung'],
                'current_adjust_pct': row['Prozentsatz'],
                'recommended_adjust_pct': round(recommended_pct),
                'cpc': current_cpc,
                'rpc': target_rpc,
                'min_rpc': min_rpc,
                'base_cpc': base_cpc,
                'clicks': row['Klicks'],
                'spend': row['Ausgaben'],
                'sales': row['Verkäufe'],
                'current_acos': row.get('ACOS', 0) * 100 if row.get('ACOS', 0) < 1 else row.get('ACOS', 0),
                'is_total': False
            })
        
        # Add normal campaign total
        total_acos = None
        if grp['Verkäufe'].sum() > 0:
            total_acos = (grp['Ausgaben'].sum() / grp['Verkäufe'].sum()) * 100
            
        recommendations.append({
            'campaign_id': campaign_id,
            'placement': 'Gesamt',
            'clicks': grp['Klicks'].sum(),
            'spend': grp['Ausgaben'].sum(),
            'sales': grp['Verkäufe'].sum(),
            'current_acos': total_acos,
            'total_rpc': grp['Verkäufe'].sum() / grp['Klicks'].sum() if grp['Klicks'].sum() > 0 else None,
            'target_cpc': min_rpc * target_acos if min_rpc else None,
            'base_cpc_total': base_cpc,
            'min_rpc_total': min_rpc,
            'is_total': True
        })

    return recommendations
