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
    
    # Create tabs for different views
    tab_kw, tab_bid, tab_placement, tab_products, tab_export = st.tabs([
        "Keyword-Änderungen", 
        "Suchbegriff-Analyse",
        "Platzierungs­anpassungen",
        "Produkte",
        "Export"
    ])
    
    with tab_kw:
        render_keyword_changes_tab(optimization_results.get('keyword_performance', []))
    
    with tab_bid:
        render_bid_changes_tab(bid_changes)
    
    with tab_placement:
        render_placement_adjustments_tab(optimization_results.get('placement_adjustments', []))
    
    with tab_products:
        render_products_tab()
    
    with tab_export:
        render_export_tab(optimization_results)

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
    """Zeigt Keywords in sinnvollen Kategorien basierend auf Performance und Handlungsbedarf"""
    import pandas as pd
    st.subheader("Keyword-Analyse")

    # Get current configuration values
    client_config = st.session_state.get('client_config', {})
    keyword_acos = client_config.get('keyword_acos', 20.0)
    max_keyword_clicks = client_config.get('max_keyword_clicks', 50)
    
    st.info(f"📊 **Analyse-Kriterien:** ACOS-Limit {keyword_acos}% | Max. Klicks ohne Conversion: {max_keyword_clicks}")
    
    if not keyword_perf:
        st.info("Keine Keyword-Daten verfügbar")
        return
    
    # Re-classify keywords based on current configuration
    if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
        from app.utils.keyword_classifier import classify_keywords
        # Re-run classification with current config values
        keyword_acos_decimal = keyword_acos / 100  # Convert to decimal for classifier
        keyword_perf = classify_keywords(st.session_state.df_campaign, keyword_acos_decimal)
    
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
        
        st.markdown(f"### 📊 Kampagne **{campaign_id}**")
        st.markdown(f"**Name:** {campaign_name} | **Targeting:** {targeting_type}")

        # Simplified keyword categorization into 3 meaningful groups
        def categorize_keyword(row):
            clicks = row.get('clicks', 0)
            orders = row.get('orders', 0)
            acos = row.get('acos', 0)
            
            # 1. Zu pausieren: Above limits (high ACOS or too many clicks without conversion)
            if acos > (keyword_acos / 100):  # Above ACOS limit
                return 'zu_pausieren'
            elif clicks >= max_keyword_clicks and orders == 0:  # Too many clicks without conversion
                return 'zu_pausieren'
            
            # 2. Zu wenig Daten: Below conversion limit but no sales yet
            elif orders == 0:  # No conversions yet, but within limits
                return 'zu_wenig_daten'
            
            # 3. Bleibende Keywords: Within bounds with conversions (will be sorted by ACOS)
            else:
                return 'bleibende_keywords'

        grp = grp.copy()
        grp['category'] = grp.apply(categorize_keyword, axis=1)
        
        # Create expandable sections for the 3 main categories
        categories = [
            ('zu_pausieren', '⏸️ Zu pausierende Keywords'),
            ('zu_wenig_daten', '📊 Zu wenig Daten'),
            ('bleibende_keywords', '✅ Aktive Keywords')
        ]
        
        for cat_key, cat_name in categories:
            cat_data = grp[grp['category'] == cat_key]
            if not cat_data.empty:
                with st.expander(f"{cat_name} ({len(cat_data)} Keywords)"):
                    # Show explanation for each category
                    if cat_key == 'zu_pausieren':
                        st.markdown(f"⚠️ **Keywords über den Limits:** ACOS >{keyword_acos:.1f}% oder ≥{max_keyword_clicks} Klicks ohne Conversion")
                    elif cat_key == 'zu_wenig_daten':
                        st.markdown(f"📊 **Noch keine Conversions:** Keywords innerhalb der Limits aber noch ohne Bestellungen")
                    elif cat_key == 'bleibende_keywords':
                        st.markdown(f"✅ **Aktive Keywords mit Conversions:** Innerhalb der Limits (ACOS ≤{keyword_acos:.1f}%) und bereits mit Bestellungen - sortiert nach ACOS")
                    
                    # Sort "Aktive Keywords" by ACOS (ascending - best first)
                    if cat_key == 'bleibende_keywords':
                        cat_data = cat_data.sort_values('acos', ascending=True)
                    
                    # Prepare display data - no reason needed for active keywords
                    if cat_key == 'bleibende_keywords':
                        cols_to_show = ['keyword', 'clicks', 'spend', 'sales', 'acos']
                    else:
                        cols_to_show = ['keyword', 'clicks', 'spend', 'sales', 'acos', 'reason']
                    
                    if 'match_type' in cat_data.columns:
                        cols_to_show.insert(1, 'match_type')
                    if 'orders' in cat_data.columns:
                        cols_to_show.insert(-2 if cat_key == 'bleibende_keywords' else -3, 'orders')
                    if 'conversion_rate' in cat_data.columns:
                        cols_to_show.insert(-1, 'conversion_rate')
                    
                    df_display = cat_data[cols_to_show].copy()
                    
                    rename_dict = {
                        'keyword': 'Keyword',
                        'clicks': 'Klicks',
                        'orders': 'Bestellungen',
                        'spend': 'Ausgaben',
                        'sales': 'Verkäufe',
                        'acos': 'ACOS %',
                        'conversion_rate': 'CR %',
                        'match_type': 'Übereinstimmungstyp',
                        'reason': 'Grund'
                    }
                    df_display = df_display.rename(columns=rename_dict)
                    
                    # Format ACOS and CR as Prozentwert (convert from decimal)
                    if 'ACOS %' in df_display.columns:
                        df_display['ACOS %'] = df_display['ACOS %'].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) and x <= 1 else f"{x:.1f}%" if pd.notna(x) else "N/A")
                    if 'CR %' in df_display.columns:
                        df_display['CR %'] = df_display['CR %'].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) and x <= 1 else f"{x:.1f}%" if pd.notna(x) else "N/A")
                    
                    # Monetary columns
                    if 'Ausgaben' in df_display.columns:
                        df_display['Ausgaben'] = df_display['Ausgaben'].apply(lambda x: f"€{x:.2f}" if pd.notna(x) else "€0.00")
                    if 'Verkäufe' in df_display.columns:
                        df_display['Verkäufe'] = df_display['Verkäufe'].apply(lambda x: f"€{x:.2f}" if pd.notna(x) else "€0.00")
                    
                    st.dataframe(df_display, use_container_width=True)


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
                        if 'hypothetical_acos_note' in full_sorted.columns:
                            cols_full.append('hypothetical_acos_note')
                        full_disp = full_sorted[cols_full].rename(columns={
                            'customer_search_term':'Suchbegriff',
                            'match_type':'Übereinstimmungstyp',
                            'clicks':'Klicks',
                            'orders':'Bestellungen',
                            'spend':'Ausgaben',
                            'sales':'Verkäufe',
                            'conversion_rate':'CR %',
                            'acos_pct':'ACOS %',
                            'hypothetical_acos_note':'Hypothetischer ACOS'
                        })
                        if 'CR %' in full_disp.columns:
                            full_disp['CR %'] = full_disp['CR %'].apply(lambda x: round(x*100,2) if not pd.isna(x) else pd.NA)
                        
                        # Highlight rows with hypothetical ACOS
                        if 'Hypothetischer ACOS' in full_disp.columns:
                            # Show info about hypothetical ACOS calculations
                            hyp_acos_count = full_disp['Hypothetischer ACOS'].str.contains('Hypothetischer ACOS', na=False).sum()
                            if hyp_acos_count > 0:
                                st.info(f"ℹ️ {hyp_acos_count} Suchbegriffe verwenden hypothetischen ACOS (0 Verkäufe, Preis aus Datenbank)")
                        
                        st.dataframe(full_disp, use_container_width=True)


