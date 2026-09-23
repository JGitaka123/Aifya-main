package main

import (
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// ── Types ───────────────────────────────────────────────────────────────────

// SyncOperation represents a queued offline operation from a client.
type SyncOperation struct {
	ID            string    `json:"id"`
	FacilityID    string    `json:"facility_id"`
	DeviceID      string    `json:"device_id"`
	EntityType    string    `json:"entity_type"`
	EntityID      string    `json:"entity_id"`
	OperationType string    `json:"operation_type"` // create, update, delete
	Payload       any       `json:"payload"`
	ClientTS      time.Time `json:"client_timestamp"`
	ServerTS      time.Time `json:"server_timestamp,omitempty"`
	Status        string    `json:"status"` // pending, applied, conflict, rejected
	ConflictInfo  *string   `json:"conflict_info,omitempty"`
}

// SyncPushRequest is the batch push request from an offline client.
type SyncPushRequest struct {
	FacilityID string          `json:"facility_id" binding:"required"`
	DeviceID   string          `json:"device_id" binding:"required"`
	Operations []SyncOperation `json:"operations" binding:"required"`
}

// SyncPullRequest requests changes since a given timestamp.
type SyncPullRequest struct {
	FacilityID  string    `json:"facility_id" binding:"required"`
	DeviceID    string    `json:"device_id" binding:"required"`
	Since       time.Time `json:"since"`
	EntityTypes []string  `json:"entity_types,omitempty"`
}

// SyncPullResponse contains changes for the client to apply.
type SyncPullResponse struct {
	Changes    []SyncChange `json:"changes"`
	ServerTime time.Time    `json:"server_time"`
	HasMore    bool         `json:"has_more"`
	Total      int          `json:"total"`
}

// SyncChange represents a single change for the client.
type SyncChange struct {
	EntityType    string    `json:"entity_type"`
	EntityID      string    `json:"entity_id"`
	OperationType string    `json:"operation_type"`
	Payload       any       `json:"payload"`
	Timestamp     time.Time `json:"timestamp"`
	Version       int64     `json:"version"`
}

// SyncStatus tracks per-device sync state.
type SyncStatus struct {
	DeviceID    string    `json:"device_id"`
	FacilityID  string    `json:"facility_id"`
	LastSyncAt  time.Time `json:"last_sync_at"`
	PendingOps  int       `json:"pending_operations"`
	ConflictOps int       `json:"conflict_operations"`
	IsOnline    bool      `json:"is_online"`
}

// ── In-Memory Store (production would use PostgreSQL + Kafka) ───────────────

var (
	operations   []SyncOperation
	deviceStatus map[string]*SyncStatus
	opMu         sync.RWMutex
)

func init() {
	operations = make([]SyncOperation, 0)
	deviceStatus = make(map[string]*SyncStatus)
}

// ── Main ────────────────────────────────────────────────────────────────────

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8021"
	}

	r := gin.Default()

	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": "sync-service",
		})
	})

	v1 := r.Group("/api/v1/sync")
	{
		// Push offline operations to server
		v1.POST("/push", pushOperations)

		// Pull changes since last sync
		v1.POST("/pull", pullChanges)

		// Get sync status for a device
		v1.GET("/status/:device_id", getSyncStatus)

		// Resolve a conflict
		v1.POST("/resolve/:operation_id", resolveConflict)

		// Register/heartbeat a device
		v1.POST("/heartbeat", deviceHeartbeat)
	}

	log.Printf("Sync service starting on port %s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

// ── Handlers ────────────────────────────────────────────────────────────────

func pushOperations(c *gin.Context) {
	var req SyncPushRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	opMu.Lock()
	defer opMu.Unlock()

	now := time.Now().UTC()
	results := make([]gin.H, 0, len(req.Operations))

	for _, op := range req.Operations {
		// Assign server-side ID and timestamp
		if op.ID == "" {
			op.ID = uuid.NewString()
		}
		op.FacilityID = req.FacilityID
		op.DeviceID = req.DeviceID
		op.ServerTS = now

		// Conflict detection: check if entity was modified after client timestamp
		conflict := detectConflict(op)
		if conflict {
			op.Status = "conflict"
			conflictMsg := "Entity was modified after your local change"
			op.ConflictInfo = &conflictMsg
		} else {
			op.Status = "applied"
		}

		operations = append(operations, op)
		results = append(results, gin.H{
			"id":            op.ID,
			"status":        op.Status,
			"conflict_info": op.ConflictInfo,
		})
	}

	// Update device status
	updateDeviceStatus(req.DeviceID, req.FacilityID, now)

	c.JSON(http.StatusOK, gin.H{
		"processed":   len(results),
		"results":     results,
		"server_time": now,
	})
}

func pullChanges(c *gin.Context) {
	var req SyncPullRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	opMu.RLock()
	defer opMu.RUnlock()

	now := time.Now().UTC()
	entityFilter := make(map[string]bool)
	for _, et := range req.EntityTypes {
		entityFilter[et] = true
	}

	var changes []SyncChange
	for _, op := range operations {
		if op.FacilityID != req.FacilityID {
			continue
		}
		if op.DeviceID == req.DeviceID {
			continue // Don't echo back own operations
		}
		if op.ServerTS.Before(req.Since) || op.ServerTS.Equal(req.Since) {
			continue
		}
		if op.Status != "applied" {
			continue
		}
		if len(entityFilter) > 0 && !entityFilter[op.EntityType] {
			continue
		}

		changes = append(changes, SyncChange{
			EntityType:    op.EntityType,
			EntityID:      op.EntityID,
			OperationType: op.OperationType,
			Payload:       op.Payload,
			Timestamp:     op.ServerTS,
			Version:       op.ServerTS.UnixMilli(),
		})
	}

	if changes == nil {
		changes = []SyncChange{}
	}

	// Cap at 500 changes per pull
	hasMore := false
	if len(changes) > 500 {
		changes = changes[:500]
		hasMore = true
	}

	c.JSON(http.StatusOK, SyncPullResponse{
		Changes:    changes,
		ServerTime: now,
		HasMore:    hasMore,
		Total:      len(changes),
	})
}

func getSyncStatus(c *gin.Context) {
	deviceID := c.Param("device_id")

	opMu.RLock()
	defer opMu.RUnlock()

	status, exists := deviceStatus[deviceID]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}

	// Count pending and conflict operations
	pending := 0
	conflicts := 0
	for _, op := range operations {
		if op.DeviceID == deviceID {
			if op.Status == "pending" {
				pending++
			}
			if op.Status == "conflict" {
				conflicts++
			}
		}
	}
	status.PendingOps = pending
	status.ConflictOps = conflicts

	c.JSON(http.StatusOK, status)
}

