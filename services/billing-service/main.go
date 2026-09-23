package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

var db *pgxpool.Pool

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8020"
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("DATABASE_URL is required")
	}

	// Connect to PostgreSQL
	var err error
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	config, err := pgxpool.ParseConfig(dbURL)
	if err != nil {
		log.Fatalf("Failed to parse DB config: %v", err)
	}
	config.MaxConns = 20
	config.MinConns = 2

	db, err = pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	r := gin.Default()

	r.GET("/health", healthCheck)

	v1 := r.Group("/api/v1/billing-svc")
	{
		v1.GET("/invoices", listInvoices)
		v1.GET("/invoices/:id", getInvoice)
		v1.POST("/invoices", createInvoice)
		v1.POST("/invoices/:id/items", addInvoiceItem)
		v1.POST("/invoices/:id/finalize", finalizeInvoice)
		v1.POST("/invoices/:id/void", voidInvoice)
		v1.POST("/invoices/:id/waive", waiveInvoice)

		v1.GET("/payments/:invoice_id", listPayments)
		v1.POST("/payments", recordPayment)

		v1.GET("/revenue/daily", dailyRevenue)
	}

	log.Printf("Billing service starting on port %s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func healthCheck(c *gin.Context) {
	err := db.Ping(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":  "unhealthy",
			"service": "billing-service",
			"error":   err.Error(),
		})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"status":  "ok",
		"service": "billing-service",
	})
}

// ── Invoice Types ───────────────────────────────────────────────────────────

// InvoiceRow represents an invoice from the database.
type InvoiceRow struct {
	ID             uuid.UUID  `json:"id"`
	FacilityID     uuid.UUID  `json:"facility_id"`
	InvoiceNumber  string     `json:"invoice_number"`
	PatientID      uuid.UUID  `json:"patient_id"`
	EncounterID    *uuid.UUID `json:"encounter_id"`
	Status         string     `json:"status"`
	Subtotal       int64      `json:"subtotal"`
	TaxAmount      int64      `json:"tax_amount"`
	DiscountAmount int64      `json:"discount_amount"`
	TotalAmount    int64      `json:"total_amount"`
	PaidAmount     int64      `json:"paid_amount"`
	BalanceDue     int64      `json:"balance_due"`
	Notes          *string    `json:"notes"`
	CreatedAt      time.Time  `json:"created_at"`
}

// InvoiceItemRow represents an invoice item.
type InvoiceItemRow struct {
	ID          uuid.UUID  `json:"id"`
	InvoiceID   uuid.UUID  `json:"invoice_id"`
	ItemType    string     `json:"item_type"`
	Description string     `json:"description"`
	Quantity    int        `json:"quantity"`
	UnitPrice   int64      `json:"unit_price"`
	TotalPrice  int64      `json:"total_price"`
	ReferenceID *uuid.UUID `json:"reference_id"`
}

// PaymentRow represents a payment.
type PaymentRow struct {
	ID            uuid.UUID `json:"id"`
	InvoiceID     uuid.UUID `json:"invoice_id"`
	Amount        int64     `json:"amount"`
	PaymentMethod string    `json:"payment_method"`
	ReferenceNo   *string   `json:"reference_no"`
	ReceivedBy    uuid.UUID `json:"received_by"`
	Notes         *string   `json:"notes"`
	CreatedAt     time.Time `json:"created_at"`
}

// ── Create Invoice Request ──────────────────────────────────────────────────

// CreateInvoiceReq is the request body for creating an invoice.
type CreateInvoiceReq struct {
	FacilityID  uuid.UUID  `json:"facility_id" binding:"required"`
	PatientID   uuid.UUID  `json:"patient_id" binding:"required"`
	EncounterID *uuid.UUID `json:"encounter_id"`
	Notes       *string    `json:"notes"`
	CreatedBy   uuid.UUID  `json:"created_by" binding:"required"`
}

// AddItemReq is the request body for adding an invoice item.
type AddItemReq struct {
	ItemType    string     `json:"item_type" binding:"required"`
	Description string     `json:"description" binding:"required"`
	Quantity    int        `json:"quantity" binding:"required,min=1"`
	UnitPrice   int64      `json:"unit_price" binding:"required,min=0"`
	ReferenceID *uuid.UUID `json:"reference_id"`
}

