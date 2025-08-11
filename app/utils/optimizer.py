import pandas as pd
import numpy as np
import os
from typing import Dict, List, Any, TypedDict, Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv
import streamlit as st
import traceback

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
import openai

# Load environment variables from .env file
load_dotenv()

# Type definitions for LangGraph state
class PPCState(TypedDict):
    df_campaign: pd.DataFrame
    df_search_terms: pd.DataFrame
    client_config: Dict[str, Any]
    bid_changes: List[Dict[str, Any]]
    keyword_changes: List[Dict[str, Any]]
    optimization_summary: Dict[str, Any]
    current_step: str
    debug_info: List[str]


def analyze_keywords(state: PPCState) -> PPCState:
    """
    Analyze keywords based on the optimization rules and flag for changes
    """
    # Get dataframes from state
    df_search_terms = state['df_search_terms'].copy()
    client_config = state['client_config']
    
    # Initialize keyword changes list
    keyword_changes = []
    
    # Get the target ACOS based on client configuration (convert to decimal)
    target_acos = 0.20  # Default target (20% as decimal)
    if client_config.get('is_market_leader', False):
        target_acos = 0.08  # 8% as decimal
    if client_config.get('has_large_inventory', False):
        target_acos = 0.08  # 8% as decimal
    # Override with explicit target if provided
    if 'target_acos' in client_config and client_config['target_acos'] is not None:
        target_acos = float(client_config['target_acos']) / 100  # Convert percentage to decimal
    
    # Ensure required columns exist with defaults if missing - prefer values from Excel
    for col in ['clicks', 'orders', 'acos', 'conversion_rate']:
        if col not in df_search_terms.columns:
            if col in ['clicks', 'orders']:
                df_search_terms[col] = 0
            elif col == 'acos':
                # Only calculate ACOS if not available in Excel (as decimal value)
                if 'spend' in df_search_terms.columns and 'sales' in df_search_terms.columns:
                    df_search_terms[col] = (df_search_terms['spend'] / df_search_terms['sales'].replace(0, np.nan))
                else:
                    df_search_terms[col] = np.nan
            elif col == 'conversion_rate':
                # Only calculate conversion rate if not available in Excel (as decimal value)
                if 'clicks' in df_search_terms.columns and 'orders' in df_search_terms.columns:
                    df_search_terms[col] = (df_search_terms['orders'] / df_search_terms['clicks'].replace(0, np.nan))
                else:
                    df_search_terms[col] = np.nan
    
    # Calculate hypothetical ACOS for products with 0 sales using database pricing
    from app.utils.hypothetical_acos import HypotheticalACOSCalculator
    try:
        calculator = HypotheticalACOSCalculator()
        df_search_terms = calculator.enrich_dataframe_with_hypothetical_acos(
            df_search_terms, 
            client_config.get('target_acos', 20.0)
        )
        # Update state with enriched data
        state['df_search_terms'] = df_search_terms
    except Exception as e:
        state['debug_info'].append(f"Warning: Could not calculate hypothetical ACOS: {e}")
    
    # Convert numeric columns to numeric type in case they're strings
    for col in ['clicks', 'orders', 'acos', 'conversion_rate']:
        if col in df_search_terms.columns:
            df_search_terms[col] = pd.to_numeric(df_search_terms[col], errors='coerce')
    
    # Apply keyword rules
    # Rule 1: Pause keywords with ≥ 25 clicks and no conversions
    clicks_threshold = client_config.get('keywords_min_clicks', 25)
    mask_no_conversion = (df_search_terms['clicks'] >= clicks_threshold) & (df_search_terms['orders'] == 0)
    for _, row in df_search_terms[mask_no_conversion].iterrows():
        # Use 'customer_search_term' for reporting and 'keyword' for bidding
        keyword = row['keyword'] if 'keyword' in row else row['search_term']
        search_term = row['customer_search_term'] if 'customer_search_term' in row else row['search_term']
        
        keyword_changes.append({
            'keyword': keyword,
            'customer_search_term': search_term,
            'action': 'pause',
            'reason': f"No conversions after {row['clicks']} clicks",
            'original_data': {k: v for k, v in row.items() if k in ['clicks', 'orders', 'acos', 'conversion_rate']}
        })
    
    # Rule 2: Pause keywords with ACOS > target and CR < 10%
    min_conversion_rate = client_config.get('min_conversion_rate', 10.0) / 100  # Convert to decimal
    # Handle NaN values properly in the comparison
    mask_high_acos_low_cr = (
        (~pd.isna(df_search_terms['acos'])) & 
        (df_search_terms['acos'] > target_acos) & 
        ((pd.isna(df_search_terms['conversion_rate'])) | (df_search_terms['conversion_rate'] < min_conversion_rate))
    )
    for _, row in df_search_terms[mask_high_acos_low_cr].iterrows():
        # Skip if already flagged for change
        keyword = row['keyword'] if 'keyword' in row else row['search_term']
        if any(change['keyword'] == keyword for change in keyword_changes):
            continue
        
        # Use 'customer_search_term' for reporting and 'keyword' for bidding
        search_term = row['customer_search_term'] if 'customer_search_term' in row else row['search_term']
        
        # Handle the case where conversion_rate might be NaN
        cr_display = f"{row['conversion_rate']*100:.1f}%" if not pd.isna(row['conversion_rate']) else "N/A"
        acos_display = f"{row['acos']*100:.1f}%" if not pd.isna(row['acos']) else "N/A"
        
        keyword_changes.append({
            'keyword': keyword,
            'customer_search_term': search_term,
            'action': 'pause',
            'reason': f"High ACOS ({acos_display}) and low conversion rate ({cr_display})",
            'original_data': {k: v for k, v in row.items() if k in ['clicks', 'orders', 'acos', 'conversion_rate']}
        })
    
    # Rule 3: Keep keywords with ACOS ≤ target AND CR ≥ min_conversion_rate
    mask_keep = (
        (~pd.isna(df_search_terms['acos']) & (df_search_terms['acos'] <= target_acos)) & 
        (~pd.isna(df_search_terms['conversion_rate']) & (df_search_terms['conversion_rate'] >= min_conversion_rate))
    )
    for _, row in df_search_terms[mask_keep].iterrows():
        # Skip if already flagged for change
        keyword = row['keyword'] if 'keyword' in row else row['search_term']
        if any(change['keyword'] == keyword for change in keyword_changes):
            continue
            
        # Use 'customer_search_term' for reporting and 'keyword' for bidding
        search_term = row['customer_search_term'] if 'customer_search_term' in row else row['search_term']
        
        # Handle the case where metrics might be NaN
        cr_display = f"{row['conversion_rate']*100:.1f}%" if not pd.isna(row['conversion_rate']) else "N/A"
        acos_display = f"{row['acos']*100:.1f}%" if not pd.isna(row['acos']) else "N/A"
        
        keyword_changes.append({
            'keyword': keyword,
            'customer_search_term': search_term,
            'action': 'keep',
            'reason': f"Good performance: ACOS ({acos_display}) and good conversion rate ({cr_display})",
            'original_data': {k: v for k, v in row.items() if k in ['clicks', 'orders', 'acos', 'conversion_rate']}
        })
    
    # Update state
    state['keyword_changes'] = keyword_changes
    state['current_step'] = 'analyze_bids'
    state['debug_info'].append(f"Processed {len(keyword_changes)} keyword changes")
    
    return state


