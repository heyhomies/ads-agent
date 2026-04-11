import streamlit as st

def render_configuration():
    """
    Unified configuration page with essential settings in German
    """
    st.title("Konfiguration")
    
    # Get existing config or use defaults
    if 'client_config' not in st.session_state:
        st.session_state.client_config = {
            'max_keyword_clicks': 30,
            'keyword_acos': 35.0,
            'product_acos': 35.0,
            'target_acos_placement': 20.0
        }
    
    # Main configuration form
    with st.form("unified_config_form"):
        st.subheader("Einstellungen")
        
        # Maximum clicks per keyword
        max_keyword_clicks = st.number_input(
            "Maximale Klicks pro Keyword ohne Conversion",
            min_value=1,
            max_value=1000,
            value=st.session_state.client_config.get('max_keyword_clicks', 30),
            step=1,
            help="Maximale Anzahl von Klicks ohne Conversion, bevor ein Keyword pausiert wird"
        )
        
        # Keyword ACOS threshold
        keyword_acos = st.slider(
            "Keyword ACOS (%)",
            min_value=0.0,
            max_value=200.0,
            value=st.session_state.client_config.get('keyword_acos', 35.0),
            step=1.0,
            help="ACOS-Grenzwert für Keywords"
        )
        
        # Product ACOS threshold  
        product_acos = st.slider(
            "Produkt ACOS (%)",
            min_value=0.0,
            max_value=200.0,
            value=st.session_state.client_config.get('product_acos', 35.0),
            step=1.0,
            help="ACOS-Grenzwert für Produkte (einschließlich hypothetischer ACOS für Produkte ohne Verkäufe)"
        )
        
        # Target ACOS for placement adjustments (Gebotsanpassungen)
        target_acos_placement = st.slider(
            "Ziel-ACOS für Gebotsanpassungen (%)",
            min_value=0.0,
            max_value=200.0,
            value=st.session_state.client_config.get('target_acos_placement', 20.0),
            step=0.5,
            help="Ziel-ACOS für die Berechnung der Placement-Bid-Anpassungen"
        )
        
        
        # Submit button
        submitted = st.form_submit_button("Konfiguration speichern")
        
        if submitted:
            # Update session state with simplified config
            st.session_state.client_config = {
                'max_keyword_clicks': max_keyword_clicks,
                'keyword_acos': keyword_acos,
                'product_acos': product_acos,
                'target_acos_placement': target_acos_placement
            }
            
            # CRITICAL: Clear all cached calculations that depend on configuration
            # This forces recalculation when user navigates to Dashboard
            cache_keys_to_clear = [
                'optimization_results',
                'placement_adjustments',
                'keyword_performance',
                'export_buffer',
                'export_ready'
            ]
            
            for key in cache_keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.success("✅ Konfiguration gespeichert! Alle Berechnungen werden beim nächsten Dashboard-Besuch aktualisiert.")
            st.info("📊 **Wichtiger Hinweis**: Wechseln Sie zum Dashboard, damit alle Werte mit der neuen Konfiguration neu berechnet werden.")
    
    # Display current configuration
    if st.session_state.client_config:
        st.subheader("Aktuelle Konfiguration")
        
        config = st.session_state.client_config
        
        # Create a styled representation of the configuration
        st.info(f"""
        **Maximale Klicks pro Keyword:** {config.get('max_keyword_clicks', 50)}
        
        **Keyword ACOS:** {config.get('keyword_acos', 20.0)}%
        
        **Produkt ACOS:** {config.get('product_acos', 20.0)}%
        
        **Ziel-ACOS für Gebotsanpassungen:** {config.get('target_acos_placement', 20.0)}%
        """) 