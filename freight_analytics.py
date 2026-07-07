import os
import sqlite3
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Define constants
DATA_RAW_PATH = "freight_orders_raw.csv"
DATA_CLEANED_PATH = "freight_orders_cleaned.csv"
DB_PATH = "freight_operations.db"

# Route Distances (in km) between major Indian cities
DISTANCES = {
    ('Mumbai', 'Pune'): 150,
    ('Mumbai', 'Delhi NCR'): 1400,
    ('Mumbai', 'Bangalore'): 1000,
    ('Mumbai', 'Chennai'): 1330,
    ('Mumbai', 'Hyderabad'): 700,
    ('Delhi NCR', 'Bangalore'): 2100,
    ('Delhi NCR', 'Chennai'): 2200,
    ('Delhi NCR', 'Pune'): 1400,
    ('Delhi NCR', 'Hyderabad'): 1500,
    ('Bangalore', 'Chennai'): 350,
    ('Bangalore', 'Pune'): 830,
    ('Bangalore', 'Hyderabad'): 570,
    ('Chennai', 'Pune'): 1000,
    ('Chennai', 'Hyderabad'): 630,
    ('Pune', 'Hyderabad'): 560
}

def get_distance(origin, dest):
    if origin == dest:
        return 50  # Intra-city shipment
    if (origin, dest) in DISTANCES:
        return DISTANCES[(origin, dest)]
    if (dest, origin) in DISTANCES:
        return DISTANCES[(dest, origin)]
    return 1000  # Fallback