def adjust_bids(state: PPCState) -> PPCState:
    """
    Adjust bids based on keyword performance
    """
    # Get dataframes from state
    df_search_terms = state['df_search_terms'].copy()
    df_campaign = state['df_campaign'].copy()
    client_config = state['client_config']
    
    # Initialize bid changes list
    bid_changes = []
    
    # Get the target ACOS based on client configuration (convert to decimal)
    target_acos = 0.20  # Default target (20% as decimal)
    if client_config.get('is_market_leader', False):
        target_acos = 0.08  # 8% as decimal
    if client_config.get('has_large_inventory', False):
        target_acos = 0.08  # 8% as decimal
    # Override with explicit target if provided
    if 'target_acos' in client_config and client_config['target_acos'] is not None:
        target_acos = float(client_config['target_acos']) / 100  # Convert percentage to decimal
    
    # For each keyword with enough data, calculate the optimal bid
    mask_enough_data = df_search_terms['clicks'] > 10
    for _, row in df_search_terms[mask_enough_data].iterrows():
        # Get the correct keyword identifier for bidding
        keyword = row['keyword'] if 'keyword' in row else row['search_term']
        search_term = row['customer_search_term'] if 'customer_search_term' in row else row['search_term']
        
        # Skip keywords that will be paused
        if any(change['keyword'] == keyword and change['action'] == 'pause' 
               for change in state['keyword_changes']):
            continue
        
        # Current metrics
        current_acos = row['acos'] if not pd.isna(row['acos']) else 0
        current_cpc = row['cpc'] if not pd.isna(row['cpc']) else 0
        
        # Bid adjustment based on ACOS performance
        if current_acos == 0 and row['orders'] > 0:
            # Special case: ACOS is 0 but has orders (should be impossible)
            adjustment_factor = 1.1  # Increase slightly
        elif current_acos == 0 and row['orders'] == 0:
            # No conversions, reduce bid
            adjustment_factor = 0.7
        elif current_acos > target_acos * 1.5:
            # ACOS way too high, reduce bid significantly
            adjustment_factor = 0.6
        elif current_acos > target_acos:
            # ACOS too high, reduce bid
            adjustment_factor = target_acos / current_acos
        elif current_acos < target_acos * 0.5 and row['orders'] > 0:
            # ACOS much lower than target and has orders, can increase bid
            adjustment_factor = 1.3
        elif current_acos < target_acos and row['orders'] > 0:
            # ACOS lower than target and has orders, can increase bid slightly
            adjustment_factor = 1.1
        else:
            # Keep bid the same
            adjustment_factor = 1.0
        
        # Apply adjustment
        new_bid = current_cpc * adjustment_factor
        
        # Add to bid changes if there's a significant change
        if abs(adjustment_factor - 1.0) > 0.05:  # 5% threshold for changes
            bid_changes.append({
                'keyword': keyword,
                'customer_search_term': search_term,
                'current_bid': current_cpc,
                'new_bid': new_bid,
                'change_percentage': (adjustment_factor - 1) * 100,
                'reason': get_bid_change_reason(current_acos, target_acos, row['orders'], row['clicks']),
                'original_data': {k: v for k, v in row.items() if k in ['clicks', 'orders', 'acos', 'conversion_rate']}
            })
    
    # Update state
    state['bid_changes'] = bid_changes
    state['current_step'] = 'generate_summary'
    state['debug_info'].append(f"Processed {len(bid_changes)} bid changes")
    
    return state


