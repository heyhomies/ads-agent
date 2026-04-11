import streamlit as st

def render_configuration():
    """
    Unified configuration page with essential settings in German
    """
    st.title("Konfiguration")

    st.info(
        "Diese Einstellungen steuern, welche Keywords und Produkte im exportierten Bulk Sheet pausiert werden "
        "und wie die Placement-Gebotsanpassungen berechnet werden. "
        "Ein Element wird nur pausiert, wenn es den Klick-Schwellenwert **und** den jeweiligen ACOS-Grenzwert gleichzeitig überschreitet "
        "– oder wenn es den Klick-Schwellenwert ohne eine einzige Conversion erreicht hat."
    )

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

        # Minimum clicks threshold
        max_keyword_clicks = st.number_input(
            "Mindestklicks für Pausierungsentscheidung",
            min_value=1,
            max_value=1000,
            value=st.session_state.client_config.get('max_keyword_clicks', 30),
            step=1,
            help="Ein Keyword oder Produkt wird erst pausiert, wenn es mindestens so viele Klicks hat. "
                 "Darunter ist der ACOS statistisch nicht belastbar genug."
        )

        # Keyword ACOS threshold
        keyword_acos = st.slider(
            "Keyword ACOS (%)",
            min_value=0.0,
            max_value=200.0,
            value=st.session_state.client_config.get('keyword_acos', 35.0),
            step=1.0,
            help="Keywords mit einem ACOS über diesem Wert werden pausiert – vorausgesetzt, "
                 "der Mindestklick-Schwellenwert ist erreicht."
        )

        # Product ACOS threshold
        product_acos = st.slider(
            "Produkt ACOS (%)",
            min_value=0.0,
            max_value=200.0,
            value=st.session_state.client_config.get('product_acos', 35.0),
            step=1.0,
            help="Produkte mit einem ACOS über diesem Wert werden pausiert – vorausgesetzt, "
                 "der Mindestklick-Schwellenwert ist erreicht. Bei Produkten ohne Umsatz wird ein hypothetischer ACOS berechnet."
        )

        # Target ACOS for placement adjustments (Gebotsanpassungen)
        target_acos_placement = st.slider(
            "Ziel-ACOS für Gebotsanpassungen (%)",
            min_value=0.0,
            max_value=200.0,
            value=st.session_state.client_config.get('target_acos_placement', 20.0),
            step=0.5,
            help="Grundlage für die Berechnung des Basis-CPC und der Placement-Bid-Anpassungen. "
                 "Ein niedrigerer Wert führt zu konservativeren Geboten."
        )

        # Submit button
        submitted = st.form_submit_button("Konfiguration speichern")

        if submitted:
            st.session_state.client_config = {
                'max_keyword_clicks': max_keyword_clicks,
                'keyword_acos': keyword_acos,
                'product_acos': product_acos,
                'target_acos_placement': target_acos_placement
            }

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
            st.info("📊 Wechseln Sie zum Dashboard, damit alle Werte mit der neuen Konfiguration neu berechnet werden.")

    # Display current configuration
    if st.session_state.client_config:
        st.subheader("Aktuelle Konfiguration")
        config = st.session_state.client_config
        st.info(f"""
        **Mindestklicks für Pausierungsentscheidung:** {config.get('max_keyword_clicks', 30)}

        **Keyword ACOS:** {config.get('keyword_acos', 35.0)}%

        **Produkt ACOS:** {config.get('product_acos', 35.0)}%

        **Ziel-ACOS für Gebotsanpassungen:** {config.get('target_acos_placement', 20.0)}%
        """)
