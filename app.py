import streamlit as st
import pandas as pd
import os
import base64
from pathlib import Path
from app.utils.excel_processor import process_amazon_report
from app.utils.optimizer import apply_optimization_rules
from app.components.dashboard import render_dashboard
from app.components.configuration import render_configuration
from app.utils.export_utils import generate_export_excel
from io import BytesIO
from app.utils.placement_adjuster import compute_placement_adjustments

st.set_page_config(
    page_title="Amazon PPC Optimizer by heyhome",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load logo
_logo_path = Path(__file__).parent / "logo.png"
_logo_b64 = ""
if _logo_path.exists():
    _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()

st.markdown("""
<style>
/* Buttons: Dunkelgrün mit Gelb */
.stButton > button,
.stDownloadButton > button {
    background-color: #4d7b73 !important;
    color: #e7e137 !important;
    border: 1px solid #4d7b73 !important;
    font-weight: bold !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    background-color: #3a6059 !important;
    color: #e7e137 !important;
    border-color: #3a6059 !important;
}
.stButton > button:active,
.stDownloadButton > button:active {
    background-color: #2d4d48 !important;
    color: #e7e137 !important;
}

/* Erfolgsmeldungen: Hellgrün Hintergrund, Dunkelgrün Text */
div[data-testid="stNotification"] {
    background-color: #b3d8b8 !important;
    border-color: #4d7b73 !important;
}
div[data-testid="stNotification"] p,
div[data-testid="stNotification"] span {
    color: #4d7b73 !important;
}
div[data-testid="stNotification"] svg {
    fill: #4d7b73 !important;
    color: #4d7b73 !important;
}
.stAlert > div {
    background-color: #b3d8b8 !important;
    color: #4d7b73 !important;
}
</style>
""", unsafe_allow_html=True)

def main():
    if _logo_b64:
        st.sidebar.image(_logo_path, width=45)
    st.sidebar.title("Amazon PPC Optimierer")
    
    # Initialize session state for page navigation if not already set
    if 'page' not in st.session_state:
        st.session_state.page = "Bericht hochladen"
        
    # Navigation
    page_options = ["Bericht hochladen", "Konfiguration", "Dashboard"]

    current_index = page_options.index(st.session_state.page) if st.session_state.page in page_options else 0
    selected_page_from_sidebar = st.sidebar.selectbox(
        "Navigation",
        page_options,
        index=current_index,
    )
    if st.session_state.page != selected_page_from_sidebar:
        st.session_state.page = selected_page_from_sidebar
        st.rerun()

    active_page = st.session_state.page
    
    if active_page == "Bericht hochladen":
        if _logo_b64:
            st.image(_logo_path, width=45)
        st.title("Amazon PPC Optimizer by heyhome")
        st.markdown("---")
        
        with st.expander("Hilfe zum Datei-Upload", expanded=True):
            st.markdown("""
            ### Erwartetes Dateiformat
            Bitte lade eine Amazon Bulk-Sheet-Excel-Datei mit folgenden Arbeitsblättern hoch:
            
            **Erforderlich für Gebotsänderungen:**
            - **Sponsored Products-Kampagnen** – hier werden die Gebote angepasst
            
            **Optional für Analyse:**
            - **SP Bericht Suchbegriff** – dient nur zur Analyse von Keyword-Ausreißern (hoher ACOS, ACOS = 0, sehr niedriger ACOS)
            
            **Wichtige Spalten im Sheet „Sponsored Products-Kampagnen“:**
            - **Keywords** (z. B. „Keyword-Text“) – zum Abgleich und Anpassen der Gebote
            - **Gebote** (z. B. „Max. Gebot“, „CPC“) – werden aktualisiert
            - Leistungskennzahlen: **Klicks**, **Kosten**, **Bestellungen**, **Umsatz**, **ACOS** etc.
            
            Das System identifiziert Keyword-Ausreißer und passt die Gebote entsprechend an.
            """)
        
        uploaded_file = st.file_uploader("Bulk-Sheet auswählen (Excel)", type=["xlsx"])
        
        if uploaded_file is not None:
            temp_upload_dir = "temp_uploads"
            if not os.path.exists(temp_upload_dir):
                os.makedirs(temp_upload_dir)
            temp_upload_filepath = os.path.join(temp_upload_dir, uploaded_file.name)
            
            try:
                with open(temp_upload_filepath, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.session_state.temp_upload_filepath = temp_upload_filepath # Store for exporter
                
                with st.spinner("Excel-Datei verarbeiten..."):
                    # Update to handle new return values from process_amazon_report
                    processed_data = process_amazon_report(temp_upload_filepath)
                    
                    if processed_data[0] is None: # Check if processing failed (indicated by first element being None)
                        st.error("Datei konnte nicht verarbeitet werden. Bitte überprüfen Sie die Fehlermeldungen und das Dateiformat.")
                        return

                    (
                        df_campaign, df_search_terms, 
                        original_search_terms_sheet_name, original_campaign_sheet_name,
                        identified_original_keyword_column, identified_original_bid_target_column,
                        all_original_sheet_names
                    ) = processed_data
                
                if df_campaign is None or df_campaign.empty:
                    st.error("Konnte keine gültigen Kampagnendaten extrahieren. Bitte überprüfen Sie die Datei und stellen Sie sicher, dass das Blatt „Sponsored Products-Kampagnen“ existiert.")
                    return
                
                # --- Preview processed data ---
                st.subheader("Vorschau Kampagnendaten (Basis für Änderungen)")
                st.dataframe(df_campaign.head(), use_container_width=True)
                
                if df_search_terms is not None and not df_search_terms.empty:
                    st.subheader("Vorschau Suchbegriff-Daten (nur Analyse)")
                    st.dataframe(df_search_terms.head(), use_container_width=True)
                else:
                    st.warning("Kein Suchbegriff-Sheet gefunden. Analyse beschränkt sich auf Kampagnendaten.")
                    
                can_continue = True
                # Ensure essential columns for optimizer are present in the campaign data
                if 'keyword' not in df_campaign.columns:
                    st.error("Kampagnendaten fehlt die 'keyword' Spalte. Fortfahren nicht möglich.")
                    can_continue = False
                if 'clicks' not in df_campaign.columns or 'spend' not in df_campaign.columns:
                    st.error("Kampagnendaten fehlt die 'clicks' oder 'spend' Spalten. Fortfahren nicht möglich.")
                    can_continue = False
                
                if can_continue:
                    st.session_state.df_campaign = df_campaign
                    st.session_state.df_search_terms = df_search_terms
                    # Store original names for export
                    st.session_state.original_search_terms_sheet_name = original_search_terms_sheet_name
                    st.session_state.original_campaign_sheet_name = original_campaign_sheet_name
                    st.session_state.identified_original_keyword_column = identified_original_keyword_column
                    st.session_state.identified_original_bid_target_column = identified_original_bid_target_column
                    st.session_state.all_original_sheet_names = all_original_sheet_names

                    # ── Campaign selection & per-campaign target ACOS ──────────
                    st.divider()
                    st.subheader("Kampagnen-Auswahl & Ziel-ACOS")

                    all_campaigns = []
                    if 'campaign_name' in df_campaign.columns:
                        all_campaigns = sorted([
                            c for c in df_campaign['campaign_name'].dropna().unique()
                            if str(c).strip()
                        ])

                    if all_campaigns:
                        global_target = st.session_state.get('client_config', {}).get('target_acos_placement', 20.0)
                        existing_acos = st.session_state.get('campaign_target_acos', {})
                        existing_selection = st.session_state.get('campaign_selection', {})

                        st.caption(
                            f"Globaler Ziel-ACOS: **{global_target}%**  ·  "
                            "Haken setzen = Kampagne optimieren, Ziel-ACOS pro Kampagne übersteuern:"
                        )

                        campaign_df = pd.DataFrame({
                            'Optimieren': [existing_selection.get(c, True) for c in all_campaigns],
                            'Kampagne': all_campaigns,
                            'Ziel-ACOS (%)': [existing_acos.get(c, global_target) for c in all_campaigns],
                        })

                        edited = st.data_editor(
                            campaign_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'Optimieren': st.column_config.CheckboxColumn('Optimieren', width='small'),
                                'Kampagne': st.column_config.TextColumn('Kampagne', disabled=True),
                                'Ziel-ACOS (%)': st.column_config.NumberColumn(
                                    'Ziel-ACOS (%)', min_value=0.0, max_value=200.0, step=0.5, format="%.1f"
                                ),
                            },
                            key="campaign_acos_editor",
                        )

                        # Derive selected campaigns and per-campaign ACOS from edited table
                        selected_campaigns = edited.loc[edited['Optimieren'], 'Kampagne'].tolist()
                        st.session_state.campaign_selection = dict(zip(edited['Kampagne'], edited['Optimieren']))
                        st.session_state.campaign_target_acos = dict(zip(edited['Kampagne'], edited['Ziel-ACOS (%)']))

                        if not selected_campaigns:
                            st.warning("Bitte mindestens eine Kampagne zur Optimierung auswählen.")
                    else:
                        selected_campaigns = []
                        st.warning("Keine Kampagnennamen in den Daten gefunden.")
                    # ──────────────────────────────────────────────────────────

                    if st.button("Optimierung starten"):
                        with st.spinner("Optimierungsregeln anwenden..."):
                            client_config = st.session_state.get('client_config', {
                                'keyword_acos': 20.0,
                                'product_acos': 20.0,
                                'target_acos_placement': 20.0,
                                'max_keyword_clicks': 50
                            })
                            campaign_target_acos = st.session_state.get('campaign_target_acos', {})

                            # Filter to selected campaigns only
                            df_to_optimize = df_campaign.copy()
                            if selected_campaigns and 'campaign_name' in df_to_optimize.columns:
                                df_to_optimize = df_to_optimize[df_to_optimize['campaign_name'].isin(selected_campaigns)]
                            st.session_state.df_campaign = df_to_optimize

                            try:
                                optimization_results = apply_optimization_rules(
                                    st.session_state.df_campaign,
                                    st.session_state.df_search_terms,
                                    client_config
                                )

                                # Add hypothetical ACOS calculations
                                from app.utils.hypothetical_acos import add_hypothetical_acos_to_optimization_results
                                optimization_results = add_hypothetical_acos_to_optimization_results(
                                    optimization_results,
                                    client_config.get('product_acos', 20.0)
                                )

                                # Update session state with enriched data for dashboard access
                                if 'df_search_terms_with_hypothetical' in optimization_results:
                                    st.session_state.df_search_terms = optimization_results['df_search_terms_with_hypothetical']
                                if 'df_campaign_with_hypothetical' in optimization_results:
                                    st.session_state.df_campaign = optimization_results['df_campaign_with_hypothetical']

                                # Calculate placement bid adjustments (per-campaign ACOS)
                                try:
                                    placement_target_acos = client_config.get('target_acos_placement', 20.0)
                                    placement_adjustments = compute_placement_adjustments(
                                        st.session_state.df_campaign,
                                        target_acos=placement_target_acos / 100,
                                        df_campaign_full=st.session_state.df_campaign,
                                        campaign_target_acos=campaign_target_acos,
                                    )
                                except Exception as e:
                                    placement_adjustments = []
                                    st.session_state["placement_error"] = str(e)
                                optimization_results['placement_adjustments'] = placement_adjustments

                                # Keyword classification (per-campaign ACOS)
                                from app.utils.keyword_classifier import classify_keywords
                                keyword_perf = classify_keywords(
                                    st.session_state.df_campaign,
                                    target_acos=float(client_config.get('keyword_acos', 20)) / 100,
                                    campaign_target_acos=campaign_target_acos,
                                )
                                optimization_results['keyword_performance'] = keyword_perf
                                st.session_state.optimization_results = optimization_results
                                st.success("Optimierung erfolgreich abgeschlossen!")
                                st.session_state.page = "Dashboard"
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler während der Optimierung: {str(e)}")
                                import traceback
                                st.code(traceback.format_exc())
            except Exception as e:
                st.error(f"Fehler beim Verarbeiten der hochgeladenen Datei: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                # Clean up temp file if needed, or leave for export
                # For now, we leave it as its path is stored for export
                pass 
    
    elif active_page == "Konfiguration":
        render_configuration()
    
    elif active_page == "Dashboard":
        # Check if we need to recalculate due to config changes
        need_recalculation = False
        
        if 'optimization_results' not in st.session_state:
            need_recalculation = True
            
        # Check if all required data exists for recalculation
        has_data = (
            'df_campaign' in st.session_state and 
            st.session_state.df_campaign is not None and
            not st.session_state.df_campaign.empty
        )
        
        if need_recalculation and has_data:
            st.info("🔄 **Konfiguration wurde geändert - Berechnungen werden aktualisiert...**")
            
            with st.spinner("Neuberechnung mit aktueller Konfiguration..."):
                try:
                    client_config = st.session_state.get('client_config', {
                        'keyword_acos': 20.0, 
                        'product_acos': 20.0,
                        'target_acos_placement': 20.0,
                        'max_keyword_clicks': 50
                    })
                    
                    # Recalculate optimization results
                    optimization_results = apply_optimization_rules(
                        st.session_state.df_campaign, 
                        st.session_state.get('df_search_terms', pd.DataFrame()),
                        client_config
                    )
                    
                    # Add hypothetical ACOS calculations
                    from app.utils.hypothetical_acos import add_hypothetical_acos_to_optimization_results
                    optimization_results = add_hypothetical_acos_to_optimization_results(
                        optimization_results, 
                        client_config.get('target_acos', 20.0)
                    )
                    
                    # Update session state with enriched data
                    if 'df_search_terms_with_hypothetical' in optimization_results:
                        st.session_state.df_search_terms = optimization_results['df_search_terms_with_hypothetical']
                    if 'df_campaign_with_hypothetical' in optimization_results:
                        st.session_state.df_campaign = optimization_results['df_campaign_with_hypothetical']
                        
                    # Calculate placement bid adjustments (per-campaign ACOS)
                    campaign_target_acos = st.session_state.get('campaign_target_acos', {})
                    placement_target_acos = client_config.get('target_acos_placement', 20.0)
                    placement_adjustments = compute_placement_adjustments(
                        st.session_state.df_campaign,
                        target_acos=placement_target_acos / 100,
                        df_campaign_full=st.session_state.df_campaign,
                        campaign_target_acos=campaign_target_acos,
                    )
                    optimization_results['placement_adjustments'] = placement_adjustments

                    # Keyword classification (per-campaign ACOS)
                    from app.utils.keyword_classifier import classify_keywords
                    keyword_perf = classify_keywords(
                        st.session_state.df_campaign,
                        target_acos=float(client_config.get('keyword_acos', 20)) / 100,
                        campaign_target_acos=campaign_target_acos,
                    )
                    optimization_results['keyword_performance'] = keyword_perf
                    
                    st.session_state.optimization_results = optimization_results
                    st.success("✅ Dashboard mit aktueller Konfiguration aktualisiert!")
                    st.rerun()  # Refresh to show updated dashboard
                    
                except Exception as e:
                    st.error(f"❌ Fehler bei der Neuberechnung: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        # Show dashboard if we have results
        if 'optimization_results' in st.session_state:
            render_dashboard(st.session_state.optimization_results)
        elif not has_data:
            st.info("Bitte laden Sie zuerst einen Bericht hoch und optimieren, um das Dashboard zu sehen und Ergebnisse zu exportieren.")
            if st.button("Zur Upload-Seite"):
                st.session_state.page = "Bericht hochladen"
                st.rerun()
        else:
            st.error("Unerwarteter Zustand: Daten vorhanden, aber Berechnungen fehlgeschlagen.")

if __name__ == "__main__":
    main() 