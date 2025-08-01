/**
 * Core module exports
 */

export { FactEngine } from './engine';
export { ConfigManager } from './config-manager';
export { PerformanceMonitor } from './performance-monitor';
export { ErrorHandler } from './error-handler';
export { createLogger, logger, logPerformance } from './logger';

export type { Template, ProcessingContext, ProcessingResult } from './engine';
export type { FactConfig } from './config-manager';
export type { PerformanceMetrics, SystemMetrics } from './performance-monitor';
export type { ErrorContext } from './error-handler';