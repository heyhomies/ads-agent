from typing import List, Dict
import pandas as pd
import numpy as np
import warnings
import streamlit as st


def compute_placement_adjustments(df_campaign: pd.DataFrame, target_acos: float = 0.20) -> List[Dict]:
    """Compute bid adjustment recommendations for placement rows (Gebotsanpassung) in the campaign sheet.

    For zero-sales placements with clicks, sales are adjusted to 1 Euro for meaningful RPC calculations.
    
    SPECIAL RULE: If Top-Platzierung has <20 clicks:
    - Apply +100 percentage points increase to Top-Platzierung only
    - Base CPC determined from "Standardgebot für die Anzeigengruppe" of "Anzeigengruppe" entity
    - Keep other placements unchanged
    - Cap max bid at €1.50 (scale percentage down if needed)
    - No RPC-based optimization for these campaigns
    
    NORMAL PROCESSING: If Top-Platzierung has ≥20 clicks:
    - Standard RPC-based optimization
    - If any placement adjustment exceeds 900% (Amazon's maximum), the system automatically scales:
      - Base CPC is increased by an INTEGER multiplier (calculated as int(max_percentage/900) + 1)
      - All placement percentages are reduced proportionally (maintaining relative differences)
      - Maximum percentage is capped at exactly 900%
      - No percentage goes below 0%

    Args:
        df_campaign (pd.DataFrame): The processed campaign dataframe from `process_amazon_report`.
        target_acos (float, optional): Target ACOS as a fraction (e.g. 0.20 for 20%). Defaults to 0.20.

    Returns:
        List[Dict]: Recommendation records with keys
            ['campaign_id', 'placement', 'current_adjust_pct', 'recommended_adjust_pct',
             'cpc', 'rpc', 'min_rpc', 'base_cpc', 'scaling_applied', 'integer_multiplier']
    """
    # Ensure required columns are present
    required_cols = {'kampagnen-id', 'entität', 'platzierung', 'prozentsatz', 'clicks', 'spend', 'sales'}
    missing = required_cols - set(df_campaign.columns)
    if missing:
        raise ValueError(f"Campaign dataframe missing required columns for placement analysis: {missing}")

    # Focus on placement adjustment entity rows
    df_place = df_campaign[df_campaign['entität'].str.lower() == 'gebotsanpassung'].copy()
    if df_place.empty:
        return []

    # Normalise placement names that we care about
    # Map German placement labels to concise slugs
    placement_map = {
        'platzierung produktseite': 'product_page',
        'platzierung rest der suche': 'rest_of_search',
        'top-platzierung': 'top_of_search'
    }

    # Clean placement column for matching (lowercase, strip)
    df_place['placement_key'] = df_place['platzierung'].str.lower().str.strip()

    # Filter only the three main placements
    df_place = df_place[df_place['placement_key'].isin(placement_map.keys())].copy()
    if df_place.empty:
        return []

    # Calculate CPC (clicks / spend) safeguarding divide-by-zero
    df_place['calc_cpc'] = df_place.apply(lambda r: (r['spend'] / r['clicks']) if r['clicks'] != 0 else 0, axis=1)

    # For zero sales placements with clicks, set sales to 1 Euro for meaningful calculations
    df_place['sales_adjusted'] = df_place.apply(
        lambda r: 1.0 if (r['sales'] == 0 and r['clicks'] > 0) else r['sales'], axis=1
    )
    
    # Calculate RPC (sales / clicks) using adjusted sales
    df_place['rpc'] = df_place.apply(lambda r: (r['sales_adjusted'] / r['clicks']) if r['clicks'] != 0 else float('inf'), axis=1)

    # Results list
    recommendations: List[Dict] = []

    # Group by campaign ID
    for campaign_id, grp in df_place.groupby('kampagnen-id'):
        # NEW RULE: Check if Top-Platzierung has less than 20 clicks
        top_placement_row = grp[grp['placement_key'] == 'top-platzierung']
        low_top_clicks = False
        
        if not top_placement_row.empty:
            top_clicks = top_placement_row['clicks'].iloc[0]
            if top_clicks < 20:
                low_top_clicks = True
        
        # Apply special rule for campaigns with low Top-Placement clicks
        if low_top_clicks:
            # *** SPECIAL RULE INFO DISPLAYED RIGHT UNDER CAMPAIGN HEADLINE ***
            st.info(f"🎯 **SPEZIALREGEL ANGEWENDET für Campaign {campaign_id}**: Top-Platzierung hat nur {top_clicks} Klicks (<20)")
            
            # *** IDENTIFY BASE CPC FROM ANZEIGENGRUPPE STANDARD BID ***
            # Find Anzeigengruppe entity in this campaign to get standard bid
            campaign_adgroups = df_campaign[
                (df_campaign['kampagnen-id'] == campaign_id) & 
                (df_campaign['entität'].astype(str).str.lower() == 'anzeigengruppe')
            ]
            
            # Get base CPC from "Standardgebot für die Anzeigengruppe" 
            if not campaign_adgroups.empty:
                # Check for the standard bid column (try different possible names)
                standard_bid_col = None
                possible_columns = [
                    'Standardgebot für die Anzeigengruppe',
                    'standardgebot für die anzeigengruppe', 
                    'Standardgebot für die Anzeigengruppe (Nur zu Informationszwecken)',
                    'Standard bid for ad group'
                ]
                
                for col_name in possible_columns:
                    if col_name in campaign_adgroups.columns:
                        standard_bid_col = col_name
                        break
                
                if standard_bid_col:
                    standard_bids = campaign_adgroups[standard_bid_col].dropna()
                    if not standard_bids.empty and len(standard_bids) > 0:
                        # Use the first non-null standard bid (should be consistent across ad groups)
                        base_cpc_from_adgroup = standard_bids.iloc[0]
                        try:
                            base_cpc_from_adgroup = float(base_cpc_from_adgroup)
                            st.info(f"   💰 **Base CPC aus Anzeigengruppe**: €{base_cpc_from_adgroup:.2f} ('{standard_bid_col}')")
                        except (ValueError, TypeError):
                            base_cpc_from_adgroup = 0.50
                            st.warning(f"   ⚠️ Standardgebot '{standard_bids.iloc[0]}' nicht numerisch - verwende Default: €{base_cpc_from_adgroup:.2f}")
                    else:
                        base_cpc_from_adgroup = 0.50
                        st.warning(f"   ⚠️ Standardgebot-Spalte '{standard_bid_col}' leer - verwende Default: €{base_cpc_from_adgroup:.2f}")
                else:
                    base_cpc_from_adgroup = 0.50
                    available_cols = list(campaign_adgroups.columns)
                    st.warning(f"   ⚠️ **Standardgebot-Spalte nicht gefunden** - verwende Default: €{base_cpc_from_adgroup:.2f}")
                    st.info(f"   📋 **Verfügbare Spalten in Anzeigengruppe:** {', '.join(available_cols[:8])}...")  # Show first 8 columns
                    st.info(f"   🔍 **Gesuchte Spalten:** 'Standardgebot für die Anzeigengruppe', 'Standardgebot für die Anzeigengruppe (...)', etc.")
            else:
                base_cpc_from_adgroup = 0.50
                st.warning(f"   ⚠️ Keine Anzeigengruppe in Campaign {campaign_id} gefunden - verwende Default: €{base_cpc_from_adgroup:.2f}")
            
            # Special handling: Only increase Top-Platzierung by 100 percentage points
            for _, row in grp.iterrows():
                placement_label = row['platzierung']
                current_pct = row['prozentsatz']
                
                if row['placement_key'] == 'top-platzierung':
                    # *** INCREASE BY 100 PERCENTAGE POINTS ***
                    target_increase = 100  # Start with 100 percentage points
                    recommended_pct = current_pct + target_increase
                    
                    # Calculate what the max bid would be with base CPC from ad group
                    potential_max_bid = base_cpc_from_adgroup * (1 + recommended_pct / 100)
                    
                    # *** CHECK €1.50 LIMIT AND SCALE DOWN IF NECESSARY ***
                    max_bid_limit = 1.50
                    capped_bid = False
                    actual_increase = target_increase  # Will be adjusted if needed
                    
                    # First, check if current percentage already exceeds €1.50 limit
                    current_max_bid = base_cpc_from_adgroup * (1 + current_pct / 100)
                    
                    if current_max_bid > max_bid_limit:
                        # Current percentage already too high - set to maximum that gives €1.50
                        if base_cpc_from_adgroup > 0:
                            max_possible_pct = (max_bid_limit / base_cpc_from_adgroup - 1) * 100
                            recommended_pct = max_possible_pct
                            actual_increase = 0  # No increase possible
                            capped_bid = True
                            st.warning(f"   ⚠️ **Aktuelle Anpassung {current_pct}% ergibt bereits €{current_max_bid:.2f}** - auf {recommended_pct:.0f}% reduziert für €1,50 Max-Gebot")
                            st.info(f"   📋 **Keine +100PP möglich** - Anpassung muss auf Maximum für €1,50 begrenzt werden")
                    elif potential_max_bid > max_bid_limit:
                        # +100PP would exceed limit - scale down the increase
                        if base_cpc_from_adgroup > 0:
                            max_possible_pct = (max_bid_limit / base_cpc_from_adgroup - 1) * 100
                            actual_increase = max_possible_pct - current_pct  # How much we can actually increase
                            recommended_pct = current_pct + actual_increase
                            capped_bid = True
                            st.warning(f"   ⚠️ +100PP würde €{potential_max_bid:.2f} ergeben - auf +{actual_increase:.0f}PP skaliert für €1,50 Max-Gebot")
                    
                    final_max_bid = base_cpc_from_adgroup * (1 + recommended_pct / 100)
                    
                    recommendations.append({
                        'campaign_id': campaign_id,
                        'placement': placement_label,
                        'current_adjust_pct': current_pct,
                        'recommended_adjust_pct': round(recommended_pct),
                        'cpc': base_cpc_from_adgroup,  # Use base CPC from ad group
                        'rpc': row['rpc'] if row['rpc'] != float('inf') else None,
                        'min_rpc': None,  # Not applicable for this rule
                        'base_cpc': base_cpc_from_adgroup,  # Base CPC from ad group
                        'clicks': row['clicks'],
                        'spend': row['spend'],
                        'sales': row['sales'],
                        'is_total': False,
                        'is_zero_sales': False,
                        'scaling_applied': capped_bid,
                        'special_rule': 'low_top_clicks',
                        'new_max_bid': round(final_max_bid, 2),
                        'bid_capped': capped_bid,
                        'actual_increase': round(actual_increase)
                    })
                    
                    if capped_bid:
                        if actual_increase == 0:
                            # Case 1: Current percentage was already too high - had to reduce it
                            st.success(f"   📊 **Top-Platzierung**: {current_pct}% → {round(recommended_pct)}% (auf Maximum reduziert) | Max-Gebot: €{final_max_bid:.2f}")
                        else:
                            # Case 2: +100PP was too much - scaled down the increase
                            st.success(f"   📊 **Top-Platzierung**: {current_pct}% → {round(recommended_pct)}% (+{round(actual_increase)}PP skaliert) | Max-Gebot: €{final_max_bid:.2f}")
                    else:
                        st.success(f"   📊 **Top-Platzierung**: {current_pct}% → {round(recommended_pct)}% (+{round(actual_increase)}PP) | Max-Gebot: €{final_max_bid:.2f}")
                        
                else:
                    # Keep other placements unchanged
                    recommendations.append({
                        'campaign_id': campaign_id,
                        'placement': placement_label,
                        'current_adjust_pct': current_pct,
                        'recommended_adjust_pct': current_pct,  # No change
                        'cpc': base_cpc_from_adgroup,  # Use same base CPC
                        'rpc': row['rpc'] if row['rpc'] != float('inf') else None,
                        'min_rpc': None,
                        'base_cpc': base_cpc_from_adgroup,  # Same base CPC
                        'clicks': row['clicks'],
                        'spend': row['spend'],
                        'sales': row['sales'],
                        'is_total': False,
                        'is_zero_sales': False,
                        'scaling_applied': False,
                        'special_rule': 'low_top_clicks'
                    })
            
            # Add totals row for special rule campaigns
            total_clicks = grp['clicks'].sum()
            total_spend = grp['spend'].sum()
            total_sales = grp['sales'].sum()
            
            recommendations.append({
                'campaign_id': campaign_id,
                'placement': 'Gesamt',
                'current_adjust_pct': None,
                'recommended_adjust_pct': None,
                'cpc': None,
                'current_acos': None,
                'rpc': None,
                'min_rpc': None,
                'base_cpc': None,
                'clicks': total_clicks,
                'spend': round(total_spend, 2),
                'sales': round(total_sales, 2),
                'is_total': True,
                'special_rule': 'low_top_clicks',
                'base_cpc_total': base_cpc_from_adgroup  # Use actual base CPC from ad group
            })
            
            continue  # Skip normal processing for this campaign
        
        # NORMAL PROCESSING: Campaign has sufficient Top-Placement clicks (≥20)
        # Determine min RPC among available placements
        valid_rpc = grp['rpc'].replace([float('inf')], pd.NA).dropna()
        if valid_rpc.empty:
            continue  # Skip campaign if no valid RPCs
        min_rpc = valid_rpc.min()
        
        # Base CPC calculation using adjusted sales (no minimum needed since we adjust sales to 1 Euro)
        base_cpc = min_rpc * target_acos  # Basis CPC
        # Check if this was originally a zero sales campaign before adjustment
        original_sales = grp['sales'].sum()
        is_zero_sales_campaign = (original_sales == 0)

        # First pass: Calculate initial percentages to check for 900% limit
        placement_recommendations = []
        max_recommended_pct = 0
        
        for _, row in grp.iterrows():
            placement_label = row['platzierung']
            current_pct = row['prozentsatz']
            rpc = row['rpc']
            
            if pd.isna(rpc) or rpc == float('inf') or pd.isna(min_rpc):
                # Cannot compute adjustment when no clicks or min_rpc is invalid
                recommended_pct = current_pct  # keep unchanged
            else:
                # Suppress numpy runtime warnings for this division
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    ratio = rpc / min_rpc  # ≥ 1
                # Amazon interprets 0 % as keine Änderung, 100 % als Verdopplung.
                # Daher: (ratio − 1) * 100 liefert 0 % bei minimalem RPC und 100 % bei Verdopplung.
                # Round to whole numbers for cleaner bid adjustments
                recommended_pct = round(max(ratio - 1, 0) * 100)
                max_recommended_pct = max(max_recommended_pct, recommended_pct)
            
            placement_recommendations.append({
                'row': row,
                'placement_label': placement_label,
                'current_pct': current_pct,
                'rpc': rpc,
                'recommended_pct': recommended_pct,
                'can_calculate': not (pd.isna(rpc) or rpc == float('inf') or pd.isna(min_rpc))
            })
        
        # Check if scaling is needed (any percentage > 900%)
        scaling_factor = 1.0
        integer_multiplier = 1
        if max_recommended_pct > 900:
            # Calculate integer multiplier for Base CPC (round up to ensure we stay under 900%)
            integer_multiplier = int(max_recommended_pct / 900) + 1
            scaling_factor = 900 / max_recommended_pct
            # Scale up Base CPC by integer multiplier
            base_cpc = base_cpc * integer_multiplier
        
        # Second pass: Apply scaling and create final recommendations
        for placement_rec in placement_recommendations:
            row = placement_rec['row']
            if placement_rec['can_calculate'] and scaling_factor < 1.0:
                # Apply scaling - percentage down, Base CPC already scaled up
                # Round scaled percentages to whole numbers
                recommended_pct = round(max(placement_rec['recommended_pct'] * scaling_factor, 0))
            else:
                recommended_pct = placement_rec['recommended_pct']

            recommendations.append({
                'campaign_id': campaign_id,
                'placement': placement_rec['placement_label'],
                'current_adjust_pct': placement_rec['current_pct'],
                'recommended_adjust_pct': recommended_pct,
                'cpc': row.get('cpc', row['calc_cpc']),
                'current_acos': round(row.get('acos', 0) * 100, 2) if 'acos' in row else None,
                'rpc': round(placement_rec['rpc'], 4) if placement_rec['rpc'] != float('inf') else None,
                'min_rpc': round(min_rpc, 4),
                'base_cpc': round(base_cpc, 2),
                'clicks': row['clicks'],
                'spend': row['spend'],
                'sales': row['sales'],
                'is_total': False,
                'is_zero_sales': is_zero_sales_campaign,
                'scaling_applied': scaling_factor < 1.0,
                'scaling_factor': round(scaling_factor, 4) if scaling_factor < 1.0 else None,
                'integer_multiplier': integer_multiplier if integer_multiplier > 1 else None
            })

        # --- Totals row per campaign ---
        total_clicks = grp['clicks'].sum()
        total_spend = grp['spend'].sum()
        total_sales_adjusted = grp['sales_adjusted'].sum()
        total_sales_original = grp['sales'].sum()  # Keep original for display
        total_acos = (total_spend / total_sales_adjusted * 100) if total_sales_adjusted else None
        total_rpc = (total_sales_adjusted / total_clicks) if total_clicks else None
        target_cpc_campaign = (total_rpc * target_acos) if total_rpc is not None else None
        
        # Basis-CPC = niedrigster RPC (min_rpc) * Target ACOS (scaled if needed)
        base_cpc_total = base_cpc  # Use the already scaled base_cpc

        recommendations.append({
            'campaign_id': campaign_id,
            'placement': 'Gesamt',
            'current_adjust_pct': None,
            'recommended_adjust_pct': None,
            'cpc': None,
            'current_acos': round(total_acos, 2) if total_acos is not None else None,
            'rpc': None,
            'min_rpc': None,
            'base_cpc': None,
            'clicks': total_clicks,
            'spend': round(total_spend, 2),
            'sales': round(total_sales_original, 2),
            'total_rpc': round(total_rpc, 4) if total_rpc is not None else None,
            'target_cpc': round(target_cpc_campaign, 2) if target_cpc_campaign is not None else None,
            'base_cpc_total': round(base_cpc_total, 2),
            'min_rpc_total': round(min_rpc, 4),
            'is_total': True,
            'is_zero_sales': is_zero_sales_campaign,
            'scaling_applied': scaling_factor < 1.0,
            'scaling_factor': round(scaling_factor, 4) if scaling_factor < 1.0 else None,
            'integer_multiplier': integer_multiplier if integer_multiplier > 1 else None
        })

    # Sort recommendations to ensure consistent order: Top-Platzierung, Platzierung Produktseite, Platzierung Rest der Suche
    def get_placement_sort_order(rec):
        """Return sort order for placement (lower numbers = earlier in list)"""
        placement = rec.get('placement', '').lower()
        
        # Define desired order
        order_map = {
            'top-platzierung': 1,
            'platzierung produktseite': 2,
            'platzierung rest der suche': 3,
            'gesamt': 4  # Totals always last
        }
        
        return order_map.get(placement, 999)  # Unknown placements go to end
    
    # Sort recommendations by campaign_id first, then by placement order
    recommendations.sort(key=lambda r: (r['campaign_id'], get_placement_sort_order(r)))
    
    return recommendations 