def render_placement_adjustments_tab(initial_adjustments):
    """Render placement bid adjustment recommendations per campaign using configured target ACOS"""
    import streamlit as st  # ensure local import for type checker
    from app.utils.placement_adjuster import compute_placement_adjustments

    st.subheader("Gebotsanpassungen")

    # Get target ACOS from unified configuration
    client_config = st.session_state.get('client_config', {})
    target_acos_pct = client_config.get('target_acos_placement', 20.0)
    
    # Display current target ACOS setting
    st.info(f"📊 **Aktuelle Konfiguration:** Ziel-ACOS: {target_acos_pct}% (konfigurierbar unter 'Konfiguration')")

    # Recompute recommendations based on configuration value
    if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
        df_campaign = st.session_state.df_campaign
        placement_adjustments = compute_placement_adjustments(
            df_campaign, 
            target_acos=target_acos_pct / 100,
            df_campaign_full=df_campaign  # Pass full dataframe for Base CPC lookup
        )
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

            # *** CHECK FOR SPECIAL RULE AND DISPLAY INFORMATION ***
            special_rule_applied = grp['special_rule'].eq('low_top_clicks').any() if 'special_rule' in grp.columns else False
            
            if special_rule_applied:
                # Get special rule details from the group
                top_placement_row = grp[grp['placement'].str.contains('Top', case=False, na=False)]
                if not top_placement_row.empty:
                    # Get the details from the top placement row
                    special_row = top_placement_row.iloc[0]
                    current_pct = special_row.get('current_adjust_pct', 0)
                    recommended_pct = special_row.get('recommended_adjust_pct', 0)
                    bid_capped = special_row.get('bid_capped', False)
                    new_max_bid = special_row.get('new_max_bid', 0)
                    actual_increase = special_row.get('actual_increase', 0)
                    
                    # Get base CPC info
                    base_cpc = special_row.get('base_cpc', 0.50)
                    
                    # Display only basic special rule information
                    st.info(f"🎯 **SPEZIALREGEL für Campaign {campaign_id}**: Top-Platzierung <20 Klicks")
                    
                    # Show Base CPC information under campaign heading
                    if base_cpc == 0.50:
                        st.warning(f"⚠️ Standardgebot-Spalte nicht gefunden - verwende Default: €{base_cpc:.2f}")
                    else:
                        st.success(f"💰 **Base CPC**: €{base_cpc:.2f} aus Anzeigengruppe")
                    
                    # Show the adjustment logic under campaign heading
                    if bid_capped:
                        if actual_increase == 0:
                            # Current percentage was already too high
                            current_max_bid = base_cpc * (1 + current_pct / 100)
                            st.warning(f"⚠️ Aktuelle Anpassung {current_pct}% ergibt bereits €{current_max_bid:.2f} - auf {recommended_pct:.0f}% reduziert für €1,50 Max-Gebot")
                            st.info(f"📋 Keine +100PP möglich - Anpassung muss auf Maximum für €1,50 begrenzt werden")
                        else:
                            # +100PP was too much - scaled down  
                            potential_max_bid = base_cpc * (1 + (current_pct + 100) / 100)
                            st.warning(f"⚠️ +100PP würde €{potential_max_bid:.2f} ergeben - skaliert auf +{actual_increase:.0f}PP für €1,50 Max-Gebot")
                    
                    # Always show the final adjustment result
                    st.success(f"📊 **Top-Platzierung**: {current_pct}% → {recommended_pct:.0f}% (+{actual_increase:.0f}PP) | €{new_max_bid:.2f}")

            total_row = grp[grp['is_total'] == True].iloc[0] if not grp[grp['is_total'] == True].empty else None

            # Check if this is a zero sales campaign and show warning (only for non-special rule campaigns)
            if not special_rule_applied and total_row is not None and total_row.get('is_zero_sales', False):
                st.info("ℹ️ **Hinweis**: Diese Kampagne hat 0€ Umsatz. Verkäufe wurden für Berechnungen auf 1€ gesetzt.")
            
            # Check if scaling was applied and show scaling info (only for normal campaigns)
            if not special_rule_applied and total_row is not None and total_row.get('scaling_applied', False):
                integer_multiplier = total_row.get('integer_multiplier', 1)
                st.warning(f"⚖️ **Skalierung angewendet**: Anpassungen überschritten 900%. "
                          f"Basis-CPC wurde um {integer_multiplier}x erhöht, "
                          f"Anpassungen proportional reduziert (max 900%).")

            # Display comprehensive metrics using HTML cards
            if total_row is not None and 'total_rpc' in total_row:
                    # Kartenlayout mit HTML
                    metrics = [
                        ("Klicks", f"{int(total_row['clicks'])}"),
                        ("Ausgaben", f"€{total_row['spend']:.2f}"),
                        ("Verkäufe", f"€{total_row['sales']:.2f}"),
                        ("ACOS", f"{total_row['current_acos']:.1f}%"),
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
            
            # Add scaling info if available
            if 'scaling_applied' in grp.columns and grp['scaling_applied'].any():
                display_cols.append('integer_multiplier')
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
                'base_cpc': 'Basis CPC',
                'integer_multiplier': 'CPC Multiplikator'
            }
            df_display = df_display.rename(columns={k: v for k, v in rename_map.items() if k in df_display.columns})
            
            # Format ACOS as percentage (already calculated as percentage in placement_adjuster)
            if 'ACOS %' in df_display.columns:
                df_display['ACOS %'] = df_display['ACOS %'].apply(
                    lambda x: f"{x:.1f}%" if pd.notna(x) else ""
                )
            
            st.dataframe(df_display, use_container_width=True)


