"""
Pydantic models for the predictive analytics engine.

These models define the response shapes for all analytics predictions
including readmission risk, bed demand, no-show, stockout, and revenue forecasting.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field


class ReadmissionRisk(BaseModel):
    """
    Readmission risk prediction for a single patient.

    @param patient_id: UUID of the patient
    @param risk_score: Probability of readmission within 30 days (0.0-1.0)
    @param risk_level: Categorical risk level derived from score
    @param contributing_factors: Human-readable factors driving the score
    @param recommended_interventions: Suggested clinical interventions
    """

    patient_id: uuid.UUID
    risk_score: float = Field(ge=0.0, le=1.0, description="Probability of readmission (0-1)")
    risk_level: str = Field(
        pattern=r"^(low|moderate|high)$",
        description="Categorical risk level: low (<0.3), moderate (0.3-0.6), high (>0.6)",
    )
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Human-readable factors contributing to risk",
    )
    recommended_interventions: list[str] = Field(
        default_factory=list,
        description="Suggested interventions to reduce readmission risk",
    )


class BedDemandForecast(BaseModel):
    """
    Bed demand forecast for a single day in a specific department.

    @param date: Forecast date
    @param department: Department name or ID
    @param predicted_occupancy: Predicted occupancy percentage (0-100)
    @param confidence_interval: Lower and upper bounds of the prediction
    @param current_occupancy: Current occupancy percentage
    @param recommended_actions: Suggested operational actions
    """

    date: date
    department: str
    predicted_occupancy: float = Field(
        ge=0.0, le=100.0, description="Predicted bed occupancy percentage"
    )
    confidence_interval: tuple[float, float] = Field(
        description="Lower and upper bounds of prediction (percentage)"
    )
    current_occupancy: float = Field(
        ge=0.0, le=100.0, description="Current bed occupancy percentage"
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Suggested actions based on forecast",
    )


class NoShowPrediction(BaseModel):
    """
    No-show prediction for a single appointment.

    @param appointment_id: UUID of the appointment
    @param patient_id: UUID of the patient
    @param no_show_probability: Probability the patient will not show up (0-1)
    @param risk_factors: Human-readable factors driving the prediction
    @param recommended_action: Suggested action to mitigate no-show risk
    """

    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    no_show_probability: float = Field(
        ge=0.0, le=1.0, description="Probability of no-show (0-1)"
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Factors contributing to no-show risk",
    )
    recommended_action: str = Field(
        description="Suggested action to reduce no-show likelihood"
    )


class StockoutPrediction(BaseModel):
    """
    Stock-out risk prediction for a single inventory item.

    @param item_code: Inventory item code
    @param item_name: Human-readable item name
    @param current_stock: Current stock quantity on hand
    @param predicted_days_to_stockout: Estimated days until stock runs out
    @param daily_consumption_rate: Average units consumed per day
    @param reorder_quantity: Recommended quantity to reorder
    @param urgency: Urgency level based on days to stockout
    """

    item_code: str
    item_name: str
    current_stock: int = Field(ge=0, description="Current stock quantity")
    predicted_days_to_stockout: float = Field(
        ge=0.0, description="Estimated days until stockout"
    )
    daily_consumption_rate: float = Field(
        ge=0.0, description="Average daily consumption"
    )
    reorder_quantity: int = Field(ge=0, description="Recommended reorder quantity")
    urgency: str = Field(
        pattern=r"^(low|moderate|high|critical)$",
        description="Urgency: critical (<7d), high (<14d), moderate (<30d), low (>30d)",
    )


class RevenueForecast(BaseModel):
    """
    Revenue forecast for a single month.

    @param period: Month in YYYY-MM format
    @param predicted_revenue_cents: Predicted total revenue in KES cents
    @param confidence_lower: Lower bound of confidence interval (KES cents)
    @param confidence_upper: Upper bound of confidence interval (KES cents)
    @param components: Revenue breakdown by department/service type
    """

    period: str = Field(description="Month in YYYY-MM format")
    predicted_revenue_cents: int = Field(
        ge=0, description="Predicted revenue in KES cents"
    )
    confidence_lower: int = Field(
        ge=0, description="Lower confidence bound (KES cents)"
    )
    confidence_upper: int = Field(
        ge=0, description="Upper confidence bound (KES cents)"
    )
    components: dict[str, int] = Field(
        default_factory=dict,
        description="Revenue breakdown by department/service (KES cents)",
    )


class AnalyticsDashboard(BaseModel):
    """
    Combined analytics dashboard aggregating key predictions.

    @param top_readmission_risks: Patients with highest readmission risk
    @param bed_forecast_7d: Bed demand forecast for the next 7 days
    @param upcoming_no_shows: Appointments with highest no-show probability
    @param critical_stockouts: Inventory items at risk of stockout
    @param revenue_forecast_3m: Revenue forecast for the next 3 months
    @param generated_at: ISO 8601 timestamp when the dashboard was generated
    """

    top_readmission_risks: list[ReadmissionRisk] = Field(default_factory=list)
    bed_forecast_7d: list[BedDemandForecast] = Field(default_factory=list)
    upcoming_no_shows: list[NoShowPrediction] = Field(default_factory=list)
    critical_stockouts: list[StockoutPrediction] = Field(default_factory=list)
    revenue_forecast_3m: list[RevenueForecast] = Field(default_factory=list)
    generated_at: str = Field(description="ISO 8601 timestamp of generation")