def generate_raw_dataset(num_rows=105000, seed=42):
    """Generates a realistic synthetic logistics dataset with engineered anomalies."""
    np.random.seed(seed)
    
    # 1. Base Columns
    order_ids = [f"FGT-{i:07d}" for i in range(1, num_rows + 1)]
    
    # Date Range: 2025-07-01 to 2026-06-30 (12 months)
    start_date = datetime.date(2025, 7, 1)
    date_offsets = np.random.randint(0, 365, size=num_rows)
    order_dates = [start_date + datetime.timedelta(days=int(offset)) for offset in date_offsets]
    
    shipping_modes = ['Standard', 'Express', 'Same Day', 'Freight/LTL']
    mode_probs = [0.55, 0.25, 0.08, 0.12]
    modes = np.random.choice(shipping_modes, size=num_rows, p=mode_probs)
    
    carriers = ['BlueDart Allied', 'Apex Freight', 'Bharat Haulers', 'Deccan Transports', 'SpeedRun Logistics']
    carrier_choices = np.random.choice(carriers, size=num_rows)
    
    cities = ['Mumbai', 'Delhi NCR', 'Bangalore', 'Chennai', 'Pune', 'Hyderabad']
    origins = np.random.choice(cities, size=num_rows)
    destinations = []
    for o in origins:
        choices = [c for c in cities if c != o]
        destinations.append(np.random.choice(choices))
    
    order_values = np.random.uniform(20000, 500000, size=num_rows).round(2)
    weights = np.random.uniform(50, 15000, size=num_rows).round(2)
    
    segments = ['Manufacturing', 'Retail', 'Automotive', 'Pharma']
    segment_probs = [0.35, 0.25, 0.20, 0.20]
    cust_segments = np.random.choice(segments, size=num_rows, p=segment_probs)
    
    df = pd.DataFrame({
        'order_id': order_ids,
        'order_date': order_dates,
        'shipping_mode': modes,
        'carrier': carrier_choices,
        'origin_region': origins,
        'destination_region': destinations,
        'order_value': order_values,
        'weight_kg': weights,
        'customer_segment': cust_segments
    })
    
    # Convert order_date to datetime.date
    df['order_date'] = pd.to_datetime(df['order_date']).dt.date
    
    # 2. Promised SLA & Actual Delivery Dates
    sla_map = {
        'Same Day': 0,
        'Express': 2,
        'Standard': 5,
        'Freight/LTL': 8
    }
    df['promised_delivery_date'] = df.apply(
        lambda row: row['order_date'] + datetime.timedelta(days=sla_map[row['shipping_mode']]),
        axis=1
    )
    
    # Generate delays
    # Base: 82% on time, 18% late
    # Ensure delay >= -SLA so that actual_delivery_date is never before order_date
    is_late = np.random.rand(num_rows) < 0.18
    delays = np.zeros(num_rows)
    for mode, sla in sla_map.items():
        mode_idx = df['shipping_mode'] == mode
        mode_late = is_late[mode_idx]
        num_ontime = sum(~mode_late)
        num_late = sum(mode_late)
        
        mode_delays = np.zeros(sum(mode_idx))
        if num_ontime > 0:
            min_delay = -sla
            mode_delays[~mode_late] = np.random.randint(min_delay, 1, size=num_ontime)
        if num_late > 0:
            mode_delays[mode_late] = np.random.randint(1, 7, size=num_late)
            
        delays[mode_idx] = mode_delays
        
    df['delay_days'] = delays
    
    # Apply Anomaly 1: Bharat Haulers on Delhi NCR -> Bangalore route corridor is heavily delayed
    bharat_delhi_blr = (df['carrier'] == 'Bharat Haulers') & \
                       (df['origin_region'] == 'Delhi NCR') & \
                       (df['destination_region'] == 'Bangalore')
    # 78% of these orders are late, with delay between 4 and 12 days
    num_bharat = sum(bharat_delhi_blr)
    bharat_is_late = np.random.rand(num_bharat) < 0.78
    bharat_delays = np.zeros(num_bharat)
    bharat_delays[~bharat_is_late] = np.random.randint(-2, 1, size=sum(~bharat_is_late))
    bharat_delays[bharat_is_late] = np.random.randint(4, 13, size=sum(bharat_is_late))
    df.loc[bharat_delhi_blr, 'delay_days'] = bharat_delays
    
    # Apply Anomaly 3: Mumbai -> Chennai corridor delay rises linearly month-over-month
    mumbai_chennai = (df['origin_region'] == 'Mumbai') & (df['destination_region'] == 'Chennai')
    # Calculate months since July 2025
    df_order_dt = pd.to_datetime(df['order_date'])
    month_index = (df_order_dt.dt.year - 2025) * 12 + (df_order_dt.dt.month - 7)
    df['month_index'] = month_index
    
    # Add a progressive delay to Mumbai-Chennai route
    trend_delays = (df['month_index'] * 0.7).astype(int)
    df.loc[mumbai_chennai, 'delay_days'] += trend_delays[mumbai_chennai]
    df.drop(columns=['month_index'], inplace=True)
    
    # Construct actual delivery date
    df['actual_delivery_date'] = df.apply(
        lambda row: row['promised_delivery_date'] + datetime.timedelta(days=int(row['delay_days'])),
        axis=1
    )
    df.drop(columns=['delay_days'], inplace=True)
    
    # 3. Freight Cost Calculation
    # Standard rates:
    mode_rates = {
        'Standard': {'base': 1.5, 'weight': 0.002},
        'Express': {'base': 3.0, 'weight': 0.004},
        'Same Day': {'base': 45.0, 'weight': 8.0, 'surcharge': 8000.0}, # Anomaly 2: Very expensive Same Day
        'Freight/LTL': {'base': 0.9, 'weight': 0.001}
    }
    
    costs = []
    for idx, row in df.iterrows():
        origin = row['origin_region']
        dest = row['destination_region']
        mode = row['shipping_mode']
        weight = row['weight_kg']
        val = row['order_value']
        
        dist = get_distance(origin, dest)
        rates = mode_rates[mode]
        
        if mode == 'Same Day':
            # Surcharge + distance rate + weight rate
            cost = rates['surcharge'] + dist * rates['base'] + weight * rates['weight']
        else:
            cost = dist * (rates['base'] + weight * rates['weight'])
            
        # Add random noise (±10%)
        noise = np.random.normal(0, 0.05 * cost)
        cost += noise
        
        # Anomaly 2 cap: ensure freight cost does not exceed 85% of order value but stays high
        if mode == 'Same Day':
            cost = min(cost, val * 0.82)
            cost = max(cost, val * 0.18) # keep it very high
            
        costs.append(round(cost, 2))
        
    df['freight_cost'] = costs
    
    # 4. Perturb Data to Introduce Nulls & Outliers (Dirty Data)
    print("--- Perturbing dataset to introduce dirty data (nulls, outliers, chronological errors)...")
    
    # Nulls in actual_delivery_date (1.5%) - shipments not yet delivered or missing logs
    null_idx_actual = df.sample(frac=0.015, random_state=101).index
    df.loc[null_idx_actual, 'actual_delivery_date'] = pd.NaT
    
    # Nulls in freight_cost (1.0%)
    null_idx_cost = df.sample(frac=0.01, random_state=102).index
    df.loc[null_idx_cost, 'freight_cost'] = np.nan
    
    # Nulls in customer_segment (0.5%)
    null_idx_segment = df.sample(frac=0.005, random_state=103).index
    df.loc[null_idx_segment, 'customer_segment'] = None
    
    # Outliers in freight_cost: Typo errors (extremely high value, 0.15%)
    outlier_idx_cost = df.sample(frac=0.0015, random_state=104).index
    df.loc[outlier_idx_cost, 'freight_cost'] = np.random.uniform(2500000, 10000000, size=len(outlier_idx_cost)).round(2)
    
    # Outliers in freight_cost: Negative values (0.15%)
    neg_idx_cost = df.sample(frac=0.0015, random_state=105).index
    df.loc[neg_idx_cost, 'freight_cost'] = -1 * df.loc[neg_idx_cost, 'freight_cost']
    
    # Outliers in weight_kg: Typos (excessively high weight, 0.1%)
    outlier_idx_weight = df.sample(frac=0.001, random_state=106).index
    df.loc[outlier_idx_weight, 'weight_kg'] = np.random.uniform(2000000, 8000000, size=len(outlier_idx_weight)).round(2)
    
    # Chronological errors: actual_delivery_date before order_date (0.05% of rows, ~52 rows)
    chrono_err_idx = df[df['actual_delivery_date'].notnull()].sample(frac=0.0005, random_state=107).index
    for idx in chrono_err_idx:
        df.loc[idx, 'actual_delivery_date'] = df.loc[idx, 'order_date'] - datetime.timedelta(days=np.random.randint(15, 45))
        
    df.to_csv(DATA_RAW_PATH, index=False)
    print(f"Generated raw dataset with {len(df)} rows. Saved to {DATA_RAW_PATH}")
    return df

