import pandas as pd
from io import BytesIO
import streamlit as st # For potential logging or error display, though not strictly needed here
from .campaign_pauser import CampaignPauser
from datetime import datetime

def generate_export_excel(original_excel_path: str,
                          bid_changes: list,
                          search_terms_sheet_name: str,
                          keyword_match_col_original_name: str,
                          bid_update_col_original_name: str,
                          campaign_sheet_name: str = None, # Now required: original campaign sheet name
                          all_original_sheet_names: list = None,
                          placement_changes: list = None,
                          client_config: dict = None,
                          negative_keywords: list = None,
                          pause_keywords: list = None,
                          pause_products: list = None):
    """
    Generates an Excel file in memory with placement adjustments and Base CPC updates.
    
    Features:
    - Placement (Platzierung) adjustments for all three placement types
    - Base CPC updates for Keywords and Product Targeting based on targeting type
    - Intelligent keyword and product pausing based on configuration thresholds

    Args:
        original_excel_path (str): Path to the originally uploaded Excel file.
        bid_changes (list): List of dictionaries with bid change information (IGNORED - keyword updates disabled).
        search_terms_sheet_name (str): The original name of the search terms sheet (for analysis reference).
        keyword_match_col_original_name (str): Original name of the column to match keywords on in campaign sheet (IGNORED).
        bid_update_col_original_name (str): Original name of the column where bids should be updated (IGNORED).
        campaign_sheet_name (str, required): Original name of the campaign sheet where changes are made.
        all_original_sheet_names (list, optional): List of all original sheet names to preserve order and other sheets.
        placement_changes (list, optional): List of placement adjustment changes to apply.
        client_config (dict, optional): Client configuration with thresholds for pausing.

    Returns:
        BytesIO: Buffer containing the new Excel file with placement adjustments and Base CPC updates, or None on failure.
    """
    if not original_excel_path:
        st.error("Export Error: Original Excel file path is missing.")
        return None
    if not campaign_sheet_name:
        st.error("Export Error: Campaign sheet name is required for making bid changes.")
        return None
    if not keyword_match_col_original_name:
        st.error("Export Error: Original keyword column name for matching is missing.")
        return None
    if not bid_update_col_original_name:
        st.error("Export Error: Original bid column name for updating is missing.")
        return None

    try:
        xls = pd.ExcelFile(original_excel_path)
        
        # Use all_original_sheet_names if provided and valid, otherwise default to xls.sheet_names
        sheet_names_to_process = all_original_sheet_names if all_original_sheet_names and len(all_original_sheet_names) > 0 else xls.sheet_names
        
        sheets_data = {}
        for name in sheet_names_to_process:
            if name in xls.sheet_names:
                df_sheet = xls.parse(name)
                if not df_sheet.empty:  # Skip empty sheets (e.g. placeholder "Sheet3")
                    sheets_data[name] = df_sheet
            else:
                st.warning(f"Export Warning: Sheet '{name}' was listed but not found in the original file. It will be skipped.")

        if campaign_sheet_name not in sheets_data:
            st.error(f"Export Error: Campaign sheet '{campaign_sheet_name}' not found in the loaded Excel data.")
            return None

        df_to_update = sheets_data[campaign_sheet_name].copy() # Work on campaign sheet copy

        if keyword_match_col_original_name not in df_to_update.columns:
            st.error(f"Export Error: Keyword match column '{keyword_match_col_original_name}' not found in sheet '{campaign_sheet_name}'. Available: {df_to_update.columns.tolist()}")
            return None
        if bid_update_col_original_name not in df_to_update.columns:
            st.error(f"Export Error: Bid update column '{bid_update_col_original_name}' not found in sheet '{campaign_sheet_name}'. Available: {df_to_update.columns.tolist()}")
            return None

        # --- Clean Keyword Match Column ---------------------------------------------------
        # Convert to string **after** filling NaNs so we do not get the literal string "nan".
        df_to_update[keyword_match_col_original_name] = (
            df_to_update[keyword_match_col_original_name]
            .fillna("")          # real NaNs → blank strings
            .astype(str)          # keep original text
        )

        # Remove any leftover literal "nan" / "None" strings that might already exist
        df_to_update[keyword_match_col_original_name] = df_to_update[keyword_match_col_original_name].replace(
            to_replace=["nan", "NaN", "None"], value=""
        )
        
        # Prepare bid update column to accept numeric data, preserving existing numbers
        df_to_update[bid_update_col_original_name] = pd.to_numeric(df_to_update[bid_update_col_original_name], errors='coerce')

        # Ensure an 'Operation' column exists (Amazon bulksheet expects this in column C).
        # If not present, insert it as the third column (index 2) and default to empty strings.
        if 'Operation' not in df_to_update.columns:
            df_to_update.insert(2, 'Operation', '')
        else:
            # Ensure Operation column can accept string values
            df_to_update['Operation'] = df_to_update['Operation'].astype('object')

        updated_keywords_count = 0
        updated_placements_count = 0
        updated_base_cpc_count = 0
        anzeigengruppe_updates = 0
        campaign_name_updates = 0
        
        # --- KEYWORD BID UPDATES DISABLED ---
        # Keyword bid updates have been disabled per user request.
        # Only placement adjustments and Base CPC updates will be included in the export.
        st.info("ℹ️ Keyword bid updates are disabled. Only placement adjustments and Base CPC updates will be exported.")
        
        # ------------------- Apply placement changes ----------------------------
        if placement_changes:
            if 'Platzierung' in df_to_update.columns and 'Prozentsatz' in df_to_update.columns:
                for pl_change in placement_changes:
                    camp_id = pl_change.get('campaign_id')
                    placement_label = pl_change.get('placement')
                    new_pct = pl_change.get('recommended_adjust_pct')
                    
                    # Check if this is a special rule application
                    special_rule = pl_change.get('special_rule')
                    bid_capped = pl_change.get('bid_capped', False)
                    new_max_bid = pl_change.get('new_max_bid')
            
                    try:
                        new_pct_val = float(new_pct)
                    except (ValueError, TypeError):
                        continue

                    # Ensure we only update placement adjustment rows, not keyword rows
                    if 'Entität' in df_to_update.columns:
                        entity_col = 'Entität'
                    elif 'Entity' in df_to_update.columns:
                        entity_col = 'Entity'
                    else:
                        entity_col = None

                    if entity_col:
                        mask_pl = (
                            (df_to_update['Kampagnen-ID'] == camp_id) &
                            (df_to_update['Platzierung'] == placement_label) &
                            (df_to_update[entity_col].astype(str).str.lower() == 'gebotsanpassung')
                        )
                    else:
                        # Fallback: if no entity column, use original logic but with warning
                        mask_pl = (
                            (df_to_update['Kampagnen-ID'] == camp_id) &
                            (df_to_update['Platzierung'] == placement_label)
                        )
                        st.warning("⚠️ No Entity column found. Placement updates may affect unintended rows.")
                    idxs = df_to_update[mask_pl].index
                    if not idxs.empty:
                        df_to_update.loc[idxs, 'Prozentsatz'] = new_pct_val
                        # Ensure Operation column accepts string values before setting
                        if df_to_update['Operation'].dtype != 'object':
                            df_to_update['Operation'] = df_to_update['Operation'].astype('object')
                        df_to_update.loc[idxs, 'Operation'] = 'Update'
                        updated_placements_count += len(idxs)
                        
                        # Show special rule info in export
                        if special_rule == 'low_top_clicks':
                            if bid_capped and new_max_bid:
                                st.success(f"   🎯 **Spezialregel angewendet:** Campaign {camp_id} {placement_label}: {new_pct_val}% (Max-Gebot auf €{new_max_bid:.2f} begrenzt)")
                            elif placement_label == 'Top-Platzierung':
                                st.success(f"   🎯 **Spezialregel angewendet:** Campaign {camp_id} {placement_label}: {new_pct_val}% (+100% für <20 Klicks)")
                        else:
                            st.success(f"   ✅ Campaign {camp_id} {placement_label}: {new_pct_val}% angewendet")

        # ------------------- Apply Base CPC updates ----------------------------
        # Update Base CPC for keyword and product targeting rows based on campaign placement adjustments
        if placement_changes:
            # Create a mapping of campaign_id to base_cpc from placement changes
            # Use the campaign-level base_cpc_total from totals rows, not individual placement base_cpc
            campaign_base_cpc = {}
            for pl_change in placement_changes:
                camp_id = pl_change.get('campaign_id')
                is_total = pl_change.get('is_total', False)
                
                # Only use the campaign-level totals row for base_cpc
                if is_total and camp_id:
                    base_cpc_total = pl_change.get('base_cpc_total')
                    if base_cpc_total is not None:
                        campaign_base_cpc[camp_id] = base_cpc_total
            
            # Check for required columns
            entity_col = None
            if 'Entität' in df_to_update.columns:
                entity_col = 'Entität'
            elif 'Entity' in df_to_update.columns:
                entity_col = 'Entity'
            
            targeting_col = None
            if 'Targeting-Typ' in df_to_update.columns:
                targeting_col = 'Targeting-Typ'
            elif 'Targeting-Type' in df_to_update.columns:
                targeting_col = 'Targeting-Type'
            elif 'Targeting Type' in df_to_update.columns:
                targeting_col = 'Targeting Type'
            
            bid_cols_to_update = []
            if 'Gebot' in df_to_update.columns:
                bid_cols_to_update.append('Gebot')
            if 'Standardgebot für die Anzeigengruppe' in df_to_update.columns:
                bid_cols_to_update.append('Standardgebot für die Anzeigengruppe')
            if 'Standardgebot für die Anzeigengruppe (Nur zu Informationszwecken)' in df_to_update.columns:
                bid_cols_to_update.append('Standardgebot für die Anzeigengruppe (Nur zu Informationszwecken)')
            
            if entity_col and targeting_col and bid_cols_to_update and campaign_base_cpc:
                st.info(f"🔍 **Base CPC Updates:** Processing {len(campaign_base_cpc)} campaigns")
                
                for camp_id, base_cpc_val in campaign_base_cpc.items():
                    try:
                        base_cpc_numeric = float(base_cpc_val)
                        base_cpc_rounded = round(base_cpc_numeric, 2)
                    except (ValueError, TypeError):
                        st.warning(f"   ⚠️ Invalid Base CPC value for campaign {camp_id}: {base_cpc_val}")
                        continue
                    
                    # Get campaign targeting type for this campaign
                    campaign_rows = df_to_update[df_to_update['Kampagnen-ID'] == camp_id]
                    if campaign_rows.empty:
                        st.warning(f"   ⚠️ No rows found for campaign {camp_id}")
                        continue
                    
                    # Get targeting type from any row in this campaign (should be consistent)
                    targeting_type = campaign_rows[targeting_col].iloc[0] if not campaign_rows[targeting_col].empty else None
                    
                    if pd.isna(targeting_type):
                        st.warning(f"   ⚠️ No targeting type for campaign {camp_id}")
                        continue
                    
                    targeting_type_str = str(targeting_type).lower().strip()
                    
                    # Determine target entity type based on targeting type
                    target_entity = None
                    if 'automatisch' in targeting_type_str or 'automatic' in targeting_type_str:
                        # Auto campaigns: Update "Produkt-Targeting" or "Product Targeting" rows
                        target_entity = 'produkt-targeting'
                        entity_display = '🎯 Product Targeting (Auto)'
                    elif 'manuell' in targeting_type_str or 'manual' in targeting_type_str:
                        # Manual campaigns: Update "Keyword" rows  
                        target_entity = 'keyword'
                        entity_display = '🔤 Keywords (Manual)'
                    else:
                        st.warning(f"   ⚠️ Unknown targeting type '{targeting_type_str}' for campaign {camp_id}")
                        continue
                    
                    # Find rows to update based on campaign ID and entity type
                    mask_base_cpc = (
                        (df_to_update['Kampagnen-ID'] == camp_id) &
                        (df_to_update[entity_col].astype(str).str.lower() == target_entity)
                    )
                    
                    idxs = df_to_update[mask_base_cpc].index
                    
                    if not idxs.empty:
                        # Update bid columns with 2 decimal places
                        for bid_col in bid_cols_to_update:
                            df_to_update.loc[idxs, bid_col] = base_cpc_rounded
                        # Ensure Operation column accepts string values before setting
                        if df_to_update['Operation'].dtype != 'object':
                            df_to_update['Operation'] = df_to_update['Operation'].astype('object')
                        df_to_update.loc[idxs, 'Operation'] = 'Update'
                        updated_base_cpc_count += len(idxs)
                        
                        st.success(f"   ✅ {entity_display}: Campaign {camp_id} - {len(idxs)} rows updated with Base CPC €{base_cpc_rounded:.2f}")
                    else:
                        # Check what entities actually exist in this campaign
                        campaign_entities = campaign_rows[entity_col].astype(str).str.lower().unique()
                        st.warning(f"   ⚠️ No '{target_entity}' rows found for campaign {camp_id}. Available entities: {sorted(campaign_entities)}")
                
                st.info(f"📊 **Total Base CPC Updates:** {updated_base_cpc_count} rows")
                
                # *** UPDATE ANZEIGENGRUPPE STANDARD BID COLUMNS ***
                # Update "Standardgebot für die Anzeigengruppe" for Anzeigengruppe entities
                anzeigengruppe_updates = 0
                
                for camp_id, base_cpc_val in campaign_base_cpc.items():
                    try:
                        base_cpc_numeric = float(base_cpc_val)
                    except (ValueError, TypeError):
                        continue
                    
                    # Find Anzeigengruppe entities for this campaign
                    anzeigengruppe_mask = (
                        (df_to_update['Kampagnen-ID'] == camp_id) &
                        (df_to_update[entity_col].astype(str).str.lower() == 'anzeigengruppe')
                    )
                    
                    anzeigengruppe_idxs = df_to_update[anzeigengruppe_mask].index
                    
                    if not anzeigengruppe_idxs.empty:
                        # Update Standardgebot columns for Anzeigengruppe entities
                        base_cpc_rounded = round(base_cpc_numeric, 2)
                        
                        # Update the main Standardgebot column
                        if 'Standardgebot für die Anzeigengruppe' in df_to_update.columns:
                            df_to_update.loc[anzeigengruppe_idxs, 'Standardgebot für die Anzeigengruppe'] = base_cpc_rounded
                        
                        # Update the info-only column if it exists
                        if 'Standardgebot für die Anzeigengruppe (Nur zu Informationszwecken)' in df_to_update.columns:
                            df_to_update.loc[anzeigengruppe_idxs, 'Standardgebot für die Anzeigengruppe (Nur zu Informationszwecken)'] = base_cpc_rounded
                        
                        # Set Operation column for Anzeigengruppe updates
                        if df_to_update['Operation'].dtype != 'object':
                            df_to_update['Operation'] = df_to_update['Operation'].astype('object')
                        df_to_update.loc[anzeigengruppe_idxs, 'Operation'] = 'Update'
                        
                        anzeigengruppe_updates += len(anzeigengruppe_idxs)
                        st.success(f"   ✅ Anzeigengruppe: Campaign {camp_id} - {len(anzeigengruppe_idxs)} Standardgebote aktualisiert auf €{base_cpc_rounded:.2f}")
                
                if anzeigengruppe_updates > 0:
                    st.info(f"📊 **Anzeigengruppe-Updates:** {anzeigengruppe_updates} Standardgebote aktualisiert")
            
            elif not entity_col:
                st.warning("⚠️ No Entity column found. Base CPC updates skipped.")
            elif not targeting_col:
                st.warning("⚠️ No Targeting Type column found. Base CPC updates skipped.")
            elif not bid_cols_to_update:
                st.warning("⚠️ No bid columns ('Gebot', 'Standardgebot für die Anzeigengruppe', 'Standardgebot für die Anzeigengruppe (Nur zu Informationszwecken)') found. Base CPC updates skipped.")
            elif not campaign_base_cpc:
                st.warning("⚠️ No Base CPC values found in placement changes. Base CPC updates skipped.")
            
            # *** UPDATE CAMPAIGN NAMES WITH DATE AND TARGET ACOS ***
            # Moved outside Base CPC block - campaign names should always be updated when entity_col exists
            # This ensures renaming happens even if campaign_base_cpc is empty
            if entity_col and client_config and 'target_acos_placement' in client_config:
                # Generate date string in (D)DMMYY format
                today = datetime.now()
                day = today.day
                month = today.month
                year = today.year % 100  # Last 2 digits of year
                date_str = f"{day}{month:02d}{year:02d}"  # e.g., "91025" for 9. Oct 2025
                
                target_acos_pct = int(client_config.get('target_acos_placement', 20))
                
                # Find Campaign entities
                campaign_mask = df_to_update[entity_col].astype(str).str.lower() == 'kampagne'
                campaign_entities = df_to_update[campaign_mask]
                
                if not campaign_entities.empty:
                    st.info(f"🏷️ **Updating campaign names** with date {date_str} and target ACOS {target_acos_pct}%")
                    
                    for idx, campaign_row in campaign_entities.iterrows():
                        # Get original campaign name
                        original_name = campaign_row.get('Kampagnenname', campaign_row.get('Campaign Name', 'Unknown'))
                        
                        # Remove existing date and ACOS suffix if present (in case of re-optimization)
                        # Pattern: remove all " [date] [acos]%" patterns from end
                        import re
                        cleaned_name = str(original_name)
                        # Remove multiple date/acos patterns that might exist
                        cleaned_name = re.sub(r'\s+\d{5,6}\s+\d{1,2}%', '', cleaned_name)  # Remove all occurrences
                        cleaned_name = re.sub(r'\s+\d{5,6}$', '', cleaned_name)  # Remove trailing date without %
                        cleaned_name = cleaned_name.strip()  # Clean up any extra spaces
                        
                        # Add new optimization date and target ACOS
                        new_name = f"{cleaned_name} {date_str} {target_acos_pct}%"
                        
                        # Update campaign name
                        if 'Kampagnenname' in df_to_update.columns:
                            df_to_update.at[idx, 'Kampagnenname'] = new_name
                        if 'Campaign Name' in df_to_update.columns:
                            df_to_update.at[idx, 'Campaign Name'] = new_name
                            
                        # Set Operation for campaign name update
                        if df_to_update['Operation'].dtype != 'object':
                            df_to_update['Operation'] = df_to_update['Operation'].astype('object')
                        df_to_update.at[idx, 'Operation'] = 'Update'
                        
                        campaign_name_updates += 1
                        
                        campaign_id = campaign_row.get('Kampagnen-ID', 'Unknown')
                        st.success(f"   ✅ Campaign {campaign_id}: '{cleaned_name}' → '{new_name}'")
                    
                    if campaign_name_updates > 0:
                        st.info(f"📊 **Campaign Name Updates:** {campaign_name_updates} Kampagnennamen aktualisiert")

        # ------------------- Apply Campaign Pausing Logic ----------------------------
        paused_keywords_count = 0
        paused_products_count = 0

        if pause_keywords is not None or pause_products is not None:
            # Use user-confirmed pauses from the Export tab UI
            try:
                entity_col = next((c for c in ['Entität', 'entität'] if c in df_to_update.columns), None)
                campaign_id_col = next((c for c in ['Kampagnen-ID', 'kampagnen-id'] if c in df_to_update.columns), None)
                kw_text_col = next((c for c in ['Keyword-Text', 'keyword-text'] if c in df_to_update.columns), None)
                asin_col = next((c for c in ['ASIN', 'asin'] if c in df_to_update.columns), None)

                if entity_col and campaign_id_col:
                    for item in (pause_keywords or []):
                        cid = str(item.get('campaign_id', ''))
                        kw = str(item.get('keyword', ''))
                        if not cid or not kw or not kw_text_col:
                            continue
                        mask = (
                            (df_to_update[entity_col].astype(str).str.lower() == 'keyword') &
                            (df_to_update[campaign_id_col].astype(str) == cid) &
                            (df_to_update[kw_text_col].astype(str) == kw)
                        )
                        if mask.any():
                            df_to_update.loc[mask, 'Operation'] = 'Update'
                            df_to_update.loc[mask, 'Zustand'] = 'Angehalten'
                            paused_keywords_count += int(mask.sum())

                    for item in (pause_products or []):
                        cid = str(item.get('campaign_id', ''))
                        asin = str(item.get('asin', ''))
                        if not cid or not asin or not asin_col:
                            continue
                        mask = (
                            (df_to_update[entity_col].astype(str).str.lower() == 'produktanzeige') &
                            (df_to_update[campaign_id_col].astype(str) == cid) &
                            (df_to_update[asin_col].astype(str) == asin)
                        )
                        if mask.any():
                            df_to_update.loc[mask, 'Operation'] = 'Update'
                            df_to_update.loc[mask, 'Zustand'] = 'Angehalten'
                            paused_products_count += int(mask.sum())
            except Exception as e:
                st.warning(f"⚠️ Fehler beim Anwenden der bestätigten Pausierungen: {str(e)}")

        elif client_config:
            # Fallback: automatic pausing when UI hasn't been used yet
            try:
                pauser = CampaignPauser()
                df_to_update, pause_summary = pauser.process_campaign_sheet(df_to_update, client_config)
                paused_keywords_count = pause_summary.get('keywords_paused', 0)
                paused_products_count = pause_summary.get('products_paused', 0)
            except Exception as e:
                st.warning(f"⚠️ Fehler beim Pausieren von Kampagnen-Elementen: {str(e)}")

        # ------------------- Add Negative Keywords ----------------------------
        neg_kw_count = 0
        if negative_keywords:
            new_rows = []
            for nk in negative_keywords:
                search_term = nk.get('search_term', '')
                campaign_id = nk.get('campaign_id', '')
                ad_group_id = nk.get('ad_group_id', '')
                if not search_term or not campaign_id:
                    continue
                row = {col: '' for col in df_to_update.columns}
                row['Produkt'] = 'Sponsored Products'
                row['Entität'] = 'Negatives Keyword'
                row['Operation'] = 'Create'
                if 'Kampagnen-ID' in row:
                    row['Kampagnen-ID'] = campaign_id
                if 'Anzeigengruppen-ID' in row and ad_group_id:
                    row['Anzeigengruppen-ID'] = ad_group_id
                if 'Zustand' in row:
                    row['Zustand'] = 'Aktiviert'
                if 'Keyword-Text' in row:
                    row['Keyword-Text'] = search_term
                if 'Übereinstimmungstyp' in row:
                    row['Übereinstimmungstyp'] = 'Negativ Exact'
                new_rows.append(row)

            if new_rows:
                df_negatives = pd.DataFrame(new_rows, columns=df_to_update.columns)
                df_to_update = pd.concat([df_to_update, df_negatives], ignore_index=True)
                neg_kw_count = len(new_rows)
                st.success(f"🚫 {neg_kw_count} Negative Keywords zur Export-Datei hinzugefügt.")

        sheets_data[campaign_sheet_name] = df_to_update

        # Show export summary
        messages = []
        if updated_placements_count > 0:
            messages.append(f"{updated_placements_count} Platzierungs-Anpassungen")
        if updated_base_cpc_count > 0:
            messages.append(f"{updated_base_cpc_count} Basis-CPC Aktualisierungen")
        if anzeigengruppe_updates > 0:
            messages.append(f"{anzeigengruppe_updates} Anzeigengruppe-Standardgebote")
        if campaign_name_updates > 0:
            messages.append(f"{campaign_name_updates} Kampagnennamen aktualisiert")
        if paused_keywords_count > 0:
            messages.append(f"{paused_keywords_count} Keywords pausiert")
        if paused_products_count > 0:
            messages.append(f"{paused_products_count} Produkte pausiert")
        if neg_kw_count > 0:
            messages.append(f"{neg_kw_count} Negative Keywords hinzugefügt")
        
        if messages:
            st.success(f"✅ Export erfolgreich: {', '.join(messages)} wurden aktualisiert.")
        else:
            st.warning("⚠️ Keine Änderungen gefunden oder angewendet.")

        output_buffer = BytesIO()
        with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
            for sheet_name_to_write in sheet_names_to_process:
                if sheet_name_to_write in sheets_data: # Check if sheet was loaded
                    sheets_data[sheet_name_to_write].to_excel(writer, sheet_name=sheet_name_to_write, index=False)
        
        output_buffer.seek(0)
        return output_buffer

    except FileNotFoundError:
        st.error(f"Export Error: Original Excel file not found at '{original_excel_path}'.")
        return None
    except Exception as e:
        st.error(f"Export Error: An unexpected error occurred: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None 