// RecordPaymentReq is the request body for recording a payment.
type RecordPaymentReq struct {
	InvoiceID     uuid.UUID `json:"invoice_id" binding:"required"`
	Amount        int64     `json:"amount" binding:"required,min=1"`
	PaymentMethod string    `json:"payment_method" binding:"required"`
	ReferenceNo   *string   `json:"reference_no"`
	ReceivedBy    uuid.UUID `json:"received_by" binding:"required"`
	Notes         *string   `json:"notes"`
}

// WaiveReq is the request body for waiving part of an invoice.
type WaiveReq struct {
	Amount   int64     `json:"amount" binding:"required,min=1"`
	Reason   string    `json:"reason" binding:"required"`
	WaivedBy uuid.UUID `json:"waived_by" binding:"required"`
}

// ── Invoice Handlers ────────────────────────────────────────────────────────

func listInvoices(c *gin.Context) {
	facilityID := c.Query("facility_id")
	if facilityID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "facility_id required"})
		return
	}

	status := c.Query("status")
	ctx := c.Request.Context()

	var rows []InvoiceRow
	var query string
	var args []any

	if status != "" {
		query = `SELECT id, facility_id, invoice_number, patient_id, encounter_id,
			status, subtotal, tax_amount, discount_amount, total_amount, paid_amount,
			balance_due, notes, created_at
			FROM invoices WHERE facility_id = $1 AND status = $2 AND is_deleted = false
			ORDER BY created_at DESC LIMIT 200`
		args = []any{facilityID, status}
	} else {
		query = `SELECT id, facility_id, invoice_number, patient_id, encounter_id,
			status, subtotal, tax_amount, discount_amount, total_amount, paid_amount,
			balance_due, notes, created_at
			FROM invoices WHERE facility_id = $1 AND is_deleted = false
			ORDER BY created_at DESC LIMIT 200`
		args = []any{facilityID}
	}

	pgRows, err := db.Query(ctx, query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "database query failed"})
		return
	}
	defer pgRows.Close()

	for pgRows.Next() {
		var row InvoiceRow
		err := pgRows.Scan(
			&row.ID, &row.FacilityID, &row.InvoiceNumber, &row.PatientID,
			&row.EncounterID, &row.Status, &row.Subtotal, &row.TaxAmount,
			&row.DiscountAmount, &row.TotalAmount, &row.PaidAmount,
			&row.BalanceDue, &row.Notes, &row.CreatedAt,
		)
		if err != nil {
			continue
		}
		rows = append(rows, row)
	}

	if rows == nil {
		rows = []InvoiceRow{}
	}

	c.JSON(http.StatusOK, gin.H{"items": rows, "total": len(rows)})
}

func getInvoice(c *gin.Context) {
	id := c.Param("id")
	ctx := c.Request.Context()

	var inv InvoiceRow
	err := db.QueryRow(ctx, `SELECT id, facility_id, invoice_number, patient_id,
		encounter_id, status, subtotal, tax_amount, discount_amount, total_amount,
		paid_amount, balance_due, notes, created_at
		FROM invoices WHERE id = $1 AND is_deleted = false`, id).Scan(
		&inv.ID, &inv.FacilityID, &inv.InvoiceNumber, &inv.PatientID,
		&inv.EncounterID, &inv.Status, &inv.Subtotal, &inv.TaxAmount,
		&inv.DiscountAmount, &inv.TotalAmount, &inv.PaidAmount,
		&inv.BalanceDue, &inv.Notes, &inv.CreatedAt,
	)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "invoice not found"})
		return
	}

	// Fetch items
	itemRows, err := db.Query(ctx, `SELECT id, invoice_id, item_type, description,
		quantity, unit_price, total_price, reference_id
		FROM invoice_items WHERE invoice_id = $1`, inv.ID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch items"})
		return
	}
	defer itemRows.Close()

	var items []InvoiceItemRow
	for itemRows.Next() {
		var item InvoiceItemRow
		err := itemRows.Scan(&item.ID, &item.InvoiceID, &item.ItemType,
			&item.Description, &item.Quantity, &item.UnitPrice,
			&item.TotalPrice, &item.ReferenceID)
		if err != nil {
			continue
		}
		items = append(items, item)
	}
	if items == nil {
		items = []InvoiceItemRow{}
	}

	c.JSON(http.StatusOK, gin.H{"invoice": inv, "items": items})
}

