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

if __name__ == "__main__":
    df_raw = generate_raw_dataset(105000)
    df_clean = clean_dataset(df_raw)
