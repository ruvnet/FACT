use criterion::{black_box, criterion_group, criterion_main, Criterion};
use fact_wasm_core::{FastCache, QueryProcessor};

fn cache_insertion_benchmark(c: &mut Criterion) {
    c.bench_function("cache_insert_1000", |b| {
        b.iter(|| {
            let mut cache = FastCache::new(1000);
            for i in 0..1000 {
                let key = format!("key_{}", i);
                let data = format!("data_value_{}", i);
                cache.set(black_box(&key), black_box(&data), 60000);
            }
        })
    });
}

fn cache_retrieval_benchmark(c: &mut Criterion) {
    let mut cache = FastCache::new(1000);
    // Pre-populate cache
    for i in 0..1000 {
        let key = format!("key_{}", i);
        let data = format!("data_value_{}", i);
        cache.set(&key, &data, 60000);
    }

    c.bench_function("cache_get_1000", |b| {
        b.iter(|| {
            for i in 0..1000 {
                let key = format!("key_{}", i);
                cache.get(black_box(&key));
            }
        })
    });
}

fn query_processing_benchmark(c: &mut Criterion) {
    c.bench_function("query_process_100", |b| {
        b.iter(|| {
            let mut processor = QueryProcessor::new();
            for i in 0..100 {
                let query = format!("SELECT * FROM table_{} WHERE id = {}", i % 10, i);
                processor.process_query(black_box(&query));
            }
        })
    });
}

criterion_group!(
    benches,
    cache_insertion_benchmark,
    cache_retrieval_benchmark,
    query_processing_benchmark
);
criterion_main!(benches);