func resolveConflict(c *gin.Context) {
	opID := c.Param("operation_id")

	var body struct {
		Resolution string `json:"resolution" binding:"required"` // accept_server, accept_client, merge
		Payload    any    `json:"payload,omitempty"`             // merged payload if resolution=merge
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	opMu.Lock()
	defer opMu.Unlock()

	for i := range operations {
		if operations[i].ID == opID && operations[i].Status == "conflict" {
			switch body.Resolution {
			case "accept_server":
				operations[i].Status = "rejected"
			case "accept_client":
				operations[i].Status = "applied"
			case "merge":
				if body.Payload != nil {
					operations[i].Payload = body.Payload
				}
				operations[i].Status = "applied"
			default:
				c.JSON(http.StatusBadRequest, gin.H{"error": "invalid resolution"})
				return
			}

			c.JSON(http.StatusOK, gin.H{
				"id":         opID,
				"status":     operations[i].Status,
				"resolution": body.Resolution,
			})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{"error": "operation not found or not in conflict"})
}

func deviceHeartbeat(c *gin.Context) {
	var body struct {
		DeviceID   string `json:"device_id" binding:"required"`
		FacilityID string `json:"facility_id" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	opMu.Lock()
	defer opMu.Unlock()

	now := time.Now().UTC()
	updateDeviceStatus(body.DeviceID, body.FacilityID, now)

	c.JSON(http.StatusOK, gin.H{
		"status":      "ok",
		"server_time": now,
	})
}

// ── Helpers ─────────────────────────────────────────────────────────────────

// detectConflict checks if the same entity was modified after the client's timestamp.
func detectConflict(op SyncOperation) bool {
	for i := len(operations) - 1; i >= 0; i-- {
		existing := operations[i]
		if existing.EntityType == op.EntityType &&
			existing.EntityID == op.EntityID &&
			existing.DeviceID != op.DeviceID &&
			existing.Status == "applied" &&
			existing.ServerTS.After(op.ClientTS) {
			return true
		}
	}
	return false
}

// updateDeviceStatus updates or creates a device sync status entry.
func updateDeviceStatus(deviceID, facilityID string, now time.Time) {
	if status, exists := deviceStatus[deviceID]; exists {
		status.LastSyncAt = now
		status.IsOnline = true
	} else {
		deviceStatus[deviceID] = &SyncStatus{
			DeviceID:   deviceID,
			FacilityID: facilityID,
			LastSyncAt: now,
			IsOnline:   true,
		}
	}
}
