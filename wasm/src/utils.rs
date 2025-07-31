//! Utility functions for WASM integration

use wasm_bindgen::prelude::*;
use js_sys::{Array, Object, Reflect};
use web_sys::console;

/// Macro for console logging
#[macro_export]
macro_rules! log {
    ( $( $t:tt )* ) => {
        web_sys::console::log_1(&format!( $( $t )* ).into());
    }
}

/// Macro for console warnings
#[macro_export]
macro_rules! warn {
    ( $( $t:tt )* ) => {
        web_sys::console::warn_1(&format!( $( $t )* ).into());
    }
}

/// Macro for console errors
#[macro_export]
macro_rules! error {
    ( $( $t:tt )* ) => {
        web_sys::console::error_1(&format!( $( $t )* ).into());
    }
}

/// Timer utility for performance measurements
#[wasm_bindgen]
pub struct Timer {
    start_time: f64,
    label: String,
}

#[wasm_bindgen]
impl Timer {
    #[wasm_bindgen(constructor)]
    pub fn new(label: &str) -> Timer {
        let timer = Timer {
            start_time: js_sys::Date::now(),
            label: label.to_string(),
        };
        log!("Timer '{}' started", label);
        timer
    }

    #[wasm_bindgen]
    pub fn elapsed(&self) -> f64 {
        js_sys::Date::now() - self.start_time
    }

    #[wasm_bindgen]
    pub fn finish(&self) -> f64 {
        let elapsed = self.elapsed();
        log!("Timer '{}' finished: {:.3}ms", self.label, elapsed);
        elapsed
    }
}

/// Memory usage utilities
#[wasm_bindgen]
pub fn get_memory_usage() -> JsValue {
    // Get WASM memory information (simplified for initial version)
    let byte_length = 1024.0 * 1024.0; // Placeholder: 1MB
    
    let usage_info = serde_json::json!({
        "wasm_memory_bytes": byte_length,
        "wasm_memory_mb": byte_length / (1024.0 * 1024.0),
        "timestamp": js_sys::Date::now()
    });

    serde_wasm_bindgen::to_value(&usage_info).unwrap_or(JsValue::NULL)
}

/// Convert JavaScript Array to Rust Vec<String>
pub fn js_array_to_vec_string(array: &Array) -> Vec<String> {
    let mut vec = Vec::with_capacity(array.length() as usize);
    for i in 0..array.length() {
        if let Some(value) = array.get(i).as_string() {
            vec.push(value);
        }
    }
    vec
}

/// Convert Rust Vec<String> to JavaScript Array
pub fn vec_string_to_js_array(vec: &[String]) -> Array {
    let array = Array::new();
    for item in vec {
        array.push(&JsValue::from_str(item));
    }
    array
}

/// Safe JSON parsing with error handling
#[wasm_bindgen]
pub fn safe_json_parse(json_str: &str) -> JsValue {
    match serde_json::from_str::<serde_json::Value>(json_str) {
        Ok(value) => serde_wasm_bindgen::to_value(&value).unwrap_or(JsValue::NULL),
        Err(e) => {
            error!("JSON parse error: {}", e);
            JsValue::NULL
        }
    }
}

/// Generate a simple hash for strings (not cryptographically secure)
#[wasm_bindgen]
pub fn simple_hash(input: &str) -> u32 {
    let mut hash: u32 = 5381;
    for byte in input.bytes() {
        hash = ((hash << 5).wrapping_add(hash)).wrapping_add(byte as u32);
    }
    hash
}

/// Validate SQL query syntax (basic validation)
#[wasm_bindgen]
pub fn validate_sql_query(query: &str) -> JsValue {
    let trimmed = query.trim().to_lowercase();
    
    let is_valid = trimmed.starts_with("select") || 
                   trimmed.starts_with("insert") ||
                   trimmed.starts_with("update") ||
                   trimmed.starts_with("delete") ||
                   trimmed.starts_with("create") ||
                   trimmed.starts_with("drop") ||
                   trimmed.starts_with("alter");

    let validation_result = serde_json::json!({
        "valid": is_valid,
        "query_type": if is_valid {
            trimmed.split_whitespace().next().unwrap_or("unknown")
        } else {
            "invalid"
        },
        "length": query.len()
    });

    serde_wasm_bindgen::to_value(&validation_result).unwrap_or(JsValue::NULL)
}

/// Escape SQL string literals
#[wasm_bindgen]
pub fn escape_sql_string(input: &str) -> String {
    input.replace('\'', "''")
}

/// Format bytes to human readable format
#[wasm_bindgen]
pub fn format_bytes(bytes: f64) -> String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    let mut size = bytes;
    let mut unit_index = 0;

    while size >= 1024.0 && unit_index < UNITS.len() - 1 {
        size /= 1024.0;
        unit_index += 1;
    }

    if unit_index == 0 {
        format!("{:.0} {}", size, UNITS[unit_index])
    } else {
        format!("{:.2} {}", size, UNITS[unit_index])
    }
}

/// Performance testing utilities
#[wasm_bindgen]
pub struct PerformanceProfiler {
    measurements: Vec<(String, f64)>,
    start_time: f64,
}

#[wasm_bindgen]
impl PerformanceProfiler {
    #[wasm_bindgen(constructor)]
    pub fn new() -> PerformanceProfiler {
        PerformanceProfiler {
            measurements: Vec::new(),
            start_time: js_sys::Date::now(),
        }
    }

    #[wasm_bindgen]
    pub fn mark(&mut self, label: &str) {
        let current_time = js_sys::Date::now();
        let elapsed = current_time - self.start_time;
        self.measurements.push((label.to_string(), elapsed));
        log!("Performance mark '{}': {:.3}ms", label, elapsed);
    }

    #[wasm_bindgen]
    pub fn get_report(&self) -> JsValue {
        let mut measurements_json = Vec::new();
        
        for (label, time) in &self.measurements {
            measurements_json.push(serde_json::json!({
                "label": label,
                "time_ms": time,
                "time_from_start": time
            }));
        }

        let report = serde_json::json!({
            "total_time_ms": js_sys::Date::now() - self.start_time,
            "measurements": measurements_json,
            "measurement_count": self.measurements.len()
        });

        serde_wasm_bindgen::to_value(&report).unwrap_or(JsValue::NULL)
    }

    #[wasm_bindgen]
    pub fn reset(&mut self) {
        self.measurements.clear();
        self.start_time = js_sys::Date::now();
    }
}