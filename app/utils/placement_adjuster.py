from typing import List, Dict
import pandas as pd
import numpy as np
import warnings


def compute_placement_adjustments(df_campaign: pd.DataFrame, target_acos: float = 0.20) -> List[Dict]:
    """Compute bid adjustment recommendations for placement rows (Gebotsanpassung) in the campaign sheet.

    Args:
        df_campaign (pd.DataFrame): The processed campaign dataframe from `process_amazon_report`.
        target_acos (float, optional): Target ACOS as a fraction (e.g. 0.20 for 20%). Defaults to 0.20.

    Returns:
        List[Dict]: Recommendation records with keys
            ['campaign_id', 'placement', 'current_adjust_pct', 'recommended_adjust_pct',
             'cpc', 'rpc', 'min_rpc', 'base_cpc']
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

    # Calculate RPC (sales / clicks) safeguarding
    df_place['rpc'] = df_place.apply(lambda r: (r['sales'] / r['clicks']) if r['clicks'] != 0 else float('inf'), axis=1)

    # Results list
    recommendations: List[Dict] = []

    # Group by campaign ID
    for campaign_id, grp in df_place.groupby('kampagnen-id'):
        # Determine min RPC among available placements
        valid_rpc = grp['rpc'].replace([float('inf')], pd.NA).dropna()
        if valid_rpc.empty:
            continue  # Skip campaign if no valid RPCs
        min_rpc = valid_rpc.min()
        
        # Base CPC calculation with minimum of 0.01 for zero sales campaigns
        base_cpc = min_rpc * target_acos  # Basis CPC
        if base_cpc == 0.0 or min_rpc == 0.0:
            base_cpc = 0.01  # Set minimum bid of 0.01 Euro for campaigns with no sales
            is_zero_sales_campaign = True
        else:
            is_zero_sales_campaign = False

        for _, row in grp.iterrows():
            placement_label = row['platzierung']
            current_pct = row['prozentsatz']
            rpc = row['rpc']
            if pd.isna(rpc) or rpc == float('inf') or min_rpc == 0 or pd.isna(min_rpc):
                # Cannot compute adjustment when sales is zero or min_rpc is invalid
                recommended_pct = current_pct  # keep unchanged
            else:
                # Suppress numpy runtime warnings for this division
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    ratio = rpc / min_rpc  # ≥ 1
                # Amazon interprets 0 % as keine Änderung, 100 % als Verdopplung.
                # Daher: (ratio − 1) * 100 liefert 0 % bei minimalem RPC und 100 % bei Verdopplung.
                recommended_pct = round(max(ratio - 1, 0) * 100, 1)

            recommendations.append({
                'campaign_id': campaign_id,
                'placement': placement_label,
                'current_adjust_pct': current_pct,
                'recommended_adjust_pct': recommended_pct,
                'cpc': row.get('cpc', row['calc_cpc']),
                'current_acos': round(row.get('acos', 0) * 100, 2) if 'acos' in row else None,
                'rpc': round(rpc, 4) if rpc != float('inf') else None,
                'min_rpc': round(min_rpc, 4),
                'base_cpc': round(base_cpc, 4),
                'clicks': row['clicks'],
                'spend': row['spend'],
                'sales': row['sales'],
                'is_total': False,
                'is_zero_sales': is_zero_sales_campaign
            })

        # --- Totals row per campaign ---
        total_clicks = grp['clicks'].sum()
        total_spend = grp['spend'].sum()
        total_sales = grp['sales'].sum()
        total_acos = (total_spend / total_sales * 100) if total_sales else None
        total_rpc = (total_sales / total_clicks) if total_clicks else None
        target_cpc_campaign = (total_rpc * target_acos) if total_rpc is not None else None
        
        # Basis-CPC = niedrigster RPC (min_rpc) * Target ACOS, minimum 0.01 Euro
        base_cpc_total = min_rpc * target_acos
        if base_cpc_total == 0.0 or min_rpc == 0.0:
            base_cpc_total = 0.01  # Set minimum bid of 0.01 Euro

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
            'sales': round(total_sales, 2),
            'total_rpc': round(total_rpc, 4) if total_rpc is not None else None,
            'target_cpc': round(target_cpc_campaign, 4) if target_cpc_campaign is not None else None,
            'base_cpc_total': round(base_cpc_total, 4),
            'min_rpc_total': round(min_rpc, 4),
            'is_total': True,
            'is_zero_sales': is_zero_sales_campaign
        })

    return recommendations 