def get_bid_change_reason(current_acos, target_acos, orders, clicks):
    """Helper function to generate human-readable reasons for bid changes"""
    if current_acos == 0 and orders == 0:
        return f"No conversions after {clicks} clicks"
    elif current_acos > target_acos * 1.5:
        return f"ACOS ({current_acos*100:.1f}%) is much higher than target ({target_acos*100:.1f}%)"
    elif current_acos > target_acos:
        return f"ACOS ({current_acos*100:.1f}%) is higher than target ({target_acos*100:.1f}%)"
    elif current_acos < target_acos * 0.5 and orders > 0:
        return f"ACOS ({current_acos*100:.1f}%) is much lower than target ({target_acos*100:.1f}%), room to bid higher for more traffic"
    elif current_acos < target_acos and orders > 0:
        return f"ACOS ({current_acos*100:.1f}%) is below target ({target_acos*100:.1f}%), slight increase to get more traffic"
    else:
        return "Current performance is acceptable"


def generate_optimization_summary(state: PPCState) -> PPCState:
    """
    Generate a summary of all the changes to be made
    """
    # Get changes from state
    keyword_changes = state['keyword_changes']
    bid_changes = state['bid_changes']
    
    # Count stats
    keywords_to_pause = [k for k in keyword_changes if k['action'] == 'pause']
    keywords_to_keep = [k for k in keyword_changes if k['action'] == 'keep']
    bids_to_increase = [b for b in bid_changes if b['change_percentage'] > 0]
    bids_to_decrease = [b for b in bid_changes if b['change_percentage'] < 0]
    
    # Calculate averages
    avg_pause_acos = np.mean([k['original_data']['acos'] for k in keywords_to_pause 
                             if k['original_data'] and 'acos' in k['original_data'] and not pd.isna(k['original_data']['acos'])]) if keywords_to_pause else 0
    avg_bid_increase = np.mean([b['change_percentage'] for b in bids_to_increase]) if bids_to_increase else 0
    avg_bid_decrease = np.mean([b['change_percentage'] for b in bids_to_decrease]) if bids_to_decrease else 0
    
    # Generate summary
    summary = {
        'total_keywords_analyzed': len(state['df_search_terms'] if state.get('df_search_terms') is not None else []),
        'keywords_to_pause': len(keywords_to_pause),
        'keywords_to_keep': len(keywords_to_keep),
        'bids_to_adjust': len(bid_changes),
        'bids_to_increase': len(bids_to_increase),
        'bids_to_decrease': len(bids_to_decrease),
        'avg_pause_acos': avg_pause_acos,
        'avg_bid_increase': avg_bid_increase,
        'avg_bid_decrease': avg_bid_decrease,
        'estimated_impact': {
            'projected_acos_reduction': estimate_acos_impact(state),
            'cost_saving': estimate_cost_savings(state),
            'efficiency_improvement': estimate_efficiency_improvement(state)
        },
        'general_recommendations': generate_ai_recommendations(state)
    }
    
    # Update state
    state['optimization_summary'] = summary
    state['current_step'] = 'complete'
    state['debug_info'].append("Optimization summary generated")
    
    return state