func createInvoice(c *gin.Context) {
	var req CreateInvoiceReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()

	// Generate invoice number: INV-YYYYMMDD-NNNN
	now := time.Now()
	datePrefix := now.Format("20060102")

	var count int64
	err := db.QueryRow(ctx,
		`SELECT COUNT(*) FROM invoices WHERE facility_id = $1 AND invoice_number LIKE $2`,
		req.FacilityID, fmt.Sprintf("INV-%s-%%", datePrefix),
	).Scan(&count)
	if err != nil {
		count = 0
	}
	invoiceNumber := fmt.Sprintf("INV-%s-%04d", datePrefix, count+1)

	id := uuid.New()
	_, err = db.Exec(ctx, `INSERT INTO invoices
		(id, facility_id, invoice_number, patient_id, encounter_id, status,
		subtotal, tax_amount, discount_amount, total_amount, paid_amount, balance_due,
		notes, created_by, updated_by)
		VALUES ($1, $2, $3, $4, $5, 'draft', 0, 0, 0, 0, 0, 0, $6, $7, $7)`,
		id, req.FacilityID, invoiceNumber, req.PatientID, req.EncounterID,
		req.Notes, req.CreatedBy,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create invoice"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"id":             id,
		"invoice_number": invoiceNumber,
		"status":         "draft",
	})
}

