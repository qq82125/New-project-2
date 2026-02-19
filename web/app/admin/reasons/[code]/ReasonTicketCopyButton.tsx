'use client';

import { Button } from '../../../../components/ui/button';
import { toast } from '../../../../components/ui/use-toast';

export default function ReasonTicketCopyButton({ text }: { text: string }) {
  return (
    <Button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          toast({ title: '已复制', description: '已复制工单文本' });
        } catch {
          toast({ variant: 'destructive', title: '复制失败', description: '浏览器不支持或权限受限' });
        }
      }}
    >
      复制工单文本
    </Button>
  );
}
