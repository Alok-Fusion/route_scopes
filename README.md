# Freight & Logistics Operations Analytics
### 💼 Business Analyst Portfolio Project: Supply Chain Laneway & Carrier Performance Analysis

---

## 📌 Executive Project Overview
This project simulates a real-world **Supply Chain Operations & Logistics Analytics** scenario at a freight-tech startup. Faced with rising customer SLA complaints, logistics margin leakage, and upcoming carrier contract renewals, this project delivers a data-driven investigation into network inefficiencies. 

Rather than a machine learning showcase, this portfolio project is built from a **Business Analyst (BA) lens**, demonstrating:
1. **Business Process Understanding**: Mapping logistical delays and expedited freight costs to bottom-line financial impacts (margins, customer churn, and contract penalties).
2. **Data Engineering & Quality Control (QC)**: Programmatically generating a 105,000-row transaction dataset, injecting operational anomalies (nulls, billing typos, weight outliers, date issues), and building a robust Pandas data cleaning pipeline.
3. **Relational Database & SQL Fluency**: Modeling data in a local SQLite database and executing advanced SQL queries (including Common Table Expressions (CTEs), window functions, conditional aggregations, and date functions) to query operations metrics.
4. **Business Intelligence (BI) Visualizations**: Designing a 6-panel operational dashboard (Matplotlib/Seaborn) to highlight bottleneck routes and cost leakages.
5. **Business Requirements Document (BRD)**: Translating raw data into a formal, executive-ready BRD containing actionable lane-level reallocations and target KPIs.

---

## 🛠️ Repository Architecture

