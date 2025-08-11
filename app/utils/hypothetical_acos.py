#!/usr/bin/env python3
"""
Hypothetical ACOS Calculator
Calculates hypothetical ACOS for products with 0 sales using database pricing data.
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import streamlit as st

# Add the project root to the path to import PostgreSQLRetriever
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from postgres_data_retriever import PostgreSQLRetriever
except ImportError:
    # Fallback for when running from different context
    import importlib.util
    spec = importlib.util.spec_from_file_location("postgres_data_retriever", 
                                                 os.path.join(project_root, "postgres_data_retriever.py"))
    postgres_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(postgres_module)
    PostgreSQLRetriever = postgres_module.PostgreSQLRetriever

class HypotheticalACOSCalculator:
    def __init__(self):
        self.db_retriever = PostgreSQLRetriever()
        self.pricing_data = None
        
    def load_pricing_data(self) -> bool:
        """Load pricing data from PostgreSQL database."""
        try:
            if not self.db_retriever.connect():
                return False
            
            # Get all pricing data
            self.pricing_data = self.db_retriever.get_table_data('pricing', limit=1000)
            self.db_retriever.disconnect()
            
            if self.pricing_data.empty:
                st.warning("No pricing data found in database")
                return False
            
            st.info(f"✅ Loaded {len(self.pricing_data)} pricing records from database")
            return True
            
        except Exception as e:
            st.error(f"Error loading pricing data: {e}")
            return False
    
    def get_price_for_sku(self, sku: str) -> Optional[float]:
        """Get price for a specific SKU from the loaded pricing data."""
        if self.pricing_data is None or self.pricing_data.empty:
            return None
            
        # Try to find exact SKU match in 'seller-sku' column
        sku_match = self.pricing_data[self.pricing_data['seller-sku'] == sku]
        
        if not sku_match.empty:
            return float(sku_match.iloc[0]['price'])
        
        return None
    
    def calculate_hypothetical_acos(self, spend: float, sku: str, target_acos_slider: float = None) -> Dict[str, Any]:
        """
        Calculate hypothetical ACOS for products with 0 sales.
        
        Formula: Hypothetical ACOS = Ausgaben / (Price from database (gross) / 1.19)
        
        Args:
            spend: Amount spent on advertising (Ausgaben)
            sku: Product SKU to look up price
            target_acos_slider: Target ACOS from slider (as percentage, e.g., 20.0 for 20%)
            
        Returns:
            Dict with calculation results and metadata
        """
        # Get price from database
        gross_price = self.get_price_for_sku(sku)
        
        if gross_price is None:
            return {
                'hypothetical_acos': None,
                'hypothetical_acos_pct': None,
                'net_price': None,
                'gross_price': None,
                'spend': spend,
                'sku': sku,
                'error': f'Price not found for SKU {sku}',
                'has_data': False
            }
        
        # Calculate net price (remove 19% VAT)
        net_price = gross_price / 1.19
        
        # Calculate hypothetical ACOS (as decimal)
        hypothetical_acos = spend / net_price if net_price > 0 else 0
        
        # Convert to percentage for display
        hypothetical_acos_pct = hypothetical_acos * 100
        
        # Apply target ACOS slider influence if provided
        adjusted_acos_pct = hypothetical_acos_pct
        if target_acos_slider is not None:
            # The slider should influence the calculation - the closer to target, the better
            influence_factor = target_acos_slider / 100  # Convert to decimal
            adjusted_acos_pct = hypothetical_acos_pct * (1 + influence_factor * 0.1)  # Small adjustment based on target
        
        return {
            'hypothetical_acos': hypothetical_acos,
            'hypothetical_acos_pct': hypothetical_acos_pct,
            'adjusted_acos_pct': adjusted_acos_pct,
            'net_price': net_price,
            'gross_price': gross_price,
            'spend': spend,
            'sku': sku,
            'error': None,
            'has_data': True
        }
    
    def enrich_dataframe_with_hypothetical_acos(self, df: pd.DataFrame, target_acos_slider: float = None) -> pd.DataFrame:
        """
        Enrich a dataframe with hypothetical ACOS calculations for rows with 0 sales.
        
        Args:
            df: DataFrame with columns 'sales', 'spend', 'asin' (or 'asin1')
            target_acos_slider: Target ACOS from configuration slider
            
        Returns:
            DataFrame with additional columns for hypothetical ACOS
        """
        if self.pricing_data is None:
            if not self.load_pricing_data():
                return df
        
        df_enriched = df.copy()
        
        # Initialize new columns
        df_enriched['hypothetical_acos'] = np.nan
        df_enriched['hypothetical_acos_pct'] = np.nan
        df_enriched['hypothetical_acos_note'] = ''
        df_enriched['price_from_db'] = np.nan
        df_enriched['net_price_calculated'] = np.nan
        
        # Find rows with 0 sales - check for both German and English column names
        sales_col = None
        for col in ['sales', 'verkäufe', 'Verkäufe']:
            if col in df_enriched.columns:
                sales_col = col
                break
        
        spend_col = None
        for col in ['spend', 'ausgaben', 'Ausgaben']:
            if col in df_enriched.columns:
                spend_col = col
                break
        
        if sales_col is None or spend_col is None:
            st.warning(f"⚠️ Required columns not found. Sales: {sales_col}, Spend: {spend_col}")
            return df_enriched
        
        zero_sales_mask = (df_enriched[sales_col] == 0) | (pd.isna(df_enriched[sales_col]))
        
        # Determine SKU column name (check both campaign and search terms data)
        sku_col = None
        for col in ['sku', 'SKU', 'produkt', 'seller-sku']:
            if col in df_enriched.columns:
                sku_col = col
                break
        
        if sku_col is None:
            st.warning("No SKU column found in data for hypothetical ACOS calculation")
            return df_enriched
        
        # Calculate hypothetical ACOS for zero sales rows
        zero_sales_count = 0
        hypothetical_count = 0
        
        for idx, row in df_enriched[zero_sales_mask].iterrows():
            zero_sales_count += 1
            
            spend = row.get(spend_col, 0)
            sku = row.get(sku_col, '')
            
            if spend > 0 and sku:
                result = self.calculate_hypothetical_acos(spend, sku, target_acos_slider)
                
                if result['has_data']:
                    hypothetical_count += 1
                    
                    # Store the calculated values
                    df_enriched.at[idx, 'hypothetical_acos'] = result['hypothetical_acos']
                    df_enriched.at[idx, 'hypothetical_acos_pct'] = result['hypothetical_acos_pct']
                    df_enriched.at[idx, 'price_from_db'] = result['gross_price']
                    df_enriched.at[idx, 'net_price_calculated'] = result['net_price']
                    
                    # Replace the original ACOS with hypothetical ACOS
                    if 'acos' in df_enriched.columns:
                        df_enriched.at[idx, 'acos'] = result['hypothetical_acos']
                    
                    # Add explanatory note
                    note = f"Keine Verkäufe - Hypothetischer ACOS: {result['hypothetical_acos_pct']:.1f}% (basierend auf DB-Preis: €{result['gross_price']:.2f})"
                    df_enriched.at[idx, 'hypothetical_acos_note'] = note
                else:
                    df_enriched.at[idx, 'hypothetical_acos_note'] = f"Keine Verkäufe - Preis für SKU {sku} nicht in DB gefunden"
        
        if hypothetical_count > 0:
            st.success(f"✅ Calculated hypothetical ACOS for {hypothetical_count} out of {zero_sales_count} products with 0 sales")
        elif zero_sales_count > 0:
            st.warning(f"⚠️ Found {zero_sales_count} products with 0 sales, but could not calculate hypothetical ACOS (missing price data)")
        
        return df_enriched


def add_hypothetical_acos_to_optimization_results(optimization_results: Dict[str, Any], target_acos_slider: float = None) -> Dict[str, Any]:
    """
    Add hypothetical ACOS calculations to optimization results.
    
    Args:
        optimization_results: The optimization results dictionary
        target_acos_slider: Target ACOS from configuration slider
        
    Returns:
        Updated optimization results with hypothetical ACOS data
    """
    calculator = HypotheticalACOSCalculator()
    
    # Process search terms data if available
    if 'df_search_terms' in st.session_state and st.session_state.df_search_terms is not None:
        df_search_terms = st.session_state.df_search_terms.copy()
        df_enriched = calculator.enrich_dataframe_with_hypothetical_acos(df_search_terms, target_acos_slider)
        optimization_results['df_search_terms_with_hypothetical'] = df_enriched
    
    # Process campaign data if available
    if 'df_campaign' in st.session_state and st.session_state.df_campaign is not None:
        df_campaign = st.session_state.df_campaign.copy()
        df_campaign_enriched = calculator.enrich_dataframe_with_hypothetical_acos(df_campaign, target_acos_slider)
        optimization_results['df_campaign_with_hypothetical'] = df_campaign_enriched
    
    return optimization_results 