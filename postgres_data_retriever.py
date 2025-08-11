#!/usr/bin/env python3
"""
PostgreSQL Data Retriever
Connects to PostgreSQL database and retrieves data from tables.
"""

import os
import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

class PostgreSQLRetriever:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Database connection parameters
        self.host = os.getenv('HOST', 'db.guiggfyirxppckrqrrwa.supabase.co')
        self.port = os.getenv('PORT', '5432')
        self.database = os.getenv('DATABASE', 'postgres')
        self.user = os.getenv('DATABASE_USER', 'postgres')
        self.password = os.getenv('PASSWORD', 'AmazonAgent')
        
        self.connection = None
        
    def connect(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            print(f"🔌 Connecting to {self.host}:{self.port}/{self.database} as {self.user}")
            
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=30,
                sslmode='require'  # Supabase requires SSL
            )
            
            print("✅ Successfully connected to PostgreSQL!")
            return True
            
        except psycopg2.Error as e:
            print(f"❌ Connection failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            print("🔌 Disconnected from database")
    
    def list_tables(self) -> List[str]:
        """List all tables in the database."""
        if not self.connection:
            print("❌ No database connection")
            return []
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            print(f"📋 Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table}")
            
            return tables
            
        except psycopg2.Error as e:
            print(f"❌ Error listing tables: {e}")
            return []
    
    def describe_table(self, table_name: str) -> Dict[str, Any]:
        """Get table structure and basic info."""
        if not self.connection:
            print("❌ No database connection")
            return {}
        
        try:
            cursor = self.connection.cursor()
            
            # Get column information
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cursor.fetchall()
            
            # Get row count
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(
                sql.Identifier(table_name)
            ))
            row_count = cursor.fetchone()[0]
            
            cursor.close()
            
            table_info = {
                'table_name': table_name,
                'row_count': row_count,
                'columns': [
                    {
                        'name': col[0],
                        'type': col[1],
                        'nullable': col[2],
                        'default': col[3]
                    }
                    for col in columns
                ]
            }
            
            print(f"\n📊 Table: {table_name}")
            print(f"   Rows: {row_count:,}")
            print(f"   Columns: {len(columns)}")
            for col in table_info['columns']:
                nullable = "NULL" if col['nullable'] == 'YES' else "NOT NULL"
                print(f"     - {col['name']} ({col['type']}) {nullable}")
            
            return table_info
            
        except psycopg2.Error as e:
            print(f"❌ Error describing table {table_name}: {e}")
            return {}
    
    def query_data(self, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """Execute a query and return results as pandas DataFrame."""
        if not self.connection:
            print("❌ No database connection")
            return pd.DataFrame()
        
        try:
            df = pd.read_sql_query(query, self.connection, params=params)
            print(f"✅ Query executed successfully. Retrieved {len(df)} rows.")
            return df
            
        except Exception as e:
            print(f"❌ Query failed: {e}")
            return pd.DataFrame()
    
    def get_table_data(self, table_name: str, limit: int = 100) -> pd.DataFrame:
        """Retrieve data from a specific table."""
        query = sql.SQL("SELECT * FROM {} LIMIT %s").format(
            sql.Identifier(table_name)
        )
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (limit,))
            
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            
            # Get data
            data = cursor.fetchall()
            cursor.close()
            
            df = pd.DataFrame(data, columns=columns)
            print(f"✅ Retrieved {len(df)} rows from {table_name}")
            return df
            
        except psycopg2.Error as e:
            print(f"❌ Error retrieving data from {table_name}: {e}")
            return pd.DataFrame()
    
    def search_tables(self, search_term: str) -> List[str]:
        """Search for tables containing the search term."""
        if not self.connection:
            print("❌ No database connection")
            return []
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name ILIKE %s
                ORDER BY table_name;
            """, (f'%{search_term}%',))
            
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            print(f"🔍 Found {len(tables)} tables matching '{search_term}':")
            for table in tables:
                print(f"  - {table}")
            
            return tables
            
        except psycopg2.Error as e:
            print(f"❌ Error searching tables: {e}")
            return []

def main():
    """Main function to demonstrate the PostgreSQL retriever."""
    print("🚀 PostgreSQL Data Retriever")
    print("=" * 50)
    
    # Create retriever instance
    retriever = PostgreSQLRetriever()
    
    # Connect to database
    if not retriever.connect():
        return
    
    try:
        # List all tables
        print("\n1️⃣ Listing all tables...")
        tables = retriever.list_tables()
        
        if not tables:
            print("No tables found in the database.")
            return
        
        # Describe first few tables
        print("\n2️⃣ Describing tables...")
        for table in tables[:3]:  # Limit to first 3 tables
            retriever.describe_table(table)
        
        # Get sample data from first table
        if tables:
            print(f"\n3️⃣ Sample data from {tables[0]}...")
            sample_data = retriever.get_table_data(tables[0], limit=5)
            if not sample_data.empty:
                print(sample_data.to_string())
        
        # Example custom query
        print("\n4️⃣ Example custom query...")
        if tables:
            query = f"SELECT * FROM {tables[0]} LIMIT 3"
            result = retriever.query_data(query)
            if not result.empty:
                print("Query result:")
                print(result.to_string())
    
    finally:
        # Always disconnect
        retriever.disconnect()

if __name__ == "__main__":
    main() 