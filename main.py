import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import google.generativeai as genai

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing Supabase credentials in .env file!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise RuntimeError("Missing Gemini API key in .env file!")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-flash-lite')

app = FastAPI(title="OmniTrack Core API", version="2.0.0")

# ==========================================
# 2. DATA MODELS (Input Validation)
# ==========================================
class SessionRequest(BaseModel):
    date: str
    session_name: str

class AttendanceRequest(BaseModel):
    roll_number: int
    date: str
    session_name: str

class SQLRequest(BaseModel):
    user_query: str

# 🆕 NEW: Validation for adding a new student
class StudentRequest(BaseModel):
    roll_number: int
    full_name: str
    photo_url: str = ""  # Optional! They can leave it blank

# ==========================================
# 3. READ ROUTES (Fetching Data)
# ==========================================
@app.get("/")
def health_check():
    return {"status": "online", "message": "OmniTrack Backend is running securely."}

@app.get("/get-students")
def get_all_students():
    """SPEED UP: Only fetching the columns we actually need to save bandwidth."""
    try:
        response = supabase.table("students").select("id, roll_number, full_name, photo_url").order("roll_number").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/get-sessions/{date}")
def get_sessions(date: str):
    response = supabase.table("attendance_logs").select("session_name").eq("date", date).execute()
    unique_sessions = list(set([item["session_name"] for item in response.data]))
    return {"active_sessions": unique_sessions}

@app.get("/get-attendance/{date}/{session_name}")
def get_attendance(date: str, session_name: str):
    """SPEED UP: Using a Supabase Foreign Key Join to fetch everything in 1 database call instead of 2."""
    response = supabase.table("attendance_logs")\
        .select("status, students(roll_number)")\
        .eq("date", date)\
        .eq("session_name", session_name)\
        .execute()
    
    status_map = {}
    for item in response.data:
        if item.get("students"):
            roll_str = str(item["students"]["roll_number"])
            status_map[roll_str] = item["status"]
            
    return status_map

@app.get("/get-student-history/{roll_number}")
def get_student_history(roll_number: int):
    """Fetches the complete attendance history for a single student."""
    student_res = supabase.table("students").select("id, full_name").eq("roll_number", roll_number).limit(1).execute()
    
    if not student_res.data:
        return {"error": "Student not found"}
        
    student_id = student_res.data[0]["id"]
    full_name = student_res.data[0]["full_name"]
    
    logs_res = supabase.table("attendance_logs")\
        .select("date, session_name, status")\
        .eq("student_id", student_id)\
        .order("date", desc=True)\
        .execute()
        
    return {
        "full_name": full_name,
        "history": logs_res.data
    }

# ==========================================
# 4. WRITE ROUTES (Modifying Data)
# ==========================================
@app.post("/start-session")
def start_session(req: SessionRequest):
    existing = supabase.table("attendance_logs").select("log_id").eq("date", req.date).eq("session_name", req.session_name).limit(1).execute()
    if existing.data:
        return {"error": f"Session for {req.session_name} on {req.date} already exists."}
        
    students = supabase.table("students").select("id").execute().data
    if not students:
        raise HTTPException(status_code=400, detail="No students found in the database to start a session.")

    logs = [{"student_id": s["id"], "date": req.date, "session_name": req.session_name, "status": "Absent"} for s in students]
    supabase.table("attendance_logs").insert(logs).execute()
    
    return {"message": f"Session '{req.session_name}' initialized successfully."}

@app.post("/mark-present")
def mark_present(req: AttendanceRequest):
    student = supabase.table("students").select("id").eq("roll_number", req.roll_number).limit(1).execute().data
    if not student:
        return {"error": f"Student with Roll Number {req.roll_number} not found."}
        
    supabase.table("attendance_logs").update({"status": "Present"})\
        .eq("student_id", student[0]["id"])\
        .eq("date", req.date)\
        .eq("session_name", req.session_name)\
        .execute()
        
    return {"message": f"Roll number {req.roll_number} marked Present!"}

