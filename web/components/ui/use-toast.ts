'use client';

import { useEffect, useState } from 'react';

export type ToastVariant = 'default' | 'destructive';

export type ToastItem = {
  id: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
};

type ToastState = {
  toasts: ToastItem[];
};

type Listener = (state: ToastState) => void;

let memoryState: ToastState = { toasts: [] };
const listeners = new Set<Listener>();

function emit() {
  listeners.forEach((l) => l(memoryState));
}

function uid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function toast(input: Omit<ToastItem, 'id'> & { id?: string }) {
  const id = input.id || uid();
  const item: ToastItem = { ...input, id };
  memoryState = { toasts: [item, ...memoryState.toasts].slice(0, 5) };
  emit();

  // Auto-dismiss.
  window.setTimeout(() => dismiss(id), 4200);

  return { id };
}

export function dismiss(id: string) {
  memoryState = { toasts: memoryState.toasts.filter((t) => t.id !== id) };
  emit();
}

export function useToast() {
  const [state, setState] = useState<ToastState>(memoryState);

  useEffect(() => {
    listeners.add(setState);
    return () => {
      listeners.delete(setState);
    };
  }, []);

  return {
    toasts: state.toasts,
    toast,
    dismiss,
  };
}