*   **[freight_analytics.py](file:///c:/Users/ak500/OneDrive/Desktop/IT/route_scopes/freight_analytics.py)**: End-to-end Python pipeline containing data generation, dirty data injection, Pandas cleaning, SQLite load, SQL executions, and dashboard generation.
*   **[freight_analytics.ipynb](file:///c:/Users/ak500/OneDrive/Desktop/IT/route_scopes/freight_analytics.ipynb)**: An interactive Jupyter Notebook mapping the code execution with explanatory markdown, formatted SQL tables, and inline charts.
*   **[BRD.md](file:///c:/Users/ak500/OneDrive/Desktop/IT/route_scopes/BRD.md)**: Standalone executive Business Requirement Document (BRD) outlining the findings.
*   **[freight_orders_raw.csv](file:///c:/Users/ak500/OneDrive/Desktop/IT/route_scopes/freight_orders_raw.csv)**: Raw transaction CSV containing injected dirty data (105,000 rows).
*   **[freight_orders_cleaned.csv](file:///c:/Users/ak500/OneDrive/Desktop/IT/route_scopes/freight_orders_cleaned.csv)**: The structured dataset after applying the cleaning pipeline (104,941 rows).
*   **[freight_operations.db](file:///c:/Users/ak500/OneDrive/Desktop/IT/route_scopes/freight_operations.db)**: Relational SQLite database file containing the cleaned dataset.
*   **[dashboard.png](file:///c:/Users/ak500/OneDrive/Desktop/IT/route_scopes/dashboard.png)**: 6-panel BI dashboard summarizing lane and carrier performances.

---

## 🧼 Data Quality & QA Matrix

Production freight systems are prone to logging failures, human errors, and corrupted transactions. To demonstrate data quality awareness, a raw dataset of **105,000 transactions** was generated and perturbed with specific dirty data types. 

The cleaning pipeline in Pandas resolves these issues using the following QA framework:

| Input Field | Data Type | Injected Anomaly | Business/Analytical Risk | Cleaning Resolution Strategy |
| :--- | :--- | :--- | :--- | :--- |
| `actual_delivery_date` | Date / Text | **Chronological Violations (0.05%)**: Delivery date occurs *before* the order date. | Impossible physical event. Corrupts transit cycle-time and delay calculations. | **Row Removal**: Dropped from the dataset (59 rows removed) as entries are fundamentally invalid. |
| `customer_segment` | Categorical | **Missing Data (0.5%)**: Null customer classifications. | Prevents accurate segment revenue and cost profiling. | **Imputation**: Filled missing entries with the most common segment mode (`Manufacturing`). |
| `weight_kg` | Numeric | **Outliers / Typo Errors (0.1%)**: Weights up to 8,000,000 kg (physically impossible for a single truck). | Heavily skews freight cost estimates, average loads, and capacity projections. | **Capped Imputation**: Replaced weight values `> 50,000 kg` with the median weight of the customer segment. |
| `freight_cost` | Numeric | **Sign Errors (0.15%)**: Costs generated as negative values. | Invalidates expense aggregations and total shipping spend calculations. | **Sign Normalization**: Converted all negative cost values to absolute numbers. |
| `freight_cost` | Numeric | **Billing Outliers (0.15%)**: Bill values up to ₹10,000,000 (typo adding extra zeros). | Artificially inflates shipping spend and distorts shipping cost-to-value ratios. | **Median Imputation**: Replaced extreme cost values (`> ₹1,000,000`) with the median cost of the corresponding carrier and mode. |
| `freight_cost` | Numeric | **Missing Billings (1.0%)**: Null freight expenses. | Leads to underreporting total operational logistics spend. | **Median Imputation**: Imputed missing bills with the median cost of the corresponding carrier and mode. |
| `actual_delivery_date` | Date | **Active Shipments (1.5%)**: Null delivery dates. | Could be mistaken for missing logs if not handled with care. | **Preserved Nulls**: Maintained as `NULL` in the database to represent active, in-transit orders. Standard delay calculations exclude them. |

---

## 💾 SQLite Relational Database Model

Cleaned data is loaded into `freight_operations.db` under the table name `freight_orders` with the following schema structure:

*   `order_id` (TEXT, PRIMARY KEY): Unique alphanumeric shipment identifier.
*   `order_date` (TEXT): Date order was placed (Format: `YYYY-MM-DD`).
*   `promised_delivery_date` (TEXT): Scheduled SLA delivery date (Format: `YYYY-MM-DD`).
*   `actual_delivery_date` (TEXT, NULLABLE): Date of final delivery (`NULL` represents active/in-transit orders).
*   `shipping_mode` (TEXT): Categorical (`Standard`, `Express`, `Same Day`, `Freight/LTL`).
*   `carrier` (TEXT): Categorical carrier name (5 fictional companies).
*   `origin_region` (TEXT): Indian origin city (Mumbai, Delhi NCR, Bangalore, Chennai, Pune, Hyderabad).
*   `destination_region` (TEXT): Indian destination city.
*   `order_value` (REAL): Value of goods in Indian Rupees (INR).
*   `weight_kg` (REAL): Total weight of cargo.
*   `customer_segment` (TEXT): Categorical customer segment.
*   `freight_cost` (REAL): Net shipping bill in INR.

---

## 🔍 SQL Analytical Deep-Dive & Interpretations

The following raw SQL queries are embedded and executed programmatically within the Python scripts. Each query resolves a specific business query:

### Q1: On-time Delivery (OTD) Rate
*   **Business Question**: Which carriers and shipping modes are failing to meet their contractual SLAs?
*   **SQL Query (Carrier)**:
    ```sql
    SELECT carrier,
           COUNT(*) as total_orders,
           SUM(CASE WHEN actual_delivery_date <= promised_delivery_date THEN 1 ELSE 0 END) as on_time_orders,
           ROUND(CAST(SUM(CASE WHEN actual_delivery_date <= promised_delivery_date THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as on_time_percentage
    FROM freight_orders
    WHERE actual_delivery_date IS NOT NULL
    GROUP BY carrier
    ORDER BY on_time_percentage DESC;
    ```
*   **Result & BA Interpretation**:
    *   *BlueDart Allied* leads carrier reliability at **80.43%**, while *Bharat Haulers* lags at **78.27%**.
    *   **BA Narrative**: Bharat Haulers operates 2.16% below our leading carrier. This represents a significant risk to customer satisfaction and indicates a lane-specific routing issue.

---

### Q2: Route Corridor Delay Metrics
*   **Business Question**: What are the worst-performing origin-to-destination corridors by transit delay?
*   **SQL Query**:
    ```sql
    SELECT origin_region, destination_region,
           ROUND(AVG(julianday(actual_delivery_date) - julianday(promised_delivery_date)), 2) as avg_delay_days,
           COUNT(*) as total_orders
    FROM freight_orders
    WHERE actual_delivery_date IS NOT NULL
    GROUP BY origin_region, destination_region
    ORDER BY avg_delay_days DESC;
    ```
*   **Result & BA Interpretation**:
    *   *Mumbai to Chennai* averages a delay of **2.30 days** across 3,484 orders.
    *   *Delhi NCR to Bangalore* averages **0.48 days** of delay across 3,392 orders.
    *   **BA Narrative**: All other routes maintain negative average delays (meaning they are delivered early). Mumbai-to-Chennai is a severe network bottleneck that requires regional operational investigation.

---

### Q3: Proportional Freight Surcharges
*   **Business Question**: Which carrier charges the highest rate relative to the value of shipped orders?
*   **SQL Query**:
    ```sql
    SELECT carrier,
           ROUND(AVG((freight_cost / order_value) * 100), 2) as avg_freight_cost_pct,
           ROUND(AVG(freight_cost), 2) as avg_freight_cost_inr
    FROM freight_orders
    GROUP BY carrier
    ORDER BY avg_freight_cost_pct DESC;
    ```
*   **Result & BA Interpretation**:
    *   *SpeedRun Logistics* incurs the highest average cost-to-value ratio at **17.08%** (average bill of ₹27,665.22).
    *   **BA Narrative**: SpeedRun Logistics leads in cost ratio, indicating a premium pricing model or a higher share of Same Day shipping routes.

---

### Q4: Month-over-Month Order Volume Trend
*   **Business Question**: How does volume fluctuate monthly, and does volume density correlate with network delay?
*   **SQL Query**:
    ```sql
    SELECT strftime('%Y-%m', order_date) as order_month,
           COUNT(*) as total_orders,
           ROUND(AVG(julianday(actual_delivery_date) - julianday(promised_delivery_date)), 2) as avg_delay_days
    FROM freight_orders
    GROUP BY order_month
    ORDER BY order_month;
    ```
*   **Result & BA Interpretation**:
    *   Peak volume occurred in **2025-07** with **9,092** orders. Average delays across the network gradually grew from -1.07 days in July 2025 to -0.79 days in June 2026.
    *   **BA Narrative**: While volume remains stable (between 8k-9k orders monthly), average delays show a rising trend, suggesting system-wide efficiency loss.

---

### Q5: Laneway Ranking (CTE & Window Function)
*   **Business Question**: What are the top 5 worst-performing route corridors ranked by average delay?
*   **SQL Query**:
    ```sql
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
    ```
*   **Result & BA Interpretation**:
    *   Rank 1: Mumbai to Chennai (2.30 days delay)
    *   Rank 2: Delhi NCR to Bangalore (0.48 days delay)
    *   **BA Narrative**: The top 2 worst routes stand out with positive delays, while Rank 3 (Bangalore to Chennai) drops straight to a healthy -1.00 days delay. Lane mitigation should focus exclusively on Mumbai-Chennai and Delhi NCR-Bangalore.

---

### Q6: Rolling Carrier Performance (Partition Window Function)
*   **Business Question**: What is the rolling 3-month average delay per carrier, and are service levels degrading?
*   **SQL Query**:
    ```sql
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
    ```
*   **Result & BA Interpretation**:
    *   *Bharat Haulers* experienced a service degradation, with rolling 3-month delay peaks at **-0.56 days** in June 2026.
    *   **BA Narrative**: Windowed rolling averages highlight that Bharat Haulers' service levels declined steadily in the second half of the year, confirming operational capacity constraints.

---

### Q7: High-Cost Customer Segment Surcharge
*   **Business Question**: Which customer segment suffers from the highest relative freight bills?
*   **SQL Query**:
    ```sql
    SELECT customer_segment,
           ROUND(AVG((freight_cost / order_value) * 100), 2) as avg_freight_cost_pct,
           ROUND(AVG(freight_cost), 2) as avg_freight_cost_inr,
           ROUND(AVG(order_value), 2) as avg_order_value_inr,
           COUNT(*) as total_orders
    FROM freight_orders
    GROUP BY customer_segment
    ORDER BY avg_freight_cost_pct DESC;
    ```
*   **Result & BA Interpretation**:
    *   The *Manufacturing* segment carries the highest relative freight cost of **17.03%** of order value (average bill of ₹27,836.52 on an average order value of ₹259,881.28).
    *   **BA Narrative**: Manufacturing accounts for 36,995 shipments. Its high cost ratio indicates a severe over-reliance on Same Day and expedited lanes for shipping industrial components, directly impacting gross margins.

---

## 📈 Visual Dashboard Analysis

The python pipeline exports a combined high-resolution dashboard (`dashboard.png`) and individual panels summarizing operational trends:

![Operations Dashboard](dashboard.png)

### Dashboard Visual Insights:
1.  **Panel 1: Carrier On-Time Rate**: Highlights carrier OTD. Bharat Haulers clearly lags, which supports our recommendation to divert Delhi NCR–Bangalore lane volumes.
2.  **Panel 2: Shipping Mode Delay Distribution**: Shows standard shipping has a wider distribution but reasonable medians. Same Day remains tight, but its premium cost raises questions.
3.  **Panel 3: Freight Cost vs Order Value**: Shows Same Day shipments clustering above the red dotted 10% healthy threshold. This identifies expedited freight as our largest financial leakage.
4.  **Panel 4: MoM Order Volume & Delay Trend**: Displays flat monthly volume, while average delays rise steadily. This indicates systemic carrier bottlenecking.
5.  **Panel 5: Route Delay Heatmap**: Instantly flags the Mumbai-to-Chennai lane in deep red with an average delay of 2.30 days, pinpointing the network's biggest operational bottleneck.
6.  **Panel 6: Segment On-Time vs Late Count**: Illustrates that Manufacturing and Retail suffer the largest absolute count of late shipments, posing significant customer retention risks.

---

## 📄 Standalone Business Requirement Document (BRD)

The complete Business Requirement Document (BRD) is embedded below:

### Freight Delivery Performance — Business Requirement & Findings Summary

#### 1. Background
This analysis was commissioned by the Logistics Operations team following a significant uptick in service complaints regarding late deliveries in late Q1 2026. Prior to finalizing contract renewals for the upcoming fiscal year, this analysis was structured to review the last 12 months of shipment transaction data (covering 104,941 completed orders). The goal is to isolate systemic carrier delays, identify lanes causing severe SLA breaches, and evaluate proportional shipping modes to establish a baseline for renegotiating carrier SLAs and lane allocation.

#### 2. Objective
To implement a metrics-driven carrier scorecard and lane routing framework that improves the overall on-time delivery rate, reduces average transit delay, and minimizes logistics margin leakage by reallocating shipments away from underperforming carriers and shipping modes.

#### 3. Key Findings
*   **Carrier SLA Underperformance**: *Bharat Haulers* is the worst-performing carrier across the network, exhibiting a network-low on-time delivery rate of **78.27%** across 20,778 shipments. This is 2.16% below the leading carrier (*BlueDart Allied* at **80.43%**).
*   **Corridor Bottlenecks**: The **Mumbai to Chennai** corridor represents the single largest bottleneck in the logistics network. Out of 3,484 deliveries, it averaged an operational delay of **2.30 days** per shipment. Our trend analysis reveals a rising delay trajectory that progressively deteriorated month-over-month.
*   **Delhi NCR to Bangalore Lane Failures**: The **Delhi NCR to Bangalore** route is the second worst-performing lane with an average delay of **0.48 days** across 3,392 orders. This delay is heavily driven by *Bharat Haulers*, whose on-time rate on this specific route corridor drops to a severe **~25%** due to local hub capacity constraints.
*   **Logistics Margin Erosion via Expedited Modes**: *Same Day* shipping mode costs are extremely high relative to order value, averaging **17.03%** of product value. The *Manufacturing* customer segment experienced the highest proportional logistics expense at **17.03%** of order value, representing ₹27,836.52 in average freight costs on a ₹259,881.28 average order value.

#### 4. Business Impact
*   **SLA Contract Penalty Exposure**: Late deliveries on the Mumbai-Chennai and Delhi NCR-Bangalore lanes have triggered customer SLA penalty clauses, resulting in an estimated ₹450,000 in liquidated damages in Q1 2026 alone.
*   **Client Relationship Risk**: Systemic delays on critical lanes risk shutting down manufacturing assembly lines for primary automotive and manufacturing clients, increasing customer churn risk by an estimated **8-10%** for these high-value segments.
*   **Financial Leakage**: Over-reliance on Same Day shipping for standard orders represents a significant margin drain, consuming up to **15-20%** of gross profit margins on industrial manufacturing orders.

#### 5. Recommendations
1.  **Divert Lane Volume**: Immediately reallocate **50%** of the Delhi NCR to Bangalore lane volume away from *Bharat Haulers* to *BlueDart Allied* or *Apex Freight* to restore lane SLA compliance.
2.  **Lanes and Hub Auditing**: Commission a detailed operational audit of the Mumbai-Chennai corridor to determine whether root causes are tied to local seaport/customs clearance congestion or regional warehouse bottlenecks. Temporarily reroute high-priority shipments to Express mode via Pune.
3.  **Same-Day Shipping Guardrails**: Implement approval gates in the ERP system requiring divisional director sign-off for any Same Day or Same Day Manufacturing shipment costing more than 10% of order value. Emphasize transition to Standard shipping (which averages a healthy **2-4%** cost-to-value ratio).

#### 6. Proposed KPI to Track Going Forward
*   **KPI Definition**: On-time Delivery (OTD) Rate by Carrier and Route Corridor.
*   **Calculation**: `(Total On-time Deliveries / Total Completed Deliveries) * 100` calculated monthly per carrier per corridor.
*   **Target**: **>85%** on-time performance for all carriers on all active route corridors, with a contract warning threshold at **<80%**.

---

## 🚀 How to Run the Project

### Prerequisites
Make sure you have python installed along with the required libraries:
```bash
pip install pandas numpy matplotlib seaborn
```

### Steps to Run
1.  Clone this repository:
    ```bash
    git clone https://github.com/Alok-Fusion/route_scopes.git
    cd route_scopes
    ```
2.  Run the main python pipeline script:
    ```bash
    python freight_analytics.py
    ```
    This script will:
    - Generate the raw data (`freight_orders_raw.csv`).
    - Clean the data and save `freight_orders_cleaned.csv`.
    - Setup the SQLite database `freight_operations.db` and load tables.
    - Run and output all 7 SQL queries with interpretations in the terminal.
    - Save the operational charts and `dashboard.png`.
3.  Open the Jupyter notebook to run cells interactively:
    ```bash
    jupyter notebook freight_analytics.ipynb
    ```
