/**
 * Commands initialization and exports
 */

import { Command } from 'commander';
import { FactEngine } from '../core/engine';
import { WasmLoader } from '../wasm/loader';

import { initProcessCommand } from './process';
import { initTemplateCommands } from './template';
import { initMcpCommands } from './mcp';
import { initBenchmarkCommands } from './benchmark';
import { initConfigCommands } from './config';

export function initializeCommands(
  program: Command,
  engine: FactEngine | null,
  wasmLoader: WasmLoader
): void {
  // Initialize all command groups
  initProcessCommand(program, engine, wasmLoader);
  initTemplateCommands(program, engine, wasmLoader);
  initMcpCommands(program, engine, wasmLoader);
  initBenchmarkCommands(program, engine, wasmLoader);
  initConfigCommands(program, engine, wasmLoader);
}

export * from './process';
export * from './template';
export * from './mcp';
export * from './benchmark';
export * from './config';