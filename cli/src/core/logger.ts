/**
 * Logger configuration for FACT CLI
 */

import winston from 'winston';
import { join } from 'path';
import { ensureDirSync } from 'fs-extra';

// Ensure logs directory exists
const logsDir = join(process.cwd(), 'logs');
ensureDirSync(logsDir);

// Custom format for console output
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: 'HH:mm:ss' }),
  winston.format.colorize(),
  winston.format.printf(({ level, message, timestamp, label }) => {
    const labelStr = label ? `[${label}] ` : '';
    return `${timestamp} ${level}: ${labelStr}${message}`;
  })
);

// Custom format for file output
const fileFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

// Create the main logger
const mainLogger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: fileFormat,
  defaultMeta: { service: 'fact-cli' },
  transports: [
    // Error log file
    new winston.transports.File({
      filename: join(logsDir, 'error.log'),
      level: 'error',
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 5,
    }),
    
    // Combined log file
    new winston.transports.File({
      filename: join(logsDir, 'combined.log'),
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 5,
    }),
  ],
});

// Add console transport in development or when DEBUG is set
if (process.env.NODE_ENV !== 'production' || process.env.DEBUG) {
  mainLogger.add(new winston.transports.Console({
    format: consoleFormat,
    level: process.env.DEBUG ? 'debug' : 'info',
  }));
}

// Create labeled loggers for different components
export function createLogger(label: string): winston.Logger {
  return mainLogger.child({ label });
}

// Export the main logger as well
export { mainLogger as logger };

// Performance logging helper
export function logPerformance(label: string, startTime: number, additionalData?: any): void {
  const duration = Date.now() - startTime;
  const logger = createLogger('performance');
  
  logger.info(`${label} completed in ${duration}ms`, {
    duration,
    ...additionalData,
  });
}