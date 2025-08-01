/**
 * Performance Monitor for FACT CLI
 */

import { createLogger } from './logger';

const logger = createLogger('performance');

export interface PerformanceMetrics {
  processingTime: number;
  memoryUsed: number;
  cacheHit?: boolean;
}

export interface SystemMetrics {
  cpu: {
    usage: number;
    loadAverage: number[];
  };
  memory: {
    total: number;
    used: number;
    free: number;
    percentage: number;
  };
  uptime: number;
  processCount: number;
}

export class PerformanceMonitor {
  private processingMetrics: PerformanceMetrics[] = [];
  private maxMetricsHistory = 1000;
  private systemMetricsInterval?: NodeJS.Timeout;
  private isInitialized = false;

  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    logger.info('Initializing performance monitor');

    // Start collecting system metrics every 30 seconds
    this.systemMetricsInterval = setInterval(() => {
      this.collectSystemMetrics();
    }, 30000);

    this.isInitialized = true;
    logger.info('Performance monitor initialized');
  }

  recordProcessing(metrics: PerformanceMetrics): void {
    this.processingMetrics.push({
      ...metrics,
      // Add timestamp for tracking
      timestamp: Date.now(),
    } as any);

    // Keep only the most recent metrics
    if (this.processingMetrics.length > this.maxMetricsHistory) {
      this.processingMetrics = this.processingMetrics.slice(-this.maxMetricsHistory);
    }

    logger.debug('Processing metrics recorded:', metrics);
  }

  getMetrics(): {
    processing: {
      total: number;
      average: {
        processingTime: number;
        memoryUsed: number;
      };
      recent: PerformanceMetrics[];
      cacheHitRate?: number;
    };
    system: SystemMetrics;
  } {
    const processing = this.getProcessingMetrics();
    const system = this.getSystemMetrics();

    return {
      processing,
      system,
    };
  }

  private getProcessingMetrics() {
    if (this.processingMetrics.length === 0) {
      return {
        total: 0,
        average: {
          processingTime: 0,
          memoryUsed: 0,
        },
        recent: [],
      };
    }

    const totalProcessingTime = this.processingMetrics.reduce(
      (sum, metric) => sum + metric.processingTime,
      0
    );
    const totalMemoryUsed = this.processingMetrics.reduce(
      (sum, metric) => sum + metric.memoryUsed,
      0
    );

    const cacheHits = this.processingMetrics.filter(
      (metric) => metric.cacheHit === true
    ).length;
    const cacheHitRate = cacheHits > 0 ? (cacheHits / this.processingMetrics.length) * 100 : undefined;

    // Get recent metrics (last 10)
    const recent = this.processingMetrics.slice(-10);

    return {
      total: this.processingMetrics.length,
      average: {
        processingTime: totalProcessingTime / this.processingMetrics.length,
        memoryUsed: totalMemoryUsed / this.processingMetrics.length,
      },
      recent,
      cacheHitRate,
    };
  }

  private getSystemMetrics(): SystemMetrics {
    const memoryUsage = process.memoryUsage();
    const cpuUsage = process.cpuUsage();

    return {
      cpu: {
        usage: (cpuUsage.user + cpuUsage.system) / 1000000, // Convert to seconds
        loadAverage: require('os').loadavg(),
      },
      memory: {
        total: require('os').totalmem(),
        used: memoryUsage.rss,
        free: require('os').freemem(),
        percentage: (memoryUsage.rss / require('os').totalmem()) * 100,
      },
      uptime: process.uptime(),
      processCount: 1, // Single process for now
    };
  }

  private collectSystemMetrics(): void {
    const metrics = this.getSystemMetrics();
    
    // Log warnings if resources are running low
    if (metrics.memory.percentage > 80) {
      logger.warn(`High memory usage: ${metrics.memory.percentage.toFixed(1)}%`);
    }

    if (metrics.cpu.loadAverage[0] > require('os').cpus().length) {
      logger.warn(`High CPU load: ${metrics.cpu.loadAverage[0].toFixed(2)}`);
    }

    logger.debug('System metrics collected:', {
      memoryUsage: `${metrics.memory.percentage.toFixed(1)}%`,
      cpuLoad: metrics.cpu.loadAverage[0].toFixed(2),
      uptime: `${(metrics.uptime / 3600).toFixed(1)}h`,
    });
  }

  clearMetrics(): void {
    this.processingMetrics = [];
    logger.info('Performance metrics cleared');
  }

  exportMetrics(): any {
    return {
      timestamp: new Date().toISOString(),
      metrics: this.getMetrics(),
      configuration: {
        maxMetricsHistory: this.maxMetricsHistory,
        isInitialized: this.isInitialized,
      },
    };
  }

  shutdown(): void {
    if (this.systemMetricsInterval) {
      clearInterval(this.systemMetricsInterval);
      this.systemMetricsInterval = undefined;
    }

    this.isInitialized = false;
    logger.info('Performance monitor shutdown');
  }
}