//! Policy Gateway for Agent Governance
//!
//! This service enforces novel-language governance rules:
//! - Protocol registration required before novel-language use
//! - Periodic English reports required for continued use
//! - All messages logged for audit trail
//!
//! # Endpoints
//! - `POST /register_protocol_for_agent` - Register a protocol
//! - `POST /report` - Submit an English translation report
//! - `POST /send` - Send a message (gated by compliance)
//! - `GET /health` - Health check

use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::{Arc, RwLock},
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tower_http::cors::{Any, CorsLayer};
use tracing::{info, warn, Level};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

// =============================================================================
// Configuration
// =============================================================================

/// Maximum seconds allowed between reports for novel-language use
const REPORT_INTERVAL_SEC: u64 = 60;

/// Minimum coverage fraction required in reports
const MIN_COVERAGE: f64 = 0.95;

/// Minimum English summary length in characters
const MIN_SUMMARY_LENGTH: usize = 30;

// =============================================================================
// State
// =============================================================================

/// Shared application state
#[derive(Clone, Default)]
struct AppState {
    inner: Arc<RwLock<InnerState>>,
}

/// Internal mutable state
#[derive(Default)]
struct InnerState {
    /// Protocol registry: agent_id -> (protocol_key -> descriptor)
    protocols: HashMap<String, HashMap<String, ProtocolDescriptor>>,
    
    /// Last report timestamp: "agent_id::protocol_key" -> unix_timestamp
    last_report_ts: HashMap<String, u64>,
    
    /// Violation counts: agent_id -> count
    violations: HashMap<String, u32>,
}

// =============================================================================
// Data Types
// =============================================================================

/// Protocol metadata required for registration
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ProtocolDescriptor {
    name: String,
    version: String,
    purpose: String,
    scope: String,
    risk_tier: String,
    translation_method: String,
}

/// Request to register a protocol for an agent
#[derive(Debug, Clone, Serialize, Deserialize)]
struct RegisterProtocolRequest {
    agent_id: String,
    protocol: ProtocolDescriptor,
}

/// English translation report
#[derive(Debug, Clone, Serialize, Deserialize)]
struct EnglishReport {
    agent_id: String,
    protocol_name: String,
    protocol_version: String,
    window_start_ts: f64,
    window_end_ts: f64,
    message_ids: Vec<String>,
    english_summary: String,
    coverage: f64,
    self_confidence: f64,
    notes: Option<String>,
}

/// Protocol reference in messages
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ProtocolRef {
    name: String,
    version: String,
}

/// Request to send a message
#[derive(Debug, Clone, Serialize, Deserialize)]
struct SendMessageRequest {
    from: String,
    to: String,
    content: String,
    protocol: Option<ProtocolRef>,
    ts: Option<f64>,
}

/// Generic API response
#[derive(Debug, Serialize)]
struct ApiResponse {
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    message: Option<String>,
}

impl ApiResponse {
    fn success() -> Self {
        Self { ok: true, error: None, message: None }
    }
    
    fn success_with_message(msg: &str) -> Self {
        Self { ok: true, error: None, message: Some(msg.to_string()) }
    }
    
    fn error(msg: &str) -> Self {
        Self { ok: false, error: Some(msg.to_string()), message: None }
    }
}

// =============================================================================
// Utility Functions
// =============================================================================

/// Get current Unix timestamp in seconds
fn now_unix_sec() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs()
}

/// Create protocol key from name and version
fn protocol_key(name: &str, version: &str) -> String {
    format!("{name}:{version}")
}

