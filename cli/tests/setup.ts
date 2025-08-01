/**
 * Jest test setup
 */

// Mock console methods to reduce noise in tests
global.console = {
  ...console,
  log: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
};

// Mock process.exit
const mockExit = jest.fn();
process.exit = mockExit as any;

// Reset mocks before each test
beforeEach(() => {
  jest.clearAllMocks();
  mockExit.mockClear();
});