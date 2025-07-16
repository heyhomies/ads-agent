import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any

def render_dashboard(optimization_results: Dict[str, Any]):
    """
    Render the dashboard showing optimization results
    
    Args:
        optimization_results (dict): The optimization results from LangGraph workflow
    """
    st.title("Optimierungsergebnisse")
    
    # Extract data from results
    keyword_changes = optimization_results.get("keyword_changes", [])
    bid_changes = optimization_results.get("bid_changes", [])
    summary = optimization_results.get("summary", {})
    
    # Create metrics row - Updated to show Bids Increased/Decreased
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Analysierte Keywords", 
            f"{summary.get('total_keywords_analyzed', 0)}"
        )
    
    with col2:
        st.metric(
            "Zu pausierende Keywords",
            f"{summary.get('keywords_to_pause', 0)}",
            delta=f"{summary.get('keywords_to_pause', 0)}", 
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            "Erhöhte Gebote",
            f"{summary.get('bids_to_increase', 0)}",
             delta=f"{summary.get('avg_bid_increase', 0):.1f}% Ø", 
             delta_color="normal"
        )
    
    with col4:
        st.metric(
            "Gesenkte Gebote",
            f"{summary.get('bids_to_decrease', 0)}",
            delta=f"{summary.get('avg_bid_decrease', 0):.1f}% Ø", 
            delta_color="inverse"
        )
    
    # Create tabs for different views
    tab_kw, tab_bid, tab_placement = st.tabs([
        "Keyword-Änderungen", 
        "Gebotsanpassungen",
        "Platzierungs­anpassungen"
    ])
    
    with tab_kw:
        render_keyword_changes_tab(optimization_results.get('keyword_performance', []))
    
    with tab_bid:
        render_bid_changes_tab(bid_changes)
    
    with tab_placement:
        render_placement_adjustments_tab(optimization_results.get('placement_adjustments', []))

    # KI-Empfehlungen Tab entfernt


def render_overview_tab(optimization_results: Dict[str, Any]):
    """Render the overview tab with summary charts"""
    summary = optimization_results.get("summary", {})
    estimated_impact = summary.get('estimated_impact', {})
    
    st.subheader("Performance Impact Overview")
    
    # Display Est. ACOS Reduction and Cost Savings more prominently here
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric(
            "Est. ACOS Reduction",
            f"{estimated_impact.get('projected_acos_reduction', 0):.2f}%",
            delta_color="off" # No delta needed as value is the change
        )
    with col_b:
        st.metric(
            "Est. Cost Savings",
            f"${estimated_impact.get('cost_saving', 0):.2f}",
            delta_color="off"
        )
    with col_c:
        st.metric(
            "Efficiency Improvement",
            f"{estimated_impact.get('efficiency_improvement', 0):.2f}%",
            delta_color="off"
        )
    st.markdown("---")

    # Create columns for charts
    col1, col2 = st.columns(2)
    
    # Keyword actions pie chart
    with col1:
        keyword_data = {
            'Action': ['Pause', 'Keep'],
            'Count': [
                summary.get('keywords_to_pause', 0),
                summary.get('keywords_to_keep', 0)
            ]
        }
        df_keyword_pie = pd.DataFrame(keyword_data)
        
        if df_keyword_pie['Count'].sum() > 0:
            fig_keyword_pie = px.pie(
                df_keyword_pie, 
                values='Count', 
                names='Action',
                title='Keyword Actions Breakdown',
                color='Action',
                color_discrete_map={'Pause': '#FF4B4B', 'Keep': '#36A2EB'}
            )
            st.plotly_chart(fig_keyword_pie, use_container_width=True)
        else:
            st.info("No keyword action data available for chart.")
    
    # Bid adjustments pie chart
    with col2:
        bid_data = {
            'Action': ['Increase', 'Decrease', 'No Change'], # Added No Change
            'Count': [
                summary.get('bids_to_increase', 0),
                summary.get('bids_to_decrease', 0),
                summary.get('total_keywords_analyzed', 0) - 
                (summary.get('bids_to_increase', 0) + summary.get('bids_to_decrease', 0)) # Calculate no change
            ]
        }
        df_bid_pie = pd.DataFrame(bid_data)
        df_bid_pie = df_bid_pie[df_bid_pie['Count'] >= 0] # Ensure no negative counts
        
        if df_bid_pie['Count'].sum() > 0:
            fig_bid_pie = px.pie(
                df_bid_pie, 
                values='Count', 
                names='Action',
                title='Bid Adjustments Breakdown',
                color='Action',
                color_discrete_map={'Increase': '#4BC0C0', 'Decrease': '#FFCD56', 'No Change': '#D3D3D3'}
            )
            st.plotly_chart(fig_bid_pie, use_container_width=True)
        else:
            st.info("No bid adjustment data available for chart.")
    
    st.markdown("---")
    # Gauge chart for ACOS reduction can remain if desired, or be removed if redundant with metric above
    projected_acos_reduction = estimated_impact.get('projected_acos_reduction', 0)
    if projected_acos_reduction is not None:
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = projected_acos_reduction,
            title = {'text': "Projected ACOS Reduction (%)"},
            gauge = {
                'axis': {'range': [None, max(20, projected_acos_reduction + 5)]}, # Dynamic range
                'bar': {'color': "#1f77b4"},
                'steps': [
                    {'range': [0, 5], 'color': "lightgreen"},
                    {'range': [5, 10], 'color': "lightyellow"},
                    # {'range': [10, 20], 'color': "lightcoral"} # Removed fixed upper step
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': summary.get('target_acos', 20) # Show target ACOS if available
                }
            }
        ))
        st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.info("Projected ACOS reduction data not available for gauge chart.")