def render_products_tab():
    """Render all products per campaign with their performance and hypothetical ACOS indicators"""
    st.subheader("Produktleistung pro Kampagne")
    
    # Get original campaign data directly - avoid enriched data which might be search terms
    df_campaign = None
    
    # Try to read the original campaign data directly from the temp file
    if 'temp_upload_filepath' in st.session_state and 'original_campaign_sheet_name' in st.session_state:
        try:
            import pandas as pd
            temp_file = st.session_state.temp_upload_filepath
            sheet_name = st.session_state.original_campaign_sheet_name
            df_campaign = pd.read_excel(temp_file, sheet_name=sheet_name)
            st.info(f"📊 Lade Kampagnendaten direkt aus '{sheet_name}' Sheet")
        except Exception as e:
            st.warning(f"⚠️ Fehler beim direkten Laden: {e}")
    
    # Fallback: Try optimization results but check if it has Entität column
    if df_campaign is None and 'optimization_results' in st.session_state:
        optimization_results = st.session_state.optimization_results
        if 'df_campaign_with_hypothetical' in optimization_results:
            potential_df = optimization_results['df_campaign_with_hypothetical']
            if 'Entität' in potential_df.columns:
                df_campaign = potential_df
                st.info("📊 Verwende angereicherte Kampagnendaten (mit Entität)")
            else:
                st.warning("⚠️ Angereicherte Daten haben keine Entität-Spalte")
    
    # Last resort: Try session state but validate it has Entität column
    if df_campaign is None and 'df_campaign' in st.session_state:
        potential_df = st.session_state.df_campaign
        if potential_df is not None and 'Entität' in potential_df.columns:
            df_campaign = potential_df
            st.info("📊 Verwende Kampagnendaten aus Session State (mit Entität)")
        else:
            st.warning("⚠️ Session State Kampagnendaten haben keine Entität-Spalte")
    
    if df_campaign is None:
        st.error("❌ Keine validen Kampagnendaten verfügbar")
        return
    
    # Check if we have the Entität column
    if 'Entität' not in df_campaign.columns:
        st.error("❌ Keine 'Entität' Spalte gefunden. Dies sind keine Kampagnendaten.")
        return
    
    # Filter for products (Produktanzeige)
    products_mask = df_campaign['Entität'].astype(str).str.lower() == 'produktanzeige'
    df_products = df_campaign[products_mask].copy()
    st.success(f"✅ 'Entität' Spalte gefunden. {len(df_products)} Produktanzeigen gefiltert.")
    
    if df_products.empty:
        st.info("Keine Produktdaten gefunden")
        return
    
    # Calculate hypothetical ACOS for products with 0 sales
    st.info("🔄 Berechne hypothetischen ACOS für Produkte ohne Verkäufe...")
    
    # Import the hypothetical ACOS calculator
    from app.utils.hypothetical_acos import HypotheticalACOSCalculator
    
    # Get product ACOS from configuration
    product_acos = st.session_state.get('client_config', {}).get('product_acos', 20.0)
    
    # Calculate hypothetical ACOS
    calculator = HypotheticalACOSCalculator()
    df_products_enriched = calculator.enrich_dataframe_with_hypothetical_acos(df_products, product_acos)
    
    st.success(f"📦 **{len(df_products_enriched)} Produkte** gefunden")
    
    # Overall summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_spend = df_products_enriched['Ausgaben'].sum() if 'Ausgaben' in df_products_enriched.columns else 0
    total_sales = df_products_enriched['Verkäufe'].sum() if 'Verkäufe' in df_products_enriched.columns else 0
    total_clicks = df_products_enriched['Klicks'].sum() if 'Klicks' in df_products_enriched.columns else 0
    
    # Count products with hypothetical ACOS
    hypothetical_count = 0
    if 'hypothetical_acos_note' in df_products_enriched.columns:
        hypothetical_count = df_products_enriched['hypothetical_acos_note'].str.contains('Hypothetischer ACOS', na=False).sum()
    
    with col1:
        st.metric("Gesamtausgaben", f"€{total_spend:.2f}")
    with col2:
        st.metric("Gesamtumsatz", f"€{total_sales:.2f}")
    with col3:
        st.metric("Gesamtklicks", f"{total_clicks}")
    with col4:
        st.metric("Hypothetischer ACOS", f"{hypothetical_count}", delta="0 Verkäufe", delta_color="off")
    
    # Group products by campaign - check if campaign ID column exists
    campaign_id_col = None
    for col in ['Kampagnen-ID', 'kampagnen-id', 'campaign_id', 'Campaign ID']:
        if col in df_products_enriched.columns:
            campaign_id_col = col
            break
    
    if campaign_id_col is None:
        st.warning("Keine Kampagnen-ID Spalte gefunden. Zeige Daten ohne Gruppierung.")
        # Show all products in one group
        campaign_groups = [('Alle Produkte', df_products_enriched)]
    else:
        campaign_groups = df_products_enriched.groupby(campaign_id_col)
    
    for campaign_id, campaign_products in campaign_groups:
        # Get campaign name
        campaign_name = "Unbekannt"
        if 'Kampagnenname' in campaign_products.columns:
            campaign_name = campaign_products['Kampagnenname'].iloc[0] if not campaign_products['Kampagnenname'].isna().all() else "Unbekannt"
        elif 'Kampagnenname (Nur zu Informationszwecken)' in campaign_products.columns:
            campaign_name = campaign_products['Kampagnenname (Nur zu Informationszwecken)'].iloc[0] if not campaign_products['Kampagnenname (Nur zu Informationszwecken)'].isna().all() else "Unbekannt"
        
        # Get targeting type
        targeting_type = "Unbekannt"
        if 'Targeting-Typ' in campaign_products.columns:
            targeting_type = campaign_products['Targeting-Typ'].iloc[0] if not campaign_products['Targeting-Typ'].isna().all() else "Unbekannt"
        
        st.subheader(f"📢 Kampagne {campaign_id}")
        st.write(f"**Name:** {campaign_name} | **Targeting:** {targeting_type}")
        
        # Campaign summary metrics - check for different possible column names
        spend_cols = ['Ausgaben', 'ausgaben', 'spend', 'Spend']
        sales_cols = ['Verkäufe', 'verkäufe', 'sales', 'Sales']
        clicks_cols = ['Klicks', 'klicks', 'clicks', 'Clicks']
        orders_cols = ['Bestellungen', 'bestellungen', 'orders', 'Orders']
        
        camp_spend = 0
        for col in spend_cols:
            if col in campaign_products.columns:
                camp_spend = campaign_products[col].sum()
                break
        
        camp_sales = 0
        for col in sales_cols:
            if col in campaign_products.columns:
                camp_sales = campaign_products[col].sum()
                break
        
        camp_clicks = 0
        for col in clicks_cols:
            if col in campaign_products.columns:
                camp_clicks = campaign_products[col].sum()
                break
        
        camp_orders = 0
        for col in orders_cols:
            if col in campaign_products.columns:
                camp_orders = campaign_products[col].sum()
                break
        
        # Calculate campaign ACOS - use actual ACOS column which now includes hypothetical values
        camp_acos = 0
        if 'ACOS' in campaign_products.columns:
            # Calculate weighted average of ACOS for products with spend
            total_spend_with_acos = 0
            weighted_acos_sum = 0
            for idx, product in campaign_products.iterrows():
                product_spend = product.get('Ausgaben', 0)
                product_acos = product.get('ACOS', 0)
                if product_spend > 0 and pd.notna(product_acos):
                    total_spend_with_acos += product_spend
                    weighted_acos_sum += product_acos * product_spend
            
            if total_spend_with_acos > 0:
                camp_acos = (weighted_acos_sum / total_spend_with_acos) * 100
        elif camp_sales > 0:
            camp_acos = (camp_spend / camp_sales * 100)
        
        # Count products with hypothetical ACOS in this campaign
        camp_hypothetical = 0
        if 'hypothetical_acos_note' in campaign_products.columns:
            camp_hypothetical = campaign_products['hypothetical_acos_note'].str.contains('Hypothetischer ACOS', na=False).sum()
        
        # Campaign metrics in columns
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Ausgaben", f"€{camp_spend:.2f}")
        with col2:
            st.metric("Umsatz", f"€{camp_sales:.2f}")
        with col3:
            st.metric("Klicks", f"{camp_clicks}")
        with col4:
            st.metric("ACOS", f"{camp_acos:.1f}%")
        with col5:
            st.metric("Hyp. ACOS", f"{camp_hypothetical}")
        
        # Prepare product table
        display_cols = ['SKU', 'Ausgaben', 'Verkäufe', 'Klicks', 'Bestellungen', 'ACOS', 'Conversion-Rate']
        
        # Add hypothetical ACOS indicator
        campaign_products_display = campaign_products.copy()
        
        # Create hypothetical ACOS indicator
        if 'hypothetical_acos_note' in campaign_products_display.columns:
            campaign_products_display['Hyp. ACOS'] = campaign_products_display['hypothetical_acos_note'].apply(
                lambda x: "✅ Ja" if pd.notna(x) and 'Hypothetischer ACOS' in str(x) else "❌ Nein"
            )
            display_cols.append('Hyp. ACOS')
        
        # Filter columns that exist
        existing_cols = [col for col in display_cols if col in campaign_products_display.columns]
        
        if existing_cols:
            df_display = campaign_products_display[existing_cols].copy()
            
            # Format ACOS column - this now includes hypothetical ACOS values
            if 'ACOS' in df_display.columns:
                df_display['ACOS'] = df_display['ACOS'].apply(
                    lambda x: f"{x*100:.1f}%" if pd.notna(x) and x <= 1 else f"{x:.1f}%" if pd.notna(x) else "0.0%"
                )
            
            # Format Conversion Rate
            if 'Conversion-Rate' in df_display.columns:
                df_display['Conversion-Rate'] = df_display['Conversion-Rate'].apply(
                    lambda x: f"{x*100:.1f}%" if pd.notna(x) and x <= 1 else f"{x:.1f}%" if pd.notna(x) else "0.0%"
                )
            
            # Format monetary columns
            if 'Ausgaben' in df_display.columns:
                df_display['Ausgaben'] = df_display['Ausgaben'].apply(
                    lambda x: f"€{x:.2f}" if pd.notna(x) else "€0.00"
                )
            
            if 'Verkäufe' in df_display.columns:
                df_display['Verkäufe'] = df_display['Verkäufe'].apply(
                    lambda x: f"€{x:.2f}" if pd.notna(x) else "€0.00"
                )
            
            st.dataframe(df_display, use_container_width=True)
        
        # Show hypothetical ACOS details if any exist
        if camp_hypothetical > 0:
            with st.expander(f"🔍 Details zu {camp_hypothetical} Produkten mit hypothetischem ACOS"):
                hyp_products = campaign_products[
                    campaign_products['hypothetical_acos_note'].str.contains('Hypothetischer ACOS', na=False)
                ]
                
                for idx, product in hyp_products.iterrows():
                    sku = product.get('SKU', 'Unbekannt')
                    note = product.get('hypothetical_acos_note', '')
                    spend = product.get('Ausgaben', 0)
                    acos_value = product.get('ACOS', 0)
                    
                    st.write(f"**{sku}** (€{spend:.2f} Ausgaben): {note}")
                    if pd.notna(acos_value):
                        st.write(f"   → **ACOS wurde ersetzt:** {acos_value*100:.1f}%")
    
    # Legend
    st.markdown("---")
    st.markdown("""
    **Legende:**
    - **ACOS**: Zeigt den tatsächlichen ACOS oder hypothetischen ACOS (bei 0 Verkäufen)
    - **Hyp. ACOS**: Zeigt an, ob für dieses Produkt ein hypothetischer ACOS berechnet wurde
    - **✅ Ja**: Hypothetischer ACOS wurde basierend auf Datenbankpreis berechnet und in ACOS-Spalte eingetragen
    - **❌ Nein**: Regulärer ACOS basierend auf tatsächlichen Verkäufen
    """)


