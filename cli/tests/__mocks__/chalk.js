/**
 * Mock for chalk module
 */

const mockChalk = {
  red: (text) => text,
  green: (text) => text,
  blue: (text) => text,
  yellow: (text) => text,
  cyan: (text) => text,
  gray: (text) => text,
  grey: (text) => text,
  bold: (text) => text,
};

// Add nested properties
mockChalk.red.bold = (text) => text;
mockChalk.green.bold = (text) => text;
mockChalk.blue.bold = (text) => text;
mockChalk.yellow.bold = (text) => text;

module.exports = mockChalk;