def render_keyword_changes_tab(keyword_perf):
    """Zeigt gut und schlecht laufende Keywords je Kampagne an (keine Gebotsratschläge)"""
    import pandas as pd
    st.subheader("Keyword-Leistung")

    # Get current configuration values
    client_config = st.session_state.get('client_config', {})
    target_acos = client_config.get('target_acos', 20.0)
    min_conversion_rate = client_config.get('min_conversion_rate', 10.0)
    
    st.info(f"📊 **Aktuelle Filter:** Target ACOS ≤ {target_acos}% UND Conversion Rate ≥ {min_conversion_rate}% = 'gut'")
    
    if not keyword_perf:
        st.info("Keine Keyword-Daten verfügbar")
        return
    
    # Re-classify keywords based on current configuration
    if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
        from app.utils.keyword_classifier import classify_keywords
        # Re-run classification with current config values
        target_acos_decimal = target_acos / 100  # Convert to decimal for classifier
        min_conversion_rate_decimal = min_conversion_rate / 100  # Convert to decimal for classifier
        keyword_perf = classify_keywords(st.session_state.df_campaign, target_acos_decimal, min_conversion_rate_decimal)
    
    if not keyword_perf:
        st.info("Keine Keyword-Daten verfügbar")
        return
    
    df_kw = pd.DataFrame(keyword_perf)

    for campaign_id, grp in df_kw.groupby('campaign_id'):
        # Get campaign info from campaign data if available
        campaign_name = "N/A"
        targeting_type = "N/A"
        
        if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
            df_campaign = st.session_state.df_campaign
            # Find campaign info for this campaign ID
            campaign_rows = df_campaign[df_campaign['kampagnen-id'] == campaign_id]
            if not campaign_rows.empty:
                first_row = campaign_rows.iloc[0]
                # Get campaign name
                if 'campaign_name' in first_row:
                    campaign_name = first_row['campaign_name']
                
                # Get targeting type
                if 'targeting-typ' in first_row:
                    targeting_type = first_row['targeting-typ']
        
        st.markdown(f"### Kampagne **{campaign_id}**")
        st.markdown(f"**Name:** {campaign_name} | **Targeting:** {targeting_type}")

        good = grp[grp['status'] == 'gut']
        bad = grp[grp['status'] == 'schlecht']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Gut laufende Keywords")
            if good.empty:
                st.info("Keine")
            else:
                # Include match_type, orders, and conversion_rate if available
                cols_to_show = ['keyword', 'clicks', 'spend', 'sales', 'acos', 'reason']
                if 'match_type' in good.columns:
                    cols_to_show.insert(1, 'match_type')
                if 'orders' in good.columns:
                    cols_to_show.insert(-3, 'orders')  # Insert after clicks, before spend
                if 'conversion_rate' in good.columns:
                    cols_to_show.insert(-1, 'conversion_rate')  # Insert before reason
                df_good = good[cols_to_show].copy()
                
                rename_dict = {
                    'keyword': 'Keyword',
                    'clicks': 'Klicks',
                    'orders': 'Bestellungen',
                    'spend': 'Ausgaben',
                    'sales': 'Verkäufe',
                    'acos': 'ACOS %',
                    'conversion_rate': 'CR %',
                    'reason': 'Grund'
                }
                if 'match_type' in df_good.columns:
                    rename_dict['match_type'] = 'Übereinstimmungstyp'
                df_good = df_good.rename(columns=rename_dict)
                # Format ACOS and CR as Prozentwert (convert from decimal)
                if 'ACOS %' in df_good.columns:
                    df_good['ACOS %'] = df_good['ACOS %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                if 'CR %' in df_good.columns:
                    df_good['CR %'] = df_good['CR %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                st.dataframe(df_good, use_container_width=True)
        
        with col2:
            st.subheader("Schlecht laufende Keywords")
            if bad.empty:
                st.info("Keine")
            else:
                # Include match_type, orders, and conversion_rate if available
                cols_to_show = ['keyword', 'clicks', 'spend', 'sales', 'acos', 'reason']
                if 'match_type' in bad.columns:
                    cols_to_show.insert(1, 'match_type')
                if 'orders' in bad.columns:
                    cols_to_show.insert(-3, 'orders')  # Insert after clicks, before spend
                if 'conversion_rate' in bad.columns:
                    cols_to_show.insert(-1, 'conversion_rate')  # Insert before reason
                df_bad = bad[cols_to_show].copy()
                
                rename_dict = {
                    'keyword': 'Keyword',
                    'clicks': 'Klicks',
                    'orders': 'Bestellungen',
                    'spend': 'Ausgaben',
                    'sales': 'Verkäufe',
                    'acos': 'ACOS %',
                    'conversion_rate': 'CR %',
                    'reason': 'Grund'
                }
                if 'match_type' in df_bad.columns:
                    rename_dict['match_type'] = 'Übereinstimmungstyp'
                df_bad = df_bad.rename(columns=rename_dict)
                # Format ACOS and CR as Prozentwert (convert from decimal)
                if 'ACOS %' in df_bad.columns:
                    df_bad['ACOS %'] = df_bad['ACOS %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                if 'CR %' in df_bad.columns:
                    df_bad['CR %'] = df_bad['CR %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                st.dataframe(df_bad, use_container_width=True)


def render_bid_changes_tab(bid_changes):
    """Render the bid changes tab with detailed tables"""
    # Abschnitt Gebotsänderungen entfernt; es werden nur noch Suchbegriff-Analysen angezeigt.

    # ---------------------- Suchbegriff-Analyse ----------------------
    if 'df_search_terms' in st.session_state and st.session_state.df_search_terms is not None:
        df_st = st.session_state.df_search_terms.copy()
        if 'kampagnen-id' in df_st.columns and ('customer_search_term' in df_st.columns or 'suchbegriff_eines_kunden' in df_st.columns):
            # Normalisiere Spaltenname
            if 'customer_search_term' not in df_st.columns:
                df_st['customer_search_term'] = df_st['suchbegriff_eines_kunden']

            st.markdown("---")
            st.subheader("Suchbegriff-Analyse")

            for camp_id, grp in df_st.groupby('kampagnen-id'):
                with st.container():
                    # Get campaign info from campaign data if available
                    campaign_name = "N/A"
                    targeting_type = "N/A"
                    
                    if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
                        df_campaign = st.session_state.df_campaign
                        # Find campaign info for this campaign ID
                        campaign_rows = df_campaign[df_campaign['kampagnen-id'] == camp_id]
                        if not campaign_rows.empty:
                            first_row = campaign_rows.iloc[0]
                                                         # Get campaign name
                            if 'campaign_name' in first_row:
                                campaign_name = first_row['campaign_name']
                            
                            # Get targeting type
                            if 'targeting-typ' in first_row:
                                targeting_type = first_row['targeting-typ']
                    
                    st.markdown(f"#### Kampagne **{camp_id}**")
                    st.markdown(f"**Name:** {campaign_name} | **Targeting:** {targeting_type}")

                    # ACOS als Prozent Format
                    grp['acos_pct'] = grp['acos'].apply(lambda x: round(x*100,2) if x <= 1 else round(x,2))

                    # Sortierung: gültige ACOS >0 nach Wert, ACOS==0 ans Ende
                    grp_nonzero = grp[grp['acos'] > 0]
                    grp_zero = grp[grp['acos'] == 0]

                    best15 = grp_nonzero.sort_values('acos').head(15)
                    worst15 = grp_nonzero.sort_values('acos', ascending=False).head(15)

                    col_best, col_worst = st.columns(2)
                    with col_best:
                        st.markdown("**Beste 15 Suchbegriffe** (niedrigster ACOS)")
                        cols_best = ['customer_search_term','clicks','spend','sales','acos_pct']
                        if 'match_type' in best15.columns:
                            cols_best.insert(1, 'match_type')
                        if 'orders' in best15.columns:
                            cols_best.insert(-2, 'orders')  # Insert after clicks, before spend
                        if 'conversion_rate' in best15.columns:
                            cols_best.insert(-1, 'conversion_rate')
                        df_best_disp = best15[cols_best].rename(columns={
                            'customer_search_term':'Suchbegriff',
                            'match_type':'Übereinstimmungstyp',
                            'clicks':'Klicks',
                            'orders':'Bestellungen',
                            'spend':'Ausgaben',
                            'sales':'Verkäufe',
                            'conversion_rate':'CR %',
                            'acos_pct':'ACOS %'
                        })
                        if 'CR %' in df_best_disp.columns:
                            df_best_disp['CR %'] = df_best_disp['CR %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                        st.dataframe(df_best_disp, use_container_width=True)

                    with col_worst:
                        st.markdown("**Schlechteste 15 Suchbegriffe** (höchster ACOS)")
                        cols_worst = ['customer_search_term','clicks','spend','sales','acos_pct']
                        if 'match_type' in worst15.columns:
                            cols_worst.insert(1, 'match_type')
                        if 'orders' in worst15.columns:
                            cols_worst.insert(-2, 'orders')  # Insert after clicks, before spend
                        if 'conversion_rate' in worst15.columns:
                            cols_worst.insert(-1, 'conversion_rate')
                        df_worst_disp = worst15[cols_worst].rename(columns={
                            'customer_search_term':'Suchbegriff',
                            'match_type':'Übereinstimmungstyp',
                            'clicks':'Klicks',
                            'orders':'Bestellungen',
                            'spend':'Ausgaben',
                            'sales':'Verkäufe',
                            'conversion_rate':'CR %',
                            'acos_pct':'ACOS %'
        })
                        if 'CR %' in df_worst_disp.columns:
                            df_worst_disp['CR %'] = df_worst_disp['CR %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                        st.dataframe(df_worst_disp, use_container_width=True)

                    with st.expander("Alle Suchbegriffe"):
                        # kombiniere, sortiere: erst nonzero nach ACOS aufsteigend, dann zero
                        full_sorted = pd.concat([
                            grp_nonzero.sort_values('acos'),
                            grp_zero
                        ])
                        cols_full = ['customer_search_term','clicks','spend','sales','acos_pct']
                        if 'match_type' in full_sorted.columns:
                            cols_full.insert(1, 'match_type')
                        if 'orders' in full_sorted.columns:
                            cols_full.insert(-2, 'orders')  # Insert after clicks, before spend
                        if 'conversion_rate' in full_sorted.columns:
                            cols_full.insert(-1, 'conversion_rate')
                        full_disp = full_sorted[cols_full].rename(columns={
                            'customer_search_term':'Suchbegriff',
                            'match_type':'Übereinstimmungstyp',
                            'clicks':'Klicks',
                            'orders':'Bestellungen',
                            'spend':'Ausgaben',
                            'sales':'Verkäufe',
                            'conversion_rate':'CR %',
                            'acos_pct':'ACOS %'
                        })
                        if 'CR %' in full_disp.columns:
                            full_disp['CR %'] = full_disp['CR %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                        st.dataframe(full_disp, use_container_width=True)


def render_placement_adjustments_tab(initial_adjustments):
    """Render placement bid adjustment recommendations per campaign with interactive target ACOS slider"""
    import streamlit as st  # ensure local import for type checker
    from app.utils.placement_adjuster import compute_placement_adjustments

    st.subheader("Placement Bid Adjustments")

    # Determine default target ACOS from configuration or 20 %
    default_target = st.session_state.get('client_config', {}).get('target_acos', 20.0)

    target_acos_pct = st.slider(
        "Target ACOS (%)",
        min_value=5.0,
        max_value=50.0,
        value=float(default_target),
        step=0.5,
        key="placement_target_acos_slider",
        help="Adjust the target ACOS to see updated placement recommendations"
    )

    # Recompute recommendations based on slider value
    if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
        df_campaign = st.session_state.df_campaign
        placement_adjustments = compute_placement_adjustments(df_campaign, target_acos=target_acos_pct / 100)
    else:
        placement_adjustments = initial_adjustments or []

    if not placement_adjustments:
        st.info("No placement adjustment data available")
        return

    df_placement = pd.DataFrame(placement_adjustments)

    # Separate totals for metrics display
    for campaign_id, grp in df_placement.groupby('campaign_id'):
        with st.container():
            st.markdown(f"### Kampagne **{campaign_id}**")

            total_row = grp[grp['is_total'] == True].iloc[0] if not grp[grp['is_total'] == True].empty else None

            # Check if this is a zero sales campaign and show warning
            if total_row is not None and total_row.get('is_zero_sales', False):
                st.warning("⚠️ **Hinweis**: Diese Kampagne hat 0€ Umsatz. Der Basis-CPC wurde auf das Mindestgebot von 0,01€ gesetzt.")

            # Display comprehensive metrics using HTML cards
            if total_row is not None and 'total_rpc' in total_row:
                    # Kartenlayout mit HTML
                    metrics = [
                        ("Klicks", f"{int(total_row['clicks'])}"),
                        ("Ausgaben", f"€{total_row['spend']:.2f}"),
                        ("Verkäufe", f"€{total_row['sales']:.2f}"),
                        ("ACOS", f"{total_row['current_acos']}%"),
                        ("RPC gesamt", f"{total_row['total_rpc']:.4f}"),
                        ("Ziel-CPC", f"€{total_row['target_cpc']:.2f}"),
                        ("Basis-CPC", f"€{total_row['base_cpc_total']:.2f}"),
                        ("Niedrigster RPC", f"{total_row['min_rpc_total']:.4f}")
                    ]
                    card_html = "<div style='display:flex;flex-wrap:wrap;'>"
                    for label, val in metrics:
                        card_html += f"<div style='flex:1 0 200px;background:#f7f7f7;margin:6px;padding:12px;border-radius:8px;text-align:center'>"
                        card_html += f"<div style='font-size:14px;font-weight:600'>{label}</div>"
                        card_html += f"<div style='font-size:20px;font-weight:700'>{val}</div>"
                        card_html += "</div>"
                    card_html += "</div>"
                    st.markdown(card_html, unsafe_allow_html=True)

            # Data table without the helper flag column
            display_cols = [
                'placement',
                'clicks',
                'spend',
                'sales',
                'current_adjust_pct',
                'recommended_adjust_pct',
                'current_acos',
                'cpc',
                'rpc',
                'min_rpc',
                'base_cpc'
            ]
            display_cols = [c for c in display_cols if c in grp.columns]

            df_display = grp[grp['is_total'] == False][display_cols].copy()
            rename_map = {
                'placement': 'Platzierung',
                'clicks': 'Klicks',
                'spend': 'Ausgaben',
                'sales': 'Verkäufe',
                'current_adjust_pct': 'Akt. Anpassung %',
                'recommended_adjust_pct': 'Empf. Anpassung %',
                'current_acos': 'ACOS %',
                'cpc': 'CPC',
                'rpc': 'RPC',
                'min_rpc': 'Min. RPC',
                'base_cpc': 'Basis CPC'
            }
            df_display = df_display.rename(columns={k: v for k, v in rename_map.items() if k in df_display.columns})
            st.dataframe(df_display, use_container_width=True)


def render_recommendations_tab(recommendations):
    """Render the AI recommendations tab"""
    st.subheader("AI-Powered Recommendations")
    
    if not recommendations:
        st.info("No AI recommendations available")
        return
    
    for i, rec in enumerate(recommendations, 1):
        st.markdown(f"**{i}. {rec}**")
    
    # Add explanation
    st.markdown("---")
    st.markdown("""
    **About these recommendations:**
    
    These AI-powered recommendations are generated based on analysis of your campaign data and the optimization changes. 
    They are meant to complement the automated changes with strategic insights to further improve your PPC performance.
    """) 