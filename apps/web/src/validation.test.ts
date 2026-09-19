import { describe, expect, it } from 'vitest';
import { parseNumber, validatePositive, validatePositiveInt } from './validation';

describe('parseNumber', () => {
  it('parses a valid numeric string', () => {
    expect(parseNumber('42.5')).toBe(42.5);
  });
  it('returns null for a blank string', () => {
    expect(parseNumber('  ')).toBeNull();
  });
  it('returns null for a non-numeric string', () => {
    expect(parseNumber('abc')).toBeNull();
  });
});

describe('validatePositive', () => {
  it('rejects zero', () => {
    expect(validatePositive('0', 'GVWR')).toMatch(/greater than zero/);
  });
  it('rejects a negative value', () => {
    expect(validatePositive('-100', 'GVWR')).toMatch(/greater than zero/);
  });
  it('accepts a positive value', () => {
    expect(validatePositive('9500', 'GVWR')).toBeNull();
  });
  it('requires a value by default', () => {
    expect(validatePositive('', 'GVWR')).toMatch(/required/);
  });
  it('allows blank when not required', () => {
    expect(validatePositive('', 'GCWR', false)).toBeNull();
  });
});

describe('validatePositiveInt', () => {
  it('rejects a non-integer', () => {
    expect(validatePositiveInt('2.5', 'Axle Count')).toMatch(/whole number/);
  });
  it('accepts a positive integer', () => {
    expect(validatePositiveInt('2', 'Axle Count')).toBeNull();
  });
  it('rejects zero', () => {
    expect(validatePositiveInt('0', 'Axle Count')).toMatch(/greater than zero/);
  });
});
