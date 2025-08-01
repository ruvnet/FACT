/**
 * Benchmark commands - Performance testing functionality
 */

import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import { FactEngine } from '../core/engine';
import { WasmLoader } from '../wasm/loader';
import { createLogger } from '../core/logger';

const logger = createLogger('cmd-benchmark');

interface BenchmarkResult {
  operation: string;
  iterations: number;
  totalTime: number;
  averageTime: number;
  minTime: number;
  maxTime: number;
  throughput: number;
  memoryUsage: {
    before: number;
    after: number;
    peak: number;
  };
}

export function initBenchmarkCommands(
  program: Command,
  engine: FactEngine | null,
  wasmLoader: WasmLoader
): void {
  const benchmarkCmd = program
    .command('benchmark')
    .alias('bench')
    .description('Performance benchmarking commands');

  // Run benchmarks
  benchmarkCmd
    .command('run')
    .alias('r')
    .description('Run performance benchmarks')
    .option('-i, --iterations <count>', 'Number of iterations', '100')
    .option('-t, --test <type>', 'Benchmark type (wasm, template, engine, all)', 'all')
    .option('-o, --output <path>', 'Save results to file')
    .option('--format <type>', 'Output format (json, table, csv)', 'table')
    .option('--warmup <count>', 'Warmup iterations', '10')
    .action(async (options) => {
      const spinner = ora('Running benchmarks...').start();
      const results: BenchmarkResult[] = [];
      
      try {
        if (!engine || !wasmLoader.isReady()) {
          throw new Error('Engine or WASM not initialized');
        }

        const iterations = parseInt(options.iterations);
        const warmupIterations = parseInt(options.warmup);
        const testType = options.test;

        // Warmup
        if (warmupIterations > 0) {
          spinner.text = 'Warming up...';
          await runWarmup(engine, wasmLoader, warmupIterations);
        }

        // Run benchmarks based on type
        if (testType === 'wasm' || testType === 'all') {
          spinner.text = 'Benchmarking WASM operations...';
          const wasmResult = await benchmarkWasm(wasmLoader, iterations);
          results.push(wasmResult);
        }

        if (testType === 'template' || testType === 'all') {
          spinner.text = 'Benchmarking template processing...';
          const templateResult = await benchmarkTemplateProcessing(engine, iterations);
          results.push(templateResult);
        }

        if (testType === 'engine' || testType === 'all') {
          spinner.text = 'Benchmarking engine operations...';
          const engineResults = await benchmarkEngine(engine, iterations);
          results.push(...engineResults);
        }

        spinner.stop();

        // Display results
        console.log(chalk.green.bold('✅ Benchmarks completed!'));
        console.log();

        if (options.format === 'json') {
          console.log(JSON.stringify(results, null, 2));
        } else if (options.format === 'csv') {
          displayCsvResults(results);
        } else {
          displayTableResults(results);
        }

        // Save to file if requested
        if (options.output) {
          const { writeFile } = require('fs-extra');
          const timestamp = new Date().toISOString();
          
          const output = {
            timestamp,
            iterations,
            results,
            system: {
              platform: process.platform,
              arch: process.arch,
              nodeVersion: process.version,
              memory: process.memoryUsage(),
            }
          };

          await writeFile(options.output, JSON.stringify(output, null, 2));
          console.log(chalk.blue(`\n💾 Results saved to: ${options.output}`));
        }

      } catch (error) {
        spinner.stop();
        console.error(chalk.red.bold('❌ Benchmark failed:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Compare benchmarks
  benchmarkCmd
    .command('compare')
    .alias('c')
    .description('Compare benchmark results')
    .argument('<file1>', 'First benchmark file')
    .argument('<file2>', 'Second benchmark file')
    .action(async (file1, file2) => {
      try {
        const { readFile } = require('fs-extra');
        
        const data1 = JSON.parse(await readFile(file1, 'utf8'));
        const data2 = JSON.parse(await readFile(file2, 'utf8'));

        console.log(chalk.blue.bold('📊 Benchmark Comparison:'));
        console.log();
        
        console.log(chalk.cyan(`File 1: ${file1} (${data1.timestamp})`));
        console.log(chalk.cyan(`File 2: ${file2} (${data2.timestamp})`));
        console.log();

        // Compare results
        const comparison = compareResults(data1.results, data2.results);
        displayComparison(comparison);

      } catch (error) {
        console.error(chalk.red.bold('❌ Comparison failed:'));
        console.error(chalk.red(error instanceof Error ? error.message : String(error)));
        process.exit(1);
      }
    });

  // Profile memory
  benchmarkCmd
    .command('profile')
    .alias('p')
    .description('Profile memory usage during operations')
    .option('-d, --duration <seconds>', 'Profiling duration', '60')
    .option('-i, --interval <ms>', 'Sampling interval', '1000')
    .action(async (options) => {
      const duration = parseInt(options.duration) * 1000;
      const interval = parseInt(options.interval);
      
      console.log(chalk.blue.bold('🔍 Starting memory profiling...'));
      console.log(chalk.gray(`Duration: ${duration / 1000}s, Interval: ${interval}ms`));
      console.log();

      const samples: Array<{
        timestamp: number;
        memory: NodeJS.MemoryUsage;
      }> = [];

      const startTime = Date.now();
      const profileInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        
        if (elapsed >= duration) {
          clearInterval(profileInterval);
          displayMemoryProfile(samples);
          return;
        }

        samples.push({
          timestamp: elapsed,
          memory: process.memoryUsage(),
        });

        // Display current stats
        const current = samples[samples.length - 1];
        const mb = (bytes: number) => (bytes / 1024 / 1024).toFixed(2);
        
        process.stdout.write(`\r${chalk.blue('Memory:')} RSS: ${mb(current.memory.rss)}MB, Heap: ${mb(current.memory.heapUsed)}MB, External: ${mb(current.memory.external)}MB`);
        
      }, interval);
    });
}

async function runWarmup(engine: FactEngine, wasmLoader: WasmLoader, iterations: number): Promise<void> {
  for (let i = 0; i < iterations; i++) {
    try {
      await engine.analyzeContext({ test: `warmup-${i}` });
    } catch {
      // Ignore warmup errors
    }
  }
}

async function benchmarkWasm(wasmLoader: WasmLoader, iterations: number): Promise<BenchmarkResult> {
  const wasm = wasmLoader.getWasm();
  const times: number[] = [];
  const memoryBefore = process.memoryUsage().heapUsed;
  let memoryPeak = memoryBefore;

  for (let i = 0; i < iterations; i++) {
    const start = Date.now();
    
    try {
      wasm.analyze_context(JSON.stringify({ test: `iteration-${i}` }));
    } catch {
      // Some WASM functions might not be fully implemented
    }
    
    const end = Date.now();
    times.push(end - start);
    
    const currentMemory = process.memoryUsage().heapUsed;
    if (currentMemory > memoryPeak) {
      memoryPeak = currentMemory;
    }
  }

  const memoryAfter = process.memoryUsage().heapUsed;
  const totalTime = times.reduce((sum, time) => sum + time, 0);

  return {
    operation: 'WASM Context Analysis',
    iterations,
    totalTime,
    averageTime: totalTime / iterations,
    minTime: Math.min(...times),
    maxTime: Math.max(...times),
    throughput: iterations / (totalTime / 1000),
    memoryUsage: {
      before: memoryBefore,
      after: memoryAfter,
      peak: memoryPeak,
    }
  };
}

async function benchmarkTemplateProcessing(engine: FactEngine, iterations: number): Promise<BenchmarkResult> {
  const times: number[] = [];
  const memoryBefore = process.memoryUsage().heapUsed;
  let memoryPeak = memoryBefore;

  for (let i = 0; i < iterations; i++) {
    const start = Date.now();
    
    try {
      await engine.processTemplate({
        data: { test: `iteration-${i}`, value: Math.random() }
      });
    } catch {
      // Ignore processing errors for benchmarking
    }
    
    const end = Date.now();
    times.push(end - start);
    
    const currentMemory = process.memoryUsage().heapUsed;
    if (currentMemory > memoryPeak) {
      memoryPeak = currentMemory;
    }
  }

  const memoryAfter = process.memoryUsage().heapUsed;
  const totalTime = times.reduce((sum, time) => sum + time, 0);

  return {
    operation: 'Template Processing',
    iterations,
    totalTime,
    averageTime: totalTime / iterations,
    minTime: Math.min(...times),
    maxTime: Math.max(...times),
    throughput: iterations / (totalTime / 1000),
    memoryUsage: {
      before: memoryBefore,
      after: memoryAfter,
      peak: memoryPeak,
    }
  };
}

async function benchmarkEngine(engine: FactEngine, iterations: number): Promise<BenchmarkResult[]> {
  const results: BenchmarkResult[] = [];

  // Benchmark context analysis
  const analysisTimes: number[] = [];
  const memoryBefore = process.memoryUsage().heapUsed;
  let memoryPeak = memoryBefore;

  for (let i = 0; i < iterations; i++) {
    const start = Date.now();
    
    try {
      await engine.analyzeContext({ test: `analysis-${i}`, complexity: i % 10 });
    } catch {
      // Ignore errors
    }
    
    const end = Date.now();
    analysisTimes.push(end - start);
    
    const currentMemory = process.memoryUsage().heapUsed;
    if (currentMemory > memoryPeak) {
      memoryPeak = currentMemory;
    }
  }

  const totalAnalysisTime = analysisTimes.reduce((sum, time) => sum + time, 0);
  const memoryAfter = process.memoryUsage().heapUsed;

  results.push({
    operation: 'Context Analysis',
    iterations,
    totalTime: totalAnalysisTime,
    averageTime: totalAnalysisTime / iterations,
    minTime: Math.min(...analysisTimes),
    maxTime: Math.max(...analysisTimes),
    throughput: iterations / (totalAnalysisTime / 1000),
    memoryUsage: {
      before: memoryBefore,
      after: memoryAfter,
      peak: memoryPeak,
    }
  });

  return results;
}

function displayTableResults(results: BenchmarkResult[]): void {
  console.log(chalk.blue.bold('📊 Benchmark Results:'));
  console.log();

  results.forEach((result, index) => {
    console.log(chalk.cyan(`${index + 1}. ${result.operation}`));
    console.log(chalk.gray(`   Iterations: ${result.iterations}`));
    console.log(chalk.gray(`   Total time: ${result.totalTime}ms`));
    console.log(chalk.gray(`   Average time: ${result.averageTime.toFixed(2)}ms`));
    console.log(chalk.gray(`   Min time: ${result.minTime}ms`));
    console.log(chalk.gray(`   Max time: ${result.maxTime}ms`));
    console.log(chalk.gray(`   Throughput: ${result.throughput.toFixed(2)} ops/sec`));
    console.log(chalk.gray(`   Memory delta: ${((result.memoryUsage.after - result.memoryUsage.before) / 1024 / 1024).toFixed(2)}MB`));
    console.log();
  });
}

function displayCsvResults(results: BenchmarkResult[]): void {
  console.log('Operation,Iterations,TotalTime,AverageTime,MinTime,MaxTime,Throughput,MemoryDelta');
  results.forEach(result => {
    const memoryDelta = (result.memoryUsage.after - result.memoryUsage.before) / 1024 / 1024;
    console.log(`"${result.operation}",${result.iterations},${result.totalTime},${result.averageTime.toFixed(2)},${result.minTime},${result.maxTime},${result.throughput.toFixed(2)},${memoryDelta.toFixed(2)}`);
  });
}

function compareResults(results1: BenchmarkResult[], results2: BenchmarkResult[]): any {
  const comparison: any = {};
  
  results1.forEach(result1 => {
    const result2 = results2.find(r => r.operation === result1.operation);
    if (result2) {
      const improvement = ((result2.averageTime - result1.averageTime) / result1.averageTime) * 100;
      comparison[result1.operation] = {
        before: result1.averageTime,
        after: result2.averageTime,
        improvement: improvement,
        isImprovement: improvement < 0
      };
    }
  });
  
  return comparison;
}

function displayComparison(comparison: any): void {
  Object.entries(comparison).forEach(([operation, data]: [string, any]) => {
    const color = data.isImprovement ? chalk.green : chalk.red;
    const symbol = data.isImprovement ? '↓' : '↑';
    const improvementText = data.isImprovement ? 'faster' : 'slower';
    
    console.log(chalk.cyan(`${operation}:`));
    console.log(chalk.gray(`  Before: ${data.before.toFixed(2)}ms`));
    console.log(chalk.gray(`  After: ${data.after.toFixed(2)}ms`));
    console.log(color(`  ${symbol} ${Math.abs(data.improvement).toFixed(2)}% ${improvementText}`));
    console.log();
  });
}

function displayMemoryProfile(samples: Array<{ timestamp: number; memory: NodeJS.MemoryUsage }>): void {
  console.log('\n');
  console.log(chalk.blue.bold('📈 Memory Profile Summary:'));
  console.log();
  
  const mb = (bytes: number) => (bytes / 1024 / 1024).toFixed(2);
  const initial = samples[0];
  const final = samples[samples.length - 1];
  
  console.log(chalk.cyan('Initial Memory:'));
  console.log(chalk.gray(`  RSS: ${mb(initial.memory.rss)}MB`));
  console.log(chalk.gray(`  Heap Used: ${mb(initial.memory.heapUsed)}MB`));
  console.log(chalk.gray(`  External: ${mb(initial.memory.external)}MB`));
  console.log();
  
  console.log(chalk.cyan('Final Memory:'));
  console.log(chalk.gray(`  RSS: ${mb(final.memory.rss)}MB`));
  console.log(chalk.gray(`  Heap Used: ${mb(final.memory.heapUsed)}MB`));
  console.log(chalk.gray(`  External: ${mb(final.memory.external)}MB`));
  console.log();
  
  const rssDelta = final.memory.rss - initial.memory.rss;
  const heapDelta = final.memory.heapUsed - initial.memory.heapUsed;
  
  console.log(chalk.cyan('Memory Delta:'));
  console.log(chalk.gray(`  RSS: ${rssDelta > 0 ? '+' : ''}${mb(rssDelta)}MB`));
  console.log(chalk.gray(`  Heap: ${heapDelta > 0 ? '+' : ''}${mb(heapDelta)}MB`));
}