def render_export_tab(optimization_results: Dict[str, Any]):
    """Render the Export tab with change explanations and export functionality"""
    st.subheader("📤 Export")
    
    # Get configuration values for display
    client_config = st.session_state.get('client_config', {})
    keyword_acos = client_config.get('keyword_acos', 20.0)
    product_acos = client_config.get('product_acos', 20.0)
    max_keyword_clicks = client_config.get('max_keyword_clicks', 50)
    target_acos_placement = client_config.get('target_acos_placement', 20.0)
    
    # Show current configuration values being used
    st.info(f"📊 **Aktuelle Konfiguration:** Keyword ACOS: {keyword_acos}% | Produkt ACOS: {product_acos}% | Max Klicks: {max_keyword_clicks} | Placement ACOS: {target_acos_placement}%")
    
    st.markdown("### 📋 Folgende Änderungen werden in der Excel-Datei vorgenommen:")
    
    # Show specific changes that will be made
    with st.expander("🔧 **Platzierungs-Anpassungen (Gebotsanpassungen)**", expanded=True):
        st.markdown(f"**Ziel-ACOS**: {target_acos_placement}% (aus Konfiguration)")
        st.markdown(f"📊 **Aktuelle Konfiguration**: Ziel-ACOS für Gebotsanpassungen: {target_acos_placement}%")
        
        st.markdown("### 🎯 **Spezialregel für wenig Traffic:**")
        st.markdown("• **Bedingung**: Top-Platzierung < 20 Klicks")
        st.markdown("• **Aktion**: Nur Top-Platzierung +100% (andere bleiben unverändert)")
        st.markdown("• **Max-Gebot-Schutz**: Automatische Begrenzung auf €1,50")
        
        if 'placement_adjustments' in optimization_results:
            placements = optimization_results['placement_adjustments']
            placement_data = [p for p in placements if not p.get('is_total', False)]
            
            if placement_data:
                st.info(f"🎯 **{len(placement_data)} Platzierungs-Anpassungen** werden vorgenommen:")
                
                # Show placement adjustments in a table
                df_placements = pd.DataFrame(placement_data)
                if not df_placements.empty:
                    # Select relevant columns for display
                    display_cols = ['campaign_id', 'placement', 'current_adjust_pct', 'recommended_adjust_pct']
                    existing_cols = [col for col in display_cols if col in df_placements.columns]
                    
                    if existing_cols:
                        df_display = df_placements[existing_cols].copy()
                        
                        # Rename columns to German
                        column_mapping = {
                            'campaign_id': 'Kampagnen-ID',
                            'placement': 'Platzierung',
                            'current_adjust_pct': 'Aktuell (%)',
                            'recommended_adjust_pct': 'Neu (%)'
                        }
                        df_display = df_display.rename(columns=column_mapping)
                        
                        # Add special rule indicator
                        if 'special_rule' in df_placements.columns:
                            df_display['Spezialregel'] = df_placements['special_rule'].apply(
                                lambda x: "🎯 <20 Klicks" if x == 'low_top_clicks' else ""
                            )
                        
                        # Add Standardgebot (Base CPC) column
                        if 'base_cpc' in df_placements.columns:
                            df_display['Standardgebot'] = df_placements.apply(
                                lambda row: f"€{row.get('base_cpc', 0):.2f}" 
                                if pd.notna(row.get('base_cpc')) and not row.get('is_total', False)
                                else "", 
                                axis=1
                            )
                        
                        # Add max bid calculation (Anpassung × Gebot)
                        if 'base_cpc' in df_placements.columns and 'recommended_adjust_pct' in df_placements.columns:
                            df_display['Max-Gebot'] = df_placements.apply(
                                lambda row: f"€{row.get('base_cpc', 0) * (1 + row.get('recommended_adjust_pct', 0) / 100):.2f}" 
                                if pd.notna(row.get('base_cpc')) and pd.notna(row.get('recommended_adjust_pct')) and not row.get('is_total', False)
                                else "", 
                                axis=1
                            )
                        
                        # Format the percentage columns
                        if 'Aktuell (%)' in df_display.columns:
                            df_display['Aktuell (%)'] = df_display['Aktuell (%)'].apply(
                                lambda x: f"{x}%" if pd.notna(x) else "0%"
                            )
                        if 'Neu (%)' in df_display.columns:
                            df_display['Neu (%)'] = df_display['Neu (%)'].apply(
                                lambda x: f"{x}%" if pd.notna(x) else "0%"
                            )
                        
                        st.dataframe(df_display, use_container_width=True)
                        
                        # Show special rule summary
                        special_rule_count = df_placements.get('special_rule', pd.Series()).eq('low_top_clicks').sum()
                        # Count capped bids for special rule campaigns
                        capped_count = 0
                        if 'bid_capped' in df_placements.columns and 'special_rule' in df_placements.columns:
                            capped_count = len(df_placements[
                                (df_placements['bid_capped'] == True) & 
                                (df_placements['special_rule'] == 'low_top_clicks')
                            ])
                        
                        if special_rule_count > 0:
                            st.info(f"🎯 **{special_rule_count} Platzierungen** verwenden Spezialregel für <20 Klicks")
                        if capped_count > 0:
                            st.warning(f"💰 **{capped_count} Max-Gebote** wurden auf €1,50 begrenzt")
            else:
                st.success("✅ Keine Platzierungs-Anpassungen erforderlich")
        else:
            st.info("ℹ️ Keine Platzierungsdaten verfügbar")
    
    with st.expander("🎯 **Gebots-Updates (Basis-CPC)**"):
        st.markdown(f"**Alle relevanten Entitäten erhalten die jeweiligen Basis-CPCs ihrer Kampagnen:**")
        st.markdown("• **Manuelle Kampagnen**: 🔤 Keywords + 🛍️ Product Ads")  
        st.markdown("• **Automatische Kampagnen**: 🎯 Product Targeting")
        st.markdown(f"📊 **Berechnung**: Basis-CPC = min_rpc × {target_acos_placement}% Ziel-ACOS")
        
        if 'placement_adjustments' in optimization_results:
            placements = optimization_results['placement_adjustments']
            # Get campaign base CPC values from totals rows
            campaign_base_cpc = {}
            for p in placements:
                if p.get('is_total', False):
                    campaign_id = p.get('campaign_id')
                    base_cpc_total = p.get('base_cpc_total')
                    if campaign_id and base_cpc_total is not None:
                        campaign_base_cpc[campaign_id] = base_cpc_total
            
            if campaign_base_cpc:
                st.info(f"🎯 **{len(campaign_base_cpc)} Kampagnen** haben Basis-CPC Werte für Keyword-Updates")
                
                # Create table showing campaign basis CPCs
                cpc_data = []
                for campaign_id, base_cpc in campaign_base_cpc.items():
                    cpc_data.append({
                        'Kampagnen-ID': campaign_id,
                        'Basis-CPC': f"€{base_cpc:.2f}",
                        'Anwendung': 'Alle Keywords + Produktanzeigen + Produkt-Targeting'
                    })
                
                if cpc_data:
                    df_cpc = pd.DataFrame(cpc_data)
                    st.dataframe(df_cpc, use_container_width=True)
                    
                    st.markdown("**📝 Alle Keywords, Produktanzeigen und Produkt-Targeting** erhalten automatisch den Basis-CPC ihrer jeweiligen Kampagne")
            else:
                st.info("ℹ️ Keine Basis-CPC Werte verfügbar")
        else:
            st.info("ℹ️ Keine Platzierungsdaten für Basis-CPC Berechnung verfügbar")
        
    with st.expander("⏸️ **Keyword-Pausierung**"):
        client_config = st.session_state.get('client_config', {})
        keyword_acos = client_config.get('keyword_acos', 20.0)
        max_keyword_clicks = client_config.get('max_keyword_clicks', 50)
        
        st.markdown(f"**Pausierungs-Kriterien**: ACOS >{keyword_acos:.1f}% oder ≥{max_keyword_clicks} Klicks ohne Conversion")
        st.markdown(f"📊 **Aktuelle Konfiguration**: Keyword ACOS Limit: {keyword_acos}% | Max Klicks: {max_keyword_clicks}")
        
        # Analyze actual campaign keywords (not search terms) for pausing
        campaign_keywords_to_pause = []
        
        if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
            from app.utils.campaign_pauser import CampaignPauser
            
            df_campaign = st.session_state.df_campaign
            
            # Create a CampaignPauser instance to preview what would be paused
            pauser = CampaignPauser()
            
            # Get preview of what would be paused without actually modifying the data
            try:
                preview_results = pauser.preview_pausing(df_campaign, client_config)
                campaign_keywords_to_pause = preview_results.get('keywords_to_pause', [])
            except Exception as e:
                st.info(f"ℹ️ Keyword-Vorschau nicht verfügbar: {str(e)} - wird beim Export durchgeführt")
                campaign_keywords_to_pause = []
        
        if campaign_keywords_to_pause:
            st.warning(f"⏸️ **{len(campaign_keywords_to_pause)} Campaign Keywords** werden pausiert:")
            
            # Show keywords in a table
            keywords_data = []
            for kw in campaign_keywords_to_pause:
                keyword = kw.get('keyword', 'Unbekannt')
                clicks = kw.get('clicks', 0)
                orders = kw.get('orders', 0)
                acos = kw.get('acos', 0)
                reason = kw.get('reason', 'Keine Angabe')
                
                # Format ACOS
                if pd.notna(acos) and acos > 0:
                    if acos <= 1:
                        acos_display = f"{acos*100:.1f}%"
                    else:
                        acos_display = f"{acos:.1f}%"
                else:
                    acos_display = 'N/A'
                
                keywords_data.append({
                    'Keyword': keyword,
                    'Klicks': int(clicks) if pd.notna(clicks) else 'N/A',
                    'Bestellungen': int(orders) if pd.notna(orders) else 'N/A',
                    'ACOS': acos_display,
                    'Grund': reason
                })
            
            if keywords_data:
                df_keywords = pd.DataFrame(keywords_data)
                st.dataframe(df_keywords, use_container_width=True)
                
        else:
            st.success("✅ Keine Campaign Keywords müssen pausiert werden")
    
    with st.expander("🛍️ **Produkt-Pausierung**"):
        st.markdown(f"**ACOS-Grenzwert**: >{product_acos}% (inkl. hypothetischer ACOS)")
        st.markdown(f"📊 **Aktuelle Konfiguration**: Produkt ACOS Limit: {product_acos}%")
        
        # Check if we have campaign data to analyze products  
        if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
            from app.utils.campaign_pauser import CampaignPauser
            
            df_campaign = st.session_state.df_campaign
            pauser = CampaignPauser()
            
            # Get preview of what products would be paused
            try:
                preview_results = pauser.preview_pausing(df_campaign, client_config)
                products_to_pause = preview_results.get('products_to_pause', [])
                
                if products_to_pause:
                    st.warning(f"⏸️ **{len(products_to_pause)} Produkte** werden pausiert:")
                    
                    # Show products in a table
                    products_data = []
                    for prod in products_to_pause:
                        products_data.append({
                            'SKU': prod['sku'],
                            'ACOS': f"{prod['acos']:.1f}%",
                            'Grund': prod['reason']
                        })
                    
                    if products_data:
                        df_products = pd.DataFrame(products_data)
                        st.dataframe(df_products, use_container_width=True)
                else:
                    st.success("✅ Keine Produkte müssen pausiert werden")
                    
            except Exception as e:
                st.info(f"ℹ️ Produktpausierung wird beim Export durchgeführt (Vorschau nicht verfügbar: {str(e)})")
        else:
            st.info("ℹ️ Produktpausierung wird beim Export durchgeführt")
    
    st.markdown("### ⚠️ **Wichtige Hinweise:**")
    st.markdown("""
    - **Keywords erhalten Basis-CPC ihrer Kampagne** - basierend auf Platzierungs-Optimierung
    - **Platzierungs-Anpassungen** werden für alle drei Placement-Typen optimiert
    - **Spezialregel**: Kampagnen mit <20 Klicks Top-Platzierung bekommen nur +100% Top-Placement-Erhöhung
    - **Max-Gebot-Schutz**: Automatische Begrenzung auf €1,50 bei Spezialregel
    - **Keywords/Produkte werden pausiert** basierend auf intelligenter Analyse aus Konfiguration
    - **Alle anderen Sheets** bleiben unverändert erhalten
    - **Original-Datei** wird nicht überschrieben - eine neue Datei wird erstellt
    """)
    
    # Export functionality
    st.markdown("---")
    st.markdown("### 💾 **Export starten:**")
    
    if st.button("📤 Export-Datei vorbereiten", type="primary"):
        if not st.session_state.get('identified_original_keyword_column') or \
           not st.session_state.get('identified_original_bid_target_column'):
            st.error("Export nicht möglich: Original-Schlüsselwort oder Gebots-Spalten-Namen wurden während des Uploads nicht korrekt identifiziert. Bitte laden Sie erneut hoch.")
        else:
            with st.spinner("Export wird vorbereitet..."):
                try:
                    from app.utils.export_utils import generate_export_excel
                    
                    # Get all required data from session state
                    temp_file = st.session_state.get('temp_upload_filepath')
                    bid_changes = optimization_results.get("bid_changes", [])
                    search_terms_sheet = st.session_state.get('search_terms_sheet_name', 'Search Terms')
                    campaign_sheet = st.session_state.get('original_campaign_sheet_name', 'Campaign')
                    keyword_col = st.session_state.get('identified_original_keyword_column', 'Keyword')
                    bid_col = st.session_state.get('identified_original_bid_target_column', 'Bid')
                    all_sheets = st.session_state.get('all_original_sheet_names', [])
                    placement_changes = optimization_results.get('placement_adjustments', [])
                    
                    # Keep all placement changes including totals (needed for Base CPC extraction)
                    placement_changes_filtered = placement_changes
                    
                    current_target_acos = None
                    if 'placement_target_acos_slider' in st.session_state:
                        current_target_acos = st.session_state.placement_target_acos_slider / 100
                    else:
                        # Fall back to client config
                        current_target_acos = float(client_config.get('target_acos_placement', 20.0)) / 100
                    
                    # Recompute placement adjustments with current ACOS if needed
                    if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
                        from app.utils.placement_adjuster import compute_placement_adjustments
                        placement_changes_filtered = compute_placement_adjustments(
                            st.session_state.df_campaign, 
                            target_acos=current_target_acos,
                            df_campaign_full=st.session_state.df_campaign
                        )
                        # Keep totals for Base CPC extraction in export, but filter for display purposes if needed
                        # The export function needs the totals rows to extract base_cpc_total values
                    
                    # Debug: Show what config is being passed to export
                    st.info(f"🔧 **Übergabe an Export:** {client_config}")
                    
                    # Debug: Show placement changes structure
                    total_changes = [p for p in placement_changes_filtered if p.get('is_total', False)]
                    st.info(f"🔍 **Placement Changes Debug:** Total records: {len(placement_changes_filtered)}, Total rows with base_cpc_total: {len(total_changes)}")
                    if total_changes:
                        for total in total_changes:
                            st.info(f"   📊 Campaign {total.get('campaign_id')}: base_cpc_total = €{total.get('base_cpc_total', 'N/A')}")
                    
                    # Generate export file
                    export_buffer = generate_export_excel(
                        original_excel_path=temp_file,
                        bid_changes=bid_changes,
                        search_terms_sheet_name=search_terms_sheet,
                        keyword_match_col_original_name=keyword_col,
                        bid_update_col_original_name=bid_col,
                        campaign_sheet_name=campaign_sheet,
                        all_original_sheet_names=all_sheets,
                        placement_changes=placement_changes_filtered,
                        client_config=client_config
                    )
                    
                    if export_buffer:
                        # Store in session state for download
                        st.session_state.export_buffer = export_buffer
                        st.session_state.export_ready = True
                        st.success("✅ Export erfolgreich vorbereitet! Download ist bereit.")
                    else:
                        st.error("❌ Export fehlgeschlagen. Bitte versuchen Sie es erneut.")
                        
                except Exception as e:
                    st.error(f"❌ Export-Fehler: {str(e)}")
                    import traceback
                    with st.expander("🔍 Fehler-Details"):
                        st.code(traceback.format_exc())
    
    # Show download button if export is ready
    if st.session_state.get('export_ready', False) and st.session_state.get('export_buffer'):
        st.success("✅ Export bereit!")
        st.download_button(
            label="Aktualisierter Bericht herunterladen",
            data=st.session_state.export_buffer.getvalue(),
            file_name="Amazon_PPC_Optimized.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="export_download_button_persistent"
        )


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