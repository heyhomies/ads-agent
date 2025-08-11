#!/usr/bin/env python3
"""
Check available tables in the database
"""

import sys
sys.path.append('.')

from postgres_data_retriever import PostgreSQLRetriever

def check_tables():
    """Check what tables are available in the database"""
    print("🔍 Checking Available Database Tables")
    print("=" * 50)
    
    retriever = PostgreSQLRetriever()
    if not retriever.connect():
        print("❌ Database connection failed")
        return
    
    try:
        # List all tables
        tables = retriever.list_tables()
        print(f"📊 Available tables: {tables}")
        
        # If tables exist, show structure
        if tables:
            for table in tables:
                print(f"\n📋 Table: {table}")
                try:
                    schema = retriever.describe_table(table)
                    print(f"   Columns: {schema}")
                    
                    # Show sample data
                    sample_data = retriever.get_table_data(table, limit=3)
                    if not sample_data.empty:
                        print(f"   Sample data ({len(sample_data)} rows):")
                        print(sample_data.to_string(index=False))
                    else:
                        print(f"   No data in table")
                        
                except Exception as e:
                    print(f"   Error accessing table: {e}")
        else:
            print("❌ No tables found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        retriever.disconnect()

if __name__ == "__main__":
    check_tables() 