func addInvoiceItem(c *gin.Context) {
	invoiceID := c.Param("id")
	var req AddItemReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	totalPrice := int64(req.Quantity) * req.UnitPrice

	itemID := uuid.New()
	_, err := db.Exec(ctx, `INSERT INTO invoice_items
		(id, invoice_id, item_type, description, quantity, unit_price, total_price, reference_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		itemID, invoiceID, req.ItemType, req.Description,
		req.Quantity, req.UnitPrice, totalPrice, req.ReferenceID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to add item"})
		return
	}

	// Recalculate invoice totals
	err = recalculateInvoice(ctx, invoiceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to recalculate"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"id": itemID, "total_price": totalPrice})
}

func finalizeInvoice(c *gin.Context) {
	invoiceID := c.Param("id")
	ctx := c.Request.Context()

	tag, err := db.Exec(ctx,
		`UPDATE invoices SET status = 'final' WHERE id = $1 AND status = 'draft' AND is_deleted = false`,
		invoiceID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot finalize invoice"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "final"})
}

func voidInvoice(c *gin.Context) {
	invoiceID := c.Param("id")
	ctx := c.Request.Context()

	tag, err := db.Exec(ctx,
		`UPDATE invoices SET status = 'void' WHERE id = $1 AND status != 'void' AND is_deleted = false`,
		invoiceID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot void invoice"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "void"})
}

func waiveInvoice(c *gin.Context) {
	invoiceID := c.Param("id")
	var req WaiveReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()

	// Apply waiver as a discount
	tag, err := db.Exec(ctx,
		`UPDATE invoices SET
			discount_amount = discount_amount + $1,
			total_amount = total_amount - $1,
			balance_due = balance_due - $1,
			waiver_amount = COALESCE(waiver_amount, 0) + $1,
			waiver_reason = $2,
			waiver_approved_by = $3
		WHERE id = $4 AND is_deleted = false AND balance_due >= $1`,
		req.Amount, req.Reason, req.WaivedBy, invoiceID,
	)
	if err != nil || tag.RowsAffected() == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot waive amount"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"waived": req.Amount})
}

// ── Payment Handlers ────────────────────────────────────────────────────────

func recordPayment(c *gin.Context) {
	var req RecordPaymentReq
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()

	// Check invoice exists and has balance
	var balanceDue int64
	var invoiceStatus string
	err := db.QueryRow(ctx,
		`SELECT balance_due, status FROM invoices WHERE id = $1 AND is_deleted = false`,
		req.InvoiceID,
	).Scan(&balanceDue, &invoiceStatus)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "invoice not found"})
		return
	}
	if invoiceStatus == "void" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "cannot pay voided invoice"})
		return
	}
	if req.Amount > balanceDue {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":       "payment exceeds balance",
			"balance_due": balanceDue,
		})
		return
	}

	// Insert payment
	paymentID := uuid.New()
	_, err = db.Exec(ctx, `INSERT INTO payments
		(id, facility_id, invoice_id, amount, payment_method, reference_number,
		received_by, notes, created_by, updated_by)
		SELECT $1, facility_id, $2, $3, $4, $5, $6, $7, $6, $6
		FROM invoices WHERE id = $2`,
		paymentID, req.InvoiceID, req.Amount, req.PaymentMethod,
		req.ReferenceNo, req.ReceivedBy, req.Notes,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to record payment"})
		return
	}

	// Update invoice paid_amount and balance
	newBalance := balanceDue - req.Amount
	newStatus := "partial"
	if newBalance == 0 {
		newStatus = "paid"
	}

	_, err = db.Exec(ctx,
		`UPDATE invoices SET
			paid_amount = paid_amount + $1,
			balance_due = $2,
			status = $3
		WHERE id = $4`,
		req.Amount, newBalance, newStatus, req.InvoiceID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update invoice"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"payment_id":  paymentID,
		"amount":      req.Amount,
		"balance_due": newBalance,
		"status":      newStatus,
	})
}

func listPayments(c *gin.Context) {
	invoiceID := c.Param("invoice_id")
	ctx := c.Request.Context()

	rows, err := db.Query(ctx, `SELECT id, invoice_id, amount, payment_method,
		reference_number, received_by, notes, created_at
		FROM payments WHERE invoice_id = $1 ORDER BY created_at DESC`, invoiceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "database query failed"})
		return
	}
	defer rows.Close()

	var payments []PaymentRow
	for rows.Next() {
		var p PaymentRow
		err := rows.Scan(&p.ID, &p.InvoiceID, &p.Amount, &p.PaymentMethod,
			&p.ReferenceNo, &p.ReceivedBy, &p.Notes, &p.CreatedAt)
		if err != nil {
			continue
		}
		payments = append(payments, p)
	}
	if payments == nil {
		payments = []PaymentRow{}
	}

	c.JSON(http.StatusOK, gin.H{"items": payments, "total": len(payments)})
}

// ── Revenue ─────────────────────────────────────────────────────────────────

func dailyRevenue(c *gin.Context) {
	facilityID := c.Query("facility_id")
	if facilityID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "facility_id required"})
		return
	}

	ctx := c.Request.Context()

	var totalRevenue int64
	var paymentCount int64
	err := db.QueryRow(ctx, `SELECT COALESCE(SUM(p.amount), 0), COUNT(p.id)
		FROM payments p
		JOIN invoices i ON p.invoice_id = i.id
		WHERE i.facility_id = $1 AND p.created_at::date = CURRENT_DATE`,
		facilityID,
	).Scan(&totalRevenue, &paymentCount)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query failed"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"date":          time.Now().Format("2006-01-02"),
		"total_revenue": totalRevenue,
		"payment_count": paymentCount,
	})
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func recalculateInvoice(ctx context.Context, invoiceID string) error {
	var subtotal int64
	err := db.QueryRow(ctx,
		`SELECT COALESCE(SUM(total_price), 0) FROM invoice_items WHERE invoice_id = $1`,
		invoiceID,
	).Scan(&subtotal)
	if err != nil {
		return err
	}

	_, err = db.Exec(ctx, `UPDATE invoices SET
		subtotal = $1,
		total_amount = $1 - discount_amount + tax_amount,
		balance_due = $1 - discount_amount + tax_amount - paid_amount
		WHERE id = $2`,
		subtotal, invoiceID,
	)
	return err
}
