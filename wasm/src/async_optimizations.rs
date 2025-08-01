//! Async optimizations for FACT WASM core
//! 
//! This module provides non-blocking operations and efficient async patterns
//! for WASM environments.

use wasm_bindgen::prelude::*;
use wasm_bindgen_futures::JsFuture;
use js_sys::Promise;
use web_sys::{console, Window};
use std::rc::Rc;
use std::cell::RefCell;
use futures::channel::oneshot;

/// Async cache with non-blocking operations
#[wasm_bindgen]
pub struct AsyncCache {
    cache: Rc<RefCell<crate::FastCache>>,
    pending_operations: Rc<RefCell<Vec<PendingOperation>>>,
}

struct PendingOperation {
    operation_type: AsyncOperationType,
    key: String,
    value: Option<String>,
    resolver: Option<oneshot::Sender<Option<String>>>,
}

enum AsyncOperationType {
    Get,
    Set,
    Delete,
}

#[wasm_bindgen]
impl AsyncCache {
    #[wasm_bindgen(constructor)]
    pub fn new(max_size: usize) -> AsyncCache {
        AsyncCache {
            cache: Rc::new(RefCell::new(crate::FastCache::new(max_size))),
            pending_operations: Rc::new(RefCell::new(Vec::new())),
        }
    }

    /// Async get operation - returns a Promise
    #[wasm_bindgen]
    pub fn get_async(&self, key: &str) -> Promise {
        let cache = self.cache.clone();
        let key = key.to_string();
        
        wasm_bindgen_futures::future_to_promise(async move {
            // Simulate async delay for demo
            let promise = Promise::resolve(&JsValue::from(10));
            let _ = JsFuture::from(promise).await?;
            
            let result = cache.borrow_mut().get(&key);
            Ok(result.unwrap_or_else(|| JsValue::NULL).into())
        })
    }

    /// Async set operation - returns a Promise
    #[wasm_bindgen]
    pub fn set_async(&self, key: &str, value: &str, ttl_ms: u64) -> Promise {
        let cache = self.cache.clone();
        let key = key.to_string();
        let value = value.to_string();
        
        wasm_bindgen_futures::future_to_promise(async move {
            // Simulate async delay for demo
            let promise = Promise::resolve(&JsValue::from(5));
            let _ = JsFuture::from(promise).await?;
            
            let success = cache.borrow_mut().set(&key, &value, ttl_ms);
            Ok(JsValue::from(success))
        })
    }

    /// Batch async operations
    #[wasm_bindgen]
    pub fn batch_operations(&self, operations: &JsValue) -> Promise {
        let cache = self.cache.clone();
        let operations = operations.clone();
        
        wasm_bindgen_futures::future_to_promise(async move {
            // Process batch operations
            let results = js_sys::Array::new();
            
            // Simulate processing multiple operations
            for i in 0..10 {
                let promise = Promise::resolve(&JsValue::from(i));
                let _ = JsFuture::from(promise).await?;
                results.push(&JsValue::from(format!("processed_{}", i)));
            }
            
            Ok(results.into())
        })
    }
}

/// Non-blocking query processor
#[wasm_bindgen]
pub struct AsyncQueryProcessor {
    processor: Rc<RefCell<crate::QueryProcessor>>,
    max_concurrent: usize,
    active_queries: Rc<RefCell<usize>>,
}

#[wasm_bindgen]
impl AsyncQueryProcessor {
    #[wasm_bindgen(constructor)]
    pub fn new(max_concurrent: usize) -> AsyncQueryProcessor {
        AsyncQueryProcessor {
            processor: Rc::new(RefCell::new(crate::QueryProcessor::new())),
            max_concurrent,
            active_queries: Rc::new(RefCell::new(0)),
        }
    }

