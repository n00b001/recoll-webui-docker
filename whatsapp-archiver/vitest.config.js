import { defineConfig } from 'vitest/config'
import os from 'os'

// Run tests with min(4, cpu_count * 2) threads
const cpuCount = os.cpus().length
const maxThreads = Math.min(4, cpuCount * 2)

export default defineConfig({
  test: {
    // Parallel execution (Vitest 4: poolOptions are top-level)
    threads: true,
    maxThreads,
    // Coverage via v8 + 80% thresholds (lines AND branches)
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json'],
      reportsDirectory: './coverage',
      include: ['lib.js'],
      exclude: ['node_modules/**', 'coverage/**', '**/*.test.*', 'index.js'],
      thresholds: {
        lines: 80,
        branches: 80,
        functions: 80,
      },
    },
  },
})
