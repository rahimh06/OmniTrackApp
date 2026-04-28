"""
OmniTrack AI — FastAPI Backend  (main.py)
==========================================
Run with:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Endpoints
---------
GET  /                              Health check
GET  /get-students                  All students (id, roll_number, full_name, photo_url)
GET  /get-course-sessions           All courses from the sessions catalogue table
GET  /get-sessions/{date}           Sessions that have been STARTED on a given date
GET  /get-attendance/{date}/{name}  Roll→status map for one session
GET  /get-student-history/{roll}    Full attendance history for one student
POST /start-session                 Initialize all-absent records for a session
POST /mark-present                  Flip one student to Present
POST /mark-absent                   Flip one student to Absent
POST /mark-all-present              Flip entire session to Present
DELETE /delete-session              Wipe all logs for a session
POST /add-student                   Add a new student to the roster
DELETE /delete-student/{roll}       Remove student + all their logs
POST /ai-sql-search                 Natural-language → SQL via Gemini → DB result
"""

import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import google.generativeai as genai

# ── Environment ─────────────────────────────────────────────────
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in .env")
if not GEMINI_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env")

# ── Supabase client ──────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Gemini client ────────────────────────────────────────────────
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

# ── FastAPI app ──────────────────────────────────────────────────
app = FastAPI(title="OmniTrack AI API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================================================
# DATA MODELS
# ================================================================

class SessionRequest(BaseModel):
    date: str
    session_name: str

class AttendanceRequest(BaseModel):
    roll_number: int
    date: str
    session_name: str

class SQLRequest(BaseModel):
    user_query: str

class StudentRequest(BaseModel):
    roll_number: int
    full_name: str
    photo_url: str = ""

# ================================================================
# READ ROUTES
# ================================================================

@app.get("/")
def health_check():
    return {"status": "online", "message": "OmniTrack AI Backend is running."}


@app.get("/get-students")
def get_all_students():
    """Returns the full class roster, ordered by roll number."""
    try:
        response = (
            supabase.table("students")
            .select("id, roll_number, full_name, photo_url")
            .order("roll_number")
            .execute()
        )
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/get-course-sessions")
def get_course_sessions():
    """
    Returns all courses from the sessions catalogue table.
    Used by the Streamlit dashboard to populate the session selector.
    """
    try:
        response = (
            supabase.table("sessions")
            .select("course_name")
            .order("id")
            .execute()
        )
        return {"courses": [row["course_name"] for row in response.data]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/get-sessions/{date}")
def get_active_sessions_for_date(date: str):
    """
    Returns which sessions have ALREADY BEEN STARTED on a given date.
    (i.e. sessions that have at least one row in attendance_logs)
    """
    try:
        response = (
            supabase.table("attendance_logs")
            .select("session_name")
            .eq("date", date)
            .execute()
        )
        unique_sessions = list(set(item["session_name"] for item in response.data))
        return {"active_sessions": unique_sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/get-attendance/{date}/{session_name}")
def get_attendance(date: str, session_name: str):
    """
    Returns a dict mapping roll_number → status for every student
    in a given session.  Uses a foreign-key join so it's one DB call.
    """
    try:
        response = (
            supabase.table("attendance_logs")
            .select("status, students(roll_number)")
            .eq("date", date)
            .eq("session_name", session_name)
            .execute()
        )
        status_map = {}
        for item in response.data:
            if item.get("students"):
                roll_str = str(item["students"]["roll_number"])
                status_map[roll_str] = item["status"]
        return status_map
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/get-student-history/{roll_number}")
def get_student_history(roll_number: int):
    """Fetches the complete attendance history for a single student."""
    try:
        student_res = (
            supabase.table("students")
            .select("id, full_name")
            .eq("roll_number", roll_number)
            .limit(1)
            .execute()
        )
        if not student_res.data:
            return {"error": "Student not found"}

        student_id = student_res.data[0]["id"]
        full_name  = student_res.data[0]["full_name"]

        logs_res = (
            supabase.table("attendance_logs")
            .select("date, session_name, status")
            .eq("student_id", student_id)
            .order("date", desc=True)
            .execute()
        )
        return {"full_name": full_name, "history": logs_res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/get-summary/{date}/{session_name}")
def get_session_summary(date: str, session_name: str):
    """
    Returns a quick Present/Absent count for a session.
    Shown as a metric card in the Streamlit dashboard.
    """
    try:
        response = (
            supabase.table("attendance_logs")
            .select("status")
            .eq("date", date)
            .eq("session_name", session_name)
            .execute()
        )
        total   = len(response.data)
        present = sum(1 for r in response.data if r["status"] == "Present")
        absent  = total - present
        return {
            "total": total,
            "present": present,
            "absent": absent,
            "percentage": round((present / total) * 100, 1) if total > 0 else 0.0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ================================================================
# WRITE ROUTES
# ================================================================

@app.post("/start-session")
def start_session(req: SessionRequest):
    """
    Creates an 'Absent' row in attendance_logs for EVERY student.
    This is the 'default absent' system — teachers only need to
    mark who IS present, not who is absent.
    """
    # Prevent accidental duplicate sessions
    existing = (
        supabase.table("attendance_logs")
        .select("log_id")
        .eq("date", req.date)
        .eq("session_name", req.session_name)
        .limit(1)
        .execute()
    )
    if existing.data:
        return {"error": f"Session '{req.session_name}' on {req.date} already exists."}

    students = supabase.table("students").select("id").execute().data
    if not students:
        raise HTTPException(
            status_code=400,
            detail="No students in the database. Add students first."
        )

    logs = [
        {
            "student_id":   s["id"],
            "date":         req.date,
            "session_name": req.session_name,
            "status":       "Absent",
        }
        for s in students
    ]
    supabase.table("attendance_logs").insert(logs).execute()
    return {"message": f"Session '{req.session_name}' started. {len(logs)} students defaulted to Absent."}


@app.post("/mark-present")
def mark_present(req: AttendanceRequest):
    student = (
        supabase.table("students")
        .select("id")
        .eq("roll_number", req.roll_number)
        .limit(1)
        .execute()
        .data
    )
    if not student:
        return {"error": f"Roll number {req.roll_number} not found in the roster."}

    supabase.table("attendance_logs").update({"status": "Present"}).eq(
        "student_id", student[0]["id"]
    ).eq("date", req.date).eq("session_name", req.session_name).execute()

    return {"message": f"Roll {req.roll_number} marked Present ✅"}


@app.post("/mark-absent")
def mark_absent(req: AttendanceRequest):
    student = (
        supabase.table("students")
        .select("id")
        .eq("roll_number", req.roll_number)
        .limit(1)
        .execute()
        .data
    )
    if not student:
        return {"error": "Student not found."}

    supabase.table("attendance_logs").update({"status": "Absent"}).eq(
        "student_id", student[0]["id"]
    ).eq("date", req.date).eq("session_name", req.session_name).execute()

    return {"message": f"Roll {req.roll_number} marked Absent."}


@app.post("/mark-all-present")
def mark_all_present(req: SessionRequest):
    supabase.table("attendance_logs").update({"status": "Present"}).eq(
        "date", req.date
    ).eq("session_name", req.session_name).execute()

    return {"message": f"All students marked Present for '{req.session_name}' on {req.date}!"}


@app.delete("/delete-session")
def delete_session(date: str, session_name: str):
    supabase.table("attendance_logs").delete().eq("date", date).eq(
        "session_name", session_name
    ).execute()
    return {"message": f"Session '{session_name}' on {date} deleted."}


# ================================================================
# ROSTER MANAGEMENT
# ================================================================

@app.post("/add-student")
def add_student(req: StudentRequest):
    """Safely adds a new student, preventing duplicate roll numbers."""
    existing = (
        supabase.table("students")
        .select("id")
        .eq("roll_number", req.roll_number)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return {"error": f"Roll number {req.roll_number} already exists in the roster."}

    try:
        supabase.table("students").insert(
            {
                "roll_number": req.roll_number,
                "full_name":   req.full_name,
                "photo_url":   req.photo_url,
            }
        ).execute()
        return {"message": f"'{req.full_name}' (Roll {req.roll_number}) added successfully!"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


@app.delete("/delete-student/{roll_number}")
def delete_student(roll_number: int):
    """
    Removes a student and all their attendance history.
    The ON DELETE CASCADE on attendance_logs handles the cleanup
    automatically, but we do it explicitly for safety.
    """
    student = (
        supabase.table("students")
        .select("id, full_name")
        .eq("roll_number", roll_number)
        .limit(1)
        .execute()
        .data
    )
    if not student:
        return {"error": f"Roll number {roll_number} not found."}

    student_id = student[0]["id"]
    full_name  = student[0]["full_name"]

    try:
        supabase.table("attendance_logs").delete().eq("student_id", student_id).execute()
        supabase.table("students").delete().eq("id", student_id).execute()
        return {"message": f"'{full_name}' (Roll {roll_number}) and all their records removed."}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


# ================================================================
# AI ANALYTICS
# ================================================================

@app.post("/ai-sql-search")
def ai_sql_search(req: SQLRequest):
    """
    Converts a natural-language question into a PostgreSQL SELECT query
    using Gemini, then runs it via the execute_sql_query RPC function.

    IMPORTANT: The execute_sql_query function MUST exist in your Supabase
    project (see supabase_setup.sql) or this endpoint will always fail.
    """

    prompt = f"""
You are a PostgreSQL expert for a university attendance system called OmniTrack AI.
Your ONLY job is to convert the teacher's question into a valid SQL SELECT query.

DATABASE SCHEMA:
- Table: students
  Columns: id (uuid), roll_number (integer), full_name (text), photo_url (text)

- Table: sessions
  Columns: id (integer), course_name (text)
  Current courses: 'AI Theory', 'AI Lab', 'Database Theory', 'Database Lab', 'SDA'

- Table: attendance_logs
  Columns: log_id (uuid), student_id (uuid → students.id), date (date), session_name (text), status (text)
  status values: 'Present' or 'Absent' (always capital P or A)
  session_name examples: 'AI Theory', 'AI Lab', 'Database Theory', 'Database Lab', 'SDA'

STRICT RULES:
1. Output RAW SQL ONLY — no markdown, no ```sql, no explanation, no "Here is:"
2. ONLY write SELECT statements — no INSERT, UPDATE, DELETE, DROP, etc.
3. Use ILIKE for name searches: full_name ILIKE '%Yahya%'
4. Session names and status values MUST use Title Case: 'AI Theory', 'Present', 'Absent'
5. Always JOIN students and attendance_logs when the query needs both name and status.
6. For "today" queries, use CURRENT_DATE. For "this week", use date >= CURRENT_DATE - INTERVAL '7 days'.
7. If the question is ambiguous or not related to attendance data, return exactly:
   CLARIFICATION: <your question for the teacher>

QUESTION: "{req.user_query}"

SQL:"""

    try:
        response      = model.generate_content(prompt)
        raw_output    = response.text.strip()

        # Remove accidental markdown fences Gemini sometimes adds
        cleaned = re.sub(r"```(?:sql)?", "", raw_output, flags=re.IGNORECASE).strip()
        # Strip trailing semicolon (Supabase RPC handles it)
        generated_sql = cleaned.rstrip(";").strip()

        # Handle clarification responses
        if generated_sql.upper().startswith("CLARIFICATION:"):
            clarification_text = generated_sql[len("CLARIFICATION:"):].strip()
            return {"clarification": clarification_text}

        # Safety gate: must be a SELECT
        if not generated_sql.upper().startswith("SELECT"):
            return {
                "clarification": (
                    "I couldn't turn your question into a database query. "
                    "Try rephrasing it — for example: "
                    "'Who was absent in AI Lab today?' or "
                    "'Show all students with less than 50% attendance.'"
                )
            }

        # Execute via the Supabase RPC function
        result = supabase.rpc("execute_sql_query", {"query_text": generated_sql}).execute()
        return {"sql_used": generated_sql, "data": result.data}

    except Exception as e:
        error_msg = str(e)
        if "execute_sql_query" in error_msg and "does not exist" in error_msg:
            return {
                "error": (
                    "Setup required: The 'execute_sql_query' function is missing from "
                    "your Supabase project. Run supabase_setup.sql in your SQL Editor first."
                )
            }
        return {"error": f"AI Query Error: {error_msg}", "failed_sql": generated_sql if 'generated_sql' in locals() else "N/A"}
