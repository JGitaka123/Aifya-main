from app.models.appointment import Appointment, DoctorSchedule
from app.models.auth_account import AuthAccount
from app.models.base import AuditMixin, EventBase
from app.models.billing import Invoice, InvoiceItem, Payment
from app.models.clinical_trial import (
    ClinicalTrial,
    TrialAdverseEvent,
    TrialAIScreening,
    TrialParticipant,
    TrialParticipantVisit,
    TrialVisitSchedule,
)
from app.models.communication import (
    CommunicationPreference,
    PatientMessage,
)
from app.models.dental import DentalChart, DentalTreatmentPlan, DentalVisit
from app.models.diagnosis import Diagnosis
from app.models.emergency import EmergencyVisit
from app.models.encounter import ClinicalNote, Encounter
from app.models.facility import Facility
from app.models.finance import (
    Account,
    AccountingPeriod,
    BankStatement,
    Budget,
    FinanceAuditLog,
    FixedAsset,
    IdempotencyKey,
    InsuranceClaimFinance,
    InventoryLot,
    OpeningBalance,
    PostingRule,
    RecurringTemplate,
    TaxRate,
    Transaction,
    TransactionEntry,
)
from app.models.hr import Attendance, LeaveRequest, Shift, ShiftAssignment, StaffProfile
from app.models.insurance import (
    InsuranceClaim,
    InsuranceScheme,
    PatientInsurance,
    PreAuthorization,
)
from app.models.inventory import (
    InventoryItem,
    InventoryTransaction,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from app.models.ipd import Admission, Bed, NursingNote, Ward
from app.models.lab import LabOrder, LabResult
from app.models.licensing import (
    AppUpdate,
    FacilityLicense,
    FacilityUpdateStatus,
    UsageTelemetry,
)
from app.models.mch import (
    ANCProfile,
    ANCVisit,
    ChildRecord,
    DeliveryRecord,
    Immunization,
)
from app.models.mpesa import MpesaStkRequest
from app.models.patient import Patient
from app.models.payroll import (
    Employee,
    EmployeeSalary,
    NSSFTier,
    PAYEBand,
    PayrollLineItem,
    PayrollRun,
    StatutoryRate,
)
from app.models.payroll_extra import (
    DisciplinaryCase,
    EmployeeDeduction,
    ExitChecklist,
    GrievanceCase,
    LeaveType,
    PayrollLeaveRequest,
    PerformanceReview,
    TrainingAttendance,
    TrainingProgram,
)
from app.models.pharmacy import (
    Dispensing,
    PharmacyBatch,
    PharmacyItem,
    StockTransaction,
)
from app.models.prescription import Prescription
from app.models.radiology import ImagingOrder, ImagingResult
from app.models.referral import Referral
from app.models.referral_template import ReferralTemplate
from app.models.report import GeneratedReport, ReportTemplate
from app.models.sms import SmsCampaign, SmsDeliveryLog
from app.models.staff import Department, Staff
from app.models.theatre import OperatingTheatre, SurgicalCase
from app.models.vital import VitalSign

__all__ = [
    "ANCProfile",
    "ANCVisit",
    # Finance
    "Account",
    "AccountingPeriod",
    "Admission",
    "AppUpdate",
    "Appointment",
    "Attendance",
    "AuditMixin",
    "AuthAccount",
    "BankStatement",
    "Bed",
    "Budget",
    "ChildRecord",
    "ClinicalNote",
    "ClinicalTrial",
    "DeliveryRecord",
    "DentalChart",
    "DentalTreatmentPlan",
    "DentalVisit",
    "Department",
    "Diagnosis",
    # Payroll extra
    "DisciplinaryCase",
    "Dispensing",
    "DoctorSchedule",
    "EmergencyVisit",
    # Payroll
    "Employee",
    "EmployeeDeduction",
    "EmployeeSalary",
    "Encounter",
    "EventBase",
    "ExitChecklist",
    "Facility",
    "FacilityLicense",
    "FacilityUpdateStatus",
    "FinanceAuditLog",
    "FixedAsset",
    "GeneratedReport",
    "GrievanceCase",
    "IdempotencyKey",
    "ImagingOrder",
    "ImagingResult",
    "Immunization",
    "InsuranceClaim",
    "InsuranceClaimFinance",
    "InsuranceScheme",
    "InventoryItem",
    "InventoryLot",
    "InventoryTransaction",
    "Invoice",
    "InvoiceItem",
    "LabOrder",
    "LabResult",
    "LeaveRequest",
    "LeaveType",
    "MpesaStkRequest",
    "NSSFTier",
    "NursingNote",
    "OpeningBalance",
    "OperatingTheatre",
    "PAYEBand",
    "Patient",
    "PatientInsurance",
    "Payment",
    "PayrollLeaveRequest",
    "PayrollLineItem",
    "PayrollRun",
    "PerformanceReview",
    "PharmacyBatch",
    "PharmacyItem",
    "PostingRule",
    "PreAuthorization",
    "Prescription",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "RecurringTemplate",
    "Referral",
    "ReferralTemplate",
    "ReportTemplate",
    "Shift",
    "ShiftAssignment",
    "SmsCampaign",
    "SmsDeliveryLog",
    "Staff",
    "StaffProfile",
    "StatutoryRate",
    "StockTransaction",
    "Supplier",
    "SurgicalCase",
    "TaxRate",
    "TrainingAttendance",
    "TrainingProgram",
    "Transaction",
    "TransactionEntry",
    "TrialAIScreening",
    "TrialAdverseEvent",
    "TrialParticipant",
    "TrialParticipantVisit",
    "TrialVisitSchedule",
    "UsageTelemetry",
    "VitalSign",
    "Ward",
]