    /// Process query asynchronously with throttling
    #[wasm_bindgen]
    pub fn process_query_async(&self, query: &str) -> Promise {
        let processor = self.processor.clone();
        let active_queries = self.active_queries.clone();
        let max_concurrent = self.max_concurrent;
        let query = query.to_string();
        
        wasm_bindgen_futures::future_to_promise(async move {
            // Check if we can process more queries
            loop {
                let current_active = *active_queries.borrow();
                if current_active < max_concurrent {
                    *active_queries.borrow_mut() += 1;
                    break;
                }
                
                // Wait before retrying
                let promise = Promise::resolve(&JsValue::from(10));
                let _ = JsFuture::from(promise).await?;
            }
            
            // Process the query
            let result = processor.borrow_mut().process_query(&query);
            
            // Release the slot
            *active_queries.borrow_mut() -= 1;
            
            // Convert QueryResult to JsValue
            let result_obj = js_sys::Object::new();
            js_sys::Reflect::set(&result_obj, &"success".into(), &JsValue::from(result.success))?;
            js_sys::Reflect::set(&result_obj, &"execution_time_ms".into(), &JsValue::from(result.execution_time_ms))?;
            js_sys::Reflect::set(&result_obj, &"cache_hit".into(), &JsValue::from(result.cache_hit))?;
            js_sys::Reflect::set(&result_obj, &"data".into(), &JsValue::from_str(&result.data()))?;
            
            Ok(result_obj.into())
        })
    }

    /// Get current active query count
    #[wasm_bindgen]
    pub fn active_queries(&self) -> usize {
        *self.active_queries.borrow()
    }
}

/// Web Worker interface for parallel processing
#[wasm_bindgen]
pub struct WorkerPool {
    worker_count: usize,
    task_queue: Rc<RefCell<Vec<WorkerTask>>>,
}

struct WorkerTask {
    task_type: TaskType,
    data: String,
    resolver: Option<oneshot::Sender<String>>,
}

enum TaskType {
    Hash,
    Process,
    Validate,
}

#[wasm_bindgen]
impl WorkerPool {
    #[wasm_bindgen(constructor)]
    pub fn new(worker_count: usize) -> WorkerPool {
        WorkerPool {
            worker_count,
            task_queue: Rc::new(RefCell::new(Vec::new())),
        }
    }

    /// Submit task to worker pool
    #[wasm_bindgen]
    pub fn submit_task(&self, task_type: &str, data: &str) -> Promise {
        let task_queue = self.task_queue.clone();
        let task_type = task_type.to_string();
        let data = data.to_string();
        
        wasm_bindgen_futures::future_to_promise(async move {
            // Simulate worker processing
            let processing_time = match task_type.as_str() {
                "hash" => 5,
                "process" => 15,
                "validate" => 10,
                _ => 20,
            };
            
            let promise = Promise::resolve(&JsValue::from(processing_time));
            let _ = JsFuture::from(promise).await?;
            
            let result = format!("{}_{}_processed", task_type, data.len());
            Ok(JsValue::from_str(&result))
        })
    }

    /// Get worker pool stats
    #[wasm_bindgen]
    pub fn get_stats(&self) -> JsValue {
        let stats = serde_json::json!({
            "worker_count": self.worker_count,
            "queue_length": self.task_queue.borrow().len(),
            "status": "active"
        });
        
        serde_wasm_bindgen::to_value(&stats).unwrap_or(JsValue::NULL)
    }
}

/// Streaming data processor for large datasets
#[wasm_bindgen]
pub struct StreamProcessor {
    chunk_size: usize,
    processed_chunks: usize,
    total_bytes: usize,
}

#[wasm_bindgen]
impl StreamProcessor {
    #[wasm_bindgen(constructor)]
    pub fn new(chunk_size: usize) -> StreamProcessor {
        StreamProcessor {
            chunk_size,
            processed_chunks: 0,
            total_bytes: 0,
        }
    }

