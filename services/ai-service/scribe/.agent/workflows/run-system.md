---
description: How to start the Aifya Health Platform mock environment
---

To run the full system with the mock EMR data:

1. **Prerequisites**: Ensure Docker is running and you have Python 3.12+ and Node.js 18+ installed.
2. **Start Docker Services**:
   ```bash
   docker compose up -d aifya-db minio
   ```
3. **Start Backend**:
   ```bash
   cd backend
   source venv/bin/activate
   pip install -r requirements.txt
   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. **Start Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

5. **Access the System**:
   - URL: [http://localhost:3000](http://localhost:3000)
   - Credentials: `doctor@aifya.com` / `Password123!`
