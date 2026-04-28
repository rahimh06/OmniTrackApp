"""
OmniTrack AI — Streamlit Teacher & Student Dashboard  (app.py)
===============================================================
Run with:  streamlit run app.py

Set BACKEND_URL in your .env file, or it defaults to localhost:8000.
"""

import os
import datetime
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ================================================================
# CONFIGURATION
# ================================================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD", "admin123")

st.set_page_config(
    page_title="OmniTrack AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================
# SESSION STATE INITIALISATION
# ================================================================
for key in ["role", "roll_number"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ================================================================
# HELPER FUNCTIONS
# ================================================================

def api(endpoint: str, method: str = "GET", payload: dict = None, params: dict = None):
    """
    Wrapper for all backend API calls.
    Returns the parsed JSON on success, or None on failure.
    """
    url = f"{BACKEND_URL}/{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=payload, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, params=params, timeout=10)
        else:
            st.error(f"Unknown HTTP method: {method}")
            return None

        if r.status_code == 200:
            return r.json()
        else:
            detail = r.json().get("detail", r.text)
            st.error(f"API Error ({r.status_code}): {detail}")
            return None

    except requests.exceptions.ConnectionError:
        st.error(
            f"🚨 Cannot connect to backend at `{BACKEND_URL}`.\n\n"
            "Make sure `main.py` is running: `uvicorn main:app --reload`"
        )
        return None
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The server took too long to respond.")
        return None


@st.cache_data(ttl=300)
def get_cached_students():
    return api("get-students") or []


@st.cache_data(ttl=600)
def get_cached_courses():
    """Loads the course list from the sessions table in the DB."""
    result = api("get-course-sessions")
    if result and "courses" in result:
        return result["courses"]
    # Fallback if DB call fails
    return ["AI Theory", "AI Lab", "Database Theory", "Database Lab", "SDA"]


@st.cache_data(ttl=30)
def get_active_sessions(date_str: str):
    result = api(f"get-sessions/{date_str}")
    return result.get("active_sessions", []) if result else []


# ================================================================
# LOGIN SCREEN
# ================================================================
if st.session_state.role is None:
    st.markdown(
        "<h1 style='text-align:center;'>🎓 OmniTrack AI</h1>"
        "<p style='text-align:center; color:grey;'>Multi-Session Attendance & Analytics</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👨‍🎓 Student Access")
        with st.form("student_login"):
            roll_input = st.number_input("Enter Your Roll Number:", min_value=1, step=1)
            if st.form_submit_button("View My Attendance", use_container_width=True):
                st.session_state.role = "student"
                st.session_state.roll_number = roll_input
                st.rerun()

    with col2:
        st.subheader("👨‍🏫 Teacher Access")
        with st.form("teacher_login"):
            pwd = st.text_input("Enter Password:", type="password")
            if st.form_submit_button("Login as Teacher", use_container_width=True):
                if pwd == TEACHER_PASSWORD:
                    st.session_state.role = "teacher"
                    st.rerun()
                else:
                    st.error("Incorrect password.")

    st.stop()


# ================================================================
# STUDENT DASHBOARD
# ================================================================
elif st.session_state.role == "student":
    roll = st.session_state.roll_number

    hdr, logout_col = st.columns([5, 1])
    with hdr:
        st.title("👨‍🎓 My Attendance Record")
    with logout_col:
        st.write("")
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.role = None
            st.session_state.roll_number = None
            st.rerun()

    st.divider()

    with st.spinner("Loading your attendance..."):
        data = api(f"get-student-history/{roll}")

    if not data:
        st.error("Could not reach the server.")
    elif "error" in data:
        st.error(f"Student with roll number {roll} not found. Check your roll number.")
    else:
        st.subheader(f"Welcome, {data['full_name']}!")
        history = data["history"]

        if not history:
            st.info("No attendance records found yet.")
        else:
            total      = len(history)
            present    = sum(1 for r in history if r["status"] == "Present")
            absent     = total - present
            percentage = (present / total) * 100

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Overall Attendance", f"{percentage:.1f}%")
            m2.metric("Total Classes",      total)
            m3.metric("Classes Attended",   present)
            m4.metric("Classes Missed",     absent)

            # Per-session breakdown
            st.divider()
            st.markdown("### 📊 Session-wise Breakdown")
            df = pd.DataFrame(history)
            if not df.empty:
                session_stats = (
                    df.groupby("session_name")["status"]
                    .value_counts()
                    .unstack(fill_value=0)
                    .reset_index()
                )
                st.dataframe(session_stats, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("### 📅 Full Attendance Log")
            df_display = pd.DataFrame(history)
            df_display.columns = ["Date", "Session", "Status"]
            df_display["Status"] = df_display["Status"].apply(
                lambda s: f"✅ {s}" if s == "Present" else f"❌ {s}"
            )
            st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.stop()


# ================================================================
# TEACHER DASHBOARD
# ================================================================
elif st.session_state.role == "teacher":

    # ── Header ─────────────────────────────────────────────────
    hdr, logout_col = st.columns([5, 1])
    with hdr:
        st.title("🎓 OmniTrack — Command Center")
    with logout_col:
        st.write("")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.role = None
            st.rerun()

    # ── Sidebar: session controls ───────────────────────────────
    with st.sidebar:
        st.header("⚙️ Session Controls")
        today          = datetime.date.today()
        selected_date  = st.date_input("Date", today, max_value=today)
        date_str       = str(selected_date)

        # Load courses from DB (not hardcoded)
        all_courses    = get_cached_courses()
        active_sessions = get_active_sessions(date_str)

        # Show a ✅ tick next to sessions that are already started
        display_opts   = [
            f"{c} ✅" if c in active_sessions else c
            for c in all_courses
        ]
        selected_opt   = st.selectbox("Course / Session", display_opts)
        session_name   = selected_opt.replace(" ✅", "").strip()

        st.divider()

        if st.button("▶️ Start Session", type="primary", use_container_width=True):
            if session_name in active_sessions:
                st.toast(f"'{session_name}' is already started!", icon="ℹ️")
            else:
                res = api(
                    "start-session", "POST",
                    {"date": date_str, "session_name": session_name}
                )
                if res and "error" not in res:
                    st.toast(res.get("message", "Session started!"), icon="✅")
                    st.cache_data.clear()
                    st.rerun()
                elif res and "error" in res:
                    st.error(res["error"])

        if st.button("🗑️ Delete Session", use_container_width=True):
            res = api(
                "delete-session", "DELETE",
                params={"date": date_str, "session_name": session_name}
            )
            if res:
                st.toast("Session deleted.", icon="🗑️")
                st.cache_data.clear()
                st.rerun()

        # Live summary metrics in sidebar
        if session_name in active_sessions:
            st.divider()
            summary = api(f"get-summary/{date_str}/{session_name}")
            if summary:
                st.metric("Present", summary["present"])
                st.metric("Absent",  summary["absent"])
                st.metric("Attendance", f"{summary['percentage']}%")

    # ── Main tabs ───────────────────────────────────────────────
    tab_attendance, tab_ai, tab_roster = st.tabs(
        ["📝 Attendance", "🤖 AI Analytics", "👥 Manage Roster"]
    )

    # ────────────────────────────────────────────────────────────
    # TAB 1: ATTENDANCE
    # ────────────────────────────────────────────────────────────
    with tab_attendance:
        if session_name not in active_sessions:
            st.warning(
                f"**'{session_name}'** has not been started for {selected_date}.\n\n"
                "Click **▶️ Start Session** in the sidebar to begin."
            )
        else:
            students_list   = get_cached_students()
            attendance_data = api(f"get-attendance/{date_str}/{session_name}") or {}

            # ── Quick roll-number entry ─────────────────────────
            st.markdown("### ⌨️ Quick Entry")
            st.caption("Search by name or roll number, then click Log Present.")
            student_map = {
                f"{s['roll_number']} — {s['full_name']}": s["roll_number"]
                for s in students_list
            }

            qcol1, qcol2 = st.columns([3, 1])
            with qcol1:
                selected_str = st.selectbox(
                    "Student:",
                    options=list(student_map.keys()),
                    index=None,
                    placeholder="Search by name or roll number…",
                    label_visibility="collapsed",
                )
            with qcol2:
                if st.button("Log Present ✅", use_container_width=True):
                    if selected_str is None:
                        st.warning("Select a student first.")
                    else:
                        r = student_map[selected_str]
                        if attendance_data.get(str(r)) == "Present":
                            st.toast(f"{selected_str} is already Present!", icon="ℹ️")
                        else:
                            api("mark-present", "POST", {
                                "roll_number": r,
                                "date": date_str,
                                "session_name": session_name,
                            })
                            st.toast(f"{selected_str} marked Present!", icon="✅")
                            st.rerun()

            st.divider()

            # ── Class roster ────────────────────────────────────
            list_col, action_col = st.columns([4, 1])
            with list_col:
                st.markdown("### 📋 Live Class Roster")
            with action_col:
                if st.button("⚡ Mark ALL Present", use_container_width=True):
                    api("mark-all-present", "POST", {
                        "date": date_str,
                        "session_name": session_name,
                    })
                    st.toast("Entire class marked Present!", icon="🎉")
                    st.rerun()

            with st.container(height=460):
                for student in students_list:
                    roll   = student.get("roll_number")
                    status = attendance_data.get(str(roll), "Absent")
                    c1, c2, c3, c4 = st.columns(
                        [1, 3, 2, 2], vertical_alignment="center"
                    )

                    with c1:
                        photo = (student.get("photo_url") or "").strip()
                        if photo.startswith("http"):
                            try:
                                st.image(photo, width=48)
                            except Exception:
                                st.markdown("👤")
                        else:
                            st.markdown("👤")

                    with c2:
                        st.markdown(f"**{student.get('full_name')}**")
                        st.caption(f"Roll: {roll}")

                    with c3:
                        if status == "Present":
                            st.markdown(
                                "<p style='color:#28a745;font-weight:700;'>🟢 Present</p>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                "<p style='color:#dc3545;font-weight:700;'>🔴 Absent</p>",
                                unsafe_allow_html=True,
                            )

                    with c4:
                        if status == "Absent":
                            if st.button(
                                "Mark Present", key=f"p_{roll}",
                                type="primary", use_container_width=True
                            ):
                                api("mark-present", "POST", {
                                    "roll_number": roll,
                                    "date": date_str,
                                    "session_name": session_name,
                                })
                                st.rerun()
                        else:
                            if st.button(
                                "Undo", key=f"u_{roll}",
                                use_container_width=True
                            ):
                                api("mark-absent", "POST", {
                                    "roll_number": roll,
                                    "date": date_str,
                                    "session_name": session_name,
                                })
                                st.rerun()

    # ────────────────────────────────────────────────────────────
    # TAB 2: AI ANALYTICS
    # ────────────────────────────────────────────────────────────
    with tab_ai:
        st.markdown("### 🤖 AI-Powered Analytics")
        st.caption(
            "Ask any question about your attendance data in plain English. "
            "The AI will convert it to SQL and query the database instantly."
        )

        # Suggestion chips
        suggestions = [
            "Who was absent in AI Lab today?",
            "Show all students present in Database Theory this week",
            "Which students have been absent more than 3 times?",
            "Show attendance percentage for each student",
            "List all sessions for today",
        ]

        st.markdown("**💡 Try one of these:**")
        chip_cols = st.columns(len(suggestions))
        for i, sug in enumerate(suggestions):
            with chip_cols[i]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state["ai_query"] = sug

        st.divider()

        user_query = st.text_input(
            "Your question:",
            value=st.session_state.get("ai_query", ""),
            placeholder="e.g. Show me all students absent in SDA today",
        )

        if st.button("🔍 Analyze", type="primary"):
            if not user_query.strip():
                st.warning("Please enter a question first.")
            else:
                with st.spinner("AI is analyzing…"):
                    output = api("ai-sql-search", "POST", {"user_query": user_query})

                if output:
                    if "error" in output:
                        st.error(f"❌ {output['error']}")
                    elif "clarification" in output:
                        st.info(f"🤔 **AI needs clarification:** {output['clarification']}")
                    elif "data" in output:
                        st.success("✅ Query executed successfully!")
                        with st.expander("🔍 SQL Generated by AI", expanded=False):
                            st.code(output.get("sql_used", ""), language="sql")
                        if output["data"]:
                            st.dataframe(
                                pd.DataFrame(output["data"]),
                                use_container_width=True,
                            )
                        else:
                            st.info("No records matched your query.")

    # ────────────────────────────────────────────────────────────
    # TAB 3: MANAGE ROSTER
    # ────────────────────────────────────────────────────────────
    with tab_roster:
        st.header("👥 Manage Student Roster")

        add_col, del_col = st.columns(2)

        with add_col:
            st.subheader("➕ Add Student")
            with st.form("add_form", clear_on_submit=True):
                new_roll  = st.number_input("Roll Number", min_value=1, step=1)
                new_name  = st.text_input("Full Name")
                new_photo = st.text_input("Photo URL (optional)")
                if st.form_submit_button("Add Student", use_container_width=True):
                    if not new_name.strip():
                        st.warning("Name is required.")
                    else:
                        res = api("add-student", "POST", {
                            "roll_number": new_roll,
                            "full_name":   new_name.strip(),
                            "photo_url":   new_photo.strip(),
                        })
                        if res and "error" in res:
                            st.error(res["error"])
                        elif res:
                            st.success(res.get("message", "Student added!"))
                            st.cache_data.clear()

        with del_col:
            st.subheader("❌ Remove Student")
            students_list = get_cached_students()
            if not students_list:
                st.info("No students in the roster.")
            else:
                opts = {
                    f"{s['roll_number']} — {s['full_name']}": s["roll_number"]
                    for s in students_list
                }
                with st.form("del_form"):
                    to_delete = st.selectbox("Select Student:", list(opts.keys()))
                    confirmed = st.checkbox(
                        "I confirm: delete this student AND their entire attendance history."
                    )
                    if st.form_submit_button("Delete Student", type="primary", use_container_width=True):
                        if not confirmed:
                            st.warning("Tick the confirmation box to proceed.")
                        else:
                            r = opts[to_delete]
                            res = api(f"delete-student/{r}", "DELETE")
                            if res and "error" in res:
                                st.error(res["error"])
                            elif res:
                                st.success(res.get("message", "Student removed."))
                                st.cache_data.clear()
                                st.rerun()