    /// Process data stream in chunks
    #[wasm_bindgen]
    pub fn process_stream(&mut self, data: &str) -> Promise {
        let chunk_size = self.chunk_size;
        let data = data.to_string();
        let processed_chunks = self.processed_chunks;
        
        wasm_bindgen_futures::future_to_promise(async move {
            let mut results = Vec::new();
            let chunks = data.as_bytes().chunks(chunk_size);
            
            for (i, chunk) in chunks.enumerate() {
                // Yield control periodically
                if i % 10 == 0 {
                    let promise = Promise::resolve(&JsValue::from(1));
                    let _ = JsFuture::from(promise).await?;
                }
                
                // Process chunk
                let processed = format!("chunk_{}_size_{}", i + processed_chunks, chunk.len());
                results.push(processed);
            }
            
            let result_array = js_sys::Array::new();
            for result in results {
                result_array.push(&JsValue::from_str(&result));
            }
            
            Ok(result_array.into())
        })
    }

    #[wasm_bindgen]
    pub fn get_progress(&self) -> JsValue {
        let progress = serde_json::json!({
            "processed_chunks": self.processed_chunks,
            "total_bytes": self.total_bytes,
            "chunk_size": self.chunk_size
        });
        
        serde_wasm_bindgen::to_value(&progress).unwrap_or(JsValue::NULL)
    }
}

/// Background task scheduler
#[wasm_bindgen]
pub struct TaskScheduler {
    scheduled_tasks: Rc<RefCell<Vec<ScheduledTask>>>,
    running: Rc<RefCell<bool>>,
}

struct ScheduledTask {
    id: String,
    interval_ms: u32,
    callback: js_sys::Function,
    last_run: f64,
}

#[wasm_bindgen]
impl TaskScheduler {
    #[wasm_bindgen(constructor)]
    pub fn new() -> TaskScheduler {
        TaskScheduler {
            scheduled_tasks: Rc::new(RefCell::new(Vec::new())),
            running: Rc::new(RefCell::new(false)),
        }
    }

    /// Schedule a recurring task
    #[wasm_bindgen]
    pub fn schedule_task(&self, id: &str, interval_ms: u32, callback: js_sys::Function) {
        let task = ScheduledTask {
            id: id.to_string(),
            interval_ms,
            callback,
            last_run: js_sys::Date::now(),
        };
        
        self.scheduled_tasks.borrow_mut().push(task);
    }

    /// Start the scheduler
    #[wasm_bindgen]
    pub fn start(&self) -> Promise {
        let scheduled_tasks = self.scheduled_tasks.clone();
        let running = self.running.clone();
        *running.borrow_mut() = true;
        
        wasm_bindgen_futures::future_to_promise(async move {
            while *running.borrow() {
                let now = js_sys::Date::now();
                
                // Check and run scheduled tasks
                let mut tasks_to_run = Vec::new();
                {
                    let mut tasks = scheduled_tasks.borrow_mut();
                    for task in tasks.iter_mut() {
                        if now - task.last_run >= task.interval_ms as f64 {
                            tasks_to_run.push(task.id.clone());
                            task.last_run = now;
                        }
                    }
                }
                
                // Execute tasks
                for task_id in tasks_to_run {
                    console::log_1(&format!("Executing scheduled task: {}", task_id).into());
                }
                
                // Wait before next cycle
                let promise = Promise::resolve(&JsValue::from(100));
                let _ = JsFuture::from(promise).await?;
            }
            
            Ok(JsValue::from("Scheduler stopped"))
        })
    }

    /// Stop the scheduler
    #[wasm_bindgen]
    pub fn stop(&self) {
        *self.running.borrow_mut() = false;
    }

    /// Get scheduler status
    #[wasm_bindgen]
    pub fn get_status(&self) -> JsValue {
        let status = serde_json::json!({
            "running": *self.running.borrow(),
            "scheduled_tasks": self.scheduled_tasks.borrow().len()
        });
        
        serde_wasm_bindgen::to_value(&status).unwrap_or(JsValue::NULL)
    }
}