// ── Predictive Analytics Types ──────────────────────────────────────────────

/** Risk level for readmission prediction. */
export type RiskLevel = "low" | "medium" | "high" | "critical";

/** Urgency level for stockout predictions. */
export type StockoutUrgency = "low" | "medium" | "high" | "critical";

/** Recommended action for no-show predictions. */
export type NoShowAction =
  | "standard_reminder"
  | "phone_call"
  | "double_book"
  | "reschedule";

// ── Readmission Risk ────────────────────────────────────────────────────────

/** Contributing factor to readmission risk. */
export interface ContributingFactor {
  /** Factor name (e.g., "prior_admissions", "chronic_condition") */
  factor: string;
  /** Impact weight 0.0–1.0 */
  weight: number;
  /** Human-readable description */
  description: string;
}

/** AI-predicted readmission risk for a patient. */
export interface ReadmissionRisk {
  /** Patient UUID */
  patient_id: string;
  /** Patient name for display */
  patient_name: string;
  /** Risk score 0.0–1.0 */
  risk_score: number;
  /** Categorical risk level */
  risk_level: RiskLevel;
  /** Factors contributing to the risk score */
  contributing_factors: ContributingFactor[];
  /** AI-recommended interventions to reduce readmission */
  recommended_interventions: string[];
}

// ── Bed Demand Forecast ─────────────────────────────────────────────────────

/** Forecasted bed occupancy for a department on a given date. */
export interface BedDemandForecast {
  /** ISO 8601 date string */
  date: string;
  /** Department name */
  department: string;
  /** Predicted occupancy percentage 0–100 */
  predicted_occupancy: number;
  /** Lower bound of confidence interval */
  confidence_lower: number;
  /** Upper bound of confidence interval */
  confidence_upper: number;
  /** Current real-time occupancy percentage 0–100 */
  current_occupancy: number;
  /** AI-recommended actions based on forecast */
  recommended_actions: string[];
}

// ── No-Show Prediction ──────────────────────────────────────────────────────

/** AI-predicted no-show probability for an appointment. */
export interface NoShowPrediction {
  /** Appointment UUID */
  appointment_id: string;
  /** Patient UUID */
  patient_id: string;
  /** Patient name for display */
  patient_name: string;
  /** No-show probability 0.0–1.0 */
  no_show_probability: number;
  /** Factors contributing to no-show risk */
  risk_factors: string[];
  /** Recommended action to mitigate no-show */
  recommended_action: NoShowAction;
}

// ── Stockout Prediction ─────────────────────────────────────────────────────

/** AI-predicted stockout for an inventory item. */
export interface StockoutPrediction {
  /** Inventory item code */
  item_code: string;
  /** Human-readable item name */
  item_name: string;
  /** Current stock quantity */
  current_stock: number;
  /** Predicted days until stockout */
  predicted_days_to_stockout: number;
  /** Average daily consumption rate */
  daily_consumption_rate: number;
  /** Recommended reorder quantity */
  reorder_quantity: number;
  /** Urgency classification */
  urgency: StockoutUrgency;
}

// ── Revenue Forecast ────────────────────────────────────────────────────────

/** Revenue component breakdown. */
export interface RevenueComponent {
  /** Component name (e.g., "consultation", "pharmacy", "lab") */
  name: string;
  /** Predicted revenue in KES cents */
  amount_cents: number;
}

/** AI-predicted revenue for a future period. */
export interface RevenueForecast {
  /** Period label (e.g., "2026-05", "2026-06") */
  period: string;
  /** Predicted total revenue in KES cents */
  predicted_revenue_cents: number;
  /** Lower bound of confidence interval in KES cents */
  confidence_lower: number;
  /** Upper bound of confidence interval in KES cents */
  confidence_upper: number;
  /** Revenue breakdown by component */
  components: RevenueComponent[];
}

// ── Analytics Dashboard ─────────────────────────────────────────────────────

/** Aggregated predictive analytics dashboard data. */
export interface AnalyticsDashboard {
  /** High-risk readmission patients */
  readmission_risks: ReadmissionRisk[];
  /** Bed demand forecasts for upcoming days */
  bed_forecasts: BedDemandForecast[];
  /** Items predicted to stock out soon */
  stockout_predictions: StockoutPrediction[];
  /** Revenue forecasts for upcoming months */
  revenue_forecasts: RevenueForecast[];
  /** Appointment no-show predictions */
  no_show_predictions: NoShowPrediction[];
  /** ISO 8601 timestamp when dashboard data was generated */
  generated_at: string;
}
