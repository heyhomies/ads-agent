from typing import List, Dict
import pandas as pd
import numpy as np
import warnings
import streamlit as st


def compute_placement_adjustments(df_campaign: pd.DataFrame, target_acos: float = 0.20, df_campaign_full: pd.DataFrame = None, campaign_target_acos: dict | None = None) -> List[Dict]:
    """Compute bid adjustment recommendations for placement rows (Gebotsanpassung) in the campaign sheet.

    For zero-sales placements with clicks, sales are adjusted to 1 Euro for meaningful RPC calculations.
    If any placement adjustment exceeds 900% (Amazon's maximum), the system automatically scales:
    - Base CPC is increased by an INTEGER multiplier (calculated as int(max_percentage/900) + 1)
    - All placement percentages are reduced proportionally (maintaining relative differences)
    - Maximum percentage is capped at exactly 900%
    - No percentage goes below 0%

    MAX BID PROTECTION: All campaigns (normal and special rule) have max bid capped at €1.50.
    If the calculated max bid would exceed €1.50, the percentage is scaled down accordingly.

    SPECIAL RULE: If Top-Platzierung has < 20 clicks, apply +100 percentage points increase only to Top-Platzierung,
    using Base CPC from Anzeigengruppe entity instead of RPC-based calculation.

    Args:
        df_campaign (pd.DataFrame): The processed campaign dataframe from `process_amazon_report`.
        target_acos (float, optional): Target ACOS as a fraction (e.g. 0.20 for 20%). Defaults to 0.20.
        df_campaign_full (pd.DataFrame, optional): Full campaign dataframe for Base CPC lookup.

    Returns:
        List[Dict]: Recommendation records with keys
            ['campaign_id', 'placement', 'current_adjust_pct', 'recommended_adjust_pct',
             'cpc', 'rpc', 'min_rpc', 'base_cpc', 'scaling_applied', 'integer_multiplier']
    """
    # Dynamically detect column names (German original or English processed)
    def find_column(df, possible_names):
        """Find the first matching column name from a list of possibilities"""
        for name in possible_names:
            if name in df.columns:
                return name
        return None

    # Find actual column names
    campaign_id_col = find_column(df_campaign, ['kampagnen-id', 'campaign_id', 'Kampagnen-ID'])
    entity_col = find_column(df_campaign, ['entität', 'entity', 'Entität'])
    placement_col = find_column(df_campaign, ['platzierung', 'placement', 'Platzierung'])
    percentage_col = find_column(df_campaign, ['prozentsatz', 'percentage', 'Prozentsatz'])
    clicks_col = find_column(df_campaign, ['clicks', 'klicks', 'Klicks'])
    spend_col = find_column(df_campaign, ['spend', 'ausgaben', 'Ausgaben'])
    sales_col = find_column(df_campaign, ['sales', 'verkäufe', 'Verkäufe'])

    # Check if we found all required columns
    missing_cols = []
    col_mapping = {
        'campaign_id': campaign_id_col,
        'entity': entity_col, 
        'placement': placement_col,
        'percentage': percentage_col,
        'clicks': clicks_col,
        'spend': spend_col,
        'sales': sales_col
    }
    
    for field, col_name in col_mapping.items():
        if col_name is None:
            missing_cols.append(field)
    
    if missing_cols:
        available_cols = list(df_campaign.columns)[:10]  # Show first 10 columns
        raise ValueError(f"Missing required columns: {missing_cols}. Available columns (first 10): {available_cols}")

    # Focus on placement adjustment entity rows
    df_place = df_campaign[df_campaign[entity_col].str.lower() == 'gebotsanpassung'].copy()
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
    df_place['placement_key'] = df_place[placement_col].str.lower().str.strip()

    # Filter only the three main placements
    df_place = df_place[df_place['placement_key'].isin(placement_map.keys())].copy()
    if df_place.empty:
        return []

    # Column names are already identified above - remove duplicate assignment

    # Calculate CPC (spend / clicks) safeguarding divide-by-zero
    df_place['calc_cpc'] = df_place.apply(lambda r: (r[spend_col] / r[clicks_col]) if r[clicks_col] != 0 else 0, axis=1)

    # For zero sales placements with clicks, set sales to 1 Euro for meaningful calculations
    df_place['sales_adjusted'] = df_place.apply(
        lambda r: 1.0 if (r[sales_col] == 0 and r[clicks_col] > 0) else r[sales_col], axis=1
    )
    
    # Calculate RPC (sales / clicks) using adjusted sales
    df_place['rpc'] = df_place.apply(lambda r: (r['sales_adjusted'] / r[clicks_col]) if r[clicks_col] != 0 else float('inf'), axis=1)

    # Results list
    recommendations: List[Dict] = []

    # Pre-build campaign_id → campaign_name mapping for per-campaign ACOS lookup
    campaign_name_col = find_column(df_campaign, ['campaign_name', 'kampagne', 'kampagnenname'])
    id_to_name: dict = {}
    if campaign_name_col and campaign_id_col in df_campaign.columns:
        id_to_name = df_campaign[[campaign_id_col, campaign_name_col]].dropna().drop_duplicates().set_index(campaign_id_col)[campaign_name_col].to_dict()

    # Group by campaign ID
    for campaign_id, grp in df_place.groupby(campaign_id_col):

        # Resolve effective target ACOS for this campaign
        campaign_name = str(id_to_name.get(campaign_id, ''))
        if campaign_target_acos and campaign_name in campaign_target_acos:
            effective_target_acos = campaign_target_acos[campaign_name] / 100
        else:
            effective_target_acos = target_acos

        # *** CHECK FOR SPECIAL RULE: Top-Platzierung < 20 clicks ***
        top_placement = grp[grp['placement_key'] == 'top-platzierung']
        
        if not top_placement.empty and top_placement[clicks_col].iloc[0] < 20:
            # *** APPLY SPECIAL RULE ***
            # Get Base CPC from Anzeigengruppe entity if full dataframe available
            base_cpc = 0.50  # Default
            
            if df_campaign_full is not None:
                # Try to find Anzeigengruppe entity for this campaign
                anzeigengruppe = df_campaign_full[
                    (df_campaign_full[campaign_id_col] == campaign_id) & 
                    (df_campaign_full[entity_col].astype(str).str.lower() == 'anzeigengruppe')
                ]
                
                if not anzeigengruppe.empty:
                    # Look for Standard bid column
                    possible_cols = [
                        'standardgebot_für_die_anzeigengruppe',
                        'Standardgebot für die Anzeigengruppe',  
                        'standardgebot für die anzeigengruppe'
                    ]
                    
                    for col in possible_cols:
                        if col in anzeigengruppe.columns:
                            try:
                                base_cpc = float(anzeigengruppe[col].iloc[0])
                                break
                            except:
                                continue
            
            # Process each placement with special rule
            for _, row in grp.iterrows():
                current_pct = row[percentage_col]
                
                if row['placement_key'] == 'top-platzierung':
                    # Apply +100 percentage points to Top-Platzierung
                    target_pct = current_pct + 100
                    
                    # *** FIRST: Cap at 900% maximum (Amazon limit) ***
                    if target_pct > 900:
                        target_pct = 900
                    
                    max_bid = base_cpc * (1 + target_pct / 100)
                    actual_increase = target_pct - current_pct
                    
                    # *** SECOND: Cap at €1.50 max bid ***
                    if max_bid > 1.50:
                        # Scale down to hit €1.50 exactly
                        target_pct = ((1.50 / base_cpc) - 1) * 100
                        # But still respect 900% limit
                        target_pct = min(target_pct, 900)
                        max_bid = 1.50
                        actual_increase = target_pct - current_pct
                    
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
                        'current_acos': (row[spend_col] / row[sales_col] * 100) if row[sales_col] > 0 else 0,
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
                        'current_acos': (row[spend_col] / row[sales_col] * 100) if row[sales_col] > 0 else 0,
                        'is_total': False,
                        'special_rule': 'low_top_clicks'
                    })
            
            # Add campaign total for special rule
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
                'base_cpc_total': base_cpc,
                'is_total': True,
                'special_rule': 'low_top_clicks'
            })
            
        else:
            # *** NORMAL CAMPAIGN LOGIC (ORIGINAL) ***
            # Determine min RPC among available placements
            valid_rpc = grp['rpc'].replace([float('inf')], pd.NA).dropna()
            if valid_rpc.empty:
                continue  # Skip campaign if no valid RPCs
            min_rpc = valid_rpc.min()
            
            # Base CPC calculation using adjusted sales (no minimum needed since we adjust sales to 1 Euro)
            base_cpc = min_rpc * effective_target_acos  # Basis CPC
            # Check if this was originally a zero sales campaign before adjustment
            original_sales = grp[sales_col].sum()
            is_zero_sales_campaign = (original_sales == 0)

            # First pass: Calculate initial percentages to check for 900% limit
            placement_recommendations = []
            max_recommended_pct = 0
            
            for _, row in grp.iterrows():
                placement_label = row[placement_col]
                current_pct = row[percentage_col]
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

                # *** ADD €1.50 MAX BID CAPPING FOR NORMAL CAMPAIGNS ***
                max_bid_original = base_cpc * (1 + recommended_pct / 100)
                bid_capped = False
                
                if max_bid_original > 1.50:
                    # Scale down percentage to hit €1.50 max bid
                    recommended_pct = ((1.50 / base_cpc) - 1) * 100
                    recommended_pct = max(0, recommended_pct)  # Don't go negative
                    bid_capped = True

                recommendations.append({
                    'campaign_id': campaign_id,
                    'placement': placement_rec['placement_label'],
                    'current_adjust_pct': placement_rec['current_pct'],
                    'recommended_adjust_pct': round(recommended_pct),
                    'cpc': row.get('cpc', row['calc_cpc']),
                    'current_acos': round((row[spend_col] / row[sales_col] * 100), 2) if row[sales_col] > 0 else None,
                    'rpc': round(placement_rec['rpc'], 4) if placement_rec['rpc'] != float('inf') else None,
                    'min_rpc': round(min_rpc, 4),
                    'base_cpc': round(base_cpc, 2),
                    'clicks': row[clicks_col],
                    'spend': row[spend_col],
                    'sales': row[sales_col],
                    'is_total': False,
                    'is_zero_sales': is_zero_sales_campaign,
                    'scaling_applied': scaling_factor < 1.0,
                    'scaling_factor': round(scaling_factor, 4) if scaling_factor < 1.0 else None,
                    'integer_multiplier': integer_multiplier if integer_multiplier > 1 else None,
                    'bid_capped': bid_capped,  # €1.50 bid capping applied
                    'special_rule': None,  # Mark as normal campaign
                    'new_max_bid': min(max_bid_original, 1.50)  # Store capped max bid
                })

            # --- Totals row per campaign ---
            total_clicks = grp[clicks_col].sum()
            total_spend = grp[spend_col].sum()
            total_sales_adjusted = grp['sales_adjusted'].sum()
            total_sales_original = grp[sales_col].sum()  # Keep original for display
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
                'integer_multiplier': integer_multiplier if integer_multiplier > 1 else None,
                'bid_capped': False,  # Totals row doesn't have bid capping
                'special_rule': None  # Normal campaign total
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