@app.post("/mark-absent")
def mark_absent(req: AttendanceRequest):
    student = supabase.table("students").select("id").eq("roll_number", req.roll_number).limit(1).execute().data
    if not student:
        return {"error": "Student not found!"}
        
    supabase.table("attendance_logs").update({"status": "Absent"})\
        .eq("student_id", student[0]["id"])\
        .eq("date", req.date)\
        .eq("session_name", req.session_name)\
        .execute()
        
    return {"message": f"Roll number {req.roll_number} marked Absent."}

@app.post("/mark-all-present")
def mark_all_present(req: SessionRequest):
    supabase.table("attendance_logs").update({"status": "Present"})\
        .eq("date", req.date)\
        .eq("session_name", req.session_name)\
        .execute()
        
    return {"message": f"Everyone marked Present for {req.session_name}!"}

@app.delete("/delete-session")
def delete_session(date: str, session_name: str):
    supabase.table("attendance_logs").delete().eq("date", date).eq("session_name", session_name).execute()
    return {"message": f"Session {session_name} deleted successfully."}

# ==========================================
# 4.5 MANAGE ROSTER ROUTES (NEW!)
# ==========================================
@app.post("/add-student")
def add_student(req: StudentRequest):
    """Safely adds a new student to the database."""
    # 1. Prevent duplicate roll numbers
    existing = supabase.table("students").select("id").eq("roll_number", req.roll_number).limit(1).execute().data
    if existing:
        return {"error": f"A student with Roll Number {req.roll_number} already exists!"}
        
    # 2. Insert new student
    new_student = {
        "roll_number": req.roll_number,
        "full_name": req.full_name,
        "photo_url": req.photo_url
    }
    
    try:
        supabase.table("students").insert(new_student).execute()
        return {"message": f"Successfully added {req.full_name} to the roster!"}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

@app.delete("/delete-student/{roll_number}")
def delete_student(roll_number: int):
    """Removes a student and safely wipes their history to prevent crashes."""
    # 1. Find the student ID
    student = supabase.table("students").select("id").eq("roll_number", roll_number).limit(1).execute().data
    if not student:
        return {"error": f"Roll number {roll_number} not found."}
        
    student_id = student[0]["id"]
    
    try:
        # 2. Wipe their attendance logs first (Required by Postgres rules)
        supabase.table("attendance_logs").delete().eq("student_id", student_id).execute()
        
        # 3. Finally, delete the student
        supabase.table("students").delete().eq("id", student_id).execute()
        return {"message": f"Student {roll_number} and all their history have been removed."}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

# ==========================================
# 5. AI ROUTES
# ==========================================
@app.post("/ai-sql-search")
def ai_sql_search(req: SQLRequest):
    prompt = f"""
    You are a strictly logical Text-to-SQL translator for a PostgreSQL database.
    
    DATABASE SCHEMA:
    Table 1: students (id, roll_number, full_name, photo_url)
    Table 2: attendance_logs (log_id, student_id, date, session_name, status)
    * attendance_logs.student_id joins to students.id
    
    THE USER REQUEST: "{req.user_query}"
    
    YOUR INSTRUCTIONS & RULES:
    1. If the request is vague, reply ONLY with a clarification question.
    2. If clear, return the SQL query starting with SELECT.
    3. Always use JOINs if needed.
    4. Pay strict attention to column locations. 'full_name' and 'roll_number' ONLY exist in the 'students' table. 
    5. CASE SENSITIVITY FIX: If the user types a session (e.g., 'ai theory') or status (e.g., 'present') in lowercase, YOU MUST match the exact capitalization in the SQL (e.g., T2.session_name = 'AI Theory' AND T2.status = 'Present').
    CRITICAL OUTPUT FORMATTING:
    - You must output RAW TEXT ONLY.
    - DO NOT wrap the SQL in ```sql or ``` blocks.
    - DO NOT add any conversational text.
    """
    
    response = model.generate_content(prompt)
    generated_sql = response.text.strip().rstrip(';')
    
    try:
        if not generated_sql.upper().startswith("SELECT"):
            return {"clarification": generated_sql}
            
        result = supabase.rpc("execute_sql_query", {"query_text": generated_sql}).execute()
        return {"sql_used": generated_sql, "data": result.data}
        
    except Exception as e:
        return {"error": f"Database Execution Error: {str(e)}", "failed_sql": generated_sql}
