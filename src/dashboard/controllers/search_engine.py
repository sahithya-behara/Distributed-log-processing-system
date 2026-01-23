import pandas as pd
from datetime import datetime

def search_logs(df: pd.DataFrame, query: str = "", filters: dict = None) -> pd.DataFrame:
    """
    Search and filter logs based on isolated search parameters.
    
    Args:
        df: The source dataframe (raw data).
        query: Keyword string to search for (case-insensitive).
        filters: Dictionary containing independent search filters:
                 - date_range: (start_date, end_date) tuple or None
                 - levels: list of log levels (e.g., ['ERROR', 'INFO']) or None
                 - services: list of services/sources or None
    
    Returns:
        Filtered DataFrame.
    """
    if df.empty:
        return df
        
    result_df = df.copy()
    
    # 1. Apply Filters First (Performance)
    if filters:
        # Date Level Isolation
        date_range = filters.get('date_range')
        if date_range:
            start, end = date_range
            # Ensure timestamp column exists and is datetime
            if 'timestamp' in result_df.columns:
                 # Standardize to datetime if not already (should be handled by loader, but safe check)
                # Standardize to datetime if not already
                s_ts = pd.Timestamp(start)
                e_ts = pd.Timestamp(end)
                
                result_df = result_df[
                    (result_df['timestamp'] >= s_ts) & 
                    (result_df['timestamp'] <= e_ts)
                ]

        # Log Level Isolation
        levels = filters.get('levels')
        if levels and 'log_level' in result_df.columns:
            result_df = result_df[result_df['log_level'].isin(levels)]

        # Service Isolation
        services = filters.get('services')
        if services and 'service' in result_df.columns:
            # Handle "All Services" or explicit selection
            # Assuming UI passes only specific services if filtered
            result_df = result_df[result_df['service'].isin(services)]

    # 2. Text Search
    if query and not result_df.empty:
        query = query.lower().strip()
        
        # Construct a boolean mask for keyword match across relevant columns
        mask = pd.Series(False, index=result_df.index)
        
        search_cols = [col for col in ['message', 'service', 'log_level'] if col in result_df.columns]
        
        for col in search_cols:
             # Vectorized string contains
             mask |= result_df[col].astype(str).str.lower().str.contains(query, na=False)
             
        # Optional: Check timestamp string representation if query looks like a date?
        # For now, keep it simple to content/metadata.
             
        result_df = result_df[mask]
        
    return result_df
