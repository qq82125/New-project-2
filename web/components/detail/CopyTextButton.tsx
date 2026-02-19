'use client';

import { Button } from '../ui/button';
import { toast } from '../ui/use-toast';

async function copyText(value: string): Promise<boolean> {
  const text = String(value || '').trim();
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export default function CopyTextButton({ value }: { value: string }) {
  return (
    <Button
      type="button"
      size="sm"
      variant="ghost"
      onClick={async () => {
        const ok = await copyText(value);
        if (ok) toast({ title: '已复制', description: value });
        else toast({ variant: 'destructive', title: '复制失败', description: '浏览器不支持或权限受限' });
      }}
    >
      复制
    </Button>
  );
}
