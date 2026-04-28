// ============================================================
//  config.js  —  OmniTrack AI | Shared Configuration
//
//  ⚠️  CHANGE API_BASE EVERY TIME YOU START THE BACKEND ⚠️
//
//  Option A — Development (phone + laptop on same WiFi):
//    1. Find your laptop's local IP:
//       - Windows:  run `ipconfig`  → look for IPv4 Address
//       - Mac/Linux: run `ifconfig` → look for inet address
//    2. Set API_BASE = "http://YOUR_LAPTOP_IP:8000"
//    Example: "http://192.168.1.45:8000"
//
//  Option B — Remote access with ngrok (phone on any network):
//    1. Install ngrok: https://ngrok.com/download
//    2. Run: ngrok http 8000
//    3. Copy the https://xxxx.ngrok-free.app URL
//    4. Set API_BASE to that URL (no trailing slash)
//
//  Option C — Deployed backend:
//    Set API_BASE to your production URL.
// ============================================================

export const API_BASE = "http://YOUR_LAPTOP_IP:8000";
// Example: export const API_BASE = "http://192.168.1.45:8000";
// Example: export const API_BASE = "https://xxxx.ngrok-free.app";

// ── Session list ─────────────────────────────────────────────
// Keep this list in sync with the 'sessions' table in Supabase
// and the seed data in supabase_setup.sql
export const SESSIONS = [
  "AI Theory",
  "AI Lab",
  "Database Theory",
  "Database Lab",
  "SDA",
];
