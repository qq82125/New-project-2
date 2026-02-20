'use client';

import { useState } from 'react';
import { Button } from '../ui/button';
import { toast } from '../ui/use-toast';

export default function CopyButton({
  text,
  label = '复制链接',
  successDescription = '内容已复制到剪贴板',
  errorDescription = '请手动复制',
  size = 'md',
  variant = 'secondary',
}: {
  text: string;
  label?: string;
  successDescription?: string;
  errorDescription?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'secondary' | 'ghost' | 'destructive';
}) {
  const [busy, setBusy] = useState(false);

  async function onCopy() {
    if (busy) return;
    setBusy(true);
    try {
      await navigator.clipboard.writeText(text);
      toast({ title: '已复制', description: successDescription });
    } catch {
      toast({ variant: 'destructive', title: '复制失败', description: errorDescription });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button type="button" variant={variant} size={size} onClick={onCopy} disabled={busy}>
      {busy ? '复制中…' : label}
    </Button>
  );
}