/// Heuristic check if text appears to be English
///
/// Returns `true` if the text is plausibly English.
/// Conservative: flags anything suspicious as non-English.
///
/// For production, consider:
/// - Language model classifier
/// - Entropy-based detection
/// - Compression ratio analysis
fn looks_like_english(s: &str) -> bool {
    let s = s.trim();
    if s.is_empty() {
        return true;
    }

    // Reject if contains non-ASCII characters
    if s.chars().any(|c| c as u32 > 0x7F) {
        return false;
    }

    // Count recognizable word-like tokens
    let word_count = s
        .split(|c: char| !c.is_alphabetic())
        .filter(|w| w.len() >= 2)
        .count();

    // Reject if very few words in a long string
    if s.len() > 40 && word_count < 3 {
        return false;
    }

    // Check vowel ratio (English typically ~30-40%)
    let letters: usize = s.chars().filter(|c| c.is_ascii_alphabetic()).count();
    if letters > 0 {
        let vowels: usize = s
            .chars()
            .filter(|c| matches!(c.to_ascii_lowercase(), 'a' | 'e' | 'i' | 'o' | 'u'))
            .count();
        let ratio = (vowels as f64) / (letters as f64);
        if s.len() > 30 && ratio < 0.20 {
            return false;
        }
    }

    true
}

// =============================================================================
// Handlers
// =============================================================================

/// Health check endpoint
async fn health() -> (StatusCode, Json<ApiResponse>) {
    (StatusCode::OK, Json(ApiResponse::success_with_message("Gateway operational")))
}

/// Register a protocol for an agent
async fn register_protocol_for_agent(
    State(state): State<AppState>,
    Json(req): Json<RegisterProtocolRequest>,
) -> (StatusCode, Json<ApiResponse>) {
    let key = protocol_key(&req.protocol.name, &req.protocol.version);
    
    let mut st = state.inner.write().unwrap();
    st.protocols
        .entry(req.agent_id.clone())
        .or_default()
        .insert(key.clone(), req.protocol);

    info!(
        agent_id = %req.agent_id,
        protocol = %key,
        event = "protocol_registered",
        "Protocol registered"
    );

    (StatusCode::OK, Json(ApiResponse::success()))
}

/// Submit an English translation report
async fn submit_report(
    State(state): State<AppState>,
    Json(report): Json<EnglishReport>,
) -> (StatusCode, Json<ApiResponse>) {
    let key = protocol_key(&report.protocol_name, &report.protocol_version);
    let report_key = format!("{}::{}", report.agent_id, key);

    // Validate protocol registration
    {
        let st = state.inner.read().unwrap();
        let registered = st
            .protocols
            .get(&report.agent_id)
            .and_then(|m| m.get(&key))
            .is_some();

        if !registered {
            warn!(
                agent_id = %report.agent_id,
                protocol = %key,
                event = "report_rejected",
                reason = "protocol_not_registered",
                "Report rejected: protocol not registered"
            );
            return (
                StatusCode::FORBIDDEN,
                Json(ApiResponse::error("Protocol not registered")),
            );
        }
    }

    // Validate coverage threshold
    if report.coverage < MIN_COVERAGE {
        warn!(
            agent_id = %report.agent_id,
            protocol = %key,
            event = "report_rejected",
            reason = "coverage_low",
            coverage = %report.coverage,
            "Report rejected: coverage below minimum"
        );
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::error(&format!(
                "Coverage {:.2} below minimum {:.2}",
                report.coverage, MIN_COVERAGE
            ))),
        );
    }

    // Validate summary length
    if report.english_summary.trim().len() < MIN_SUMMARY_LENGTH {
        warn!(
            agent_id = %report.agent_id,
            protocol = %key,
            event = "report_rejected",
            reason = "summary_too_short",
            "Report rejected: English summary too short"
        );
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::error(&format!(
                "English summary must be at least {} characters",
                MIN_SUMMARY_LENGTH
            ))),
        );
    }

    // Accept report and update timestamp
    {
        let mut st = state.inner.write().unwrap();
        st.last_report_ts.insert(report_key.clone(), now_unix_sec());
    }

    info!(
        agent_id = %report.agent_id,
        protocol = %key,
        event = "report_accepted",
        message_count = %report.message_ids.len(),
        coverage = %report.coverage,
        "Report accepted"
    );

    (StatusCode::OK, Json(ApiResponse::success()))
}