def clean_dataset(df_raw):
    """Executes data cleaning pipeline on raw dataframe."""
    print("--- Executing Data Cleaning Pipeline ---")
    df = df_raw.copy()
    
    # Convert dates to datetime
    df['order_date'] = pd.to_datetime(df['order_date'])
    df['promised_delivery_date'] = pd.to_datetime(df['promised_delivery_date'])
    df['actual_delivery_date'] = pd.to_datetime(df['actual_delivery_date'])
    
    # Log initial status
    print(f"Initial shape: {df.shape}")
    print(f"Initial null counts:\n{df.isnull().sum()}\n")
    
    # 1. Address chronological anomalies: actual_delivery_date < order_date
    chrono_violation = df['actual_delivery_date'] < df['order_date']
    violation_count = chrono_violation.sum()
    print(f"Chronological violations found (actual_delivery_date < order_date): {violation_count}")
    if violation_count > 0:
        df = df[~chrono_violation].copy()
        print(f"Removed {violation_count} rows. New shape: {df.shape}")
        
    # 2. Impute null customer_segment (use the mode, which is 'Manufacturing')
    mode_segment = df['customer_segment'].mode()[0]
    null_segment_count = df['customer_segment'].isnull().sum()
    print(f"Null customer_segment count: {null_segment_count}")
    if null_segment_count > 0:
        df['customer_segment'] = df['customer_segment'].fillna(mode_segment)
        print(f"Imputed missing customer_segment with mode: '{mode_segment}'")
        
    # 3. Clean weight outliers (weight_kg > 50,000 is physically impossible for industrial freight trucks)
    weight_outliers = df['weight_kg'] > 50000
    outlier_weight_count = weight_outliers.sum()
    print(f"Weight outliers (> 50,000 kg) found: {outlier_weight_count}")
    if outlier_weight_count > 0:
        median_weight = df.loc[~weight_outliers, 'weight_kg'].median()
        df.loc[weight_outliers, 'weight_kg'] = median_weight
        print(f"Replaced weight outliers with overall median weight: {median_weight} kg")
        
    # 4. Clean negative freight costs
    negative_costs = df['freight_cost'] < 0
    neg_cost_count = negative_costs.sum()
    print(f"Negative freight costs found: {neg_cost_count}")
    if neg_cost_count > 0:
        # Check if they are just sign-flipped
        df.loc[negative_costs, 'freight_cost'] = df.loc[negative_costs, 'freight_cost'].abs()
        print(f"Resolved negative freight costs by converting to absolute values.")
        
    # 5. Clean extreme freight_cost outliers (costs > 1,000,000 INR represent typos)
    extreme_costs = df['freight_cost'] > 1000000
    extreme_cost_count = extreme_costs.sum()
    print(f"Extreme freight cost outliers (> INR 1,000,000) found: {extreme_cost_count}")
    if extreme_cost_count > 0:
        # Group by shipping_mode and carrier to find typical median cost
        for mode in df['shipping_mode'].unique():
            for carrier in df['carrier'].unique():
                subset_idx = extreme_costs & (df['shipping_mode'] == mode) & (df['carrier'] == carrier)
                if subset_idx.any():
                    median_cost = df.loc[~extreme_costs & (df['shipping_mode'] == mode) & (df['carrier'] == carrier), 'freight_cost'].median()
                    # fallback if no matching rows
                    if pd.isnull(median_cost):
                        median_cost = df.loc[~extreme_costs, 'freight_cost'].median()
                    df.loc[subset_idx, 'freight_cost'] = median_cost
        print(f"Replaced extreme cost outliers with corresponding shipping mode + carrier median costs.")
        
    # 6. Impute null freight_cost values
    null_cost = df['freight_cost'].isnull()
    null_cost_count = null_cost.sum()
    print(f"Missing freight_cost records: {null_cost_count}")
    if null_cost_count > 0:
        for mode in df['shipping_mode'].unique():
            for carrier in df['carrier'].unique():
                subset_idx = null_cost & (df['shipping_mode'] == mode) & (df['carrier'] == carrier)
                if subset_idx.any():
                    median_cost = df.loc[df['freight_cost'].notnull() & (df['shipping_mode'] == mode) & (df['carrier'] == carrier), 'freight_cost'].median()
                    if pd.isnull(median_cost):
                        median_cost = df.loc[df['freight_cost'].notnull(), 'freight_cost'].median()
                    df.loc[subset_idx, 'freight_cost'] = median_cost
        print(f"Imputed missing freight_cost with corresponding shipping mode + carrier median costs.")
        
    # Final check
    print(f"\nFinal null counts:\n{df.isnull().sum()}")
    print(f"Note: Nulls in actual_delivery_date are preserved as they represent active, undelivered in-transit shipments.")
    
    # Save cleaned file
    df.to_csv(DATA_CLEANED_PATH, index=False)
    print(f"Cleaned dataset saved to {DATA_CLEANED_PATH}. Final size: {len(df)} rows.")
    return df

