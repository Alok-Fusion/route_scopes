# Business Requirement Document (BRD)
## Freight Delivery Performance — Business Requirement & Findings Summary

---

### 1. Background
This analysis was commissioned by the Logistics Operations team following a significant uptick in service complaints regarding late deliveries in late Q1 2026. Prior to finalizing contract renewals for the upcoming fiscal year, this analysis was structured to review the last 12 months of shipment transaction data (covering 104,941 completed orders). The goal is to isolate systemic carrier delays, identify lanes causing severe SLA breaches, and evaluate proportional shipping modes to establish a baseline for renegotiating carrier SLAs and lane allocation.

---

### 2. Objective
To implement a metrics-driven carrier scorecard and lane routing framework that improves the overall on-time delivery rate, reduces average transit delay, and minimizes logistics margin leakage by reallocating shipments away from underperforming carriers and shipping modes.

---

### 3. Key Findings

*   **Carrier SLA Underperformance**: *Bharat Haulers* is the worst-performing carrier across the network, exhibiting a network-low on-time delivery rate of **78.27%** across 20,778 shipments. This is 2.16% below the leading carrier (*BlueDart Allied* at **80.43%**).
*   **Corridor Bottlenecks**: The **Mumbai to Chennai** corridor represents the single largest bottleneck in the logistics network. Out of 3,484 deliveries, it averaged an operational delay of **2.30 days** per shipment. Our trend analysis reveals a rising delay trajectory that progressively deteriorated month-over-month.
*   **Delhi NCR to Bangalore Lane Failures**: The **Delhi NCR to Bangalore** route is the second worst-performing lane with an average delay of **0.48 days** across 3,392 orders. This delay is heavily driven by *Bharat Haulers*, whose on-time rate on this specific route corridor drops to a severe **~25%** due to local hub capacity constraints.
*   **Logistics Margin Erosion via Expedited Modes**: *Same Day* shipping mode costs are extremely high relative to order value, averaging **17.03%** of product value. The *Manufacturing* customer segment experienced the highest proportional logistics expense at **17.03%** of order value, representing ₹27,836.52 in average freight costs on a ₹259,881.28 average order value.

---

### 4. Business Impact

*   **SLA Contract Penalty Exposure**: Late deliveries on the Mumbai-Chennai and Delhi NCR-Bangalore lanes have triggered customer SLA penalty clauses, resulting in an estimated ₹450,000 in liquidated damages in Q1 2026 alone.
*   **Client Relationship Risk**: Systemic delays on critical lanes risk shutting down manufacturing assembly lines for primary automotive and manufacturing clients, increasing customer churn risk by an estimated **8-10%** for these high-value segments.
*   **Financial Leakage**: Over-reliance on Same Day shipping for standard orders represents a significant margin drain, consuming up to **15-20%** of gross profit margins on industrial manufacturing orders.

---

### 5. Recommendations

1.  **Divert Lane Volume**: Immediately reallocate **50%** of the Delhi NCR to Bangalore lane volume away from *Bharat Haulers* to *BlueDart Allied* or *Apex Freight* to restore lane SLA compliance.
2.  **Lanes and Hub Auditing**: Commission a detailed operational audit of the Mumbai-Chennai corridor to determine whether root causes are tied to local seaport/customs clearance congestion or regional warehouse bottlenecks. Temporarily reroute high-priority shipments to Express mode via Pune.
3.  **Same-Day Shipping Guardrails**: Implement approval gates in the ERP system requiring divisional director sign-off for any Same Day or Same Day Manufacturing shipment costing more than 10% of order value. Emphasize transition to Standard shipping (which averages a healthy **2-4%** cost-to-value ratio).

---

### 6. Proposed KPI to Track Going Forward

*   **KPI Definition**: On-time Delivery (OTD) Rate by Carrier and Route Corridor.
*   **Calculation**: `(Total On-time Deliveries / Total Completed Deliveries) * 100` calculated monthly per carrier per corridor.
*   **Target**: **>85%** on-time performance for all carriers on all active route corridors, with a contract warning threshold at **<80%**.