/// Send a message (gated by compliance checks)
async fn send_message(
    State(state): State<AppState>,
    Json(req): Json<SendMessageRequest>,
) -> (StatusCode, Json<ApiResponse>) {
    let is_english = looks_like_english(&req.content);

    // English messages pass through freely
    if is_english {
        info!(
            from = %req.from,
            to = %req.to,
            event = "msg_accepted",
            kind = "english",
            "English message accepted"
        );
        return (StatusCode::OK, Json(ApiResponse::success()));
    }

    // Novel language: require protocol declaration
    let pref = match &req.protocol {
        Some(p) => p,
        None => {
            warn!(
                from = %req.from,
                event = "msg_rejected",
                reason = "missing_protocol",
                "Novel language without protocol declaration"
            );
            
            // Record violation
            {
                let mut st = state.inner.write().unwrap();
                *st.violations.entry(req.from.clone()).or_insert(0) += 1;
            }
            
            return (
                StatusCode::FORBIDDEN,
                Json(ApiResponse::error(
                    "Novel language requires protocol declaration",
                )),
            );
        }
    };

    let key = protocol_key(&pref.name, &pref.version);
    let report_key = format!("{}::{}", req.from, key);

    let st = state.inner.read().unwrap();

    // Check protocol registration
    let registered = st
        .protocols
        .get(&req.from)
        .and_then(|m| m.get(&key))
        .is_some();

    if !registered {
        warn!(
            from = %req.from,
            protocol = %key,
            event = "msg_rejected",
            reason = "protocol_not_registered",
            "Protocol not registered"
        );
        return (
            StatusCode::FORBIDDEN,
            Json(ApiResponse::error("Protocol not registered")),
        );
    }

    // Check report freshness
    let last = st.last_report_ts.get(&report_key).copied().unwrap_or(0);
    let now = now_unix_sec();

    if now.saturating_sub(last) > REPORT_INTERVAL_SEC {
        warn!(
            from = %req.from,
            protocol = %key,
            event = "msg_rejected",
            reason = "report_overdue",
            seconds_since_report = %(now - last),
            "Report overdue"
        );
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ApiResponse::error(
                "Report overdue: submit English report to continue novel-language messaging",
            )),
        );
    }

    info!(
        from = %req.from,
        to = %req.to,
        event = "msg_accepted",
        kind = "novel",
        protocol = %key,
        "Novel message accepted"
    );

    (StatusCode::OK, Json(ApiResponse::success()))
}

// =============================================================================
// Main
// =============================================================================

#[tokio::main]
async fn main() {
    // Initialize logging
    tracing_subscriber::registry()
        .with(fmt::layer().json())
        .with(EnvFilter::from_default_env().add_directive(Level::INFO.into()))
        .init();

    let state = AppState::default();

    // Configure CORS for development
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(health))
        .route("/register_protocol_for_agent", post(register_protocol_for_agent))
        .route("/report", post(submit_report))
        .route("/send", post(send_message))
        .layer(cors)
        .with_state(state);

    let addr: SocketAddr = "0.0.0.0:8080".parse().unwrap();
    
    info!(
        address = %addr,
        event = "gateway_started",
        "Policy Gateway listening"
    );

    // Graceful shutdown on Ctrl+C
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .unwrap();
}

async fn shutdown_signal() {
    tokio::signal::ctrl_c()
        .await
        .expect("Failed to install Ctrl+C handler");
    info!(event = "shutdown", "Shutting down gracefully");
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_looks_like_english() {
        assert!(looks_like_english("Hello, how are you today?"));
        assert!(looks_like_english("The quick brown fox jumps over the lazy dog."));
        assert!(looks_like_english(""));
        assert!(looks_like_english("   "));
        
        // Should flag as non-English
        assert!(!looks_like_english("X9|d=17;u=0x3f;rt=2;ack#77"));
        assert!(!looks_like_english("CMD|seq=0;state=0x00"));
        assert!(!looks_like_english("αβγδ")); // Non-ASCII
        assert!(!looks_like_english("xyzxyzxyzxyzxyzxyzxyzxyzxyzxyzxyzxyzxyz")); // No vowels
    }

    #[test]
    fn test_protocol_key() {
        assert_eq!(protocol_key("test", "1.0"), "test:1.0");
        assert_eq!(protocol_key("my_protocol", "2.3.4"), "my_protocol:2.3.4");
    }
}