def estimate_acos_impact(state: PPCState) -> float:
    """Estimate the impact on ACOS from the proposed changes"""
    df_search_terms = state['df_search_terms']
    if df_search_terms is None or 'keyword' not in df_search_terms.columns: # Check for keyword column
        print("Warning: 'keyword' column missing in df_search_terms for ACOS impact estimation.")
        return 0
        
    current_spend = df_search_terms['spend'].sum() if 'spend' in df_search_terms.columns else 0
    current_sales = df_search_terms['sales'].sum() if 'sales' in df_search_terms.columns else 0
    
    keywords_to_pause_identifiers = [k['keyword'] for k in state['keyword_changes'] if k['action'] == 'pause']
    paused_spend = df_search_terms[df_search_terms['keyword'].isin(keywords_to_pause_identifiers)]['spend'].sum() 
    
    bid_change_impact = 0
    for change in state['bid_changes']:
        keyword_identifier = change['keyword'] # This is the biddable keyword
        change_pct = change['change_percentage'] / 100
        # Match using the 'keyword' (biddable keyword) column
        keyword_spend_series = df_search_terms[df_search_terms['keyword'] == keyword_identifier]['spend']
        keyword_spend = keyword_spend_series.sum() if not keyword_spend_series.empty else 0
        bid_change_impact += keyword_spend * change_pct
    
    new_spend = current_spend - paused_spend + bid_change_impact
    
    paused_sales = df_search_terms[df_search_terms['keyword'].isin(keywords_to_pause_identifiers)]['sales'].sum()
    new_sales = current_sales - paused_sales
    
    if new_sales == 0 or current_sales == 0 or new_spend < 0: # Added check for new_spend < 0
        return 0
    
    current_acos_calc = (current_spend / current_sales) * 100 if current_sales > 0 else 0
    new_acos_calc = (new_spend / new_sales) * 100 if new_sales > 0 else 0
    
    return current_acos_calc - new_acos_calc


def estimate_cost_savings(state: PPCState) -> float:
    """Estimate the cost savings from the proposed changes"""
    df_search_terms = state['df_search_terms']
    if df_search_terms is None or 'keyword' not in df_search_terms.columns: # Check for keyword column
        print("Warning: 'keyword' column missing in df_search_terms for cost savings estimation.")
        return 0

    keywords_to_pause_identifiers = [k['keyword'] for k in state['keyword_changes'] if k['action'] == 'pause']
    paused_spend = df_search_terms[df_search_terms['keyword'].isin(keywords_to_pause_identifiers)]['spend'].sum()
    
    bid_change_impact_savings = 0
    for change in state['bid_changes']:
        keyword_identifier = change['keyword'] # This is the biddable keyword
        if change['change_percentage'] < 0:  # Only count decreases as savings
            change_pct = change['change_percentage'] / 100
            # Match using the 'keyword' (biddable keyword) column
            keyword_spend_series = df_search_terms[df_search_terms['keyword'] == keyword_identifier]['spend']
            keyword_spend = keyword_spend_series.sum() if not keyword_spend_series.empty else 0
            bid_change_impact_savings += keyword_spend * abs(change_pct)
    
    return paused_spend + bid_change_impact_savings


def estimate_efficiency_improvement(state: PPCState) -> float:
    """Estimate the efficiency improvement percentage"""
    df_search_terms = state['df_search_terms']
    
    if df_search_terms is None or 'acos' not in df_search_terms.columns or df_search_terms['acos'].isna().all():
        return 0
    
    # Calculate current average ACOS, handling potential NaNs and infinities
    valid_acos = df_search_terms['acos'][np.isfinite(df_search_terms['acos'])]
    current_avg_acos = valid_acos.mean() if not valid_acos.empty else 0
    
    acos_reduction = estimate_acos_impact(state)
    
    if current_avg_acos == 0:
        # If current ACOS is 0, any reduction is technically infinite improvement if reduction is positive.
        # Or 0 if no reduction. For simplicity, return a large number or handle as per business logic.
        return 100.0 if acos_reduction > 0 else 0 # Placeholder for significant improvement
    
    return (acos_reduction / current_avg_acos) * 100


