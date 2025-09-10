"""
Campaign Pauser Module

Handles pausing of products and keywords in the Sponsored Products-Kampagnen sheet
based on ACOS and hypothetical ACOS thresholds from configuration.
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Tuple, Dict, Any
from .hypothetical_acos import HypotheticalACOSCalculator

class CampaignPauser:
    """Handles pausing of products and keywords based on ACOS thresholds"""
    
    def __init__(self):
        self.hypothetical_calculator = HypotheticalACOSCalculator()
    
    def preview_pausing(self, df_campaign: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preview what keywords and products would be paused without modifying data
        
        Args:
            df_campaign: Campaign sheet DataFrame
            config: Configuration dictionary with thresholds
            
        Returns:
            Dictionary with preview results: {'keywords_to_pause': [...], 'products_to_pause': [...]}
        """
        if df_campaign is None or df_campaign.empty:
            return {'keywords_to_pause': [], 'products_to_pause': []}
        
        # Get thresholds from config
        max_keyword_acos = config.get('keyword_acos', 20.0) / 100.0  # Convert to decimal
        max_product_acos = config.get('product_acos', 20.0) / 100.0  # Convert to decimal
        max_clicks_no_conversion = config.get('max_keyword_clicks', 50)
        
        keywords_to_pause = []
        products_to_pause = []
        
        # Preview Keywords - check for both processed and original column names
        entity_col = None
        if 'entität' in df_campaign.columns:
            entity_col = 'entität'
        elif 'Entität' in df_campaign.columns:
            entity_col = 'Entität'
        
        if entity_col:
            keyword_mask = df_campaign[entity_col].astype(str).str.lower() == 'keyword'
            keywords_df = df_campaign[keyword_mask].copy()
            
            for _, row in keywords_df.iterrows():
                # Try both English (processed) and German (original) column names
                keyword_text = row.get('keyword', row.get('Keyword-Text', 'Unbekannt'))
                clicks = row.get('clicks', row.get('Klicks', 0))
                orders = row.get('orders', row.get('Bestellungen', 0))
                current_acos = row.get('acos', row.get('ACOS', 0))
                
                # Convert ACOS to decimal if it's a percentage
                if pd.notna(current_acos) and current_acos > 1:
                    current_acos = current_acos / 100.0
                
                should_pause = False
                reason = ""
                
                # Check if ACOS exceeds threshold
                if pd.notna(current_acos) and current_acos > max_keyword_acos:
                    should_pause = True
                    reason = f"ACOS {current_acos*100:.1f}% > Threshold {max_keyword_acos*100:.1f}%"
                
                # Check clicks without conversion
                elif pd.notna(clicks) and clicks >= max_clicks_no_conversion and (pd.isna(orders) or orders == 0):
                    should_pause = True
                    reason = f"{clicks} Klicks ohne Conversion (>= {max_clicks_no_conversion})"
                
                if should_pause:
                    keywords_to_pause.append({
                        'keyword': keyword_text,
                        'clicks': clicks,
                        'orders': orders if pd.notna(orders) else 0,
                        'acos': current_acos,
                        'reason': reason
                    })
            
            # Preview Products
            product_mask = df_campaign[entity_col].astype(str).str.lower() == 'produktanzeige'
            products_df = df_campaign[product_mask].copy()
            
            for _, row in products_df.iterrows():
                # Try both English (processed) and German (original) column names
                current_acos = row.get('acos', row.get('ACOS', 0))
                sales = row.get('sales', row.get('Verkäufe', 0))
                sku = row.get('sku', row.get('SKU', 'Unbekannt'))
                
                should_pause = False
                reason = ""
                
                # Convert ACOS to decimal if it's a percentage
                if pd.notna(current_acos) and current_acos > 1:
                    current_acos = current_acos / 100.0
                
                # Check regular ACOS threshold
                if pd.notna(current_acos) and current_acos > max_product_acos:
                    should_pause = True
                    reason = f"ACOS {current_acos*100:.1f}% > Threshold {max_product_acos*100:.1f}%"
                    if pd.isna(sales) or sales == 0:
                        reason += " (Hypothetischer ACOS)"
                
                if should_pause:
                    products_to_pause.append({
                        'sku': sku,
                        'acos': current_acos * 100,
                        'reason': reason
                    })
        
        return {
            'keywords_to_pause': keywords_to_pause,
            'products_to_pause': products_to_pause
        }
    
    
    def process_campaign_sheet(self, df_campaign: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Process the campaign sheet and pause products/keywords above thresholds
        
        Args:
            df_campaign: Campaign sheet DataFrame
            config: Configuration dictionary with thresholds
            
        Returns:
            Tuple of (updated_dataframe, summary_stats)
        """
        if df_campaign is None or df_campaign.empty:
            return df_campaign, {'keywords_paused': 0, 'products_paused': 0}
        
        # Make a copy to avoid modifying original
        df_updated = df_campaign.copy()
        
        # Get thresholds from config
        max_keyword_acos = config.get('keyword_acos', 20.0) / 100.0  # Convert to decimal
        max_product_acos = config.get('product_acos', 20.0) / 100.0  # Convert to decimal
        max_clicks_no_conversion = config.get('max_keyword_clicks', 50)
        
        # Debug: Show configuration being used
        st.info(f"🔧 **CampaignPauser verwendet:** Keyword ACOS: {max_keyword_acos*100:.1f}% | Produkt ACOS: {max_product_acos*100:.1f}% | Max Klicks: {max_clicks_no_conversion}")
        
        # Initialize counters
        keywords_paused = 0
        products_paused = 0
        
        # Process Keywords - check for both processed and original column names
        entity_col = None
        if 'entität' in df_updated.columns:
            entity_col = 'entität'
        elif 'Entität' in df_updated.columns:
            entity_col = 'Entität'
        elif 'entity' in df_updated.columns:
            entity_col = 'entity'
        elif 'Entity' in df_updated.columns:
            entity_col = 'Entity'
        
        if entity_col:
            keyword_mask = df_updated[entity_col].astype(str).str.lower() == 'keyword'
            keywords_df = df_updated[keyword_mask].copy()
            
            st.write(f"🔧 **Debug Keyword Processing:** Found entity column '{entity_col}', {len(keywords_df)} keyword rows")
        else:
            st.error("❌ Keine Entität-Spalte gefunden! Keywords können nicht verarbeitet werden.")
            st.write(f"📋 Verfügbare Spalten: {list(df_updated.columns)}")
            keywords_df = pd.DataFrame()  # Empty dataframe
        
        if not keywords_df.empty:
            st.info(f"🔍 Analyzing {len(keywords_df)} keywords for pausing...")
            
            for idx in keywords_df.index:
                row = df_updated.loc[idx]
                
                # Try both English (processed) and German (original) column names
                current_acos = row.get('acos', row.get('ACOS', 0))
                clicks = row.get('clicks', row.get('Klicks', 0))
                orders = row.get('orders', row.get('Bestellungen', 0))
                
                should_pause = False
                reason = ""
                
                # Convert ACOS to decimal if it's a percentage
                if pd.notna(current_acos) and current_acos > 1:
                    current_acos = current_acos / 100.0
                
                # Check if ACOS exceeds threshold
                if pd.notna(current_acos) and current_acos > max_keyword_acos:
                    should_pause = True
                    reason = f"ACOS {current_acos*100:.1f}% > Threshold {max_keyword_acos*100:.1f}%"
                
                # Check clicks without conversion
                elif pd.notna(clicks) and clicks >= max_clicks_no_conversion and (pd.isna(orders) or orders == 0):
                    should_pause = True
                    reason = f"{clicks} Klicks ohne Conversion (>= {max_clicks_no_conversion})"
                
                if should_pause:
                    df_updated.at[idx, 'Operation'] = 'Update'
                    df_updated.at[idx, 'Zustand'] = 'Angehalten'
                    keywords_paused += 1
                    
                    keyword_text = row.get('keyword', row.get('Keyword-Text', 'Unbekannt'))
                    st.write(f"   ⏸️ Keyword pausiert: {keyword_text} - {reason}")
        
        # Process Products (Produktanzeige)
        if entity_col:
            product_mask = df_updated[entity_col].astype(str).str.lower() == 'produktanzeige'
            products_df = df_updated[product_mask].copy()
        
        if not products_df.empty:
            st.info(f"🔍 Analyzing {len(products_df)} products for pausing...")
            
            # Load hypothetical ACOS calculator
            if self.hypothetical_calculator.load_pricing_data():
                # Enrich products with hypothetical ACOS
                products_enriched = self.hypothetical_calculator.enrich_dataframe_with_hypothetical_acos(
                    products_df, config.get('product_acos', 20.0)
                )
                
                for idx in products_df.index:
                    row = df_updated.loc[idx]
                    
                    # Check regular ACOS first
                    current_acos = row.get('ACOS', 0)
                    sales = row.get('Verkäufe', 0)
                    sku = row.get('SKU', '')
                    
                    should_pause = False
                    reason = ""
                    
                    # Convert ACOS to decimal if it's a percentage
                    if pd.notna(current_acos) and current_acos > 1:
                        current_acos = current_acos / 100.0
                    
                    # If product has sales, check regular ACOS
                    if pd.notna(sales) and sales > 0:
                        if pd.notna(current_acos) and current_acos > max_product_acos:
                            should_pause = True
                            reason = f"ACOS {current_acos*100:.1f}% > Threshold {max_product_acos*100:.1f}%"
                    
                    # If product has no sales, check hypothetical ACOS
                    elif pd.notna(sales) and sales == 0:
                        spend = row.get('Ausgaben', 0)
                        if pd.notna(spend) and spend > 0 and sku:
                            # Calculate hypothetical ACOS
                            hyp_result = self.hypothetical_calculator.calculate_hypothetical_acos(
                                spend, sku, config.get('product_acos', 20.0)
                            )
                            
                            if hyp_result['has_data']:
                                hyp_acos = hyp_result['hypothetical_acos']
                                if hyp_acos > max_product_acos:
                                    should_pause = True
                                    reason = f"Hypothetischer ACOS {hyp_acos*100:.1f}% > Threshold {max_product_acos*100:.1f}%"
                    
                    if should_pause:
                        df_updated.at[idx, 'Operation'] = 'Update'
                        df_updated.at[idx, 'Zustand'] = 'Angehalten'
                        products_paused += 1
                        
                        st.write(f"   ⏸️ Produkt pausiert: {sku} - {reason}")
            else:
                st.warning("⚠️ Konnte Datenbankverbindung für hypothetischen ACOS nicht herstellen")
        
        # Summary
        summary = {
            'keywords_paused': keywords_paused,
            'products_paused': products_paused,
            'total_paused': keywords_paused + products_paused
        }
        
        if summary['total_paused'] > 0:
            st.success(f"✅ Pausierung abgeschlossen: {keywords_paused} Keywords, {products_paused} Produkte")
        else:
            st.info("ℹ️ Keine Keywords oder Produkte zum Pausieren gefunden")
        
        return df_updated, summary
    
    def get_pausing_preview(self, df_campaign: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a preview of what would be paused without actually making changes
        
        Args:
            df_campaign: Campaign sheet DataFrame
            config: Configuration dictionary with thresholds
            
        Returns:
            Dictionary with preview information
        """
        if df_campaign is None or df_campaign.empty:
            return {'keywords_to_pause': [], 'products_to_pause': [], 'total_count': 0}
        
        # Get thresholds from config
        max_keyword_acos = config.get('keyword_acos', 20.0) / 100.0
        max_product_acos = config.get('product_acos', 20.0) / 100.0
        max_clicks_no_conversion = config.get('max_keyword_clicks', 50)
        
        keywords_to_pause = []
        products_to_pause = []
        
        # Check Keywords
        keyword_mask = df_campaign['Entität'].astype(str).str.lower() == 'keyword'
        for idx, row in df_campaign[keyword_mask].iterrows():
            current_acos = row.get('ACOS', 0)
            clicks = row.get('Klicks', 0)
            orders = row.get('Bestellungen', 0)
            keyword_text = row.get('Keyword-Text', 'Unknown')
            
            # Convert ACOS to decimal if it's a percentage
            if pd.notna(current_acos) and current_acos > 1:
                current_acos = current_acos / 100.0
            
            if pd.notna(current_acos) and current_acos > max_keyword_acos:
                keywords_to_pause.append({
                    'keyword': keyword_text,
                    'acos': current_acos * 100,
                    'reason': f"ACOS {current_acos*100:.1f}% > Threshold {max_keyword_acos*100:.1f}%"
                })
            elif pd.notna(clicks) and clicks >= max_clicks_no_conversion and (pd.isna(orders) or orders == 0):
                keywords_to_pause.append({
                    'keyword': keyword_text,
                    'clicks': clicks,
                    'reason': f"{clicks} Klicks ohne Conversion (>= {max_clicks_no_conversion})"
                })
        
        # Check Products
        product_mask = df_campaign['Entität'].astype(str).str.lower() == 'produktanzeige'
        for idx, row in df_campaign[product_mask].iterrows():
            current_acos = row.get('ACOS', 0)
            sales = row.get('Verkäufe', 0)
            sku = row.get('SKU', '')
            
            # Convert ACOS to decimal if it's a percentage
            if pd.notna(current_acos) and current_acos > 1:
                current_acos = current_acos / 100.0
            
            if pd.notna(sales) and sales > 0:
                if pd.notna(current_acos) and current_acos > max_product_acos:
                    products_to_pause.append({
                        'sku': sku,
                        'acos': current_acos * 100,
                        'reason': f"ACOS {current_acos*100:.1f}% > Threshold {max_product_acos*100:.1f}%"
                    })
        
        return {
            'keywords_to_pause': keywords_to_pause,
            'products_to_pause': products_to_pause,
            'total_count': len(keywords_to_pause) + len(products_to_pause)
        } 