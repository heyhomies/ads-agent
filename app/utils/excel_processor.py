import pandas as pd
import streamlit as st
import warnings

def process_amazon_report(file_path):
    """
    Process Amazon Bulk Sheet Excel file focusing on Sponsored Products-Kampagnen sheet for changes.
    SP Bericht Suchbegriff is used only for analysis to identify keyword outliers.
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        tuple: (
            df_campaign_processed, 
            df_search_terms_processed, 
            original_search_terms_sheet_name, 
            original_campaign_sheet_name,
            identified_original_keyword_column,  // e.g., "Keyword-Text" in campaigns sheet
            identified_original_bid_target_column // e.g., "CPC" or "Kosten pro Klick" in campaigns sheet
        )
    """
    try:
        xls = pd.ExcelFile(file_path)
        # Filter out empty sheets (e.g. placeholder "Sheet3" added by Excel/Amazon)
        all_sheet_names = [
            name for name in xls.sheet_names
            if not xls.parse(name).empty
        ]
        st.info(f"Sheets found in Excel file: {', '.join(all_sheet_names)}")

        original_search_terms_sheet_name = None
        original_campaign_sheet_name = None

        # --- Sheet Identification ---
        # Look for SP Bericht Suchbegriff for analysis only
        if "SP Bericht Suchbegriff" in all_sheet_names:
            original_search_terms_sheet_name = "SP Bericht Suchbegriff"
            st.success(f"Found 'SP Bericht Suchbegriff' sheet for keyword analysis!")
        else:
            for sheet in all_sheet_names:
                if "Suchbegriff" in sheet or "Search Term" in sheet or "SP Bericht" in sheet:
                    original_search_terms_sheet_name = sheet
                    break
        
        # Look for Sponsored Products-Kampagnen sheet for making changes
        if "Sponsored Products-Kampagnen" in all_sheet_names:
            original_campaign_sheet_name = "Sponsored Products-Kampagnen"
            st.success(f"Found 'Sponsored Products-Kampagnen' sheet for bid modifications!")
        else:
            for sheet in all_sheet_names:
                if "Kampagne" in sheet or "Campaign" in sheet or "Sponsored Products" in sheet:
                    original_campaign_sheet_name = sheet
                    break

        if not original_campaign_sheet_name:
            st.error("Could not find 'Sponsored Products-Kampagnen' sheet. This is required for making bid changes.")
            return None, None, None, None, None, None, None

        if not original_search_terms_sheet_name:
            st.warning("Could not find 'SP Bericht Suchbegriff' sheet. Analysis will be limited.")
            original_search_terms_sheet_name = st.selectbox(
                "Select Search Terms Sheet for Analysis", options=all_sheet_names, index=0 if all_sheet_names else None, key="select_search_sheet_analysis"
            )

        st.info(f"Using '{original_campaign_sheet_name}' for bid changes")
        st.info(f"Using '{original_search_terms_sheet_name}' for keyword analysis")

        # --- Load Campaign Sheet (Primary for Changes) ---
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Workbook contains no default style")
        df_campaign_raw = pd.read_excel(file_path, sheet_name=original_campaign_sheet_name)
        raw_campaign_columns = list(df_campaign_raw.columns)
        
        # Define mappings for campaign sheet (where changes will be made)
        column_mappings_campaign = {
            'kampagne': 'campaign_name', 'kampagnenname': 'campaign_name', 'campaign': 'campaign_name',
            'kampagnen-id': 'kampagnen-id', 'campaign_id': 'kampagnen-id', 'kampagnenid': 'kampagnen-id',
            'targeting-typ': 'targeting-typ', 'targeting_typ': 'targeting-typ', 'targeting_type': 'targeting-typ',
            'tagesbudget': 'daily_budget', 'status': 'status', 'gebotstyp': 'bidding_strategy', 
            'anzeigengruppe': 'ad_group_name', 'anzeigengruppenname': 'ad_group_name', 'ad_group': 'ad_group_name',
            'max._gebot': 'max_bid', 'maximales_gebot': 'max_bid', 'max_bid': 'max_bid',
            'gebot': 'max_bid',
            'keyword-text': 'keyword', 'keyword_text': 'keyword', 'keyword': 'keyword',
            'übereinstimmungstyp': 'match_type', 'match_type': 'match_type', 'übereinstimmung': 'match_type',
            'klicks': 'clicks', 'impressionen': 'impressions', 'ausgaben': 'spend', 'verkäufe': 'sales',
            'bestellungen': 'orders', 'acos': 'acos', 'conversion_rate': 'conversion_rate',
            'konversionsrate': 'conversion_rate', 'cpc': 'cpc', 'kosten_pro_klick': 'cpc', 'roas': 'roas'
        }

        # Identify original keyword and bid columns in campaign sheet
        identified_original_keyword_column = None
        identified_original_bid_target_column = None

        preferred_keyword_keys_normalized = ['keyword-text', 'keyword_text', 'keyword']
        for orig_col_name in raw_campaign_columns:
            norm_col = orig_col_name.lower().strip().replace(' ', '_')
            if norm_col in preferred_keyword_keys_normalized and column_mappings_campaign.get(norm_col) == 'keyword':
                identified_original_keyword_column = orig_col_name
                break
        
        preferred_bid_keys_normalized = ['max._gebot', 'maximales_gebot', 'max_bid', 'cpc', 'kosten_pro_klick', 'gebot']
        for orig_col_name in raw_campaign_columns:
            norm_col = orig_col_name.lower().strip().replace(' ', '_')
            if norm_col in preferred_bid_keys_normalized and (column_mappings_campaign.get(norm_col) in ['max_bid', 'cpc']):
                identified_original_bid_target_column = orig_col_name
                break

        # --- Load Search Terms Sheet (Analysis Only) ---
        df_search_terms_processed = None
        if original_search_terms_sheet_name:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Workbook contains no default style")
            df_search_terms_raw = pd.read_excel(file_path, sheet_name=original_search_terms_sheet_name)
            df_search_terms_processed = df_search_terms_raw.copy()
            df_search_terms_processed.columns = [col.lower().strip().replace(' ', '_') for col in df_search_terms_processed.columns]
            
            # Define mappings for search terms (analysis only)
            column_mappings_search_terms = {
                'suchbegriff': 'customer_search_term', 'suchbegriff_eines_kunden': 'customer_search_term', 'customer_search_term': 'customer_search_term',
                'kampagnen-id': 'kampagnen-id', 'campaign_id': 'kampagnen-id', 'kampagnenid': 'kampagnen-id',
                'keyword-text': 'keyword', 'keyword_text': 'keyword', 'keyword': 'keyword',
                'übereinstimmungstyp': 'match_type', 'match_type': 'match_type', 'übereinstimmung': 'match_type',
                'klicks': 'clicks', 'impressionen': 'impressions', 'ausgaben': 'spend', 'verkäufe': 'sales',
                'bestellungen': 'orders', 'acos': 'acos', 'conversion_rate': 'conversion_rate',
                'konversionsrate': 'conversion_rate', 'cpc': 'cpc', 'kosten_pro_klick': 'cpc', 'roas': 'roas'
            }
            
            df_search_terms_processed = rename_columns_for_processing(df_search_terms_processed, column_mappings_search_terms)
            
            # Only calculate metrics if they don't exist in the Excel file
            if 'conversion_rate' not in df_search_terms_processed.columns and 'orders' in df_search_terms_processed.columns and 'clicks' in df_search_terms_processed.columns:
                df_search_terms_processed['conversion_rate'] = (df_search_terms_processed['orders'] / df_search_terms_processed['clicks'].replace(0, float('nan')))
            if 'acos' not in df_search_terms_processed.columns and 'spend' in df_search_terms_processed.columns and 'sales' in df_search_terms_processed.columns:
                df_search_terms_processed['acos'] = (df_search_terms_processed['spend'] / df_search_terms_processed['sales'].replace(0, float('nan')))
        
        # --- Process Campaign Sheet (Primary Data) ---
        df_campaign_processed = df_campaign_raw.copy()
        st.info(f"Campaign sheet original columns: {', '.join(raw_campaign_columns)}")
        df_campaign_processed.columns = [col.lower().strip().replace(' ', '_') for col in df_campaign_processed.columns]
        df_campaign_processed = rename_columns_for_processing(df_campaign_processed, column_mappings_campaign)
        
        # Handle missing required columns for campaign processing
        required_campaign_cols = ['keyword', 'clicks', 'spend']
        missing_cols = [col for col in required_campaign_cols if col not in df_campaign_processed.columns]
        
        if missing_cols:
            st.warning(f"Missing required columns in campaign sheet: {', '.join(missing_cols)}")
            for col in missing_cols:
                if col in ['clicks', 'spend', 'sales', 'orders']:
                    df_campaign_processed[col] = 0
                else:
                    df_campaign_processed[col] = ""
        
        # Fill campaign_name from read-only info column for rows where it's NaN
        # (Amazon only populates the editable 'Kampagnenname' on Kampagne rows;
        #  all other entities like Gebotsanpassung, Keyword etc. only have the info column)
        info_col = 'kampagnenname_(nur_zu_informationszwecken)'
        if 'campaign_name' in df_campaign_processed.columns and info_col in df_campaign_processed.columns:
            df_campaign_processed['campaign_name'] = df_campaign_processed['campaign_name'].fillna(
                df_campaign_processed[info_col]
            )

        # Only calculate metrics if they don't exist in the Excel file
        if 'conversion_rate' not in df_campaign_processed.columns and 'orders' in df_campaign_processed.columns and 'clicks' in df_campaign_processed.columns:
            df_campaign_processed['conversion_rate'] = (df_campaign_processed['orders'] / df_campaign_processed['clicks'].replace(0, float('nan')))
        if 'acos' not in df_campaign_processed.columns and 'spend' in df_campaign_processed.columns and 'sales' in df_campaign_processed.columns:
            df_campaign_processed['acos'] = (df_campaign_processed['spend'] / df_campaign_processed['sales'].replace(0, float('nan')))
        
        # Final validation
        if not identified_original_keyword_column:
            st.error("The primary KEYWORD column in campaign sheet could not be identified. Bid changes will not work.")
        if not identified_original_bid_target_column:
            st.error("The BID/CPC column in campaign sheet could not be identified. Bid changes will not work.")

        st.success(f"Processed campaign data columns: {', '.join(df_campaign_processed.columns)}")
        if df_search_terms_processed is not None:
            st.success(f"Processed search terms data for analysis: {', '.join(df_search_terms_processed.columns)}")
        
        return (
            df_campaign_processed, df_search_terms_processed, 
            original_search_terms_sheet_name, original_campaign_sheet_name,
            identified_original_keyword_column, identified_original_bid_target_column,
            all_sheet_names
        )
        
    except Exception as e:
        st.error(f"Error processing Excel file: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None, None, None, None, None, None, None

def rename_columns_for_processing(df, mapping): # Renamed from just rename_columns
    renamed_df = df.copy()
    for col_original_case_sensitive in list(renamed_df.columns): # Iterate over a copy of column names
        col_lower_normalized = col_original_case_sensitive.lower().strip().replace(' ', '_')
        if col_lower_normalized in mapping:
            new_name = mapping[col_lower_normalized]
            # Ensure we don't overwrite an already correctly named column by a less specific mapping
            # E.g. if 'keyword' column already exists, don't let 'keyword_text' mapping overwrite it if 'keyword' itself was also a mapping key
            if new_name not in renamed_df.columns or col_original_case_sensitive == new_name : # or if mapping to itself (idempotent)
                 renamed_df = renamed_df.rename(columns={col_original_case_sensitive: new_name})
            elif new_name in renamed_df.columns and col_original_case_sensitive != new_name:
                 # A column with the target new_name already exists, and it's not the current one.
                 # This implies a conflict or a more specific mapping already applied.
                 # For now, we'll assume the first applied mapping or existing column is preferred.
                 # Or, one could collect conflicts.
                 pass


    return renamed_df 