def generate_ai_recommendations(state: PPCState) -> List[str]:
    """Generate AI-powered recommendations based on the data"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("OPENAI_API_KEY not found. Skipping AI recommendations.")
            return ["OpenAI API key not configured. AI recommendations unavailable."]

        llm = ChatOpenAI(model="gpt-4o", temperature=0.2, api_key=api_key) # Slightly increased temperature for more nuanced recommendations
        
        df_search_terms = state['df_search_terms']
        client_config = state['client_config']
        keyword_changes = state['keyword_changes']
        bid_changes = state['bid_changes']
        summary = state.get('optimization_summary', {})
        estimated_impact = summary.get('estimated_impact', {})

        if df_search_terms is None or df_search_terms.empty or 'keyword' not in df_search_terms.columns:
            print("Warning: df_search_terms is empty or 'keyword' column missing for AI recommendations.")
            return ["Insufficient data for AI recommendations (missing keywords or search terms data)."]

        # Enhanced Statistics Extraction
        paused_keywords_details = []
        for kc in keyword_changes:
            if kc['action'] == 'pause':
                reason = kc['reason']
                kw = kc['keyword']
                orig_data = kc.get('original_data', {})
                acos = orig_data.get('acos', 'N/A')
                clicks = orig_data.get('clicks', 'N/A')
                paused_keywords_details.append(f"- '{kw}' (ACOS: {acos if acos != 'N/A' else 'N/A'}%, Clicks: {clicks}) due to: {reason}")

        bids_increased_count = summary.get('bids_to_increase', 0)
        bids_decreased_count = summary.get('bids_to_decrease', 0)
        avg_bid_increase_pct = summary.get('avg_bid_increase', 0)
        avg_bid_decrease_pct = summary.get('avg_bid_decrease', 0)

        significant_bid_changes_details = []
        # Get top 2-3 examples of significant bid changes (abs percentage)
        sorted_bids = sorted(bid_changes, key=lambda x: abs(x.get('change_percentage', 0)), reverse=True)
        for bc in sorted_bids[:3]:
            kw = bc['keyword']
            change_pct = bc.get('change_percentage', 0)
            new_bid = bc.get('new_bid', 'N/A')
            reason = bc.get('reason', 'N/A')
            direction = "increased" if change_pct > 0 else "decreased"
            significant_bid_changes_details.append(f"- Bid for '{kw}' {direction} by {change_pct:.1f}% to ${new_bid:.2f} because: {reason}")
            
        top_performing_keywords_df = df_search_terms[df_search_terms['keyword'].notna() & df_search_terms['acos'].notna()].sort_values('acos')
        top_performing_keywords = top_performing_keywords_df['keyword'].head(3).tolist()
        
        worst_performing_keywords_df = df_search_terms[
            (df_search_terms['keyword'].notna()) & 
            (df_search_terms['clicks'] > 10) & 
            (df_search_terms['acos'].notna())
        ].sort_values('acos', ascending=False)
        worst_performing_keywords_for_review = worst_performing_keywords_df['keyword'].head(3).tolist()


        context = f"""
        **Client Configuration:**
        - Market Leader: {client_config.get('is_market_leader', False)}
        - Large Inventory: {client_config.get('has_large_inventory', False)}
        - Target ACOS: {client_config.get('target_acos', 20.0)}%

        **Automated Optimization Summary:**
        - Total Keywords Analyzed: {summary.get('total_keywords_analyzed', len(df_search_terms))}
        - Keywords Paused: {summary.get('keywords_to_pause', 0)}
        - Keywords Kept: {summary.get('keywords_to_keep', 0)}
        - Total Bids Adjusted: {summary.get('bids_to_adjust', 0)}
          - Bids Increased: {bids_increased_count} (Average: {avg_bid_increase_pct:.1f}%)
          - Bids Decreased: {bids_decreased_count} (Average: {avg_bid_decrease_pct:.1f}%)
        - Estimated ACOS Reduction: {estimated_impact.get('projected_acos_reduction', 0):.2f}%
        - Estimated Cost Savings: ${estimated_impact.get('cost_saving', 0):.2f}

        **Specific Examples of Automated Changes:**
        Keywords Paused (Examples):
        {'\n'.join(paused_keywords_details[:3]) if paused_keywords_details else '  N/A - No keywords were paused or details unavailable.'}

        Significant Bid Adjustments (Examples):
        {'\n'.join(significant_bid_changes_details) if significant_bid_changes_details else '  N/A - No significant bid changes to highlight or details unavailable.'}

        **Current Top Performing Keywords (Low ACOS, Biddable):**
        {', '.join(top_performing_keywords) if top_performing_keywords else 'N/A'}

        **Current Worst Performing Keywords for Review (High ACOS, >10 Clicks, Biddable):**
        {', '.join(worst_performing_keywords_for_review) if worst_performing_keywords_for_review else 'N/A'}
        """
        
        prompt = f"""
        You are an expert Amazon PPC Optimization Strategist.
        The system has just performed an automated analysis and applied the following changes and estimates to a client's PPC campaign data:

        {context}

        Based *specifically* on these automated changes and the provided statistics:
        1.  Provide 3-5 highly specific, actionable recommendations that build upon the automated changes.
        2.  Explain the likely positive impacts of the automated changes that were made (e.g., pausing unprofitable keywords, adjusting bids towards target ACOS).
        3.  Suggest concrete next steps for the user to manually review or further optimize. These should go beyond the automated changes. For example, if keywords were paused, what should the user investigate about them? If bids were adjusted, what should be monitored?
        4.  If there are 'Worst Performing Keywords for Review', suggest specific actions for them (e.g., check search term reports for negative keywords, analyze landing page relevance, consider reducing bid further if already adjusted, or pausing if performance doesn't improve).
        5.  If there are 'Top Performing Keywords', how can the user leverage them further (e.g., budget allocation, campaign scaling, protecting top positions)?

        Recommendations should be strategic, data-driven, and directly related to the information provided. 
        Focus on practical advice the user can implement.
        Present the output as a bulleted list. Do not include a generic introduction or conclusion.
        """
        
        messages = [
            SystemMessage(content="You are an Amazon PPC optimization expert assistant, providing highly specific and data-driven recommendations based on automated changes."),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        recommendations = response.content.strip().split('\n')
        # Further clean up each recommendation, removing potential leading list characters if LLM adds them redundantly
        recommendations = [r.strip().lstrip('•-* ').strip() for r in recommendations if r.strip()] 
        
        return recommendations
        
    except Exception as e:
        print(f"Error generating AI recommendations: {str(e)}")
        st.code(traceback.format_exc()) # Show full traceback in Streamlit for easier debugging
        return [
            "An error occurred while generating AI recommendations.",
            "Please check the application logs for more details.",
            "Default advice: Review keywords with high ACOS and low conversions for potential pausing or bid reduction.",
            "Monitor keywords with recent bid changes closely for performance shifts."
        ]


def create_optimization_workflow():
    """
    Create a LangGraph workflow for the Amazon PPC optimization process
    """
    # Initialize the graph
    workflow = StateGraph(PPCState)
    
    # Add nodes
    workflow.add_node("analyze_keywords", analyze_keywords)
    workflow.add_node("adjust_bids", adjust_bids)
    workflow.add_node("generate_summary", generate_optimization_summary)
    
    # Add edges
    workflow.add_edge("analyze_keywords", "adjust_bids")
    workflow.add_edge("adjust_bids", "generate_summary")
    workflow.add_edge("generate_summary", END)
    
    # Set the entry point using the older API method
    workflow.set_entry_point("analyze_keywords")
    
    # Compile the graph
    return workflow.compile()


def apply_optimization_rules(df_campaign, df_search_terms, client_config):
    """
    Apply optimization rules to the campaign data using LangGraph workflow
    
    Args:
        df_campaign (pd.DataFrame): Campaign data
        df_search_terms (pd.DataFrame): Search terms data
        client_config (dict): Client configuration settings
        
    Returns:
        dict: Optimization results including changes and metrics
    """
    # Create initial state
    initial_state = {
        "df_campaign": df_campaign,
        "df_search_terms": df_search_terms,
        "client_config": client_config,
        "bid_changes": [],
        "keyword_changes": [],
        "optimization_summary": {},
        "current_step": "start",
        "debug_info": []
    }
    
    # Create and run the workflow
    workflow = create_optimization_workflow()
    final_state = workflow.invoke(initial_state)
    
    # Get the results
    return {
        "keyword_changes": final_state["keyword_changes"],
        "bid_changes": final_state["bid_changes"],
        "summary": final_state["optimization_summary"],
        "debug_info": final_state["debug_info"]
    } 