/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/tests'],
  testMatch: [
    '**/__tests__/**/*.ts',
    '**/?(*.)+(spec|test).ts'
  ],
  transform: {
    '^.+\\.ts$': 'ts-jest'
  },
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/types/**/*',
    '!src/index.ts'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: [
    'text',
    'lcov',
    'html'
  ],
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1'
  },
  testTimeout: 10000,
  verbose: true,
  clearMocks: true,
  restoreMocks: true,
  
  // Handle WASM and binary files
  moduleFileExtensions: ['ts', 'js', 'json', 'wasm'],
  transform: {
    '^.+\\.ts$': 'ts-jest',
    '\\.(wasm)$': '<rootDir>/tests/__mocks__/fileMock.js'
  },
  
  // Mock external dependencies
  moduleNameMapping: {
    '^ws$': '<rootDir>/tests/__mocks__/ws.js',
    '^chalk$': '<rootDir>/tests/__mocks__/chalk.js'
  }
};