def load_data_to_sqlite(df, db_path=DB_PATH):
    """Loads cleaned dataframe into local SQLite database."""
    print("\n--- Loading cleaned data into SQLite database ---")
    conn = sqlite3.connect(db_path)
    df.to_sql('freight_orders', conn, if_exists='replace', index=False)
    conn.commit()
    print(f"Loaded {len(df)} rows into table 'freight_orders' in SQLite database '{db_path}'.")
    conn.close()

def run_sql_queries(db_path=DB_PATH):
    """Executes the raw SQL queries and prints formatted results and interpretations."""
    print("\n--- Executing Database Analysis & SQL Queries ---")
    conn = sqlite3.connect(db_path)
    
    # Query 1a: On-time delivery by carrier
    q1a_sql = """
    SELECT carrier,
           COUNT(*) as total_orders,
           SUM(CASE WHEN actual_delivery_date <= promised_delivery_date THEN 1 ELSE 0 END) as on_time_orders,
           ROUND(CAST(SUM(CASE WHEN actual_delivery_date <= promised_delivery_date THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as on_time_percentage
    FROM freight_orders
    WHERE actual_delivery_date IS NOT NULL
    GROUP BY carrier
    ORDER BY on_time_percentage DESC;
    """
    
    # Query 1b: On-time delivery by shipping mode
    q1b_sql = """
    SELECT shipping_mode,
           COUNT(*) as total_orders,
           SUM(CASE WHEN actual_delivery_date <= promised_delivery_date THEN 1 ELSE 0 END) as on_time_orders,
           ROUND(CAST(SUM(CASE WHEN actual_delivery_date <= promised_delivery_date THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as on_time_percentage
    FROM freight_orders
    WHERE actual_delivery_date IS NOT NULL
    GROUP BY shipping_mode
    ORDER BY on_time_percentage DESC;
    """
    
    # Query 2: Avg delay by origin-destination route
    q2_sql = """
    SELECT origin_region, destination_region,
           ROUND(AVG(julianday(actual_delivery_date) - julianday(promised_delivery_date)), 2) as avg_delay_days,
           COUNT(*) as total_orders
    FROM freight_orders
    WHERE actual_delivery_date IS NOT NULL
    GROUP BY origin_region, destination_region
    ORDER BY avg_delay_days DESC;
    """
    
    # Query 3: Freight cost as % of order value by carrier
    q3_sql = """
    SELECT carrier,
           ROUND(AVG((freight_cost / order_value) * 100), 2) as avg_freight_cost_pct,
           ROUND(AVG(freight_cost), 2) as avg_freight_cost_inr
    FROM freight_orders
    GROUP BY carrier
    ORDER BY avg_freight_cost_pct DESC;
    """
    
    # Query 4: Month-over-month volume trend
    q4_sql = """
    SELECT strftime('%Y-%m', order_date) as order_month,
           COUNT(*) as total_orders,
           ROUND(AVG(julianday(actual_delivery_date) - julianday(promised_delivery_date)), 2) as avg_delay_days
    FROM freight_orders
    GROUP BY order_month
    ORDER BY order_month;
    """
    
    # Query 5: CTE for top 5 worst routes
    q5_sql = """
    WITH route_delays AS (
        SELECT origin_region, destination_region,
               AVG(julianday(actual_delivery_date) - julianday(promised_delivery_date)) as avg_delay,
               COUNT(*) as total_orders
        FROM freight_orders
        WHERE actual_delivery_date IS NOT NULL
        GROUP BY origin_region, destination_region
    )
    SELECT origin_region, destination_region,
           ROUND(avg_delay, 2) as avg_delay_days,
           total_orders,
           RANK() OVER (ORDER BY avg_delay DESC) as delay_rank
    FROM route_delays
    ORDER BY delay_rank ASC
    LIMIT 5;
    """
    
    # Query 6: Window function - running average delay per carrier by month
    q6_sql = """
    WITH monthly_carrier_performance AS (
        SELECT carrier,
               strftime('%Y-%m', order_date) as order_month,
               AVG(julianday(actual_delivery_date) - julianday(promised_delivery_date)) as avg_delay
        FROM freight_orders
        WHERE actual_delivery_date IS NOT NULL
        GROUP BY carrier, order_month
    )
    SELECT carrier,
           order_month,
           ROUND(avg_delay, 2) as monthly_avg_delay,
           ROUND(AVG(avg_delay) OVER (
               PARTITION BY carrier
               ORDER BY order_month
               ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
           ), 2) as rolling_3m_avg_delay
    FROM monthly_carrier_performance
    ORDER BY carrier, order_month;
    """
    
    # Query 7: Highest avg freight cost relative to order value by customer segment
    q7_sql = """
    SELECT customer_segment,
           ROUND(AVG((freight_cost / order_value) * 100), 2) as avg_freight_cost_pct,
           ROUND(AVG(freight_cost), 2) as avg_freight_cost_inr,
           ROUND(AVG(order_value), 2) as avg_order_value_inr,
           COUNT(*) as total_orders
    FROM freight_orders
    GROUP BY customer_segment
    ORDER BY avg_freight_cost_pct DESC;
    """
    
    queries = [
        ("Query a(i): On-time Delivery % by Carrier", q1a_sql, 
         lambda df: f"Business Interpretation: {df.iloc[0]['carrier']} leads network reliability with {df.iloc[0]['on_time_percentage']}% on-time performance, while {df.iloc[-1]['carrier']} lags at {df.iloc[-1]['on_time_percentage']}%."),
        
        ("Query a(ii): On-time Delivery % by Shipping Mode", q1b_sql, 
         lambda df: f"Business Interpretation: {df.iloc[0]['shipping_mode']} exhibits the highest on-time rate ({df.iloc[0]['on_time_percentage']}%), whereas {df.iloc[-1]['shipping_mode']} has the lowest ({df.iloc[-1]['on_time_percentage']}%) due to long-haul complexities."),
        
        ("Query b: Average Delay by Route Corridor (Worst to Best)", q2_sql, 
         lambda df: f"Business Interpretation: The {df.iloc[0]['origin_region']} to {df.iloc[0]['destination_region']} corridor is the most delayed route, averaging {df.iloc[0]['avg_delay_days']} days of delay per shipment."),
        
        ("Query c: Freight Cost as % of Order Value by Carrier", q3_sql, 
         lambda df: f"Business Interpretation: {df.iloc[0]['carrier']} incurs the highest proportional cost at {df.iloc[0]['avg_freight_cost_pct']}% of order value, suggesting premium charging or inefficient route structures."),
        
        ("Query d: Month-over-Month Order Volume Trend", q4_sql, 
         lambda df: f"Business Interpretation: Network volume peaked in {df.loc[df['total_orders'].idxmax(), 'order_month']} with {df.loc[df['total_orders'].idxmax(), 'total_orders']} orders, matching seasonal shipping rushes."),
        
        ("Query e: Top 5 Worst Routes (Ranked via CTE & Window Rank)", q5_sql, 
         lambda df: f"Business Interpretation: Underperforming routes are topped by {df.iloc[0]['origin_region']}-{df.iloc[0]['destination_region']} (Rank {df.iloc[0]['delay_rank']}, delay {df.iloc[0]['avg_delay_days']} days), identifying key lanes requiring capacity reallocation."),
        
        ("Query f: Rolling 3-Month Average Delay per Carrier (Window Function)", q6_sql, 
         lambda df: f"Business Interpretation: Carrier {df.loc[df['rolling_3m_avg_delay'].idxmax(), 'carrier']} experienced the highest rolling 3-month delay of {df.loc[df['rolling_3m_avg_delay'].idxmax(), 'rolling_3m_avg_delay']} days in {df.loc[df['rolling_3m_avg_delay'].idxmax(), 'order_month']}, highlighting mid-year service degradation."),
        
        ("Query g: Customer Segment Freight Cost % of Order Value", q7_sql, 
         lambda df: f"Business Interpretation: The {df.iloc[0]['customer_segment']} segment carries the highest relative logistics expense at {df.iloc[0]['avg_freight_cost_pct']}% of product value.")
    ]
    
    results = {}
    for name, sql, interp in queries:
        print("\n" + "="*80)
        print(f"Executing: {name}")
        print("="*80)
        print(sql.strip())
        print("-" * 80)
        
        df_res = pd.read_sql_query(sql, conn)
        # Display the result
        print(df_res.to_string(index=False))
        print("-" * 80)
        
        # Display business interpretation
        business_text = interp(df_res)
        print(business_text)
        print("="*80 + "\n")
        
        results[name] = df_res
        
    conn.close()
    return results

