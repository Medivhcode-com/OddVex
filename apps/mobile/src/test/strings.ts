import { screen } from '@testing-library/react-native';

type Json = null | string | { props?: Record<string, unknown>; children?: Json[] | null } | Json[];

function collect(node: Json, into: string[]): void {
  if (node === null || node === undefined) return;
  if (typeof node === 'string') {
    into.push(node);
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((child) => collect(child, into));
    return;
  }
  for (const key of ['accessibilityLabel', 'accessibilityHint', 'placeholder', 'aria-label']) {
    const value = node.props?.[key];
    if (typeof value === 'string') into.push(value);
  }
  node.children?.forEach((child) => collect(child, into));
}

/** Every string on the screen: visible text plus accessibility labels and hints. */
export function screenStrings(): string[] {
  const strings: string[] = [];
  collect(screen.toJSON() as Json, strings);
  return strings;
}