def generate_dashboard(df_clean):
    """Generates the multi-panel analytics dashboard and saves individual panels."""
    print("\n--- Generating Visualization Panels & Dashboard ---")
    
    # Pre-processing data for plotting
    df_plot = df_clean.copy()
    df_plot['order_date'] = pd.to_datetime(df_plot['order_date'])
    df_plot['promised_delivery_date'] = pd.to_datetime(df_plot['promised_delivery_date'])
    df_plot['actual_delivery_date'] = pd.to_datetime(df_plot['actual_delivery_date'])
    
    df_delivered = df_plot[df_plot['actual_delivery_date'].notnull()].copy()
    df_delivered['on_time'] = df_delivered['actual_delivery_date'] <= df_delivered['promised_delivery_date']
    df_delivered['delay_days'] = (df_delivered['actual_delivery_date'] - df_delivered['promised_delivery_date']).dt.days
    df_delivered['status'] = df_delivered['on_time'].map({True: 'On-Time', False: 'Late'})
    
    # 1. On-time delivery % by carrier (horizontal bar)
    carrier_otd = df_delivered.groupby('carrier')['on_time'].mean().reset_index()
    carrier_otd['on_time_pct'] = (carrier_otd['on_time'] * 100).round(2)
    carrier_otd = carrier_otd.sort_values(by='on_time_pct', ascending=False).reset_index(drop=True)
    
    # 4. Monthly trends (dual line)
    df_plot['order_month'] = df_plot['order_date'].dt.strftime('%Y-%m')
    monthly_trend = df_plot.groupby('order_month').agg(
        total_orders=('order_id', 'count'),
        avg_delay=('actual_delivery_date', lambda x: (x - df_plot.loc[x.index, 'promised_delivery_date']).dt.days.mean())
    ).reset_index()
    monthly_trend = monthly_trend.sort_values(by='order_month').reset_index(drop=True)
    
    # 5. Route delay heatmap (origin vs destination)
    route_matrix = df_delivered.groupby(['origin_region', 'destination_region'])['delay_days'].mean().unstack()
    
    # 6. Customer segment on-time vs late (stacked bar)
    segment_status = df_delivered.groupby(['customer_segment', 'status']).size().unstack(fill_value=0)
    segment_status = segment_status.reindex(['Manufacturing', 'Retail', 'Automotive', 'Pharma'])

    # Set style
    sns.set_theme(style='whitegrid', context='talk')
    
    # Create combined dashboard
    fig, axes = plt.subplots(3, 2, figsize=(24, 26))
    fig.suptitle('Freight Operations Analytics Dashboard', fontsize=32, weight='bold', y=0.98)
    
    # Panel 1: Carrier On-Time Performance
    sns.barplot(x='on_time_pct', y='carrier', data=carrier_otd, ax=axes[0, 0], palette='viridis')
    axes[0, 0].set_title('1. On-Time Delivery Rate (%) by Carrier', weight='bold')
    axes[0, 0].set_xlabel('On-Time Percentage (%)')
    axes[0, 0].set_ylabel('Carrier')
    axes[0, 0].set_xlim(70, 85)
    for idx, row in carrier_otd.iterrows():
        axes[0, 0].text(row['on_time_pct'] - 1.5, idx, f"{row['on_time_pct']}%", color='white', ha='center', va='center', weight='bold')
        
    # Panel 2: Delay Distribution by Shipping Mode
    sns.boxplot(x='shipping_mode', y='delay_days', data=df_delivered, ax=axes[0, 1], showfliers=False, palette='Set2')
    axes[0, 1].set_title('2. Delivery Delay Distribution by Shipping Mode', weight='bold')
    axes[0, 1].set_xlabel('Shipping Mode')
    axes[0, 1].set_ylabel('Delay in Days (Actual - Promised)')
    
    # Panel 3: Freight Cost vs Order Value (Scatter plot)
    df_sample = df_plot.sample(n=2000, random_state=42)
    sns.scatterplot(x='order_value', y='freight_cost', hue='carrier', data=df_sample, ax=axes[1, 0], alpha=0.6, palette='tab10')
    x_line = np.linspace(0, 500000, 100)
    axes[1, 0].plot(x_line, 0.10 * x_line, color='red', linestyle='--', linewidth=2, label='10% Healthy Cost Threshold')
    axes[1, 0].set_title('3. Freight Cost vs Order Value (Sampled)', weight='bold')
    axes[1, 0].set_xlabel('Order Value (INR)')
    axes[1, 0].set_ylabel('Freight Cost (INR)')
    axes[1, 0].legend(fontsize=12, loc='upper left')
    
    # Panel 4: Monthly volume and delay trend (dual axis)
    ax4 = axes[1, 1]
    color = 'tab:blue'
    ax4.set_xlabel('Month')
    ax4.set_ylabel('Order Volume', color=color)
    sns.lineplot(x='order_month', y='total_orders', data=monthly_trend, marker='o', ax=ax4, color=color, linewidth=3)
    ax4.tick_params(axis='y', labelcolor=color)
    ax4.tick_params(axis='x', labelrotation=45)
    ax4.set_title('4. Monthly Order Volume & Average Delay Trend', weight='bold')
    
    ax4_twin = ax4.twinx()
    color2 = 'tab:orange'
    ax4_twin.set_ylabel('Avg Delay (Days)', color=color2)
    sns.lineplot(x='order_month', y='avg_delay', data=monthly_trend, marker='s', ax=ax4_twin, color=color2, linewidth=3)
    ax4_twin.tick_params(axis='y', labelcolor=color2)
    ax4_twin.grid(False)
    
    # Panel 5: Origin-Destination average delay heatmap
    sns.heatmap(route_matrix, annot=True, fmt=".2f", cmap='coolwarm', center=0, ax=axes[2, 0], cbar_kws={'label': 'Days'})
    axes[2, 0].set_title('5. Route Delay Heatmap (Average Delay in Days)', weight='bold')
    axes[2, 0].set_xlabel('Destination Region')
    axes[2, 0].set_ylabel('Origin Region')
    
    # Panel 6: Segment breakdown (stacked bar)
    segment_status.plot(kind='bar', stacked=True, ax=axes[2, 1], color=['salmon', 'mediumseagreen'])
    axes[2, 1].set_title('6. On-Time vs Late Deliveries by Customer Segment', weight='bold')
    axes[2, 1].set_xlabel('Customer Segment')
    axes[2, 1].set_ylabel('Order Count')
    axes[2, 1].legend(title='Status')
    axes[2, 1].tick_params(axis='x', labelrotation=0)
    
    plt.tight_layout()
    plt.savefig('dashboard.png', dpi=150)
    print("Combined dashboard image saved to dashboard.png")
    
    # Individual Panels Saving
    # Panel 1:
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    sns.barplot(x='on_time_pct', y='carrier', data=carrier_otd, ax=ax1, palette='viridis')
    ax1.set_title('On-Time Delivery Rate (%) by Carrier', weight='bold')
    ax1.set_xlabel('On-Time Percentage (%)')
    ax1.set_ylabel('Carrier')
    ax1.set_xlim(70, 85)
    for idx, row in carrier_otd.iterrows():
        ax1.text(row['on_time_pct'] - 1.0, idx, f"{row['on_time_pct']}%", color='white', ha='center', va='center', weight='bold')
    fig1.tight_layout()
    fig1.savefig('panel_1_carrier_otd.png', dpi=150)
    plt.close(fig1)
    
    # Panel 2:
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    sns.boxplot(x='shipping_mode', y='delay_days', data=df_delivered, ax=ax2, showfliers=False, palette='Set2')
    ax2.set_title('Delivery Delay Distribution by Shipping Mode', weight='bold')
    ax2.set_xlabel('Shipping Mode')
    ax2.set_ylabel('Delay in Days')
    fig2.tight_layout()
    fig2.savefig('panel_2_delay_distribution.png', dpi=150)
    plt.close(fig2)
    
    # Panel 3:
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    sns.scatterplot(x='order_value', y='freight_cost', hue='carrier', data=df_sample, ax=ax3, alpha=0.6, palette='tab10')
    ax3.plot(x_line, 0.10 * x_line, color='red', linestyle='--', linewidth=2, label='10% Healthy Cost Threshold')
    ax3.set_title('Freight Cost vs Order Value (Sampled)', weight='bold')
    ax3.set_xlabel('Order Value (INR)')
    ax3.set_ylabel('Freight Cost (INR)')
    ax3.legend(fontsize=10)
    fig3.tight_layout()
    fig3.savefig('panel_3_cost_vs_value.png', dpi=150)
    plt.close(fig3)
    
    # Panel 4:
    fig4, ax4 = plt.subplots(figsize=(10, 6))
    ax4.set_xlabel('Month')
    ax4.set_ylabel('Order Volume', color='tab:blue')
    sns.lineplot(x='order_month', y='total_orders', data=monthly_trend, marker='o', ax=ax4, color='tab:blue', linewidth=3)
    ax4.tick_params(axis='y', labelcolor='tab:blue')
    ax4.tick_params(axis='x', labelrotation=45)
    ax4_twin = ax4.twinx()
    ax4_twin.set_ylabel('Avg Delay (Days)', color='tab:orange')
    sns.lineplot(x='order_month', y='avg_delay', data=monthly_trend, marker='s', ax=ax4_twin, color='tab:orange', linewidth=3)
    ax4_twin.tick_params(axis='y', labelcolor='tab:orange')
    ax4_twin.grid(False)
    ax4.set_title('Monthly Order Volume & Average Delay Trend', weight='bold')
    fig4.tight_layout()
    fig4.savefig('panel_4_monthly_trends.png', dpi=150)
    plt.close(fig4)
    
    # Panel 5:
    fig5, ax5 = plt.subplots(figsize=(10, 8))
    sns.heatmap(route_matrix, annot=True, fmt=".2f", cmap='coolwarm', center=0, ax=ax5, cbar_kws={'label': 'Days'})
    ax5.set_title('Route Delay Heatmap (Average Delay in Days)', weight='bold')
    ax5.set_xlabel('Destination Region')
    ax5.set_ylabel('Origin Region')
    fig5.tight_layout()
    fig5.savefig('panel_5_route_heatmap.png', dpi=150)
    plt.close(fig5)
    
    # Panel 6:
    fig6, ax6 = plt.subplots(figsize=(10, 6))
    segment_status.plot(kind='bar', stacked=True, ax=ax6, color=['salmon', 'mediumseagreen'])
    ax6.set_title('On-Time vs Late Deliveries by Customer Segment', weight='bold')
    ax6.set_xlabel('Customer Segment')
    ax6.set_ylabel('Order Count')
    ax6.legend(title='Status')
    ax6.tick_params(axis='x', labelrotation=0)
    fig6.tight_layout()
    fig6.savefig('panel_6_segment_breakdown.png', dpi=150)
    plt.close(fig6)
    
    plt.close('all')
    print("Individual visualization panels saved as panel_1_... to panel_6_...")

if __name__ == "__main__":
    df_raw = generate_raw_dataset(105000)
    df_clean = clean_dataset(df_raw)
    load_data_to_sqlite(df_clean)
    sql_results = run_sql_queries()
    generate_dashboard(df_clean)


